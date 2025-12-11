# projets/api_views.py
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404
from django.db import transaction
from decimal import Decimal, InvalidOperation
from ..models import Decompte#, RevisionPrix, ConfigRevisionProjet, IndiceRevision, ValeurIndice
from ..models import Projet, Attachement
from datetime import datetime
# =========================================================================
# VUES API POUR LA RÉVISION DES PRIX
# =========================================================================

# @login_required
# @require_http_methods(["GET"])
# def revision_detail(request, decompte_id):
#     """
#     Récupère les détails de la révision d'un décompte
#     GET /api/decomptes/{decompte_id}/revision/
#     """
#     try:
#         # Récupérer le décompte avec vérification de permission
#         decompte = get_object_or_404(Decompte, id=decompte_id)
        
#         # Vérifier que l'utilisateur a accès au projet
#         projet = decompte.attachement.projet
#         if not request.user.has_perm('projets.view_projet', projet):
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Vous n\'avez pas l\'autorisation d\'accéder à ce projet.'
#             }, status=403)
        
#         # Récupérer ou créer la révision
#         revision, created = RevisionPrix.objects.get_or_create(
#             decompte=decompte,
#             defaults={
#                 'config': projet.config_revision if hasattr(projet, 'config_revision') else None,
#                 'date_revision': decompte.date_emission,
#                 'periode_debut': decompte.attachement.date_debut_periode,
#                 'periode_fin': decompte.attachement.date_fin_periode,
#                 'statut': 'BROUILLON'
#             }
#         )
        
#         # Si la révision vient d'être créée, tenter de la calculer
#         if created and revision.config:
#             try:
#                 revision.calculer_revision()
#             except Exception as e:
#                 # Si le calcul échoue, on continue avec les valeurs par défaut
#                 print(f"Calcul automatique échoué: {e}")
        
#         # Préparer les données de réponse
#         data = {
#             'success': True,
#             'revision': {
#                 'id': revision.id,
#                 'decompte_id': revision.decompte.id,
#                 'montant_HT_revisable': float(revision.montant_HT_revisable or 0),
#                 'montant_HT_non_revisable': float(revision.montant_HT_non_revisable or 0),
#                 'taux_revision_calcule': float(revision.taux_revision_calcule or 0),
#                 'montant_revision_calcule': float(revision.montant_revision_calcule or 0),
#                 'statut': revision.statut,
#                 'statut_display': revision.get_statut_display(),
#                 'date_revision': revision.date_revision.strftime('%Y-%m-%d') if revision.date_revision else None,
#                 'periode_debut': revision.periode_debut.strftime('%Y-%m-%d') if revision.periode_debut else None,
#                 'periode_fin': revision.periode_fin.strftime('%Y-%m-%d') if revision.periode_fin else None,
#                 'date_calcul': revision.date_calcul.strftime('%Y-%m-%d %H:%M:%S') if revision.date_calcul else None,
#                 'date_validation': revision.date_validation.strftime('%Y-%m-%d %H:%M:%S') if revision.date_validation else None,
#                 'valide_par': revision.valide_par.username if revision.valide_par else None,
#                 'config_id': revision.config.id if revision.config else None,
#                 'detail_calcul': revision.detail_calcul or {}
#             },
#             'decompte': {
#                 'id': decompte.id,
#                 'numero': decompte.numero,
#                 'montant_revision_prix': float(decompte.montant_revision_prix or 0),
#                 'montant_total_ht': float(decompte.montant_situation_ht or 0),
#                 'montant_total_ttc': float(decompte.montant_situation_ttc or 0),
#                 'montant_net_a_payer': float(decompte.montant_situation_net_a_payer or 0)
#             }
#         }
        
#         # Ajouter les informations du projet si disponible
#         if revision.config:
#             data['config'] = {
#                 'id': revision.config.id,
#                 'type_marche': revision.config.type_marche,
#                 'type_marche_display': revision.config.get_type_marche_display(),
#                 'coefficient_K': float(revision.config.coefficient_K or 0),
#                 'marge_variation': float(revision.config.marge_variation or 0),
#                 'taux_TVA': float(revision.config.taux_TVA or 0),
#                 'coefficients': revision.config.coefficients
#             }
        
#         return JsonResponse(data)
        
#     except Decompte.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Décompte non trouvé.'
#         }, status=404)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Erreur serveur: {str(e)}'
#         }, status=500)


# @login_required
# @csrf_exempt
# @require_http_methods(["POST"])
# def calculer_revision(request, decompte_id):
#     """
#     Calcule automatiquement la révision d'un décompte
#     POST /api/decomptes/{decompte_id}/revision/calculer/
#     """
#     try:
#         with transaction.atomic():
#             # Récupérer le décompte
#             decompte = get_object_or_404(Decompte, id=decompte_id)
            
#             # Vérifier les permissions
#             projet = decompte.attachement.projet
#             if not request.user.has_perm('projets.change_decompte', decompte):
#                 return JsonResponse({
#                     'success': False,
#                     'message': 'Vous n\'avez pas l\'autorisation de modifier ce décompte.'
#                 }, status=403)
            
