"""
Vues de gestion des ressources affectées à un projet.
"""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projets.decorators import chef_projet_required, can_view_projet
from projets.forms import RessourceAffecteeForm
from projets.models import (
    Projet, Atelier, CategorieCharge, RessourceAffectee,
)
from projets.utils.navigation import crumb, project_crumbs
from projets.utils.utils import ajax_response, is_ajax, render_page_or_fragment


# ============================================================
# API : ateliers d'un projet
# ============================================================

@can_view_projet
def api_ateliers_projet(request, projet_id):
    """Retourne les ateliers actifs d'un projet (JSON)."""
    projet = get_object_or_404(Projet, id=projet_id)
    ateliers = (
        Atelier.objects.filter(projet=projet, actif=True)
        .order_by('code')
        .values('id', 'code', 'libelle')
    )
    return ajax_response(success=True, ateliers=list(ateliers))


# ============================================================
# Page principale : liste des ressources du projet (onglets par type)
# ============================================================

@can_view_projet
def ressources_projet(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    categories = CategorieCharge.objects.filter(actif=True).order_by('ordre', 'nom')

    categories_data = []
    total = 0
    for cat in categories:
        liste = list(
            RessourceAffectee.objects
            .filter(projet=projet, categorie_charge=cat)
            .select_related('atelier', 'categorie_charge')
            .order_by('-date_debut', 'designation')
        )
        total += len(liste)
        categories_data.append({
            'categorie': cat,
            'ressources': liste,
            'count': len(liste),
        })

    ctx = {
        'projet': projet,
        'categories_data': categories_data,
        'total_ressources': total,
        'breadcrumb_items': project_crumbs(projet, crumb("Ressources")),
    }
    return render_page_or_fragment(
        request,
        full_template='projets/ressources/liste_ressources.html',
        fragment_template='projets/ressources/_liste_ressources_content.html',
        context=ctx,
    )


# ============================================================
# CRUD AJAX
# ============================================================

@chef_projet_required
@require_POST
def ajouter_ressource(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    form = RessourceAffecteeForm(request.POST, projet=projet)
    if form.is_valid():
        ressource = form.save()
        return ajax_response(
            success=True,
            message=f"« {ressource.designation} » affectée au projet.",
            ressource_id=ressource.id,
        )
    return ajax_response(
        success=False,
        message="Veuillez corriger les erreurs.",
        errors=form.errors.get_json_data(),
        status=400,
    )


@chef_projet_required
@require_POST
def modifier_ressource(request, ressource_id):
    ressource = get_object_or_404(
        RessourceAffectee.objects.select_related('projet'),
        id=ressource_id,
    )
    form = RessourceAffecteeForm(request.POST, instance=ressource, projet=ressource.projet)
    if form.is_valid():
        ressource = form.save()
        return ajax_response(
            success=True,
            message=f"Affectation de « {ressource.designation} » modifiée.",
        )
    return ajax_response(
        success=False,
        message="Veuillez corriger les erreurs.",
        errors=form.errors.get_json_data(),
        status=400,
    )


@chef_projet_required
@require_POST
def supprimer_ressource(request, ressource_id):
    ressource = get_object_or_404(RessourceAffectee, id=ressource_id)
    designation = ressource.designation
    ressource.delete()
    return ajax_response(
        success=True,
        message=f"Affectation de « {designation} » retirée.",
    )


# ============================================================
# API : options de ressources selon le type (pour select dynamique)
# ============================================================

@can_view_projet
def api_options_ressource(request, projet_id):
    """Retourne les options d'un type de ressource (JSON) pour alimenter le <select>."""
    code = request.GET.get('code', '').upper()
    entry = RessourceAffecteeForm.RESSOURCE_MAP.get(code)
    if not entry:
        return ajax_response(success=False, message="Type non supporté.", status=400)

    Model, champ_designation, champ_prix, _ = entry
    qs = Model.objects.filter(actif=True).order_by(champ_designation)

    options = [
        {
            'id': obj.pk,
            'label': getattr(obj, champ_designation),
            'unite': getattr(obj, 'unite', '') or '',
            'prix': str(getattr(obj, champ_prix, 0) or 0),
        }
        for obj in qs
    ]
    return ajax_response(success=True, options=options)