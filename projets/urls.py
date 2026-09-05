# projets/urls.py

from django.urls import path, include
from .views.data_views import views as data_views
from .views.user_views import views as user_views
from .views.project_views import views as project_views
from .views.site_views import views as site_views
from .views.reporting_views import views as reporting_views
from .views.task_views import views as task_views
from .views.notification_views import views as notification_views
from .views.os_views import views as os_views
from .views.lot_views import views as lot_views
from .views.suivi_views import views as suivi_views
from .views.attachement_views import views as attachement_views
from django.views.generic import TemplateView

app_name = "projets"


# URL patterns pour les différentes fonctionnalités de l'application
commun_urlpatterns = [
    # Home
    path('home/', site_views.home, name='home'),
    path('dossiers/gerer/', project_views.gerer_dossiers, name='gerer_dossiers'),
    path('dossiers/<int:dossier_id>/modifier/', project_views.modifier_dossier, name='modifier_dossier'),
    path('', site_views.landing, name='landing'),
    # Apropos
    path('apropos/', site_views.apropos, name='apropos'),
    # Secure download
    path('download-document/<str:model_name>/<int:object_id>/', os_views.secure_download, name='download_document'),    
    # API pour lister les taches 
    path('api/get-form-data/', task_views.get_form_data, name='get_form_data'),
    # PWA URLs
    path('manifest.json', TemplateView.as_view(template_name='manifest.json', content_type='application/json',), name='manifest'),
    path('serviceworker.js', TemplateView.as_view( content_type='application/javascript',), name='serviceworker'),
]

# Gestion des documents, du suivi d'exécution et des fichiers de suivi
suivi_urlpatterns = [
    # Gestion des documents
    path('projet/<int:projet_id>/documents/', os_views.documents_projet, name='documents'), 
    path('projet/<int:projet_id>/documents/supprimer/<int:document_id>/', os_views.supprimer_document, name='supprimer_document'),
    path('document/<int:document_id>/telecharger/', os_views.telecharger_document, name='telecharger_document'),
    path('document/<int:document_id>/afficher/', os_views.AfficherDocumentView.as_view(), name='afficher_document'),
    path('projet/<int:projet_id>/documents/ajouter/', os_views.ajouter_document, name='ajouter_document'),
    
    # Suivi d'exécution
    path('projet/<int:projet_id>/rapports-journaliers/ajouter/', reporting_views.ajouter_rapport_journalier, name='ajouter_rapport_journalier'),
    path('projet/<int:projet_id>/rapports-journaliers/', reporting_views.rapports_journaliers, name='rapports_journaliers'),
    path('projet/<int:projet_id>/rapports-journaliers/formulaire/', reporting_views.formulaire_rapport_journalier, name='formulaire_rapport_journalier'),
    path('projet/<int:projet_id>/rapports-journaliers/<int:rapport_id>/', reporting_views.detail_rapport_journalier, name='detail_rapport_journalier'),
    path('projet/<int:projet_id>/rapports-journaliers/<int:rapport_id>/modifier/', reporting_views.modifier_rapport_journalier, name='modifier_rapport_journalier'),
    path('projet/<int:projet_id>/rapports-journaliers/<int:rapport_id>/supprimer/', reporting_views.supprimer_rapport_journalier, name='supprimer_rapport_journalier'),
    path('projet/<int:projet_id>/situations-mensuelles/', reporting_views.situations_mensuelles, name='situations_mensuelles'),
    path('projet/<int:projet_id>/situations-mensuelles/ajouter/', reporting_views.ajouter_situation_mensuelle, name='ajouter_situation_mensuelle'),
    path('projet/<int:projet_id>/situations-mensuelles/<int:situation_id>/modifier/', reporting_views.modifier_situation_mensuelle, name='modifier_situation_mensuelle'),
    path('projet/<int:projet_id>/situations-mensuelles/<int:situation_id>/supprimer/', reporting_views.supprimer_situation_mensuelle, name='supprimer_situation_mensuelle'),
    path('projet/<int:projet_id>/situations-mensuelles/<int:situation_id>/supprimer-document/', reporting_views.supprimer_document_situation_mensuelle, name='supprimer_document_situation_mensuelle'),
    path('projet/<int:projet_id>/suivi/', suivi_views.suivi_execution, name='suivi_execution'),
    path('projet/<int:projet_id>/suivi/ajouter/', suivi_views.ajouter_suivi, name='ajouter_suivi'),
    path('projet/<int:projet_id>/suivi/supprimer/<int:suivi_id>/', suivi_views.supprimer_suivi, name='supprimer_suivi'),
    path('projet/<int:projet_id>/suivi/modifier/<int:suivi_id>/', suivi_views.modifier_suivi, name='modifier_suivi'),

    # Suivi d'exécution - Suppression de document du rapport journalier
    path('projet/<int:projet_id>/rapports-journaliers/<int:rapport_id>/supprimer-document/', reporting_views.supprimer_document_rapport_journalier, name='supprimer_document_rapport_journalier'),

    # Fichiers de suivi
    path('fichier_suivi/<int:fichier_id>/afficher/', suivi_views.afficher_fichier_suivi, name='afficher_fichier_suivi'),
    path('fichier_suivi/<int:fichier_id>/telecharger/', suivi_views.telecharger_fichier_suivi, name='telecharger_fichier_suivi'),
    path('fichier_suivi/<int:fichier_id>/supprimer/', suivi_views.supprimer_fichier_suivi, name='supprimer_fichier_suivi'),
    path('projet/<int:projet_id>/suivi/<int:suivi_id>/fichiers/ajouter/', suivi_views.ajouter_fichier_suivi, name='ajouter_fichier_suivi'),
]

