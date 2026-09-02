from datetime import date, datetime

from django.utils import timezone 
from django.utils.timezone import timedelta
import json
import os
from django.apps import apps
from django.conf import settings

from django.forms import ValidationError
from django.core.exceptions import PermissionDenied
from django.shortcuts import render, get_object_or_404, redirect

from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden, HttpResponseNotFound, HttpResponseRedirect, JsonResponse, FileResponse, Http404
from django.urls import  reverse, reverse_lazy
from django.utils.translation import gettext as _
from django.views import View
from projets.decorators import can_edit_projet, can_view_projet, chef_projet_required, est_gerant, gestion_utilisateurs_required, modules_projet_required, projets_accessibles, superuser_required
from projets.exporters import ExcelExporter
from projets.services.attachement_service import DonneesAttachementInvalides, enregistrer_lignes_attachement

from ..forms import (
    ClientForm, DecompteForm, DossierForm, DocumentAdministratifForm,
    EntrepriseForm, IngenieurForm, OrdreServiceForm, ProjetForm, TacheForm,
    AttachementForm, UtilisateurCreationForm, RapportJournalierForm,
    DepenseRapportJournalierFormSet, StockRapportJournalierFormSet,
    SituationMensuelleForm, DepenseSituationMensuelleFormSet,
    StockSituationMensuelleFormSet, DocumentSituationMensuelleFormSet,
    PersonnelForm, MaterielForm, LocationForm, SousTraitanceForm,
    ConsommableForm, FournitureForm,
)
from ..models import *

from django.views.generic import ListView

from django.db import IntegrityError, transaction
from django.db.models import OuterRef, Subquery, Sum, Avg, Q, Value
from django.db.models.functions import Coalesce
from django.contrib import messages

from django.contrib.auth.models import User 
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
import logging

logger = logging.getLogger(__name__)


def permission_denied(request, exception=None):
    return render(request, 'errors/access_restricted.html', status=403)


def page_not_found(request, exception=None):
    return render(request, 'errors/access_restricted.html', {
        'page_not_found': True,
    }, status=404)

#------------------ POur la Gestion des taches ------------------
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from decimal import Decimal, InvalidOperation
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

def get_file_field(instance):
    return (
        getattr(instance, 'fichier', None)
        or getattr(instance, 'documents', None)
        or getattr(instance, 'fichier_validation', None)
        or getattr(instance, 'document', None)
    )

def get_projet_from_instance(instance):
    if hasattr(instance, 'projet'):
        return instance.projet
    elif hasattr(instance, 'suivi'):
        return instance.suivi.projet
    elif hasattr(instance, 'attachement'):
        return instance.attachement.projet
    elif hasattr(instance,'processValidation'):
        return instance.processValidation.attachement.projet
    return None

def clean_url(url, replace_https=True):
    """Nettoie l'URL en supprimant les espaces et forçant le https"""
    if not url:
        return url
    # Ne pas altérer les querystrings signées (R2/S3), juste normaliser les bords.
    url = str(url).strip()
    if ' ' in url:
        url = url.replace(' ', '%20')
    if replace_https:
        if url.startswith('http://'):
            url = url.replace('http://', 'https://')
    return url

@login_required
@can_view_projet
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
    user = request.user

    if not projet:
        return HttpResponseForbidden("Projet non trouvé pour cet objet")
    if not user in projet.users.all():
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
            original_filename = os.path.basename(getattr(file_field, 'name', 'fichier'))
        # Téléchargement avec nom de fichier explicite
        return serve_file_with_original_name(file_field, original_filename)
    else:        
        # On récupère l'URL du fichier
        url = clean_url(file_field.url)
        # Redirection vers le backend de stockage
        return HttpResponseRedirect(url)

def download_document(request, model_name, object_id):
    model = apps.get_model('projets', model_name)
    if not model:
        return HttpResponseForbidden("Modèle non reconnu")
    
    # On cherche l'objet
    obj = get_object_or_404(model, id=object_id)
    if not obj:
        return HttpResponseNotFound("Objet non trouvé")
    
    # On cherche le projet associé
    projet = get_projet_from_instance(obj)
    user = request.user

    if not projet:
        return HttpResponseForbidden("Projet non trouvé pour cet objet")
    if not user in projet.users.all():
        return HttpResponseForbidden("Accès refusé au projet associé")
    
    # On cherche le fichier
    file_field = get_file_field(obj)
    if not file_field:
        return HttpResponseForbidden("Aucun fichier lié à cet objet")
    
    if not hasattr(file_field, 'url'):
        return HttpResponseNotFound("Fichier non accessible")

    secure_url = clean_url(file_field.url)
    return HttpResponseRedirect(secure_url)

def delete_document(request, model_name, object_id):
    model = apps.get_model('projets', model_name)
    if not model:
        False, "Modèle non reconnu"
    
    # On cherche l'objet
    obj = get_object_or_404(model, id=object_id)
    if not obj: 
        return False, "Objet non rencontré"
    
    # On cherche le projet associé
    projet = get_projet_from_instance(obj)
    user = request.user

    if not projet:
        return False, "Projet non rencontré pour cet objet"
    if not user in projet.users.all():
        return False, "Accès refusé au projet associé"
    
    # On cherche le fichier
    file_field = get_file_field(obj)
    if not file_field:
        return False, "Aucun fichier lié à cet objet"
    
    # On supprime le fichier quel que soit le backend (local ou R2/S3)
    try:
        file_name = getattr(file_field, 'name', '')
        file_field.delete(save=False)
        return True, f"Fichier supprimé: {file_name}"
    except Exception as e:
        return False, f"Erreur suppression fichier: {e}"
    
def serve_file_with_original_name(file_field, original_filename):
    """Télécharge le fichier avec le nom original (tous backends)."""
    try:
        import requests
        import urllib.parse
        
        file_url = clean_url(file_field.url)
        
        response = requests.get(file_url, stream=True)
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
 
#------------------ Pour la Gestion de login ------------------
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

#------------------ Landing view - Page d'accueil ------------------
def landing(request):
    """Point d'entrée public et redirection après authentification."""
    if request.user.is_authenticated:
        return redirect('projets:liste_projets')
    
    return render(request, 'projets/apropos.html')

@login_required
def home(request):
    # Nombre de projets
    today = date.today()
    profile = request.user.profile
    projets_utilisateur = projets_accessibles(request.user)
    projets_recents = projets_utilisateur.order_by('-date_creation')[:5]  # Derniers 5 projets créés
    
    # Pour les graphiques - on prend les 10 derniers projets pour plus de données
    projets_pour_graphiques = projets_utilisateur.order_by('-date_creation')[:10]
    
    # Projets en retard (utilisant le nouveau champ en_retard)
    projets_en_retard = projets_utilisateur.filter(en_retard=True).order_by('-date_debut')[:5]
    
    # Nouveaux appels d'offres (à traiter)
    nouveaux_ao = projets_utilisateur.filter(a_traiter=True).order_by('-date_creation')[:5]
    
    # Réceptions récemment validées
    receptions_validees = projets_utilisateur.filter(reception_validee=True).order_by('-date_reception')[:5]
    
    # Statistiques principales
    nb_projets_en_cours = projets_utilisateur.filter(statut='COURS').count()
    nb_projets_en_retard = projets_utilisateur.filter(en_retard=True).count()

    # Avancement moyen des projets en cours
    avancement_moyen = projets_utilisateur.filter(statut='COURS').aggregate(moy=Avg('avancement'))['moy'] or 0
    avancement_moyen = float(avancement_moyen)

    # Appels d'offres
    nb_appels_offres = projets_utilisateur.filter(statut='AO').count()
    nb_a_traiter = projets_utilisateur.filter(a_traiter=True).count()
    
    # Réceptions
    nb_receptions_validees = projets_utilisateur.filter(reception_validee=True).count()
    nb_receptions_en_retard = projets_utilisateur.filter(reception_validee=True, en_retard=True).count()
    
    # Chiffre d'affaires
    annee_courante = date.today().year
    ca_total = projets_utilisateur.filter(date_debut__year=annee_courante).aggregate(total=Sum('montant'))['total'] or 0
    
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

    # Préparation des données pour ApexCharts
    chart_data = {
        'projets': [],
        'categories': ['Mensuel', 'Trimestriel', 'Annuel'],  # Pour les filtres
        'stats': {
            'avancement_moyen': round(avancement_moyen, 0),
            'nb_projets': projets_utilisateur.count(),
            'nb_en_retard': nb_projets_en_retard
        }
    }

    for projet in projets_pour_graphiques:
        # Déterminer la couleur en fonction de l'avancement
        avancement = float(projet.avancement) or 0
        if avancement < 20:
            couleur = '#ef4444'  # red-500
            statut_color = 'Critique'
        elif avancement < 40:
            couleur = '#f97316'  # orange-500
            statut_color = 'En retard'
        elif avancement < 60:
            couleur = '#eab308'  # yellow-500
            statut_color = 'En cours'
        elif avancement < 80:
            couleur = '#22c55e'  # green-500
            statut_color = 'Bien avancé'
        else:
            couleur = '#16a34a'  # green-600
            statut_color = 'Presque terminé'
        delai = projet.delai or 0
        date_debut = projet.date_debut or date.today()
        date_fin_prevue = date_debut + timedelta(days=delai)
        chart_data['projets'].append({
            'id': projet.id,
            'nom': projet.nom,
            'nom_court': projet.nom[:15] + '...' if len(projet.nom) > 15 else projet.nom,
            'avancement': round(avancement),
            'montant': float(projet.montant or 0),
            'couleur': couleur,
            'statut_color': statut_color,
            'statut': projet.statut,
            'en_retard': projet.en_retard,
            'date_creation': projet.date_creation.strftime('%Y-%m-%d') if projet.date_creation else None,
            'date_fin_prevue': date_fin_prevue.strftime('%Y-%m-%d') if date_fin_prevue else None
        })
    
    # Calculer les données mensuelles, trimestrielles, annuelles

    now = datetime.now()
    # Données mensuelles
    start_month = now - timedelta(days=30)
    projets_mensuels = projets_utilisateur.filter(date_creation__gte=start_month)

    chart_data['mensuel'] = {
        'labels': ['Sem 1', 'Sem 2', 'Sem 3', 'Sem 4'],
        'avancements': [65, 72, 68, 75]  # À adapter avec vos vraies données
    }

    # Données trimestrielles  
    chart_data['trimestriel'] = {
        'labels': ['Mois 1', 'Mois 2', 'Mois 3'],
        'avancements': [60, 68, 72]
    }
    
    # Données annuelles
    chart_data['annuel'] = {
        'labels': ['Q1', 'Q2', 'Q3', 'Q4'],
        'avancements': [55, 65, 70, 68]
    }
    from django.core.serializers.json import DjangoJSONEncoder
    
    chart_data_json = json.dumps(chart_data, cls=DjangoJSONEncoder)
    context = {
        'projets_recents': projets_recents,
        'projets_en_retard': projets_en_retard,
        'nouveaux_ao': nouveaux_ao,
        'receptions_validees': receptions_validees,
        'resume_cartes': resume_cartes,
        'notifications': notifications,
        'nb_notifications': nb_notifications,
        'profile': profile,
        'echeances': echeances,
        'chart_data_json': chart_data_json,
        'projets_noms': json.dumps([p.nom for p in projets_utilisateur]),
        'projets_noms_recents': json.dumps([p.nom for p in projets_recents]),
        'projets_avancements': json.dumps([round(p.avancement) if p.avancement is not None else 0 for p in projets_utilisateur]),
        'avancement_projets_recents': json.dumps([round(p.avancement) if p.avancement is not None else 0 for p in projets_recents])
    }
    return render(request, 'projets/home.html', context)


