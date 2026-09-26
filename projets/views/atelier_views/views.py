"""
Vues pour la gestion des ateliers rattachés à un projet.
"""

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from datetime import date, timedelta
from collections import defaultdict


from projets.decorators import chef_projet_required
from projets.forms import AffectationRessourceForm, AtelierForm
from projets.models import AffectationRessource, Atelier, Materiel, Projet
from projets.utils.utils import ajax_response, is_ajax

from calendar import monthrange
from django.db.models.functions import Coalesce
from django.db.models import Value

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

    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non supportée'}, status=405)

    form = AtelierForm(request.POST, projet=projet)

    if form.is_valid():
        atelier = form.save()
        if is_ajax(request):
            return ajax_response(
                success=True,
                message=f"Atelier « {atelier.libelle} » ajouté avec succès.",
            )
        messages.success(request, f"Atelier « {atelier.libelle} » ajouté avec succès.")
        return redirect('projets:ateliers_projet', projet_id=projet.id)

    # Erreurs de validation
    if is_ajax(request):
        return ajax_response(
            success=False,
            message="Veuillez corriger les erreurs du formulaire.",
            errors=form.errors.get_json_data(),
            status=400,
        )

    return render(request, 'projets/ateliers/liste.html', {
        'projet': projet,
        'form': form,
        'ateliers': Atelier.objects.filter(projet=projet).prefetch_related('affectations'),
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
        if is_ajax(request):
            return ajax_response(
                success=True,
                message=f"Atelier « {atelier.libelle} » modifié avec succès.",
            )
        messages.success(request, f"Atelier « {atelier.libelle} » modifié avec succès.")
        return redirect('projets:ateliers_projet', projet_id=projet.id)

    if is_ajax(request):
        return ajax_response(
            success=False,
            message="Veuillez corriger les erreurs du formulaire.",
            errors=form.errors.get_json_data(),
            status=400,
        )

    return render(request, 'projets/ateliers/liste.html', {
        'projet': projet,
        'form': form,
        'atelier': atelier,
        'ateliers': Atelier.objects.filter(projet=projet).prefetch_related('affectations'),
    })

# ============================================================
# Suppression d'un atelier
# ============================================================

@chef_projet_required
def supprimer_atelier(request, projet_id, atelier_id):
    projet = get_object_or_404(Projet, id=projet_id)
    atelier = get_object_or_404(Atelier, id=atelier_id, projet=projet)
    libelle = atelier.libelle

    # Protection : refuser la suppression si des dépendances existent
    if atelier.affectations.exists() or atelier.releves.exists():
        message = (
            f"Impossible de supprimer « {libelle} » : "
            f"des ressources ou des relevés y sont rattachés."
        )
        if is_ajax(request):
            return ajax_response(success=False, message=message, status=400)
        messages.error(request, message)
        return redirect('projets:ateliers_projet', projet_id=projet.id)

    atelier.delete()

    if is_ajax(request):
        return ajax_response(
            success=True,
            message=f"Atelier « {libelle} » supprimé avec succès.",
        )
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

    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non supportée'}, status=405)

    form = AffectationRessourceForm(request.POST, atelier=atelier)

    if form.is_valid():
        affectation = form.save()
        if is_ajax(request):
            return ajax_response(
                success=True,
                message=f"Matériel « {affectation.materiel.designation} » affecté à l'atelier.",
            )
        messages.success(request, f"Matériel « {affectation.materiel.designation} » affecté.")
        return redirect('projets:materiels_atelier', projet_id=projet.id, atelier_id=atelier.id)

    if is_ajax(request):
        return ajax_response(
            success=False,
            message="Veuillez corriger les erreurs du formulaire.",
            errors=form.errors.get_json_data(),
            status=400,
        )

    return render(request, 'projets/ateliers/materiels.html', {
        'projet': projet,
        'atelier': atelier,
        'form': form,
        'affectations': AffectationRessource.objects.filter(atelier=atelier).select_related('materiel', 'materiel__type_materiel'),
        'materiels_disponibles': Materiel.objects.filter(actif=True).select_related('type_materiel'),
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
        if is_ajax(request):
            return ajax_response(
                success=True,
                message=f"Affectation de « {affectation.materiel.designation} » modifiée.",
            )
        messages.success(request, "Affectation modifiée avec succès.")
        return redirect('projets:materiels_atelier', projet_id=projet.id, atelier_id=atelier.id)

    if is_ajax(request):
        return ajax_response(
            success=False,
            message="Veuillez corriger les erreurs du formulaire.",
            errors=form.errors.get_json_data(),
            status=400,
        )

    return render(request, 'projets/ateliers/materiels.html', {
        'projet': projet,
        'atelier': atelier,
        'form': form,
        'affectation': affectation,
        'affectations': AffectationRessource.objects.filter(atelier=atelier).select_related('materiel', 'materiel__type_materiel'),
        'materiels_disponibles': Materiel.objects.filter(actif=True).select_related('type_materiel'),
    })


@chef_projet_required
def supprimer_affectation(request, projet_id, atelier_id, affectation_id):
    projet = get_object_or_404(Projet, id=projet_id)
    atelier = get_object_or_404(Atelier, id=atelier_id, projet=projet)
    affectation = get_object_or_404(AffectationRessource, id=affectation_id, atelier=atelier)
    designation = affectation.materiel.designation

    affectation.delete()

    if is_ajax(request):
        return ajax_response(
            success=True,
            message=f"Affectation de « {designation} » retirée avec succès.",
        )
    messages.success(request, f"Affectation de « {designation} » retirée avec succès.")
    return redirect('projets:materiels_atelier', projet_id=projet.id, atelier_id=atelier.id)

@chef_projet_required
def planning_ateliers(request, projet_id):
    """
    Planning des affectations de matériel aux ateliers du projet.

    Query params :
        - atelier : id d'un atelier (optionnel, sinon tous)
        - debut   : date de début de la période (YYYY-MM-DD)
        - fin     : date de fin de la période (YYYY-MM-DD)
    """
    projet = get_object_or_404(Projet, id=projet_id)
    ateliers = Atelier.objects.filter(projet=projet).order_by('code')

    # --- Filtre atelier (validé) ---
    atelier_id = request.GET.get('atelier')
    ateliers_selectionnes = ateliers
    atelier_id_valide = None
    if atelier_id:
        try:
            atelier_id_valide = int(atelier_id)
            ateliers_selectionnes = ateliers.filter(id=atelier_id_valide)
        except (ValueError, TypeError):
            atelier_id_valide = None
            ateliers_selectionnes = ateliers

    # --- Période (par défaut : mois calendaire en cours) ---
    today = date.today()
    debut_str = request.GET.get('debut')
    fin_str = request.GET.get('fin')

    try:
        debut = date.fromisoformat(debut_str) if debut_str else today.replace(day=1)
    except (ValueError, TypeError):
        debut = today.replace(day=1)

    # Fin par défaut : dernier jour du mois de début
    dernier_jour = monthrange(debut.year, debut.month)[1]
    try:
        fin = date.fromisoformat(fin_str) if fin_str else debut.replace(day=dernier_jour)
    except (ValueError, TypeError):
        fin = debut.replace(day=dernier_jour)

    # Sécurité : fin >= debut
    if fin < debut:
        fin = debut

    # --- Récupération des affectations ---
    affectations = (
        AffectationRessource.objects
        .filter(
            atelier__in=ateliers_selectionnes,
            date_debut__lte=fin,
        )
        .filter(
            Q(date_fin__isnull=True) | Q(date_fin__gte=debut)
        )
        .select_related('materiel', 'materiel__type_materiel', 'atelier')
        .order_by(
            Coalesce('materiel__immatriculation', Value('zzzzz')),
            'materiel__designation',
            'date_debut',
        )
    )

    duree_totale = (fin - debut).days + 1
    lignes = defaultdict(list)

    for aff in affectations:
        # Bornes réelles de l'affectation dans la période
        aff_debut = max(aff.date_debut, debut)

        # Pour une affectation en cours, on borne à aujourd'hui (ou fin de période)
        if aff.date_fin is None:
            aff_fin_reelle = min(today, fin)
        else:
            aff_fin_reelle = min(aff.date_fin, fin)

        # Si l'affectation commence après la fin de période → ignorer
        if aff_debut > fin:
            continue

        # Si l'affectation est complètement avant la période → ignorer
        if aff_fin_reelle < debut:
            continue

        offset = (aff_debut - debut).days
        largeur = max((aff_fin_reelle - aff_debut).days + 1, 1)

        # Pourcentages bornés
        offset_pct = max(0.0, min(100.0, (offset / duree_totale) * 100))
        largeur_pct = max(0.0, min(100.0 - offset_pct, (largeur / duree_totale) * 100))

        lignes[aff.materiel_id].append({
            'affectation': aff,
            # ✅ f-string = chaîne avec POINT (pas de virgule)
            'offset_pct': f"{offset_pct:.4f}",
            'largeur_pct': f"{largeur_pct:.4f}",
            'date_debut_reelle': aff.date_debut,
            'date_fin_reelle': aff.date_fin,
            'en_cours': aff.date_fin is None,
            'atelier_code': aff.atelier.code,
            'atelier_libelle': aff.atelier.libelle,
        })

    # --- Regroupement par matériel ---
    lignes_finales = {}
    for materiel_id, barres in lignes.items():
        # Trier les barres par date de début
        barres.sort(key=lambda b: b['affectation'].date_debut)
        lignes_finales[materiel_id] = {
            'materiel': barres[0]['affectation'].materiel,
            'barres': barres,
        }

    jours_periode = [debut + timedelta(days=i) for i in range(duree_totale)]

    return render(request, 'projets/ateliers/planning.html', {
        'projet': projet,
        'ateliers': ateliers,
        'atelier_selectionne': atelier_id_valide,
        'debut': debut,
        'fin': fin,
        'duree_totale': duree_totale,
        'jours_periode': jours_periode,
        'lignes': lignes_finales,
        'affectations': affectations,
    })