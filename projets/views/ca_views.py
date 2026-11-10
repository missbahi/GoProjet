import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from projets.decorators import can_view_projet, peut_valider_directement
from projets.forms_ca import ChiffreAffaireForm
from projets.models import ChiffreAffaire, Projet, SituationMensuelle
from projets.services.chiffre_affaire import enregistrer_ca, lignes_pour_ca, mois_voisin
from projets.utils.navigation import crumb, project_crumbs


def _projet(projet_id):
    projet = get_object_or_404(Projet.objects.select_related('dossier'), pk=projet_id)
    if not projet.dossier_id or projet.dossier.activite != 'TRAVAUX':
        raise PermissionDenied('Le CA mensuel est réservé au suivi Travaux.')
    return projet


@can_view_projet
@require_http_methods(['GET'])
def liste_ca(request, projet_id):
    projet = _projet(projet_id)
    context = {
        'projet': projet, 'cas': projet.chiffres_affaires.annotate(
            a_suivant=Exists(ChiffreAffaire.objects.filter(projet=projet, periode__gt=OuterRef('periode'))),
            a_situation=Exists(SituationMensuelle.objects.filter(ca_id=OuterRef('pk'))),
        ).order_by('-periode'),
        'peut_modifier': peut_valider_directement(request.user, projet),
        'breadcrumb_items': project_crumbs(projet, crumb("Chiffres d'affaires")),
    }
    template = 'projets/ca/_liste_content.html' if request.headers.get('HX-Request') else 'projets/ca/liste.html'
    return render(request, template, context)


@can_view_projet
@require_http_methods(['POST'])
@transaction.atomic
def action_ca(request, projet_id, ca_id, action):
    projet = _projet(projet_id)
    if not peut_valider_directement(request.user, projet):
        raise PermissionDenied('Action réservée au chef de projet autorisé et au superutilisateur.')
    Projet.objects.select_for_update().get(pk=projet.pk)
    ca = get_object_or_404(ChiffreAffaire.objects.select_for_update(), pk=ca_id, projet=projet)
    try:
        if action == 'supprimer':
            if ca.statut != ChiffreAffaire.Statut.BROUILLON:
                raise ValidationError('Seul un CA en brouillon peut être supprimé.')
            if projet.chiffres_affaires.filter(periode__gt=ca.periode).exists():
                raise ValidationError('Seul le dernier CA du projet peut être supprimé.')
            if SituationMensuelle.objects.filter(ca=ca).exists():
                raise ValidationError('Ce CA est lié à une situation et ne peut pas être supprimé.')
            ca.delete()
            message = 'CA supprimé.'
        elif action in {'valider', 'devalider'}:
            statut_attendu = 'BROUILLON' if action == 'valider' else 'VALIDE'
            if ca.statut != statut_attendu:
                raise ValidationError('Le statut du CA a changé. Rechargez la liste.')
            lignes = json.dumps([
                {'id': ligne.ligne_bordereau_id, 'quantite_cumulee': str(ligne.quantite_cumulee),
                 'cumul_initial': str(ligne.cumul_initial)}
                for ligne in ca.lignes.all()
            ])
            apercu = enregistrer_ca(ca, lignes, request.user, action=action)
            enregistrer_ca(ca, lignes, request.user, action=action, confirmation=apercu['confirmation'])
            message = 'CA validé ; les recettes des situations en brouillon ont été synchronisées.' if action == 'valider' else 'CA remis en brouillon.'
        else:
            raise ValidationError('Action CA inconnue.')
    except ValidationError as error:
        return JsonResponse({'success': False, 'message': ' '.join(error.messages)}, status=400)
    return JsonResponse({'success': True, 'message': message})


@can_view_projet
@require_http_methods(['GET', 'POST'])
def formulaire_ca(request, projet_id, ca_id=None):
    projet = _projet(projet_id)
    peut_modifier = peut_valider_directement(request.user, projet)
    if not ca_id and not peut_modifier or request.method == 'POST' and not peut_modifier:
        raise PermissionDenied('Création et modification réservées au chef de projet autorisé et au superutilisateur.')
    ca = get_object_or_404(ChiffreAffaire, pk=ca_id, projet=projet) if ca_id else ChiffreAffaire(projet=projet)
    dernier = projet.chiffres_affaires.order_by('-periode').first()
    ca.periode = ca.periode or (mois_voisin(dernier.periode, 1) if dernier else timezone.localdate().replace(day=1))
    form = ChiffreAffaireForm(
        request.POST if request.method == 'POST' else None, instance=ca, projet=projet,
        initial={'mois': ca.periode.strftime('%Y-%m')},
    )
    if not peut_modifier:
        for field in form.fields.values():
            field.disabled = True
    if request.method == 'POST':
        if not form.is_valid():
            return JsonResponse({'erreur': ' '.join(
                f'{form.fields[champ].label if champ in form.fields else "CA"} : {erreur}'
                for champ, erreurs in form.errors.items() for erreur in erreurs
            )}, status=400)
        try:
            resultat = enregistrer_ca(
                form.save(commit=False), request.POST.get('lignes'), request.user,
                action=request.POST.get('action', 'enregistrer'),
                confirmation=request.POST.get('confirmation', ''),
            )
        except ValidationError as error:
            return JsonResponse({'erreur': ' '.join(error.messages)}, status=400)
        if resultat.get('enregistre'):
            messages.success(request, 'CA enregistré ; les situations en brouillon concernées ont été synchronisées.')
            resultat['redirect'] = reverse('projets:modifier_ca', args=[projet.pk, resultat['id']])
        return JsonResponse(resultat)
    lignes = lignes_pour_ca(ca)
    premier = not projet.chiffres_affaires.exclude(pk=ca.pk).filter(periode__lt=ca.periode).exists()
    return render(request, 'projets/ca/formulaire.html', {
        'projet': projet, 'ca': ca, 'form': form,
        'lignes': json.dumps(lignes, default=str), 'premier': premier,
        'peut_modifier': peut_modifier, 'existant': bool(ca.pk),
        'breadcrumb_items': project_crumbs(
            projet, crumb("Chiffres d'affaires", 'projets:liste_ca', args=[projet.pk]),
            crumb(f'CA {ca.periode:%m/%Y}'),
        ),
    })
