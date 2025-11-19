from decimal import Decimal
import os
from django.db import models
from django.db.models import Sum
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_save, pre_delete
from django.utils import timezone
# ------------------------ Profile ------------------------ #
def avatar_upload_path(instance, filename):
    """Génère un chemin unique pour l'avatar"""
    # Obtenir l'extension du fichier
    ext = filename.split('.')[-1]
    # Créer un nom de fichier unique
    filename = f"{instance.user.username}_avatar_{instance.user.id}.{ext}"
    return os.path.join('avatars', filename)

from django.core.files.storage import default_storage
class Profile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrateur'),
        ('CHEF_PROJET', 'Chef de Projet'),
        ('UTILISATEUR', 'Utilisateur'),
        
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='UTILISATEUR'
    )
    
    avatar = models.ImageField(
        upload_to=avatar_upload_path, 
        default='avatars/default.png',
        blank=True
    )
    
    def __str__(self):
        return f"{self.user.username} Profile"
    
    @property
    def avatar_url(self):
        """
        Retourne l'URL de l'avatar ou l'avatar par défaut
        Vérifie d'abord si le fichier existe physiquement
        """
        if self.avatar and hasattr(self.avatar, 'url') and self.avatar.name != 'avatars/default.png':
            # Vérifier si le fichier existe réellement
            if default_storage.exists(self.avatar.name):
                return self.avatar.url
        return '/static/images/default_avatar.png'
    
    def save(self, *args, **kwargs):
        """Surcharge de la méthode save pour gérer les anciens avatars"""
        # Si c'est une mise à jour et qu'un avatar existait déjà
        if self.pk:
            try:
                old_profile = Profile.objects.get(pk=self.pk)
                if old_profile.avatar and old_profile.avatar != self.avatar:
                    # Supprimer l'ancien avatar s'il existe
                    if default_storage.exists(old_profile.avatar.name):
                        default_storage.delete(old_profile.avatar.name)
            except Profile.DoesNotExist:
                pass
        super().save(*args, **kwargs)

# Signaux pour gérer la création/suppression des profils et avatars
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Créer un profil automatiquement quand un utilisateur est créé"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Sauvegarder le profil quand l'utilisateur est sauvegardé"""
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver(pre_delete, sender=Profile)
def delete_avatar_file(sender, instance, **kwargs):
    """Supprimer le fichier avatar quand le profil est supprimé"""
    if instance.avatar and instance.avatar.name != 'avatars/default.png':
        if default_storage.exists(instance.avatar.name):
            default_storage.delete(instance.avatar.name)

