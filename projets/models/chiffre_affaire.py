import calendar
from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from .suivi_projet import ActiviteTravauxMixin


class ChiffreAffaire(ActiviteTravauxMixin, models.Model):
    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        VALIDE = 'VALIDE', 'Validé'

    class Origine(models.TextChoices):
        DEBUT = 'DEBUT', 'Suivi depuis le début du projet'
        REPRISE = 'REPRISE', 'Reprise de cumuls antérieurs'

    projet = models.ForeignKey('Projet', on_delete=models.CASCADE, related_name='chiffres_affaires')
    periode = models.DateField(verbose_name='Mois du CA')
    origine = models.CharField(max_length=10, choices=Origine.choices, default=Origine.DEBUT)
    observations = models.TextField(blank=True)
    statut = models.CharField(max_length=10, choices=Statut.choices, default=Statut.BROUILLON)
    montant_mensuel = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), editable=False)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    modifie_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    valide_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    date_validation = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['periode', 'pk']
        verbose_name = "Chiffre d'affaires mensuel"
        verbose_name_plural = "Chiffres d'affaires mensuels"
        constraints = [
            models.UniqueConstraint(fields=['projet', 'periode'], name='unique_ca_projet_mois'),
        ]

    def clean(self):
        super().clean()
        if self.periode and self.periode.day != 1:
            raise ValidationError({'periode': 'Le mois du CA doit être représenté par son premier jour.'})

    @property
    def date_debut(self):
        return self.periode

    @property
    def date_fin(self):
        return date(self.periode.year, self.periode.month, calendar.monthrange(self.periode.year, self.periode.month)[1])

    def __str__(self):
        return f'CA {self.periode:%m/%Y} — {self.projet.nom}'


class LigneChiffreAffaire(models.Model):
    ca = models.ForeignKey(ChiffreAffaire, on_delete=models.CASCADE, related_name='lignes')
    ligne_bordereau = models.ForeignKey('LigneBordereau', on_delete=models.PROTECT, related_name='lignes_ca')
    numero = models.CharField(max_length=20, blank=True)
    designation = models.TextField()
    unite = models.CharField(max_length=10, blank=True)
    est_titre = models.BooleanField(default=False)
    niveau = models.PositiveIntegerField(default=0)
    ordre = models.PositiveIntegerField(default=0)
    quantite_marche = models.DecimalField(max_digits=15, decimal_places=3)
    prix_unitaire = models.DecimalField(max_digits=12, decimal_places=2)
    quantite_cumulee = models.DecimalField(max_digits=15, decimal_places=3)
    cumul_initial = models.DecimalField(max_digits=15, decimal_places=3, default=Decimal('0'))

    class Meta:
        ordering = ['ordre', 'pk']
        constraints = [
            models.UniqueConstraint(fields=['ca', 'ligne_bordereau'], name='unique_ca_ligne_bordereau'),
            models.CheckConstraint(condition=models.Q(quantite_cumulee__gte=0), name='ca_cumul_positif'),
            models.CheckConstraint(condition=models.Q(cumul_initial__gte=0), name='ca_initial_positif'),
        ]
