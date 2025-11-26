from datetime import date, datetime, timedelta
import json
import os
import cloudinary
from django.apps import apps
from django.conf import settings

from django.forms import ValidationError
from django.shortcuts import render, get_object_or_404, redirect

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound, HttpResponseRedirect, JsonResponse, FileResponse, Http404
from django.urls import  reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views import View

from projets.decorators import chef_projet_required, superuser_required
from projets.manager import BordereauTreeManager

from .forms import ClientForm, DecompteForm, EntrepriseForm, IngenieurForm, OrdreServiceForm, ProjetForm, TacheForm, AttachementForm
from .models import Attachement, Decompte, Entreprise, FichierSuivi, Ingenieur, Notification, OrdreService, Profile, Projet, SuiviExecution, TypeOrdreService
from .models import  LotProjet, LigneAttachement, LigneBordereau, Client, DocumentAdministratif, Tache
from .models import Attachement, ProcessValidation

from django.views.generic import ListView

from django.db.models import Sum, Avg, Q 
from django.contrib import messages

from django.contrib.auth.models import User 
from django.contrib.auth.decorators import permission_required, login_required, user_passes_test
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
import logging
logger = logging.getLogger(__name__)
from django.utils import timezone

#------------------ POur la Gestion des taches ------------------
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from decimal import Decimal
from django.contrib.auth import views as auth_views

MAX_UPLOAD_SIZE = 5 * 1024 * 1024
VIEWABLE_TYPES = {
        '.pdf': 'application/pdf',
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.txt': 'text/plain',
        '.csv': 'text/csv',
        '.html': 'text/html',
        '.htm': 'text/html',
    }

import django
from django.views.decorators.csrf import csrf_exempt
def get_file_field(instance):
    return getattr(instance, 'fichier', None) or getattr(instance, 'documents', None) or getattr(instance, 'fichier_validation', None)

def get_projet_from_instance(instance):
    if hasattr(instance, 'projet'):
        return instance.projet
    elif hasattr(instance, 'suivi'):
        return instance.suivi.projet
    elif hasattr(instance, 'attachement'):
        return instance.attachement.projet
    return None

def extract_filename_from_url(url):
    """Extrait un nom de fichier depuis une URL Cloudinary"""
    if not url:
        return None
    
    filename = url.split('/')[-1]
    if '?' in filename:
        filename = filename.split('?')[0]
    if '._' in filename:
        filename = filename.split('._')[0] + '.' + filename.split('.')[-1]
    
    return filename
@login_required
def secure_download(request, model_name, object_id):
    """
    Téléchargement sécurisé avec tous les paramètres dans l'URL
    model_name: nom du modèle (Attachment, Document, etc.)
    object_id: ID de l'objet à télécharger
    """
    model = apps.get_model('projets', model_name)
    if not model:
        return HttpResponseForbidden("Modèle non reconnu")
    
    # On cherche l'objet
    obj = get_object_or_404(model, id=object_id)
    if not obj:
        return HttpResponseNotFound("Objet non trouvé")
    
    # On cherche le projet associé
    projet = get_projet_from_instance(obj)
    if not projet:
        return HttpResponseForbidden("Projet non trouvé pour cet objet")
    if not request.user.has_perm('projets.view_projet', projet):
        return HttpResponseForbidden("Accès refusé au projet associé")
    
    # On cherche le fichier
    file_field = get_file_field(obj)
    if not file_field:
        return HttpResponseForbidden("Aucun fichier lié à cet objet")
    
    # On force le download si demandé
    force_download = request.GET.get('download', 'false').lower() == 'true'
    
    if force_download:
        # Récupérer le nom original pour le header
        if hasattr(obj, 'original_filename') and obj.original_filename:
            original_filename = obj.original_filename
        else:
            original_filename = extract_filename_from_url(file_field.url)
        
        print(f"Original filename for download: {file_field.url} -> {original_filename}")
        # Redirection vers Cloudinary avec le nom original
        return serve_file_with_original_name(file_field, original_filename)
    else:        
        # On récupère l'URL du fichier
        url = file_field.url
        # Redirection vers Cloudinary
        return HttpResponseRedirect(url)

def serve_file_with_original_name(file_field, original_filename):
    """Télécharge le fichier avec le nom original"""
    try:
        import requests
        import urllib.parse
        
        cloudinary_url = file_field.url
        print(f"🔍 URL Cloudinary avant nettoyage: {cloudinary_url}")
        if '%20=' in cloudinary_url:
            cloudinary_url = cloudinary_url.replace('%20=', '')
            print(f"🔧 URL nettoyée: {cloudinary_url}")
        
        response = requests.get(cloudinary_url, stream=True)
        response.raise_for_status()
        
        django_response = HttpResponse(
            response.iter_content(chunk_size=8192),
            content_type=response.headers.get('content-type', 'application/octet-stream')
        )
        
        encoded_filename = urllib.parse.quote(original_filename)
        django_response['Content-Disposition'] = f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        
        return django_response
        
    except Exception as e:
        print(f"Erreur téléchargement: {e}")
        return HttpResponseRedirect(file_field.url)
    
@csrf_exempt
def diagnostic(request):
    """Page de diagnostic complète pour Railway"""
    
    # Test des fichiers statiques
    static_tests = {}
    js_files_to_check = [
        'projets/js/modals.js',
        'projets/js/chart.js', 
        'projets/js/profile.js',
        'projets/js/notification-handler.js',
        'projets/images/default.png'
    ]
    
    for file_path in js_files_to_check:
        full_path = os.path.join(settings.STATIC_ROOT, file_path)
        static_tests[file_path] = {
            'exists': os.path.exists(full_path),
            'path': full_path,
            'in_static_root': os.path.exists(settings.STATIC_ROOT)
        }
    
    # Informations système
    system_info = {
        'django_version': django.get_version(),
        'debug_mode': settings.DEBUG,
        'static_root': settings.STATIC_ROOT,
        'static_url': settings.STATIC_URL,
        'staticfiles_dirs': [str(p) for p in settings.STATICFILES_DIRS],
        'installed_apps': [app for app in settings.INSTALLED_APPS if 'django' not in app],
        'database': settings.DATABASES['default']['ENGINE'],
        'whitenoise_in_middleware': 'whitenoise.middleware.WhiteNoiseMiddleware' in settings.MIDDLEWARE
    }
    
    # Test URLs
    base_url = request.build_absolute_uri('/')[:-1]
    test_urls = {
        'home_page': f"{base_url}/",
        'login_page': f"{base_url}/accounts/login/",
        'static_modals_js': f"{base_url}/static/projets/js/modals.js",
        'static_chart_js': f"{base_url}/static/projets/js/chart.js",
        'diagnostic_page': f"{base_url}/diagnostic/",
    }
    
    context = {
        'system_info': system_info,
        'static_tests': static_tests,
        'test_urls': test_urls,
        'base_url': base_url,
    }

    return render(request, 'projets/diagnostic.html', context)

#------------------ Puur la Gestion de login ------------------
class CustomLoginView(auth_views.LoginView):
    template_name = 'authentification/login.html'
    
    def form_valid(self, form):
        messages.success(self.request, "Connexion réussie !")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, "Identifiant ou mot de passe incorrect.")
        return super().form_invalid(form)

class CustomPasswordResetView(auth_views.PasswordResetView):
    template_name = 'authentification/password_reset_form.html'
    email_template_name = 'authentification/password_reset_email.html'
    subject_template_name = 'authentification/password_reset_subject.txt'
    success_url = reverse_lazy('password_reset_done')
    def get_template_names(self):
        templates = super().get_template_names()
        return templates
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        return context
    def form_valid(self, form):
        messages.info(self.request, "Un email de réinitialisation a été envoyé.")
        return super().form_valid(form)

class CustomPasswordResetDoneView(auth_views.PasswordResetDoneView):
    template_name = 'authentification/password_reset_done.html'

class CustomPasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = 'authentification/password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')
    
    def form_valid(self, form):
        messages.success(self.request, "Votre mot de passe a été modifié avec succès !")
        return super().form_valid(form)

class CustomPasswordResetCompleteView(auth_views.PasswordResetCompleteView):
    template_name = 'authentification/password_reset_complete.html'

# Vue pour gérer l'accès refusé
def access_denied(request):
    return render(request, 'authentification/access_denied.html', status=403)

#------------------ Page d'accueil ------------------
@login_required
def home(request):
    # Nombre de projets
    today = date.today()
    projets_recents = request.user.projets.all().order_by('-date_creation')[:5]  # Derniers 5 projets créés
    
    # Projets en retard (utilisant le nouveau champ en_retard)
    projets_en_retard = request.user.projets.all().filter(en_retard=True).order_by('-date_debut')[:5]
    
    # Nouveaux appels d'offres (à traiter)
    nouveaux_ao = request.user.projets.all().filter(a_traiter=True).order_by('-date_creation')[:5]
    
    # Réceptions récemment validées
    receptions_validees = request.user.projets.all().filter(reception_validee=True).order_by('-date_reception')[:5]
    
    # Statistiques principales
    nb_projets_en_cours = request.user.projets.all().filter(statut='COURS').count()
    nb_projets_en_retard = request.user.projets.all().filter(en_retard=True).count()
    
    # Avancement moyen des projets en cours
    avancement_moyen = request.user.projets.all().filter(statut='COURS').aggregate(moy=Avg('avancement'))['moy'] or 0
    
    # Appels d'offres
    nb_appels_offres = request.user.projets.all().filter(statut='AO').count()
    nb_a_traiter = request.user.projets.all().filter(a_traiter=True).count()
    
    # Réceptions
    nb_receptions_validees = request.user.projets.all().filter(reception_validee=True).count()
    nb_receptions_en_retard = request.user.projets.all().filter(reception_validee=True, en_retard=True).count()
    
    # Chiffre d'affaires
    annee_courante = date.today().year
    ca_total = request.user.projets.all().filter(date_debut__year=annee_courante).aggregate(total=Sum('montant'))['total'] or 0
    
    # Notifications non lues pour l'utilisateur connecté
    if request.user.is_authenticated:
        notifications = Notification.objects.filter(utilisateur=request.user, lue=False).order_by('-date_creation')[:5]
        nb_notifications = Notification.objects.filter(utilisateur=request.user, lue=False).count()
    else:
        notifications = []
        nb_notifications = 0

    resume_cartes = [
        {
            "titre": "Projets en cours",
            "valeur": nb_projets_en_cours,
            "couleur": "blue",
            "icône": "fa-hard-hat",
            "sous_titre": "Avancement moyen",
            "sous_valeur": f"{avancement_moyen:.0f} %",
            "progress": round(avancement_moyen)
        },
        {
            "titre": "Appels d'offres",
            "valeur": nb_appels_offres,
            "couleur": "cyan",
            "icône": "fa-file-signature",
            "sous_titre": "À traiter",
            "sous_valeur": nb_a_traiter,
            "progress": round((nb_a_traiter / nb_appels_offres) * 100) if nb_appels_offres else 0
        },
        {
            "titre": "Réceptions validées",
            "valeur": nb_receptions_validees,
            "couleur": "purple",
            "icône": "fa-check-circle",
            "sous_titre": "En retard",
            "sous_valeur": nb_receptions_en_retard,
            "progress": round((nb_receptions_en_retard / nb_receptions_validees) * 100) if nb_receptions_validees else 0
        },
        {
            "titre": "Chiffre d'affaires",
            "valeur": f"{round(ca_total / 1_000_000, 1)}M MAD",
            "couleur": "orange",
            "icône": "fa-coins",
            "sous_titre": "Cette année",
            "sous_valeur": f"{nb_receptions_validees} réceptions",
            "progress": min(100, nb_receptions_validees * 10)  # Pourcentage arbitraire pour l'affichage
        },
    ]
     # Échéances à venir (7 prochains jours)
    echeances = Tache.objects.filter(date_fin__gte=today).order_by('date_fin')[:3]

    context = {
        'projets_recents': projets_recents,
        'projets_en_retard': projets_en_retard,
        'nouveaux_ao': nouveaux_ao,
        'receptions_validees': receptions_validees,
        'resume_cartes': resume_cartes,
        'notifications': notifications,
        'nb_notifications': nb_notifications,
        'echeances': echeances,
        'projets_noms': json.dumps([p.nom for p in request.user.projets.all().all()]),
        'projets_noms_recents': json.dumps([p.nom for p in projets_recents]),
        'projets_avancements': json.dumps([round(p.avancement) if p.avancement is not None else 0 for p in request.user.projets.all().all()]),
        'avancement_projets_recents': json.dumps([round(p.avancement) if p.avancement is not None else 0 for p in projets_recents])
    }
    return render(request, 'projets/home.html', context)

