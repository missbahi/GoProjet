"""Météo des rapports journaliers.

- ``conditions`` : catalogue des conditions (codes, libellés, icônes), sans dépendance.
- ``open_meteo`` : météo en ligne d'une journée (Open-Meteo), désactivée par défaut.
"""

from .conditions import (  # noqa: F401
    METEO, METEO_CHOICES, METEO_GROUPES, METEO_ICONE_DEFAUT, METEO_RAPIDES,
    meteo_icone, meteo_libelle,
)
