import mimetypes
import os
import urllib.parse
from datetime import datetime

import requests
from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import (
    FileResponse,
    Http404,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
    HttpResponseNotFound,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from projets.decorators import can_view_projet, modules_projet_required
from projets.forms import DocumentAdministratifForm, OrdreServiceForm
from projets.models import DocumentAdministratif, OrdreService, Projet, TypeOrdreService


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
    elif hasattr(instance, 'processValidation'):
        return instance.processValidation.attachement.projet
    elif hasattr(instance, 'situation'):
        return instance.situation.projet
    return None


def clean_url(url, replace_https=True):
    """Nettoie l'URL en supprimant les espaces et forçant le https"""
    if not url:
        return url
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

    obj = get_object_or_404(model, id=object_id)
    if not obj:
        return HttpResponseNotFound("Objet non trouvé")

    projet = get_projet_from_instance(obj)
    user = request.user

    if not projet:
        return HttpResponseForbidden("Projet non trouvé pour cet objet")
    if user not in projet.users.all():
        return HttpResponseForbidden("Accès refusé au projet associé")

    file_field = get_file_field(obj)
    if not file_field:
        return HttpResponseForbidden("Aucun fichier lié à cet objet")

    force_download = request.GET.get('download', 'false').lower() == 'true'

    if force_download:
        if hasattr(obj, 'original_filename') and obj.original_filename:
            original_filename = obj.original_filename
        else:
            original_filename = os.path.basename(getattr(file_field, 'name', 'fichier'))
        return serve_file_with_original_name(file_field, original_filename)
    else:
        url = clean_url(file_field.url)
        return HttpResponseRedirect(url)


def download_document(request, model_name, object_id):
    model = apps.get_model('projets', model_name)
    if not model:
        return HttpResponseForbidden("Modèle non reconnu")

    obj = get_object_or_404(model, id=object_id)
    if not obj:
        return HttpResponseNotFound("Objet non trouvé")

    projet = get_projet_from_instance(obj)
    user = request.user

    if not projet:
        return HttpResponseForbidden("Projet non trouvé pour cet objet")
    if user not in projet.users.all():
        return HttpResponseForbidden("Accès refusé au projet associé")

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
        return False, "Modèle non reconnu"

    obj = get_object_or_404(model, id=object_id)
    if not obj:
        return False, "Objet non rencontré"

    projet = get_projet_from_instance(obj)
    user = request.user

    if not projet:
        return False, "Projet non rencontré pour cet objet"
    if user not in projet.users.all():
        return False, "Accès refusé au projet associé"

    file_field = get_file_field(obj)
    if not file_field:
        return False, "Aucun fichier lié à cet objet"

    try:
        file_name = getattr(file_field, 'name', '')
        file_field.delete(save=False)
        return True, f"Fichier supprimé: {file_name}"
    except Exception as e:
        return False, f"Erreur suppression fichier: {e}"


def serve_file_with_original_name(file_field, original_filename):
    """Télécharge le fichier avec le nom original (tous backends)."""
    try:
        file_url = clean_url(file_field.url)

        if file_url.startswith('/'):
            response = FileResponse(
                file_field.open('rb'),
                content_type=mimetypes.guess_type(original_filename)[0]
                or 'application/octet-stream',
            )
            encoded_filename = urllib.parse.quote(original_filename)
            response['Content-Disposition'] = (
                f'attachment; filename="{encoded_filename}"; '
                f'filename*=UTF-8\'\'{encoded_filename}'
            )
            return response

        response = requests.get(file_url, stream=True)
        response.raise_for_status()

        django_response = HttpResponse(
            response.iter_content(chunk_size=8192),
            content_type=response.headers.get('content-type', 'application/octet-stream'),
        )

        encoded_filename = urllib.parse.quote(original_filename)
        django_response['Content-Disposition'] = (
            f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        )
        return django_response

    except Exception as e:
        print(f"Erreur téléchargement: {e}")
        return HttpResponseRedirect(file_field.url)


# ------ Documents et Suivi ------
@login_required
@modules_projet_required
def documents_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    documents = projet.documents_administratifs.all()
    return render(
        request,
        'projets/documents_administratifs.html',
        {'projet': projet, 'documents': documents},
    )


@modules_projet_required
def supprimer_document(request, projet_id, document_id):
    if request.method == 'POST':
        document = get_object_or_404(DocumentAdministratif, id=document_id, projet_id=projet_id)
        nom_document = document.type_document

        try:
            document.delete()
            messages.success(request, f"Le document '{nom_document}' a été supprimé avec succès.")
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression du document: {str(e)}")

        return redirect('projets:documents', projet_id=projet_id)

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

            if not type_document or not fichier:
                messages.error(request, "Le type de document et le fichier sont obligatoires.")
                return redirect('projets:documents', projet_id=projet_id)

            if fichier.size > 10 * 1024 * 1024:
                messages.error(request, "Le fichier ne doit pas dépasser 10MB.")
                return redirect('projets:documents', projet_id=projet_id)

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
        if 'notifier_os' in request.POST:
            ordre_id = request.POST.get('notifier_os')
            ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
            try:
                ordre.statut = 'NOTIFIE'
                ordre.full_clean()
                ordre.save()
                messages.success(request, f"L'ordre de service {ordre.reference} a été notifié avec succès.")
            except ValidationError as e:
                messages.error(request, f"Erreur lors de la notification: {e}")

            return redirect('projets:ordres_service', projet_id=projet.id)

        elif 'annuler_os' in request.POST:
            ordre_id = request.POST.get('annuler_os')
            ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)
            ordre.statut = 'ANNULE'
            ordre.save()
            messages.success(request, f"L'ordre de service {ordre.reference} a été annulé.")
            return redirect('projets:ordres_service', projet_id=projet.id)

        else:
            form = OrdreServiceForm(request.POST, request.FILES, instance=ordre_a_modifier, projet=projet)

            if form.is_valid():
                try:
                    ordre = form.save(commit=False)
                    ordre.projet = projet

                    fichier = request.FILES.get('fichier')
                    original_filename = request.POST.get('original_filename')
                    ordre.original_filename = original_filename
                    if fichier:
                        ordre.fichier = fichier
                        ordre.original_filename = fichier.name
                    if not ordre_a_modifier:
                        ordre.statut = 'BROUILLON'

                    if 'supprimer_document' in request.POST and request.POST['supprimer_document'] == '1':
                        if ordre.fichier:
                            ordre.fichier = None
                            ordre.original_filename = None

                    if ordre.statut == 'NOTIFIE':
                        ordre.full_clean()

                    ordre.save()

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

    os_notifies = ordres_service.filter(statut='NOTIFIE')
    os_brouillons = ordres_service.filter(statut='BROUILLON')
    os_annules = ordres_service.filter(statut='ANNULE')

    if not projet.ordres_service.filter(type_os__code='OSN', statut='NOTIFIE').exists():
        codes_autorises = ['OSN']
    elif not projet.ordres_service.filter(type_os__code='OSC', statut='NOTIFIE').exists():
        codes_autorises = ['OSC']
    else:
        dernier_os = projet.ordres_service.filter(statut='NOTIFIE').order_by('-ordre_sequence').first()
        dernier_os_type = dernier_os.type_os.code if dernier_os and dernier_os.type_os else None
        if dernier_os_type in ['OSC', 'OSR']:
            codes_autorises = ['OSA', 'OSC10', 'OSV', 'AUTRE']
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
            'date_reference': date_reference,
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
            if 'supprimer_document' in request.POST and request.POST['supprimer_document'] == '1':
                try:
                    ordre_modifie.fichier = None
                except Exception as e:
                    messages.error(request, f"Erreur lors de la suppression du document: {e}")
                    return redirect('projets:modifier_ordre_service', projet_id=projet.id, ordre_id=ordre.id)
            ordre_modifie.save()
            messages.success(request, f"L'ordre de service {ordre_modifie.reference} a été modifié avec succès.")
            return redirect('projets:ordres_service', projet_id=projet.id)
    else:
        form = OrdreServiceForm(instance=ordre)

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
            if ordre.statut != 'BROUILLON':
                messages.error(request, "Seuls les ordres de service en brouillon peuvent être notifiés.")
                return redirect('projets:ordres_service', projet_id=projet.id)

            ordre.statut = 'NOTIFIE'
            ordre.full_clean()
            ordre.save()

            messages.success(request, f"L'ordre de service {ordre.reference} a été notifié avec succès.")

        except ValidationError as e:
            error_details = []
            for field, errors in e.error_dict.items():
                for error in errors:
                    if field == '__all__':
                        error_details.append(str(error))
                    else:
                        error_details.append(f"{field}: {str(error)}")

            error_message = " | ".join(error_details)
            messages.error(request, f"Impossible de notifier: {error_message}")

            ordre.statut = 'BROUILLON'
            ordre.save()

        except Exception as e:
            messages.error(request, f"Erreur inattendue: {e}")
    return redirect('projets:ordres_service', projet_id=projet.id)


