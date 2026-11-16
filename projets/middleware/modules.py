from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin

from projets.modules import MODULES, module_pour_route, modules_desactives


class ModulesDisponiblesMiddleware(MiddlewareMixin):
    """Refuse l'accès aux modules désactivés pour l'utilisateur connecté."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None
        match = request.resolver_match
        module = module_pour_route(match.namespace, match.url_name)
        if module and module in modules_desactives(request.user):
            raise PermissionDenied(
                f"Le module « {MODULES[module]['label']} » n'est pas disponible pour votre compte."
            )
        return None
