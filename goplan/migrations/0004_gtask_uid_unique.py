# goplan/migrations/0004_gtask_uid_unique.py
import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("goplan", "0003_gtask_uid_wbs_data")]

    operations = [
        # ⚡ Uniquement du DDL, sur une transaction fraîche.
        # Toutes les valeurs de uid sont déjà remplies et distinctes,
        # donc la contrainte unique peut être posée sans UPDATE préalable.
        migrations.AlterField(
            model_name="gtask",
            name="uid",
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, unique=True,
                verbose_name="UID",
            ),
        ),
    ]