from django.contrib import admin
from .models import GWorkCalendar, GPlan, GPlanPrintSettings, GResource, GTask, GTaskDependency, GTaskAssignment
from .forms import GTaskModelForm


@admin.register(GWorkCalendar)
class GWorkCalendarAdmin(admin.ModelAdmin):
    list_display = ['nom', 'heures_par_jour', 'is_default']


@admin.register(GPlan)
class GPlanAdmin(admin.ModelAdmin):
    list_display = ['nom', 'date_debut', 'date_fin_cible', 'date_etat', 'created_at']


@admin.register(GPlanPrintSettings)
class GPlanPrintSettingsAdmin(admin.ModelAdmin):
    list_display = ['plan', 'format', 'orientation', 'timescale', 'period_mode', 'updated_at']
    list_select_related = ['plan']


@admin.register(GResource)
class GResourceAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type_ressource', 'capacite_jour']


@admin.register(GTask)
class GTaskAdmin(admin.ModelAdmin):
    form = GTaskModelForm
    list_display = ['code', 'nom', 'plan', 'date_debut', 'date_fin', 'avancement']
    list_filter = ['plan', 'type_tache', 'est_critique']


@admin.register(GTaskDependency)
class GTaskDependencyAdmin(admin.ModelAdmin):
    list_display = ['predecesseur', 'successeur', 'type_lien', 'decalage_jours']


@admin.register(GTaskAssignment)
class GTaskAssignmentAdmin(admin.ModelAdmin):
    list_display = ['tache', 'ressource', 'charge', 'taux_affectation']