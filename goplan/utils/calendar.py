from datetime import timedelta

from ..services.calendar import WorkCalendarService


def est_jour_ouvre(jour, calendrier):
    """Vérifie si un jour est ouvré selon le calendrier."""
    return WorkCalendarService(calendrier).is_working_day(jour)


def ajouter_jours_ouvres(date_debut, nb_jours, calendrier=None):
    """Ajoute N jours ouvrés à une date."""
    if nb_jours == 0:
        return date_debut

    sens = 1 if nb_jours > 0 else -1
    reste = abs(nb_jours)
    courant = date_debut
    service = WorkCalendarService(calendrier)

    while reste > 0:
        courant += timedelta(days=sens)
        if service.is_working_day(courant):
            reste -= 1

    return courant