from decimal import Decimal

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from projets.decorators import categorie_charge_required, chef_projet_required

from projets.models import (
    Client, Consommable, Entreprise, Fourniture, Ingenieur, Location, Materiel, TypeMateriel,
    Personnel, SousTraitance, Transport, CategorieCharge,
)
from projets.forms import (
    CategorieChargeForm, ClientForm, ConsommableForm, EntrepriseForm, FournitureForm, IngenieurForm,
    LocationForm, MaterielForm, PersonnelForm, SousTraitanceForm, TransportForm,
    TypeMaterielForm, 
)

from projets.utils.icones import choix_icones
from projets.utils.import_parsers import parser_import_materiel

@chef_projet_required
def partial_ingenieurs(request):
    ingenieurs = Ingenieur.objects.all()
    return render(request, 'projets/partials/ingenieurs.html', {'ingenieurs': ingenieurs})


@chef_projet_required
def partial_entreprises(request):
    entreprises = Entreprise.objects.all()
    return render(request, 'projets/partials/entreprises.html', {'entreprises': entreprises})


@chef_projet_required
def partial_clients(request):
    clients = Client.objects.all()
    return render(request, 'projets/partials/clients.html', {'clients': clients})


@chef_projet_required
def partial_personnel(request):
    personnel = Personnel.objects.all()
    return render(request, 'projets/partials/personnel.html', {'personnel': personnel})


@chef_projet_required
def partial_materiel(request):
    materiel = Materiel.objects.select_related('type_materiel').all()
    types_materiel_actifs = TypeMateriel.objects.filter(actif=True).order_by('nom')
    return render(request, 'projets/partials/materiel.html', {
        'materiel': materiel,
        'types_materiel_actifs': types_materiel_actifs,
    })


@chef_projet_required
def partial_transports(request):
    transports = Transport.objects.all()
    return render(request, 'projets/partials/transport.html', {'transports': transports})


@chef_projet_required
def partial_locations(request):
    locations = Location.objects.all()
    return render(request, 'projets/partials/locations.html', {'locations': locations})


@chef_projet_required
def partial_sous_traitances(request):
    sous_traitances = SousTraitance.objects.all()
    return render(request, 'projets/partials/sous_traitances.html', {'sous_traitances': sous_traitances})


@chef_projet_required
def partial_consommables(request):
    consommables = Consommable.objects.all()
    return render(request, 'projets/partials/consommables.html', {'consommables': consommables})


@chef_projet_required
def partial_fournitures(request):
    fournitures = Fourniture.objects.all()
    return render(request, 'projets/partials/fournitures.html', {'fournitures': fournitures})


@chef_projet_required
def base_donnees(request):
    return render(request, 'projets/base_donnees.html', {
        'choix_icones': choix_icones(),
        'types_materiel_actifs': TypeMateriel.objects.filter(actif=True).order_by('nom'),
    })

# ============================================================
# Gestion des types de matériel (référentiel)
# ============================================================

@chef_projet_required
def partial_types_materiel(request):
    types_materiel = TypeMateriel.objects.all()
    return render(
        request,
        'projets/partials/types_materiel.html',
        {'types_materiel': types_materiel},
    )


@chef_projet_required
def ajouter_type_materiel(request):
    if request.method != 'POST':
        form = TypeMaterielForm()
        return render(
            request,
            'projets/partials/types_materiel.html',
            {'form': form},
        )

    form = TypeMaterielForm(request.POST)
    if form.is_valid():
        type_materiel = form.save()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': f"Le type de matériel « {type_materiel.nom} » a été ajouté avec succès.",
            })
        return redirect('projets:partial_types_materiel')

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(
            {'success': False, 'errors': form.errors.get_json_data()},
            status=400,
        )
    return render(
        request,
        'projets/partials/types_materiel.html',
        {'form': form},
    )


@chef_projet_required
def modifier_type_materiel(request, type_materiel_id):
    type_materiel = get_object_or_404(TypeMateriel, id=type_materiel_id)

    if request.method != 'POST':
        return JsonResponse({'error': 'Méthode non supportée'}, status=405)

    form = TypeMaterielForm(request.POST, instance=type_materiel)

    if form.is_valid():
        type_materiel = form.save()
        if request.GET.get('modal') == 'true':
            return JsonResponse({
                'success': True,
                'message': f"Type de matériel « {type_materiel.nom} » modifié avec succès.",
            })
        messages.success(request, f"Type de matériel « {type_materiel.nom} » modifié avec succès.")
        return redirect('projets:partial_types_materiel')

    if request.GET.get('modal') == 'true':
        return JsonResponse(
            {'success': False, 'errors': form.errors.get_json_data()},
            status=400,
        )

    return render(
        request,
        'projets/partials/types_materiel.html',
        {'form': form, 'type_materiel': type_materiel},
    )


