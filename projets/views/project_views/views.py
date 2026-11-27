from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projets.decorators import (
    can_view_projet, chef_projet_required, dossier_utilisateur, est_admin_dossier,
    peut_creer_projet, peut_gerer_projet, peut_supprimer_projet,
    projets_accessibles, superuser_required,
)
from projets.forms import DossierForm, ProjetForm
from projets.models import Dossier, Notification, Projet
from projets.models.profile import Profile
from projets.services.dashboard_contexte import construire_contexte_dashboard
from projets.utils.utils import render_page_or_fragment


@superuser_required
def gerer_dossiers(request):
    if request.method == 'POST':
        form = DossierForm(request.POST, user=request.user)
        if form.is_valid():
            dossier = form.save()
            messages.success(
                request,
                f'Le dossier « {dossier.nom} » a été créé et ses projets ont été rattachés.',
            )
            return redirect('projets:gerer_dossiers')
    else:
        form = DossierForm(user=request.user)
    context = {
        'form': form,
        'dossiers': Dossier.objects.prefetch_related('projets'),
        'projets_sans_dossier': Projet.objects.filter(dossier__isnull=True).order_by('nom'),
    }

    return render_page_or_fragment(
        request,
        full_template='projets/dossiers/gerer_dossiers.html',
        fragment_template='projets/dossiers/_gerer_dossiers_content.html',
        context=context,
    )

    
