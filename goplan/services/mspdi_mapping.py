# goplan/services/mspdi_mapping.py
"""Constantes de mapping GoPlan ↔ MS Project XML (MSPDI).

Référence : schéma MSPDI (Project 2010+, SaveVersion=14).
"""
from ..models import GTask, GTaskDependency


# ══════════════════════════════════════════════════════════════
# TYPE DE TÂCHE → flags MSPDI
# ══════════════════════════════════════════════════════════════
# Milestone=1 → durée 0
# Summary=1   → groupe (rollup)
# Recurring=1 → tâche récurrente
TASK_TYPE_FLAGS = {
    GTask.Type.JALON:      {"Milestone": "1", "Summary": "0", "Recurring": "0"},
    GTask.Type.GROUPE:     {"Milestone": "0", "Summary": "1", "Recurring": "0"},
    GTask.Type.RECURRENTE: {"Milestone": "0", "Summary": "0", "Recurring": "1"},
    GTask.Type.TACHE:      {"Milestone": "0", "Summary": "0", "Recurring": "0"},
}


# ══════════════════════════════════════════════════════════════
# CONTRAINTE → <ConstraintType>
# ══════════════════════════════════════════════════════════════
# 0 = As Soon As Possible
# 1 = As Late As Possible
# 2 = Must Start On      (nécessite <ConstraintDate>)
# 3 = Must Finish On     (nécessite <ConstraintDate>)
CONSTRAINT_TYPE = {
    GTask.Contrainte.ASAP:       "0",
    GTask.Contrainte.ALAP:       "1",
    GTask.Contrainte.DEBUT_FIXE: "2",
    GTask.Contrainte.FIN_FIXE:   "3",
    GTask.Contrainte.DEBUT_MIN: "4",
    GTask.Contrainte.FIN_MIN: "5",
    GTask.Contrainte.DEBUT_MAX: "6",
    GTask.Contrainte.FIN_MAX: "7",
}


# ══════════════════════════════════════════════════════════════
# DÉPENDANCE → <PredecessorLink>/<Type>
# ══════════════════════════════════════════════════════════════
# 0 = FF, 1 = FS (défaut), 2 = SF, 3 = SS
DEPENDENCY_TYPE = {
    GTaskDependency.Type.FF: "0",
    GTaskDependency.Type.FS: "1",
    GTaskDependency.Type.SF: "2",
    GTaskDependency.Type.SS: "3",
}


# ══════════════════════════════════════════════════════════════
# JOURS : Python isoweekday (1=Lun…7=Dim)
#      → MSPDI DayType   (1=Dim, 2=Lun … 7=Sam)
# ══════════════════════════════════════════════════════════════
def iso_to_mspdi_daytype(iso_day: int) -> str:
    return str((int(iso_day) % 7) + 1)


# Plages horaires d'une journée ouvrée (matin + après-midi)
DEFAULT_WORKING_TIMES = [
    ("08:00:00", "12:00:00"),
    ("13:00:00", "17:00:00"),
]


# ══════════════════════════════════════════════════════════════
# FORMATS
# ══════════════════════════════════════════════════════════════
# DurationFormat / LagFormat : 7 = Days (3 = Minutes).
DURATION_FORMAT_DAYS = "7"
LAG_FORMAT_DAYS = "7"


# ══════════════════════════════════════════════════════════════
# NAMESPACE / VERSION
# ══════════════════════════════════════════════════════════════
MSPDI_NS = "http://schemas.microsoft.com/project"
MSPDI_SAVE_VERSION = "14"   # Project 2010+ (compatible 2013/2016/2019/365)


def register_namespaces():
    """Évite les préfixes ns0: dans le XML généré."""
    import xml.etree.ElementTree as ET
    ET.register_namespace("", MSPDI_NS)