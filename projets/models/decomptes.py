from decimal import Decimal
import os
from django.db import models, transaction
from django.db.models import Sum
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings

# ------------------------ Attachement ------------------------
class Attachement(models.Model):
    STATUT_ATTACHEMENT = [
        ('BROUILLON', 'Brouillon'),
        ('SIGNE', 'Signé'),
        ('TRANSMIS', 'Transmis'),
        ('VALIDE', 'Validé'),
        ('REFUSE', 'Refusé'),
        ('MODIFIE', 'Modifié'),
    ]

    projet = models.ForeignKey('Projet', on_delete=models.CASCADE, related_name='attachements')
    sequence = models.PositiveIntegerField(verbose_name="Ordre de l'attachement")
    precedent = models.ForeignKey(
        'self',
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True,
        related_name='suivants',
        verbose_name="Attachement précédent",
    )
    numero = models.CharField(max_length=20, verbose_name="Numéro d'attachement")
    date_etablissement = models.DateField(verbose_name="Date d'établissement")
    date_debut_periode = models.DateField(verbose_name="Date début période")
    date_fin_periode = models.DateField(verbose_name="Date fin période")
    statut = models.CharField(max_length=15, choices=STATUT_ATTACHEMENT, default='BROUILLON')
    observations = models.TextField(blank=True, verbose_name="Observations")
    montant_ht = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Montant HT", default=Decimal('0.00'))

    fichier = models.FileField(upload_to='attachements/%Y/%m/', null=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True, verbose_name="Nom de fichier original")
    
    date_creation = models.DateTimeField(auto_now_add=True)
    modifie_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='attachements_modifies', verbose_name="Modifié par")

    class Meta: 
        verbose_name = "Attachement"
        verbose_name_plural = "Attachements"
        ordering = ['projet', 'sequence']
        constraints = [
            models.UniqueConstraint(fields=['projet', 'sequence'], name='unique_attachement_sequence_projet'),
        ]

    def marquer_modification(self, user):
        if user is not None:
            self.modifie_par = user
        return self

    def initialiser_processus_validation(self, demandeur):
        if self.projet.dossier_id and self.projet.dossier.activite == 'TRAVAUX':
            return
        types_validation = [
            ('TECHNIQUE', 1, True, User.objects.filter(is_staff=True).first()),
            ('ADMINISTRATIVE', 2, True, User.objects.filter(is_staff=True).first()),
            ('FINANCIERE', 3, True, User.objects.filter(is_superuser=True).first()),
            ('FINAL', 4, True, User.objects.filter(is_superuser=True).first()),
        ]
        
        for type_val, ordre, obligatoire, validateur_par_defaut in types_validation:
            ProcessValidation.objects.create(
                attachement=self,
                type_validation=type_val,
                ordre_validation=ordre,
                est_obligatoire=obligatoire,
                demandeur_validation=demandeur,
                validateur=validateur_par_defaut,
                date_limite=timezone.now() + timezone.timedelta(days=7)
            )
    @property
    def get_file_name(self):
        if self.original_filename:
            return self.original_filename
        elif self.fichier:
            return os.path.basename(self.fichier.name)
        return ""
    @property
    def annee(self):
        return self.date_debut_periode.year if self.date_debut_periode else None
    
    @property
    def peut_etre_reouvert(self):
        return self.statut == 'VALIDE'
    
    def peut_etre_reouvert_par(self, user):
        if not self.peut_etre_reouvert:
            return False
        return user.is_superuser or user.is_staff or user.has_perm('projets.reopen_attachment')
    
    def reouvrir(self, user):
        if not self.peut_etre_reouvert_par(user):
            raise PermissionError("Vous n'avez pas la permission de réouvrir cet attachement")
        
        self.marquer_modification(user)
        self.statut = 'BROUILLON'
        self.save()
        
        self.validations.update(
            statut_validation='EN_ATTENTE',
            validateur=None,
            date_validation=None,
            commentaires='',
            motifs_rejet=''
        )
        self.statut = 'BROUILLON'
        self.save(update_fields=['statut', 'modifie_par'])
    
    def transmettre(self, user):
        if self.statut != 'SIGNE':
            raise ValueError("Seuls les attachements signés peuvent être transmis.")
        
        self.marquer_modification(user)
        self.statut = 'TRANSMIS'
        self.save(update_fields=['statut', 'modifie_par'])
        
        self.initialiser_processus_validation(demandeur=user)
    @property
    def total_montant_ht(self):
        return sum(ligne.montant_ligne_realise for ligne in self.lignes_attachement.all())

    @classmethod
    def get_latest_attachement(cls, projet):
        return cls.objects.filter(projet=projet).order_by('-sequence').first()

    def get_previous_attachement(self):
        if self.pk:
            return self.precedent
        if self.projet_id:
            return type(self).get_latest_attachement(self.projet)
        return None

    def _date_debut_attendue(self, precedent):
        if precedent:
            return precedent.date_fin_periode + timedelta(days=1)

        osc = self.projet.ordres_service.filter(
            type_os__code='OSC',
            statut='NOTIFIE',
            date_effet__isnull=False,
        ).order_by('ordre_sequence').first()
        return osc.date_effet if osc else None

    def verifier_continuite_periode(self):
        precedent = self.get_previous_attachement()
        date_attendue = self._date_debut_attendue(precedent) if self.projet_id else None
        if not date_attendue:
            raise ValidationError({
                'date_debut_periode': "Un OS de commencement notifié avec une date d'effet est requis.",
            })
        if self.date_debut_periode != date_attendue:
            raise ValidationError({
                'date_debut_periode': (
                    "La date de début doit correspondre au lendemain de l'attachement précédent "
                    "ou à la date d'effet de l'OS de commencement."
                ),
            })

    def verifier_fin_periode_hors_arret(self, date_fin):
        if not self.projet_id or not date_fin:
            return
        evenements = self.projet.ordres_service.filter(
            type_os__code__in=['OSA', 'OSR'], statut='NOTIFIE',
            date_effet__isnull=False,
        ).select_related('type_os').order_by('date_effet', 'ordre_sequence', 'pk')
        periodes = []
        debut_arret = None
        for evenement in evenements:
            if evenement.type_os.code == 'OSA' and debut_arret is None:
                debut_arret = evenement.date_effet
            elif evenement.type_os.code == 'OSR' and debut_arret is not None:
                periodes.append((debut_arret, evenement.date_effet))
                debut_arret = None
        if debut_arret is not None:
            periodes.append((debut_arret, None))
        for arret, reprise in periodes:
            if arret <= date_fin and (reprise is None or date_fin < reprise):
                veille = arret - timedelta(days=1)
                choix = f"le {veille:%d/%m/%Y} (veille de l'arrêt)"
                if reprise:
                    choix += f" ou le {reprise:%d/%m/%Y} (reprise)"
                else:
                    choix += " ; aucun OS de reprise notifié ne permet encore de proposer une date de reprise"
                raise ValidationError({
                    'date_fin_periode': (
                        f"La date de fin se situe dans une période d'arrêt du projet "
                        f"à compter du {arret:%d/%m/%Y}. Choisissez {choix}."
                    ),
                })

    def clean(self):
        super().clean()
        errors = {}
        precedent = self.get_previous_attachement()
        ancien = type(self).objects.get(pk=self.pk) if self.pk else None
        if self.statut == 'TRANSMIS' and (not ancien or ancien.statut != 'TRANSMIS'):
            try:
                self.verifier_fin_periode_hors_arret(self.date_fin_periode)
            except ValidationError as error:
                errors.update(error.message_dict)

        if self.date_debut_periode and self.date_fin_periode:
            if self.date_fin_periode < self.date_debut_periode:
                errors['date_fin_periode'] = "La date de fin ne peut précéder la date de début."

            if not ancien or (self.statut == 'TRANSMIS' and ancien.statut != 'TRANSMIS'):
                try:
                    self.verifier_continuite_periode()
                except ValidationError as error:
                    errors.update(error.message_dict)

        if not self.pk and precedent and precedent.statut not in {'SIGNE', 'VALIDE'}:
            errors[NON_FIELD_ERRORS] = (
                "L'attachement précédent doit être signé ou validé avant de créer le suivant."
            )

        if self.pk and self.suivants.exists():
            if (
                self.date_debut_periode != ancien.date_debut_periode
                or self.date_fin_periode != ancien.date_fin_periode
            ):
                errors['date_debut_periode'] = (
                    "Les dates ne peuvent pas être modifiées lorsqu'un attachement suivant existe."
                )
        if errors:
            raise ValidationError(errors)
    
    @property
    def montant_ht_attachement_precedent(self):
        precedent = self.get_previous_attachement()
        return precedent.total_montant_ht if precedent else Decimal('0.00')
    
    @property
    def montant_situation(self):
        return self.total_montant_ht - self.montant_ht_attachement_precedent

    def recalculer_montant_ht(self):
        self.montant_ht = self.montant_situation
        if self.pk:
            type(self).objects.filter(pk=self.pk).update(montant_ht=self.montant_ht)
        return self.montant_ht
        
    def __str__(self):
        return f"Attachement {self.numero} - {self.projet.nom}"

    def save(self, *args, **kwargs):
        if self._state.adding:
            from projets.models.projet import Projet

            with transaction.atomic():
                Projet.objects.select_for_update().get(pk=self.projet_id)
                precedent = type(self).get_latest_attachement(self.projet)
                date_debut_attendue = self._date_debut_attendue(precedent)
                if precedent and precedent.statut not in {'SIGNE', 'VALIDE'}:
                    raise ValidationError(
                        "L'attachement précédent doit être signé ou validé avant de créer le suivant."
                    )
                if not date_debut_attendue:
                    raise ValidationError(
                        "Un OS de commencement notifié avec une date d'effet est requis."
                    )
                if self.date_debut_periode != date_debut_attendue:
                    raise ValidationError(
                        {'date_debut_periode': "La date ne respecte pas la continuité des attachements."}
                    )
                if self.date_fin_periode < self.date_debut_periode:
                    raise ValidationError(
                        {'date_fin_periode': "La date de fin ne peut précéder la date de début."}
                    )
                self.precedent = precedent
                self.sequence = precedent.sequence + 1 if precedent else 1
                self.numero = f"DP{self.sequence:02d}"
                if self.statut == 'TRANSMIS':
                    self.verifier_fin_periode_hors_arret(self.date_fin_periode)
                return super().save(*args, **kwargs)
        elif self.pk:
            ancien = type(self).objects.get(pk=self.pk)
            statut_enregistre = kwargs.get('update_fields')
            if (
                self.statut == 'TRANSMIS'
                and ancien.statut != 'TRANSMIS'
                and (statut_enregistre is None or 'statut' in statut_enregistre)
            ):
                self.verifier_continuite_periode()
                self.verifier_fin_periode_hors_arret(self.date_fin_periode)
            if (
                self.projet_id != ancien.projet_id
                or self.sequence != ancien.sequence
                or self.precedent_id != ancien.precedent_id
                or self.numero != ancien.numero
            ):
                raise ValidationError(
                    "Le projet, le numéro et le rang de l'attachement ne peuvent pas être modifiés."
                )

            dates_modifiees = (
                self.date_debut_periode != ancien.date_debut_periode
                or self.date_fin_periode != ancien.date_fin_periode
            )
            if dates_modifiees and self.suivants.exists():
                raise ValidationError(
                    "Les dates ne peuvent pas être modifiées lorsqu'un attachement suivant existe."
                )
            if dates_modifiees:
                if self.date_fin_periode < self.date_debut_periode:
                    raise ValidationError(
                        {'date_fin_periode': "La date de fin ne peut précéder la date de début."}
                    )
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.suivants.exists():
            raise ValidationError("Un attachement ayant un suivant ne peut pas être supprimé.")
        return super().delete(*args, **kwargs)
    
