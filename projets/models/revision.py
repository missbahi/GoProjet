from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

# =====================================================================
# 1. ÉNUMÉRATIONS (Choices Django)
# =====================================================================

class StatutIndex(models.TextChoices):
    IND_DEF = "IND_DEF", _("Index définitif")
    IND_PRO = "IND_PRO", _("Index provisoire")
    IND_ND = "IND_ND", _("Index non disponible")

class MethodeArrondi(models.TextChoices):
    TRONCATURE = "TRONCATURE", _("Troncature (4 décimales)")
    ARRONDI = "ARRONDI", _("Arrondi mathématique (HALF_UP)")

class PolitiqueIndex(models.TextChoices):
    DEFINITIF_SEULEMENT = "DEFINITIF_SEULEMENT", _("Définitif seulement")
    PROVISOIRE_ET_REPORT_M2 = "PROVISOIRE_ET_REPORT_M2", _("Provisoire avec report M+2")

class TypeTerme(models.TextChoices):
    SIMPLE = "SIMPLE", _("Index simple")
    COMPOSITE = "COMPOSITE", _("Index composite (A*(1+B))")

# =====================================================================
# 2. INDEX ET VALEURS
# =====================================================================

class IndexReference(models.Model):
    """Référentiel des symboles d'index (ex: BAT6, TR5B, ING, etc.)."""
    symbole = models.CharField(max_length=20, unique=True)
    libelle = models.CharField(max_length=200, blank=True)
    famille = models.CharField(max_length=100, blank=True)
    
    class Meta:
        verbose_name = _("Index de référence")
        verbose_name_plural = _("Index de référence")
        
    def __str__(self):
        return self.symbole

class IndexValeur(models.Model):
    """Valeur mensuelle d'un index (définitif ou provisoire)."""
    index = models.ForeignKey(IndexReference, on_delete=models.CASCADE, related_name="valeurs")
    mois = models.DateField(_("Mois de l'index"), help_text=_("Toujours le 1er jour du mois (AAAA-MM-01)"))
    valeur = models.DecimalField(
        _("Valeur"), max_digits=15, decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
    )
    statut = models.CharField(max_length=10, choices=StatutIndex.choices, default=StatutIndex.IND_DEF)
    source = models.CharField(_("Source du bulletin"), max_length=255, blank=True)
    date_publication = models.DateField(_("Date de publication"), null=True, blank=True)
    date_saisie = models.DateTimeField(_("Date de saisie"), auto_now=True)
    
    class Meta:
        unique_together = ('index', 'mois')
        verbose_name = _("Valeur d'index")
        verbose_name_plural = _("Valeurs d'index")
        
    def __str__(self):
        return f"{self.index.symbole} - {self.mois.strftime('%Y-%m')} = {self.valeur}"

    def clean(self):
        super().clean()
        if self.mois and self.mois.day != 1:
            self.mois = self.mois.replace(day=1)

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    @classmethod
    def publier(cls, index, mois, valeur, statut=StatutIndex.IND_PRO, **kwargs):
        """Publie une valeur et remplace le provisoire lorsque le définitif arrive."""
        mois_normalise = mois.replace(day=1)
        publication, cree = cls.objects.get_or_create(
            index=index, mois=mois_normalise,
            defaults={"valeur": valeur, "statut": statut, **kwargs},
        )
        if not cree:
            publication.valeur = valeur
            publication.statut = statut
            for champ, nouvelle_valeur in kwargs.items():
                setattr(publication, champ, nouvelle_valeur)
            publication.save(update_fields=[
                "valeur", "statut", *kwargs.keys(), "date_saisie",
            ])
        return publication, cree


class IndexRevisionProjet(models.Model):
    """Index ajouté explicitement au tableur d'un projet."""

    projet = models.ForeignKey(
        "Projet",
        on_delete=models.CASCADE,
        related_name="indexes_revision",
    )
    index = models.ForeignKey(
        IndexReference,
        on_delete=models.CASCADE,
        related_name="projets_revision",
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("projet", "index"),
                name="unique_index_revision_projet",
            ),
        ]

# =====================================================================
# 3. FORMULES DE RÉVISION
# =====================================================================

