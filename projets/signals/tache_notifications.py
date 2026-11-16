from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from ..models import Tache, Notification
from .tache_echeances import send_email_notification


def _envoyer_email_affectation(tache, emetteur):
    """E-mail au seul responsable, si l'envoi d'e-mails est activé."""
    responsable = tache.responsable
    if not getattr(settings, 'SEND_EMAIL_NOTIFICATIONS', False) or not responsable:
        return
    site = getattr(settings, 'SITE_NAME', 'GoProjet')
    par = ''
    if emetteur:
        par = f" par {emetteur.get_full_name().strip() or emetteur.username}"
    lignes = [
        f"Bonjour {responsable.get_full_name().strip() or responsable.username},",
        "",
        f"Vous avez été désigné(e){par} comme responsable de la tâche « {tache.titre} ».",
        f"Projet : {tache.projet.nom}",
        f"Priorité : {tache.get_priorite_display()}",
    ]
    if tache.date_fin:
        lignes.append(f"Échéance : {tache.date_fin:%d/%m/%Y}")
    site_url = getattr(settings, 'SITE_URL', '')
    if site_url:
        lignes += ["", f"{site_url.rstrip('/')}/projet/{tache.projet_id}/taches/{tache.pk}/"]
    send_email_notification(
        responsable, f"[{site}] Tâche assignée : {tache.titre}", "\n".join(lignes),
    )


@receiver(pre_save, sender=Tache)
def memoriser_etat_tache(sender, instance, **kwargs):
    """Mémorise l'état précédent pour décider des notifications après sauvegarde."""
    ancien = None
    if instance.pk:
        ancien = Tache.objects.filter(pk=instance.pk).values(
            'responsable_id', 'priorite', 'terminee', 'avancement',
        ).first()
    instance._etait_existante = ancien is not None
    instance._ancien_responsable_id = ancien['responsable_id'] if ancien else None
    instance._ancienne_priorite = ancien['priorite'] if ancien else None
    instance._etait_achevee = bool(ancien and (ancien['terminee'] or ancien['avancement'] >= 100))


@receiver(post_save, sender=Tache)
def notifier_responsable_tache(sender, instance, created, **kwargs):
    """Seul le responsable est notifié : affectation, réaffectation, passage en urgence."""
    emetteur = getattr(instance, '_emetteur', None)
    responsable = instance.responsable
    ancien_id = getattr(instance, '_ancien_responsable_id', None)
    existante = getattr(instance, '_etait_existante', False)

    achevee = instance.terminee or instance.avancement >= 100
    createur = instance.cree_par
    if (existante and achevee and not instance._etait_achevee and createur
            and createur.is_active and createur != emetteur):
        Notification.creer_notification_tache(
            tache=instance, type_notif='TACHE_TERMINEE',
            emetteur=emetteur, utilisateurs_cibles=[createur],
        )

    if created or (existante and ancien_id != instance.responsable_id):
        if responsable:
            Notification.creer_notification_tache(
                tache=instance, type_notif='TACHE_ASSIGNEE',
                emetteur=emetteur, utilisateurs_cibles=[responsable],
            )
            _envoyer_email_affectation(instance, emetteur)
        if ancien_id and not created:
            Notification.objects.create(
                utilisateur_id=ancien_id,
                projet=instance.projet,
                tache=instance,
                emetteur=emetteur,
                type_notification='TACHE_MODIFIEE',
                titre="Réaffectation de tâche",
                message=f"Vous n'êtes plus responsable de la tâche '{instance.titre}'",
                objet_id=instance.pk,
                objet_type='tache',
                niveau_urgence='FAIBLE',
            )
        return

    if (existante and responsable and not instance.terminee
            and instance._ancienne_priorite != 'URGENTE'
            and instance.priorite == 'URGENTE'):
        Notification.creer_notification_tache(
            tache=instance, type_notif='TACHE_URGENTE',
            emetteur=emetteur, utilisateurs_cibles=[responsable],
        )
