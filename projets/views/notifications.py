from datetime import timedelta
from django.utils import timezone 
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET, require_http_methods
from django.contrib.auth.decorators import login_required
import json

from projets.models import Attachement, DocumentAdministratif, Notification, OrdreService, Projet, Tache
from django.shortcuts import get_object_or_404, redirect, render
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

@login_required
@require_POST
def creer_notification(request):
    """
    Vue pour créer une notification via le formulaire modal
    """
    try:
        data = request.POST
        from django.contrib import messages
        # Validation des champs obligatoires
        required_fields = ['projet_id', 'type_notification', 'titre', 'message']
        for field in required_fields:
            if field not in data or not data[field].strip():
                messages.error(request, f"Le champ '{field}' est obligatoire.")
                return redirect(request.META.get('HTTP_REFERER', 'home'))
        
        projet_id = data['projet_id']
        projet = get_object_or_404(Projet, id=projet_id)
        
        # Vérifier les permissions
        if not request.user.has_perm('projets.add_notification', projet):
            messages.error(request, "Vous n'avez pas la permission de créer des notifications pour ce projet.")
            return redirect(request.META.get('HTTP_REFERER', 'home'))
        
        # Préparer les données pour la notification
        notification_data = {
            'utilisateur_id': data.get('utilisateur') or request.user.id,
            'projet': projet,
            'type_notification': data['type_notification'],
            'titre': data['titre'],
            'message': data['message'],
            'niveau_urgence': data.get('niveau_urgence', 'MOYEN'),
            'action_url': data.get('action_url', ''),
            'emetteur': request.user,
        }
        
        # Champs optionnels avec validation
        if data.get('date_echeance'):
            notification_data['date_echeance'] = data['date_echeance']
        
        if data.get('expire_le'):
            notification_data['expire_le'] = data['expire_le']
        
        # Booléens
        notification_data['prioritaire'] = data.get('prioritaire') == 'true'
        notification_data['can_be_closed'] = data.get('can_be_closed', 'true') == 'true'
        
        # Relations optionnelles
        if data.get('tache'):
            try:
                notification_data['tache'] = Tache.objects.get(id=data['tache'], projet=projet)
            except Tache.DoesNotExist:
                pass
        
        if data.get('document'):
            try:
                notification_data['document'] = DocumentAdministratif.objects.get(
                    id=data['document'], projet=projet
                )
            except DocumentAdministratif.DoesNotExist:
                pass
        
        if data.get('ordre_service'):
            try:
                notification_data['ordre_service'] = OrdreService.objects.get(
                    id=data['ordre_service'], projet=projet
                )
            except OrdreService.DoesNotExist:
                pass
        
        # Objet générique
        if data.get('objet_id') and data.get('objet_type'):
            notification_data['objet_id'] = data['objet_id']
            notification_data['objet_type'] = data['objet_type']
        
        # Créer la notification
        notification = Notification.objects.create(**notification_data)
        
        # Log l'action
        messages.success(
            request, 
            f"Notification '{notification.titre}' créée avec succès."
        )
        
        # Redirection 
        from django.urls import reverse
        redirect_url = data.get('redirect_to') or reverse('projets:liste_projets')
        return redirect(redirect_url)
        
    except Exception as e:
        messages.error(
            request, 
            f"Erreur lors de la création de la notification: {str(e)}"
        )
        return redirect(request.META.get('HTTP_REFERER', 'home')) 
