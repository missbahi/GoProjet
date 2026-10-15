from decimal import Decimal
from datetime import date
import hashlib
import os

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _


from .projet import Projet
from .ressources import EtatMateriel

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

class CategorieCharge(models.Model):
    code = models.SlugField(max_length=50, unique=True, verbose_name=_('Code'))
    nom = models.CharField(max_length=100, verbose_name=_('Nom'))
    actif = models.BooleanField(default=True, verbose_name=_('Active'))
    ordre = models.PositiveIntegerField(default=0, verbose_name=_('Ordre'))

    class Meta:
        ordering = ['ordre', 'nom', 'id']
        verbose_name = _('Catégorie de charge')
        verbose_name_plural = _('Catégories de charges')

    def __str__(self):
        return self.nom

class DepenseRapportJournalier(models.Model):
    rapport = models.ForeignKey(RapportJournalier, on_delete=models.CASCADE, related_name='depenses',
        verbose_name=_('Rapport journalier'))
    categorie = models.CharField(max_length=30)
    categorie_charge = models.ForeignKey(CategorieCharge, on_delete=models.PROTECT, null=True, blank=True,
        related_name='depenses_rapports_journaliers', verbose_name=_('Catégorie de charge'))
    designation = models.CharField(max_length=200, verbose_name=_('Désignation'))
    quantite = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('1.000'))
    unite = models.CharField(max_length=30, blank=True, verbose_name=_('Unité'))
    
    # Ancienne colonne "montant" réutilisée telle quelle pour ne pas casser les données existantes
    prix_unitaire = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'),
        db_column='montant', verbose_name=_('Prix unitaire'))
    observations = models.TextField(blank=True, verbose_name=_('Observations'))
    montant = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'),
        db_column='montant_total', editable=False, verbose_name=_('Montant'))

    def save(self, *args, **kwargs):
        self.montant = (self.quantite or Decimal('0.000')) * (self.prix_unitaire or Decimal('0.00'))
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['categorie', 'id']

    def __str__(self):
        return f'{self.get_categorie_display()} - {self.designation}'

class StockRapportJournalier(models.Model):
    rapport = models.ForeignKey(RapportJournalier, on_delete=models.CASCADE, related_name='stocks',
        verbose_name=_('Rapport journalier'))
    designation = models.CharField(max_length=200, verbose_name=_('Désignation'))
    unite = models.CharField(max_length=30, blank=True, verbose_name=_('Unité'))
    quantite_entree = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    quantite_sortie = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))
    stock_restant = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))

    class Meta:
        ordering = ['designation', 'id']

    def __str__(self):
        return self.designation

class ReleveMateriel(models.Model):
    """Relevé journalier d'utilisation d'un matériel sur un chantier.
    """

    rapport = models.ForeignKey(
        RapportJournalier,
        on_delete=models.CASCADE,
        related_name='releves_materiel',
        verbose_name=_("Rapport journalier"),
    )
    materiel = models.ForeignKey(
        'projets.Materiel',
        on_delete=models.PROTECT,
        related_name='releves',
        verbose_name=_("Matériel"),
    )
    atelier = models.ForeignKey(
        'projets.Atelier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='releves',
        verbose_name=_("Atelier"),
    )
    etat = models.CharField(
        max_length=20,
        choices=EtatMateriel.choices,
        verbose_name=_("État"),
    )
    localisation = models.CharField(
        max_length=150,
        blank=True,
        verbose_name=_("Localisation"),
    )
    heures = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=Decimal('0.00'),
        verbose_name=_("Heures"),
    )
    commentaire = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Commentaire"),
    )

    class Meta:
        ordering = ['materiel__designation', 'etat', 'id']
        verbose_name = _("Relevé matériel")
        verbose_name_plural = _("Relevés matériel")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(heures__gte=0) & models.Q(heures__lte=24),
                name='releve_materiel_heures_valides',
            ),
        ]

    def __str__(self):
        return f"{self.materiel} - {self.get_etat_display()} ({self.heures}h)"

