"""Données en lecture seule du Sommaire (consultation d'un projet)."""
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum

from projets.models import (
    ChiffreAffaire, DepenseSituationMensuelle, DocumentAdministratif, LigneBordereau, OrdreService,
    SituationMensuelle, StockSituationMensuelle, Tache,
)
from projets.models.decomptes import Attachement, Decompte
from projets.services.home_indicators import _montant_expression


ZERO = Decimal('0')
CENT = Decimal('100')


def _mois_suivant(annee, mois):
    return (annee + 1, 1) if mois == 12 else (annee, mois + 1)


def evolution_mensuelle(projet_ids, today):
    """CA mensuel (brouillons inclus) et attachements validés, par mois, jusqu'au mois courant.

    Un attachement est rattaché au mois de la fin de sa période ; son montant est
    la différence de cumul avec l'attachement précédent.
    """
    ids = list(projet_ids)
    par_mois = {}

    def ajouter(cle, champ, montant):
        mois = par_mois.setdefault(cle, {'ca': ZERO, 'attachements': ZERO})
        mois[champ] += montant or ZERO

    cas = (ChiffreAffaire.objects.filter(projet_id__in=ids, periode__lte=today.replace(day=1))
           .order_by().values('periode__year', 'periode__month').annotate(total=Sum('montant_mensuel')))
    for ligne in cas:
        ajouter((ligne['periode__year'], ligne['periode__month']), 'ca', ligne['total'])

    cumuls = list(
        Attachement.objects.filter(projet_id__in=ids).order_by()
        .annotate(cumul=Sum(_montant_expression(
            'lignes_attachement__quantite_realisee', 'lignes_attachement__prix_unitaire',
        )))
        .values('pk', 'precedent_id', 'statut', 'date_fin_periode', 'cumul')
    )
    cumul_par_id = {row['pk']: row['cumul'] or ZERO for row in cumuls}
    for row in cumuls:
        if row['statut'] == 'VALIDE' and row['date_fin_periode'] <= today:
            montant = (row['cumul'] or ZERO) - cumul_par_id.get(row['precedent_id'], ZERO)
            ajouter((row['date_fin_periode'].year, row['date_fin_periode'].month), 'attachements', montant)

    if not par_mois:
        return {'mois': [], 'ca': [], 'attachements': [], 'ca_cumul': [], 'attachements_cumul': []}

    annee, mois = min(par_mois)
    fin = max(max(par_mois), (today.year, today.month))
    resultat = {'mois': [], 'ca': [], 'attachements': [], 'ca_cumul': [], 'attachements_cumul': []}
    cumul_ca = cumul_att = ZERO
    while (annee, mois) <= fin:
        valeurs = par_mois.get((annee, mois), {'ca': ZERO, 'attachements': ZERO})
        cumul_ca += valeurs['ca']
        cumul_att += valeurs['attachements']
        resultat['mois'].append(f'{annee}-{mois:02d}')
        resultat['ca'].append(float(valeurs['ca']))
        resultat['attachements'].append(float(valeurs['attachements']))
        resultat['ca_cumul'].append(float(cumul_ca))
        resultat['attachements_cumul'].append(float(cumul_att))
        annee, mois = _mois_suivant(annee, mois)
    return resultat


