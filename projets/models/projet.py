from decimal import Decimal
import os
import cloudinary
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.db.models import Q
from django.core.exceptions import ValidationError

# ------------------------ Entreprise ------------------------ #
class Entreprise(models.Model):
    nom = models.CharField(_("Nom de l'entreprise"), max_length=200)
    contact = models.CharField(_("Contact"), max_length=150, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    telephone = models.CharField(_("Téléphone"), max_length=20, blank=True)
    adresse = models.TextField(_("Adresse"), blank=True)

    class Meta:
        verbose_name = _("Entreprise")
        verbose_name_plural = _("Entreprises")

    def __str__(self):
        return self.nom

# ------------------------ Appel d'offre --------------------- #
class AppelOffre(models.Model):
    TYPE_AO = [
        ('TRAVAUX', 'Travaux'),
        ('FOURNITURES', 'Fournitures'),
        ('SERVICES', 'Services'),
        ('CONCESSION', 'Concession'),
        ('PARTENARIAT', 'Partenariat'),
        ('AUTRE', 'Autre'),
    ]

    class Decision(models.TextChoices):
        EN_ATTENTE = 'EN_ATTENTE', _('En attente')
        ACCEPTE = 'ACCEPTE', _('Accepté')
        REFUSE = 'REFUSE', _('Refusé')

    nom = models.CharField(_("Nom d'appel d'offre"), max_length=50)
    objet = models.TextField(_("Objet du marché"), max_length=200)
    numero = models.CharField(_("Numéro du marché"), max_length=100, unique=True)
    maitre_ouvrage = models.CharField(_("Maître d'ouvrage"), max_length=200)
    localisation = models.CharField(_("Localisation"), max_length=200)
    type = models.CharField(_("Type d'AO"), max_length=20, choices=TYPE_AO, default='TRAVAUX')
    date_reception = models.DateField(_("Date d'appel d'offres"))
    date_limite = models.DateField(_("Date limite de soumission"))
    estimation_moa = models.DecimalField(_("Estimation du MOA (DH)"), max_digits=12, decimal_places=2, null=True, blank=True)
    caution_provisoire = models.DecimalField(_("Caution provisoire (DH)"), max_digits=12, decimal_places=2, null=True, blank=True)
    decision = models.CharField(_("Décision"), max_length=20, choices=Decision.choices, default=Decision.EN_ATTENTE)
    date_creation = models.DateTimeField(_("Date d'enregistrement"), auto_now_add=True)
    avancement = models.DecimalField(_("Avancement (%)"), max_digits=5, decimal_places=2, default=0.0)

    # Relation avec Projet
    projet = models.OneToOneField(
        'Projet',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appel_offre_rel'
    )

    class Meta:
        verbose_name = _("Appel d'offre")
        verbose_name_plural = _("Appels d'offre")
        ordering = ['-date_reception']

    def __str__(self):
        return f"AO {self.numero} - {self.nom}"

    @property
    def jours_restants(self):
        """Jours restants avant la date limite"""
        if self.date_limite:
            return (self.date_limite - date.today()).days
        return None

# ------------------------ Projet ---------------------------- #

class Projet(models.Model):
    TYPE_PROJET = [
        ('VRD', 'Voirie et Réseaux Divers'),
        ('ROUTE', 'Route'),
        ('PONT', 'Pont'),
        ('BATIMENT', 'Bâtiment'),
        ('CONSTRUCTION', 'Construction'),
        ('ASSAINISSEMENT EP', 'Assainissement EP'),
        ('ASSAINISSEMENT EU', 'Assainissement EU'),
        ('ASSAINISSEMENT', 'Assainissement'),
        ('ADDUCTION_EAU_POTABLE', "Adduction d'eau potable"),
        ('EQUIPEMENT', 'Équipement'),
        ('AMENAGEMENT', 'Aménagement'),
        ('GENIE_CIVIL', 'Génie Civil'),
        ('TRAVAUX_PUBLICS', 'Travaux Publics'),
        ('ELECTRICITE', 'Électricité'),
        ('HYDRAULIQUE', 'Hydraulique'),
        ('TELECOMMUNICATION', 'Télécommunication'),
        ('ENVIRONNEMENT', 'Environnement'),
        ('URBANISME', 'Urbanisme'),
        ('ESPACE_PUBLIC', 'Espace Public'),
        ('PLACE_PUBLIQUE', 'Place Publique'),
        ('ESPACE_VERT', 'Espace Vert'),
        ('TERRAINS_SPORTIFS', 'Terrins Sportifs'),
        ('TERRAINS_PROXIMITES', 'Terrains Proximités'),
        ('AUTRE', 'Autre'),
    ]

    class Statut(models.TextChoices):
        APPEL_OFFRE = 'AO', _("Appel d'offre")
        EN_ETUDE = 'ETUDE', _('En étude')
        EN_ATTENTE = 'ATTENTE', _('En attente')
        EN_DEMARRAGE = 'DEM', _('En démarrage')
        EN_COURS = 'COURS', _('En cours')
        EN_ARRET = 'ARRET', _('En arrêt')
        EN_RECEPTION = 'RECEP', _('En réception')
        EN_RECEPTION_PROVISOIRE = 'RECEP_PROV', _('En réception provisoire')
        EN_RECEPTION_DEFINITIVE = 'RECEP_DEF', _('En réception définitive')
        RECEPTION_PROVISOIRE = 'RP', _('Réception provisoire')
        RECEPTION_DEFINITIVE = 'RD', _('Réception définitive')
        CLOTURE = 'CLO', _('Clôturé')

    type_projet = models.CharField(_("Type de projet"), max_length=50, choices=TYPE_PROJET, default='VRD', null=True, blank=True)
    nom = models.CharField(_("Nom du projet"), max_length=50)
    objet = models.TextField(_("Objet du marché"), max_length=200)
    numero = models.CharField(_("Numéro du marché"), max_length=100, unique=True)
    maitre_ouvrage = models.CharField(_("Maître d'ouvrage"), max_length=200)
    localisation = models.CharField(_("Localisation"), max_length=200)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, verbose_name=_("Utilisateurs"), blank=True, related_name='projets')
    revisable = models.BooleanField(_("Revisable"), default=False, null=True, blank=True)
    montant = models.DecimalField(_("Montant estimé (DH)"), max_digits=12, decimal_places=2, null=True, blank=True)
    montant_soumission = models.DecimalField(_("Montant de la soumission (DH)"), max_digits=12, decimal_places=2, null=True, blank=True)
 
    statut = models.CharField(_("Statut"), max_length=15, choices=Statut.choices, default=Statut.APPEL_OFFRE)
    date_debut = models.DateField(_("Date de début prévue"), null=True, blank=True)
    delai = models.IntegerField(_("Délai (jours)"), null=True, blank=True, default=0)
    date_creation = models.DateTimeField(_("Date d'enregistrement"), auto_now_add=True)
    avancement = models.DecimalField(_("Avancement (%)"), max_digits=5, decimal_places=2, default=0.0)

    entreprise = models.ForeignKey('Entreprise', on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Entreprise adjudicataire"))
    appel_offre = models.OneToOneField('AppelOffre', on_delete=models.SET_NULL, null=True, blank=True, related_name='projet_associe')
    revisable = models.BooleanField(_("Revisable"), null=True, blank=True, default=False)
    epoque_base = models.DateField(_("Epoque de base"), null=True, blank=True)
    a_traiter = models.BooleanField(_("À traiter (appel d'offre)"), null=True, blank=True, default=False)
    en_retard = models.BooleanField(_("En retard"), null=True, blank=True, default=False)
    reception_validee = models.BooleanField(_("Réception validée"), null=True, blank=True, default=False)
    date_reception = models.DateField(_("Date de réception"), null=True, blank=True)
    date_limite_soumission = models.DateField(_("Date limite de soumission"), null=True, blank=True)

    class Meta:
        verbose_name = _("Projet")
        verbose_name_plural = _("Projets")
        ordering = ['-date_creation']
    
    def __str__(self):
        return f"{self.nom} ({self.numero})"
    
    def save(self, *args, **kwargs):
        update_flags = kwargs.pop('update_flags', True)
        super().save(*args, **kwargs)
        
        if update_flags and not getattr(self, '_updating_flags', False):
            try:
                self._updating_flags = True
                self.update_status_flags(force_save=False)
            finally:
                delattr(self, '_updating_flags')
    
    def update_status_flags(self, force_save=True):
        """Met à jour les indicateurs de statut pour la page d'accueil"""
        if self.date_debut and self.delai and self.statut in [self.Statut.EN_COURS, self.Statut.EN_ARRET]:
            date_limite = self.date_debut + timedelta(days=self.delai)
            self.en_retard = date.today() > date_limite and self.avancement < 100
        
        self.a_traiter = self.statut == self.Statut.APPEL_OFFRE and self.date_limite_soumission and self.date_limite_soumission >= date.today()
        self.reception_validee = self.statut in [self.Statut.RECEPTION_PROVISOIRE, self.Statut.RECEPTION_DEFINITIVE, self.Statut.CLOTURE]
        
        if force_save:
            self.save(update_flags=False)
    
    def get_type_echeance_display(self):
        if self.statut == 'AO':
            return "Appel d'offres"
        elif self.statut in ['RECEP', 'RECEP_DEF']:
            return "Réception"
        return "Échéance"
    
    def montant_total(self, force_update=False):
        """Calcule le montant total et synchronise le champ si nécessaire."""
        try:
            total_lots = sum(lot.montant_total_ht for lot in self.lots.all()) 
            nouveau_montant = total_lots * Decimal('1.2')
            ancien_montant = self.montant or Decimal('0')
            montants_different = abs(ancien_montant - nouveau_montant) > Decimal('0.01')
            
            if force_update or montants_different:
                from django.db import transaction
                with transaction.atomic():
                    Projet.objects.filter(id=self.id).update(montant=nouveau_montant)
                    self.montant = nouveau_montant
                
            return nouveau_montant
        except Exception as e:
            print(f"Erreur calcul montant projet {self.id}: {e}")
            return self.montant or Decimal('0')
    
    @property
    def marche_approuve(self):
        return self.ordres_service.filter(
            type_os__code='OSN',
            statut='NOTIFIE'
        ).exists()
    
    @property
    def projet_demarre(self):
        return self.ordres_service.filter(
            type_os__code='OSC',
            statut='NOTIFIE'
        ).exists()
    
    @property
    def projet_en_arret(self):
        dernier_osa = self.ordres_service.filter(
            type_os__code='OSA', 
            statut='NOTIFIE'
        ).order_by('-ordre_sequence').first()
        
        if not dernier_osa:
            return False
        
        dernier_osr = self.ordres_service.filter(
            type_os__code='OSR', 
            statut='NOTIFIE'
        ).order_by('-ordre_sequence').first()
        
        return not dernier_osr or dernier_osa.ordre_sequence > dernier_osr.ordre_sequence
    
    @property
    def projet_en_cours(self):
        return not self.projet_en_arret
    
    @property
    def statut_workflow(self):
        if not self.marche_approuve:
            return "Marché non approuvé"
        elif not self.projet_demarre:
            return "Marché approuvé - En attente de démarrage"
        elif self.projet_en_arret:
            return "Projet en arrêt"
        else:
            return "Projet en cours"
    
    @property
    def avancement_workflow(self):
        montant_total = self.montant_total()
        dernier_attachement = self.attachements.order_by('-id').first()
        montant_attachements = dernier_attachement.total_montant_ht if dernier_attachement else 0
        if montant_total > 0:
            return round((montant_attachements / montant_total) * 100)
        return 0
    
    def jours_decoules_depuis_demarrage(self, date_reference=None):
        if date_reference is None:
            date_reference = timezone.now().date()
        
        osc = self.ordres_service.filter(
            type_os__code='OSC',
            statut='NOTIFIE'
        ).order_by('ordre_sequence').first()
        
        if not osc or not osc.date_effet:
            return None
        
        date_demarrage = osc.date_effet
        
        if date_reference < date_demarrage:
            return 0
        
        evenements = self.ordres_service.filter(
            Q(type_os__code='OSA') | Q(type_os__code='OSR'),
            statut='NOTIFIE',
            date_effet__isnull=False
        ).filter(
            date_effet__gte=date_demarrage,
            date_effet__lte=date_reference
        ).order_by('date_effet', 'ordre_sequence')
        
        jours_total = 0
        date_debut_periode = date_demarrage
        en_arret = False
        
        for evenement in evenements:
            if evenement.type_os.code == 'OSA' and not en_arret:
                jours_periode = (evenement.date_effet - date_debut_periode).days
                jours_total += max(0, jours_periode)
                date_debut_periode = evenement.date_effet
                en_arret = True
            elif evenement.type_os.code == 'OSR' and en_arret:
                date_debut_periode = evenement.date_effet
                en_arret = False
        
        if not en_arret:
            jours_derniere_periode = (date_reference - date_debut_periode).days
            jours_total += max(0, jours_derniere_periode)
        
        return jours_total
    
    def jours_decoules_aujourdhui(self):
        return self.jours_decoules_depuis_demarrage()
    
    def get_historique_periodes(self, date_reference=None):
        if date_reference is None:
            date_reference = timezone.now().date()
        
        osc = self.ordres_service.filter(
            type_os__code='OSC',
            statut='NOTIFIE'
        ).order_by('ordre_sequence').first()
        
        if not osc or not osc.date_effet:
            return []
        
        date_demarrage = osc.date_effet
        
        evenements = self.ordres_service.filter(
            Q(type_os__code='OSA') | Q(type_os__code='OSR'),
            statut='NOTIFIE',
            date_effet__isnull=False
        ).filter(
            date_effet__gte=date_demarrage,
            date_effet__lte=date_reference
        ).order_by('date_effet', 'ordre_sequence')
        
        periodes = []
        date_debut = date_demarrage
        en_arret = False
        
        for evenement in evenements:
            type_periode = "arrêt" if en_arret else "travaux"
            duree = (evenement.date_effet - date_debut).days
            periodes.append({
                'type': type_periode,
                'debut': date_debut,
                'fin': evenement.date_effet,
                'duree': max(0, duree)
            })
            date_debut = evenement.date_effet
            en_arret = (evenement.type_os.code == 'OSA')
        
        if date_debut <= date_reference:
            type_periode = "arrêt" if en_arret else "travaux"
            duree = (date_reference - date_debut).days
            periodes.append({
                'type': type_periode,
                'debut': date_debut,
                'fin': date_reference,
                'duree': max(0, duree),
                'en_cours': True
            })
        
        return periodes
    
    def montant_total_formate(self):
        return "{:,.2f}".format(self.montant_total()).replace(",", " ")
    
    @property
    def jours_restants(self):
        if self.date_limite_soumission:
            return (self.date_limite_soumission - date.today()).days
        return None

    @property
    def retard_jours(self):
        if self.en_retard and self.date_debut and self.delai:
            date_limite = self.date_debut + timedelta(days=self.delai)
            return (date.today() - date_limite).days
        return 0
    
    @classmethod
    def projets_en_retard(cls):
        return cls.objects.filter(en_retard=True)

    @classmethod
    def nouveaux_appels_offres(cls):
        return cls.objects.filter(a_traiter=True, date_limite_soumission__gte=date.today())

    @classmethod
    def receptions_validees_recentes(cls):
        return cls.objects.filter(reception_validee=True, date_reception__gte=date.today()-timedelta(days=30))

# ------------------ Ordre de service ------------------------
 
class TypeOrdreService(models.Model):
    TYPE_CHOICES = [
        ('OSN', 'OS de Notification de l\'approbation du marché'),
        ('OSC', 'OS de Commencement'),
        ('OSA', 'OS d\'Arrêt'),
        ('OSR', 'OS de Reprise'),
        ('OSC10', 'OS de Continuation jusqu\'à 10%'),
        ('OSV', 'OS d\'Approbation d\'Avenant'),
        ('AUTRE', 'Autre OS'),
    ]
    
    code = models.CharField(max_length=10, choices=TYPE_CHOICES, unique=True)
    nom = models.CharField(max_length=100)
    description = models.TextField()
    ordre_min = models.IntegerField(help_text="Ordre minimum dans la séquence")
    ordre_max = models.IntegerField(help_text="Ordre maximum dans la séquence")
    precedent_obligatoire = models.ManyToManyField('self', symmetrical=False, blank=True)
    unique_dans_projet = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.code} - {self.nom}"

