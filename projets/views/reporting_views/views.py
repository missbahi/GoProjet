from decimal import Decimal
from datetime import date, timedelta
import logging
import os

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Case, IntegerField, Prefetch, Q, Sum, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from projets.decorators import can_edit_projet, can_view_projet, chef_projet_required, consultation_projet_required
from projets.decorators import can_devalidate_situation_mensuelle, can_validate_situation_mensuelle

from projets.forms import (
    DepenseRapportJournalierFormSet, DepenseSituationMensuelleFormSet,
    DocumentSituationMensuelleFormSet, RecetteSituationMensuelleFormSet,
    RecetteSituationMensuelleInitialFormSet, RapportJournalierForm,
    SituationMensuelleForm, StockRapportJournalierFormSet,
    LigneTravailRapportJournalierFormSet,
    StockSituationMensuelleFormSet, fichiers_rapport_journalier,
)
from projets.models import (
    Projet, SituationMensuelle, RecetteSituationMensuelle,
    DocumentSituationMensuelle, RapportJournalier,
    DocumentRapportJournalier, LigneBordereau, LigneTravailRapportJournalier,
)
from projets.models.projet import Dossier
from projets.models import ChiffreAffaire
from projets.services.chiffre_affaire import synchroniser_situation_ca
from projets.models.suivi_projet import CategorieCharge
from projets.utils.navigation import crumb, project_crumbs
from projets.services.meteo.open_meteo import MeteoIndisponible, meteo_du_jour, meteo_en_ligne_active
from projets.services.realise_bordereau import RealiseLigne, realise_par_ligne


logger = logging.getLogger(__name__)

RAPPORTS_PAR_PAGE = 30


def _enregistrer_documents_rapport(request, rapport):
    for fichier in fichiers_rapport_journalier(request.FILES):
        DocumentRapportJournalier.objects.create(
            rapport=rapport,
            fichier=fichier,
            original_filename=fichier.name,
            taille=fichier.size,
        )


def _format_validation_errors(validation_form):
    errors = validation_form.errors
    if hasattr(errors, 'as_text'):
        return errors.as_text()
    details = []
    non_form_errors = validation_form.non_form_errors()
    if non_form_errors:
        details.append(non_form_errors.as_text())
    for index, form_errors in enumerate(errors):
        if form_errors:
            details.append(f'Formulaire {index}: {form_errors.as_text()}')
    return '\n'.join(details)

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

    should_show_default_recettes = situation is None or not situation.pk or not situation.recettes.exists()
    if should_show_default_recettes:
        kwargs.setdefault('initial', RECETTE_INITIAL_DATA)
        formset_class = RecetteSituationMensuelleInitialFormSet
    else:
        kwargs.setdefault('queryset', situation.recettes.order_by(
            Case(
                When(rubrique=RecetteSituationMensuelle.Rubrique.TRAVAUX_REALISES, then=Value(1)),
                When(rubrique=RecetteSituationMensuelle.Rubrique.REVISION_PRIX, then=Value(2)),
                When(rubrique=RecetteSituationMensuelle.Rubrique.REFACTURATION_EXTERNE, then=Value(3)),
                output_field=IntegerField(),
            )
        ))
        formset_class = RecetteSituationMensuelleFormSet
    formset = formset_class(*args, instance=situation, **kwargs)
    ca = None
    if situation and situation.projet_id and situation.annee and situation.mois:
        ca = situation.ca if situation.ca_id else ChiffreAffaire.objects.filter(
            projet_id=situation.projet_id, periode=date(situation.annee, situation.mois, 1),
            statut=ChiffreAffaire.Statut.VALIDE,
        ).first()
    if ca:
        for recette_form in formset.forms:
            rubrique = recette_form.initial.get('rubrique') or recette_form.instance.rubrique
            if rubrique == RecetteSituationMensuelle.Rubrique.TRAVAUX_REALISES:
                recette_form.fields['montant'].disabled = True
                recette_form.initial['montant'] = ca.montant_mensuel
        formset.ca_source = ca
    return formset


def _synchroniser_chiffre_affaires(situation):
    synchroniser_situation_ca(situation)
    total = situation.recettes.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')
    updated_at = timezone.now()
    situation.chiffre_affaires = total
    situation.updated_at = updated_at
    SituationMensuelle.objects.filter(pk=situation.pk).update(
        chiffre_affaires=total,
        updated_at=updated_at,
    )


def _creer_rubriques_recettes_manquantes(situation):
    for recette in RECETTE_INITIAL_DATA:
        RecetteSituationMensuelle.objects.get_or_create(
            situation=situation,
            rubrique=recette['rubrique'],
            defaults={'montant': Decimal('0.00')},
        )


