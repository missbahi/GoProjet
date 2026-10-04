# ------------------------ Profile ------------------------ #
import os
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from django.templatetags.static import static


def avatar_upload_path(instance, filename):
    """Génère un chemin unique pour l'avatar."""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.username}_avatar_{instance.user.id}.{ext}"
    return os.path.join('avatars', filename)


class Profile(models.Model):
    ROLE_CHOICES = [
        ('CHEF_PROJET', 'Chef de projet'),
        ('GERANT', 'Chef de projet (historique)'),
        ('CHEF_CHANTIER', 'Chef de chantier'),
        ('POINTEUR', 'Pointeur'),
        ('STAFF', 'Staff'),
        ('UTILISATEUR', 'Utilisateur'),
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

    liste_projets_vue = models.CharField(
        max_length=10,
        choices=VUE_CHOICES,
        default='tableau',
        verbose_name="Vue des projets préférée",
    )

    theme = models.CharField(
        max_length=10,
        choices=THEME_CHOICES,
        default='dark',
        verbose_name="Thème préféré",
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='UTILISATEUR',
    )

    tel = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        verbose_name="Téléphone",
        help_text="Téléphone de contact",
    )

    # ⚡ Pas de default='avatars/...' : le fallback est géré par avatar_url.
    # Le fichier par défaut est static/images/default.png, servi par WhiteNoise.
    avatar = models.ImageField(
        upload_to=avatar_upload_path,
        blank=True,
    )

    def __str__(self):
        return f"{self.user.username} Profile"

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