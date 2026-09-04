from django.db.models.signals import pre_save, post_delete
from django.apps import apps
from django.db.models import FileField
from django.dispatch import receiver

from projets.models import (
    Attachement,
    DocumentAdministratif,
    EtapeValidation,
    FichierSuivi,
    OrdreService,
    ProcessValidation,
    RapportJournalier,
    SituationMensuelle,
    DocumentSituationMensuelle,
)
    
@receiver(post_delete, sender=Attachement)
@receiver(post_delete, sender=DocumentAdministratif)
@receiver(post_delete, sender=OrdreService)
@receiver(post_delete, sender=FichierSuivi)
@receiver(post_delete, sender=ProcessValidation)
@receiver(post_delete, sender=EtapeValidation)
def delete_document(sender, instance, **kwargs):
    delete_file_field(instance)


@receiver(post_delete, sender=RapportJournalier)
def delete_rapport_document(sender, instance, **kwargs):
    delete_file_field(instance, field_name='document')


@receiver(post_delete, sender=SituationMensuelle)
def delete_situation_document(sender, instance, **kwargs):
    return None


@receiver(post_delete, sender=DocumentSituationMensuelle)
def delete_situation_document_file(sender, instance, **kwargs):
    delete_file_field(instance, field_name='fichier')
  

@receiver(pre_save, sender=Attachement)
@receiver(pre_save, sender=FichierSuivi)
@receiver(pre_save, sender=DocumentAdministratif)
@receiver(pre_save, sender=OrdreService)
@receiver(pre_save, sender=ProcessValidation)
@receiver(pre_save, sender=EtapeValidation)
@receiver(pre_save, sender=RapportJournalier)
@receiver(pre_save, sender=DocumentSituationMensuelle)
def handle_file_update(sender, instance, **kwargs):
    """
    Gère la suppression des anciens fichiers lors de leur remplacement.
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
    field_name = 'document' if hasattr(old_instance, 'document') else 'fichier'
    old_file = getattr(old_instance, field_name, None)
    new_file = getattr(instance, field_name, None)
    
    # Cas 1: Pas de changement de fichier → sortir
    if old_file == new_file:
        return False
    
    # Cas 2: Fichier supprimé (nouveau fichier est None)
    if old_file and new_file is None:
        return delete_file_object(old_file, instance=old_instance)
    
    # Cas 3: Fichier modifié (ancien et nouveau existent mais sont différents)
    if old_file and new_file and old_file != new_file:
        print(f"🔄 Fichier modifié pour {sender.__name__} ID {instance.pk}, ancien fichier supprimé")
        return delete_file_object(old_file, instance=old_instance)

def file_is_referenced_elsewhere(file_field, instance=None):
    """Vérifie qu'aucun autre objet ne référence la même clé de stockage."""
    file_name = getattr(file_field, 'name', '')
    if not file_name:
        return False

    for model in apps.get_models():
        for field in model._meta.get_fields():
            if not isinstance(field, FileField) or field.remote_field:
                continue

            references = model._default_manager.filter(**{field.name: file_name})
            if instance is not None and model is instance.__class__:
                references = references.exclude(pk=instance.pk)
            if references.exists():
                return True
    return False


def delete_file_object(file_field, instance=None):
    """
    Supprime un fichier via le backend de stockage configuré.
    """
    if not file_field:
        return False

    try:
        if file_is_referenced_elsewhere(file_field, instance=instance):
            return False
        # Les champs fichier Django exposent delete().
        if hasattr(file_field, 'delete'):
            file_field.delete(save=False)
            return True
    except Exception as e:
        print(f"❌ Erreur lors de la suppression du fichier: {e}")
        return False

def delete_file_field(instance, field_name='fichier'):
    """
    Supprime le champ fichier d'une instance Django.
    """
    file_field = getattr(instance, field_name, None)

    if not file_field:
        return False
    return delete_file_object(file_field, instance=instance)