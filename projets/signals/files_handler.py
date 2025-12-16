import os
import re
import cloudinary
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
        resource = api.resource(public_id, resource_type='raw')
        print(f"✅ Fichier trouvé: {resource['public_id']}")
        print(f"   Type: {resource['resource_type']}")
        print(f"   Format: {resource['format']}")
        print(f"   Taille: {resource['bytes']} bytes")
        return True
    except NotFound:
        print(f"❌ Fichier non trouvé: {public_id}")
        return False
    except Exception as e:
        print(f"❌ Erreur: {e}")
        return False

# def file_name_from_url(file):
#     """
#     Retourne le public_id complet avec extension
#     en combinant public_id (sans extension) et extension de l'URL
#     """
#     from pathlib import Path
#     url = file.url.replace(' ', '')
#     public_id = file.public_id
#     exit_code = Path(url).suffix
#     return public_id + exit_code
    
def delete_cloudinary_file1(instance):
            
    field_name = 'fichier'
    
    file_field = getattr(instance, field_name, None)
     # Cloudinary
    if hasattr(file_field, 'public_id') and file_field.public_id:
        try:
            result = cloudinary.uploader.destroy(
                file_field.public_id,
                resource_type='raw',
                invalidate=True
            )
            if result.get('result') == 'ok':
                print(f"✅ Fichier Cloudinary supprimé (delete): {file_field.public_id}")
            else:
                print(f"⚠️ {result.get('result')} (delete): {file_field.public_id}")
        except Exception as e:
            print(f"❌ Erreur suppression Cloudinary (delete): {e}")
    
    # Fichier local (au cas où)
    elif hasattr(file_field, 'path') and file_field.path:
        try:
            import os
            if os.path.exists(file_field.path):
                os.remove(file_field.path)
                print(f"✅ Fichier local supprimé (delete): {file_field.path}")
        except Exception as e:
            print(f"❌ Erreur suppression locale (delete): {e}")

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
        return
    
    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    
    # Récupérer les fichiers
    old_file = getattr(old_instance, 'fichier', None)
    new_file = getattr(instance, 'fichier', None)
    
    # Cas 1: Pas de changement de fichier → sortir
    if old_file == new_file:
        return
    
    # Cas 2: Fichier supprimé (nouveau fichier est None)
    if old_file and new_file is None:
        _delete_cloudinary_file(old_file)
        print(f"🗑️  Fichier supprimé pour {sender.__name__} ID {instance.pk}")
        return
    
    # Cas 3: Fichier modifié (ancien et nouveau existent mais sont différents)
    if old_file and new_file and old_file != new_file:
        _delete_cloudinary_file(old_file)
        print(f"🔄 Fichier modifié pour {sender.__name__} ID {instance.pk}, ancien fichier supprimé")
        return

def _delete_cloudinary_file(file_field):
    """
    Supprime un fichier Cloudinary de manière sécurisée.
    
    Args:
        file_field: Le champ CloudinaryField
    """
    if not file_field:
        return
    
    try:
        # Méthode 1: Utiliser delete() si disponible (CloudinaryField)
        if hasattr(file_field, 'delete'):
            file_field.delete()
            return
        
        # Méthode 2: Supprimer via public_id
        if hasattr(file_field, 'public_id') and file_field.public_id:
            try:
                cloudinary.uploader.destroy(
                    file_field.public_id,
                    resource_type='raw',  # auto-détecte le type
                    type='upload',
                    invalidate=True  # Invalide le cache CDN
                )
                print(f"✅ Fichier Cloudinary supprimé: {file_field.public_id}")
            except CloudinaryError as e:
                if "not found" not in str(e).lower():
                    print(f"⚠️  Erreur suppression Cloudinary: {e}")
        
        # Méthode 3: Supprimer via l'URL
        elif hasattr(file_field, 'url'):
            _delete_by_url(file_field.url)
            
    except Exception as e:
        print(f"❌ Erreur lors de la suppression du fichier: {e}")

def _delete_by_url(url):
    """Supprime un fichier Cloudinary à partir de son URL."""
    import re
    
    if not url or 'cloudinary.com' not in url:
        return
    
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
                print(f"✅ Fichier supprimé via URL: {public_id}")
                break
            except CloudinaryError as e:
                if "not found" not in str(e).lower():
                    print(f"⚠️  Erreur suppression via URL: {e}")

def delete_cloudinary_file(instance, field_name='fichier'):
    """
    Supprime un fichier Cloudinary ou local de manière sécurisée.
    
    Args:
        instance: L'instance du modèle Django
        field_name: Nom du champ CloudinaryField/FileField
    """
    file_field = getattr(instance, field_name, None)
    
    if not file_field:
        return
    
    # 1. Essayer la méthode CloudinaryField.delete() si disponible
    if hasattr(file_field, 'delete'):
        try:
            file_field.delete()
            print(f"✅ Fichier supprimé via .delete(): {file_field}")
            return
        except Exception as e:
            print(f"⚠️ Échec .delete(), tentative autre méthode: {e}")
    
    # 2. Supprimer via Cloudinary API (public_id)
    if hasattr(file_field, 'public_id') and file_field.public_id:
        public_id = file_field.public_id + '.' + file_field.format
        print(f"✅ Fichier Cloudinary supprimé: {public_id}")
        resource = api.resource(public_id, resource_type='raw')
        print(f"   Type: {resource['resource_type']} - Format: {resource['format']} - Taille: {resource['bytes']} bytes")
        _delete_cloudinary_by_public_id(public_id)
        return
    
    # 3. Supprimer via Cloudinary API (URL)
    if hasattr(file_field, 'url') and file_field.url:
        _delete_cloudinary_by_url(file_field.url)
        return
    
    # 4. Fallback: Fichier local
    if hasattr(file_field, 'path') and file_field.path and os.path.exists(file_field.path):
        try:
            os.remove(file_field.path)
            print(f"✅ Fichier local supprimé: {file_field.path}")
        except Exception as e:
            print(f"❌ Erreur suppression locale: {e}")

def _delete_cloudinary_by_public_id(public_id, resource_type='raw'):
    """Supprime un fichier Cloudinary via son public_id."""
    try:
        result = cloudinary.uploader.destroy(
            public_id,
            resource_type=resource_type,
            type='upload',
            invalidate=True
        )
        
        if result.get('result') == 'ok':
            print(f"✅ Fichier Cloudinary supprimé: {public_id}")
        else:
            print(f"⚠️ Résultat inattendu: {result.get('result')} pour {public_id}")
            
    except CloudinaryError as e:
        if "not found" not in str(e).lower():
            print(f"⚠️ Erreur suppression Cloudinary: {e}")
    except Exception as e:
        print(f"❌ Erreur inattendue: {e}")

def _delete_cloudinary_by_url(url):
    """Supprime un fichier Cloudinary à partir de son URL."""
    if not url or 'cloudinary.com' not in url:
        return
    
    # Extraire public_id de l'URL
    public_id = extract_public_id_from_url(url)
    if public_id:
        _delete_cloudinary_by_public_id(public_id)

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