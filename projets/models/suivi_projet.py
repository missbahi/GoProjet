from decimal import Decimal
from datetime import date
import hashlib
import os

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _

from .projet import Projet


class ActiviteTravauxMixin:
    def clean(self):
        super().clean()
        if self.projet_id and self.projet.dossier_id:
            if self.projet.dossier.activite != 'TRAVAUX':
                raise ValidationError({
                    'projet': _('Ce suivi est disponible uniquement pour les dossiers de travaux.')
                })


def rapport_journalier_document_upload_path(instance, filename):
    return f'rapports_journaliers/projet_{instance.projet_id}/{instance.date}/{filename}'


def situation_mensuelle_document_upload_path(instance, filename):
    situation = instance.situation
    return f'situations_mensuelles/projet_{situation.projet_id}/{situation.annee}-{situation.mois:02d}/{filename}'


class RapportJournalier(ActiviteTravauxMixin, models.Model):
    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name='rapports_journaliers',
        verbose_name=_('Projet')
    )
    date = models.DateField(verbose_name=_('Date'))
    meteo = models.CharField(max_length=100, blank=True, verbose_name=_('Météo'))
    temperature = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        verbose_name=_('Température')
    )
    travaux_realises = models.TextField(blank=True, verbose_name=_('Travaux réalisés'))
    evenements = models.TextField(blank=True, verbose_name=_('Événements'))
    observations = models.TextField(blank=True, verbose_name=_('Observations'))
    redacteur = models.CharField(max_length=150, blank=True, verbose_name=_('Rédacteur'))
    document = models.FileField(
        _('Document'), upload_to=rapport_journalier_document_upload_path,
        blank=True, null=True
    )
    original_filename = models.CharField(
        max_length=255, blank=True, verbose_name=_('Nom de fichier original')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date', '-id']
        constraints = [
            models.UniqueConstraint(fields=['projet', 'date'], name='unique_rapport_journalier_projet_date')
        ]

    def __str__(self):
        return f'{self.projet.nom} - {self.date}'

    @property
    def document_nom(self):
        if self.original_filename:
            return self.original_filename
        elif self.document:
            return os.path.basename(self.document.name)
        return ''

    @property
    def total_depenses(self):
        if hasattr(self, 'total_depenses_annotated'):
            return self.total_depenses_annotated
        return self.depenses.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')


class CategorieDepenseTravaux(models.TextChoices):
    PERSONNEL = 'PERSONNEL', _('Personnel')
    MATERIEL = 'MATERIEL', _('Matériel')
    LOCATION = 'LOCATION', _('Location')
    SOUS_TRAITANCE = 'SOUS_TRAITANCE', _('Sous-traitance')
    FOURNITURE = 'FOURNITURE', _('Fourniture')
    TRANSPORT = 'TRANSPORT', _('Transport')
    CONSOMMABLE = 'CONSOMMABLE', _('Consommable')


class DepenseRapportJournalier(models.Model):
    rapport = models.ForeignKey(
        RapportJournalier, on_delete=models.CASCADE, related_name='depenses',
        verbose_name=_('Rapport journalier')
    )
    categorie = models.CharField(max_length=30, choices=CategorieDepenseTravaux.choices)
    designation = models.CharField(max_length=200, verbose_name=_('Désignation'))
    quantite = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('1.000'))
    unite = models.CharField(max_length=30, blank=True, verbose_name=_('Unité'))
    # Ancienne colonne "montant" réutilisée telle quelle pour ne pas casser les données existantes
    prix_unitaire = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        db_column='montant', verbose_name=_('Prix unitaire')
    )
    observations = models.TextField(blank=True, verbose_name=_('Observations'))
    montant = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        db_column='montant_total', editable=False, verbose_name=_('Montant')
    )

    def save(self, *args, **kwargs):
        self.montant = (self.quantite or Decimal('0.000')) * (self.prix_unitaire or Decimal('0.00'))
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['categorie', 'id']

    def __str__(self):
        return f'{self.get_categorie_display()} - {self.designation}'


