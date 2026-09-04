from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models.signals import post_save
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from datetime import date, timedelta
from decimal import Decimal
import json
import os
import shutil
import tempfile

from .decorators import est_chef_chantier, est_pointeur, projets_accessibles
from .forms import DossierForm, UtilisateurCreationForm, DocumentSituationMensuelleFormSet
from .services.attachement_service import DonneesAttachementInvalides, enregistrer_lignes_attachement
from .exporters import ExcelExporter
from .models import (
	Attachement,
	Dossier,
	DocumentAdministratif,
	EtapeValidation,
	FichierSuivi,
	Materiel,
	OrdreService,
	Personnel,
	ProcessValidation,
	Projet,
	LotProjet,
	LigneBordereau,
	LigneAttachement,
	SuiviExecution,
	TypeOrdreService,
	RapportJournalier,
	DepenseRapportJournalier,
	Notification,
	SituationMensuelle,
	DocumentSituationMensuelle,
	DepenseSituationMensuelle,
	StockSituationMensuelle,
)
from .signals.notifications import gerer_notifications_projet


class RolesEtDossiersTests(TestCase):
	def setUp(self):
		self.superuser = User.objects.create_superuser(
			username='proprietaire', password='test-password'
		)
		self.gerant = User.objects.create_user(
			username='gerant', password='test-password'
		)
		self.gerant.profile.role = 'GERANT'
		self.gerant.profile.save()
		self.autre_gerant = User.objects.create_user(
			username='autre-gerant', password='test-password'
		)
		self.autre_gerant.profile.role = 'GERANT'
		self.autre_gerant.profile.save()
		self.dossier = Dossier.objects.create(nom='Dossier A', gerant=self.gerant)
		self.autre_dossier = Dossier.objects.create(
			nom='Dossier B', gerant=self.autre_gerant
		)

	def test_gerant_ne_voit_que_ses_projets(self):
		projet_a = Projet(
			nom='Projet A', objet='Objet', numero='A-1',
			maitre_ouvrage='MOA', localisation='Lieu', dossier=self.dossier
		)
		projet_b = Projet(
			nom='Projet B', objet='Objet', numero='B-1',
			maitre_ouvrage='MOA', localisation='Lieu', dossier=self.autre_dossier
		)
		Projet.objects.bulk_create([projet_a, projet_b])

		accessibles = projets_accessibles(self.gerant)

		self.assertEqual(list(accessibles.values_list('numero', flat=True)), ['A-1'])

	def test_gerant_ne_peut_creer_que_staff_ou_utilisateur(self):
		form = UtilisateurCreationForm(user=self.gerant)

		self.assertEqual(
			[value for value, label in form.fields['role'].choices],
			['STAFF', 'UTILISATEUR'],
		)
		self.assertFalse(form.fields['dossiers'].queryset.exclude(pk=self.dossier.pk).exists())

		form = UtilisateurCreationForm(data={
			'username': 'nouvel-utilisateur',
			'password1': 'A-valid-password-123!',
			'password2': 'A-valid-password-123!',
			'role': 'GERANT',
			'dossiers': [self.dossier.pk],
		}, user=self.gerant)

		self.assertFalse(form.is_valid())

	def test_dossier_activite_est_requise_et_persistante(self):
		form = DossierForm(data={
			'nom': 'Dossier Services',
			'description': 'Prestations de service',
			'activite': Dossier.Activite.SERVICES,
			'gerant': self.gerant.pk,
		})

		self.assertTrue(form.is_valid(), form.errors)
		dossier = form.save()
		self.assertEqual(dossier.activite, Dossier.Activite.SERVICES)
		self.assertEqual(
			set(form.fields['activite'].choices),
			set(Dossier.Activite.choices),
		)

	def test_utilisateur_cree_par_gerant_n_est_pas_superuser(self):
		form = UtilisateurCreationForm(data={
			'username': 'staff-cree',
			'password1': 'A-valid-password-123!',
			'password2': 'A-valid-password-123!',
			'role': 'STAFF',
			'dossiers': [self.dossier.pk],
		}, user=self.gerant)

		self.assertTrue(form.is_valid(), form.errors)
		utilisateur = form.save()

		self.assertFalse(utilisateur.is_superuser)
		self.assertFalse(utilisateur.is_staff)
		self.assertEqual(utilisateur.profile.role, 'STAFF')
		self.assertIn(self.dossier, utilisateur.dossiers.all())

	def test_ajout_projet_modal_ajax_retourne_json(self):
		self.client.force_login(self.gerant)
		response = self.client.post(
			reverse('projets:ajouter_projet_modal'),
			{
				'nom': 'Projet AJAX',
				'objet': 'Création via modal',
				'numero': 'AJAX-001',
				'maitre_ouvrage': 'MOA',
				'localisation': 'Rabat',
				'statut': 'AO',
				'avancement': 0,
			},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)

		self.assertEqual(response.status_code, 200)
		self.assertJSONEqual(response.content, {'success': True})
		self.assertTrue(Projet.objects.filter(numero='AJAX-001').exists())


