# projets/decorators.py
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.contrib import messages
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
                user_in_project = projet.users.filter(id=request.user.id).exists()
                user_can_view = request.user in projet.users.all()

                # Vérifier si l'utilisateur fait partie du projet
                if not user_in_project:
                    raise PermissionDenied
                # Vérifier si l'utilisateur est le chef du projet
                if not user_can_view:
                    raise PermissionDenied
            except Projet.DoesNotExist:
                raise PermissionDenied
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def permission_required(permission_codename=None, check_object_permission=None, message=None):
    """
    Décorateur flexible pour gérer les permissions
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return login_required(view_func)(request, *args, **kwargs)
            
            # Vérification permission basique
            if permission_codename and not request.user.has_perm(permission_codename):
                if message:
                    messages.error(request, message)
                raise PermissionDenied
            
            # Vérification permission sur objet
            if check_object_permission:
                obj = check_object_permission(request, *args, **kwargs)
                if not obj:
                    raise PermissionDenied
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def role_required(*roles, message="Accès non autorisé"):
    """Décorateur pour vérifier les rôles utilisateur"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return login_required(view_func)(request, *args, **kwargs)
            
            user_has_role = False
            if request.user.is_superuser:
                user_has_role = True
            else:
                # Vérifier le rôle dans le profil
                if hasattr(request.user, 'profile') and request.user.profile.role in roles:
                    user_has_role = True
                # Vérifier les groupes
                elif request.user.groups.filter(name__in=roles).exists():
                    user_has_role = True
            
            if not user_has_role:
                messages.error(request, message)
                raise PermissionDenied
            
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def can_edit_projet(view_func):
    """Décorateur spécifique pour l'édition de projet"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        
        # Superusers peuvent tout faire
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        projet = Projet.objects.get(id=projet_id)
        user_can_edit = request.user in projet.users.all()
        # Vérifier la permission générique
        if not user_can_edit: #request.user.has_perm('projets.change_projet'):
            messages.error(request, "Vous n'avez pas la permission de modifier les projets")
            raise PermissionDenied
        
        # Vérification spécifique à l'objet
        projet_id = kwargs.get('projet_id') or kwargs.get('pk')
        if projet_id:
            from .models import Projet
            try:
                projet = Projet.objects.get(id=projet_id)
                # Vérifier si l'utilisateur est propriétaire ou membre avec droits
                if not (projet.users.filter(id=request.user.id).exists()):
                    messages.error(request, "Vous ne pouvez modifier que vos propres projets")
                    raise PermissionDenied
            except Projet.DoesNotExist:
                messages.error(request, "Projet non trouvé")
                raise PermissionDenied
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view