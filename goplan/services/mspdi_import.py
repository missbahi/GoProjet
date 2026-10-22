# goplan/services/mspdi_import.py
"""Import d'un fichier MS Project XML (MSPDI) vers un nouveau GPlan."""
from __future__ import annotations

import datetime as dt
import logging
import re
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import GCalendarException, GPlan, GTask, GTaskDependency, GWorkCalendar
from .calendar import WorkCalendarService
from .dependencies import recalculate_dependencies


NS = {"p": "http://schemas.microsoft.com/project"}
MAX_TASKS = 10_000
WORKING_FORMATS = {"3", "5", "7", "9", "11", "35", "37", "39", "41", "43"}
logger = logging.getLogger(__name__)


# ══════════════════════════════════════════════════════════════
# Helpers de parsing
# ══════════════════════════════════════════════════════════════

def _text(el, path: str, default=None):
    if el is None:
        return default
    found = el.find(path, NS)
    if found is None or found.text is None:
        return default
    return found.text


def _int(el, path: str, default=0) -> int:
    value = _text(el, path)
    if value is None:
        return default
    try:
        return int(value.strip())
    except (TypeError, ValueError) as error:
        raise ValidationError(f"Entier XML invalide pour {path} : {value}.") from error


def _decimal(el, path: str, default=Decimal("0")) -> Decimal:
    value = _text(el, path)
    if value is None:
        return default
    try:
        result = Decimal(value.strip())
    except (InvalidOperation, TypeError, ValueError) as error:
        raise ValidationError(f"Nombre XML invalide pour {path} : {value}.") from error
    if not result.is_finite():
        raise ValidationError(f"Nombre XML non fini pour {path}.")
    return result


def _parse_iso_date(value: str | None) -> dt.date | None:
    """Extrait la date d'un timestamp MSPDI : '2026-10-19T00:00:00' → date(2026,10,19)."""
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value[:10])
    except ValueError as error:
        raise ValidationError(f"Date XML invalide : {value}.") from error


_DURATION_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def _parse_duration_hours(value: str | None) -> Decimal:
    """PT440H0M0S → Decimal(440), sans arrondi intermédiaire."""
    if not value:
        return Decimal(0)
    m = _DURATION_RE.fullmatch(value.strip())
    if not m:
        raise ValidationError(f"Durée XML invalide : {value}.")
    hours = Decimal(m.group(1) or 0)
    minutes = Decimal(m.group(2) or 0)
    seconds = Decimal(m.group(3) or 0)
    return hours + minutes / 60 + seconds / 3600


def _time_to_hours(value: str | None) -> float:
    """'08:30:00' → 8.5."""
    if not value:
        raise ValidationError("Horaire XML manquant.")
    try:
        h, m, s = (int(x) for x in value.split(":"))
        if not (0 <= h <= 24 and 0 <= m < 60 and 0 <= s < 60) or (h == 24 and (m or s)):
            raise ValueError
        return h + m / 60 + s / 3600
    except (ValueError, AttributeError) as error:
        raise ValidationError(f"Horaire XML invalide : {value}.") from error


# ══════════════════════════════════════════════════════════════
# Mapping MSPDI → modèles
# ══════════════════════════════════════════════════════════════

CONSTRAINT_FROM_MSPDI = {
    "0": GTask.Contrainte.ASAP,
    "1": GTask.Contrainte.ALAP,
    "2": GTask.Contrainte.DEBUT_FIXE,
    "3": GTask.Contrainte.FIN_FIXE,
    "4": GTask.Contrainte.DEBUT_MIN,
    "5": GTask.Contrainte.FIN_MIN,
    "6": GTask.Contrainte.DEBUT_MAX,
    "7": GTask.Contrainte.FIN_MAX,
}

DEPENDENCY_FROM_MSPDI = {
    "0": GTaskDependency.Type.FF,
    "1": GTaskDependency.Type.FS,
    "2": GTaskDependency.Type.SF,
    "3": GTaskDependency.Type.SS,
}


def _task_type_from_xml(task_el) -> str:
    if _text(task_el, "p:Milestone") == "1":
        return GTask.Type.JALON
    if _text(task_el, "p:Summary") == "1":
        return GTask.Type.GROUPE
    if _text(task_el, "p:Recurring") == "1":
        return GTask.Type.RECURRENTE
    return GTask.Type.TACHE


