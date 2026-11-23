from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin

from projets.modules import (
    MODULES, destination_repli, module_pour_route,
    module_redirige_si_desactive, modules_desactives,
)


class ModulesDisponiblesMiddleware(MiddlewareMixin):
    """Refuse l'accès aux modules désactivés, sauf modules à redirection."""

    def process_view(self, request, view_func, view_args, view_kwargs):
        if not request.user.is_authenticated:
            return None

        match = request.resolver_match
        module = module_pour_route(match.namespace, match.url_name)
        if not module or module not in modules_desactives(request.user):
            return None

        # Module "home" désactivé → redirection, pas de 403
        if module_redirige_si_desactive(module):
            cible = destination_repli(request.user)
            if cible:
                # Évite la boucle si la cible est elle-même "home"
                if cible != f'{match.namespace}:{match.url_name}':
                    return redirect(cible)
            # Aucune cible → on laisse passer (mieux qu'un 403 sur l'accueil)
            return None

        raise PermissionDenied(
            f"Le module « {MODULES[module]['label']} » n'est pas disponible pour votre compte."
        )
