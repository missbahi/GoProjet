# signals/validation_notifications.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from django.utils.translation import gettext as _
from datetime import timedelta

from ..models import ProcessValidation, EtapeValidation, Notification, Projet, User

def create_validation_notification(process_validation, type_notif, emetteur=None, utilisateurs_cibles=None):
    """Helper pour créer des notifications de validation"""
    
    titre_map = {
        'VALIDATION_DEMANDEE': f"🔄 Validation demandée: {process_validation.get_type_validation_display()}",
        'VALIDATION_EN_ATTENTE': f"⏳ Validation en attente: {process_validation.get_type_validation_display()}",
        'VALIDATION_VALIDEE': f"✅ Validation approuvée: {process_validation.get_type_validation_display()}",
        'VALIDATION_REJETEE': f"❌ Validation rejetée: {process_validation.get_type_validation_display()}",
        'VALIDATION_CORRECTION': f"🔧 Correction demandée: {process_validation.get_type_validation_display()}",
        'VALIDATION_EN_RETARD': f"⚠️ Validation en retard: {process_validation.get_type_validation_display()}",
        'VALIDATION_ECHEANCE': f"📅 Échéance approchante: {process_validation.get_type_validation_display()}",
    }
    
    message_map = {
        'VALIDATION_DEMANDEE': f"Une validation {process_validation.get_type_validation_display()} a été demandée pour l'attachement {process_validation.attachement.numero}",
        'VALIDATION_EN_ATTENTE': f"La validation {process_validation.get_type_validation_display()} de l'attachement {process_validation.attachement.numero} est en attente de votre approbation",
        'VALIDATION_VALIDEE': f"La validation {process_validation.get_type_validation_display()} de l'attachement {process_validation.attachement.numero} a été approuvée",
        'VALIDATION_REJETEE': f"La validation {process_validation.get_type_validation_display()} de l'attachement {process_validation.attachement.numero} a été rejetée",
        'VALIDATION_CORRECTION': f"Des corrections sont demandées pour la validation {process_validation.get_type_validation_display()} de l'attachement {process_validation.attachement.numero}",
        'VALIDATION_EN_RETARD': f"La validation {process_validation.get_type_validation_display()} de l'attachement {process_validation.attachement.numero} est en retard",
        'VALIDATION_ECHEANCE': f"L'échéance de validation {process_validation.get_type_validation_display()} de l'attachement {process_validation.attachement.numero} approche",
    }
    
    niveau_urgence_map = {
        'VALIDATION_DEMANDEE': 'MOYEN',
        'VALIDATION_EN_ATTENTE': 'MOYEN',
        'VALIDATION_VALIDEE': 'INFO',
        'VALIDATION_REJETEE': 'ELEVE',
        'VALIDATION_CORRECTION': 'MOYEN',
        'VALIDATION_EN_RETARD': 'CRITIQUE',
        'VALIDATION_ECHEANCE': 'ELEVE',
    }
    
    # Par défaut, notifier le validateur et le demandeur
    if utilisateurs_cibles is None:
        utilisateurs_cibles = set()
        if process_validation.validateur:
            utilisateurs_cibles.add(process_validation.validateur)
        if process_validation.demandeur_validation:
            utilisateurs_cibles.add(process_validation.demandeur_validation)
        
        # Notifier aussi les responsables du projet
        projet = process_validation.attachement.projet
        if projet:
            for user in projet.users.all():
                utilisateurs_cibles.add(user)
    
    notifications = []
    for user in utilisateurs_cibles:
        notification = Notification(
            utilisateur=user,
            projet=process_validation.attachement.projet if process_validation.attachement.projet else None,
            emetteur=emetteur,
            type_notification='VALIDATION_ATTACHEMENT',
            titre=titre_map.get(type_notif, "Notification validation"),
            message=message_map.get(type_notif, f"Notification pour la validation {process_validation.id}"),
            niveau_urgence=niveau_urgence_map.get(type_notif, 'MOYEN'),
            action_url=f"/attachements/{process_validation.attachement.id}/validations/{process_validation.id}/",
            objet_id=process_validation.id,
            objet_type='process_validation',
            date_echeance=process_validation.date_limite if type_notif in ['VALIDATION_ECHEANCE', 'VALIDATION_EN_RETARD'] else None,
            prioritaire=type_notif in ['VALIDATION_EN_RETARD', 'VALIDATION_REJETEE'],
            can_be_closed=True
        )
        notifications.append(notification)
    
    Notification.objects.bulk_create(notifications)
    return notifications

