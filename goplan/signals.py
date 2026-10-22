# goplan/signals.py
"""
Signaux de l'app GoPlan.

Les signaux seront ajoutés au fur et à mesure des sprints.
Pour l'instant, ce module est vide mais doit exister pour que
l'import dans `apps.py` (ready()) fonctionne.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

# ⚡ Les receivers viendront ici :
# from .models import GTask
#
# @receiver(post_save, sender=GTask)
# def recalculer_plan_apres_save(sender, instance, **kwargs):
#     ...