@receiver(pre_delete, sender=User)
def delete_user_profile(sender, instance, **kwargs):
    """Supprimer le profil quand l'utilisateur est supprimé"""
    if hasattr(instance, 'profile'):
        instance.profile.delete()

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
from django.db.models import Q
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
    
        # Ajoutez un paramètre pour éviter la récursion
        update_flags = kwargs.pop('update_flags', True)
        
        # Sauvegarde initiale
        super().save(*args, **kwargs)
        
        # Mise à jour des flags si demandé et si pas déjà en cours
        if update_flags and not getattr(self, '_updating_flags', False):
            try:
                self._updating_flags = True
                self.update_status_flags(force_save=False)
            finally:
                delattr(self, '_updating_flags')
    def update_status_flags(self, force_save=True):
        """Met à jour les indicateurs de statut pour la page d'accueil"""
        # Vérification des projets en retard
        if self.date_debut and self.delai and self.statut in [self.Statut.EN_COURS, self.Statut.EN_ARRET]:
            date_limite = self.date_debut + timedelta(days=self.delai)
            self.en_retard = date.today() > date_limite and self.avancement < 100
        
        # Vérification des nouveaux appels d'offres
        self.a_traiter = self.statut == self.Statut.APPEL_OFFRE and self.date_limite_soumission and self.date_limite_soumission >= date.today()
        
        # Vérification des réceptions validées
        self.reception_validee = self.statut in [self.Statut.RECEPTION_PROVISOIRE, self.Statut.RECEPTION_DEFINITIVE, self.Statut.CLOTURE]
        
        if force_save:
            self.save(update_flags=False)  # On désactive la mise à jour des flags pour éviter la récursion
    def get_type_echeance_display(self):
        if self.statut == 'AO':
            return "Appel d'offres"
        elif self.statut in ['RECEP', 'RECEP_DEF']:
            return "Réception"
        return "Échéance"
    def montant_total(self, force_update=False):
        """
        Calcule le montant total et synchronise le champ si nécessaire.
        
        Args:
            force_update: Force la mise à jour même si les montants semblent égaux
        """
        try:
            # Calcul du nouveau montant
            total_lots = sum(lot.montant_total_ht for lot in self.lots.all()) 
            nouveau_montant = total_lots * Decimal('1.2')
            
            # Conversion pour comparaison fiable
            ancien_montant = self.montant or Decimal('0')
            
            # Comparaison décimale sécurisée
            montants_different = abs(ancien_montant - nouveau_montant) > Decimal('0.01')
            
            if force_update or montants_different:
                # Mise à jour sans risque de récursion
                from django.db import transaction
                
                with transaction.atomic():
                    Projet.objects.filter(id=self.id).update(montant=nouveau_montant)
                    self.montant = nouveau_montant  # Mise à jour de l'instance
                
            return nouveau_montant
            
        except Exception as e:
            # Gestion d'erreur robuste
            print(f"Erreur calcul montant projet {self.id}: {e}")
            return self.montant or Decimal('0')
    @property
    def marche_approuve(self):
        """Le Marché est approuvé si l'entrepreneur a été notifié de l'approbation du marché"""
        return self.ordres_service.filter(
            type_os__code='OSN',
            statut='NOTIFIE'
        ).exists()
    
    @property
    def projet_demarre(self):
        """Projet a démarré si l'entrepreneur est notifié pour démarrer les travaux"""
        return self.ordres_service.filter(
            type_os__code='OSC',
            statut='NOTIFIE'
        ).exists()
    
    @property
    def projet_en_arret(self):
        """
        Projet en arrêt s'il existe un OS d'Arrêt notifié 
        et qu'aucun OS de Reprise plus récent n'existe
        """
        # Dernier OSA notifié
        dernier_osa = self.ordres_service.filter(
            type_os__code='OSA', 
            statut='NOTIFIE'
        ).order_by('-ordre_sequence').first()
        
        if not dernier_osa:
            return False
        
        # Dernier OSR notifié (tout OSR, pas seulement après OSA)
        dernier_osr = self.ordres_service.filter(
            type_os__code='OSR', 
            statut='NOTIFIE'
        ).order_by('-ordre_sequence').first()
        
        # Le projet est en arrêt si :
        # - Il y a un OSA
        # - ET soit pas d'OSR, soit l'OSA est plus récent que l'OSR
        return not dernier_osr or dernier_osa.ordre_sequence > dernier_osr.ordre_sequence
    @property
    def projet_en_cours(self):
        """Projet est en cours s'il n'y a pas d'arrêt"""
        return not self.projet_en_arret
    
    @property
    def statut_workflow(self):
        """Retourne le statut textuel du projet"""
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
        """Retourne l'avancement en pourcentage du projet"""
        montant_total = self.montant_total()
        dernier_attachement = self.attachements.order_by('-id').first()
        montant_attachements = dernier_attachement.total_montant_ht if dernier_attachement else 0
        if montant_total > 0:
            return round((montant_attachements / montant_total) * 100)
        return 0
    def jours_decoules_depuis_demarrage(self, date_reference=None):
        """
        Calcule les jours découlés depuis le démarrage en excluant les périodes d'arrêt
        selon la séquence des OSA (arrêt) et OSR (reprise)
        """
        # Date de reference
        if date_reference is None:
            date_reference = timezone.now().date()
        
        # Trouver l'OSC notifié (démarrage)
        osc = self.ordres_service.filter(
            type_os__code='OSC',
            statut='NOTIFIE'
        ).order_by('ordre_sequence').first()
        
        if not osc or not osc.date_effet:
            return None  # Projet non démarré
        
        date_demarrage = osc.date_effet
        
        if date_reference < date_demarrage:
            return 0
        
        # Récupérer tous les OSA et OSR notifiés, triés par date d'effet
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
        en_arret = False  # État initial : en cours
        
        for evenement in evenements:
            if evenement.type_os.code == 'OSA' and not en_arret:
                # Début d'une période d'arrêt
                jours_periode = (evenement.date_effet - date_debut_periode).days
                jours_total += max(0, jours_periode)
                date_debut_periode = evenement.date_effet
                en_arret = True
                
            elif evenement.type_os.code == 'OSR' and en_arret:
                # Fin d'une période d'arrêt
                date_debut_periode = evenement.date_effet
                en_arret = False
        
        # Gérer la dernière période
        if not en_arret:
            # Période en cours jusqu'à la date de référence
            jours_derniere_periode = (date_reference - date_debut_periode).days
            jours_total += max(0, jours_derniere_periode)
        # Si en arrêt à la date de référence, on n'ajoute pas les jours d'arrêt
        
        return jours_total
    
    def jours_decoules_aujourdhui(self):
        """Retourne les jours découlés jusqu'à aujourd'hui"""
        return self.jours_decoules_depuis_demarrage()
    
    def get_historique_periodes(self, date_reference=None):
        """Retourne le détail des périodes pour debug"""
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
        
        # Dernière période
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
        """Retourne le nombre de jours restants avant la date limite"""
        if self.date_limite_soumission:
            return (self.date_limite_soumission - date.today()).days
        return None

    @property
    def retard_jours(self):
        """Retourne le nombre de jours de retard"""
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
from django.core.exceptions import ValidationError
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
    documents = models.FileField(upload_to='ordres_services/', null=True, blank=True)
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

    def __str__(self):
        return f"{self.reference} - {self.titre}"
    def save(self, *args, **kwargs):
        # Déterminer l'ordre dans la séquence
        if not self.ordre_sequence:
            dernier_ordre = OrdreService.objects.filter(
                projet=self.projet
            ).aggregate(models.Max('ordre_sequence'))['ordre_sequence__max'] or 0
            self.ordre_sequence = dernier_ordre + 1
        
        # Ne pas appeler full_clean() ici
        # La validation sera faite manuellement dans les vues quand nécessaire
        super().save(*args, **kwargs)
    def clean(self):
        super().clean()
        errors = {}
        
        # Vérifier si l'objet est prêt pour la validation
        if not self.pk or not hasattr(self, 'projet') or self.projet is None:
            return
        
        # Validation des contraintes métier
        if self.statut == 'NOTIFIE':
            # Vérification des prérequis
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
            
            # Vérification unicité
            if self.type_os.unique_dans_projet:
                existing = OrdreService.objects.filter(
                    projet=self.projet,
                    type_os=self.type_os,
                    statut='NOTIFIE'
                ).exclude(pk=self.pk)
                if existing.exists():
                    errors['type_os'] = f"Un {self.type_os.nom} existe déjà pour ce projet"
            
            # Vérification séquenceOSAR/OSR
            if self.type_os.code == 'OSA':
                dernier_os = OrdreService.objects.filter(
                    projet=self.projet,
                    statut='NOTIFIE'
                ).exclude(pk=self.pk).order_by('-ordre_sequence').first()
                
                if dernier_os and dernier_os.type_os.code == 'OSA':
                    errors['type_os'] = "Un OS d'arrêt ne peut pas suivre un autre OS d'arrêt"
            
            # Vérification OSR après OSA
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
    @property
    def influence_delai(self):
        """Détermine si cet OS influence le délai du projet"""
        return self.type_os.code in ['OSC', 'OSA', 'OSR']

    @property
    def influence_budget(self):
        """Détermine si cet OS influence le budget du projet"""
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
        """Retourne le nombre de jours restants avant la date de fin"""
        if self.date_fin:
            return (self.date_fin - date.today()).days
        return None

