from decimal import Decimal
import os
from django import forms

from projets.models.projet import DocumentAdministratif

# from projets.models.revision import RevisionPrix
from .models import Client, Decompte, Ingenieur, Profile, Projet, Entreprise, Tache, Attachement, OrdreService

from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
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
            'type_projet', 'nom', 'maitre_ouvrage', 'numero', 'objet', 'date_debut',
            'delai', 'avancement', 'statut', 'montant', 'montant_soumission',
            'localisation', 'entreprise', 'revisable'
        ]
        widgets = {
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
            'localisation': forms.TextInput(attrs={'placeholder': 'Localisation du projet'}),
            'entreprise': forms.Select(attrs={'placeholder': 'Nom de l\'entreprise'}),
            'revisable': forms.CheckboxInput(attrs={'class': 'hidden peer', 'id': 'revisable-toggle'
            }),
            
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['revisable'].label = "Projet révisable"
        self.fields['revisable'].help_text = "Les prix seront ajustés selon les indices officiels"
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
                'class': 'form-input file-upload'
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