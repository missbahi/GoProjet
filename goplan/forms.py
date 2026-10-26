from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.forms.models import BaseInlineFormSet, inlineformset_factory
from .models import GPlan, GPlanPrintSettings, GTask
from .services.calendar import get_calendar_for_plan
from .services.dependencies import recalculate_group_rollups


class GPlanForm(forms.ModelForm):
    class Meta:
        model = GPlan
        fields = ['nom', 'description', 'date_debut', 'date_fin_cible', 'date_etat', 'calendrier']
        widgets = {
            'nom': forms.TextInput(attrs={'placeholder': 'Ex : Planning chantier A'}),
            'description': forms.Textarea(attrs={'rows': 3}),
            # ⚡ format ISO obligatoire pour <input type="date">
            'date_debut': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date'},
            ),
            'date_fin_cible': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'type': 'date'},
            ),
            'date_etat': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Forcer les input_formats pour accepter les dates ISO
        self.fields['date_debut'].input_formats = ['%Y-%m-%d']
        self.fields['date_fin_cible'].input_formats = ['%Y-%m-%d']
        self.fields['date_etat'].input_formats = ['%Y-%m-%d']

        # Appliquer la classe CSS
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'app-modal-input')

        self.fields['calendrier'].empty_label = "— Sélectionner un calendrier —"


