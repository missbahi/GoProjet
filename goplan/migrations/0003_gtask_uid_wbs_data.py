# goplan/migrations/0003_gtask_uid_wbs_data.py
import uuid
from collections import defaultdict

from django.db import migrations, models


def populate_uid(apps, schema_editor):
    """Génère un UUID unique pour chaque tâche existante."""
    GTask = apps.get_model("goplan", "GTask")
    for task in GTask.objects.filter(uid__isnull=True).iterator():
        task.uid = uuid.uuid4()
        task.save(update_fields=["uid"])


def populate_wbs(apps, schema_editor):
    """Calcule le WBS hiérarchique de chaque plan."""
    GPlan = apps.get_model("goplan", "GPlan")
    GTask = apps.get_model("goplan", "GTask")

    for plan in GPlan.objects.all().iterator():
        tasks = list(GTask.objects.filter(plan=plan).order_by("ordre", "pk"))
        if not tasks:
            continue
        by_parent = defaultdict(list)
        for t in tasks:
            by_parent[t.parent_id].append(t)
        for siblings in by_parent.values():
            siblings.sort(key=lambda t: (t.ordre, t.pk))

        updates = []

        def visit(parent_id, prefix):
            for idx, task in enumerate(by_parent.get(parent_id, []), start=1):
                wbs = f"{prefix}{idx}"
                if task.wbs != wbs:
                    task.wbs = wbs
                    updates.append(task)
                visit(task.pk, f"{wbs}.")

        visit(None, "")
        if updates:
            GTask.objects.bulk_update(updates, ["wbs"])


class Migration(migrations.Migration):
    dependencies = [("goplan", "0002_calendar_exceptions")]

    operations = [
        # 1. Ajout des champs (uid nullable pour permettre le remplissage)
        migrations.AddField(
            model_name="gtask",
            name="uid",
            field=models.UUIDField(
                null=True, blank=True, editable=False, verbose_name="UID",
            ),
        ),
        migrations.AddField(
            model_name="gtask",
            name="wbs",
            field=models.CharField(
                blank=True, default="", editable=False,
                max_length=50, verbose_name="WBS",
            ),
            preserve_default=False,
        ),
        # 2. Remplissage des données — PAS d'AlterField ici
        migrations.RunPython(populate_uid, migrations.RunPython.noop),
        migrations.RunPython(populate_wbs, migrations.RunPython.noop),
    ]