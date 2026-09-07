from decimal import Decimal
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, OuterRef, Subquery, Sum, Value, When
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from projets.decorators import can_edit_projet, can_view_projet, chef_projet_required
from projets.forms import (
    DepenseRapportJournalierFormSet, DepenseSituationMensuelleFormSet,
    DocumentSituationMensuelleFormSet, RecetteSituationMensuelleFormSet, RapportJournalierForm,
    SituationMensuelleForm, StockRapportJournalierFormSet,
    StockSituationMensuelleFormSet,
)
from projets.models import *

RECETTE_INITIAL_DATA = [
    {'rubrique': RecetteSituationMensuelle.Rubrique.TRAVAUX_REALISES},
    {'rubrique': RecetteSituationMensuelle.Rubrique.REVISION_PRIX},
    {'rubrique': RecetteSituationMensuelle.Rubrique.REFACTURATION_EXTERNE},
]


def _recettes_formset(*args, situation=None, **kwargs):
    if args and args[0] is not None and 'recettes-TOTAL_FORMS' not in args[0]:
        post_data = args[0].copy()
        rubriques = [
            RecetteSituationMensuelle.Rubrique.TRAVAUX_REALISES,
            RecetteSituationMensuelle.Rubrique.REVISION_PRIX,
            RecetteSituationMensuelle.Rubrique.REFACTURATION_EXTERNE,
        ]
        montants = [post_data.get('chiffre_affaires', '0'), '0', '0']
        post_data.update({
            'recettes-TOTAL_FORMS': str(len(rubriques)),
            'recettes-INITIAL_FORMS': '0',
            'recettes-MIN_NUM_FORMS': '0',
            'recettes-MAX_NUM_FORMS': '1000',
        })
        for index, (rubrique, montant) in enumerate(zip(rubriques, montants)):
            post_data.update({
                f'recettes-{index}-rubrique': rubrique,
                f'recettes-{index}-montant': montant,
            })
        args = (post_data, *args[1:])
    if situation is None or not situation.pk:
        kwargs.setdefault('initial', RECETTE_INITIAL_DATA)
    else:
        kwargs.setdefault('queryset', situation.recettes.order_by(
            Case(
                When(rubrique=RecetteSituationMensuelle.Rubrique.TRAVAUX_REALISES, then=Value(1)),
                When(rubrique=RecetteSituationMensuelle.Rubrique.REVISION_PRIX, then=Value(2)),
                When(rubrique=RecetteSituationMensuelle.Rubrique.REFACTURATION_EXTERNE, then=Value(3)),
                output_field=IntegerField(),
            )
        ))
    return RecetteSituationMensuelleFormSet(*args, instance=situation, **kwargs)


def _synchroniser_chiffre_affaires(situation):
    total = situation.recettes.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
    situation.chiffre_affaires = total
    situation.save(update_fields=['chiffre_affaires', 'updated_at'])


