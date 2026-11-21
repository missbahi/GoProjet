from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms import inlineformset_factory
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from projets.decorators import (
    chef_projet_required,
    consultation_projet_required,
    est_observateur,
)
from projets.forms import FormuleRevisionForm, MoisBaseRevisionForm, TermeFormuleForm
from projets.models import FormuleRevision, LigneBordereau, Projet, TermeFormule
from projets.models.revision import (
    IndexReference,
    IndexRevisionProjet,
    IndexValeur,
    StatutIndex,
)
from projets.services.revision_presets import (
    FORMULES_REVISION_PAR_CODE,
    FORMULES_REVISION_PREDEFINIES,
    initial_termes_formule,
)
from projets.services.revision_readiness import (
    compter_lignes_simples_couvertes,
    controle_indexes_revision,
    index_ids_tableur,
    lignes_principales_revision_lot,
    indicateur_revision_tableau_bord,
)
from projets.services.sommaire import lignes_principales_lot
from projets.utils.navigation import crumb, project_crumbs


TermeFormuleFormSet = inlineformset_factory(
    FormuleRevision,
    TermeFormule,
    form=TermeFormuleForm,
    extra=1,
    can_delete=True,
)


def _contexte_revision(
    projet, formule_form=None, termes_formset=None, preset_code=None,
    mois_base_form=None,
):
    lots_data = []
    for lot in projet.lots.prefetch_related(
        'lignes__formule_revision',
    ).order_by('id'):
        titres, principales = lignes_principales_revision_lot(lot)
        ids = [ligne['id'] for ligne in principales]
        lignes = {
            ligne.pk: ligne
            for ligne in lot.lignes.filter(pk__in=ids)
        }
        principales_data = []
        for ligne in principales:
            instance = lignes.get(ligne['id'])
            if instance:
                principales_data.append({
                    **ligne,
                    'instance': instance,
                })
        lots_data.append({
            'lot': lot,
            'titres': ' › '.join(titres),
            'lignes_principales': principales_data,
        })

    predefinie = FORMULES_REVISION_PAR_CODE.get(preset_code)
    if formule_form is None and predefinie:
        formule_form = FormuleRevisionForm(initial={
            "code": predefinie["code"],
            "libelle": predefinie["libelle"],
            "k": predefinie["k"],
            "est_index_global": predefinie.get("est_index_global", False),
        })
    if termes_formset is None and predefinie:
        symboles = {
            symbole
            for terme in predefinie["termes"]
            for symbole in terme[2:]
            if symbole
        }
        indexes = {
            index.symbole: index
            for index in IndexReference.objects.filter(symbole__in=symboles)
        }
        if set(indexes) != symboles:
            manquants = sorted(symboles - set(indexes))
            raise ValueError(
                "Index prédéfinis manquants : " + ", ".join(manquants)
            )
        termes_initiaux = initial_termes_formule(predefinie, indexes)
        predefini_formset = inlineformset_factory(
            FormuleRevision,
            TermeFormule,
            form=TermeFormuleForm,
            extra=len(termes_initiaux),
            can_delete=True,
        )
        termes_formset = predefini_formset(prefix="termes")
        for formulaire, initial in zip(termes_formset.forms, termes_initiaux):
            formulaire.initial.update(initial)

    indicateur = indicateur_revision_tableau_bord(projet)
    controle_indexes = controle_indexes_revision(projet)
    couverture = compter_lignes_simples_couvertes(projet)
    formules = list(
        projet.formules_revision.prefetch_related(
            'termes__index_simple',
            'termes__index_composite_a',
            'termes__index_composite_b',
        ).order_by('code')
    )
    for formule in formules:
        formule.nombre_lignes_affectees = couverture[formule.pk]
    ids_tableur = index_ids_tableur(projet, controle_indexes)
    indexes_revision = list(
        IndexReference.objects.filter(
            pk__in=ids_tableur,
        ).order_by("symbole")
    )
    valeurs_map = {
        (valeur.index_id, valeur.mois): valeur
        for valeur in IndexValeur.objects.filter(
            index_id__in=ids_tableur,
            mois__in=controle_indexes["mois_tableur"],
        )
    }
    grille_indexes = [
        {
            "index": index,
            "cellules": [
                {
                    "mois": mois,
                    "valeur": valeurs_map.get((index.pk, mois)),
                }
                for mois in controle_indexes["mois_tableur"]
            ],
        }
        for index in indexes_revision
    ]
    statuts_mois = []
    for mois in controle_indexes["mois_tableur"]:
        statuts = [
            valeur.statut
            for valeur in valeurs_map.values()
            if valeur.mois == mois
        ]
        statuts_mois.append({
            "mois": mois,
            "statut": (
                StatutIndex.IND_DEF
                if mois == projet.mois_base_revision
                else (
                    StatutIndex.IND_PRO
                    if not statuts or StatutIndex.IND_PRO in statuts
                    else StatutIndex.IND_DEF
                )
            ),
        })
    return {
        'projet': projet,
        'lots_data': lots_data,
        'formules': formules,
        'formule_form': formule_form or FormuleRevisionForm(),
        'termes_formset': termes_formset or TermeFormuleFormSet(),
        'formules_predefinies': FORMULES_REVISION_PREDEFINIES,
        'preset_selectionne': preset_code,
        'mois_base_form': mois_base_form or MoisBaseRevisionForm(
            instance=projet,
            os_commencement=projet.os_commencement,
        ),
        'os_commencement': projet.os_commencement,
        'configuration_revision_prete': bool(
            indicateur and indicateur.statut == 'PRET'
        ),
        'controle_indexes': controle_indexes,
        'indexes_revision': indexes_revision,
        'grille_indexes': grille_indexes,
        'statuts_mois': statuts_mois,
        'breadcrumb_items': project_crumbs(projet, crumb("Révision des prix")),
    }


