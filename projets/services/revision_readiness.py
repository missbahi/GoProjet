from collections import Counter
from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from projets.models.revision import (
    IndexRevisionProjet,
    IndexValeur,
    IndicateurRevisionProjet,
    StatutIndex,
)
from projets.models.projet import LigneBordereau
from projets.services.sommaire import lignes_principales_lot


def invalider_indicateur_revision(projet_id):
    IndicateurRevisionProjet.objects.filter(projet_id=projet_id).update(
        statut=IndicateurRevisionProjet.Statut.A_CONTROLER,
    )


def compter_lignes_simples_couvertes(projet):
    """Compte les feuilles couvertes par chaque formule, héritage compris."""
    lignes = list(
        LigneBordereau.objects.filter(lot__projet=projet).values(
            "id", "parent_id", "formule_revision_id",
        )
    )
    par_id = {ligne["id"]: ligne for ligne in lignes}
    parents = {
        ligne["parent_id"] for ligne in lignes
        if ligne["parent_id"] is not None
    }
    couverture = Counter()
    for ligne in lignes:
        if ligne["id"] in parents:
            continue
        courante = ligne
        formule_id = None
        while courante is not None:
            if courante["formule_revision_id"] is not None:
                formule_id = courante["formule_revision_id"]
                break
            courante = par_id.get(courante["parent_id"])
        if formule_id is not None:
            couverture[formule_id] += 1
    return couverture


def _mois_dans_intervalle(debut, fin):
    curseur = debut.replace(day=1)
    fin = fin.replace(day=1)
    mois = []
    while curseur <= fin:
        mois.append(curseur)
        if curseur.month == 12:
            curseur = date(curseur.year + 1, 1, 1)
        else:
            curseur = curseur.replace(month=curseur.month + 1)
    return mois


def controle_indexes_revision(projet):
    """Contrôle les index M0 et les mois couverts par les attachements."""
    index_ids = {
        index_id
        for formule in projet.formules_revision.prefetch_related("termes")
        for terme in formule.termes.all()
        for index_id in terme.index_ids
        if index_id is not None
    }
    mois_requis = set()
    mois_tableur = []
    if projet.mois_base_revision:
        mois_base = projet.mois_base_revision.replace(day=1)
        mois_requis.add(mois_base)
        mois_tableur.append(mois_base)
    attachements = list(
        projet.attachements.only(
            "date_debut_periode", "date_fin_periode",
        ).order_by("date_debut_periode")
    )
    for attachement in attachements:
        mois_requis.update(
            _mois_dans_intervalle(
                attachement.date_debut_periode,
                attachement.date_fin_periode,
            )
        )
    dernier_attachement_mois = (
        max(attachement.date_fin_periode for attachement in attachements).replace(day=1)
        if attachements else None
    )
    os_commencement = projet.os_commencement
    mois_fin = dernier_attachement_mois or (
        os_commencement.date_effet.replace(day=1) if os_commencement else None
    )
    if os_commencement and mois_fin:
        mois_osc = os_commencement.date_effet.replace(day=1)
        mois_depuis_osc = _mois_dans_intervalle(mois_osc, mois_fin)
        mois_requis.update(mois_depuis_osc)
        mois_tableur.extend(
            mois for mois in mois_depuis_osc if mois not in mois_tableur
        )
    mois_tableur.extend(
        mois
        for mois in IndexValeur.objects.filter(
            index__projets_revision__projet=projet,
        ).values_list("mois", flat=True).distinct()
        if mois not in mois_tableur
    )
    valeurs = list(
        IndexValeur.objects.filter(
            index_id__in=index_ids,
            mois__in=mois_requis,
        ).select_related("index")
    )
    valeurs_par_index_mois = {
        (valeur.index_id, valeur.mois): valeur for valeur in valeurs
    }
    manquants = []
    provisoires = []
    for index_id in sorted(index_ids):
        for mois in sorted(mois_requis):
            valeur = valeurs_par_index_mois.get((index_id, mois))
            if valeur is None:
                manquants.append({"index_id": index_id, "mois": mois})
            elif valeur.statut == StatutIndex.IND_PRO:
                provisoires.append({"index_id": index_id, "mois": mois})

    dernier_mois_par_index = {}
    for index_id in index_ids:
        dernier_mois_par_index[index_id] = (
            IndexValeur.objects.filter(index_id=index_id)
            .order_by("-mois")
            .values_list("mois", flat=True)
            .first()
        )
    dernier_bulletin_disponible = (
        min(
            mois for mois in dernier_mois_par_index.values()
            if mois is not None
        )
        if index_ids and all(dernier_mois_par_index.values())
        else None
    )
    bulletin_a_jour = bool(
        dernier_attachement_mois
        and dernier_bulletin_disponible
        and dernier_bulletin_disponible >= dernier_attachement_mois
    )
    erreurs = []
    if not index_ids:
        erreurs.append("Aucun index n'est utilisé par les formules.")
    if manquants:
        erreurs.append(
            f"{len(manquants)} valeur(s) d'index requise(s) sont absente(s)."
        )
    if (
        dernier_attachement_mois
        and not bulletin_a_jour
    ):
        erreurs.append(
            "Le dernier bulletin disponible est antérieur au dernier mois "
            "des attachements."
        )
    if (
        projet.politique_index_revision == "DEFINITIF_SEULEMENT"
        and provisoires
    ):
        erreurs.append(
            "Des index requis sont provisoires alors que la politique du projet "
            "impose des index définitifs."
        )
    return {
        "pret": not erreurs,
        "erreurs": erreurs,
        "index_ids": index_ids,
        "mois_requis": sorted(mois_requis),
        "mois_tableur": sorted(mois_tableur),
        "manquants": manquants,
        "provisoires": provisoires,
        "dernier_attachement_mois": dernier_attachement_mois,
        "dernier_bulletin_disponible": dernier_bulletin_disponible,
        "bulletin_a_jour": bulletin_a_jour,
    }