#             # Récupérer ou créer la révision
#             revision, created = RevisionPrix.objects.get_or_create(
#                 decompte=decompte,
#                 defaults={
#                     'config': projet.config_revision if hasattr(projet, 'config_revision') else None,
#                     'date_revision': decompte.date_emission,
#                     'periode_debut': decompte.attachement.date_debut_periode,
#                     'periode_fin': decompte.attachement.date_fin_periode,
#                     'statut': 'BROUILLON'
#                 }
#             )
            
#             # Vérifier qu'une configuration existe
#             if not revision.config:
#                 return JsonResponse({
#                     'success': False,
#                     'message': 'Aucune configuration de révision définie pour ce projet.'
#                 }, status=400)
            
#             # Effectuer le calcul
#             success = revision.calculer_revision()
            
#             if not success:
#                 return JsonResponse({
#                     'success': False,
#                     'message': 'Le calcul de la révision a échoué. Vérifiez les indices disponibles.'
#                 }, status=400)
            
#             # Mettre à jour le décompte avec le montant calculé
#             decompte.montant_revision_prix = revision.montant_revision_calcule
#             decompte.save()
            
#             # Préparer la réponse
#             response_data = {
#                 'success': True,
#                 'message': 'Révision calculée avec succès.',
#                 'revision': {
#                     'id': revision.id,
#                     'montant_HT_revisable': float(revision.montant_HT_revisable),
#                     'montant_HT_non_revisable': float(revision.montant_HT_non_revisable),
#                     'taux_revision_calcule': float(revision.taux_revision_calcule),
#                     'montant_revision_calcule': float(revision.montant_revision_calcule),
#                     'statut': revision.statut,
#                     'statut_display': revision.get_statut_display(),
#                     'detail_calcul': revision.detail_calcul or {}
#                 },
#                 'decompte': {
#                     'montant_revision_prix': float(decompte.montant_revision_prix)
#                 }
#             }
            
#             # Ajouter les variations détaillées si disponibles
#             if revision.detail_calcul and 'variations_indices' in revision.detail_calcul:
#                 response_data['variations_indices'] = revision.detail_calcul['variations_indices']
            
#             return JsonResponse(response_data)
            
#     except Decompte.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Décompte non trouvé.'
#         }, status=404)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Erreur lors du calcul: {str(e)}'
#         }, status=500)


# @login_required
# @csrf_exempt
# @require_http_methods(["POST"])
# def valider_revision(request, decompte_id):
#     """
#     Valide ou ajuste manuellement la révision
#     POST /api/decomptes/{decompte_id}/revision/valider/
#     """
#     try:
#         with transaction.atomic():
#             # Récupérer le décompte
#             decompte = get_object_or_404(Decompte, id=decompte_id)
            
#             # Vérifier les permissions
#             projet = decompte.attachement.projet
#             if not request.user.has_perm('projets.change_decompte', decompte):
#                 return JsonResponse({
#                     'success': False,
#                     'message': 'Vous n\'avez pas l\'autorisation de modifier ce décompte.'
#                 }, status=403)
            
#             # Récupérer la révision
#             revision = get_object_or_404(RevisionPrix, decompte=decompte)
            
#             # Parser les données JSON
#             try:
#                 data = json.loads(request.body)
#             except json.JSONDecodeError:
#                 return JsonResponse({
#                     'success': False,
#                     'message': 'Données JSON invalides.'
#                 }, status=400)
            
            
#             # Validation des données
#             try:
#                 if taux_valide is not None:
#                     taux_valide = Decimal(str(taux_valide))
#                     if taux_valide < -100 or taux_valide > 100:
#                         return JsonResponse({
#                             'success': False,
#                             'message': 'Le taux doit être compris entre -100% et 100%.'
#                         }, status=400)
                
#                 if montant_valide is not None:
#                     montant_valide = Decimal(str(montant_valide))
#                     if montant_valide < 0:
#                         return JsonResponse({
#                             'success': False,
#                             'message': 'Le montant ne peut pas être négatif.'
#                         }, status=400)
                        
#             except (ValueError, InvalidOperation):
#                 return JsonResponse({
#                     'success': False,
#                     'message': 'Valeurs numériques invalides.'
#                 }, status=400)
            
#             # Vérifier la cohérence taux/montant
#             if taux_valide is not None and montant_valide is not None:
#                 montant_calcule = revision.montant_HT_revisable * (taux_valide / Decimal('100'))
#                 if abs(montant_calcule - montant_valide) > Decimal('0.01'):
#                     return JsonResponse({
#                         'success': False,
#                         'message': f'Incohérence: le montant {montant_valide} DH ne correspond pas au taux {taux_valide}% (devrait être {montant_calcule:.2f} DH)'
#                     }, status=400)
            
#             # Valider la révision
#             revision.valider(
#                 user=request.user,
#                 taux_valide=taux_valide,
#                 montant_valide=montant_valide,
#                 motif_ajustement=motif_ajustement
#             )
            
