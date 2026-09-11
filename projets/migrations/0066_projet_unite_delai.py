from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('projets', '0065_remove_legacy_category_choices'),
    ]

    operations = [
        migrations.AlterField(
            model_name='projet',
            name='delai',
            field=models.IntegerField(blank=True, default=0, null=True, verbose_name='Délai'),
        ),
        migrations.AddField(
            model_name='projet',
            name='unite_delai',
            field=models.CharField(
                choices=[('JOURS', 'Jours'), ('MOIS', 'Mois')],
                default='JOURS',
                max_length=5,
                verbose_name='Unité du délai',
            ),
        ),
    ]