def resultat_mensuel(projet_ids, today):
    """Résultat des situations mensuelles par mois : CA − dépenses + variation de stock.

    Brouillons et situations validées sont confondus ; les mois à venir sont exclus.
    """
    ids = list(projet_ids)
    jusqu_a = Q(situation__annee__lt=today.year) | Q(situation__annee=today.year, situation__mois__lte=today.month)
    par_mois = {}

    def ajouter(cle, champ, montant):
        mois = par_mois.setdefault(cle, {'ca': ZERO, 'depenses': ZERO, 'stock': ZERO})
        mois[champ] += montant or ZERO

    situations = (SituationMensuelle.objects.filter(projet_id__in=ids)
                  .filter(Q(annee__lt=today.year) | Q(annee=today.year, mois__lte=today.month))
                  .order_by().values('annee', 'mois').annotate(total=Sum('chiffre_affaires')))
    for ligne in situations:
        ajouter((ligne['annee'], ligne['mois']), 'ca', ligne['total'])
    depenses = (DepenseSituationMensuelle.objects.filter(jusqu_a, situation__projet_id__in=ids)
                .order_by().values('situation__annee', 'situation__mois').annotate(total=Sum('montant')))
    for ligne in depenses:
        ajouter((ligne['situation__annee'], ligne['situation__mois']), 'depenses', ligne['total'])
    variation = ExpressionWrapper(
        F('qte_entree') * F('pu_entree') - F('qte_sortie') * F('pu_sortie'),
        output_field=DecimalField(max_digits=30, decimal_places=5),
    )
    stocks = (StockSituationMensuelle.objects.filter(jusqu_a, situation__projet_id__in=ids)
              .order_by().values('situation__annee', 'situation__mois').annotate(total=Sum(variation)))
    for ligne in stocks:
        ajouter((ligne['situation__annee'], ligne['situation__mois']), 'stock', ligne['total'])

    serie = {'mois': [], 'resultat': [], 'resultat_cumul': [], 'pct': [], 'pct_cumul': []}
    if not par_mois:
        return serie
    annee, mois = min(par_mois)
    fin = max(par_mois)
    cumul_ca = cumul_resultat = ZERO
    while (annee, mois) <= fin:
        valeurs = par_mois.get((annee, mois), {'ca': ZERO, 'depenses': ZERO, 'stock': ZERO})
        resultat = valeurs['ca'] - valeurs['depenses'] + valeurs['stock']
        cumul_ca += valeurs['ca']
        cumul_resultat += resultat
        serie['mois'].append(f'{annee}-{mois:02d}')
        serie['resultat'].append(float(resultat))
        serie['resultat_cumul'].append(float(cumul_resultat))
        serie['pct'].append(float(resultat / valeurs['ca'] * CENT) if valeurs['ca'] else None)
        serie['pct_cumul'].append(float(cumul_resultat / cumul_ca * CENT) if cumul_ca else None)
        annee, mois = _mois_suivant(annee, mois)
    return serie


def evolution_avec_resultat(projet_ids, today):
    """Série CA/attachements enrichie du résultat des situations, alignée sur les mêmes mois."""
    ids = list(projet_ids)
    evolution = evolution_mensuelle(ids, today)
    resultat = resultat_mensuel(ids, today)
    mois = sorted(set(evolution['mois']) | set(resultat['mois']))
    if not mois:
        return {**evolution, 'mois': [], 'resultat': [], 'resultat_cumul': [], 'pct': [], 'pct_cumul': []}

    def aligner(source, cle, defaut, report=False):
        valeurs = dict(zip(source['mois'], source[cle]))
        sortie, precedent = [], defaut
        for libelle in mois:
            if libelle in valeurs:
                precedent = valeurs[libelle]
                sortie.append(precedent)
            else:
                sortie.append(precedent if report else defaut)
        return sortie

    return {
        'mois': mois,
        'ca': aligner(evolution, 'ca', 0.0),
        'attachements': aligner(evolution, 'attachements', 0.0),
        'ca_cumul': aligner(evolution, 'ca_cumul', 0.0, report=True),
        'attachements_cumul': aligner(evolution, 'attachements_cumul', 0.0, report=True),
        'resultat': aligner(resultat, 'resultat', 0.0),
        'resultat_cumul': aligner(resultat, 'resultat_cumul', 0.0, report=True),
        'pct': aligner(resultat, 'pct', None),
        'pct_cumul': aligner(resultat, 'pct_cumul', None, report=True),
    }