@login_required
def modifier_dossier(request, dossier_id):
    dossier = get_object_or_404(Dossier, id=dossier_id)
    if not request.user.is_superuser and (
        not est_admin_dossier(request.user)
        or dossier_utilisateur(request.user).pk != dossier.pk
    ):
        raise PermissionDenied

    if request.method == 'POST':
        form = DossierForm(request.POST, instance=dossier, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Le dossier « {dossier.nom} » a été modifié.')
            return redirect('projets:gerer_dossiers' if request.user.is_superuser else 'projets:home')
    else:
        form = DossierForm(instance=dossier, user=request.user)

    context = {
        'form': form,
        'dossier': dossier,
    }

    # ⚡ Rendu conditionnel : fragment si requête HTMX, page complète sinon
    if request.headers.get('HX-Request'):
        return render(request, 'projets/dossiers/_modifier_dossier_content.html', context)
    return render(request, 'projets/dossiers/modifier_dossier.html', context)


@superuser_required
@require_POST
def supprimer_dossier(request, dossier_id):
    dossier = get_object_or_404(Dossier, pk=dossier_id)
    if dossier.projets.exists() or dossier.utilisateurs.exists():
        messages.error(request, "Retirez les projets et les utilisateurs avant de supprimer ce dossier.")
        return redirect('projets:gerer_dossiers')
    try:
        dossier.delete()
    except ProtectedError:
        messages.error(request, "Ce dossier contient encore des référentiels ou des calendriers.")
        return redirect('projets:gerer_dossiers')
    messages.success(request, "Le dossier a été supprimé.")
    return redirect('projets:gerer_dossiers')

from django.core.paginator import Paginator

@login_required
def liste_projets(request):
    search_term = request.GET.get('search', '').strip()
    sort_field = request.GET.get('sort')
    sort_order = request.GET.get('order', 'asc')
    # vue = request.GET.get('vue') or request.COOKIES.get('projets_vue', 'tableau')
    # Vue : URL > préférence utilisateur > défaut
    vue_param = request.GET.get('vue')
    if vue_param in ('tableau', 'cartes'):
        vue = vue_param
        # Mettre à jour la préférence utilisateur (persistant)
        try:
            profile = request.user.profile
            if profile.liste_projets_vue != vue:
                profile.liste_projets_vue = vue
                profile.save(update_fields=['liste_projets_vue'])
        except Profile.DoesNotExist:
            pass
    else:
        try:
            vue = request.user.profile.liste_projets_vue or 'tableau'
        except Profile.DoesNotExist:
            vue = 'tableau'
    if vue not in ('tableau', 'cartes'):
        vue = 'tableau'
 
    can_handler = peut_gerer_projet(request.user)

    projets = (
        projets_accessibles(request.user)
        .select_related('dossier', 'entreprise')
        .prefetch_related('attachements')
    )

    if search_term and len(search_term) >= 3:
        query = (
            Q(nom__icontains=search_term)
            | Q(numero__icontains=search_term)
            | Q(maitre_ouvrage__icontains=search_term)
            | Q(entreprise__nom__icontains=search_term)
            | Q(localisation__icontains=search_term)
        )
        projets = projets.filter(query)

    # Tri (avancement retiré : ne fonctionne pas sur une @property)
    if sort_field:
        sort_mapping = {
            'nom': 'nom',
            'numero': 'numero',
            'maitre_ouvrage': 'maitre_ouvrage',
            'entreprise': 'entreprise__nom',
            'montant_total': 'montant',
            'localisation': 'localisation',
            'statut': 'statut',
        }
        if sort_field in sort_mapping:
            order_field = sort_mapping[sort_field]
            if sort_order == 'desc':
                order_field = f'-{order_field}'
            projets = projets.order_by(order_field)
        else:
            projets = projets.order_by('nom')
    else:
        projets = projets.order_by('nom')

    # Pagination : 25 par page
    paginator = Paginator(projets, 25)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    context = {
        'can_handler': can_handler,
        'can_create_project': peut_creer_projet(request.user),
        'can_delete_project': peut_supprimer_projet(request.user),
        'page_obj': page_obj,
        'projets': page_obj,  # rétrocompatibilité
        'vue': vue,
        'search_term': search_term,
        'notification_urgency_levels': Notification.NIVEAU_URGENCE,
        'notification_types': Notification.TYPE_NOTIFICATION,
    }

        # Cas particulier : HTMX pour rafraîchir la liste seule
    if request.headers.get('HX-Request'):
        hx_target = request.headers.get('HX-Target', '')

        if hx_target == 'liste_projets':
            # Juste le partial tableau/cartes
            return render(request, 'projets/projets/_liste_projets_partial.html', context)
        
        # Sinon, fragment complet (avec en-tête et contrôles)
        return render(request, 'projets/projets/_liste_projets_content.html', context)

    # Rendu classique (accès direct, F5)
    return render(request, 'projets/projets/liste_projets.html', context)


@chef_projet_required
def ajouter_projet_modal(request):
    if not peut_creer_projet(request.user):
        raise PermissionDenied("Vous ne pouvez pas créer de projet.")
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if request.method == 'POST':
        form = ProjetForm(request.POST, user=request.user)
        if form.is_valid():
            projet = form.save(commit=False)
            projet.montant = 0
            projet.save()
            projet.users.add(request.user)

            from projets.services.notification_service import NotificationService
            NotificationService.creer_notification_personnalisee(
                utilisateur=request.user,
                type_notif='PROJET_MODIFIE',
                titre=f'Nouveau projet: {projet.nom}',
                message=f'Le projet {projet.nom} a été créé.',
                projet=projet,
                niveau_urgence='MOYEN',
            )
            if is_ajax:
                return JsonResponse({'success': True})
            messages.success(request, 'Projet ajouté avec succès.')
            return redirect('projets:liste_projets')

        if is_ajax:
            return JsonResponse({'success': False, 'errors': form.errors.as_json()})
        print(form.errors)
        messages.error(request, "Erreur lors de l'ajout du projet. Veuillez corriger les erreurs ci-dessous.")
        messages.error(request, form.errors)
        return redirect('projets:liste_projets')

    form = ProjetForm(user=request.user)
    return render(request, 'projets/projets/ajouter_projet_modal.html', {
        'form': form,
        'statuts': Projet.Statut.choices,
    })


@chef_projet_required
def modifier_projet_modal(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    if request.method == 'POST':
        form = ProjetForm(request.POST, instance=projet, user=request.user)
        if form.is_valid():
            projet = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Projet modifié avec succès!',
                    'projet': {
                        'nom': projet.nom,
                        'avancement': projet.avancement,
                        'statut': projet.get_statut_display(),
                    },
                })
            return redirect('projets:liste_projets')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('modal'):
            return JsonResponse({
                'success': False,
                'errors': form.errors.get_json_data(),
                'message': 'Veuillez corriger les erreurs ci-dessous',
            }, status=400)

    else:
        form = ProjetForm(instance=projet, user=request.user)
    return render(request, 'projets/projets/modifier_projet_modal.html', {
        'form': form,
        'projet': projet,
        'statuts': Projet.Statut.choices,
        'entreprises': form.fields['entreprise'].queryset,
    })


@chef_projet_required
def supprimer_projet(request, projet_id):
    if not peut_supprimer_projet(request.user):
        raise PermissionDenied("La suppression d'un projet est réservée aux administrateurs.")
    projet = get_object_or_404(Projet, id=projet_id)
    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non supportée'}, status=405)
    projet.delete()
    return redirect('projets:liste_projets')


@login_required
@can_view_projet
def dashboard_projet(request, projet_id):
    projet = get_object_or_404(Projet.objects.select_related('dossier'), id=projet_id)
    ctx = construire_contexte_dashboard(request.user, projet)

    template = (
        'projets/dashboard_projet/_dashboard_fragment.html'
        if request.headers.get('HX-Request')
        else 'projets/dashboard_projet/dashboard.html'
    )
    return render(request, template, ctx)