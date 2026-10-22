# goplan/calendar_forms.py
from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from .models import GCalendarException, GWorkCalendar


WEEKDAYS = [
    (1, "Lundi"), (2, "Mardi"), (3, "Mercredi"), (4, "Jeudi"),
    (5, "Vendredi"), (6, "Samedi"), (7, "Dimanche"),
]


class CalendarForm(forms.ModelForm):
    jours_ouvres = forms.TypedMultipleChoiceField(
        label="Jours ouvrés", choices=WEEKDAYS, coerce=int,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = GWorkCalendar
        fields = ["nom", "jours_ouvres", "heures_par_jour", "is_default"]
        widgets = {
            "heures_par_jour": forms.NumberInput(
                attrs={"min": "0.01", "max": "24", "step": "0.01"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("nom", "heures_par_jour"):
            self.fields[name].widget.attrs["class"] = "app-modal-input"
        # ⚡ Normalise jours_ouvres : JSON peut contenir ["1","2"] ou [1,2]
        if self.instance.pk and self.instance.jours_ouvres:
            try:
                self.initial["jours_ouvres"] = [
                    int(j) for j in self.instance.jours_ouvres
                ]
            except (TypeError, ValueError):
                pass
        elif not self.instance.pk:
            self.initial["jours_ouvres"] = [1, 2, 3, 4, 5]

    def clean_heures_par_jour(self):
        hours = self.cleaned_data["heures_par_jour"]
        if not Decimal("0") < hours <= Decimal("24"):
            raise forms.ValidationError(
                "Indiquez un nombre d'heures supérieur à zéro et inférieur ou égal à 24."
            )
        return hours


class GCalendarExceptionForm(forms.ModelForm):
    class Meta:
        model = GCalendarException
        fields = ["date", "heures"]
        widgets = {
            "date": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date", "class": "app-modal-input"},
            ),
            "heures": forms.NumberInput(
                attrs={"min": "0", "max": "24", "step": "0.01", "class": "app-modal-input"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["date"].input_formats = ["%Y-%m-%d"]
        self.fields["date"].required = True

    def has_changed(self):
        if self.is_bound and not self.instance.pk and all(
            not self.data.get(self.add_prefix(name)) for name in ("date", "heures")
        ):
            return False
        return super().has_changed()

    def clean_heures(self):
        hours = self.cleaned_data["heures"]
        if not 0 <= hours <= 24:
            raise forms.ValidationError("Les heures doivent être comprises entre 0 et 24.")
        return hours


CalendarExceptionFormSet = inlineformset_factory(
    GWorkCalendar, GCalendarException,
    form=GCalendarExceptionForm,
    extra=1, can_delete=True, validate_min=False,
)