from django.apps import AppConfig


class GoplanConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'goplan'
    verbose_name = "GoPlan — Planification"

    def ready(self):
        # Charger les signaux
        from . import signals  # noqa