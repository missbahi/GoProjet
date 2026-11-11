"""Explicit consultation surface for dossier observers; new routes are denied by default."""
from functools import lru_cache
import re

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.urls import URLResolver, get_resolver

from projets.decorators import projets_accessibles


READ_VIEWS = {
    'projets': {
        'landing', 'apropos', 'home', 'liste_projets', 'dashboard',
        'lots_projet', 'saisie_bordereau', 'export_bordereau_excel', 'apercu_impression_bordereau',
        'liste_ca', 'modifier_ca', 'documents', 'telecharger_document', 'afficher_document',
        'rapports_journaliers', 'detail_rapport_journalier', 'situations_mensuelles',
        'apercu_situation_mensuelle', 'suivi_execution', 'afficher_fichier_suivi',
        'telecharger_fichier_suivi', 'ateliers_projet', 'materiels_atelier',
        'planning_ateliers', 'apercu_impression_planning', 'ressources_projet',
        'api_ateliers_projet', 'liste_taches_projet', 'liste_taches', 'detail_tache',
        'liste_attachements', 'detail_attachement', 'tracabilite_validation_attachement',
        'liste_decomptes', 'detail_decompte', 'calcul_retard_decompte', 'fiche_controle',
        'ordres_service', 'details_ordre_service', 'api_jours_decoules', 'download_document',
        'liste_notifications', 'notification_panel', 'notifications_non_lues_api',
        'notification_data_api', 'profile_modal', 'password_modal', 'serve_avatar',
        'manifest', 'serviceworker', 'sommaire', 'sommaire_projet', 'sommaire_onglet',
    },
    'goplan': {'liste_plans', 'gantt_plan', 'taches_inline', 'apercu_plan', 'export_mspdi',
               'liste_calendriers'},
    '': {'login', 'logout', 'password_reset', 'password_reset_done', 'password_reset_confirm',
         'password_reset_complete', 'access_denied', 'home', 'manifest', 'serviceworker',
         'offline'},
}

# Personal account/session state does not change dossier data.
PERSONAL_VIEWS = {
    'projets': {'password_change', 'set_theme', 'mark_version_seen',
                'mark_notification_as_read', 'mark_notification_as_unread',
                'mark_selected_as_read', 'mark_all_notifications_as_read',
                'marquer_notification_lue', 'marquer_guide_observateur'},
    '': {'login', 'logout', 'password_reset', 'password_reset_confirm'},
}

OBJECT_SCOPES = {
    'attachement_id': ('Attachement', 'projet_id'),
    'decompte_id': ('Decompte', 'attachement__projet_id'),
    'document_id': ('DocumentAdministratif', 'projet_id'),
    'fichier_id': ('FichierSuivi', 'suivi__projet_id'),
    'rapport_id': ('RapportJournalier', 'projet_id'),
    'situation_id': ('SituationMensuelle', 'projet_id'),
    'atelier_id': ('Atelier', 'projet_id'),
    'ordre_id': ('OrdreService', 'projet_id'),
    'ca_id': ('ChiffreAffaire', 'projet_id'),
    'lot_id': ('LotProjet', 'projet_id'),
}

DOWNLOAD_SCOPES = {
    'attachement': 'projet_id',
    'decompte': 'attachement__projet_id',
    'ordreservice': 'projet_id',
    'documentadministratif': 'projet_id',
    'fichiersuivi': 'suivi__projet_id',
    'rapportjournalier': 'projet_id',
    'situationmensuelle': 'projet_id',
    'documentsituationmensuelle': 'situation__projet_id',
    'processvalidation': 'attachement__projet_id',
    'etapevalidation': 'processValidation__attachement__projet_id',
}


def observer_route_allowed(namespace, name, method):
    if name in PERSONAL_VIEWS.get(namespace, set()):
        return True
    return method in {'GET', 'HEAD', 'OPTIONS'} and name in READ_VIEWS.get(namespace, set())


def plans_observables(user):
    from goplan.models import GPlan
    from projets.models import Projet

    return GPlan.objects.filter(
        content_type=ContentType.objects.get_for_model(Projet),
        object_id__in=projets_accessibles(user).values('pk'),
    )


def verifier_perimetre_observateur(request, match):
    accessibles = projets_accessibles(request.user)
    kwargs = match.kwargs
    if 'projet_id' in kwargs and not accessibles.filter(pk=kwargs['projet_id']).exists():
        raise PermissionDenied("Ce projet n'appartient pas à vos dossiers.")
    for key, (model_name, project_path) in OBJECT_SCOPES.items():
        if key in kwargs:
            model = apps.get_model('projets', model_name)
            qs = model.objects.filter(pk=kwargs[key], **{project_path + '__in': accessibles})
            if 'projet_id' in kwargs:
                qs = qs.filter(**{project_path: kwargs['projet_id']})
            if not qs.exists():
                raise PermissionDenied("Cet élément n'appartient pas à vos dossiers.")
    if match.url_name == 'detail_tache':
        from projets.models import Tache
        if not Tache.objects.filter(pk=kwargs['pk'], projet__in=accessibles).exists():
            raise PermissionDenied
    if 'plan_id' in kwargs and not plans_observables(request.user).filter(pk=kwargs['plan_id']).exists():
        raise PermissionDenied("Ce planning n'est pas rattaché à un projet de vos dossiers.")
    if match.url_name == 'download_document':
        name = kwargs['model_name'].lower()
        path = DOWNLOAD_SCOPES.get(name)
        if not path:
            raise PermissionDenied("Ce type de document n'est pas consultable.")
        model = apps.get_model('projets', name)
        if not model.objects.filter(pk=kwargs['object_id'], **{path + '__in': accessibles}).exists():
            raise PermissionDenied("Ce document n'appartient pas à vos dossiers.")


@lru_cache(maxsize=1)
def observer_url_patterns():
    """Share the server's named-route policy with the read-only interface."""
    patterns = []

    def visit(resolver, prefix='', namespace=''):
        for route in resolver.url_patterns:
            expression = route.pattern.regex.pattern.removeprefix('^').removesuffix('$').removesuffix(r'\Z')
            if isinstance(route, URLResolver):
                visit(route, prefix + expression, route.namespace or namespace)
            elif route.name:
                methods = [method for method in ('GET', 'POST')
                           if observer_route_allowed(namespace, route.name, method)]
                if methods:
                    expression = re.sub(r'\(\?P<[^>]+>', '(?:', expression)
                    patterns.append({'pattern': '^/' + prefix + expression + '$', 'methods': methods})

    visit(get_resolver())
    return patterns
