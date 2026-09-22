"""
Vues pour la gestion des ateliers rattachés à un projet.
"""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from projets.decorators import chef_projet_required
from projets.forms import AffectationRessourceForm, AtelierForm
from projets.models import AffectationRessource, Atelier, Materiel, Projet


# ============================================================
# Liste des ateliers d'un projet
# ============================================================

@chef_projet_required
def ateliers_projet(request, projet_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Méthode non supportée'}, status=405)
    projet = get_object_or_404(Projet, id=projet_id)
    ateliers = (
        Atelier.objects
        .filter(projet=projet)
        .prefetch_related('affectations')
        .order_by('code')
    )
    return render(request, 'projets/ateliers/liste.html', {
        'projet': projet,
        'ateliers': ateliers,
    })

# ============================================================
# Ajout d'un atelier
# ============================================================

@chef_projet_required
def ajouter_atelier(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)

    if request.method == 'POST':
        form = AtelierForm(request.POST, projet=projet)
        if form.is_valid():
            atelier = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f"Atelier « {atelier.libelle} » ajouté avec succès.",
                })
            messages.success(request, f"Atelier « {atelier.libelle} » ajouté avec succès.")
            return redirect('projets:ateliers_projet', projet_id=projet.id)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'errors': form.errors.get_json_data()},
                status=400,
            )
    else:
        form = AtelierForm(projet=projet)

    return render(request, 'projets/ateliers/liste.html', {
        'projet': projet,
        'form': form,
    })


# ============================================================
# Modification d'un atelier
# ============================================================

@chef_projet_required
def modifier_atelier(request, projet_id, atelier_id):
    projet = get_object_or_404(Projet, id=projet_id)
    atelier = get_object_or_404(Atelier, id=atelier_id, projet=projet)

    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non supportée'}, status=405)

    form = AtelierForm(request.POST, instance=atelier, projet=projet)

    if form.is_valid():
        atelier = form.save()
        if request.GET.get('modal') == 'true':
            return JsonResponse({
                'success': True,
                'message': f"Atelier « {atelier.libelle} » modifié avec succès.",
            })
        messages.success(request, f"Atelier « {atelier.libelle} » modifié avec succès.")
        return redirect('projets:ateliers_projet', projet_id=projet.id)

    if request.GET.get('modal') == 'true':
        return JsonResponse(
            {'success': False, 'errors': form.errors.get_json_data()},
            status=400,
        )

    return render(request, 'projets/ateliers/liste.html', {
        'projet': projet,
        'form': form,
        'atelier': atelier,
    })


# ============================================================
# Suppression d'un atelier
# ============================================================

@chef_projet_required
def supprimer_atelier(request, projet_id, atelier_id):
    projet = get_object_or_404(Projet, id=projet_id)
    atelier = get_object_or_404(Atelier, id=atelier_id, projet=projet)
    libelle = atelier.libelle

    # Protection : refuser la suppression si des ressources ou relevés y sont rattachés
    if atelier.affectations.exists() or atelier.releves.exists():
        message = (
            f"Impossible de supprimer « {libelle} » : "
            f"des ressources ou des relevés y sont rattachés."
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect('projets:ateliers_projet', projet_id=projet.id)

    atelier.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f"Atelier « {libelle} » supprimé avec succès.",
        })
    messages.success(request, f"Atelier « {libelle} » supprimé avec succès.")
    return redirect('projets:ateliers_projet', projet_id=projet.id)


# ============================================================
# Gestion des matériels affectés à un atelier
# ============================================================

@chef_projet_required
def materiels_atelier(request, projet_id, atelier_id):
    if request.method != 'GET':
        return JsonResponse({'error': 'Méthode non supportée'}, status=405)
    projet = get_object_or_404(Projet, id=projet_id)
    atelier = get_object_or_404(Atelier, id=atelier_id, projet=projet)
    affectations = (
        AffectationRessource.objects
        .filter(atelier=atelier)
        .select_related('materiel', 'materiel__type_materiel')
        .order_by('-date_debut', 'materiel__designation')
    )
    materiels_disponibles = (
        Materiel.objects.filter(actif=True)
        .select_related('type_materiel')
        .order_by('designation')
    )
    return render(request, 'projets/ateliers/materiels.html', {
        'projet': projet,
        'atelier': atelier,
        'affectations': affectations,
        'materiels_disponibles': materiels_disponibles,
    })

@chef_projet_required
def ajouter_affectation(request, projet_id, atelier_id):
    projet = get_object_or_404(Projet, id=projet_id)
    atelier = get_object_or_404(Atelier, id=atelier_id, projet=projet)

    if request.method == 'POST':
        form = AffectationRessourceForm(request.POST, atelier=atelier)
        if form.is_valid():
            affectation = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': f"Matériel « {affectation.materiel.designation} » affecté à l'atelier.",
                })
            messages.success(request, f"Matériel « {affectation.materiel.designation} » affecté.")
            return redirect('projets:materiels_atelier', projet_id=projet.id, atelier_id=atelier.id)

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse(
                {'success': False, 'errors': form.errors.get_json_data()},
                status=400,
            )
    else:
        form = AffectationRessourceForm(atelier=atelier)

    return render(request, 'projets/ateliers/materiels.html', {
        'projet': projet,
        'atelier': atelier,
        'form': form,
    })


@chef_projet_required
def modifier_affectation(request, projet_id, atelier_id, affectation_id):
    projet = get_object_or_404(Projet, id=projet_id)
    atelier = get_object_or_404(Atelier, id=atelier_id, projet=projet)
    affectation = get_object_or_404(AffectationRessource, id=affectation_id, atelier=atelier)

    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non supportée'}, status=405)

    form = AffectationRessourceForm(request.POST, instance=affectation, atelier=atelier)

    if form.is_valid():
        affectation = form.save()
        if request.GET.get('modal') == 'true':
            return JsonResponse({
                'success': True,
                'message': f"Affectation de « {affectation.materiel.designation} » modifiée.",
            })
        messages.success(request, "Affectation modifiée avec succès.")
        return redirect('projets:materiels_atelier', projet_id=projet.id, atelier_id=atelier.id)

    if request.GET.get('modal') == 'true':
        return JsonResponse(
            {'success': False, 'errors': form.errors.get_json_data()},
            status=400,
        )

    materiels_disponibles = (
        Materiel.objects.filter(actif=True)
        .select_related('type_materiel')
        .order_by('designation')
    )
    return render(request, 'projets/ateliers/materiels.html', {
        'projet': projet,
        'atelier': atelier,
        'form': form,
        'affectation': affectation,
        'materiels_disponibles': materiels_disponibles,
    })

@chef_projet_required
def supprimer_affectation(request, projet_id, atelier_id, affectation_id):
    projet = get_object_or_404(Projet, id=projet_id)
    atelier = get_object_or_404(Atelier, id=atelier_id, projet=projet)
    affectation = get_object_or_404(AffectationRessource, id=affectation_id, atelier=atelier)
    designation = affectation.materiel.designation

    affectation.delete()

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f"Affectation de « {designation} » retirée avec succès.",
        })
    messages.success(request, f"Affectation de « {designation} » retirée avec succès.")
    return redirect('projets:materiels_atelier', projet_id=projet.id, atelier_id=atelier.id)