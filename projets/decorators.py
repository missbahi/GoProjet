# projets/decorators.py

from django.core.exceptions import PermissionDenied
from django.contrib.auth.decorators import login_required
from functools import wraps
from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
import unicodedata


def est_observateur(user):
    return bool(
        user.is_authenticated and not user.is_superuser
        and getattr(getattr(user, 'profile', None), 'role', None) == 'OBSERVATEUR'
    )


def notifications_accessibles(user):
    from projets.models import Notification

    notifications = Notification.objects.filter(utilisateur=user)
    if not user.is_superuser:
        notifications = notifications.filter(
            Q(projet__isnull=True) | Q(projet__in=projets_accessibles(user))
        )
    return notifications


def projets_accessibles(user):
    """Retourne uniquement les projets autorisés pour l'utilisateur."""
    from .models import Projet

    if not user.is_authenticated:
        return Projet.objects.none()
    if user.is_superuser:
        return Projet.objects.all()

    if est_observateur(user):
        return Projet.objects.filter(dossier__utilisateurs=user).distinct()

    role = getattr(getattr(user, 'profile', None), 'role', None)
    if role == 'A_RECLASSER':
        return Projet.objects.none()
    dossiers = list(dossiers_accessibles(user).values_list('pk', flat=True)[:2])
    if len(dossiers) != 1:
        return Projet.objects.none()
    projets = Projet.objects.filter(dossier_id=dossiers[0])
    if est_admin_dossier(user):
        return projets
    return projets.filter(users=user).distinct()


def est_admin_dossier(user):
    return bool(
        user.is_authenticated and not user.is_superuser
        and getattr(getattr(user, 'profile', None), 'role', None) == 'ADMIN_DOSSIER'
    )


def est_directeur_projet(user):
    return bool(
        user.is_authenticated and not user.is_superuser
        and getattr(getattr(user, 'profile', None), 'role', None) == 'DIRECTEUR_PROJET'
    )


def peut_gerer_projet(user):
    return bool(user.is_authenticated and (
        user.is_superuser or est_admin_dossier(user)
        or est_directeur_projet(user) or est_chef_projet(user)
    ))


def peut_creer_projet(user):
    return bool(user.is_authenticated and (
        user.is_superuser or est_admin_dossier(user) or est_directeur_projet(user)
    ))


def peut_supprimer_projet(user):
    return bool(user.is_authenticated and (user.is_superuser or est_admin_dossier(user)))


def dossiers_accessibles(user):
    from .models import Dossier

    if not user.is_authenticated:
        return Dossier.objects.none()
    if user.is_superuser:
        return Dossier.objects.all()
    if est_admin_dossier(user):
        return Dossier.objects.filter(Q(utilisateurs=user) | Q(gerant=user)).distinct()
    return Dossier.objects.filter(utilisateurs=user).distinct()


def dossier_utilisateur(user):
    dossiers = list(dossiers_accessibles(user)[:2])
    if len(dossiers) != 1:
        raise PermissionDenied(
            "Votre compte doit être rattaché à un seul dossier. Contactez l'Admin."
        )
    return dossiers[0]


def dossier_courant(request):
    from .models import Dossier

    selection = request.POST.get('dossier') or request.GET.get('dossier')
    if not request.user.is_superuser:
        dossier = dossier_utilisateur(request.user)
        if selection and str(dossier.pk) != str(selection):
            raise PermissionDenied("Vous ne pouvez pas accéder à un autre dossier.")
        return dossier
    selection = selection or request.session.get('dossier_id')
    if not selection:
        raise PermissionDenied("Sélectionnez un dossier pour accéder à sa configuration.")
    if not str(selection).isdigit():
        raise PermissionDenied("Le dossier sélectionné est invalide.")
    dossier = Dossier.objects.filter(pk=selection).first()
    if dossier is None:
        raise PermissionDenied("Le dossier sélectionné n'existe pas.")
    request.session['dossier_id'] = dossier.pk
    return dossier


def configuration_dossier_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if not (request.user.is_superuser or est_admin_dossier(request.user)):
            raise PermissionDenied("La configuration est réservée aux administrateurs du dossier.")
        request.dossier = dossier_courant(request)
        return view_func(request, *args, **kwargs)
    return wrapped

def est_gerant(user):
    return est_admin_dossier(user)

def est_chef_projet(user):
    return bool(
        user.is_authenticated and not user.is_superuser
        and getattr(getattr(user, 'profile', None), 'role', None) == 'CHEF_PROJET'
    )

def peut_valider_directement(user, projet):
    return bool(
        user and user.is_authenticated and projet
        and projet.dossier_id and projet.dossier.activite == 'TRAVAUX'
        and (user.is_superuser or (
            peut_gerer_projet(user) and projets_accessibles(user).filter(pk=projet.pk).exists()
        ))
    )

def _normaliser_role(role):
    role_sans_accents = unicodedata.normalize('NFKD', str(role or ''))
    role_sans_accents = ''.join(
        caractere for caractere in role_sans_accents
        if not unicodedata.combining(caractere)
    )
    return ''.join(
        caractere for caractere in role_sans_accents.upper()
        if caractere.isalnum()
    )

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

def peut_gerer_utilisateurs(user):
    """Accès à la gestion des comptes : même règle pour la vue et pour les menus."""
    return bool(user.is_authenticated and (
        user.is_superuser or est_admin_dossier(user) or est_directeur_projet(user)
    ))

def gestion_utilisateurs_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if not peut_gerer_utilisateurs(request.user):
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
        if not peut_gerer_projet(request.user):
            raise PermissionDenied
        projet_id = kwargs.get('projet_id') or kwargs.get('pk')
        if projet_id and not projets_accessibles(request.user).filter(id=projet_id).exists():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def consultation_projet_required(view_func):
    """Consultation chef de projet ou observateur, sans autoriser d'écriture."""
    chef_view = chef_projet_required(view_func)

    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not est_observateur(request.user):
            return chef_view(request, *args, **kwargs)
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            raise PermissionDenied("Le rôle Observateur est limité à la consultation.")
        if not projets_accessibles(request.user).filter(pk=kwargs.get('projet_id')).exists():
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return wrapped

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

def _situation_action_required(check_func, message):
    """Factory de décorateur pour les actions sur situations (JSON si AJAX)."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'success': False, 'message': 'Votre session a expiré. Veuillez vous reconnecter.'},
                        status=401,
                    )
                return login_required(view_func)(request, *args, **kwargs)
            if not check_func(request.user, kwargs.get('projet_id')):
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse(
                        {'success': False, 'message': message},
                        status=403,
                    )
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def _peut_agir_sur_situation(user, projet_id):
    return bool(
        user.is_superuser or (
            peut_gerer_projet(user) and projet_id is not None
            and projets_accessibles(user).filter(pk=projet_id).exists()
        )
    )


can_validate_situation_mensuelle = _situation_action_required(
    _peut_agir_sur_situation,
    "Vous n'êtes pas autorisé à valider les situations mensuelles."
)

can_devalidate_situation_mensuelle = _situation_action_required(
    _peut_agir_sur_situation,
    "Vous n'êtes pas autorisé à dévalider les situations mensuelles."
)

def categorie_charge_required(view_func):
    return configuration_dossier_required(view_func)