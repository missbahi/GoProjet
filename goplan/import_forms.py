from django import forms


MAX_XML_BYTES = 5 * 1024 * 1024


class XmlImportForm(forms.Form):
    fichier = forms.FileField(
        label="Fichier MS Project XML",
        widget=forms.ClearableFileInput(attrs={"accept": ".xml,application/xml,text/xml"}),
    )
    accepter_remplacement = forms.BooleanField(
        required=True,
        label="J'accepte de remplacer définitivement tout le contenu de ce planning, "
              "y compris son titre, sa description et son rattachement projet.",
    )

    def __init__(self, *args, replacing=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not replacing:
            del self.fields["accepter_remplacement"]

    def clean_fichier(self):
        upload = self.cleaned_data["fichier"]
        if not upload.name.lower().endswith(".xml"):
            raise forms.ValidationError("Sélectionnez un fichier .xml.")
        if not 0 < upload.size <= MAX_XML_BYTES:
            raise forms.ValidationError("Le fichier XML doit être non vide et ne pas dépasser 5 Mo.")
        return upload


class ImportedPlanForm(forms.Form):
    nom = forms.CharField(label="Titre du planning", max_length=200)
    description = forms.CharField(label="Description", required=False, widget=forms.Textarea(attrs={"rows": 3}))
    date_debut = forms.DateField(label="Date de début importée", disabled=True)
    date_fin_cible = forms.DateField(label="Date de fin importée", required=False, disabled=True)
    date_etat = forms.DateField(label="Date d'état importée", required=False, disabled=True)
    calendrier = forms.CharField(label="Calendrier importé", required=False, disabled=True)
    accepter_remplacement = forms.BooleanField(
        label="Je confirme le remplacement définitif de ce planning.", required=True,
    )

    def __init__(self, *args, imported, replacing=False, **kwargs):
        initial = {
            "nom": imported.nom, "description": imported.description,
            "date_debut": imported.date_debut, "date_fin_cible": imported.date_fin_cible,
            "date_etat": imported.date_etat,
            "calendrier": str(imported.calendrier) if imported.calendrier_id else "Standard lundi-vendredi",
        }
        super().__init__(*args, initial=initial, **kwargs)
        if not replacing:
            del self.fields["accepter_remplacement"]
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "app-modal-input"
