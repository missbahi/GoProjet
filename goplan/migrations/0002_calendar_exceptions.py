# goplan/migrations/0002_calendar_exceptions.py
import datetime

import django.db.models.deletion
from django.db import migrations, models


def forward_data(apps, schema_editor):
    """Migre GWorkCalendar.exceptions (JSON) → GCalendarException (relationnel).

    ⚠️ Pendant cette opération, `GWorkCalendar` porte À LA FOIS :
      - le JSONField `exceptions` (encore présent)
      - la relation inverse `exceptions` (créée par GCalendarException)
    Le descripteur inverse masque le champ. On évite donc tout accès par
    attribut (`cal.exceptions`) et on passe par values_list / update().
    """
    GWorkCalendar = apps.get_model("goplan", "GWorkCalendar")
    GCalendarException = apps.get_model("goplan", "GCalendarException")

    rows = GWorkCalendar.objects.values_list("pk", "exceptions").iterator()
    for cal_id, raw in rows:
        raw = raw or []
        if isinstance(raw, dict):
            raw = [{"date": k, "heures": v} for k, v in raw.items()]
        seen = set()
        for item in raw:
            if not isinstance(item, dict):
                continue
            iso = item.get("date")
            if not iso:
                continue
            try:
                d = datetime.date.fromisoformat(str(iso))
            except ValueError:
                continue
            if d in seen:
                continue
            seen.add(d)
            try:
                heures = float(item.get("heures", 0) or 0)
            except (TypeError, ValueError):
                heures = 0.0
            GCalendarException.objects.create(
                calendrier_id=cal_id, date=d, heures=heures,
            )


def backward_data(apps, schema_editor):
    """Rollback : reconstruit le JSON depuis la table relationnelle.

    Même précaution : on écrit via QuerySet.update(), pas via attribut.
    """
    GWorkCalendar = apps.get_model("goplan", "GWorkCalendar")
    GCalendarException = apps.get_model("goplan", "GCalendarException")

    for cal_id, in GWorkCalendar.objects.values_list("pk").iterator():
        payload = [
            {"date": exc.date.isoformat(), "heures": float(exc.heures)}
            for exc in GCalendarException.objects
                                .filter(calendrier_id=cal_id)
                                .order_by("date")
        ]
        # ⚡ update() cible la colonne via _meta, ignore le descripteur inverse
        GWorkCalendar.objects.filter(pk=cal_id).update(exceptions=payload)


class Migration(migrations.Migration):
    dependencies = [("goplan", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="GCalendarException",
            fields=[
                ("id", models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name="ID",
                )),
                ("date", models.DateField(verbose_name="Date")),
                ("heures", models.DecimalField(
                    decimal_places=2, default=0,
                    max_digits=5, verbose_name="Heures",
                )),
                ("calendrier", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="exceptions",
                    to="goplan.gworkcalendar",
                )),
            ],
            options={
                "verbose_name": "Exception calendrier",
                "verbose_name_plural": "Exceptions calendrier",
                "ordering": ["date"],
            },
        ),
        migrations.RunPython(forward_data, backward_data),
        migrations.AddConstraint(
            model_name="gcalendarexception",
            constraint=models.UniqueConstraint(
                fields=("calendrier", "date"),
                name="goplan_calendar_unique_exception_date",
            ),
        ),
        migrations.RemoveField(model_name="gworkcalendar", name="exceptions"),
    ]