class FormuleRevision(models.Model):
    """Formule de révision rattachée à un projet ou un lot."""
    projet = models.ForeignKey('Projet', on_delete=models.CASCADE, related_name="formules_revision")
    code = models.CharField(max_length=50)
    libelle = models.CharField(max_length=200, blank=True)
    k = models.DecimalField(
        _("Partie fixe (k)"),
        max_digits=5,
        decimal_places=4,
        default=Decimal("0.15"),
        validators=[
            MinValueValidator(Decimal("0.15")),
            MaxValueValidator(Decimal("1")),
        ],
    )
    est_index_global = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('projet', 'code')
        verbose_name = _("Formule de révision")
        verbose_name_plural = _("Formules de révision")
        
    def __str__(self):
        return f"{self.projet.numero} - {self.code}"

    @property
    def formule_latex(self):
        from projets.services.revision_presets import formule_latex

        termes = []
        for terme in self.termes.all():
            termes.append((
                terme.type_terme,
                terme.coefficient,
                terme.index_simple.symbole if terme.index_simple_id else None,
                (
                    terme.index_composite_a.symbole
                    if terme.index_composite_a_id else None
                ),
                (
                    terme.index_composite_b.symbole
                    if terme.index_composite_b_id else None
                ),
            ))
        return formule_latex(self.k, termes)

    def clean(self):
        super().clean()
        if self.pk:
            self.valider()

    @property
    def mois_base(self):
        return self.projet.mois_base_revision

    def save(self, *args, **kwargs):
        self.clean()
        return super().save(*args, **kwargs)

    def valider(self):
        """Applique les mêmes contrôles mathématiques que revision_prix.py."""
        termes = list(self.termes.all())
        erreurs = {}
        avertissements = []

        if not self.projet.mois_base_revision:
            erreurs["__all__"] = _("Le mois de base du projet doit être renseigné.")

        if self.k < Decimal("0.15"):
            erreurs["k"] = _("La partie fixe k doit être supérieure ou égale à 0,15.")

        total = self.k + sum((terme.coefficient for terme in termes), Decimal("0"))
        if total.quantize(Decimal("0.0001")) != Decimal("1.0000"):
            erreurs["__all__"] = _(
                "La somme de k et des coefficients doit être égale à 1."
            )

        if self.est_index_global:
            if len(termes) != 1 or termes[0].type_terme != TypeTerme.SIMPLE:
                erreurs["est_index_global"] = _(
                    "Une formule à index global exige un seul terme simple."
                )

        montant_marche = (
            self.projet.montant_soumission
            or self.projet.montant
            or Decimal("0")
        )
        nombre_index = len({
            index_id
            for terme in termes
            for index_id in terme.index_ids
            if index_id is not None
        })
        if montant_marche and montant_marche <= Decimal("1000000") and nombre_index > 5:
            avertissements.append(
                _("Marché inférieur ou égal à 1 M DH : plus de 5 index sont utilisés.")
            )

        if erreurs:
            raise ValidationError(erreurs)
        return avertissements

class TermeFormule(models.Model):
    """Terme d'une formule de révision (simple ou composite)."""
    formule = models.ForeignKey(FormuleRevision, on_delete=models.CASCADE, related_name="termes")
    type_terme = models.CharField(max_length=10, choices=TypeTerme.choices, default=TypeTerme.SIMPLE)
    coefficient = models.DecimalField(
        max_digits=5,
        decimal_places=4,
        validators=[
            MinValueValidator(Decimal("0.0001")),
            MaxValueValidator(Decimal("1")),
        ],
    )
    
    # Pour les termes simples
    index_simple = models.ForeignKey(IndexReference, on_delete=models.PROTECT, null=True, blank=True, related_name="termes_simples")
    
    # Pour les termes composites (A * (1 + B))
    index_composite_a = models.ForeignKey(IndexReference, on_delete=models.PROTECT, null=True, blank=True, related_name="termes_composites_a")
    index_composite_b = models.ForeignKey(IndexReference, on_delete=models.PROTECT, null=True, blank=True, related_name="termes_composites_b")

    class Meta:
        verbose_name = _("Terme de formule")
        verbose_name_plural = _("Termes de formule")
        constraints = [
            models.UniqueConstraint(
                fields=("formule", "index_simple"),
                condition=models.Q(type_terme=TypeTerme.SIMPLE),
                name="unique_index_simple_par_formule",
            ),
            models.UniqueConstraint(
                fields=("formule", "index_composite_a", "index_composite_b"),
                condition=models.Q(type_terme=TypeTerme.COMPOSITE),
                name="unique_terme_composite_par_formule",
            ),
        ]

    @property
    def index_ids(self):
        if self.type_terme == TypeTerme.COMPOSITE:
            return (self.index_composite_a_id, self.index_composite_b_id)
        return (self.index_simple_id,)

    def clean(self):
        super().clean()
        if self.type_terme == TypeTerme.SIMPLE:
            if not self.index_simple_id:
                raise ValidationError({"index_simple": _("Un index simple est requis.")})
            if self.index_composite_a_id or self.index_composite_b_id:
                raise ValidationError(
                    _("Un terme simple ne peut pas comporter d'index composite.")
                )
        elif self.type_terme == TypeTerme.COMPOSITE:
            if not self.index_composite_a_id or not self.index_composite_b_id:
                raise ValidationError({
                    "index_composite_a": _("Les index A et B sont requis."),
                    "index_composite_b": _("Les index A et B sont requis."),
                })
            if self.index_composite_a_id == self.index_composite_b_id:
                raise ValidationError(
                    {"index_composite_b": _("Les index A et B doivent être différents.")}
                )
            if self.index_simple_id:
                raise ValidationError(
                    _("Un terme composite ne peut pas comporter d'index simple.")
                )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

class IndicateurRevisionProjet(models.Model):
    """Dernier verdict enregistré sur la préparation de la révision."""

    class Statut(models.TextChoices):
        A_CONTROLER = "A_CONTROLER", _("À contrôler")
        PRET = "PRET", _("Prêt")
        INCOMPLET = "INCOMPLET", _("Incomplet")

    projet = models.OneToOneField(
        "Projet",
        on_delete=models.CASCADE,
        related_name="indicateur_revision",
    )
    statut = models.CharField(
        max_length=15,
        choices=Statut.choices,
        default=Statut.A_CONTROLER,
    )
    details = models.JSONField(default=dict, blank=True)
    dernier_controle = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Indicateur de révision")
        verbose_name_plural = _("Indicateurs de révision")

    def __str__(self):
        return f"{self.projet.numero} - {self.get_statut_display()}"