#             # Mettre à jour le décompte
#             decompte.montant_revision_prix = revision.montant_revision_valide
#             decompte.save()
            
#             # Journaliser l'action
#             revision.historique.create(
#                 utilisateur=request.user,
#                 action='VALIDATION' if taux_valide is None and montant_valide is None else 'MODIF_MNT',
#                 ancienne_valeur={
#                     'montant_revision_valide': float(revision.montant_revision_calcule)
#                 },
#                 nouvelle_valeur={
#                     'montant_revision_valide': float(revision.montant_revision_valide),
#                     'taux_revision_valide': float(revision.taux_revision_valide) if revision.taux_revision_valide else None
#                 },
#                 commentaire=motif_ajustement
#             )
            
#             return JsonResponse({
#                 'success': True,
#                 'message': 'Révision validée avec succès.',
#                 'revision': {
#                     'id': revision.id,
#                     'taux_revision_valide': float(revision.taux_revision_valide) if revision.taux_revision_valide else None,
#                     'montant_revision_valide': float(revision.montant_revision_valide),
#                     'statut': revision.statut,
#                     'statut_display': revision.get_statut_display(),
#                     'valide_par': revision.valide_par.username if revision.valide_par else None,
#                     'date_validation': revision.date_validation.strftime('%Y-%m-%d %H:%M:%S') if revision.date_validation else None
#                 },
#                 'decompte': {
#                     'montant_revision_prix': float(decompte.montant_revision_prix)
#                 }
#             })
            
#     except Decompte.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Décompte non trouvé.'
#         }, status=404)
        
#     except RevisionPrix.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Révision de prix non trouvée pour ce décompte.'
#         }, status=404)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Erreur lors de la validation: {str(e)}'
#         }, status=500)


# @login_required
# @csrf_exempt
# @require_http_methods(["POST"])
# def rejeter_revision(request, decompte_id):
#     """
#     Rejette la proposition de révision
#     POST /api/decomptes/{decompte_id}/revision/rejeter/
#     """
#     try:
#         # Récupérer le décompte
#         decompte = get_object_or_404(Decompte, id=decompte_id)
        
#         # Vérifier les permissions
#         projet = decompte.attachement.projet
#         if not request.user.has_perm('projets.change_decompte', decompte):
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Vous n\'avez pas l\'autorisation de modifier ce décompte.'
#             }, status=403)
        
#         # Récupérer la révision
#         revision = get_object_or_404(RevisionPrix, decompte=decompte)
        
#         # Parser les données JSON
#         try:
#             data = json.loads(request.body)
#         except json.JSONDecodeError:
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Données JSON invalides.'
#             }, status=400)
        
#         motif = data.get('motif', '')
        
#         if not motif:
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Un motif est requis pour rejeter la révision.'
#             }, status=400)
        
#         # Rejeter la révision
#         revision.rejeter(motif)
        
#         # Mettre à jour le décompte
#         decompte.montant_revision_prix = Decimal('0')
#         decompte.save()
        
#         # Journaliser l'action
#         revision.historique.create(
#             utilisateur=request.user,
#             action='REJET',
#             commentaire=motif
#         )
        
#         return JsonResponse({
#             'success': True,
#             'message': 'Révision rejetée avec succès.',
#             'revision': {
#                 'id': revision.id,
#                 'statut': revision.statut,
#                 'statut_display': revision.get_statut_display(),
#                 'motif_ajustement': revision.motif_ajustement
#             }
#         })
        
#     except Decompte.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Décompte non trouvé.'
#         }, status=404)
        
#     except RevisionPrix.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Révision de prix non trouvée pour ce décompte.'
#         }, status=404)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Erreur lors du rejet: {str(e)}'
#         }, status=500)


# @login_required
# @require_http_methods(["GET"])
# def historique_revision(request, decompte_id):
#     """
#     Récupère l'historique des modifications d'une révision
#     GET /api/decomptes/{decompte_id}/revision/historique/
#     """
#     try:
#         # Récupérer le décompte
#         decompte = get_object_or_404(Decompte, id=decompte_id)
        
#         # Vérifier les permissions
#         projet = decompte.attachement.projet
#         if not request.user.has_perm('projets.view_decompte', decompte):
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Vous n\'avez pas l\'autorisation de voir ce décompte.'
#             }, status=403)
        
#         # Récupérer la révision
#         revision = get_object_or_404(RevisionPrix, decompte=decompte)
        
#         # Récupérer l'historique
#         historique = revision.historique.all().order_by('-date_modification')
        
#         historique_data = []
#         for h in historique:
#             historique_data.append({
#                 'id': h.id,
#                 'date_modification': h.date_modification.strftime('%Y-%m-%d %H:%M:%S'),
#                 'utilisateur': h.utilisateur.username if h.utilisateur else None,
#                 'utilisateur_nom': h.utilisateur.get_full_name() if h.utilisateur and h.utilisateur.get_full_name() else h.utilisateur.username if h.utilisateur else None,
#                 'action': h.action,
#                 'action_display': h.get_action_display() if hasattr(h, 'get_action_display') else h.action,
#                 'ancienne_valeur': h.ancienne_valeur,
#                 'nouvelle_valeur': h.nouvelle_valeur,
#                 'commentaire': h.commentaire or ''
#             })
        