@consultation_projet_required
def gestion_revision_prix(request, projet_id):
    projet = get_object_or_404(Projet, pk=projet_id)
    if not projet.revision_prix_disponible:
        messages.warning(
            request,
            "La révision des prix nécessite un projet révisable et un OS de "
            "commencement notifié avec une date d'effet.",
        )
        return redirect('projets:dashboard', projet_id=projet.pk)
    contexte = _contexte_revision(
        projet, preset_code=request.GET.get("preset"),
    )
    contexte["peut_modifier_revision"] = not est_observateur(request.user)
    if request.headers.get('HX-Request'):
        return render(
            request,
            'projets/revision/_revision_prix_content.html',
            contexte,
        )
    return render(
        request,
        'projets/revision/gestion_revision_prix.html',
        contexte,
    )


@chef_projet_required
def modifier_formule_revision(request, projet_id, formule_id):
    projet = get_object_or_404(Projet, pk=projet_id)
    if not projet.revision_prix_disponible:
        messages.warning(request, "L'OS de commencement est requis.")
        return redirect('projets:dashboard', projet_id=projet.pk)
    formule = get_object_or_404(
        FormuleRevision.objects.prefetch_related("termes"),
        pk=formule_id,
        projet=projet,
    )
    if request.method == "POST":
        formule_form = FormuleRevisionForm(request.POST, instance=formule)
        termes_formset = TermeFormuleFormSet(
            request.POST, instance=formule, prefix="termes",
        )
        try:
            with transaction.atomic():
                if not formule_form.is_valid() or not termes_formset.is_valid():
                    raise ValidationError("Le formulaire contient des erreurs.")
                formule = formule_form.save(commit=False)
                formule.save()
                termes_formset.instance = formule
                termes_formset.save()
                formule.valider()
        except ValidationError as error:
            formule_form.add_error(None, error)
        else:
            messages.success(request, f"La formule « {formule.code} » a été modifiée.")
            return redirect('projets:gestion_revision_prix', projet_id=projet.pk)
    else:
        formule_form = FormuleRevisionForm(instance=formule)
        termes_formset = TermeFormuleFormSet(instance=formule, prefix="termes")

    contexte = _contexte_revision(projet, formule_form, termes_formset)
    contexte["peut_modifier_revision"] = True
    contexte["formule_a_modifier"] = formule
    return render(
        request,
        'projets/revision/gestion_revision_prix.html',
        contexte,
    )