@login_required
@require_GET
def notification_data_api(request, projet_id):
    """
    API pour récupérer les données nécessaires à la création de notification
    pour un projet spécifique.
    """
    try:
        projet = get_object_or_404(Projet, id=projet_id)
        
        # Vérifier les permissions (ajustez selon votre système de permissions)
        if not request.user.has_perm('projets.view_projet', projet):
            return JsonResponse({
                'error': 'Permission refusée',
                'detail': "Vous n'avez pas la permission d'accéder à ce projet."
            }, status=403)
        
        # Options de filtrage depuis les paramètres GET
        limit_taches = int(request.GET.get('limit_taches', 20))
        limit_documents = int(request.GET.get('limit_documents', 20))
        limit_os = int(request.GET.get('limit_os', 20))
        
        statut_filter = request.GET.get('statut', '')
        
        # Base querysets
        taches_qs = Tache.objects.filter(projet=projet)
        documents_qs = DocumentAdministratif.objects.filter(projet=projet)
        ordres_service_qs = OrdreService.objects.filter(projet=projet)
        
        # Appliquer des filtres optionnels
        if statut_filter:
            taches_qs = taches_qs.filter(statut=statut_filter)
            ordres_service_qs = ordres_service_qs.filter(statut=statut_filter)
        
        # Récupérer les données avec limites
        taches = taches_qs.order_by('-created_at')[:limit_taches]
        documents = documents_qs.order_by('-date_remise')[:limit_documents]
        ordres_service = ordres_service_qs.order_by('-date_publication')[:limit_os]
        
        # Récupérer d'autres objets utiles
        attachements = Attachement.objects.filter(projet=projet).order_by('-date_fin_periode')[:10]
        # reunions = Reunion.objects.filter(projet=projet).order_by('-date_debut')[:10]
        
        # Objets récents (7 derniers jours)
        date_limite = timezone.now() - timedelta(days=7)
        objets_recents = {
            'taches_recentes': taches_qs.filter(created_at__gte=date_limite).count(),
            'documents_recents': documents_qs.filter(date_remise__gte=date_limite).count(),
            'os_recents': ordres_service_qs.filter(date_publication__gte=date_limite).count(),
        }
        
        # Préparer les données pour JSON
        data = {
            'success': True,
            'projet': {
                'id': projet.id,
                'nom': projet.nom,
                'client': str(projet.maitre_ouvrage) if projet.maitre_ouvrage else None,
                'statut': projet.get_statut_display(),
                'date_debut': projet.date_debut.strftime('%Y-%m-%d') if projet.date_debut else None,
                'delai': projet.delai if projet.delai else None,
            },
            'statistiques': {
                'total_taches': taches_qs.count(),
                'total_documents': documents_qs.count(),
                'total_ordres_service': ordres_service_qs.count(),
                'total_attachements': attachements.count(),
                # 'total_reunions': reunions.count(),
                **objets_recents
            },
            'taches': [
                {
                    'id': t.id,
                    'titre': t.titre,
                    'priorite': t.get_priorite_display(),
                    'date_creation': t.date_creation.strftime('%Y-%m-%d %H:%M'),
                    'date_fin': t.date_fin.strftime('%Y-%m-%d') if t.date_echeance else None,
                    'responsable': str(t.responsable.get_full_name()) if t.responsable else None,
                }
                for t in taches
            ],
            'documents': [
                {
                    'id': d.id,
                    'nom': d.original_filename if d.original_filename else d.get_file_name(),
                    'type_document': d.type_document,
                    'type_display': d.get_type_document_display(),
                    'date_creation': d.date_remise.strftime('%Y-%m-%d %H:%M'),
                    'statut': d.statut,
                    # 'created_by': str(d.created_by) if d.created_by else None,
                }
                for d in documents
            ],
            'ordres_service': [
                {
                    'id': os.id,
                    'numero': os.reference,
                    'titre': os.titre,
                    'statut': os.statut,
                    'statut_display': os.get_statut_display(),
                    'date_creation': os.created_at.strftime('%Y-%m-%d %H:%M'),
                }
                for os in ordres_service
            ],
            'attachements': [
                {
                    'id': a.id,
                    'numero': a.numero,
                    'date_etablissement': a.date_etablissement.strftime('%Y-%m-%d') if a.date_etablissement else None,
                    'statut': a.get_statut_display(),
                }
                for a in attachements
            ],
            # 'reunions': [
            #     {
            #         'id': r.id,
            #         'titre': r.titre,
            #         'date_debut': r.date_debut.strftime('%Y-%m-%d %H:%M'),
            #         'type_reunion': r.get_type_reunion_display(),
            #     }
            #     for r in reunions
            # ],
            'suggestions': {
                'types_notification': [
                    {'code': 'TACHE_URGENTE', 'label': 'Tâche urgente'},
                    {'code': 'TACHE_ECHEANCE', 'label': 'Échéance tâche approchante'},
                    {'code': 'REUNION', 'label': 'Rappel réunion'},
                    {'code': 'DOCUMENT_A_SIGNER', 'label': 'Document à signer'},
                    {'code': 'ECHEANCE', 'label': 'Échéance approchante'},
                ],
                'urgence_par_defaut': 'MOYEN',
                'expiration_par_defaut': (timezone.now() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M'),
            }
        }
        
        return JsonResponse(data, json_dumps_params={'ensure_ascii': False})
        
    except Projet.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Projet non trouvé',
            'detail': f"Aucun projet avec l'ID {projet_id} n'existe."
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erreur serveur',
            'detail': str(e)
        }, status=500)
        
