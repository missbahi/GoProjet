# projets/utils/utils.py
"""
Utilitaires partagés pour les vues.
"""
from functools import wraps
from django.http import JsonResponse


def is_ajax(request):
    """
    Détecte une requête AJAX de manière fiable.

    Retourne True si le header X-Requested-With vaut XMLHttpRequest,
    ce qui est le cas pour fetch() et XMLHttpRequest côté client.
    """
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


def ajax_response(success=True, message='', errors=None, status=200, **extra):
    """
    Construit une JsonResponse standardisée.

    Args:
        success: booléen indiquant le succès
        message: message lisible par l'utilisateur
        errors: dict des erreurs de formulaire (form.errors.get_json_data())
        status: code HTTP (400 pour les erreurs de validation)
        **extra: champs supplémentaires à inclure dans la réponse
    """
    payload = {'success': success, 'message': message}
    if errors is not None:
        payload['errors'] = errors
    payload.update(extra)
    return JsonResponse(payload, status=status)