@require_POST
@chef_projet_required
def supprimer_formule_revision(request, projet_id, formule_id):
    projet = get_object_or_404(Projet, pk=projet_id)
    if not projet.revision_prix_disponible:
        messages.warning(request, "L'OS de commencement est requis.")
        return redirect('projets:dashboard', projet_id=projet.pk)

    with transaction.atomic():
        formule = get_object_or_404(
            FormuleRevision.objects.select_for_update(),
            pk=formule_id,
            projet=projet,
        )
        nombre_lignes = compter_lignes_simples_couvertes(projet)[formule.pk]
        nombre_affectations_directes = formule.lignes_bordereau.count()
        if nombre_lignes and request.POST.get('confirmer_suppression') != 'on':
            messages.warning(
                request,
                f"La formule « {formule.code} » est affectée à {nombre_lignes} "
                "ligne(s). Confirmez le retrait des affectations avant sa suppression.",
            )
            return redirect('projets:gestion_revision_prix', projet_id=projet.pk)

        code = formule.code
        if nombre_affectations_directes:
            formule.lignes_bordereau.update(formule_revision=None)
        formule.delete()

    if nombre_lignes:
        messages.success(
            request,
            f"La formule « {code} » a été supprimée et retirée de "
            f"{nombre_lignes} ligne(s).",
        )
    else:
        messages.success(request, f"La formule « {code} » a été supprimée.")
    return redirect('projets:gestion_revision_prix', projet_id=projet.pk)


def _promouvoir_affectations_vers_parents(projet):
    """Remonte une même formule sur le parent lorsqu'il couvre tout le niveau."""
    for lot in projet.lots.all():
        _, principales = lignes_principales_lot(lot)
        lignes = LigneBordereau.objects.filter(
            pk__in=[ligne["id"] for ligne in principales],
        ).select_related("parent").in_bulk()
        groupes = {}
        for principale in principales:
            ligne = lignes[principale["id"]]
            if ligne.parent_id:
                groupes.setdefault(ligne.parent_id, []).append(ligne)
        for enfants in groupes.values():
            formules = {enfant.formule_revision_id for enfant in enfants}
            if len(enfants) < 2 or len(formules) != 1 or None in formules:
                continue
            parent = enfants[0].parent
            if parent is None:
                continue
            parent.formule_revision_id = next(iter(formules))
            parent.save(update_fields=["formule_revision"])
            LigneBordereau.objects.filter(
                pk__in=[enfant.pk for enfant in enfants],
            ).update(formule_revision=None)


@require_POST
@chef_projet_required
def creer_formule_revision(request, projet_id):
    projet = get_object_or_404(Projet, pk=projet_id)
    if not projet.revision_prix_disponible:
        messages.warning(request, "L'OS de commencement est requis.")
        return redirect('projets:dashboard', projet_id=projet.pk)
    if not projet.mois_base_revision:
        messages.warning(request, "Renseignez d'abord le mois de base du projet.")
        return redirect('projets:gestion_revision_prix', projet_id=projet.pk)
    formule_form = FormuleRevisionForm(request.POST)
    termes_formset = TermeFormuleFormSet(request.POST, prefix="termes")
    try:
        with transaction.atomic():
            if not formule_form.is_valid() or not termes_formset.is_valid():
                raise ValidationError("Le formulaire contient des erreurs.")
            formule = formule_form.save(commit=False)
            formule.projet = projet
            formule.save()
            termes_formset.instance = formule
            termes_formset.save()
            formule.valider()
    except ValidationError as error:
        if formule_form.is_valid() and termes_formset.is_valid():
            formule_form.add_error(None, error)
        contexte = _contexte_revision(projet, formule_form, termes_formset)
        contexte["peut_modifier_revision"] = True
        return render(
            request,
            'projets/revision/gestion_revision_prix.html',
            contexte,
            status=400,
        )

    messages.success(request, f"La formule « {formule.code} » a été créée.")
    return redirect('projets:gestion_revision_prix', projet_id=projet.pk)


