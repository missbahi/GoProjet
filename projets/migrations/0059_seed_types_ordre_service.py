from django.db import migrations


TYPES_ORDRE_SERVICE = [
    {
        'code': 'OSN',
        'nom': "OS de Notification de l'approbation du marché",
        'description': "Notification de l'approbation du marché",
        'ordre_min': 1,
        'ordre_max': 1,
        'unique_dans_projet': True,
        'prerequis': [],
    },
    {
        'code': 'OSC',
        'nom': 'OS de Commencement',
        'description': 'Ordre de commencement des travaux',
        'ordre_min': 2,
        'ordre_max': 2,
        'unique_dans_projet': True,
        'prerequis': ['OSN'],
    },
    {
        'code': 'OSA',
        'nom': "OS d'Arrêt",
        'description': 'Ordre d’arrêt des travaux',
        'ordre_min': 3,
        'ordre_max': 99,
        'unique_dans_projet': False,
        'prerequis': ['OSC'],
    },
    {
        'code': 'OSR',
        'nom': 'OS de Reprise',
        'description': 'Ordre de reprise des travaux',
        'ordre_min': 3,
        'ordre_max': 99,
        'unique_dans_projet': False,
        'prerequis': ['OSA'],
    },
    {
        'code': 'OSC10',
        'nom': "OS de Continuation jusqu'à 10%",
        'description': "Ordre de continuation jusqu'à 10%",
        'ordre_min': 3,
        'ordre_max': 99,
        'unique_dans_projet': False,
        'prerequis': ['OSC'],
    },
    {
        'code': 'OSV',
        'nom': "OS d'Approbation d'Avenant",
        'description': "Ordre d'approbation d'un avenant",
        'ordre_min': 3,
        'ordre_max': 99,
        'unique_dans_projet': False,
        'prerequis': ['OSC'],
    },
    {
        'code': 'AUTRE',
        'nom': 'Autre OS',
        'description': 'Autre ordre de service',
        'ordre_min': 3,
        'ordre_max': 99,
        'unique_dans_projet': False,
        'prerequis': [],
    },
]


def seed_types_ordre_service(apps, schema_editor):
    type_model = apps.get_model('projets', 'TypeOrdreService')
    types = {}

    for type_data in TYPES_ORDRE_SERVICE:
        prerequis = type_data['prerequis']
        defaults = {
            key: value for key, value in type_data.items()
            if key != 'prerequis'
        }
        type_instance, _ = type_model.objects.update_or_create(
            code=type_data['code'],
            defaults=defaults,
        )
        types[type_instance.code] = (type_instance, prerequis)

    for type_instance, prerequis in types.values():
        type_instance.precedent_obligatoire.set(
            [types[code][0] for code in prerequis]
        )


def unseed_types_ordre_service(apps, schema_editor):
    type_model = apps.get_model('projets', 'TypeOrdreService')
    type_model.objects.filter(
        code__in=[type_data['code'] for type_data in TYPES_ORDRE_SERVICE]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('projets', '0058_ressources_tarifs'),
    ]

    operations = [
        migrations.RunPython(seed_types_ordre_service, unseed_types_ordre_service),
    ]