@chef_projet_required
def supprimer_type_materiel(request, type_materiel_id):
    type_materiel = get_object_or_404(TypeMateriel, id=type_materiel_id)
    nom = type_materiel.nom

    # Protection : empêcher la suppression si des matériels y sont rattachés
    if type_materiel.materiels.exists():
        message = (
            f"Impossible de supprimer « {nom} » : "
            f"{type_materiel.materiels.count()} matériel(s) y sont rattachés."
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect('projets:partial_types_materiel')

    type_materiel.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f"Type de matériel « {nom} » supprimé avec succès.",
        })
    messages.success(request, f"Type de matériel « {nom} » supprimé avec succès.")
    return redirect('projets:partial_types_materiel')

@categorie_charge_required
def partial_categories_charges(request):
    categories = CategorieCharge.objects.all()
    resource_modules = {
        'PERSONNEL': ('Personnel', 'partial_personnel', 'fa-users-gear'),
        'MATERIEL': ('Matériel', 'partial_materiel', 'fa-truck-monster'),
        'LOCATION': ('Locations', 'partial_locations', 'fa-location-dot'),
        'SOUS_TRAITANCE': ('Sous-traitances', 'partial_sous_traitances', 'fa-handshake'),
        'TRANSPORT': ('Transports', 'partial_transports', 'fa-truck'),
        'CONSOMMABLE': ('Consommables', 'partial_consommables', 'fa-boxes-stacked'),
        'FOURNITURE': ('Fournitures', 'partial_fournitures', 'fa-box-open'),
    }
    category_rows = [
        {
            'category': category,
            'resource': resource_modules.get(category.code),
            'resource_url': reverse(
                f"projets:{resource_modules[category.code][1]}"
            ) if category.code in resource_modules else None,
        }
        for category in categories
    ]
    return render(request, 'projets/partials/categories_charges.html', {
        'categories': categories,
        'category_rows': category_rows,
        'form': CategorieChargeForm(),
    })


@categorie_charge_required
def ajouter_categorie_charge(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Méthode non autorisée.'}, status=405)
    form = CategorieChargeForm(request.POST)
    if form.is_valid():
        categorie = form.save()
        return JsonResponse({'success': True, 'message': f'Catégorie « {categorie.nom} » ajoutée.'})
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)


@categorie_charge_required
def modifier_categorie_charge(request, categorie_id):
    categorie = get_object_or_404(CategorieCharge, id=categorie_id)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Méthode non autorisée.'}, status=405)
    form = CategorieChargeForm(request.POST, instance=categorie)
    if form.is_valid():
        categorie = form.save()
        return JsonResponse({'success': True, 'message': f'Catégorie « {categorie.nom} » modifiée.'})
    return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)


@chef_projet_required
def ajouter_ingenieur(request):
    if request.method == 'POST':
        form = IngenieurForm(request.POST)
        if form.is_valid():
            ingenieur = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': "L'ingenieur " + ingenieur.nom + ' ajouté avec succès'})
            return redirect('projets:partial_ingenieurs')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = IngenieurForm()
    return render(request, 'projets/partials/ingenieurs.html', {'form': form})


@chef_projet_required
def modifier_ingenieur(request, ingenieur_id):
    ingenieur = get_object_or_404(Ingenieur, id=ingenieur_id)
    if request.method == 'POST':
        form = IngenieurForm(request.POST, instance=ingenieur)
        if form.is_valid():
            ingenieur = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Ingénieur ' + ingenieur.nom + ' modifié avec succès'})
        elif request.GET.get('modal') == 'true':
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'error': 'Méthode non supportée'}, status=400)


@chef_projet_required
def supprimer_ingenieur(request, ingenieur_id):
    ingenieur = get_object_or_404(Ingenieur, id=ingenieur_id)
    ingenieur.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Ingénieur ' + ingenieur.nom + ' supprimé avec succès.'})
    messages.success(request, 'Ingénieur supprimé avec succès.')
    return redirect('projets:partial_ingenieurs')


