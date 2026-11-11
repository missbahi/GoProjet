from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin

from projets.decorators import est_observateur
from projets.observer_access import observer_route_allowed, verifier_perimetre_observateur


class ObserverReadOnlyMiddleware(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        if not est_observateur(request.user):
            return None
        match = request.resolver_match
        if not observer_route_allowed(match.namespace, match.url_name, request.method):
            raise PermissionDenied("Observateur : consultation uniquement, sans modification.")
        verifier_perimetre_observateur(request, match)
        return None