@superuser_required
def gerer_dossiers(request):
    if request.method == 'POST':
        form = DossierForm(request.POST)
        if form.is_valid():
            dossier = form.save()
            messages.success(
                request,
                f"Le dossier « {dossier.nom} » a été créé et ses projets ont été rattachés."
            )
            return redirect('projets:gerer_dossiers')
    else:
        form = DossierForm()

    return render(request, 'projets/dossiers/gerer_dossiers.html', {
        'form': form,
        'dossiers': Dossier.objects.prefetch_related('projets'),
        'projets_sans_dossier': Projet.objects.filter(
            dossier__isnull=True
        ).order_by('nom'),
    })


@superuser_required
def modifier_dossier(request, dossier_id):
    dossier = get_object_or_404(Dossier, id=dossier_id)
    if request.method == 'POST':
        form = DossierForm(request.POST, instance=dossier)
        if form.is_valid():
            form.save()
            messages.success(request, f"Le dossier « {dossier.nom} » a été modifié.")
            return redirect('projets:gerer_dossiers')
    else:
        form = DossierForm(instance=dossier)

    return render(request, 'projets/dossiers/modifier_dossier.html', {
        'form': form,
        'dossier': dossier,
    })

# --------------- Gestion des utilisateurs 
@gestion_utilisateurs_required
def modifier_utilisateur(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if user.is_superuser and user.pk != request.user.pk:
        raise PermissionDenied
    if not request.user.is_superuser and not user.dossiers.filter(gerant=request.user).exists():
        raise PermissionDenied

    can_manage_account_status = request.user.is_superuser and user.pk != request.user.pk
    can_manage_roles = (request.user.is_superuser or est_gerant(request.user)) and user.pk != request.user.pk

    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')

        user.email = email
        if password:
            user.set_password(password)
        profile, created = Profile.objects.get_or_create(user=user)

        if can_manage_roles:
            role = request.POST.get('role')
            roles_autorises = (
                {'CHEF_PROJET', 'GERANT', 'CHEF_CHANTIER', 'POINTEUR', 'STAFF', 'UTILISATEUR'}
                if request.user.is_superuser
                else {'CHEF_CHANTIER', 'POINTEUR', 'STAFF', 'UTILISATEUR'}
            )
            if role not in roles_autorises:
                raise PermissionDenied
            user.is_superuser = False
            user.is_staff = False
            profile.role = role

        if can_manage_account_status:
            user.is_active = request.POST.get('is_active') == 'on'

        if 'avatar' in request.FILES:
            profile.avatar = request.FILES['avatar']
            profile.save()

        user.save()
        profile.save()
        if request.user.is_superuser and user.pk != request.user.pk:
            user.dossiers.set(Dossier.objects.filter(id__in=request.POST.getlist('dossiers')))
        elif not request.user.is_superuser:
            user.dossiers.set(Dossier.objects.filter(gerant=request.user, id__in=request.POST.getlist('dossiers')))
        return redirect('projets:liste_utilisateurs')

    return render(request, 'projets/utilisateurs/modifier_utilisateur.html', {
        'user': user,
        'dossiers': Dossier.objects.all() if request.user.is_superuser else Dossier.objects.filter(gerant=request.user),
        'role_choices': (
            [
                ('CHEF_PROJET', 'Chef de projet'), ('CHEF_CHANTIER', 'Chef de chantier'),
                ('POINTEUR', 'Pointeur'), ('STAFF', 'Staff'), ('UTILISATEUR', 'Utilisateur'),
            ] if request.user.is_superuser else [
                ('CHEF_CHANTIER', 'Chef de chantier'), ('POINTEUR', 'Pointeur'),
                ('STAFF', 'Staff'), ('UTILISATEUR', 'Utilisateur'),
            ]
        ),
        'can_manage_account_status': can_manage_account_status,
        'can_manage_roles': can_manage_roles,
        'can_manage_user_dossiers': user.pk != request.user.pk,
    })

@gestion_utilisateurs_required
def liste_utilisateurs(request):
    if request.user.is_superuser:
        utilisateurs = User.objects.all()
    else:
        utilisateurs = User.objects.filter(dossiers__gerant=request.user).distinct()
    return render(request, 'projets/utilisateurs/liste_utilisateurs.html', {'utilisateurs': utilisateurs})

@gestion_utilisateurs_required
def ajouter_utilisateur(request):
    if request.method == 'POST':
        form = UtilisateurCreationForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                form.save()
                return redirect('projets:liste_utilisateurs')
            except Exception as e:
                print(f"Erreur lors de la création de l'utilisateur: {e}")
                form.add_error(None, f"Une erreur est survenue lors de la création de l'utilisateur.")
        else:
            # Afficher les erreurs de formulaire
            print("Erreurs de formulaire:")
            print(form.errors)
    else:
        form = UtilisateurCreationForm(user=request.user)
    
    return render(request, 'projets/utilisateurs/ajouter_utilisateur.html', {
        'form': form,
    })

@gestion_utilisateurs_required
def supprimer_utilisateur(request, user_id):
    user = get_object_or_404(User, id=user_id)
    if not request.user.is_superuser and not user.dossiers.filter(gerant=request.user).exists():
        raise PermissionDenied
    user.delete()
    return redirect('projets:liste_utilisateurs')   

@gestion_utilisateurs_required
def gerer_projets_utilisateur(request, user_id):
    utilisateur = get_object_or_404(User, id=user_id)
    projets_autorises = projets_accessibles(request.user)
    if not request.user.is_superuser and not utilisateur.dossiers.filter(gerant=request.user).exists():
        raise PermissionDenied
    tous_les_projets = projets_autorises
    projets_utilisateur = utilisateur.projets.filter(id__in=projets_autorises.values('id'))
    
    if request.method == 'POST':
        # Gérer l'ajout/suppression de projets
        projets_selectionnes = request.POST.getlist('projets')
        
        # Mettre à jour la relation ManyToMany
        utilisateur.projets.set(projets_autorises.filter(id__in=projets_selectionnes))
        
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
    can_handler = request.user.is_superuser or request.user.dossiers_geres.exists()
    projets = projets_accessibles(request.user).order_by('nom')

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
        'can_handler': can_handler,
        'projets': projets,
        'notification_urgency_levels': Notification.NIVEAU_URGENCE,
        'notification_types': Notification.TYPE_NOTIFICATION,
        'search_term': search_term,  # Pour l'affichage dans le template
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
                titre=f"Nouveau projet: {projet.nom}",
                message=f"Le projet {projet.nom} a été créé.",
                projet=projet,
                niveau_urgence='MOYEN',
            )

            if is_ajax:
                return JsonResponse({'success': True})
            
            messages.success(request, 'Projet ajouté avec succès.')
            return redirect('projets:liste_projets')
        else:
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'errors': form.errors.as_json()
                })
            print(form.errors)
            messages.error(request, 'Erreur lors de l\'ajout du projet. Veuillez corriger les erreurs ci-dessous.')
            messages.error(request,form.errors)
            return redirect('projets:liste_projets')
    
    form = ProjetForm(user=request.user)
    
    context = {
        'form': form,
        'statuts': Projet.Statut.choices,
    }
        
    return render(request, 'projets/modals/ajouter_projet_modal.html', context)

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
    
    form = ProjetForm(instance=projet, user=request.user)
    
    context = {
        'form': form,
        'projet': projet,
        'statuts': Projet.Statut.choices,
        'entreprises': Entreprise.objects.all(),
    }
    return render(request, 'projets/modals/modifier_projet_modal.html', context)

@chef_projet_required
def supprimer_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    projet.delete()
    return redirect('projets:liste_projets')

#------------------ Pages statiques ------------------
def apropos(request):
    return render(request, 'projets/apropos.html')

from django.views.decorators.http import require_GET
@require_GET
def offline_view(request):
    """Vue pour la page hors ligne"""
    return render(request, 'projets/offline.html')

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

    def get_queryset(self):
        user = self.request.user
        queryset = Tache.objects.select_related('projet', 'responsable')
        
        # Filtrage simple : superuser voit tout, sinon seulement les tâches de ses projets
        if not user.is_superuser:
            queryset = queryset.filter(projet__in=projets_accessibles(user))
        
        # Application des filtres
        filters = {
            'responsable_id': self.request.GET.get('responsable'),
            'terminee': {'true': True, 'false': False}.get(self.request.GET.get('terminee')),
            'priorite': self.request.GET.get('priorite')
        }
        
        return queryset.filter(**{k: v for k, v in filters.items() if v is not None})

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Responsables : superuser voit tous, sinon seulement les utilisateurs de ses projets
        if user.is_superuser:
            context['responsables'] = User.objects.filter(tache__isnull=False).distinct()
        else:
            context['responsables'] = User.objects.filter(projets__in=projets_accessibles(user)).distinct()
        
        return context


@login_required
def get_form_data(request):
    user = request.user
    # Récupérer les projets et utilisateurs liés à l'utilisateur connecté
    if user.is_superuser:
        # Superutilisateur voit tous les projets et tous les utilisateurs
        projets = Projet.objects.all().values('id', 'nom')
        responsables = User.objects.all().values('id', 'username')
    else:
        # Utilisateur normal voit seulement ses projets
        projets = projets_accessibles(user).values('id', 'nom')
        # Et seulement lui-même comme responsable possible
        responsables = User.objects.filter(id=user.id).values('id', 'username')
            
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
    template_name = 'projets/taches/modifier_tache.html'
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
                print(f"Erreur détail tâche {self.object.id}: {str(e)}")
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

@chef_projet_required
def partial_personnel(request):
    personnel = Personnel.objects.all()
    return render(request, 'projets/partials/personnel.html', {'personnel': personnel})

@chef_projet_required
def partial_materiel(request):
    materiel = Materiel.objects.all()
    return render(request, 'projets/partials/materiel.html', {'materiel': materiel})

@chef_projet_required
def partial_locations(request):
    locations = Location.objects.all()
    return render(request, 'projets/partials/locations.html', {'locations': locations})

@chef_projet_required
def partial_sous_traitances(request):
    sous_traitances = SousTraitance.objects.all()
    return render(request, 'projets/partials/sous_traitances.html', {'sous_traitances': sous_traitances})

@chef_projet_required
def partial_consommables(request):
    consommables = Consommable.objects.all()
    return render(request, 'projets/partials/consommables.html', {'consommables': consommables})

@chef_projet_required
def partial_fournitures(request):
    fournitures = Fourniture.objects.all()
    return render(request, 'projets/partials/fournitures.html', {'fournitures': fournitures})

@chef_projet_required
def base_donnees(request):
    return render(request, 'projets/base_donnees.html')

