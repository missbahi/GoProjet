# ------------------------ Profile ------------------------ #
import os
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from django.core.exceptions import ValidationError
from django.templatetags.static import static


def avatar_upload_path(instance, filename):
    """Génère un chemin unique pour l'avatar."""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.username}_avatar_{instance.user.id}.{ext}"
    return os.path.join('avatars', filename)


class Profile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN_DOSSIER', 'Administrateur de dossier'),
        ('DIRECTEUR_PROJET', 'Directeur de projet'),
        ('CHEF_PROJET', 'Chef de projet'),
        ('CHEF_CHANTIER', 'Chef de chantier'),
        ('POINTEUR', 'Pointeur'),
        ('OBSERVATEUR', 'Observateur'),
    ]
    VUE_CHOICES = [
        ('tableau', 'Tableau'),
        ('cartes', 'Cartes'),
    ]

    THEME_CHOICES = [
        ('dark', 'Sombre'),
        ('light', 'Clair'),
        ('system', 'Système'),
    ]

    liste_projets_vue = models.CharField(max_length=10, choices=VUE_CHOICES, default='tableau', verbose_name="Vue des projets préférée",)
    theme = models.CharField(max_length=10, choices=THEME_CHOICES, default='dark', verbose_name="Thème préféré",)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='comptes_crees',
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='UTILISATEUR',)
    tel = models.CharField( max_length=20, blank=True, null=True, verbose_name="Téléphone", help_text="Téléphone de contact",)
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True,)
    last_seen_version = models.CharField(
        _("Dernière version vue"),
        max_length=20,
        blank=True,
        default="",
        help_text=_("Version de l'app vue par l'utilisateur à sa dernière connexion."),
    )
    last_version_check = models.DateTimeField(
        _("Dernière vérification de version"),
        null=True,
        blank=True,
    )
    guide_observateur_masque = models.BooleanField(
        _("Guide Observateur masqué"),
        default=False,
        help_text=_("Si coché, la fenêtre de bienvenue de l'Observateur ne s'ouvre plus automatiquement."),
    )

    def __str__(self):
        return f"{self.user.username} Profile"

    def clean(self):
        super().clean()
        if self.user_id and not self.user.is_superuser and self.role != 'OBSERVATEUR':
            from .projet import Dossier
            from django.db.models import Q
            dossiers = Dossier.objects.filter(
                Q(utilisateurs=self.user) | Q(gerant=self.user)
            ).distinct()
            if dossiers.count() > 1:
                raise ValidationError({
                    'role': "Résolvez explicitement les rattachements multiples avant de modifier ce rôle."
                })

    def save(self, *args, **kwargs):
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values_list('role', flat=True).first()
            if previous != self.role:
                self.clean()
        return super().save(*args, **kwargs)

    @property
    def avatar_url(self):
        """
        Retourne l'URL de l'avatar ou l'image par défaut.
        - Si un avatar a été uploadé → son URL (media ou R2)
        - Sinon → static/images/default.png (servi par WhiteNoise)
        """
        if self.avatar and self.avatar.name:
            try:
                return self.avatar.url
            except (ValueError, AttributeError):
                pass
        return static('images/default.png')


# ============================================================
# Signaux
# ============================================================

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Créer un profil automatiquement quand un utilisateur est créé."""
    if created:
        Profile.objects.create(user=instance)


@receiver(pre_delete, sender=User)
def delete_user_profile(sender, instance, **kwargs):
    """Supprimer le profil quand l'utilisateur est supprimé."""
    if hasattr(instance, 'profile'):
        instance.profile.delete()


@receiver(models.signals.m2m_changed, sender='projets.Dossier_utilisateurs')
def validate_single_dossier(sender, instance, action, reverse, pk_set, **kwargs):
    if action != 'pre_add' or not pk_set:
        return
    from .projet import Dossier
    from django.db.models import Q
    users = [instance] if reverse else User.objects.filter(pk__in=pk_set).select_related('profile')
    for user in users:
        if user.is_superuser or user.profile.role == 'OBSERVATEUR':
            continue
        existing = set(Dossier.objects.filter(
            Q(utilisateurs=user) | Q(gerant=user)
        ).values_list('pk', flat=True))
        resulting = existing | (set(pk_set) if reverse else {instance.pk})
        if len(resulting) > 1 and resulting != existing:
            raise ValidationError(
                "Un utilisateur non observateur ne peut être rattaché qu'à un seul dossier."
            )