@require_POST
@chef_projet_required
def affecter_formules_revision(request, projet_id):
    projet = get_object_or_404(Projet, pk=projet_id)
    if not projet.revision_prix_disponible:
        messages.warning(request, "L'OS de commencement est requis.")
        return redirect('projets:dashboard', projet_id=projet.pk)
    lignes_ids = []
    affectations = {}
    for cle, valeur in request.POST.items():
        if not cle.startswith('formule_ligne_'):
            continue
        try:
            ligne_id = int(cle.removeprefix('formule_ligne_'))
            formule_id = int(valeur) if valeur else None
        except ValueError:
            continue
        lignes_ids.append(ligne_id)
        affectations[ligne_id] = formule_id

    formules = {
        formule.pk: formule
        for formule in projet.formules_revision.filter(pk__in=affectations.values())
    }
    lignes = {
        ligne.pk: ligne
        for ligne in LigneBordereau.objects.filter(
            pk__in=lignes_ids,
            lot__projet=projet,
        )
    }

    with transaction.atomic():
        for ligne_id, formule_id in affectations.items():
            ligne = lignes.get(ligne_id)
            formule = formules.get(formule_id) if formule_id is not None else None
            if ligne is None or (formule_id is not None and formule is None):
                messages.error(request, "Une affectation ne correspond pas au projet.")
                return redirect('projets:gestion_revision_prix', projet_id=projet.pk)
            ligne.formule_revision = formule
            ligne.save(update_fields=['formule_revision'])
        _promouvoir_affectations_vers_parents(projet)

    messages.success(request, "Les formules ont été affectées aux lignes principales.")
    return redirect('projets:gestion_revision_prix', projet_id=projet.pk)


@require_POST
@chef_projet_required
def enregistrer_mois_base_revision(request, projet_id):
    projet = get_object_or_404(Projet, pk=projet_id)
    if not projet.revision_prix_disponible:
        messages.warning(request, "L'OS de commencement est requis.")
        return redirect('projets:dashboard', projet_id=projet.pk)
    formulaire = MoisBaseRevisionForm(
        request.POST,
        instance=projet,
        os_commencement=projet.os_commencement,
    )
    if formulaire.is_valid():
        formulaire.save()
        messages.success(
            request,
            "Le mois de base unique du projet a été enregistré.",
        )
        return redirect('projets:gestion_revision_prix', projet_id=projet.pk)
    contexte = _contexte_revision(projet, mois_base_form=formulaire)
    contexte["peut_modifier_revision"] = True
    return render(
        request,
        'projets/revision/gestion_revision_prix.html',
        contexte,
        status=400,
    )


