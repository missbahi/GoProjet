from django.core import signing
from django.core.exceptions import SuspiciousOperation
from django.urls import reverse

NOTIFICATION_ORIGIN_SALT = 'projets.notifications.breadcrumb'


def notification_origin_token(items, request):
    if not items or request is None:
        return ''
    origin = [dict(item) for item in items]
    origin[-1]['url'] = request.get_full_path()
    return signing.dumps(origin, salt=NOTIFICATION_ORIGIN_SALT, compress=True)


def notification_origin_items(token):
    if not token:
        return []
    try:
        return signing.loads(token, salt=NOTIFICATION_ORIGIN_SALT)
    except signing.BadSignature as exc:
        raise SuspiciousOperation('Invalid notification breadcrumb signature') from exc


def crumb(label, url_name=None, args=None, icon=None, hx=True):
    url = reverse(url_name, args=args) if url_name else None
    return {'label': label, 'url': url, 'icon': icon, 'hx': hx}


def project_crumbs(projet, *items):
    """Fil d'Ariane famille projet : Projets › <projet> › items…

    Sans items, le projet est l'élément courant (dashboard).
    """
    return [
        crumb("Projets", "projets:liste_projets"),
        crumb(projet.nom, "projets:dashboard", args=[projet.id]),
        *items,
    ]