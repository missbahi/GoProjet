from django.db import models
from django.utils.translation import gettext_lazy as _


class Personnel(models.Model):
    nom = models.CharField(_("Nom"), max_length=150)
    fonction = models.CharField(_("Fonction"), max_length=100, blank=True)
    telephone = models.CharField(_("Téléphone"), max_length=20, blank=True)
    unite = models.CharField(_("Unité"), max_length=50, blank=True, default="")
    tarif = models.DecimalField(_("Tarif"), max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Personnel")
        verbose_name_plural = _("Personnel")
        ordering = ['nom']

    def __str__(self):
        return f"{self.nom} ({self.fonction})" if self.fonction else self.nom

class TypeMateriel(models.Model):
    """Type d'engin : Pelle sur chenilles à godet, Pelle chenilles BRH, etc."""

    ICONE_DIR = "images/materiels"

    nom = models.CharField(_("Désignation"), max_length=255, unique=True)
    icone = models.CharField(
        _("Icône"),
        max_length=120,
        blank=True,
        help_text=_("Nom du fichier situé dans static/images/materiels/"),
    )
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Type de matériel")
        verbose_name_plural = _("Types de matériel")
        ordering = ["nom"]

    def __str__(self):
        return self.nom

    @property
    def icone_path(self):
        """Chemin relatif utilisable avec {% static %}."""
        if self.icone:
            return f"{self.ICONE_DIR}/{self.icone}"
        return f"{self.ICONE_DIR}/default.avif"

class EtatMateriel(models.TextChoices):
    """États possibles d'un matériel sur un chantier."""
    MARCHE = "MARCHE", _("En marche")
    ARRET = "ARRET", _("À l'arrêt")
    PANNE = "PANNE", _("En panne")
    MAINTENANCE = "MAINTENANCE", _("En maintenance")
    DISPONIBLE = "DISPONIBLE", _("Disponible")

class Materiel(models.Model):
    designation = models.CharField(_("Désignation"), max_length=150)
    type_materiel = models.ForeignKey(
        TypeMateriel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="materiels",
        verbose_name=_("Type de matériel"),
    )
    immatriculation = models.CharField(_("N° de parc"), max_length=50, blank=True)
    unite = models.CharField(_("Unité"), max_length=20, blank=True)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Matériel")
        verbose_name_plural = _("Matériel")
        ordering = ['designation']

    def __str__(self):
        return self.designation

class Atelier(models.Model):
    """Atelier (ou équipe) rattaché à un projet.

    Ex. : Atelier 01 Voirie, Atelier 02 Terrassements généraux.
    """

    projet = models.ForeignKey(
        'projets.Projet',
        on_delete=models.CASCADE,
        related_name='ateliers',
        null=True,        
        blank=True,
        verbose_name=_("Projet"),
    )
    code = models.CharField(_("Code"), max_length=10)
    libelle = models.CharField(_("Libellé"), max_length=255)
    description = models.TextField(_("Description"), blank=True)
    actif = models.BooleanField(_("Actif"), default=True)
    date_creation = models.DateTimeField(_("Créé le"), auto_now_add=True)

    class Meta:
        verbose_name = _("Atelier")
        verbose_name_plural = _("Ateliers")
        ordering = ["projet", "code"]
        constraints = [
            models.UniqueConstraint(
                fields=["projet", "code"],
                name="unique_atelier_projet_code",
            ),
        ]

    def __str__(self):
        return f"Atelier {self.code} {self.libelle}"

    def clean(self):
        super().clean()
        if self.code:
            self.code = self.code.strip().zfill(2)

class AffectationRessource(models.Model):
    """Affectation d'un matériel de la base à un atelier."""

    atelier = models.ForeignKey(
        Atelier, 
        on_delete=models.CASCADE, 
        related_name="affectations",
        verbose_name=_("Atelier"),
    )
    materiel = models.ForeignKey(
        Materiel,
        on_delete=models.PROTECT, 
        related_name="affectations",
        verbose_name=_("Matériel"),
    )
    date_debut = models.DateField(_("Début"))
    date_fin = models.DateField(_("Fin"), null=True, blank=True)
    commentaire = models.CharField(_("Commentaire"), max_length=255, blank=True)

    class Meta:
        verbose_name = _("Affectation de ressource")
        verbose_name_plural = _("Affectations de ressources")
        ordering = ["-date_debut"]
        constraints = [
            models.UniqueConstraint(
                fields=["atelier", "materiel", "date_debut"],
                name="unique_affectation_materiel_atelier_date",
            ),
            models.CheckConstraint(
                condition=models.Q(date_fin__isnull=True)
                | models.Q(date_fin__gte=models.F("date_debut")),
                name="affectation_dates_coherentes",
            ),
        ]
 
    def __str__(self):
        return f"{self.materiel} → {self.atelier}"

class Location(models.Model):
    designation = models.CharField(_("Désignation"), max_length=150)
    type_materiel = models.CharField(_("Type de matériel"), max_length=100, blank=True)
    locataire = models.CharField(_("Locataire"), max_length=50, blank=True)
    unite = models.CharField(_("Unité"), max_length=20, blank=True)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Location")
        verbose_name_plural = _("Locations")
        ordering = ['designation']

    def __str__(self):
        return self.designation

class Transport(models.Model):
    designation = models.CharField(_("Désignation"), max_length=150)
    type_transport = models.CharField(_("Type"), max_length=100, blank=True)
    transporteur = models.CharField(_("Transporteur"), max_length=50, blank=True)
    unite = models.CharField(_("Unité"), max_length=20, blank=True)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Transport")
        verbose_name_plural = _("Transports")
        ordering = ['designation']

    def __str__(self):
        return self.designation

class SousTraitance(models.Model):
    designation = models.CharField(_("Désignation"), max_length=150)
    type_sous_traitance = models.CharField(_("Type"), max_length=100, blank=True)
    prestataire = models.CharField(_("Prestataire"), max_length=50, blank=True)
    unite = models.CharField(_("Unité"), max_length=20, blank=True)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Sous-traitance")
        verbose_name_plural = _("Sous-traitances")
        ordering = ['designation']

    def __str__(self):
        return self.designation

class Consommable(models.Model):
    designation = models.CharField(_("Désignation"), max_length=150)
    type_consommable = models.CharField(_("Type"), max_length=100, blank=True)
    fournisseur = models.CharField(_("Fournisseur"), max_length=50, blank=True)
    unite = models.CharField(_("Unité"), max_length=20, blank=True)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Consommable")
        verbose_name_plural = _("Consommables")
        ordering = ['designation']

    def __str__(self):
        return self.designation

class Fourniture(models.Model):
    designation = models.CharField(_("Désignation"), max_length=150)
    type_fourniture = models.CharField(_("Type"), max_length=100, blank=True)
    fournisseur = models.CharField(_("Fournisseur"), max_length=50, blank=True)
    unite = models.CharField(_("Unité"), max_length=20, blank=True)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Fourniture")
        verbose_name_plural = _("Fournitures")
        ordering = ['designation']

    def __str__(self):
        return self.designation