@require_POST
@chef_projet_required
def enregistrer_valeurs_indexes(request, projet_id):
    projet = get_object_or_404(Projet, pk=projet_id)
    if not projet.revision_prix_disponible:
        messages.warning(request, "L'OS de commencement est requis.")
        return redirect('projets:dashboard', projet_id=projet.pk)

    controle = controle_indexes_revision(projet)
    index_ids = index_ids_tableur(projet, controle)
    indexes = IndexReference.objects.filter(pk__in=index_ids).in_bulk()
    nouveaux_mois = {}
    nouveaux_indexes = {}
    erreurs = []

    for cle, brut in request.POST.items():
        if not cle.startswith("nouveau_mois_"):
            continue
        token = cle.removeprefix("nouveau_mois_")
        brut = brut.strip()
        if not brut:
            continue
        try:
            mois = date.fromisoformat(f"{brut}-01")
        except ValueError:
            erreurs.append("Un mois supplémentaire est invalide.")
            continue
        if mois in controle["mois_tableur"]:
            erreurs.append(f"Le mois {mois:%m/%Y} existe déjà dans la grille.")
            continue
        nouveaux_mois[token] = mois

    for cle, brut in request.POST.items():
        if not cle.startswith("nouvel_index_") or not cle.endswith("_symbole"):
            continue
        token = cle.removeprefix("nouvel_index_").removesuffix("_symbole")
        symbole = brut.strip().upper()
        if not symbole:
            continue
        if len(symbole) > 20:
            erreurs.append(f"Le symbole « {symbole} » dépasse 20 caractères.")
            continue
        index_existant = IndexReference.objects.filter(
            symbole__iexact=symbole,
        ).first()
        nouveaux_indexes[token] = {
            "symbole": symbole,
            "libelle": request.POST.get(
                f"nouvel_index_{token}_libelle", "",
            ).strip(),
            "index_existant_id": index_existant.pk if index_existant else None,
        }

    def valeur_numerique(index_libelle, mois, brut):
        brut = brut.strip()
        if not brut:
            return None
        try:
            valeur = Decimal(brut.replace(",", "."))
        except InvalidOperation:
            erreurs.append(
                f"{index_libelle} {mois:%m/%Y} : valeur numérique invalide."
            )
            return None
        if valeur < 0:
            erreurs.append(
                f"{index_libelle} {mois:%m/%Y} : la valeur doit être positive."
            )
            return None
        return valeur

    operations = []
    mois_existants = controle["mois_tableur"]
    tous_les_mois = {
        **{mois.strftime("%Y%m"): mois for mois in mois_existants},
        **{f"col_{token}": mois for token, mois in nouveaux_mois.items()},
    }
    statuts = {}
    for code_mois, mois in tous_les_mois.items():
        statut = request.POST.get(
            f"statut_mois_{code_mois}",
            StatutIndex.IND_DEF,
        )
        if statut not in StatutIndex.values:
            erreurs.append(f"{mois:%m/%Y} : statut invalide.")
        statuts[code_mois] = statut

    for index_id, index in indexes.items():
        for code_mois, mois in tous_les_mois.items():
            cle = (
                f"valeur_index_{index_id}_{code_mois}"
                if not code_mois.startswith("col_")
                else (
                    f"valeur_colonne_"
                    f"{code_mois.removeprefix('col_')}_{index_id}"
                )
            )
            valeur = valeur_numerique(
                index.symbole, mois, request.POST.get(cle, ""),
            )
            if valeur is not None:
                operations.append((index, mois, valeur, statuts[code_mois]))

    for token, donnees in nouveaux_indexes.items():
        for code_mois, mois in tous_les_mois.items():
            cle = (
                f"valeur_nouvelle_ligne_{token}_{code_mois}"
                if not code_mois.startswith("col_")
                else f"valeur_nouvelle_ligne_{token}_{code_mois}"
            )
            valeur = valeur_numerique(
                donnees["symbole"], mois, request.POST.get(cle, ""),
            )
            if valeur is not None:
                operations.append((token, mois, valeur, statuts[code_mois]))

    if erreurs:
        messages.error(request, " ".join(erreurs))
        return redirect('projets:gestion_revision_prix', projet_id=projet.pk)

    nombre = 0
    with transaction.atomic():
        for index_id in indexes:
            IndexRevisionProjet.objects.get_or_create(
                projet=projet,
                index_id=index_id,
            )
        nouveaux_indexes_objets = {}
        for token, donnees in nouveaux_indexes.items():
            index_existant_id = donnees.pop("index_existant_id")
            index = (
                IndexReference.objects.get(pk=index_existant_id)
                if index_existant_id
                else IndexReference.objects.create(**donnees)
            )
            IndexRevisionProjet.objects.get_or_create(projet=projet, index=index)
            nouveaux_indexes_objets[token] = index
        for index, mois, valeur, statut in operations:
            if isinstance(index, str):
                index = nouveaux_indexes_objets[index]
            publication = IndexValeur.objects.filter(
                index=index,
                mois=mois,
            ).first()
            modification = (
                publication is None
                or publication.valeur != valeur
                or publication.statut != statut
            )
            IndexValeur.publier(
                index,
                mois,
                valeur,
                statut,
                source=request.POST.get("source_bulletin", "").strip(),
                date_publication=timezone.localdate(),
            )
            if modification:
                nombre += 1
    if nombre:
        messages.success(
            request,
            f"{nombre} valeur(s) d'index enregistrée(s).",
        )
    else:
        messages.warning(request, "Aucune valeur n'a été renseignée.")
    return redirect('projets:gestion_revision_prix', projet_id=projet.pk)