#         return JsonResponse({
#             'success': True,
#             'historique': historique_data,
#             'total': len(historique_data)
#         })
        
#     except Decompte.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Décompte non trouvé.'
#         }, status=404)
        
#     except RevisionPrix.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Révision de prix non trouvée pour ce décompte.'
#         }, status=404)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Erreur serveur: {str(e)}'
#         }, status=500)


# @login_required
# @require_http_methods(["GET"])
# def indices_disponibles(request, decompte_id=None):
#     """
#     Récupère la liste des indices disponibles
#     GET /api/indices/disponibles/
#     GET /api/decomptes/{decompte_id}/indices/disponibles/
#     """
#     try:
#         # Si un décompte est spécifié, récupérer les indices pertinents
#         config_coefficients = None
#         if decompte_id:
#             decompte = get_object_or_404(Decompte, id=decompte_id)
#             projet = decompte.attachement.projet
            
#             # Vérifier les permissions
#             if not request.user in projet.users.all():
#                 return JsonResponse({
#                     'success': False,
#                     'message': 'Vous n\'avez pas l\'autorisation d\'accéder à ce projet.'
#                 }, status=403)
            
#             # Récupérer la configuration du projet
#             if hasattr(projet, 'config_revision'):
#                 config_coefficients = projet.config_revision.coefficients
        
#         # Récupérer tous les indices
#         indices = IndiceRevision.objects.all().order_by('code')
        
#         indices_data = []
#         for indice in indices:
#             # Récupérer la dernière valeur connue
#             derniere_valeur = ValeurIndice.objects.filter(
#                 indice=indice
#             ).order_by('-mois').first()
            
#             # Récupérer la valeur du mois dernier pour comparaison
#             from datetime import datetime
#             from dateutil.relativedelta import relativedelta
            
#             mois_dernier = datetime.now() - relativedelta(months=1)
#             valeur_mois_dernier = ValeurIndice.objects.filter(
#                 indice=indice,
#                 mois__year=mois_dernier.year,
#                 mois__month=mois_dernier.month
#             ).first()
            
#             indice_info = {
#                 'id': indice.id,
#                 'code': indice.code,
#                 'libelle': indice.libelle,
#                 'unite': indice.unite,
#                 'coefficient': config_coefficients.get(indice.code, 0) if config_coefficients else 0,
#                 'derniere_valeur': {
#                     'valeur': float(derniere_valeur.valeur) if derniere_valeur else 0,
#                     'mois': derniere_valeur.mois.strftime('%Y-%m') if derniere_valeur else None,
#                     'date_publication': derniere_valeur.date_publication.strftime('%Y-%m-%d') if derniere_valeur else None
#                 } if derniere_valeur else None,
#                 'valeur_mois_dernier': {
#                     'valeur': float(valeur_mois_dernier.valeur) if valeur_mois_dernier else 0,
#                     'mois': valeur_mois_dernier.mois.strftime('%Y-%m') if valeur_mois_dernier else None
#                 } if valeur_mois_dernier else None
#             }
            
#             # Calculer la variation si possible
#             if derniere_valeur and valeur_mois_dernier and valeur_mois_dernier.valeur > 0:
#                 variation = ((derniere_valeur.valeur - valeur_mois_dernier.valeur) / valeur_mois_dernier.valeur) * 100
#                 indice_info['variation_mensuelle'] = float(variation)
#             else:
#                 indice_info['variation_mensuelle'] = 0
            
#             indices_data.append(indice_info)
        
#         # Récupérer les statistiques générales
#         total_indices = indices.count()
#         indices_avec_valeurs = sum(1 for i in indices_data if i['derniere_valeur'])
        
#         return JsonResponse({
#             'success': True,
#             'indices': indices_data,
#             'statistiques': {
#                 'total_indices': total_indices,
#                 'indices_avec_valeurs': indices_avec_valeurs,
#                 'pourcentage_complet': (indices_avec_valeurs / total_indices * 100) if total_indices > 0 else 0
#             },
#             'config_coefficients': config_coefficients if config_coefficients else {}
#         })
        
#     except Decompte.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Décompte non trouvé.'
#         }, status=404)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Erreur serveur: {str(e)}'
#         }, status=500)


# @login_required
# @csrf_exempt
# @require_http_methods(["POST"])
# def simuler_revision(request, decompte_id):
#     """
#     Simule une révision avec des paramètres personnalisés
#     POST /api/decomptes/{decompte_id}/revision/simuler/
#     """
#     try:
#         # Récupérer le décompte
#         decompte = get_object_or_404(Decompte, id=decompte_id)
        
#         # Vérifier les permissions
#         projet = decompte.attachement.projet
#         if not request.user.has_perm('projets.view_decompte', decompte):
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Vous n\'avez pas l\'autorisation de voir ce décompte.'
#             }, status=403)
        
