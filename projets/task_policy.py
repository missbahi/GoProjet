from django.contrib.auth.models import User
from django.db.models import Exists, OuterRef, Q

from projets.decorators import peut_gerer_projet, projets_accessibles
from projets.models import Dossier


def responsables_eligibles(projet):
    if projet is None:
        return User.objects.none()
    autres_dossiers = Dossier.objects.filter(
        Q(utilisateurs=OuterRef('pk')) | Q(gerant=OuterRef('pk')),
    ).exclude(pk=projet.dossier_id)
    locaux = User.objects.filter(is_superuser=False).filter(
        Q(profile__role='ADMIN_DOSSIER')
        & (Q(dossiers=projet.dossier_id) | Q(dossiers_geres=projet.dossier_id))
        | Q(
            profile__role__in=['DIRECTEUR_PROJET', 'CHEF_PROJET', 'CHEF_CHANTIER'],
            dossiers=projet.dossier_id, projets=projet,
        )
    ).alias(autre_dossier=Exists(autres_dossiers)).filter(
        autre_dossier=False,
    ) if projet.dossier_id else User.objects.none()
    return User.objects.filter(is_active=True).filter(
        Q(pk__in=locaux.values('pk')) | Q(is_superuser=True),
    ).select_related('profile').distinct().order_by('first_name', 'last_name', 'username')


def libelle_responsable(user):
    nom = user.get_full_name().strip() or user.username
    profile = getattr(user, 'profile', None)
    role = 'Admin' if user.is_superuser else profile.get_role_display() if profile else ''
    return f'{nom} — {role}' if role else nom


def peut_gerer_taches(user, projet=None):
    return bool(
        user and user.is_authenticated and user.is_active and peut_gerer_projet(user)
        and (projet is None or projets_accessibles(user).filter(pk=projet.pk).exists())
    )


def responsables_affectables(user, projet):
    if projet is None or not peut_gerer_taches(user, projet):
        return User.objects.none()
    roles = {
        'ADMIN_DOSSIER': ['DIRECTEUR_PROJET', 'CHEF_PROJET', 'CHEF_CHANTIER'],
        'DIRECTEUR_PROJET': ['CHEF_PROJET', 'CHEF_CHANTIER'],
        'CHEF_PROJET': ['CHEF_CHANTIER'],
    }
    subordonnes = (
        Q(is_superuser=False) if user.is_superuser
        else Q(profile__role__in=roles.get(user.profile.role, []))
    )
    return responsables_eligibles(projet).filter(Q(pk=user.pk) | subordonnes)


def peut_actualiser_tache(user, tache):
    return peut_gerer_taches(user, tache.projet) or bool(
        user and user.is_authenticated and user.pk == tache.responsable_id
        and responsables_eligibles(tache.projet).filter(pk=user.pk).exists()
    )