# ------------------ Documents administratifs ----------------
def document_upload_path(instance, filename):
    # Génère un chemin unique: documents_administratifs/projet_<id>/<nom_fichier>
    return f'documents_administratifs/projet_{instance.projet.id}/{filename}'
class DocumentAdministratif(models.Model):
    """Modèle pour les documents administratifs"""
    projet = models.ForeignKey('Projet', on_delete=models.CASCADE, related_name='documents_administratifs', verbose_name=_("Projet"))
    fichier = models.FileField(_("Fichier"), upload_to=document_upload_path)  # Utilise la fonction
    type_document = models.CharField(_("Type de document"), max_length=100)
    date_remise = models.DateField(_("Date de remise"), null=True, blank=True)
    
    class Meta:
        verbose_name = _("Document administratif")
        verbose_name_plural = _("Documents administratifs")
        ordering = ['type_document']

    def __str__(self):
        return f"{self.type_document} - {self.projet.nom}"

    # Méthode utilitaire pour obtenir l'extension du fichier
    def get_file_extension(self):
        return os.path.splitext(self.fichier.name)[1][1:].upper() if self.fichier else ''
def clean_empty_dirs(start_path):
    """Supprime récursivement les dossiers vides à partir de start_path"""
    for root, dirs, files in os.walk(start_path, topdown=False):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            try:
                if not os.listdir(dir_path):  # Si le dossier est vide
                    os.rmdir(dir_path)
            except (OSError, PermissionError):
                pass  # Ignorer les erreurs de permission    
            
