import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist

from projets.models.revision import IndexValeur, StatutIndex, TypeTerme


ZERO = Decimal("0")
CENT = Decimal("0.01")
QUATRE_DECIMALES = Decimal("0.0001")


class ErreurCalculRevision(ValueError):
    pass


def _premier_jour_mois(valeur):
    return valeur.replace(day=1)


def _index_valeur(index_id, mois, autoriser_provisoire, autoriser_report):
    valeur = (
        IndexValeur.objects.filter(index_id=index_id, mois=mois)
        .select_related("index")
        .first()
    )
    if valeur:
        if valeur.statut == StatutIndex.IND_ND:
            raise ErreurCalculRevision(
                f"Index indisponible pour {valeur.index.symbole} en {mois:%m/%Y}."
            )
        if (
            valeur.statut == StatutIndex.IND_PRO
            and not autoriser_provisoire
        ):
            raise ErreurCalculRevision(
                f"Index provisoire non autorisé pour {valeur.index.symbole} "
                f"en {mois:%m/%Y}."
            )
        return valeur.valeur, valeur.statut, mois

    if not autoriser_report or not autoriser_provisoire:
        raise ErreurCalculRevision(
            f"Index manquant pour le mois {mois:%m/%Y}."
        )

    valeur = (
        IndexValeur.objects.filter(
            index_id=index_id,
            mois__lt=mois,
            statut=StatutIndex.IND_PRO,
        )
        .select_related("index")
        .order_by("-mois")
        .first()
    )
    if not valeur:
        raise ErreurCalculRevision(f"Aucune valeur d'index disponible avant {mois:%m/%Y}.")
    return valeur.valeur, StatutIndex.IND_PRO, valeur.mois


def _arreter(valeur, methode):
    mode = ROUND_DOWN if methode == "TRONCATURE" else ROUND_HALF_UP
    return valeur.quantize(QUATRE_DECIMALES, rounding=mode)


def _calculer_cr(formule, mois_execution):
    projet = formule.projet
    mois_base = projet.mois_base_revision
    if not mois_base:
        raise ErreurCalculRevision("Le mois de base du projet n'est pas renseigné.")

    politique_provisoire = (
        projet.politique_index_revision == "PROVISOIRE_ET_REPORT_M2"
    )
    somme = ZERO
    details = []
    provisoire = False
    for terme in formule.termes.all():
        if terme.type_terme == TypeTerme.SIMPLE:
            courant, statut, mois_resolu = _index_valeur(
                terme.index_simple_id,
                mois_execution,
                politique_provisoire,
                politique_provisoire and projet.appliquer_report_m_plus_2,
            )
            base, _, _ = _index_valeur(
                terme.index_simple_id,
                mois_base,
                True,
                False,
            )
            if base == ZERO:
                raise ErreurCalculRevision(
                    f"Index de base nul pour {terme.index_simple.symbole}."
                )
            rapport = _arreter(
                courant / base,
                projet.methode_arrondi_revision,
            )
            expression = terme.index_simple.symbole
            indices = [{
                "symbole": terme.index_simple.symbole,
                "base": str(base),
                "courant": str(courant),
            }]
        else:
            courant_a, statut_a, mois_resolu_a = _index_valeur(
                terme.index_composite_a_id,
                mois_execution,
                politique_provisoire,
                politique_provisoire and projet.appliquer_report_m_plus_2,
            )
            courant_b, statut_b, mois_resolu_b = _index_valeur(
                terme.index_composite_b_id,
                mois_execution,
                politique_provisoire,
                politique_provisoire and projet.appliquer_report_m_plus_2,
            )
            base_a, _, _ = _index_valeur(
                terme.index_composite_a_id,
                mois_base,
                True,
                False,
            )
            base_b, _, _ = _index_valeur(
                terme.index_composite_b_id,
                mois_base,
                True,
                False,
            )
            denominateur = base_a * (Decimal("1") + base_b)
            if denominateur == ZERO:
                raise ErreurCalculRevision("Dénominateur du terme composite nul.")
            rapport = _arreter(
                (courant_a * (Decimal("1") + courant_b)) / denominateur,
                projet.methode_arrondi_revision,
            )
            statut = StatutIndex.IND_PRO if StatutIndex.IND_PRO in (
                statut_a, statut_b,
            ) else StatutIndex.IND_DEF
            mois_resolu = min(mois_resolu_a, mois_resolu_b)
            expression = (
                f"{terme.index_composite_a.symbole}"
                f"(1+{terme.index_composite_b.symbole})"
            )
            indices = [
                {
                    "symbole": terme.index_composite_a.symbole,
                    "base": str(base_a),
                    "courant": str(courant_a),
                },
                {
                    "symbole": terme.index_composite_b.symbole,
                    "base": str(base_b),
                    "courant": str(courant_b),
                },
            ]

        provisoire = provisoire or statut == StatutIndex.IND_PRO
        somme += terme.coefficient * rapport
        details.append({
            "expression": expression,
            "coefficient": str(terme.coefficient),
            "rapport": str(rapport),
            "statut_index": statut,
            "mois_resolu": mois_resolu.isoformat(),
            "indices": indices,
        })

    return {
        "cr": _arreter(formule.k + somme, projet.methode_arrondi_revision),
        "provisoire": provisoire,
        "termes": details,
    }


