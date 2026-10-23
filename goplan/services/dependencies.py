"""Propagation des contraintes de liaison sur les dates inclusives."""
from collections import deque
from datetime import timedelta
from decimal import Decimal
from math import ceil

from django.core.exceptions import ValidationError

from ..models import GTask
from .calendar import get_calendar_for_plan


def shift_workdays(calendar, day, offset):
    if offset == 0:
        return day
    if hasattr(calendar, "shift_working_days"):
        try:
            return calendar.shift_working_days(day, offset)
        except ValidationError as error:
            raise ValidationError("Le décalage dépasse la plage de dates disponible.") from error
    direction = 1 if offset > 0 else -1
    try:
        for _ in range(abs(offset)):
            while True:
                day += timedelta(days=direction)
                if calendar.is_working_day(day):
                    break
    except OverflowError:
        raise ValidationError("Le décalage dépasse la plage de dates disponible.")
    return day


def _task_ancestors(tasks):
    by_id = {task.pk: task for task in tasks}
    ancestors = {}
    for task in tasks:
        parents = set()
        parent_id = task.parent_id
        while parent_id in by_id and parent_id not in parents:
            parents.add(parent_id)
            parent_id = by_id[parent_id].parent_id
        ancestors[task.pk] = parents
    return ancestors


def possible_predecessors(tasks, links):
    """Structural choices shared by the Gantt selector and POST validation."""
    ancestors = _task_ancestors(tasks)
    all_pks = {task.pk for task in tasks}
    descendants = {pk: set() for pk in all_pks}
    for task_pk, anc_set in ancestors.items():
        for anc_pk in anc_set:
            descendants[anc_pk].add(task_pk)

    outgoing = {pk: set() for pk in all_pks}
    for task in tasks:
        if task.parent_id in outgoing:
            outgoing[task.pk].add(task.parent_id)
    for link in links:
        if link.predecesseur_id in outgoing and link.successeur_id in outgoing:
            outgoing[link.predecesseur_id].add(link.successeur_id)

    choices = {}
    for task in tasks:
        pk = task.pk
        reachable = {pk}
        pending = [pk]
        while pending:
            for successor_id in outgoing[pending.pop()]:
                if successor_id not in reachable:
                    reachable.add(successor_id)
                    pending.append(successor_id)
        choices[pk] = all_pks - reachable - ancestors[pk] - descendants[pk]
    return choices


