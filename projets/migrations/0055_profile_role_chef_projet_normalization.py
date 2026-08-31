from django.db import migrations, models


def normalize_role_chef_projet(apps, schema_editor):
    Profile = apps.get_model('projets', 'Profile')
    Profile.objects.filter(role='GERANT').update(role='CHEF_PROJET')


class Migration(migrations.Migration):

    dependencies = [
        ('projets', '0054_attachement_modifie_par'),
    ]

    operations = [
        migrations.AlterField(
            model_name='profile',
            name='role',
            field=models.CharField(
                choices=[
                    ('CHEF_PROJET', 'Chef de projet'),
                    ('GERANT', 'Chef de projet (historique)'),
                    ('STAFF', 'Staff'),
                    ('UTILISATEUR', 'Utilisateur'),
                ],
                default='UTILISATEUR',
                max_length=20,
            ),
        ),
        migrations.RunPython(
            normalize_role_chef_projet,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