class GPlanAppearanceForm(forms.ModelForm):
    class Meta:
        model = GPlan
        fields = [
            "gantt_arrondi", "gantt_epaisseur", "gantt_groupe",
            "gantt_jalon", "gantt_liaison", "gantt_couleur_liaison",
        ]
        widgets = {"gantt_couleur_liaison": forms.TextInput(attrs={"type": "color"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "app-modal-input")


class GPlanPrintSettingsForm(forms.ModelForm):
    class Meta:
        model = GPlanPrintSettings
        exclude = ["plan", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("period_start", "period_end"):
            self.fields[name].input_formats = ["%Y-%m-%d"]


class GTaskScheduleForm(forms.ModelForm):
    """Shared task fields and working-calendar validation."""

    class Meta:
        model = GTask
        fields = [
            'code', 'nom', 'type_tache', 'duree',
            'date_debut', 'date_fin', 'contrainte', 'date_contrainte', 'avancement',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'placeholder': 'T-001'}),
            'nom': forms.TextInput(attrs={'placeholder': 'Désignation'}),
            'date_debut': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'date_fin': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'date_contrainte': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'duree': forms.NumberInput(attrs={'step': '0.5', 'min': '0'}),
            'avancement': forms.NumberInput(attrs={'step': '5', 'min': '0', 'max': '100'}),
        }

    def __init__(self, *args, calendar_service=None, group_schedule=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.calendar_service = calendar_service
        self.fields['date_debut'].input_formats = ['%Y-%m-%d']
        self.fields['date_fin'].input_formats = ['%Y-%m-%d']
        self.fields['date_contrainte'].input_formats = ['%Y-%m-%d']
        self.fields['code'].required = False
        self.fields['date_debut'].required = False
        self.fields['date_fin'].required = False
        self.fields['duree'].required = False
        self.group_schedule = (
            self.instance.type_tache == GTask.Type.GROUPE
            if group_schedule is None else group_schedule
        )
        if self.group_schedule:
            self.initial["type_tache"] = GTask.Type.GROUPE
            for name in ("type_tache", "duree", "date_debut", "date_fin"):
                self.fields[name].disabled = True

    def clean(self):
        cleaned = super().clean()
        constraint = GTask(
            contrainte=cleaned.get("contrainte", GTask.Contrainte.ASAP),
            date_contrainte=cleaned.get("date_contrainte"),
        )
        try:
            constraint.validate_constraint_dates(None, None)
        except ValidationError as error:
            self.add_error(None, error)
        if self.group_schedule:
            requested_type = self.data.get(self.add_prefix("type_tache"))
            if requested_type not in (None, "", GTask.Type.TACHE, GTask.Type.GROUPE):
                self.add_error("type_tache", "Une tâche avec des sous-tâches doit rester un groupe.")
            return cleaned
        debut = cleaned.get("date_debut")
        fin = cleaned.get("date_fin")
        duree = cleaned.get("duree")

        svc = self.calendar_service
        if svc is None:
            return cleaned
        if cleaned.get("type_tache") == GTask.Type.JALON:
            cleaned["duree"] = 0
            if debut:
                cleaned["date_fin"] = debut
            try:
                constraint.validate_constraint_dates(cleaned.get("date_debut"), cleaned.get("date_fin"))
            except ValidationError as error:
                self.add_error(None, error)
            return cleaned
        if duree is not None and (duree <= 0 or duree * 2 != int(duree * 2)):
            self.add_error("duree", "La durée doit être positive, par pas d'une demi-journée.")
            return cleaned
        try:
            if debut:
                debut = svc.next_working_day(debut)
                cleaned["date_debut"] = debut
            if duree is None and "duree" not in self.errors:
                if debut and fin:
                    duree = svc.working_days_between(debut, fin)
                    if not duree:
                        self.add_error("date_fin", "La période ne contient aucun jour ouvré.")
                        return cleaned
                    cleaned["duree"] = duree
                else:
                    self.add_error("duree", "Renseignez la durée ou les deux dates.")
            if debut and duree is not None:
                cleaned["date_fin"] = svc.add_working_days(debut, duree)
            constraint.validate_constraint_dates(cleaned.get("date_debut"), cleaned.get("date_fin"))
        except ValidationError as error:
            self.add_error(None, error)
        return cleaned


class GTaskInlineForm(GTaskScheduleForm):
    node_key = forms.CharField(widget=forms.HiddenInput(), max_length=100)
    parent_key = forms.CharField(widget=forms.HiddenInput(), required=False, max_length=100)

    class Meta(GTaskScheduleForm.Meta):
        fields = GTaskScheduleForm.Meta.fields + ['ordre', 'couleur']
        widgets = {
            **GTaskScheduleForm.Meta.widgets,
            'ordre': forms.HiddenInput(),
            'couleur': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ordre'].required = False
        self.initial['node_key'] = str(self.instance.pk) if self.instance.pk else f'new-{self.prefix}'
        self.initial['parent_key'] = str(self.instance.parent_id or '')
        if not self.instance.pk:
            self.initial['ordre'] = 2147483647

    def has_changed(self):
        # L'ordre et les cles techniques ne doivent pas remplir la ligne vide.
        return any(name not in {'node_key', 'parent_key', 'ordre'} for name in self.changed_data)


class GTaskGanttForm(GTaskScheduleForm):
    """Single-task editing, sharing the inline calendar validation."""

    class Meta(GTaskScheduleForm.Meta):
        fields = GTaskScheduleForm.Meta.fields + ['couleur']
        widgets = {**GTaskScheduleForm.Meta.widgets, 'couleur': forms.HiddenInput()}

    def __init__(self, *args, children_count=None, **kwargs):
        self._children_count = children_count
        super().__init__(*args, **kwargs)
        self.fields['avancement'].widget.attrs['step'] = '0.01'

    def clean_couleur(self):
        if self.add_prefix('couleur') not in self.data:
            return self.instance.couleur
        value = self.cleaned_data['couleur']
        if value and not (
            len(value) == 7 and value.startswith('#')
            and all(char in '0123456789abcdefABCDEF' for char in value[1:])
        ):
            raise ValidationError("Choisissez une couleur au format #RRGGBB.")
        return value.lower()

    def clean_avancement(self):
        value = self.cleaned_data['avancement']
        if not 0 <= value <= 100:
            raise ValidationError("L'avancement doit être compris entre 0 et 100.")
        return value

    def clean(self):
        cleaned = super().clean()
        self.instance.type_tache = cleaned.get('type_tache', self.instance.type_tache)
        if self._children_count is not None:
            children_count = self._children_count
        else:
            children_count = self.instance.sous_taches.count() if self.instance.pk else 0
        try:
            self.instance.validate_task_type(children_count)
        except ValidationError as error:
            self.add_error(None, error)
        return cleaned


_INLINE_UPDATE_FIELDS = [
    "parent", "ordre", "type_tache", "code", "nom", "duree",
    "date_debut", "date_fin", "contrainte", "date_contrainte", "avancement",
]

_REVISION_TASK_FIELDS = tuple(
    field.attname for field in GTask._meta.concrete_fields
    if field.attname not in GTask.DISPLAY_STATE_FIELDS
)


def _task_state_tuple(task):
    return (
        task.parent_id,
        task.ordre,
        task.type_tache,
        task.code,
        task.nom,
        task.duree,
        task.date_debut,
        task.date_fin,
        task.contrainte,
        task.date_contrainte,
        task.avancement,
    )


class BaseGTaskInlineFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calendar_error = None
        try:
            self.calendar_service = get_calendar_for_plan(self.instance)
        except ValidationError as error:
            self.calendar_service = None
            self.calendar_error = error
        tasks = list(self.get_queryset())
        self._tasks_list = tasks
        self._tasks_by_pk = {task.pk: task for task in tasks}
        self._db_snapshots = {task.pk: _task_state_tuple(task) for task in tasks}
        self._pre_rollup_revision_values = None

        if self.is_bound:
            self.group_keys = set()
            for index in range(self.total_form_count()):
                prefix = self.add_prefix(index)
                deleted = forms.BooleanField(required=False).to_python(self.data.get(f"{prefix}-DELETE"))
                if not deleted and (self.data.get(f"{prefix}-id") or self.data.get(f"{prefix}-nom")):
                    parent_key = self.data.get(f"{prefix}-parent_key")
                    if parent_key:
                        self.group_keys.add(parent_key)
        else:
            self.group_keys = {str(task.parent_id) for task in tasks if task.parent_id}
            self._pre_rollup_revision_values = [
                {attname: getattr(task, attname) for attname in _REVISION_TASK_FIELDS}
                for task in tasks
            ]
            if self.calendar_service:
                try:
                    recalculate_group_rollups(
                        self.instance, tasks, self.calendar_service, persist=False,
                    )
                except ValidationError as error:
                    self.calendar_error = error

    def get_form_kwargs(self, index):
        kwargs = super().get_form_kwargs(index)
        kwargs["calendar_service"] = self.calendar_service
        if self.is_bound and index is not None:
            key = self.data.get(f"{self.add_prefix(index)}-node_key", "")
        elif index is not None and index < self.initial_form_count():
            key = str(self.get_queryset()[index].pk)
        else:
            key = f"new-{self.add_prefix(index)}"
        kwargs["group_schedule"] = key in self.group_keys
        return kwargs

    def add_fields(self, form, index):
        super().add_fields(form, index)
        id_field = form.fields['id']
        id_field.queryset = self.get_queryset()
        tasks_by_pk = self._tasks_by_pk

        # Évite la requête SQL unitaire `queryset.get(pk=...)` de ModelChoiceField.to_python par ligne
        def _fast_to_python(value):
            if value in id_field.empty_values:
                return None
            if isinstance(value, GTask):
                return value
            try:
                key = int(str(value))
            except (ValueError, TypeError):
                raise ValidationError(
                    id_field.error_messages["invalid_choice"],
                    code="invalid_choice",
                    params={"value": value},
                )
            obj = tasks_by_pk.get(key)
            if obj is None:
                raise ValidationError(
                    id_field.error_messages["invalid_choice"],
                    code="invalid_choice",
                    params={"value": value},
                )
            return obj

        id_field.to_python = _fast_to_python

    def clean(self):
        super().clean()
        if self.calendar_error:
            raise self.calendar_error
        if any(self.errors):
            return

        submitted_ids = []
        active = {}
        for form in self.forms:
            task = form.cleaned_data.get('id')
            if form.instance.pk:
                if not task or task.pk != form.instance.pk:
                    raise ValidationError("Identifiant de tâche invalide. Rechargez le planning.")
                submitted_ids.append(task.pk)
            elif task:
                raise ValidationError("Identifiant de tâche invalide. Rechargez le planning.")
            if self._should_delete_form(form) or (not form.instance.pk and not form.has_changed()):
                continue
            key = form.cleaned_data['node_key']
            expected = str(form.instance.pk) if form.instance.pk else f'new-{form.prefix}'
            if key != expected or key in active:
                form.add_error('node_key', "Identifiant de ligne invalide ou dupliqué.")
            active[key] = form

        expected_ids = set(self._tasks_by_pk)
        if len(submitted_ids) != len(set(submitted_ids)) or set(submitted_ids) != expected_ids:
            raise ValidationError("Le contenu du planning a changé ou est incomplet. Rechargez la page.")
        if any(self.errors):
            return

        children = {key: [] for key in active}
        roots = []
        for key, form in active.items():
            parent = form.cleaned_data['parent_key']
            if parent == key:
                form.add_error('parent_key', "Une tâche ne peut pas être son propre parent.")
            elif parent and parent not in active:
                form.add_error('parent_key', "Le parent est absent, vide, supprimé ou hors de ce planning.")
            elif parent:
                children[parent].append(key)
            else:
                roots.append(key)
        if any(self.errors):
            return

        visited = set()
        for key in active:
            path = set()
            current = key
            while current and current not in visited:
                if current in path:
                    raise ValidationError("La hiérarchie contient un cycle.")
                path.add(current)
                current = active[current].cleaned_data['parent_key']
            visited.update(path)

        for key, form in active.items():
            task = form.instance
            if children[key] and task.type_tache == GTask.Type.TACHE:
                task.type_tache = GTask.Type.GROUPE
            elif not children[key] and task.type_tache == GTask.Type.GROUPE:
                task.type_tache = GTask.Type.TACHE
            try:
                task.validate_task_type(len(children[key]))
            except ValidationError as error:
                form.add_error(None, error)
        if any(self.errors):
            return

        def order_key(key):
            return active[key].cleaned_data.get('ordre') or 0

        roots.sort(key=order_key)
        for siblings in children.values():
            siblings.sort(key=order_key)
        self.hierarchy_forms = []
        pending = list(reversed(roots))
        while pending:
            key = pending.pop()
            self.hierarchy_forms.append(active[key])
            pending.extend(reversed(children[key]))

    @transaction.atomic
    def save(self, commit=True):
        if not commit:
            raise ValueError("La sauvegarde de la hiérarchie exige commit=True.")
        if not self.is_valid():
            raise ValueError("Le formset doit être valide avant la sauvegarde.")

        saved = {}
        to_update = []
        for order, form in enumerate(self.hierarchy_forms):
            task = form.instance
            task.plan = self.instance
            parent_key = form.cleaned_data['parent_key']
            parent_obj = saved[parent_key] if parent_key else None
            task.parent = parent_obj
            task.parent_id = parent_obj.pk if parent_obj else None
            task.ordre = order
            if task.pk is None:
                task.save()
            elif _task_state_tuple(task) != self._db_snapshots.get(task.pk):
                to_update.append(task)
            saved[form.cleaned_data['node_key']] = task

        # Les enfants déplacés sont persistés en un seul bulk_update avant les suppressions CASCADE.
        if to_update:
            GTask.objects.bulk_update(to_update, _INLINE_UPDATE_FIELDS)

        for form in self.deleted_forms:
            if form.instance.pk:
                form.instance.delete()

        saved_list = list(saved.values())
        recalculate_group_rollups(self.instance, saved_list, self.calendar_service)
        return saved_list


GTaskInlineFormSet = inlineformset_factory(
    GPlan, GTask,
    form=GTaskInlineForm,
    formset=BaseGTaskInlineFormSet,
    extra=1, 
    can_delete=True,
    validate_min=False,
)


class GTaskModelForm(forms.ModelForm):
    class Meta:
        model = GTask
        fields = '__all__'

    def clean(self):
        cleaned = super().clean()
        self.instance.type_tache = cleaned.get('type_tache', self.instance.type_tache)
        children_count = self.instance.sous_taches.count() if self.instance.pk else 0
        try:
            self.instance.validate_task_type(children_count)
        except ValidationError as error:
            self.add_error(None, error)
        return cleaned