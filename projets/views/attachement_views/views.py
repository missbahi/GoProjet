import json
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from projets.decorators import modules_projet_required, projets_accessibles
from projets.forms import AttachementForm, DecompteForm
from projets.manager import LigneHierarchique
from projets.models import (
    Attachement,
    Decompte,
    EtapeValidation,
    LigneAttachement,
    LigneBordereau,
    LotProjet,
    ProcessValidation,
    Projet,
)
from projets.services.attachement_service import DonneesAttachementInvalides, enregistrer_lignes_attachement
from projets.views.lot_views.views import _est_ligne_titre_bordereau, _iter_lignes_bordereau_hierarchiques
from projets.views.os_views.views import download_document


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
        form = AttachementForm(initial={'statut': 'BROUILLON'})

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
        'is_edition': False,
    }
    return render(request, 'projets/decomptes/attachement_form.html', context)


@modules_projet_required
def modifier_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    _verifier_acces_attachement(request, attachement, {'BROUILLON', 'MODIFIE', 'TRANSMIS', 'REFUSE'})
    projet = attachement.projet
    lignes_bordereau = list(_iter_lignes_bordereau_hierarchiques(projet))

    if request.method == 'POST':
        statut_initial = attachement.statut
        form = AttachementForm(request.POST, request.FILES, instance=attachement)
        if form.is_valid():
            try:
                with transaction.atomic():
                    attachement = form.save(commit=False)
                    if statut_initial in {'TRANSMIS', 'REFUSE'} and attachement.statut != 'BROUILLON':
                        attachement.statut = statut_initial
                    retour_en_brouillon = (
                        statut_initial in {'TRANSMIS', 'REFUSE'}
                        and attachement.statut == 'BROUILLON'
                    )
                    if retour_en_brouillon:
                        attachement.validations.update(
                            statut_validation='EN_ATTENTE',
                            validateur=None,
                            date_validation=None,
                            commentaires='',
                            motifs_rejet='',
                        )
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
            'est_titre': hasattr(ligne, 'has_children') and ligne.has_children(),
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

    while lignes_data and lignes_data[-1]['is_title']:
        lignes_data.pop()

    lignes_json = json.dumps(lignes_data, default=str)

    attachement.peut_reouvrir = (attachement.statut == 'VALIDE' and (request.user.is_superuser or request.user.is_staff))
    attachement.peut_supprimer = attachement.statut != 'VALIDE'
    attachement.est_validable = attachement.statut in ['BROUILLON', 'TRANSMIS', 'REFUSE']
    attachement.ferme = attachement.statut == 'SIGNE'

    context = {
        'projet': projet,
        'attachement': attachement,
        'form': form,
        'lignes': lignes_json,
        'total_lignes': len(lignes_bordereau),
        'total_attachement': float(0.0),
        'is_edition': True,
    }
    return render(request, 'projets/decomptes/attachement_form.html', context)


@modules_projet_required
def detail_attachement(request, attachement_id):
    attachement = get_object_or_404(Attachement, id=attachement_id)
    lots = LotProjet.objects.filter(projet=attachement.projet).order_by('id')
    lots_data = []
    montant_total = Decimal('0.00')
    total_lignes = 0

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
            messages.success(request, f"Attachement {numero} supprimé avec succès! ({count_lignes} lignes supprimées)")
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression : {str(e)}")

        return redirect('projets:liste_attachements', projet_id=projet_id)

    count_lignes = attachement.lignes_attachement.count()
    return render(request, 'projets/decomptes/supprimer_attachement.html', {
        'attachement': attachement,
        'count_lignes': count_lignes,
    })


def attachements_ajouter_decompte(request, attachement_id):
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


@login_required
def ajouter_etape(request, process_id):
    try:
        process_validation = ProcessValidation.objects.get(id=process_id)
        attachement_id = process_validation.attachement.id

        if not process_validation.peut_etre_valide_par(request.user):
            messages.error(request, "Permission refusée.")
            return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)

        if request.method == 'POST':
            nom = request.POST.get('nom')
            obligatoire = request.POST.get('obligatoire') == 'true'
            commentaire = request.POST.get('commentaire', '')

            if not nom:
                messages.error(request, "Le nom de l'étape est obligatoire.")
                return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)

            dernier_ordre = process_validation.etapes.aggregate(Max('ordre'))['ordre__max']
            nouvel_ordre = (dernier_ordre or 0) + 1

            EtapeValidation.objects.create(
                processValidation=process_validation,
                nom=nom,
                ordre=nouvel_ordre,
                obligatoire=obligatoire,
                commentaire=commentaire,
            )

            messages.success(request, f"Nouvelle étape '{nom}' ajoutée avec succès !")
            return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)

    except ProcessValidation.DoesNotExist:
        messages.error(request, "Processus de validation non trouvé.")
        return redirect('projets:liste_attachements')

    return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)


