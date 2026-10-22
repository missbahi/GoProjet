# goplan/services/mspdi_export.py
"""Export d'un GPlan au format MS Project XML (MSPDI)."""
from __future__ import annotations

import datetime as dt
import io
from collections import defaultdict
from decimal import Decimal
from xml.etree import ElementTree as ET

from ..models import GPlan, GTask, GTaskDependency
from . import mspdi_mapping as M
from .calendar import get_calendar_for_plan


# ══════════════════════════════════════════════════════════════
# Helpers XML
# ══════════════════════════════════════════════════════════════

def _sub(parent: ET.Element, tag: str, text=None, **attrib) -> ET.Element:
    """Ajoute un sous-élément avec le namespace MSPDI par défaut."""
    el = ET.SubElement(parent, f"{{{M.MSPDI_NS}}}{tag}", attrib)
    if text is not None:
        el.text = str(text)
    return el


def _fmt_date(d: dt.date | None) -> str:
    """Date ISO MSPDI (minuit, sans timezone)."""
    return f"{d.isoformat()}T00:00:00"


def _duration_iso(days: float, hours_per_day: float) -> str:
    """Durée ISO 8601 en heures (1 jour = heures_par_jour)."""
    seconds = round(Decimal(str(days or 0)) * Decimal(str(hours_per_day)) * 3600)
    hours, seconds = divmod(max(0, seconds), 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"PT{hours}H{minutes}M{seconds}S"


def _hours_to_hhmmss(hours: float) -> str:
    """4.5 → '04:30:00' (pour les <ToTime> d'exceptions)."""
    seconds = round(Decimal(str(hours)) * 3600)
    whole, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{whole:02d}:{minutes:02d}:{seconds:02d}"


# ══════════════════════════════════════════════════════════════
# WBS et ordre hiérarchique (calculés en mémoire, sans écriture DB)
# ══════════════════════════════════════════════════════════════

def _compute_wbs_map(tasks: list[GTask]) -> dict[int, str]:
    by_parent = defaultdict(list)
    for t in tasks:
        by_parent[t.parent_id].append(t)
    for siblings in by_parent.values():
        siblings.sort(key=lambda t: (t.ordre, t.pk))

    wbs_map: dict[int, str] = {}

    def visit(pid, prefix):
        for idx, task in enumerate(by_parent.get(pid, []), start=1):
            wbs = f"{prefix}{idx}"
            wbs_map[task.pk] = wbs
            visit(task.pk, f"{wbs}.")

    visit(None, "")
    return wbs_map


def _order_by_hierarchy(tasks: list[GTask]) -> list[tuple[GTask, int]]:
    """DFS [(task, level)] — parents avant enfants."""
    by_parent = defaultdict(list)
    for t in tasks:
        by_parent[t.parent_id].append(t)
    for siblings in by_parent.values():
        siblings.sort(key=lambda t: (t.ordre, t.pk))

    result: list[tuple[GTask, int]] = []

    def visit(pid, level):
        for t in by_parent.get(pid, []):
            result.append((t, level))
            visit(t.pk, level + 1)

    visit(None, 0)
    return result


# ══════════════════════════════════════════════════════════════
# Bloc calendrier
# ══════════════════════════════════════════════════════════════

def _build_calendar(project_el: ET.Element, cal) -> None:
    """Ajoute <Calendars><Calendar UID=1>."""
    calendars_el = _sub(project_el, "Calendars")
    cal_el = _sub(calendars_el, "Calendar")
    _sub(cal_el, "UID", "1")
    _sub(cal_el, "Name", cal.calendar.nom if cal.calendar else "Standard")
    _sub(cal_el, "IsBaseCalendar", "1")
    _sub(cal_el, "BaseCalendarUID", "-1")

    # ── Jours ouvrés ──
    weekdays_el = _sub(cal_el, "WeekDays")
    working_set = set(cal.jours_ouvres) if cal.jours_ouvres else {1, 2, 3, 4, 5}
    hours = float(cal.calendar.heures_par_jour) if cal.calendar else 8
    times = M.DEFAULT_WORKING_TIMES if hours == 8 else [("00:00:00", _hours_to_hhmmss(hours))]
    for iso_day in range(1, 8):
        wd = _sub(weekdays_el, "WeekDay")
        _sub(wd, "DayType", M.iso_to_mspdi_daytype(iso_day))
        _sub(wd, "DayWorking", "1" if iso_day in working_set else "0")
        if iso_day in working_set:
            times_el = _sub(wd, "WorkingTimes")
            for start, end in times:
                wt = _sub(times_el, "WorkingTime")
                _sub(wt, "FromTime", start)
                _sub(wt, "ToTime", end)

    # ── Exceptions (cal.exceptions est un dict {iso: heures} via le service) ──
    exceptions = sorted(cal.exceptions.items()) if cal.exceptions else []
    if exceptions:
        exc_el = _sub(cal_el, "Exceptions")
        for idx, (iso, heures) in enumerate(exceptions, start=1):
            exc = _sub(exc_el, "Exception")
            _sub(exc, "EnteredByOccurrences", "0")
            _sub(exc, "Index", str(idx))
            _sub(exc, "Name", iso)
            tp = _sub(exc, "TimePeriod")
            _sub(tp, "FromDate", f"{iso}T00:00:00")
            _sub(tp, "ToDate", f"{iso}T23:59:00")
            _sub(exc, "DayWorking", "1" if heures > 0 else "0")
            if heures > 0:
                times_el = _sub(exc, "WorkingTimes")
                wt = _sub(times_el, "WorkingTime")
                _sub(wt, "FromTime", "00:00:00")
                _sub(wt, "ToTime", _hours_to_hhmmss(float(heures)))


# ══════════════════════════════════════════════════════════════
# Bloc tâches
# ══════════════════════════════════════════════════════════════

def _build_tasks(
    project_el: ET.Element,
    tasks: list[GTask],
    wbs_map: dict[int, str],
    cal,
) -> None:
    hours_per_day = float(cal.calendar.heures_par_jour) if cal.calendar else 8.0
    ordered = _order_by_hierarchy(tasks)

    # Dépendances groupées par successeur
    predecessor_links: dict[int, list] = defaultdict(list)
    for link in GTaskDependency.objects.filter(
        successeur__in=[t.pk for t in tasks],
    ).select_related("predecesseur"):
        predecessor_links[link.successeur_id].append(link)

    tasks_el = _sub(project_el, "Tasks")
    for index, (task, level) in enumerate(ordered, start=1):
        t_el = _sub(tasks_el, "Task")
        _sub(t_el, "UID", str(task.pk))
        _sub(t_el, "ID", str(index))
        _sub(t_el, "Name", task.nom or f"Tâche {task.pk}")
        _sub(t_el, "Type", "0")       # 0 = Fixed Units (défaut)
        _sub(t_el, "IsNull", "0")
        _sub(t_el, "WBS", wbs_map.get(task.pk, str(index)))
        _sub(t_el, "OutlineNumber", wbs_map.get(task.pk, str(index)))
        _sub(t_el, "OutlineLevel", str(level + 1))

        if task.date_debut:
            _sub(t_el, "Start", _fmt_date(task.date_debut))
        if task.date_fin:
            _sub(t_el, "Finish", _fmt_date(task.date_fin))

        # Durée : 0 pour un jalon
        duration_days = 0.0 if task.type_tache == GTask.Type.JALON else float(task.duree or 0)
        _sub(t_el, "Duration", _duration_iso(duration_days, hours_per_day))
        _sub(t_el, "DurationFormat", M.DURATION_FORMAT_DAYS)

        # Milestone / Summary / Recurring
        flags = M.TASK_TYPE_FLAGS.get(
            task.type_tache, M.TASK_TYPE_FLAGS[GTask.Type.TACHE],
        )
        for tag, val in flags.items():
            _sub(t_el, tag, val)

        _sub(t_el, "PercentComplete", str(int(float(task.avancement or 0))))
        _sub(t_el, "ConstraintType", M.CONSTRAINT_TYPE.get(task.contrainte, "0"))
        _sub(t_el, "CalendarUID", "1")

        if task.contrainte in (
            GTask.Contrainte.DEBUT_MIN, GTask.Contrainte.DEBUT_MAX,
            GTask.Contrainte.FIN_MIN, GTask.Contrainte.FIN_MAX,
        ):
            task.validate_constraint_dates(task.date_debut, task.date_fin)
            _sub(t_el, "ConstraintDate", _fmt_date(task.date_contrainte))

        # Fixed constraints also support the legacy start/end-only representation.
        if task.contrainte == GTask.Contrainte.DEBUT_FIXE and task.date_debut:
            _sub(t_el, "ConstraintDate", _fmt_date(task.date_debut))
        elif task.contrainte == GTask.Contrainte.FIN_FIXE and task.date_fin:
            _sub(t_el, "ConstraintDate", _fmt_date(task.date_fin))

        if task.description:
            _sub(t_el, "Notes", task.description)

        # Dépendances (PredecessorLink doit venir après Notes, avant Actual*)
        for link in predecessor_links.get(task.pk, []):
            pl = _sub(t_el, "PredecessorLink")
            _sub(pl, "PredecessorUID", str(link.predecesseur_id))
            _sub(pl, "Type", M.DEPENDENCY_TYPE.get(link.type_lien, "1"))
            _sub(pl, "CrossProject", "0")
            # LinkLag : dixièmes de minute → jours × h/jour × 60 × 10
            lag_tenths = round(Decimal(link.decalage_jours) * Decimal(str(hours_per_day)) * 600)
            _sub(pl, "LinkLag", str(lag_tenths))
            _sub(pl, "LagFormat", M.LAG_FORMAT_DAYS)


# ══════════════════════════════════════════════════════════════
# Point d'entrée
# ══════════════════════════════════════════════════════════════

def export_plan_to_mspdi(plan: GPlan) -> bytes:
    """
    Sérialise un plan au format MS Project XML (MSPDI).
    Retourne les bytes UTF-8 (avec déclaration XML).
    N'écrit rien en base : le WBS est calculé en mémoire.
    """
    M.register_namespaces()

    tasks = list(plan.taches.order_by("ordre", "pk"))
    wbs_map = _compute_wbs_map(tasks)
    cal = get_calendar_for_plan(plan)

    project_el = ET.Element(f"{{{M.MSPDI_NS}}}Project")

    # ── En-tête projet ──
    _sub(project_el, "SaveVersion", M.MSPDI_SAVE_VERSION)
    _sub(project_el, "Name", plan.nom)
    if plan.description:
        _sub(project_el, "Title", plan.description[:255])
    _sub(project_el, "ScheduleFromStart", "1")
    if plan.date_debut:
        _sub(project_el, "StartDate", _fmt_date(plan.date_debut))
    if plan.date_fin_cible:
        _sub(project_el, "FinishDate", _fmt_date(plan.date_fin_cible))
    _sub(project_el, "CalendarUID", "1")
    _sub(project_el, "DefaultStartTime", "08:00:00")
    _sub(project_el, "DefaultFinishTime", "17:00:00")
    minutes = round((cal.calendar.heures_par_jour if cal.calendar else Decimal(8)) * 60)
    _sub(project_el, "MinutesPerDay", minutes)
    _sub(project_el, "MinutesPerWeek", minutes * len(cal.jours_ouvres))
    _sub(project_el, "DaysPerMonth", "20")
    if plan.date_etat:
        _sub(project_el, "StatusDate", _fmt_date(plan.date_etat))

    # ── Sections ──
    _build_calendar(project_el, cal)
    _build_tasks(project_el, tasks, wbs_map, cal)

    # ── Sérialisation ──
    tree = ET.ElementTree(project_el)
    ET.indent(tree, space="  ")
    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue()