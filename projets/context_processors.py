from django.utils import timezone
from .modules import MODULES, modules_desactives
from .version import APP_VERSION, get_versions_between


def observer_access(request):
    from projets.decorators import (
        dossiers_accessibles, est_admin_dossier, est_directeur_projet,
        est_observateur, est_pointeur, peut_gerer_utilisateurs,
        peut_creer_projet, peut_gerer_projet, peut_supprimer_projet,
    )
    from projets.observer_access import observer_url_patterns

    readonly = est_observateur(request.user)
    pointeur = est_pointeur(request.user)
    desactives = (
        modules_desactives(request.user) if request.user.is_authenticated else frozenset()
    )
    context = {
        'observer_readonly': readonly,
        'is_pointeur': pointeur,
        'observer_url_patterns': observer_url_patterns() if readonly else [],
        'can_manage_users': peut_gerer_utilisateurs(request.user),
        'can_configure_dossier': request.user.is_authenticated and (
            request.user.is_superuser or est_admin_dossier(request.user)
        ),
        'can_create_project': peut_creer_projet(request.user),
        'can_delete_project': peut_supprimer_projet(request.user),
        'can_manage_project': peut_gerer_projet(request.user),
        'role_refonte_en_attente': (
            request.user.is_authenticated
            and getattr(getattr(request.user, 'profile', None), 'role', None) == 'A_RECLASSER'
        ),
        'dossier_affectation_invalide': False,
        'modules_desactives': desactives,
        'modules_actifs': (
            {key: mod for key, mod in MODULES.items() if key not in desactives}
            if request.user.is_authenticated else {}
        ),
    }
    dossier = getattr(request, 'dossier', None)
    if dossier is None and request.user.is_authenticated:
        dossiers = dossiers_accessibles(request.user)
        if request.user.is_superuser:
            selection = request.session.get('dossier_id')
            dossier = dossiers.filter(pk=selection).first() if selection else None
        else:
            choices = list(dossiers[:2])
            dossier = choices[0] if len(choices) == 1 else None
            context['dossier_affectation_invalide'] = (
                not readonly and len(choices) != 1
                and getattr(request.user.profile, 'role', None) in {
                    'ADMIN_DOSSIER', 'DIRECTEUR_PROJET', 'CHEF_PROJET',
                    'CHEF_CHANTIER', 'POINTEUR',
                }
            )
    context['dossier_actif'] = dossier
    if readonly:
        masque = request.user.profile.guide_observateur_masque
        context['observer_guide_masque'] = masque
        context['observer_guide_auto'] = not masque and not request.session.get('observer_guide_ferme')
    return context

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
