from decimal import Decimal
from datetime import date
import hashlib
import os
import re
from django import forms
from django.forms.models import BaseInlineFormSet
from django.db.models import Q
from django.core.exceptions import ValidationError

from projets.utils.icones import choix_icones

# from projets.models.revision import RevisionPrix

from .models import (
    Client, Decompte, Dossier, Ingenieur, Profile, Projet, Entreprise, Tache,
    Attachement, OrdreService, RapportJournalier, DepenseRapportJournalier,
    StockRapportJournalier, SituationMensuelle, DepenseSituationMensuelle,
    DocumentAdministratif, StockSituationMensuelle, DocumentSituationMensuelle,
    RecetteSituationMensuelle, Personnel, Materiel, Atelier, TypeMateriel,
    AffectationRessource, Location, Transport, SousTraitance, Consommable,
    Fourniture, CategorieCharge, RessourceAffectee,
    ReleveMateriel, SuiviExecution,
)
 
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class FrenchDecimalField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            value = re.sub(r'\s+', '', value).replace(',', '.')
        return super().to_python(value)

class SuiviExecutionForm(forms.ModelForm):
    class Meta:
        model = SuiviExecution
        fields = ['date', 'type_suivi', 'importance', 'titre', 'commentaire', 'redacteur']
        widgets = {
            'date': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'commentaire': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = 'app-modal-input'

class SuiviFilesInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class SuiviFilesField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', SuiviFilesInput)
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else [data]
        cleaned = []
        errors = []
        for file in files:
            try:
                uploaded = super().clean(file, initial)
                if uploaded is None:
                    continue
                if uploaded.size > 10 * 1024 * 1024:
                    raise forms.ValidationError(
                        "Le fichier %(name)s dépasse la taille maximale de 10 Mo.",
                        params={'name': uploaded.name},
                    )
                cleaned.append(uploaded)
            except forms.ValidationError as error:
                errors.extend(error.error_list)
        if errors:
            raise forms.ValidationError(errors)
        return cleaned


class SuiviExecutionAjoutForm(SuiviExecutionForm):
    fichiers = SuiviFilesField(
        required=False, max_length=255, label="Fichiers joints",
        widget=SuiviFilesInput(attrs={'data-suivi-files': '', 'aria-describedby': 'suivi-files-help'}),
    )

class CategorieChargeForm(forms.ModelForm):
    class Meta:
        model = CategorieCharge
        fields = ['code', 'nom', 'ordre', 'actif']
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'FRAIS_GENERAUX'}),
            'nom': forms.TextInput(attrs={'placeholder': 'Frais généraux'}),
            'ordre': forms.NumberInput(attrs={'min': '0'}),
        }

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'avatar': forms.FileInput(attrs={
                'accept': 'image/*',
                'capture': 'environment',  # 
                'multiple': False,
            })}
        labels = {
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'email': 'Email'
        }

class AvatarUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']
    
    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            # Validation de la taille (max 2MB)
            if avatar.size > 5 * 1024 * 1024:
                raise forms.ValidationError("L'image ne doit pas dépasser 2MB.")
            
            # Validation du type de fichier
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif']
            ext = os.path.splitext(avatar.name)[1].lower()
            if ext not in valid_extensions:
                raise forms.ValidationError("Format de fichier non supporté. Utilisez JPG, PNG ou GIF.")
        
        return avatar

class ProjetForm(forms.ModelForm):

    # Style CSS commun pour tous les champs

    class Meta:
        model = Projet
        fields = [
            'dossier', 'type_projet', 'nom', 'maitre_ouvrage', 'numero', 'objet', 'date_debut',
            'delai', 'unite_delai', 'avancement', 'statut', 'montant', 'montant_soumission', 'taux_tva',
            'localisation', 'entreprise', 'revisable'
        ]
        widgets = {
            'dossier': forms.Select(attrs={'placeholder': 'Dossier du projet'}),
            'type_projet': forms.Select(attrs={'placeholder': 'Type de projet'}),
            'nom': forms.TextInput(attrs={'placeholder': 'Nom du projet *'}),
            'maitre_ouvrage': forms.TextInput(attrs={'placeholder': 'Maître d\'ouvrage'}),
            'numero': forms.TextInput(attrs={'placeholder': 'N° marché *'}),
            'objet': forms.Textarea(attrs={ 'rows': 3, 'placeholder': 'Objet du projet *', 'style': 'min-height: auto;'}),
            'date_debut': forms.DateInput(attrs={ 'type': 'date', 'placeholder': 'Date de début *', }),
            'delai': forms.NumberInput(attrs={'class': ' text-right', 'placeholder': 'Durée', 'min': '0'}),
            'unite_delai': forms.Select(),
            'avancement': forms.NumberInput(attrs={'class': ' text-right', 'placeholder': 'Avancement en %'}),
            'statut': forms.Select(attrs={'placeholder': 'Statut du projet'}),
            'montant': forms.NumberInput(attrs={'class': ' text-right', 'placeholder': 'Montant estimé (DH)'}),
            'montant_soumission': forms.NumberInput(attrs={'class': ' text-right', 'placeholder': 'Montant soumission (DH)'}),
            'taux_tva': forms.NumberInput(attrs={'class': ' text-right', 'placeholder': 'Taux TVA par défaut (%)', 'step': '0.01', 'min': '0', 'max': '100'}),
            'localisation': forms.TextInput(attrs={'placeholder': 'Localisation du projet'}),
            'entreprise': forms.Select(attrs={'placeholder': 'Nom de l\'entreprise'}),
            'revisable': forms.CheckboxInput(attrs={'class': 'hidden peer', 'id': 'revisable-toggle'
            }),
            
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and user.is_superuser:
            self.fields['dossier'].queryset = Dossier.objects.all()
        elif user:
            self.fields['dossier'].queryset = Dossier.objects.filter(gerant=user)
        else:
            self.fields['dossier'].queryset = Dossier.objects.none()
        self.fields['revisable'].label = "Projet révisable"
        self.fields['revisable'].help_text = "Les prix seront ajustés selon les indices officiels"
        if not self.instance.pk:
            self.fields['taux_tva'].initial = 20.0
        if self.instance and self.instance.date_debut:
            self.initial['date_debut'] = self.instance.date_debut.strftime('%Y-%m-%d')
                

    def clean_montant(self):
        montant_val = self.cleaned_data.get('montant')
        if montant_val is None:
            return None
        if montant_val < 0:
            raise forms.ValidationError("Le montant ne peut pas être négatif.")
        return montant_val

    def clean_montant_soumission(self):
        montant_val = self.cleaned_data.get('montant_soumission')
        if montant_val is None:
            return None
        if montant_val < 0:
            raise forms.ValidationError("Le montant de soumission ne peut pas être négatif.")
        return montant_val

class DossierForm(forms.ModelForm):
    projets = forms.ModelMultipleChoiceField(
        label=_("Projets à rattacher"),
        queryset=Projet.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = Dossier
        fields = ['nom', 'description', 'activite', 'gerant']
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Nom du dossier *'}),
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Description du dossier'}),
            'gerant': forms.Select(attrs={'placeholder': 'Chef de projet du dossier'}),
        }

    def __init__(self, *args, projet=None, **kwargs):
        kwargs.pop('projet', None)
        super().__init__(*args, **kwargs)
        self.projet = projet or getattr(self.instance, 'projet', None)
        self.fields['gerant'].queryset = User.objects.filter(
            is_superuser=False,
            profile__role__in=['GERANT', 'CHEF_PROJET'],
        ).order_by('username')
        projets_disponibles = Projet.objects.filter(dossier__isnull=True)
        if self.instance.pk:
            projets_disponibles = Projet.objects.filter(
                Q(dossier__isnull=True) | Q(dossier=self.instance)
            )
            self.initial['projets'] = self.instance.projets.values_list('id', flat=True)
        self.fields['projets'].queryset = projets_disponibles.order_by('nom')

    def save(self, commit=True):
        dossier = super().save(commit=commit)
        if commit:
            projets_selectionnes = self.cleaned_data['projets']
            Projet.objects.filter(dossier=dossier).exclude(
                id__in=projets_selectionnes.values_list('id', flat=True)
            ).update(dossier=None)
            Projet.objects.filter(
                id__in=projets_selectionnes.values_list('id', flat=True)
            ).update(dossier=dossier)
        return dossier

class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = ['nom', 'fonction', 'telephone', 'unite', 'tarif', 'actif']
        labels = {'nom': 'Nom', 'fonction': 'Fonction', 'telephone': 'Téléphone', 'unite': 'Unité', 'tarif': 'Tarif', 'actif': 'Actif'}
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Nom *'}),
            'fonction': forms.TextInput(attrs={'placeholder': 'Fonction *'}),
            'telephone': forms.TextInput(attrs={'placeholder': 'Téléphone *'}),
            'unite': forms.TextInput(attrs={'placeholder': 'Unité *'}),
            'tarif': forms.TextInput(attrs={'placeholder': 'Tarif *'}),
            'actif': forms.CheckboxInput(),
        }