@chef_projet_required
def ajouter_client(request):
    if request.method == 'POST':
        form = ClientForm(request.POST)
        if form.is_valid():
            client = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Le client ' + client.nom + ' ajouté avec succès'})
            return redirect('projets:partial_clients')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = ClientForm()
    return render(request, 'projets/partials/clients.html', {'form': form})


@chef_projet_required
def modifier_client(request, client_id):
    client = Client.objects.get(id=client_id)
    if request.method == 'POST':
        form = ClientForm(request.POST, instance=client)
        if form.is_valid():
            client = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Le client ' + client.nom + ' modifié avec succès'})
            return redirect('projets:partial_clients')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = ClientForm(instance=client)
    return render(request, 'projets/partials/clients.html', {'form': form})


@chef_projet_required
def supprimer_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    client.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Client ' + client.nom + ' supprimé avec succès.'})
    messages.success(request, 'Client supprimé avec succès.')
    return redirect('projets:partial_clients')


@chef_projet_required
def ajouter_entreprise(request):
    if request.method == 'POST':
        form = EntrepriseForm(request.POST)
        if form.is_valid():
            entreprise = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Entreprise ' + entreprise.nom + ' ajoutée avec succès'})
            return redirect('projets:partial_entreprises')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = EntrepriseForm()
    return render(request, 'projets/partials/entreprises.html', {'form': form, 'entreprise': entreprise})


@chef_projet_required
def modifier_entreprise(request, entreprise_id):
    entreprise = get_object_or_404(Entreprise, id=entreprise_id)
    if request.method == 'POST':
        form = EntrepriseForm(request.POST, instance=entreprise)
        if form.is_valid():
            entreprise = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': f'Entreprise {entreprise.nom} modifiée avec succès'})
            messages.success(request, f'Entreprise {entreprise.nom} modifiée avec succès')
            return redirect('projets:partial_entreprises')
        if request.GET.get('modal') == 'true':
            errors = {field: [str(error) for error in error_list] for field, error_list in form.errors.items()}
            return JsonResponse({'success': False, 'errors': errors}, status=400)
    else:
        form = EntrepriseForm(instance=entreprise)
    return render(request, 'projets/partials/entreprises.html', {'form': form, 'entreprise': entreprise})


@chef_projet_required
def supprimer_entreprise(request, entreprise_id):
    entreprise = get_object_or_404(Entreprise, id=entreprise_id)
    entreprise.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Entreprise' + entreprise.nom + ' supprimée avec succès.'})
    messages.success(request, 'Entreprise supprimé avec succès.')
    return redirect('projets:partial_entreprises')


@chef_projet_required
def ajouter_personnel(request):
    if request.method == 'POST':
        form = PersonnelForm(request.POST)
        if form.is_valid():
            personnel = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Le personnel ' + personnel.nom + ' a été ajouté avec succès'})
            return redirect('projets:partial_personnel')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = PersonnelForm()
    return render(request, 'projets/partials/personnel.html', {'form': form})


@chef_projet_required
def modifier_personnel(request, personnel_id):
    personnel = get_object_or_404(Personnel, id=personnel_id)
    if request.method == 'POST':
        form = PersonnelForm(request.POST, instance=personnel)
        if form.is_valid():
            personnel = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Personnel ' + personnel.nom + ' modifié avec succès'})
        elif request.GET.get('modal') == 'true':
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'error': 'Méthode non supportée'}, status=400)


@chef_projet_required
def supprimer_personnel(request, personnel_id):
    personnel = get_object_or_404(Personnel, id=personnel_id)
    personnel.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Personnel ' + personnel.nom + ' supprimé avec succès.'})
    messages.success(request, 'Personnel supprimé avec succès.')
    return redirect('projets:partial_personnel')


@chef_projet_required
def ajouter_materiel(request):
    if request.method == 'POST':
        form = MaterielForm(request.POST)
        if form.is_valid():
            materiel = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Le matériel ' + materiel.designation + ' a été ajouté avec succès'})
            return redirect('projets:partial_materiel')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = MaterielForm()
    return render(request, 'projets/partials/materiel.html', {'form': form})


