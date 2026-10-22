# goplan/services/wbs.py
"""Calcul du WBS hiérarchique pour un plan."""
from collections import defaultdict


def recalculate_wbs(plan, tasks=None):
    """
    Recalcule le champ `wbs` de toutes les tâches du plan.
    - tasks : liste optionnelle (évite un double query si déjà chargée)
    - Retourne la liste des tâches modifiées (à bulk_update par l'appelant).
    """
    if tasks is None:
        tasks = list(plan.taches.order_by("ordre", "pk"))

    by_parent = defaultdict(list)
    for task in tasks:
        by_parent[task.parent_id].append(task)

    for siblings in by_parent.values():
        siblings.sort(key=lambda t: (t.ordre, t.pk))

    updated = []

    def visit(parent_id, prefix):
        for idx, task in enumerate(by_parent.get(parent_id, []), start=1):
            new_wbs = f"{prefix}{idx}"
            if task.wbs != new_wbs:
                task.wbs = new_wbs
                updated.append(task)
            visit(task.pk, f"{new_wbs}.")

    visit(None, "")
    return updated