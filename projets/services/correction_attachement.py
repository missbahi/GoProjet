import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import DatabaseError

from projets.models import Attachement, Decompte, LigneAttachement
from projets.services.attachement_service import preparer_lignes_attachement


CHAMPS_MONTANTS = (
    'montant_ht', 'montant_tva', 'montant_ttc', 'montant_retenue_garantie',
    'montant_ras', 'montant_net_a_payer',
)
CHAMPS_EDITABLES = (
    'date_etablissement', 'date_debut_periode', 'date_fin_periode', 'observations',
)
SALT = 'projets.correction-exceptionnelle-attachement'


def projeter_montants_decompte(decompte, montant_situation):
    anciens = {champ: getattr(decompte, champ) for champ in CHAMPS_MONTANTS}
    decompte.calculer_montants(montant_situation)
    impacts = []
    for champ in CHAMPS_MONTANTS:
        setattr(decompte, champ, getattr(decompte, champ).quantize(Decimal('0.01')))
        impacts.append({
            'objet': f"Décompte {decompte.numero}",
            'champ': str(decompte._meta.get_field(champ).verbose_name),
            'avant': str(anciens[champ]), 'apres': str(getattr(decompte, champ)),
        })
    decompte.full_clean()
    return impacts


def preparer_correction_chaine(form, lignes, decomptes):
    totaux = {a.pk: Decimal('0') for a in form.attachements}
    for ligne in lignes:
        totaux[ligne.attachement_id] += ligne.montant_ligne_realise
    comptes = {d.attachement_id: d for d in decomptes}
    modifications = []
    precedent_id = None
    for sequence, attachement in enumerate(form.attachements_ordonnes, 1):
        debut = form.cleaned_data[f'date_debut_periode_{attachement.pk}']
        fin = form.cleaned_data[f'date_fin_periode_{attachement.pk}']
        montant = (totaux[attachement.pk] - totaux.get(precedent_id, Decimal('0'))).quantize(Decimal('0.01'))
        Attachement._meta.get_field('montant_ht').clean(montant, attachement)
        numero = f'DP{sequence:02d}'
        recalcul = precedent_id != attachement.precedent_id or montant != attachement.montant_ht
        changement = (
            sequence != attachement.sequence or numero != attachement.numero
            or precedent_id != attachement.precedent_id
            or debut != attachement.date_debut_periode or fin != attachement.date_fin_periode
            or montant != attachement.montant_ht
        )
        decompte = comptes.get(attachement.pk)
        if changement and decompte and (
            decompte.statut in {'PAYE', 'PARTIEL'} or decompte.date_paiement
        ):
            raise ValidationError(
                f"Correction bloquée : le décompte {decompte.numero} de "
                f"l'attachement {attachement.numero} (ID {attachement.pk}) est payé ou partiellement payé."
            )
        if changement:
            impacts = [{
                'objet': f"Situation {attachement.numero} (ID {attachement.pk})",
                'champ': 'Montant HT', 'avant': str(attachement.montant_ht), 'apres': str(montant),
            }]
            compte = None
            if recalcul and decompte:
                impacts.extend(projeter_montants_decompte(decompte, montant))
                compte = {
                    'id': decompte.pk,
                    'montants': {champ: str(getattr(decompte, champ)) for champ in CHAMPS_MONTANTS},
                }
            modifications.append({
                'id': attachement.pk, 'numero': attachement.numero, 'nouveau_numero': numero,
                'ancienne_sequence': attachement.sequence, 'nouvelle_sequence': sequence,
                'ancien_precedent_id': attachement.precedent_id, 'nouveau_precedent_id': precedent_id,
                'ancien_debut': attachement.date_debut_periode.isoformat(),
                'ancienne_fin': attachement.date_fin_periode.isoformat(),
                'nouveau_debut': debut.isoformat(), 'nouvelle_fin': fin.isoformat(),
                'ancien_montant_ht': str(attachement.montant_ht), 'nouveau_montant_ht': str(montant),
                'decompte': compte, 'impacts': impacts,
            })
        precedent_id = attachement.pk
    return modifications