@login_required
def valider_etape(request, etape_id):
    try:
        etape = EtapeValidation.objects.get(id=etape_id)

        if not etape.processValidation.peut_etre_valide_par(request.user):
            messages.error(request, "Permission refusée.")
            return redirect_to_attachement(etape)

        if request.method == 'POST':
            commentaire = request.POST.get('commentaire', '')
            etape.valider(request.user, commentaire)
            messages.success(request, f"Étape '{etape.nom}' validée avec succès !")

    except EtapeValidation.DoesNotExist:
        messages.error(request, "Étape de validation non trouvée.")
        return redirect('projets:liste_attachements')

    return redirect_to_attachement(etape)


@login_required
def passer_etape(request, etape_id):
    try:
        etape = EtapeValidation.objects.get(id=etape_id)

        if not etape.processValidation.peut_etre_valide_par(request.user):
            messages.error(request, "Permission refusée.")
            return redirect_to_attachement(etape)

        if etape.obligatoire:
            messages.error(request, "Impossible de passer une étape obligatoire.")
            return redirect_to_attachement(etape)

        if request.method == 'POST':
            commentaire = request.POST.get('commentaire', '')
            etape.est_validee = True
            etape.valide_par = request.user
            etape.date_validation = timezone.now()
            etape.commentaire = commentaire if commentaire else "Étape passée"
            etape.save()
            etape.processValidation.valider(request.user)

            messages.warning(request, f"Étape '{etape.nom}' passée.")

    except EtapeValidation.DoesNotExist:
        messages.error(request, "Étape de validation non trouvée.")
        return redirect('projets:liste_attachements')

    return redirect_to_attachement(etape)


@login_required
def modifier_etape(request, etape_id):
    try:
        etape = EtapeValidation.objects.get(id=etape_id)

        if not etape.processValidation.peut_etre_valide_par(request.user):
            messages.error(request, "Permission refusée.")
            return redirect_to_attachement(etape)

        if etape.est_validee:
            messages.error(request, "Impossible de modifier une étape déjà validée.")
            return redirect_to_attachement(etape)

        if request.method == 'POST':
            nouveau_nom = request.POST.get('nom')
            nouveau_commentaire = request.POST.get('commentaire', '')
            obligatoire_value = request.POST.get('obligatoire')
            nouvelle_obligatoire = obligatoire_value == 'on'

            if nouveau_nom:
                etape.nom = nouveau_nom
            etape.commentaire = nouveau_commentaire
            etape.obligatoire = nouvelle_obligatoire
            etape.save()

            messages.success(request, f"Étape '{etape.nom}' modifiée avec succès.")
            return redirect_to_attachement(etape)

    except EtapeValidation.DoesNotExist:
        messages.error(request, "Étape non trouvée.")

    return redirect_to_attachement(etape)


@login_required
def reinitialiser_etape(request, etape_id):
    try:
        etape = EtapeValidation.objects.get(id=etape_id)

        if not etape.processValidation.peut_etre_valide_par(request.user):
            messages.error(request, "Permission refusée.")
            return redirect_to_attachement(etape)

        if not etape.est_validee:
            messages.warning(request, "Cette étape n'est pas encore validée.")
            return redirect_to_attachement(etape)

        etape.est_validee = False
        etape.valide_par = None
        etape.date_validation = None
        etape.save()

        etapes_suivantes = etape.processValidation.etapes.filter(ordre__gt=etape.ordre)
        etapes_suivantes.update(
            est_validee=False,
            valide_par=None,
            date_validation=None
        )

        messages.warning(request, f"Étape '{etape.nom}' réinitialisée. Le processus a repris depuis cette étape.")

    except EtapeValidation.DoesNotExist:
        messages.error(request, "Étape non trouvée.")

    return redirect_to_attachement(etape)


@login_required
def supprimer_etape(request, etape_id):
    try:
        etape = EtapeValidation.objects.get(id=etape_id)
        process_validation = etape.processValidation
        attachement_id = process_validation.attachement.id

        if not process_validation.peut_etre_valide_par(request.user):
            messages.error(request, "Permission refusée.")
            return redirect_to_attachement(etape)

        if etape.est_validee:
            messages.error(request, "Impossible de supprimer une étape déjà validée.")
            return redirect_to_attachement(etape)

        total_etapes = process_validation.etapes.count()
        if total_etapes <= 1:
            messages.error(request, "Impossible de supprimer la dernière étape du processus.")
            return redirect_to_attachement(etape)

        nom_etape = etape.nom
        etape.delete()

        etapes_restantes = process_validation.etapes.order_by('ordre')
        for index, etape_restante in enumerate(etapes_restantes, start=1):
            if etape_restante.ordre != index:
                etape_restante.ordre = index
                etape_restante.save()

        process_validation.valider(request.user)
        messages.success(request, f"Étape '{nom_etape}' supprimée avec succès.")

    except EtapeValidation.DoesNotExist:
        messages.error(request, "Étape non trouvée.")

    return redirect('projets:validation_technique_attachement', attachement_id=attachement_id)