def _jours_calendaires_executes(debut, fin, periodes_arret):
    jours = (fin - debut).days + 1
    for arret, reprise in periodes_arret:
        debut_arret = max(debut, arret)
        fin_arret = min(fin, (reprise - timedelta(days=1)) if reprise else fin)
        if debut_arret <= fin_arret:
            jours -= (fin_arret - debut_arret).days + 1
    return max(0, jours)


def _parts_mensuelles(montant, date_debut, date_fin, periodes_arret=()):
    if date_fin < date_debut:
        raise ErreurCalculRevision("La période de l'attachement est invalide.")

    total_jours = _jours_calendaires_executes(
        date_debut, date_fin, periodes_arret,
    )
    if total_jours == 0:
        raise ErreurCalculRevision(
            "L'attachement ne contient aucun jour travaillable hors période d'arrêt."
        )
    if (
        _premier_jour_mois(date_debut) == _premier_jour_mois(date_fin)
        or len(_mois_segments(date_debut, date_fin)) == 1
    ):
        return {
            _premier_jour_mois(date_debut): {
                "montant": montant,
                "jours": total_jours,
            }
        }

    curseur = date_debut
    parts = {}
    while curseur <= date_fin:
        fin_mois = date(
            curseur.year,
            curseur.month,
            calendar.monthrange(curseur.year, curseur.month)[1],
        )
        fin = min(fin_mois, date_fin)
        jours = _jours_calendaires_executes(curseur, fin, periodes_arret)
        montant_part = (
            montant * Decimal(jours) / Decimal(total_jours)
        ).quantize(CENT, rounding=ROUND_HALF_UP)
        parts[curseur.replace(day=1)] = {
            "montant": montant_part,
            "jours": jours,
        }
        curseur = fin + timedelta(days=1)
    if parts:
        dernier = max(parts)
        parts[dernier]["montant"] += montant - sum(
            (part["montant"] for part in parts.values()), ZERO,
        )
    return parts


def _mois_segments(date_debut, date_fin):
    resultat = []
    curseur = date_debut.replace(day=1)
    fin = date_fin.replace(day=1)
    while curseur <= fin:
        resultat.append(curseur)
        curseur = (
            date(curseur.year + 1, 1, 1)
            if curseur.month == 12
            else curseur.replace(month=curseur.month + 1)
        )
    return resultat


def _quantite_precedente(attachement, ligne_lot_id):
    precedent = attachement.get_previous_attachement()
    if not precedent:
        return ZERO
    ligne = precedent.lignes_attachement.filter(
        ligne_lot_id=ligne_lot_id,
    ).first()
    return ligne.quantite_cumulee if ligne else ZERO


def _origine_formule_revision(ligne_bordereau):
    courante = ligne_bordereau
    while courante is not None:
        if courante.formule_revision_id:
            return courante, courante.formule_revision
        courante = courante.parent
    return None, None


