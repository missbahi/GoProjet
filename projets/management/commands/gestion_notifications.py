# projets/management/commands/gestion_notifications.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

class Command(BaseCommand):
    """Gère les notifications périodiques (échéances, retards, nettoyage)"""
    
    help = 'Gère les notifications périodiques (échéances, retards, nettoyage)'
    
    def add_arguments(self, parser):
        """Définition des arguments optionnels - CETTE MÉTHODE DOIT ÊTRE PRÉSENTE"""
        parser.add_argument(
            '--action',
            type=str,
            choices=['cleanup', 'check', 'all'],
            default='all',
            help='Action spécifique à exécuter: cleanup, check, all'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Nombre de jours pour la suppression des anciennes notifications (default: 30)'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Mode verbeux avec plus de détails'
        )
    
    def handle(self, *args, **options):
        """Méthode principale exécutée"""
        action = options['action']
        days = options['days']
        verbose = options['verbose']
        
        if verbose:
            self.stdout.write("🚀 Mode verbeux activé")
            self.stdout.write(f"Action: {action}, Jours: {days}")
        
        self.stdout.write(f"🔍 Début de la gestion des notifications")
        
        # Votre logique ici...
        
        if action in ['cleanup', 'all']:
            cleaned = self.nettoyer_notifications(days, verbose)
            self.stdout.write(self.style.SUCCESS(
                f"🗑️  {cleaned} notifications expirées supprimées"
            ))
        
        if action in ['check', 'all']:
            checked = self.verifier_echeances(verbose)
            self.stdout.write(self.style.SUCCESS(
                f"🔔 {checked['notifications']} notifications créées"
            ))
        
        self.stdout.write("✅ Gestion terminée")
    
    def nettoyer_notifications(self, days, verbose=False):
        """Supprime les notifications expirées"""
        from ...models import Notification
        
        date_limite = timezone.now() - timedelta(days=days)
        
        if verbose:
            self.stdout.write(f"📅 Suppression des notifications avant {date_limite}")
        
        expired = Notification.objects.filter(
            expire_le__lt=timezone.now()
        )
        
        count = expired.count()
        
        if verbose and count > 0:
            self.stdout.write(f"📊 {count} notifications à supprimer:")
            for n in expired[:5]:  # Affiche les 5 premières
                self.stdout.write(f"   - {n.titre} (expire: {n.expire_le})")
            if count > 5:
                self.stdout.write(f"   ... et {count-5} autres")
        
        expired.delete()
        return count
    
    def verifier_echeances(self, verbose=False):
        """Vérifie les échéances des tâches et validations"""
        from ...models import Tache, ProcessValidation, Notification
        
        aujourdhui = timezone.now().date()
        notifications_creees = 0
        
        if verbose:
            self.stdout.write(f"📅 Date du jour: {aujourdhui}")
        
        # Vérifier les tâches
        taches_en_retard = Tache.objects.filter(
            date_fin__lt=aujourdhui,
            terminee=False
        ).select_related('projet', 'responsable')
        
        if verbose:
            self.stdout.write(f"📋 {taches_en_retard.count()} tâches en retard")
        
        for tache in taches_en_retard:
            if tache.responsable:
                Notification.objects.create(
                    utilisateur=tache.responsable,
                    projet=tache.projet,
                    type_notification='TACHE_EN_RETARD',
                    titre=f"⚠️ Tâche en retard: {tache.titre}",
                    message=f"La tâche '{tache.titre}' est en retard de {(aujourdhui - tache.date_fin).days} jours",
                    niveau_urgence='CRITIQUE',
                    action_url=f"/taches/{tache.id}/"
                )
                notifications_creees += 1
                
                if verbose:
                    self.stdout.write(f"   📨 Notification pour: {tache.responsable.username}")
        
        # Vérifier les validations
        validations_en_retard = ProcessValidation.objects.filter(
            date_limite__lt=timezone.now(),
            statut_validation='EN_ATTENTE'
        ).select_related('validateur', 'attachement__projet')
        
        if verbose:
            self.stdout.write(f"📄 {validations_en_retard.count()} validations en retard")
        
        for validation in validations_en_retard:
            if validation.validateur:
                Notification.objects.create(
                    utilisateur=validation.validateur,
                    projet=validation.attachement.projet,
                    type_notification='VALIDATION_EN_RETARD',
                    titre=f"⏰ Validation en retard",
                    message=f"La validation {validation.get_type_validation_display()} de l'attachement {validation.attachement.numero} est en retard",
                    niveau_urgence='CRITIQUE',
                    action_url=f"/attachements/{validation.attachement.id}/validations/"
                )
                notifications_creees += 1
        
        return {'notifications': notifications_creees}