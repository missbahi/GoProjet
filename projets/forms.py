import os
from django import forms
from .models import Client, Decompte, Ingenieur, Profile, Projet, Entreprise, Tache, Attachement, OrdreService, TypeOrdreService
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.db.models import  Q 
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
            'localisation', 'entreprise'
            # 'client' retiré car absent du modèle / sinon l'ajouter explicitement dans fields
        ]
        COMMON_CSS_CLASSES = 'w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500'

        widgets = {
            'type_projet': forms.Select(attrs={'class': COMMON_CSS_CLASSES, 'placeholder': 'Type de projet'}),
            'nom': forms.TextInput(attrs={'class': COMMON_CSS_CLASSES, 'placeholder': 'Nom du projet *'}),
            'maitre_ouvrage': forms.TextInput(attrs={'class': COMMON_CSS_CLASSES, 'placeholder': 'Maître d\'ouvrage'}),
            'numero': forms.TextInput(attrs={'class': COMMON_CSS_CLASSES, 'placeholder': 'N° marché *'}),
            'objet': forms.Textarea(attrs={'class': COMMON_CSS_CLASSES, 'rows': 3, 'placeholder': 'Objet du projet *', 'style': 'min-height: auto;'}),
            'date_debut': forms.DateInput(attrs={'class': COMMON_CSS_CLASSES, 'type': 'date', 'placeholder': 'Date de début *'}),
            'delai': forms.NumberInput(attrs={'class': COMMON_CSS_CLASSES + ' text-right', 'step': '1', 'min': '1', 'max': '3650', 'placeholder': 'Délai en jours'}),
            'avancement': forms.NumberInput(attrs={'class': COMMON_CSS_CLASSES + ' text-right', 'step': '1', 'min': '0', 'max': '100', 'placeholder': 'Avancement en %'}),
            'statut': forms.Select(attrs={'class': COMMON_CSS_CLASSES, 'placeholder': 'Statut du projet'}),
            'montant': forms.NumberInput(attrs={'class': COMMON_CSS_CLASSES + ' text-right', 'placeholder': 'Montant estimé (DH)'}),
            'montant_soumission': forms.NumberInput(attrs={'class': COMMON_CSS_CLASSES + ' text-right', 'placeholder': 'Montant soumission (DH)'}),
            'localisation': forms.TextInput(attrs={'class': COMMON_CSS_CLASSES, 'placeholder': 'Localisation du projet'}),
            'entreprise': forms.Select(attrs={'class': COMMON_CSS_CLASSES, 'placeholder': 'Nom de l\'entreprise'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field.label_attrs = {'class': 'block text-sm font-medium text-gray-700 mb-1'}
            if field.required:
                field.label = (field.label or '') + ' *'

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
                'readonly': True
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

class DecompteForm(forms.ModelForm):
    class Meta:
        model = Decompte
        fields = [
            'attachement', 'type_decompte', 'numero', 'date_emission', 
            'date_echeance', 'statut', 'taux_tva', 'taux_retenue_garantie', 
            'taux_ras', 'autres_retenues', 'numero_bordereau', 'date_paiement', 
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
        super().__init__(*args, **kwargs)
        self.attachements_disponibles_count = kwargs.pop('attachements_disponibles_count', None)
        
        # Ajouter les classes CSS pour le style
        for field_name, field in self.fields.items():
            if hasattr(field, 'widget') and hasattr(field.widget, 'attrs'):
                field.widget.attrs.update({'class': 'form-control'})
                
        self.fields['attachement'].empty_label = None
        
        print('attachements_disponibles_count :', self.attachements_disponibles_count)
        if (self.attachements_disponibles_count == 1 and 
            'attachement' in self.fields):  
            # Si il n'y a qu'un seul attachement disponible, le mettre en readonly
            self.fields['attachement'].widget.attrs.update({
                'readonly': 'readonly',
                'class': 'form-control bg-gray-700 cursor-not-allowed'
            })
            # Stocker la valeur pour qu'elle soit sauvegardée malgré le disabled
            if self.fields['attachement'].queryset.count() == 1:
                seul_attachement = self.fields['attachement'].queryset.first()
                self.fields['attachement'].initial = seul_attachement
    
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