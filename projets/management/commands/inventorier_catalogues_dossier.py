import json

from django.apps import apps
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Inventorie les catalogues historiques sans dossier, sans modifier aucune donnée."

    def add_arguments(self, parser):
        parser.add_argument('--json', action='store_true', dest='as_json', help='Sortie JSON avec identifiants.')

    def handle(self, *args, **options):
        inventory = {}
        for name in (
            'Client', 'Entreprise', 'Ingenieur', 'CategorieCharge', 'Personnel', 'Materiel',
            'Location', 'Transport', 'SousTraitance', 'Consommable', 'Fourniture',
        ):
            model = apps.get_model('projets', name)
            rows = model.objects.filter(dossier__isnull=True).order_by('pk')
            inventory[name] = [{'id': row.pk, 'libelle': str(row)} for row in rows]
        if options['as_json']:
            self.stdout.write(json.dumps(inventory, ensure_ascii=False))
            return
        for name, rows in inventory.items():
            self.stdout.write(f'{name}: {len(rows)} sans dossier')
            for row in rows:
                self.stdout.write(f"  #{row['id']} — {row['libelle']}")
