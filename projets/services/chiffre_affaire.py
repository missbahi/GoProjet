import hashlib
import json
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from projets.decorators import peut_valider_directement
from projets.models import (
    ChiffreAffaire, LigneChiffreAffaire, Projet, RecetteSituationMensuelle, SituationMensuelle,
)


SALT = 'projets.ca.apercu'
CENTIME = Decimal('0.01')


def mois_voisin(periode, decalage):
    index = periode.year * 12 + periode.month - 1 + decalage
    annee, mois = divmod(index, 12)
    if not 1 <= annee <= 9999:
        raise ValidationError('Le mois dépasse la plage de dates autorisée.')
    return date(annee, mois + 1, 1)


def lignes_pour_ca(ca):
    from projets.views.lot_views.views import _est_ligne_titre_bordereau, _iter_lignes_bordereau_hierarchiques

    precedent = ChiffreAffaire.objects.filter(
        projet_id=ca.projet_id, periode=mois_voisin(ca.periode, -1),
    ).first()
    precedentes = {l.ligne_bordereau_id: l for l in precedent.lignes.all()} if precedent else {}
    existantes = {l.ligne_bordereau_id: l for l in ca.lignes.all()} if ca.pk else {}
    lignes = []
    bordereau = [] if ca.pk else _iter_lignes_bordereau_hierarchiques(ca.projet)
    for ordre, ligne in enumerate(bordereau):
        lignes.append({
            'id': ligne.id, 'numero': ligne.numero or '', 'designation': ligne.designation,
            'unite': ligne.unite or '', 'est_titre': _est_ligne_titre_bordereau(ligne),
            'niveau': ligne.level(), 'ordre': ordre,
            'quantite_marche': str(ligne.quantite or 0), 'prix_unitaire': str(ligne.pu or 0),
        })
    index = {l['id']: l for l in lignes}
    for source in (precedentes, existantes):
        for pk, ligne in source.items():
            if ca.pk and pk not in existantes:
                continue
            valeurs = {
                champ: getattr(ligne, champ) for champ in (
                    'numero', 'designation', 'unite', 'est_titre', 'niveau', 'ordre',
                    'quantite_marche', 'prix_unitaire',
                )
            }
            if pk not in index:
                index[pk] = {'id': pk}
                lignes.append(index[pk])
            index[pk].update(valeurs)
    for ligne in lignes:
        pk = ligne['id']
        existante = existantes.get(pk)
        precedente = precedentes.get(pk)
        ligne['cumul_initial'] = str(existante.cumul_initial if existante else 0)
        ligne['cumul_precedent'] = str(
            precedente.quantite_cumulee if precedente else (existante.cumul_initial if existante else 0)
        )
        ligne['quantite_cumulee'] = str(
            existante.quantite_cumulee if existante else (precedente.quantite_cumulee if precedente else 0)
        )
    return sorted(lignes, key=lambda l: (l['ordre'], l['id']))


def _quantite(valeur):
    try:
        quantite = Decimal(str(valeur))
    except (ValueError, TypeError, InvalidOperation) as error:
        raise ValidationError('Quantité invalide.') from error
    if not quantite.is_finite() or quantite < 0:
        raise ValidationError('Les cumuls doivent être des nombres positifs ou nuls.')
    LigneChiffreAffaire._meta.get_field('quantite_cumulee').clean(quantite, None)
    return quantite


def synchroniser_situation_ca(situation):
    """À appeler dans la transaction de sauvegarde de la situation ou du CA."""
    ca = ChiffreAffaire.objects.filter(
        projet_id=situation.projet_id, periode=date(situation.annee, situation.mois, 1),
        statut=ChiffreAffaire.Statut.VALIDE,
    ).first()
    if situation.ca_id:
        ca = ChiffreAffaire.objects.get(pk=situation.ca_id)
        if (ca.projet_id, ca.periode.year, ca.periode.month) != (
            situation.projet_id, situation.annee, situation.mois,
        ):
            raise ValidationError('Le mois de la situation liée au CA ne peut pas être déplacé.')
    if ca:
        if situation.est_validee:
            raise ValidationError('Dévalidez la situation avant de modifier ses recettes liées au CA.')
        situation.ca = ca
        RecetteSituationMensuelle.objects.update_or_create(
            situation=situation, rubrique=RecetteSituationMensuelle.Rubrique.TRAVAUX_REALISES,
            defaults={'montant': ca.montant_mensuel},
        )
        situation.chiffre_affaires = situation.recettes.aggregate(total=Sum('montant'))['total'] or Decimal('0')
        SituationMensuelle._meta.get_field('chiffre_affaires').clean(situation.chiffre_affaires, situation)
        situation.save(update_fields=['ca', 'chiffre_affaires', 'updated_at'])


