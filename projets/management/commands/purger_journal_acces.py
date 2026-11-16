from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from projets.models.journal import JournalAcces


class Command(BaseCommand):
    help = "Supprime les entrées du journal d'accès plus anciennes que N mois."

    def add_arguments(self, parser):
        parser.add_argument('--mois', type=int, default=12)

    def handle(self, *args, **options):
        limite = timezone.now() - timedelta(days=30 * options['mois'])
        supprimees, _ = JournalAcces.objects.filter(date__lt=limite).delete()
        self.stdout.write(f"{supprimees} entrée(s) supprimée(s).")