# --------------- Gestion des utilisateurs ---------------
@login_required     
@user_passes_test(lambda u: u.is_superuser)
def modifier_utilisateur(request, user_id):
    user = get_object_or_404(User, id=user_id)

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        role = request.POST.get('role')

        user.email = email
        if password:
            user.set_password(password)

        if role == 'admin':
            user.is_superuser = True
            user.is_staff = True
        elif role == 'staff':
            user.is_superuser = False
            user.is_staff = True
        else:
            user.is_superuser = False
            user.is_staff = False

        if 'avatar' in request.FILES:
            profile, created = Profile.objects.get_or_create(user=user)
            profile.avatar = request.FILES['avatar']
            profile.save()

        user.save()
        return redirect('projets:liste_utilisateurs')

    return render(request, 'projets/utilisateurs/modifier_utilisateur.html', {'user': user})
@superuser_required
def liste_utilisateurs(request):
    utilisateurs = User.objects.all()
    return render(request, 'projets/utilisateurs/liste_utilisateurs.html', {'utilisateurs': utilisateurs})
@superuser_required
def ajouter_utilisateur(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user = User.objects.create_user(username=username, email=email, password=password)
        return redirect('projets:liste_utilisateurs')
    return render(request, 'projets/utilisateurs/ajouter_utilisateur.html')
@superuser_required
def supprimer_utilisateur(request, user_id):
    user = get_object_or_404(User, id=user_id)
    user.delete()
    return redirect('projets:liste_utilisateurs')   
@superuser_required
@user_passes_test(lambda u: u.is_superuser)
def gerer_projets_utilisateur(request, user_id):
    utilisateur = get_object_or_404(User, id=user_id)
    tous_les_projets = Projet.objects.all()
    projets_utilisateur = utilisateur.projets.all()
    
    if request.method == 'POST':
        # Gérer l'ajout/suppression de projets
        projets_selectionnes = request.POST.getlist('projets')
        
        # Mettre à jour la relation ManyToMany
        utilisateur.projets.set(projets_selectionnes)
        
        messages.success(request, f"Les projets de {utilisateur.username} ont été mis à jour avec succès.")
        return redirect('projets:liste_utilisateurs')
    
    context = {
        'utilisateur': utilisateur,
        'tous_les_projets': tous_les_projets,
        'projets_utilisateur': projets_utilisateur,
    }
    
    return render(request, 'projets/utilisateurs/gerer_projets_utilisateur.html', context)
# -------------- projets -------------------------
from django.db.models import Q
@login_required
def liste_projets(request):
    search_term = request.GET.get('search', '').strip()
    sort_field = request.GET.get('sort')
    sort_order = request.GET.get('order', 'asc')
    if request.user.is_superuser:
        # Superuser voit tous les projets
        projets = Projet.objects.all().order_by('nom')
    else:
        # Les autres utilisateurs voient seulement leurs projets
        projets = request.user.projets.all().order_by('nom')

    if search_term and len(search_term) >= 3:
        # Recherche dans multiple champs
        query = Q(nom__icontains=search_term) | \
                Q(numero__icontains=search_term) | \
                Q(maitre_ouvrage__icontains=search_term) | \
                Q(entreprise__nom__icontains=search_term) | \
                Q(localisation__icontains=search_term)
        
        projets = projets.filter(query)
    
    # Tri
    if sort_field:
        sort_mapping = {
            'nom': 'nom',
            'numero': 'numero',
            'maitre_ouvrage': 'maitre_ouvrage', 
            'entreprise': 'entreprise__nom',
            'montant_total': 'montant',
            'localisation': 'localisation',
            'statut': 'statut',
            'avancement': 'avancement_workflow'
        }
        
        if sort_field in sort_mapping:
            order_field = sort_mapping[sort_field]
            if sort_order == 'desc':
                order_field = f'-{order_field}'
            projets = projets.order_by(order_field)
    
    context = {
        'projets': projets,
        'notification_types': Notification.TYPE_NOTIFICATION,
        'search_term': search_term,  # Pour l'affichage dans le template
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'projets/partials/liste_projets_partial.html', context)
    
    return render(request, 'projets/liste_projets.html', context)
@chef_projet_required
def ajouter_projet_modal(request):
    if request.method == 'POST':
        form = ProjetForm(request.POST)
        if form.is_valid():
            projet = form.save()
            projet.montant = 0.0  # ou une autre valeur par défaut
            projet.users.add(request.user)  # Ajouter l'utilisateur actuel au projet
            projet.save()
            if request.GET.get('modal'):
                return JsonResponse({'success': True})
            
            messages.success(request, 'Projet ajouté avec succès.')
            return redirect('projets:liste_projets')
        else:
            if request.GET.get('modal'):
                return JsonResponse({
                    'success': False,
                    'errors': form.errors.as_json()
                })
            print(form.errors)
            messages.error(request, 'Erreur lors de l\'ajout du projet. Veuillez corriger les erreurs ci-dessous.')
            messages.error(request,form.errors)
            return redirect('projets:liste_projets')
    
    form = ProjetForm()
    
    context = {
        'form': form,
        'statuts': Projet.Statut.choices,
        'entreprises': Entreprise.objects.all()
    }
        
    return render(request, 'projets/modals/ajouter_projet_modal.html', context)
@permission_required('auth.add_user')
def modifier_projet_modal(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    if request.method == 'POST':
        form = ProjetForm(request.POST, instance=projet)
        if form.is_valid():
            projet = form.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Projet modifié avec succès!',
                    'projet': {
                        'nom': projet.nom,
                        'avancement': projet.avancement,
                        'statut': projet.get_statut_display()
                    }
                })
            return redirect('projets:liste_projets')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('modal'):
                return JsonResponse({
                    'success': False,
                    'errors': form.errors.get_json_data(),
                    'message': 'Veuillez corriger les erreurs ci-dessous'
                }, status=400)
    
    form = ProjetForm(instance=projet)
    
    context = {
        'form': form,
        'projet': projet,
        'statuts': Projet.Statut.choices,
        'entreprises': Entreprise.objects.all(),
    }
    return render(request, 'projets/modals/modifier_projet_modal.html', context)
@permission_required('auth.add_user')
def modifier_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    
    if request.method == 'POST':
        form = ProjetForm(request.POST, instance=projet)
        if form.is_valid():
            projet = form.save()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('modal'):
                return JsonResponse({
                    'success': True,
                    'message': 'Projet modifié avec succès!',
                    'projet': {
                        'nom': projet.nom,
                        'avancement': projet.avancement,
                        'statut': projet.get_statut_display()
                    }
                })
            return redirect('projets:liste_projets')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('modal'):
                return JsonResponse({
                    'success': False,
                    'errors': form.errors.get_json_data(),
                    'message': 'Veuillez corriger les erreurs ci-dessous'
                }, status=400)
    
    form = ProjetForm(instance=projet)
    
    context = {
        'form': form,
        'projet': projet,
        'statuts': Projet.Statut.choices,
        'entreprises': Entreprise.objects.all(),
        'is_modal': request.GET.get('modal')
    }
    
    # if request.GET.get('modal'):
    #     return render(request, 'projets/modifier_projet.html', context)
    return render(request, 'projets/modifier_projet.html', context)
@permission_required('auth.add_user')
def supprimer_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    projet.delete()
    return redirect('projets:liste_projets')

#------------------ Pages statiques ------------------
def apropos(request):
    return render(request, 'projets/apropos.html')

class AjaxResponseMixin:
    def render_to_json_response(self, context, success=True, status=200):
        return JsonResponse({
            'success': success,
            'data': context,
            'message': context.get('message', '')
        }, status=status)
     
# Liste des tâches - Créer une tache - Modifier une tache - Supprimer une tache - Détail d'une tache   
class ListeTachesView(LoginRequiredMixin, ListView):
    model = Tache
    template_name = 'projets/taches/liste_taches.html'
    context_object_name = 'taches'
    queryset = Tache.objects.select_related('projet', 'responsable')

    def get_queryset(self):
        queryset = super().get_queryset()
        filters = {
            'responsable_id': self.request.GET.get('responsable'),
            'terminee': {'true': True, 'false': False}.get(self.request.GET.get('terminee')),
            'priorite': self.request.GET.get('priorite')
        }
        
        return queryset.filter(**{
            k: v for k, v in filters.items() if v is not None
        })

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['responsables'] = User.objects.filter(
            tache__isnull=False
        ).distinct().order_by('username')
        return context
def get_form_data(request):
    projets = Projet.objects.values('id', 'nom')
    responsables = User.objects.values('id', 'username')
    
    # CORRECTION: Format explicite pour les priorités
    priorites = [
        {'value': value, 'label': label} 
        for value, label in Tache.PRIORITE
    ]

    return JsonResponse({
        'projets': list(projets),
        'responsables': list(responsables),
        'priorites': priorites  # Format clair {value, label}
    })
class CreerTacheView(LoginRequiredMixin, CreateView):
    model = Tache
    form_class = TacheForm
    success_url = reverse_lazy('projets:liste_taches')

    def post(self, request, *args, **kwargs):
        logger.info(
            f"Création tâche - User: {request.user} - "
            f"Données: {request.POST.dict()}"
        )
        
        form = self.get_form()
        
        if form.is_valid():
            return self.form_valid(form)
        return self.form_invalid(form)

    def form_valid(self, form):
        try:
            self.object = form.save(commit=False)
            self.object.createur = self.request.user
            self.object.save()
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'tache_id': self.object.id,
                    'message': 'Tâche créée avec succès',
                    'data': {
                        'titre': self.object.titre,
                        'projet': self.object.projet.nom if self.object.projet else None,
                        'statut': 'Terminée' if self.object.terminee else 'En cours'
                    }
                })
            
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Erreur création tâche: {str(e)}")
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Erreur serveur lors de la création'
                }, status=500)
            raise

    def form_invalid(self, form):
        logger.warning(
            f"Formulaire invalide - Erreurs: {form.errors.as_json()}"
        )
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors.get_json_data(),
                'message': 'Veuillez corriger les erreurs ci-dessous',
                'error_fields': list(form.errors.keys())
            }, status=400)
            
        return super().form_invalid(form)
class ModifierTacheView(LoginRequiredMixin, UpdateView):
    model = Tache
    form_class = TacheForm
    success_url = reverse_lazy('projets:liste_taches')
    queryset = Tache.objects.select_related('projet', 'responsable')

    def dispatch(self, request, *args, **kwargs):
        # Vérification des permissions avant même de traiter la requête
        if not request.user.has_perm('projets.change_tache'):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        logger.info(
            f"Modification tâche ID {self.object.id} - "
            f"User: {request.user} - Données: {request.POST.dict()}"
        )
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            self.object = form.save()
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'tache_id': self.object.id,
                    'message': 'Tâche mise à jour avec succès',
                    'changes': form.changed_data,  # Liste des champs modifiés
                    'new_data': {
                        'statut': 'Terminée' if self.object.terminee else 'En cours',
                        'avancement': f"{self.object.avancement}%"
                    }
                })
                
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Erreur modification tâche: {str(e)}")
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': 'Erreur serveur lors de la mise à jour'
                }, status=500)
            raise

    def form_invalid(self, form):
        logger.warning(
            f"Formulaire modification invalide - ID: {self.object.id} - "
            f"Erreurs: {form.errors.as_json()}"
        )
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'errors': form.errors.get_json_data(),
                'message': 'Veuillez corriger les erreurs ci-dessous',
                'error_fields': list(form.errors.keys())
            }, status=400)
            
        return super().form_invalid(form)
class DetailTacheView(DetailView):
    model = Tache
    queryset = Tache.objects.select_related('projet', 'responsable')
    # template_name = 'projets/taches/detail_tache'
    template_name = 'projets/taches/tache_details.html'
    context_object_name = 'tache'  # Important pour le template HTML

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        
        # Ajoutez des données supplémentaires pour le template HTML
        tache = self.object
        context['priorite_display'] = tache.get_priorite_display()
        context['est_en_retard'] = tache.date_fin and tache.date_fin < timezone.now().date() and not tache.terminee
        
        return context

    def render_to_json_response(self):
        """Sérialisation pour les requêtes AJAX seulement"""
        tache = self.object
        
        return JsonResponse({
            'success': True,
            'data': {
                'id': tache.id,
                'titre': tache.titre,
                'priorite': tache.priorite,
                'terminee': tache.terminee,
                'avancement': tache.avancement,
                'description': tache.description,
                'date_debut': tache.date_debut.isoformat() if tache.date_debut else None,
                'date_fin': tache.date_fin.isoformat() if tache.date_fin else None,
                'projet': {
                    'id': tache.projet.id if tache.projet else None,
                    'nom': tache.projet.nom if tache.projet else None
                },
                'responsable': {
                    'id': tache.responsable.id if tache.responsable else None,
                    'nom_complet': tache.responsable.get_full_name() if tache.responsable else None,
                    'username': tache.responsable.username if tache.responsable else None
                }
            }
        })

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        # Requête AJAX - retourne JSON
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                return self.render_to_json_response()
            except Exception as e:
                logger.error(f"Erreur détail tâche {self.object.id}: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': "Erreur lors du chargement des données"
                }, status=500)
        
        # Requête normale - retourne HTML
        return super().get(request, *args, **kwargs)