@login_required
@can_view_projet
def rapports_journaliers(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    rapports = projet.rapports_journaliers.annotate(
        total_depenses_annotated=Coalesce(
            Sum('depenses__montant'), Value(Decimal('0.00'))
        )
    ).prefetch_related('documents_joints').order_by('-date', '-id')
    page = Paginator(rapports, RAPPORTS_PAR_PAGE).get_page(request.GET.get('page'))

    ctx = {
            'projet': projet,
            'rapports': page.object_list,
            'page_obj': page,
            'breadcrumb_items': project_crumbs(projet, crumb("Rapports journaliers")),
        }
    
    if request.headers.get('HX-Request'):
        return render(request, 'projets/rapports/_rapports_journaliers_content.html', ctx)

    return render(request, 'projets/rapports/rapports_journaliers.html', ctx)

#----------------------- Suivi d'execution ---------------------------
def _projet_travaux_or_403(projet_id):
    """Récupère un projet de travaux ou lève une 403."""
    projet = get_object_or_404(Projet.objects.select_related('dossier'), id=projet_id)
    if not projet.dossier_id or projet.dossier.activite != Dossier.Activite.TRAVAUX:
        raise PermissionDenied("Ce suivi est réservé aux dossiers de travaux.")
    return projet

def _date_rapport_par_defaut(projet, aujourd_hui=None):
    """Date proposée pour un nouveau rapport.

    Aujourd'hui s'il n'existe aucun rapport ; sinon le lendemain du dernier
    rapport lorsque celui-ci appartient au mois en cours ; sinon aujourd'hui.
    """
    aujourd_hui = aujourd_hui or timezone.localdate()
    derniere = (
        RapportJournalier.objects.filter(projet=projet)
        .order_by('-date').values_list('date', flat=True).first()
    )
    if derniere and (derniere.year, derniere.month) == (aujourd_hui.year, aujourd_hui.month):
        return derniere + timedelta(days=1)
    return aujourd_hui


def _formsets_reproduits(rapport_source, projet):
    """Formsets dépenses et stocks pré-remplis à partir d'un rapport existant.

    Seules les dépenses et les stocks sont reproduits ; le stock restant du
    rapport source devient le point de départ (entrées et sorties remises à zéro).
    """
    initial_depenses = [
        {
            'categorie': d.categorie,
            'categorie_charge': d.categorie_charge_id,
            'designation': d.designation,
            'quantite': d.quantite,
            'unite': d.unite,
            'prix_unitaire': d.prix_unitaire,
            'observations': d.observations,
        }
        for d in rapport_source.depenses.all()
    ]
    initial_stocks = [
        {
            'designation': s.designation,
            'unite': s.unite,
            'quantite_entree': Decimal('0'),
            'quantite_sortie': Decimal('0'),
            'stock_restant': s.stock_restant,
        }
        for s in rapport_source.stocks.all()
    ]
    depenses = DepenseRapportJournalierFormSet(form_kwargs={'projet': projet}, initial=initial_depenses)
    depenses.extra = len(initial_depenses)
    stocks = StockRapportJournalierFormSet(initial=initial_stocks)
    stocks.extra = len(initial_stocks)
    return depenses, stocks


def _signaler_erreurs_rapport(request, form, depenses, stocks, travaux):
    """Message utilisateur après un échec de validation du rapport."""
    codes_formulaire = {
        erreur.code for erreurs in form.errors.as_data().values() for erreur in erreurs
    }
    seulement_doublon = (
        codes_formulaire == {'doublon'}
        and not depenses.total_error_count()
        and not stocks.total_error_count()
        and not travaux.total_error_count()
    )
    if seulement_doublon:
        messages.warning(
            request,
            'Un rapport existe déjà à cette date : cochez la confirmation pour en créer un autre.',
        )
        return
    error_messages = []
    if form.errors:
        error_messages.append(f"Formulaire: {_format_validation_errors(form)}")
    if depenses.errors:
        error_messages.append(f"Dépenses: {_format_validation_errors(depenses)}")
    if stocks.errors:
        error_messages.append(f"Stocks: {_format_validation_errors(stocks)}")
    if travaux.errors:
        error_messages.append(f"Travaux: {_format_validation_errors(travaux)}")
    messages.error(request, f"Erreurs: {'; '.join(error_messages)}")


def _lignes_bordereau_proposees(projet):
    """Lignes du bordereau proposées dans « Lignes BPU » : hors titres, prix unitaire > 0."""
    return LigneBordereau.objects.filter(lot__projet=projet, est_titre=False, prix_unitaire__gt=0)


def _lignes_bpu(projet, date_ref, exclure_rapport_id=None):
    """Lignes proposées, avec quantité du marché et réalisé à la date du rapport.

    Réalisé : voir projets/services/realise_bordereau.py (cumul officiel le plus
    récent + rapports postérieurs).
    """
    realise = realise_par_ligne(projet, date_ref, exclure_rapport_id=exclure_rapport_id)
    vide = RealiseLigne()
    lignes = (
        _lignes_bordereau_proposees(projet)
        .select_related('lot')
        .order_by('lot__id', 'ordre_affichage', 'id')
    )
    return [
        {
            'id': ligne.pk,
            'numero': ligne.numero or '',
            'designation': ligne.designation,
            'unite': ligne.unite or '',
            'prix': str(ligne.prix_unitaire),
            'quantite_marche': str(ligne.quantite),
            'lot': ligne.lot.nom,
            **realise.get(ligne.pk, vide).as_dict(),
        }
        for ligne in lignes
    ]


def _activites_projet(projet):
    """Activités déjà saisies dans le projet (suggestions du champ Activité)."""
    return list(
        RapportJournalier.objects.filter(projet=projet).exclude(activite='')
        .order_by('activite').values_list('activite', flat=True).distinct()
    )


@login_required
@can_edit_projet
def ajouter_rapport_journalier(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    is_xhr = request.headers.get('HX-Request') == 'true' or request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _build_ctx(form, depenses, stocks, travaux, source=None):
        return {
            'projet': projet,
            'form': form,
            'depenses': depenses,
            'stocks': stocks,
            'travaux': travaux,
            'depenses_groupees': _grouper_depenses_par_categorie(depenses, projet=projet),
            'source': source,
            'rapports_reproductibles': (
                RapportJournalier.objects.filter(projet=projet)
                .only('id', 'date', 'activite').order_by('-date', '-id')[:15]
            ),
            'activites': _activites_projet(projet),
            'meteo_en_ligne': meteo_en_ligne_active() and bool(projet.localisation),
            'a_lignes_bpu': _lignes_bordereau_proposees(projet).exists(),
            'breadcrumb_items': project_crumbs(
                projet,
                crumb("Rapports journaliers", "projets:rapports_journaliers", args=[projet.id]),
                crumb("Nouveau rapport"),
            ),
        }

    if request.method == 'POST':
        form = RapportJournalierForm(request.POST, request.FILES, projet=projet)
        depenses = DepenseRapportJournalierFormSet(request.POST, form_kwargs={'projet': projet})
        stocks = StockRapportJournalierFormSet(request.POST)
        travaux = LigneTravailRapportJournalierFormSet(request.POST, form_kwargs={'projet': projet})

        if (
            form.is_valid()
            and depenses.is_valid()
            and stocks.is_valid()
            and travaux.is_valid()
        ):
            rapport = form.save(commit=False)
            rapport.projet = projet
            with transaction.atomic():
                rapport.save()
                depenses.instance = rapport
                stocks.instance = rapport
                travaux.instance = rapport
                depenses.save()
                stocks.save()
                travaux.save()
                _enregistrer_documents_rapport(request, rapport)

            msg = 'Rapport journalier enregistré avec succès.'
            if is_xhr:
                return JsonResponse({
                    'success': True,
                    'message': msg,
                    'url': reverse('projets:rapports_journaliers', args=[projet.id]),
                })

            messages.success(request, msg)
            return redirect('projets:rapports_journaliers', projet_id=projet.id)

        _signaler_erreurs_rapport(request, form, depenses, stocks, travaux)
        ctx = _build_ctx(form, depenses, stocks, travaux)
        if is_xhr:
            return render(request, 'projets/rapports/_modifier_rapport_journalier_content.html', ctx, status=400)
        return render(request, 'projets/rapports/modifier_rapport_journalier.html', ctx, status=400)

    # GET — nouveau rapport, éventuellement reproduit d'un rapport existant (?depuis=<id>)
    source = None
    if request.GET.get('depuis'):
        source = get_object_or_404(
            RapportJournalier.objects.prefetch_related('depenses', 'stocks'),
            pk=request.GET['depuis'], projet=projet,
        )
    form = RapportJournalierForm(initial={
        'date': _date_rapport_par_defaut(projet).strftime('%Y-%m-%d'),
        'activite': source.activite if source else '',
        'redacteur': request.user.get_full_name() or request.user.username,
    })
    if source:
        depenses, stocks = _formsets_reproduits(source, projet)
    else:
        depenses = DepenseRapportJournalierFormSet(form_kwargs={'projet': projet})
        stocks = StockRapportJournalierFormSet()
    travaux = LigneTravailRapportJournalierFormSet(form_kwargs={'projet': projet})

    ctx = _build_ctx(form, depenses, stocks, travaux, source=source)

    if is_xhr:
        return render(request, 'projets/rapports/_modifier_rapport_journalier_content.html', ctx)
    return render(request, 'projets/rapports/modifier_rapport_journalier.html', ctx)

def _rapport_journalier_complet(projet, rapport_id):
    return get_object_or_404(
        RapportJournalier.objects.prefetch_related(
            'stocks', 'documents_joints',
            Prefetch(
                'lignes_travaux',
                queryset=LigneTravailRapportJournalier.objects.select_related('ligne_bordereau'),
            ),
        ),
        id=rapport_id, projet=projet
    )


def _depenses_groupees_rapport(rapport, projet):
    """Dépenses du rapport par catégorie : ([(code, nom, depenses, total)], total général)."""
    depenses = list(rapport.depenses.all())
    categorie_ids = {d.categorie_charge_id for d in depenses if d.categorie_charge_id}
    categories = CategorieCharge.objects.filter(
        Q(actif=True) | Q(pk__in=categorie_ids), dossier_id=projet.dossier_id,
    )

    depenses_groupees = []
    for category in categories:
        depenses_categorie = [
            d for d in depenses
            if (d.categorie_charge_id and d.categorie_charge_id == category.id)
            or (not d.categorie_charge_id and d.categorie == category.code)
        ]
        if depenses_categorie:
            total = sum((d.montant for d in depenses_categorie), Decimal('0.00'))
            depenses_groupees.append((category.code, category.nom, depenses_categorie, total))
    return depenses_groupees, sum((d.montant for d in depenses), Decimal('0.00'))


@login_required
@can_edit_projet
def api_lignes_bpu_rapport(request, projet_id):
    """Lignes « BPU » du rapport (?date=AAAA-MM-JJ&rapport=<id à exclure du cumul>)."""
    projet = _projet_travaux_or_403(projet_id)
    try:
        date_ref = date.fromisoformat(request.GET.get('date', ''))
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Date invalide.'}, status=400)
    exclure = request.GET.get('rapport')
    exclure = int(exclure) if exclure and exclure.isdigit() else None
    return JsonResponse({
        'success': True,
        'date': date_ref.isoformat(),
        'lignes': _lignes_bpu(projet, date_ref, exclure_rapport_id=exclure),
    })


@login_required
@can_edit_projet
def api_meteo_rapport(request, projet_id):
    """Météo en ligne d'une journée pour pré-remplir le rapport (?date=AAAA-MM-JJ)."""
    projet = _projet_travaux_or_403(projet_id)
    try:
        jour = date.fromisoformat(request.GET.get('date', ''))
    except ValueError:
        return JsonResponse({'success': False, 'message': 'Date invalide.'}, status=400)
    try:
        meteo = meteo_du_jour(projet.localisation, jour)
    except MeteoIndisponible as erreur:
        return JsonResponse({'success': False, 'message': str(erreur)})
    return JsonResponse({'success': True, **meteo.as_dict()})


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}


@login_required
@can_view_projet
def apercu_rapport_journalier(request, projet_id, rapport_id):
    """Aperçu avant impression d'un rapport journalier (A4 portrait)."""
    projet = _projet_travaux_or_403(projet_id)
    rapport = _rapport_journalier_complet(projet, rapport_id)
    depenses_groupees, total_depenses = _depenses_groupees_rapport(rapport, projet)

    documents = list(rapport.documents_joints.all())
    photos = [d for d in documents if os.path.splitext(d.nom)[1].lower() in IMAGE_EXTENSIONS]
    autres_documents = [d for d in documents if d not in photos]

    # Ordre chronologique (date, id) : plusieurs rapports peuvent partager une date.
    rapports_projet = RapportJournalier.objects.filter(projet=projet).only('id', 'date')
    avant = Q(date__lt=rapport.date) | Q(date=rapport.date, id__lt=rapport.id)
    apres = Q(date__gt=rapport.date) | Q(date=rapport.date, id__gt=rapport.id)
    precedent = rapports_projet.filter(avant).order_by('-date', '-id').first()
    suivant = rapports_projet.filter(apres).order_by('date', 'id').first()

    return render(request, 'projets/rapports/apercu_rapport_journalier.html', {
        'projet': projet,
        'rapport': rapport,
        'numero': rapports_projet.filter(avant).count() + 1,
        'travaux': rapport.lignes_travaux.all(),
        'depenses_groupees': depenses_groupees,
        'total_depenses': total_depenses,
        'stocks': rapport.stocks.all(),
        'photos': photos,
        'autres_documents': autres_documents,
        'precedent': precedent,
        'suivant': suivant,
        'date_edition': timezone.localtime(),
    })


@login_required
@can_view_projet
def detail_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = _rapport_journalier_complet(projet, rapport_id)
    depenses_groupees, total_depenses = _depenses_groupees_rapport(rapport, projet)

    ctx = {
        'projet': projet,
        'rapport': rapport,
        'depenses_groupees': depenses_groupees,
        'total_depenses': total_depenses,
        'breadcrumb_items': project_crumbs(
            projet,
            crumb("Rapports journaliers", "projets:rapports_journaliers", args=[projet.id]),
            crumb(f"Rapport {rapport.date.strftime('%d/%m/%Y')}"),
        ),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'projets/rapports/_detail_rapport_journalier_content.html', ctx)
    return render(request, 'projets/rapports/detail_rapport_journalier.html', ctx)

def _referentiel_depenses(projet):
    """Ressources actives affectées au projet, groupées par catégorie (1 requête).

    Couvre toutes les catégories du dossier, y compris les catégories
    personnalisées et le transport.
    """
    referentiel = {}
    ressources = (
        projet.ressources_affectees
        .filter(actif=True, categorie_charge__dossier_id=projet.dossier_id)
        .order_by('designation')
        .values('categorie_charge_id', 'designation', 'unite', 'tarif')
    )
    for ressource in ressources:
        referentiel.setdefault(ressource['categorie_charge_id'], []).append({
            'designation': ressource['designation'],
            'unite': ressource['unite'] or '',
            'prix': str(ressource['tarif'] or Decimal('0.00')),
        })
    return referentiel


def _grouper_depenses_par_categorie(depenses_formset, projet):
    """Regroupe les lignes du formset par catégorie, avec total et référentiel.

    Réutilise les catégories déjà chargées par le formset : aucune requête par ligne.
    """
    def categorie_id(form):
        # Ligne enregistrée : instance ; ligne pré-remplie (reproduction) : initial.
        return form.instance.categorie_charge_id or form.initial.get('categorie_charge')

    def montant(form):
        if form.instance.pk or form.is_bound:
            return form.instance.montant or Decimal('0.00')
        return (form.initial.get('quantite') or Decimal('0')) * (form.initial.get('prix_unitaire') or Decimal('0'))

    existing_ids = {categorie_id(form) for form in depenses_formset.forms if categorie_id(form)}
    categories = [
        category for category in depenses_formset.categories_charge
        if category.actif or category.pk in existing_ids
    ]
    par_id = {category.pk: category for category in categories}
    groupes = {category.code: [] for category in categories}
    for depense_form in depenses_formset.forms:
        category = par_id.get(categorie_id(depense_form))
        code = category.code if category else (
            depense_form.instance.categorie or depense_form.initial.get('categorie')
        )
        if code in groupes:
            groupes[code].append(depense_form)
    referentiel = _referentiel_depenses(projet=projet)
    return [
        (
            category.code,
            category.nom,
            groupes[category.code],
            sum((montant(f) for f in groupes[category.code]), Decimal('0.00')),
            referentiel.get(category.pk, []),
            category.pk,
        )
        for category in categories
    ]

@login_required
@can_edit_projet
def modifier_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)
    is_xhr = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    def _build_ctx(form, depenses, stocks, travaux):
        return {
            'projet': projet,
            'rapport': rapport,
            'documents': list(rapport.documents_joints.all()),
            'form': form,
            'depenses': depenses,
            'stocks': stocks,
            'travaux': travaux,
            'depenses_groupees': _grouper_depenses_par_categorie(depenses, projet=projet),
            'activites': _activites_projet(projet),
            'meteo_en_ligne': meteo_en_ligne_active() and bool(projet.localisation),
            'a_lignes_bpu': _lignes_bordereau_proposees(projet).exists(),
            'breadcrumb_items': project_crumbs(
                projet,
                crumb("Rapports journaliers", "projets:rapports_journaliers", args=[projet.id]),
                crumb(f"Modifier — {rapport.date.strftime('%d/%m/%Y')}"),
            ),
        }

    if request.method == 'POST':
        form = RapportJournalierForm(request.POST, request.FILES, instance=rapport, projet=projet)
        depenses = DepenseRapportJournalierFormSet(
            request.POST, instance=rapport, form_kwargs={'projet': projet},
        )
        stocks = StockRapportJournalierFormSet(request.POST, instance=rapport)
        travaux = LigneTravailRapportJournalierFormSet(
            request.POST, instance=rapport,
        )

        if (
            form.is_valid()
            and depenses.is_valid()
            and stocks.is_valid()
            and travaux.is_valid()
        ):
            rapport = form.save(commit=False)
            with transaction.atomic():
                rapport.save()
                depenses.save()
                stocks.save()
                travaux.save()
                _enregistrer_documents_rapport(request, rapport)
                rapport.documents_joints.filter(
                    pk__in=request.POST.getlist('supprimer_document'),
                ).delete()

            msg = 'Rapport journalier modifié.'
            if is_xhr:
                return JsonResponse({
                    'success': True,
                    'message': msg,
                    'url': reverse('projets:rapports_journaliers', args=[projet.id]),
                })
            messages.success(request, msg)
            return redirect('projets:rapports_journaliers', projet_id=projet.id)

        msg = "Le rapport n'a pas pu être modifié. Vérifiez les informations saisies."
        if is_xhr:
            return JsonResponse({
                'success': False,
                'message': msg,
                'errors': {
                    'form': form.errors.get_json_data(),
                    'depenses': depenses.errors,
                    'stocks': stocks.errors,
                    'travaux': travaux.errors,
                },
            }, status=400)
        _signaler_erreurs_rapport(request, form, depenses, stocks, travaux)
        return render(request, 'projets/rapports/modifier_rapport_journalier.html',
                      _build_ctx(form, depenses, stocks, travaux), status=400)

    # GET
    form = RapportJournalierForm(instance=rapport)
    depenses = DepenseRapportJournalierFormSet(instance=rapport, form_kwargs={'projet': projet})
    stocks = StockRapportJournalierFormSet(instance=rapport)
    travaux = LigneTravailRapportJournalierFormSet(instance=rapport)

    ctx = _build_ctx(form, depenses, stocks, travaux)

    if request.headers.get('HX-Request'):
        return render(request, 'projets/rapports/_modifier_rapport_journalier_content.html', ctx)
    return render(request, 'projets/rapports/modifier_rapport_journalier.html', ctx)