@override_settings(
	USE_R2_DOCUMENTS=False,
	STORAGES={
		'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
		'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
	},
)
class ValidationAttachementRoleTests(TestCase):
	def setUp(self):
		self.projet = Projet.objects.create(
			nom='Projet Validation',
			objet='Validation de flux',
			numero='VAL-001',
			maitre_ouvrage='MOA',
			localisation='Rabat',
		)
		self.chef = User.objects.create_user(
			username='chef-projet', password='test-password'
		)
		self.chef.profile.role = 'CHEF_PROJET'
		self.chef.profile.save()
		self.projet.users.add(self.chef)
		self.attachement = Attachement.objects.create(
			projet=self.projet,
			numero='ATT-001',
			date_etablissement=date.today(),
			date_debut_periode=date.today(),
			date_fin_periode=date.today() + timedelta(days=30),
			statut='TRANSMIS',
		)
		self.validation = ProcessValidation.objects.create(
			attachement=self.attachement,
			type_validation='TECHNIQUE',
			ordre_validation=1,
			est_obligatoire=True,
			demandeur_validation=self.chef,
			statut_validation='EN_ATTENTE',
		)
		self.lot = LotProjet.objects.create(projet=self.projet, nom='Lot test')
		self.ligne_bordereau = LigneBordereau.objects.create(
			lot=self.lot,
			numero='1.1',
			designation='Ligne test',
			unite='u',
			quantite=Decimal('10'),
			prix_unitaire=Decimal('100'),
		)

	def test_chef_de_projet_peut_valider_attachement(self):
		self.assertTrue(self.validation.peut_etre_valide_par(self.chef))

	def test_validation_attachement_page_est_accessible_pour_chef_de_projet(self):
		self.client.force_login(self.chef)
		response = self.client.get(reverse('projets:validation_attachement', args=[self.attachement.id]))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Validation')

	def test_retour_depuis_validation_technique_affiche_le_processus_complet(self):
		self.client.force_login(self.chef)

		response = self.client.get(reverse('projets:validation_technique_attachement', args=[self.attachement.id]))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, reverse('projets:validation_attachement', args=[self.attachement.id]))

	def test_tracabilite_validation_expose_les_details_en_consultation(self):
		self.validation.valider(self.chef, 'Contrôle conforme')
		self.client.force_login(self.chef)

		response = self.client.get(reverse('projets:tracabilite_validation_attachement', args=[self.attachement.id]))

		self.assertEqual(response.status_code, 200)
		contenu = response.json()
		self.assertEqual(contenu['attachement'], 'ATT-001')
		self.assertEqual(contenu['validations'][0]['type'], 'Validation technique')
		self.assertEqual(contenu['validations'][0]['statut'], 'Validé')
		self.assertEqual(contenu['validations'][0]['validateur'], 'chef-projet')
		self.assertEqual(contenu['validations'][0]['commentaires'], 'Contrôle conforme')

	def test_utilisateur_sans_acces_ne_peut_pas_modifier_attachement(self):
		utilisateur = User.objects.create_user(username='sans-acces', password='test-password')
		self.client.force_login(utilisateur)

		response = self.client.get(reverse('projets:modifier_attachement', args=[self.attachement.id]))

		self.assertEqual(response.status_code, 403)

	@override_settings(DEBUG=False)
	def test_refus_acces_affiche_la_modale_utilisateur(self):
		utilisateur = User.objects.create_user(username='sans-acces-modal', password='test-password')
		self.client.force_login(utilisateur)

		response = self.client.get(reverse('projets:modifier_attachement', args=[self.attachement.id]))

		self.assertEqual(response.status_code, 403)
		self.assertContains(response, 'Accès restreint', status_code=403)
		self.assertContains(response, 'Cette action n', status_code=403)

	def test_attachement_transmis_peut_revenir_en_brouillon(self):
		self.client.force_login(self.chef)
		LigneAttachement.objects.create(
			attachement=self.attachement,
			ligne_lot=self.ligne_bordereau,
			numero=self.ligne_bordereau.numero,
			designation=self.ligne_bordereau.designation,
			unite=self.ligne_bordereau.unite,
			quantite_initiale=self.ligne_bordereau.quantite,
			prix_unitaire=self.ligne_bordereau.prix_unitaire,
			quantite_realisee=Decimal('1'),
			quantite_cumulee=Decimal('1'),
		)

		response = self.client.post(
			reverse('projets:modifier_attachement', args=[self.attachement.id]),
			{
				'numero': self.attachement.numero,
				'date_etablissement': self.attachement.date_etablissement,
				'date_debut_periode': self.attachement.date_debut_periode,
				'date_fin_periode': self.attachement.date_fin_periode,
				'statut': 'BROUILLON',
				'observations': '',
				'lignes_attachement': '[{"id": %d, "quantite_realisee": 2}]' % self.ligne_bordereau.id,
			},
		)

		self.assertEqual(response.status_code, 302)
		self.attachement.refresh_from_db()
		self.assertEqual(self.attachement.statut, 'BROUILLON')
		self.assertEqual(self.validation.statut_validation, 'EN_ATTENTE')

	def test_attachement_refuse_peut_revenir_en_brouillon(self):
		self.attachement.statut = 'REFUSE'
		self.attachement.save(update_fields=['statut'])
		self.validation.statut_validation = 'REJETE'
		self.validation.motifs_rejet = 'Quantité à corriger'
		self.validation.save(update_fields=['statut_validation', 'motifs_rejet'])
		self.client.force_login(self.chef)

		response = self.client.post(
			reverse('projets:modifier_attachement', args=[self.attachement.id]),
			{
				'numero': self.attachement.numero,
				'date_etablissement': self.attachement.date_etablissement,
				'date_debut_periode': self.attachement.date_debut_periode,
				'date_fin_periode': self.attachement.date_fin_periode,
				'statut': 'BROUILLON',
				'observations': '',
				'lignes_attachement': '[]',
			},
		)

		self.assertEqual(response.status_code, 302)
		self.attachement.refresh_from_db()
		self.validation.refresh_from_db()
		self.assertEqual(self.attachement.statut, 'BROUILLON')
		self.assertEqual(self.validation.statut_validation, 'EN_ATTENTE')
		self.assertEqual(self.validation.motifs_rejet, '')

	def test_attachement_ne_peut_pas_etre_valide_depuis_le_formulaire(self):
		self.client.force_login(self.chef)

		response = self.client.post(
			reverse('projets:modifier_attachement', args=[self.attachement.id]),
			{
				'numero': self.attachement.numero,
				'date_etablissement': self.attachement.date_etablissement,
				'date_debut_periode': self.attachement.date_debut_periode,
				'date_fin_periode': self.attachement.date_fin_periode,
				'statut': 'VALIDE',
				'observations': '',
				'lignes_attachement': '[]',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.attachement.refresh_from_db()
		self.assertEqual(self.attachement.statut, 'TRANSMIS')
		self.assertContains(response, 'Le statut Validé est attribué uniquement par le processus de validation.')

	def test_validation_d_un_autre_attachement_est_refusee(self):
		autre_attachement = Attachement.objects.create(
			projet=self.projet,
			numero='ATT-002',
			date_etablissement=date.today(),
			date_debut_periode=date.today(),
			date_fin_periode=date.today() + timedelta(days=30),
			statut='TRANSMIS',
		)
		autre_validation = ProcessValidation.objects.create(
			attachement=autre_attachement,
			type_validation='TECHNIQUE',
			ordre_validation=1,
			est_obligatoire=True,
			demandeur_validation=self.chef,
			statut_validation='EN_ATTENTE',
		)
		self.client.force_login(self.chef)

		response = self.client.post(
			reverse('projets:validation_attachement', args=[self.attachement.id]),
			{'validation_id': autre_validation.id, 'action_type': 'valider'},
		)

		self.assertEqual(response.status_code, 404)
		autre_validation.refresh_from_db()
		self.assertEqual(autre_validation.statut_validation, 'EN_ATTENTE')

	def test_json_invalide_ne_supprime_pas_les_lignes_existantes(self):
		LigneAttachement.objects.create(
			attachement=self.attachement,
			ligne_lot=self.ligne_bordereau,
			numero=self.ligne_bordereau.numero,
			designation=self.ligne_bordereau.designation,
			unite=self.ligne_bordereau.unite,
			quantite_initiale=self.ligne_bordereau.quantite,
			prix_unitaire=self.ligne_bordereau.prix_unitaire,
			quantite_realisee='2',
		)

		with self.assertRaises(DonneesAttachementInvalides):
			enregistrer_lignes_attachement(self.attachement, '{invalide')

		self.assertEqual(self.attachement.lignes_attachement.count(), 1)

	def test_ligne_d_un_autre_projet_est_refusee(self):
		autre_projet = Projet.objects.create(
			nom='Autre projet', objet='Test', numero='VAL-002', maitre_ouvrage='MOA', localisation='Rabat'
		)
		autre_lot = LotProjet.objects.create(projet=autre_projet, nom='Autre lot')
		autre_ligne = LigneBordereau.objects.create(
			lot=autre_lot, numero='1.1', designation='Ligne externe', unite='u', quantite=Decimal('1'), prix_unitaire=Decimal('1')
		)

		with self.assertRaises(DonneesAttachementInvalides):
			enregistrer_lignes_attachement(
				self.attachement,
				json.dumps([{'id': autre_ligne.id, 'quantite_realisee': 1}]),
			)

		self.assertEqual(self.attachement.lignes_attachement.count(), 0)

	def test_service_remplace_les_lignes_valides(self):
		enregistrer_lignes_attachement(
			self.attachement,
			json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': 3.5}]),
		)

		ligne = self.attachement.lignes_attachement.get()
		self.assertEqual(ligne.ligne_lot, self.ligne_bordereau)
		self.assertEqual(ligne.quantite_realisee, 3.5)

	def test_ligne_sans_designation_est_ignoree(self):
		ligne_sans_designation = LigneBordereau.objects.create(
			lot=self.lot,
			numero='',
			designation='',
			unite='',
			quantite=Decimal('0'),
			prix_unitaire=Decimal('0'),
		)

		enregistrer_lignes_attachement(
			self.attachement,
			json.dumps([
				{'id': ligne_sans_designation.id, 'quantite_realisee': 0},
				{'id': self.ligne_bordereau.id, 'quantite_realisee': 3.5},
			]),
		)

		self.assertFalse(
			self.attachement.lignes_attachement.filter(ligne_lot=ligne_sans_designation).exists()
		)
		self.assertTrue(
			self.attachement.lignes_attachement.filter(ligne_lot=self.ligne_bordereau).exists()
		)

	def test_derniere_etape_technique_validee_valide_le_processus_technique(self):
		premiere_etape = EtapeValidation.objects.create(
			processValidation=self.validation, nom='Contrôle terrain', ordre=1
		)
		derniere_etape = EtapeValidation.objects.create(
			processValidation=self.validation, nom='Contrôle métrés', ordre=2
		)

		premiere_etape.valider(self.chef, 'Conforme')
		self.validation.refresh_from_db()
		self.assertEqual(self.validation.statut_validation, 'EN_ATTENTE')

		derniere_etape.valider(self.chef, 'Conforme')
		self.validation.refresh_from_db()
		self.assertEqual(self.validation.statut_validation, 'VALIDE')

	def test_etape_technique_optionnelle_passee_valide_le_processus(self):
		etape = EtapeValidation.objects.create(
			processValidation=self.validation,
			nom='Pièce complémentaire',
			ordre=1,
			obligatoire=False,
		)
		self.client.force_login(self.chef)

		response = self.client.post(reverse('projets:passer_etape', args=[etape.id]))

		self.assertEqual(response.status_code, 302)
		self.validation.refresh_from_db()
		self.assertEqual(self.validation.statut_validation, 'VALIDE')

	def test_suppression_derniere_etape_non_validee_valide_le_processus_technique(self):
		etape_validee = EtapeValidation.objects.create(
			processValidation=self.validation, nom='Contrôle terminé', ordre=1
		)
		etape_a_supprimer = EtapeValidation.objects.create(
			processValidation=self.validation, nom='Contrôle retiré', ordre=2
		)
		etape_validee.valider(self.chef, 'Conforme')
		self.client.force_login(self.chef)

		response = self.client.post(reverse('projets:supprimer_etape', args=[etape_a_supprimer.id]))

		self.assertEqual(response.status_code, 302)
		self.assertFalse(EtapeValidation.objects.filter(id=etape_a_supprimer.id).exists())
		self.validation.refresh_from_db()
		self.assertEqual(self.validation.statut_validation, 'VALIDE')

	def test_suppression_attachement_supprime_les_fichiers_de_validation(self):
		self.attachement.fichier = SimpleUploadedFile('attachement.pdf', b'attachement')
		self.attachement.save()
		self.validation.fichier = SimpleUploadedFile('validation.pdf', b'validation')
		self.validation.save()
		etape = EtapeValidation.objects.create(
			processValidation=self.validation,
			nom='Pièce technique',
			ordre=1,
			fichier=SimpleUploadedFile('etape.pdf', b'etape'),
		)
		fichiers = [
			self.attachement.fichier.name,
			self.validation.fichier.name,
			etape.fichier.name,
		]
		self.assertTrue(all(default_storage.exists(fichier) for fichier in fichiers))

		self.attachement.delete()

		self.assertTrue(all(not default_storage.exists(fichier) for fichier in fichiers))


class LotProjetTauxTvaTests(TestCase):
	def setUp(self):
		self.projet = Projet.objects.create(
			nom='Projet TVA', objet='Test TVA', numero='TVA-001',
			maitre_ouvrage='MOA', localisation='Rabat',
		)

	def test_taux_tva_du_lot_est_prioritaire(self):
		lot = LotProjet.objects.create(projet=self.projet, nom='Lot A', taux_tva=Decimal('14.00'))
		self.assertEqual(lot.taux_tva_applicable, Decimal('14.00'))

	def test_lot_hors_tva_avec_taux_zero(self):
		lot = LotProjet.objects.create(projet=self.projet, nom='Lot B', taux_tva=Decimal('0.00'))
		self.assertEqual(lot.taux_tva_applicable, Decimal('0.00'))
		self.assertEqual(lot.montant_tva, Decimal('0.00'))

	def test_repli_sur_le_taux_du_projet_si_lot_non_renseigne(self):
		self.projet.taux_tva = Decimal('10.00')
		self.projet.save()
		lot = LotProjet.objects.create(projet=self.projet, nom='Lot C', taux_tva=None)
		self.assertEqual(lot.taux_tva_applicable, Decimal('10.00'))

	def test_repli_final_sur_20_pourcent_si_rien_de_renseigne(self):
		lot = LotProjet.objects.create(projet=self.projet, nom='Lot D', taux_tva=None)
		self.assertIsNone(self.projet.taux_tva)
		self.assertEqual(lot.taux_tva_applicable, Decimal('20.00'))

	def test_export_excel_additionne_le_ttc_par_taux_de_lot(self):
		lot_standard = LotProjet.objects.create(projet=self.projet, nom='Lot standard', taux_tva=Decimal('20.00'))
		LigneBordereau.objects.create(
			lot=lot_standard, numero='1.1', designation='Ligne standard', unite='u',
			quantite=Decimal('10'), prix_unitaire=Decimal('100'),
		)
		lot_hors_tva = LotProjet.objects.create(projet=self.projet, nom='Lot hors TVA', taux_tva=Decimal('0.00'))
		LigneBordereau.objects.create(
			lot=lot_hors_tva, numero='1.1', designation='Ligne hors TVA', unite='u',
			quantite=Decimal('10'), prix_unitaire=Decimal('100'),
		)

		lots = LotProjet.objects.filter(projet=self.projet)
		exporter = ExcelExporter(self.projet, lots)
		ws = exporter.create_summary_sheet()

		montant_total_ttc = next(
			row[1].value for row in ws.iter_rows(min_row=4) if row[0].value == 'Montant total TTC'
		)
		self.assertEqual(montant_total_ttc, 2200.0)


class RolesPointeurChefChantierTests(TestCase):
	def setUp(self):
		self.superuser = User.objects.create_superuser(username='admin-role', password='test-password')
		self.projet = Projet.objects.create(
			nom='Projet Chantier', objet='Test roles', numero='ROLE-001',
			maitre_ouvrage='MOA', localisation='Rabat',
		)

		self.pointeur = User.objects.create_user(username='pointeur', password='test-password')
		self.pointeur.profile.role = 'POINTEUR'
		self.pointeur.profile.save()
		self.projet.users.add(self.pointeur)

		self.chef_chantier = User.objects.create_user(username='chef-chantier', password='test-password')
		self.chef_chantier.profile.role = 'CHEF_CHANTIER'
		self.chef_chantier.profile.save()
		self.projet.users.add(self.chef_chantier)

	def test_helpers_de_role(self):
		self.assertTrue(est_pointeur(self.pointeur))
		self.assertFalse(est_chef_chantier(self.pointeur))
		self.assertTrue(est_chef_chantier(self.chef_chantier))
		self.assertFalse(est_pointeur(self.chef_chantier))

	def test_pointeur_ne_peut_pas_acceder_au_tableau_de_bord(self):
		self.client.force_login(self.pointeur)
		response = self.client.get(reverse('projets:dashboard', args=[self.projet.id]))
		self.assertEqual(response.status_code, 403)

	def test_chef_de_chantier_peut_acceder_au_tableau_de_bord(self):
		self.client.force_login(self.chef_chantier)
		response = self.client.get(reverse('projets:dashboard', args=[self.projet.id]))
		self.assertEqual(response.status_code, 200)

	def test_pointeur_peut_lister_les_rapports_journaliers(self):
		self.client.force_login(self.pointeur)
		response = self.client.get(reverse('projets:rapports_journaliers', args=[self.projet.id]))
		self.assertEqual(response.status_code, 200)

	def test_lots_et_situations_reserves_au_chef_de_projet(self):
		self.client.force_login(self.chef_chantier)
		response_lots = self.client.get(reverse('projets:lots_projet', args=[self.projet.id]))
		response_situations = self.client.get(reverse('projets:situations_mensuelles', args=[self.projet.id]))
		self.assertEqual(response_lots.status_code, 403)
		self.assertEqual(response_situations.status_code, 403)


class PersonnelMaterielBaseDonneesTests(TestCase):
	def setUp(self):
		self.superuser = User.objects.create_superuser(username='admin-ressources', password='test-password')

	def test_ajout_personnel_par_superuser(self):
		self.client.force_login(self.superuser)
		response = self.client.post(reverse('projets:ajouter_personnel'), {
			'nom': 'Karim Alaoui', 'fonction': 'Maçon', 'telephone': '0600000000', 'actif': 'on',
		})
		self.assertEqual(response.status_code, 302)
		self.assertTrue(Personnel.objects.filter(nom='Karim Alaoui').exists())

	def test_ajout_materiel_par_superuser(self):
		self.client.force_login(self.superuser)
		response = self.client.post(reverse('projets:ajouter_materiel'), {
			'designation': 'Pelle hydraulique', 'type_materiel': 'Engin de terrassement',
			'immatriculation': 'EH-123', 'actif': 'on',
		})
		self.assertEqual(response.status_code, 302)
		self.assertTrue(Materiel.objects.filter(designation='Pelle hydraulique').exists())

	def test_liste_personnel_et_materiel_accessibles_depuis_configuration(self):
		self.client.force_login(self.superuser)
		response_personnel = self.client.get(reverse('projets:partial_personnel'))
		response_materiel = self.client.get(reverse('projets:partial_materiel'))
		self.assertEqual(response_personnel.status_code, 200)
		self.assertEqual(response_materiel.status_code, 200)

	def test_tarif_personnel_est_transmis_au_modal_de_modification(self):
		personnel = Personnel.objects.create(nom='Karim Alaoui', tarif=Decimal('125.50'))
		self.client.force_login(self.superuser)

		response = self.client.get(reverse('projets:partial_personnel'))

		self.assertContains(response, 'data-tarif="125,50"')


class StorageDocumentFlowsTests(TestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls._media_root = tempfile.mkdtemp(prefix='goprojet-test-media-')
		post_save.disconnect(gerer_notifications_projet, sender=Projet)

	@classmethod
	def tearDownClass(cls):
		post_save.connect(gerer_notifications_projet, sender=Projet)
		shutil.rmtree(cls._media_root, ignore_errors=True)
		super().tearDownClass()

	def setUp(self):
		self.settings_ctx = override_settings(MEDIA_ROOT=self._media_root)
		self.settings_ctx.enable()

		self.user = User.objects.create_user(
			username='doc-user', password='test-password'
		)
		self.user.profile.role = 'GERANT'
		self.user.profile.save()
		self.client.login(username='doc-user', password='test-password')

		self.projet = Projet.objects.create(
			nom='Projet Stockage',
			objet='Validation stockage',
			numero='STK-001',
			maitre_ouvrage='MOA',
			localisation='Rabat',
		)
		self.projet.users.add(self.user)

	def tearDown(self):
		self.settings_ctx.disable()

	def test_suivi_travaux_refuse_pour_un_dossier_services(self):
		dossier = Dossier.objects.create(
			nom='Dossier Services Suivi',
			gerant=self.user,
			activite=Dossier.Activite.SERVICES,
		)
		projet = Projet.objects.create(
			nom='Projet Services', objet='Objet', numero='S-1',
			maitre_ouvrage='MOA', localisation='Lieu', dossier=dossier,
		)

		rapport = RapportJournalier(projet=projet, date=date.today())
		with self.assertRaises(ValidationError):
			rapport.full_clean()

	def test_rapport_et_situation_calculent_les_totaux(self):
		rapport = RapportJournalier.objects.create(
			projet=self.projet, date=date.today(), meteo='Ensoleillé',
		)
		DepenseRapportJournalier.objects.create(
			rapport=rapport, categorie='PERSONNEL', designation='Équipe', prix_unitaire=100,
		)
		DepenseRapportJournalier.objects.create(
			rapport=rapport, categorie='TRANSPORT', designation='Camion', prix_unitaire=50,
		)
		self.assertEqual(rapport.total_depenses, 150)

		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=8, chiffre_affaires=500,
		)
		DepenseSituationMensuelle.objects.create(
			situation=situation, categorie='FOURNITURE', designation='Acier', montant=200,
		)
		stock = StockSituationMensuelle.objects.create(
			situation=situation, designation='Ciment', unite='sac',
			quantite=10, prix_unitaire=12,
		)
		self.assertEqual(situation.total_depenses, 200)
		self.assertEqual(stock.valeur, 120)
		self.assertEqual(situation.total_stock, 120)

	def test_modification_rapport_remplace_le_document(self):
		dossier = Dossier.objects.create(
			nom='Dossier Travaux Rapports', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		rapport = RapportJournalier.objects.create(
			projet=self.projet, date=date.today(),
			document=SimpleUploadedFile('ancien.pdf', b'ancien'),
			original_filename='ancien.pdf',
		)

		get_response = self.client.get(
			reverse('projets:modifier_rapport_journalier', args=[self.projet.id, rapport.id])
		)
		self.assertEqual(get_response.status_code, 200)
		self.assertContains(get_response, 'supprimer-document')
		self.assertNotContains(get_response, 'supprimer_rapport_document')

		post_response = self.client.post(
			reverse('projets:modifier_rapport_journalier', args=[self.projet.id, rapport.id]),
			{
				'date': date.today().isoformat(),
				'document': SimpleUploadedFile('nouveau.pdf', b'nouveau'),
				'depenses-TOTAL_FORMS': '0',
				'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0',
				'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '0',
				'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0',
				'stocks-MAX_NUM_FORMS': '1000',
			},
		)
		self.assertRedirects(
			post_response,
			reverse('projets:suivi_execution', args=[self.projet.id]),
		)
		rapport.refresh_from_db()
		self.assertEqual(rapport.original_filename, 'nouveau.pdf')
		self.assertTrue(rapport.document.name.endswith('nouveau.pdf'))

	def test_creation_rapport_enregistre_le_document(self):
		dossier = Dossier.objects.create(
			nom='Dossier Travaux Upload', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		response = self.client.post(
			reverse('projets:ajouter_rapport_journalier', args=[self.projet.id]),
			{
				'date': date.today().isoformat(),
				'document': SimpleUploadedFile('rapport.pdf', b'contenu'),
				'depenses-TOTAL_FORMS': '0',
				'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0',
				'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '0',
				'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0',
				'stocks-MAX_NUM_FORMS': '1000',
			},
		)
		self.assertRedirects(
			response,
			reverse('projets:suivi_execution', args=[self.projet.id]),
		)
		rapport = RapportJournalier.objects.get(projet=self.projet)
		self.assertEqual(rapport.original_filename, 'rapport.pdf')
		self.assertTrue(rapport.document.name.endswith('rapport.pdf'))

	def test_suppression_ne_supprime_pas_un_fichier_partage(self):
		fichier = SimpleUploadedFile('partage.pdf', b'document partage')
		premier = DocumentAdministratif.objects.create(
			projet=self.projet, fichier=fichier, type_document='Rapport',
		)
		second_projet = Projet.objects.create(
			nom='Projet Partage', objet='Objet', numero='STK-002',
			maitre_ouvrage='MOA', localisation='Rabat',
		)
		second = DocumentAdministratif(
			projet=second_projet, type_document='Rapport',
		)
		second.fichier.name = premier.fichier.name
		second.save()

		fichier_nom = premier.fichier.name
		premier.delete()

		self.assertTrue(default_storage.exists(fichier_nom))
		second.delete()
		self.assertFalse(default_storage.exists(fichier_nom))

	def test_suppression_document_rapport(self):
		dossier = Dossier.objects.create(
			nom='Dossier Travaux Suppression', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		rapport = RapportJournalier.objects.create(
			projet=self.projet, date=date.today(),
			document=SimpleUploadedFile('a-supprimer.pdf', b'ancien'),
			original_filename='a-supprimer.pdf',
		)
		response = self.client.post(
			reverse(
				'projets:supprimer_document_rapport_journalier',
				args=[self.projet.id, rapport.id],
			)
		)
		self.assertRedirects(
			response,
			reverse(
				'projets:modifier_rapport_journalier',
				args=[self.projet.id, rapport.id],
			),
		)
		rapport.refresh_from_db()
		self.assertFalse(rapport.document)
		self.assertEqual(rapport.original_filename, '')

	def test_suppression_rapport_supprime_son_document(self):
		dossier = Dossier.objects.create(
			nom='Dossier Travaux Rapport Suppression', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		rapport = RapportJournalier.objects.create(
			projet=self.projet, date=date.today(),
			document=SimpleUploadedFile('rapport-a-supprimer.pdf', b'ancien'),
			original_filename='rapport-a-supprimer.pdf',
		)
		nom_document = rapport.document.name
		self.assertTrue(rapport.document.storage.exists(nom_document))

		response = self.client.post(
			reverse(
				'projets:supprimer_rapport_journalier',
				args=[self.projet.id, rapport.id],
			)
		)
		self.assertRedirects(
			response,
			reverse('projets:suivi_execution', args=[self.projet.id]),
		)
		self.assertFalse(RapportJournalier.objects.filter(pk=rapport.pk).exists())
		self.assertFalse(rapport.document.storage.exists(nom_document))

	def test_creation_rapport_refuse_date_deja_utilisee(self):
		dossier = Dossier.objects.create(
			nom='Dossier Travaux Doublon', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		RapportJournalier.objects.create(projet=self.projet, date=date.today())
		response = self.client.post(
			reverse('projets:ajouter_rapport_journalier', args=[self.projet.id]),
			{
				'date': date.today().isoformat(),
				'depenses-TOTAL_FORMS': '0',
				'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0',
				'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '0',
				'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0',
				'stocks-MAX_NUM_FORMS': '1000',
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'existe déjà')
		self.assertEqual(
			RapportJournalier.objects.filter(projet=self.projet).count(), 1
		)
		self.assertTrue(
			any('existe déjà' in str(message) for message in response.wsgi_request._messages)
		)

	def test_dashboard_ouvre_la_liste_des_rapports_journaliers(self):
		dossier = Dossier.objects.create(
			nom='Dossier Travaux Dashboard', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		RapportJournalier.objects.create(projet=self.projet, date=date.today())

		dashboard_response = self.client.get(
			reverse('projets:dashboard', args=[self.projet.id])
		)
		self.assertEqual(dashboard_response.status_code, 200)
		self.assertContains(dashboard_response, 'Rapports journaliers')
		self.assertContains(
			dashboard_response,
			reverse('projets:rapports_journaliers', args=[self.projet.id]),
		)

		liste_response = self.client.get(
			reverse('projets:rapports_journaliers', args=[self.projet.id])
		)
		self.assertEqual(liste_response.status_code, 200)
		self.assertContains(liste_response, date.today().strftime('%d/%m/%Y'))

	def test_situation_mensuelle_notifie_et_gere_son_document(self):
		dossier = Dossier.objects.create(
			nom='Dossier Situation Notifications', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		utilisateur_dossier = User.objects.create_user(
			username='situation-user', password='test-password'
		)
		dossier.utilisateurs.add(utilisateur_dossier)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])

		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=8,
		)
		document = DocumentSituationMensuelle.objects.create(
			situation=situation,
			fichier=SimpleUploadedFile('situation.pdf', b'contenu'),
			original_filename='situation.pdf',
		)
		self.assertEqual(
			Notification.objects.filter(
				objet_id=situation.id,
				type_notification='NOUVELLE_SITUATION_MENSUELLE',
			).count(),
			2,
		)
		nom_document = document.fichier.name
		self.assertTrue(document.fichier.storage.exists(nom_document))

		situation.delete()
		self.assertFalse(document.fichier.storage.exists(nom_document))

	def test_situation_accepte_plusieurs_depenses_et_stocks(self):
		dossier = Dossier.objects.create(
			nom='Dossier Situation Lignes', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		response = self.client.post(
			reverse('projets:ajouter_situation_mensuelle', args=[self.projet.id]),
			{
				'annee': 2026, 'mois': 9, 'chiffre_affaires': '1250.00',
				'depenses-TOTAL_FORMS': '2', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'depenses-0-categorie': 'PERSONNEL',
				'depenses-0-designation': 'Équipe A', 'depenses-0-montant': '100.00',
				'depenses-1-categorie': 'PERSONNEL',
				'depenses-1-designation': 'Équipe B', 'depenses-1-montant': '150.00',
				'stocks-TOTAL_FORMS': '2', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'stocks-0-designation': 'Ciment', 'stocks-0-unite': 'sac',
				'stocks-0-quantite': '10', 'stocks-0-prix_unitaire': '50.00',
				'stocks-1-designation': 'Acier', 'stocks-1-unite': 'kg',
				'stocks-1-quantite': '20', 'stocks-1-prix_unitaire': '12.50',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)
		self.assertRedirects(
			response,
			reverse('projets:situations_mensuelles', args=[self.projet.id]),
		)
		situation = SituationMensuelle.objects.get(projet=self.projet, mois=9)
		self.assertEqual(situation.depenses.count(), 2)
		self.assertEqual(situation.stocks.count(), 2)
		self.assertEqual(situation.total_depenses, 250)
		self.assertEqual(situation.total_stock, 750)

	def test_situation_refuse_document_duplique_par_contenu(self):
		dossier = Dossier.objects.create(
			nom='Dossier Situation Doublon Document', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=11,
		)
		DocumentSituationMensuelle.objects.create(
			situation=situation,
			fichier=SimpleUploadedFile('premier.pdf', b'meme contenu'),
		)
		formset = DocumentSituationMensuelleFormSet(
			{
				'documents-TOTAL_FORMS': '1',
				'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0',
				'documents-MAX_NUM_FORMS': '1000',
			},
			{'documents-0-fichier': SimpleUploadedFile('autre-nom.pdf', b'meme contenu')},
			instance=situation,
		)
		self.assertFalse(formset.is_valid())
		self.assertIn('existe déjà', str(formset.non_form_errors()))

	def test_creation_rapport_notifie_les_utilisateurs_concernes(self):
		dossier = Dossier.objects.create(
			nom='Dossier Rapport Notifications', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		utilisateur_dossier = User.objects.create_user(
			username='rapport-user', password='test-password'
		)
		dossier.utilisateurs.add(utilisateur_dossier)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])

		rapport = RapportJournalier.objects.create(
			projet=self.projet, date=date.today(),
		)
		self.assertEqual(
			Notification.objects.filter(
				objet_id=rapport.id,
				type_notification='NOUVEAU_RAPPORT_JOURNALIER',
			).count(),
			2,
		)

	def test_document_administratif_upload_download_delete(self):
		fichier = SimpleUploadedFile(
			'document-test.pdf', b'%PDF-test-content', content_type='application/pdf'
		)
		resp = self.client.post(
			reverse('projets:ajouter_document', args=[self.projet.id]),
			{
				'projet': self.projet.id,
				'type_document': 'Rapport',
				'date_remise': date.today().isoformat(),
				'fichier': fichier,
			},
		)
		self.assertEqual(resp.status_code, 302)

		doc = DocumentAdministratif.objects.get(projet=self.projet)
		self.assertTrue(doc.fichier.name)
		self.assertEqual(doc.original_filename, 'document-test.pdf')
		stored_file_path = doc.fichier.path
		self.assertTrue(os.path.exists(stored_file_path))

		download_resp = self.client.get(
			reverse('projets:telecharger_document', args=[doc.id])
		)
		self.assertEqual(download_resp.status_code, 302)
		self.assertIn('documents_administratifs', download_resp['Location'])

		suppr_resp = self.client.post(
			reverse('projets:supprimer_document', args=[self.projet.id, doc.id])
		)
		self.assertEqual(suppr_resp.status_code, 302)
		self.assertFalse(DocumentAdministratif.objects.filter(id=doc.id).exists())
		self.assertFalse(os.path.exists(stored_file_path))

	def test_fichier_suivi_upload_and_download(self):
		suivi = SuiviExecution.objects.create(
			projet=self.projet,
			titre='Suivi Test',
			type_suivi='reunion',
			commentaire='RAS',
		)
		fichier = SimpleUploadedFile(
			'compte-rendu.txt', b'compte rendu', content_type='text/plain'
		)

		resp = self.client.post(
			reverse('projets:ajouter_fichier_suivi', args=[self.projet.id, suivi.id]),
			{
				'fichiers': [fichier],
				'descriptions[]': ['note test'],
			},
		)
		self.assertEqual(resp.status_code, 302)

		fichier_suivi = FichierSuivi.objects.get(suivi=suivi)
		download_resp = self.client.get(
			reverse('projets:telecharger_fichier_suivi', args=[fichier_suivi.id])
		)
		self.assertEqual(download_resp.status_code, 302)
		self.assertIn('suivis_execution', download_resp['Location'])

	def test_secure_download_forbidden_for_non_member(self):
		outsider = User.objects.create_user(
			username='outsider', password='test-password'
		)
		fichier = SimpleUploadedFile(
			'document-securite.pdf', b'%PDF-sec', content_type='application/pdf'
		)
		doc = DocumentAdministratif.objects.create(
			projet=self.projet,
			type_document='Rapport',
			fichier=fichier,
			original_filename=fichier.name,
		)

		self.client.login(username='outsider', password='test-password')
		resp = self.client.get(
			reverse('projets:download_document', args=['DocumentAdministratif', doc.id])
		)
		self.assertEqual(resp.status_code, 403)

	def test_ordre_service_upload_and_secure_download(self):
		type_os, _ = TypeOrdreService.objects.get_or_create(
			code='AUTRE',
			defaults={
				'nom': 'Autre OS',
				'description': 'Test',
				'ordre_min': 1,
				'ordre_max': 99,
			},
		)
		fichier = SimpleUploadedFile(
			'os-note.pdf', b'%PDF-os', content_type='application/pdf'
		)

		resp = self.client.post(
			reverse('projets:ordres_service', args=[self.projet.id]),
			{
				'type_os': type_os.id,
				'reference': 'OS-TEST-01',
				'titre': 'Ordre de service test',
				'description': 'Description test',
				'date_publication': date.today().isoformat(),
				'date_limite': '',
				'date_effet': '',
				'duree_extension': 0,
				'montant_supplementaire': 0,
				'fichier': fichier,
				'statut': 'BROUILLON',
			},
		)
		self.assertEqual(resp.status_code, 302)

		ordre = OrdreService.objects.get(projet=self.projet, reference='OS-TEST-01')
		download_resp = self.client.get(
			reverse('projets:download_document', args=['OrdreService', ordre.id])
		)
		self.assertEqual(download_resp.status_code, 302)
		self.assertIn('ordres_services', download_resp['Location'])

	def test_lot_deletion_requires_post_and_removes_bordereau_lines(self):
		lot = LotProjet.objects.create(projet=self.projet, nom='Lot à supprimer')
		LigneBordereau.objects.create(
			lot=lot,
			designation='Ligne de test',
			quantite=1,
			prix_unitaire=100,
		)

		url = reverse('projets:supprimer_lot', args=[self.projet.id, lot.id])
		get_resp = self.client.get(url)
		self.assertEqual(get_resp.status_code, 302)
		self.assertTrue(LotProjet.objects.filter(id=lot.id).exists())

		post_resp = self.client.post(url)
		self.assertEqual(post_resp.status_code, 302)
		self.assertFalse(LotProjet.objects.filter(id=lot.id).exists())
		self.assertFalse(LigneBordereau.objects.filter(lot_id=lot.id).exists())