def redirect_to_attachement(etape):
    return redirect('projets:validation_technique_attachement', attachement_id=etape.processValidation.attachement.id)


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
    etape = get_object_or_404(EtapeValidation, id=etape_id)

    if not etape.fichier:
        messages.error(request, "Aucun fichier associé à cette étape.")
        return redirect_to_attachement(etape)

    try:
        return download_document(request, 'EtapeValidation', etape_id)
    except Exception as e:
        messages.error(request, f"Erreur lors du téléchargement : {str(e)}")
        return redirect_to_attachement(etape)


@login_required
@modules_projet_required
def liste_decomptes(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    decomptes = Decompte.objects.filter(attachement__projet=projet).order_by('-id')

    statut_filter = request.GET.get('statut')
    if statut_filter:
        decomptes = decomptes.filter(statut=statut_filter)

    from_attachement_list = request.GET.get('from_attachements') == 'true'
    attachement_id = request.GET.get('attachement_id')
    action_type = request.GET.get('action')

    attachement_cible = None
    if from_attachement_list and attachement_id:
        try:
            attachement_cible = Attachement.objects.get(id=attachement_id, projet=projet)
            if action_type == 'modifier':
                decomptes = decomptes.filter(attachement=attachement_cible)
        except Attachement.DoesNotExist:
            pass

    search_query = request.GET.get('search', '')
    if search_query and len(search_query) >= 3:
        decomptes = decomptes.filter(
            Q(numero__icontains=search_query)
            | Q(type_decompte__icontains=search_query)
            | Q(statut__icontains=search_query)
            | Q(numero_bordereau__icontains=search_query)
            | Q(attachement__numero__icontains=search_query)
        )

    sort_field = request.GET.get('sort', '-date_emission')
    if sort_field in ['numero', 'date_emission', 'date_echeance', 'statut', 'montant_net_a_payer']:
        decomptes = decomptes.order_by(sort_field)
    elif sort_field in ['-numero', '-date_emission', '-date_echeance', '-statut', '-montant_net_a_payer']:
        decomptes = decomptes.order_by(sort_field)

    dernier_decompte = Decompte.objects.filter(attachement__projet=projet).order_by('-id').first()

    total_ht = dernier_decompte.montant_ht if dernier_decompte else 0
    total_ttc = dernier_decompte.montant_ttc if dernier_decompte else 0
    total_net = dernier_decompte.montant_net_a_payer if dernier_decompte else 0
    payes_count = decomptes.filter(statut='PAYE').count()

    decomptes_payes = Decompte.objects.filter(attachement__projet=projet, statut='PAYE')
    decomptes_emis = Decompte.objects.filter(attachement__projet=projet, statut='EMIS')
    decomptes_valides = Decompte.objects.filter(attachement__projet=projet, statut='VALIDE')
    decomptes_brouillons = Decompte.objects.filter(attachement__projet=projet, statut='BROUILLON')

    attachements_sans_decompte = Attachement.objects.filter(projet=projet, decompte__isnull=True)

    decompte_a_modifier = None
    form = None

    if request.method == 'POST':
        decompte_id = request.POST.get('decompte_id')
    else:
        decompte_id = request.GET.get('modifier')

    if decompte_id:
        decompte_a_modifier = get_object_or_404(Decompte, id=decompte_id, attachement__projet=projet)
        if request.method == 'POST':
            form = DecompteForm(request.POST, instance=decompte_a_modifier)
        else:
            form = DecompteForm(instance=decompte_a_modifier)

        attachement_ids = list(attachements_sans_decompte.values_list('id', flat=True))
        attachement_ids.append(decompte_a_modifier.attachement.id)

        form.fields['attachement'].queryset = Attachement.objects.filter(
            id__in=attachement_ids
        ).order_by('numero')

    elif from_attachement_list and attachement_cible and action_type == 'ajouter':
        if request.method == 'POST':
            form = DecompteForm(request.POST)
        else:
            form = DecompteForm()

        form.fields['attachement'].queryset = attachements_sans_decompte.order_by('numero')

        if attachements_sans_decompte.filter(id=attachement_cible.id).exists():
            form.initial['attachement'] = attachement_cible.id
            form.initial['numero'] = f"DEC-{attachement_cible.numero}-{date.today().strftime('%Y%m')}"
            form.initial['date_emission'] = date.today()

            if attachement_cible.date_fin_periode:
                form.initial['date_echeance'] = max(date.today(), attachement_cible.date_fin_periode)
            else:
                form.initial['date_echeance'] = date.today() + timedelta(days=30)

            form.initial['type_decompte'] = 'PROVISOIRE'
            form.initial['statut'] = 'BROUILLON'
            form.initial['taux_tva'] = 20.0
            form.initial['taux_retenue_garantie'] = 10.0
            form.initial['taux_ras'] = 0.0
            form.initial['autres_retenues'] = 0.0

    else:
        if request.method == 'POST':
            form = DecompteForm(request.POST)
        else:
            form = DecompteForm()

        form.fields['attachement'].queryset = attachements_sans_decompte.order_by('numero')
        form.initial['date_emission'] = date.today()
        form.initial['taux_tva'] = 20.0
        form.initial['taux_retenue_garantie'] = 10.0

    if request.method == 'POST':
        if form.is_valid():
            decompte = form.save()
            action = "modifié" if decompte_id else "créé"
            messages.success(request, f"Décompte {decompte.numero} {action} avec succès.")

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
        'attachement_cible': attachement_cible,
    }

    return render(request, 'projets/decomptes/liste_decomptes.html', context)