def _parse_calendar(project_el) -> GWorkCalendar | None:
    """Lit le calendrier du projet, avec héritage de ses jours de semaine."""
    calendars = {}
    for item in project_el.findall("p:Calendars/p:Calendar", NS):
        uid = _text(item, "p:UID")
        if not uid or uid in calendars:
            raise ValidationError("UID de calendrier absent ou dupliqué.")
        calendars[uid] = item
    if not calendars:
        if _text(project_el, "p:CalendarUID") not in (None, "-1"):
            raise ValidationError("Le calendrier du projet est absent du fichier.")
        if _text(project_el, "p:MinutesPerDay") is not None:
            minutes = _int(project_el, "p:MinutesPerDay")
            if not 0 < minutes <= 1440:
                raise ValidationError("MinutesPerDay doit être compris entre 1 et 1440.")
            return GWorkCalendar.objects.create(
                nom="Standard importé", jours_ouvres=[1, 2, 3, 4, 5],
                heures_par_jour=Decimal(minutes) / 60,
            )
        return None
    selected = _text(project_el, "p:CalendarUID")
    if selected is None and len(calendars) == 1:
        selected = next(iter(calendars))
    if selected not in calendars:
        raise ValidationError("Le CalendarUID du projet ne désigne aucun calendrier disponible.")
    cal_el = calendars[selected]
    chain = []
    visited = set()
    uid = selected
    while uid not in (None, "-1"):
        if uid in visited or uid not in calendars:
            raise ValidationError("Héritage des calendriers invalide.")
        visited.add(uid)
        current = calendars[uid]
        chain.insert(0, current)
        uid = _text(current, "p:BaseCalendarUID")

    nom = _text(cal_el, "p:Name", "Calendrier importé")[:100]
    week = {}
    for current in chain:
        for wd in current.findall("p:WeekDays/p:WeekDay", NS):
            day_type = _int(wd, "p:DayType", default=0)
            if day_type == 0:
                continue  # Date-specific overrides are imported below.
            if not 1 <= day_type <= 7:
                raise ValidationError("DayType de calendrier invalide.")
            iso_day = 7 if day_type == 1 else day_type - 1
            working = _text(wd, "p:DayWorking")
            if working not in ("0", "1"):
                raise ValidationError("DayWorking de calendrier invalide.")
            week[iso_day] = working == "1"
    jours_ouvres = sorted(day for day, working in week.items() if working)
    if not jours_ouvres:
        raise ValidationError("Le calendrier importé ne définit aucun jour ouvré.")

    heures_par_jour = Decimal("8")
    minutes_per_day = _int(project_el, "p:MinutesPerDay", default=480)
    if not 0 < minutes_per_day <= 1440:
        raise ValidationError("MinutesPerDay doit être compris entre 1 et 1440.")
    heures_par_jour = Decimal(minutes_per_day) / Decimal(60)

    calendar = GWorkCalendar.objects.create(
        nom=nom,
        jours_ouvres=jours_ouvres,
        heures_par_jour=heures_par_jour,
        is_default=False,
    )

    # Date ranges are expanded because GoPlan stores one exception per date.
    for current in chain:
        exceptions = current.findall("p:Exceptions/p:Exception", NS)
        exceptions += [
            wd for wd in current.findall("p:WeekDays/p:WeekDay", NS)
            if _text(wd, "p:DayType") == "0"
        ]
        for exc in exceptions:
            if _text(exc, "p:Type") not in (None, "1"):
                raise ValidationError("Les exceptions récurrentes ne sont pas encore prises en charge.")
            date_str = _text(exc, "p:TimePeriod/p:FromDate")
            exc_date = _parse_iso_date(date_str)
            end = _parse_iso_date(_text(exc, "p:TimePeriod/p:ToDate")) or exc_date
            if not exc_date or end < exc_date:
                raise ValidationError("Période d'exception calendrier invalide.")
            if (end - exc_date).days > 36600:
                raise ValidationError("La période d'exception dépasse 100 ans.")

            day_working = _text(exc, "p:DayWorking") == "1"
            if _text(exc, "p:DayWorking") not in ("0", "1"):
                raise ValidationError("DayWorking d'exception invalide.")
            if day_working:
                hours = 0.0
                for wt in exc.findall("p:WorkingTimes/p:WorkingTime", NS):
                    span = _time_to_hours(_text(wt, "p:ToTime")) - _time_to_hours(_text(wt, "p:FromTime"))
                    if span <= 0:
                        raise ValidationError("Plage de travail d'exception invalide.")
                    hours += span
                heures = Decimal(str(round(max(hours, 0), 2)))
                if heures == 0:
                    heures = heures_par_jour
            else:
                heures = Decimal("0")
            WorkCalendarService._validate_hours(heures)
            for offset in range((end - exc_date).days + 1):
                GCalendarException.objects.update_or_create(
                    calendrier=calendar, date=exc_date + dt.timedelta(days=offset),
                    defaults={"heures": heures},
                )

    return calendar