@transaction.atomic
def calculer_revision_attachement(attachement):
    from projets.services.revision_readiness import (
        controle_indexes_revision,
        indicateur_revision_tableau_bord,
    )

    projet = attachement.projet
    if not projet.revision_prix_disponible:
        raise ErreurCalculRevision(
            "Un projet révisable avec un OS de commencement notifié est requis."
        )
    indicateur = indicateur_revision_tableau_bord(projet)
    if not indicateur or indicateur.statut != "PRET":
        raise ErreurCalculRevision(
            "Toutes les lignes principales du bordereau doivent avoir une "
            "formule valide avant le calcul."
        )
    controle_indexes = controle_indexes_revision(projet)
    if not controle_indexes["pret"]:
        raise ErreurCalculRevision(
            "Les index nécessaires ne sont pas disponibles ou ne sont pas à jour : "
            + " ".join(controle_indexes["erreurs"])
        )

    lignes = attachement.lignes_attachement.select_related(
        "ligne_lot__formule_revision",
        "ligne_lot__parent__formule_revision",
    ).order_by("pk")
    groupes = {}
    for ligne in lignes:
        quantite_periode = (
            ligne.quantite_cumulee
            - _quantite_precedente(attachement, ligne.ligne_lot_id)
        )
        if quantite_periode == ZERO:
            continue
        origine, formule = _origine_formule_revision(ligne.ligne_lot)
        if not formule and quantite_periode != ZERO:
            raise ErreurCalculRevision(
                f"La ligne « {ligne.designation} » n'a pas de formule de révision."
            )
        montant = (quantite_periode * ligne.prix_unitaire).quantize(
            CENT, rounding=ROUND_HALF_UP,
        )
        if montant == ZERO:
            continue
        groupe = groupes.setdefault(origine.pk, {
            "origine": origine,
            "formule": formule,
            "montant": ZERO,
            "lignes": 0,
        })
        groupe["montant"] += montant
        groupe["lignes"] += 1

    calculs = []
    total_revision = ZERO
    provisoire = False
    for groupe in groupes.values():
        origine = groupe["origine"]
        formule = groupe["formule"]
        montant = groupe["montant"]
        parts = _parts_mensuelles(
            montant,
            attachement.date_debut_periode,
            attachement.date_fin_periode,
            attachement._periodes_arret_notifiees(),
        )
        calcul_ligne = []
        for mois, repartition in parts.items():
            montant_mois = repartition["montant"]
            coefficient = _calculer_cr(formule, mois)
            revision = (
                montant_mois * (coefficient["cr"] - Decimal("1"))
            ).quantize(CENT, rounding=ROUND_HALF_UP)
            termes_justifies = []
            for terme in coefficient["termes"]:
                contribution = (
                    montant_mois
                    * Decimal(terme["coefficient"])
                    * (Decimal(terme["rapport"]) - Decimal("1"))
                ).quantize(CENT, rounding=ROUND_HALF_UP)
                termes_justifies.append({
                    **terme,
                    "contribution_revision_ht": str(contribution),
                })
            total_revision += revision
            provisoire = provisoire or coefficient["provisoire"]
            calcul_ligne.append({
                "mois": mois.isoformat(),
                "montant_ht": str(montant_mois),
                "cr": str(coefficient["cr"]),
                "revision_ht": str(revision),
                "jours_travailles": repartition["jours"],
                "provisoire": coefficient["provisoire"],
                "termes": termes_justifies,
            })
        calculs.append({
            "ligne": origine.designation,
            "formule": formule.code,
            "montant_ht": str(montant),
            "nombre_lignes_descendantes": groupe["lignes"],
            "mois": calcul_ligne,
        })

    total_revision = total_revision.quantize(CENT, rounding=ROUND_HALF_UP)
    index_ids = {
        index_id
        for formule in projet.formules_revision.prefetch_related("termes")
        for terme in formule.termes.all()
        for index_id in terme.index_ids
        if index_id
    }
    mois_definitifs = {}
    for index_id in index_ids:
        mois_definitifs[index_id] = (
            IndexValeur.objects.filter(
                index_id=index_id,
                statut=StatutIndex.IND_DEF,
            )
            .order_by("-mois")
            .values_list("mois", flat=True)
            .first()
        )
    dernier_definitif = (
        min(mois for mois in mois_definitifs.values() if mois)
        if mois_definitifs
        and all(mois_definitifs.values())
        else None
    )
    detail = {
        "lignes": calculs,
        "provisoire": provisoire,
        "dernier_mois_definitif": (
            dernier_definitif.isoformat() if dernier_definitif else None
        ),
        "mois_courant": date.today().replace(day=1).isoformat(),
        "indices_a_jour": bool(
            dernier_definitif
            and dernier_definitif >= date.today().replace(day=1)
        ),
    }
    attachement.montant_revision_prix = total_revision
    attachement.detail_calcul_revision = detail
    attachement.date_calcul_revision = timezone_now()
    attachement.save(
        update_fields=[
            "montant_revision_prix",
            "detail_calcul_revision",
            "date_calcul_revision",
        ]
    )

    try:
        decompte = attachement.decompte
    except ObjectDoesNotExist:
        decompte = None
    if decompte:
        decompte.montant_revision_prix = total_revision
        decompte.save()

    return total_revision, detail


def timezone_now():
    from django.utils import timezone

    return timezone.now()