def appliquer_correction_chaine(projet, attachements, modifications):
    """Appelé sous transaction et verrous de projet, chaîne, lignes et décomptes."""
    rangs_occupes = {a.sequence for a in attachements}
    prochain_rang = len(attachements) + 1
    for modification in modifications:
        if modification['ancienne_sequence'] != modification['nouvelle_sequence']:
            while prochain_rang in rangs_occupes:
                prochain_rang += 1
            Attachement._meta.get_field('sequence').clean(prochain_rang, None)
            Attachement.objects.filter(pk=modification['id'], projet=projet).update(sequence=prochain_rang)
            rangs_occupes.add(prochain_rang)
            prochain_rang += 1
    for modification in modifications:
        Attachement.objects.filter(pk=modification['id'], projet=projet).update(
            sequence=modification['nouvelle_sequence'],
            precedent_id=modification['nouveau_precedent_id'],
            numero=modification['nouveau_numero'],
            date_debut_periode=modification['nouveau_debut'],
            date_fin_periode=modification['nouvelle_fin'],
            montant_ht=Decimal(modification['nouveau_montant_ht']),
        )
        compte = modification['decompte']
        if compte:
            Decompte.objects.filter(pk=compte['id'], attachement_id=modification['id']).update(**{
                champ: Decimal(valeur) for champ, valeur in compte['montants'].items()
            })


