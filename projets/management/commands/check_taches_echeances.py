from django.core.management.base import BaseCommand
from projets.signals.tache_echeances import check_echeances_taches_quotidien


class Command(BaseCommand):
    help = "Vérifie les échéances des tâches et envoie les alertes."

    def handle(self, *args, **options):
        stats = check_echeances_taches_quotidien()
        self.stdout.write(self.style.SUCCESS(
            f"✅ Échéances traitées : "
            f"aujourd'hui={stats['aujourdhui']}, "
            f"demain={stats['demain']}, "
            f"retard={stats['retard']}, "
            f"urgentes={stats['urgentes']}"
        ))