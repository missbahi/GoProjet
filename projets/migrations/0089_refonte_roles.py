from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def reclassify_historical_roles(apps, schema_editor):
    Profile = apps.get_model('projets', 'Profile')
    profiles = Profile.objects.using(schema_editor.connection.alias)
    profiles.filter(role='GERANT').update(role='ADMIN_DOSSIER')
    # Historical project chiefs had dossier-wide authority. Their intended new
    # role cannot be inferred safely from their existing project assignments.
    profiles.filter(role='CHEF_PROJET').update(role='A_RECLASSER')


class Migration(migrations.Migration):
    dependencies = [
        ('projets', '0088_catalogues_dossier'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='profile', name='created_by',
            field=models.ForeignKey(
                to=settings.AUTH_USER_MODEL, on_delete=django.db.models.deletion.SET_NULL,
                null=True, blank=True, related_name='comptes_crees',
            ),
        ),
        migrations.RunPython(reclassify_historical_roles, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='profile', name='role',
            field=models.CharField(
                max_length=20, default='UTILISATEUR',
                choices=[
                    ('ADMIN_DOSSIER', 'Administrateur de dossier'),
                    ('DIRECTEUR_PROJET', 'Directeur de projet'),
                    ('CHEF_PROJET', 'Chef de projet'),
                    ('CHEF_CHANTIER', 'Chef de chantier'),
                    ('POINTEUR', 'Pointeur'),
                    ('OBSERVATEUR', 'Observateur'),
                ],
            ),
        ),
    ]