class OrdreService(models.Model):
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('NOTIFIE', 'Notifié'),
        ('ANNULE', 'Annulé'),
    ]
    
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name='ordres_service')
    type_os = models.ForeignKey(TypeOrdreService, on_delete=models.PROTECT)
    reference = models.CharField(max_length=50)
    titre = models.CharField(max_length=200)
    description = models.TextField()
    date_publication = models.DateField()
    date_limite = models.DateField(null=True, blank=True)
    date_effet = models.DateField(null=True, blank=True)
    
    # Champ compatible Cloudinary
    if getattr(settings, 'USE_CLOUDINARY', False):
        from cloudinary.models import CloudinaryField
        fichier = CloudinaryField('raw', 
                                    folder='ordres_services', 
                                    resource_type='raw', 
                                    null=True, 
                                    blank=True,
                                    db_column='documents')
    else:
        fichier = models.FileField(upload_to='ordres_services/', 
                                     null=True, 
                                     blank=True,
                                     db_column='documents')
    original_filename = models.CharField(max_length=255, blank=True, verbose_name="Nom de fichier original")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    ordre_sequence = models.IntegerField(help_text="Ordre dans la séquence du projet")
    
    # Champs spécifiques selon le type
    duree_extension = models.IntegerField(null=True, blank=True, default=0, help_text="Durée d'extension en jours")
    montant_supplementaire = models.DecimalField(max_digits=12, decimal_places=2, default=0, null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['projet', 'reference']
        ordering = ['projet', 'ordre_sequence', 'date_publication']
    @property
    def get_file_name(self):
        if self.original_filename:
            return self.original_filename
        elif self.fichier:
            if getattr(settings, 'USE_CLOUDINARY', False):
                return self.__str__()
            return os.path.basename(self.fichier.name)
        return ""
    def __str__(self):
        return f"{self.reference} - {self.titre}"
    
    def save(self, *args, **kwargs):
        if not self.ordre_sequence:
            dernier_ordre = OrdreService.objects.filter(
                projet=self.projet
            ).aggregate(models.Max('ordre_sequence'))['ordre_sequence__max'] or 0
            self.ordre_sequence = dernier_ordre + 1
        super().save(*args, **kwargs)
    
    def clean(self):
        super().clean()
        errors = {}
        
        if not self.pk or not hasattr(self, 'projet') or self.projet is None:
            return
        
        if self.statut == 'NOTIFIE':
            prerequis = self.type_os.precedent_obligatoire.all()
            if prerequis.exists():
                os_precedents = OrdreService.objects.filter(
                    projet=self.projet,
                    type_os__in=prerequis,
                    statut='NOTIFIE'
                )
                if not os_precedents.exists():
                    types_manquants = ", ".join([p.code for p in prerequis])
                    errors['type_os'] = f"Prérequis manquant: {types_manquants}"
            
            if self.type_os.unique_dans_projet:
                existing = OrdreService.objects.filter(
                    projet=self.projet,
                    type_os=self.type_os,
                    statut='NOTIFIE'
                ).exclude(pk=self.pk)
                if existing.exists():
                    errors['type_os'] = f"Un {self.type_os.nom} existe déjà pour ce projet"
            
            if self.type_os.code == 'OSA':
                dernier_os = OrdreService.objects.filter(
                    projet=self.projet,
                    statut='NOTIFIE'
                ).exclude(pk=self.pk).order_by('-ordre_sequence').first()
                
                if dernier_os and dernier_os.type_os.code == 'OSA':
                    errors['type_os'] = "Un OS d'arrêt ne peut pas suivre un autre OS d'arrêt"
            
            if self.type_os.code == 'OSR':
                dernier_osa = OrdreService.objects.filter(
                    projet=self.projet,
                    type_os__code='OSA',
                    statut='NOTIFIE'
                ).order_by('-ordre_sequence').first()
                
                if not dernier_osa:
                    errors['type_os'] = "Un OS de reprise doit être précédé d'un OS d'arrêt"
        
        if errors:
            raise ValidationError(errors)
    # def download_url(self):
    #     if not self.fichier:
    #         return None
    #     return self.fichier.build_url(flags='attahement')
    @property
    def influence_delai(self):
        return self.type_os.code in ['OSC', 'OSA', 'OSR']

    @property
    def influence_budget(self):
        return self.type_os.code in ['OSC10', 'OSV']
 
# ------------------ Tâches ----------------------------------
class Tache(models.Model):
    PRIORITE = [
        ('BASSE', 'Basse'),
        ('NORMALE', 'Normale'),
        ('HAUTE', 'Haute'),
        ('URGENTE', 'Urgente'),
    ]

    projet = models.ForeignKey('Projet', on_delete=models.CASCADE)
    titre = models.CharField(max_length=200)
    description = models.TextField()
    date_debut = models.DateField()
    date_fin = models.DateField() 
    priorite = models.CharField(max_length=10, choices=PRIORITE, default='NORMALE')
    responsable = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    terminee = models.BooleanField(default=False)
    avancement = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
 
    class Meta:
        verbose_name = _("Tâche")
        verbose_name_plural = _("Tâches")
        ordering = ['date_fin']

    def __str__(self):
        return f"{self.titre} - {self.projet.nom}"

    @property
    def jours_restants(self):
        if self.date_fin:
            return (self.date_fin - date.today()).days
        return None

    @property
    def jours_retard(self):
        if self.terminee : return 0
        if self.date_fin:
            return (date.today() - self.date_fin).days
        return 0
# ------------------ Documents administratifs ----------------
def document_upload_path(instance, filename):
    return f'documents_administratifs/projet_{instance.projet.id}/{filename}'

class DocumentAdministratif(models.Model):
    """Modèle pour les documents administratifs"""
    TYPE_CHOICES = [
        ('', 'Sélectionner un type...'),
        ('Attestation', 'Attestation'),
        ('Attestation d\'enregistrement', 'Attestation d\'enregistrement'),
        ('Attestation de conformité', 'Attestation de conformité'),
        ('Attestation d\'assurance', 'Attestation d\'assurance'),
        ('Assurance', 'Assurance'),
        ('Caution provisoire', 'Caution provisoire'),
        ('Caution définitive', 'Caution définitive'),
        ('Bon de commande', 'Bon de commande'),
        ('CPS', 'Cahier des prescriptions spéciales (CPS)'),
        ('CPS avenant', 'CPS d\'avenant'),
        ('Cahier des charges', 'Cahier des charges (CDC)'),
        ('Contrat', 'Contrat'),
        ('Contrat de sous-traitance', 'Contrat de sous-traitance'),
        ('Cahier des clauses techniques', 'Cahier des clauses techniques (CCT)'),
        ('CCTP', 'Cahier des clauses techniques particulières (CCTP)'),
        ('CCAP', 'Cahier des clauses administratives particulières (CCAP)'),
        ('Cahier des clauses administratives', 'Cahier des clauses administratives (CCA)'),
        ('BDP', 'Bordereau des prix (BDP)'),
        ('Contrat de garantie', 'Contrat de garantie'),
        ('Convention', 'Convention'),
        ('Autorisation', 'Autorisation'),
        ('Rapport', 'Rapport'),
        ('Procès-verbal', 'Procès-verbal (PV)'),
        ('Autre', 'Autre'),
    ]
    projet = models.ForeignKey('Projet', on_delete=models.CASCADE, related_name='documents_administratifs', verbose_name=_("Projet"))
    
    # Champ compatible Cloudinary
    if getattr(settings, 'USE_CLOUDINARY', False):
        from cloudinary.models import CloudinaryField
        fichier = CloudinaryField('raw', folder='documents_administratifs', resource_type='raw', default=None)
    else:
        fichier = models.FileField(_("Fichier"), upload_to=document_upload_path)
        
    original_filename = models.CharField(max_length=255, blank=True, verbose_name="Nom de fichier original")
    type_document = models.CharField(_("Type de document"), max_length=100, choices=TYPE_CHOICES, default='', blank=True)
    date_remise = models.DateField(_("Date de remise"), null=True, blank=True)
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        verbose_name = _("Document administratif")
        verbose_name_plural = _("Documents administratifs")
        ordering = ['type_document']
    @property
    def get_file_name(self):
        if self.original_filename:
            return self.original_filename
        elif self.fichier:
            if getattr(settings, 'USE_CLOUDINARY', False):
                return self.__str__()
            return os.path.basename(self.fichier.name)
        return ""
    def __str__(self):
        return f"{self.type_document} - {self.projet.nom}"

    def get_file_extension(self):
        return os.path.splitext(self.fichier.name)[1][1:].upper() if self.fichier else ''

# ------------------ Lots du projet --------------------------
class Line:
    def __init__(self, id=None, parent=None, numero="", designation="New Line", montant=Decimal('0.00')):
        self.id=id
        self.parent = parent
        self.numero = numero
        self.designation = designation
        self.montant = montant
        self.children = []
    
    def amount(self):
        if self.children:
            return sum(child.amount() for child in self.children)
        return self.montant
    
    def add_child(self, child_line):
        child_line.parent = self
        self.children.append(child_line)
        return child_line
    
    def insert_child(self, index, child_line):
        child_line.parent = self
        self.children.insert(index, child_line)
        return child_line
    
    def remove_child(self, child_line):
        if child_line in self.children:
            self.children.remove(child_line)
            child_line.parent = None
        else:
            raise ValueError("Child line not found")
        return child_line
    
    def index_of(self, child_line):
        try:
            return self.children.index(child_line)
        except ValueError:
            return -1
    
    def index(self):
        if self.parent:
            return self.parent.index_of(self)
        return -1
    
    def get_child(self, index):
        if 0 <= index < len(self.children):
            return self.children[index]
        return None
    
    def find_by_id(self, id):
        for child in self.get_descendants():
            if child.id == id:
                return child
        return None
    
    def level(self):
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level
    
    def child_count(self):
        return len(self.children)
    
    def has_children(self):
        return len(self.children) > 0
    
    def get_children(self):
        return self.children
    
    def get_descendants(self):
        descendants = []
        for child in self.children:
            descendants.append(child)
            descendants.extend(child.get_descendants())
        return descendants
    
    def siblings(self):
        if self.parent:
            return [child for child in self.parent.children if child != self]
        return []
    
    def previous(self):
        if self.parent:
            index = self.parent.index_of(self)
            if index > 0:
                return self.parent.children[index - 1]
        return None
    
    def next(self):
        if self.parent:
            index = self.parent.index_of(self)
            if index < len(self.parent.children) - 1:
                return self.parent.children[index + 1]
        return None
    
    def indent(self):
        previous = self.previous()
        if previous:
            self.niveau += 1
            previous.add_child(self)
            return self
        return None
    
    def outdent(self):
        if self.parent:
            index = self.parent.index()
            grandparent = self.parent.parent
            self.parent.remove_child(self)
            if grandparent:
                grandparent.insert_child(index+1, self)
            return self
        return None
    
    def __str__(self):
        return f"{self.designation} ({self.amount()})"

class LineBPU(Line):
    def __init__(self, id=None, parent=None, numero="", designation="New Line", unite="", quantite=Decimal('0.00'), pu=Decimal('0.00')):
        super().__init__(id=id, parent=parent, numero=numero, designation=designation,)
        self.unite = unite
        self.quantite = quantite
        self.pu = pu
    
    def get_child_by_id(self, id):
        for child in self.children:
            if isinstance(child, LineBPU) and child.id == id:
                return child
        return None
    
    def __str__(self):
        return f"{self.id} | {self.numero} | {self.designation} | {self.unite} | {self.quantite} | {self.pu} | {self.amount()}"
    
    def amount(self):
        if self.has_children():
            return sum(child.amount() for child in self.children)
        else:
            return self.quantite * self.pu

class LotProjet(models.Model):
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name='lots', verbose_name=_("Projet"))
    nom = models.CharField(_("Nom du lot"), max_length=200)
    description = models.TextField(_("Description"), blank=True)

    class Meta:
        verbose_name = _("Lot du projet")
        verbose_name_plural = _("Lots du projet")
        ordering = ['nom']

    def __str__(self):
        return f"{self.projet.nom} – {self.nom}"

    @property
    def montant_total_ht(self):
        total = self.lignes.aggregate(total_ht=Sum('montant_calcule'))['total_ht']
        return total if total is not None else Decimal('0.00')

    @property
    def montant_tva(self):
        return self.montant_total_ht * Decimal('0.20')

    @property
    def montant_total_ttc(self):
        return self.montant_total_ht + self.montant_tva

    @property
    def montant_formate(self):
        mnt_ht = self.montant_total_ht * Decimal('1.20')
        mnt_txt = "{:,.2f}".format(mnt_ht).replace(",", " ") if mnt_ht else "0.00"
        return mnt_txt
    @property
    def montant_realise(self):
        total = self.lignes.aggregate(total_ht=Sum('montant_realise'))['total_ht']
        return total if total is not None else Decimal('0.00')
    
    def to_line_tree(self):
        lignes_dict = {}
        root = Line(numero="Root", designation=self.nom)
        
        for ligne in self.lignes.all():
            lignes_dict[ligne.id] = LineBPU(
                id=ligne.id,
                numero=ligne.numero,
                designation=ligne.designation,
                unite=ligne.unite,
                quantite=ligne.quantite,
                pu=ligne.prix_unitaire,
            )

        for ligne in self.lignes.all():
            line_instance = lignes_dict[ligne.id]
            if ligne.parent_id:
                parent_instance = lignes_dict.get(ligne.parent_id)
                if parent_instance:
                    parent_instance.add_child(line_instance)
            else:
                root.add_child(line_instance)
        return root

