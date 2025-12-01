from datetime import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_http_methods
from django.contrib.auth.decorators import login_required
import json

from projets.models import Notification
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q

@login_required
def liste_notifications(request):
    """Page complète des notifications"""
    notifications = Notification.objects.filter(
        utilisateur=request.user
    ).order_by('-date_creation').select_related('projet')
    
    unread_count = notifications.filter(lue=False).count()
    
    context = {
        'notifications': notifications,
        'unread_count': unread_count,
    }
    return render(request, 'projets/liste_notifications.html', context)
@require_POST
@login_required
def mark_notification_as_read(request, notification_id):
    """Marquer une notification spécifique comme lue"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            utilisateur=request.user
        )
        notification.marquer_comme_lue()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification non trouvée'}, status=404)

@require_POST
@login_required
def mark_notification_as_unread(request, notification_id):
    """Marquer une notification spécifique comme non lue"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            utilisateur=request.user
        )
        notification.marquer_comme_non_lue()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification non trouvée'}, status=404)

@require_http_methods(["DELETE"])
@login_required
def delete_notification(request, notification_id):
    """Supprimer une notification spécifique"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            utilisateur=request.user
        )
        notification.delete()
        return JsonResponse({'success': True})
    except Notification.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Notification non trouvée'}, status=404)

@require_POST
@login_required
def mark_selected_as_read(request):
    """Marquer plusieurs notifications comme lues"""
    try:
        data = json.loads(request.body)
        notification_ids = data.get('notification_ids', [])
        
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            utilisateur=request.user,
            lue=False
        )
        
        count = notifications.count()
        notifications.update(lue=True, date_lue=timezone.now())
        
        return JsonResponse({'success': True, 'count': count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
@login_required
def delete_selected_notifications(request):
    """Supprimer plusieurs notifications"""
    try:
        data = json.loads(request.body)
        notification_ids = data.get('notification_ids', [])
        
        notifications = Notification.objects.filter(
            id__in=notification_ids,
            utilisateur=request.user
        )
        
        count = notifications.count()
        notifications.delete()
        
        return JsonResponse({'success': True, 'count': count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
@login_required
def delete_all_read_notifications(request):
    """Supprimer toutes les notifications lues"""
    try:
        notifications = Notification.objects.filter(
            utilisateur=request.user,
            lue=True
        )
        
        count = notifications.count()
        notifications.delete()
        
        return JsonResponse({'success': True, 'count': count})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)

@require_POST
@login_required  
def mark_all_notifications_as_read(request):
    """Marquer toutes les notifications de l'utilisateur comme lues"""
    updated = Notification.marquer_toutes_comme_lues(request.user)
    return JsonResponse({'success': True, 'count': updated})

@require_POST
@login_required
def delete_all_notifications(request):
    """Supprimer toutes les notifications de l'utilisateur"""
    deleted, _ = Notification.objects.filter(utilisateur=request.user).delete()
    return JsonResponse({'success': True, 'count': deleted})

@require_POST
@login_required
def creer_notification(request, projet_id):
    if request.method == 'POST':
        from projets.services import notification_service
        data = json.loads(request.body)
        user = request.user
        projet_id = data.get('projet_id')
        type_notif = data.get('type_notif')
        titre = data.get('titre')
        message = data.get('message')
        niveau_urgence = data.get('niveau_urgence')
        action_url = data.get('action_url')
        
        notification_service.NotificationService.creer_notification_personnalisee(request.user, projet_id)

        return JsonResponse({'success': True})
    else:
        
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)