@login_required
@can_view_projet
def rapports_journaliers(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    rapports = projet.rapports_journaliers.annotate(
        total_depenses_annotated=Coalesce(
            Sum('depenses__montant'), Value(Decimal('0.00'))
        )
    ).prefetch_related('depenses')
    return render(request, 'projets/suivi/rapports_journaliers.html', {
        'projet': projet,
        'rapports': rapports,
    })

#----------------------- Suivi d'execution ---------------------------
def _projet_travaux_or_403(projet_id):
    projet = get_object_or_404(Projet.objects.select_related('dossier'), id=projet_id)
    if not projet.dossier_id or projet.dossier.activite != Dossier.Activite.TRAVAUX:
        raise PermissionDenied("Ce suivi est réservé aux dossiers de travaux.")
    return projet

@login_required
@can_edit_projet
def ajouter_rapport_journalier(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    
    if request.method == 'POST':
        form = RapportJournalierForm(request.POST, request.FILES, projet=projet)
        depenses = DepenseRapportJournalierFormSet(request.POST)
        stocks = StockRapportJournalierFormSet(request.POST)
        
        if form.is_valid() and depenses.is_valid() and stocks.is_valid():
            rapport = form.save(commit=False)
            rapport.projet = projet
            
            # Gestion du fichier
            fichier = request.FILES.get('document')
            if fichier:
                rapport.document = fichier
                rapport.original_filename = fichier.name
            
            try:
                with transaction.atomic():
                    rapport.save()
                    depenses.instance = rapport
                    stocks.instance = rapport
                    depenses.save()
                    stocks.save()
            except IntegrityError:
                messages.error(
                    request,
                    'Un rapport journalier existe déjà pour cette date dans ce projet.',
                )
                return redirect('projets:rapports_journaliers', projet_id=projet.id)
            
            messages.success(request, 'Rapport journalier enregistré avec succès.')
            return redirect('projets:rapports_journaliers', projet_id=projet.id)
        else:
            # Afficher les erreurs
            error_messages = []
            if form.errors:
                error_messages.append(f"Formulaire: {form.errors.as_text()}")
            if depenses.errors:
                error_messages.append(f"Dépenses: {depenses.errors.as_text()}")
            if stocks.errors:
                error_messages.append(f"Stocks: {stocks.errors.as_text()}")
            
            messages.error(request, f"Erreurs: {'; '.join(error_messages)}")
            return render(request, 'projets/suivi/ajouter_rapport_journalier.html', {
                'projet': projet,
                'form': form,
                'depenses': depenses,
                'stocks': stocks,
                'depenses_groupees': _grouper_depenses_par_categorie(depenses),
            })
    
    today = timezone.now().date()
    form = RapportJournalierForm(initial={
        'date': today.strftime('%Y-%m-%d'),
        'redacteur': request.user.get_full_name() or request.user.username,
    })
    depenses = DepenseRapportJournalierFormSet()
    stocks = StockRapportJournalierFormSet()
    return render(request, 'projets/suivi/ajouter_rapport_journalier.html', {
        'projet': projet,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'depenses_groupees': _grouper_depenses_par_categorie(depenses),
    })

@login_required
@can_view_projet
def detail_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(
        RapportJournalier.objects.annotate(
            total_depenses_annotated=Coalesce(
                Sum('depenses__montant'), Value(Decimal('0.00'))
            )
        ).prefetch_related('depenses', 'stocks'),
        id=rapport_id, projet=projet
    )
    depenses_groupees = []
    for value, label in CategorieDepenseTravaux.choices:
        depenses_categorie = [d for d in rapport.depenses.all() if d.categorie == value]
        if depenses_categorie:
            total = sum((d.montant for d in depenses_categorie), Decimal('0.00'))
            depenses_groupees.append((value, label, depenses_categorie, total))
    return render(request, 'projets/suivi/detail_rapport_journalier.html', {
        'projet': projet,
        'rapport': rapport,
        'depenses_groupees': depenses_groupees,
    })


def _referentiel_depenses():
    """Entrées du référentiel (base de données) proposées par catégorie de dépense."""
    def options(queryset, champ_designation, champ_prix):
        return [
            {
                'designation': getattr(obj, champ_designation),
                'unite': obj.unite or '',
                'prix': getattr(obj, champ_prix) or Decimal('0.00'),
            }
            for obj in queryset
        ]

    return {
        CategorieDepenseTravaux.PERSONNEL: options(
            Personnel.objects.filter(actif=True).order_by('nom'), 'nom', 'tarif'
        ),
        CategorieDepenseTravaux.MATERIEL: options(
            Materiel.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
        CategorieDepenseTravaux.LOCATION: options(
            Location.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
        CategorieDepenseTravaux.SOUS_TRAITANCE: options(
            SousTraitance.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
        CategorieDepenseTravaux.FOURNITURE: options(
            Fourniture.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
        CategorieDepenseTravaux.CONSOMMABLE: options(
            Consommable.objects.filter(actif=True).order_by('designation'), 'designation', 'prix_unitaire'
        ),
    }


def _grouper_depenses_par_categorie(depenses_formset):
    groupes = {value: [] for value, label in CategorieDepenseTravaux.choices}
    for depense_form in depenses_formset.forms:
        categorie = depense_form.instance.categorie
        if categorie in groupes:
            groupes[categorie].append(depense_form)
    referentiel = _referentiel_depenses()
    return [
        (
            value, 'Consommable & Carburant' if value == CategorieDepenseTravaux.CONSOMMABLE else label, groupes[value],
            sum((f.instance.montant or Decimal('0.00') for f in groupes[value]), Decimal('0.00')),
            referentiel.get(value, []),
        )
        for value, label in CategorieDepenseTravaux.choices
    ]


@login_required
@can_edit_projet
def formulaire_rapport_journalier(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    
    if request.method == 'POST':
        form = RapportJournalierForm(request.POST, request.FILES, projet=projet)
        depenses = DepenseRapportJournalierFormSet(request.POST)
        stocks = StockRapportJournalierFormSet(request.POST)
        
        if form.is_valid() and depenses.is_valid() and stocks.is_valid():
            rapport = form.save(commit=False)
            rapport.projet = projet
            
            # Gestion du fichier
            fichier = request.FILES.get('document')
            if fichier:
                rapport.document = fichier
                rapport.original_filename = fichier.name
            
            try:
                with transaction.atomic():
                    rapport.save()
                    depenses.instance = rapport
                    stocks.instance = rapport
                    depenses.save()
                    stocks.save()
            except IntegrityError:
                messages.error(
                    request,
                    'Un rapport journalier existe déjà pour cette date dans ce projet.',
                )
                return redirect('projets:rapports_journaliers', projet_id=projet.id)
            
            messages.success(request, 'Rapport journalier enregistré avec succès.')
            return redirect('projets:rapports_journaliers', projet_id=projet.id)
        else:
            # Afficher les erreurs
            error_messages = []
            if form.errors:
                error_messages.append(f"Formulaire: {form.errors.as_text()}")
            if depenses.errors:
                error_messages.append(f"Dépenses: {depenses.errors.as_text()}")
            if stocks.errors:
                error_messages.append(f"Stocks: {stocks.errors.as_text()}")
            
            messages.error(request, f"Erreurs: {'; '.join(error_messages)}")
            return render(request, 'projets/suivi/_formulaire_rapport_journalier.html', {
                'projet': projet,
                'form': form,
                'depenses': depenses,
                'stocks': stocks,
                'depenses_groupees': _grouper_depenses_par_categorie(depenses),
                'erreurs': True,
            })
    else:
        # Initialiser avec la date au format ISO
        today = timezone.now().date()
        form = RapportJournalierForm(initial={
            'date': today.strftime('%Y-%m-%d'),  # Format ISO explicite
            'redacteur': request.user.get_full_name() or request.user.username
        })
        depenses = DepenseRapportJournalierFormSet()
        stocks = StockRapportJournalierFormSet()
    
    depenses_groupees = _grouper_depenses_par_categorie(depenses)
    
    return render(request, 'projets/suivi/_formulaire_rapport_journalier.html', {
        'projet': projet,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'depenses_groupees': depenses_groupees,
    })


@login_required
@can_edit_projet
def modifier_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)

    if request.method == 'POST':
        form = RapportJournalierForm(
            request.POST, request.FILES, instance=rapport, projet=projet
        )
        depenses = DepenseRapportJournalierFormSet(request.POST, instance=rapport)
        stocks = StockRapportJournalierFormSet(request.POST, instance=rapport)
        if form.is_valid() and depenses.is_valid() and stocks.is_valid():
            rapport = form.save(commit=False)
            fichier = request.FILES.get('document')
            with transaction.atomic():
                if fichier:
                    rapport.document = fichier
                    rapport.original_filename = fichier.name
                rapport.save()
                depenses.save()
                stocks.save()
            messages.success(request, 'Rapport journalier modifié.')
            return redirect('projets:rapports_journaliers', projet_id=projet.id)
        messages.error(request, "Le rapport journalier n'a pas pu être modifié. Vérifiez les informations saisies.")
        return render(request, 'projets/suivi/modifier_rapport_journalier.html', {
            'projet': projet,
            'rapport': rapport,
            'form': form,
            'depenses': depenses,
            'stocks': stocks,
            'depenses_groupees': _grouper_depenses_par_categorie(depenses),
        })
    else:
        form = RapportJournalierForm(instance=rapport)
        # S'assurer que la date est au bon format
        if rapport.date:
            form.initial['date'] = rapport.date.strftime('%Y-%m-%d')
        depenses = DepenseRapportJournalierFormSet(instance=rapport)
        stocks = StockRapportJournalierFormSet(instance=rapport)

    return render(request, 'projets/suivi/modifier_rapport_journalier.html', {
        'projet': projet,
        'rapport': rapport,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'depenses_groupees': _grouper_depenses_par_categorie(depenses),
    })


@login_required
@can_edit_projet
def supprimer_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)
    if request.method == 'POST':
        rapport.delete()
        messages.success(request, 'Rapport journalier supprimé.')
    return redirect('projets:rapports_journaliers', projet_id=projet_id)


@login_required
@can_edit_projet
def supprimer_document_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)
    if request.method == 'POST':
        if rapport.document:
            rapport.document = None
            rapport.original_filename = ''
            rapport.save(update_fields=['document', 'original_filename'])
            messages.success(request, 'Document supprimé du rapport journalier.')
        else:
            messages.info(request, 'Aucun document à supprimer.')
    return redirect('projets:modifier_rapport_journalier', projet_id=projet_id, rapport_id=rapport_id)


@login_required
@chef_projet_required
def situations_mensuelles(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    depenses_total = DepenseSituationMensuelle.objects.filter(
        situation_id=OuterRef('pk')
    ).values('situation_id').annotate(total=Sum('montant')).values('total')
    stocks_total = StockSituationMensuelle.objects.filter(
        situation_id=OuterRef('pk')
    ).values('situation_id').annotate(total=Sum('valeur')).values('total')
    situations = projet.situations_mensuelles.annotate(
        total_depenses_annotated=Coalesce(
            Subquery(depenses_total), Value(Decimal('0.00'))
        ),
        total_stock_annotated=Coalesce(
            Subquery(stocks_total), Value(Decimal('0.00'))
        ),
    ).prefetch_related('depenses', 'stocks')
    return render(request, 'projets/suivi/situations_mensuelles.html', {
        'projet': projet,
        'situations': situations,
    })


@login_required
@chef_projet_required
def apercu_situation_mensuelle(request, projet_id, situation_id):
    projet = _projet_travaux_or_403(projet_id)
    situation = get_object_or_404(
        SituationMensuelle.objects.prefetch_related('depenses', 'stocks', 'documents', 'recettes'),
        id=situation_id,
        projet=projet,
    )
    recettes = situation.recettes.order_by(
        Case(
            When(rubrique=RecetteSituationMensuelle.Rubrique.TRAVAUX_REALISES, then=Value(1)),
            When(rubrique=RecetteSituationMensuelle.Rubrique.REVISION_PRIX, then=Value(2)),
            When(rubrique=RecetteSituationMensuelle.Rubrique.REFACTURATION_EXTERNE, then=Value(3)),
            output_field=IntegerField(),
        )
    )
    depenses_par_categorie = [
        (value, label, sum((depense.montant or Decimal('0.00') for depense in situation.depenses.filter(categorie=value)), Decimal('0.00')), list(situation.depenses.filter(categorie=value)))
        for value, label in CategorieDepenseTravaux.choices
        if situation.depenses.filter(categorie=value).exists()
    ]
    return render(request, 'projets/suivi/apercu_situation_mensuelle.html', {
        'projet': projet,
        'situation': situation,
        'recettes': recettes,
        'depenses_par_categorie': [(value, label, depenses, total) for value, label, total, depenses in depenses_par_categorie],
        'stocks': situation.stocks.all(),
        'documents': situation.documents.all(),
    })


def _group_situation_expenses(formset):
    groups = {value: [] for value, label in CategorieDepenseTravaux.choices}
    for form in formset.forms:
        if form.instance.categorie in groups:
            groups[form.instance.categorie].append(form)
    return [
        (
            value,
            label,
            groups[value],
            sum((form.instance.montant or Decimal('0.00') for form in groups[value]), Decimal('0.00')),
        )
        for value, label in CategorieDepenseTravaux.choices
    ]

@login_required
@can_view_projet
def upload_rapport_document(request, projet_id, rapport_id):
    """Upload un document pour un rapport journalier"""
    projet = get_object_or_404(Projet, id=projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)
    
    if request.method != 'POST':
        messages.error(request, "Méthode non autorisée")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    fichier = request.FILES.get('document')
    if not fichier:
        messages.error(request, "Aucun fichier sélectionné")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    # Vérifier la taille (max 10MB)
    if fichier.size > 10 * 1024 * 1024:
        messages.error(request, "Le fichier ne doit pas dépasser 10MB")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    # Vérifier le type de fichier
    valid_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif']
    ext = os.path.splitext(fichier.name)[1].lower()
    if ext not in valid_extensions:
        messages.error(request, f"Type de fichier non supporté. Utilisez: {', '.join(valid_extensions)}")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    try:
        # Supprimer l'ancien document s'il existe
        # Sauvegarder le nouveau document
        rapport.document = fichier
        rapport.original_filename = fichier.name
        rapport.save()
        
        messages.success(request, f"Document '{fichier.name}' ajouté avec succès au rapport du {rapport.date.strftime('%d/%m/%Y')}")
    except Exception as e:
        messages.error(request, f"Erreur lors de l'upload: {str(e)}")
    
    return redirect('projets:suivi_execution', projet_id=projet_id)


@login_required
@chef_projet_required
def ajouter_situation_mensuelle(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    depenses = DepenseSituationMensuelleFormSet(request.POST or None)
    stocks = StockSituationMensuelleFormSet(request.POST or None)
    recettes = _recettes_formset(request.POST or None)
    documents = DocumentSituationMensuelleFormSet(request.POST or None, request.FILES or None)
    if request.method == 'POST':
        form = SituationMensuelleForm(request.POST, request.FILES, projet=projet)
        if form.is_valid():
            situation = form.save(commit=False)
            situation.projet = projet
            periode = form.cleaned_data.get('periode')
            if periode:
                year, month = (int(part) for part in periode.split('-'))
                situation.annee, situation.mois = year, month
            depenses = DepenseSituationMensuelleFormSet(request.POST, instance=situation)
            stocks = StockSituationMensuelleFormSet(request.POST, instance=situation)
            recettes = _recettes_formset(request.POST, situation=situation)
            documents = DocumentSituationMensuelleFormSet(request.POST, request.FILES, instance=situation)
            if depenses.is_valid() and stocks.is_valid() and recettes.is_valid() and documents.is_valid():
                try:
                    with transaction.atomic():
                        situation.save()
                        depenses.instance = situation
                        stocks.instance = situation
                        depenses.save()
                        stocks.save()
                        recettes.save()
                        _synchroniser_chiffre_affaires(situation)
                        documents.save()
                except IntegrityError:
                    form.add_error('mois', 'Une situation existe déjà pour cette période.')
                else:
                    messages.success(request, 'Situation mensuelle enregistrée.')
                    return redirect('projets:situations_mensuelles', projet_id=projet.id)
            else:
                messages.error(request, 'La situation n\'a pas été enregistrée. Corrigez les erreurs indiquées.')
    else:
        form = SituationMensuelleForm(initial={
            'annee': timezone.now().year,
            'mois': timezone.now().month,
        })
        depenses = DepenseSituationMensuelleFormSet()
        stocks = StockSituationMensuelleFormSet()
        recettes = _recettes_formset()
        documents = DocumentSituationMensuelleFormSet()

    return render(request, 'projets/suivi/ajouter_situation_mensuelle.html', {
        'projet': projet,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'recettes': recettes,
        'documents': documents,
        'depenses_groupees': _group_situation_expenses(depenses),
    })


@login_required
@chef_projet_required
def modifier_situation_mensuelle(request, projet_id, situation_id):
    projet = _projet_travaux_or_403(projet_id)
    situation = get_object_or_404(SituationMensuelle, id=situation_id, projet=projet)
    if request.method == 'POST':
        form = SituationMensuelleForm(request.POST, request.FILES, instance=situation, projet=projet)
        depenses = DepenseSituationMensuelleFormSet(request.POST, instance=situation)
        stocks = StockSituationMensuelleFormSet(request.POST, instance=situation)
        recettes = _recettes_formset(request.POST, situation=situation)
        documents = DocumentSituationMensuelleFormSet(request.POST, request.FILES, instance=situation)
        if form.is_valid() and depenses.is_valid() and stocks.is_valid() and recettes.is_valid() and documents.is_valid():
            situation = form.save(commit=False)
            with transaction.atomic():
                situation.save()
                depenses.save()
                stocks.save()
                recettes.save()
                _synchroniser_chiffre_affaires(situation)
                documents.save()
            messages.success(request, 'Situation mensuelle modifiée.')
            return redirect('projets:situations_mensuelles', projet_id=projet.id)
        messages.error(request, 'La situation n\'a pas été enregistrée. Corrigez les erreurs indiquées.')
    else:
        form = SituationMensuelleForm(instance=situation)
        depenses = DepenseSituationMensuelleFormSet(instance=situation)
        stocks = StockSituationMensuelleFormSet(instance=situation)
        recettes = _recettes_formset(situation=situation)
        documents = DocumentSituationMensuelleFormSet(instance=situation)
    return render(request, 'projets/suivi/modifier_situation_mensuelle.html', {
        'projet': projet, 'situation': situation, 'form': form,
        'depenses': depenses, 'stocks': stocks,
        'recettes': recettes,
        'depenses_groupees': _group_situation_expenses(depenses),
        'documents': documents,
    })


@login_required
@chef_projet_required
def supprimer_situation_mensuelle(request, projet_id, situation_id):
    projet = _projet_travaux_or_403(projet_id)
    situation = get_object_or_404(SituationMensuelle, id=situation_id, projet=projet)
    if request.method == 'POST':
        situation.delete()
        messages.success(request, 'Situation mensuelle supprimée.')
    return redirect('projets:situations_mensuelles', projet_id=projet.id)


@login_required
@chef_projet_required
def supprimer_document_situation_mensuelle(request, projet_id, situation_id):
    projet = _projet_travaux_or_403(projet_id)
    situation = get_object_or_404(SituationMensuelle, id=situation_id, projet=projet)
    if request.method == 'POST':
        document = get_object_or_404(DocumentSituationMensuelle, id=request.POST.get('document_id'), situation=situation)
        document.delete()
        messages.success(request, 'Document mensuel supprimé.')
    return redirect('projets:modifier_situation_mensuelle', projet_id=projet.id, situation_id=situation.id)