@login_required
@can_edit_projet
def supprimer_rapport_journalier(request, projet_id, rapport_id):
    projet = _projet_travaux_or_403(projet_id)
    rapport = get_object_or_404(RapportJournalier, id=rapport_id, projet=projet)
    is_xhr = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    if request.method != 'POST':
        return redirect('projets:rapports_journaliers', projet_id=projet_id)

    date_str = rapport.date.strftime('%d/%m/%Y')
    rapport.delete()
    msg = f'Rapport du {date_str} supprimé.'

    if is_xhr:
        return JsonResponse({'success': True, 'message': msg})

    messages.success(request, msg)
    return redirect('projets:rapports_journaliers', projet_id=projet_id)


def _crumbs_situations(projet, *items):
    return project_crumbs(
        projet,
        crumb("Situations mensuelles", "projets:situations_mensuelles", args=[projet.id]),
        *items,
    )

def _situation_brouillon_or_403(situation):
    """Lève une 403 si la situation n'est pas en brouillon."""
    if not situation.est_brouillon:
        raise PermissionDenied(
            "Cette situation est validée et ne peut plus être modifiée."
        )

@login_required
@consultation_projet_required
def situations_mensuelles(request, projet_id):
    projet = get_object_or_404(Projet, id=projet_id)
    situations = list(
        projet.situations_mensuelles
        .prefetch_related('stocks', 'depenses', 'recettes')
    )

    ctx = {
        'projet': projet,
        'situations': situations,
        'breadcrumb_items': project_crumbs(projet, crumb("Situations mensuelles")),
    }

    if request.headers.get('HX-Request'):
        return render(request, 'projets/situations/_situations_content.html', ctx)

    return render(request, 'projets/situations/situations_mensuelles.html', ctx)


