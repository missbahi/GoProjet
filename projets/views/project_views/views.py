from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from projets.decorators import can_view_projet, chef_projet_required, projets_accessibles, superuser_required
from projets.forms import DossierForm, ProjetForm
from projets.models import (
    Attachement, Decompte, DocumentAdministratif, Dossier, Entreprise,
    Notification, OrdreService, Projet, SuiviExecution,
)


@superuser_required
def gerer_dossiers(request):
    if request.method == 'POST':
        form = DossierForm(request.POST)
        if form.is_valid():
            dossier = form.save()
            messages.success(
                request,
                f'Le dossier « {dossier.nom} » a été créé et ses projets ont été rattachés.',
            )
            return redirect('projets:gerer_dossiers')
    else:
        form = DossierForm()

    return render(request, 'projets/dossiers/gerer_dossiers.html', {
        'form': form,
        'dossiers': Dossier.objects.prefetch_related('projets'),
        'projets_sans_dossier': Projet.objects.filter(dossier__isnull=True).order_by('nom'),
    })


@superuser_required
def modifier_dossier(request, dossier_id):
    dossier = get_object_or_404(Dossier, id=dossier_id)
    if request.method == 'POST':
        form = DossierForm(request.POST, instance=dossier)
        if form.is_valid():
            form.save()
            messages.success(request, f'Le dossier « {dossier.nom} » a été modifié.')
            return redirect('projets:gerer_dossiers')
    else:
        form = DossierForm(instance=dossier)

    return render(request, 'projets/dossiers/modifier_dossier.html', {
        'form': form,
        'dossier': dossier,
    })


@login_required
def liste_projets(request):
    search_term = request.GET.get('search', '').strip()
    sort_field = request.GET.get('sort')
    sort_order = request.GET.get('order', 'asc')
    can_handler = request.user.is_superuser or request.user.dossiers_geres.exists()
    projets = projets_accessibles(request.user).order_by('nom')

    if search_term and len(search_term) >= 3:
        query = (
            Q(nom__icontains=search_term)
            | Q(numero__icontains=search_term)
            | Q(maitre_ouvrage__icontains=search_term)
            | Q(entreprise__nom__icontains=search_term)
            | Q(localisation__icontains=search_term)
        )
        projets = projets.filter(query)

    if sort_field:
        sort_mapping = {
            'nom': 'nom',
            'numero': 'numero',
            'maitre_ouvrage': 'maitre_ouvrage',
            'entreprise': 'entreprise__nom',
            'montant_total': 'montant',
            'localisation': 'localisation',
            'statut': 'statut',
            'avancement': 'avancement_workflow',
        }
        if sort_field in sort_mapping:
            order_field = sort_mapping[sort_field]
            if sort_order == 'desc':
                order_field = f'-{order_field}'
            projets = projets.order_by(order_field)

    context = {
        'can_handler': can_handler,
        'projets': projets,
        'notification_urgency_levels': Notification.NIVEAU_URGENCE,
        'notification_types': Notification.TYPE_NOTIFICATION,
        'search_term': search_term,
    }
    if request.headers.get('HX-Request'):
        return render(request, 'projets/partials/liste_projets_partial.html', context)
    return render(request, 'projets/liste_projets.html', context)


@chef_projet_required
def ajouter_projet_modal(request):
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
    return render(request, 'projets/modals/ajouter_projet_modal.html', {
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

    form = ProjetForm(instance=projet, user=request.user)
    return render(request, 'projets/modals/modifier_projet_modal.html', {
        'form': form,
        'projet': projet,
        'statuts': Projet.Statut.choices,
        'entreprises': Entreprise.objects.all(),
    })


@chef_projet_required
def supprimer_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    projet.delete()
    return redirect('projets:liste_projets')


@login_required
@can_view_projet
def dashboard_projet(request, projet_id):
    projet = get_object_or_404(Projet.objects.select_related('dossier'), id=projet_id)
    rapports_journaliers = projet.rapports_journaliers.all()
    dernier_rapport_journalier = rapports_journaliers.first()
    situations_mensuelles = projet.situations_mensuelles.all()
    derniere_situation_mensuelle = situations_mensuelles.first()
    lots = projet.lots.all()
    montant_total = sum((lot.montant_total_ttc for lot in lots), Decimal('0'))
    montant_total_formate = '{:,.2f}'.format(montant_total).replace(',', ' ') if montant_total else '0.00'

    decomptes = Decompte.objects.filter(attachement__projet=projet)
    total_decomptes = decomptes.count()
    decomptes_payes = decomptes.filter(statut='PAYE').count()
    decomptes_emis = decomptes.filter(statut='EMIS').count()
    decomptes_retard = decomptes.filter(statut='EN_RETARD').count()
    decomptes_recents = decomptes.order_by('-date_emission')[:5]
    attachements = Attachement.objects.filter(projet=projet)
    documents_administratifs = DocumentAdministratif.objects.filter(projet=projet)
    ordre_services = OrdreService.objects.filter(projet=projet)
    suivis_execution = SuiviExecution.objects.filter(projet=projet)
    can_handler = request.user.is_superuser or request.user.dossiers_geres.exists()

    return render(request, 'projets/dashboard.html', {
        'can_handler': can_handler,
        'projet': projet,
        'lots': lots,
        'montant_total': montant_total_formate,
        'total_decomptes': total_decomptes,
        'decomptes_payes': decomptes_payes,
        'decomptes_emis': decomptes_emis,
        'decomptes_retard': decomptes_retard,
        'decomptes_recents': decomptes_recents,
        'attachements': attachements,
        'documents_administratifs': documents_administratifs,
        'ordre_services': ordre_services,
        'suivis_execution': suivis_execution,
        'rapports_journaliers': rapports_journaliers,
        'dernier_rapport_journalier': dernier_rapport_journalier,
        'situations_mensuelles': situations_mensuelles,
        'derniere_situation_mensuelle': derniere_situation_mensuelle,
    })