class CorrectionPeriodesAttachement(models.Model):
    projet = models.ForeignKey('Projet', on_delete=models.CASCADE, related_name='corrections_periodes_attachements')
    auteur = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    date_correction = models.DateTimeField(auto_now_add=True)
    motif = models.TextField()
    modifications = models.JSONField()

    class Meta:
        ordering = ['-date_correction', '-pk']
        verbose_name = "Correction des périodes d'attachement"
        verbose_name_plural = "Corrections des périodes d'attachement"


# ------------------------ Ligne Attachement ------------------------
class LigneAttachement(models.Model):
    attachement = models.ForeignKey('Attachement', on_delete=models.CASCADE, related_name='lignes_attachement')
    ligne_lot = models.ForeignKey('LigneBordereau', on_delete=models.CASCADE, related_name='lignes_attachement')
    numero = models.CharField(_("N°"), max_length=20, null=True, blank=True)
    designation = models.TextField(_("Désignation"))
    unite = models.CharField(_("Unité"), max_length=10, null=True, blank=True)
    quantite_initiale = models.DecimalField(_("Quantité"), max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2)
    quantite_realisee = models.DecimalField(max_digits=15, decimal_places=3, default=0, verbose_name="Quantité réalisée")
    quantite_cumulee = models.DecimalField(max_digits=15, decimal_places=3, default=0, verbose_name="Quantité cumulée")

    class Meta:
        verbose_name = "Ligne d'attachement"
        verbose_name_plural = "Lignes d'attachement"
        unique_together = ['attachement', 'ligne_lot']

    @property
    def montant_ligne_realise(self):
        return self.quantite_realisee * self.prix_unitaire

    @property
    def montant_cumule(self):
        return self.quantite_cumulee * self.prix_unitaire
        
    @property
    def is_title(self):
        return not self.numero or not self.unite or (self.quantite_initiale is None or self.quantite_initiale == 0)
    
    def save(self, *args, **kwargs):
        if self.pk and self.attachement.suivants.exists():
            ancien = type(self).objects.get(pk=self.pk)
            champs_proteges = (
                'ligne_lot_id',
                'numero',
                'designation',
                'unite',
                'quantite_initiale',
                'prix_unitaire',
                'quantite_realisee',
                'quantite_cumulee',
            )
            if any(
                getattr(self, champ) != getattr(ancien, champ)
                for champ in champs_proteges
            ):
                raise ValidationError(
                    "Les lignes ne peuvent pas être modifiées lorsqu'un attachement suivant existe."
                )
        elif self.attachement.suivants.exists():
            raise ValidationError(
                "Les lignes ne peuvent pas être modifiées lorsqu'un attachement suivant existe."
            )
        if self.quantite_realisee is None:
            self.quantite_realisee = 0
        if self.quantite_realisee < 0:
            raise ValidationError({"quantite_realisee": "Le cumul réalisé ne peut pas être négatif."})
        self.quantite_cumulee = self.quantite_realisee
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.attachement.suivants.exists():
            raise ValidationError(
                "Les lignes ne peuvent pas être supprimées lorsqu'un attachement suivant existe."
            )
        return super().delete(*args, **kwargs)

