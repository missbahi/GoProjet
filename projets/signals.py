import cloudinary
from django.dispatch import receiver
from django.db.models.signals import post_delete, pre_save
from cloudinary import api
from cloudinary.exceptions import NotFound

from projets.models import Attachement, FichierSuivi, DocumentAdministratif, OrdreService, ProcessValidation
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
    url = file.url
    public_id = file.public_id
    exit_code = Path(url).suffix
    return public_id + exit_code
    

def delete_cloudinary_file(instance):

    file = getattr(instance, 'fichier', None) or getattr(instance, 'documents', None) or getattr(instance, 'fichier_validation', None)
    if file and file.public_id:
        try:
            public_id_with_ext = f"{file.public_id}.{file.format}"  # obligatoire
            print(f"Suppression du fichier Cloudinary: {public_id_with_ext}")
            cloudinary.uploader.destroy(public_id_with_ext, resource_type='raw', type='upload', invalidate=True)
        except Exception as e:
            print(f"Erreur lors de la suppression du fichier Cloudinary: {e}")

@receiver(post_delete, sender=Attachement)
@receiver(post_delete, sender=DocumentAdministratif)
@receiver(post_delete, sender=OrdreService)
@receiver(post_delete, sender=FichierSuivi)
@receiver(post_delete, sender=ProcessValidation)
def delete_document(sender, instance, **kwargs):
    delete_cloudinary_file(instance)
  
@receiver(pre_save, sender=Attachement)
def update_attachement_file(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = Attachement.objects.get(pk=instance.pk)
    except Attachement.DoesNotExist:
        return
    if old_instance.fichier and instance.fichier and old_instance.fichier != instance.fichier:
        cloudinary.uploader.destroy(old_instance.fichier.public_id, resource_type="raw")        

@receiver(pre_save, sender=FichierSuivi)
def update_fichier_suivi_file(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = FichierSuivi.objects.get(pk=instance.pk)
    except FichierSuivi.DoesNotExist:
        return
    if old_instance.fichier and instance.fichier and old_instance.fichier != instance.fichier:
        cloudinary.uploader.destroy(old_instance.fichier.public_id, resource_type="raw")

@receiver(pre_save, sender=DocumentAdministratif)
def update_document_administratif_file(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = DocumentAdministratif.objects.get(pk=instance.pk)
    except DocumentAdministratif.DoesNotExist:
        return
    if old_instance.fichier and instance.fichier and old_instance.fichier != instance.fichier:
        cloudinary.uploader.destroy(old_instance.fichier.public_id, resource_type="raw")

@receiver(pre_save, sender=OrdreService)
def update_ordre_service_file(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = OrdreService.objects.get(pk=instance.pk)
    except OrdreService.DoesNotExist:
        return
    if old_instance.documents and instance.documents and old_instance.documents != instance.documents:
        cloudinary.uploader.destroy(old_instance.documents.public_id, resource_type="raw")

@receiver(pre_save, sender=ProcessValidation)
def update_process_validation_file(sender, instance, **kwargs):
    if not instance.pk:
        return
    try:
        old_instance = ProcessValidation.objects.get(pk=instance.pk)
    except ProcessValidation.DoesNotExist:
        return
    if old_instance.fichier_validation and instance.fichier_validation and old_instance.fichier_validation != instance.fichier_validation:
        cloudinary.uploader.destroy(old_instance.fichier_validation.public_id, resource_type="raw")    
