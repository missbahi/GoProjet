from django.db.models.signals import post_save, pre_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import date

from projets.models import Attachement, Notification, OrdreService, Projet, RapportJournalier, SituationMensuelle
from django.contrib.auth.models import User

@receiver(post_save, sender=Projet)
def gerer_notifications_projet(sender, instance: Projet, created, **kwargs):
    if created:
        # Notification pour nouveau projet
        utilisateur = instance.users.first()
        if not utilisateur:
            return
        from projets.services.notification_service import NotificationService
        NotificationService.creer_notification_personnalisee(
            utilisateur=utilisateur,
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


@receiver(post_save, sender=OrdreService)
def verifier_echeances_os(sender, instance: OrdreService, **kwargs):
    if instance.date_limite:
        jours_restants = (instance.date_limite - timezone.now().date()).days
        
        if jours_restants == 7:
            Notification.creer_notification_os(instance, 'OS_ECHEANCE')
        elif jours_restants == 1:
            Notification.creer_notification_os(instance, 'OS_ECHEANCE')


def _utilisateurs_concernes(projet):
    from django.db.models import Q
    return User.objects.filter(
        Q(projets=projet) |
        Q(dossiers_geres__projets=projet) |
        Q(dossiers=projet.dossier)
    ).distinct()


@receiver(post_save, sender=RapportJournalier)
def notifier_rapport_journalier(sender, instance, created, **kwargs):
    type_notif = 'NOUVEAU_RAPPORT_JOURNALIER' if created else 'RAPPORT_JOURNALIER_MODIFIE'
    titre = 'Nouveau rapport journalier' if created else 'Rapport journalier modifié'
    for utilisateur in _utilisateurs_concernes(instance.projet):
        Notification.objects.create(
            utilisateur=utilisateur,
            projet=instance.projet,
            type_notification=type_notif,
            titre=f'{titre} - {instance.projet.nom}',
            message=f'Le rapport du {instance.date:%d/%m/%Y} du projet {instance.projet.nom} est disponible.',
            action_url=f'/projet/{instance.projet_id}/rapports-journaliers/{instance.pk}/',
            objet_id=instance.pk,
            objet_type='rapport_journalier',
        )


@receiver(pre_save, sender=SituationMensuelle)
def capturer_ancien_statut_situation(sender, instance, **kwargs):
    """Capture l'ancien statut AVANT le save."""
    if instance.pk:
        try:
            ancien = SituationMensuelle.objects.only('statut').get(pk=instance.pk)
            instance._ancien_statut = ancien.statut
        except SituationMensuelle.DoesNotExist:
            instance._ancien_statut = None
    else:
        instance._ancien_statut = None


@receiver(post_save, sender=SituationMensuelle)
def notifier_situation_mensuelle(sender, instance, created, **kwargs):
    """Notifie les utilisateurs selon le cycle de vie de la situation."""

    ancien_statut = getattr(instance, '_ancien_statut', None)

    # ── Changement de statut détecté ──
    if not created and ancien_statut is not None and ancien_statut != instance.statut:
        if instance.statut == SituationMensuelle.Statut.VALIDEE:
            _notifier_situation_validee(instance)
            return
        elif instance.statut == SituationMensuelle.Statut.BROUILLON and ancien_statut == SituationMensuelle.Statut.VALIDEE:
            _notifier_situation_devalidee(instance)
            return
    
    # ── Création / modification simple ──
    type_notif = 'NOUVELLE_SITUATION_MENSUELLE' if created else 'SITUATION_MENSUELLE_MODIFIEE'
    titre = 'Nouvelle situation mensuelle' if created else 'Situation mensuelle modifiée'
    periode = f'{instance.mois:02d}/{instance.annee}'
    notifications = [
        Notification(
            utilisateur_id=utilisateur_id,
            projet=instance.projet,
            type_notification=type_notif,
            titre=f'{titre} - {instance.projet.nom}',
            message=f'La situation mensuelle {periode} du projet {instance.projet.nom} est disponible.',
            action_url=f'/projet/{instance.projet_id}/situations-mensuelles/',
            objet_id=instance.pk,
            objet_type='situation_mensuelle',
        )
        for utilisateur_id in _utilisateurs_concernes(instance.projet).values_list('id', flat=True)
    ]
    Notification.objects.bulk_create(notifications)


def _notifier_situation_validee(instance):
    """Notification dédiée à la validation."""
    periode = f'{instance.mois:02d}/{instance.annee}'
    valideur = instance.validee_par
    valideur_label = (valideur.get_full_name() or valideur.username) if valideur else 'Système'
    
    notifications = [
        Notification(
            utilisateur_id=utilisateur_id,
            projet=instance.projet,
            type_notification='SITUATION_MENSUELLE_VALIDEE',
            titre=f'Situation {periode} validée - {instance.projet.nom}',
            message=(
                f'La situation mensuelle {periode} du projet {instance.projet.nom} '
                f'a été validée par {valideur_label}.'
            ),
            action_url=f'/projet/{instance.projet_id}/situations-mensuelles/{instance.pk}/apercu/',
            objet_id=instance.pk,
            objet_type='situation_mensuelle',
            niveau_urgence='INFO',
        )
        for utilisateur_id in _utilisateurs_concernes(instance.projet)
                              .exclude(id=valideur.id if valideur else None)
                              .values_list('id', flat=True)
    ]
    Notification.objects.bulk_create(notifications)


def _notifier_situation_devalidee(instance):
    """Notification dédiée à la dévalidation."""
    periode = f'{instance.mois:02d}/{instance.annee}'
    devalideur = instance.devalidee_par
    devalideur_label = (devalideur.get_full_name() or devalideur.username) if devalideur else 'Système'
    
    notifications = [
        Notification(
            utilisateur_id=utilisateur_id,
            projet=instance.projet,
            type_notification='SITUATION_MENSUELLE_DEVALIDEE',
            titre=f'⚠️ Situation {periode} rouverte - {instance.projet.nom}',
            message=(
                f'La situation mensuelle {periode} du projet {instance.projet.nom} '
                f'a été remise en brouillon par {devalideur_label}. '
                f'Elle est de nouveau modifiable.'
            ),
            action_url=f'/projet/{instance.projet_id}/situations-mensuelles/',
            objet_id=instance.pk,
            objet_type='situation_mensuelle',
            niveau_urgence='ELEVE',
        )
        for utilisateur_id in _utilisateurs_concernes(instance.projet)
                              .exclude(id=devalideur.id if devalideur else None)
                              .values_list('id', flat=True)
    ]
    Notification.objects.bulk_create(notifications)
