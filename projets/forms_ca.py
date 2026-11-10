from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from projets.models import ChiffreAffaire


class ChiffreAffaireForm(forms.ModelForm):
    mois = forms.CharField(label='Mois du CA', widget=forms.TextInput(attrs={'type': 'month'}))

    class Meta:
        model = ChiffreAffaire
        fields = ['origine', 'observations']
        widgets = {'observations': forms.Textarea(attrs={'rows': 1})}

    def __init__(self, *args, projet, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.projet = projet
        if self.instance.pk:
            self.initial['mois'] = self.instance.periode.strftime('%Y-%m')
            self.fields['mois'].disabled = True
            self.fields['origine'].disabled = True
        elif projet.chiffres_affaires.exists():
            self.fields['origine'].disabled = True
            self.fields['mois'].disabled = True
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-control'

    def clean_mois(self):
        try:
            periode = date.fromisoformat(self.cleaned_data['mois'] + '-01')
        except ValueError as error:
            raise ValidationError('Sélectionnez un mois valide.') from error
        self.instance.periode = periode
        return periode
