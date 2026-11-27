from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from projets.decorators import est_observateur
from projets.services.home_contexte import construire_contexte_home


MODULES_APROPOS = (
    ('fa-file-invoice', 'Bordereau des prix',
     "Lots et lignes de prix hiérarchisés, aperçu avant impression et export Excel."),
    ('fa-file-signature', 'Ordres de service et délais',
     "OS de commencement, d'arrêt et de reprise, avec calcul de l'échéance et alertes de dépassement."),
    ('fa-ruler-combined', 'Attachements',
     "Quantités réalisées par période, circuit de validation et traçabilité de chaque étape."),
    ('fa-money-check-dollar', 'Décomptes',
     "Décomptes issus des attachements : retenues, TVA, net à payer et suivi des paiements."),
    ('fa-chart-column', "Chiffre d'affaires mensuel",
     "Production du mois, cumul et avancement rapportés au marché."),
    ('fa-coins', 'Situations mensuelles',
     "Recettes, dépenses, stocks et résultat du mois, avec aperçu imprimable."),
    ('fa-clipboard-list', "Suivi d'exécution et rapports",
     "Rapports journaliers, fichiers de suivi, ateliers, planning des ateliers et ressources affectées."),
    ('fa-calendar-alt', 'Plannings',
     "Diagramme de Gantt, calendriers de travail, tâches et export MS Project."),
    ('fa-folder-open', 'Documents et notifications',
     "Documents administratifs du marché, téléchargements sécurisés et alertes sur vos projets."),
)


def landing(request):
    if request.user.is_authenticated:
        if est_observateur(request.user):
            return redirect('projets:home')
        return redirect('projets:liste_projets')
    return render(request, 'projets/landing/apropos.html', {'modules': MODULES_APROPOS})

@login_required
def home(request):
    today = timezone.localdate()
    ctx = construire_contexte_home(request.user, today)
    if request.headers.get('HX-Request'):
        return render(request, 'projets/home/_home_content.html', ctx)
    return render(request, 'projets/home/home.html', ctx)

@login_required
@require_POST
def marquer_guide_observateur(request):
    """Mémorise la préférence « Ne plus afficher » du guide de bienvenue (action personnelle)."""
    if not est_observateur(request.user):
        raise PermissionDenied
    profile = request.user.profile
    profile.guide_observateur_masque = request.POST.get('ne_plus_afficher') == '1'
    profile.save(update_fields=['guide_observateur_masque'])
    request.session['observer_guide_ferme'] = True
    return JsonResponse({'success': True, 'masque': profile.guide_observateur_masque})


def apropos(request):
    return render(request, 'projets/landing/apropos.html', {'modules': MODULES_APROPOS})


@require_GET
def offline_view(request):
    return render(request, 'projets/landing/offline.html')


def permission_denied(request, exception=None):
    return render(request, 'errors/access_restricted.html', status=403)


def page_not_found(request, exception=None):
    return render(request, 'errors/access_restricted.html', {
        'page_not_found': True,
    }, status=404)
