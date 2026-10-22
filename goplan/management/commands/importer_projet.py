from django.core.management.base import BaseCommand
from projets.models import Projet
from goplan.models import GPlan, GTask
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = "Importe un projet GoProjet dans GoPlan"

    def add_arguments(self, parser):
        parser.add_argument('projet_id', type=int)

    def handle(self, *args, **options):
        projet = Projet.objects.get(pk=options['projet_id'])
        ct = ContentType.objects.get_for_model(Projet)

        plan, _ = GPlan.objects.get_or_create(
            content_type=ct, object_id=projet.id,
            defaults={'nom': f"Planning — {projet.nom}", 'date_debut': projet.date_debut},
        )

        for tache in projet.tache_set.all():
            GTask.objects.get_or_create(
                plan=plan, code=str(tache.id),
                defaults={
                    'nom': tache.titre,
                    'description': tache.description,
                    'duree': (tache.date_fin - tache.date_debut).days or 1,
                    'date_debut': tache.date_debut,
                    'date_fin': tache.date_fin,
                    'avancement': tache.avancement,
                },
            )

        self.stdout.write(self.style.SUCCESS(f"✅ Plan créé : {plan.id}"))