from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

from projets.version import APP_VERSION

@login_required
@require_POST
def mark_version_seen(request):
    """L'utilisateur a vu et acquitté la nouvelle version."""
    profile = request.user.profile
    profile.last_seen_version = APP_VERSION
    profile.last_version_check = timezone.now()
    profile.save(update_fields=["last_seen_version", "last_version_check"])

    # Éviter les rappels pendant la même session
    request.session["version_notice_shown_for"] = APP_VERSION

    return JsonResponse({"success": True, "version": APP_VERSION})