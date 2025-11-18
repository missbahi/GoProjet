# management/commands/load_os_types.py
from django.core.management.base import BaseCommand
from projets.models import TypeOrdreService

class Command(BaseCommand):
    help = 'Charge les types d\'ordres de service initiaux'

    def handle(self, *args, **options):
        types_data = [
            {
                'code': 'OSN',
                'nom': 'OS de Notification de l\'approbation du marché',
                'description': 'Premier OS notifiant l\'approbation du marché',
                'ordre_min': 1,
                'ordre_max': 1,
                'unique_dans_projet': True,
                'precedent_obligatoire': []
            },
            {
                'code': 'OSC',
                'nom': 'OS de Commencement',
                'description': 'OS autorisant le commencement des travaux',
                'ordre_min': 2,
                'ordre_max': 2,
                'unique_dans_projet': True,
                'precedent_obligatoire': ['OSN']
            },
            {
                'code': 'OSA',  # Code unique pour l'arrêt
                'nom': 'OS d\'Arrêt',
                'description': 'OS ordonnant l\'arrêt des travaux',
                'ordre_min': 3,
                'ordre_max': 100,
                'unique_dans_projet': False,
                'precedent_obligatoire': ['OSC']
            },
            {
                'code': 'OSR',
                'nom': 'OS de Reprise',
                'description': 'OS autorisant la reprise des travaux après arrêt',
                'ordre_min': 4,
                'ordre_max': 100,
                'unique_dans_projet': False,
                'precedent_obligatoire': ['OSA']  # Référence au code corrigé
            },
            {
                'code': 'OSC10',
                'nom': 'OS de Continuation jusqu\'à 10%',
                'description': 'OS autorisant la continuation des travaux au-delà du montant initial jusqu\'à 10%',
                'ordre_min': 3,
                'ordre_max': 100,
                'unique_dans_projet': False,
                'precedent_obligatoire': ['OSC']
            },
            {
                'code': 'OSV',  # Code unique pour l'avenant
                'nom': 'OS d\'Approbation d\'Avenant',
                'description': 'OS approuvant un avenant au marché',
                'ordre_min': 3,
                'ordre_max': 100,
                'unique_dans_projet': False,
                'precedent_obligatoire': ['OSC']
            }
        ]

        for type_data in types_data:
            precedents = type_data.pop('precedent_obligatoire')
            
            try:
                type_os, created = TypeOrdreService.objects.get_or_create(
                    code=type_data['code'],
                    defaults=type_data
                )
                
                if created:
                    self.stdout.write(f"✅ Type {type_os.code} créé")
                    
                    # Ajouter les prérequis
                    for precedent_code in precedents:
                        try:
                            precedent = TypeOrdreService.objects.get(code=precedent_code)
                            type_os.precedent_obligatoire.add(precedent)
                            self.stdout.write(f"   ↳ Prérequis {precedent_code} ajouté")
                        except TypeOrdreService.DoesNotExist:
                            self.stdout.write(f"❌ Prérequis {precedent_code} non trouvé pour {type_os.code}")
                else:
                    self.stdout.write(f"⚠️ Type {type_os.code} existe déjà")
                    
            except Exception as e:
                self.stdout.write(f"❌ Erreur avec {type_data['code']}: {e}")

        self.stdout.write(self.style.SUCCESS(f'✅ {TypeOrdreService.objects.count()} types d\'OS chargés'))

