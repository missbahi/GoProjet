from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin

from projets.observer_access import PERSONAL_VIEWS, verifier_perimetre_observateur


class ProjectScopeMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        if not user.is_authenticated or user.is_superuser:
            return None
        match = request.resolver_match
        if match.namespace == 'admin':
            raise PermissionDenied("L'administration globale est réservée à l'Admin.")
        if match.namespace not in {'projets', 'goplan'}:
            return None
        role = getattr(getattr(user, 'profile', None), 'role', None)
        if role == 'A_RECLASSER':
            personal = PERSONAL_VIEWS.get(match.namespace, set())
            if match.url_name not in personal | {'home', 'landing', 'apropos', 'liste_projets'}:
                raise PermissionDenied(
                    "Votre rôle doit être attribué par l'Admin."
                )
        verifier_perimetre_observateur(request, match)
        return None
