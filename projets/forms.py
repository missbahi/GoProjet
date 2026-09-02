from decimal import Decimal
from datetime import date
import hashlib
import os
from django import forms
from django.forms.models import BaseInlineFormSet
from django.db.models import Q

from projets.models.projet import DocumentAdministratif

# from projets.models.revision import RevisionPrix
from .models import (
    Client, Decompte, Dossier, Ingenieur, Profile, Projet, Entreprise, Tache,
    Attachement, OrdreService, RapportJournalier, DepenseRapportJournalier,
    StockRapportJournalier, SituationMensuelle, DepenseSituationMensuelle,
    StockSituationMensuelle, DocumentSituationMensuelle, Personnel, Materiel,
    Location, SousTraitance, Consommable, Fourniture,
)

from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.utils.translation import gettext_lazy as _
from django.utils import timezone


class FrenchDecimalField(forms.DecimalField):
    def to_python(self, value):
        if isinstance(value, str):
            value = value.replace('\u00a0', '').replace(' ', '').replace(',', '.')
        return super().to_python(value)

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
            'delai', 'avancement', 'statut', 'montant', 'montant_soumission', 'taux_tva',
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
            'delai': forms.NumberInput(attrs={'class': ' text-right', 'placeholder': 'Délai en jours'}),
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

class PersonnelForm(forms.ModelForm):
    class Meta:
        model = Personnel
        fields = ['nom', 'fonction', 'telephone', 'unite', 'tarif', 'actif']

class MaterielForm(forms.ModelForm):
    class Meta:
        model = Materiel
        fields = ['designation', 'type_materiel', 'immatriculation', 'unite', 'prix_unitaire', 'actif']

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


class TacheForm(forms.ModelForm):
    class Meta:
        model = Tache
        fields = '__all__'
        widgets = {
            'date_debut': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'date_fin': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea'}),
            'priorite': forms.Select(attrs={'class': 'form-select'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            if field not in ['terminee', 'description']:
                self.fields[field].widget.attrs.update({'class': 'form-input'})

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
    class Meta:
        model = DocumentAdministratif
        fields = ['projet', 'type_document', 'fichier', 'date_remise', 'description', 'original_filename']
        widgets = {
            'fichier': forms.FileInput(attrs={
            'accept': 'image/*,video/*,.pdf,.doc,.docx',
            'capture': 'environment',  # 'environment' pour caméra arrière, 'user' pour frontale
            'multiple': False,
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = DocumentAdministratif.TYPE_CHOICES
        self.fields['type_document'].widget = forms.Select(choices=choices)
        # Adapté pour mobile
        self.fields['fichier'].widget.attrs.update({
            'accept': 'image/*,video/*,.pdf,.doc,.docx',
            'capture': 'environment',  # 'environment' pour caméra arrière, 'user' pour frontale
            'multiple': False,  # Pour iOS/Android, évitez multiple sur mobile
        })
        
        self.fields['type_document'].widget.attrs.update({
            'class': 'form-select',
            'required': 'required',
        })

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
    class Meta:
        model = DepenseRapportJournalier
        fields = ['categorie', 'designation', 'quantite', 'unite', 'prix_unitaire', 'observations']
        widgets = {
            'categorie': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'categorie':
                field.widget.attrs.setdefault('class', 'form-control')

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
    chiffre_affaires = FrenchDecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'situation-field js-french-number'}),
    )
    class Meta:
        model = SituationMensuelle
        fields = ['annee', 'mois', 'date_debut', 'date_fin', 'chiffre_affaires', 'observations']
        widgets = {
            'annee': forms.HiddenInput(),
            'mois': forms.HiddenInput(),
            'date_debut': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'date_fin': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
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
        date_debut = cleaned_data.get('date_debut')
        date_fin = cleaned_data.get('date_fin')
        if annee and mois:
            if not date_debut:
                date_debut = date(int(annee), int(mois), 1)
                cleaned_data['date_debut'] = date_debut
            if not date_fin:
                next_month = date_debut.replace(day=28) + timezone.timedelta(days=4)
                cleaned_data['date_fin'] = next_month.replace(day=1) - timezone.timedelta(days=1)
        if date_debut and date_fin and date_debut > date_fin:
            self.add_error('date_fin', 'La date de fin doit être postérieure à la date de début.')
        if annee and mois and self.projet:
            existantes = SituationMensuelle.objects.filter(
                projet=self.projet, annee=annee, mois=mois
            )
            if self.instance.pk:
                existantes = existantes.exclude(pk=self.instance.pk)
            if existantes.exists():
                self.add_error('mois', 'Une situation existe déjà pour cette période.')
        return cleaned_data


class DocumentSituationMensuelleForm(forms.ModelForm):
    class Meta:
        model = DocumentSituationMensuelle
        fields = ['fichier']
        widgets = {'fichier': forms.FileInput(attrs={'accept': '.pdf,.doc,.docx,.xls,.xlsx,.jpg,.jpeg,.png,.gif'})}

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
    montant = FrenchDecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    class Meta:
        model = DepenseSituationMensuelle
        fields = ['categorie', 'designation', 'montant']
        widgets = {'categorie': forms.HiddenInput()}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if name != 'categorie':
                field.widget.attrs.setdefault('class', 'form-control')

class StockSituationMensuelleForm(forms.ModelForm):
    quantite = FrenchDecimalField(
        max_digits=12, decimal_places=3,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    prix_unitaire = FrenchDecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.TextInput(attrs={'inputmode': 'decimal', 'class': 'form-control js-french-number'}),
    )
    class Meta:
        model = StockSituationMensuelle
        fields = ['designation', 'unite', 'quantite', 'prix_unitaire']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')

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
    form=DepenseSituationMensuelleForm, extra=0, can_delete=True,
)
StockSituationMensuelleFormSet = forms.inlineformset_factory(
    SituationMensuelle, StockSituationMensuelle,
    form=StockSituationMensuelleForm, extra=0, can_delete=True,
)
DocumentSituationMensuelleFormSet = forms.inlineformset_factory(
    SituationMensuelle, DocumentSituationMensuelle,
    form=DocumentSituationMensuelleForm, formset=DocumentSituationMensuelleBaseFormSet,
    extra=1, can_delete=True,
)