@receiver(pre_delete, sender=DocumentAdministratif)
def delete_document_file(sender, instance, **kwargs):
    """Supprime le fichier physique lorsque l'objet DocumentAdministratif est supprimé"""
    if instance.fichier:
        file_path = instance.fichier.path
        if os.path.isfile(file_path):
            # Sauvegarder le chemin du dossier parent pour nettoyage
            parent_dir = os.path.dirname(file_path)
            os.remove(file_path)
            
            # Nettoyer les dossiers vides (optionnel)
            from django.conf import settings
            clean_empty_dirs(settings.MEDIA_ROOT)

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
        """Insère un enfant à une position spécifique"""
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
        return f"{self.id} - {self.numero} - {self.designation} | {self.unite} | {self.quantite} | {self.pu} | {self.amount()}"
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
        # Utilisation de l'agrégation pour optimiser la performance
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
    def to_line_tree(self):
        """Convertit les lignes du lot en une structure hiérarchique de Line"""
        lignes_dict = {}
        root = Line(numero="Root", designation=self.nom)
        # Créer des instances Line pour chaque LigneBordereau
        for ligne in self.lignes.all():
            lignes_dict[ligne.id] = LineBPU(
                id=ligne.id,
                numero=ligne.numero,
                designation=ligne.designation,
                unite=ligne.unite,
                quantite=ligne.quantite,
                pu=ligne.prix_unitaire,
            )

        # Établir les relations parent-enfant
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
    # Champ pour stocker le montant calculé, pour une meilleure performance d'agrégation
    montant_calcule = models.DecimalField(_("Montant"), max_digits=15, decimal_places=2, default=Decimal('0.00'))
    
    # Nouveaux champs pour l'hiérarchie
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
        """Retourne le montant total incluant les enfants"""
        if self.est_titre:
            total = sum(child.get_montant_total() for child in self.enfants.all())
            return total
        return self.montant_calcule
    
    @property
    def has_children(self):
        return self.enfants.exists()
    
    @property
    def is_feuille(self):
        # Une ligne est considérée comme une feuille si elle n'a pas d'enfants
        return not self.enfants.exists()
    
    @property
    def is_title (self):
        # Une ligne est considérée comme un titre si elle n'a pas d'unité, de quantité et de prix unitaire
        return  not self.numero or not self.unite or (self.quantite is None or self.quantite == 0) 
    @property
    def get_quantite_deja_realisee(self):
        """Retourne la dernière quantité réalisée cumulée pour cette ligne"""
        if self.is_title:
            return Decimal('0')
        
        # Récupérer la dernière ligne attachement (la plus récente)
        dernier_att_cette_ligne = self.lignes_attachement.select_related('attachement').order_by(
            '-attachement__date_etablissement', '-id'
        ).first()
        
        if dernier_att_cette_ligne:
            return dernier_att_cette_ligne.quantite_realisee
        return Decimal('0')
    
    @property
    def quantite_restante(self):
        """Retourne la quantité restante à réaliser"""
        return self.quantite - self.get_quantite_deja_realisee
    
    def save(self, *args, **kwargs):
        # Calcul automatique du niveau hiérarchique
        if self.parent:
            self.niveau = self.parent.niveau + 1
        else:
            self.niveau = 0
            
        # Calcul automatique du montant
        if not self.est_titre:
            self.montant_calcule = self.quantite * self.prix_unitaire
        else:
            self.montant_calcule = Decimal('0.00')
        super().save(*args, **kwargs)
        
    def __str__(self):
        return f"{self.numero} – {self.designation[:30]}"

# ------------------------ Notification ------------------------
class Notification(models.Model):
    TYPE_NOTIFICATION = [
        ('RETARD', 'Projet en retard'),
        ('NOUVEAU_AO', "Nouvel appel d'offres"),
        ('RECEPTION', 'Réception validée'),
        ('REUNION', 'Rendez-vous'),
        ('ECHEANCE', 'Échéance approchante'),
        ('OS_NOTIFIE', 'Ordre de service notifié'),  # ← OS
        ('OS_ANNULE', 'Ordre de service annulé'),    # ← OS
        ('OS_ECHEANCE', 'Échéance OS approchante'),  # ← OS
        ('AUTRE', 'Autre'),
    ]

    utilisateur = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, null=True, blank=True)
    type_notification = models.CharField(max_length=20, choices=TYPE_NOTIFICATION)
    titre = models.CharField(max_length=100)
    message = models.TextField()
    lue = models.BooleanField(default=False)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_echeance = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['-date_creation']
        verbose_name = _("Notification")
        verbose_name_plural = _("Notifications")

    def __str__(self):
        return f"{self.titre} - {self.utilisateur.username}"

    @classmethod
    def creer_notification_projet(cls, projet: Projet, type_notif):
        """Crée une notification pour tous les utilisateurs concernés par un projet"""
        # Ici vous pourriez cibler seulement les utilisateurs concernés (chefs de projet, etc.)
        users = User.objects.all()  # Ou une logique plus fine pour cibler les bons utilisateurs
        titre_map = {
            'RETARD': f"Projet en retard: {projet.nom}",
            'NOUVEAU_AO': f"Nouvel appel d'offres: {projet.nom}",
            'RECEPTION': f"Réception validée: {projet.nom}",
            'ECHEANCE': f"Échéance approchante: {projet.nom}",
        }
        
        for user in users:
            cls.objects.create(
                utilisateur=user,
                projet=projet,
                type_notification=type_notif,
                titre=titre_map.get(type_notif, "Notification projet"),
                message=f"Le projet {projet.nom} ({projet.numero}) nécessite votre attention.",
                date_echeance=projet.date_limite_soumission if type_notif == 'ECHEANCE' else None
            )

    @classmethod
    def creer_notification_os(cls, ordre_service, type_notif, utilisateurs_cibles=None):
        """Crée une notification pour un ordre de service spécifique"""
        if utilisateurs_cibles is None:
            # Cibler par défaut les utilisateurs liés au projet
            from django.db.models import Q
            utilisateurs_cibles = User.objects.filter(
                Q(profile__projets=ordre_service.projet) | 
                Q(profile__role__in=['ADMIN', 'CHEF_PROJET'])
            ).distinct()
        
        titre_map = {
            'OS_NOTIFIE': f"OS notifié: {ordre_service.reference}",
            'OS_ANNULE': f"OS annulé: {ordre_service.reference}",
            'OS_ECHEANCE': f"Échéance OS: {ordre_service.reference}",
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
                type_notification=type_notif,
                titre=titre_map.get(type_notif, "Notification OS"),
                message=message_map.get(type_notif, f"Notification pour l'OS {ordre_service.reference}"),
                date_echeance=ordre_service.date_limite if type_notif == 'OS_ECHEANCE' else None
            )
            notifications.append(notification)
        
        # Créer en bulk pour plus d'efficacité
        cls.objects.bulk_create(notifications)
        
        return len(notifications)