class StockRapportJournalier(models.Model):
    rapport = models.ForeignKey(
        RapportJournalier, on_delete=models.CASCADE, related_name='stocks',
        verbose_name=_('Rapport journalier')
    )
    designation = models.CharField(max_length=200, verbose_name=_('Désignation'))
    unite = models.CharField(max_length=30, blank=True, verbose_name=_('Unité'))
    quantite_entree = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    quantite_sortie = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    stock_restant = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))

    class Meta:
        ordering = ['designation', 'id']

    def __str__(self):
        return self.designation


class SituationMensuelle(ActiviteTravauxMixin, models.Model):
    projet = models.ForeignKey(
        Projet, on_delete=models.CASCADE, related_name='situations_mensuelles',
        verbose_name=_('Projet')
    )
    annee = models.PositiveIntegerField(verbose_name=_('Année'))
    mois = models.PositiveSmallIntegerField(verbose_name=_('Mois'))
    date_debut = models.DateField(null=True, blank=True, verbose_name=_('Date de début'))
    date_fin = models.DateField(null=True, blank=True, verbose_name=_('Date de fin'))
    chiffre_affaires = models.DecimalField(
        max_digits=15, decimal_places=2, default=Decimal('0.00'),
        verbose_name=_("Chiffre d'affaires")
    )
    observations = models.TextField(blank=True, verbose_name=_('Observations'))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-annee', '-mois', '-id']
        constraints = [
            models.UniqueConstraint(fields=['projet', 'annee', 'mois'], name='unique_situation_mensuelle_projet_periode')
        ]

    def clean(self):
        super().clean()
        if self.mois < 1 or self.mois > 12:
            raise ValidationError({'mois': _('Le mois doit être compris entre 1 et 12.')})

    def __str__(self):
        return f'{self.projet.nom} - {self.mois:02d}/{self.annee}'

    @property
    def total_depenses(self):
        if hasattr(self, 'total_depenses_annotated'):
            return self.total_depenses_annotated
        return self.depenses.aggregate(total=Sum('montant'))['total'] or Decimal('0.00')

    @property
    def total_stock(self):
        if hasattr(self, 'total_stock_annotated'):
            return self.total_stock_annotated
        return self.stocks.aggregate(total=Sum('valeur'))['total'] or Decimal('0.00')


class DocumentSituationMensuelle(models.Model):
    situation = models.ForeignKey(
        SituationMensuelle, on_delete=models.CASCADE, related_name='documents',
        verbose_name=_('Situation mensuelle'),
    )
    fichier = models.FileField(
        _('Document'), upload_to=situation_mensuelle_document_upload_path,
    )
    original_filename = models.CharField(max_length=255, blank=True)
    checksum = models.CharField(max_length=64, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['situation', 'checksum'],
                condition=~models.Q(checksum=''),
                name='unique_situation_document_checksum',
            ),
        ]

    def save(self, *args, **kwargs):
        if self.fichier and not self.checksum:
            digest = hashlib.sha256()
            self.fichier.open('rb')
            for chunk in iter(lambda: self.fichier.read(1024 * 1024), b''):
                digest.update(chunk)
            self.fichier.seek(0)
            self.checksum = digest.hexdigest()
        if self.fichier and not self.original_filename:
            self.original_filename = os.path.basename(self.fichier.name)
        super().save(*args, **kwargs)

    @property
    def nom(self):
        return self.original_filename or os.path.basename(self.fichier.name)


class DepenseSituationMensuelle(models.Model):
    situation = models.ForeignKey(
        SituationMensuelle, on_delete=models.CASCADE, related_name='depenses',
        verbose_name=_('Situation mensuelle')
    )
    categorie = models.CharField(max_length=30, choices=CategorieDepenseTravaux.choices)
    designation = models.CharField(max_length=200, verbose_name=_('Désignation'))
    montant = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ['categorie', 'id']


class StockSituationMensuelle(models.Model):
    situation = models.ForeignKey(
        SituationMensuelle, on_delete=models.CASCADE, related_name='stocks',
        verbose_name=_('Situation mensuelle')
    )
    designation = models.CharField(max_length=200, verbose_name=_('Désignation'))
    unite = models.CharField(max_length=30, blank=True, verbose_name=_('Unité'))
    quantite = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    prix_unitaire = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    valeur = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ['designation', 'id']

    def save(self, *args, **kwargs):
        self.valeur = self.quantite * self.prix_unitaire
        super().save(*args, **kwargs)
