# projets/decorators.py
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from functools import wraps

def superuser_required(view_func):
    """Décorateur pour restreindre l'accès aux superutilisateurs"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if not request.user.is_superuser:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def staff_required(view_func):
    """Décorateur pour restreindre l'accès au staff"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if not request.user.is_staff:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def chef_projet_required(view_func):
    """Décorateur pour les chefs de projet"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if not (request.user.is_staff or request.user.is_superuser or 
                hasattr(request.user, 'profile') and request.user.profile.role == 'CHEF_PROJET'):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def can_view_projet(view_func):
    """Décorateur pour vérifier si l'utilisateur peut voir un projet spécifique"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        
        # Superusers peuvent tout voir
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        
        # Récupérer le projet depuis les kwargs ou autre
        projet_id = kwargs.get('projet_id') or kwargs.get('pk')
        if projet_id:
            from .models import Projet
            try:
                projet = Projet.objects.get(id=projet_id)
                # Vérifier si l'utilisateur fait partie du projet
                if not projet.users.filter(id=request.user.id).exists():
                    raise PermissionDenied
            except Projet.DoesNotExist:
                raise PermissionDenied
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view