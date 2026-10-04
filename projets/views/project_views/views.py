from decimal import Decimal
from projets.models.profile import Profile

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from projets.decorators import can_view_projet, chef_projet_required, projets_accessibles, superuser_required
from projets.forms import DossierForm, ProjetForm
from projets.models import (
    Attachement, Decompte, DocumentAdministratif, Dossier, Entreprise,
    Notification, OrdreService, Projet, SuiviExecution,
)
from projets.utils.utils import render_page_or_fragment


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

    context = {
        'form': form,
        'dossier': dossier,
    }

    # ⚡ Rendu conditionnel : fragment si requête HTMX, page complète sinon
    if request.headers.get('HX-Request'):
        return render(request, 'projets/dossiers/_modifier_dossier_content.html', context)
    return render(request, 'projets/dossiers/modifier_dossier.html', context)

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

    can_handler = request.user.is_superuser or request.user.dossiers_geres.exists()

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
            return render(request, 'projets/partials/_liste_projets_partial.html', context)
        
        # Sinon, fragment complet (avec en-tête et contrôles)
        return render(request, 'projets/partials/_liste_projets_content.html', context)

    # Rendu classique (accès direct, F5)
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
    ordres_notifies = list(
        ordre_services.filter(statut='NOTIFIE', date_effet__isnull=False)
        .select_related('type_os')
        .order_by('date_effet', 'ordre_sequence')
    )
    osc = min(
        (ordre for ordre in ordres_notifies if ordre.type_os.code == 'OSC'),
        key=lambda ordre: ordre.ordre_sequence,
        default=None,
    )
    today = timezone.localdate()
    date_fin_previsionnelle = projet.date_fin_previsionnelle(today)
    jours_ecoules = projet.jours_decoules_depuis_demarrage(today)
    date_fin_contractuelle = projet.ajouter_delai(osc.date_effet) if osc else None
    jours_extension = (
        (date_fin_previsionnelle - date_fin_contractuelle).days
        if date_fin_previsionnelle and date_fin_contractuelle else 0
    )
    jours_avant_echeance = (
        (date_fin_previsionnelle - today).days if date_fin_previsionnelle else None
    )

    if not projet.delai:
        statut_delai = 'INCOMPLET'
        libelle_delai = 'Délai à renseigner'
        message_delai = 'Ajoutez le délai contractuel pour activer le suivi de l’échéance.'
    elif not osc:
        statut_delai = 'ATTENTE_OSC'
        libelle_delai = 'OSC attendu'
        message_delai = 'La date de fin sera calculée après notification de l’OS de commencement.'
    elif jours_avant_echeance is not None and jours_avant_echeance < 0:
        statut_delai = 'RETARD'
        libelle_delai = f'{abs(jours_avant_echeance)} jour(s) de dépassement'
        message_delai = 'L’échéance prévisionnelle est dépassée.'
    elif projet.projet_en_arret:
        statut_delai = 'ARRET'
        libelle_delai = 'Chantier en arrêt'
        message_delai = 'L’échéance sera recalculée après notification de l’OS de reprise.'
    elif jours_avant_echeance is not None and jours_avant_echeance <= 30:
        statut_delai = 'ALERTE'
        libelle_delai = f'Échéance dans {jours_avant_echeance} jour(s)'
        message_delai = 'La date de fin prévisionnelle approche.'
    else:
        statut_delai = 'NORMAL'
        libelle_delai = 'Dans les délais'
        message_delai = 'Aucune alerte de délai à ce jour.'

    delai_pilotage = {
        'osc': osc,
        'date_fin': date_fin_previsionnelle,
        'jours_ecoules': jours_ecoules,
        'jours_extension': jours_extension,
        'jours_avant_echeance': jours_avant_echeance,
        'statut': statut_delai,
        'libelle': libelle_delai,
        'message': message_delai,
    }
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
        'delai_pilotage': delai_pilotage,
        'suivis_execution': suivis_execution,
        'rapports_journaliers': rapports_journaliers,
        'dernier_rapport_journalier': dernier_rapport_journalier,
        'situations_mensuelles': situations_mensuelles,
        'derniere_situation_mensuelle': derniere_situation_mensuelle,
    })