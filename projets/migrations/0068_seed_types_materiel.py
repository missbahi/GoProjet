# projets/migrations/0068_seed_types_materiel.py
"""
Initialise le référentiel TypeMateriel avec les 13 types prédéfinis
utilisés par l'application.

- Idempotent : utilise get_or_create sur `nom` (unique=True), donc
  réexécuter la migration ne crée pas de doublons.
- Reverse explicite : supprime uniquement les types de cette liste,
  sans toucher aux types ajoutés manuellement par la suite.
- Vérifie la présence physique des icônes dans
  static/images/materiels/ et log un warning (sans bloquer) sinon.
"""

from django.db import migrations


# (nom affiché, nom du fichier icône dans static/images/materiels/)
TYPES_MATERIEL_PREDEFINIS = [
    ("Autobétonnière",                  "autobeton.jpg"),
    ("Bobcat",                          "bobcat-cat.jpg"),
    ("Bulldozer",                       "bull-cat.jpg"),
    ("Camion solo",                     "camion-solo.avif"),
    ("Camion citerne",                  "camion-citerne.avif"),
    ("Chargeur",                        "chargeur-cat.jpg"),
    ("Compacteur",                      "compac-cat.jpg"),
    ("Minipelle",                       "minipelle-cat.jpg"),
    ("Niveleuse",                       "niveleuse-cat.jpg"),
    ("Pelle sur chenilles avec BRH",    "pelle-brh-cat.jpg"),
    ("Pelle sur chenilles avec godet",  "pelle-cat.jpg"),
    ("Pelle sur pneus",                 "pelle-pneus-cat.jpg"),
    ("Tractopelle",                     "tractopelle-cat.jpg"),
]


from django.contrib.staticfiles import finders

def seed_types_materiel(apps, schema_editor):
    TypeMateriel = apps.get_model("projets", "TypeMateriel")
    ICONE_DIR = "images/materiels"

    for nom, icone in TYPES_MATERIEL_PREDEFINIS:
        TypeMateriel.objects.get_or_create(
            nom=nom,
            defaults={"icone": icone, "actif": True},
        )
        if icone and not finders.find(f"{ICONE_DIR}/{icone}"):
            print(
                f"[seed_types_materiel] ATTENTION : icône introuvable "
                f"pour « {nom} » → {icone}"
            )


def unseed_types_materiel(apps, schema_editor):
    TypeMateriel = apps.get_model("projets", "TypeMateriel")
    noms = [nom for nom, _ in TYPES_MATERIEL_PREDEFINIS]
    TypeMateriel.objects.filter(nom__in=noms).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("projets", "0067_typemateriel_atelier"),
    ]

    operations = [
        migrations.RunPython(seed_types_materiel, unseed_types_materiel),
    ]