@receiver(post_save, sender=Projet)
def gerer_notifications_projet(sender, instance: Projet, created, **kwargs):
    """Gère la création des notifications lors des changements de statut d'un projet"""
    if not created:
        # Vérifier les changements qui nécessitent des notifications
        ancien_projet = Projet.objects.get(pk=instance.pk)
        
        # Notification pour les projets en retard
        if instance.en_retard and not ancien_projet.en_retard:
            Notification.creer_notification_projet(instance, 'RETARD')
        
        # Notification pour les nouveaux AO
        if instance.a_traiter and not ancien_projet.a_traiter:
            Notification.creer_notification_projet(instance, 'NOUVEAU_AO')
        
        # Notification pour les réceptions validées
        if instance.reception_validee and not ancien_projet.reception_validee:
            Notification.creer_notification_projet(instance, 'RECEPTION')
        
        # Notification pour les échéances approchantes (7 jours avant)
        if instance.date_limite_soumission and instance.date_limite_soumission != ancien_projet.date_limite_soumission:
            jours_restants = (instance.date_limite_soumission - date.today()).days
            if 0 < jours_restants <= 7:
                Notification.creer_notification_projet(instance, 'ECHEANCE')

@receiver(pre_save, sender=Projet)
def mettre_a_jour_indicateurs(sender, instance, **kwargs):
    """Met à jour les indicateurs avant la sauvegarde"""
    """Version sécurisée du signal"""
    if not getattr(instance, '_updating_flags', False):
        instance.update_status_flags(force_save=False)

@receiver(post_save, sender=OrdreService)
def gerer_notifications_os(sender, instance: OrdreService, created, **kwargs):
    """Gère la création des notifications pour les ordres de service"""
    
    if created:
        # Notification pour nouvel OS créé (en brouillon)
        Notification.creer_notification_os(
            instance, 
            'AUTRE',
            utilisateurs_cibles=User.objects.filter(
                profile__role__in=['ADMIN', 'CHEF_PROJET']
            )
        )
    
    else:
        # Vérifier les changements de statut
        try:
            ancien_os = OrdreService.objects.get(pk=instance.pk)
            
            # Notification pour OS notifié
            if instance.statut == 'NOTIFIE' and ancien_os.statut != 'NOTIFIE':
                Notification.creer_notification_os(instance, 'OS_NOTIFIE')
            
            # Notification pour OS annulé
            elif instance.statut == 'ANNULE' and ancien_os.statut != 'ANNULE':
                Notification.creer_notification_os(instance, 'OS_ANNULE')
                
        except OrdreService.DoesNotExist:
            pass

@receiver(post_save, sender=OrdreService)
def verifier_echeances_os(sender, instance: OrdreService, **kwargs):
    """Vérifie les échéances des OS et crée des notifications si nécessaire"""
    if instance.date_limite:
        jours_restants = (instance.date_limite - timezone.now().date()).days
        
        # Notification 7 jours avant l'échéance
        if jours_restants == 7:
            Notification.creer_notification_os(instance, 'OS_ECHEANCE')
        
        # Notification 1 jour avant l'échéance
        elif jours_restants == 1:
            Notification.creer_notification_os(instance, 'OS_ECHEANCE')
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
        ('autre', _('Autre')),
    ]
    
    projet = models.ForeignKey(Projet, on_delete=models.CASCADE, related_name='suivis_execution', verbose_name=_("Projet"))
    date = models.DateField(_("Date de suivi"), default=timezone.now)
    titre = models.CharField(_("Titre"), max_length=200)
    type_suivi = models.CharField(_("Type"), max_length=100, choices=TYPE_SUIVI_CHOICES)
    
    commentaire = models.TextField(_("Commentaire ou résumé"))
    redacteur = models.CharField(_("Rédigé par"), max_length=100, blank=True)
    
    # Nouveaux champs pour améliorer le suivi
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

