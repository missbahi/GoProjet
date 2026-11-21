from django.db import migrations


INDEXES = (
    ("ING", "Ingénierie", "Index global"),
    ("TR5Bis", "Travaux routiers TR5 bis", "Routes"),
    ("TR2", "Travaux routiers TR2", "Routes"),
    ("BAT6", "Bâtiment tous corps d'état", "Bâtiment"),
    ("S", "Salaire et charges", "Salaire et charges"),
    ("Chtp", "Chauffage TP", "Salaire et charges"),
    ("Ch", "Charges", "Salaire et charges"),
    ("Mtn", "Matériel de transport", "Transport"),
    ("Mc3", "Matériel Mc3", "Matériels"),
    ("Pg", "Fonte", "Métaux ferreux"),
    ("Tpc", "Tuyau PVC", "Matériels"),
    ("Cu", "Cuivre", "Métaux non ferreux"),
    ("Ap", "Aluminium Ap", "Métaux non ferreux"),
    ("Ale", "Aluminium Ale", "Métaux non ferreux"),
    ("Cs", "Ciment en sacs", "Liants"),
)


def seed_indexes(apps, schema_editor):
    IndexReference = apps.get_model("projets", "IndexReference")
    for symbole, libelle, famille in INDEXES:
        IndexReference.objects.get_or_create(
            symbole=symbole,
            defaults={"libelle": libelle, "famille": famille},
        )


def normaliser_epoques_base(apps, schema_editor):
    Projet = apps.get_model("projets", "Projet")
    for projet in Projet.objects.exclude(epoque_base__isnull=True).iterator():
        mois = projet.epoque_base.replace(day=1)
        if mois != projet.epoque_base:
            Projet.objects.filter(pk=projet.pk).update(epoque_base=mois)


def unseed_indexes(apps, schema_editor):
    IndexReference = apps.get_model("projets", "IndexReference")
    IndexReference.objects.filter(
        symbole__in=[symbole for symbole, _, _ in INDEXES],
        termes_simples__isnull=True,
        termes_composites_a__isnull=True,
        termes_composites_b__isnull=True,
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("projets", "0094_indexreference_projet_appliquer_report_m_plus_2_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_indexes, unseed_indexes),
        migrations.RunPython(normaliser_epoques_base, migrations.RunPython.noop),
    ]
