"""Dossier-private catalogue defaults and explicit form scoping."""
from django.core.exceptions import PermissionDenied


CATEGORIES_INITIALES = (
    ('PERSONNEL', 'Personnel'), ('MATERIEL', 'Matériel'),
    ('LOCATION', 'Location'), ('SOUS_TRAITANCE', 'Sous-traitance'),
    ('FOURNITURE', 'Fourniture'), ('TRANSPORT', 'Transport'),
    ('CONSOMMABLE', 'Consommable'),
)


def initialiser_categories_dossier(dossier):
    from projets.models import CategorieCharge
    for ordre, (code, nom) in enumerate(CATEGORIES_INITIALES, start=1):
        CategorieCharge.objects.using(dossier._state.db or 'default').get_or_create(
            dossier=dossier, code=code, defaults={'nom': nom, 'ordre': ordre},
        )


class CatalogueDossierFormMixin:
    def __init__(self, *args, dossier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.dossier = dossier or getattr(self.instance, 'dossier', None)
        if self.instance.pk and dossier and self.instance.dossier_id != dossier.pk:
            raise PermissionDenied("Catalogue d'un autre dossier.")
        if self.dossier:
            self.instance.dossier = self.dossier

    def clean(self):
        cleaned = super().clean()
        if self.dossier is None:
            from django.forms import ValidationError
            raise ValidationError("Sélectionnez un dossier pour modifier son catalogue.")
        return cleaned
