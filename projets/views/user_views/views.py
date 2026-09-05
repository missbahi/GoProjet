import json
import mimetypes
import os

from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.core.exceptions import PermissionDenied
from django.core.files.storage import default_storage
from django.http import FileResponse, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

import logging

from projets.decorators import est_gerant, gestion_utilisateurs_required, projets_accessibles
from projets.forms import AvatarUpdateForm, UtilisateurCreationForm
from projets.models import Dossier, Profile
from projets.views.os_views.views import  clean_url

from django.contrib.auth.models import User

logger = logging.getLogger(__name__)
MAX_UPLOAD_SIZE = 5 * 1024 * 1024

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
            except Exception as exception:
                print(f"Erreur lors de la création de l'utilisateur: {exception}")
                form.add_error(None, "Une erreur est survenue lors de la création de l'utilisateur.")
        else:
            print('Erreurs de formulaire:')
            print(form.errors)
    else:
        form = UtilisateurCreationForm(user=request.user)

    return render(request, 'projets/utilisateurs/ajouter_utilisateur.html', {'form': form})


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
        projets_selectionnes = request.POST.getlist('projets')
        utilisateur.projets.set(projets_autorises.filter(id__in=projets_selectionnes))
        messages.success(request, f'Les projets de {utilisateur.username} ont été mis à jour avec succès.')
        return redirect('projets:liste_utilisateurs')

    return render(request, 'projets/utilisateurs/gerer_projets_utilisateur.html', {
        'utilisateur': utilisateur,
        'tous_les_projets': tous_les_projets,
        'projets_utilisateur': projets_utilisateur,
    })


def serve_avatar(request, filename):
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
def upload_avatar(request):
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
            error_msg = f'La taille du fichier ({avatar_file.size / (1024 * 1024):.2f} Mo) dépasse la limite autorisée de {max_mb:.0f} Mo.'
            response = HttpResponse(status=400)
            response['HX-Trigger'] = json.dumps({'showMessage': error_msg, 'messageType': 'error'})
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
    return render(request, 'projets/modals/avatar_upload_modal.html', {'user': request.user})


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
            if 'avatar' in request.FILES:
                if request.FILES['avatar'].size > MAX_UPLOAD_SIZE:
                    return HttpResponseBadRequest("L'image ne doit pas dépasser 5MB")
                profile.avatar = request.FILES['avatar']
                profile.save()

            user.email = request.POST.get('email', user.email)
            user.first_name = request.POST.get('first_name', user.first_name)
            user.last_name = request.POST.get('last_name', user.last_name)
            user.save()

            return HttpResponse(status=204, headers={'HX-Trigger': json.dumps({
                'profileUpdated': True,
                'closeModal': True,
                'showMessage': 'Profil mis à jour avec succès',
            })})
        except Exception as exception:
            return HttpResponseBadRequest(f'Erreur: {exception}')
    return HttpResponseBadRequest('Méthode non autorisée')


@login_required
def profile_modal(request):
    return render(request, 'projets/modals/profile_modal.html', {'user': request.user})


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
                logger.info('Password changed for %s', user.username)
                return redirect('home')
            except Exception:
                logger.exception('Password change failed for %s', request.user.username)
                messages.error(request, 'Erreur lors du changement de mot de passe')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'projets/password_change.html', {'form': form})