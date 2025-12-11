# management/commands/import_indices.py
from django.core.management.base import BaseCommand
from projets.models import IndiceRevision, ValeurIndice
import csv
from datetime import datetime

class Command(BaseCommand):
    help = 'Importe les indices de révision officiels'
    
    def handle(self, *args, **kwargs):
        # Indices officiels marocains (exemples)
        indices = [
            {'code': 'BT01', 'libelle': 'Bâtiment gros œuvre', 'unite': 'Index'},
            {'code': 'BT02', 'libelle': 'Bâtiment second œuvre', 'unite': 'Index'},
            {'code': 'TP01', 'libelle': 'Travaux publics terrassement', 'unite': 'Index'},
            {'code': 'MA01', 'libelle': 'Main d\'œuvre bâtiment', 'unite': 'Heure'},
            {'code': 'AC01', 'libelle': 'Acier de construction', 'unite': 'Tonne'},
            {'code': 'CM01', 'libelle': 'Ciment', 'unite': 'Tonne'},
        ]
        
        for data in indices:
            indice, created = IndiceRevision.objects.update_or_create(
                code=data['code'],
                defaults=data
            )
            if created:
                self.stdout.write(f"Créé: {indice}")
            else:
                self.stdout.write(f"Mis à jour: {indice}")