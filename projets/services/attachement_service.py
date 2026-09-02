import json
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from projets.models import LigneAttachement, LigneBordereau


class DonneesAttachementInvalides(ValueError):
    """Données de lignes d'attachement non exploitables."""


def enregistrer_lignes_attachement(attachement, lignes_json):
    """Valide puis remplace les lignes d'un attachement dans une transaction parente."""
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

        identifiants.append(ligne_id)
        lignes_saisies.append((ligne_id, quantite_realisee))

    if len(identifiants) != len(set(identifiants)):
        raise DonneesAttachementInvalides("Une ligne de bordereau ne peut être présente qu'une fois.")

    lignes_bordereau = LigneBordereau.objects.filter(id__in=identifiants, lot__projet=attachement.projet,).in_bulk()
    if len(lignes_bordereau) != len(identifiants):
        raise DonneesAttachementInvalides("Une ligne sélectionnée n'appartient pas au projet.")

    nouvelles_lignes = []
    for ligne_id, quantite_realisee in lignes_saisies:
        ligne_bordereau = lignes_bordereau[ligne_id]
        if not ligne_bordereau.designation or not ligne_bordereau.designation.strip():
            continue

        if quantite_realisee <= 0 and not ligne_bordereau.is_title:
            continue

        quantite = Decimal('0') if ligne_bordereau.is_title else quantite_realisee
        ligne_attachement = LigneAttachement(
            attachement=attachement,
            ligne_lot=ligne_bordereau,
            numero=ligne_bordereau.numero,
            designation=ligne_bordereau.designation,
            unite=ligne_bordereau.unite,
            prix_unitaire=ligne_bordereau.prix_unitaire,
            quantite_initiale=ligne_bordereau.quantite,
            quantite_realisee=quantite,
            quantite_cumulee=quantite,
        )
        try:
            ligne_attachement.full_clean()
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

    LigneAttachement.objects.filter(attachement=attachement).delete()
    LigneAttachement.objects.bulk_create(nouvelles_lignes)