#         # Parser les données JSON
#         try:
#             data = json.loads(request.body)
#         except json.JSONDecodeError:
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Données JSON invalides.'
#             }, status=400)
        
#         # Récupérer les paramètres de simulation
#         coefficients_personnalises = data.get('coefficients', {})
#         coefficient_K = data.get('coefficient_K')
#         montant_revisable = data.get('montant_revisable')
        
#         # Récupérer ou créer une révision temporaire pour le calcul
#         revision, created = RevisionPrix.objects.get_or_create(
#             decompte=decompte,
#             defaults={
#                 'config': projet.config_revision if hasattr(projet, 'config_revision') else None,
#                 'date_revision': decompte.date_emission,
#                 'periode_debut': decompte.attachement.date_debut_periode,
#                 'periode_fin': decompte.attachement.date_fin_periode,
#                 'statut': 'BROUILLON'
#             }
#         )
        
#         # Vérifier qu'une configuration existe
#         if not revision.config:
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Aucune configuration de révision définie pour ce projet.'
#             }, status=400)
        
#         # Sauvegarder la configuration originale
#         config_originale = revision.config.coefficients.copy()
#         K_original = revision.config.coefficient_K
        
#         try:
#             # Appliquer les coefficients personnalisés
#             if coefficients_personnalises:
#                 revision.config.coefficients = coefficients_personnalises
            
#             if coefficient_K is not None:
#                 revision.config.coefficient_K = Decimal(str(coefficient_K))
            
#             # Utiliser le montant revisable personnalisé si fourni
#             if montant_revisable is not None:
#                 montant_revisable_decimal = Decimal(str(montant_revisable))
#             else:
#                 montant_revisable_decimal = revision._calculer_montant_revisable()
            
#             # Simuler le calcul
#             indices_base = revision._get_indices_base()
#             indices_courants = revision._get_indices_courants()
            
#             variations = {}
#             total_variation = Decimal('0')
            
#             for code, coeff in revision.config.coefficients.items():
#                 try:
#                     I0 = indices_base.get(code)  # Indice de base
#                     I1 = indices_courants.get(code)  # Indice courant
                    
#                     if I0 and I1 and I0 > 0:
#                         variation = (I1 / I0 - Decimal('1'))
#                         variations[code] = {
#                             'indice_base': float(I0),
#                             'indice_courant': float(I1),
#                             'variation': float(variation),
#                             'coefficient': float(coeff),
#                             'contribution': float(variation * coeff)
#                         }
#                         total_variation += variation * coeff
#                 except (KeyError, TypeError, ZeroDivisionError):
#                     continue
            
#             # Appliquer le coefficient de stabilité K
#             variation_finale = total_variation * revision.config.coefficient_K
            
#             # Vérifier le seuil de déclenchement
#             seuil = revision.config.marge_variation / Decimal('100')
            
#             if abs(variation_finale) < seuil:
#                 variation_finale = Decimal('0')
            
#             # Calculer le montant de révision
#             montant_revision = montant_revisable_decimal * variation_finale
            
#             # Préparer les résultats
#             resultats = {
#                 'success': True,
#                 'simulation': {
#                     'montant_revisable': float(montant_revisable_decimal),
#                     'total_variation': float(total_variation),
#                     'coefficient_K': float(revision.config.coefficient_K),
#                     'variation_finale': float(variation_finale),
#                     'montant_revision': float(montant_revision),
#                     'taux_revision': float(variation_finale * Decimal('100')),
#                     'seuil_applique': float(seuil),
#                     'seuil_atteint': abs(variation_finale) >= seuil
#                 },
#                 'variations_indices': variations,
#                 'coefficients_utilises': revision.config.coefficients,
#                 'indices_base': {k: float(v) for k, v in indices_base.items()},
#                 'indices_courants': {k: float(v) for k, v in indices_courants.items()}
#             }
            
#             # Comparer avec la configuration originale si demandé
#             if data.get('comparer_avec_original', False):
#                 # Restaurer la configuration originale
#                 revision.config.coefficients = config_originale
#                 revision.config.coefficient_K = K_original
                
#                 # Recalculer avec la configuration originale
#                 total_variation_original = Decimal('0')
#                 for code, coeff in revision.config.coefficients.items():
#                     try:
#                         I0 = indices_base.get(code)
#                         I1 = indices_courants.get(code)
#                         if I0 and I1 and I0 > 0:
#                             variation = (I1 / I0 - Decimal('1'))
#                             total_variation_original += variation * coeff
#                     except (KeyError, TypeError, ZeroDivisionError):
#                         continue
                
#                 variation_finale_original = total_variation_original * revision.config.coefficient_K
                
#                 # Appliquer le seuil
#                 if abs(variation_finale_original) < seuil:
#                     variation_finale_original = Decimal('0')
                
#                 montant_revision_original = montant_revisable_decimal * variation_finale_original
                
