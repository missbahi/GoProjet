import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from projets.decorators import chef_projet_required
from projets.exporters import ExcelExporter
from projets.manager import LigneHierarchique
from projets.models import LigneBordereau, LotProjet, Projet


@chef_projet_required
def saisie_bordereau(request, projet_id, lot_id):
    lot = get_object_or_404(LotProjet, id=lot_id, projet_id=projet_id)
    lot_root = lot.to_line_tree()

    data = [
        {
            'id': ligne.id,
            'numero': ligne.numero,
            'designation': ligne.designation,
            'unite': ligne.unite,
            'quantite': float(ligne.quantite),
            'prix_unitaire': float(ligne.pu),
            'montant': float(ligne.amount()),
            'niveau': ligne.level(),
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

            lignes_existantes = {ligne.id: ligne for ligne in LigneBordereau.objects.filter(lot=lot)}
            id_mapping = {}
            lignes_existantes_utilisees = set()

            lignes = {}
            for index, row in enumerate(body):
                ligne_id = row.get('id')
                if ligne_id and ligne_id in lignes_existantes:
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
                for index, row in enumerate(body):
                    ligne_id = row.get('id')
                    parent_id = row.get('parent_id')
                    ligne: LigneBordereau = lignes[ligne_id]
                    if parent_id and parent_id in lignes:
                        ligne.parent = lignes[parent_id]
                    else:
                        ligne.parent = None
                    ligne.save()
                    id_mapping[ligne_id] = ligne.id

                lignes_a_supprimer = set(lignes_existantes.keys()) - lignes_existantes_utilisees
                if lignes_a_supprimer:
                    LigneBordereau.objects.filter(id__in=lignes_a_supprimer).delete()

                return JsonResponse({
                    'success': True,
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
    lots = LotProjet.objects.filter(projet=projet).order_by('id')
    lots_data = []
    montant_total = 0
    total_lignes = 0

    for lot in lots:
        lignes = LigneBordereau.objects.filter(lot=lot).order_by('id')
        total_lot = sum(
            (ligne.quantite or 0) * (ligne.prix_unitaire or 0)
            for ligne in lignes
        )
        if total_lot == 0:
            continue

        lines_root = LigneHierarchique({'id': 0, lot.nom: 'root'})
        lines_root.build_tree(lignes, lines_root)
        lignes_table = lines_root.export_to_table()

        lots_data.append({
            'lot': lot,
            'id': lot.id,
            'nom': lot.nom,
            'description': lot.description,
            'lignes_table': lignes_table,
            'total_lot': total_lot,
        })

        montant_total += total_lot
        total_lignes += len(lignes_table)

    context = {
        'projet': projet,
        'can_editer': can_editer,
        'lots': lots_data,
        'montant_total': montant_total,
        'total_lots': len(lots_data),
        'total_lignes': total_lignes,
    }
    return render(request, 'projets/lots/lots_details.html', context)
