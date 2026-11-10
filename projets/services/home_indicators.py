from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum

from projets.models import ChiffreAffaire, LigneBordereau
from projets.models.decomptes import Attachement


ZERO = Decimal('0')


def _montant_expression(quantite, prix):
    return ExpressionWrapper(
        F(quantite) * F(prix), output_field=DecimalField(max_digits=30, decimal_places=5),
    )


def indicateurs_home(projets, today):
    """Calcul en lecture seule, sans additionner les instantanés cumulés."""
    ids = [projet.pk for projet in projets]
    marches = {
        row['lot__projet_id']: row['total']
        for row in LigneBordereau.objects.filter(lot__projet_id__in=ids)
        .values('lot__projet_id').annotate(total=Sum('montant_calcule'))
    }
    cas = list(ChiffreAffaire.objects.filter(
        projet_id__in=ids, periode__lte=today.replace(day=1),
    ).annotate(
        cumul=Sum(_montant_expression('lignes__quantite_cumulee', 'lignes__prix_unitaire'),
                  filter=Q(lignes__est_titre=False)),
    ).order_by('projet_id', 'periode'))
    derniers_ca = {ca.projet_id: ca for ca in cas}
    attachements = list(Attachement.objects.filter(
        projet_id__in=ids, statut='VALIDE', date_fin_periode__lte=today,
    ).annotate(cumul=Sum(_montant_expression(
        'lignes_attachement__quantite_realisee', 'lignes_attachement__prix_unitaire',
    ))).order_by('projet_id', 'sequence'))
    derniers_attachements = {att.projet_id: att for att in attachements}
    ca_annuel = sum((ca.montant_mensuel for ca in cas if ca.periode.year == today.year), ZERO)
    ca_annuel_brouillon = sum((
        ca.montant_mensuel for ca in cas
        if ca.periode.year == today.year and ca.statut == 'BROUILLON'
    ), ZERO)
    production_ca = sum((ca.cumul or ZERO for ca in derniers_ca.values()), ZERO)
    attachements_valides = sum((att.cumul or ZERO for att in derniers_attachements.values()), ZERO)

    for projet in projets:
        ca = derniers_ca.get(projet.pk)
        attachement = derniers_attachements.get(projet.pk)
        projet.home_marche_ht = marches.get(projet.pk) or ZERO
        projet.home_cumul_ht = None
        projet.home_source = 'Aucun CA ni attachement validé'
        projet.home_source_date = None
        projet.home_provisoire = False
        if ca is not None:
            projet.home_cumul_ht = ca.cumul or ZERO
            projet.home_source = f'CA {ca.periode:%m/%Y} — {ca.get_statut_display()}'
            projet.home_source_date = ca.periode
            projet.home_provisoire = ca.statut == 'BROUILLON'
        elif attachement is not None:
            projet.home_cumul_ht = attachement.cumul or ZERO
            projet.home_source = f'Attachement {attachement.numero} — Validé'
            projet.home_source_date = attachement.date_fin_periode
        projet.home_avancement = (
            projet.home_cumul_ht / projet.home_marche_ht * 100
            if projet.home_cumul_ht is not None and projet.home_marche_ht > 0 else None
        )
        projet.home_progress = max(ZERO, min(Decimal('100'), projet.home_avancement or ZERO))
        projet.home_echeance = None
        projet.home_echeance_erreur = ''
        try:
            projet.home_echeance = projet.date_fin_previsionnelle(date_reference=today)
            if projet.home_echeance is None and projet.date_debut and projet.delai:
                projet.home_echeance = projet.echeance_avec_avenants(
                    projet.ajouter_delai(projet.date_debut), date_reference=today,
                )
        except ValidationError as error:
            projet.home_echeance_erreur = ' '.join(error.messages)
        projet.home_en_retard = bool(
            projet.statut in {'COURS', 'ARRET'} and projet.home_echeance
            and projet.home_echeance < today
            and (projet.home_avancement is None or projet.home_avancement < 100)
        )
    return {
        'ca_annuel': ca_annuel, 'ca_annuel_brouillon': ca_annuel_brouillon,
        'production_ca': production_ca, 'attachements_valides': attachements_valides,
        'nb_ca': len(derniers_ca), 'nb_attachements': len(derniers_attachements),
        'nb_ca_brouillons': sum(ca.statut == 'BROUILLON' for ca in derniers_ca.values()),
    }