# situation mensuelle
def situation_mensuelle_document_upload_path(instance, filename):
    situation = instance.situation
    return f'situations_mensuelles/projet_{situation.projet_id}/{situation.annee}-{situation.mois:02d}/{filename}'

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
    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', _('Brouillon')
        VALIDEE = 'VALIDEE', _('Validée')

    statut = models.CharField(
        _("Statut"), max_length=20,
        choices=Statut.choices, default=Statut.BROUILLON,
    )
    date_validation = models.DateTimeField(
        _("Date de validation"), null=True, blank=True,
    )
    validee_par = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='situations_validees', verbose_name=_("Validée par"),
    )
    date_devalidation = models.DateTimeField(
        _("Date de dévalidation"), null=True, blank=True,
    )
    devalidee_par = models.ForeignKey(
        'auth.User', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='situations_devalidees', verbose_name=_("Dévalidée par"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-annee', '-mois', '-id']
        constraints = [
            models.UniqueConstraint(fields=['projet', 'annee', 'mois'], name='unique_situation_mensuelle_projet_periode')
        ]

    def clean(self):
        super().clean()
        if self.mois is None:
            return
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

    @property
    def variation_stock(self):
        """Σ des variations de stock (E − S) sur toutes les lignes."""
        total = Decimal('0.00')
        for ligne in self.stocks.all():
            total += ligne.variation_stock
        return total

    @property
    def resultat(self):
        """Résultat = CA − Dépenses + Variation de stock."""
        return (self.chiffre_affaires or Decimal('0.00')) \
             - (self.total_depenses or Decimal('0.00')) \
             + self.variation_stock

    @property
    def pct_resultat(self):
        """Résultat / CA × 100 (None si CA nul)."""
        ca = self.chiffre_affaires or Decimal('0.00')
        if ca == 0:
            return None
        return (self.resultat / ca) * Decimal('100')
    
    @property
    def est_brouillon(self):
        return self.statut == self.Statut.BROUILLON

    @property
    def est_validee(self):
        return self.statut == self.Statut.VALIDEE

class RecetteSituationMensuelle(models.Model):
    class Rubrique(models.TextChoices):
        TRAVAUX_REALISES = 'TRAVAUX_REALISES', _('Travaux réalisés')
        REVISION_PRIX = 'REVISION_PRIX', _('Révision des prix')
        REFACTURATION_EXTERNE = 'REFACTURATION_EXTERNE', _('Refacturation externe')

    situation = models.ForeignKey(
        SituationMensuelle, on_delete=models.CASCADE, related_name='recettes',
        verbose_name=_('Situation mensuelle'),
    )
    rubrique = models.CharField(max_length=30, choices=Rubrique.choices)
    montant = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))

    class Meta:
        ordering = ['rubrique', 'id']
        constraints = [
            models.UniqueConstraint(
                fields=['situation', 'rubrique'],
                name='unique_recette_situation_rubrique',
            ),
        ]

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
    categorie = models.CharField(max_length=30)
    categorie_charge = models.ForeignKey(
        CategorieCharge, on_delete=models.PROTECT, null=True, blank=True,
        related_name='depenses_situations_mensuelles', verbose_name=_('Catégorie de charge')
    )
    designation = models.CharField(max_length=200, verbose_name=_('Désignation'))
    montant_base = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), db_column='montant')
    cession_entrante = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    cession_sortante = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    montant = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'), db_column='montant_total', editable=False)

    class Meta:
        ordering = ['categorie', 'id']

    def save(self, *args, **kwargs):
        self.montant = sum(
            Decimal(str(valeur or '0.00'))
            for valeur in (self.montant_base, self.cession_entrante, self.cession_sortante)
        )
        super().save(*args, **kwargs)

class StockSituationMensuelle(models.Model):
    """
    Ligne de stock d'un article pour une situation mensuelle.

    Calculs :
        SI  (montant)   = qte_initiale × pu_initial
        E   (montant)   = qte_entree   × pu_entree
        S   (montant)   = qte_sortie   × pu_sortie
        QF  (quantité)  = qte_initiale + qte_entree − qte_sortie
        SF  (montant)   = SI + E − S
        PUf (unitaire)  = SF / QF   (si QF > 0)
        ΔStock          = E − S  (variation intégrée au résultat)
    """

    situation = models.ForeignKey(
        SituationMensuelle, on_delete=models.CASCADE, related_name='stocks',
        verbose_name=_('Situation mensuelle'),
    )
    designation = models.CharField(_("Désignation"), max_length=200)
    unite = models.CharField(_("Unité"), max_length=30, blank=True)

    # Stock initial
    qte_initiale = models.DecimalField(
        _("Qté initiale"), max_digits=15, decimal_places=3, default=Decimal('0.000'),
    )
    pu_initial = models.DecimalField(
        _("PU initial (DH)"), max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )

    # Entrées
    qte_entree = models.DecimalField(
        _("Qté entrée"), max_digits=15, decimal_places=3, default=Decimal('0.000'),
    )
    pu_entree = models.DecimalField(
        _("PU entrée (DH)"), max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )

    # Sorties
    qte_sortie = models.DecimalField(
        _("Qté sortie"), max_digits=15, decimal_places=3, default=Decimal('0.000'),
    )
    pu_sortie = models.DecimalField(
        _("PU sortie (DH)"), max_digits=15, decimal_places=2, default=Decimal('0.00'),
    )

    class Meta:
        ordering = ['designation', 'id']
        verbose_name = _("Stock (situation mensuelle)")
        verbose_name_plural = _("Stocks (situation mensuelle)")

    # ---------- Calculs ----------

    @property
    def montant_initial(self):
        return (self.qte_initiale or Decimal('0')) * (self.pu_initial or Decimal('0'))

    @property
    def montant_entree(self):
        return (self.qte_entree or Decimal('0')) * (self.pu_entree or Decimal('0'))

    @property
    def montant_sortie(self):
        return (self.qte_sortie or Decimal('0')) * (self.pu_sortie or Decimal('0'))

    @property
    def qte_finale(self):
        return (self.qte_initiale or Decimal('0')) \
             + (self.qte_entree or Decimal('0')) \
             - (self.qte_sortie or Decimal('0'))

    @property
    def montant_final(self):
        return self.montant_initial + self.montant_entree - self.montant_sortie

    @property
    def pu_final(self):
        if self.qte_finale and self.qte_finale > 0:
            return self.montant_final / self.qte_finale
        return None

    @property
    def variation_stock(self):
        """ΔStock = E − S (les entrées augmentent le stock, les sorties le diminuent)."""
        return self.montant_entree - self.montant_sortie

    def __str__(self):
        return self.designation