# ------------------------ Processus de validation ------------------------
class ProcessValidation(models.Model):
    STATUT_VALIDATION_CHOICES = [
        ('EN_ATTENTE', 'En attente de validation'),
        ('VALIDE', 'Validé'),
        ('REJETE', 'Rejeté'),
        ('CORRECTION', 'En cours de correction'),
    ]
    
    TYPE_VALIDATION_CHOICES = [
        ('TECHNIQUE', 'Validation technique'),
        ('ADMINISTRATIVE', 'Validation administrative'),
        ('FINANCIERE', 'Validation financière'),
        ('FINAL', 'Validation finale'),
    ]
    
    attachement = models.ForeignKey('Attachement', on_delete=models.CASCADE, related_name='validations', verbose_name="Attachement à valider")
    tache_associee = models.OneToOneField('Tache', on_delete=models.SET_NULL, null=True, blank=True, related_name='validation_associee',  verbose_name="Tâche associée")
    type_validation = models.CharField(max_length=20, choices=TYPE_VALIDATION_CHOICES, default='TECHNIQUE', verbose_name="Type de validation")
    statut_validation = models.CharField(max_length=15, choices=STATUT_VALIDATION_CHOICES, default='EN_ATTENTE', verbose_name="Statut de la validation")
    validateur = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validations_effectuees', verbose_name="Validateur")
    demandeur_validation = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='validations_demandees', verbose_name="Demandeur de validation")
    date_demande = models.DateTimeField(auto_now_add=True, verbose_name="Date de demande")
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    date_limite = models.DateTimeField(null=True, blank=True, verbose_name="Date limite de validation")
    commentaires = models.TextField(blank=True, null=True, verbose_name="Commentaires sur la validation")
    motifs_rejet = models.TextField(blank=True, null=True, verbose_name="Motifs de rejet le cas échéant")
    
    fichier = models.FileField(upload_to='validations_attachements/%Y/%m/',
                               null=True,
                               blank=True,
                               verbose_name="Fichier de validation",
                               db_column='fichier_validation',)
    
    ordre_validation = models.PositiveIntegerField(default=1, verbose_name="Ordre dans le processus de validation")
    est_obligatoire = models.BooleanField(default=True, verbose_name="Validation obligatoire")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    original_filename = models.CharField(max_length=255, blank=True, verbose_name="Nom de fichier original")
    @property
    def get_file_name(self):
        if self.original_filename:
            return self.original_filename
        elif self.fichier:
            return os.path.basename(self.fichier.name)
        return ""
    
    class Meta:
        verbose_name = "Processus de validation"
        verbose_name_plural = "Processus de validation"
        ordering = ['attachement', 'ordre_validation', 'type_validation']
        unique_together = ['attachement', 'type_validation']
        indexes = [
            models.Index(fields=['attachement', 'statut_validation']),
            models.Index(fields=['validateur', 'statut_validation']),
            models.Index(fields=['date_limite']),
        ]
    
    def __str__(self):
        return f"Validation {self.get_type_validation_display()} - {self.attachement.numero} ({self.get_statut_validation_display()})"

    def save(self, *args, **kwargs):
        if self.statut_validation == 'VALIDE' and not self.date_validation:
            self.date_validation = timezone.now()
        super().save(*args, **kwargs)
        self._update_statut_attachement()

    def _update_statut_attachement(self):
        attachement = self.attachement
        if attachement.projet.dossier_id and attachement.projet.dossier.activite == 'TRAVAUX':
            return
        validations_obligatoires = attachement.validations.filter(est_obligatoire=True)
        validations_validees = validations_obligatoires.filter(statut_validation='VALIDE')
        validations_rejetees = validations_obligatoires.filter(statut_validation='REJETE')
        validations_en_correction = validations_obligatoires.filter(statut_validation='CORRECTION')

        if validations_rejetees.exists():
            attachement.statut = 'REFUSE'
            attachement.modifie_par = self.demandeur_validation or self.validateur
            attachement.save(update_fields=['statut', 'modifie_par'])
            return

        if validations_en_correction.exists():
            attachement.statut = 'MODIFIE'
            attachement.modifie_par = self.demandeur_validation or self.validateur
            attachement.save(update_fields=['statut', 'modifie_par'])
            return

        if validations_obligatoires.count() and validations_obligatoires.count() == validations_validees.count():
            attachement.statut = 'VALIDE'
            attachement.modifie_par = self.validateur or self.demandeur_validation
            attachement.save(update_fields=['statut', 'modifie_par'])
            return

        if attachement.statut not in ['BROUILLON', 'SIGNE', 'TRANSMIS', 'VALIDE', 'REFUSE', 'MODIFIE']:
            attachement.statut = 'TRANSMIS'
            attachement.save(update_fields=['statut'])

    @property
    def est_en_retard(self):
        if self.date_limite and self.statut_validation == 'EN_ATTENTE':
            return timezone.now() > self.date_limite
        return False

    @property
    def jours_restants(self):
        if self.date_limite and self.statut_validation == 'EN_ATTENTE':
            delta = self.date_limite - timezone.now()
            return max(0, delta.days)
        return None
    
    def peut_etre_valide_par(self, user):
        if self.statut_validation != 'EN_ATTENTE':
            return False

        if user.is_superuser:
            return True

        if user.is_staff and self.type_validation in ['TECHNIQUE', 'ADMINISTRATIVE']:
            return True

        role = getattr(getattr(user, 'profile', None), 'role', None)
        if role in {'GERANT', 'CHEF_PROJET'}:
            return True

        if self.validateur and self.validateur == user:
            return True

        if user.has_perm('projets.valider_attachement'):
            return True

        return False
    
    @property
    def est_en_attente(self):
        return self.statut_validation == 'EN_ATTENTE'
    
    @property
    def est_validee(self):
        return self.statut_validation == 'VALIDE'
    
    def verifier_etapes_validation(self):
        toutes_valides = self.etapes.filter(est_validee=False).count() == 0
        return toutes_valides
            
    def valider(self, user, commentaires="", fichier=None):
        if not self.peut_etre_valide_par(user):
            raise PermissionError("Cet utilisateur ne peut pas valider cette étape")
        if not self.verifier_etapes_validation():
            return False
        
        self.statut_validation = 'VALIDE'
        self.validateur = user
        self.commentaires = commentaires
        if fichier:
            self.fichier = fichier
        self.save()
        self._update_statut_attachement()
        return True

    def rejeter(self, user, motifs, fichier=None):
        if not self.peut_etre_valide_par(user):
            raise PermissionError("Cet utilisateur ne peut pas rejeter cette étape")
        
        self.statut_validation = 'REJETE'
        self.validateur = user
        self.motifs_rejet = motifs
        if fichier:
            self.fichier = fichier
        self.save()
        self._update_statut_attachement()

    def demander_correction(self, user, commentaires):
        if not self.peut_etre_valide_par(user):
            raise PermissionError("Cet utilisateur ne peut pas demander une correction")
        
        self.statut_validation = 'CORRECTION'
        self.validateur = user
        self.commentaires = commentaires
        self.save()
        self._update_statut_attachement()

    @classmethod
    def get_validations_en_attente(cls, user=None):
        queryset = cls.objects.filter(statut_validation='EN_ATTENTE')
        if user:
            queryset = queryset.filter(validateur=user)
        return queryset

    @classmethod
    def get_prochain_ordre_validation(cls, attachement):
        last_validation = cls.objects.filter(attachement=attachement).order_by('-ordre_validation').first()
        return (last_validation.ordre_validation + 1) if last_validation else 1

    def initier_etapes_techniques_par_defaut(self):
        etapes_standardes = [
            ('Validation du levé topographique', 1),
            ('Vérification des plans d\'attachement', 2),
            ('Agrément des matériaux par le laboratoire', 3),
            ('Contrôle des travaux par le laboratoire', 4),
            ('Vérification du métré sur site', 5),
            ('Approbation du rapport technique', 6),
        ]
        
        for nom_etape, ordre in etapes_standardes:
            EtapeValidation.objects.create(
                processValidation=self,
                nom=nom_etape,
                ordre=ordre
            )

