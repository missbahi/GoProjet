from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from projets.models import (
    FormuleRevision,
    LigneBordereau,
    LotProjet,
    OrdreService,
    Projet,
    TermeFormule,
)
from projets.services.revision_readiness import invalider_indicateur_revision


@receiver(post_save, sender=Projet, dispatch_uid="revision_invalider_projet")
def invalider_apres_modification_projet(sender, instance, **kwargs):
    invalider_indicateur_revision(instance.pk)


@receiver(post_save, sender=OrdreService, dispatch_uid="revision_invalider_os")
@receiver(post_delete, sender=OrdreService, dispatch_uid="revision_invalider_os_supprime")
def invalider_apres_modification_os(sender, instance, **kwargs):
    if instance.projet_id:
        invalider_indicateur_revision(instance.projet_id)


@receiver(post_save, sender=LotProjet, dispatch_uid="revision_invalider_lot")
@receiver(post_delete, sender=LotProjet, dispatch_uid="revision_invalider_lot_supprime")
def invalider_apres_modification_lot(sender, instance, **kwargs):
    if instance.projet_id:
        invalider_indicateur_revision(instance.projet_id)


@receiver(post_save, sender=LigneBordereau, dispatch_uid="revision_invalider_ligne")
@receiver(post_delete, sender=LigneBordereau, dispatch_uid="revision_invalider_ligne_supprimee")
def invalider_apres_modification_ligne(sender, instance, **kwargs):
    if instance.lot_id:
        projet_id = (
            LotProjet.objects.filter(pk=instance.lot_id)
            .values_list("projet_id", flat=True)
            .first()
        )
        if projet_id:
            invalider_indicateur_revision(projet_id)


@receiver(post_save, sender=FormuleRevision, dispatch_uid="revision_invalider_formule")
@receiver(post_delete, sender=FormuleRevision, dispatch_uid="revision_invalider_formule_supprimee")
def invalider_apres_modification_formule(sender, instance, **kwargs):
    if instance.projet_id:
        invalider_indicateur_revision(instance.projet_id)


@receiver(post_save, sender=TermeFormule, dispatch_uid="revision_invalider_terme")
@receiver(post_delete, sender=TermeFormule, dispatch_uid="revision_invalider_terme_supprime")
def invalider_apres_modification_terme(sender, instance, **kwargs):
    if instance.formule_id:
        projet_id = (
            FormuleRevision.objects.filter(pk=instance.formule_id)
            .values_list("projet_id", flat=True)
            .first()
        )
        if projet_id:
            invalider_indicateur_revision(projet_id)
