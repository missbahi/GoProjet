from django.utils import timezone
from .version import APP_VERSION, get_versions_between


def app_version(request):
    """Injecte la version dans tous les templates."""
    return {"APP_VERSION": APP_VERSION}


def version_update_notice(request):
    """
    Retourne les versions à annoncer à l'utilisateur connecté,
    si sa dernière vue est différente de la version courante.
    """
    if not request.user.is_authenticated:
        return {}

    profile = getattr(request.user, "profile", None)
    if not profile:
        return {}

    last_seen = (profile.last_seen_version or "").strip()
    if last_seen == APP_VERSION:
        return {"version_notice": None}

    # Ne pas spammer : ne redemander qu'une fois par session
    if request.session.get("version_notice_shown_for") == APP_VERSION:
        return {"version_notice": None}

    updates = get_versions_between(last_seen, APP_VERSION)
    return {
        "version_notice": {
            "current": APP_VERSION,
            "last_seen": last_seen or None,
            "updates": updates,
        }
    }