def index_ids_tableur(projet, controle):
    """Index requis ou déjà alimentés pour un mois du tableur courant."""
    ids = set(controle["index_ids"])
    ids.update(
        IndexRevisionProjet.objects.filter(projet=projet)
        .values_list("index_id", flat=True)
    )
    return ids


def lignes_principales_revision_lot(lot):
    """Raccourcit les grandes lignes vers leur ancêtre d'affectation direct."""
    titres, principales = lignes_principales_lot(lot)
    lignes = {
        ligne.pk: ligne
        for ligne in lot.lignes.select_related("formule_revision", "parent").all()
    }
    if not principales:
        principales = [
            {
                "id": ligne.pk,
                "numero": ligne.numero,
                "designation": ligne.designation,
            }
            for ligne in lignes.values()
            if ligne.parent_id is None
        ]
    resultat = {}
    for principale in principales:
        courante = lignes.get(principale["id"])
        origine = courante
        while courante is not None and not courante.formule_revision_id:
            courante = lignes.get(courante.parent_id)
        cible = courante or origine
        if cible is not None:
            resultat[cible.pk] = {
                **principale,
                "id": cible.pk,
                "numero": cible.numero,
                "designation": cible.designation,
            }
    return titres, list(resultat.values())


@transaction.atomic
def controler_preparation_revision(projet):
    """Calcule puis mémorise le premier contrôle de préparation."""
    indicateur, _ = IndicateurRevisionProjet.objects.get_or_create(projet=projet)
    erreurs = []
    racines = []
    for lot in projet.lots.all():
        _, principales = lignes_principales_revision_lot(lot)
        for principale in principales:
            racines.append({
                "id": principale["id"],
                "nom": lot.nom,
                "designation": principale["designation"],
            })
    ids = [ligne["id"] for ligne in racines]
    lignes_formulees = set(
        projet.lots.filter(lignes__pk__in=ids, lignes__formule_revision__isnull=False)
        .values_list("lignes__pk", flat=True)
    )
    formules = list(projet.formules_revision.prefetch_related("termes"))

    if not projet.os_commencement:
        erreurs.append("Aucun OS de commencement notifié avec date d'effet n'est défini.")
    if not projet.mois_base_revision:
        erreurs.append("Le mois de base de la révision n'est pas renseigné.")
    if not projet.lots.exists():
        erreurs.append("Aucun lot n'est défini.")
    if projet.lots.exists() and not racines:
        erreurs.append("Aucune ligne racine n'est définie dans les bordereaux.")
    if not formules:
        erreurs.append("Aucune formule de révision n'est créée.")

    non_couvertes = [
        {
            "lot": ligne["nom"],
            "ligne": ligne["designation"],
        }
        for ligne in racines
        if ligne["id"] not in lignes_formulees
    ]
    for ligne in non_couvertes:
        erreurs.append(
            f"Lot {ligne['lot']} : la ligne racine « {ligne['ligne']} » n'a pas de formule."
        )

    for formule in formules:
        try:
            formule.valider()
        except ValidationError as error:
            erreurs.append(
                f"Formule {formule.code} : {' '.join(error.messages)}"
            )

    indicateur.statut = (
        IndicateurRevisionProjet.Statut.PRET
        if not erreurs
        else IndicateurRevisionProjet.Statut.INCOMPLET
    )
    indicateur.details = {
        "erreurs": erreurs,
        "nombre_lots": projet.lots.count(),
        "nombre_formules": len(formules),
        "nombre_lignes_racines": len(racines),
        "nombre_lignes_couvertes": len(racines) - len(non_couvertes),
        "nombre_lignes_non_couvertes": len(non_couvertes),
    }
    indicateur.dernier_controle = timezone.now()
    indicateur.save(update_fields=["statut", "details", "dernier_controle"])
    return indicateur


def indicateur_revision_tableau_bord(projet):
    """Retourne le verdict mémorisé ou effectue le premier contrôle."""
    if not projet.revision_prix_disponible:
        return None
    indicateur = IndicateurRevisionProjet.objects.filter(projet=projet).first()

    if (
        indicateur is None
        or indicateur.statut == IndicateurRevisionProjet.Statut.A_CONTROLER
    ):
        indicateur = controler_preparation_revision(projet)
    return indicateur