def _grandes_lignes(lignes, total_lot):
    """Grandes lignes d'un lot : on descend tant qu'un niveau n'a qu'une seule ligne parent.

    Les lignes à montant nul sont ignorées à chaque niveau, pour qu'une ligne vide ne bloque
    pas la descente. On s'arrête au premier niveau comportant plusieurs lignes ou une ligne
    simple de montant > 0, et on retient les lignes parents (sinon, après avoir traversé au
    moins un titre, les lignes simples de ce niveau). Retourne (titres traversés, lignes).
    """
    enfants = {}
    for ligne in lignes:
        enfants.setdefault(ligne['parent_id'], []).append(ligne)
    montants = {}

    def montant(ligne):
        if ligne['id'] not in montants:
            sous_lignes = enfants.get(ligne['id'])
            montants[ligne['id']] = (
                sum((montant(sous) for sous in sous_lignes), ZERO) if sous_lignes
                else ligne['montant_calcule'] or ZERO
            )
        return montants[ligne['id']]

    def significatives(niveau):
        return [ligne for ligne in niveau if montant(ligne) > 0]

    niveau = significatives(enfants.get(None, []))
    titres = []
    while len(niveau) == 1 and niveau[0]['id'] in enfants:
        titres.append(niveau[0]['designation'])
        niveau = significatives(enfants[niveau[0]['id']])
    retenues = [ligne for ligne in niveau if ligne['id'] in enfants] or (niveau if titres else [])
    resultat = []
    for ligne in retenues:
        valeur = montant(ligne)
        resultat.append({
            'numero': ligne['numero'], 'designation': ligne['designation'], 'ht': valeur,
            'part': valeur / total_lot * CENT if total_lot else None,
            'nb_sous_lignes': len(enfants.get(ligne['id'], [])),
        })
    return titres, resultat


def synthese_lots(projet):
    """Montants HT/TVA/TTC par lot, avec les grandes lignes (premier niveau) du bordereau."""
    lignes_par_lot = {}
    for ligne in (LigneBordereau.objects.filter(lot__projet=projet)
                  .order_by('ordre_affichage', 'id')
                  .values('id', 'lot_id', 'parent_id', 'numero', 'designation', 'montant_calcule')):
        lignes_par_lot.setdefault(ligne['lot_id'], []).append(ligne)
    lots = []
    total_ht = total_tva = ZERO
    for lot in projet.lots.all():
        lignes = lignes_par_lot.get(lot.pk, [])
        ht = sum((ligne['montant_calcule'] or ZERO for ligne in lignes), ZERO)
        tva = ht * lot.taux_tva_applicable / CENT
        titres, grandes_lignes = _grandes_lignes(lignes, ht)
        lots.append({
            'lot': lot, 'ht': ht, 'tva': tva, 'ttc': ht + tva, 'taux': lot.taux_tva_applicable,
            'grandes_lignes': grandes_lignes, 'titres': ' › '.join(titres),
        })
        total_ht += ht
        total_tva += tva
    return {'lots': lots, 'ht': total_ht, 'tva': total_tva, 'ttc': total_ht + total_tva}


def synthese_decomptes(projet):
    return Decompte.objects.filter(attachement__projet=projet).aggregate(
        total=Count('pk'),
        payes=Count('pk', filter=Q(statut='PAYE')),
        emis=Count('pk', filter=Q(statut='EMIS')),
        en_retard=Count('pk', filter=Q(statut='EN_RETARD')),
        net_a_payer=Sum('montant_net_a_payer'),
    )


def suivi_administratif(projet):
    ordres = OrdreService.objects.filter(projet=projet)
    return {
        'ordres': list(ordres.select_related('type_os').order_by('-ordre_sequence', '-pk')[:5]),
        'nb_ordres_notifies': ordres.filter(statut='NOTIFIE').count(),
        'nb_ordres_brouillons': ordres.filter(statut='BROUILLON').count(),
        'nb_documents': DocumentAdministratif.objects.filter(projet=projet).count(),
    }


def prochaines_taches(projet, today):
    taches = Tache.objects.filter(projet=projet, terminee=False)
    return {
        'a_venir': list(taches.filter(date_fin__gte=today).order_by('date_fin', 'pk')[:5]),
        'nb_en_retard': taches.filter(date_fin__lt=today).count(),
    }


def synthese_situations(projet):
    situations = list(projet.situations_mensuelles.all())
    cumul_validees = sum(
        (s.chiffre_affaires or ZERO for s in situations if s.est_validee), ZERO,
    )
    return {
        'situations': situations,
        'cumul_validees': cumul_validees,
        'nb_brouillons': sum(s.est_brouillon for s in situations),
    }
