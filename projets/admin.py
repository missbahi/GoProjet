from django.contrib import admin
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin
from .models import Attachement, Decompte, DocumentAdministratif, OrdreService, Profile, Projet, Entreprise, AppelOffre, SuiviExecution, Tache, Notification, TypeOrdreService
class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False

class CustomUserAdmin(UserAdmin):
    inlines = [ProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active']
    list_filter = ['is_staff', 'is_superuser', 'is_active']

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
# ------------------------ Admin Entreprise ------------------------
@admin.register(Entreprise)
class EntrepriseAdmin(admin.ModelAdmin):
    list_display = ('nom', 'contact', 'email', 'telephone')
    search_fields = ('nom', 'contact', 'email', 'telephone')
    list_per_page = 20

# ------------------------ Admin Appel d'Offre ------------------------
@admin.register(AppelOffre)
class AppelOffreAdmin(admin.ModelAdmin):
    list_display = ('nom', 'numero', 'type', 'date_reception', 'date_limite', 'decision', 'projet')
    list_filter = ('type', 'decision')
    search_fields = ('nom', 'numero', 'maitre_ouvrage', 'localisation')
    list_per_page = 20
    date_hierarchy = 'date_reception'

# ------------------------ Admin Projet ------------------------
@admin.register(Projet)
class ProjetAdmin(admin.ModelAdmin):
    list_display = ('nom', 'numero', 'type_projet', 'localisation', 'entreprise', 'statut', 'date_debut', 'delai', 'avancement', 'en_retard')
    list_filter = ('type_projet', 'statut', 'en_retard')
    search_fields = ('nom', 'numero', 'maitre_ouvrage', 'localisation')
    list_per_page = 20
    date_hierarchy = 'date_creation'

# ------------------------ Admin Attachement ------------------------
@admin.register(Attachement)
class AttachementAdmin(admin.ModelAdmin):
    list_display = ['numero', 'projet', 'date_etablissement', 'statut', 'total_montant_ht']
    list_filter = ['statut', 'date_etablissement']
    search_fields = ['numero', 'projet__nom']

# ------------------------ Admin Decompte ------------------------
@admin.register(Decompte)
class DecompteAdmin(admin.ModelAdmin):
    list_display = ['numero', 'attachement', 'type_decompte', 'date_emission', 'montant_net_a_payer', 'statut']
    list_filter = ['type_decompte', 'statut', 'date_emission']
    search_fields = ['numero', 'attachement__projet__nom']

# ------------------------ Admin Ordre de Service ------------------------
@admin.register(OrdreService)
class OrdreServiceAdmin(admin.ModelAdmin):
    list_display = ('reference', 'titre', 'projet', 'date_publication', 'date_limite')
    search_fields = ('reference', 'titre', 'description', 'projet__nom')
    list_filter = ('date_publication', 'date_limite')
    date_hierarchy = 'date_publication'
    list_per_page = 20

# ------------------------ Admin Type Ordre de Service ------------------------
@admin.register(TypeOrdreService)
class TypeOrdreServiceAdmin(admin.ModelAdmin):
    list_display = ('nom', 'code', 'description')
    search_fields = ('nom', 'code', 'description')
# ------------------------ Admin Tache ------------------------
@admin.register(Tache)
class TacheAdmin(admin.ModelAdmin):
    list_display = ('titre', 'projet', 'responsable', 'priorite', 'terminee', 'date_debut', 'date_fin')
    list_filter = ('priorite', 'terminee', 'date_debut', 'date_fin')
    search_fields = ('titre', 'description', 'projet__nom', 'responsable__username')
    date_hierarchy = 'date_fin'
    list_per_page = 20

# ------------------------ Admin Document Administratif ------------------------
@admin.register(DocumentAdministratif)
class DocumentAdministratifAdmin(admin.ModelAdmin):
    list_display = ('type_document', 'projet', 'date_remise', 'fichier')
    search_fields = ('type_document', 'projet__nom')
    list_filter = ('type_document',)
    date_hierarchy = 'date_remise'
    list_per_page = 20
    
# ------------------------ Admin Notification ------------------------
@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        'titre',
        'utilisateur',
        'projet',
        'type_notification',
        'lue',
        'date_creation',
        'date_echeance',
    )
    list_filter = (
        'type_notification',
        'lue',
        'date_creation',
        'date_echeance',
    )
    search_fields = (
        'titre',
        'message',
        'utilisateur__username',
        'projet__nom',
        'projet__numero',
    )
    ordering = ('-date_creation',)
    readonly_fields = ('date_creation',)

    # Action pour marquer comme lue
    actions = ['marquer_comme_lue']

    def marquer_comme_lue(self, request, queryset):
        updated = queryset.update(lue=True)
        self.message_user(request, f"{updated} notification(s) marquée(s) comme lue(s).")
    marquer_comme_lue.short_description = "Marquer les notifications sélectionnées comme lues"
    
@admin.register(Profile)    
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'avatar')
    search_fields = ('user__username', 'user__email')
    list_per_page = 20    

@admin.register(SuiviExecution)
class SuiviExecutionAdmin(admin.ModelAdmin):
    list_display = ('type_suivi', 'projet', 'titre', 'date', 'redacteur', 'importance', 'date_creation', 'date_modification')
    list_filter = ('type_suivi', 'importance', 'date', 'date_creation', 'date_modification')
    search_fields = ('titre', 'description', 'projet__nom', 'redacteur')
    date_hierarchy = 'date'
    list_per_page = 20