class SupprimerTacheView(LoginRequiredMixin, DeleteView):
    model = Tache
    success_url = reverse_lazy('projets:liste_taches')

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        
        try:
            self.object.delete()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Tâche supprimée avec succès'
                })
            return super().delete(request, *args, **kwargs)
            
        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': str(e)
                }, status=400)
            raise

#------------------ Gestion de la base de données ------------------
@chef_projet_required
def partial_ingenieurs(request):
    ingenieurs = Ingenieur.objects.all()
    return render(request, 'projets/partials/ingenieurs.html', {'ingenieurs': ingenieurs})
@chef_projet_required
def partial_entreprises(request):
    entreprises = Entreprise.objects.all()
    return render(request, 'projets/partials/entreprises.html', {'entreprises': entreprises})
@chef_projet_required
def partial_clients(request):
    clients = Client.objects.all()
    return render(request, 'projets/partials/clients.html', {'clients': clients})

@superuser_required
def base_donnees(request):
    return render(request, 'projets/base_donnees.html')

#------------------ Gestion d'un projet ------------------
@login_required
def dashboard_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    lots = projet.lots.all()
    mnt = 0
    for lot in lots:
       mnt += lot.montant_total_ttc
    mnt_txt = "{:,.2f}".format(mnt).replace(",", " ") if mnt else "0.00"
    
    # Données pour les décomptes
    decomptes = Decompte.objects.filter(attachement__projet=projet)
    total_decomptes = decomptes.count()
    decomptes_payes = decomptes.filter(statut='PAYE').count()
    decomptes_emis = decomptes.filter(statut='EMIS').count()
    decomptes_retard = decomptes.filter(statut='EN_RETARD').count()
    decomptes_recents = decomptes.order_by('-date_emission')[:5]  # 5 plus récents
    attachements = Attachement.objects.filter(projet=projet)
    context = {
        'projet': projet,
        'lots': lots,
        'montant_total': mnt_txt,
        'total_decomptes': total_decomptes,
        'decomptes_payes': decomptes_payes,
        'decomptes_emis': decomptes_emis,
        'decomptes_retard': decomptes_retard,
        'decomptes_recents': decomptes_recents,
        'attachements': attachements
    }
    
    return render(request, 'projets/dashboard.html', context)

#------------------ Gestion des bordereaux ------------------
@chef_projet_required
def saisie_bordereau(request, projet_id, lot_id):
    lot = get_object_or_404(LotProjet, id=lot_id, projet_id=projet_id)
    lot_root = lot.to_line_tree()
    # Création du JSON   
    data = [
        {
            'id': ligne.id,
            'numero': ligne.numero,
            'designation': ligne.designation,
            'unite': ligne.unite, # if not ligne.est_titre else '',
            'quantite': float(ligne.quantite), # if not ligne.est_titre else 0,
            'prix_unitaire': float(ligne.pu), # if not ligne.est_titre else 0,
            'montant': float(ligne.amount()),
            'niveau': ligne.level(), #) ligne.niveau,
            'est_titre': ligne.has_children(),  
            'parent_id': ligne.parent.id if ligne.parent else None,
            '_expanded': False,
        }
        for ligne in lot_root.get_descendants()
    ]
    
    json_str = json.dumps(data, ensure_ascii=False)
        
    return render(request, 'projets/lots/saisie_bordereau.html', {
        'lot': lot,
        'root': lot_root,
        'lignes': json_str,
    })

def indent_node(request, lot_id, node_id):
    """API pour indenter un node"""
    if request.method == 'POST':
        lot = get_object_or_404(LotProjet, id=lot_id)
        tree_manager = BordereauTreeManager(lot)
        success = tree_manager.indent_node(node_id)
        return JsonResponse({'success': success})
@login_required
def outdent_node(request, lot_id, node_id):
    """API pour outdenter un node"""
    if request.method == 'POST':
        lot = get_object_or_404(LotProjet, id=lot_id)
        tree_manager = BordereauTreeManager(lot)
        success = tree_manager.outdent_node(node_id)
        return JsonResponse({'success': success})

def toggle_node(request, lot_id, node_id):
    """API pour basculer un node"""
    if request.method == 'POST':
        lot = get_object_or_404(LotProjet, id=lot_id)
        tree_manager = BordereauTreeManager(lot)
        
        expanded = request.POST.get('expanded') == 'true'
        success = tree_manager.toggle_node(node_id, expanded)
        
        return JsonResponse({'success': success, 'expanded': expanded})

def get_children(request, lot_id, node_id):
    """API pour récupérer les enfants d'un node"""
    lot = get_object_or_404(LotProjet, id=lot_id)
    tree_manager = BordereauTreeManager(lot)
    
    children_ids = tree_manager.get_children_ids(node_id)
    return JsonResponse({'children': children_ids})
@chef_projet_required
def sauvegarder_lignes_bordereau(request, lot_id):
    if request.method == "POST":
        try:
            body = json.loads(request.body)

            lot = get_object_or_404(LotProjet, id=lot_id)
            
            # Récupérer les lignes existantes
            lignes_existantes = {ligne.id: ligne for ligne in LigneBordereau.objects.filter(lot=lot)}
            lignes_existantes_utilisees = set()
            
            lignes = {}
            for index, row in enumerate(body):
                ligne_id = row.get('id')
                if ligne_id and ligne_id in lignes_existantes:
                    # Mettre à jour une ligne existante
                    ligne = lignes_existantes[ligne_id]
                    ligne.numero = row.get('numero', '')
                    ligne.designation = row.get('designation', '')
                    ligne.unite = row.get('unite', '')
                    ligne.quantite = Decimal(str(row.get('quantite', 0)))
                    ligne.prix_unitaire = Decimal(str(row.get('prix_unitaire', 0)))
                    ligne.niveau = row.get('niveau', 0)
                    ligne.est_titre = row.get('est_titre', False)
                    ligne.ordre_affichage = index
                    ligne.montant_calcule = row.get('montant', 0)
                    
                    lignes_existantes_utilisees.add(ligne_id)
                    
                    lignes[ligne_id] = ligne
                else:
                    # Créer une nouvelle ligne
                    ligne = LigneBordereau(
                        lot=lot,
                        numero=row.get('numero', ''),
                        designation=row.get('designation', ''),
                        unite=row.get('unite', ''),
                        quantite=Decimal(str(row.get('quantite', 0))),
                        prix_unitaire=Decimal(str(row.get('prix_unitaire', 0))),
                        niveau=row.get('niveau', 0),
                        est_titre=row.get('est_titre', False),
                        ordre_affichage=index,
                        montant_calcule=row.get('montant', 0)
                    )
                    
                    lignes[ligne_id] = ligne
            try:
                # Gerer les relations parent-enfant et Enregistrer 
                for index, row in enumerate(body):
                    ligne_id = row.get('id')
                    parent_id = row.get('parent_id')    
                    ligne: LigneBordereau = lignes[ligne_id]
                    # Assigner le parent, None si aucun parent n'est trouvé (niveau 0)
                    ligne.parent = lignes[parent_id] if parent_id else None
                    # Enregistrer la ligne
                    ligne.save()
                # Supprimer les lignes non utilisées
                lignes_a_supprimer = set(lignes_existantes.keys()) - lignes_existantes_utilisees
                if lignes_a_supprimer:
                    LigneBordereau.objects.filter(id__in=lignes_a_supprimer).delete()
                
                return JsonResponse({'success': True, 
                                    'message': 'Lignes sauvegardées avec succès.', 
                                    'status': 'ok'})
            except Exception as e:
                print(e)
                return JsonResponse({'error': str(e)}, status=400)

        except Exception as e:
            import traceback
            return JsonResponse({
                'status': 'error',
                'message': f"Erreur lors de la sauvegarde: {str(e)}",
                'traceback': traceback.format_exc()
            }, status=500)

#------------------ Gestion des notifications ------------------
@login_required
def creer_notification(request):
    if request.method == 'POST':
        projet_id = request.POST.get('projet_id')
        type_notif = request.POST.get('type_notification')
        message = request.POST.get('message')
        
        try:
            projet = Projet.objects.get(id=projet_id)
            
            Notification.objects.create(
                utilisateur=request.user,
                projet=projet,
                type_notification=type_notif,
                titre=f"Notification manuelle - {projet.nom}",
                message=message,
                date_echeance=request.POST.get('date_echeance')
            )
            
            messages.success(request, _("Notification créée avec succès!"))
        except Projet.DoesNotExist:
            messages.error(request, _("Projet introuvable"))
        except Exception as e:
            messages.error(request, _(f"Erreur: {str(e)}"))
    
    return redirect('projets:liste_projets')
def liste_notifications(request):
    notifications = Notification.objects.filter(utilisateur=request.user).order_by('-date_creation')
    return render(request, 'projets/liste_notifications.html', {'notifications': notifications})
@login_required
def mark_notification_as_read(request, notification_id):
    notification = get_object_or_404(Notification, id=notification_id, utilisateur=request.user)
    notification.lue = True
    notification.save()
    return redirect('projets:liste_notifications')
def mark_all_notifications_as_read(request):
    Notification.objects.filter(utilisateur=request.user, lue=False).update(lue=True)
    return redirect('projets:liste_notifications')

#------------------ Gestion du profil ------------------

def serve_avatar(request, filename):
    """Vue personnalisée pour servir les avatars avec fallback"""
    avatar_path = os.path.join(settings.MEDIA_ROOT, 'avatars', filename)
    
    # Vérifier si le fichier existe
    if os.path.exists(avatar_path):
        with open(avatar_path, 'rb') as f:
            return HttpResponse(f.read(), content_type='image/jpeg')
    else:
        # Servir l'avatar par défaut
        default_avatar = os.path.join(settings.STATIC_ROOT, 'images', 'default.png')
        if os.path.exists(default_avatar):
            with open(default_avatar, 'rb') as f:
                return HttpResponse(f.read(), content_type='image/png')
        else:
            return HttpResponseNotFound('Avatar not found')
# Définition de la taille maximale (5 Mo en octets)
@login_required
def upload_avatar(request):
    """
    Gère la requête POST pour l'upload et la sauvegarde de l'avatar avec Cloudinary
    """
    if request.method == 'POST':
        avatar_file = request.FILES.get('avatar')
        if not avatar_file:
            response = HttpResponse(status=400)
            response['HX-Trigger'] = json.dumps({
                'showMessage': 'Veuillez sélectionner un fichier image à uploader.',
                'messageType': 'error'
            })
            return response
            
        if avatar_file.size > MAX_UPLOAD_SIZE:
            max_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
            error_msg = f"La taille du fichier ({avatar_file.size / (1024 * 1024):.2f} Mo) dépasse la limite autorisée de {max_mb:.0f} Mo."
            response = HttpResponse(status=400)
            response['HX-Trigger'] = json.dumps({
                'showMessage': error_msg,
                'messageType': 'error'
            })
            return response
            
        try:
            profile = request.user.profile
            
            # Gestion Cloudinary vs stockage local
            if getattr(settings, 'USE_CLOUDINARY', False):
                # Upload vers Cloudinary
                upload_result = cloudinary.uploader.upload(
                    avatar_file,
                    folder="avatars",
                    transformation=[
                        {'width': 300, 'height': 300, 'crop': 'fill', 'gravity': 'face'}
                    ]
                )
                profile.avatar = upload_result['public_id']
            else:
                # Stockage local classique
                profile.avatar = avatar_file
                
            profile.save()
            
            # ✅ SUCCÈS : Renvoyer 200 avec les triggers
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                'avatarUpdated': True,
                'closeModal': True,
                'showMessage': 'Photo de profil mise à jour avec succès !',
                'messageType': 'success'
            })
            return response
            
        except Exception as e:
            response = HttpResponse(status=500)
            response['HX-Trigger'] = json.dumps({
                'showMessage': f"Une erreur s'est produite lors de l'upload : {str(e)}",
                'messageType': 'error'
            })
            return response

    return redirect('home')

@login_required
def avatar_upload_modal(request):
    """Retourne la modal d'upload d'avatar (réponse GET pour HTMX)."""
    context = {
        'user': request.user
    }
    return render(request, 'projets/modals/avatar_upload_modal.html', context)

from .forms import AvatarUpdateForm
@login_required
def profile_view(request):
    profile = request.user.profile
    
    if request.method == 'POST':
        form = AvatarUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Votre avatar a été mis à jour!')
            return redirect('profile')
    else:
        form = AvatarUpdateForm(instance=profile)
    
    return render(request, 'profile.html', {'form': form, 'profile': profile})

@login_required
def profile_update(request):
    if request.method == 'POST':
        try:
            user = request.user
            profile = user.profile
            
            # Mise à jour de l'avatar
            if 'avatar' in request.FILES:
                if request.FILES['avatar'].size > 5*1024*1024:  # 5MB max
                    return HttpResponseBadRequest("L'image ne doit pas dépasser 5MB")
                profile.avatar = request.FILES['avatar']
                profile.save()
            
            # Mise à jour des autres champs
            user.email = request.POST.get('email', user.email)
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.save()
            
            return HttpResponse(
                status=204,
                headers={
                    'HX-Trigger': json.dumps({
                        'profileUpdated': True,
                        'closeModal': True,
                        'showMessage': 'Profil mis à jour avec succès'
                    })
                }
            )

        except Exception as e:
            return HttpResponseBadRequest(f"Erreur: {str(e)}")
    
    return HttpResponseBadRequest("Méthode non autorisée")

