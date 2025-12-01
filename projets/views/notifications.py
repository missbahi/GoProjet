from datetime import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required

from projets.models import Notification

@login_required
def notifications_json(request):
    """API pour récupérer les notifications en JSON"""
    notifications = request.user.notifications.filter(lue=False).order_by('-date_creation')[:10]
    
    data = [{
        'id': notif.id,
        'titre': notif.titre,
        'message': notif.message,
        'type': notif.type_notification,
        'urgence': notif.niveau_urgence,
        'date_creation': notif.date_creation.strftime('%d/%m/%Y %H:%M'),
        'action_url': notif.action_url,
        'est_recente': notif.est_recente,
    } for notif in notifications]
    
    return JsonResponse({'notifications': data})

@login_required
@require_http_methods(['POST'])
def marquer_comme_lue(request, notification_id):
    """Marquer une notification comme lue"""
    try:
        notification = request.user.notifications.get(id=notification_id)
        notification.marquer_comme_lue()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification non trouvée'}, status=404)

@login_required
@require_http_methods(['POST'])
def tout_marquer_comme_lue(request):
    """Marquer toutes les notifications comme lues"""
    updated = request.user.notifications.filter(lue=False).update(
        lue=True, 
        date_lue=timezone.now()
    )
    return JsonResponse({'success': True, 'marquees': updated})