#                 resultats['comparaison'] = {
#                     'original': {
#                         'total_variation': float(total_variation_original),
#                         'variation_finale': float(variation_finale_original),
#                         'montant_revision': float(montant_revision_original),
#                         'taux_revision': float(variation_finale_original * Decimal('100'))
#                     },
#                     'difference': {
#                         'montant': float(montant_revision - montant_revision_original),
#                         'taux': float((variation_finale - variation_finale_original) * Decimal('100'))
#                     }
#                 }
            
#             return JsonResponse(resultats)
            
#         finally:
#             # Restaurer la configuration originale
#             revision.config.coefficients = config_originale
#             revision.config.coefficient_K = K_original
        
#     except Decompte.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Décompte non trouvé.'
#         }, status=404)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Erreur lors de la simulation: {str(e)}'
#         }, status=500)

# @login_required
# @require_http_methods(["GET"])
# def rapport_revision(request, decompte_id):
#     """
#     Génère un rapport détaillé de la révision au format JSON
#     GET /api/decomptes/{decompte_id}/revision/rapport/
#     """
#     try:
#         # Récupérer le décompte
#         decompte = get_object_or_404(Decompte, id=decompte_id)
        
#         # Vérifier les permissions
#         projet = decompte.attachement.projet
#         if not request.user.has_perm('projets.view_decompte', decompte):
#             return JsonResponse({
#                 'success': False,
#                 'message': 'Vous n\'avez pas l\'autorisation de voir ce décompte.'
#             }, status=403)
        
#         # Récupérer la révision
#         revision = get_object_or_404(RevisionPrix, decompte=decompte)
        
#         # Préparer le rapport
#         rapport = {
#             'entete': {
#                 'projet': {
#                     'nom': projet.nom,
#                     'numero': projet.numero,
#                     'maitre_ouvrage': projet.maitre_ouvrage
#                 },
#                 'decompte': {
#                     'numero': decompte.numero,
#                     'date_emission': decompte.date_emission.strftime('%d/%m/%Y') if decompte.date_emission else None,
#                     'type': decompte.get_type_decompte_display(),
#                     'attachement': decompte.attachement.numero if decompte.attachement else None
#                 },
#                 'revision': {
#                     'statut': revision.get_statut_display(),
#                     'date_calcul': revision.date_calcul.strftime('%d/%m/%Y %H:%M') if revision.date_calcul else None,
#                     'date_validation': revision.date_validation.strftime('%d/%m/%Y %H:%M') if revision.date_validation else None,
#                     'valide_par': revision.valide_par.get_full_name() if revision.valide_par else None
#                 }
#             },
#             'montants': {
#                 'HT_revisable': float(revision.montant_HT_revisable or 0),
#                 'HT_non_revisable': float(revision.montant_HT_non_revisable or 0),
#                 'revision_calcule': float(revision.montant_revision_calcule or 0),
#                 'revision_valide': float(revision.montant_revision_valide or 0),
#                 'taux_calcule': float(revision.taux_revision_calcule or 0),
#                 'taux_valide': float(revision.taux_revision_valide or 0) if revision.taux_revision_valide else None,
#                 'difference_ajustement': float(revision.difference_ajustement or 0)
#             },
#             'configuration': {
#                 'type_marche': revision.config.get_type_marche_display() if revision.config else None,
#                 'coefficient_K': float(revision.config.coefficient_K) if revision.config else None,
#                 'marge_variation': float(revision.config.marge_variation) if revision.config else None,
#                 'taux_TVA': float(revision.config.taux_TVA) if revision.config else None,
#                 'coefficients': revision.config.coefficients if revision.config else {}
#             },
#             'calcul_detaille': revision.detail_calcul or {},
#             'indices': {
#                 'base': revision.detail_calcul.get('indices_base', {}) if revision.detail_calcul else {},
#                 'courants': revision.detail_calcul.get('indices_courants', {}) if revision.detail_calcul else {}
#             },
#             'impact_financier': {
#                 'montant_HT_initial': float(decompte.montant_situation_ht - (decompte.montant_revision_prix or 0)),
#                 'montant_HT_final': float(decompte.montant_situation_ht),
#                 'variation_HT': float(decompte.montant_revision_prix or 0),
#                 'taux_variation_HT': float((decompte.montant_revision_prix or 0) / (decompte.montant_situation_ht - (decompte.montant_revision_prix or 0)) * 100) if (decompte.montant_situation_ht - (decompte.montant_revision_prix or 0)) > 0 else 0,
#                 'impact_TTC': float((decompte.montant_revision_prix or 0) * (1 + (decompte.taux_tva or 0) / 100))
#             }
#         }
        
#         # Ajouter l'historique récent si demandé
#         if request.GET.get('inclure_historique', 'false').lower() == 'true':
#             historique = revision.historique.all().order_by('-date_modification')[:10]
#             rapport['historique_recent'] = [
#                 {
#                     'date': h.date_modification.strftime('%d/%m/%Y %H:%M'),
#                     'action': h.get_action_display(),
#                     'utilisateur': h.utilisateur.get_full_name() if h.utilisateur else None,
#                     'commentaire': h.commentaire
#                 }
#                 for h in historique
#             ]
        