# Gestion des projets et des lots
projets_urlpatterns = [
     # Gestion des projets
    path('projets/', project_views.liste_projets, name='liste_projets'),
    path('projets/liste_projets/', project_views.liste_projets, name='liste_projets'),
    path('projet/<int:projet_id>/supprimer/', project_views.supprimer_projet, name='supprimer_projet'),
    path('projet/<int:projet_id>/dashboard/', project_views.dashboard_projet, name='dashboard'),
    path('projets/ajouter_projet_modal/', project_views.ajouter_projet_modal, name='ajouter_projet_modal'),
    path('modifier_projet_modal/<int:projet_id>/', project_views.modifier_projet_modal, name='modifier_projet_modal'),
    # Gestion des lots et du bordereau des prix
    path('projet/<int:projet_id>/lots/', lot_views.lots_projet, name='lots_projet'),
    path('projet/<int:projet_id>/lots/details/', lot_views.lots_details, name='lots_details'),
    path('projet/<int:projet_id>/lot/<int:lot_id>/modifier/', lot_views.modifier_lot, name='modifier_lot'),
    path('projet/<int:projet_id>/lot/<int:lot_id>/supprimer/', lot_views.supprimer_lot, name='supprimer_lot'),
    path('api/projet/lots/<int:projet_id>/export-excel/', lot_views.export_excel, name='export_excel'),
    path('projet/<int:projet_id>/lot/<int:lot_id>/saisie/', lot_views.saisie_bordereau, name='saisie_bordereau'),
    path('api/lot/<int:lot_id>/save/', lot_views.sauvegarder_lignes_bordereau, name='sauvegarder_lignes_bordereau'),
]