def profile_modal(request):
    return render(request, 'projets/modals/profile_modal.html', {
        'user': request.user
    })

@login_required
def password_modal(request):
    return render(request, 'projets/modals/password_modal.html')
@login_required
def password_change(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            try:
                user = form.save()
                update_session_auth_hash(request, user)
                logger.info(f"Password changed for {user.username}")
                return redirect('home')
            except Exception as e:
                logger.error(f"Password change failed for {request.user.username}: {str(e)}")
                messages.error(request, "Erreur lors du changement de mot de passe")
    else:
        form = PasswordChangeForm(request.user)
    
    return render(request, 'projets/password_change.html', {'form': form})

#------------------ Gestion du calendrier ------------------
def partial_calendiers(request):
    date_debut = date.today()
    date_fin = date_debut + timedelta(days=30)
    
    echeances = Projet.objects.filter(
        Q(date_limite_soumission__range=[date_debut, date_fin]) |
        Q(date_reception__range=[date_debut, date_fin])
    ).order_by('date_limite_soumission')
    
    context = {
        'echeances': echeances,
        'aujourdhui': date_debut.strftime("%Y-%m-%d"),
    }
    return render(request, 'projets/partials/calendrier.html', context)

# ------  Ingenieurs ------
@permission_required('auth.add_user')
def ajouter_ingenieur(request):
    if request.method == 'POST':
        form = IngenieurForm(request.POST)
        if form.is_valid():
            ingenieur = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Réponse JSON pour les requêtes AJAX
                return JsonResponse({
                    'success': True,
                    'message': 'L\'ingenieur ' + ingenieur.nom + ' ajouté avec succès'
                })
            else:
                return redirect('projets:partial_ingenieurs')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Retourner les erreurs de formulaire pour AJAX
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    else:
        form = IngenieurForm()
    
    # Pour les requêtes non-AJAX, retourner le template normal
    return render(request, 'projets/partials/ingenieurs.html', {'form': form})
    # Ajoutez du debug temporaire
@permission_required('auth.add_user')
def modifier_ingenieur(request, ingenieur_id):
    ingenieur = get_object_or_404(Ingenieur, id=ingenieur_id)
    
    if request.method == 'POST':
        form = IngenieurForm(request.POST, instance=ingenieur)
        
        if form.is_valid():
            ingenieur = form.save()            
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Ingénieur ' + ingenieur.nom + ' modifié avec succès'})
        else:
            if request.GET.get('modal') == 'true':
                return JsonResponse({
                    'success': False, 
                    'errors': form.errors.get_json_data()
                }, status=400)
    
    return JsonResponse({'error': 'Méthode non supportée'}, status=400)
@permission_required('auth.add_user')
def supprimer_ingenieur(request, ingenieur_id):
    ingenieur = get_object_or_404(Ingenieur, id=ingenieur_id)
    ingenieur.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Ingénieur " + ingenieur.nom + " supprimé avec succès."})

    messages.success(request, "Ingénieur supprimé avec succès.")
    return redirect("projets:partial_ingenieurs")

# -------- Clients --------
def ajouter_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Réponse JSON pour les requêtes AJAX
                return JsonResponse({
                    'success': True,
                    'message': 'Le client ' + client.nom + ' ajouté avec succès'
                })
            else:
                return redirect('projets:partial_clients')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Retourner les erreurs de formulaire pour AJAX
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    else:
        form = ClientForm()
    
    # Pour les requêtes non-AJAX, retourner le template normal
    return render(request, 'projets/partials/clients.html', {'form': form})
def modifier_client(request, client_id):
    client = Client.objects.get(id=client_id)
    
    if request.method == "POST":
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            # Si c'est une requête AJAX (via le paramètre ?modal=true), on retourne une réponse JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Le client ' + client.nom + ' modifié avec succès'
                })
            else:
                return redirect('projets:partial_clients')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    else:
        form = ClientForm(instance=client)
    # Pour les requêtes non-AJAX
    return render(request, "projets/partials/clients.html", {"form": form})
def supprimer_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": 'Client ' + client.nom + ' supprimé avec succès.'})

    messages.success(request, "Client supprimé avec succès.")
    return redirect("projets:partial_clients")

# -------- Entreprises --------
def ajouter_entreprise(request):
    if request.method == 'POST':
        form = EntrepriseForm(request.POST)
        if form.is_valid():
            entreprise = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Réponse JSON pour les requêtes AJAX
                return JsonResponse({
                    'success': True,
                    'message': 'Entreprise ' + entreprise.nom + ' ajoutée avec succès'
                })
            else:
                return redirect('projets:partial_entreprises')
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Retourner les erreurs de formulaire pour AJAX
                return JsonResponse({
                    'success': False,
                    'errors': form.errors
                })
    else:
        form = EntrepriseForm()
    return render(request, 'projets/partials/entreprises.html', {
        'form': form, 
        'entreprise': entreprise
    })
def modifier_entreprise(request, entreprise_id):
    entreprise = get_object_or_404(Entreprise, id=entreprise_id)
    
    if request.method == 'POST':
        form = EntrepriseForm(request.POST, instance=entreprise)
        
        if form.is_valid():
            entreprise = form.save()
            
            # REQUÊTE AJAX
            if request.GET.get('modal') == 'true':
                return JsonResponse({
                    'success': True,
                    'message': f'Entreprise {entreprise.nom} modifiée avec succès'
                })
            
            # REQUÊTE NORMALE  
            messages.success(request, f'Entreprise {entreprise.nom} modifiée avec succès')
            return redirect('projets:partial_entreprises')
        
        # FORMULAIRE INVALIDE - AJAX
        elif request.GET.get('modal') == 'true':
            # Convertir les erreurs en format JSON
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            
            return JsonResponse({
                'success': False,
                'errors': errors
            }, status=400)
    
    # METHODE GET
    else:
        form = EntrepriseForm(instance=entreprise)
    
    return render(request, 'projets/partials/entreprises.html', {
        'form': form, 
        'entreprise': entreprise
    })
def supprimer_entreprise(request, entreprise_id):
    entreprise = get_object_or_404(Entreprise, id=entreprise_id)
    entreprise.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse(
            {"success": True,
             "message": 'Entreprise' + entreprise.nom + ' supprimée avec succès.'
             })

    messages.success(request, "Entreprise supprimé avec succès.")
    return redirect("projets:partial_entreprises")

# ------  Lots ------
def modifier_lot(request, projet_id, lot_id):
    lot = get_object_or_404(LotProjet, id=lot_id, projet_id=projet_id)
    
    if request.method == "POST":
        nouveau_nom = request.POST.get("nom", "").strip()
        
        # Validation simple
        if not nouveau_nom:
            messages.error(request, "Le nom du lot ne peut pas être vide")
        else:
            lot.nom = nouveau_nom
            lot.save()
            messages.success(request, "Le nom du lot a été mis à jour avec succès")
            return redirect('projets:lots_projet', projet_id=projet_id)
    
    context = {
        'lot': lot,
        'projet_id': projet_id,
    }
    return render(request, 'projets/lots/modifier_lot.html', context)
def supprimer_lot(request, projet_id, lot_id):
    lot = get_object_or_404(LotProjet, id=lot_id, projet_id=projet_id)
    lot.delete()
    return redirect('projets:lots_projet', projet_id=projet_id)
def lots_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)

    if request.method == "POST":
        nom_lot = request.POST.get("nom")
        if nom_lot:
            LotProjet.objects.create(projet=projet, nom=nom_lot)

        return redirect('projets:lots_projet', projet_id=projet_id)
    lots = LotProjet.objects.filter(projet=projet).order_by('id')
    # lots = projet.lots.all().order_by('id')
    return render(request, 'projets/lots/lots_projet.html', {'projet': projet, 'lots': lots})    

# ------  Documents et Suivi ------
def documents_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    documents = projet.documents_administratifs.all()
    return render(request, 'projets/documents_administratifs.html', {'projet': projet, 'documents': documents})
def supprimer_document(request, projet_id, document_id):
    if request.method == 'POST':
        document = get_object_or_404(DocumentAdministratif, id=document_id, projet_id=projet_id)
        nom_document = document.type_document
        
        try:
            document.delete()  # Cela supprimera aussi le fichier physique
            messages.success(request, f"Le document '{nom_document}' a été supprimé avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression du document: {str(e)}")
        
        return redirect('projets:documents', projet_id=projet_id)
    
    # Si ce n'est pas une requête POST, rediriger
    return redirect('projets:documents', projet_id=projet_id)
def telecharger_document(request, document_id):
    document = get_object_or_404(DocumentAdministratif, id=document_id)
    return secure_download(request, 'DocumentAdministratif', document_id)

    file_path = document.fichier.path
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=False)
    else:
        raise Http404("Le document n'existe pas")