# ------------------ Lignes de bordereau ---------------------
class LigneBordereau(models.Model):
    lot = models.ForeignKey(LotProjet, on_delete=models.CASCADE, related_name='lignes', verbose_name=_("Lot"))
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='enfants', 
                               verbose_name=_("Ligne parente (optionnel)"))
    
    numero = models.CharField(_("N°"), max_length=20, null=True, blank=True)
    designation = models.TextField(_("Désignation"))
    unite = models.CharField(_("Unité"), max_length=10, null=True, blank=True)
    quantite = models.DecimalField(_("Quantité"), max_digits=10, decimal_places=2)
    prix_unitaire = models.DecimalField(_("Prix unitaire (DH)"), max_digits=12, decimal_places=2)
    montant_calcule = models.DecimalField(_("Montant"), max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    niveau = models.IntegerField(_("Niveau hiérarchique"), default=0)
    est_titre = models.BooleanField(_("Est un titre"), default=False)
    ordre_affichage = models.IntegerField(_("Ordre d'affichage"), default=0)
        
    class Meta:
        verbose_name = _("Ligne de bordereau")
        verbose_name_plural = _("Lignes de bordereau")
        ordering = ['ordre_affichage', 'id']
    
    @property
    def montant(self):
        if self.enfants.exists():
            return sum(enfant.montant for enfant in self.enfants.all())
        return self.quantite * self.prix_unitaire
     
    def get_montant_total(self):
        if self.est_titre:
            total = sum(child.get_montant_total() for child in self.enfants.all())
            return total
        return self.montant_calcule
    
    @property
    def has_children(self):
        return self.enfants.exists()
    
    @property
    def level(self):
        level = 0
        current = self.parent
        while current:
            level += 1
            current = current.parent
        return level
    
    @property
    def is_feuille(self):
        return not self.enfants.exists()
    
    @property
    def is_title(self):
        return not self.numero or not self.unite or (self.quantite is None or self.quantite == 0)
    
    @property
    def get_quantite_deja_realisee(self):
        if self.is_title:
            return Decimal('0')
        
        dernier_att_cette_ligne = self.lignes_attachement.select_related('attachement').order_by(
            '-attachement__date_etablissement', '-id'
        ).first()
        
        if dernier_att_cette_ligne:
            return dernier_att_cette_ligne.quantite_realisee
        return Decimal('0')
    @property
    def montant_realise(self):
        if self.est_titre:
            total = sum(child.montant_realise for child in self.enfants.all())
            return total
        return self.get_quantite_deja_realisee * self.prix_unitaire
    @property
    def quantite_restante(self):
        return self.quantite - self.get_quantite_deja_realisee
    
    def save(self, *args, **kwargs):
        if self.parent:
            self.niveau = self.parent.niveau + 1
        else:
            self.niveau = 0
            
        if not self.est_titre:
            self.montant_calcule = self.quantite * self.prix_unitaire
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.numero} – {self.designation[:30]}"

