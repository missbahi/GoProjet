import os
import re
import cloudinary
from django.conf import settings
from django.dispatch import receiver
from cloudinary import api
from cloudinary.exceptions import NotFound
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
import cloudinary.uploader
from cloudinary.exceptions import Error as CloudinaryError
from projets.models import Attachement, EtapeValidation, FichierSuivi, DocumentAdministratif, OrdreService, ProcessValidation
def check_file_exists(public_id):
    try:
        # Configuration Cloudinary
        cloudinary.config(
            cloud_name=force_clean(settings.CLOUDINARY_CLOUD_NAME),
            api_key=settings.CLOUDINARY_API_KEY,
            api_secret=settings.CLOUDINARY_API_SECRET,
            secure=True
        )
        # Essayer de trouver le fichier sur Cloudinary
        resource = api.resource(public_id, resource_type='raw')
        return True
    except NotFound:
        print(f"❌ Fichier non trouvé: {public_id}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False
    
@receiver(post_delete, sender=Attachement)
@receiver(post_delete, sender=DocumentAdministratif)
@receiver(post_delete, sender=OrdreService)
@receiver(post_delete, sender=FichierSuivi)
@receiver(post_delete, sender=ProcessValidation)
@receiver(post_delete, sender=EtapeValidation)
def delete_document(sender, instance, **kwargs):
    delete_cloudinary_file(instance)
  

@receiver(pre_save, sender=Attachement)
@receiver(pre_save, sender=FichierSuivi)
@receiver(pre_save, sender=DocumentAdministratif)
@receiver(pre_save, sender=OrdreService)
@receiver(pre_save, sender=ProcessValidation)
@receiver(pre_save, sender=EtapeValidation)
def handle_file_update(sender, instance, **kwargs):
    """
    Gère la suppression des anciens fichiers Cloudinary lors de leur remplacement.
    Ne s'active que si le fichier a réellement changé ou été supprimé.
    """
    # Nouvelle instance, rien à supprimer
    if not instance.pk:
        return False
    
    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return False
    
    # Récupérer les fichiers
    old_file = getattr(old_instance, 'fichier', None)
    new_file = getattr(instance, 'fichier', None)
    
    # Cas 1: Pas de changement de fichier → sortir
    if old_file == new_file:
        return False
    
    # Cas 2: Fichier supprimé (nouveau fichier est None)
    if old_file and new_file is None:
        return _delete_cloudinary_file(old_file)
    
    # Cas 3: Fichier modifié (ancien et nouveau existent mais sont différents)
    if old_file and new_file and old_file != new_file:
        print(f"🔄 Fichier modifié pour {sender.__name__} ID {instance.pk}, ancien fichier supprimé")
        return _delete_cloudinary_file(old_file)

def _delete_cloudinary_file(file_field):
    """
    Supprime un fichier Cloudinary de manière sécurisée.
    
    Args:
        file_field: Le champ CloudinaryField
    """
    if not file_field:
        return False
    
    try:
        # Méthode 1: Utiliser delete() si disponible (CloudinaryField)
        if hasattr(file_field, 'delete'):
            file_field.delete()
            return True
        
        # Méthode 2: Supprimer via public_id
        if hasattr(file_field, 'public_id') and file_field.public_id:
            try:
                result = cloudinary.uploader.destroy(file_field.public_id, resource_type='raw', type='upload')
                if result.get('result') == 'ok': 
                    return True
                else:
                    print(f"⚠️ {result.get('result')} (delete): {file_field.public_id}")
                    return False
            except CloudinaryError as e:
                if "not found" not in str(e).lower():
                    print(f"⚠️  Erreur suppression Cloudinary: {e}")
                return False
        
        # Méthode 3: Supprimer via l'URL
        elif hasattr(file_field, 'url'):
            return _delete_by_url(file_field.url)
            
    except Exception as e:
        print(f"❌ Erreur lors de la suppression du fichier: {e}")
        return False

def _delete_by_url(url):
    """Supprime un fichier Cloudinary à partir de son URL."""
    import re
    
    if not url or 'cloudinary.com' not in url:
        return False
    
    # Extraire le public_id de l'URL
    patterns = [
        r'upload/(?:v\d+/)?(.+?)(?:\.[a-z]+)?$',
        r'image/upload/(?:v\d+/)?(.+?)(?:\.[a-z]+)?$',
        r'video/upload/(?:v\d+/)?(.+?)(?:\.[a-z]+)?$',
        r'raw/upload/(?:v\d+/)?(.+?)(?:\.[a-z]+)?$',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            public_id = match.group(1)
            try:
                cloudinary.uploader.destroy(public_id, resource_type='raw')
                return True
            except CloudinaryError as e:
                if "not found" not in str(e).lower():
                    print(f"⚠️  Erreur suppression via URL: {e}")
                return False
    return False

def delete_cloudinary_file(instance, field_name='fichier'):
    """
    Supprime un fichier Cloudinary ou local de manière sécurisée.
    
    Args:
        instance: L'instance du modèle Django
        field_name: Nom du champ CloudinaryField/FileField
    """
    file_field = getattr(instance, field_name, None)
    
    if not file_field:
        return False
    
    # 1. Essayer la méthode CloudinaryField.delete() si disponible
    if hasattr(file_field, 'delete'):
        try:
            file_field.delete()
            return True
        except Exception as e:
            print(f"⚠️ Échec .delete(), tentative autre méthode: {e}")
            return False
    # 2. Supprimer via Cloudinary API (public_id)
    if hasattr(file_field, 'public_id'):
        public_id = file_field.public_id + '.' + file_field.format

        force_config_cloudinary()
        try:
            resource = api.resource(public_id, resource_type='raw')
        except NotFound:
            print(f"❌ Fichier Cloudinary non trouvé")
            return False

        return _delete_cloudinary_by_public_id(public_id)
            
    # 3. Supprimer via Cloudinary API (URL)
    if hasattr(file_field, 'url') and file_field.url:
        force_config_cloudinary()
        return _delete_cloudinary_by_url(file_field.url)
    
    # 4. Fallback: Fichier local
    if hasattr(file_field, 'path') and file_field.path and os.path.exists(file_field.path):
        try:
            os.remove(file_field.path)
            print(f"✅ Fichier local supprimé: {file_field.path}")
        except Exception as e:
            print(f"❌ Erreur suppression locale: {e}")
            
def force_clean(value):
        import re
        value = str(value).strip()
        
        # Supprimer tout sauf lettres et chiffres
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', str(value))
        return cleaned

def force_config_cloudinary():
    cleaned_name = force_clean(settings.CLOUDINARY_CLOUD_NAME)
    cloudinary.config(
        cloud_name=cleaned_name,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET
    ) 

def _delete_cloudinary_by_public_id(public_id, resource_type='raw'):
    """Supprime un fichier Cloudinary via son public_id."""
    try:
        result = cloudinary.uploader.destroy(public_id, resource_type=resource_type, type='upload')
        
        if result.get('result') == 'ok':
            return True
        else:
            print(f"⚠️ Résultat inattendu: {result.get('result')} pour {public_id}")
            return False
            
    except CloudinaryError as e:
        if "not found" not in str(e).lower():
            print(f"⚠️ Erreur suppression Cloudinary: {e}")
        return False
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")
        return False
    
def _delete_cloudinary_by_url(url):
    """Supprime un fichier Cloudinary à partir de son URL."""
    if not url or 'cloudinary.com' not in url:
        return False
    
    # Extraire public_id de l'URL
    public_id = extract_public_id_from_url(url)
    if public_id:
       return _delete_cloudinary_by_public_id(public_id)

def extract_public_id_from_url(url):
    """Extrait le public_id d'une URL Cloudinary."""
    patterns = [
        r'upload/(?:v\d+/)?(.+?)(?:\.[a-z]+)?$',
        r'image/upload/(?:v\d+/)?(.+?)(?:\.[a-z]+)?$',
        r'video/upload/(?:v\d+/)?(.+?)(?:\.[a-z]+)?$',
        r'raw/upload/(?:v\d+/)?(.+?)(?:\.[a-z]+)?$',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None