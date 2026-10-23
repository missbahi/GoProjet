from django.urls import path

from goplan.views import export_views
from .views import calendar_views, plan_views, task_views, gantt_views, export_views, import_views
app_name = 'goplan'

urlpatterns = [
    # Plans - Liste de plans, Edition d'un plan (Nouveau, Modifier, Supprimer)
    path('plans/', plan_views.liste_plans, name='liste_plans'),
    path('plans/nouveau/', plan_views.creer_plan, name='creer_plan'),
    path('plans/<int:plan_id>/modifier/', plan_views.modifier_plan, name='modifier_plan'),
    path('plans/<int:plan_id>/supprimer/', plan_views.supprimer_plan, name='supprimer_plan'),

    # Plans - Import / Export XML adapté au format MS Project
    path('plans/import/xml/', import_views.import_mspdi, name='import_mspdi'),
    path('plans/<int:plan_id>/import/xml/', import_views.import_mspdi, name='replace_mspdi'),
    path('plans/<int:plan_id>/export/mspdi/', export_views.export_mspdi, name='export_mspdi'),

    # Plans - Gantt
    path('plans/<int:plan_id>/gantt/', gantt_views.gantt_plan, name='gantt_plan'),
    path('plans/<int:plan_id>/gantt/apparence/', gantt_views.save_gantt_appearance, name='save_gantt_appearance'),
    path('plans/<int:plan_id>/gantt/tache/save/', gantt_views.save_gantt_task, name='save_gantt_task'),
    path('plans/<int:plan_id>/gantt/tache/supprimer/', gantt_views.delete_gantt_task, name='delete_gantt_task'),
    path('plans/<int:plan_id>/gantt/liaison/save/', gantt_views.save_gantt_link, name='save_gantt_link'),
    path('plans/<int:plan_id>/taches/repli/', gantt_views.toggle_task_fold, name='toggle_task_fold'),

    # Appliquer la couleur copiée
    path('plans/<int:plan_id>/gantt/tache/couleur/', gantt_views.set_gantt_task_color, name='set_gantt_task_color'),

    # Aperçu avant impression
    path('plans/<int:plan_id>/apercu/', gantt_views.apercu_plan, name='apercu_plan'),
    path('plans/<int:plan_id>/apercu/reglages/', gantt_views.save_print_settings, name='save_print_settings'),
    path('plans/<int:plan_id>/apercu/reglages/reinitialiser/', gantt_views.reset_print_settings, name='reset_print_settings'),

    # Calendriers
    path('calendriers/', calendar_views.liste_calendriers, name='liste_calendriers'),
    path('calendriers/nouveau/', calendar_views.calendrier_form, name='creer_calendrier'),
    path('calendriers/<int:calendar_id>/modifier/', calendar_views.calendrier_form, name='modifier_calendrier'),
    path('calendriers/<int:calendar_id>/supprimer/', calendar_views.supprimer_calendrier, name='supprimer_calendrier'),

    # Tâches inline
    path('plans/<int:plan_id>/taches/inline/', task_views.taches_inline, name='taches_inline'),
    path('plans/<int:plan_id>/taches/inline/save/', task_views.save_taches_inline, name='save_taches_inline'),
    
]