# Gestion de la base de données
base_donnees_urlpatterns = [
    path('base-donnees/', data_views.base_donnees, name='base_donnees'),
    # Gestion des ingénieurs
    path('ingenieurs/ajouter/', data_views.ajouter_ingenieur, name='ajouter_ingenieur'),
    path('ingenieurs/modifier/<int:ingenieur_id>/', data_views.modifier_ingenieur, name='modifier_ingenieur'),
    path('ingenieurs/supprimer/<int:ingenieur_id>/', data_views.supprimer_ingenieur, name='supprimer_ingenieur'),
    path('base_donnees/ingenieurs/', data_views.partial_ingenieurs, name='partial_ingenieurs'),
    
    # Gestion des entreprises
    path('entreprises/ajouter/', data_views.ajouter_entreprise, name='ajouter_entreprise'),
    path('entreprises/modifier/<int:entreprise_id>/', data_views.modifier_entreprise, name='modifier_entreprise'),
    path('entreprises/supprimer/<int:entreprise_id>/', data_views.supprimer_entreprise, name='supprimer_entreprise'),
    path('base_donnees/entreprises/', data_views.partial_entreprises, name='partial_entreprises'),
    
    # Gestion des clients
    path('clients/ajouter/', data_views.ajouter_client, name='ajouter_client'),
    path('clients/modifier/<int:client_id>/', data_views.modifier_client, name='modifier_client'),
    path('clients/supprimer/<int:client_id>/', data_views.supprimer_client, name='supprimer_client'),
    path('base_donnees/clients/', data_views.partial_clients, name='partial_clients'),

    # Gestion du personnel
    path('personnel/ajouter/', data_views.ajouter_personnel, name='ajouter_personnel'),
    path('personnel/modifier/<int:personnel_id>/', data_views.modifier_personnel, name='modifier_personnel'),
    path('personnel/supprimer/<int:personnel_id>/', data_views.supprimer_personnel, name='supprimer_personnel'),
    path('base_donnees/personnel/', data_views.partial_personnel, name='partial_personnel'),

    # Gestion du matériel
    path('materiel/ajouter/', data_views.ajouter_materiel, name='ajouter_materiel'),
    path('materiel/modifier/<int:materiel_id>/', data_views.modifier_materiel, name='modifier_materiel'),
    path('materiel/supprimer/<int:materiel_id>/', data_views.supprimer_materiel, name='supprimer_materiel'),
    path('base_donnees/materiel/', data_views.partial_materiel, name='partial_materiel'),

    # Gestion des transports
    path('transports/ajouter/', data_views.ajouter_transport, name='ajouter_transport'),
    path('transports/modifier/<int:transport_id>/', data_views.modifier_transport, name='modifier_transport'),
    path('transports/supprimer/<int:transport_id>/', data_views.supprimer_transport, name='supprimer_transport'),
    path('base_donnees/transports/', data_views.partial_transports, name='partial_transports'),

    # Gestion des locations
    path('locations/ajouter/', data_views.ajouter_location, name='ajouter_location'),
    path('locations/modifier/<int:location_id>/', data_views.modifier_location, name='modifier_location'),
    path('locations/supprimer/<int:location_id>/', data_views.supprimer_location, name='supprimer_location'),
    path('base_donnees/locations/', data_views.partial_locations, name='partial_locations'),

    # Gestion des sous-traitances
    path('sous_traitances/ajouter/', data_views.ajouter_sous_traitance, name='ajouter_sous_traitance'),
    path('sous_traitances/modifier/<int:sous_traitance_id>/', data_views.modifier_sous_traitance, name='modifier_sous_traitance'),
    path('sous_traitances/supprimer/<int:sous_traitance_id>/', data_views.supprimer_sous_traitance, name='supprimer_sous_traitance'),
    path('base_donnees/sous_traitances/', data_views.partial_sous_traitances, name='partial_sous_traitances'),

    # Gestion des consommables
    path('consommables/ajouter/', data_views.ajouter_consommable, name='ajouter_consommable'),
    path('consommables/modifier/<int:consommable_id>/', data_views.modifier_consommable, name='modifier_consommable'),
    path('consommables/supprimer/<int:consommable_id>/', data_views.supprimer_consommable, name='supprimer_consommable'),
    path('base_donnees/consommables/', data_views.partial_consommables, name='partial_consommables'),

    # Gestion des fournitures
    path('fournitures/ajouter/', data_views.ajouter_fourniture, name='ajouter_fourniture'),
    path('fournitures/modifier/<int:fourniture_id>/', data_views.modifier_fourniture, name='modifier_fourniture'),
    path('fournitures/supprimer/<int:fourniture_id>/', data_views.supprimer_fourniture, name='supprimer_fourniture'),
    path('base_donnees/fournitures/', data_views.partial_fournitures, name='partial_fournitures'),
]

# Gestion des taches
tache_urlpatterns = [
    path('taches/', task_views.ListeTachesView.as_view(), name='liste_taches'),
    path('taches/nouvelle/', task_views.CreerTacheView.as_view(), name='creer_tache'),
    path('taches/<int:pk>/modifier/', task_views.ModifierTacheView.as_view(), name='modifier_tache'),
    path('taches/<int:pk>/supprimer/', task_views.SupprimerTacheView.as_view(), name='supprimer_tache'),
    path('taches/<int:pk>/', task_views.DetailTacheView.as_view(), name='detail_tache'), 
]

