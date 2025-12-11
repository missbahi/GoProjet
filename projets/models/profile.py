# ------------------------ Profile ------------------------ #
import os
import os
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.models import User
from django.dispatch import receiver
from django.db.models.signals import post_save, pre_delete
from django.conf import settings


def avatar_upload_path(instance, filename):
    """Génère un chemin unique pour l'avatar"""
    ext = filename.split('.')[-1]
    filename = f"{instance.user.username}_avatar_{instance.user.id}.{ext}"
    return os.path.join('avatars', filename)

class Profile(models.Model):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrateur'),
        ('CHEF_PROJET', 'Chef de Projet'),
        ('UTILISATEUR', 'Utilisateur'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20, 
        choices=ROLE_CHOICES, 
        default='UTILISATEUR'
    )
    tel = models.CharField(
        max_length=20, 
        blank=True, 
        null=True,
        verbose_name="Téléphone",
        help_text="Téléphone de contact")
    # Champ compatible Cloudinary
    if getattr(settings, 'USE_CLOUDINARY', False):
        from cloudinary.models import CloudinaryField
        avatar = CloudinaryField('image', folder='avatars',
            transformation=[
                {'width': 300, 'height': 300, 'crop': 'fill', 'gravity': 'face'}
            ],
            default='https://res.cloudinary.com/ddfqmth4q/image/upload/v1764860471/default_qu1agn.png',
            # https://res.cloudinary.com/ddfqmth4q/image/upload/v1/avatars/defult.png
        )
    else:
        avatar = models.ImageField(
            upload_to=avatar_upload_path, 
            default='avatars/default.png', 
            blank=True
        )
    def __str__(self):
        return f"{self.user.username} Profile"
    
    @property
    def avatar_url(self):
        """Retourne l'URL de l'avatar - fonctionne avec Cloudinary et local"""
        if self.avatar and hasattr(self.avatar, 'url'):
            url = self.avatar.url
            url = url.replace(' =', '')
            return url
        elif getattr(settings, 'USE_CLOUDINARY', False):
            return "https://res.cloudinary.com/ddfqmth4q/image/upload/v1764860471/default_qu1agn.png"
        return '/static/images/default.png'
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

# Signaux pour gérer la création/suppression des profils
@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Créer un profil automatiquement quand un utilisateur est créé"""
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """Sauvegarder le profil quand l'utilisateur est sauvegardé"""
    if hasattr(instance, 'profile'):
        instance.profile.save()

@receiver(pre_delete, sender=User)
def delete_user_profile(sender, instance, **kwargs):
    """Supprimer le profil quand l'utilisateur est supprimé"""
    if hasattr(instance, 'profile'):
        instance.profile.delete()