class EtapeValidation(models.Model):
    processValidation = models.ForeignKey(ProcessValidation, related_name="etapes", on_delete=models.CASCADE)
    nom = models.CharField(max_length=255)
    ordre = models.PositiveIntegerField()
    est_validee = models.BooleanField(default=False)
    date_validation = models.DateTimeField(null=True, blank=True)
    valide_par = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL)
    commentaire = models.TextField(blank=True)
    obligatoire = models.BooleanField(default=True)
    fichier = models.FileField(upload_to='validations_attachements_etapes/%Y/%m/',
                                null=True,
                                blank=True,
                                verbose_name="Fichier de validation",
                                db_column='fichier_validation')
    original_filename = models.CharField(max_length=255, blank=True, verbose_name="Nom de fichier original")
    @property
    def get_file_name(self):
        if self.original_filename:
            return self.original_filename
        elif self.fichier:
            return os.path.basename(self.fichier.name)
        return ""
    class Meta:
        verbose_name = "Étape de validation"
        verbose_name_plural = "Étapes de validation"
        ordering = ['ordre']
    
    def valider(self, user, commentaire=""):
        self.est_validee = True
        self.date_validation = timezone.now()
        self.valide_par = user
        self.commentaire = commentaire
        self.save()
        self.processValidation.valider(user)

