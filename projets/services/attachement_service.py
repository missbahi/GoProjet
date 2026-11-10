import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from projets.models import LigneAttachement, LigneBordereau


class DonneesAttachementInvalides(ValueError):
    """Données de lignes d'attachement non exploitables."""


def enregistrer_lignes_attachement(attachement, lignes_json):
    """Valide puis remplace les lignes d'un attachement dans une transaction parente."""
    nouvelles_lignes = preparer_lignes_attachement(attachement, lignes_json)
    if attachement.suivants.exists():
        champs = (
            'ligne_lot_id', 'numero', 'designation', 'unite', 'quantite_initiale',
            'prix_unitaire', 'quantite_realisee', 'quantite_cumulee',
        )
        existantes = {
            ligne.ligne_lot_id: tuple(getattr(ligne, champ) for champ in champs)
            for ligne in attachement.lignes_attachement.all()
        }
        soumises = {
            ligne.ligne_lot_id: tuple(getattr(ligne, champ) for champ in champs)
            for ligne in nouvelles_lignes
        }
        if existantes != soumises:
            raise DonneesAttachementInvalides(
                "Les lignes ne peuvent pas être modifiées lorsqu'un attachement suivant existe."
            )
    LigneAttachement.objects.filter(attachement=attachement).delete()
    LigneAttachement.objects.bulk_create(nouvelles_lignes)
    attachement.recalculer_montant_ht()


def preparer_lignes_attachement(attachement, lignes_json, *, conserver_instantanes=False):
    if not lignes_json:
        lignes_data = []
    else:
        try:
            lignes_data = json.loads(lignes_json)
        except (TypeError, json.JSONDecodeError) as error:
            raise DonneesAttachementInvalides("Le format des lignes d'attachement est invalide.") from error

    if not isinstance(lignes_data, list):
        raise DonneesAttachementInvalides("Les lignes d'attachement doivent être une liste.")

    lignes_saisies = []
    identifiants = []

    for ligne_data in lignes_data:
        if not isinstance(ligne_data, dict) or 'id' not in ligne_data:
            raise DonneesAttachementInvalides("Chaque ligne d'attachement doit contenir un identifiant.")

        try:
            ligne_id = int(ligne_data['id'])
            quantite_realisee = Decimal(str(ligne_data.get('quantite_realisee', 0)))
        except (TypeError, ValueError, InvalidOperation) as error:
            raise DonneesAttachementInvalides("Une quantité réalisée est invalide.") from error

        if not quantite_realisee.is_finite():
            raise DonneesAttachementInvalides("Une quantité réalisée doit être un nombre fini.")
        if quantite_realisee < 0:
            raise DonneesAttachementInvalides("Le cumul réalisé ne peut pas être négatif.")

        identifiants.append(ligne_id)
        lignes_saisies.append((ligne_id, quantite_realisee))

    if len(identifiants) != len(set(identifiants)):
        raise DonneesAttachementInvalides("Une ligne de bordereau ne peut être présente qu'une fois.")

    precedent = attachement.get_previous_attachement()
    lignes_precedentes = {
        ligne.ligne_lot_id: ligne
        for ligne in precedent.lignes_attachement.all()
    } if precedent else {}
    if conserver_instantanes:
        lignes_precedentes.update({
            ligne.ligne_lot_id: ligne for ligne in attachement.lignes_attachement.all()
        })
    quantites_saisies = dict(lignes_saisies)
    for ligne_id, ligne_precedente in lignes_precedentes.items():
        if ligne_id not in quantites_saisies:
            lignes_saisies.append((ligne_id, ligne_precedente.quantite_cumulee))
            identifiants.append(ligne_id)
            quantites_saisies[ligne_id] = ligne_precedente.quantite_cumulee

    lignes_bordereau = LigneBordereau.objects.filter(
        id__in=identifiants,
        lot__projet=attachement.projet,
    ).in_bulk()
    if len(lignes_bordereau) != len(identifiants):
        raise DonneesAttachementInvalides("Une ligne sélectionnée n'appartient pas au projet.")

    nouvelles_lignes = []
    instantanes = {
        ligne.ligne_lot_id: ligne for ligne in attachement.lignes_attachement.all()
    } if conserver_instantanes else {}
    for ligne_id, quantite_realisee in lignes_saisies:
        ligne_bordereau = lignes_bordereau[ligne_id]
        source = instantanes.get(ligne_id, ligne_bordereau)
        if not source.designation or not source.designation.strip():
            continue

        quantite = Decimal('0') if source.is_title else quantite_realisee
        ligne_attachement = LigneAttachement(
            attachement=attachement,
            ligne_lot=ligne_bordereau,
            numero=source.numero,
            designation=source.designation,
            unite=source.unite,
            prix_unitaire=source.prix_unitaire,
            quantite_initiale=source.quantite_initiale if ligne_id in instantanes else source.quantite,
            quantite_realisee=quantite,
            quantite_cumulee=quantite,
        )
        try:
            ligne_attachement.full_clean(validate_unique=False)
        except ValidationError as error:
            print(
                "Ligne invalide:",
                ligne_id,
                ligne_bordereau.numero,
                repr(ligne_bordereau.designation),
                error.message_dict,
            )
            raise DonneesAttachementInvalides(
                f"Ligne {ligne_id, ligne_bordereau.numero} invalide : {error.message_dict}") from error
        nouvelles_lignes.append(ligne_attachement)

    return nouvelles_lignes
