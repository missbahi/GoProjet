from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from projets.models import Projet
from projets.modules import MODULE_CHOICES
from projets.user_policy import (
    RETIRED_ROLES, dossiers_affectables, peut_agir_utilisateur,
    roles_assignables, valider_dossiers_utilisateur,
)


class UtilisateurModificationForm(forms.Form):
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    password = forms.CharField(required=False, strip=False)
    confirm_password = forms.CharField(required=False, strip=False)
    role = forms.ChoiceField(required=False)
    is_active = forms.BooleanField(required=False)
    dossiers = forms.ModelMultipleChoiceField(queryset=None, required=False)
    avatar = forms.ImageField(required=False)
    modules = forms.MultipleChoiceField(choices=MODULE_CHOICES, required=False)

    def __init__(self, *args, actor, target, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor, self.target = actor, target
        self.permissions = {
            'role': peut_agir_utilisateur(actor, target, 'role'),
            'is_active': peut_agir_utilisateur(actor, target, 'status'),
            'dossiers': peut_agir_utilisateur(actor, target, 'dossiers'),
            'password': peut_agir_utilisateur(actor, target, 'password'),
            'modules': peut_agir_utilisateur(actor, target, 'modules'),
        }
        self.fields['role'].choices = roles_assignables(actor)
        if self.is_bound and self.data.get('role') and self.data['role'] not in {
            value for value, _ in self.fields['role'].choices
        }:
            raise PermissionDenied("Ce rôle ne peut pas être attribué.")
        self.fields['dossiers'].queryset = dossiers_affectables(actor)
        for field in ('role', 'is_active', 'dossiers', 'modules'):
            if not self.permissions[field]:
                self.fields.pop(field)
        if not self.permissions['password']:
            self.fields.pop('password')
            self.fields.pop('confirm_password')

    def clean(self):
        cleaned = super().clean()
        target = self.target
        for field, permitted in self.permissions.items():
            if permitted:
                continue
            if field == 'dossiers' and field in self.data:
                raise PermissionDenied("Seul l'Admin peut changer l'appartenance au dossier.")
            supplied = self.data.getlist(field) if hasattr(self.data, 'getlist') else self.data.get(field)
            if supplied:
                raise PermissionDenied("Ce champ ne peut pas être modifié sur ce compte.")
        if not self.permissions['password'] and self.data.get('confirm_password'):
            raise PermissionDenied
        role = target.profile.role
        if self.permissions['role']:
            selected = cleaned.get('role')
            if selected:
                role = selected
            elif role not in RETIRED_ROLES:
                self.add_error('role', "Sélectionnez un rôle autorisé.")
        self.resulting_role = role
        # A local administrator may promote an account, but must not reset its
        # password or deactivate it in the same request as the promotion.
        if role == 'ADMIN_DOSSIER' and not self.actor.is_superuser and target.pk != self.actor.pk:
            if cleaned.get('password') or (
                self.permissions['is_active'] and not cleaned.get('is_active')
            ):
                raise PermissionDenied("Seul l'Admin peut désactiver ou réinitialiser ce compte.")
        password = cleaned.get('password')
        if password or cleaned.get('confirm_password'):
            if password != cleaned.get('confirm_password'):
                self.add_error('confirm_password', "Les mots de passe ne correspondent pas.")
            if password:
                try:
                    password_validation.validate_password(password, target)
                except ValidationError as exc:
                    self.add_error('password', exc)
        if cleaned.get('avatar') and cleaned['avatar'].size > 5 * 1024 * 1024:
            self.add_error('avatar', "L'avatar ne doit pas dépasser 5 Mo.")
        self.resulting_dossiers = list(target.dossiers.all())
        if self.permissions['dossiers'] and 'dossiers' in cleaned:
            selected = list(cleaned['dossiers'])
            if not self.actor.is_superuser:
                permitted = self.fields['dossiers'].queryset
                selected.extend(target.dossiers.exclude(pk__in=permitted.values('pk')))
            self.resulting_dossiers = selected
        try:
            valider_dossiers_utilisateur(target, role, self.resulting_dossiers)
        except ValidationError as exc:
            self.add_error(None, exc)
        # Moving an account must be explicit, not leave cross-dossier project
        # permissions dormant and capable of resurfacing later.
        scope_changed = (
            {d.pk for d in self.resulting_dossiers}
            != set(target.dossiers.values_list('pk', flat=True))
            or role != target.profile.role
        )
        if scope_changed and role != 'OBSERVATEUR' and target.projets.exclude(
            dossier__in=self.resulting_dossiers,
        ).exists():
            self.add_error(None, "Retirez d'abord les projets hors des dossiers sélectionnés.")
        return cleaned

    @transaction.atomic
    def save(self):
        target = self.target
        # This order permits an explicit observer -> single-dossier transition.
        if self.permissions['dossiers']:
            target.dossiers.set(self.resulting_dossiers)
        for name in ('email', 'first_name', 'last_name'):
            setattr(target, name, self.cleaned_data[name])
        if self.permissions['is_active']:
            target.is_active = self.cleaned_data['is_active']
        if self.cleaned_data.get('password'):
            target.set_password(self.cleaned_data['password'])
        target.profile.role = self.resulting_role
        if self.resulting_role == 'OBSERVATEUR':
            target.is_staff = False
        if self.permissions['modules']:
            # Les cases cochées sont les modules disponibles ; le reste est désactivé.
            disponibles = set(self.cleaned_data.get('modules') or [])
            target.profile.modules_desactives = [
                key for key, _label in MODULE_CHOICES if key not in disponibles
            ]
        if self.cleaned_data.get('avatar'):
            target.profile.avatar = self.cleaned_data['avatar']
        target.save()
        target.profile.save()
        return target
