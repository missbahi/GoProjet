import django.db.models.deletion
from django.db import migrations, models


def rattacher_calendriers(apps, schema_editor):
    Calendar = apps.get_model('goplan', 'GWorkCalendar')
    ExceptionModel = apps.get_model('goplan', 'GCalendarException')
    Plan = apps.get_model('goplan', 'GPlan')
    Projet = apps.get_model('projets', 'Projet')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    using = schema_editor.connection.alias
    content_type = ContentType.objects.using(using).filter(app_label='projets', model='projet').first()
    if content_type is None:
        return
    projects = dict(Projet.objects.using(using).values_list('pk', 'dossier_id'))
    for calendar in Calendar.objects.using(using).filter(dossier__isnull=True, is_default=False):
        plans = Plan.objects.using(using).filter(
            calendrier_id=calendar.pk, content_type_id=content_type.pk,
        )
        dossiers = {projects.get(plan.object_id) for plan in plans}
        for dossier_id in sorted(dossier for dossier in dossiers if dossier is not None):
            copy = Calendar.objects.using(using).create(
                nom=calendar.nom, jours_ouvres=calendar.jours_ouvres,
                heures_par_jour=calendar.heures_par_jour,
                is_default=False, dossier_id=dossier_id,
            )
            ExceptionModel.objects.using(using).bulk_create([
                ExceptionModel(
                    calendrier_id=copy.pk, date=exception.date,
                    heures=exception.heures,
                )
                for exception in ExceptionModel.objects.using(using).filter(calendrier_id=calendar.pk)
            ])
            ids = [pk for pk, owner in projects.items() if owner == dossier_id]
            plans.filter(object_id__in=ids).update(calendrier_id=copy.pk)


class Migration(migrations.Migration):
    dependencies = [
        ('goplan', '0011_performance_indexes'),
        ('projets', '0088_catalogues_dossier'),
    ]

    operations = [
        migrations.AddField(
            model_name='gworkcalendar',
            name='dossier',
            field=models.ForeignKey(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name='calendriers', to='projets.dossier',
            ),
        ),
        migrations.RunPython(rattacher_calendriers),
    ]