def _collect_tasks(project_el) -> list[dict]:
    """Retourne la liste des <Task> parsés, triés par <ID>."""
    raw = []
    uids, ids = set(), set()
    for task_el in project_el.findall(".//p:Tasks/p:Task", NS):
        uid = _text(task_el, "p:UID")
        task_id = _int(task_el, "p:ID", default=0)
        if not uid or task_id <= 0 or _text(task_el, "p:IsNull") == "1":
            continue
        uid = uid.strip()
        if uid in uids or task_id in ids:
            raise ValidationError(f"UID ou ID de tâche dupliqué : {uid}.")
        uids.add(uid)
        ids.add(task_id)
        constraint = _text(task_el, "p:ConstraintType", "0")
        if constraint not in CONSTRAINT_FROM_MSPDI:
            raise ValidationError(f"Type de contrainte XML inconnu : {constraint}.")
        if constraint in ("2", "3", "4", "5", "6", "7") and not _text(task_el, "p:ConstraintDate"):
            raise ValidationError("ConstraintDate est obligatoire pour cette contrainte XML.")
        if _text(task_el, "p:DurationFormat", "7") not in WORKING_FORMATS | {"21", "53"}:
            raise ValidationError("Les durées écoulées ou en pourcentage ne sont pas prises en charge.")
        task_calendar = _text(task_el, "p:CalendarUID", "-1")
        if task_calendar not in ("-1", _text(project_el, "p:CalendarUID")):
            raise ValidationError("Les calendriers spécifiques aux tâches ne sont pas encore pris en charge.")

        raw.append({
            "uid": uid.strip(),
            "id": task_id,
            "name": (_text(task_el, "p:Name") or "").strip() or f"Tâche {uid}",
            "wbs": (_text(task_el, "p:WBS") or "").strip(),
            "outline_level": max(1, _int(task_el, "p:OutlineLevel", default=1)),
            "type": _task_type_from_xml(task_el),
            "date_debut": _parse_iso_date(_text(task_el, "p:Start")),
            "date_fin": _parse_iso_date(_text(task_el, "p:Finish")),
            "duration_hours": _parse_duration_hours(_text(task_el, "p:Duration")),
            "progress": _decimal(task_el, "p:PercentComplete", default=Decimal("0")),
            "constraint_type": constraint,
            "constraint_date": _parse_iso_date(_text(task_el, "p:ConstraintDate")),
            "notes": (_text(task_el, "p:Notes") or "").strip(),
            "predecessors": [
                {
                    "uid": _text(pl, "p:PredecessorUID"),
                    "type": _text(pl, "p:Type", "1") or "1",
                    "lag_tenths": _int(pl, "p:LinkLag", default=0),
                    "format": _text(pl, "p:LagFormat", "7"),
                    "cross_project": _text(pl, "p:CrossProject", "0"),
                }
                for pl in task_el.findall("p:PredecessorLink", NS)
            ],
        })
        if not 0 <= raw[-1]["progress"] <= 100:
            raise ValidationError(f"{raw[-1]['name']} : avancement hors de la plage 0 à 100.")
        if (raw[-1]["date_debut"] and raw[-1]["date_fin"]
                and raw[-1]["date_fin"] < raw[-1]["date_debut"]):
            raise ValidationError(f"{raw[-1]['name']} : dates inversées.")

    raw.sort(key=lambda t: t["id"])
    if len(raw) > MAX_TASKS:
        raise ValidationError(f"Le fichier contient plus de {MAX_TASKS} tâches.")
    return raw


# ══════════════════════════════════════════════════════════════
# Construction du plan
# ══════════════════════════════════════════════════════════════

def _validate_hierarchy(tasks_data: list[dict]) -> None:
    """L'OutlineLevel doit rester cohérent (pas de saut de niveau)."""
    last_level = 0
    for t in tasks_data:
        if t["outline_level"] > last_level + 1:
            raise ValidationError(
                f"Hiérarchie invalide près de « {t['name']} » : "
                f"niveau {t['outline_level']} après niveau {last_level}."
            )
        last_level = t["outline_level"]


