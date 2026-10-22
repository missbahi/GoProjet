"""
Calcul CPM (Critical Path Method) pour une planification GoPlan.
"""
from collections import defaultdict, deque
from datetime import date, timedelta
from decimal import Decimal

from ..utils.calendar import ajouter_jours_ouvres


def calculer_plan(plan):
    """
    Calcule les dates de début/fin, marges et chemin critique.

    Algorithme :
      1. Tri topologique (détection de cycles)
      2. Passage forward : dates au plus tôt
      3. Passage backward : dates au plus tard
      4. Calcul des marges
      5. Identification du chemin critique
    """
    taches = list(plan.taches.exclude(type_tache='JALON'))

    # 1. Tri topologique
    ordre = _tri_topologique(taches)
    if ordre is None:
        raise ValueError("Cycle détecté dans les dépendances.")

    calendrier = plan.calendrier

    # 2. Forward pass
    for tache in ordre:
        _forward_pass(tache, plan, calendrier)

    # 3. Backward pass
    date_fin_projet = max((t.date_fin for t in taches if t.date_fin), default=plan.date_debut)
    for tache in reversed(ordre):
        _backward_pass(tache, date_fin_projet, calendrier)

    # 4. Marges et chemin critique
    for tache in taches:
        if tache.date_debut and tache.date_debut_fin_tard:
            tache.marge_totale = (tache.date_debut_fin_tard - tache.date_debut).days
            tache.est_critique = (tache.marge_totale == 0)
            tache.save(update_fields=['marge_totale', 'est_critique'])

    return plan


def _tri_topologique(taches):
    """Retourne les tâches en ordre topologique, ou None si cycle."""
    graph = defaultdict(list)
    in_degree = {t.id: 0 for t in taches}
    taches_by_id = {t.id: t for t in taches}

    for tache in taches:
        for dep in tache.dependances_entrantes.all():
            if dep.predecesseur_id in taches_by_id:
                graph[dep.predecesseur_id].append(tache.id)
                in_degree[tache.id] += 1

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


def _forward_pass(tache, plan, calendrier):
    """Calcule la date de début au plus tôt."""
    debut_min = plan.date_debut

    for dep in tache.dependances_entrantes.all():
        pred = dep.predecesseur
        if not pred.date_fin:
            continue

        if dep.type_lien == 'FS':
            candidat = ajouter_jours_ouvres(
                pred.date_fin, 1 + dep.decalage_jours, calendrier
            )
        elif dep.type_lien == 'SS':
            candidat = ajouter_jours_ouvres(
                pred.date_debut, dep.decalage_jours, calendrier
            )
        elif dep.type_lien == 'FF':
            candidat = ajouter_jours_ouvres(
                pred.date_fin, dep.decalage_jours - int(tache.duree), calendrier
            )
        elif dep.type_lien == 'SF':
            candidat = ajouter_jours_ouvres(
                pred.date_debut, dep.decalage_jours - int(tache.duree), calendrier
            )
        else:
            continue

        debut_min = max(debut_min, candidat)

    # Applique la contrainte si DEBUT_FIXE
    if tache.contrainte == 'FIXE_DEBUT' and tache.date_debut:
        debut_min = tache.date_debut

    tache.date_debut = debut_min
    tache.date_fin = ajouter_jours_ouvres(debut_min, int(tache.duree) - 1, calendrier)
    tache.save(update_fields=['date_debut', 'date_fin'])


def _backward_pass(tache, date_fin_projet, calendrier):
    """Calcule la date de fin au plus tard (pour marges)."""
    # À compléter pour le calcul complet des marges
    tache.date_debut_fin_tard = date_fin_projet - timedelta(days=int(tache.duree) - 1)