# projets/signals/tache_echeances.py
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from ..models import Tache, Notification


def create_notification(user, titre, message, type_notif='AUTRE', action_url=None, projet=None, niveau_urgence='MOYEN'):
    """Helper pour créer une notification (adapté au modèle Notification)."""
    if not user:
        return False

    Notification.objects.create(
        utilisateur=user,
        projet=projet,
        type_notification=type_notif,
        titre=titre,
        message=message,
        action_url=action_url or '',
        niveau_urgence=niveau_urgence,
        lue=False,
    )
    return True


def send_email_notification(user, subject, message):
    """Envoie un email de notification (si email configuré)."""
    if user and user.email:
        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True,
            )
            return True
        except Exception as e:
            print(f"❌ Erreur envoi email à {user.email}: {e}")
    return False


def notify_projet_users(projet, titre, message, type_notif='AUTRE', action_url=None, exclude_user=None, niveau_urgence='MOYEN'):
    """Notifie tous les utilisateurs du projet."""
    users_notifies = 0
    for user in projet.users.all():
        if exclude_user and user == exclude_user:
            continue
        if create_notification(
            user, titre, message, type_notif, action_url,
            projet=projet, niveau_urgence=niveau_urgence,
        ):
            users_notifies += 1
    return users_notifies


def check_echeances_taches_quotidien():
    """Vérifie les échéances quotidiennement (à appeler par cron)."""
    aujourdhui = timezone.now().date()
    stats = {'aujourdhui': 0, 'demain': 0, 'retard': 0, 'urgentes': 0}

    # ───────── 1. Tâches qui expirent aujourd'hui ─────────
    taches_aujourdhui = Tache.objects.filter(
        date_fin=aujourdhui,
        terminee=False,
    ).select_related('projet', 'responsable')

    for tache in taches_aujourdhui:
        action_url = f"/projet/{tache.projet_id}/taches/{tache.id}/"
        titre_resp = "Échéance aujourd'hui"
        titre_projet = "Échéance de tâche aujourd'hui"
        message = f"La tâche « {tache.titre} » expire aujourd'hui."

        if tache.responsable:
            create_notification(
                tache.responsable,
                titre_resp, message,
                'TACHE_ECHEANCE',
                action_url,
                projet=tache.projet,
                niveau_urgence='ELEVE',
            )

            # Email optionnel
            if getattr(settings, 'SEND_EMAIL_NOTIFICATIONS', False):
                email_subject = f"[{getattr(settings, 'SITE_NAME', 'GoProjet')}] {titre_resp}"
                email_message = render_to_string('emails/echeance_aujourdhui.txt', {
                    'tache': tache,
                    'user': tache.responsable,
                    'site_name': getattr(settings, 'SITE_NAME', 'GoProjet'),
                    'site_url': getattr(settings, 'SITE_URL', ''),
                })
                send_email_notification(tache.responsable, email_subject, email_message)

        notify_projet_users(
            tache.projet,
            titre_projet, message,
            'TACHE_ECHEANCE',
            action_url,
            exclude_user=tache.responsable,
            niveau_urgence='ELEVE',
        )
        stats['aujourdhui'] += 1

    # ───────── 2. Tâches qui expirent demain ─────────
    demain = aujourdhui + timedelta(days=1)
    taches_demain = Tache.objects.filter(
        date_fin=demain,
        terminee=False,
    ).select_related('projet', 'responsable')

    for tache in taches_demain:
        action_url = f"/projet/{tache.projet_id}/taches/{tache.id}/"
        if tache.responsable:
            create_notification(
                tache.responsable,
                "Échéance demain",
                f"La tâche « {tache.titre} » expire demain.",
                'TACHE_ECHEANCE',
                action_url,
                projet=tache.projet,
                niveau_urgence='MOYEN',
            )
        stats['demain'] += 1

    # ───────── 3. Tâches en retard ─────────
    taches_retard = Tache.objects.filter(
        date_fin__lt=aujourdhui,
        terminee=False,
    ).select_related('projet', 'responsable')

    for tache in taches_retard:
        jours_retard = (aujourdhui - tache.date_fin).days
        action_url = f"/projet/{tache.projet_id}/taches/{tache.id}/"
        message = f"La tâche « {tache.titre} » est en retard de {jours_retard} jour(s)."

        if tache.responsable:
            create_notification(
                tache.responsable,
                "Tâche en retard",
                message,
                'TACHE_EN_RETARD',
                action_url,
                projet=tache.projet,
                niveau_urgence='CRITIQUE',
            )

        notify_projet_users(
            tache.projet,
            "Tâche en retard",
            message,
            'TACHE_EN_RETARD',
            action_url,
            exclude_user=tache.responsable,
            niveau_urgence='CRITIQUE',
        )
        stats['retard'] += 1

    # ───────── 4. Tâches URGENTES non terminées ─────────
    taches_urgentes = Tache.objects.filter(
        priorite='URGENTE',
        terminee=False,
        date_fin__gte=aujourdhui,
    ).select_related('projet', 'responsable')

    for tache in taches_urgentes:
        action_url = f"/projet/{tache.projet_id}/taches/{tache.id}/"
        if tache.responsable:
            create_notification(
                tache.responsable,
                "Rappel tâche urgente",
                f"La tâche urgente « {tache.titre} » est toujours en cours.",
                'TACHE_URGENTE',
                action_url,
                projet=tache.projet,
                niveau_urgence='ELEVE',
            )
        stats['urgentes'] += 1

    return stats