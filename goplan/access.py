from django.db.models import Q

from projets.decorators import dossier_utilisateur
from projets.observer_access import plans_observables

from .models import GWorkCalendar


def plans_accessibles(user):
    from .models import GPlan

    return GPlan.objects.all() if user.is_superuser else plans_observables(user)


def calendriers_accessibles(user):
    if user.is_superuser:
        return GWorkCalendar.objects.all()
    from projets.decorators import est_observateur

    if est_observateur(user):
        return GWorkCalendar.objects.filter(
            pk__in=plans_accessibles(user).values('calendrier_id'),
        )
    dossier = dossier_utilisateur(user)
    return GWorkCalendar.objects.filter(
        Q(dossier=dossier) | Q(dossier__isnull=True, is_default=True)
        | Q(pk__in=plans_accessibles(user).values('calendrier_id')),
    ).distinct()


def calendriers_modifiables(user):
    if user.is_superuser:
        return GWorkCalendar.objects.all()
    return GWorkCalendar.objects.filter(dossier=dossier_utilisateur(user))