# ------------------------ Notification ------------------------
class Notification(models.Model):
    TYPE_NOTIFICATION = [
        # TÂCHES (types)
        ('NOUVELLE_TACHE', 'Nouvelle tâche créée'),
        ('TACHE_ASSIGNEE', 'Tâche assignée'),
        ('TACHE_MODIFIEE', 'Tâche modifiée'),
        ('TACHE_TERMINEE', 'Tâche terminée'),
        ('TACHE_URGENTE', 'Tâche devenue urgente'),
        ('TACHE_ECHEANCE', 'Échéance tâche approchante'),
        ('TACHE_EN_RETARD', 'Tâche en retard'),
        
        # PROJETS
        ('RETARD', 'Projet en retard'),
        ('NOUVEAU_AO', "Nouvel appel d'offres"),
        ('RECEPTION', 'Réception validée'),
        ('REUNION', 'Rendez-vous'),
        ('ECHEANCE', 'Échéance approchante'),
        ('PROJET_TERMINE', 'Projet terminé'),
        ('PROJET_ANNULE', 'Projet annulé'),
        ('PROJET_SUSPENDU', 'Projet suspendu'),
        ('PROJET_REOUVERT', 'Projet reouvert'),
        ('PROJET_MODIFIE', 'Projet modifié'),
        ('PROJET_EN_ARRET', 'Projet en arret'),
        ('NOUVEAU_PROJET', 'Nouveau projet'),
        
        # ATTACHEMENTS
        ('ATTACHEMENT_BROUILLON', 'Attachement en cours de travail'),
        ('ATTACHEMENT_TRANSMIS', 'Attachement transmis'),
        ('ATTACHEMENT_MODIFIE', 'Attachement modifié'),
        ('ATTACHEMENT_SUPPRIME', 'Attachement supprimé'),
        ('ATTACHEMENT_VALIDE', 'Attachement validé'),
        ('ATTACHEMENT_REFUSE', 'Attachement refusé'),
        ('NOUVEL_ATTACHEMENT', 'Nouvel attachement créé'),
        ('ATTACHEMENT_SIGNE', 'Attachement en attente'),
                
        # ORDRES DE SERVICE
        ('OS_NOTIFIE', 'Ordre de service notifié'),
        ('OS_ANNULE', 'Ordre de service annulé'),
        ('OS_ECHEANCE', 'Échéance OS approchante'),
        
        # VALIDATIONS
        ('VALIDATION_ATTACHEMENT', 'Validation attachement requise'),
        ('ETAPE_VALIDEE', 'Étape de validation terminée'),
        ('DOCUMENT_A_SIGNER', 'Document à signer'),
        
        # FICHIERS
        ('FICHIER_MODIFIE', 'Fichier modifié'),
        ('FICHIER_SUPPRIME', 'Fichier supprimé'),
        
        # UTILISATEURS
        ('NOUVEL_UTILISATEUR', 'Nouvel utilisateur ajouté'),
        ('ROLE_MODIFIE', 'Rôle modifié'),
        
        ('AUTRE', 'Autre'),
    ]
    
    NIVEAU_URGENCE = [
        ('INFO', 'Information'),
        ('FAIBLE', 'Faible'),
        ('MOYEN', 'Moyen'),
        ('ELEVE', 'Élevé'),
        ('CRITIQUE', 'Critique'),
    ]
    
    # Champs existants
    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    projet = models.ForeignKey('Projet', on_delete=models.CASCADE, null=True, blank=True)
    type_notification = models.CharField(max_length=30, choices=TYPE_NOTIFICATION)
    titre = models.CharField(max_length=100)
    message = models.TextField()
    lue = models.BooleanField(default=False)
    niveau_urgence = models.CharField(max_length=10, choices=NIVEAU_URGENCE, default='MOYEN')
    action_url = models.CharField(max_length=200, blank=True, null=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_echeance = models.DateField(null=True, blank=True)
    date_lue = models.DateTimeField(null=True, blank=True)
    
    # NOUVEAUX CHAMPS
    emetteur = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='notifications_envoyees',
        verbose_name="Émetteur de la notification"
    )
    
    objet_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID de l'objet concerné")
    objet_type = models.CharField(
        max_length=50, 
        blank=True, 
        help_text="Type d'objet (ex: 'tache', 'document', 'reunion')"
    )
    
    expire_le = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Date d'expiration de la notification"
    )
    
    prioritaire = models.BooleanField(
        default=False,
        help_text="Notification prioritaire (s'affiche en premier)"
    )
    
    can_be_closed = models.BooleanField(
        default=True,
        help_text="L'utilisateur peut fermer cette notification"
    )
    
    # Relations optionnelles pour plus de flexibilité
    tache = models.ForeignKey(
        'Tache', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    
    document = models.ForeignKey(
        'DocumentAdministratif', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    
    ordre_service = models.ForeignKey(
        'OrdreService', 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='notifications'
    )
    
    class Meta:
        ordering = ['-prioritaire', '-date_creation']
        indexes = [
            models.Index(fields=['utilisateur', 'lue']),
            models.Index(fields=['utilisateur', 'prioritaire']),
            models.Index(fields=['date_creation']),
            models.Index(fields=['expire_le']),
            models.Index(fields=['type_notification']),
            models.Index(fields=['objet_type', 'objet_id']),
        ]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.titre} - {self.utilisateur.username} ({'Lue' if self.lue else 'Non lue'})"

    def marquer_comme_lue(self, save=True):
        """Marque la notification comme lue"""
        if not self.lue:
            self.lue = True
            self.date_lue = timezone.now()
            if save:
                self.save()
            return True
        return False

    def marquer_comme_non_lue(self, save=True):
        """Marque la notification comme non lue"""
        if self.lue:
            self.lue = False
            self.date_lue = None
            if save:
                self.save()
            return True
        return False

    @property
    def est_recente(self):
        """Vérifie si la notification a été créée il y a moins de 24h"""
        return (timezone.now() - self.date_creation).total_seconds() < 86400  # 24h

    @property
    def est_expiree(self):
        """Vérifie si la notification est expirée"""
        if self.expire_le:
            return timezone.now() > self.expire_le
        return False

    @property
    def jours_restants(self):
        """Retourne le nombre de jours avant expiration"""
        if self.date_echeance:
            delta = self.date_echeance - timezone.now().date()
            return delta.days if delta.days > 0 else 0
        return None

    @property
    def badge_color(self):
        """Retourne la couleur du badge selon le type"""
        colors = {
            'NOUVELLE_TACHE': 'primary',
            'TACHE_ASSIGNEE': 'info',
            'TACHE_TERMINEE': 'success',
            'TACHE_URGENTE': 'danger',
            'TACHE_EN_RETARD': 'warning',
            'OS_NOTIFIE': 'info',
            'OS_ANNULE': 'danger',
            'VALIDATION_ATTACHEMENT': 'warning',
            'DOCUMENT_A_SIGNER': 'primary',
        }
        return colors.get(self.type_notification, 'secondary')

    @property
    def icon_class(self):
        """Retourne la classe d'icône selon le type"""
        icons = {
            'NOUVELLE_TACHE': 'fas fa-tasks',
            'TACHE_ASSIGNEE': 'fas fa-user-check',
            'TACHE_TERMINEE': 'fas fa-check-circle',
            'TACHE_URGENTE': 'fas fa-exclamation-triangle',
            'TACHE_EN_RETARD': 'fas fa-clock',
            'OS_NOTIFIE': 'fas fa-file-contract',
            'OS_ANNULE': 'fas fa-ban',
            'VALIDATION_ATTACHEMENT': 'fas fa-file-upload',
            'DOCUMENT_A_SIGNER': 'fas fa-signature',
            'REUNION': 'fas fa-calendar-alt',
            'ECHEANCE': 'fas fa-calendar-times',
        }
        return icons.get(self.type_notification, 'fas fa-bell')

    def get_absolute_url(self):
        """Retourne l'URL de l'objet concerné"""
        if self.action_url:
            return self.action_url
        projet_id = self.projet.id
        # URLs par défaut selon le type d'objet
        url_map = {
            'tache': f'/taches/{self.objet_id}', # path('taches/<int:pk>/', views.DetailTacheView.as_view(), name='detail_tache'),
            'document': f'document/{self.objet_id}/afficher/', #path('document/<int:document_id>/afficher/', views.AfficherDocumentView.as_view(), name='afficher_document'), 
            'projet': f'/projet/{projet_id}/dashboard', #path('projet/<int:projet_id>/dashboard/', views.dashboard_projet, name='dashboard'),
            'ordre_service': f'/projet/{projet_id}/ordres-service/{self.objet_id}/details/', # path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/details/', views.details_ordre_service, name='details_ordre_service'),
        }
        
        return url_map.get(self.objet_type, '#')

    # ==================== MÉTHODES DE CLASSE NOTIFICATION ====================

    @classmethod
    def creer_notification_tache(cls, tache, type_notif, emetteur=None, utilisateurs_cibles=None):
        """Crée une notification pour une tâche"""
        if utilisateurs_cibles is None:
            # Par défaut, notifier le responsable et les utilisateurs du projet
            utilisateurs_cibles = set(tache.projet.users.all())
            if tache.responsable:
                utilisateurs_cibles.add(tache.responsable)
        
        titre_map = {
            'NOUVELLE_TACHE': f"Nouvelle tâche : {tache.titre}",
            'TACHE_ASSIGNEE': f"Tâche assignée : {tache.titre}",
            'TACHE_MODIFIEE': f"Tâche modifiée : {tache.titre}",
            'TACHE_TERMINEE': f"Tâche terminée : {tache.titre}",
            'TACHE_URGENTE': f"⚠️ Tâche urgente : {tache.titre}",
            'TACHE_ECHEANCE': f"Échéance approchante : {tache.titre}",
            'TACHE_EN_RETARD': f"Tâche en retard : {tache.titre}",
        }
        
        message_map = {
            'NOUVELLE_TACHE': f"Une nouvelle tâche a été créée dans le projet {tache.projet.nom}",
            'TACHE_ASSIGNEE': f"Vous avez été assigné à la tâche '{tache.titre}'",
            'TACHE_MODIFIEE': f"La tâche '{tache.titre}' a été modifiée",
            'TACHE_TERMINEE': f"La tâche '{tache.titre}' a été marquée comme terminée",
            'TACHE_URGENTE': f"La tâche '{tache.titre}' a été marquée comme URGENTE",
            'TACHE_ECHEANCE': f"La tâche '{tache.titre}' approche de son échéance ({tache.date_fin})",
            'TACHE_EN_RETARD': f"La tâche '{tache.titre}' est en retard de {tache.jours_retard} jour(s)",
        }
        
        niveau_urgence_map = {
            'NOUVELLE_TACHE': 'MOYEN',
            'TACHE_ASSIGNEE': 'MOYEN',
            'TACHE_MODIFIEE': 'FAIBLE',
            'TACHE_TERMINEE': 'INFO',
            'TACHE_URGENTE': 'CRITIQUE',
            'TACHE_ECHEANCE': 'ELEVE',
            'TACHE_EN_RETARD': 'CRITIQUE',
        }
        
        notifications = []
        for user in utilisateurs_cibles:
            notification = cls(
                utilisateur=user,
                projet=tache.projet,
                tache=tache,
                emetteur=emetteur,
                type_notification=type_notif,
                titre=titre_map.get(type_notif, f"Notification tâche"),
                message=message_map.get(type_notif, f"Notification pour la tâche {tache.titre}"),
                niveau_urgence=niveau_urgence_map.get(type_notif, 'MOYEN'),
                action_url=f"/taches/{tache.id}/",
                objet_id=tache.id,
                objet_type='tache',
                date_echeance=tache.date_fin if type_notif in ['TACHE_ECHEANCE', 'TACHE_EN_RETARD'] else None,
                prioritaire=type_notif in ['TACHE_URGENTE', 'TACHE_EN_RETARD'],
                can_be_closed=type_notif not in ['TACHE_URGENTE', 'TACHE_EN_RETARD']
            )
            notifications.append(notification)
        
        cls.objects.bulk_create(notifications)
            
        return notifications

    @classmethod
    def creer_notification_projet(cls, projet, type_notif, emetteur=None, utilisateurs_cibles=None):
        """Crée une notification pour un projet"""
        if utilisateurs_cibles is None:
            utilisateurs_cibles = projet.users.all()
        
        titre_map = {
            'RETARD': f"⏰ Projet en retard: {projet.nom}",
            'NOUVEAU_AO': f"📄 Nouvel appel d'offres: {projet.nom}",
            'RECEPTION': f"✅ Réception validée: {projet.nom}",
            'ECHEANCE': f"📅 Échéance approchante: {projet.nom}",
            'REUNION': f"👥 Rendez-vous projet: {projet.nom}",
        }
        
        message_map = {
            'RETARD': f"Le projet {projet.nom} ({projet.numero}) est en retard.",
            'NOUVEAU_AO': f"Un nouvel appel d'offres a été créé pour le projet {projet.nom}.",
            'RECEPTION': f"La réception du projet {projet.nom} a été validée.",
            'ECHEANCE': f"L'échéance du projet {projet.nom} approche ({projet.date_limite_soumission}).",
            'REUNION': f"Un nouveau rendez-vous a été planifié pour le projet {projet.nom}.",
        }
        
        notifications = []
        for user in utilisateurs_cibles:
            notification = cls(
                utilisateur=user,
                projet=projet,
                emetteur=emetteur,
                type_notification=type_notif,
                titre=titre_map.get(type_notif, f"Notification projet"),
                message=message_map.get(type_notif, f"Notification pour le projet {projet.nom}"),
                action_url=f"/projets/{projet.id}/",
                objet_id=projet.id,
                objet_type='projet',
                date_echeance=projet.date_limite_soumission if type_notif == 'ECHEANCE' else None,
                prioritaire=type_notif in ['RETARD', 'ECHEANCE'],
                can_be_closed=True
            )
            notifications.append(notification)
        
        cls.objects.bulk_create(notifications)
        return notifications

    @classmethod
    def creer_notification_os(cls, ordre_service, type_notif, emetteur=None, utilisateurs_cibles=None):
        """Crée une notification pour un ordre de service"""
        if utilisateurs_cibles is None:
            # Notifier les utilisateurs du projet et les admins
            from django.db.models import Q
            utilisateurs_cibles = User.objects.filter(
                Q(profile__projets=ordre_service.projet) | 
                Q(profile__role__in=['ADMIN', 'CHEF_PROJET'])
            ).distinct()
        
        titre_map = {
            'OS_NOTIFIE': f"📋 OS notifié: {ordre_service.reference}",
            'OS_ANNULE': f"❌ OS annulé: {ordre_service.reference}",
            'OS_ECHEANCE': f"⏰ Échéance OS: {ordre_service.reference}",
        }
        
        message_map = {
            'OS_NOTIFIE': f"L'ordre de service {ordre_service.reference} - {ordre_service.titre} a été notifié pour le projet {ordre_service.projet.nom}.",
            'OS_ANNULE': f"L'ordre de service {ordre_service.reference} - {ordre_service.titre} a été annulé pour le projet {ordre_service.projet.nom}.",
            'OS_ECHEANCE': f"L'échéance de l'ordre de service {ordre_service.reference} approche ({ordre_service.date_limite}).",
        }
        
        notifications = []
        for user in utilisateurs_cibles:
            notification = cls(
                utilisateur=user,
                projet=ordre_service.projet,
                ordre_service=ordre_service,
                emetteur=emetteur,
                type_notification=type_notif,
                titre=titre_map.get(type_notif, "Notification OS"),
                message=message_map.get(type_notif, f"Notification pour l'OS {ordre_service.reference}"),
                action_url=f"/ordres-service/{ordre_service.id}/",
                objet_id=ordre_service.id,
                objet_type='ordre_service',
                date_echeance=ordre_service.date_limite if type_notif == 'OS_ECHEANCE' else None,
                prioritaire=type_notif in ['OS_ANNULE', 'OS_ECHEANCE'],
                can_be_closed=True
            )
            notifications.append(notification)
        
        cls.objects.bulk_create(notifications)
        return notifications

    @classmethod
    def nettoyer_notifications_expirees(cls):
        """Supprime les notifications expirées"""
        expired = cls.objects.filter(expire_le__lt=timezone.now())
        count = expired.count()
        expired.delete()
        return count

    @classmethod
    def marquer_toutes_comme_lues(cls, utilisateur):
        """Marque toutes les notifications d'un utilisateur comme lues"""
        updated = cls.objects.filter(
            utilisateur=utilisateur, 
            lue=False
        ).update(
            lue=True, 
            date_lue=timezone.now()
        )
        return updated

    @classmethod
    def get_notifications_non_lues(cls, utilisateur):
        """Retourne les notifications non lues d'un utilisateur"""
        return cls.objects.filter(
            utilisateur=utilisateur,
            lue=False,
            expire_le__isnull=True
        ).exclude(
            expire_le__lt=timezone.now()
        ).order_by('-prioritaire', '-date_creation')

    @classmethod
    def get_statistiques(cls, utilisateur):
        """Retourne des statistiques sur les notifications"""
        notifications = cls.objects.filter(utilisateur=utilisateur)
        
        return {
            'total': notifications.count(),
            'non_lues': notifications.filter(lue=False).count(),
            'prioritaires': notifications.filter(prioritaire=True, lue=False).count(),
            'urgentes': notifications.filter(niveau_urgence='CRITIQUE', lue=False).count(),
            'recentes': notifications.filter(date_creation__gte=timezone.now() - timedelta(days=1)).count(),
        }
# ------------------------ Client ------------------------
class Client(models.Model):
    nom = models.CharField(max_length=100)
    contact = models.CharField(max_length=150, blank=True)
    email = models.EmailField(_("Email"), blank=True)
    telephone = models.CharField(_("Téléphone"), max_length=20, blank=True)
    adresse = models.TextField(_("Adresse"), blank=True)
    
    def __str__(self):
        return self.nom

# ------------------------ Ingenieur ------------------------
class Ingenieur(models.Model):
    nom = models.CharField(max_length=100)

    def __str__(self):
        return self.nom

# ------------------------ Suivi d'exécution ------------------------
class SuiviExecution(models.Model):
    TYPE_SUIVI_CHOICES = [
        ('reunion', _('Réunion de chantier')),
        ('incident', _('Incident')),
        ('planning', _('Mise à jour planning')),
        ('livraison', _('Livraison')),
        ('validation', _('Validation d\'étape')),
        ('courrier', _('Courrier')),
        ('autre', _('Autre')),
    ]
    
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name='suivis_execution', verbose_name=_("Projet"))
    date = models.DateField(_("Date de suivi"), default=timezone.now)
    titre = models.CharField(_("Titre"), max_length=200)
    type_suivi = models.CharField(_("Type"), max_length=100, choices=TYPE_SUIVI_CHOICES)
    
    commentaire = models.TextField(_("Commentaire ou résumé"))
    redacteur = models.CharField(_("Rédigé par"), max_length=100, blank=True)
    
    date_creation = models.DateTimeField(_("Date de création"), default=timezone.now)
    date_modification = models.DateTimeField(_("Dernière modification"), default=timezone.now)
    importance = models.CharField(_("Importance"), max_length=10, choices=[
        ('faible', _('Faible')),
        ('moyenne', _('Moyenne')),
        ('elevee', _('Élevée')),
    ], default='moyenne')

    class Meta:
        verbose_name = _("Suivi d'exécution")
        verbose_name_plural = _("Suivis d'exécution")
        ordering = ['-date', '-date_creation']

    def __str__(self):
        return f"{self.date} - {self.titre} ({self.projet.nom})"
    def delete(self, *args, **kwargs):
        """
        Supprime le suivi et TOUS ses fichiers associés
        (Cloudinary ou local)
        """
        
        for fichier_suivi in self.fichiers.all(): 
            fichier_suivi.delete()  # Utilise la méthode delete de FichierSuivi
        
        # 2. Puis supprimer le suivi lui-même
        super().delete(*args, **kwargs)
        
