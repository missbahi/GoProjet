# signals/tache_echeances.py
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.utils.translation import gettext as _
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string

from ..models import Tache, Notification

def create_notification(user, titre, message, type_notif='info', lien=None):
    """Helper pour créer une notification"""
    if user and user.is_authenticated:
        Notification.objects.create(
            user=user,
            titre=titre,
            message=message,
            type=type_notif,
            lien=lien,
            lue=False
        )
        return True
    return False

def send_email_notification(user, subject, message):
    """Envoyer un email de notification"""
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

def notify_projet_users(projet, titre, message, type_notif='info', lien=None, exclude_user=None):
    """Notifier tous les utilisateurs du projet"""
    users_notifies = 0
    for user in projet.users.all():
        if exclude_user and user == exclude_user:
            continue
        if create_notification(user, titre, message, type_notif, lien):
            users_notifies += 1
    return users_notifies

def check_echeances_taches_quotidien():
    """Vérifie les échéances quotidiennement (à appeler par cron)"""
    aujourdhui = timezone.now().date()
    stats = {
        'aujourdhui': 0, 
        'demain': 0,
        'retard': 0,
        'urgentes': 0
    }
    
    # 1. Tâches qui expirent aujourd'hui
    taches_aujourdhui = Tache.objects.filter(
        date_fin=aujourdhui,
        terminee=False
    ).select_related('projet', 'responsable')
    
    for tache in taches_aujourdhui:
        # Notification au responsable
        if tache.responsable:
            titre = _("Échéance aujourd'hui")
            message = _("La tâche '{titre}' expire aujourd'hui").format(
                titre=tache.titre
            )
            create_notification(
                tache.responsable,
                titre,
                message,
                'urgence',
                f"/taches/{tache.id}/"
            )
            
            # Email
            if getattr(settings, 'SEND_EMAIL_NOTIFICATIONS', False):
                email_subject = f"[{settings.SITE_NAME}] {titre}"
                email_message = render_to_string('emails/echeance_aujourdhui.txt', {
                    'tache': tache,
                    'user': tache.responsable,
                    'site_name': settings.SITE_NAME,
                    'site_url': settings.SITE_URL
                })
                send_email_notification(tache.responsable, email_subject, email_message)
        
        # Notification aux autres utilisateurs du projet
        titre = _("Échéance de tâche aujourd'hui")
        message = _("La tâche '{titre}' expire aujourd'hui").format(
            titre=tache.titre
        )
        notify_projet_users(
            tache.projet,
            titre,
            message,
            'warning',
            f"/taches/{tache.id}/",
            exclude_user=tache.responsable
        )
        
        stats['aujourdhui'] += 1
    
    # 2. Tâches qui expirent demain
    demain = aujourdhui + timedelta(days=1)
    taches_demain = Tache.objects.filter(
        date_fin=demain,
        terminee=False
    ).select_related('projet', 'responsable')
    
    for tache in taches_demain:
        if tache.responsable:
            titre = _("Échéance demain")
            message = _("La tâche '{titre}' expire demain").format(
                titre=tache.titre
            )
            create_notification(
                tache.responsable,
                titre,
                message,
                'warning',
                f"/taches/{tache.id}/"
            )
        stats['demain'] += 1
    
    # 3. Tâches en retard
    taches_retard = Tache.objects.filter(
        date_fin__lt=aujourdhui,
        terminee=False
    ).select_related('projet', 'responsable')
    
    for tache in taches_retard:
        jours_retard = (aujourdhui - tache.date_fin).days
        
        # Notification au responsable
        if tache.responsable:
            titre = _("Tâche en retard")
            message = _("La tâche '{titre}' est en retard de {jours} jour(s)").format(
                titre=tache.titre,
                jours=jours_retard
            )
            create_notification(
                tache.responsable,
                titre,
                message,
                'danger',
                f"/taches/{tache.id}/"
            )
        
        # Notification à TOUS les utilisateurs du projet
        titre = _("Tâche en retard")
        message = _("La tâche '{titre}' est en retard de {jours} jour(s)").format(
            titre=tache.titre,
            jours=jours_retard
        )
        notify_projet_users(
            tache.projet,
            titre,
            message,
            'danger',
            f"/taches/{tache.id}/",
            exclude_user=tache.responsable
        )
        
        stats['retard'] += 1
    
    # 4. Tâches prioritaires URGENTES (vérification supplémentaire)
    taches_urgentes = Tache.objects.filter(
        priorite='URGENTE',
        terminee=False,
        date_fin__gte=aujourdhui  # Pas encore expirées
    ).select_related('projet', 'responsable')
    
    for tache in taches_urgentes:
        # Rappel quotidien pour les tâches urgentes
        if tache.responsable:
            titre = _("Rappel tâche urgente")
            message = _("La tâche urgente '{titre}' est toujours en cours").format(
                titre=tache.titre
            )
            create_notification(
                tache.responsable,
                titre,
                message,
                'danger',
                f"/taches/{tache.id}/"
            )
        stats['urgentes'] += 1
    
    return stats