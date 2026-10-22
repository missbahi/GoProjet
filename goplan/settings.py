"""
Configuration par défaut de GoPlan.
Surcharger via GOPLAN_SETTINGS dans settings.py du projet hôte.
"""
from django.conf import settings

GOPLAN_DEFAULTS = {
    # Calendrier
    'DEFAULT_WORK_DAYS': [1, 2, 3, 4, 5],  # Lun-Ven
    'DEFAULT_HOURS_PER_DAY': 8,
    'DEFAULT_HOLIDAYS': [],

    # Gantt
    'GANTT_LIBRARY': 'frappe',             # frappe | dhtmlx | custom
    'GANTT_DEFAULT_VIEW': 'week',          # day | week | month
    'GANTT_SHOW_TODAY': True,
    'GANTT_DRAGGABLE': True,
    'GANTT_LANGUAGE': 'fr',

    # CPM
    'AUTO_CALCULATE_DATES': True,          # recalcul auto à chaque save
    'ALLOW_CYCLES': False,                 # interdire les cycles
    'LAG_DEFAULT': 0,

    # Ressources
    'ENABLE_RESOURCES': True,
    'OVERALLOCATION_WARNING': True,

    # Export
    'EXPORT_PDF_ENABLED': True,
    'EXPORT_EXCEL_ENABLED': True,
    'EXPORT_ICAL_ENABLED': True,

    # Permissions
    'REQUIRE_LOGIN': True,
    'PERMISSION_DECORATOR': 'django.contrib.auth.decorators.login_required',
}


def get_goplan_setting(key, default=None):
    """Récupère un setting GoPlan avec fallback par défaut."""
    user_settings = getattr(settings, 'GOPLAN_SETTINGS', {})
    return user_settings.get(key, GOPLAN_DEFAULTS.get(key, default))