from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from projets.decorators import chef_projet_required
from projets.forms import (
    ClientForm, ConsommableForm, EntrepriseForm, FournitureForm, IngenieurForm,
    LocationForm, MaterielForm, PersonnelForm, SousTraitanceForm, TransportForm,
)
from projets.models import (
    Client, Consommable, Entreprise, Fourniture, Ingenieur, Location, Materiel,
    Personnel, SousTraitance, Transport,
)


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
    materiel = Materiel.objects.all()
    return render(request, 'projets/partials/materiel.html', {'materiel': materiel})


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
    return render(request, 'projets/base_donnees.html')


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
    materiel = get_object_or_404(Materiel, id=materiel_id)
    materiel.delete()
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': 'Matériel ' + materiel.designation + ' supprimé avec succès.'})
    messages.success(request, 'Matériel supprimé avec succès.')
    return redirect('projets:partial_materiel')


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