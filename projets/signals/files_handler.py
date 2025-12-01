import cloudinary
from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save
from cloudinary import api
from cloudinary.exceptions import NotFound

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

def file_name_from_url(file):
    """
    Retourne le public_id complet avec extension
    en combinant public_id (sans extension) et extension de l'URL
    """
    from pathlib import Path
    url = file.url.replace(' ', '')
    public_id = file.public_id
    exit_code = Path(url).suffix
    return public_id + exit_code
    
def delete_cloudinary_file(instance):
            
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
def update_file(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    old_file = getattr(old_instance, 'fichier', None)
    new_file = getattr(instance, 'fichier', None)
    
    # Si pas de fichier ou fichiers identiques
    if not old_file or not new_file or old_file == new_file:
        return
    
    # Vérifier si c'est un CloudinaryField
    if hasattr(old_file, 'public_id') and old_file.public_id:
        public_id = old_file.public_id
        try:
            from cloudinary.exceptions import Error as CloudinaryError
            cloudinary.api.resource(public_id, resource_type='raw')
            
            # Le fichier existe, on peut le supprimer
        except CloudinaryError as e:
            if "not found" in str(e).lower():
                print(f"Fichier non trouvé, pas de suppression: {public_id}")
                return
            else:
                raise e
    
        cloudinary.uploader.destroy(public_id, resource_type='raw', type='upload', invalidate=True)
        print(f"Fichier modifié pour {sender.__name__} ID {instance.pk}, suppression de l'ancien fichier.")
        
    elif hasattr(old_file, 'path') and old_file.path:
        # Vérifier si le fichier existe physiquement
        import os
        if os.path.exists(old_file.path):
            try:
                os.remove(old_file.path)
                print(f"Fichier local supprimé: {old_file.path}")
                
                # Optionnel: supprimer le dossier parent si vide
                folder = os.path.dirname(old_file.path)
                if not os.listdir(folder):
                    os.rmdir(folder)
                    
            except OSError as e:
                print(f"Erreur suppression fichier local: {e}")
        else:
            print(f"Fichier local déjà supprimé: {old_file.path}")
    
    # CAS 3: FICHIER AVEC URL (ex: S3, autre storage)
    elif hasattr(old_file, 'url'):
        print(f"Fichier externe supprimé: {old_file.url}")
    
    # CAS 4: FICHIER INCONNU
    else:
        print(f"Type de fichier non géré: {type(old_file)}")
        print(f"Attributs disponibles: {dir(old_file)}")