# ------------------------ Décompte ------------------------    
class Decompte(models.Model):
    TYPE_DECOMPTE = [
        ('PROVISOIRE', 'Décompte provisoire'),
        ('DEFINITIF', 'Décompte définitif'),
        ('SOLDE', 'Décompte de solde'),
    ]

    STATUT_DECOMPTE = [
        ('BROUILLON', 'Brouillon'),
        ('VALIDE', 'Validé'),
        ('EMIS', 'Émis'),
        ('EN_RETARD', 'En retard de paiement'),
        ('PAYE', 'Payé'),
        ('PARTIEL', 'Payé partiellement'),
    ]

    attachement = models.OneToOneField('Attachement', on_delete=models.CASCADE, related_name='decompte')
    type_decompte = models.CharField(max_length=15, choices=TYPE_DECOMPTE, default='PROVISOIRE')
    numero = models.CharField(max_length=20, verbose_name="Numéro de décompte")
    date_emission = models.DateField(verbose_name="Date d'émission")
    date_echeance = models.DateField(verbose_name="Date d'échéance", null=True, blank=True)
    statut = models.CharField(max_length=15, choices=STATUT_DECOMPTE, default='BROUILLON')

    montant_ht = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant HT")
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20.0, verbose_name="Taux TVA (%)")
    montant_tva = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant TVA")
    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant TTC")

    taux_retenue_garantie = models.DecimalField(max_digits=5, decimal_places=2, default=10.0, verbose_name="Taux retenue de garantie (%)")
    montant_retenue_garantie = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant retenue de garantie")

    taux_ras = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="Taux RAS (%)")
    montant_ras = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant RAS")

    autres_retenues = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Autres retenues")

    montant_net_a_payer = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant net à payer")

    numero_bordereau = models.CharField(max_length=50, blank=True, verbose_name="Numéro de bordereau")
    date_paiement = models.DateField(null=True, blank=True, verbose_name="Date de paiement")
    observations = models.TextField(blank=True, verbose_name="Observations")
    
    montant_revision_prix = models.DecimalField(max_digits=15, decimal_places=2, default=0, null=True, blank=True, verbose_name="Révision des prix")
    
    @property
    def montant_total_avec_revision(self):
        """Calcule le montant total avec révision"""
        total = self.montant_situation_ht or Decimal('0')
        return total + (self.montant_revision_prix or Decimal('0'))
    
    @property
    def montant_TTC_avec_revision(self):
        """Calcule le TTC avec révision"""
        return self.montant_total_avec_revision * (1 + Decimal('0.20'))  # TVA 20%
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.m_ht_situation = 0.0
        
    @property
    def montant_situation_ht(self):
        self.m_ht_situation = self.attachement.montant_situation
        return float(self.m_ht_situation)
    
    @property
    def montant_situation_retenue_garantie(self):
        taux = float(self.taux_retenue_garantie) if self.taux_retenue_garantie else 0.0
        return float(self.m_ht_situation)*taux/100
    
    @property
    def reste_a_payer_ht(self):
        return float(self.m_ht_situation) - float(self.montant_situation_retenue_garantie)
    
    @property
    def montant_situation_ttc(self):
        return self.reste_a_payer_ht*(1+(float(self.taux_tva)/100))
    
    @property
    def montant_situation_tva(self):
        return self.montant_situation_ttc - self.reste_a_payer_ht
    
    @property
    def montant_situation_ras(self):
        taux = float(self.taux_ras) if self.taux_ras else 0.0
        return float(self.m_ht_situation)*(taux/100)
    
    @property
    def montant_situation_autres_retenues(self):
        return float(self.autres_retenues) if self.autres_retenues else 0.0
    
    @property
    def montant_situation_net_a_payer(self):
        return max(
            0.0,
            self.montant_situation_ttc
            - self.montant_situation_ras
            - self.montant_situation_autres_retenues,
        )
    
    class Meta:
        verbose_name = "Décompte"
        verbose_name_plural = "Décomptes"
        ordering = ['-date_emission', '-numero']

    def calculer_montants(self, montant_situation):
        zero = Decimal('0.00')
        taux_tva = Decimal(str(self.taux_tva or 0))
        taux_retenue_garantie = Decimal(str(self.taux_retenue_garantie or 0))
        taux_ras = Decimal(str(self.taux_ras or 0))
        autres_retenues = Decimal(str(self.autres_retenues or 0))
        self.montant_ht = montant_situation + Decimal(str(self.montant_revision_prix or 0))
        self.montant_tva = (self.montant_ht * taux_tva) / Decimal('100')
        self.montant_ttc = self.montant_ht + self.montant_tva
        self.montant_retenue_garantie = (self.montant_ht * taux_retenue_garantie) / Decimal('100')
        self.montant_ras = (self.montant_ht * taux_ras) / Decimal('100')
        total_retenues = self.montant_retenue_garantie + self.montant_ras + autres_retenues
        self.montant_net_a_payer = max(zero, self.montant_ttc - total_retenues)

    def save(self, *args, **kwargs):
        self.calculer_montants(self.attachement.montant_situation)
        super().save(*args, **kwargs)

    @property
    def est_en_retard(self):
        if self.date_echeance and self.statut in ['EMIS', 'PARTIEL']:
            return date.today() > self.date_echeance
        return False
    
    def __str__(self):
        return f"Décompte {self.numero} - {self.attachement.projet.nom}"