class UtilisateurCreationForm(UserCreationForm):
    ROLE_CHOICES = (
        ('CHEF_PROJET', 'Chef de projet'),
        ('CHEF_CHANTIER', 'Chef de chantier'),
        ('POINTEUR', 'Pointeur'),
        ('STAFF', 'Staff'),
        ('UTILISATEUR', 'Utilisateur'),
    )
    email = forms.EmailField(required=False)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    role = forms.ChoiceField(choices=ROLE_CHOICES)
    dossiers = forms.ModelMultipleChoiceField(
        queryset=Dossier.objects.none(), required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.creator = user
        if user and user.is_superuser:
            self.fields['dossiers'].queryset = Dossier.objects.all()
        elif user:
            self.fields['role'].choices = (
                ('CHEF_CHANTIER', 'Chef de chantier'), ('POINTEUR', 'Pointeur'),
                ('STAFF', 'Staff'), ('UTILISATEUR', 'Utilisateur'),
            )
            self.fields['dossiers'].queryset = Dossier.objects.filter(gerant=user)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data.get('email', '')
        user.first_name = self.cleaned_data.get('first_name', '')
        user.last_name = self.cleaned_data.get('last_name', '')
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
            user.profile.role = self.cleaned_data['role']
            user.profile.save()
            user.dossiers.set(self.cleaned_data['dossiers'])
        return user
        
class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ['nom', 'contact', 'email', 'telephone', 'adresse']

class IngenieurForm(forms.ModelForm):
    class Meta:
        model = Ingenieur
        fields = ['nom']
        labels = {'name': 'Nom'}

class EntrepriseForm(forms.ModelForm):
    class Meta:
        model = Entreprise
        fields = ['nom', 'contact', 'email', 'telephone', 'adresse']

def materiels_affectes_projet(projet):
    ressources = RessourceAffectee.objects.filter(
        projet=projet, categorie_charge__code='MATERIEL', actif=True,
    ).values('objet_id')
    return Materiel.objects.filter(pk__in=ressources).select_related('type_materiel').order_by('designation')


class AffectationRessourceForm(forms.ModelForm):
    """
    Formulaire d'affectation d'un matériel à un atelier.

    Contextes d'utilisation :
    - Création depuis « Matériels de l'atelier » : `atelier=...` est passé,
      le champ atelier est masqué/injecté.
    - Édition d'une affectation existante : `atelier=...` fige l'atelier courant.

    Règles métier validées :
    1. L'atelier est obligatoire (injecté si absent des données).
    2. La date de fin, si fournie, doit être ≥ date de début.
    3. Un matériel ne peut pas être affecté à deux endroits sur des périodes
       qui se chevauchent (tous ateliers confondus).
    4. Le matériel et toute la période doivent être disponibles dans les
       ressources actives du projet, sans exception en édition.
    """

    class Meta:
        model = AffectationRessource
        fields = ['atelier', 'materiel', 'date_debut', 'date_fin', 'commentaire']
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'date_fin': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, atelier=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.atelier = atelier or (self.instance.atelier if self.instance.pk else None)
        atelier = self.atelier

        # --- Champ atelier ---
        qs_ateliers = Atelier.objects.filter(actif=True)
        if atelier:
            # Figer l'atelier fourni, même s'il est inactif.
            qs_ateliers = Atelier.objects.filter(pk=atelier.pk)
        self.fields['atelier'].queryset = qs_ateliers.order_by('code')
        self.fields['atelier'].required = False  # injecté par clean/save si absent

        # --- Champ materiel ---
        self.fields['materiel'].queryset = (
            materiels_affectes_projet(atelier.projet) if atelier else Materiel.objects.none()
        )
        self.fields['materiel'].error_messages['invalid_choice'] = _(
            "Choisissez un matériel parmi les ressources actives affectées à ce projet."
        )

        # --- Pré-remplissage HTML5 des dates ---
        for nom in ('date_debut', 'date_fin'):
            valeur = getattr(self.instance, nom, None)
            if valeur:
                self.initial[nom] = valeur.strftime('%Y-%m-%d')

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def clean(self):
        cleaned = super().clean()
        # 1. Injection / validation de l'atelier
        atelier = cleaned.get('atelier') or self.atelier
        if not atelier:
            self.add_error('atelier', _("L'atelier est obligatoire."))
            return cleaned
        cleaned['atelier'] = atelier

        debut = cleaned.get('date_debut')
        fin = cleaned.get('date_fin')
        materiel = cleaned.get('materiel')

        # 2. Cohérence des dates
        if debut and fin and fin < debut:
            self.add_error(
                'date_fin',
                _("La date de fin ne peut précéder la date de début.")
            )
            # On continue : d'autres erreurs peuvent être utiles à l'utilisateur

        # 3. Détection de chevauchement (requête SQL, pas de boucle Python)
        if materiel and debut:
            disponibilites = RessourceAffectee.objects.filter(
                projet=atelier.projet, categorie_charge__code='MATERIEL',
                objet_id=materiel.pk, actif=True, date_debut__lte=debut,
            )
            if fin:
                disponibilites = disponibilites.filter(Q(date_fin__isnull=True) | Q(date_fin__gte=fin))
            else:
                disponibilites = disponibilites.filter(date_fin__isnull=True)
            if not disponibilites.exists():
                self.add_error('date_debut', _(
                    "La période de l'atelier doit être comprise dans une période de "
                    "disponibilité de ce matériel sur le projet. Sans date de fin, "
                    "la ressource du projet doit être en cours."
                ))
            conflit = self._trouver_conflit(materiel, debut, fin)
            if conflit:
                self.add_error('materiel', self._message_conflit(conflit))

        return cleaned

    def _trouver_conflit(self, materiel, debut, fin):
        """
        Retourne la première AffectationRessource qui chevauche [debut, fin]
        pour ce matériel, ou None.

        Deux périodes [d1, f1] et [d2, f2] se chevauchent si :
            d1 <= f2   ET   d2 <= f1
        où f = None signifie « infini » (en cours).

        Traduction SQL :
            - d1 <= f2  →  filtre : date_fin__gte=debut  OU  date_fin__isnull=True
            - d2 <= f1  →  filtre : date_debut__lte=fin  OU  (fin is None → pas de filtre)
        """
        qs = AffectationRessource.objects.filter(materiel=materiel)

        # Exclusion de l'affectation en cours d'édition
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        # Condition 1 : l'autre finit après notre début (ou est en cours)
        qs = qs.filter(Q(date_fin__isnull=True) | Q(date_fin__gte=debut))

        # Condition 2 : l'autre commence avant notre fin (ou notre fin est infinie)
        if fin is not None:
            qs = qs.filter(date_debut__lte=fin)
        # sinon : pas de borne supérieure, toute affectation future compte

        return qs.select_related('atelier').order_by('date_debut').first()

    @staticmethod
    def _message_conflit(conflit):
        """Construit un message d'erreur lisible."""
        fin_txt = (
            conflit.date_fin.strftime('%d/%m/%Y')
            if conflit.date_fin else _("nouvel ordre")
        )
        return _(
            "Ce matériel est déjà affecté à l'atelier « %(atelier)s » "
            "du %(debut)s au %(fin)s."
        ) % {
            'atelier': f"{conflit.atelier.code} – {conflit.atelier.libelle}",
            'debut': conflit.date_debut.strftime('%d/%m/%Y'),
            'fin': fin_txt,
        }

    # ------------------------------------------------------------------
    # Sauvegarde
    # ------------------------------------------------------------------

    def save(self, commit=True):
        affectation = super().save(commit=False)

        # Injection défensive de l'atelier
        if not affectation.atelier_id:
            if self.atelier:
                affectation.atelier = self.atelier
            else:
                # Ne devrait jamais arriver si clean() a été appelé
                raise ValueError(
                    "Impossible de sauvegarder une affectation sans atelier."
                )

        if commit:
            affectation.save()
            # Nécessaire si le formulaire contient des m2m (pas le cas ici, mais bon réflexe)
            self.save_m2m()

        return affectation

class TypeMaterielForm(forms.ModelForm):
    icone = forms.ChoiceField(choices=(), required=False, label="Icône")

    class Meta:
        model = TypeMateriel
        fields = ["nom", "icone", "actif"]
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Pelles sur chenilles à godet'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choix = choix_icones()
        courant = self.instance.icone if self.instance and self.instance.pk else ""
        if courant and courant not in {valeur for valeur, libelle in choix}:
            choix.append((courant, f"{courant} (fichier introuvable)"))
        self.fields["icone"].choices = choix

class MaterielForm(forms.ModelForm):
    class Meta:
        model = Materiel
        fields = ["designation", "type_materiel", "immatriculation",
                  "unite", "prix_unitaire", "actif"]
        widgets = {
            'designation': forms.TextInput(attrs={'placeholder': 'Pelle CAT 320D'}),
            'immatriculation': forms.TextInput(attrs={'placeholder': 'N° de parc'}),
        }
        labels = {
            'immatriculation': 'N° Parc',
        }
    
    def clean_immatriculation(self):
        """Vérifie l'unicité du N° Parc côté formulaire (sans contrainte BDD)."""
        no_parc = self.cleaned_data.get('immatriculation')
        
        if not no_parc:
            return no_parc  # autoriser vide
        
        qs = Materiel.objects.filter(immatriculation=no_parc)
        
        # Exclure l'instance en cours de modification
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        
        if qs.exists():
            raise forms.ValidationError(
                "Ce N° Parc existe déjà. Veuillez en choisir un autre."
            )
        
        return no_parc

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        type_id = self.instance.type_materiel_id if self.instance and self.instance.pk else None
        if type_id:
            qs = TypeMateriel.objects.filter(Q(actif=True) | Q(pk=type_id))
        else:
            qs = TypeMateriel.objects.filter(actif=True)
        champ = self.fields["type_materiel"]
        champ.queryset = qs.order_by("nom")
        champ.required = False
        champ.empty_label = "— Non défini —"
        if type_id:
            self.initial["type_materiel"] = type_id

class AtelierForm(forms.ModelForm):
    class Meta:
        model = Atelier
        fields = ['code', 'libelle', 'description', 'actif']
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': '01'}),
            'libelle': forms.TextInput(attrs={'placeholder': 'Terrassements généraux'}),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, projet=None, **kwargs):
        self.projet = projet
        super().__init__(*args, **kwargs)

    def clean_code(self):
        code = (self.cleaned_data['code'] or '').strip().zfill(2)
        if self.projet:
            qs = Atelier.objects.filter(projet=self.projet, code=code)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f"Un atelier avec le code « {code} » existe déjà pour ce projet."
                )
        return code

    def save(self, commit=True):
        atelier = super().save(commit=False)
        if self.projet:
            atelier.projet = self.projet
        if commit:
            atelier.save()
        return atelier