@login_required
@require_GET
def notifications_non_lues_api(request):
    """
    API pour récupérer les notifications non lues de l'utilisateur
    """
    try:
        notifications = Notification.objects.filter(
            utilisateur=request.user,
            lue=False
        ).select_related('projet', 'tache', 'document', 'ordre_service')
        
        # Filtrer les notifications expirées
        now = timezone.now()
        notifications = notifications.filter(
            Q(expire_le__isnull=True) | Q(expire_le__gt=now)
        )
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 10))
        
        from django.db.models import Count
        from django.core.paginator import Paginator
        
        paginator = Paginator(notifications, per_page)
        page_obj = paginator.get_page(page)
        
        data = {
            'success': True,
            'total': paginator.count,
            'page': page_obj.number,
            'pages': paginator.num_pages,
            'has_next': page_obj.has_next(),
            'has_previous': page_obj.has_previous(),
            'notifications': [
                {
                    'id': n.id,
                    'titre': n.titre,
                    'message': n.message,
                    'type_notification': n.type_notification,
                    'type_display': n.get_type_notification_display(),
                    'niveau_urgence': n.niveau_urgence,
                    'urgence_display': n.get_niveau_urgence_display(),
                    'date_creation': n.date_creation.strftime('%Y-%m-%d %H:%M'),
                    'date_creation_relative': n.date_creation.strftime('%H:%M'),
                    'est_recente': n.est_recente,
                    'projet': {
                        'id': n.projet.id,
                        'nom': n.projet.nom
                    } if n.projet else None,
                    'action_url': n.action_url or n.get_absolute_url(),
                    'prioritaire': n.prioritaire,
                    'can_be_closed': n.can_be_closed,
                    'icon_class': n.icon_class,
                    'badge_color': n.badge_color,
                }
                for n in page_obj.object_list
            ],
            'statistiques': {
                'total_non_lues': notifications.count(),
                'par_urgence': list(notifications.values('niveau_urgence').annotate(count=Count('id'))),
                'par_type': list(notifications.values('type_notification').annotate(count=Count('id'))),
            }
        }
        
        return JsonResponse(data, json_dumps_params={'ensure_ascii': False})
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': 'Erreur serveur',
            'detail': str(e)
        }, status=500)
        
@login_required
@require_POST
def marquer_notification_lue(request, notification_id):
    """
    API pour marquer une notification comme lue
    """
    try:
        notification = get_object_or_404(
            Notification, 
            id=notification_id, 
            utilisateur=request.user
        )
        
        if notification.marquer_comme_lue():
            return JsonResponse({
                'success': True,
                'message': 'Notification marquée comme lue'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Notification déjà lue'
            })
            
    except Notification.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Notification non trouvée'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)