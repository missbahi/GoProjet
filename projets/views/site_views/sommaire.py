from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from projets.decorators import (
    consultation_projet_required, est_chef_projet, est_observateur, projets_accessibles,
)
from projets.services import sommaire as service
from projets.services.home_indicators import indicateurs_home
from projets.utils.navigation import crumb
from projets.utils.utils import render_page_or_fragment


ONGLETS = (
    ('dashboard', 'Dashboard', 'fa-home'),
    ('bordereau', 'Bordereau', 'fa-file-invoice'),
    ('situations', 'Situations', 'fa-coins'),
)


def sommaire_liste_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        user = request.user
        if not (user.is_superuser or est_observateur(user) or est_chef_projet(user)):
            raise PermissionDenied
        return view_func(request, *args, **kwargs)
    return login_required(wrapped)


def _projet_avec_indicateurs(request, projet_id, today):
    projet = get_object_or_404(projets_accessibles(request.user).select_related('dossier', 'entreprise'), pk=projet_id)
    indicateurs_home([projet], today)
    return projet


@require_GET
@sommaire_liste_required
def sommaire_liste(request):
    today = timezone.localdate()
    projets = list(projets_accessibles(request.user).select_related('entreprise', 'dossier')
                   .order_by('-date_creation', '-pk'))
    indicateurs_home(projets, today)
    return render_page_or_fragment(
        request, 'projets/sommaire/sommaire_liste.html', 'projets/sommaire/_sommaire_liste_content.html',
        {'projets': projets, 'date_indicateurs': today,
         'evolution': service.evolution_avec_resultat((p.pk for p in projets), today),
         'evolution_titre': 'Évolution mensuelle — tous vos projets',
         'nb_en_retard': sum(p.home_en_retard for p in projets)},
    )


@require_GET
@consultation_projet_required
def sommaire_projet(request, projet_id):
    today = timezone.localdate()
    projet = _projet_avec_indicateurs(request, projet_id, today)
    return render_page_or_fragment(
        request, 'projets/sommaire/sommaire_projet.html', 'projets/sommaire/_sommaire_projet_content.html',
        {'projet': projet, 'date_indicateurs': today, 'onglets': ONGLETS,
         'evolution': service.evolution_avec_resultat([projet.pk], today),
         'evolution_titre': 'Évolution mensuelle du projet',
         'breadcrumb_items': [
             crumb('Sommaire', 'projets:sommaire', icon='fas fa-list-check'),
             crumb(projet.nom),
         ]},
    )


@require_GET
@consultation_projet_required
def sommaire_onglet(request, projet_id, onglet):
    if onglet not in {code for code, _, _ in ONGLETS}:
        raise Http404
    if not request.headers.get('HX-Request'):
        return redirect('projets:sommaire_projet', projet_id=projet_id)
    today = timezone.localdate()
    projet = _projet_avec_indicateurs(request, projet_id, today)
    context = {'projet': projet, 'onglet': onglet, 'onglets': ONGLETS, 'date_indicateurs': today}
    if onglet == 'dashboard':
        context.update(
            lots=service.synthese_lots(projet),
            decomptes=service.synthese_decomptes(projet),
            administratif=service.suivi_administratif(projet),
            taches=service.prochaines_taches(projet, today),
        )
    elif onglet == 'bordereau':
        context['lots'] = service.synthese_lots(projet)
    else:
        context['situations'] = service.synthese_situations(projet)
    return render(request, 'projets/sommaire/_onglet.html', context)
