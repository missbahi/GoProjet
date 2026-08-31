# projets/decorators.py
from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.contrib import messages
from django.db.models import Q


def projets_accessibles(user):
    """Retourne uniquement les projets autorisés pour l'utilisateur."""
    from .models import Projet

    if user.is_superuser:
        return Projet.objects.all()

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role in {'POINTEUR', 'CHEF_CHANTIER'}:
        # Restreint aux seuls projets explicitement affectés (pas tout le dossier).
        return Projet.objects.filter(users=user).distinct()

    return Projet.objects.filter(
        Q(dossier__gerant=user) | Q(dossier__utilisateurs=user) |
        Q(users=user, dossier__isnull=True)
    ).distinct()


def est_gerant(user):
    if not user.is_authenticated or user.is_superuser:
        return False
    role = getattr(getattr(user, 'profile', None), 'role', None)
    return role in {'GERANT', 'CHEF_PROJET'}


def est_chef_projet(user):
    return est_gerant(user)


def est_chef_chantier(user):
    if not user.is_authenticated or user.is_superuser or est_gerant(user):
        return False

    role = getattr(getattr(user, 'profile', None), 'role', None)
    return role == 'CHEF_CHANTIER'


def est_pointeur(user):
    if not user.is_authenticated or user.is_superuser or est_chef_chantier(user):
        return False
    role = getattr(getattr(user, 'profile', None), 'role', None)
    return role == 'POINTEUR'


def gestion_utilisateurs_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if not (request.user.is_superuser or est_gerant(request.user)):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view

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
        is_chef = est_chef_projet(request.user)
        if not (request.user.is_superuser or is_chef):
            raise PermissionDenied
        projet_id = kwargs.get('projet_id') or kwargs.get('pk')
        if projet_id and not projets_accessibles(request.user).filter(id=projet_id).exists():
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
                user_in_project = projets_accessibles(request.user).filter(
                    id=projet.id
                ).exists()

                # Vérifier si l'utilisateur fait partie du projet
                if not user_in_project:
                    raise PermissionDenied
            except Projet.DoesNotExist:
                raise PermissionDenied
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def modules_projet_required(view_func):
    """Comme can_view_projet, mais le pointeur est limité à la saisie des rapports journaliers."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)

        if not request.user.is_superuser:
            if est_pointeur(request.user):
                raise PermissionDenied

            projet_id = kwargs.get('projet_id') or kwargs.get('pk')
            if projet_id:
                from .models import Projet
                try:
                    projet = Projet.objects.get(id=projet_id)
                    if not projets_accessibles(request.user).filter(id=projet.id).exists():
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
        # Vérification spécifique à l'objet
        projet_id = kwargs.get('projet_id') or kwargs.get('pk')
        if projet_id:
            from .models import Projet
            try:
                projet = Projet.objects.get(id=projet_id)
                if not projets_accessibles(request.user).filter(id=projet.id).exists():
                    messages.error(request, "Vous ne pouvez modifier que vos propres projets")
                    raise PermissionDenied
            except Projet.DoesNotExist:
                messages.error(request, "Projet non trouvé")
                raise PermissionDenied
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view