# ------------------------
class LigneDecompte(models.Model):
    NATURE_DEPENSES_CHOICES = [
        ('penalite_retard', 'PENALITE POUR RETARD DE TRAVAUX'),
        ('penalite_absence_reunion', 'PENALITES POUR ABSENCE REUNION DE CHANTIER'),
        ('autre_penalite', 'AUTRE PENALITE'),
        ('revision_prix', 'REVISION DES PRIX'),
        ('retenue_assurance_decenale', 'RETENUE ASSURANCE DECENALE'),
        ('retenue_garantie', 'RETENUE GARANTIE'),
        ('ras', 'RETENUE A LA SOURCE'),
        ('penalite_retard','PENALITE POUR RETARD DE TRAVAUX'),
        ('autres', 'AUTRES RETENUES'),
    ]
    NATURE_RECETTES_CHOICES = [
        ('travaux_metre', 'TRAVAUX TERMINES AU METRE'),
        ('travaux_forfait', 'TRAVAUX TERMINES AU FORFAIT'),
        ('travaux_avenants', 'TRAVAUX TERMINES AVENANTS'),
        ('travaux_non_termines', 'TRAVAUX NON TERMINES'),
        ('approvisionnement', 'APPROVISIONNEMENT'),
        ('honoraires', 'HONORAIRES'),
    ]
    nature_depenses = models.CharField(
        max_length=50, 
        choices=NATURE_DEPENSES_CHOICES,
        verbose_name="Nature des dépenses"
    )
    nature_recettes = models.CharField(
        max_length=50, 
        choices=NATURE_RECETTES_CHOICES,
        verbose_name="Nature des recettes"
    )

    cumul_a_date = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Cumul à date (A)"
    )
    
    cumul_deja_percu = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Cumul déjà perçu (B)"
    )
    
    reste_a_payer = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Reste à payer (A)-(B)"
    )
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Décompte"
        verbose_name_plural = "Décomptes"
        ordering = ['nature_depenses']

    def save(self, *args, **kwargs):
        self.reste_a_payer = self.cumul_a_date - self.cumul_deja_percu
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_nature_depenses_display()} - {self.cumul_a_date}"

    @property
    def nature_depenses_display(self):
        return self.get_nature_depenses_display()

class ResumeDecompte(models.Model):
    sous_total_ht = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Sous-total HT"
    )
    
    total_ht = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Total HT"
    )
    
    tva_taux = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=20.00,
        verbose_name="Taux TVA %"
    )
    
    tva_montant = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Montant TVA"
    )
    
    total_ttc = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Total TTC"
    )
    
    acompte_ttc = models.DecimalField(
        max_digits=15, 
        decimal_places=2, 
        default=0.00,
        verbose_name="Acompte TTC à délivrer"
    )
    
    date_calcul = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Résumé de décompte"
        verbose_name_plural = "Résumés de décomptes"

    def calculer_totaux(self, decomptes):
        self.sous_total_ht = sum(d.cumul_a_date for d in decomptes)
        self.total_ht = self.sous_total_ht
        self.tva_montant = self.total_ht * (self.tva_taux / 100)
        self.total_ttc = self.total_ht + self.tva_montant
        self.save()

    def __str__(self):
        return f"Résumé décompte - {self.date_calcul.strftime('%d/%m/%Y')}"