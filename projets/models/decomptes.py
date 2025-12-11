from decimal import Decimal
import os
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from datetime import date
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
    numero = models.CharField(max_length=20, verbose_name="Numéro d'attachement")
    date_etablissement = models.DateField(verbose_name="Date d'établissement")
    date_debut_periode = models.DateField(verbose_name="Date début période")
    date_fin_periode = models.DateField(verbose_name="Date fin période")
    statut = models.CharField(max_length=15, choices=STATUT_ATTACHEMENT, default='BROUILLON')
    observations = models.TextField(blank=True, verbose_name="Observations")
    
    # Champ compatible Cloudinary
    if getattr(settings, 'USE_CLOUDINARY', False):
        from cloudinary.models import CloudinaryField
        fichier = CloudinaryField('raw', folder='attachements', resource_type='raw', default=None, blank=True, null=True)
    else:
        fichier = models.FileField(upload_to='attachements/%Y/%m/', null=True, blank=True)
    original_filename = models.CharField(max_length=255, blank=True, verbose_name="Nom de fichier original")
    
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta: 
        verbose_name = "Attachement"
        verbose_name_plural = "Attachements"
        ordering = ['-date_etablissement', '-numero']

    def initialiser_processus_validation(self, demandeur):
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
            if getattr(settings, 'USE_CLOUDINARY', False):
                return self.__str__()
            return os.path.basename(self.fichier.name)
        return ""
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
        
        self.statut = 'BROUILLON'
        self.save()
        
        self.validations.update(
            statut_validation='EN_ATTENTE',
            validateur=None,
            date_validation=None,
            commentaires='',
            motifs_rejet=''
        )
    
    def transmettre(self, user):
        if self.statut != 'SIGNE':
            raise ValueError("Seuls les attachements signés peuvent être transmis.")
        
        self.statut = 'TRANSMIS'
        self.save()
        
        self.initialiser_processus_validation(demandeur=user)
    @property
    def total_montant_ht(self):
        return sum(ligne.montant_ligne_realise for ligne in self.lignes_attachement.all())

    def get_previous_attachement(self):
        return Attachement.objects.filter(projet=self.projet, id__lt=self.id).order_by('-id').first()
    
    @property
    def montant_ht_attachement_precedent(self):
        try:
            precedent = self.get_previous_attachement()
            if precedent:
                return precedent.total_montant_ht
            return 0
        except Exception:
            return 0
    
    @property
    def montant_situation(self):
        return self.total_montant_ht - self.montant_ht_attachement_precedent
        
    def __str__(self):
        return f"Attachement {self.numero} - {self.projet.nom}"
    
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
        if not self.pk:
            cumul_precedent = LigneAttachement.objects.filter(
                ligne_lot=self.ligne_lot,
                attachement__date_etablissement__lt=self.attachement.date_etablissement
            ).aggregate(total=Sum('quantite_realisee'))['total'] or 0
            self.quantite_cumulee = cumul_precedent + self.quantite_realisee
        super().save(*args, **kwargs)

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
    
    # Champ compatible Cloudinary
    if getattr(settings, 'USE_CLOUDINARY', False):
        from cloudinary.models import CloudinaryField
        fichier= CloudinaryField('raw', 
                                folder='validations_attachements', 
                                resource_type='raw', 
                                null=True, 
                                blank=True,
                                db_column='fichier_validation',)
    else:
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
            if getattr(settings, 'USE_CLOUDINARY', False):
                return self.__str__()
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
        validations_obligatoires = self.attachement.validations.filter(est_obligatoire=True)
        validations_validees = validations_obligatoires.filter(statut_validation='VALIDE')
        
        if validations_obligatoires.count() == validations_validees.count():
            self.attachement.statut = 'VALIDE'
            self.attachement.save()

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
            #raise ValueError("Toutes les étapes de validation doivent être validées avant de valider cet attachement")
        
        self.statut_validation = 'VALIDE'
        self.validateur = user
        self.commentaires = commentaires
        if fichier:
            self.fichier = fichier
        self.save()
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

    def demander_correction(self, user, commentaires):
        if not self.peut_etre_valide_par(user):
            raise PermissionError("Cet utilisateur ne peut pas demander une correction")
        
        self.statut_validation = 'CORRECTION'
        self.validateur = user
        self.commentaires = commentaires
        self.save()

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
        # Champ compatible Cloudinary
    if getattr(settings, 'USE_CLOUDINARY', False):
        from cloudinary.models import CloudinaryField
        fichier = CloudinaryField('raw', 
                                    folder='validations_attachements_etapes', 
                                    resource_type='raw', 
                                    null=True, 
                                    blank=True,
                                    db_column='fichier_validation')
    else:
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
            if getattr(settings, 'USE_CLOUDINARY', False):
                return self.__str__()
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
        return self.montant_situation_ttc - self.montant_situation_ras - self.montant_situation_autres_retenues
    
    class Meta:
        verbose_name = "Décompte"
        verbose_name_plural = "Décomptes"
        ordering = ['-date_emission', '-numero']

    def save(self, *args, **kwargs):
        self.montant_ht = self.attachement.total_montant_ht + self.montant_revision_prix
        self.montant_tva = (self.montant_ht * self.taux_tva) / 100
        self.montant_ttc = self.montant_ht + self.montant_tva
        self.montant_retenue_garantie = (self.montant_ht * self.taux_retenue_garantie) / 100
        self.montant_ras = (self.montant_ht * self.taux_ras) / 100
        total_retenues = self.montant_retenue_garantie + self.montant_ras + self.autres_retenues
        self.montant_net_a_payer = max(0, self.montant_ttc - total_retenues)
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