#         return JsonResponse({
#             'success': True,
#             'rapport': rapport,
#             'generation_date': datetime.now().strftime('%d/%m/%Y %H:%M:%S')
#         })
        
#     except Decompte.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Décompte non trouvé.'
#         }, status=404)
        
#     except RevisionPrix.DoesNotExist:
#         return JsonResponse({
#             'success': False,
#             'message': 'Révision de prix non trouvée pour ce décompte.'
#         }, status=404)
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'message': f'Erreur lors de la génération du rapport: {str(e)}'
#         }, status=500)


# @login_required
# @require_http_methods(["GET"])
# def exporter_revision_csv(request, decompte_id):
#     """
#     Exporte les données de révision au format CSV
#     GET /api/decomptes/{decompte_id}/revision/export/csv/
#     """
#     import csv
#     from django.http import HttpResponse
    
#     try:
#         # Récupérer le décompte
#         decompte = get_object_or_404(Decompte, id=decompte_id)
        
#         # Vérifier les permissions
#         projet = decompte.attachement.projet
#         if not request.user.has_perm('projets.view_decompte', decompte):
#             return HttpResponse(
#                 "Vous n'avez pas l'autorisation d'accéder à ce décompte.",
#                 status=403,
#                 content_type='text/plain'
#             )
        
#         # Récupérer la révision
#         revision = get_object_or_404(RevisionPrix, decompte=decompte)
        
#         # Créer la réponse HTTP avec en-tête CSV
#         response = HttpResponse(content_type='text/csv')
#         response['Content-Disposition'] = f'attachment; filename="revision_prix_{decompte.numero}_{datetime.now().strftime("%Y%m%d")}.csv"'
        
#         writer = csv.writer(response, delimiter=';')
        
#         # Écrire l'en-tête
#         writer.writerow(['RAPPORT DE RÉVISION DE PRIX'])
#         writer.writerow([])
#         writer.writerow(['PROJET', projet.nom, 'NUMÉRO', projet.numero])
#         writer.writerow(['DÉCOMPTE', decompte.numero, 'DATE', decompte.date_emission.strftime('%d/%m/%Y') if decompte.date_emission else ''])
#         writer.writerow(['ATTACHEMENT', decompte.attachement.numero if decompte.attachement else '', 'TYPE', decompte.get_type_decompte_display()])
#         writer.writerow([])
        
#         # Section montants
#         writer.writerow(['MONTANTS'])
#         writer.writerow(['Montant HT révisable', f"{revision.montant_HT_revisable:,.2f} DH"])
#         writer.writerow(['Montant HT non révisable', f"{revision.montant_HT_non_revisable:,.2f} DH"])
#         writer.writerow(['Taux de révision calculé', f"{revision.taux_revision_calcule:,.2f} %"])
#         writer.writerow(['Montant de révision calculé', f"{revision.montant_revision_calcule:,.2f} DH"])
#         writer.writerow(['Taux de révision validé', f"{revision.taux_revision_valide:,.2f} %" if revision.taux_revision_valide else 'N/A'])
#         writer.writerow(['Montant de révision validé', f"{revision.montant_revision_valide:,.2f} DH" if revision.montant_revision_valide else 'N/A'])
#         writer.writerow(['Différence d\'ajustement', f"{revision.difference_ajustement:,.2f} DH"])
#         writer.writerow([])
        
#         # Configuration
#         if revision.config:
#             writer.writerow(['CONFIGURATION'])
#             writer.writerow(['Type de marché', revision.config.get_type_marche_display()])
#             writer.writerow(['Coefficient K', f"{revision.config.coefficient_K:.3f}"])
#             writer.writerow(['Marge de variation', f"{revision.config.marge_variation:.2f} %"])
#             writer.writerow(['Taux TVA', f"{revision.config.taux_TVA:.2f} %"])
#             writer.writerow([])
            
#             # Coefficients par indice
#             writer.writerow(['COEFFICIENTS PAR INDICE'])
#             writer.writerow(['Code', 'Coefficient', 'Valeur base', 'Valeur courante', 'Variation'])
            
#             if revision.detail_calcul and 'variations_indices' in revision.detail_calcul:
#                 variations = revision.detail_calcul['variations_indices']
#                 for code, details in variations.items():
#                     writer.writerow([
#                         code,
#                         f"{details['coefficient']:.3f}",
#                         f"{details['indice_base']:.2f}",
#                         f"{details['indice_courant']:.2f}",
#                         f"{details['variation']:.4f} ({details['variation']*100:.2f}%)"
#                     ])
            
#             writer.writerow([])
        
