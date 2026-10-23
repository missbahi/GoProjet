"""Persist calendar-consistent dates when opening a planning."""
from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import GPlan, GTask, GTaskDependency
from .calendar import get_calendar_for_plan
from .dependencies import recalculate_dependencies, recalculate_group_rollups


@transaction.atomic
def repair_plan_dates(plan):
    locked_plan = GPlan.objects.select_for_update().get(pk=plan.pk)
    calendar = get_calendar_for_plan(locked_plan)
    tasks = list(locked_plan.taches.select_for_update().order_by("ordre", "pk"))
    before = {
        task.pk: (task.date_debut, task.date_fin, task.duree)
        for task in tasks
    }
    for task in tasks:
        if task.type_tache == GTask.Type.GROUPE:
            continue
        if task.type_tache == GTask.Type.JALON:
            task.duree = 0
            if task.date_debut:
                task.date_fin = task.date_debut
        else:
            if task.duree <= 0 or task.duree * 2 != int(task.duree * 2):
                raise ValidationError(f"{task} : durée invalide pour le recalcul.")
            if task.date_debut:
                task.date_debut = calendar.next_working_day(task.date_debut)
                task.date_fin = calendar.add_working_days(task.date_debut, task.duree)
        try:
            task.validate_constraint_dates(task.date_debut, task.date_fin)
        except ValidationError as error:
            raise ValidationError(f"{task} : {' '.join(error.messages)}") from error

    recalculate_group_rollups(locked_plan, tasks, calendar, persist=False)
    changed = [
        task for task in tasks
        if before[task.pk] != (task.date_debut, task.date_fin, task.duree)
    ]
    if not changed:
        return []
    GTask.objects.bulk_update(changed, ["date_debut", "date_fin", "duree"])
    links = list(GTaskDependency.objects.filter(
        successeur_id__in=before,
    ).order_by("pk"))
    recalculate_dependencies(
        locked_plan, tasks, links, {task.pk for task in changed}, calendar=calendar,
    )
    return [
        task for task in tasks
        if before[task.pk] != (task.date_debut, task.date_fin, task.duree)
    ]
