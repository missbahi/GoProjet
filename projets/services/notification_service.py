from django.db import transaction
from datetime import timedelta
from django.utils import timezone
from projets.models import Notification

class NotificationService:
    
    @staticmethod
    def creer_notification_personnalisee(utilisateur, type_notif, titre, message, projet=None, niveau_urgence='MOYEN', action_url=None):
        ''' Créer une notification personnalisée '''
        print(utilisateur, type_notif, titre, message, projet, niveau_urgence, action_url)
        
        return Notification.objects.create(
            utilisateur=utilisateur,
            projet=projet,
            type_notification=type_notif,
            titre=titre,
            message=message,
            niveau_urgence=niveau_urgence,
            action_url=action_url
        )
    
    @staticmethod
    def notifier_validation_attachement(attachement, validateur, type_notif='VALIDATION_ATTACHEMENT'):
        """Notification pour une validation d'attachement requise"""
        titre = f"Validation d'attachement: {attachement.numero}"
        message = f"L'attachement {attachement.numero} du projet {attachement.projet.nom} nécessite votre validation."
        action_url = f"/projets/attachement/{attachement.id}/validation/"
         
        return NotificationService.creer_notification_personnalisee(
            utilisateur=validateur,
            type_notif=type_notif,
            titre=titre,
            message=message,
            projet=attachement.projet,
            niveau_urgence='ELEVE',
            action_url=action_url
        )
    
    @staticmethod
    def notifier_attachement_modifie(attachement, emetteur, destinataire, type_notif='ATTACHEMENT_MODIFIE'):
        """Notification pour un attachement modifié"""
        TYPE_NOTIFICATION = Notification.TYPE_NOTIFICATION  # défini dans model Notification
        notifs = dict(TYPE_NOTIFICATION)
        
        titre = notifs[type_notif]
        if not emetteur:
            source = "Sytème"
        else:
            source = emetteur.get_full_name()
        titre = f"Statut de l'attachement: {attachement.numero} : {titre}"
        message = f"L'attachement {attachement.numero} du projet {attachement.projet.nom} a été mis à jour par {source}."
        action_url = f"/attachements/{attachement.id}/"

        return NotificationService.creer_notification_personnalisee(
            utilisateur=destinataire,
            type_notif=type_notif,
            titre=titre,
            message=message,
            projet=attachement.projet,
            niveau_urgence='MOYEN',
            action_url=action_url
        )
    @staticmethod
    def notifier_etape_validee(etape_validation):
        """Notification quand une étape est validée"""
        titre = f"Étape validée: {etape_validation.nom}"
        message = f"L'étape '{etape_validation.nom}' a été validée par {etape_validation.valide_par.username}."
        action_url = f"/projets/attachement/{etape_validation.processus_validation.attachement.id}/"
        
        # Notifier le chef de projet et l'admin
        utilisateurs = User.objects.filter(
            profile__role__in=['ADMIN', 'CHEF_PROJET'],
            profile__projets=etape_validation.processus_validation.attachement.projet
        ).distinct()
        
        notifications = []
        for user in utilisateurs:
            notification = NotificationService.creer_notification_personnalisee(
                utilisateur=user,
                type_notif='ETAPE_VALIDEE',
                titre=titre,
                message=message,
                projet=etape_validation.processus_validation.attachement.projet,
                niveau_urgence='FAIBLE',
                action_url=action_url
            )
            notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def notifier_document_a_signer(attachement, signataires):
        """Notification pour les documents à signer"""
        titre = f"Document à signer: {attachement.numero}"
        message = f"L'attachement {attachement.numero} est prêt pour signature."
        action_url = f"/projets/attachement/{attachement.id}/signature/"
        
        notifications = []
        for signataire in signataires:
            notification = NotificationService.creer_notification_personnalisee(
                utilisateur=signataire,
                type_notif='DOCUMENT_A_SIGNER',
                titre=titre,
                message=message,
                projet=attachement.projet,
                niveau_urgence='MOYEN',
                action_url=action_url
            )
            notifications.append(notification)
        
        return notifications
    
    @staticmethod
    def nettoyer_anciennes_notifications(jours=30):
        """Supprime les notifications anciennes"""
        date_limite = timezone.now() - timedelta(days=jours)
        deleted_count, _ = Notification.objects.filter(
            date_creation__lt=date_limite,
            lue=True
        ).delete()
        return deleted_count