#------------------ Gestion d'un projet ------------------
@login_required
@can_view_projet
def dashboard_projet(request, projet_id):
    projet = get_object_or_404(Projet.objects.select_related('dossier'), id=projet_id)
    rapports_journaliers = projet.rapports_journaliers.all()
    dernier_rapport_journalier = rapports_journaliers.first()
    situations_mensuelles = projet.situations_mensuelles.all()
    derniere_situation_mensuelle = situations_mensuelles.first()
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
    documents_administratifs = DocumentAdministratif.objects.filter(projet=projet)
    ordre_services = OrdreService.objects.filter(projet=projet)
    suivis_execution = SuiviExecution.objects.filter(projet=projet)
    can_handler = request.user.is_superuser or request.user.dossiers_geres.exists()
    context = {
        'can_handler': can_handler,
        'projet': projet,
        'lots': lots,
        'montant_total': mnt_txt,
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
    }
    
    return render(request, 'projets/dashboard.html', context)


@login_required
@can_view_projet
def rapports_journaliers(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    rapports = projet.rapports_journaliers.annotate(
        total_depenses_annotated=Coalesce(
            Sum('depenses__montant'), Value(Decimal('0.00'))
        )
    ).prefetch_related('depenses')
    return render(request, 'projets/suivi/rapports_journaliers.html', {
        'projet': projet,
        'rapports': rapports,
    })

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

@chef_projet_required
def export_excel(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    lots = LotProjet.objects.filter(projet=projet).order_by('id')
    
    exporter = ExcelExporter(projet, lots)
    return exporter.export()


def _iter_lignes_bordereau_hierarchiques(projet):
    """Retourne les lignes d'un projet dans le même ordre hiérarchique que la saisie du bordereau."""
    for lot in LotProjet.objects.filter(projet=projet).order_by('id'):
        lot_root = lot.to_line_tree()
        for ligne in lot_root.get_descendants():
            yield ligne


def _est_ligne_titre_bordereau(ligne):
    """Détermine si une ligne est une ligne de titre selon la logique du bordereau."""
    if hasattr(ligne, 'has_children') and ligne.has_children():
        return True
    return (
        not getattr(ligne, 'numero', None)
        or not getattr(ligne, 'unite', None)
        or getattr(ligne, 'quantite', None) is None
        or float(getattr(ligne, 'quantite', 0) or 0) == 0
    )


@chef_projet_required
def sauvegarder_lignes_bordereau(request, lot_id):
    if request.method == "POST":
        try:
            body = json.loads(request.body)

            lot = get_object_or_404(LotProjet, id=lot_id)
            
            # Récupérer les lignes existantes
            lignes_existantes = {ligne.id: ligne for ligne in LigneBordereau.objects.filter(lot=lot)}
            id_mapping = {}
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
                    id_mapping[ligne_id] = ligne.id
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
                    if parent_id and parent_id in lignes:
                        ligne.parent = lignes[parent_id]
                    else:
                        ligne.parent = None
                    # Enregistrer la ligne
                    ligne.save()
                    id_mapping[ligne_id] = ligne.id

                # Supprimer les lignes non utilisées
                lignes_a_supprimer = set(lignes_existantes.keys()) - lignes_existantes_utilisees
                
                if lignes_a_supprimer:
                    LigneBordereau.objects.filter(id__in=lignes_a_supprimer).delete()
                    

                # Retourner les nouveaux id et les anciens id
                
                return JsonResponse({'success': True, 
                                    'message': 'Lignes sauvegardées avec succès.', 
                                    'status': 'ok',
                                    'lignes': id_mapping,
                                    }, status=200)
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
#------------------ Gestion du profil ------------------

def serve_avatar(request, filename):
    """Vue personnalisée pour servir les avatars avec fallback"""
    avatar_path = os.path.join(settings.MEDIA_ROOT, 'avatars', filename)
    
    # Vérifier si le fichier existe
    if os.path.exists(avatar_path):
        with open(avatar_path, 'rb') as f:
            return HttpResponse(f.read(), content_type='image/jpeg')
    else:
        return redirect(default_storage.url('avatars/default.jpeg'))

# Définition de la taille maximale (5 Mo en octets)
@login_required
def upload_avatar(request):
    """
    Gère la requête POST pour l'upload et la sauvegarde de l'avatar.
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

from projets.forms import AvatarUpdateForm
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

@login_required
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
@chef_projet_required
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

@chef_projet_required
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

@chef_projet_required
def supprimer_ingenieur(request, ingenieur_id):
    ingenieur = get_object_or_404(Ingenieur, id=ingenieur_id)
    ingenieur.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Ingénieur " + ingenieur.nom + " supprimé avec succès."})

    messages.success(request, "Ingénieur supprimé avec succès.")
    return redirect("projets:partial_ingenieurs")

# -------- Clients --------
@chef_projet_required
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

@chef_projet_required
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

@chef_projet_required
def supprimer_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client.delete()
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": 'Client ' + client.nom + ' supprimé avec succès.'})

    messages.success(request, "Client supprimé avec succès.")
    return redirect("projets:partial_clients")

# -------- Entreprises --------
@chef_projet_required
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

@chef_projet_required
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

@chef_projet_required
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

# -------- Personnel --------
@chef_projet_required
def ajouter_personnel(request):
    if request.method == 'POST':
        form = PersonnelForm(request.POST)
        if form.is_valid():
            personnel = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Le personnel ' + personnel.nom + ' a été ajouté avec succès'
                })
            return redirect('projets:partial_personnel')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = PersonnelForm()
    return render(request, 'projets/partials/personnel.html', {'form': form})

@chef_projet_required
def modifier_personnel(request, personnel_id):
    personnel = get_object_or_404(Personnel, id=personnel_id)

    if request.method == 'POST':
        form = PersonnelForm(request.POST, instance=personnel)
        if form.is_valid():
            personnel = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Personnel ' + personnel.nom + ' modifié avec succès'})
        else:
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

    return JsonResponse({'error': 'Méthode non supportée'}, status=400)

@chef_projet_required
def supprimer_personnel(request, personnel_id):
    personnel = get_object_or_404(Personnel, id=personnel_id)
    personnel.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Personnel " + personnel.nom + " supprimé avec succès."})

    messages.success(request, "Personnel supprimé avec succès.")
    return redirect("projets:partial_personnel")

# -------- Matériel --------
@chef_projet_required
def ajouter_materiel(request):
    if request.method == 'POST':
        form = MaterielForm(request.POST)
        if form.is_valid():
            materiel = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Le matériel ' + materiel.designation + ' a été ajouté avec succès'
                })
            return redirect('projets:partial_materiel')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = MaterielForm()
    return render(request, 'projets/partials/materiel.html', {'form': form})

@chef_projet_required
def modifier_materiel(request, materiel_id):
    materiel = get_object_or_404(Materiel, id=materiel_id)

    if request.method == 'POST':
        form = MaterielForm(request.POST, instance=materiel)
        if form.is_valid():
            materiel = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Matériel ' + materiel.designation + ' modifié avec succès'})
        else:
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

    return JsonResponse({'error': 'Méthode non supportée'}, status=400)

@chef_projet_required
def supprimer_materiel(request, materiel_id):
    materiel = get_object_or_404(Materiel, id=materiel_id)
    materiel.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Matériel " + materiel.designation + " supprimé avec succès."})

    messages.success(request, "Matériel supprimé avec succès.")
    return redirect("projets:partial_materiel")

# -------- Locations --------
@chef_projet_required
def ajouter_location(request):
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'La location ' + location.designation + ' a été ajoutée avec succès'
                })
            return redirect('projets:partial_locations')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = LocationForm()
    return render(request, 'projets/partials/locations.html', {'form': form})

@chef_projet_required
def modifier_location(request, location_id):
    location = get_object_or_404(Location, id=location_id)

    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            location = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Location ' + location.designation + ' modifiée avec succès'})
        else:
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

    return JsonResponse({'error': 'Méthode non supportée'}, status=400)

@chef_projet_required
def supprimer_location(request, location_id):
    location = get_object_or_404(Location, id=location_id)
    location.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Location " + location.designation + " supprimée avec succès."})

    messages.success(request, "Location supprimée avec succès.")
    return redirect("projets:partial_locations")

# -------- Sous-traitances --------
@chef_projet_required
def ajouter_sous_traitance(request):
    if request.method == 'POST':
        form = SousTraitanceForm(request.POST)
        if form.is_valid():
            sous_traitance = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'La sous-traitance ' + sous_traitance.designation + ' a été ajoutée avec succès'
                })
            return redirect('projets:partial_sous_traitances')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = SousTraitanceForm()
    return render(request, 'projets/partials/sous_traitances.html', {'form': form})

@chef_projet_required
def modifier_sous_traitance(request, sous_traitance_id):
    sous_traitance = get_object_or_404(SousTraitance, id=sous_traitance_id)

    if request.method == 'POST':
        form = SousTraitanceForm(request.POST, instance=sous_traitance)
        if form.is_valid():
            sous_traitance = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Sous-traitance ' + sous_traitance.designation + ' modifiée avec succès'})
        else:
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

    return JsonResponse({'error': 'Méthode non supportée'}, status=400)

@chef_projet_required
def supprimer_sous_traitance(request, sous_traitance_id):
    sous_traitance = get_object_or_404(SousTraitance, id=sous_traitance_id)
    sous_traitance.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Sous-traitance " + sous_traitance.designation + " supprimée avec succès."})

    messages.success(request, "Sous-traitance supprimée avec succès.")
    return redirect("projets:partial_sous_traitances")

# -------- Consommables --------
@chef_projet_required
def ajouter_consommable(request):
    if request.method == 'POST':
        form = ConsommableForm(request.POST)
        if form.is_valid():
            consommable = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'Le consommable ' + consommable.designation + ' a été ajouté avec succès'
                })
            return redirect('projets:partial_consommables')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = ConsommableForm()
    return render(request, 'projets/partials/consommables.html', {'form': form})

@chef_projet_required
def modifier_consommable(request, consommable_id):
    consommable = get_object_or_404(Consommable, id=consommable_id)

    if request.method == 'POST':
        form = ConsommableForm(request.POST, instance=consommable)
        if form.is_valid():
            consommable = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Consommable ' + consommable.designation + ' modifié avec succès'})
        else:
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

    return JsonResponse({'error': 'Méthode non supportée'}, status=400)

@chef_projet_required
def supprimer_consommable(request, consommable_id):
    consommable = get_object_or_404(Consommable, id=consommable_id)
    consommable.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Consommable " + consommable.designation + " supprimé avec succès."})

    messages.success(request, "Consommable supprimé avec succès.")
    return redirect("projets:partial_consommables")

# -------- Fournitures --------
@chef_projet_required
def ajouter_fourniture(request):
    if request.method == 'POST':
        form = FournitureForm(request.POST)
        if form.is_valid():
            fourniture = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'La fourniture ' + fourniture.designation + ' a été ajoutée avec succès'
                })
            return redirect('projets:partial_fournitures')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = FournitureForm()
    return render(request, 'projets/partials/fournitures.html', {'form': form})

@chef_projet_required
def modifier_fourniture(request, fourniture_id):
    fourniture = get_object_or_404(Fourniture, id=fourniture_id)

    if request.method == 'POST':
        form = FournitureForm(request.POST, instance=fourniture)
        if form.is_valid():
            fourniture = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Fourniture ' + fourniture.designation + ' modifiée avec succès'})
        else:
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)

    return JsonResponse({'error': 'Méthode non supportée'}, status=400)

@chef_projet_required
def supprimer_fourniture(request, fourniture_id):
    fourniture = get_object_or_404(Fourniture, id=fourniture_id)
    fourniture.delete()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({"success": True, "message": "Fourniture " + fourniture.designation + " supprimée avec succès."})

    messages.success(request, "Fourniture supprimée avec succès.")
    return redirect("projets:partial_fournitures")

# ------  Lots ------
def _parse_taux_tva(raw_value):
    """Valide le taux de TVA saisi ; vide => None (hérite du taux du projet)."""
    raw_value = (raw_value or '').strip()
    if raw_value == '':
        return None
    try:
        taux = Decimal(raw_value.replace(',', '.'))
    except (InvalidOperation, ValueError):
        raise ValueError("Le taux de TVA doit être un nombre.")
    if taux < 0 or taux > 100:
        raise ValueError("Le taux de TVA doit être compris entre 0 et 100.")
    return taux


@chef_projet_required
def modifier_lot(request, projet_id, lot_id):
    lot = get_object_or_404(LotProjet, id=lot_id, projet_id=projet_id)
    
    if request.method == "POST":
        nouveau_nom = request.POST.get("nom", "").strip()
        
        # Validation simple
        if not nouveau_nom:
            messages.error(request, "Le nom du lot ne peut pas être vide")
        else:
            try:
                taux_tva = _parse_taux_tva(request.POST.get('taux_tva'))
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('projets:lots_projet', projet_id=projet_id)
            lot.nom = nouveau_nom
            lot.description = request.POST.get("description", "").strip()
            lot.taux_tva = taux_tva
            lot.save()
            messages.success(request, "Le nom du lot a été mis à jour avec succès")
            return redirect('projets:lots_projet', projet_id=projet_id)
    
    context = {
        'lot': lot,
        'projet_id': projet_id,
    }
    return render(request, 'projets/lots/modifier_lot.html', context)

@chef_projet_required
def supprimer_lot(request, projet_id, lot_id):
    lot = get_object_or_404(LotProjet, id=lot_id, projet_id=projet_id)
    if request.method == 'POST':
        lot.delete()
    return redirect('projets:lots_projet', projet_id=projet_id)

@chef_projet_required
def lots_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)

    if request.method == "POST":
        nom_lot = request.POST.get("nom")
        if nom_lot:
            try:
                taux_tva = _parse_taux_tva(request.POST.get('taux_tva', '20'))
            except ValueError as e:
                messages.error(request, str(e))
                return redirect('projets:lots_projet', projet_id=projet_id)
            LotProjet.objects.create(
                projet=projet,
                nom=nom_lot,
                description=request.POST.get('description', '').strip(),
                taux_tva=taux_tva,
            )

        return redirect('projets:lots_projet', projet_id=projet_id)
    lots = LotProjet.objects.filter(projet=projet).order_by('id')

    return render(request, 'projets/lots/lots_projet.html', {'projet': projet, 'lots': lots})    

@login_required
@chef_projet_required
def lots_details(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    can_editer = request.user.is_superuser
    # Récupérer tous les lots du projet
    lots = LotProjet.objects.filter(projet=projet).order_by('id')
    lots_data = []
    montant_total = 0
    total_lignes = 0
    from projets.manager import LigneHierarchique
    
    for lot in lots:
        
        # Récupérer les lignes du bordereau pour ce lot
        lignes = LigneBordereau.objects.filter(lot=lot).order_by('id')
        # Calculer le total du lot
        total_lot = sum(
            (ligne.quantite or 0) * (ligne.prix_unitaire or 0) 
            for ligne in lignes
        )
        if total_lot == 0:
            continue
        
        # Construire la hiérarchie
        lines_root = LigneHierarchique({'id': 0, lot.nom: 'root'})
        lines_root.build_tree(lignes, lines_root)
        
        # Exporter en tableau pour le template
        lignes_table = lines_root.export_to_table()

        lots_data.append({
            'lot': lot,
            'id': lot.id,
            'nom': lot.nom,
            'description': lot.description,
            'lignes_table': lignes_table,  # Pour affichage en tableau avec niveaux
            'total_lot': total_lot,
        })
        
        montant_total += total_lot
        total_lignes += len(lignes_table)
    
    context = {
        'projet': projet,
        'can_editer': can_editer,
        'lots': lots_data,  # Contient déjà lot, lignes_hierarchiques, lignes_table, total_lot
        'montant_total': montant_total,
        'total_lots': len(lots_data),
        'total_lignes': total_lignes,
    }
    return render(request, 'projets/lots/lots_details.html', context)
   
# ------  Documents et Suivi ------
@login_required
@modules_projet_required
def documents_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    documents = projet.documents_administratifs.all()
    return render(request, 'projets/documents_administratifs.html', {'projet': projet, 'documents': documents})

@modules_projet_required
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
    try:
        return download_document(request, 'DocumentAdministratif', document_id)
    except Exception as e:
        messages.error(request, f"Erreur lors du téléchargement du fichier: {str(e)}")
        raise Http404("Erreur lors du téléchargement du document")

@modules_projet_required
def ajouter_document(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    
    if request.method == 'POST':
        form = DocumentAdministratifForm(request.POST, request.FILES)
        if form.is_valid():

            type_document = request.POST.get('type_document')
            date_remise = request.POST.get('date_remise')
            fichier = request.FILES.get('fichier')
            
            # Validation basique
            if not type_document or not fichier:
                messages.error(request, "Le type de document et le fichier sont obligatoires.")
                return redirect('projets:documents', projet_id=projet_id)
            
            # Vérifier la taille du fichier (max 10MB)
            if fichier.size > 10 * 1024 * 1024:
                messages.error(request, "Le fichier ne doit pas dépasser 10MB.")
                return redirect('projets:documents', projet_id=projet_id)
            
            # Créer le document
            try:
                document = DocumentAdministratif(
                    projet=projet,
                    type_document=type_document,
                    date_remise=date_remise if date_remise else None,
                    description=request.POST.get('description', ''),
                )
                document.fichier = fichier
                document.original_filename = fichier.name
                document.save()
            except Exception as e:
                messages.error(request, f"Une erreur s'est produite lors de l'ajout du document: {str(e)}")
                return redirect('projets:documents', projet_id=projet_id)
            
            messages.success(request, "Le document a été ajouté avec succès.")
        
            return redirect('projets:documents', projet_id=projet_id)
    form = DocumentAdministratifForm()
    return redirect('projets:documents', projet_id=projet_id)

class AfficherDocumentView(View):
    """Vue avec téléchargement direct depuis le backend de stockage"""
    def get(self, request, document_id):
        try:
            response = download_document(request, 'DocumentAdministratif', document_id)
            return response
            
        except Exception as e:
            messages.error(request, f"Erreur lors du téléchargement du fichier: {str(e)}")
            raise Http404("Erreur lors du chargement du document")
            
#----------------------- Suivi d'exécution ---------------------------
def _projet_travaux_or_403(projet_id):
    projet = get_object_or_404(Projet.objects.select_related('dossier'), id=projet_id)
    if not projet.dossier_id or projet.dossier.activite != Dossier.Activite.TRAVAUX:
        raise PermissionDenied("Ce suivi est réservé aux dossiers de travaux.")
    return projet

@login_required
@can_edit_projet
def ajouter_rapport_journalier(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    
    if request.method == 'POST':
        form = RapportJournalierForm(request.POST, request.FILES, projet=projet)
        depenses = DepenseRapportJournalierFormSet(request.POST)
        stocks = StockRapportJournalierFormSet(request.POST)
        
        if form.is_valid() and depenses.is_valid() and stocks.is_valid():
            rapport = form.save(commit=False)
            rapport.projet = projet
            
            # Gestion du fichier
            fichier = request.FILES.get('document')
            if fichier:
                rapport.document = fichier
                rapport.original_filename = fichier.name
            
            try:
                with transaction.atomic():
                    rapport.save()
                    depenses.instance = rapport
                    stocks.instance = rapport
                    depenses.save()
                    stocks.save()
            except IntegrityError:
                messages.error(
                    request,
                    'Un rapport journalier existe déjà pour cette date dans ce projet.',
                )
                return redirect('projets:rapports_journaliers', projet_id=projet.id)
            
            messages.success(request, 'Rapport journalier enregistré avec succès.')
            return redirect('projets:rapports_journaliers', projet_id=projet.id)
        else:
            # Afficher les erreurs
            error_messages = []
            if form.errors:
                error_messages.append(f"Formulaire: {form.errors.as_text()}")
            if depenses.errors:
                error_messages.append(f"Dépenses: {depenses.errors.as_text()}")
            if stocks.errors:
                error_messages.append(f"Stocks: {stocks.errors.as_text()}")
            
            messages.error(request, f"Erreurs: {'; '.join(error_messages)}")
            return render(request, 'projets/suivi/ajouter_rapport_journalier.html', {
                'projet': projet,
                'form': form,
                'depenses': depenses,
                'stocks': stocks,
                'depenses_groupees': _grouper_depenses_par_categorie(depenses),
            })
    
    today = timezone.now().date()
    form = RapportJournalierForm(initial={
        'date': today.strftime('%Y-%m-%d'),
        'redacteur': request.user.get_full_name() or request.user.username,
    })
    depenses = DepenseRapportJournalierFormSet()
    stocks = StockRapportJournalierFormSet()
    return render(request, 'projets/suivi/ajouter_rapport_journalier.html', {
        'projet': projet,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'depenses_groupees': _grouper_depenses_par_categorie(depenses),
    })

@login_required
@can_view_projet
def detail_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(
        RapportJournalier.objects.annotate(
            total_depenses_annotated=Coalesce(
                Sum('depenses__montant'), Value(Decimal('0.00'))
            )
        ).prefetch_related('depenses', 'stocks'),
        id=rapport_id, projet=projet
    )
    depenses_groupees = []
    for value, label in CategorieDepenseTravaux.choices:
        depenses_categorie = [d for d in rapport.depenses.all() if d.categorie == value]
        if depenses_categorie:
            total = sum((d.montant for d in depenses_categorie), Decimal('0.00'))
            depenses_groupees.append((value, label, depenses_categorie, total))
    return render(request, 'projets/suivi/detail_rapport_journalier.html', {
        'projet': projet,
        'rapport': rapport,
        'depenses_groupees': depenses_groupees,
    })


def _referentiel_depenses():
    """Entrées du référentiel (base de données) proposées par catégorie de dépense."""
    def options(queryset, champ_designation, champ_prix):
        return [
            {
                'designation': getattr(obj, champ_designation),
                'unite': obj.unite or '',
                'prix': getattr(obj, champ_prix) or Decimal('0.00'),
            }
            for obj in queryset
        ]

    return {
        CategorieDepenseTravaux.PERSONNEL: options(
            Personnel.objects.filter(actif=True).order_by('nom'), 'nom', 'tarif'
        ),
        CategorieDepenseTravaux.MATERIEL: options(
            Materiel.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
        CategorieDepenseTravaux.LOCATION: options(
            Location.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
        CategorieDepenseTravaux.SOUS_TRAITANCE: options(
            SousTraitance.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
        CategorieDepenseTravaux.FOURNITURE: options(
            Fourniture.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
        CategorieDepenseTravaux.CONSOMMABLE: options(
            Consommable.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
    }


def _grouper_depenses_par_categorie(depenses_formset):
    groupes = {value: [] for value, label in CategorieDepenseTravaux.choices}
    for depense_form in depenses_formset.forms:
        categorie = depense_form.instance.categorie
        if categorie in groupes:
            groupes[categorie].append(depense_form)
    referentiel = _referentiel_depenses()
    return [
        (
            value, label, groupes[value],
            sum((f.instance.montant or Decimal('0.00') for f in groupes[value]), Decimal('0.00')),
            referentiel.get(value, []),
        )
        for value, label in CategorieDepenseTravaux.choices
    ]


@login_required
@can_edit_projet
def formulaire_rapport_journalier(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    
    if request.method == 'POST':
        form = RapportJournalierForm(request.POST, request.FILES, projet=projet)
        depenses = DepenseRapportJournalierFormSet(request.POST)
        stocks = StockRapportJournalierFormSet(request.POST)
        
        if form.is_valid() and depenses.is_valid() and stocks.is_valid():
            rapport = form.save(commit=False)
            rapport.projet = projet
            
            # Gestion du fichier
            fichier = request.FILES.get('document')
            if fichier:
                rapport.document = fichier
                rapport.original_filename = fichier.name
            
            try:
                with transaction.atomic():
                    rapport.save()
                    depenses.instance = rapport
                    stocks.instance = rapport
                    depenses.save()
                    stocks.save()
            except IntegrityError:
                messages.error(
                    request,
                    'Un rapport journalier existe déjà pour cette date dans ce projet.',
                )
                return redirect('projets:rapports_journaliers', projet_id=projet.id)
            
            messages.success(request, 'Rapport journalier enregistré avec succès.')
            return redirect('projets:rapports_journaliers', projet_id=projet.id)
        else:
            # Afficher les erreurs
            error_messages = []
            if form.errors:
                error_messages.append(f"Formulaire: {form.errors.as_text()}")
            if depenses.errors:
                error_messages.append(f"Dépenses: {depenses.errors.as_text()}")
            if stocks.errors:
                error_messages.append(f"Stocks: {stocks.errors.as_text()}")
            
            messages.error(request, f"Erreurs: {'; '.join(error_messages)}")
            return render(request, 'projets/suivi/_formulaire_rapport_journalier.html', {
                'projet': projet,
                'form': form,
                'depenses': depenses,
                'stocks': stocks,
                'depenses_groupees': _grouper_depenses_par_categorie(depenses),
                'erreurs': True,
            })
    else:
        # Initialiser avec la date au format ISO
        today = timezone.now().date()
        form = RapportJournalierForm(initial={
            'date': today.strftime('%Y-%m-%d'),  # Format ISO explicite
            'redacteur': request.user.get_full_name() or request.user.username
        })
        depenses = DepenseRapportJournalierFormSet()
        stocks = StockRapportJournalierFormSet()
    
    depenses_groupees = _grouper_depenses_par_categorie(depenses)
    
    return render(request, 'projets/suivi/_formulaire_rapport_journalier.html', {
        'projet': projet,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'depenses_groupees': depenses_groupees,
    })


@login_required
@can_edit_projet
def modifier_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)

    if request.method == 'POST':
        form = RapportJournalierForm(
            request.POST, request.FILES, instance=rapport, projet=projet
        )
        depenses = DepenseRapportJournalierFormSet(request.POST, instance=rapport)
        stocks = StockRapportJournalierFormSet(request.POST, instance=rapport)
        if form.is_valid() and depenses.is_valid() and stocks.is_valid():
            rapport = form.save(commit=False)
            fichier = request.FILES.get('document')
            with transaction.atomic():
                if fichier:
                    if rapport.document:
                        rapport.document.delete(save=False)
                    rapport.document = fichier
                    rapport.original_filename = fichier.name
                rapport.save()
                depenses.save()
                stocks.save()
            messages.success(request, 'Rapport journalier modifié.')
            return redirect('projets:rapports_journaliers', projet_id=projet.id)
        messages.error(request, "Le rapport journalier n'a pas pu être modifié. Vérifiez les informations saisies.")
        return render(request, 'projets/suivi/modifier_rapport_journalier.html', {
            'projet': projet,
            'rapport': rapport,
            'form': form,
            'depenses': depenses,
            'stocks': stocks,
            'depenses_groupees': _grouper_depenses_par_categorie(depenses),
        })
    else:
        form = RapportJournalierForm(instance=rapport)
        # S'assurer que la date est au bon format
        if rapport.date:
            form.initial['date'] = rapport.date.strftime('%Y-%m-%d')
        depenses = DepenseRapportJournalierFormSet(instance=rapport)
        stocks = StockRapportJournalierFormSet(instance=rapport)

    return render(request, 'projets/suivi/modifier_rapport_journalier.html', {
        'projet': projet,
        'rapport': rapport,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'depenses_groupees': _grouper_depenses_par_categorie(depenses),
    })


@login_required
@can_edit_projet
def supprimer_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)
    if request.method == 'POST':
        rapport.delete()
        messages.success(request, 'Rapport journalier supprimé.')
    return redirect('projets:rapports_journaliers', projet_id=projet_id)


@login_required
@can_edit_projet
def supprimer_document_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)
    if request.method == 'POST':
        if rapport.document:
            # Supprime le fichier physique quel que soit le backend de stockage (local ou R2/S3)
            rapport.document.delete(save=False)
            rapport.original_filename = ''
            rapport.save(update_fields=['document', 'original_filename'])
            messages.success(request, 'Document supprimé du rapport journalier.')
        else:
            messages.info(request, 'Aucun document à supprimer.')
    return redirect('projets:modifier_rapport_journalier', projet_id=projet_id, rapport_id=rapport_id)


@login_required
@chef_projet_required
def situations_mensuelles(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    depenses_total = DepenseSituationMensuelle.objects.filter(
        situation_id=OuterRef('pk')
    ).values('situation_id').annotate(total=Sum('montant')).values('total')
    stocks_total = StockSituationMensuelle.objects.filter(
        situation_id=OuterRef('pk')
    ).values('situation_id').annotate(total=Sum('valeur')).values('total')
    situations = projet.situations_mensuelles.annotate(
        total_depenses_annotated=Coalesce(
            Subquery(depenses_total), Value(Decimal('0.00'))
        ),
        total_stock_annotated=Coalesce(
            Subquery(stocks_total), Value(Decimal('0.00'))
        ),
    ).prefetch_related('depenses', 'stocks')
    return render(request, 'projets/suivi/situations_mensuelles.html', {
        'projet': projet,
        'situations': situations,
    })


def _group_situation_expenses(formset):
    groups = {value: [] for value, label in CategorieDepenseTravaux.choices}
    for form in formset.forms:
        if form.instance.categorie in groups:
            groups[form.instance.categorie].append(form)
    return [
        (
            value,
            label,
            groups[value],
            sum((form.instance.montant or Decimal('0.00') for form in groups[value]), Decimal('0.00')),
        )
        for value, label in CategorieDepenseTravaux.choices
    ]

@login_required
@can_view_projet
def upload_rapport_document(request, projet_id, rapport_id):
    """Upload un document pour un rapport journalier"""
    projet = get_object_or_404(Projet, id=projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)
    
    if request.method != 'POST':
        messages.error(request, "Méthode non autorisée")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    fichier = request.FILES.get('document')
    if not fichier:
        messages.error(request, "Aucun fichier sélectionné")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    # Vérifier la taille (max 10MB)
    if fichier.size > 10 * 1024 * 1024:
        messages.error(request, "Le fichier ne doit pas dépasser 10MB")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    # Vérifier le type de fichier
    valid_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif']
    ext = os.path.splitext(fichier.name)[1].lower()
    if ext not in valid_extensions:
        messages.error(request, f"Type de fichier non supporté. Utilisez: {', '.join(valid_extensions)}")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    try:
        # Supprimer l'ancien document s'il existe
        if rapport.document and rapport.document.name:
            rapport.document.delete(save=False)
        
        # Sauvegarder le nouveau document
        rapport.document = fichier
        rapport.original_filename = fichier.name
        rapport.save()
        
        messages.success(request, f"Document '{fichier.name}' ajouté avec succès au rapport du {rapport.date.strftime('%d/%m/%Y')}")
    except Exception as e:
        messages.error(request, f"Erreur lors de l'upload: {str(e)}")
    
    return redirect('projets:suivi_execution', projet_id=projet_id)


@login_required
@chef_projet_required
def ajouter_situation_mensuelle(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    depenses = DepenseSituationMensuelleFormSet(request.POST or None)
    stocks = StockSituationMensuelleFormSet(request.POST or None)
    documents = DocumentSituationMensuelleFormSet(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        form = SituationMensuelleForm(request.POST, request.FILES, projet=projet)
        if form.is_valid():
            situation = form.save(commit=False)
            situation.projet = projet
            periode = form.cleaned_data.get('periode')
            if periode:
                year, month = (int(part) for part in periode.split('-'))
                situation.annee, situation.mois = year, month
            depenses = DepenseSituationMensuelleFormSet(request.POST, instance=situation)
            stocks = StockSituationMensuelleFormSet(request.POST, instance=situation)
            documents = DocumentSituationMensuelleFormSet(request.POST, request.FILES, instance=situation)
            if depenses.is_valid() and stocks.is_valid() and documents.is_valid():
                try:
                    with transaction.atomic():
                        situation.save()
                        depenses.instance = situation
                        stocks.instance = situation
                        depenses.save()
                        stocks.save()
                        documents.save()
                except IntegrityError:
                    form.add_error('mois', 'Une situation existe déjà pour cette période.')
                else:
                    messages.success(request, 'Situation mensuelle enregistrée.')
                    return redirect('projets:situations_mensuelles', projet_id=projet.id)
    else:
        form = SituationMensuelleForm(initial={
            'annee': timezone.now().year,
            'mois': timezone.now().month,
        })
        depenses = DepenseSituationMensuelleFormSet()
        stocks = StockSituationMensuelleFormSet()
        documents = DocumentSituationMensuelleFormSet()

    return render(request, 'projets/suivi/ajouter_situation_mensuelle.html', {
        'projet': projet,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'documents': documents,
        'depenses_groupees': _group_situation_expenses(depenses),
    })


@login_required
@chef_projet_required
def modifier_situation_mensuelle(request, projet_id, situation_id):
    projet = _projet_travaux_or_403(projet_id)
    situation = get_object_or_404(SituationMensuelle, id=situation_id, projet=projet)
    if request.method == 'POST':
        form = SituationMensuelleForm(request.POST, request.FILES, instance=situation, projet=projet)
        depenses = DepenseSituationMensuelleFormSet(request.POST, instance=situation)
        stocks = StockSituationMensuelleFormSet(request.POST, instance=situation)
        documents = DocumentSituationMensuelleFormSet(request.POST, request.FILES, instance=situation)
        if form.is_valid() and depenses.is_valid() and stocks.is_valid() and documents.is_valid():
            situation = form.save(commit=False)
            with transaction.atomic():
                situation.save()
                depenses.save()
                stocks.save()
                documents.save()
            messages.success(request, 'Situation mensuelle modifiée.')
            return redirect('projets:situations_mensuelles', projet_id=projet.id)
    else:
        form = SituationMensuelleForm(instance=situation)
        depenses = DepenseSituationMensuelleFormSet(instance=situation)
        stocks = StockSituationMensuelleFormSet(instance=situation)
        documents = DocumentSituationMensuelleFormSet(instance=situation)
    return render(request, 'projets/suivi/modifier_situation_mensuelle.html', {
        'projet': projet, 'situation': situation, 'form': form,
        'depenses': depenses, 'stocks': stocks,
        'depenses_groupees': _group_situation_expenses(depenses),
        'documents': documents,
    })


@login_required
@chef_projet_required
def supprimer_situation_mensuelle(request, projet_id, situation_id):
    projet = _projet_travaux_or_403(projet_id)
    situation = get_object_or_404(SituationMensuelle, id=situation_id, projet=projet)
    if request.method == 'POST':
        situation.delete()
        messages.success(request, 'Situation mensuelle supprimée.')
    return redirect('projets:situations_mensuelles', projet_id=projet.id)


@login_required
@chef_projet_required
def supprimer_document_situation_mensuelle(request, projet_id, situation_id):
    projet = _projet_travaux_or_403(projet_id)
    situation = get_object_or_404(SituationMensuelle, id=situation_id, projet=projet)
    if request.method == 'POST':
        document = get_object_or_404(DocumentSituationMensuelle, id=request.POST.get('document_id'), situation=situation)
        document.delete()
        messages.success(request, 'Document mensuel supprimé.')
    return redirect('projets:modifier_situation_mensuelle', projet_id=projet.id, situation_id=situation.id)


@modules_projet_required
def suivi_execution(request, projet_id):
    projet = get_object_or_404(Projet.objects.select_related('dossier'), id=projet_id)
    
    # Optimisation: précharger les fichiers avec prefetch_related
    suivis = projet.suivis_execution.all().prefetch_related('fichiers')
    
    choices = SuiviExecution.TYPE_SUIVI_CHOICES
    
    rapports_journaliers = []
    if projet.dossier_id and projet.dossier.activite == Dossier.Activite.TRAVAUX:
        rapports_journaliers = projet.rapports_journaliers.annotate(
            total_depenses_annotated=Coalesce(
                Sum('depenses__montant'), Value(Decimal('0.00'))
            )
        )[:10]
    
    return render(request, 'projets/suivi/suivi_execution.html', {
        'projet': projet,
        'suivis': suivis,
        'choices': choices,
        'rapports_journaliers': rapports_journaliers,
    })

@modules_projet_required
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
        action = request.POST.get('action')
        
        if action == 'save_and_open_files':
            # Rediriger vers le template d'ajout de fichiers
            return redirect('projets:ajouter_fichier_suivi', projet_id=projet_id, suivi_id=suivi.id)
        elif action == 'save_and_close':
            # Rediriger vers la page dashboard du projet
            return redirect('projets:dashboard', projet_id=projet_id)
        
    return redirect('projets:suivi_execution', projet_id=projet_id)

@modules_projet_required
def supprimer_suivi(request, projet_id, suivi_id):
    if request.method == 'POST':
        suivi = get_object_or_404(SuiviExecution, id=suivi_id, projet_id=projet_id)
        suivi.delete()
        messages.success(request, "Le suivi a été supprimé avec succès.")
    
    return redirect('projets:suivi_execution', projet_id=projet_id)

@modules_projet_required
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

@modules_projet_required
def afficher_fichier_suivi(request, fichier_id):
    """
    Vue pour afficher/télécharger un fichier de suivi
    """
    try:
        fichier_suivi = get_object_or_404(FichierSuivi, id=fichier_id)
        # Vérifier que le fichier existe physiquement
        if not fichier_suivi.fichier or not fichier_suivi.fichier.url:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Fichier introuvable'})
            
            messages.error(request, "Le fichier demandé est introuvable.")
            return redirect('projets:suivi_execution', projet_id=fichier_suivi.suivi.projet.id)    
    
        # Déterminer si on doit afficher dans le navigateur ou forcer le téléchargement
        extension = os.path.splitext(fichier_suivi.fichier.url)[1].lower()
        viewable_types = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.txt', '.csv', '.html', '.htm'}
        
        # Télécharger le fichier
        #response = secure_download(request, "FichierSuivi", fichier_id)
        secure_url = download_document(request, "FichierSuivi", fichier_id)
        return secure_url
    except IOError:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, "error": "Impossible d'ouvrir le fichier."})
        messages.error(request, "Impossible d'ouvrir le fichier.")
        return redirect('projets:suivi_execution', projet_id=fichier_suivi.suivi.projet.id)
    
@modules_projet_required
def supprimer_fichier_suivi(request, fichier_id):
    if request.method == 'POST':
        try: 
            fichier_suivi = get_object_or_404(FichierSuivi, id=fichier_id)
            suivi_id = fichier_suivi.suivi.id
            projet_id = fichier_suivi.suivi.projet.id  

            if fichier_suivi.fichier:
                # public_id = fichier_suivi.get_public_id
                # print("Public ID:", public_id)
                result = delete_document(request, 'FichierSuivi', fichier_id)

                if result[0]:
                    fichier_suivi.delete()
                    messages.success(request, "Le fichier a été supprimé avec succès.")
                    return redirect('projets:suivi_execution', projet_id=projet_id)
                else:
                    messages.error(request, "Une erreur s'est produite lors de la suppression du fichier.")
                    return redirect('projets:modifier_suivi', projet_id, suivi_id)

        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression du fichier: {str(e)}")
        
    return redirect('projets:suivi_execution', projet_id=projet_id)


@modules_projet_required
def telecharger_fichier_suivi(request, fichier_id):
    try:
        fichier = get_object_or_404(FichierSuivi, id=fichier_id)
        return download_document(request, 'FichierSuivi', fichier_id)
    except Exception as e:
        messages.error(request, f"Erreur lors du téléchargement du fichier: {str(e)}")
        return redirect('projets:suivi_execution', projet_id=fichier.suivi.projet.id)

@modules_projet_required
def ajouter_fichier_suivi(request, projet_id, suivi_id):
    """
    Vue pour ajouter des fichiers à un suivi d'exécution existant
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
            if fichier.size > 10 * 1024 * 1024:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 
                        'error': f"Le fichier {fichier.name} dépasse la taille maximale de 10MB"
                    })
                messages.error(request, f"Le fichier {fichier.name} dépasse la taille maximale de 10MB.")
                continue
            
            # Utiliser la description correspondante si disponible
            description = descriptions[i] if i < len(descriptions) else ''
            
            try:
                fichier_suivi = FichierSuivi(
                    suivi=suivi,
                    description=description
                )
                
                fichier_suivi.fichier = fichier
                fichier_suivi.original_filename = fichier.name
                fichier_suivi.save()
                fichiers_ajoutes.append(fichier_suivi.get_file_name)
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
def _verifier_acces_attachement(request, attachement, statuts_autorises=None):
    if not request.user.is_superuser and not projets_accessibles(request.user).filter(
        id=attachement.projet_id
    ).exists():
        raise PermissionDenied("Vous n'avez pas accès à cet attachement.")

    if statuts_autorises and attachement.statut not in statuts_autorises:
        raise PermissionDenied("Cette action n'est pas autorisée pour le statut actuel de l'attachement.")


