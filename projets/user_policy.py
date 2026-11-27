"""Account-management permissions, shared by forms, views and templates."""
from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q

from projets.decorators import (
    dossier_utilisateur, dossiers_accessibles, est_admin_dossier,
    est_directeur_projet, projets_accessibles,
)
from projets.models import Dossier, Profile


DIRECTOR_ROLES = frozenset({'CHEF_PROJET', 'CHEF_CHANTIER', 'POINTEUR'})
RETIRED_ROLES = frozenset({'STAFF', 'UTILISATEUR'})
HOLDING_ROLE = 'A_RECLASSER'


def roles_assignables(actor):
    choices = Profile.ROLE_CHOICES
    if actor and actor.is_superuser:
        return list(choices)
    if actor and est_admin_dossier(actor):
        return list(choices)
    if actor and est_directeur_projet(actor):
        return [(value, label) for value, label in choices if value in DIRECTOR_ROLES]
    return []


def utilisateurs_gerables(actor):
    if actor.is_superuser:
        return User.objects.all()
    dossier = dossier_utilisateur(actor)
    users = User.objects.filter(dossiers=dossier, is_superuser=False)
    if est_admin_dossier(actor):
        return User.objects.filter(
            Q(pk__in=users.values('pk')) | Q(pk=actor.pk)
            | Q(dossiers_geres=dossier, profile__role='ADMIN_DOSSIER'),
            is_superuser=False,
        ).distinct()
    if est_directeur_projet(actor):
        return users.filter(
            Q(projets__in=projets_accessibles(actor)) | Q(profile__created_by=actor),
            profile__role__in=DIRECTOR_ROLES,
        ).distinct()
    return User.objects.none()


def autres_admins_actifs(user):
    """Administrateurs actifs du dossier de `user`, lui excepté."""
    dossiers = Dossier.objects.filter(Q(utilisateurs=user) | Q(gerant=user))
    return User.objects.filter(
        Q(dossiers__in=dossiers) | Q(dossiers_geres__in=dossiers),
        is_active=True, is_superuser=False, profile__role='ADMIN_DOSSIER',
    ).exclude(pk=user.pk).distinct()


def peut_renoncer_admin(user):
    """Un admin de dossier peut quitter son rôle s'il laisse au moins un collègue actif."""
    return est_admin_dossier(user) and autres_admins_actifs(user).exists()


def peut_agir_utilisateur(actor, target, action):
    if not actor.is_authenticated:
        return False
    if action == 'modules':
        return actor.is_superuser and not target.is_superuser
    if actor.is_superuser:
        return action not in {'delete', 'status'} or actor.pk != target.pk
    if action == 'dossiers':
        return False
    if target.is_superuser or not utilisateurs_gerables(actor).filter(pk=target.pk).exists():
        return False
    if target.profile.role == 'ADMIN_DOSSIER':
        # Entre administrateurs, personne ne touche au compte d'un collègue.
        # Passation : chacun peut renoncer lui-même à son rôle, jamais celui d'un autre,
        # et seulement si un autre administrateur actif reste en place.
        if actor.pk != target.pk:
            return False
        if action == 'role':
            return peut_renoncer_admin(actor)
        return action in {'edit', 'password'}
    if est_admin_dossier(actor):
        return actor.pk != target.pk or action in {'edit', 'password'}
    if est_directeur_projet(actor):
        return action in {'edit', 'role', 'projects'}
    return False


def exiger_action_utilisateur(actor, target, action):
    if not peut_agir_utilisateur(actor, target, action):
        raise PermissionDenied("Vous n'êtes pas autorisé à effectuer cette action sur ce compte.")


def dossiers_affectables(actor):
    if actor.is_superuser:
        return Dossier.objects.all()
    return Dossier.objects.filter(pk=dossier_utilisateur(actor).pk)


def valider_dossiers_utilisateur(user, role, dossiers, gerance_cedee=False):
    """Validate the complete resulting scope, never silently prune old memberships.

    gerance_cedee : l'administrateur renonce à son rôle, ses dossiers gérés
    (déjà inclus dans `dossiers`) seront cédés à un collègue au moment de l'enregistrement.
    """
    ids = {d.pk for d in dossiers}
    if user.pk and not gerance_cedee:
        ids.update(user.dossiers_geres.values_list('pk', flat=True))
    if not user.is_superuser and role != 'OBSERVATEUR' and len(ids) != 1:
        raise ValidationError(
            "Ce compte doit être rattaché à un seul dossier. "
            "Les anciens rattachements multiples doivent être résolus explicitement par l'Admin."
        )
    if role == 'OBSERVATEUR' and user.pk and not gerance_cedee and user.dossiers_geres.exists():
        raise ValidationError("Retirez d'abord ce compte du champ gérant historique de ses dossiers.")