def ajouter_document(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    
    if request.method == 'POST':
        type_document = request.POST.get('type_document')
        date_remise = request.POST.get('date_remise')
        fichier = request.FILES.get('fichier')
        
        # Validation basique
        if not type_document or not fichier:
            messages.error(request, "Le type de document et le fichier sont obligatoires.")
            return redirect('projets:documents', projet_id=projet_id)
        
        # Vérifier la taille du fichier (max 20MB)
        if fichier.size > 20 * 1024 * 1024:
            messages.error(request, "Le fichier ne doit pas dépasser 20MB.")
            return redirect('projets:documents', projet_id=projet_id)
        
        # Créer le document
        try:
            document = DocumentAdministratif(
                projet=projet,
                type_document=type_document,
                date_remise=date_remise if date_remise else None,
            )
            
            # Gestion Cloudinary vs local
            if getattr(settings, 'USE_CLOUDINARY', False):
                # Upload vers Cloudinary
                upload_result = cloudinary.uploader.upload(
                    fichier,
                    folder="documents_administratifs",
                    resource_type="raw"
                )
                document.fichier = upload_result['public_id']
            else:
                # Stockage local
                document.fichier = fichier
                
            document.save()
            
            messages.success(request, f"Le document '{type_document}' a été ajouté avec succès.")
        except Exception as e:
            messages.error(request, f"Une erreur s'est produite lors de l'ajout du document: {str(e)}")
        
        return redirect('projets:documents', projet_id=projet_id)
    
    return redirect('projets:documents', projet_id=projet_id)

import requests

class AfficherDocumentView(View):
    """Vue avec téléchargement direct depuis Cloudinary"""
    
    def get(self, request, document_id):
        try:
            res = secure_download(request, 'DocumentAdministratif', document_id)
            return res
        
        
        
            document = get_object_or_404(DocumentAdministratif, id=document_id)
            projet = document.projet
            if getattr(settings, 'USE_CLOUDINARY', False):
                # 🔥 TÉLÉCHARGEMENT DIRECT
                if hasattr(document.fichier, 'url') or isinstance(document.fichier, str):
                    
                    # Récupérer l'URL Cloudinary
                    if hasattr(document.fichier, 'url'):
                        file_url = document.fichier.url
                    else:
                        from cloudinary import CloudinaryResource
                        resource = CloudinaryResource(str(document.fichier))
                        file_url = resource.build_url(resource_type="raw", sign_url=True)
                                        
                    # Télécharger le fichier depuis Cloudinary
                    response = requests.get(file_url, stream=True)

                    if response.status_code == 200:
                        # Créer la réponse Django avec le contenu
                        django_response = HttpResponse(
                            response.content,
                            content_type=response.headers.get('content-type', 'application/octet-stream'))
                        
                        # Nom du fichier pour le téléchargement
                        filename = f"{document.type_document}.pdf"
                        django_response['Content-Disposition'] = f'inline; filename="{filename}"'
                        
                        return django_response
                    else:
                        print(f"❌ Erreur téléchargement Cloudinary: {response.status_code}")
                        raise Http404("Erreur de téléchargement")
            
            raise Http404("Document non accessible")
            
        except Exception as e:
            print(f"❌ Erreur: {e}")
            raise Http404("Erreur lors du chargement du document")
            
#----------------------- Suivi d'exécution ---------------------------
def suivi_execution(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    suivis = projet.suivis_execution.all()

    return render(request, 'projets/suivi/suivi_execution.html', {
        'projet': projet,
        'suivis': suivis
    })
def ajouter_suivi(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    
    if request.method == 'POST':
        # Créer le suivi
        suivi = SuiviExecution(
            projet=projet,
            date=request.POST.get('date'),
            titre=request.POST.get('titre'),
            type_suivi=request.POST.get('type_suivi'),
            commentaire=request.POST.get('commentaire'),
            redacteur=request.POST.get('redacteur'),
            importance=request.POST.get('importance', 'moyenne')
        )
        suivi.save()
        
        # Gérer les fichiers joints
        if request.FILES.getlist('fichiers'):
            for i, fichier in enumerate(request.FILES.getlist('fichiers')):
                description = request.POST.get(f'description_{i}', '')
                fichier_suivi = FichierSuivi(
                    suivi=suivi,
                    fichier=fichier,
                    description=description
                )
                fichier_suivi.save()
        
        messages.success(request, "Le suivi a été ajouté avec succès.")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    return redirect('projets:suivi_execution', projet_id=projet_id)
def supprimer_suivi(request, projet_id, suivi_id):
    if request.method == 'POST':
        suivi = get_object_or_404(SuiviExecution, id=suivi_id, projet_id=projet_id)
        suivi.delete()
        messages.success(request, "Le suivi a été supprimé avec succès.")
    
    return redirect('projets:suivi_execution', projet_id=projet_id)
def modifier_suivi(request, projet_id, suivi_id):
    """
    Vue pour modifier un suivi d'exécution existant
    """
    projet = get_object_or_404(Projet, id=projet_id)
    suivi = get_object_or_404(SuiviExecution, id=suivi_id, projet=projet)
    
    if request.method == 'POST':
        try:
            suivi.date = request.POST.get('date', suivi.date)
            suivi.titre = request.POST.get('titre', suivi.titre)
            suivi.type_suivi = request.POST.get('type_suivi', suivi.type_suivi)
            suivi.commentaire = request.POST.get('commentaire', suivi.commentaire)
            suivi.redacteur = request.POST.get('redacteur', suivi.redacteur)
            suivi.importance = request.POST.get('importance', suivi.importance)
            suivi.save()
            
            messages.success(request, "Le suivi a été modifié avec succès.")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la modification du suivi: {str(e)}")
        
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    # Méthode GET - Afficher le formulaire de modification
    context = {
        'projet': projet,
        'suivi': suivi,
    }
    return render(request, 'projets/suivi/modifier_suivi.html', context)
def afficher_fichier_suivi(request, fichier_id):
    """
    Vue pour afficher/télécharger un fichier de suivi
    NOTE: Nous avons retiré projet_id car il n'est pas nécessaire pour récupérer le fichier
    """
    fichier_suivi = get_object_or_404(FichierSuivi, id=fichier_id)
        
    # Vérifier que le fichier existe physiquement
    if not fichier_suivi.fichier or not os.path.exists(fichier_suivi.fichier.path):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'error': 'Fichier introuvable'})
        messages.error(request, "Le fichier demandé est introuvable.")
        return redirect('projets:suivi_execution', projet_id=fichier_suivi.suivi.projet.id)
    
    # Déterminer si on doit afficher dans le navigateur ou forcer le téléchargement
    extension = os.path.splitext(fichier_suivi.fichier.name)[1].lower()
    viewable_types = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.txt', '.csv', '.html', '.htm'}
    
    try:
        file_data = open(fichier_suivi.fichier.path, 'rb').read()
    except IOError:
        messages.error(request, "Impossible d'ouvrir le fichier.")
        return redirect('projets:suivi_execution', projet_id=fichier_suivi.suivi.projet.id)
    
    if extension in viewable_types:
        # Afficher dans le navigateur
        if extension == '.pdf':
            response = HttpResponse(file_data, content_type='application/pdf')
        elif extension in {'.jpg', '.jpeg'}:
            response = HttpResponse(file_data, content_type='image/jpeg')
        elif extension == '.png':
            response = HttpResponse(file_data, content_type='image/png')
        elif extension == '.gif':
            response = HttpResponse(file_data, content_type='image/gif')
        elif extension in {'.txt', '.csv'}:
            response = HttpResponse(file_data, content_type='text/plain; charset=utf-8')
        elif extension in {'.html', '.htm'}:
            response = HttpResponse(file_data, content_type='text/html; charset=utf-8')
        else:
            response = HttpResponse(file_data, content_type='application/octet-stream')
        
        response['Content-Disposition'] = f'inline; filename="{os.path.basename(fichier_suivi.fichier.name)}"'
    else:
        # Forcer le téléchargement
        response = HttpResponse(file_data, content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(fichier_suivi.fichier.name)}"'
    
    return response
def supprimer_fichier_suivi(request, projet_id, fichier_id):
    if request.method == 'POST':
        fichier = get_object_or_404(FichierSuivi, id=fichier_id)
        fichier.delete()
        messages.success(request, "Le fichier a été supprimé avec succès.")
    
    return redirect('projets:suivi_execution', projet_id=projet_id)
def telecharger_fichier_suivi(request, fichier_id):
    fichier = get_object_or_404(FichierSuivi, id=fichier_id)
    return secure_download(request, 'FichierSuivi', fichier_id)

    file_path = fichier.fichier.path
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=False)
    else:
        raise Http404("Le fichier n'existe pas")
def ajouter_fichier_suivi(request, projet_id, suivi_id):
    """
    Vue pour ajouter des fichiers à un suivi d'exécution existant avec Cloudinary
    """
    projet = get_object_or_404(Projet, id=projet_id)
    suivi = get_object_or_404(SuiviExecution, id=suivi_id, projet=projet)
    
    if request.method == 'POST':
        fichiers = request.FILES.getlist('fichiers')
        descriptions = request.POST.getlist('descriptions[]')
        
        if not fichiers:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Aucun fichier sélectionné'})
            messages.error(request, "Aucun fichier sélectionné.")
            return redirect('projets:suivi_execution', projet_id=projet_id)
        
        fichiers_ajoutes = []
        
        for i, fichier in enumerate(fichiers):
            # Vérifier la taille du fichier (max 20MB)
            if fichier.size > 20 * 1024 * 1024:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': f"Le fichier {fichier.name} dépasse la taille maximale de 20MB"
                    })
                messages.error(request, f"Le fichier {fichier.name} dépasse la taille maximale de 20MB.")
                continue
            
            # Utiliser la description correspondante si disponible
            description = descriptions[i] if i < len(descriptions) else ''
            
            try:
                fichier_suivi = FichierSuivi(
                    suivi=suivi,
                    description=description
                )
                
                # Gestion Cloudinary vs local
                if getattr(settings, 'USE_CLOUDINARY', False):
                    upload_result = cloudinary.uploader.upload(
                        fichier,
                        folder="suivis_execution",
                        resource_type="raw"
                    )
                    fichier_suivi.fichier = upload_result['public_id']
                else:
                    fichier_suivi.fichier = fichier
                    
                fichier_suivi.save()
                fichiers_ajoutes.append(fichier_suivi.fichier.name)
                
            except Exception as e:
                error_msg = f"Erreur lors de l'ajout du fichier {fichier.name}: {str(e)}"
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': False, 'error': error_msg})
                messages.error(request, error_msg)
        
        if fichiers_ajoutes:
            success_msg = f"{len(fichiers_ajoutes)} fichier(s) ajouté(s) avec succès."
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True, 
                    'message': success_msg,
                    'fichiers': fichiers_ajoutes
                })
            messages.success(request, success_msg)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Aucun fichier n\'a pu être ajouté'})
            messages.error(request, "Aucun fichier n'a pu être ajouté.")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'redirect': False})
        
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    # Si méthode GET, afficher le formulaire d'ajout de fichiers
    context = {
        'projet': projet,
        'suivi': suivi,
    }
    return render(request, 'projets/suivi/ajouter_fichier_suivi.html', context)

