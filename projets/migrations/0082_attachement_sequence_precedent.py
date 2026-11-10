from django.db import migrations, models
import django.db.models.deletion


def backfill_attachement_chain(apps, schema_editor):
    Attachement = apps.get_model('projets', 'Attachement')
    database = schema_editor.connection.alias
    attachements = Attachement.objects.using(database).order_by(
        'projet_id', 'date_debut_periode', 'date_fin_periode', 'id'
    )

    sequence_by_project = {}
    previous_by_project = {}
    for attachement in attachements.iterator():
        projet_id = attachement.projet_id
        sequence = sequence_by_project.get(projet_id, 0) + 1
        previous_id = previous_by_project.get(projet_id)
        Attachement.objects.using(database).filter(pk=attachement.pk).update(
            sequence=sequence,
            precedent_id=previous_id,
        )
        sequence_by_project[projet_id] = sequence
        previous_by_project[projet_id] = attachement.pk


class Migration(migrations.Migration):

    dependencies = [
        ('projets', '0081_lignebordereau_expanded'),
    ]

    operations = [
        migrations.AddField(
            model_name='attachement',
            name='sequence',
            field=models.PositiveIntegerField(null=True, verbose_name="Ordre de l'attachement"),
        ),
        migrations.AddField(
            model_name='attachement',
            name='precedent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.DO_NOTHING,
                related_name='suivants',
                to='projets.attachement',
                verbose_name="Attachement précédent",
            ),
        ),
        migrations.RunPython(backfill_attachement_chain, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='attachement',
            name='sequence',
            field=models.PositiveIntegerField(verbose_name="Ordre de l'attachement"),
        ),
        migrations.AddConstraint(
            model_name='attachement',
            constraint=models.UniqueConstraint(
                fields=('projet', 'sequence'),
                name='unique_attachement_sequence_projet',
            ),
        ),
        migrations.AlterModelOptions(
            name='attachement',
            options={
                'ordering': ['projet', 'sequence'],
                'verbose_name': 'Attachement',
                'verbose_name_plural': 'Attachements',
            },
        ),
    ]