def recalculate_dependencies(plan, tasks, links, seeds, calendar=None):
    """Recalculate affected successors only; caller owns the transaction."""
    by_id = {task.pk: task for task in tasks}
    incoming = {key: [] for key in by_id}
    outgoing = {key: [] for key in by_id}
    degrees = {key: 0 for key in by_id}
    ancestors = _task_ancestors(tasks)
    children = {key: [] for key in by_id}
    for task in tasks:
        if task.parent_id in by_id:
            children[task.parent_id].append(task)
            if by_id[task.parent_id].type_tache == GTask.Type.GROUPE:
                outgoing[task.pk].append(task.parent_id)
                degrees[task.parent_id] += 1
    for link in links:
        if link.predecesseur_id not in by_id or link.successeur_id not in by_id:
            raise ValidationError("Une liaison pointe vers une tâche d'un autre planning.")
        if link.type_lien not in ("FS", "SS", "FF", "SF"):
            raise ValidationError("Une liaison enregistrée possède un type invalide.")
        if (link.predecesseur_id in ancestors[link.successeur_id]
                or link.successeur_id in ancestors[link.predecesseur_id]):
            raise ValidationError("Une liaison entre une tâche et son parent ou un ancêtre est interdite.")
        incoming[link.successeur_id].append(link)
        outgoing[link.predecesseur_id].append(link.successeur_id)
        degrees[link.successeur_id] += 1
    queue = deque(key for key, degree in degrees.items() if not degree)
    order = []
    while queue:
        key = queue.popleft()
        order.append(key)
        for successor in outgoing[key]:
            degrees[successor] -= 1
            if not degrees[successor]:
                queue.append(successor)
    if len(order) != len(tasks):
        raise ValidationError("Cette liaison crée un cycle entre les tâches.")
    if not seeds:
        return []
    affected = set(seeds)
    queue = deque(seeds)
    while queue:
        for successor in outgoing[queue.popleft()]:
            if successor not in affected:
                affected.add(successor)
                queue.append(successor)
    if calendar is None:
        calendar = get_calendar_for_plan(plan)
    changed = []
    for key in order:
        if key not in affected:
            continue
        task = by_id[key]
        if task.type_tache == GTask.Type.GROUPE:
            if _rollup_group(task, children[key], calendar):
                changed.append(task)
            continue
        if not incoming[key]:
            continue
        milestone = task.type_tache == GTask.Type.JALON
        if not milestone and (task.duree <= 0 or task.duree * 2 != int(task.duree * 2)):
            raise ValidationError(f"{task} : durée invalide pour le recalcul.")
        span = 0 if milestone else ceil(task.duree) - 1
        earliest = plan.date_debut if milestone else calendar.next_working_day(plan.date_debut)
        for link in incoming[key]:
            predecessor = by_id[link.predecesseur_id]
            if not predecessor.date_debut or not predecessor.date_fin:
                raise ValidationError(f"{predecessor} : renseignez les dates avant de lier cette tâche.")
            if predecessor.date_fin < predecessor.date_debut:
                raise ValidationError(f"{predecessor} : les dates sont inversées.")
            anchor = predecessor.date_fin if link.type_lien in ("FS", "FF") else predecessor.date_debut
            offset = link.decalage_jours + (1 if link.type_lien == "FS" else 0)
            target = shift_workdays(calendar, anchor, offset)
            # A finish bound on a non-working date must not be rounded backwards.
            if not milestone:
                target = calendar.next_working_day(target)
            candidate = shift_workdays(calendar, target, -span) if link.type_lien in ("FF", "SF") else target
            earliest = max(earliest, candidate)
        if task.contrainte in (GTask.Contrainte.DEBUT_MIN, GTask.Contrainte.FIN_MIN):
            task.validate_constraint_dates(None, None)
            bound = task.date_contrainte
            if not milestone:
                bound = calendar.next_working_day(bound)
            if task.contrainte == GTask.Contrainte.FIN_MIN:
                bound = shift_workdays(calendar, bound, -span)
            earliest = max(earliest, bound)
        if task.contrainte == GTask.Contrainte.ALAP:
            raise ValidationError(f"{task} : le calcul « au plus tard » n'est pas encore disponible.")
        if task.contrainte == GTask.Contrainte.DEBUT_FIXE:
            fixed_start = task.date_contrainte or task.date_debut
            if not fixed_start or fixed_start < earliest:
                raise ValidationError(f"{task} : la liaison est incompatible avec le début fixe.")
            start = fixed_start
            if not milestone and not calendar.is_working_day(start):
                raise ValidationError(f"{task} : le début fixe doit être ouvré.")
        elif task.contrainte == GTask.Contrainte.FIN_FIXE:
            fixed_end = task.date_contrainte or task.date_fin
            if not fixed_end or (not milestone and not calendar.is_working_day(fixed_end)):
                raise ValidationError(f"{task} : renseignez une fin fixe valide.")
            start = shift_workdays(calendar, fixed_end, -span)
            if start < earliest:
                raise ValidationError(f"{task} : la liaison est incompatible avec la fin fixe.")
        else:
            start = earliest
        end = calendar.add_working_days(start, 0 if milestone else task.duree)
        task.validate_constraint_dates(start, end)
        if (task.date_debut, task.date_fin) != (start, end):
            task.date_debut, task.date_fin = start, end
            changed.append(task)
    if changed:
        GTask.objects.bulk_update(changed, ["date_debut", "date_fin", "duree"])
    return changed


def _rollup_group(task, children, calendar):
    dated = [
        child for child in children
        if child.date_debut and child.date_fin and child.date_fin >= child.date_debut
    ]
    start = min((child.date_debut for child in dated), default=None)
    end = max((child.date_fin for child in dated), default=None)
    duration = Decimal(calendar.working_days_between(start, end)) if dated else Decimal(0)
    task.validate_constraint_dates(start, end)
    if (task.date_debut, task.date_fin, task.duree) == (start, end, duration):
        return False
    task.date_debut, task.date_fin, task.duree = start, end, duration
    return True


def recalculate_group_rollups(plan, tasks=None, calendar=None, *, persist=True):
    """Derive summaries bottom-up; reads use persist=False without database writes."""
    if tasks is None:
        tasks = list(plan.taches.order_by("ordre", "pk"))
    if calendar is None:
        calendar = get_calendar_for_plan(plan)
    by_id = {task.pk: task for task in tasks}
    children = {key: [] for key in by_id}
    for task in tasks:
        if task.parent_id is not None:
            if task.parent_id not in by_id:
                raise ValidationError("La hiérarchie contient un parent absent du planning.")
            children[task.parent_id].append(task)
    degrees = {key: len(items) for key, items in children.items()}
    queue = deque(task for task in tasks if not degrees[task.pk])
    changed = set()
    visited = 0
    while queue:
        task = queue.popleft()
        visited += 1
        if task.type_tache == GTask.Type.GROUPE and _rollup_group(task, children[task.pk], calendar):
            changed.add(task.pk)
        if task.parent_id is not None:
            degrees[task.parent_id] -= 1
            if not degrees[task.parent_id]:
                queue.append(by_id[task.parent_id])
    if visited != len(tasks):
        raise ValidationError("La hiérarchie contient un cycle.")
    if changed and persist:
        update = [task for task in tasks if task.pk in changed]
        GTask.objects.bulk_update(update, ["date_debut", "date_fin", "duree"])
    return changed