# Attachements au niveau du PROJET (pas du lot) et processus de validation des attachements
attachement_urlpatterns = [
    path('projet/<int:projet_id>/attachements/', attachement_views.liste_attachements, name='liste_attachements'),
    path('projet/<int:projet_id>/attachements/ajouter/', attachement_views.ajouter_attachement, name='ajouter_attachement'),
    path('attachements/modifier/<int:attachement_id>/', attachement_views.modifier_attachement, name='modifier_attachement'),
    path('attachements/<int:attachement_id>/', attachement_views.detail_attachement, name='detail_attachement'),
    path('attachements/<int:attachement_id>/tracabilite-validation/', attachement_views.tracabilite_validation_attachement, name='tracabilite_validation_attachement'),
    path('attachements/supprimer/<int:attachement_id>/', attachement_views.supprimer_attachement, name='supprimer_attachement'),
    path('attachements/<int:attachement_id>/ajouter_decompte/', attachement_views.attachements_ajouter_decompte, name='attachements_ajouter_decompte'),
    # validation processus
    path('attachement/<int:attachement_id>/validation/', attachement_views.validation_attachement, name='validation_attachement'),
    path('attachement/<int:attachement_id>/reouvrir/', attachement_views.reouvrir_attachement, name='reouvrir_attachement'),
    path('attachement/<int:attachement_id>/transmettre-validation/', attachement_views.transmettre_validation_attachement, name='transmettre_validation_attachement'),
    path('attachement/<int:attachement_id>/validation_technique/', attachement_views.validation_technique_attachement, name='validation_technique_attachement'),
    path('etape/<int:etape_id>/valider/', attachement_views.valider_etape, name='valider_etape'),
    path('etape/<int:etape_id>/passer/', attachement_views.passer_etape, name='passer_etape'),
    path('etape/<int:etape_id>/modifier/',  attachement_views.modifier_etape, name='modifier_etape'),
    path('etape/<int:etape_id>/reinitialiser/', attachement_views.reinitialiser_etape,  name='reinitialiser_etape'),
    path('etape/<int:etape_id>/supprimer/', attachement_views.supprimer_etape, name='supprimer_etape'),
    path('processus/<int:process_id>/ajouter_etape/', attachement_views.ajouter_etape, name='ajouter_etape'),
    # Décomptes
    path('projet/<int:projet_id>/decomptes/', attachement_views.liste_decomptes, name='liste_decomptes'),
    path('projet/<int:projet_id>/decomptes/ajouter/', attachement_views.projet_ajouter_decompte, name='projet_ajouter_decompte'),
    path('decompte/<int:decompte_id>/', attachement_views.detail_decompte, name='detail_decompte'),
    path('decompte/<int:decompte_id>/modifier/', attachement_views.modifier_decompte, name='modifier_decompte'),
    path('decompte/<int:decompte_id>/supprimer/', attachement_views.supprimer_decompte, name='supprimer_decompte'),
    path('decompte/<int:decompte_id>/calcul-retard/', attachement_views.calcul_retard_decompte, name='calcul_retard_decompte'),
    # Fiche de contrôle
    path('projet/<int:projet_id>/fiche-contrle/', attachement_views.fiche_controle, name='fiche_controle'),
]

# # Gestion du profil utilisateur et des utilisateurs
utilisateur_urlpatterns = [
    path('modal/profile/', user_views.profile_modal, name='profile_modal'),
    path('modal/password/', user_views.password_modal, name='password_modal'),
    path('profile/update/', user_views.profile_update, name='profile_update'),
    path('profile/change-password/', user_views.password_change, name='password_change'),
    path('media/avatars/<str:filename>', user_views.serve_avatar, name='serve_avatar'),
    path('modal/avatar-upload/', user_views.avatar_upload_modal, name='avatar_upload_modal'),
    path('upload-avatar/', user_views.upload_avatar, name='upload_avatar'),
    # Gestion des utilisateurs
    path('utilisateurs/', user_views.liste_utilisateurs, name='liste_utilisateurs'),
    path('utilisateurs/ajouter/', user_views.ajouter_utilisateur, name='ajouter_utilisateur'),
    path('utilisateurs/modifier/<int:user_id>/', user_views.modifier_utilisateur, name='modifier_utilisateur'),
    path('utilisateurs/supprimer/<int:user_id>/', user_views.supprimer_utilisateur, name='supprimer_utilisateur'),
    path('utilisateurs/<int:user_id>/gerer-projets/', user_views.gerer_projets_utilisateur, name='gerer_projets_utilisateur'),
]