class TransportForm(forms.ModelForm):
    class Meta:
        model = Transport
        fields = ['designation', 'type_transport', 'transporteur', 'unite', 'prix_unitaire', 'actif']

class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ['designation', 'type_materiel', 'locataire', 'unite', 'prix_unitaire', 'actif']

class SousTraitanceForm(forms.ModelForm):
    class Meta:
        model = SousTraitance
        fields = ['designation', 'type_sous_traitance', 'prestataire', 'unite', 'prix_unitaire', 'actif']

class ConsommableForm(forms.ModelForm):
    class Meta:
        model = Consommable
        fields = ['designation', 'type_consommable', 'fournisseur', 'unite', 'prix_unitaire', 'actif']

class FournitureForm(forms.ModelForm):
    class Meta:
        model = Fourniture
        fields = ['designation', 'type_fourniture', 'fournisseur', 'unite', 'prix_unitaire', 'actif']

class RessourceAffecteeForm(forms.ModelForm):
    """
    Formulaire d'affectation d'une ressource du référentiel à un projet.

    Le champ `objet_id` est alimenté par un <select> dont les options sont
    filtrées côté serveur selon `categorie_charge.code`.
    """

    # Mapping centralisé (code → modèle + labels)
    RESSOURCE_MAP = {
        'PERSONNEL':      (Personnel,      'nom',         'tarif',          'Personnel'),
        'MATERIEL':       (Materiel,       'designation', 'prix_unitaire',  'Matériel'),
        'LOCATION':       (Location,       'designation', 'prix_unitaire',  'Location'),
        'SOUS_TRAITANCE': (SousTraitance,  'designation', 'prix_unitaire',  'Sous-traitance'),
        'TRANSPORT':      (Transport,      'designation', 'prix_unitaire',  'Transport'),
        'CONSOMMABLE':    (Consommable,    'designation', 'prix_unitaire',  'Consommable'),
        'FOURNITURE':     (Fourniture,     'designation', 'prix_unitaire',  'Fourniture'),
    }

    objet_id = forms.ChoiceField(
        label=_("Ressource"),
        required=True,
        widget=forms.Select(attrs={'class': 'app-modal-input'}),
    )

    class Meta:
        model = RessourceAffectee
        fields = [
            'categorie_charge', 'atelier', 'objet_id',
            'date_debut', 'date_fin', 'tarif', 'commentaire', 'actif',
        ]
        widgets = {
            'categorie_charge': forms.Select(attrs={'class': 'app-modal-input'}),
            'atelier': forms.Select(attrs={'class': 'app-modal-input'}),
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'app-modal-input'}),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': 'app-modal-input'}),
            'tarif': forms.NumberInput(attrs={'class': 'app-modal-input', 'step': '0.01', 'min': '0'}),
            'commentaire': forms.TextInput(attrs={'class': 'app-modal-input'}),
        }

    def __init__(self, *args, projet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.projet = projet or getattr(self.instance, 'projet', None)
        self.fields['categorie_charge'].queryset = (
            CategorieCharge.objects.filter(actif=True).order_by('ordre', 'nom')
        )
        if self.projet:
            self.fields['atelier'].queryset = (
                Atelier.objects.filter(projet=self.projet, actif=True).order_by('code')
            )
        else:
            self.fields['atelier'].queryset = Atelier.objects.none()

        code = self._code_categorie_courant()
        self.fields['objet_id'].choices = self._options_pour_code(code)
        self.fields['tarif'].required = False
        # ⚡ Le champ atelier n'est pertinent que pour le MATERIEL
        if code != 'MATERIEL':
            self.fields['atelier'].widget = forms.HiddenInput()
            self.fields['atelier'].required = False
            self.initial['atelier'] = ''

        for name in ('date_debut', 'date_fin'):
            val = getattr(self.instance, name, None)
            if val:
                self.initial[name] = val.strftime('%Y-%m-%d')

    def _code_categorie_courant(self):
        """Détermine le code de catégorie courant (initial, instance ou POST)."""
        if self.data and self.data.get('categorie_charge'):
            cat = CategorieCharge.objects.filter(pk=self.data['categorie_charge']).first()
            return cat.code if cat else ''
        if self.instance and self.instance.categorie_charge_id:
            return self.instance.categorie_charge.code
        if self.initial.get('categorie_charge'):
            cat = self.initial['categorie_charge']
            return cat.code if hasattr(cat, 'code') else ''
        return ''

    def _options_pour_code(self, code):
        """Retourne les choix [(id, label), ...] pour le code de catégorie."""
        entry = self.RESSOURCE_MAP.get(code)
        if not entry:
            return [('', '— Sélectionnez d\'abord un type —')]
        Model, champ_designation, _, _ = entry
        qs = Model.objects.filter(actif=True).order_by(champ_designation)
        options = [('', '— Sélectionner —')]
        for obj in qs:
            label = getattr(obj, champ_designation)
            parc = getattr(obj, 'immatriculation', None)
            if parc:
                label = f"{parc} — {label}"
            options.append((obj.pk, label))
        return options

    def clean(self):
        cleaned = super().clean()
        code = cleaned['categorie_charge'].code if cleaned.get('categorie_charge') else ''
        objet_id = cleaned.get('objet_id')
        entry = self.RESSOURCE_MAP.get(code)

        if not entry:
            self.add_error('categorie_charge', _("Type de ressource non supporté."))
            return cleaned
        if not objet_id:
            self.add_error('objet_id', _("Sélectionnez une ressource."))
            return cleaned

        Model, champ_designation, champ_prix, _ = entry
        try:
            source = Model.objects.get(pk=int(objet_id))
        except (Model.DoesNotExist, ValueError, TypeError):
            self.add_error('objet_id', _("Ressource introuvable."))
            return cleaned

        # Snapshot dénormalisé
        cleaned['designation'] = getattr(source, champ_designation)
        cleaned['unite'] = getattr(source, 'unite', '') or ''
        if not cleaned.get('tarif') is None:
            cleaned['tarif'] = getattr(source, champ_prix, Decimal('0.00')) or Decimal('0.00')
        cleaned['projet'] = self.projet

        # Validation de chevauchement (déléguée au modèle)
        instance = self.instance
        instance.projet = self.projet
        instance.categorie_charge = cleaned['categorie_charge']
        instance.objet_id = int(objet_id)
        instance.date_debut = cleaned.get('date_debut')
        instance.date_fin = cleaned.get('date_fin')
        try:
            instance.clean()
        except ValidationError as e:
            for field, msgs in e.message_dict.items():
                for msg in msgs:
                    self.add_error(field if field in self.fields else None, msg)

        return cleaned

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.designation = self.cleaned_data['designation']
        instance.unite = self.cleaned_data.get('unite', '')
        instance.tarif = self.cleaned_data.get('tarif') or Decimal('0.00')
        instance.projet = self.projet
        # ⚡ Atelier uniquement pour le matériel
        if self.cleaned_data.get('categorie_charge') \
                and self.cleaned_data['categorie_charge'].code != 'MATERIEL':
            instance.atelier = None
        if commit:
            instance.save()
        return instance

class TacheForm(forms.ModelForm):
    class Meta:
        model = Tache
        fields = [
            'projet', 'titre', 'description',
            'date_debut', 'date_fin',
            'priorite', 'responsable',
            'terminee', 'avancement',
        ]
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-input'}),
            'priorite': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        if user is not None:
            from projets.decorators import projets_accessibles
            accessibles = projets_accessibles(user)

            # ⚡ Filtrer les projets accessibles
            self.fields['projet'].queryset = accessibles.order_by('nom')

            # ⚡ Filtrer les responsables aux users des projets accessibles
            self.fields['responsable'].queryset = User.objects.filter(
                projets__in=accessibles
            ).distinct().order_by('username')
        else:
            self.fields['projet'].queryset = Projet.objects.none()
            self.fields['responsable'].queryset = User.objects.none()

        for field in self.fields:
            if field not in ['terminee', 'description']:
                self.fields[field].widget.attrs.update({'class': 'form-input'})

    def clean(self):
        cleaned = super().clean()
        debut = cleaned.get('date_debut')
        fin = cleaned.get('date_fin')
        avancement = cleaned.get('avancement')
        projet = cleaned.get('projet')

        if debut and fin and fin < debut:
            self.add_error('date_fin', 'La date de fin ne peut précéder la date de début.')

        if avancement is not None and (avancement < 0 or avancement > 100):
            self.add_error('avancement', "L'avancement doit être compris entre 0 et 100.")

        if projet and self.user is not None:
            from projets.decorators import projets_accessibles
            if not projets_accessibles(self.user).filter(pk=projet.pk).exists():
                self.add_error('projet', "Vous n'avez pas accès à ce projet.")

        return cleaned
    
class AttachementForm(forms.ModelForm):
    original_filename = forms.CharField(widget=forms.HiddenInput(), required=False)
    class Meta:
        model = Attachement
        fields = ['numero', 'date_etablissement', 'date_debut_periode', 'date_fin_periode', 'statut', 'observations', 'fichier', 'original_filename']
        widgets = {
            'numero': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'ATT-2024-001'
            }),
            'date_etablissement': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'date_debut_periode': forms.DateInput(attrs={
                'class': 'form-input', 
                'type': 'date'
            }),
            'date_fin_periode': forms.DateInput(attrs={
                'class': 'form-input',
                'type': 'date'
            }),
            'statut': forms.Select(attrs={
                'class': 'form-input form-select'
            }),

            'fichier': forms.FileInput(attrs={
                'class': 'form-input file-upload',
                'accept': 'image/*,video/*,.pdf,.doc,.docx',
                'capture': 'environment',  # 
                'multiple': False,
            }),
            'original_filename': forms.TextInput(attrs={
                'class': 'form-input',
            }),
            'observations': forms.Textarea(attrs={
                'class': 'form-input form-textarea',
                'rows': 4,
                'placeholder': 'Observations...'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Labels personnalisés
        self.fields['numero'].label = 'Numéro d\'attachement'
        self.fields['date_etablissement'].label = 'Date d\'établissement'
        self.fields['date_debut_periode'].label = 'Date début période'
        self.fields['date_fin_periode'].label = 'Date fin période'
        self.fields['fichier'].required = False

    def clean_statut(self):
        statut = self.cleaned_data['statut']
        if statut == 'VALIDE':
            raise forms.ValidationError(
                "Le statut Validé est attribué uniquement par le processus de validation."
            )
        return statut

class DecompteForm(forms.ModelForm):
    montant_revision_prix = forms.DecimalField(
        required=False,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control text-right',
            'placeholder': '0.00',
            'step': '0.01',
        }),
        label="Révision des prix (DH)",
        help_text="Montant de la révision de prix calculée"
    )
    
    class Meta:
        model = Decompte
        fields = [
            'attachement', 'type_decompte', 'numero', 'date_emission', 
            'date_echeance', 'statut', 'taux_tva', 'taux_retenue_garantie', 
            'taux_ras', 'autres_retenues', 'montant_revision_prix', 'numero_bordereau', 'date_paiement', 
            'observations'
        ]
        widgets = {
            'date_emission': forms.DateInput(attrs={'type': 'date'}),
            'date_echeance': forms.DateInput(attrs={'type': 'date'}),
            'date_paiement': forms.DateInput(attrs={'type': 'date'}),
            'observations': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Observations supplémentaires...'}),
            'numero': forms.TextInput(attrs={'placeholder': 'Ex: DEC-2024-001'}),
            'numero_bordereau': forms.TextInput(attrs={'placeholder': 'Ex: BORD-2024-001'}),
            'taux_tva': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'taux_retenue_garantie': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'taux_ras': forms.NumberInput(attrs={'step': '0.01', 'min': '0', 'max': '100'}),
            'autres_retenues': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Récupérer le paramètre avant d'appeler le parent
        attachements_disponibles_count = kwargs.pop('attachements_disponibles_count', None)
        
        super().__init__(*args, **kwargs)
        
        # Ajouter des classes CSS à tous les champs
        for field_name, field in self.fields.items():
            if field_name not in ['observations']:  # Sauf textarea
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
        
        # Configuration spécifique pour certains champs
        self.fields['attachement'].empty_label = None
        from collections import OrderedDict
        # Positionner le champ montant_revision_prix après autres_retenues
        # Réorganiser l'ordre des champs si nécessaire
        self.fields = OrderedDict([
            ('attachement', self.fields['attachement']),
            ('type_decompte', self.fields['type_decompte']),
            ('numero', self.fields['numero']),
            ('date_emission', self.fields['date_emission']),
            ('date_echeance', self.fields['date_echeance']),
            ('statut', self.fields['statut']),
            ('taux_tva', self.fields['taux_tva']),
            ('taux_retenue_garantie', self.fields['taux_retenue_garantie']),
            ('taux_ras', self.fields['taux_ras']),
            ('autres_retenues', self.fields['autres_retenues']),
            ('montant_revision_prix', self.fields['montant_revision_prix']),  # Nouvelle position
            ('numero_bordereau', self.fields['numero_bordereau']),
            ('date_paiement', self.fields['date_paiement']),
            ('observations', self.fields['observations']),
        ])
        
        # Valeurs par défaut pour la création uniquement
        if not self.instance.pk:  # Nouveau décompte
            self.fields['taux_tva'].initial = 20.0
            self.fields['taux_retenue_garantie'].initial = 10.0
            self.fields['taux_ras'].initial = 0.0
            self.fields['autres_retenues'].initial = 0.0
            self.fields['montant_revision_prix'].initial = 0.0  # Initialisation
            self.fields['type_decompte'].initial = 'PROVISOIRE'
            self.fields['statut'].initial = 'BROUILLON'
            
            # Date d'émission par défaut = aujourd'hui
            self.fields['date_emission'].initial = timezone.now().date()
        
        # Gestion de l'attachement unique
        if attachements_disponibles_count == 1 and 'attachement' in self.fields:  
            # Si il n'y a qu'un seul attachement disponible
            self.fields['attachement'].widget.attrs.update({
                'readonly': 'readonly',
                'class': 'form-control bg-gray-700 cursor-not-allowed'
            })
            
            # Stocker la valeur pour qu'elle soit sauvegardée malgré le disabled
            if self.fields['attachement'].queryset.count() == 1:
                seul_attachement = self.fields['attachement'].queryset.first()
                self.fields['attachement'].initial = seul_attachement
        # Ajuster la forme des dates en français
        for field_name in ['date_emission', 'date_echeance', 'date_paiement']:
            if self.instance:
                # Récupérer la valeur du champ
                field_value = getattr(self.instance, field_name, None)
                
                if field_value:  # Vérifier si la valeur existe
                    # Convertir au format HTML5 (yyyy-mm-dd)
                    self.initial[field_name] = field_value.strftime('%Y-%m-%d')
    
    def clean_attachement(self):
        attachement = self.cleaned_data.get('attachement')
        
        if attachement:
            # Vérifier si un décompte existe déjà pour cet attachement
            existing_decompte = Decompte.objects.filter(attachement=attachement).first()
            
            # Si on est en mode création OU si on modifie mais qu'on change d'attachement
            if existing_decompte and (not self.instance or self.instance.attachement != attachement):
                raise forms.ValidationError(
                    f"Cet attachement a déjà un décompte associé : {existing_decompte.numero}"
                )
        
        return attachement
    
    def clean_date_echeance(self):
        date_emission = self.cleaned_data.get('date_emission')
        date_echeance = self.cleaned_data.get('date_echeance')
        
        if date_emission and date_echeance and date_echeance < date_emission:
            raise forms.ValidationError("La date d'échéance ne peut pas être antérieure à la date d'émission.")
        
        return date_echeance
    
    def clean_date_paiement(self):
        date_emission = self.cleaned_data.get('date_emission')
        date_paiement = self.cleaned_data.get('date_paiement')
        
        if date_emission and date_paiement and date_paiement < date_emission:
            raise forms.ValidationError("La date de paiement ne peut pas être antérieure à la date d'émission.")
        
        return date_paiement
    
    # def clean_montant_revision_prix(self):
    #     """Validation pour le champ montant_revision_prix"""
    #     montant = self.cleaned_data.get('montant_revision_prix')
    #     montant_ht = self.cleaned_data.get('attachement').total_montant_ht
    #     if montant and abs(montant) > montant_ht * 0.1:
    #         raise forms.ValidationError("Le montant de révision est supérieur au 10% du montant HT.")
        
    #     return montant 

class OrdreServiceForm(forms.ModelForm):
    class Meta:
        model = OrdreService
        fields = '__all__'
        exclude = ['projet', 'ordre_sequence']  # Ces champs sont gérés automatiquement
        widgets = {
            'fichier': forms.FileInput(attrs={
            'accept': 'image/*,.pdf,.doc,.docx',
            'capture': 'environment',  # 'environment' pour caméra arrière, 'user' pour frontale
            'multiple': False,
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.projet = kwargs.pop('projet', None)
        super().__init__(*args, **kwargs)
        
        # Appliquer les classes CSS à tous les champs
        for field_name, field in self.fields.items():
            field.widget.attrs['class'] = 'form-control'
            
        # Champs spécifiques
        self.fields['description'].widget.attrs['rows'] = 4
        self.fields['date_publication'].widget.attrs['type'] = 'date'
        self.fields['date_limite'].widget.attrs['type'] = 'date'
        self.fields['date_effet'].widget.attrs['type'] = 'date'
        
        # Valeur par défaut pour statut
        if not self.instance.pk:
            self.fields['statut'].initial = 'BROUILLON'

class DocumentAdministratifForm(forms.ModelForm):
    """
    Formulaire pour ajouter/modifier un document administratif.

    ⚡ 'projet' et 'original_filename' NE sont PAS dans le formulaire :
       - projet : défini par la vue (depuis l'URL)
       - original_filename : auto-rempli depuis le fichier uploadé

    ⚡ Les 'choices' de type_document viennent du modèle (pas de redéfinition).
    """

    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 Mo
    ALLOWED_EXTENSIONS = [
        # Documents
        '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
        '.txt', '.csv', '.odt', '.ods',
        # Images
        '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp',
        # Vidéos (chantier)
        '.mp4', '.mov', '.avi', '.mkv',
        # Archives
        '.zip', '.rar', '.7z',
    ]

    class Meta:
        model = DocumentAdministratif
        fields = ['type_document', 'date_remise', 'description', 'fichier']

        widgets = {
            'type_document': forms.Select(attrs={
                'class': 'app-modal-input',
                'required': 'required',
            }),
            'date_remise': forms.DateInput(attrs={
                'class': 'app-modal-input',
                'type': 'date',
            }),
            'description': forms.Textarea(attrs={
                'class': 'app-modal-input',
                'rows': 3,
                'placeholder': 'Description optionnelle…',
            }),
            'fichier': forms.FileInput(attrs={
                'class': 'app-modal-input',
                # Filtre le file picker selon le type
                'accept': (
                    '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx,'
                    '.jpg,.jpeg,.png,.gif,.webp,.svg,'
                    '.mp4,.mov,.avi,'
                    '.txt,.csv,.zip,.rar,.7z'
                ),
                # ⚡ PAS de 'capture' → l'utilisateur peut choisir photo OU fichier
                # ⚡ PAS de 'multiple' → un seul fichier (défaut)
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ⚡ Rendre type_document obligatoire (le modèle autorise '', mais on force le choix)
        self.fields['type_document'].required = True
        self.fields['type_document'].error_messages = {
            'required': 'Veuillez sélectionner un type de document.',
        }

    def clean_fichier(self):
        """
        Validation centralisée du fichier :
          - Obligatoire en création
          - Taille < MAX_FILE_SIZE (10 Mo)
          - Extension dans ALLOWED_EXTENSIONS
        """
        fichier = self.cleaned_data.get('fichier')

        # Modification : fichier déjà présent + pas de nouveau fichier → garder l'ancien
        if not fichier and self.instance and self.instance.pk and self.instance.fichier:
            return self.instance.fichier

        if not fichier:
            raise forms.ValidationError("Le fichier est obligatoire.")

        # Taille
        if fichier.size > self.MAX_FILE_SIZE:
            taille_mo = fichier.size / (1024 * 1024)
            max_mo = self.MAX_FILE_SIZE // (1024 * 1024)
            raise forms.ValidationError(
                f"Le fichier ne doit pas dépasser {max_mo} Mo "
                f"(actuel : {taille_mo:.1f} Mo)."
            )

        # Extension
        ext = os.path.splitext(fichier.name)[1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            exts = ', '.join(sorted(self.ALLOWED_EXTENSIONS))
            raise forms.ValidationError(
                f"Extension « {ext} » non autorisée. Autorisées : {exts}"
            )

        return fichier

class RapportJournalierForm(forms.ModelForm):
    class Meta:
        model = RapportJournalier
        fields = ['date', 'meteo', 'temperature', 'travaux_realises', 'evenements', 'observations', 'redacteur']
        widgets = {
            'date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'travaux_realises': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'evenements': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'observations': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, projet=None, **kwargs):
        self.projet = projet
        super().__init__(*args, **kwargs)
        if self.projet is None:
            self.projet = getattr(self.instance, 'projet', None)
        
        # Forcer le format de date ISO pour le champ HTML5 date
        if self.instance and self.instance.date:
            self.initial['date'] = self.instance.date.strftime('%Y-%m-%d')
        
        # Appliquer les classes CSS
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')
            
        # S'assurer que le champ date est bien au format ISO
        if 'date' in self.fields:
            self.fields['date'].input_formats = ['%Y-%m-%d']

    def clean(self):
        cleaned_data = super().clean()
        date_rapport = cleaned_data.get('date')
        if date_rapport and self.projet:
            rapports_existants = RapportJournalier.objects.filter(
                projet=self.projet, date=date_rapport
            )
            if self.instance.pk:
                rapports_existants = rapports_existants.exclude(pk=self.instance.pk)
            if rapports_existants.exists():
                self.add_error(
                    'date',
                    'Un rapport journalier existe déjà pour ce projet à cette date.',
                )

        fichier = self.files.get('document')
        if fichier:
            if fichier.size > 10 * 1024 * 1024:
                raise forms.ValidationError('Le document ne doit pas dépasser 10 Mo.')
            extensions_autorisees = {
                '.pdf', '.doc', '.docx', '.xls', '.xlsx',
                '.jpg', '.jpeg', '.png', '.gif',
            }
            if os.path.splitext(fichier.name)[1].lower() not in extensions_autorisees:
                raise forms.ValidationError(
                    'Type de document non supporté.'
                )
        return cleaned_data

class DepenseRapportJournalierForm(forms.ModelForm):
    categorie = forms.CharField(required=False, widget=forms.HiddenInput())
    categorie_charge = forms.ModelChoiceField(
        queryset=CategorieCharge.objects.none(), required=False, widget=forms.HiddenInput()
    )

    class Meta:
        model = DepenseRapportJournalier
        fields = ['categorie', 'categorie_charge', 'designation', 'quantite', 'unite', 'prix_unitaire', 'observations']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = CategorieCharge.objects.filter(actif=True)
        if self.instance.categorie_charge_id:
            categories = CategorieCharge.objects.filter(
                Q(actif=True) | Q(pk=self.instance.categorie_charge_id)
            )
        self.fields['categorie_charge'].queryset = categories
        for name, field in self.fields.items():
            if name not in {'categorie', 'categorie_charge'}:
                field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned_data = super().clean()
        categorie_charge = cleaned_data.get('categorie_charge')
        categorie = cleaned_data.get('categorie')
        if categorie_charge:
            cleaned_data['categorie'] = categorie_charge.code[:30]
        elif categorie:
            cleaned_data['categorie_charge'] = CategorieCharge.objects.filter(code=categorie).first()
        return cleaned_data

class StockRapportJournalierForm(forms.ModelForm):
    class Meta:
        model = StockRapportJournalier
        fields = ['designation', 'unite', 'quantite_entree', 'quantite_sortie', 'stock_restant']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

class SituationMensuelleForm(forms.ModelForm):
    periode = forms.CharField(label='Mois de la situation', required=False, widget=forms.TextInput(attrs={'type': 'month'}))
    class Meta:
        model = SituationMensuelle
        fields = ['annee', 'mois', 'date_debut', 'date_fin', 'observations']
        widgets = {
            'annee': forms.HiddenInput(),
            'mois': forms.HiddenInput(),
            'date_debut': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'lang': 'fr'}),
            'date_fin': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date', 'lang': 'fr'}),
            'observations': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, projet=None, **kwargs):
        self.projet = projet
        super().__init__(*args, **kwargs)
        self.order_fields([
            'periode', 'date_debut', 'date_fin', 'chiffre_affaires',
            'observations', 'annee', 'mois',
        ])
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'situation-field')
        self.fields['date_debut'].input_formats = ['%d/%m/%Y', '%Y-%m-%d']
        self.fields['date_fin'].input_formats = ['%d/%m/%Y', '%Y-%m-%d']
        if self.projet is None:
            self.projet = getattr(self.instance, 'projet', None)
        if self.instance.pk:
            self.initial['periode'] = f'{self.instance.annee:04d}-{self.instance.mois:02d}'
            if self.instance.date_debut:
                self.initial['date_debut'] = self.instance.date_debut.strftime('%Y-%m-%d')
            if self.instance.date_fin:
                self.initial['date_fin'] = self.instance.date_fin.strftime('%Y-%m-%d')
        else:
            today = timezone.localdate()
            self.initial['periode'] = today.strftime('%Y-%m')
            self.initial.setdefault('date_debut', today.replace(day=1).strftime('%Y-%m-%d'))
            next_month = (today.replace(day=28) + timezone.timedelta(days=4)).replace(day=1)
            self.initial.setdefault('date_fin', (next_month - timezone.timedelta(days=1)).strftime('%Y-%m-%d'))

    def clean(self):
        cleaned_data = super().clean()
        annee = cleaned_data.get('annee')
        mois = cleaned_data.get('mois')
        periode = cleaned_data.get('periode')
        if periode:
            try:
                annee, mois = (int(part) for part in periode.split('-'))
                cleaned_data['annee'] = annee
                cleaned_data['mois'] = mois
            except (TypeError, ValueError):
                self.add_error('periode', 'Sélectionnez un mois valide.')
        if annee is None or mois is None:
            self.add_error('periode', 'Sélectionnez un mois pour la situation.')
        elif not 1 <= mois <= 12:
            self.add_error('periode', 'Sélectionnez un mois valide.')
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        if annee and mois and 1 <= mois <= 12:
            premier_jour = date(int(annee), int(mois), 1)
            next_month = premier_jour.replace(day=28) + timezone.timedelta(days=4)
            dernier_jour = next_month.replace(day=1) - timezone.timedelta(days=1)
            if not date_debut:
                date_debut = premier_jour
                cleaned_data['date_debut'] = date_debut
            if not date_fin:
                date_fin = dernier_jour
                cleaned_data['date_fin'] = date_fin
            if date_debut < premier_jour:
                self.add_error('date_debut', 'La date de début doit appartenir au mois sélectionné.')
            if date_debut > dernier_jour:
                self.add_error('date_debut', 'La date de début doit appartenir au mois sélectionné.')
            if date_fin < premier_jour or date_fin > dernier_jour:
                self.add_error('date_fin', 'La date de fin doit appartenir au mois sélectionné.')
        if date_debut and date_fin and date_debut > date_fin:
            self.add_error('date_fin', 'La date de fin doit être postérieure ou égale à la date de début.')
        if annee and mois and self.projet:
            existantes = SituationMensuelle.objects.filter(
                projet=self.projet, annee=annee, mois=mois
            )
            if self.instance.pk:
                existantes = existantes.exclude(pk=self.instance.pk)
            if existantes.exists():
                self.add_error('mois', 'Une situation existe déjà pour cette période.')
        return cleaned_data

class RecetteSituationMensuelleForm(forms.ModelForm):
    montant = FrenchDecimalField(
        max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )

    class Meta:
        model = RecetteSituationMensuelle
        fields = ['rubrique', 'montant']
        widgets = {'rubrique': forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rubrique = self.initial.get('rubrique') or self.instance.rubrique
        self.rubrique_label = dict(RecetteSituationMensuelle.Rubrique.choices).get(rubrique, '')

    def clean_montant(self):
        return self.cleaned_data['montant'] or Decimal('0.00')

class DocumentSituationMensuelleForm(forms.ModelForm):
    class Meta:
        model = DocumentSituationMensuelle
        fields = ['fichier']
        widgets = {'fichier': forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif', 'class': 'document-file-input'})}

    def clean_fichier(self):
        fichier = self.cleaned_data['fichier']
        if fichier.size > 10 * 1024 * 1024:
            raise forms.ValidationError('Le document ne doit pas dépasser 10 Mo.')
        if os.path.splitext(fichier.name)[1].lower() not in {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.jpg', '.jpeg', '.png', '.gif'}:
            raise forms.ValidationError('Type de document non supporté.')
        digest = hashlib.sha256()
        for chunk in fichier.chunks():
            digest.update(chunk)
        fichier.seek(0)
        self.checksum = digest.hexdigest()
        return fichier

class DocumentSituationMensuelleBaseFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        checksums = set()
        existing = set(
            self.queryset.exclude(checksum='').values_list('checksum', flat=True)
        )
        for form in self.forms:
            if not hasattr(form, 'checksum') or form.cleaned_data.get('DELETE'):
                continue
            checksum = form.checksum
            if checksum in checksums or checksum in existing:
                raise forms.ValidationError(
                    'Ce document existe déjà dans cette situation mensuelle.'
                )
            checksums.add(checksum)

class DepenseSituationMensuelleForm(forms.ModelForm):
    categorie = forms.CharField(required=False, widget=forms.HiddenInput())
    designation = forms.CharField(required=False)
    categorie_charge = forms.IntegerField(required=False, widget=forms.HiddenInput())
    montant_base = FrenchDecimalField(
        max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    cession_entrante = FrenchDecimalField(
        max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    cession_sortante = FrenchDecimalField(
        max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )

    class Meta:
        model = DepenseSituationMensuelle
        fields = ['categorie', 'categorie_charge', 'designation', 'montant_base', 'cession_entrante', 'cession_sortante']

    def __init__(self, *args, categories_charge=None, **kwargs):
        super().__init__(*args, **kwargs)
        if categories_charge is None:
            categories_charge = CategorieCharge.objects.filter(
                Q(actif=True) | Q(pk=self.instance.categorie_charge_id)
            )
        self.categories_charge = {
            categorie.pk: categorie
            for categorie in categories_charge
        }
        montant_base_key = f'{self.prefix}-montant_base'
        montant_legacy_key = f'{self.prefix}-montant'
        if self.is_bound and montant_base_key not in self.data and montant_legacy_key in self.data:
            self.data = self.data.copy()
            self.data[montant_base_key] = self.data[montant_legacy_key]
        for name, field in self.fields.items():
            if name not in {'categorie', 'categorie_charge'}:
                field.widget.attrs.setdefault('class', 'form-control')

    def clean(self):
        cleaned_data = super().clean()
        designation = (cleaned_data.get('designation') or '').strip()
        montant_base = cleaned_data.get('montant_base')
        cession_entrante = cleaned_data.get('cession_entrante')
        cession_sortante = cleaned_data.get('cession_sortante')
        categorie = cleaned_data.get('categorie')
        categorie_charge_id = cleaned_data.get('categorie_charge')
        categorie_charge = self.categories_charge.get(categorie_charge_id)
        if categorie_charge_id and not categorie_charge:
            self.add_error('categorie_charge', 'Sélectionnez une catégorie valide.')
        cleaned_data['categorie_charge'] = categorie_charge
        if not any((designation, montant_base, cession_entrante, cession_sortante, categorie, categorie_charge)):
            return cleaned_data
        if not designation:
            self.add_error('designation', 'Indiquez une désignation pour cette charge.')
        categorie_charge = cleaned_data.get('categorie_charge')
        if categorie_charge:
            cleaned_data['categorie'] = categorie_charge.code[:30]
        elif categorie:
            cleaned_data['categorie_charge'] = next(
                (
                    categorie_connue
                    for categorie_connue in self.categories_charge.values()
                    if categorie_connue.code == categorie
                ),
                None,
            )
        return cleaned_data

    def clean_montant_base(self):
        return self.cleaned_data['montant_base'] or Decimal('0.00')

    def clean_cession_entrante(self):
        return self.cleaned_data['cession_entrante'] or Decimal('0.00')

    def clean_cession_sortante(self):
        return self.cleaned_data['cession_sortante'] or Decimal('0.00')

class StockSituationMensuelleForm(forms.ModelForm):
    qte_initiale = FrenchDecimalField(
        max_digits=15, decimal_places=3, required=False, initial=Decimal('0.000'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    pu_initial = FrenchDecimalField(
        max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    qte_entree = FrenchDecimalField(
        max_digits=15, decimal_places=3, required=False, initial=Decimal('0.000'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    pu_entree = FrenchDecimalField(
        max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    qte_sortie = FrenchDecimalField(
        max_digits=15, decimal_places=3, required=False, initial=Decimal('0.000'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    pu_sortie = FrenchDecimalField(
        max_digits=15, decimal_places=2, required=False, initial=Decimal('0.00'),
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )

    class Meta:
        model = StockSituationMensuelle
        fields = [
            'designation', 'unite',
            'qte_initiale', 'pu_initial',
            'qte_entree', 'pu_entree',
            'qte_sortie', 'pu_sortie',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

    def clean_qte_initiale(self): return self.cleaned_data['qte_initiale'] or Decimal('0.000')
    def clean_pu_initial(self):   return self.cleaned_data['pu_initial']   or Decimal('0.00')
    def clean_qte_entree(self):   return self.cleaned_data['qte_entree']   or Decimal('0.000')
    def clean_pu_entree(self):    return self.cleaned_data['pu_entree']    or Decimal('0.00')
    def clean_qte_sortie(self):   return self.cleaned_data['qte_sortie']   or Decimal('0.000')
    def clean_pu_sortie(self):    return self.cleaned_data['pu_sortie']    or Decimal('0.00')

class DepenseSituationMensuelleBaseFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        categories_charge = list(CategorieCharge.objects.filter(actif=True))
        existing_category_ids = set(
            kwargs.get('queryset', DepenseSituationMensuelle.objects.none())
            .exclude(categorie_charge_id=None)
            .values_list('categorie_charge_id', flat=True)
        )
        missing_ids = existing_category_ids.difference(
            categorie.pk for categorie in categories_charge
        )
        if missing_ids:
            categories_charge.extend(CategorieCharge.objects.filter(pk__in=missing_ids))
        form_kwargs = kwargs.setdefault('form_kwargs', {})
        form_kwargs['categories_charge'] = categories_charge
        super().__init__(*args, **kwargs)

DepenseRapportJournalierFormSet = forms.inlineformset_factory(
    RapportJournalier, DepenseRapportJournalier,
    form=DepenseRapportJournalierForm, extra=0, can_delete=True,
)

StockRapportJournalierFormSet = forms.inlineformset_factory(
    RapportJournalier, StockRapportJournalier,
    form=StockRapportJournalierForm, extra=0, can_delete=True,
)

DepenseSituationMensuelleFormSet = forms.inlineformset_factory(
    SituationMensuelle, DepenseSituationMensuelle,
    form=DepenseSituationMensuelleForm, formset=DepenseSituationMensuelleBaseFormSet,
    extra=0, can_delete=True,
)

StockSituationMensuelleFormSet = forms.inlineformset_factory(
    SituationMensuelle, StockSituationMensuelle,
    form=StockSituationMensuelleForm, extra=0, can_delete=True,
)

RecetteSituationMensuelleFormSet = forms.inlineformset_factory(
    SituationMensuelle, RecetteSituationMensuelle,
    form=RecetteSituationMensuelleForm, extra=0, can_delete=False,
)

RecetteSituationMensuelleInitialFormSet = forms.inlineformset_factory(
    SituationMensuelle, RecetteSituationMensuelle,
    form=RecetteSituationMensuelleForm, extra=3, can_delete=False,
)

DocumentSituationMensuelleFormSet = forms.inlineformset_factory(
    SituationMensuelle, DocumentSituationMensuelle,
    form=DocumentSituationMensuelleForm, formset=DocumentSituationMensuelleBaseFormSet,
    extra=1, can_delete=True,
)
