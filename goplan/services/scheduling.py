"""
Calcul CPM (Critical Path Method) pour une planification GoPlan.
"""
from collections import defaultdict, deque
from datetime import timedelta

from ..models import GTask, GTaskDependency
from .calendar import get_calendar_for_plan


def calculer_plan(plan):
    """
    Calcule les dates de début/fin, marges et chemin critique en mémoire
    puis persiste les modifications en un seul bulk_update.

    Algorithme :
      1. Tri topologique (détection de cycles)
      2. Passage forward : dates au plus tôt
      3. Passage backward : dates au plus tard
      4. Calcul des marges
      5. Identification du chemin critique
    """
    taches = list(plan.taches.exclude(type_tache='JALON'))
    if not taches:
        return plan

    taches_by_id = {t.id: t for t in taches}
    # Une seule requête pour charger toutes les dépendances entrantes du plan
    deps_by_succ = defaultdict(list)
    for dep in GTaskDependency.objects.filter(successeur_id__in=taches_by_id):
        if dep.predecesseur_id in taches_by_id:
            deps_by_succ[dep.successeur_id].append(dep)

    # 1. Tri topologique
    ordre = _tri_topologique(taches, taches_by_id, deps_by_succ)
    if ordre is None:
        raise ValueError("Cycle détecté dans les dépendances.")

    # Une seule instanciation du service calendrier pour tout le calcul
    calendar_service = get_calendar_for_plan(plan)

    # 2. Forward pass (en mémoire)
    for tache in ordre:
        _forward_pass(tache, plan, calendar_service, taches_by_id, deps_by_succ[tache.id])

    # 3. Backward pass
    date_fin_projet = max((t.date_fin for t in taches if t.date_fin), default=plan.date_debut)
    for tache in reversed(ordre):
        _backward_pass(tache, date_fin_projet, calendar_service)

    # 4. Marges et chemin critique + 1 seul bulk_update global
    for tache in taches:
        if tache.date_debut and getattr(tache, "date_debut_fin_tard", None):
            tache.marge_totale = (tache.date_debut_fin_tard - tache.date_debut).days
            tache.est_critique = (tache.marge_totale == 0)

    GTask.objects.bulk_update(
        taches, ["date_debut", "date_fin", "marge_totale", "est_critique"],
    )
    return plan


def _tri_topologique(taches, taches_by_id, deps_by_succ):
    """Retourne les tâches en ordre topologique, ou None si cycle."""
    graph = defaultdict(list)
    in_degree = {t.id: 0 for t in taches}

    for succ_id, deps in deps_by_succ.items():
        for dep in deps:
            graph[dep.predecesseur_id].append(succ_id)
            in_degree[succ_id] += 1

    queue = deque([tid for tid, deg in in_degree.items() if deg == 0])
    ordre = []

    while queue:
        tid = queue.popleft()
        ordre.append(taches_by_id[tid])
        for succ_id in graph[tid]:
            in_degree[succ_id] -= 1
            if in_degree[succ_id] == 0:
                queue.append(succ_id)

    return ordre if len(ordre) == len(taches) else None


def _forward_pass(tache, plan, calendar_service, taches_by_id, incoming_deps):
    """Calcule la date de début au plus tôt en mémoire (sans N+1 SQL)."""
    debut_min = plan.date_debut

    for dep in incoming_deps:
        pred = taches_by_id.get(dep.predecesseur_id)
        if not pred or not pred.date_fin:
            continue

        if dep.type_lien == 'FS':
            candidat = calendar_service.shift_working_days(
                pred.date_fin, 1 + dep.decalage_jours
            )
        elif dep.type_lien == 'SS':
            candidat = calendar_service.shift_working_days(
                pred.date_debut, dep.decalage_jours
            )
        elif dep.type_lien == 'FF':
            candidat = calendar_service.shift_working_days(
                pred.date_fin, dep.decalage_jours - int(tache.duree)
            )
        elif dep.type_lien == 'SF':
            candidat = calendar_service.shift_working_days(
                pred.date_debut, dep.decalage_jours - int(tache.duree)
            )
        else:
            continue

        debut_min = max(debut_min, candidat)

    # Applique la contrainte si DEBUT_FIXE
    if tache.contrainte == 'FIXE_DEBUT' and tache.date_debut:
        debut_min = tache.date_debut

    tache.date_debut = debut_min
    tache.date_fin = calendar_service.shift_working_days(debut_min, int(tache.duree) - 1)


def _backward_pass(tache, date_fin_projet, calendar_service):
    """Calcule la date de fin au plus tard (pour marges)."""
    tache.date_debut_fin_tard = date_fin_projet - timedelta(days=int(tache.duree) - 1)