@chef_projet_required
def modifier_materiel(request, materiel_id):
    materiel = get_object_or_404(Materiel, id=materiel_id)
    if request.method == 'POST':
        form = MaterielForm(request.POST, instance=materiel)
        if form.is_valid():
            materiel = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Matériel ' + materiel.designation + ' modifié avec succès'})
        elif request.GET.get('modal') == 'true':
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'error': 'Méthode non supportée'}, status=400)


@chef_projet_required
def supprimer_materiel(request, materiel_id):
    from django.db.models import ProtectedError

    materiel = get_object_or_404(Materiel, id=materiel_id)
    designation = materiel.designation

    # Vérifier les références avant de tenter la suppression
    affectations = materiel.affectations.select_related('atelier', 'atelier__projet')
    nb_affectations = affectations.count()

    if nb_affectations:
        # Construire un message détaillé et utile
        ateliers_info = []
        for aff in affectations[:5]:  # max 5 pour ne pas surcharger
            fin = aff.date_fin.strftime('%d/%m/%Y') if aff.date_fin else 'en cours'
            ateliers_info.append(
                f"• Atelier {aff.atelier.code} – {aff.atelier.libelle} "
                f"(projet : {aff.atelier.projet.nom}, "
                f"depuis le {aff.date_debut.strftime('%d/%m/%Y')}, {fin})"
            )

        if nb_affectations > 5:
            ateliers_info.append(f"• … et {nb_affectations - 5} autre(s)")

        message = (
            f"Impossible de supprimer « {designation} » : ce matériel est "
            f"actuellement affecté à {nb_affectations} atelier(s).\n\n"
            + "\n".join(ateliers_info) +
            "\n\nPour supprimer ce matériel, retirez-le d'abord de tous les "
            "ateliers, ou désactivez-le (case « Actif »)."
        )

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect('projets:partial_materiel')

    try:
        materiel.delete()
    except ProtectedError as e:
        message = (
            f"Impossible de supprimer « {designation} » : "
            f"des données y sont rattachées."
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': message}, status=400)
        messages.error(request, message)
        return redirect('projets:partial_materiel')

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f"Matériel « {designation} » supprimé avec succès.",
        })
    messages.success(request, f"Matériel « {designation} » supprimé avec succès.")
    return redirect('projets:partial_materiel')