class FichierSuivi(models.Model):
    def upload_path(instance, filename):
        return f'suivis_execution/projet_{instance.suivi.projet.id}/{instance.suivi.id}/{filename}'
    
    suivi = models.ForeignKey(SuiviExecution, on_delete=models.CASCADE, related_name='fichiers', verbose_name=_("Suivi"))
    
    # Champ compatible Cloudinary
    if getattr(settings, 'USE_CLOUDINARY', False):
        from cloudinary.models import CloudinaryField
        fichier = CloudinaryField('raw', folder='suivis_execution', resource_type='raw', default=None)
    else:
        fichier = models.FileField(_("Fichier"), upload_to=upload_path)
    original_filename = models.CharField(max_length=255, blank=True, verbose_name="Nom de fichier original")
    description = models.CharField(_("Description"), max_length=255, blank=True)
    date_ajout = models.DateTimeField(_("Date d'ajout"), default=timezone.now)
    @property
    def get_public_id(self):
        if getattr(settings, 'USE_CLOUDINARY', False):
            return self.fichier.public_id + '.' + self.fichier.format
    class Meta:
        verbose_name = _("Fichier joint au suivi")
        verbose_name_plural = _("Fichiers joints au suivi")
        ordering = ['-date_ajout']
    @property
    def get_file_name(self):
        if self.original_filename:
            return self.original_filename
        elif self.fichier:
            if getattr(settings, 'USE_CLOUDINARY', False):
                return self.__str__()
            return os.path.basename(self.fichier.name)
        return ""
    def __str__(self):
        return f"{self.fichier.name}"
