# projets/services/dashboard_delai.py
from django.utils import timezone

from projets.models import OrdreService


def calculer_delai_pilotage(projet):
    """
    Retourne le bloc `delai_pilotage` (OSC, dates, statut, libellé, message).
    Suppose que le module OS est actif.
    """
    ordre_services = OrdreService.objects.filter(projet=projet)
    ordres_notifies = list(
        ordre_services.filter(statut='NOTIFIE', date_effet__isnull=False)
        .select_related('type_os')
        .order_by('date_effet', 'ordre_sequence')
    )
    osc = min(
        (ordre for ordre in ordres_notifies if ordre.type_os.code == 'OSC'),
        key=lambda ordre: ordre.ordre_sequence,
        default=None,
    )

    today = timezone.localdate()
    date_fin_previsionnelle = projet.date_fin_previsionnelle(today)
    jours_ecoules = projet.jours_decoules_depuis_demarrage(today)
    date_fin_contractuelle = projet.ajouter_delai(osc.date_effet) if osc else None
    jours_extension = (
        (date_fin_previsionnelle - date_fin_contractuelle).days
        if date_fin_previsionnelle and date_fin_contractuelle else 0
    )
    jours_avant_echeance = (
        (date_fin_previsionnelle - today).days if date_fin_previsionnelle else None
    )

    if not projet.delai:
        statut, libelle, message = (
            'INCOMPLET',
            'Délai à renseigner',
            "Ajoutez le délai contractuel pour activer le suivi de l'échéance.",
        )
    elif not osc:
        statut, libelle, message = (
            'ATTENTE_OSC',
            'OSC attendu',
            'La date de fin sera calculée après notification de l’OS de commencement.',
        )
    elif jours_avant_echeance is not None and jours_avant_echeance < 0:
        statut = 'RETARD'
        libelle = f'{abs(jours_avant_echeance)} jour(s) de dépassement'
        message = "L'échéance prévisionnelle est dépassée."
    elif projet.projet_en_arret:
        statut, libelle, message = (
            'ARRET',
            'Chantier en arrêt',
            "L'échéance sera recalculée après notification de l'OS de reprise.",
        )
    elif jours_avant_echeance is not None and jours_avant_echeance <= 30:
        statut = 'ALERTE'
        libelle = f'Échéance dans {jours_avant_echeance} jour(s)'
        message = 'La date de fin prévisionnelle approche.'
    else:
        statut, libelle, message = (
            'NORMAL',
            'Dans les délais',
            'Aucune alerte de délai à ce jour.',
        )

    return {
        'osc': osc,
        'date_fin': date_fin_previsionnelle,
        'jours_ecoules': jours_ecoules,
        'jours_extension': jours_extension,
        'jours_avant_echeance': jours_avant_echeance,
        'statut': statut,
        'libelle': libelle,
        'message': message,
    }