# ------------------------ Views pour Attachements ------------------------
@login_required
def liste_attachements(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    attachements = Attachement.objects.filter(projet=projet).order_by('id')
    
    context = {
        'projet': projet,
        'attachements': attachements,
        # 'USE_CLOUDINARY': getattr(settings, 'USE_CLOUDINARY', False),
    }
    return render(request, 'projets/decomptes/liste_attachements.html', context)
@login_required
def ajouter_attachement(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    
    # Récupérer toutes les lignes de bordereau du projet
    lignes_bordereau = LigneBordereau.objects.filter(
        lot__projet=projet
    ).select_related('lot').order_by('lot__id', 'id')

    if request.method == 'POST':
        form = AttachementForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                attachement = form.save(commit=False)
                attachement.projet = projet
                # Gestion du fichier avec Cloudinary
                fichier = request.FILES.get('fichier')
                if fichier and getattr(settings, 'USE_CLOUDINARY', False):
                    upload_result = cloudinary.uploader.upload(
                        fichier,
                        folder="attachements",
                        resource_type="raw"
                    )
                    attachement.fichier = upload_result['public_id']
                
                attachement.save()
                
                lignes_data_json = request.POST.get('lignes_attachement')
                if lignes_data_json:
                    lignes_data = json.loads(lignes_data_json)
                    
                    # Retirer les titres de la fin
                    while lignes_data and lignes_data[-1].get('is_title'):
                        lignes_data.pop()
                        
                    for ligne_data in lignes_data:
                        # Convertir en Decimal pour éviter les problèmes de type
                        quantite_realisee = Decimal(str(ligne_data.get('quantite_realisee', 0)))
                        ligne_bordereau_id = ligne_data['id']
                        ligne_bordereau = LigneBordereau.objects.get(id=ligne_bordereau_id)
                        
                        is_title = ligne_bordereau.is_title
                        
                        # SAUVEGARDER TOUTES LES LIGNES (titres inclus)
                        if quantite_realisee > 0 or is_title:
                            quantite_cumulee = quantite_realisee

                            LigneAttachement.objects.create(
                                attachement=attachement,
                                ligne_lot=ligne_bordereau,
                                numero=ligne_bordereau.numero,
                                designation=ligne_bordereau.designation,
                                unite=ligne_bordereau.unite,
                                prix_unitaire=ligne_bordereau.prix_unitaire,
                                quantite_initiale=ligne_bordereau.quantite,
                                quantite_realisee=quantite_realisee if not is_title else Decimal('0'),
                                quantite_cumulee=quantite_cumulee,
                            )
                
                messages.success(request, "Attachement créé avec succès !")
                return redirect('projets:liste_attachements', projet_id=projet.id)
                
            except Exception as e:
                messages.error(request, f"Erreur lors de la création : {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    
    else:           
        form = AttachementForm(initial={
            'statut': 'BROUILLON',            
        })
    
    # Préparer les données pour Handsontable (GET)
    lignes_data = []
    
    for ligne in lignes_bordereau:
        if not ligne.is_title:
            quantite_deja_realisee = ligne.get_quantite_deja_realisee
        else:
            quantite_deja_realisee = None

        # Ajouter la ligne aux données pour Handsontable
        ligne_dict = {
            'id': ligne.id,
            'parent_id': ligne.parent.id if ligne.parent else None,
            'numero': ligne.numero,
            'niveau': ligne.niveau,
            'designation': ligne.designation,
            'unite': ligne.unite,
            'is_title': ligne.is_title,
            'est_titre': ligne.est_titre,
        }
        
        if not ligne.is_title:
            # Convertir les Decimal en float pour JavaScript
            ligne_dict.update({
                'quantite_prevue': float(ligne.quantite) if ligne.quantite is not None else 0.0,
                'prix_unitaire': float(ligne.prix_unitaire) if ligne.prix_unitaire is not None else 0.0,
                'quantite_deja_realisee': float(quantite_deja_realisee) if quantite_deja_realisee is not None else 0.0,
                'quantite_realisee': float(quantite_deja_realisee) if quantite_deja_realisee is not None else 0.0,
                'montant': 0.0,
            })
        else:
            ligne_dict.update({
                'quantite_prevue': None,
                'prix_unitaire': None,
                'quantite_deja_realisee': None,
                'quantite_realisee': None,
                'montant': None,
            })
        
        lignes_data.append(ligne_dict)

    # Convertir la liste de dictionnaires en JSON pour le template
    lignes_json = json.dumps(lignes_data, default=str)
    
    # Calcul du prochain numéro et dates
    nb_attachements = Attachement.objects.filter(projet=projet).count()
    next_numero = nb_attachements + 1
    date_fin_periode = timezone.now().date()
    
    if next_numero == 1:
        # SI C'est le premier attachement, la date de debut de la periode est la date de OSC si elle existe, sinon aujourd'hui
        osc = projet.ordres_service.filter(type_os__code='OSC', statut='NOTIFIE').first()
        if osc and osc.date_effet:
            date_debut_periode = osc.date_effet
        else:
            date_debut_periode = timezone.now().date()
    else:
        dernier_attachement = Attachement.objects.filter(projet=projet).latest('date_etablissement')
        # La date de debut de la periode est la date de fin du dernier attachement
        date_debut_periode = dernier_attachement.date_fin_periode
        # La date de fin de la periode est la date de debut de la periode + 30 jours
    date_fin_periode = date_debut_periode + timedelta(days=30)
    
    context = {
        'projet': projet,
        'form': form,
        'lignes': lignes_json,
        'total_lignes': lignes_bordereau.count(),
        'date_etablissement': date_fin_periode,
        'numero': 'DP' + str(next_numero).zfill(2),
        'date_debut_periode': date_debut_periode,
        'date_fin_periode': date_fin_periode,
        'is_edition': False
    }
    return render(request, 'projets/decomptes/attachement_form.html', context)
@login_required
def modifier_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    projet = attachement.projet
    
    # Récupérer toutes les lignes de bordereau du projet
    lignes_bordereau = LigneBordereau.objects.filter(
        lot__projet=projet
    ).select_related('lot').order_by('lot__id', 'id')

    if request.method == 'POST':
        form = AttachementForm(request.POST, request.FILES, instance=attachement)
        if form.is_valid():
            try:
                attachement = form.save(commit=False)
                attachement.save()
                
                # Supprimer les anciennes lignes de cet attachement
                LigneAttachement.objects.filter(attachement=attachement).delete()
                
                lignes_data_json = request.POST.get('lignes_attachement')
                if lignes_data_json:
                    lignes_data = json.loads(lignes_data_json)
                    
                    # Retirer les titres de la fin (lignes orphelines)
                    while lignes_data and lignes_data[-1].get('is_title'):
                        lignes_data.pop()
                        
                    for ligne_data in lignes_data:
                        # Convertir en Decimal pour éviter les problèmes de type
                        quantite_realisee = Decimal(str(ligne_data.get('quantite_realisee', 0)))
                        
                        ligne_bordereau_id = ligne_data['id']
                        ligne_bordereau = LigneBordereau.objects.get(id=ligne_bordereau_id)
                        
                        is_title = ligne_bordereau.is_title
                        
                        # SAUVEGARDER TOUTES LES LIGNES (titres inclus)
                        if quantite_realisee > 0 or is_title:
                            quantite_cumulee = quantite_realisee

                            LigneAttachement.objects.create(
                                attachement=attachement,
                                ligne_lot=ligne_bordereau,
                                numero=ligne_bordereau.numero,
                                designation=ligne_bordereau.designation,
                                unite=ligne_bordereau.unite,
                                prix_unitaire=ligne_bordereau.prix_unitaire,
                                quantite_initiale=ligne_bordereau.quantite,
                                quantite_realisee=quantite_realisee if not is_title else Decimal('0'),
                                quantite_cumulee=quantite_cumulee,
                            )
                
                messages.success(request, "Attachement modifié avec succès !")
                return redirect('projets:liste_attachements', projet_id=projet.id)
                
            except Exception as e:
                messages.error(request, f"Erreur lors de la modification : {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AttachementForm(instance=attachement)
    
    lignes_data = []
    # recuperer l'attachement qui un id avant attachement_id
    attachement_avant = attachement.get_previous_attachement()
    # if attachement_avant is not None: 
    #     print("date de fin de l'attachement avant : ", attachement_avant.date_fin_periode)
    # else:
    #     print("pas d'attachement avant")
    for ligne in lignes_bordereau:
        ligne_att_avant = LigneAttachement.objects.filter(attachement=attachement_avant, ligne_lot=ligne).first()
        ligne_cet_att = LigneAttachement.objects.filter(attachement=attachement, ligne_lot=ligne).first()
        if ligne.is_title:
            quantite_realisee_attachement_avant = None
            quantite_realisee = None
        else:
            quantite_realisee = ligne_cet_att.quantite_realisee if ligne_cet_att else None
            quantite_realisee_attachement_avant = ligne_att_avant.quantite_realisee if ligne_att_avant else None
        
        # Ajouter la ligne aux données pour Handsontable
        ligne_dict = {
            'id': ligne.id,
            'parent_id': ligne.parent.id if ligne.parent else None,
            'numero': ligne.numero,
            'niveau': ligne.niveau,
            'designation': ligne.designation,
            'unite': ligne.unite,
            'is_title': ligne.is_title,
            'est_titre': ligne.est_titre
        }
        
        if not ligne.is_title:
            # Convertir les Decimal en float pour JavaScript
            ligne_dict.update({
                'quantite_prevue': float(ligne.quantite) if ligne.quantite is not None else 0.0,
                'prix_unitaire': float(ligne.prix_unitaire) if ligne.prix_unitaire is not None else 0.0,
                'quantite_deja_realisee': float(quantite_realisee_attachement_avant) if quantite_realisee_attachement_avant is not None else 0.0,
                'quantite_realisee': float(quantite_realisee) if quantite_realisee is not None else 0.0,
                'montant': 0.0,
            })
        else:
            ligne_dict.update({
                'quantite_prevue': None,
                'prix_unitaire': None,
                'quantite_deja_realisee': None,
                'quantite_realisee': None,
                'montant': None,
            })
        
        lignes_data.append(ligne_dict)

    # Convertir la liste de dictionnaires en JSON pour le template
    lignes_json = json.dumps(lignes_data, default=str)
            
    # Supprimer les dernières lignes qui sont is_title
    while lignes_data and lignes_data[-1]['is_title']:
        lignes_data.pop()
    
    # Convertir la liste de dictionnaires en JSON pour le template
    lignes_json = json.dumps(lignes_data, default=str)
    
    # Création d'attributs dynamiques pour le template
    attachement.peut_reouvrir = (attachement.statut == 'VALIDE' and (request.user.is_superuser or request.user.is_staff))
    attachement.peut_supprimer = attachement.statut != 'VALIDE'
    attachement.est_validable = attachement.statut in ['BROUILLON', 'TRANSMIS']
    attachement.ferme = attachement.statut == 'SIGNE'
    
    # Création de variables de contexte
    context = {
        'projet': projet,
        'attachement': attachement,
        'form': form,
        'lignes': lignes_json,
        'total_lignes': lignes_bordereau.count(),
        'total_attachement': float(0.0),  # Convertir pour le template
        'is_edition': True
    }
    return render(request, 'projets/decomptes/attachement_form.html', context)
@login_required
def detail_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    
    # Récupérer tous les lots du projet
    lots = LotProjet.objects.filter(projet=attachement.projet).order_by('id')
    lots_data = []
    montant_total = 0
    total_lignes = 0
    
    for lot in lots:
        # Récupérer les lignes d'attachement pour ce lot
        lignes = LigneAttachement.objects.filter(attachement=attachement, ligne_lot__lot=lot).order_by('id')
        # Calculer le total du lot
        total_lot = sum(
            (ligne.quantite_realisee or 0) * (ligne.prix_unitaire or 0) 
            for ligne in lignes
        )
        
        # Préparer les données des lignes avec le montant calculé
        lignes_data = []
        for ligne in lignes:
            montant_ligne = (ligne.quantite_realisee or 0) * (ligne.prix_unitaire or 0)
            lignes_data.append({
                'numero': ligne.numero,
                'designation': ligne.designation,
                'unite': ligne.unite,
                'quantite_realisee': ligne.quantite_realisee if not ligne.is_title else None,
                'prix_unitaire': ligne.prix_unitaire if not ligne.is_title else None,
                'montant': montant_ligne if not ligne.is_title else None,
                'is_title': ligne.is_title,
            })
        while lignes_data and lignes_data[-1]['is_title']:
            lignes_data.pop() # Retirer les titres de la fin
        lots_data.append({
            'lot': lot,
            'lignes': lignes_data,
            'total_lot': total_lot
        })
        
        montant_total += total_lot
        total_lignes += len(lignes)
    
    context = {
        'attachement': attachement,
        'lots_data': lots_data,
        'montant_total': montant_total,
        'total_lots': len(lots),
        'total_lignes': total_lignes,
    }
    
    return render(request, 'projets/decomptes/detail_attachement.html', context)
@login_required
def supprimer_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    projet_id = attachement.projet.id
    
    if request.method == 'POST':
        try:
            numero = attachement.numero
            count_lignes = attachement.lignes_attachement.count()  
            attachement.delete()
            messages.success(request, f"✅ Attachement {numero} supprimé avec succès! ({count_lignes} lignes supprimées)")
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de la suppression : {str(e)}")
        
        return redirect('projets:liste_attachements', projet_id=projet_id)
    
    # GET request
    count_lignes = attachement.lignes_attachement.count()  # ✅ Même chose pour GET
    return render(request, 'projets/decomptes/supprimer_attachement.html', {
        'attachement': attachement,
        'count_lignes': count_lignes
    })
def attachements_ajouter_decompte(request, attachement_id):
    """Vue pour l'ajout d'un décompte (redirige vers liste_decomptes avec formulaire ouvert)"""
    attachement = get_object_or_404(Attachement, id=attachement_id)
    projet = attachement.projet
    return redirect(f"{reverse('projets:liste_decomptes', args=[projet.id])}?ajouter=1&attachement_id={attachement_id}")
@login_required
def validation_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    # VÉRIFICATION ET INITIALISATION AUTOMATIQUE
    if attachement.statut == 'TRANSMIS' and not attachement.validations.exists():
        attachement.initialiser_processus_validation(request.user)
        messages.info(request, "Processus de validation initialisé automatiquement.")
    validations = attachement.validations.all().order_by('ordre_validation')
    for validation in validations:
        validation.est_validable_par_utilisateur = validation.peut_etre_valide_par(request.user)
        etapes = validation.etapes.all()
        # print("Validation ID:", validation.id, "Type:", validation.type_validation, "Nombre d'étapes existantes:", etapes.count())
        if validation.type_validation == 'TECHNIQUE':
            if not etapes.exists():
                # Si aucune étape, initier les étapes standards du processus Validation Technique
                validation.initier_etapes_techniques_par_defaut()
                validation.etapes_validation = validation.etapes.all().order_by('ordre')
                # print("Initialisation des étapes techniques par défaut pour la validation ID:", validation.id)
            else:
                validation.etapes_validation = etapes.order_by('ordre') 
           
            # print("Étapes du processus de validation technique :", [etape.id for etape in validation.etapes_validation])
        else:
            validation.etapes_validation = None
    
    
    if request.method == 'POST':
        validation_id = request.POST.get('validation_id')
        action_type = request.POST.get('action_type')
        commentaires = request.POST.get('commentaires', '')
        motifs = request.POST.get('motifs', '')
        fichier = request.FILES.get('fichier')
        
        validation = get_object_or_404(ProcessValidation, id=validation_id)
        
        try:
            if action_type == 'valider':
                validation.valider(request.user, commentaires, fichier)
                messages.success(request, "Étape validée avec succès.")
            elif action_type == 'rejeter':
                validation.rejeter(request.user, motifs, fichier)
                messages.warning(request, "Étape rejetée.")
            elif action_type == 'correction':
                validation.demander_correction(request.user, commentaires)
                messages.info(request, "Correction demandée.")
        except PermissionError as e:
            messages.error(request, str(e))
        
        return redirect('projets:validation_attachement', attachement_id=attachement_id)
    
    context = {
        'attachement': attachement,
        'validations': validations,
        'user': request.user,
    }
    return render(request, 'projets/decomptes/validation_attachement.html', context)
@login_required
def reouvrir_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    
    try:
        attachement.reouvrir(request.user)
        messages.success(request, f"L'attachement {attachement.numero} a été réouvert avec succès.")
    except PermissionError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f"Erreur lors de la réouverture : {str(e)}")
    
    return redirect('projets:modifier_attachement', attachement_id=attachement_id)

# ------------------------ Views pour Décomptes ------------------------
@login_required
def liste_decomptes(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    
    # Récupérer tous les décomptes du projet
    decomptes = Decompte.objects.filter(attachement__projet=projet).order_by('-id')
    
    # Filtrer par statut si demandé
    statut_filter = request.GET.get('statut')
    if statut_filter:
        decomptes = decomptes.filter(statut=statut_filter)
    
    # Détection du contexte d'arrivée
    from_attachement_list = request.GET.get('from_attachements') == 'true'
    attachement_id = request.GET.get('attachement_id')
    action_type = request.GET.get('action')  # 'modifier' ou 'ajouter'
    
    # Si on vient de la liste des attachements avec un attachement spécifique
    attachement_cible = None
    if from_attachement_list and attachement_id:
        try:
            attachement_cible = Attachement.objects.get(id=attachement_id, projet=projet)
            
            # Filtrer pour ne montrer que le décompte lié à cet attachement (si modification)
            if action_type == 'modifier':
                decomptes = decomptes.filter(attachement=attachement_cible)
                
        except Attachement.DoesNotExist:
            pass
    
    # Recherche
    search_query = request.GET.get('search', '')
    if search_query and len(search_query) >= 3:
        decomptes = decomptes.filter(
            Q(numero__icontains=search_query) |
            Q(type_decompte__icontains=search_query) |
            Q(statut__icontains=search_query) |
            Q(numero_bordereau__icontains=search_query) |
            Q(attachement__numero__icontains=search_query)
        )
    
    # Tri
    sort_field = request.GET.get('sort', '-date_emission')
    if sort_field in ['numero', 'date_emission', 'date_echeance', 'statut', 'montant_net_a_payer']:
        decomptes = decomptes.order_by(sort_field)
    elif sort_field in ['-numero', '-date_emission', '-date_echeance', '-statut', '-montant_net_a_payer']:
        decomptes = decomptes.order_by(sort_field)
    dernier_decompte = Decompte.objects.filter(attachement__projet=projet).order_by('-id').first() # Dernier Decompte

    # Calcul des totaux
    # total_ht = decomptes.aggregate(total=Sum('montant_ht'))['total'] or 0
    # total_ttc = decomptes.aggregate(total=Sum('montant_ttc'))['total'] or 0
    # total_net = decomptes.aggregate(total=Sum('montant_net_a_payer'))['total'] or 0
    total_ht = dernier_decompte.montant_ht if dernier_decompte else 0
    total_ttc = dernier_decompte.montant_ttc if dernier_decompte else 0
    total_net = dernier_decompte.montant_net_a_payer if dernier_decompte else 0
    payes_count = decomptes.filter(statut='PAYE').count()
    
    # Compteurs par statut pour les filtres
    decomptes_payes = Decompte.objects.filter(attachement__projet=projet, statut='PAYE')
    decomptes_emis = Decompte.objects.filter(attachement__projet=projet, statut='EMIS')
    decomptes_valides = Decompte.objects.filter(attachement__projet=projet, statut='VALIDE')
    decomptes_brouillons = Decompte.objects.filter(attachement__projet=projet, statut='BROUILLON')
    
    # Attachements sans décompte (pour le compteur)
    attachements_sans_decompte = Attachement.objects.filter(projet=projet, decompte__isnull=True)
    
    # Gestion du formulaire
    decompte_a_modifier = None
    form = None
    
    # DÉTERMINER SI ON EST EN MODE MODIFICATION
    decompte_id = None
    if request.method == 'POST':
        decompte_id = request.POST.get('decompte_id')
    else:
        decompte_id = request.GET.get('modifier')
    
    # CAS 1: Mode modification d'un décompte existant
    if decompte_id:
        decompte_a_modifier = get_object_or_404(Decompte, id=decompte_id, attachement__projet=projet)
        
        if request.method == 'POST':
            form = DecompteForm(request.POST, instance=decompte_a_modifier)
        else:
            form = DecompteForm(instance=decompte_a_modifier)
        
        # Limiter les attachements disponibles (attachements sans décompte + attachement actuel)
        attachement_ids = list(attachements_sans_decompte.values_list('id', flat=True))
        attachement_ids.append(decompte_a_modifier.attachement.id)
        
        form.fields['attachement'].queryset = Attachement.objects.filter(
            id__in=attachement_ids
        ).order_by('numero')
    
    # CAS 2: Mode création avec attachement pré-sélectionné (venant de liste_attachements)
    elif from_attachement_list and attachement_cible and action_type == 'ajouter':
        if request.method == 'POST':
            form = DecompteForm(request.POST)
        else:
            form = DecompteForm()
        
        # Limiter aux attachements sans décompte (incluant l'attachement cible)
        form.fields['attachement'].queryset = attachements_sans_decompte.order_by('numero')
        
        # Pré-sélectionner et pré-remplir intelligemment
        if attachements_sans_decompte.filter(id=attachement_cible.id).exists():
            form.initial['attachement'] = attachement_cible.id
                        
            # 1. Numéro basé sur l'attachement
            form.initial['numero'] = f"DEC-{attachement_cible.numero}-{date.today().strftime('%Y%m')}"
            
            # 2. Date d'émission = aujourd'hui
            form.initial['date_emission'] = date.today()
            
            # 3. Date d'échéance = date_fin_periode de l'attachement
            if attachement_cible.date_fin_periode:
                form.initial['date_echeance'] = max(date.today(), attachement_cible.date_fin_periode)
            else:
                form.initial['date_echeance'] = date.today()+timedelta(days=30)
            
            # 4. Type de décompte par défaut = PROVISOIRE
            form.initial['type_decompte'] = 'PROVISOIRE'
            
            # 5. Statut par défaut = BROUILLON
            form.initial['statut'] = 'BROUILLON'
            
            # 6. Taux par défaut
            form.initial['taux_tva'] = 20.0
            form.initial['taux_retenue_garantie'] = 10.0
            form.initial['taux_ras'] = 0.0
            form.initial['autres_retenues'] = 0.0
    
    # CAS 3: Mode création standard (depuis dashboard)
    else:
        if request.method == 'POST':
            form = DecompteForm(request.POST)
        else:
            form = DecompteForm()
        
        form.fields['attachement'].queryset = attachements_sans_decompte.order_by('numero')
        
        # Pré-remplir les dates par défaut même en mode standard
        form.initial['date_emission'] = date.today()
        form.initial['taux_tva'] = 20.0
        form.initial['taux_retenue_garantie'] = 10.0
    
    # TRAITEMENT DE LA VALIDATION DU FORMULAIRE
    if request.method == 'POST':
        if form.is_valid():
            decompte = form.save()
            action = "modifié" if decompte_id else "créé"
            messages.success(request, f"Décompte {decompte.numero} {action} avec succès.")
            
            # Redirection contextuelle
            if from_attachement_list:
                return redirect('projets:liste_attachements', projet_id=projet.id)
            else:
                return redirect('projets:liste_decomptes', projet_id=projet.id)
        else:
            messages.error(request, "Veuillez corriger les erreurs dans le formulaire.")
    
    attachements_disponibles_count = attachements_sans_decompte.count()
    
    context = {
        'projet': projet,
        'decomptes': decomptes,
        'search_query': search_query,
        'decomptes_total_ht': total_ht,
        'decomptes_total_ttc': total_ttc,
        'decomptes_total_net': total_net,
        'decomptes_payes_count': payes_count,
        'decomptes_payes': decomptes_payes,
        'decomptes_emis': decomptes_emis,
        'decomptes_valides': decomptes_valides,
        'decomptes_brouillons': decomptes_brouillons,
        'attachements_disponibles_count': attachements_disponibles_count,
        'form': form,
        'decompte_a_modifier': decompte_a_modifier,
        'from_attachement_list': from_attachement_list,
        'attachement_id': attachement_id,
        'action_type': action_type,
        'attachement_cible': attachement_cible,  # NOUVEAU: passer l'objet attachement
    }
    
    return render(request, 'projets/decomptes/liste_decomptes.html', context)
def projet_ajouter_decompte(request, projet_id):
    """Vue pour l'ajout d'un décompte (redirige vers liste_decomptes avec formulaire ouvert)"""
    projet = get_object_or_404(Projet, id=projet_id)
    return redirect(f"{reverse('projets:liste_decomptes', args=[projet.id])}?ajouter=1")
def modifier_decompte(request, decompte_id):
    """Vue pour la modification d'un décompte (redirige vers liste_decomptes avec formulaire en mode modification)"""
    decompte = get_object_or_404(Decompte, id=decompte_id)
    return redirect(f"{reverse('projets:liste_decomptes', args=[decompte.attachement.projet.id])}?modifier={decompte.id}")
def supprimer_decompte(request, decompte_id):
    """Vue pour la suppression d'un décompte"""
    decompte = get_object_or_404(Decompte, id=decompte_id)
    projet_id = decompte.attachement.projet.id
    
    if request.method == 'POST':
        numero = decompte.numero
        decompte.delete()
        messages.success(request, f"Décompte {numero} supprimé avec succès.")
        return redirect('projets:liste_decomptes', projet_id=projet_id)
    
    # Si GET, afficher la page de confirmation
    context = {
        'decompte': decompte,
        'projet': decompte.attachement.projet
    }
    return render(request, 'projets/supprimer_decompte.html', context)
def detail_decompte(request, decompte_id):
    """Vue pour afficher le détail d'un décompte"""
    decompte = get_object_or_404(Decompte, id=decompte_id)
    projet = decompte.attachement.projet
    
    # Calcul des pourcentages pour l'affichage
    pourcentage_tva = (decompte.montant_tva / decompte.montant_ht * 100) if decompte.montant_ht > 0 else 0
    pourcentage_retenue_garantie = (decompte.montant_retenue_garantie / decompte.montant_ttc * 100) if decompte.montant_ttc > 0 else 0
    pourcentage_ras = (decompte.montant_ras / decompte.montant_ttc * 100) if decompte.montant_ttc > 0 else 0
    
    context = {
        'decompte': decompte,
        'projet': projet,
        'pourcentage_tva': pourcentage_tva,
        'pourcentage_retenue_garantie': pourcentage_retenue_garantie,
        'pourcentage_ras': pourcentage_ras,
    }
    return render(request, 'projets/decomptes/detail_decompte.html', context)
def calcul_retard_decompte(request, decompte_id):
    """API pour calculer si un décompte est en retard"""
    decompte = get_object_or_404(Decompte, id=decompte_id)
    
    est_en_retard = decompte.est_en_retard
    jours_retard = 0
    
    if decompte.date_echeance and decompte.statut in ['EMIS', 'PARTIEL']:
        aujourdhui = date.today()
        if aujourdhui > decompte.date_echeance:
            jours_retard = (aujourdhui - decompte.date_echeance).days
    
    return JsonResponse({
        'est_en_retard': est_en_retard,
        'jours_retard': jours_retard,
        'date_echeance': decompte.date_echeance.isoformat() if decompte.date_echeance else None,
        'statut': decompte.statut
    })

# -------------------- FICHE DE CONTROLE --------------------
def fiche_controle(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    attachements = Attachement.objects.filter(projet=projet).order_by('-date_etablissement')
    
    attachement_courant = None
    donnees_controle = []
    total_general = {
        'montant_marche': 0,
        'montant_partiel': 0,
        'montant_s': 0,
        'delta_montant': 0, 
        'pourcentage_realise': 0
    }
    
    attachement_id = request.GET.get('attachement_id')
    if attachement_id:
        attachement_courant = get_object_or_404(Attachement, id=attachement_id, projet=projet)
        attachement_precedent = attachement_courant.get_previous_attachement()
        
        # Récupérer tous les lots et lignes de bordereau
        lots = LotProjet.objects.filter(projet=projet).order_by('id')
        
        for lot in lots:
            lignes_bordereau = LigneBordereau.objects.filter(lot=lot).order_by('id')
            lignes_controle = []
            
            total_lot = {
                'montant_marche': 0,
                'montant_partiel': 0,
                'montant_s': 0,
                'delta_montant': 0, 
            }
            
            for ligne_bordereau in lignes_bordereau:
                if ligne_bordereau.is_title:
                    ligne_controle = {
                    'numero': ligne_bordereau.numero or '',
                    'designation': ligne_bordereau.designation,
                    'is_title': True,
                    'can_be_hidden': False
                }
                    lignes_controle.append(ligne_controle)
                    continue  # Ignorer les lignes titre
                
                # Données MARCHÉ
                quantite_marche = ligne_bordereau.quantite
                montant_marche = ligne_bordereau.montant
                
                # Données RÉALISATION - Attachement courant
                ligne_courante = LigneAttachement.objects.filter(attachement=attachement_courant, ligne_lot=ligne_bordereau).first()
                quantite_s = ligne_courante.quantite_realisee if ligne_courante else Decimal('0')
                montant_s = quantite_s * ligne_bordereau.prix_unitaire
                
                # Données RÉALISATION - Attachement précédent
                quantite_s1 = Decimal('0')
                if attachement_precedent:
                    ligne_precedente = LigneAttachement.objects.filter(attachement=attachement_precedent, 
                                                                       ligne_lot=ligne_bordereau).first()
                    quantite_s1 = ligne_precedente.quantite_realisee if ligne_precedente else Decimal('0')
                
                # Calculs intermédiaires
                quantite_partiel = quantite_s - quantite_s1
                montant_partiel = quantite_partiel * ligne_bordereau.prix_unitaire
                
                # Calculs DELTA
                delta_quantite = quantite_marche - quantite_s
                delta_montant =  montant_marche - montant_s
                
                # Pourcentage réalisé
                pourcentage_realise = (quantite_s / quantite_marche * 100) if quantite_marche > 0 else Decimal('0')
                
                ligne_controle = {
                    'numero': ligne_bordereau.numero,
                    'designation': ligne_bordereau.designation,
                    'unite': ligne_bordereau.unite,
                    'quantite_marche': quantite_marche,
                    'montant_marche': montant_marche,
                    'quantite_s1': quantite_s1,
                    'quantite_partiel': quantite_partiel,
                    'montant_partiel': montant_partiel,
                    'quantite_s': quantite_s,
                    'montant_s': montant_s,
                    'delta_quantite': delta_quantite,
                    'delta_montant': delta_montant,
                    'pourcentage_realise': pourcentage_realise,
                    'is_title': False,
                    'can_be_hidden': True if montant_s == 0 else False
                }
                
                lignes_controle.append(ligne_controle)
                
                # Totaux lot
                for key in total_lot:
                    if key in ligne_controle:
                        total_lot[key] += ligne_controle[key]
            total_lot['pourcentage_realise'] = (total_lot['montant_s'] / total_lot['montant_marche'] * 100) if total_lot['montant_marche'] > 0 else Decimal('0')

            if lignes_controle:
                donnees_controle.append({'lot': lot, 'lignes': lignes_controle, 'total_lot': total_lot})
                
                # Totaux généraux
                for key in total_general:
                    if key in total_lot:
                        total_general[key] += total_lot[key]
        total_general['pourcentage_realise'] = (total_general['montant_s'] / total_general['montant_marche'] * 100) if total_general['montant_marche'] > 0 else Decimal('0')
    
    context = {
        'projet': projet,
        'attachements': attachements,
        'attachement_courant': attachement_courant,
        'donnees_controle': donnees_controle,
        'total_general': total_general,
        'nb_lots': len(donnees_controle)>1
    }
    
    return render(request, 'projets/decomptes/fiche_controle.html', context)

# ------------------------ API pour les lignes d'attachement ------------------------
def get_lignes_attachement(request, attachement_id):
    """API pour récupérer les lignes d'un attachement en JSON"""
    attachement = get_object_or_404(Attachement, id=attachement_id)
    lignes = attachement.lignes_attachement.all()
    
    data = []
    for ligne in lignes:
        data.append({
            'id': ligne.id,
            'ligne_lot_id': ligne.ligne_lot.id,
            'designation': ligne.ligne_lot.designation,
            'unite': ligne.ligne_lot.unite,
            'prix_unitaire': float(ligne.ligne_lot.prix_unitaire),
            'quantite_realisee': float(ligne.quantite_realisee),
            'quantite_cumulee': float(ligne.quantite_cumulee),
            'montant_ligne': float(ligne.montant_ligne_realise),
            'montant_cumule': float(ligne.montant_cumule),
        })
    
    return JsonResponse(data, safe=False)

# ------------------------ Views pour Ordres de Service ------------------------
@login_required
def ordres_service(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordres_service = OrdreService.objects.filter(projet=projet).select_related('type_os').order_by('ordre_sequence')
    
    ordre_a_modifier = None
    if 'modifier_ordre' in request.GET:
        ordre_id = request.GET.get('modifier_ordre')
        ordre_a_modifier = get_object_or_404(OrdreService, id=ordre_id, projet=projet)

    if request.method == 'POST':        
        if 'notifier_os' in request.POST:  # Notification d'un OS
            ordre_id = request.POST.get('notifier_os')
            ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
            try:
                ordre.statut = 'NOTIFIE'
                ordre.full_clean()  # Validation des contraintes métier
                ordre.save()
                messages.success(request, f"L'ordre de service {ordre.reference} a été notifié avec succès.")
            except ValidationError as e:
                messages.error(request, f"Erreur lors de la notification: {e}")
            
            return redirect('projets:ordres_service', projet_id=projet.id)
        
        elif 'annuler_os' in request.POST:  # Annulation d'un OS
            ordre_id = request.POST.get('annuler_os')
            ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
            ordre.statut = 'ANNULE'
            ordre.save()
            messages.success(request, f"L'ordre de service {ordre.reference} a été annulé.")
            return redirect('projets:ordres_service', projet_id=projet.id)
        
        else:  # Création/Modification
            form = OrdreServiceForm(request.POST, request.FILES, instance=ordre_a_modifier, projet=projet)
            if form.is_valid():
                try:
                    ordre = form.save(commit=False)
                    ordre.projet = projet
                    
                    # Gestion des documents avec Cloudinary
                    fichier_document = request.FILES.get('documents')
                    if fichier_document:
                        if getattr(settings, 'USE_CLOUDINARY', False):
                            upload_result = cloudinary.uploader.upload(
                                fichier_document,
                                folder="ordres_services",
                                resource_type="raw"
                            )
                            ordre.documents = upload_result['public_id']
                        else:
                            ordre.documents = fichier_document
                            
                    if not ordre_a_modifier: # Création 
                        ordre.statut = 'BROUILLON'
                        
                    if 'supprimer_document' in request.POST and request.POST['supprimer_document'] == '1':
                        if ordre.documents:
                            if os.path.isfile(ordre.documents.path):
                                os.remove(ordre.documents.path)
                            ordre.documents = None
                    
                    if ordre.statut == 'NOTIFIE':
                        ordre.full_clean()
                                      
                    ordre.save()
                    
                    # validation avant sauvegarde
                    if ordre.statut == 'NOTIFIE':
                        messages.success(request, f"L'ordre de service {ordre.reference} a été notifié avec succès.")
                    else:
                        action = "modifié" if ordre_a_modifier else "créé"
                        messages.success(request, f"L'ordre de service {ordre.reference} a été {action} en brouillon.")
                    
                    return redirect('projets:ordres_service', projet_id=projet.id)
                    
                except ValidationError as e:
                    error_messages = []
                    for field, errors in e.error_dict.items():
                        for error in errors:
                            error_messages.append(f"{field}: {error}")
                    
                    if error_messages:
                        messages.error(request, "Erreurs de validation: " + "; ".join(error_messages))
                    else:
                        messages.error(request, f"Erreur de validation: {e}")
            else:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"{field}: {error}")
    else:
        form = OrdreServiceForm(instance=ordre_a_modifier, projet=projet)

    # Préparer les données pour l'affichage
    os_notifies = ordres_service.filter(statut='NOTIFIE')
    os_brouillons = ordres_service.filter(statut='BROUILLON')
    os_annules = ordres_service.filter(statut='ANNULE')
    
    # Préparer les données pour le template
    
    # Vérifier si un l'ordre de service de notification de l'approbation est présent
    if not projet.ordres_service.filter(type_os__code='OSN', statut='NOTIFIE').exists():
        codes_autorises = ['OSN']
    elif not projet.ordres_service.filter(type_os__code='OSC', statut='NOTIFIE').exists():
        codes_autorises = ['OSC']
    else:
        # Recuperer le dernier OS notifié
        dernier_os = projet.ordres_service.filter(statut='NOTIFIE').order_by('-ordre_sequence').first()
        # recuperer le type de l'OS
        dernier_os_type = dernier_os.type_os.code
        # si le dernier OS est un OSC ou un OSR
        if dernier_os_type in ['OSC', 'OSR']:
            codes_autorises = ['OSA', 'OSC10', 'OSV', 'AUTRE']
        # si le dernier OS est un OSA
        elif dernier_os_type == 'OSA':
            codes_autorises = ['OSR', 'OSC10', 'OSV', 'AUTRE']
        else:
            codes_autorises = ['OSA', 'OSR', 'OSC10', 'OSV', 'AUTRE']
    
    types_disponibles = TypeOrdreService.objects.filter(code__in=codes_autorises).prefetch_related('precedent_obligatoire')
    context = {
        'projet': projet,
        'ordres_service': ordres_service,
        'os_notifies': os_notifies,
        'os_brouillons': os_brouillons,
        'os_annules': os_annules,
        'ordre_a_modifier': ordre_a_modifier,
        'types_disponibles': types_disponibles,
        'form': form,
    }
    return render(request, 'projets/ordres_service/ordres_service.html', context)
def api_jours_decoules(request, projet_id):
    """API pour calculer les jours découlés"""
    projet = get_object_or_404(Projet, id=projet_id)
    date_reference = request.GET.get('date')
    
    try:
        if date_reference:
            date_ref = datetime.strptime(date_reference, '%Y-%m-%d').date()
            jours = projet.jours_decoules_depuis_demarrage(date_ref)
        else:
            jours = projet.jours_decoules_aujourdhui()
        
        return JsonResponse({
            'jours': jours,
            'projet': projet.nom,
            'date_reference': date_reference
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
def modifier_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
    
    if request.method == 'POST':
        form = OrdreServiceForm(request.POST, request.FILES, instance=ordre)
        if form.is_valid():
            ordre_modifie = form.save(commit=False)
            
            # Gestion de la suppression du document
            if 'supprimer_document' in request.POST and request.POST['supprimer_document'] == '1':
                if ordre_modifie.documents:
                    # Supprimer le fichier physique
                    if os.path.isfile(ordre_modifie.documents.path):
                        os.remove(ordre_modifie.documents.path)
                    ordre_modifie.documents = None
            
            ordre_modifie.save()
            messages.success(request, f"L'ordre de service {ordre_modifie.reference} a été modifié avec succès.")
            return redirect('projets:ordres_service', projet_id=projet.id)
    else:
        form = OrdreServiceForm(instance=ordre)
    
    # Récupérer tous les ordres de service pour l'affichage
    ordres_service = OrdreService.objects.filter(projet=projet).order_by('-date_publication')
    os_notifies = ordres_service.filter(statut='NOTIFIE')
    os_brouillons = ordres_service.filter(statut='BROUILLON')
    os_annules = ordres_service.filter(statut='ANNULE')
    types_disponibles = TypeOrdreService.objects.all().prefetch_related('precedent_obligatoire')
    context = {
        'projet': projet,
        'ordres_service': ordres_service,
        'os_notifies': os_notifies,        
        'os_brouillons': os_brouillons,   
        'os_annules': os_annules,         
        'ordre_a_modifier': ordre,
        'types_disponibles': types_disponibles,
        'form': form,
    }
    return render(request, 'projets/ordres_service/ordres_service.html', context)
def supprimer_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
    
    if request.method == 'POST':
        reference = ordre.reference
        # Supprimer le fichier document s'il existe
        if ordre.documents:
            if os.path.isfile(ordre.documents.path):
                os.remove(ordre.documents.path)
        ordre.delete()
        messages.success(request, f"L'ordre de service {reference} a été supprimé avec succès.")
        return redirect('projets:ordres_service', projet_id=projet.id)
    
    # Si GET, afficher la confirmation
    context = {
        'projet': projet,
        'ordre': ordre,
    }
    return render(request, 'projets/ordres_service/supprimer_ordre_service.html', context)
def details_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
    
    context = {
        'projet': projet,
        'ordre': ordre,
    }
    return render(request, 'projets/ordres_service/details_ordre_service.html', context)
def notifier_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)

    if request.method == 'POST':
        try:
            # Vérifier que l'OS est en brouillon
            if ordre.statut != 'BROUILLON':
                messages.error(request, "Seuls les ordres de service en brouillon peuvent être notifiés.")
                return redirect('projets:ordres_service', projet_id=projet.id)
            
            # Changer le statut et valider
            ordre.statut = 'NOTIFIE'
            
            # Debug: Valider champ par champ
            try:
                ordre.clean_fields()
            except ValidationError as e:
                raise e
                
            try:
                ordre.clean()
            except ValidationError as e:
                raise e
                
            try:
                ordre.validate_unique()
            except ValidationError as e:
                raise e
            
            # Maintenant full_clean()
            ordre.full_clean()
            
            ordre.save()
            
            messages.success(request, f"✅ L'ordre de service {ordre.reference} a été notifié avec succès.")
            
        except ValidationError as e:
            # Collecter tous les messages d'erreur
            error_details = []
            for field, errors in e.error_dict.items():
                for error in errors:
                    if field == '__all__':
                        error_details.append(str(error))
                    else:
                        error_details.append(f"{field}: {str(error)}")
            
            error_message = " | ".join(error_details)
            messages.error(request, f"❌ Impossible de notifier: {error_message}")
            
            # Revenir au statut brouillon
            ordre.statut = 'BROUILLON'
            ordre.save()
            
        except Exception as e:
            print('❌ Exception générale:', e)
            messages.error(request, f"❌ Erreur inattendue: {e}")
    return redirect('projets:ordres_service', projet_id=projet.id)
    # return redirect('projets:details_ordre_service', projet_id=projet.id, ordre_id=ordre.id)
def annuler_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
    
    if request.method == 'POST':
        # Vérifier si l'OS peut être annulé
        if ordre.statut == 'ANNULE':
            messages.warning(request, f"L'ordre de service {ordre.reference} est déjà annulé.")
            return redirect('projets:ordres_service', projet_id=projet.id)
        
        try:
            ancien_statut = ordre.statut
            ordre.statut = 'ANNULE'
            ordre.save()
            
            if ancien_statut == 'NOTIFIE':
                messages.warning(request, 
                    f"⚠️ L'ordre de service {ordre.reference} a été annulé. "
                    f"Cela peut affecter la séquence des OS suivants."
                )
            else:
                messages.info(request, f"L'ordre de service {ordre.reference} a été annulé.")
                
        except Exception as e:
            messages.error(request, f"❌ Erreur lors de l'annulation: {e}")
    
    return redirect('projets:details_ordre_service', projet_id=projet.id, ordre_id=ordre.id)
def telecharger_document_os(request, ordre_id):
    ordre = get_object_or_404(OrdreService, id=ordre_id)
    #path('download-document/<str:model_name>/<int:object_id>/', views.secure_download, name='download_document'),  
    return secure_download(request, 'OrdreService', ordre.id)

    if ordre.documents and os.path.exists(ordre.documents.path):
        with open(ordre.documents.path, 'rb') as file:
            response = HttpResponse(file.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{os.path.basename(ordre.documents.name)}"'
            return response
    else:
        messages.error(request, "Le document n'existe pas.")
        return redirect('projets:details_ordre_service', projet_id=ordre.projet.id, ordre_id=ordre.id)