#         # Résumé du calcul
#         if revision.detail_calcul:
#             writer.writerow(['RÉSUMÉ DU CALCUL'])
#             writer.writerow(['Variation totale', f"{revision.detail_calcul.get('total_variation', 0):.4f} ({revision.detail_calcul.get('total_variation', 0)*100:.2f}%)"])
#             writer.writerow(['Coefficient K appliqué', f"{revision.detail_calcul.get('coefficient_K', 0):.3f}"])
#             writer.writerow(['Variation finale', f"{revision.detail_calcul.get('variation_finale', 0):.4f} ({revision.detail_calcul.get('variation_finale', 0)*100:.2f}%)"])
#             writer.writerow(['Seuil appliqué', f"{revision.detail_calcul.get('seuil_applique', 0):.4f} ({revision.detail_calcul.get('seuil_applique', 0)*100:.2f}%)"])
#             writer.writerow(['Formule utilisée', revision.detail_calcul.get('formule_utilisee', 'N/A')])
#             writer.writerow([])
        
#         # Impact financier
#         writer.writerow(['IMPACT FINANCIER'])
#         writer.writerow(['Montant HT initial', f"{(decompte.montant_situation_ht - (decompte.montant_revision_prix or 0)):,.2f} DH"])
#         writer.writerow(['Montant HT final', f"{decompte.montant_situation_ht:,.2f} DH"])
#         writer.writerow(['Variation HT', f"{(decompte.montant_revision_prix or 0):,.2f} DH"])
#         writer.writerow(['Taux de variation HT', f"{((decompte.montant_revision_prix or 0) / (decompte.montant_situation_ht - (decompte.montant_revision_prix or 0)) * 100 if (decompte.montant_situation_ht - (decompte.montant_revision_prix or 0)) > 0 else 0):.2f} %"])
#         writer.writerow(['Impact TTC', f"{((decompte.montant_revision_prix or 0) * (1 + (decompte.taux_tva or 0) / 100)):,.2f} DH"])
#         writer.writerow([])
        
#         # Informations de suivi
#         writer.writerow(['SUIVI'])
#         writer.writerow(['Statut', revision.get_statut_display()])
#         writer.writerow(['Date de calcul', revision.date_calcul.strftime('%d/%m/%Y %H:%M') if revision.date_calcul else 'N/A'])
#         writer.writerow(['Date de validation', revision.date_validation.strftime('%d/%m/%Y %H:%M') if revision.date_validation else 'N/A'])
#         writer.writerow(['Validé par', revision.valide_par.get_full_name() if revision.valide_par else 'N/A'])
        
#         if revision.motif_ajustement:
#             writer.writerow([])
#             writer.writerow(['MOTIF D\'AJUSTEMENT'])
#             writer.writerow([revision.motif_ajustement])
        
#         writer.writerow([])
#         writer.writerow(['Généré le', datetime.now().strftime('%d/%m/%Y %H:%M:%S')])
#         writer.writerow(['Par', request.user.get_full_name() or request.user.username])
        
#         return response
        
#     except Decompte.DoesNotExist:
#         return HttpResponse(
#             "Décompte non trouvé.",
#             status=404,
#             content_type='text/plain'
#         )
        
#     except RevisionPrix.DoesNotExist:
#         return HttpResponse(
#             "Révision de prix non trouvée pour ce décompte.",
#             status=404,
#             content_type='text/plain'
#         )
        
#     except Exception as e:
#         return HttpResponse(
#             f"Erreur lors de l'export: {str(e)}",
#             status=500,
#             content_type='text/plain'
#         )


# =========================================================================
# VUE DE SANTÉ DES API
# =========================================================================

# @login_required
# @require_http_methods(["GET"])
# def api_health_check(request):
#     """
#     Vérifie l'état des API et des modèles
#     GET /api/health/
#     """
#     try:
#         # Vérifier les modèles
#         stats = {
#             'models': {
#                 'Decompte': Decompte.objects.count(),
#                 'RevisionPrix': RevisionPrix.objects.count(),
#                 'IndiceRevision': IndiceRevision.objects.count(),
#                 'ValeurIndice': ValeurIndice.objects.count(),
#                 'ConfigRevisionProjet': ConfigRevisionProjet.objects.count(),
#             },
#             'system': {
#                 'user_authenticated': request.user.is_authenticated,
#                 'user_id': request.user.id,
#                 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#             }
#         }
        
#         return JsonResponse({
#             'success': True,
#             'status': 'healthy',
#             'stats': stats,
#             'apis_disponibles': [
#                 'GET /api/decomptes/<id>/revision/',
#                 'POST /api/decomptes/<id>/revision/calculer/',
#                 'POST /api/decomptes/<id>/revision/valider/',
#                 'POST /api/decomptes/<id>/revision/rejeter/',
#                 'GET /api/decomptes/<id>/revision/historique/',
#                 'GET /api/indices/disponibles/',
#                 'POST /api/decomptes/<id>/revision/simuler/',
#                 'GET /api/decomptes/<id>/revision/rapport/',
#                 'GET /api/decomptes/<id>/revision/export/csv/',
#                 'GET /api/health/'
#             ]
#         })
        
#     except Exception as e:
#         return JsonResponse({
#             'success': False,
#             'status': 'unhealthy',
#             'error': str(e)
#         }, status=500)