@require_POST
@chef_projet_required
def supprimer_situation_mensuelle(request, projet_id, situation_id):
    situation = get_object_or_404(
        SituationMensuelle, id=situation_id, projet_id=projet_id
    )
    periode = f"{situation.mois:02d}/{situation.annee}"
    is_xhr = request.headers.get('x-requested-with') == 'XMLHttpRequest'

    try:
        situation.delete()
    except Exception as e:
        msg = f"Erreur lors de la suppression : {e}"
        if is_xhr:
            return JsonResponse({'success': False, 'message': msg}, status=500)
        messages.error(request, msg)
        return redirect('projets:situations_mensuelles', projet_id=projet_id)

    msg = f"Situation {periode} supprimée avec succès."

    if is_xhr:
        return JsonResponse({'success': True, 'message': msg})

    messages.success(request, msg)
    return redirect('projets:situations_mensuelles', projet_id=projet_id)

@login_required
@consultation_projet_required
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
    depenses = list(situation.depenses.select_related('categorie_charge'))
    categorie_ids = {depense.categorie_charge_id for depense in depenses if depense.categorie_charge_id}
    categories = CategorieCharge.objects.filter(
        Q(actif=True) | Q(pk__in=categorie_ids), dossier_id=projet.dossier_id,
    )
    depenses_par_categorie = []
    for category in categories:
        category_depenses = [
            depense for depense in depenses
            if (depense.categorie_charge_id and depense.categorie_charge_id == category.id)
            or (not depense.categorie_charge_id and depense.categorie == category.code)
        ]
        if category_depenses:
            total = sum((depense.montant or Decimal('0.00') for depense in category_depenses), Decimal('0.00'))
            depenses_par_categorie.append((category.code, category.nom, total, category_depenses))
    # Résultat = CA − Dépenses + ΔStock (propriétés du modèle)
    return render(request, 'projets/situations/apercu_situation_mensuelle.html', {
        'projet': projet,
        'situation': situation,
        'recettes': recettes,
        'depenses_par_categorie': [(value, label, depenses, total) for value, label, total, depenses in depenses_par_categorie],
        'stocks': situation.stocks.all(),
        'documents': situation.documents.all(),
    })


