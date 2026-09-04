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


class Materiel(models.Model):
    designation = models.CharField(_("Désignation"), max_length=150)
    type_materiel = models.CharField(_("Type"), max_length=100, blank=True)
    immatriculation = models.CharField(_("Immatriculation / N° de série"), max_length=50, blank=True)
    unite = models.CharField(_("Unité"), max_length=20, blank=True)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(_("Actif"), default=True)

    class Meta:
        verbose_name = _("Matériel")
        verbose_name_plural = _("Matériel")
        ordering = ['designation']

    def __str__(self):
        return self.designation

    
class Location(models.Model):
    designation = models.CharField(_("Désignation"), max_length=150)
    type_materiel = models.CharField(_("Type"), max_length=100, blank=True)
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