@receiver(post_save, sender=ProcessValidation)
def handle_process_validation_creation(sender, instance, created, **kwargs):
    """Notifications lors de la création d'un processus de validation"""
    if created:
        # Notification au validateur désigné
        if instance.validateur:
            create_validation_notification(
                instance,
                'VALIDATION_EN_ATTENTE',
                emetteur=instance.demandeur_validation,
                utilisateurs_cibles=[instance.validateur]
            )
        
        # Notification au demandeur
        if instance.demandeur_validation:
            create_validation_notification(
                instance,
                'VALIDATION_DEMANDEE',
                emetteur=instance.demandeur_validation,
                utilisateurs_cibles=[instance.demandeur_validation]
            )
        
        # Notification aux responsables du projet
        if instance.attachement.projet:
            create_validation_notification(
                instance,
                'VALIDATION_DEMANDEE',
                emetteur=instance.demandeur_validation,
                utilisateurs_cibles=instance.attachement.projet.users.all()
            )

@receiver(pre_save, sender=ProcessValidation)
def handle_process_validation_modification(sender, instance, **kwargs):
    """Notifications lors des modifications d'un processus de validation"""
    if instance.pk:
        try:
            ancien_process = ProcessValidation.objects.get(pk=instance.pk)
            
            # Changement de statut
            if ancien_process.statut_validation != instance.statut_validation:
                if instance.statut_validation == 'VALIDE':
                    create_validation_notification(
                        instance,
                        'VALIDATION_VALIDEE',
                        emetteur=instance.validateur,
                        utilisateurs_cibles=instance.attachement.projet.users.all() if instance.attachement.projet else []
                    )
                    
                elif instance.statut_validation == 'REJETE':
                    create_validation_notification(
                        instance,
                        'VALIDATION_REJETEE',
                        emetteur=instance.validateur,
                        utilisateurs_cibles=[instance.demandeur_validation] if instance.demandeur_validation else []
                    )
                    
                elif instance.statut_validation == 'CORRECTION':
                    create_validation_notification(
                        instance,
                        'VALIDATION_CORRECTION',
                        emetteur=instance.validateur,
                        utilisateurs_cibles=[instance.demandeur_validation] if instance.demandeur_validation else []
                    )
            
            # Changement de validateur
            if ancien_process.validateur != instance.validateur and instance.validateur:
                # Nouveau validateur
                create_validation_notification(
                    instance,
                    'VALIDATION_EN_ATTENTE',
                    emetteur=instance.demandeur_validation,
                    utilisateurs_cibles=[instance.validateur]
                )
        
        except ProcessValidation.DoesNotExist:
            pass

@receiver(post_save, sender=EtapeValidation)
def handle_etape_validation(sender, instance, created, **kwargs):
    """Notifications pour les étapes de validation"""
    if created:
        # Notification au validateur du processus parent
        if instance.processValidation.validateur:
            Notification.objects.create(
                utilisateur=instance.processValidation.validateur,
                projet=instance.processValidation.attachement.projet,
                type_notification='ETAPE_VALIDATION',
                titre=f"Nouvelle étape de validation: {instance.nom}",
                message=f"Une nouvelle étape '{instance.nom}' a été ajoutée au processus de validation",
                niveau_urgence='MOYEN',
                action_url=f"/validations/{instance.processValidation.id}/etapes/",
                objet_id=instance.id,
                objet_type='etape_validation'
            )
    
    # Quand une étape est validée
    elif not created and instance.est_validee:
        # Notifier le validateur du processus
        if instance.processValidation.validateur:
            Notification.objects.create(
                utilisateur=instance.processValidation.validateur,
                projet=instance.processValidation.attachement.projet,
                type_notification='ETAPE_VALIDEE',
                titre=f"✅ Étape validée: {instance.nom}",
                message=f"L'étape '{instance.nom}' a été validée par {instance.valide_par.get_full_name()}",
                niveau_urgence='INFO',
                action_url=f"/validations/{instance.processValidation.id}/etapes/",
                objet_id=instance.id,
                objet_type='etape_validation'
            )
        
        # Notifier le demandeur si c'est différent
        if (instance.processValidation.demandeur_validation and 
            instance.processValidation.demandeur_validation != instance.processValidation.validateur):
            Notification.objects.create(
                utilisateur=instance.processValidation.demandeur_validation,
                projet=instance.processValidation.attachement.projet,
                type_notification='ETAPE_VALIDEE',
                titre=f"Étape validée: {instance.nom}",
                message=f"L'étape '{instance.nom}' a été validée",
                niveau_urgence='INFO',
                action_url=f"/validations/{instance.processValidation.id}/etapes/",
                objet_id=instance.id,
                objet_type='etape_validation'
            )