@transaction.atomic
def enregistrer_ca(ca, donnees_lignes, user, *, action='enregistrer', confirmation=''):
    projet = Projet.objects.select_for_update().get(pk=ca.projet_id)
    if not peut_valider_directement(user, projet):
        raise ValidationError('Seuls le superutilisateur et le chef de projet autorisé peuvent gérer le CA.')
    chaine = list(ChiffreAffaire.objects.select_for_update().filter(projet=projet).order_by('periode'))
    anciennes_lignes = list(LigneChiffreAffaire.objects.select_for_update().filter(ca__projet=projet).order_by('pk'))
    situations = list(SituationMensuelle.objects.select_for_update().filter(projet=projet).order_by('pk'))
    recettes = list(RecetteSituationMensuelle.objects.select_for_update().filter(situation__projet=projet).order_by('pk'))
    ancien = next((a for a in chaine if a.pk == ca.pk), None)
    if ca.pk and ancien is None:
        raise ValidationError('Le CA a été supprimé. Rechargez la liste.')
    if ancien and (ancien.periode != ca.periode or ancien.origine != ca.origine):
        raise ValidationError("Le mois et l'origine d'un CA existant ne peuvent pas être modifiés.")
    if not ca.pk and any(a.periode == ca.periode for a in chaine):
        raise ValidationError('Un CA existe déjà pour ce mois.')
    precedent = next((a for a in chaine if a.periode == mois_voisin(ca.periode, -1)), None)
    suivant = next((a for a in chaine if a.periode == mois_voisin(ca.periode, 1)), None)
    if not ca.pk and chaine and ca.periode <= chaine[-1].periode:
        raise ValidationError('Créez les CA dans l’ordre des mois, après le dernier CA existant.')
    if chaine and (ancien is None or ancien != chaine[0]) and precedent is None:
        raise ValidationError('Le CA du mois précédent manque. Complétez le mois manquant.')
    if precedent and precedent.statut != ChiffreAffaire.Statut.VALIDE:
        raise ValidationError('Validez le CA du mois précédent avant de saisir le suivant.')
    if action not in {'enregistrer', 'valider', 'devalider'}:
        raise ValidationError('Action CA inconnue.')
    ca.statut = (
        ChiffreAffaire.Statut.BROUILLON if action == 'devalider'
        else ChiffreAffaire.Statut.VALIDE if action == 'valider' or ancien and ancien.statut == 'VALIDE'
        else ChiffreAffaire.Statut.BROUILLON
    )
    if action == 'devalider' and suivant:
        raise ValidationError('Un CA ayant un mois suivant ne peut pas être dévalidé.')
    ca.modifie_par = user
    if not ca.pk:
        ca.cree_par = user
    ca.full_clean()
    try:
        saisie = json.loads(donnees_lignes)
    except (TypeError, json.JSONDecodeError) as error:
        raise ValidationError('Le format des lignes CA est invalide.') from error
    if not isinstance(saisie, list) or not saisie:
        raise ValidationError('Le CA doit contenir les lignes du bordereau.')
    par_id = {}
    for ligne in saisie:
        if not isinstance(ligne, dict) or type(ligne.get('id')) is not int or ligne['id'] in par_id:
            raise ValidationError('Identifiants de lignes CA invalides ou dupliqués.')
        par_id[ligne['id']] = ligne
    references = lignes_pour_ca(ca)
    if set(par_id) != {l['id'] for l in references}:
        raise ValidationError('Les lignes du bordereau ont changé ou sont incomplètes. Rechargez la page.')
    nouvelles = []
    total = Decimal('0')
    regularisations = []
    for reference in references:
        pk = reference['id']
        cumul = _quantite(par_id[pk].get('quantite_cumulee'))
        initial = _quantite(par_id[pk].get('cumul_initial', 0))
        if precedent or ca.origine != ChiffreAffaire.Origine.REPRISE:
            if initial:
                raise ValidationError('Le cumul initial est réservé à la reprise du premier CA.')
            initial = Decimal('0')
        avant = Decimal(str(reference['cumul_precedent'])) if precedent else initial
        if reference['est_titre']:
            cumul = initial = avant = Decimal('0')
        partielle = cumul - avant
        montant = partielle * Decimal(str(reference['prix_unitaire']))
        total += montant
        if partielle < 0:
            regularisations.append(str(reference['numero']))
        ligne = LigneChiffreAffaire(
            ca=ca, ligne_bordereau_id=pk, quantite_cumulee=cumul, cumul_initial=initial,
            **{champ: reference[champ] for champ in (
                'numero', 'designation', 'unite', 'est_titre', 'niveau', 'ordre', 'quantite_marche', 'prix_unitaire',
            )},
        )
        ligne.full_clean(exclude=['ca'], validate_unique=False, validate_constraints=False)
        nouvelles.append(ligne)
    ca.montant_mensuel = total.quantize(CENTIME, rounding=ROUND_HALF_UP)
    ChiffreAffaire._meta.get_field('montant_mensuel').clean(ca.montant_mensuel, ca)
    existantes = {l.ligne_bordereau_id: l for l in anciennes_lignes if ancien and l.ca_id == ancien.pk}
    changement_lignes = not ancien or set(existantes) != {l.ligne_bordereau_id for l in nouvelles} or any(
        (l.quantite_cumulee, l.cumul_initial) != (
            existantes[l.ligne_bordereau_id].quantite_cumulee, existantes[l.ligne_bordereau_id].cumul_initial,
        ) for l in nouvelles if l.ligne_bordereau_id in existantes
    )
    if changement_lignes and suivant and suivant.statut == ChiffreAffaire.Statut.VALIDE:
        raise ValidationError('Dévalidez le CA du mois suivant avant de corriger les cumuls de ce mois.')
    montants = {ca.periode: ca.montant_mensuel}
    if suivant and changement_lignes:
        cumuls = {l.ligne_bordereau_id: l.quantite_cumulee for l in nouvelles}
        regularisations.extend(
            f'{suivant.periode:%m/%Y} : {l.numero}'
            for l in anciennes_lignes if l.ca_id == suivant.pk and not l.est_titre
            and l.quantite_cumulee < cumuls.get(l.ligne_bordereau_id, Decimal('0'))
        )
        montant_suivant = sum((
            (l.quantite_cumulee - cumuls.get(l.ligne_bordereau_id, Decimal('0'))) * l.prix_unitaire
            for l in anciennes_lignes if l.ca_id == suivant.pk
        ), Decimal('0')).quantize(CENTIME, rounding=ROUND_HALF_UP)
        ChiffreAffaire._meta.get_field('montant_mensuel').clean(montant_suivant, suivant)
        montants[suivant.periode] = montant_suivant
    if regularisations and not ca.observations.strip():
        raise ValidationError('Précisez la régularisation des cumuls en baisse dans les observations.')
    impacts = [{
        'objet': f'CA {periode:%m/%Y}', 'champ': 'Montant mensuel HT',
        'avant': str(next((a.montant_mensuel for a in chaine if a.periode == periode), Decimal('0'))),
        'apres': str(montant),
    } for periode, montant in montants.items()]
    impacts.append({
        'objet': f'CA {ca.periode:%m/%Y}', 'champ': 'Statut',
        'avant': ancien.get_statut_display() if ancien else 'Nouveau',
        'apres': ca.get_statut_display(),
    })
    for ligne in nouvelles:
        ancienne = existantes.get(ligne.ligne_bordereau_id)
        if not ancienne or (ancienne.quantite_cumulee, ancienne.cumul_initial) != (ligne.quantite_cumulee, ligne.cumul_initial):
            impacts.append({
                'objet': f'Ligne {ligne.numero}', 'champ': 'Cumul N / cumul initial',
                'avant': f'{ancienne.quantite_cumulee} / {ancienne.cumul_initial}' if ancienne else '—',
                'apres': f'{ligne.quantite_cumulee} / {ligne.cumul_initial}',
            })
    cibles = []
    for situation in situations:
        periode = date(situation.annee, situation.mois, 1)
        if periode not in montants:
            continue
        liee = situation.ca_id is not None
        source_validee = ca.statut == 'VALIDE' if periode == ca.periode else suivant.statut == 'VALIDE'
        if not liee and not source_validee:
            continue
        recette = next((r for r in recettes if r.situation_id == situation.pk and r.rubrique == 'TRAVAUX_REALISES'), None)
        montant_avant = recette.montant if recette else Decimal('0')
        impact = changement_lignes or not liee or montant_avant != montants[periode] or action == 'devalider'
        if situation.est_validee and impact:
            raise ValidationError(f'Dévalidez la situation {situation.mois:02d}/{situation.annee} avant cette correction du CA.')
        if not situation.est_validee:
            total_recettes = montants[periode] + sum((
                r.montant for r in recettes if r.situation_id == situation.pk and r.rubrique != 'TRAVAUX_REALISES'
            ), Decimal('0'))
            SituationMensuelle._meta.get_field('chiffre_affaires').clean(total_recettes, situation)
            impacts.append({
                'objet': f'Situation {situation.mois:02d}/{situation.annee}',
                'champ': 'Travaux réalisés (remplace la saisie manuelle)' if not liee else 'Travaux réalisés',
                'avant': str(montant_avant), 'apres': str(montants[periode]),
            })
            impacts.append({
                'objet': f'Situation {situation.mois:02d}/{situation.annee}',
                'champ': 'Total des recettes', 'avant': str(situation.chiffre_affaires),
                'apres': str(total_recettes),
            })
            cibles.append(situation)
    etat = {
        'user': user.pk, 'id': ca.pk, 'action': action,
        'saisie': [str(ca.periode), ca.origine, ca.observations, ca.statut],
        'chaines': [[getattr(a, f.attname) for f in a._meta.concrete_fields] for a in chaine],
        'lignes': [[getattr(l, f.attname) for f in l._meta.concrete_fields] for l in anciennes_lignes],
        'situations': [[getattr(s, f.attname) for f in s._meta.concrete_fields] for s in situations],
        'recettes': [[r.pk, r.situation_id, r.rubrique, str(r.montant)] for r in recettes],
        'nouvelles': [[getattr(l, f.attname) for f in l._meta.concrete_fields if f.name not in {'id', 'ca'}] for l in nouvelles],
    }
    empreinte = hashlib.sha256(json.dumps(etat, default=str, sort_keys=True).encode()).hexdigest()
    if not confirmation:
        return {'confirmation': signing.dumps(empreinte, salt=SALT), 'impacts': impacts, 'regularisations': regularisations}
    try:
        approuve = signing.loads(confirmation, salt=SALT, max_age=1800)
    except signing.BadSignature as error:
        raise ValidationError('L’aperçu a expiré ou est invalide. Vérifiez à nouveau les impacts.') from error
    if approuve != empreinte:
        raise ValidationError('Les données ont changé. Vérifiez à nouveau les impacts.')
    if ca.statut == 'VALIDE':
        ca.valide_par = user
        ca.date_validation = timezone.now()
    else:
        ca.valide_par = None
        ca.date_validation = None
    ca.save()
    ca.lignes.all().delete()
    for ligne in nouvelles:
        ligne.ca = ca
    LigneChiffreAffaire.objects.bulk_create(nouvelles)
    if suivant and suivant.periode in montants:
        suivant.montant_mensuel = montants[suivant.periode]
        suivant.save(update_fields=['montant_mensuel', 'updated_at'])
    for situation in cibles:
        source = ca if date(situation.annee, situation.mois, 1) == ca.periode else suivant
        situation.ca = source
        synchroniser_situation_ca(situation)
    return {'enregistre': True, 'id': ca.pk}
