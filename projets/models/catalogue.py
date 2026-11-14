from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class CatalogueDossier(models.Model):
    # NULL is reserved for retained legacy rows without an identifiable owner.
    dossier = models.ForeignKey(
        "projets.Dossier", on_delete=models.PROTECT, null=True, blank=True,
        related_name="%(class)s_catalogue",
    )

    class Meta:
        abstract = True


@receiver(post_save, sender="projets.Dossier", dispatch_uid="catalogue_categories_nouveau_dossier")
def initialiser_nouveau_dossier(sender, instance, created, raw=False, **kwargs):
    if created and not raw:
        from projets.catalogues import initialiser_categories_dossier
        initialiser_categories_dossier(instance)
