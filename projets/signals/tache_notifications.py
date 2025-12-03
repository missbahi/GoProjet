from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from ..models import Tache, Notification

@receiver(post_save, sender=Tache)
def handle_tache_creation(sender, instance, created, **kwargs):
    """Gère les notifications lors de la création d'une tâche"""
    if created:
        # Déterminer qui doit être notifié
        utilisateurs_cibles = set(instance.projet.users.all())
        if instance.responsable:
            utilisateurs_cibles.add(instance.responsable)
        
        # Créer les notifications
        Notification.creer_notification_tache(
            tache=instance,
            type_notif='NOUVELLE_TACHE',
            emetteur=kwargs.get('request_user'),  # À passer via save() si possible
            utilisateurs_cibles=utilisateurs_cibles
        )
        
        # Notification spéciale au responsable
        if instance.responsable:
            Notification.creer_notification_tache(
                tache=instance,
                type_notif='TACHE_ASSIGNEE',
                emetteur=kwargs.get('request_user'),
                utilisateurs_cibles=[instance.responsable]
            )

@receiver(pre_save, sender=Tache)
def handle_tache_modification(sender, instance, **kwargs):
    """Gère les notifications lors de la modification d'une tâche"""
    if instance.pk:
        try:
            ancienne_tache = Tache.objects.get(pk=instance.pk)
            
            # Changement de responsable
            if ancienne_tache.responsable != instance.responsable:
                # Ancien responsable
                if ancienne_tache.responsable:
                    Notification.objects.create(
                        utilisateur=ancienne_tache.responsable,
                        projet=instance.projet,
                        tache=instance,
                        type_notification='TACHE_MODIFIEE',
                        titre="Réaffectation de tâche",
                        message=f"Vous n'êtes plus responsable de la tâche '{instance.titre}'",
                        action_url=f"/taches/{instance.id}/",
                        niveau_urgence='FAIBLE'
                    )
                
                # Nouveau responsable
                if instance.responsable:
                    Notification.creer_notification_tache(
                        tache=instance,
                        type_notif='TACHE_ASSIGNEE',
                        utilisateurs_cibles=[instance.responsable]
                    )
            
            # Tâche terminée
            if not ancienne_tache.terminee and instance.terminee:
                Notification.creer_notification_tache(
                    tache=instance,
                    type_notif='TACHE_TERMINEE',
                    utilisateurs_cibles=instance.projet.users.all()
                )
            
            # Tâche devenue urgente
            if ancienne_tache.priorite != 'URGENTE' and instance.priorite == 'URGENTE':
                Notification.creer_notification_tache(
                    tache=instance,
                    type_notif='TACHE_URGENTE',
                    utilisateurs_cibles=instance.projet.users.all()
                )
            # Tâche en retard (à vérifier via cron)
            if instance.jours_retard > 0:
                Notification.creer_notification_tache(
                    tache=instance, 
                    type_notif='TACHE_EN_RETARD',
                    utilisateurs_cibles=instance.projet.users.all()
                )
                
        except Tache.DoesNotExist:
            pass