import os
import logging
from decimal import Decimal

from botocore.exceptions import BotoCoreError, ClientError
from django.contrib import messages
from django.db import DatabaseError
from django.db.models import Sum, Value
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from projets.decorators import modules_projet_required
from projets.models import Dossier, FichierSuivi, Projet, SuiviExecution
from projets.forms import SuiviExecutionAjoutForm, SuiviExecutionForm
from projets.utils.navigation import crumb, project_crumbs
from projets.views.os_views.views import delete_document, download_document

logger = logging.getLogger(__name__)


@modules_projet_required
def suivi_execution(request, projet_id):
    projet = get_object_or_404(Projet.objects.select_related('dossier'), id=projet_id)
    suivis = projet.suivis_execution.all().prefetch_related('fichiers')

    rapports_journaliers = []
    if projet.dossier_id and projet.dossier.activite == Dossier.Activite.TRAVAUX:
        rapports_journaliers = projet.rapports_journaliers.annotate(
            total_depenses_annotated=Coalesce(
                Sum('depenses__montant'), Value(Decimal('0.00'))
            )
        )[:10]

    ctx = {
        'projet': projet,
        'suivis': suivis,
        'form': SuiviExecutionAjoutForm(initial={'date': timezone.localdate()}),
        'rapports_journaliers': rapports_journaliers,
        'breadcrumb_items': project_crumbs(projet, crumb("Suivi exécution")),
    }
    # ⚡ Rendu conditionnel HTMX
    if request.headers.get('HX-Request'):
        return render(request, 'projets/suivi/_suivi_execution_content.html', ctx)

    return render(request, 'projets/suivi/suivi_execution.html', ctx)


@modules_projet_required
def ajouter_suivi(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)

    if request.method == 'POST':
        form = SuiviExecutionAjoutForm(request.POST, request.FILES)
        if not form.is_valid():
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False, 'errors': form.errors.get_json_data(),
                    'message': "Veuillez corriger les erreurs du formulaire.",
                }, status=400)
            return render(request, 'projets/suivi/suivi_execution.html', {
                'projet': projet, 'suivis': projet.suivis_execution.all().prefetch_related('fichiers'),
                'form': form, 'breadcrumb_items': project_crumbs(projet, crumb("Suivi exécution")),
            }, status=400)
        suivi = form.save(commit=False)
        suivi.projet = projet
        suivi.save()
        fichiers_ajoutes = 0
        for fichier in form.cleaned_data['fichiers']:
            try:
                FichierSuivi.objects.create(
                    suivi=suivi, fichier=fichier, original_filename=fichier.name,
                )
                fichiers_ajoutes += 1
            except (OSError, BotoCoreError, ClientError, DatabaseError):
                logger.exception("Échec d'ajout du fichier %s au suivi %s", fichier.name, suivi.pk)
                message = (
                    f"Le suivi est enregistré avec {fichiers_ajoutes} fichier(s) joint(s), "
                    f"mais l'envoi de « {fichier.name} » a échoué. "
                    "Ouvrez la gestion des fichiers pour ajouter les fichiers manquants ; "
                    "ne créez pas à nouveau ce suivi."
                )
                url = reverse('projets:ajouter_fichier_suivi', args=[projet_id, suivi.pk])
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False, 'saved': True, 'url': url, 'message': message,
                    }, status=500)
                messages.error(request, message)
                return redirect(url)
        action = request.POST.get('action')

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            if action == 'save_and_open_files':
                url = reverse('projets:ajouter_fichier_suivi', args=[projet_id, suivi.id])
            else:
                url = reverse('projets:suivi_execution', args=[projet_id])
            return JsonResponse({
                'success': True, 'url': url,
                'open_files': action == 'save_and_open_files',
                'message': "Le suivi a été enregistré avec succès.",
            })

        if action == 'save_and_open_files':
            return redirect('projets:ajouter_fichier_suivi', projet_id=projet_id, suivi_id=suivi.id)
        elif action == 'save_and_close':
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
    ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method == 'POST':
        form = SuiviExecutionForm(request.POST, instance=suivi, auto_id='edit_%s')
        if form.is_valid():
            suivi = form.save(commit=False)
            suivi.date_modification = timezone.now()
            suivi.save()
            if ajax:
                return JsonResponse({
                    'success': True,
                    'url': reverse('projets:suivi_execution', args=[projet_id]),
                    'message': "Le suivi a été modifié avec succès.",
                })
            messages.success(request, "Le suivi a été modifié avec succès.")
            return redirect('projets:suivi_execution', projet_id=projet_id)
        if ajax:
            return JsonResponse({
                'success': False, 'errors': form.errors.get_json_data(),
                'message': "Veuillez corriger les erreurs du formulaire.",
            }, status=400)
    else:
        form = SuiviExecutionForm(instance=suivi, auto_id='edit_%s')

    context = {
        'projet': projet,
        'suivi': suivi,
        'form': form,
        'editing': True,
        'breadcrumb_items': project_crumbs(
            projet, crumb("Suivi exécution", "projets:suivi_execution", args=[projet_id]),
            crumb("Modifier le suivi"),
        ),
    }
    template = 'projets/suivi/_modifier_suivi_content.html' if request.headers.get('HX-Request') else 'projets/suivi/modifier_suivi.html'
    return render(request, template, context, status=400 if form.errors else 200)


@modules_projet_required
def afficher_fichier_suivi(request, fichier_id):
    """
    Vue pour afficher/télécharger un fichier de suivi
    """
    try:
        fichier_suivi = get_object_or_404(FichierSuivi, id=fichier_id)
        if not fichier_suivi.fichier or not fichier_suivi.fichier.url:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'error': 'Fichier introuvable'})

            messages.error(request, "Le fichier demandé est introuvable.")
            return redirect('projets:suivi_execution', projet_id=fichier_suivi.suivi.projet.id)

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
            if fichier.size > 10 * 1024 * 1024:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'error': f"Le fichier {fichier.name} dépasse la taille maximale de 10MB"
                    })
                messages.error(request, f"Le fichier {fichier.name} dépasse la taille maximale de 10MB.")
                continue

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
                return JsonResponse({'success': False, 'error': "Aucun fichier n'a pu être ajouté"})
            messages.error(request, "Aucun fichier n'a pu être ajouté.")

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'redirect': False})

        return redirect('projets:suivi_execution', projet_id=projet_id)

    context = {
        'projet': projet,
        'suivi': suivi,
    }
    return render(request, 'projets/suivi/ajouter_fichier_suivi.html', context)