# Affectation d'une ressource à un projet
class RessourceAffectee(models.Model):
    """
    Affectation d'une ressource du référentiel (BDD) à un projet.
    """

    projet = models.ForeignKey(
        Projet,
        on_delete=models.CASCADE,
        related_name='ressources_affectees',
        verbose_name=_("Projet"),
    )
    atelier = models.ForeignKey(
        'Atelier',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ressources_affectees',
        verbose_name=_("Atelier (optionnel)"),
        help_text=_("Regroupement optionnel (utile pour le matériel / le personnel)."),
    )
    categorie_charge = models.ForeignKey(
        CategorieCharge,
        on_delete=models.PROTECT,
        related_name='ressources_affectees',
        verbose_name=_("Type de ressource"),
    )

    objet_id = models.PositiveIntegerField(_("ID de la ressource source"))

    # Snapshot dénormalisé (évite les JOIN et conserve l'historique)
    designation = models.CharField(_("Désignation"), max_length=255)
    unite = models.CharField(_("Unité"), max_length=20, blank=True)
    tarif = models.DecimalField(
        _("Tarif négocié (DH)"),
        max_digits=12, decimal_places=2, default=Decimal('0.00'),
    )

    # Période
    date_debut = models.DateField(_("Date de début"))
    date_fin = models.DateField(_("Date de fin"), null=True, blank=True)

    commentaire = models.CharField(_("Commentaire"), max_length=255, blank=True)
    actif = models.BooleanField(_("Actif"), default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Ressource affectée")
        verbose_name_plural = _("Ressources affectées")
        ordering = ['categorie_charge__ordre', '-date_debut', 'designation']
        indexes = [
            models.Index(fields=['projet', 'categorie_charge']),
            models.Index(fields=['projet', 'date_debut', 'date_fin']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['projet', 'categorie_charge', 'objet_id', 'date_debut'],
                name='unique_ressource_projet_objet_date',
            ),
        ]

    def __str__(self):
        return f"{self.designation} → {self.projet.nom}"

    # ---------- Propriétés utilitaires ----------

    @property
    def type_ressource_code(self):
        """Raccourci vers le code de la catégorie."""
        return self.categorie_charge.code if self.categorie_charge_id else ''

    @property
    def en_cours(self):
        return self.date_fin is None

    @property
    def est_active_a(self):
        """Retourne une closure qui teste si l'affectation est active à une date."""
        def _check(date_ref):
            if date_ref < self.date_debut:
                return False
            if self.date_fin and date_ref > self.date_fin:
                return False
            return True
        return _check

    # ---------- Validation ----------

    def clean(self):
        super().clean()
        errors = {}

        if self.date_fin and self.date_debut and self.date_fin < self.date_debut:
            errors['date_fin'] = _("La date de fin ne peut précéder la date de début.")

        if self.projet_id and self.categorie_charge_id and self.objet_id and self.date_debut:
            conflit = self._trouver_conflit()
            if conflit:
                errors['objet_id'] = _(
                    "Cette ressource est déjà affectée à ce projet sur une période "
                    "qui chevauche (%(debut)s → %(fin)s)."
                ) % {
                    'debut': conflit.date_debut.strftime('%d/%m/%Y'),
                    'fin': conflit.date_fin.strftime('%d/%m/%Y') if conflit.date_fin else _('en cours'),
                }

        if errors:
            raise ValidationError(errors)

    def _trouver_conflit(self):
        """Cherche une affectation qui chevauche [date_debut, date_fin] sur le même objet."""
        qs = RessourceAffectee.objects.filter(
            projet_id=self.projet_id,
            categorie_charge_id=self.categorie_charge_id,
            objet_id=self.objet_id,
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)

        # Condition 1 : l'autre finit après notre début (ou est en cours)
        qs = qs.filter(models.Q(date_fin__isnull=True) | models.Q(date_fin__gte=self.date_debut))

        # Condition 2 : l'autre commence avant notre fin
        if self.date_fin is not None:
            qs = qs.filter(date_debut__lte=self.date_fin)

        return qs.first()