# Gestion des ordres de service et API associées
os_urlpatterns = [
     
    path('projet/<int:projet_id>/ordres-service/', os_views.ordres_service , name='ordres_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/modifier/', os_views.modifier_ordre_service, name='modifier_ordre_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/supprimer/', os_views.supprimer_ordre_service, name='supprimer_ordre_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/details/', os_views.details_ordre_service, name='details_ordre_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/notifier/', os_views.notifier_ordre_service, name='notifier_ordre_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/annuler/', os_views.annuler_ordre_service, name='annuler_ordre_service'),
    path('api/projets/<int:projet_id>/jours-decoules/', os_views.api_jours_decoules, name='api_jours_decoules'),
]

# Gestion des notifications
notifications_urlpatterns = [
     
    path('notifications/', notification_views.liste_notifications, name='liste_notifications'),
    path('notifications/marquer-lue/<int:notification_id>/', 
         notification_views.mark_notification_as_read, name='mark_notification_as_read'),
    path('notifications/marquer-non-lue/<int:notification_id>/', 
         notification_views.mark_notification_as_unread, name='mark_notification_as_unread'),
    path('notifications/supprimer/<int:notification_id>/', 
         notification_views.delete_notification, name='delete_notification'),
    # Actions sur plusieurs notifications
    path('notifications/marquer-selection-lues/', notification_views.mark_selected_as_read, name='mark_selected_as_read'),
    path('notifications/supprimer-selection/', notification_views.delete_selected_notifications, name='delete_selected_notifications'),
    path('notifications/supprimer-toutes-lues/', notification_views.delete_all_read_notifications, name='delete_all_read_notifications'),
    # Actions globales
    path('notifications/marquer-toutes-lues/', notification_views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
    path('notifications/supprimer-toutes/', notification_views.delete_all_notifications, name='delete_all_notifications'),
    # API Notifications
    path('api/projets/<int:projet_id>/notification-data/', notification_views.notification_data_api, name='notification_data_api' ),
    path('api/notifications/non-lues/', notification_views.notifications_non_lues_api, name='notifications_non_lues_api'),
    path('api/notifications/<int:notification_id>/marquer-lue/', notification_views.marquer_notification_lue, name='marquer_notification_lue'),
    # Vue de création
    path('notifications/creer/', notification_views.creer_notification, name='creer_notification'), 
]

urlpatterns = commun_urlpatterns 
urlpatterns += suivi_urlpatterns
urlpatterns += projets_urlpatterns
urlpatterns += base_donnees_urlpatterns
urlpatterns += tache_urlpatterns
urlpatterns += attachement_urlpatterns
urlpatterns += utilisateur_urlpatterns
urlpatterns += os_urlpatterns
urlpatterns += notifications_urlpatterns

# urlpatterns += revision_urlpatterns

# revision_urlpatterns = [
#     # API de révision des prix
#     path('api/decomptes/<int:decompte_id>/revision/', revision.revision_detail, name='api_revision_detail'),
#     path('api/decomptes/<int:decompte_id>/revision/calculer/', revision.calculer_revision, name='api_calculer_revision'),
#     path('api/decomptes/<int:decompte_id>/revision/valider/',  revision.valider_revision, name='api_valider_revision'),
#     path('api/decomptes/<int:decompte_id>/revision/rejeter/', revision.rejeter_revision, name='api_rejeter_revision'),
#     path('api/decomptes/<int:decompte_id>/revision/historique/', revision.historique_revision, name='api_historique_revision'),
#     path('api/decomptes/<int:decompte_id>/revision/simuler/', revision.simuler_revision, name='api_simuler_revision'),
#     path('api/decomptes/<int:decompte_id>/revision/rapport/', revision.rapport_revision, name='api_rapport_revision'),
#     path('api/decomptes/<int:decompte_id>/revision/export/csv/', revision.exporter_revision_csv, name='api_export_revision_csv'),
#     # API des indices
#     path('api/indices/disponibles/', revision.indices_disponibles,  name='api_indices_disponibles'),
#     path('api/decomptes/<int:decompte_id>/indices/disponibles/', revision.indices_disponibles, name='api_indices_disponibles_decompte'),
#     # Santé des API
#     path('api/health/', revision.api_health_check, name='api_health_check'),
# ]


