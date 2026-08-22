from django.contrib.auth.models import User
from django.test import TestCase

from .decorators import projets_accessibles
from .forms import UtilisateurCreationForm
from .models import Dossier, Projet


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
