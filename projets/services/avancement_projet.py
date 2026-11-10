from decimal import Decimal, ROUND_HALF_UP

from projets.models import ChiffreAffaire


def avancement_ttc(projet, lots, montant_marche_ttc, today):
    ca = projet.chiffres_affaires.filter(
        periode__lte=today.replace(day=1),
    ).order_by('-periode').first()
    attachement = None
    if ca is None:
        attachement = projet.attachements.filter(
            statut='VALIDE', date_fin_periode__lte=today,
        ).order_by('-sequence').first()
    source = ca or attachement
    if source is None:
        return {'montant_ttc': None, 'pourcentage': None, 'source': 'Aucun CA ni attachement validé', 'provisoire': False}
    taux_par_lot = {lot.pk: lot.taux_tva_applicable for lot in lots}
    montant = Decimal('0')
    if ca is not None:
        lignes = ca.lignes.filter(est_titre=False).select_related('ligne_bordereau')
        for ligne in lignes:
            montant += ligne.quantite_cumulee * ligne.prix_unitaire * (
                1 + taux_par_lot[ligne.ligne_bordereau.lot_id] / 100
            )
        libelle = f'CA {ca.periode:%m/%Y} — {ca.get_statut_display()}'
    else:
        for ligne in attachement.lignes_attachement.select_related('ligne_lot'):
            montant += ligne.quantite_realisee * ligne.prix_unitaire * (
                1 + taux_par_lot[ligne.ligne_lot.lot_id] / 100
            )
        libelle = f'Attachement {attachement.numero} — Validé'
    montant = montant.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return {
        'montant_ttc': montant,
        'pourcentage': montant / montant_marche_ttc * 100 if montant_marche_ttc > 0 else None,
        'source': libelle,
        'provisoire': ca is not None and ca.statut == ChiffreAffaire.Statut.BROUILLON,
    }
