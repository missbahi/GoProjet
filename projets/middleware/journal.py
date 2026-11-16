import logging

from django.utils.deprecation import MiddlewareMixin

from projets.models.journal import JournalAcces, client_ip
from projets.modules import module_pour_route

logger = logging.getLogger(__name__)

PREFIXES_IGNORES = ('/static/', '/media/', '/favicon', '/sw.js', '/manifest')
METHODES_ECRITURE = {'POST', 'PUT', 'PATCH', 'DELETE'}


class JournalAccesMiddleware(MiddlewareMixin):
    """Journalise les pages consultées, les écritures et les accès refusés."""

    def process_response(self, request, response):
        try:
            if self._a_journaliser(request, response):
                match = request.resolver_match
                route = match.url_name or '' if match else ''
                JournalAcces.objects.create(
                    user=request.user,
                    username=request.user.get_username(),
                    ip=client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')[:255],
                    method=request.method,
                    path=request.get_full_path()[:500],
                    route=route[:150],
                    module=(module_pour_route(match.namespace, route) or '') if match else '',
                    projet_id=match.kwargs.get('projet_id') if match else None,
                    status_code=response.status_code,
                )
        except Exception:
            logger.exception("Échec de l'écriture du journal d'accès")
        return response

    @staticmethod
    def _a_journaliser(request, response):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated:
            return False
        if request.path.startswith(PREFIXES_IGNORES):
            return False
        match = request.resolver_match
        if match and (match.url_name or '').startswith(('api_', 'notification', 'mark_')):
            return response.status_code == 403
        if response.status_code == 403 or request.method in METHODES_ECRITURE:
            return True
        return request.method == 'GET' and 'text/html' in response.get('Content-Type', '')