@modules_projet_required
def liste_attachements(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    attachements = Attachement.objects.filter(projet=projet).order_by('id')
    
    context = {
        'projet': projet,
        'attachements': attachements,
    }
    return render(request, 'projets/decomptes/liste_attachements.html', context)

@modules_projet_required
def ajouter_attachement(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    
    # Récupérer toutes les lignes du projet dans le même ordre hiérarchique que la saisie du bordereau
    lignes_bordereau = list(_iter_lignes_bordereau_hierarchiques(projet))

    if request.method == 'POST':
        form = AttachementForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    attachement = form.save(commit=False)
                    attachement.projet = projet
                    fichier = request.FILES.get('fichier')
                    attachement.fichier = fichier
                    if fichier:
                        attachement.original_filename = fichier.name
                    attachement.marquer_modification(request.user)
                    attachement.save()

                    enregistrer_lignes_attachement(
                        attachement,
                        request.POST.get('lignes_attachement'),
                    )

                messages.success(request, "Attachement créé avec succès !")
                return redirect('projets:liste_attachements', projet_id=projet.id)

            except DonneesAttachementInvalides as e:
                messages.error(request, f"Données d'attachement invalides : {str(e)}")
            except Exception as e:
                messages.error(request, f"Erreur lors de la création : {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    
    else:           
        form = AttachementForm(initial={
            'statut': 'BROUILLON',            
        })
     
    # Préparer les données pour Handsontable (GET) selon le même ordre hiérarchique que la saisie du bordereau
    lignes_data = []
    
    for ligne in lignes_bordereau:
        is_title = _est_ligne_titre_bordereau(ligne)
        ligne_bordereau = LigneBordereau.objects.select_related('lot', 'parent').get(pk=ligne.id)
        quantite_deja_realisee = ligne_bordereau.get_quantite_deja_realisee if not is_title else None

        ligne_dict = {
            'id': ligne.id,
            'parent_id': ligne.parent.id if getattr(ligne, 'parent', None) else None,
            'numero': ligne.numero,
            'niveau': ligne.level() if hasattr(ligne, 'level') else ligne.niveau,
            'designation': ligne.designation,
            'unite': ligne.unite,
            'is_title': is_title,
            'est_titre': hasattr(ligne, 'has_children') and ligne.has_children(),
        }
        
        if not is_title:
            ligne_dict.update({
                'quantite_prevue': float(ligne_bordereau.quantite) if ligne_bordereau.quantite is not None else 0.0,
                'prix_unitaire': float(ligne_bordereau.prix_unitaire) if ligne_bordereau.prix_unitaire is not None else 0.0,
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

    lignes_json = json.dumps(lignes_data, default=str)
    
    nb_attachements = Attachement.objects.filter(projet=projet).count()
    next_numero = nb_attachements + 1
    date_fin_periode = timezone.now().date()
    
    if next_numero == 1:
        osc = projet.ordres_service.filter(type_os__code='OSC', statut='NOTIFIE').first()
        if osc and osc.date_effet:
            date_debut_periode = osc.date_effet
        else:
            date_debut_periode = timezone.now().date()
    else:
        dernier_attachement = Attachement.objects.filter(projet=projet).latest('date_etablissement')
        date_debut_periode = dernier_attachement.date_fin_periode
    date_fin_periode = date_debut_periode + timedelta(days=30)
    
    context = {
        'projet': projet,
        'form': form,
        'lignes': lignes_json,
        'total_lignes': len(lignes_bordereau),
        'date_etablissement': date_fin_periode,
        'numero': 'DP' + str(next_numero).zfill(2),
        'date_debut_periode': date_debut_periode,
        'date_fin_periode': date_fin_periode,
        'is_edition': False
    }
    return render(request, 'projets/decomptes/attachement_form.html', context)

@modules_projet_required
def modifier_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    _verifier_acces_attachement(request, attachement, {'BROUILLON', 'MODIFIE'})
    projet = attachement.projet
    
    # Récupérer les lignes du projet selon le même ordre hiérarchique que la saisie du bordereau
    lignes_bordereau = list(_iter_lignes_bordereau_hierarchiques(projet))
    
    if request.method == 'POST':
        form = AttachementForm(request.POST, request.FILES, instance=attachement)
        if form.is_valid():
            try:
                with transaction.atomic():
                    attachement = form.save(commit=False)
                    attachement.marquer_modification(request.user)
                    attachement.save()

                    enregistrer_lignes_attachement(
                        attachement,
                        request.POST.get('lignes_attachement'),
                    )

                messages.success(request, "Attachement modifié avec succès !")
                return redirect('projets:liste_attachements', projet_id=projet.id)

            except DonneesAttachementInvalides as e:
                messages.error(request, f"Données d'attachement invalides : {str(e)}")
            except Exception as e:
                messages.error(request, f"Erreur lors de la modification : {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        form = AttachementForm(instance=attachement)
    
    lignes_data = []
    attachement_avant = attachement.get_previous_attachement()
    for ligne in lignes_bordereau:
        ligne_bordereau = LigneBordereau.objects.select_related('lot', 'parent').get(pk=ligne.id)
        ligne_att_avant = LigneAttachement.objects.filter(attachement=attachement_avant, ligne_lot=ligne_bordereau).first()
        ligne_cet_att = LigneAttachement.objects.filter(attachement=attachement, ligne_lot=ligne_bordereau).first()
        is_title = _est_ligne_titre_bordereau(ligne)

        if is_title:
            quantite_realisee_attachement_avant = None
            quantite_realisee = None
        else:
            quantite_realisee = ligne_cet_att.quantite_realisee if ligne_cet_att else None
            quantite_realisee_attachement_avant = ligne_att_avant.quantite_realisee if ligne_att_avant else None
        
        ligne_dict = {
            'id': ligne.id,
            'parent_id': ligne.parent.id if getattr(ligne, 'parent', None) else None,
            'numero': ligne.numero,
            'niveau': ligne.level() if hasattr(ligne, 'level') else ligne_bordereau.niveau,
            'designation': ligne.designation,
            'unite': ligne.unite,
            'is_title': is_title,
            'est_titre': hasattr(ligne, 'has_children') and ligne.has_children()
        }
        
        if not is_title:
            ligne_dict.update({
                'quantite_prevue': float(ligne_bordereau.quantite) if ligne_bordereau.quantite is not None else 0.0,
                'prix_unitaire': float(ligne_bordereau.prix_unitaire) if ligne_bordereau.prix_unitaire is not None else 0.0,
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

    lignes_json = json.dumps(lignes_data, default=str)
            
    while lignes_data and lignes_data[-1]['is_title']:
        lignes_data.pop()
    
    lignes_json = json.dumps(lignes_data, default=str)
    
    attachement.peut_reouvrir = (attachement.statut == 'VALIDE' and (request.user.is_superuser or request.user.is_staff))
    attachement.peut_supprimer = attachement.statut != 'VALIDE'
    attachement.est_validable = attachement.statut in ['BROUILLON', 'TRANSMIS']
    attachement.ferme = attachement.statut == 'SIGNE'
    
    context = {
        'projet': projet,
        'attachement': attachement,
        'form': form,
        'lignes': lignes_json,
        'total_lignes': len(lignes_bordereau),
        'total_attachement': float(0.0),
        'is_edition': True
    }
    return render(request, 'projets/decomptes/attachement_form.html', context)

@modules_projet_required
def detail_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    
    lots = LotProjet.objects.filter(projet=attachement.projet).order_by('id')
    lots_data = []
    montant_total = Decimal('0.00')
    total_lignes = 0
    from projets.manager import LigneHierarchique
    
    for lot in lots:
        lot_root = lot.to_line_tree()
        lignes_attachement = []

        for ligne in lot_root.get_descendants():
            ligne_att = LigneAttachement.objects.filter(attachement=attachement, ligne_lot_id=ligne.id).first()
            if not ligne_att:
                continue

            montant_ligne = (ligne_att.quantite_realisee or Decimal('0')) * (ligne_att.prix_unitaire or Decimal('0'))
            lignes_attachement.append({
                'id': ligne.id,
                'parent_id': ligne.parent.id if getattr(ligne, 'parent', None) else None,
                'numero': ligne.numero,
                'designation': ligne.designation,
                'unite': ligne.unite,
                'quantite': float(ligne_att.quantite_realisee) if ligne_att.quantite_realisee is not None else None,
                'prix_unitaire': float(ligne_att.prix_unitaire) if ligne_att.prix_unitaire is not None else None,
                'montant': float(montant_ligne),
            })

        if not lignes_attachement:
            continue

        root = LigneHierarchique({'id': 0, 'parent_id': None, 'designation': lot.nom})
        _, root = LigneHierarchique.build_tree(lignes_attachement, root)
        lignes_table = [ligne for ligne in root.export_to_table() if ligne.get('id') != 0]
        total_lot = sum(Decimal(str(ligne['montant'])) for ligne in lignes_attachement)

        lots_data.append({
            'lot': lot,
            'lignes_table': lignes_table,
            'total_lot': total_lot,
        })
        
        montant_total += total_lot
        total_lignes += len(lignes_table)
    
    context = {
        'attachement': attachement,
        'lots_data': lots_data,
        'montant_total': montant_total,
        'total_lots': len(lots_data),
        'total_lignes': total_lignes,
    }
    return render(request, 'projets/decomptes/detail_attachement.html', context)

def tracabilite_validation_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    _verifier_acces_attachement(request, attachement)

    validations = []
    for validation in attachement.validations.prefetch_related('etapes__valide_par').select_related('validateur').order_by('ordre_validation'):
        document_url = None
        if validation.fichier:
            document_url = reverse('projets:download_document', args=['ProcessValidation', validation.id])

        validations.append({
            'type': validation.get_type_validation_display(),
            'statut': validation.get_statut_validation_display(),
            'validateur': validation.validateur.get_full_name() or validation.validateur.username if validation.validateur else None,
            'date_validation': validation.date_validation.strftime('%d/%m/%Y %H:%M') if validation.date_validation else None,
            'commentaires': validation.commentaires or '',
            'motifs_rejet': validation.motifs_rejet or '',
            'document_nom': validation.get_file_name if validation.fichier else None,
            'document_url': document_url,
            'etapes': [
                {
                    'nom': etape.nom,
                    'statut': 'Validée' if etape.est_validee else 'En attente',
                    'validateur': etape.valide_par.get_full_name() or etape.valide_par.username if etape.valide_par else None,
                    'date_validation': etape.date_validation.strftime('%d/%m/%Y %H:%M') if etape.date_validation else None,
                    'commentaire': etape.commentaire or '',
                }
                for etape in validation.etapes.all()
            ],
        })

    return JsonResponse({'attachement': attachement.numero, 'validations': validations})
    
@modules_projet_required
def supprimer_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    _verifier_acces_attachement(request, attachement, {'BROUILLON', 'MODIFIE'})
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
    _verifier_acces_attachement(request, attachement)
    if attachement.statut == 'TRANSMIS' and not attachement.validations.exists():
        with transaction.atomic():
            attachement.initialiser_processus_validation(request.user)
        messages.info(request, "Processus de validation initialisé automatiquement.")
    validations = attachement.validations.all().order_by('ordre_validation')
    for validation in validations:
        validation.est_validable_par_utilisateur = validation.peut_etre_valide_par(request.user)
        etapes = validation.etapes.all()

        if validation.type_validation == 'TECHNIQUE':
            if not etapes.exists():
                validation.initier_etapes_techniques_par_defaut()
                validation.etapes_validation = validation.etapes.all().order_by('ordre')
            else:
                validation.etapes_validation = etapes.order_by('ordre')
        else:
            validation.etapes_validation = None

    if request.method == 'POST':
        validation_id = request.POST.get('validation_id')
        action_type = request.POST.get('action_type')
        commentaires = request.POST.get('commentaires', '')
        motifs = request.POST.get('motifs', '')
        fichier = request.FILES.get('fichier')

        validation = get_object_or_404(ProcessValidation, id=validation_id, attachement=attachement)

        try:
            with transaction.atomic():
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
@require_POST
def reouvrir_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    _verifier_acces_attachement(request, attachement)

    try:
        with transaction.atomic():
            attachement.reouvrir(request.user)
        messages.success(request, f"L'attachement {attachement.numero} a été réouvert avec succès.")
    except PermissionError as e:
        messages.error(request, str(e))
    except Exception as e:
        messages.error(request, f"Erreur lors de la réouverture : {str(e)}")

    return redirect('projets:modifier_attachement', attachement_id=attachement_id)

@login_required
def validation_technique_attachement(request, attachement_id):
    """Affiche la page de validation technique"""
    attachement = get_object_or_404(Attachement, id=attachement_id)
    _verifier_acces_attachement(request, attachement)
    validation_technique = attachement.validations.filter(type_validation='TECHNIQUE').first()
    
    if not validation_technique:
        messages.error(request, "Aucun processus de validation technique trouvé.")
        return redirect('projets:modifier_attachement', attachement_id=attachement_id)
    
    etapes = validation_technique.etapes.all().order_by('ordre')
    
    context = {
        'attachement': attachement,
        'validation_technique': validation_technique,
        'etapes': etapes,
        'peut_valider': validation_technique.peut_etre_valide_par(request.user),
    }
    return render(request, 'projets/decomptes/validation_technique_attachement.html', context)

# ------------------------ Views pour Processus de Validation ------------------------
@login_required
def ajouter_etape(request, process_id):
    """Ajoute une nouvelle étape au processus de validation"""
    try:
        process_validation = ProcessValidation.objects.get(id=process_id)
        attachement_id = process_validation.attachement.id
        
        # Vérifications de sécurité
        if not process_validation.peut_etre_valide_par(request.user):
            messages.error(request, "❌ Permission refusée.")
            return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)
        
        if request.method == 'POST':
            nom = request.POST.get('nom')
            obligatoire = request.POST.get('obligatoire') == 'true'
            commentaire = request.POST.get('commentaire', '')
            
            if not nom:
                messages.error(request, "❌ Le nom de l'étape est obligatoire.")
                return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)
            
            # Déterminer le prochain ordre
            from django.db.models import Max
            dernier_ordre = process_validation.etapes.aggregate(Max('ordre'))['ordre__max']
            nouvel_ordre = (dernier_ordre or 0) + 1
            
            # Créer la nouvelle étape
            nouvelle_etape = EtapeValidation.objects.create(
                processValidation=process_validation,
                nom=nom,
                ordre=nouvel_ordre,
                obligatoire=obligatoire,
                commentaire=commentaire
            )
            
            messages.success(request, f"✅ Nouvelle étape '{nom}' ajoutée avec succès !")
            return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)
        
    except ProcessValidation.DoesNotExist:
        messages.error(request, "❌ Processus de validation non trouvé.")
        return redirect('projets:liste_attachements')
    
    return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)

@login_required
def valider_etape(request, etape_id):
    """Valide une étape spécifique"""
    try:
        etape = EtapeValidation.objects.get(id=etape_id)
        
        # Vérification des permissions
        if not etape.processValidation.peut_etre_valide_par(request.user):
            messages.error(request, "❌ Permission refusée.")
            return redirect_to_attachement(etape)
        
        if request.method == 'POST':
            commentaire = request.POST.get('commentaire', '')
            
            # ✅ UTILISATION DE VOTRE MÉTHODE valider()
            etape.valider(request.user, commentaire)
            messages.success(request, f"✅ Étape '{etape.nom}' validée avec succès !")
        
    except EtapeValidation.DoesNotExist:
        messages.error(request, "❌ Étape de validation non trouvée.")
        return redirect('projets:liste_attachements')
    
    return redirect_to_attachement(etape)

@login_required
def passer_etape(request, etape_id):
    """Passe une étape optionnelle"""
    try:
        etape = EtapeValidation.objects.get(id=etape_id)
        
        # Vérifications
        if not etape.processValidation.peut_etre_valide_par(request.user):
            messages.error(request, "❌ Permission refusée.")
            return redirect_to_attachement(etape)
        
        if etape.obligatoire:
            messages.error(request, "❌ Impossible de passer une étape obligatoire.")
            return redirect_to_attachement(etape)
        
        if request.method == 'POST':
            commentaire = request.POST.get('commentaire', '')
            
            # Marquer comme validée sans la logique métier complète
            etape.est_validee = True
            etape.valide_par = request.user
            etape.date_validation = timezone.now()
            etape.commentaire = commentaire if commentaire else "Étape passée"
            etape.save()
            etape.processValidation.valider(request.user)
            
            messages.warning(request, f"⚠️ Étape '{etape.nom}' passée.")
        
    except EtapeValidation.DoesNotExist:
        messages.error(request, "❌ Étape de validation non trouvée.")
        return redirect('projets:liste_attachements')
    
    return redirect_to_attachement(etape)

@login_required
def modifier_etape(request, etape_id):
    """Modifie une étape non validée"""
    try:
        etape = EtapeValidation.objects.get(id=etape_id)
        
        # Vérifications
        if not etape.processValidation.peut_etre_valide_par(request.user):
            messages.error(request, "❌ Permission refusée.")
            return redirect_to_attachement(etape)
        
        if etape.est_validee:
            messages.error(request, "❌ Impossible de modifier une étape déjà validée.")
            return redirect_to_attachement(etape)
        
        if request.method == 'POST':
            nouveau_nom = request.POST.get('nom')
            nouveau_commentaire = request.POST.get('commentaire', '')
            obligatoire_value = request.POST.get('obligatoire')
            
            nouvelle_obligatoire = obligatoire_value == 'on'  # ou 'true' selon votre HTML
            
            if nouveau_nom:
                etape.nom = nouveau_nom
            etape.commentaire = nouveau_commentaire
            etape.obligatoire = nouvelle_obligatoire
            
            etape.save()
            
            messages.success(request, f"✏️ Étape '{etape.nom}' modifiée avec succès.")
            return redirect_to_attachement(etape)
        
    except EtapeValidation.DoesNotExist:
        messages.error(request, "❌ Étape non trouvée.")
    
    return redirect_to_attachement(etape)

@login_required
def reinitialiser_etape(request, etape_id):
    """Réinitialise une étape validée pour reprendre le processus"""
    try:
        etape = EtapeValidation.objects.get(id=etape_id)
        
        # Vérifications
        if not etape.processValidation.peut_etre_valide_par(request.user):
            messages.error(request, "❌ Permission refusée.")
            return redirect_to_attachement(etape)
        
        if not etape.est_validee:
            messages.warning(request, "ℹ️ Cette étape n'est pas encore validée.")
            return redirect_to_attachement(etape)
        
        # Réinitialiser l'étape
        etape.est_validee = False
        etape.valide_par = None
        etape.date_validation = None
        etape.save()
        
        # Réinitialiser aussi les étapes suivantes
        etapes_suivantes = etape.processValidation.etapes.filter(ordre__gt=etape.ordre)
        etapes_suivantes.update(
            est_validee=False,
            valide_par=None,
            date_validation=None
        )
        
        messages.warning(request, f"🔄 Étape '{etape.nom}' réinitialisée. Le processus a repris depuis cette étape.")
        
    except EtapeValidation.DoesNotExist:
        messages.error(request, "❌ Étape non trouvée.")
    
    return redirect_to_attachement(etape)

@login_required
def supprimer_etape(request, etape_id):
    """Supprime une étape de validation"""
    try:
        etape = EtapeValidation.objects.get(id=etape_id)
        process_validation = etape.processValidation
        attachement_id = process_validation.attachement.id
        
        # Vérifications de sécurité
        if not process_validation.peut_etre_valide_par(request.user):
            messages.error(request, "❌ Permission refusée.")
            return redirect_to_attachement(etape)
        
        # Empêcher la suppression si l'étape est validée
        if etape.est_validee:
            messages.error(request, "❌ Impossible de supprimer une étape déjà validée.")
            return redirect_to_attachement(etape)
        
        # Empêcher la suppression si c'est la seule étape
        total_etapes = process_validation.etapes.count()
        if total_etapes <= 1:
            messages.error(request, "❌ Impossible de supprimer la dernière étape du processus.")
            return redirect_to_attachement(etape)
        
        # Sauvegarder le nom pour le message
        nom_etape = etape.nom
        
        # Supprimer l'étape
        etape.delete()
        
        # Réorganiser l'ordre des étapes restantes
        etapes_restantes = process_validation.etapes.order_by('ordre')
        for index, etape_restante in enumerate(etapes_restantes, start=1):
            if etape_restante.ordre != index:
                etape_restante.ordre = index
                etape_restante.save()

        process_validation.valider(request.user)
        
        messages.success(request, f"🗑️ Étape '{nom_etape}' supprimée avec succès.")
        
    except EtapeValidation.DoesNotExist:
        messages.error(request, "❌ Étape non trouvée.")
    
    return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)

def redirect_to_attachement(etape):
    """Redirige vers l'attachement parent de l'étape"""
    return redirect('projets:validation_technique_attachement', 
                   attachement_id=etape.processValidation.attachement.id)

@login_required
@require_POST
def transmettre_validation_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    _verifier_acces_attachement(request, attachement, {'BROUILLON'})

    try:
        with transaction.atomic():
            attachement.statut = 'SIGNE'
            attachement.save(update_fields=['statut', 'modifie_par'])
            attachement.marquer_modification(request.user)
            attachement.transmettre(request.user)
        messages.success(request, f"L'attachement {attachement.numero} a été transmis pour validation.")
    except Exception as e:
        messages.error(request, f"Erreur lors de la transmission : {str(e)}")

    return redirect('projets:modifier_attachement', attachement_id=attachement_id)

def telecharger_document_validation(request, etape_id):
    """Télécharge le document associé à une étape de validation"""
    etape = get_object_or_404(EtapeValidation, id=etape_id)
    
    if not etape.fichier:
        messages.error(request, "Aucun fichier associé à cette étape.")
        return redirect_to_attachement(etape)
    
    try:
        return download_document(request, 'EtapeValidation', etape_id)
    except Exception as e:
        messages.error(request, f"Erreur lors du téléchargement : {str(e)}")
        return redirect_to_attachement(etape)
# ------------------------ Views pour Décomptes ------------------------
@login_required
@modules_projet_required
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
            print(form.errors)
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

@modules_projet_required
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
    
    
    montant_s_ht = float(decompte.attachement.total_montant_ht) if decompte.attachement.total_montant_ht else 0.0
    revision_prix = float(decompte.montant_revision_prix) if decompte.montant_revision_prix else 0.0
    montant_s_revise = montant_s_ht + revision_prix
    montant_ht_precedent = float(decompte.attachement.montant_ht_attachement_precedent) if decompte.attachement.montant_ht_attachement_precedent else 0.0
    montant_t_ht = montant_s_revise - montant_ht_precedent
    tva = montant_t_ht * (float(decompte.taux_tva) or 0) / 100
    montant_t_ttc = montant_t_ht + tva
    rg = montant_t_ttc * float(decompte.taux_retenue_garantie or 0) / 100 if decompte.taux_retenue_garantie else 0.0
    ras = montant_t_ttc * float(decompte.taux_ras or 0) / 100 if decompte.taux_ras else 0.0
    autres = float(decompte.autres_retenues) if decompte.autres_retenues else 0.0 if decompte.autres_retenues else 0.0
    net_a_payer = montant_t_ttc - rg - ras - autres
    est_revise = revision_prix != 0
    # Calcul des pourcentages pour l'affichage
    context = {
        'decompte': decompte,
        'projet': projet,
        'est_revise': est_revise,
        'montant_s_ht': montant_s_ht,
        'revision_prix': revision_prix,
        'montant_s_revise': montant_s_revise,
        'montant_ht_precedent': montant_ht_precedent,
        'montant_t_ht': montant_t_ht,
        'tva': tva,
        'montant_t_ttc': montant_t_ttc,
        'rg': rg,
        'ras': ras,
        'autres': autres,
        'net_a_payer': net_a_payer
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
@modules_projet_required
def fiche_controle(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    attachements = Attachement.objects.filter(projet=projet).order_by('-date_etablissement')
    from projets.manager import LigneHierarchique
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
                if ligne_bordereau.montant_realise == 0:
                    continue
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
                
                # Construire la hiérarchie                
                
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
@modules_projet_required
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
                    
                    # Gestion agnostique du backend (R2/local)
                    fichier = request.FILES.get('fichier')
                    original_filename = request.POST.get('original_filename')
                    ordre.original_filename = original_filename
                    if fichier:
                        ordre.fichier = fichier
                        ordre.original_filename = fichier.name
                    if not ordre_a_modifier: # Création 
                        ordre.statut = 'BROUILLON'
                        
                    if 'supprimer_document' in request.POST and request.POST['supprimer_document'] == '1':
                        if ordre.fichier:
                            ordre.fichier.delete(save=False)
                            ordre.fichier = None
                            ordre.original_filename = None
                            
                    # validation avant sauvegarde
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

@modules_projet_required
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

@modules_projet_required
def modifier_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)

    if request.method == 'POST':
        form = OrdreServiceForm(request.POST, request.FILES, instance=ordre)
        if form.is_valid():
            ordre_modifie = form.save(commit=False)
            print('Fichier joint existe:', ordre_modifie.fichier is not None)
            print('Nom du fichier joint:', ordre_modifie.original_filename)
            # Gestion de la suppression du document
            if 'supprimer_document' in request.POST and request.POST['supprimer_document'] == '1':
                try:
                    ordre_modifie.fichier = None
                except Exception as e:
                    messages.error(request, f"Erreur lors de la suppression du document: {e}")
                    return redirect('projets:modifier_ordre_service', projet_id=projet.id, ordre_id=ordre.id)
                # ordre.document = None
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

@modules_projet_required
def supprimer_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
    
    if request.method == 'POST':
        reference = ordre.reference
        ordre.delete()
        messages.success(request, f"L'ordre de service {reference} a été supprimé avec succès.")
        return redirect('projets:ordres_service', projet_id=projet.id)
    
    # Si GET, afficher la confirmation
    context = {
        'projet': projet,
        'ordre': ordre,
    }
    return render(request, 'projets/ordres_service/supprimer_ordre_service.html', context)

@modules_projet_required
def details_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
    
    context = {
        'projet': projet,
        'ordre': ordre,
    }
    return render(request, 'projets/ordres_service/details_ordre_service.html', context)

@modules_projet_required
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

@modules_projet_required
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
    try:
        return download_document(request, 'OrdreService', ordre_id)
    except Exception as e:
        messages.error(request, f"❌ Erreur lors du telechargement: {e}")
        return redirect('projets:details_ordre_service', projet_id=ordre.projet.id, ordre_id=ordre.id)