@chef_projet_required
def importer_materiels(request):
    """
    Import de matériels depuis un texte collé (Excel, CSV, etc.).

    Query params :
        - dry_run=1 : analyse seulement, aucun enregistrement en base
        - dry_run=0 (défaut) : applique réellement

    POST data :
        - texte : le texte collé
        - has_header : 'auto' | 'true' | 'false'
        - create_types : 'true' | 'false'
        - update_existing : 'true' | 'false'
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Méthode non supportée.'}, status=405)

    texte = request.POST.get('texte', '')
    has_header_str = request.POST.get('has_header', 'auto')
    create_types = request.POST.get('create_types', 'false').lower() == 'true'
    update_existing = request.POST.get('update_existing', 'false').lower() == 'true'
    dry_run = request.GET.get('dry_run', '1') == '1'

    # Conversion has_header
    if has_header_str == 'true':
        has_header = True
    elif has_header_str == 'false':
        has_header = False
    else:
        has_header = None

    # Parsing
    lignes, warnings = parser_import_materiel(texte, has_header=has_header)

    if not lignes:
        return JsonResponse({
            'success': False,
            'message': 'Aucune ligne exploitable.',
            'warnings': warnings,
        }, status=400)

    # Préparer les types existants
    types_existants = {t.nom.lower().strip(): t for t in TypeMateriel.objects.all()}

    created = []
    updated = []
    ignored = []
    errors = []

    for ligne in lignes:
        num = ligne['numero']
        designation = (ligne['designation'] or '').strip()
        type_nom = (ligne['type'] or '').strip()

        if not designation:
            errors.append({
                'numero': num,
                'ligne': ligne['_brut'],
                'raison': "Désignation vide.",
            })
            continue

        if not type_nom:
            errors.append({
                'numero': num,
                'ligne': ligne['_brut'],
                'raison': "Type vide.",
            })
            continue

        # Recherche du type
        type_key = type_nom.lower().strip()
        type_materiel = types_existants.get(type_key)

        if not type_materiel:
            if create_types and not dry_run:
                # Créer le type sans icône
                type_materiel = TypeMateriel.objects.create(nom=type_nom, actif=True)
                types_existants[type_key] = type_materiel
            elif create_types and dry_run:
                # Simuler la création
                type_materiel = None  # sera créé à l'application
                # On continue avec un type factice pour le rapport
                pass
            else:
                # Type inconnu, proposer les types les plus proches
                suggestions = [
                    t.nom for t in TypeMateriel.objects.all()
                    if type_key in t.nom.lower() or t.nom.lower() in type_key
                ][:3]
                raison = f"Type « {type_nom} » introuvable."
                if suggestions:
                    raison += f" Suggestions : {', '.join(suggestions)}."
                errors.append({
                    'numero': num,
                    'ligne': ligne['_brut'],
                    'raison': raison,
                })
                continue

        # === Unicité par N° Parc ===
        no_parc = (ligne['immatriculation'] or '').strip()

        existant = None
        if no_parc:
            existant = Materiel.objects.filter(immatriculation=no_parc).first()

        if existant:
            if update_existing and not dry_run:
                existant.designation = designation
                existant.type_materiel = type_materiel
                existant.unite = ligne['unite'] or existant.unite
                if ligne['prix'] is not None:
                    existant.prix_unitaire = ligne['prix']
                existant.actif = ligne['actif']
                existant.save()
                updated.append({
                    'numero': num,
                    'designation': designation,
                    'type': type_materiel.nom if type_materiel else type_nom,
                })
            elif update_existing and dry_run:
                updated.append({
                    'numero': num,
                    'designation': designation,
                    'type': type_nom,
                })
            else:
                ignored.append({
                    'numero': num,
                    'designation': designation,
                    'raison': f"Un matériel avec le N° Parc « {no_parc} » existe déjà.",
                })
            continue

        # Créer le matériel
        if dry_run:
            created.append({
                'numero': num,
                'designation': designation,
                'type': type_nom,
            })
        else:
            Materiel.objects.create(
                designation=designation,
                type_materiel=type_materiel,
                immatriculation=no_parc,
                unite=ligne['unite'] or '',
                prix_unitaire=ligne['prix'] or Decimal('0.00'),
                actif=ligne['actif'],
            )
            created.append({
                'numero': num,
                'designation': designation,
                'type': type_materiel.nom if type_materiel else type_nom,
            })

    # Réponse
    return JsonResponse({
        'success': True,
        'dry_run': dry_run,
        'created': created,
        'updated': updated,
        'ignored': ignored,
        'errors': errors,
        'warnings': warnings,
        'total_lignes': len(lignes),
    })

@chef_projet_required
def ajouter_transport(request):
    if request.method == 'POST':
        form = TransportForm(request.POST)
        if form.is_valid():
            transport = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Le transport ' + transport.designation + ' a été ajouté avec succès'})
            return redirect('projets:partial_transports')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = TransportForm()
    return render(request, 'projets/partials/transport.html', {'form': form})


@chef_projet_required
def modifier_transport(request, transport_id):
    transport = get_object_or_404(Transport, id=transport_id)
    if request.method == 'POST':
        form = TransportForm(request.POST, instance=transport)
        if form.is_valid():
            transport = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Transport ' + transport.designation + ' modifié avec succès'})
        elif request.GET.get('modal') == 'true':
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'error': 'Méthode non supportée'}, status=400)


@chef_projet_required
def supprimer_transport(request, transport_id):
    transport = get_object_or_404(Transport, id=transport_id)
    transport.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Transport ' + transport.designation + ' supprimé avec succès.'})
    messages.success(request, 'Transport supprimé avec succès.')
    return redirect('projets:partial_transports')


@chef_projet_required
def ajouter_location(request):
    if request.method == 'POST':
        form = LocationForm(request.POST)
        if form.is_valid():
            location = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'La location ' + location.designation + ' a été ajoutée avec succès'})
            return redirect('projets:partial_locations')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = LocationForm()
    return render(request, 'projets/partials/locations.html', {'form': form})


@chef_projet_required
def modifier_location(request, location_id):
    location = get_object_or_404(Location, id=location_id)
    if request.method == 'POST':
        form = LocationForm(request.POST, instance=location)
        if form.is_valid():
            location = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Location ' + location.designation + ' modifiée avec succès'})
        elif request.GET.get('modal') == 'true':
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'error': 'Méthode non supportée'}, status=400)


@chef_projet_required
def supprimer_location(request, location_id):
    location = get_object_or_404(Location, id=location_id)
    location.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Location ' + location.designation + ' supprimée avec succès.'})
    messages.success(request, 'Location supprimée avec succès.')
    return redirect('projets:partial_locations')


@chef_projet_required
def ajouter_sous_traitance(request):
    if request.method == 'POST':
        form = SousTraitanceForm(request.POST)
        if form.is_valid():
            sous_traitance = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'La sous-traitance ' + sous_traitance.designation + ' a été ajoutée avec succès'})
            return redirect('projets:partial_sous_traitances')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = SousTraitanceForm()
    return render(request, 'projets/partials/sous_traitances.html', {'form': form})


@chef_projet_required
def modifier_sous_traitance(request, sous_traitance_id):
    sous_traitance = get_object_or_404(SousTraitance, id=sous_traitance_id)
    if request.method == 'POST':
        form = SousTraitanceForm(request.POST, instance=sous_traitance)
        if form.is_valid():
            sous_traitance = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Sous-traitance ' + sous_traitance.designation + ' modifiée avec succès'})
        elif request.GET.get('modal') == 'true':
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'error': 'Méthode non supportnée'}, status=400)


@chef_projet_required
def supprimer_sous_traitance(request, sous_traitance_id):
    sous_traitance = get_object_or_404(SousTraitance, id=sous_traitance_id)
    sous_traitance.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Sous-traitance ' + sous_traitance.designation + ' supprimée avec succès.'})
    messages.success(request, 'Sous-traitance supprimée avec succès.')
    return redirect('projets:partial_sous_traitances')


@chef_projet_required
def ajouter_consommable(request):
    if request.method == 'POST':
        form = ConsommableForm(request.POST)
        if form.is_valid():
            consommable = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Le consommable ' + consommable.designation + ' a été ajouté avec succès'})
            return redirect('projets:partial_consommables')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = ConsommableForm()
    return render(request, 'projets/partials/consommables.html', {'form': form})


@chef_projet_required
def modifier_consommable(request, consommable_id):
    consommable = get_object_or_404(Consommable, id=consommable_id)
    if request.method == 'POST':
        form = ConsommableForm(request.POST, instance=consommable)
        if form.is_valid():
            consommable = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Consommable ' + consommable.designation + ' modifié avec succès'})
        elif request.GET.get('modal') == 'true':
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'error': 'Méthode non supportée'}, status=400)


@chef_projet_required
def supprimer_consommable(request, consommable_id):
    consommable = get_object_or_404(Consommable, id=consommable_id)
    consommable.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Consommable ' + consommable.designation + ' supprimé avec succès.'})
    messages.success(request, 'Consommable supprimé avec succès.')
    return redirect('projets:partial_consommables')


@chef_projet_required
def ajouter_fourniture(request):
    if request.method == 'POST':
        form = FournitureForm(request.POST)
        if form.is_valid():
            fourniture = form.save()
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'La fourniture ' + fourniture.designation + ' a été ajoutée avec succès'})
            return redirect('projets:partial_fournitures')
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'errors': form.errors})
    else:
        form = FournitureForm()
    return render(request, 'projets/partials/fournitures.html', {'form': form})


@chef_projet_required
def modifier_fourniture(request, fourniture_id):
    fourniture = get_object_or_404(Fourniture, id=fourniture_id)
    if request.method == 'POST':
        form = FournitureForm(request.POST, instance=fourniture)
        if form.is_valid():
            fourniture = form.save()
            if request.GET.get('modal') == 'true':
                return JsonResponse({'success': True, 'message': 'Fourniture ' + fourniture.designation + ' modifiée avec succès'})
        elif request.GET.get('modal') == 'true':
            return JsonResponse({'success': False, 'errors': form.errors.get_json_data()}, status=400)
    return JsonResponse({'error': 'Méthode non supportée'}, status=400)


@chef_projet_required
def supprimer_fourniture(request, fourniture_id):
    fourniture = get_object_or_404(Fourniture, id=fourniture_id)
    fourniture.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Fourniture ' + fourniture.designation + ' supprimée avec succès.'})
    messages.success(request, 'Fourniture supprimé avec succès.')
    return redirect('projets:partial_fournitures')