def corriger_attachement(attachement, form, lignes_json, user, confirmation=''):
    """Appelé sous transaction et verrou de projet ; aucun changement avant confirmation."""
    attachement.verifier_debut_periode_hors_arret(form.cleaned_data['date_debut_periode'])
    attachement.verifier_fin_periode_hors_arret(form.cleaned_data['date_fin_periode'])
    chaine = list(Attachement.objects.select_for_update().filter(
        projet_id=attachement.projet_id,
    ).order_by('sequence'))
    lignes_etat = list(LigneAttachement.objects.select_for_update().filter(
        attachement__projet_id=attachement.projet_id,
    ).order_by('pk').values())
    decomptes = list(Decompte.objects.select_for_update().filter(
        attachement__projet_id=attachement.projet_id,
    ).order_by('pk'))
    etat_decomptes = [dict(d.__dict__, _state=None) for d in decomptes]
    nouvelles = preparer_lignes_attachement(
        attachement, lignes_json, conserver_instantanes=True,
    )
    anciennes_quantites = {
        ligne['ligne_lot_id']: ligne['quantite_realisee']
        for ligne in lignes_etat if ligne['attachement_id'] == attachement.pk
    }
    quantites_modifiees = any(
        anciennes_quantites.get(l.ligne_lot_id, Decimal('0')) != l.quantite_realisee
        for l in nouvelles
    )
    ancien_total = attachement.total_montant_ht
    nouveau_total = sum((ligne.montant_ligne_realise for ligne in nouvelles), Decimal('0'))
    delta = nouveau_total - ancien_total
    impacts = []
    situations = {}
    dates_changees = any(
        form.cleaned_data[champ] != getattr(attachement, champ)
        for champ in ('date_debut_periode', 'date_fin_periode')
    )
    if dates_changees:
        debut_attendu = attachement._date_debut_attendue(attachement.precedent)
        if form.cleaned_data['date_debut_periode'] != debut_attendu:
            raise ValidationError("La période corrigée doit commencer à la date attendue de la chaîne.")
        for suivant in chaine:
            if suivant.precedent_id == attachement.pk:
                fin = form.cleaned_data['date_fin_periode']
                debut_suivant_attendu = attachement.date_debut_apres_arret(
                    fin + timedelta(days=1),
                )
                if suivant.date_debut_periode != debut_suivant_attendu:
                    raise ValidationError(
                        "La date de début du suivant doit respecter la continuité après arrêt. "
                        "Utilisez la correction des périodes historiques pour modifier plusieurs périodes."
                    )
    for courant in chaine:
        variation = delta if courant.pk == attachement.pk else -delta if courant.precedent_id == attachement.pk else Decimal('0')
        if courant.pk == attachement.pk or variation:
            avant = courant.montant_situation
            situations[courant.pk] = avant + variation
            Attachement._meta.get_field('montant_ht').clean(
                situations[courant.pk].quantize(Decimal('0.01')), courant,
            )
            impacts.append({
                'objet': f"Situation {courant.numero}",
                'champ': 'Montant HT', 'avant': str(avant), 'apres': str(avant + variation),
            })
    for decompte in decomptes:
        if decompte.attachement_id not in situations:
            continue
        financier = delta != 0
        if (financier or quantites_modifiees or dates_changees) and (
            decompte.statut in {'PAYE', 'PARTIEL'} or decompte.date_paiement
        ):
            raise ValidationError(
                f"Correction bloquée : le décompte {decompte.numero} est payé ou partiellement payé."
            )
        if financier:
            impacts.extend(projeter_montants_decompte(decompte, situations[decompte.attachement_id]))
    changements = [
        {'objet': attachement.numero, 'champ': str(form.fields[champ].label), 'avant': str(getattr(attachement, champ)),
         'apres': str(form.cleaned_data[champ])}
        for champ in CHAMPS_EDITABLES
        if form.cleaned_data[champ] != getattr(attachement, champ)
    ]
    for ligne in nouvelles:
        avant = anciennes_quantites.get(ligne.ligne_lot_id, Decimal('0'))
        if avant != ligne.quantite_realisee:
            changements.append({
                'objet': f"Ligne {ligne.numero}", 'champ': 'Nouveau cumul',
                'avant': str(avant), 'apres': str(ligne.quantite_realisee),
            })
    fichier = form.files.get('fichier')
    fichier_digest = None
    if fichier and hasattr(fichier, 'chunks'):
        digest = hashlib.sha256()
        for chunk in fichier.chunks():
            digest.update(chunk)
        fichier.seek(0)
        fichier_digest = [fichier.name, digest.hexdigest()]
        changements.append({
            'objet': attachement.numero, 'champ': 'Fichier joint',
            'avant': attachement.fichier.name, 'apres': fichier.name,
        })
    etat = {
        'user': user.pk,
        'attachements': [dict(a.__dict__, _state=None) for a in chaine],
        'lignes': lignes_etat,
        'decomptes': etat_decomptes,
        'saisie': {champ: form.cleaned_data[champ] for champ in CHAMPS_EDITABLES},
        'fichier': fichier_digest,
        'nouvelles': [
            [l.ligne_lot_id, l.numero, l.designation, l.unite, l.quantite_initiale,
             l.prix_unitaire, l.quantite_realisee] for l in nouvelles
        ],
    }
    empreinte = hashlib.sha256(json.dumps(etat, default=str, sort_keys=True).encode()).hexdigest()
    if not confirmation:
        return {
            'confirmation': signing.dumps(empreinte, salt=SALT),
            'impacts': changements + impacts,
        }
    try:
        approuve = signing.loads(confirmation, salt=SALT, max_age=1800)
    except signing.BadSignature as error:
        raise ValidationError("L'aperçu a expiré. Vérifiez à nouveau les impacts.") from error
    if approuve != empreinte:
        raise ValidationError("Les données ont changé. Vérifiez à nouveau les impacts.")
    modifications = {champ: form.cleaned_data[champ] for champ in CHAMPS_EDITABLES}
    modifications['modifie_par_id'] = user.pk
    Attachement.objects.filter(pk=attachement.pk).update(**modifications)
    LigneAttachement.objects.filter(attachement=attachement).delete()
    LigneAttachement.objects.bulk_create(nouvelles)
    for pk, montant in situations.items():
        Attachement.objects.filter(pk=pk).update(montant_ht=montant)
    if delta:
        for decompte in decomptes:
            if decompte.attachement_id in situations:
                Decompte.objects.filter(pk=decompte.pk).update(**{
                    champ: getattr(decompte, champ) for champ in CHAMPS_MONTANTS
                })
    if fichier_digest:
        attachement.fichier.save(fichier.name, fichier, save=False)
        try:
            Attachement.objects.filter(pk=attachement.pk).update(
                fichier=attachement.fichier.name, original_filename=fichier.name,
            )
        except DatabaseError:
            attachement.fichier.storage.delete(attachement.fichier.name)
            raise
    return {'enregistre': True}