def _group_situation_expenses(formset, projet):
    categories = list(CategorieCharge.objects.filter(actif=True, dossier_id=projet.dossier_id))
    existing_ids = {
        form.instance.categorie_charge_id
        for form in formset.forms
        if form.instance.categorie_charge_id
    }
    if existing_ids:
        categories = list(CategorieCharge.objects.filter(
            Q(actif=True) | Q(pk__in=existing_ids), dossier_id=projet.dossier_id,
        ))
    groups = {category.code: [] for category in categories}
    for form in formset.forms:
        code = form.instance.categorie_charge.code if form.instance.categorie_charge_id else form.instance.categorie
        if code in groups:
            groups[code].append(form)
    return [
        (
            category.code,
            category.nom,
            groups[category.code],
            sum((form.instance.montant or Decimal('0.00') for form in groups[category.code]), Decimal('0.00')),
        )
        for category in categories
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
    
    fichiers = _fichier_rapport_recu(request)
    if not fichiers:
        messages.error(request, "Aucun fichier sélectionné")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    valid_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif']
    if any(fichier.size > 10 * 1024 * 1024 for fichier in fichiers):
        messages.error(request, "Chaque fichier ne doit pas dépasser 10MB")
        return redirect('projets:suivi_execution', projet_id=projet_id)
    if any(
        os.path.splitext(fichier.name)[1].lower() not in valid_extensions
        for fichier in fichiers
    ):
        messages.error(
            request,
            f"Type de fichier non supporté. Utilisez: {', '.join(valid_extensions)}",
        )
        return redirect('projets:suivi_execution', projet_id=projet_id)
    
    try:
        with transaction.atomic():
            for fichier in fichiers:
                DocumentRapportJournalier.objects.create(
                    rapport=rapport,
                    fichier=fichier,
                    original_filename=fichier.name,
                )
        messages.success(
            request,
            f"{len(fichiers)} document(s) ajouté(s) au rapport du "
            f"{rapport.date.strftime('%d/%m/%Y')}",
        )
    except Exception as e:
        messages.error(request, f"Erreur lors de l'upload: {str(e)}")
    
    return redirect('projets:suivi_execution', projet_id=projet_id)


@login_required
@chef_projet_required
def ajouter_situation_mensuelle(request, projet_id):
    projet = _projet_travaux_or_403(projet_id)
    depenses = DepenseSituationMensuelleFormSet(request.POST or None, form_kwargs={'projet': projet})
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
            depenses = DepenseSituationMensuelleFormSet(
                request.POST, instance=situation, form_kwargs={'projet': projet},
            )
            stocks = StockSituationMensuelleFormSet(request.POST, instance=situation)
            recettes = _recettes_formset(request.POST, situation=situation)
            documents = DocumentSituationMensuelleFormSet(request.POST, request.FILES, instance=situation)
            if depenses.is_valid() and stocks.is_valid() and recettes.is_valid() and documents.is_valid():
                try:
                    with transaction.atomic():
                        Projet.objects.select_for_update().get(pk=projet.pk)
                        situation.save()
                        depenses.instance = situation
                        stocks.instance = situation
                        depenses.save()
                        stocks.save()
                        recettes.save()
                        _creer_rubriques_recettes_manquantes(situation)
                        _synchroniser_chiffre_affaires(situation)
                        documents.save()
                except ValidationError as error:
                    form.add_error(None, ' '.join(error.messages))
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
        depenses = DepenseSituationMensuelleFormSet(form_kwargs={'projet': projet})
        stocks = StockSituationMensuelleFormSet()
        recettes = _recettes_formset()
        documents = DocumentSituationMensuelleFormSet()

    return render(request, 'projets/situations/ajouter_situation_mensuelle.html', {
        'projet': projet,
        'form': form,
        'depenses': depenses,
        'stocks': stocks,
        'recettes': recettes,
        'documents': documents,
        'depenses_groupees': _group_situation_expenses(depenses, projet),
        'breadcrumb_items': _crumbs_situations(projet, crumb("Nouvelle situation")),
    })


@login_required
@chef_projet_required
def modifier_situation_mensuelle(request, projet_id, situation_id):
    projet = _projet_travaux_or_403(projet_id)
    situation = get_object_or_404(SituationMensuelle, id=situation_id, projet=projet)
    depenses_queryset = situation.depenses.select_related('categorie_charge')
    if request.method == 'POST':
        form = SituationMensuelleForm(request.POST, request.FILES, instance=situation, projet=projet)
        depenses = DepenseSituationMensuelleFormSet(
            request.POST,
            instance=situation,
            queryset=depenses_queryset,
            form_kwargs={'projet': projet},
        )
        stocks = StockSituationMensuelleFormSet(request.POST, instance=situation)
        recettes = _recettes_formset(request.POST, situation=situation)
        documents = DocumentSituationMensuelleFormSet(request.POST, request.FILES, instance=situation)
        form_valid = form.is_valid()
        depenses_valid = depenses.is_valid()
        stocks_valid = stocks.is_valid()
        recettes_valid = recettes.is_valid()
        documents_valid = documents.is_valid()
        if form_valid and depenses_valid and stocks_valid and recettes_valid and documents_valid:
            situation = form.save(commit=False)
            try:
                with transaction.atomic():
                    Projet.objects.select_for_update().get(pk=projet.pk)
                    actuelle = SituationMensuelle.objects.select_for_update().get(pk=situation.pk)
                    if actuelle.est_validee and (
                        actuelle.ca_id or ChiffreAffaire.objects.filter(
                            projet=projet, periode=date(actuelle.annee, actuelle.mois, 1),
                        ).exists()
                    ):
                        raise ValidationError('Dévalidez la situation avant de modifier ses données liées au CA.')
                    situation.ca_id = actuelle.ca_id
                    situation.save()
                    depenses.save()
                    stocks.save()
                    recettes.save()
                    _synchroniser_chiffre_affaires(situation)
                    documents.save()
            except ValidationError as error:
                form.add_error(None, ' '.join(error.messages))
            except IntegrityError:
                form.add_error('mois', 'Une situation existe déjà pour cette période.')
            else:
                messages.success(request, 'Situation mensuelle modifiée.')
                return redirect(
                    'projets:modifier_situation_mensuelle',
                    projet_id=projet.id,
                    situation_id=situation.id,
                )
        validation_errors = []
        for label, validation_form in (
            ('Situation', form),
            ('Dépenses', depenses),
            ('Stocks', stocks),
            ('Recettes', recettes),
            ('Documents', documents),
        ):
            if validation_form.errors:
                validation_errors.append(
                    f'{label}: {_format_validation_errors(validation_form)}'
                )
        logger.warning(
            'Modification situation mensuelle invalide (projet=%s, situation=%s): %s',
            projet.id, situation.id, ' | '.join(validation_errors),
        )
        messages.error(request, 'La situation n\'a pas été enregistrée. Corrigez les erreurs indiquées.')
    else:
        form = SituationMensuelleForm(instance=situation)
        depenses = DepenseSituationMensuelleFormSet(
            instance=situation,
            queryset=depenses_queryset,
            form_kwargs={'projet': projet},
        )
        stocks = StockSituationMensuelleFormSet(instance=situation)
        recettes = _recettes_formset(situation=situation)
        documents = DocumentSituationMensuelleFormSet(instance=situation)
    return render(request, 'projets/situations/modifier_situation_mensuelle.html', {
        'projet': projet, 'situation': situation, 'form': form,
        'depenses': depenses, 'stocks': stocks,
        'recettes': recettes,
        'depenses_groupees': _group_situation_expenses(depenses, projet),
        'documents': documents,
        'validation_errors': validation_errors if request.method == 'POST' else [],
        'breadcrumb_items': _crumbs_situations(
            projet, crumb(f"Situation {situation.mois:02d}/{situation.annee}")
        ),
    })


@login_required
@can_validate_situation_mensuelle
@require_POST
def valider_situation_mensuelle(request, projet_id, situation_id):
    """Passe une situation de Brouillon à Validée."""
    with transaction.atomic():
        Projet.objects.select_for_update().get(pk=projet_id)
        situation = get_object_or_404(
            SituationMensuelle.objects.select_for_update(), id=situation_id, projet_id=projet_id,
        )
        ca = ChiffreAffaire.objects.filter(
            projet_id=projet_id, periode=date(situation.annee, situation.mois, 1),
        ).first()
        if ca and ca.statut != ChiffreAffaire.Statut.VALIDE:
            return JsonResponse({'success': False, 'message': 'Validez le CA du mois avant de valider la situation.'}, status=400)
        if situation.est_validee:
            return JsonResponse({'success': False, 'message': 'Cette situation est déjà validée.'}, status=400)
        synchroniser_situation_ca(situation)
        situation.statut = SituationMensuelle.Statut.VALIDEE
        situation.date_validation = timezone.now()
        situation.validee_par = request.user
        situation.save(update_fields=['statut', 'date_validation', 'validee_par'])
    return JsonResponse({
        'success': True,
        'message': f'Situation {situation.mois:02d}/{situation.annee} validée.',
    })


@login_required
@can_devalidate_situation_mensuelle
@require_POST
def devalider_situation_mensuelle(request, projet_id, situation_id):
    """Remet une situation Validée en Brouillon."""
    situation = get_object_or_404(
        SituationMensuelle, id=situation_id, projet_id=projet_id,
    )

    if situation.est_brouillon:
        return JsonResponse(
            {'success': False, 'message': 'Cette situation est déjà en brouillon.'},
            status=400,
        )

    situation.statut = SituationMensuelle.Statut.BROUILLON
    situation.date_devalidation = timezone.now()
    situation.devalidee_par = request.user
    situation.save(update_fields=['statut', 'date_devalidation', 'devalidee_par'])

    return JsonResponse({
        'success': True,
        'message': f'Situation {situation.mois:02d}/{situation.annee} remise en brouillon.',
    })

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