@modules_projet_required
def projet_ajouter_decompte(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    return redirect(f"{reverse('projets:liste_decomptes', args=[projet.id])}?ajouter=1")


def modifier_decompte(request, decompte_id):
    decompte = get_object_or_404(Decompte, id=decompte_id)
    return redirect(f"{reverse('projets:liste_decomptes', args=[decompte.attachement.projet.id])}?modifier={decompte.id}")


def supprimer_decompte(request, decompte_id):
    decompte = get_object_or_404(Decompte, id=decompte_id)
    projet_id = decompte.attachement.projet.id

    if request.method == 'POST':
        numero = decompte.numero
        decompte.delete()
        messages.success(request, f"Décompte {numero} supprimé avec succès.")
        return redirect('projets:liste_decomptes', projet_id=projet_id)

    context = {
        'decompte': decompte,
        'projet': decompte.attachement.projet,
    }
    return render(request, 'projets/supprimer_decompte.html', context)


def detail_decompte(request, decompte_id):
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
    autres = float(decompte.autres_retenues) if decompte.autres_retenues else 0.0
    net_a_payer = montant_t_ttc - rg - ras - autres
    est_revise = revision_prix != 0

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
        'net_a_payer': net_a_payer,
    }
    return render(request, 'projets/decomptes/detail_decompte.html', context)


def calcul_retard_decompte(request, decompte_id):
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
        'statut': decompte.statut,
    })


@modules_projet_required
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
        'pourcentage_realise': 0,
    }

    attachement_id = request.GET.get('attachement_id')
    if attachement_id:
        attachement_courant = get_object_or_404(Attachement, id=attachement_id, projet=projet)
        attachement_precedent = attachement_courant.get_previous_attachement()

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
                        'can_be_hidden': False,
                    }
                    lignes_controle.append(ligne_controle)
                    continue

                quantite_marche = ligne_bordereau.quantite
                montant_marche = ligne_bordereau.montant

                ligne_courante = LigneAttachement.objects.filter(attachement=attachement_courant, ligne_lot=ligne_bordereau).first()
                quantite_s = ligne_courante.quantite_realisee if ligne_courante else Decimal('0')
                montant_s = quantite_s * ligne_bordereau.prix_unitaire

                quantite_s1 = Decimal('0')
                if attachement_precedent:
                    ligne_precedente = LigneAttachement.objects.filter(
                        attachement=attachement_precedent,
                        ligne_lot=ligne_bordereau
                    ).first()
                    quantite_s1 = ligne_precedente.quantite_realisee if ligne_precedente else Decimal('0')

                quantite_partiel = quantite_s - quantite_s1
                montant_partiel = quantite_partiel * ligne_bordereau.prix_unitaire

                delta_quantite = quantite_marche - quantite_s
                delta_montant = montant_marche - montant_s

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
                    'can_be_hidden': True if montant_s == 0 else False,
                }

                lignes_controle.append(ligne_controle)

                for key in total_lot:
                    if key in ligne_controle:
                        total_lot[key] += ligne_controle[key]
            total_lot['pourcentage_realise'] = (total_lot['montant_s'] / total_lot['montant_marche'] * 100) if total_lot['montant_marche'] > 0 else Decimal('0')

            if lignes_controle:
                donnees_controle.append({'lot': lot, 'lignes': lignes_controle, 'total_lot': total_lot})

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
        'nb_lots': len(donnees_controle) > 1,
    }

    return render(request, 'projets/decomptes/fiche_controle.html', context)


def get_lignes_attachement(request, attachement_id):
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
