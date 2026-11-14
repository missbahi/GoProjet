import json
import mimetypes
import os

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.http import (
    FileResponse,
    HttpResponse,
    HttpResponseBadRequest,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

import logging

from projets.decorators import (
    est_gerant,
    gestion_utilisateurs_required,
    projets_accessibles,
)
from projets.forms import AvatarUpdateForm, UtilisateurCreationForm
from projets.models import Dossier, Profile
from projets.views.os_views.views import clean_url
from projets.utils.navigation import crumb
from projets.user_policy import (
    RETIRED_ROLES, dossiers_affectables, exiger_action_utilisateur,
    peut_agir_utilisateur, roles_assignables, utilisateurs_gerables,
)
from .forms import UtilisateurModificationForm


logger = logging.getLogger(__name__)
MAX_UPLOAD_SIZE = 5 * 1024 * 1024


def _user_form_response(request, template, context, status=200):
    return render(
        request, template,
        {**context, 'is_user_modal': request.headers.get('HX-Target') == 'user-modal-content'},
        status=status,
    )


def _user_modal_success(request, message):
    if request.headers.get('HX-Target') != 'user-modal-content':
        return None
    response = HttpResponse(status=204)
    response['HX-Trigger'] = json.dumps({'userModalSaved': {'message': message}})
    return response


# ============================================================
# UTILISATEURS — Liste, Création, Modification, Suppression
# ============================================================

@gestion_utilisateurs_required
def liste_utilisateurs(request):
    """Liste des utilisateurs accessibles."""
    user = request.user

    # ⚡ Queryset : superuser voit tout, gérant voit ses dossiers
    utilisateurs = utilisateurs_gerables(user)

    # ⚡ Optimization : précharger le profil
    utilisateurs = utilisateurs.select_related('profile').prefetch_related('dossiers').order_by('username')

    # ⚡ Filtres
    role_filter = request.GET.get('role', '').strip()
    if role_filter:
        if role_filter == 'SUPERUSER':
            utilisateurs = utilisateurs.filter(is_superuser=True)
        elif role_filter == 'INACTIF':
            utilisateurs = utilisateurs.filter(is_active=False)
        elif role_filter in {role for role, _ in Profile.ROLE_CHOICES} | {'A_RECLASSER'}:
            utilisateurs = utilisateurs.filter(profile__role=role_filter)

    # ⚡ Recherche
    search = request.GET.get('search', '').strip()
    if search and len(search) >= 2:
        utilisateurs = utilisateurs.filter(
            Q(username__icontains=search)
            | Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )

    # ⚡ Pagination
    paginator = Paginator(utilisateurs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    for target in page_obj:
        target.can_edit_account = peut_agir_utilisateur(user, target, 'edit')
        target.can_assign_projects = peut_agir_utilisateur(user, target, 'projects')
        target.can_delete_account = peut_agir_utilisateur(user, target, 'delete')

    context = {
        'utilisateurs': page_obj,
        'page_obj': page_obj,
        'role_filter': role_filter,
        'search': search,
        'breadcrumb_items': [crumb("Home", "projets:home"), crumb("Utilisateurs")],
    } 

    # ⚡ Rendu conditionnel HTMX
    if request.headers.get('HX-Request'):
        hx_target = request.headers.get('HX-Target', '')
        if hx_target == 'liste-utilisateurs-container':
            return render(
                request,
                'projets/utilisateurs/_liste_utilisateurs_table.html',
                context,
            )
        return render(
            request,
            'projets/utilisateurs/_liste_utilisateurs_content.html',
            context,
        )

    return render(request, 'projets/utilisateurs/liste_utilisateurs.html', context)


@gestion_utilisateurs_required
def ajouter_utilisateur(request):
    """Création d'un nouvel utilisateur."""
    if request.method == 'POST':
        form = UtilisateurCreationForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                new_user = form.save()
                modal_response = _user_modal_success(
                    request, f"Utilisateur « {new_user.username} » créé avec succès.",
                )
                if modal_response is not None:
                    return modal_response

                # ⚡ Succès HTMX : UNIQUEMENT dans le POST
                if request.headers.get('HX-Request'):
                    response = HttpResponse(status=200)
                    response['HX-Location'] = json.dumps({
                        'path': reverse('projets:liste_utilisateurs'),
                        'target': '#main-content',
                        'swap': 'innerHTML swap:150ms settle:150ms show:top',
                    })
                    response['HX-Trigger'] = json.dumps({
                        'showMessage': f"Utilisateur « {new_user.username} » créé avec succès.",
                        'messageType': 'success',
                    })
                    return response

                return redirect('projets:liste_utilisateurs')

            except Exception as exception:
                logger.exception("Erreur lors de la création de l'utilisateur")
                form.add_error(None, f"Erreur : {exception}")

        # ⚡ Formulaire invalide
        if request.headers.get('HX-Request'):
            return _user_form_response(
                request,
                'projets/utilisateurs/_ajouter_utilisateur_content.html',
                {'form': form},
                status=400,
            )
    else:
        form = UtilisateurCreationForm(user=request.user)

    # ⚡ GET : affichage du formulaire
    context = {'form': form}

    if request.headers.get('HX-Request'):
        return _user_form_response(
            request,
            'projets/utilisateurs/_ajouter_utilisateur_content.html',
            context,
        )
    return render(
        request,
        'projets/utilisateurs/ajouter_utilisateur.html',
        context,
    )


# ============================================================
# Helper pour le contexte de modifier_utilisateur
# ============================================================
def _modifier_utilisateur_context(
    request,
    target_user,
    can_manage_account_status,
    can_manage_roles,
    can_manage_user_dossiers,
):
    """Construit le contexte du formulaire de modification."""
    dossiers_disponibles = dossiers_affectables(request.user)
    role_choices = roles_assignables(request.user)

    return {
        'target_user': target_user,
        'dossiers': dossiers_disponibles,
        'role_choices': role_choices,
        'can_manage_account_status': can_manage_account_status,
        'can_manage_roles': can_manage_roles,
        'can_keep_current_role': target_user.profile.role in RETIRED_ROLES,
        'can_manage_user_dossiers': can_manage_user_dossiers,
        'can_manage_password': peut_agir_utilisateur(request.user, target_user, 'password'),
    }


@gestion_utilisateurs_required
def modifier_utilisateur(request, user_id):
    """Modification d'un utilisateur existant."""
    target_user = get_object_or_404(User, id=user_id)

    exiger_action_utilisateur(request.user, target_user, 'edit')

    # ⚡ Qui peut gérer quoi
    can_manage_account_status = (
        peut_agir_utilisateur(request.user, target_user, 'status')
    )
    can_manage_roles = (
        peut_agir_utilisateur(request.user, target_user, 'role')
    )
    can_manage_user_dossiers = (
        peut_agir_utilisateur(request.user, target_user, 'dossiers')
    )

    # ============================================================
    # ⚡ BLOC POST : traitement du formulaire
    # ============================================================
    if request.method == 'POST':
        form = UtilisateurModificationForm(
            request.POST, request.FILES, actor=request.user, target=target_user,
        )
        if not form.is_valid():
            context = _modifier_utilisateur_context(
                request, target_user, can_manage_account_status,
                can_manage_roles, can_manage_user_dossiers,
            )
            context['form_errors'] = form.errors
            template = (
                'projets/utilisateurs/_modifier_utilisateur_content.html'
                if request.headers.get('HX-Request')
                else 'projets/utilisateurs/modifier_utilisateur.html'
            )
            return _user_form_response(request, template, context, status=400)
        form.save()
        if target_user.pk == request.user.pk and form.cleaned_data.get('password'):
            update_session_auth_hash(request, target_user)

        modal_response = _user_modal_success(
            request, f"Utilisateur « {target_user.username} » modifié avec succès.",
        )
        if modal_response is not None:
            return modal_response

        # ⚡ Succès HTMX : UNIQUEMENT dans le POST
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=200)
            response['HX-Location'] = json.dumps({
                'path': reverse('projets:liste_utilisateurs'),
                'target': '#main-content',
                'swap': 'innerHTML swap:150ms settle:150ms show:top',
            })
            response['HX-Trigger'] = json.dumps({
                'showMessage': f"Utilisateur « {target_user.username} » modifié avec succès.",
                'messageType': 'success',
            })
            return response

        return redirect('projets:liste_utilisateurs')

    # ============================================================
    # ⚡ BLOC GET : affichage du formulaire
    # ============================================================
    context = _modifier_utilisateur_context(
        request,
        target_user,
        can_manage_account_status,
        can_manage_roles,
        can_manage_user_dossiers,
    )

    if request.headers.get('HX-Request'):
        return _user_form_response(
            request,
            'projets/utilisateurs/_modifier_utilisateur_content.html',
            context,
        )
    return render(
        request,
        'projets/utilisateurs/modifier_utilisateur.html',
        context,
    )


@gestion_utilisateurs_required
@require_POST
def supprimer_utilisateur(request, user_id):
    """Suppression d'un utilisateur."""
    target_user = get_object_or_404(User, id=user_id)

    exiger_action_utilisateur(request.user, target_user, 'delete')

    username = target_user.username
    target_user.delete()

    # ⚡ Succès HTMX
    if request.headers.get('HX-Request'):
        response = HttpResponse(status=200)
        response['HX-Location'] = json.dumps({
            'path': reverse('projets:liste_utilisateurs'),
            'target': '#main-content',
            'swap': 'innerHTML swap:150ms settle:150ms show:top',
        })
        response['HX-Trigger'] = json.dumps({
            'showMessage': f"Utilisateur « {username} » supprimé.",
            'messageType': 'success',
        })
        return response

    return redirect('projets:liste_utilisateurs')


@gestion_utilisateurs_required
def gerer_projets_utilisateur(request, user_id):
    """Gestion des projets affectés à un utilisateur."""
    utilisateur = get_object_or_404(User, id=user_id)

    exiger_action_utilisateur(request.user, utilisateur, 'projects')

    # ⚡ Projets accessibles au user connecté
    projets_autorises = projets_accessibles(request.user)

    # ⚡ Projets affectables
    tous_les_projets = projets_autorises.filter(
        dossier__in=utilisateur.dossiers.all()
    ).select_related('dossier').order_by('nom')

    # ⚡ Projets actuellement assignés
    projets_utilisateur = utilisateur.projets.filter(
        id__in=tous_les_projets.values('id')
    )
    projets_utilisateur_ids = set(projets_utilisateur.values_list('id', flat=True))

    # ============================================================
    # ⚡ BLOC POST : enregistrement
    # ============================================================
    if request.method == 'POST':
        projets_selectionnes = request.POST.getlist('projets')
        if (
            any(not str(pk).isdigit() for pk in projets_selectionnes)
            or tous_les_projets.filter(pk__in=projets_selectionnes).count()
            != len(set(projets_selectionnes))
        ):
            raise PermissionDenied("Vous ne pouvez affecter que des projets de votre périmètre.")
        projets_hors_perimetre = utilisateur.projets.exclude(
            id__in=tous_les_projets.values('id')
        )
        utilisateur.projets.set([
            *projets_hors_perimetre,
            *tous_les_projets.filter(id__in=projets_selectionnes),
        ])

        modal_response = _user_modal_success(
            request, f"Projets de {utilisateur.username} mis à jour.",
        )
        if modal_response is not None:
            return modal_response

        # ⚡ Succès HTMX : UNIQUEMENT dans le POST
        if request.headers.get('HX-Request'):
            response = HttpResponse(status=200)
            response['HX-Location'] = json.dumps({
                'path': reverse('projets:liste_utilisateurs'),
                'target': '#main-content',
                'swap': 'innerHTML swap:150ms settle:150ms show:top',
            })
            response['HX-Trigger'] = json.dumps({
                'showMessage': f"Projets de {utilisateur.username} mis à jour.",
                'messageType': 'success',
            })
            return response

        return redirect('projets:liste_utilisateurs')

    # ============================================================
    # ⚡ BLOC GET : affichage
    # ============================================================
    context = {
        'utilisateur': utilisateur,
        'tous_les_projets': tous_les_projets,
        'projets_utilisateur': projets_utilisateur,
        'projets_utilisateur_ids': projets_utilisateur_ids,
    }

    if request.headers.get('HX-Request'):
        return _user_form_response(
            request,
            'projets/utilisateurs/_gerer_projets_utilisateur_content.html',
            context,
        )
    return render(
        request,
        'projets/utilisateurs/gerer_projets_utilisateur.html',
        context,
    )


# ============================================================
# AUTRES VUES UTILISATEUR (avatar, profil, mot de passe)
# ============================================================

def serve_avatar(request, filename):
    """Sert un avatar depuis le storage."""
    avatar_name = f'avatars/{os.path.basename(filename)}'
    if not default_storage.exists(avatar_name):
        return redirect(default_storage.url('avatars/default.jpeg'))

    avatar_url = clean_url(default_storage.url(avatar_name), replace_https=False)
    if avatar_url.startswith('/'):
        return FileResponse(
            default_storage.open(avatar_name, 'rb'),
            content_type=mimetypes.guess_type(avatar_name)[0] or 'image/jpeg',
        )
    return redirect(avatar_url)


@login_required
@require_POST
def set_theme(request):
    """Sauvegarde la préférence de thème de l'utilisateur."""
    theme = request.POST.get('theme', 'dark')
    if theme not in ('dark', 'light'):
        return JsonResponse(
            {'success': False, 'error': 'Thème invalide'}, status=400
        )

    try:
        profile = request.user.profile
        profile.theme = theme
        profile.save(update_fields=['theme'])
        return JsonResponse({'success': True, 'theme': theme})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
def upload_avatar(request):
    """Upload d'avatar (via modal profil)."""
    if request.method == 'POST':
        avatar_file = request.FILES.get('avatar')
        if not avatar_file:
            response = HttpResponse(status=400)
            response['HX-Trigger'] = json.dumps({
                'showMessage': 'Veuillez sélectionner un fichier image à uploader.',
                'messageType': 'error',
            })
            return response

        if avatar_file.size > MAX_UPLOAD_SIZE:
            max_mb = MAX_UPLOAD_SIZE / (1024 * 1024)
            error_msg = (
                f'La taille du fichier ({avatar_file.size / (1024 * 1024):.2f} Mo) '
                f'dépasse la limite autorisée de {max_mb:.0f} Mo.'
            )
            response = HttpResponse(status=400)
            response['HX-Trigger'] = json.dumps({
                'showMessage': error_msg,
                'messageType': 'error',
            })
            return response

        try:
            profile = request.user.profile
            profile.avatar = avatar_file
            profile.save()
            response = HttpResponse(status=200)
            response['HX-Trigger'] = json.dumps({
                'avatarUpdated': True,
                'closeModal': True,
                'showMessage': 'Photo de profil mise à jour avec succès !',
                'messageType': 'success',
            })
            return response
        except Exception as exception:
            response = HttpResponse(status=500)
            response['HX-Trigger'] = json.dumps({
                'showMessage': f"Une erreur s'est produite lors de l'upload : {exception}",
                'messageType': 'error',
            })
            return response

    return redirect('home')


@login_required
def avatar_upload_modal(request):
    """Modal d'upload d'avatar."""
    return render(
        request,
        'projets/profile/avatar_upload_modal.html',
        {'user': request.user},
    )


@login_required
def profile_view(request):
    """Page de profil (obsolète)."""
    profile = request.user.profile
    if request.method == 'POST':
        form = AvatarUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Votre avatar a été mis à jour!')
            return redirect('profile')
    else:
        form = AvatarUpdateForm(instance=profile)
    return render(request, 'projets/profile/profile.html', {'form': form, 'profile': profile})


@login_required
def profile_update(request):
    """Mise à jour du profil (via modal)."""
    if request.method == 'POST':
        try:
            user = request.user
            profile = user.profile
            if 'avatar' in request.FILES:
                if request.FILES['avatar'].size > MAX_UPLOAD_SIZE:
                    return HttpResponseBadRequest("L'image ne doit pas dépasser 5MB")
                profile.avatar = request.FILES['avatar']
                profile.save()

            user.email = request.POST.get('email', user.email)
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.save()

            return HttpResponse(
                status=204,
                headers={'HX-Trigger': json.dumps({
                    'profileUpdated': True,
                    'closeModal': True,
                    'showMessage': 'Profil mis à jour avec succès',
                })},
            )
        except Exception as exception:
            return HttpResponseBadRequest(f'Erreur: {exception}')
    return HttpResponseBadRequest('Méthode non autorisée')


@login_required
def profile_modal(request):
    """Modal de profil."""
    return render(
        request,
        'projets/profile/profile_modal.html',
        {'user': request.user},
    )


@login_required
def password_modal(request):
    """Modal de changement de mot de passe."""
    return render(request, 'projets/profile/password_modal.html')


@login_required
def password_change(request):
    """Changement de mot de passe."""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            try:
                user = form.save()
                update_session_auth_hash(request, user)
                logger.info('Password changed for %s', user.username)
                return redirect('home')
            except Exception:
                logger.exception(
                    'Password change failed for %s', request.user.username
                )
                messages.error(
                    request, 'Erreur lors du changement de mot de passe'
                )
    else:
        form = PasswordChangeForm(request.user)
    return render(
        request, 'projets/profile/password_change.html', {'form': form}
    )