from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _

from .projet import Projet
from .suivi_projet import CategorieCharge


class RessourceAffectee(models.Model):
    """
    Affectation d'une ressource du référentiel (BDD) à un projet.

    Types supportés (via CategorieCharge.code) :
        PERSONNEL, MATERIEL, LOCATION, SOUS_TRAITANCE,
        TRANSPORT, CONSOMMABLE, FOURNITURE

    Le champ `objet_id` pointe vers l'ID dans la table source correspondante.
    Le champ `designation` est un snapshot dénormalisé pour l'affichage.
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

    # Lien "faible" vers la table source (Personnel, Materiel, etc.)
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