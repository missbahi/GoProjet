from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import date

from projets.models import Attachement, DocumentAdministratif, EtapeValidation, FichierSuivi, Notification, OrdreService, Projet
from django.contrib.auth.models import User

@receiver(post_save, sender=Projet)
def gerer_notifications_projet(sender, instance: Projet, created, **kwargs):
    if created:
        # Notification pour nouveau projet
        from projets.services.notification_service import NotificationService
        NotificationService.creer_notification_personnalisee(
            utilisateur=instance.chef_projet,
            type_notif='PROJET_MODIFIE',
            titre=f"Nouveau projet: {instance.nom}",
            message=f"Le projet {instance.nom} a été créé.",
            projet=instance,
            niveau_urgence='MOYEN'
        )
    else: 
        ancien_projet = Projet.objects.get(pk=instance.pk)
        
        if instance.en_retard and not ancien_projet.en_retard:
            Notification.creer_notification_projet(instance, 'RETARD')
        
        if instance.a_traiter and not ancien_projet.a_traiter:
            Notification.creer_notification_projet(instance, 'NOUVEAU_AO')
        
        if instance.reception_validee and not ancien_projet.reception_validee:
            Notification.creer_notification_projet(instance, 'RECEPTION')
        
        # Notification échéance projet
        if instance.date_limite_soumission and instance.date_limite_soumission != ancien_projet.date_limite_soumission:
            jours_restants = (instance.date_limite_soumission - date.today()).days
            if 0 < jours_restants <= 7:
                Notification.creer_notification_projet(instance, 'ECHEANCE')

@receiver(post_save, sender=Attachement)
def notifier_attachement_modifie(sender, instance: Attachement, created, **kwargs):
    print('notifier_validation_attachement')
    from projets.services.notification_service import NotificationService
    users = User.objects.filter(projets__id=instance.projet_id)
    type_notif = ''
    statut = instance.statut
    if created:
        type_notif = 'NOUVEL_ATTACHEMENT'
    elif statut == 'BROUILLON':
        type_notif = 'ATTACHEMENT_BROUILLON'
    elif statut == 'SIGNE':
        type_notif = 'ATTACHEMENT_SIGNE'
    elif statut == 'TRANSMIS':
        type_notif = 'ATTACHEMENT_TRANSMIS'
    elif statut == 'VALIDE':
        type_notif = 'ATTACHEMENT_VALIDE'
    elif statut == 'REFUSE':
        type_notif = 'ATTACHEMENT_REFUSE'
    elif statut == 'MODIFIE':
        type_notif = 'ATTACHEMENT_MODIFIE'
    else:
        return
    
    # TODO: notifier les validateurs techniques
    # en attendant on prend tous les utilisateurs du projet
    if hasattr(instance, 'modifie_par') and instance.modifie_par:
        user_projet = instance.modifie_par
    else:
        user_projet = None

    for user in users:
        NotificationService.notifier_attachement_modifie(instance, user_projet, user, type_notif)
            
   
@receiver(pre_save, sender=Projet)
def mettre_a_jour_indicateurs(sender, instance, **kwargs):
    if not getattr(instance, '_updating_flags', False):
        instance.update_status_flags(force_save=False)

@receiver(post_save, sender=OrdreService)
def gerer_notifications_os(sender, instance: OrdreService, created, **kwargs):
    if created:
        Notification.creer_notification_os(
            instance, 
            'AUTRE',
            utilisateurs_cibles=User.objects.filter(
                profile__role__in=['ADMIN', 'CHEF_PROJET']
            )
        )
    else:
        try:
            ancien_os = OrdreService.objects.get(pk=instance.pk)
            
            if instance.statut == 'NOTIFIE' and ancien_os.statut != 'NOTIFIE':
                Notification.creer_notification_os(instance, 'OS_NOTIFIE')
            elif instance.statut == 'ANNULE' and ancien_os.statut != 'ANNULE':
                Notification.creer_notification_os(instance, 'OS_ANNULE')
        except OrdreService.DoesNotExist:
            pass

@receiver(post_save, sender=OrdreService)
def verifier_echeances_os(sender, instance: OrdreService, **kwargs):
    if instance.date_limite:
        jours_restants = (instance.date_limite - timezone.now().date()).days
        
        if jours_restants == 7:
            Notification.creer_notification_os(instance, 'OS_ECHEANCE')
        elif jours_restants == 1:
            Notification.creer_notification_os(instance, 'OS_ECHEANCE')
