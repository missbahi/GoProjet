from collections import defaultdict

import django.db.models.deletion
from django.db import migrations, models


CATALOGUES = (
    'Entreprise', 'Client', 'Ingenieur', 'CategorieCharge', 'Personnel',
    'Materiel', 'Location', 'Transport', 'SousTraitance', 'Consommable', 'Fourniture',
)
RESSOURCES = {
    'PERSONNEL': 'Personnel', 'MATERIEL': 'Materiel', 'LOCATION': 'Location',
    'TRANSPORT': 'Transport', 'SOUS_TRAITANCE': 'SousTraitance',
    'CONSOMMABLE': 'Consommable', 'FOURNITURE': 'Fourniture',
}
BASE = (
    ('PERSONNEL', 'Personnel'), ('MATERIEL', 'Matériel'), ('LOCATION', 'Location'),
    ('SOUS_TRAITANCE', 'Sous-traitance'), ('FOURNITURE', 'Fourniture'),
    ('TRANSPORT', 'Transport'), ('CONSOMMABLE', 'Consommable'),
)


def isoler_catalogues(apps, schema_editor):
    alias = schema_editor.connection.alias
    owners = defaultdict(set)
    unowned = set()
    references = []
    generic_references = []
    models_by_name = {name: apps.get_model('projets', name) for name in CATALOGUES}
    projet = apps.get_model('projets', 'Projet')
    projet_owners = dict(projet.objects.using(alias).values_list('pk', 'dossier_id'))

    def reference(name, source_id, dossier_id, model, pk, field):
        if source_id is None:
            return
        key = (name, source_id)
        if not models_by_name[name].objects.using(alias).filter(pk=source_id).exists():
            raise RuntimeError(f"Catalogue {name} #{source_id} introuvable ({model._meta.label} #{pk}).")
        if dossier_id is None:
            unowned.add(key)
        else:
            owners[key].add(dossier_id)
        references.append((key, dossier_id, model, pk, field))

    # Explicit reference paths avoid guessing ownership from users or unrelated dossiers.
    paths = (
        ('Entreprise', 'Projet', 'entreprise_id', 'dossier_id'),
        ('CategorieCharge', 'DepenseRapportJournalier', 'categorie_charge_id', 'rapport__projet__dossier_id'),
        ('CategorieCharge', 'DepenseSituationMensuelle', 'categorie_charge_id', 'situation__projet__dossier_id'),
        ('CategorieCharge', 'RessourceAffectee', 'categorie_charge_id', 'projet__dossier_id'),
        ('Materiel', 'ReleveMateriel', 'materiel_id', 'rapport__projet__dossier_id'),
        ('Materiel', 'AffectationRessource', 'materiel_id', 'atelier__projet__dossier_id'),
    )
    known_relations = set()
    for name, referencing_name, field, path in paths:
        model = apps.get_model('projets', referencing_name)
        known_relations.add((model._meta.label_lower, field))
        for pk, source_id, dossier_id in model.objects.using(alias).values_list('pk', field, path):
            reference(name, source_id, dossier_id, model, pk, field)

    for name, model in models_by_name.items():
        for relation in model._meta.related_objects:
            field = relation.field
            related = relation.related_model
            if (related._meta.label_lower, field.attname) in known_relations:
                continue
            if related.objects.using(alias).filter(**{field.attname + '__isnull': False}).exists():
                raise RuntimeError(
                    f"Référence catalogue non classable : {related._meta.label}.{field.name}. "
                    "Définir explicitement son dossier avant de poursuivre."
                )

    affectee = apps.get_model('projets', 'RessourceAffectee')
    for pk, code, source_id, dossier_id in affectee.objects.using(alias).values_list(
        'pk', 'categorie_charge__code', 'objet_id', 'projet__dossier_id',
    ):
        name = RESSOURCES.get(code)
        if not name:
            raise RuntimeError(f"Ressource affectée #{pk} : catégorie {code!r} non classable.")
        reference(name, source_id, dossier_id, affectee, pk, 'objet_id')

    # Planning resources have generic catalogue pointers and may span several projects.
    content_type = apps.get_model('contenttypes', 'ContentType')
    catalogue_types = dict(content_type.objects.using(alias).filter(
        app_label='projets', model__in=[name.lower() for name in CATALOGUES],
    ).values_list('pk', 'model'))
    projet_type = content_type.objects.using(alias).filter(app_label='projets', model='projet').first()
    try:
        planning_resource = apps.get_model('goplan', 'GResource')
        assignment = apps.get_model('goplan', 'GTaskAssignment')
    except LookupError:
        planning_resource = None
    if planning_resource:
        names = {name.lower(): name for name in CATALOGUES}
        for wrapper in planning_resource.objects.using(alias).filter(content_type_id__in=catalogue_types):
            key = (names[catalogue_types[wrapper.content_type_id]], wrapper.object_id)
            if not models_by_name[key[0]].objects.using(alias).filter(pk=key[1]).exists():
                raise RuntimeError(f"Ressource planning #{wrapper.pk} : référence {key!r} introuvable.")
            contexts = []
            for item in assignment.objects.using(alias).filter(ressource_id=wrapper.pk).values(
                'pk', 'tache__plan__content_type_id', 'tache__plan__object_id',
            ):
                dossier_id = None
                if projet_type and item['tache__plan__content_type_id'] == projet_type.pk:
                    dossier_id = projet_owners.get(item['tache__plan__object_id'])
                contexts.append((item['pk'], dossier_id))
                if dossier_id:
                    owners[key].add(dossier_id)
                else:
                    unowned.add(key)
            if not contexts:
                unowned.add(key)
            generic_references.append((key, wrapper, contexts))

    # Other generic history (e.g. admin log entries) has no dossier ownership.
    # Retain its original target rather than moving that history to a guessed owner.
    names = {name.lower(): name for name in CATALOGUES}
    for model in apps.get_models():
        if model == planning_resource:
            continue
        fields = {field.name for field in model._meta.fields}
        if not {'content_type', 'object_id'}.issubset(fields):
            continue
        for type_id, source_id in model.objects.using(alias).filter(
            content_type_id__in=catalogue_types,
        ).values_list('content_type_id', 'object_id'):
            try:
                key = (names[catalogue_types[type_id]], int(source_id))
            except (ValueError, TypeError):
                raise RuntimeError(f"Historique {model._meta.label} : identifiant catalogue invalide {source_id!r}.")
            if not models_by_name[key[0]].objects.using(alias).filter(pk=key[1]).exists():
                raise RuntimeError(f"Historique {model._meta.label} : référence {key!r} introuvable.")
            unowned.add(key)

    # Keep an original unowned whenever any history lacks a determinable dossier.
    copies = {}
    for name, model in models_by_name.items():
        for original in list(model.objects.using(alias).all()):
            key = (name, original.pk)
            dossier_ids = sorted(owners[key])
            original_id = original.pk
            for index, dossier_id in enumerate(dossier_ids):
                if index == 0 and key not in unowned:
                    model.objects.using(alias).filter(pk=original_id).update(dossier_id=dossier_id)
                    copies[(key, dossier_id)] = original_id
                else:
                    values = {
                        field.attname: getattr(original, field.attname)
                        for field in model._meta.local_fields
                        if not field.primary_key and field.name != 'dossier'
                    }
                    clone = model.objects.using(alias).create(dossier_id=dossier_id, **values)
                    copies[(key, dossier_id)] = clone.pk
    for key, dossier_id, model, pk, field in references:
        if dossier_id:
            model.objects.using(alias).filter(pk=pk).update(**{field: copies[(key, dossier_id)]})
    for key, wrapper, contexts in generic_references:
        grouped = defaultdict(list)
        for pk, dossier_id in contexts:
            grouped[dossier_id].append(pk)
        original_available = None not in grouped and bool(grouped)
        for dossier_id, ids in grouped.items():
            if dossier_id is None:
                continue
            target = copies[(key, dossier_id)]
            if original_available:
                planning_resource.objects.using(alias).filter(pk=wrapper.pk).update(object_id=target)
                original_available = False
            else:
                values = {
                    field.attname: getattr(wrapper, field.attname)
                    for field in planning_resource._meta.local_fields
                    if not field.primary_key
                }
                values['object_id'] = target
                clone = planning_resource.objects.using(alias).create(**values)
                assignment.objects.using(alias).filter(pk__in=ids).update(ressource_id=clone.pk)

    category = models_by_name['CategorieCharge']
    for dossier_id in apps.get_model('projets', 'Dossier').objects.using(alias).values_list('pk', flat=True):
        for ordre, (code, nom) in enumerate(BASE, start=1):
            category.objects.using(alias).get_or_create(
                dossier_id=dossier_id, code=code, defaults={'nom': nom, 'ordre': ordre},
            )
    for name, model in models_by_name.items():
        ids = list(model.objects.using(alias).filter(dossier__isnull=True).values_list('pk', flat=True))
        if ids:
            print(f"Catalogue à classer — {name}: {ids}. Conservé sans dossier; réservé à l'Admin.")


class Migration(migrations.Migration):
    dependencies = [
        ('projets', '0087_remove_retired_profile_role_choices'),
        ('goplan', '0011_performance_indexes'),
    ]

    operations = [
        migrations.AddField(
            model_name=name.lower(), name='dossier',
            field=models.ForeignKey(
                to='projets.dossier', on_delete=django.db.models.deletion.PROTECT,
                null=True, blank=True,
                related_name='categoriecharge_catalogue' if name == 'CategorieCharge' else '%(class)s_catalogue',
            ),
        ) for name in CATALOGUES
    ] + [
        migrations.AlterField(
            model_name='categoriecharge', name='code',
            field=models.SlugField(max_length=50, verbose_name='Code'),
        ),
        migrations.RunPython(isoler_catalogues),
        migrations.AddConstraint(
            model_name='categoriecharge',
            constraint=models.UniqueConstraint(fields=('dossier', 'code'), name='categorie_code_dossier_unique'),
        ),
        migrations.AddConstraint(
            model_name='categoriecharge',
            constraint=models.UniqueConstraint(
                fields=('code',), condition=models.Q(dossier__isnull=True),
                name='categorie_code_orphelin_unique',
            ),
        ),
    ]