@transaction.atomic
def import_mspdi_to_new_plan(xml_bytes: bytes) -> GPlan:
    """Parse un fichier MSPDI et crée un GPlan complet. Tout ou rien."""
    if not xml_bytes:
        raise ValidationError("Fichier vide.")

    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise ValidationError(f"XML invalide : {exc}") from exc

    # Sécurité : s'assurer qu'on parle bien à un <Project> MSPDI
    if root.tag != f"{{{NS['p']}}}Project":
        raise ValidationError("Ce fichier n'est pas un projet MS Project (XML MSPDI).")

    # ═══ En-tête projet ═══
    nom = (_text(root, "p:Name") or "Import MS Project").strip()[:200]
    description = (_text(root, "p:Title") or "").strip()
    date_debut = _parse_iso_date(_text(root, "p:StartDate"))
    date_fin_cible = _parse_iso_date(_text(root, "p:FinishDate"))
    date_etat = _parse_iso_date(_text(root, "p:StatusDate"))
    tasks_data = _collect_tasks(root)

    if date_debut is None:
        # Fallback : première date de début de tâche
        for t in tasks_data:
            if t["date_debut"]:
                date_debut = t["date_debut"]
                break
    if date_debut is None:
        raise ValidationError("Aucune date de début exploitable dans le fichier.")

    # ═══ Calendrier ═══
    calendar = _parse_calendar(root)
    if calendar is None:
        calendar = GWorkCalendar.objects.filter(is_default=True).first()
    if calendar:
        WorkCalendarService(calendar)
    heures_par_jour = calendar.heures_par_jour if calendar else Decimal(8)

    # ═══ Plan ═══
    plan = GPlan.objects.create(
        nom=nom,
        description=description,
        date_debut=date_debut,
        date_fin_cible=date_fin_cible,
        date_etat=date_etat,
        calendrier=calendar,
    )

    # ═══ Tâches ═══
    _validate_hierarchy(tasks_data)

    uid_to_task: dict[str, GTask] = {}
    stack: list[tuple[int, GTask]] = []  # [(level, task), ...]

    for index, data in enumerate(tasks_data):
        # Parent : pop tant que le sommet est ≥ niveau courant
        level = data["outline_level"]
        while stack and stack[-1][0] >= level:
            stack.pop()
        parent = stack[-1][1] if stack else None

        # Conversion durée
        duration_days = data["duration_hours"] / heures_par_jour
        if data["type"] == GTask.Type.JALON:
            duration_days = Decimal("0")
            if data["date_debut"]:
                data["date_fin"] = data["date_debut"]

        # Type final : un Summary sans enfant sera corrigé en fin d'import
        task = GTask(
            plan=plan,
            parent=parent,
            code=str(index + 1),
            nom=data["name"][:255],
            description=data["notes"],
            type_tache=data["type"],
            duree=duration_days,
            date_debut=data["date_debut"],
            date_fin=data["date_fin"],
            contrainte=CONSTRAINT_FROM_MSPDI.get(data["constraint_type"], GTask.Contrainte.ASAP),
            date_contrainte=data["constraint_date"],
            ordre=index,
            avancement=data["progress"],
            wbs=data["wbs"],
        )
        task.validate_constraint_dates(task.date_debut, task.date_fin)
        task.save()
        uid_to_task[data["uid"]] = task
        stack.append((level, task))

    # ═══ Cohérence des types ═══
    parents = {task.parent_id for task in uid_to_task.values()}
    for task in uid_to_task.values():
        has_children = task.pk in parents
        if has_children and task.type_tache == GTask.Type.TACHE:
            task.type_tache = GTask.Type.GROUPE
            task.save(update_fields=["type_tache"])
        elif has_children and task.type_tache != GTask.Type.GROUPE:
            raise ValidationError(f"{task} : ce type de tâche ne peut pas avoir de sous-tâches.")
        elif not has_children and task.type_tache == GTask.Type.GROUPE:
            task.type_tache = GTask.Type.TACHE
            task.save(update_fields=["type_tache"])

    # ═══ Dépendances ═══
    for data in tasks_data:
        successor = uid_to_task.get(data["uid"])
        if not successor:
            continue
        for pred in data["predecessors"]:
            if pred["format"] not in WORKING_FORMATS or pred["cross_project"] != "0":
                raise ValidationError("Les liaisons externes ou à décalage écoulé/en pourcentage ne sont pas prises en charge.")
            predecessor = uid_to_task.get(pred["uid"])
            if not predecessor or predecessor.pk == successor.pk:
                raise ValidationError("Une liaison désigne un prédécesseur absent ou la tâche elle-même.")
            # LinkLag : dixièmes de minute → jours
            lag = Decimal(pred["lag_tenths"]) / (heures_par_jour * 600)
            if lag != int(lag):
                raise ValidationError("Un décalage de liaison fractionnaire ne peut pas être représenté en jours entiers.")
            lag_days = int(lag)
            if pred["type"] not in DEPENDENCY_FROM_MSPDI:
                raise ValidationError("Type de liaison XML inconnu.")
            GTaskDependency.objects.update_or_create(
                predecesseur=predecessor,
                successeur=successor,
                defaults={
                    "type_lien": DEPENDENCY_FROM_MSPDI.get(pred["type"], GTaskDependency.Type.FS),
                    "decalage_jours": lag_days,
                },
            )

    recalculate_dependencies(plan, list(uid_to_task.values()), list(
        GTaskDependency.objects.filter(successeur__plan=plan)
    ), [])
    resources = len(root.findall("p:Resources/p:Resource", NS))
    assignments = len(root.findall("p:Assignments/p:Assignment", NS))
    if resources or assignments:
        logger.warning(
            "Import MSPDI du plan %s : %s ressources et %s affectations non importées.",
            plan.pk, resources, assignments,
        )
    return plan