class FichierSuivi(models.Model):
    def upload_path(instance, filename):
        return f'suivis_execution/projet_{instance.suivi.projet.id}/{instance.suivi.id}/{filename}'
    
    suivi = models.ForeignKey(SuiviExecution, on_delete=models.CASCADE, related_name='fichiers', verbose_name=_("Suivi"))
    fichier = models.FileField(_("Fichier"), upload_to=upload_path)
    description = models.CharField(_("Description"), max_length=255, blank=True)
    date_ajout = models.DateTimeField(_("Date d'ajout"), default=timezone.now)

    class Meta:
        verbose_name = _("Fichier joint au suivi")
        verbose_name_plural = _("Fichiers joints au suivi")
        ordering = ['-date_ajout']

    def __str__(self):
        return f"{self.fichier.name}"

    def delete(self, *args, **kwargs):
        # Supprimer le fichier physique lors de la suppression
        if self.fichier:
            if os.path.isfile(self.fichier.path):
                os.remove(self.fichier.path)
        super().delete(*args, **kwargs)

# ------------------------ Attachement ------------------------
class Attachement(models.Model):
    STATUT_ATTACHEMENT = [
        ('BROUILLON', 'Brouillon'),
        ('SIGNE', 'Signé'),
        ('TRANSMIS', 'Transmis'),
        ('VALIDE', 'Validé'),
    ]

    projet = models.ForeignKey('Projet', on_delete=models.CASCADE, related_name='attachements')
    numero = models.CharField(max_length=20, verbose_name="Numéro d'attachement")
    date_etablissement = models.DateField(verbose_name="Date d'établissement")
    date_debut_periode = models.DateField(verbose_name="Date début période")
    date_fin_periode = models.DateField(verbose_name="Date fin période")
    statut = models.CharField(max_length=15, choices=STATUT_ATTACHEMENT, default='BROUILLON')
    observations = models.TextField(blank=True, verbose_name="Observations")
    fichier = models.FileField(upload_to='attachements/%Y/%m/', null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Attachement"
        verbose_name_plural = "Attachements"
        ordering = ['-date_etablissement', '-numero']

    def initialiser_processus_validation(self, demandeur):
        """Initialise le processus de validation pour cet attachement"""
        
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
    def peut_etre_reouvert(self):
        """Property qui vérifie si l'attachement peut être réouvert (sans user)"""
        return self.statut == 'VALIDE'
    
    def peut_etre_reouvert_par(self, user):
        """Méthode pour vérifier les permissions spécifiques"""
        if not self.peut_etre_reouvert:
            return False
        return user.is_superuser or user.is_staff or user.has_perm('projets.reopen_attachment')
    
    def reouvrir(self, user):
        """Réouvre l'attachement validé"""
        if not self.peut_etre_reouvert_par(user):
            raise PermissionError("Vous n'avez pas la permission de réouvrir cet attachement")
        
        self.statut = 'BROUILLON'
        self.save()
        
        # Réinitialiser les validations associées
        self.validations.update(
            statut_validation='EN_ATTENTE',
            validateur=None,
            date_validation=None,
            commentaires='',
            motifs_rejet=''
        )
        
    @property
    def total_montant_ht(self):
        return sum(ligne.montant_ligne_realise for ligne in self.lignes_attachement.all())

    def get_previous_attachement(self):
        return Attachement.objects.filter(projet=self.projet, id__lt=self.id).order_by('-id').first()
    @property
    def montant_ht_attachement_precedent(self):
        """Montant cumulé de l'attachement précédent (par date début période)"""
        try:
            precedent = self.get_previous_attachement() # Le plus récent avant cette période
            
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
        # Une attachement est considérée comme un titre si elle n'a pas de numéro ou d'unite
        return not self.numero or not self.unite or (self.quantite_initiale is None or self.quantite_initiale == 0) 
    def save(self, *args, **kwargs):
        # Calcul automatique du cumul précédent
        if not self.pk:  # Nouvelle ligne
            cumul_precedent = LigneAttachement.objects.filter(
                ligne_lot=self.ligne_lot,
                attachement__date_etablissement__lt=self.attachement.date_etablissement
            ).aggregate(total=Sum('quantite_realisee'))['total'] or 0
            self.quantite_cumulee = cumul_precedent + self.quantite_realisee
        super().save(*args, **kwargs)

# ------------------------ Processus de validation ------------------------
class ProcessValidation(models.Model):
    """
    Modèle pour gérer le processus de validation d'un attachement
    """
    
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
    
    # Relation avec l'attachement
    attachement = models.ForeignKey('Attachement', on_delete=models.CASCADE, related_name='validations', verbose_name="Attachement à valider")
    # Informations sur la validation
    type_validation = models.CharField( max_length=20, choices=TYPE_VALIDATION_CHOICES, default='TECHNIQUE', verbose_name="Type de validation")
    
    statut_validation = models.CharField( max_length=15, choices=STATUT_VALIDATION_CHOICES, default='EN_ATTENTE', verbose_name="Statut de la validation" )
    # Personnes impliquées
    validateur = models.ForeignKey( User, on_delete=models.SET_NULL, null=True, blank=True, related_name='validations_effectuees', verbose_name="Validateur")
    
    demandeur_validation = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='validations_demandees', verbose_name="Demandeur de validation")
    # Dates importantes
    date_demande = models.DateTimeField( auto_now_add=True, verbose_name="Date de demande" )
    
    date_validation = models.DateTimeField(null=True, blank=True, verbose_name="Date de validation")
    
    date_limite = models.DateTimeField( null=True, blank=True, verbose_name="Date limite de validation")
    # Commentaires et justificatifs
    commentaires = models.TextField(blank=True, null=True , verbose_name="Commentaires sur la validation")
    
    motifs_rejet = models.TextField( blank=True, null=True, verbose_name="Motifs de rejet le cas échéant")
    
    # Fichiers justificatifs
    fichier_validation = models.FileField(upload_to='validations_attachements/%Y/%m/', null=True, blank=True, verbose_name="Fichier de validation")
    
    # Champs techniques
    ordre_validation = models.PositiveIntegerField(default=1, verbose_name="Ordre dans le processus de validation")
    
    est_obligatoire = models.BooleanField(default=True, verbose_name="Validation obligatoire")
    
    # Métadonnées
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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
        """Override save pour gérer la logique métier"""
        # Si la validation passe à "VALIDÉ", enregistrer la date
        if self.statut_validation == 'VALIDE' and not self.date_validation:
            self.date_validation = timezone.now()
            
        # Mettre à jour le statut de l'attachement si toutes les validations sont faites
        super().save(*args, **kwargs)
        self._update_statut_attachement()

    def _update_statut_attachement(self):
        """Met à jour le statut de l'attachement selon les validations"""
        validations_obligatoires = self.attachement.validations.filter(est_obligatoire=True)
        validations_validees = validations_obligatoires.filter(statut_validation='VALIDE')
        
        if validations_obligatoires.count() == validations_validees.count():
            self.attachement.statut = 'VALIDE'
            self.attachement.save()

    @property
    def est_en_retard(self):
        """Vérifie si la validation est en retard"""
        if self.date_limite and self.statut_validation == 'EN_ATTENTE':
            return timezone.now() > self.date_limite
        return False

    @property
    def jours_restants(self):
        """Calcule le nombre de jours restants avant la date limite"""
        if self.date_limite and self.statut_validation == 'EN_ATTENTE':
            delta = self.date_limite - timezone.now()
            return max(0, delta.days)
        return None
    
    def peut_etre_valide_par(self, user):
        """
        Vérifie si un utilisateur peut valider cette étape
        """
        # Si déjà validée, rejetée ou en correction, on ne peut pas valider
        if self.statut_validation != 'EN_ATTENTE':
            return False
        
        # SUPERUSER peut TOUT valider
        if user.is_superuser:
            return True
        
        # STAFF peut valider les étapes technique et administrative
        if user.is_staff and self.type_validation in ['TECHNIQUE', 'ADMINISTRATIVE']:
            return True
        
        # Le validateur assigné peut valider
        if self.validateur and self.validateur == user:
            return True
        
        # Permissions spécifiques
        if user.has_perm('projets.valider_attachement'):
            return True
        
        return False
    
    @property
    def est_en_attente(self):
        """Property pour vérifier si l'étape est en attente"""
        return self.statut_validation == 'EN_ATTENTE'
    @property
    def est_validee(self):
        """Property pour vérifier si l'étape est validée"""
        return self.statut_validation == 'VALIDE'
    def verifier_etapes_validation(self):
        """Met à jour si toutes les étapes sont validées."""
        toutes_valides = self.etapes.filter(is_validated=False).count() == 0
        return toutes_valides
            
    def valider(self, user, commentaires="", fichier=None):
        """Méthode pour valider l'attachement"""
        if not self.peut_etre_valide_par(user):
            raise PermissionError("Cet utilisateur ne peut pas valider cette étape")
        if not self.verifier_etapes_validation():
            raise ValueError("Toutes les étapes de validation doivent être validées avant de valider cet attachement")
        
        self.statut_validation = 'VALIDE'
        self.validateur = user
        self.commentaires = commentaires
        if fichier:
            self.fichier_validation = fichier
        self.save()

    def rejeter(self, user, motifs, fichier=None):
        """Méthode pour rejeter l'attachement"""
        if not self.peut_etre_valide_par(user):
            raise PermissionError("Cet utilisateur ne peut pas rejeter cette étape")
        
        self.statut_validation = 'REJETE'
        self.validateur = user
        self.motifs_rejet = motifs
        if fichier:
            self.fichier_validation = fichier
        self.save()

    def demander_correction(self, user, commentaires):
        """Méthode pour demander une correction"""
        if not self.peut_etre_valide_par(user):
            raise PermissionError("Cet utilisateur ne peut pas demander une correction")
        
        self.statut_validation = 'CORRECTION'
        self.validateur = user
        self.commentaires = commentaires
        self.save()

    @classmethod
    def get_validations_en_attente(cls, user=None):
        """Récupère toutes les validations en attente, optionnellement pour un utilisateur spécifique"""
        queryset = cls.objects.filter(statut_validation='EN_ATTENTE')
        if user:
            queryset = queryset.filter(validateur=user)
        return queryset

    @classmethod
    def get_prochain_ordre_validation(cls, attachement):
        """Calcule le prochain ordre de validation pour un attachement"""
        last_validation = cls.objects.filter(attachement=attachement).order_by('-ordre_validation').first()
        return (last_validation.ordre_validation + 1) if last_validation else 1

    def initier_etapes_techniques_par_defaut(self):
        """Initialise les étapes standards de validation pour ce processus"""
        etapes_standardes = [
            ('Validation du levé topographique', 1),
            ('Vérification des plans d\'eattachement', 2),
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

    # Montants de base
    montant_ht = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant HT")
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=20.0, verbose_name="Taux TVA (%)")
    montant_tva = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant TVA")
    montant_ttc = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant TTC")

    # Retenues
    taux_retenue_garantie = models.DecimalField(max_digits=5, decimal_places=2, default=10.0, verbose_name="Taux retenue de garantie (%)")
    montant_retenue_garantie = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant retenue de garantie")

    taux_ras = models.DecimalField(max_digits=5, decimal_places=2, default=0.0, verbose_name="Taux RAS (%)")
    montant_ras = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant RAS")

    autres_retenues = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Autres retenues")

    # Montant net à payer
    montant_net_a_payer = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant net à payer")

    # Références de paiement
    numero_bordereau = models.CharField(max_length=50, blank=True, verbose_name="Numéro de bordereau")
    date_paiement = models.DateField(null=True, blank=True, verbose_name="Date de paiement")
    observations = models.TextField(blank=True, verbose_name="Observations")
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.m_ht_situation = 0.0
        
    @property
    def montant_situation_ht(self):
        # Montant situation de l'attachement
        self.m_ht_situation = self.attachement.montant_situation
        return self.m_ht_situation
    @property
    def montant_situation_retenue_garantie(self):
        return self.m_ht_situation*(self.taux_retenue_garantie/100)
    @property
    def reste_a_payer_ht(self):
        return self.m_ht_situation - self.montant_situation_retenue_garantie
    @property
    def montant_situation_ttc(self):
        return self.reste_a_payer_ht*(1+(self.taux_tva/100))
    # Retenues
    
    @property
    def montant_situation_tva(self):
        return self.montant_situation_ttc - self.reste_a_payer_ht
    @property
    def montant_situation_ras(self):
        return self.m_ht_situation*(self.taux_ras/100)
    @property
    def montant_situation_autres_retenues(self):
        return self.autres_retenues if self.autres_retenues else 0
    @property
    def montant_situation_net_a_payer(self):
        return self.montant_situation_ttc - self.montant_situation_ras - self.montant_situation_autres_retenues
    class Meta:
        verbose_name = "Décompte"
        verbose_name_plural = "Décomptes"
        ordering = ['-date_emission', '-numero']

    def save(self, *args, **kwargs):
        # Calculs automatiques
        self.montant_ht = self.attachement.total_montant_ht
        
        # TVA
        self.montant_tva = (self.montant_ht * self.taux_tva) / 100
        self.montant_ttc = self.montant_ht + self.montant_tva
        
        # Retenues
        self.montant_retenue_garantie = (self.montant_ht * self.taux_retenue_garantie) / 100
        self.montant_ras = (self.montant_ht * self.taux_ras) / 100
        
        # Net à payer
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
        # Calcul automatique du reste à payer
        self.reste_a_payer = self.cumul_a_date - self.cumul_deja_percu
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_nature_depenses_display()} - {self.cumul_a_date}"

    @property
    def nature_depenses_display(self):
        """Propriété pour obtenir le nom d'affichage du choix"""
        return self.get_nature_depenses_display()

class ResumeDecompte(models.Model):
    """Modèle pour stocker les totaux et sous-totaux"""
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
        """Méthode pour calculer les totaux à partir des décomptes"""
        self.sous_total_ht = sum(d.cumul_a_date for d in decomptes)
        self.total_ht = self.sous_total_ht
        self.tva_montant = self.total_ht * (self.tva_taux / 100)
        self.total_ttc = self.total_ht + self.tva_montant
        self.save()

    def __str__(self):
        return f"Résumé décompte - {self.date_calcul.strftime('%d/%m/%Y')}"
    