@modules_projet_required
def annuler_ordre_service(request, projet_id, ordre_id):
    projet = get_object_or_404(Projet, id=projet_id)
    ordre = get_object_or_404(OrdreService, id=ordre_id, projet=projet)

    if request.method == 'POST':
        if ordre.statut == 'ANNULE':
            messages.warning(request, f"L'ordre de service {ordre.reference} est déjà annulé.")
            return redirect('projets:ordres_service', projet_id=projet.id)

        try:
            ancien_statut = ordre.statut
            ordre.statut = 'ANNULE'
            ordre.save()

            if ancien_statut == 'NOTIFIE':
                messages.warning(
                    request,
                    f"L'ordre de service {ordre.reference} a été annulé. "
                    "Cela peut affecter la séquence des OS suivants.",
                )
            else:
                messages.info(request, f"L'ordre de service {ordre.reference} a été annulé.")

        except Exception as e:
            messages.error(request, f"Erreur lors de l'annulation: {e}")

    return redirect('projets:details_ordre_service', projet_id=projet.id, ordre_id=ordre.id)


def telecharger_document_os(request, ordre_id):
    ordre = get_object_or_404(OrdreService, id=ordre_id)
    try:
        return download_document(request, 'OrdreService', ordre_id)
    except Exception as e:
        messages.error(request, f"Erreur lors du téléchargement: {e}")
        return redirect('projets:details_ordre_service', projet_id=ordre.projet.id, ordre_id=ordre.id)
