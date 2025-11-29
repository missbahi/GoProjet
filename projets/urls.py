# projets/urls.py

from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView
from django.contrib.auth import views as auth_views
# This file defines the URL patterns for the 'projets' app.

app_name = "projets"

urlpatterns = [
    # Home
    path('', views.home, name='home'),
    path('diagnostic/', views.diagnostic, name='diagnostic'),

    # Gestion des projets
    path('projets/', views.liste_projets, name='liste_projets'),
    path('projets/liste_projets/', views.liste_projets, name='liste_projets'),
    
    # path('projet/<int:projet_id>/modifier/', views.modifier_projet, name='modifier_projet'),
    path('projet/<int:projet_id>/supprimer/', views.supprimer_projet, name='supprimer_projet'),
    
    path('projet/<int:projet_id>/dashboard/', views.dashboard_projet, name='dashboard'),
    
    path('projets/ajouter_projet_modal/', views.ajouter_projet_modal, name='ajouter_projet_modal'),
    path('modifier_projet_modal/<int:projet_id>/', views.modifier_projet_modal, name='modifier_projet_modal'),
    
    # Gestion des lots et du bordereau des prix
    path('projet/<int:projet_id>/lots/', views.lots_projet, name='lots_projet'),
    path('projet/<int:projet_id>/lot/<int:lot_id>/modifier/', views.modifier_lot, name='modifier_lot'),
    path('projet/<int:projet_id>/lot/<int:lot_id>/supprimer/', views.supprimer_lot, name='supprimer_lot'),
    path('projet/<int:projet_id>/lot/<int:lot_id>/saisie/', views.saisie_bordereau, name='saisie_bordereau'),
    path('api/lot/<int:lot_id>/save/', views.sauvegarder_lignes_bordereau, name='sauvegarder_lignes_bordereau'),
    
    # Gestion des nodes
    path('lot/<int:lot_id>/node/<int:node_id>/toggle/', views.toggle_node, name='toggle_node'),
    path('lot/<int:lot_id>/node/<int:node_id>/indent/', views.indent_node, name='indent_node'),
    path('lot/<int:lot_id>/node/<int:node_id>/outdent/', views.outdent_node, name='outdent_node'),
    path('lot/<int:lot_id>/node/<int:node_id>/children/', views.get_children, name='get_children'),
    
    # Apropos et base de données
    path('apropos/', views.apropos, name='apropos'),
    path('base-donnees/', views.base_donnees, name='base_donnees'),
    
    # Gestion des utilisateurs
    path('utilisateurs/', views.liste_utilisateurs, name='liste_utilisateurs'),
    path('utilisateurs/ajouter/', views.ajouter_utilisateur, name='ajouter_utilisateur'),
    path('utilisateurs/modifier/<int:user_id>/', views.modifier_utilisateur, name='modifier_utilisateur'),
    path('utilisateurs/supprimer/<int:user_id>/', views.supprimer_utilisateur, name='supprimer_utilisateur'),
    path('utilisateurs/<int:user_id>/gerer-projets/', views.gerer_projets_utilisateur, name='gerer_projets_utilisateur'),
    
    # Gestion du profil utilisateur
    path('modal/profile/', views.profile_modal, name='profile_modal'),
    path('modal/password/', views.password_modal, name='password_modal'),
    path('profile/update/', views.profile_update, name='profile_update'),
    path('profile/change-password/', views.password_change, name='password_change'),
    path('media/avatars/<str:filename>', views.serve_avatar, name='serve_avatar'),
    path('modal/avatar-upload/', views.avatar_upload_modal, name='avatar_upload_modal'),
    path('upload-avatar/', views.upload_avatar, name='upload_avatar'),
    
    path('download-document/<str:model_name>/<int:object_id>/', views.secure_download, name='download_document'),    
    
    # Gestion des notifications
    path('notifications/', views.liste_notifications, name='liste_notifications'),
    path('notifications/mark-as-read/<int:notification_id>/', views.mark_notification_as_read, name='mark_notification_as_read'),
    path('notifications/mark-all-as-read/', views.mark_all_notifications_as_read, name='mark_all_notifications_as_read'),
    path('notifications/create/', views.creer_notification, name='creer_notification'),
    
    # Gestion des ingénieurs
    path('ingenieurs/ajouter/', views.ajouter_ingenieur, name='ajouter_ingenieur'),
    path('ingenieurs/modifier/<int:ingenieur_id>/', views.modifier_ingenieur, name='modifier_ingenieur'),
    path('ingenieurs/supprimer/<int:ingenieur_id>/', views.supprimer_ingenieur, name='supprimer_ingenieur'),
    path('base_donnees/ingenieurs/', views.partial_ingenieurs, name='partial_ingenieurs'),
    
    # Gestion des entreprises
    path('entreprises/ajouter/', views.ajouter_entreprise, name='ajouter_entreprise'),
    path('entreprises/modifier/<int:entreprise_id>/', views.modifier_entreprise, name='modifier_entreprise'),
    path('entreprises/supprimer/<int:entreprise_id>/', views.supprimer_entreprise, name='supprimer_entreprise'),
    path('base_donnees/entreprises/', views.partial_entreprises, name='partial_entreprises'),
    
    # Gestion des clients
    path('clients/ajouter/', views.ajouter_client, name='ajouter_client'),
    path('clients/modifier/<int:client_id>/', views.modifier_client, name='modifier_client'),
    path('clients/supprimer/<int:client_id>/', views.supprimer_client, name='supprimer_client'),
    path('base_donnees/clients/', views.partial_clients, name='partial_clients'),
    
    # Gestion des documents
    path('projet/<int:projet_id>/documents/', views.documents_projet, name='documents'), 
    path('projet/<int:projet_id>/documents/supprimer/<int:document_id>/', views.supprimer_document, name='supprimer_document'),
    path('document/<int:document_id>/telecharger/', views.telecharger_document, name='telecharger_document'),
    path('document/<int:document_id>/afficher/', views.AfficherDocumentView.as_view(), name='afficher_document'),
    path('projet/<int:projet_id>/documents/ajouter/', views.ajouter_document, name='ajouter_document'),
    
    # Suivi d'exécution
    path('projet/<int:projet_id>/suivi/', views.suivi_execution, name='suivi_execution'),
    path('projet/<int:projet_id>/suivi/ajouter/', views.ajouter_suivi, name='ajouter_suivi'),
    path('projet/<int:projet_id>/suivi/supprimer/<int:suivi_id>/', views.supprimer_suivi, name='supprimer_suivi'),
    path('projet/<int:projet_id>/suivi/modifier/<int:suivi_id>/', views.modifier_suivi, name='modifier_suivi'),
    
    # Fichiers de suivi
    path('fichier_suivi/<int:fichier_id>/afficher/', views.afficher_fichier_suivi, name='afficher_fichier_suivi'),
    path('fichier_suivi/<int:fichier_id>/telecharger/', views.telecharger_fichier_suivi, name='telecharger_fichier_suivi'),
    path('fichier_suivi/<int:fichier_id>/supprimer/', views.supprimer_fichier_suivi, name='supprimer_fichier_suivi'),
    path('projet/<int:projet_id>/suivi/<int:suivi_id>/fichiers/ajouter/', views.ajouter_fichier_suivi, name='ajouter_fichier_suivi'),
    
    # API pour lister les taches 
    path('api/get-form-data/', views.get_form_data, name='get_form_data'),
    
    # Gestion des taches
    path('taches/', views.ListeTachesView.as_view(), name='liste_taches'),
    path('taches/nouvelle/', views.CreerTacheView.as_view(), name='creer_tache'),
    path('taches/<int:pk>/modifier/', views.ModifierTacheView.as_view(), name='modifier_tache'),
    path('taches/<int:pk>/supprimer/', views.SupprimerTacheView.as_view(), name='supprimer_tache'),
    path('taches/<int:pk>/', views.DetailTacheView.as_view(), name='detail_tache'),
    
    # Attachements au niveau du PROJET (pas du lot) 
    path('projet/<int:projet_id>/attachements/', views.liste_attachements, name='liste_attachements'),
    path('projet/<int:projet_id>/attachements/ajouter/', views.ajouter_attachement, name='ajouter_attachement'),
    path('attachements/modifier/<int:attachement_id>/', views.modifier_attachement, name='modifier_attachement'),
    path('attachements/<int:attachement_id>/', views.detail_attachement, name='detail_attachement'),
    path('attachements/supprimer/<int:attachement_id>/', views.supprimer_attachement, name='supprimer_attachement'),
    path('attachements/<int:attachement_id>/ajouter_decompte/', views.attachements_ajouter_decompte, name='attachements_ajouter_decompte'),
    path('attachement/<int:attachement_id>/validation/', views.validation_attachement, name='validation_attachement'),
    path('attachement/<int:attachement_id>/reouvrir/', views.reouvrir_attachement, name='reouvrir_attachement'),
    path('attachement/<int:attachement_id>/transmettre-validation/', views.transmettre_validation_attachement, name='transmettre_validation_attachement'),
    path('attachement/<int:attachement_id>/validation_technique/', views.validation_technique_attachement, name='validation_technique_attachement'),
    path('etape/<int:etape_id>/valider/', views.valider_etape, name='valider_etape'),
    path('etape/<int:etape_id>/passer/', views.passer_etape, name='passer_etape'),
    path('etape/<int:etape_id>/modifier/',  views.modifier_etape, name='modifier_etape'),
    path('etape/<int:etape_id>/reinitialiser/', views.reinitialiser_etape,  name='reinitialiser_etape'),
    path('etape/<int:etape_id>/supprimer/', views.supprimer_etape, name='supprimer_etape'),
    path('processus/<int:process_id>/ajouter_etape/', views.ajouter_etape, name='ajouter_etape'),
    
    # Décomptes
    path('projet/<int:projet_id>/decomptes/', views.liste_decomptes, name='liste_decomptes'),
    path('projet/<int:projet_id>/decomptes/ajouter/', views.projet_ajouter_decompte, name='projet_ajouter_decompte'),
    path('decompte/<int:decompte_id>/', views.detail_decompte, name='detail_decompte'),
    path('decompte/<int:decompte_id>/modifier/', views.modifier_decompte, name='modifier_decompte'),
    path('decompte/<int:decompte_id>/supprimer/', views.supprimer_decompte, name='supprimer_decompte'),
    path('decompte/<int:decompte_id>/calcul-retard/', views.calcul_retard_decompte, name='calcul_retard_decompte'),
    
    # Fiche de contrôle
    path('projet/<int:projet_id>/fiche-contrle/', views.fiche_controle, name='fiche_controle'),
    
    # Ordres de service
    path('projet/<int:projet_id>/ordres-service/', views.ordres_service , name='ordres_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/modifier/', views.modifier_ordre_service, name='modifier_ordre_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/supprimer/', views.supprimer_ordre_service, name='supprimer_ordre_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/details/', views.details_ordre_service, name='details_ordre_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/notifier/', views.notifier_ordre_service, name='notifier_ordre_service'),
    path('projet/<int:projet_id>/ordre-service/<int:ordre_id>/annuler/', views.annuler_ordre_service, name='annuler_ordre_service'),
    path('api/projets/<int:projet_id>/jours-decoules/', views.api_jours_decoules, name='api_jours_decoules'),
     
 ] 



