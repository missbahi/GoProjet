from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models.signals import post_save
from django.test import override_settings
from django.test import Client, RequestFactory, TestCase
from django.template import Context, Template
from django.urls import reverse
from django.utils.html import escape
from urllib.parse import urlencode, urlsplit, parse_qs

from datetime import date, timedelta
from decimal import Decimal
import json
import os
import re
import shutil
import tempfile

from .decorators import est_chef_chantier, est_pointeur, projets_accessibles
from .forms import DossierForm, SituationMensuelleForm, UtilisateurCreationForm, DocumentSituationMensuelleFormSet
from .views.reporting_views.views import _recettes_formset
from .services.attachement_service import DonneesAttachementInvalides, enregistrer_lignes_attachement
from .exporters import ExcelExporter
from .models import (
	Attachement,
	Atelier,
	AffectationRessource,
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
	StockRapportJournalier,
	Notification,
	SituationMensuelle,
	RecetteSituationMensuelle,
	DocumentSituationMensuelle,
	DepenseSituationMensuelle,
	StockSituationMensuelle,
	CategorieCharge,
)
from .signals.notifications import gerer_notifications_projet
from .utils.navigation import crumb, notification_origin_items, notification_origin_token


@override_settings(
	STORAGES={
		'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
		'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
	},
)
class NotificationBreadcrumbTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(
			username='breadcrumb-user', password='test-password'
		)
		self.client.force_login(self.user)
		self.url = reverse('projets:liste_notifications')
		self.origin_url = reverse('projets:liste_projets') + '?search=chantier&page=2'
		self.request = RequestFactory().get(self.origin_url)
		self.items = [
			crumb('Projets', 'projets:liste_projets'),
			crumb('Chantier', icon='fas fa-building'),
		]
		self.token = notification_origin_token(self.items, self.request)

	def test_breadcrumb_exports_origin_and_does_not_mutate_items(self):
		html = Template('{% load navigation %}{% breadcrumb %}').render(Context({
			'request': self.request, 'breadcrumb_items': self.items,
		}))
		self.assertIn('data-notification-origin=', html)
		items = notification_origin_items(self.token)
		self.assertEqual(items[-1]['url'], self.origin_url)
		self.assertIsNone(self.items[-1]['url'])
		self.assertEqual(items[-1]['icon'], 'fas fa-building')

	def test_explicit_breadcrumb_items_export_origin(self):
		html = Template('{% load navigation %}{% breadcrumb custom_items %}').render(Context({
			'request': self.request, 'custom_items': self.items,
		}))
		match = re.search(r'data-notification-origin="([^"]+)"', html)
		self.assertIsNotNone(match)
		self.assertEqual(
			notification_origin_items(match.group(1)),
			notification_origin_items(self.token),
		)

	def test_task_list_breadcrumb_is_flat_in_full_page_and_htmx(self):
		url = reverse('projets:liste_taches')
		for headers in ({}, {'HTTP_HX_REQUEST': 'true', 'HTTP_HX_TARGET': 'main-content'}):
			with self.subTest(headers=headers):
				response = self.client.get(url, **headers)
				self.assertEqual(response.status_code, 200)
				self.assertEqual(response.context['breadcrumb_items'], [
					crumb('Home', 'projets:home'), crumb('Taches'),
				])
				self.assertContains(response, 'aria-current="page" title="Taches"')
				match = re.search(r'data-notification-origin="([^"]+)"', response.content.decode())
				self.assertIsNotNone(match)
				origin = notification_origin_items(match.group(1))
				self.assertEqual(origin[-1]['url'], url)
				self.assertEqual(origin[-1]['label'], 'Taches')

	def test_notification_link_contains_signed_origin(self):
		url = Template('{% load navigation %}{% notification_url %}').render(Context({
			'request': self.request, 'breadcrumb_items': self.items,
		}))
		token = parse_qs(urlsplit(url).query)['breadcrumb'][0]
		self.assertEqual(notification_origin_items(token)[-1]['url'], self.origin_url)

	def test_no_origin_links_to_home(self):
		for headers in ({}, {'HTTP_HX_REQUEST': 'true'}):
			with self.subTest(headers=headers):
				response = self.client.get(self.url, **headers)
				self.assertEqual(response.status_code, 200)
				self.assertEqual(response.context['breadcrumb_items'], [
					crumb('Tableau de bord', 'projets:home'), crumb('Notifications'),
				])
				self.assertContains(response, f'href="{reverse("projets:home")}"')
				self.assertContains(response, f'hx-get="{reverse("projets:home")}"')
				self.assertContains(response, 'aria-current="page" title="Notifications"')
				self.assertContains(response, 'app-breadcrumb-current')
				self.assertContains(response, 'data-notification-origin=""')
		url = Template('{% load navigation %}{% notification_url %}').render(Context({
			'request': self.request,
		}))
		self.assertEqual(url, self.url)

	def test_empty_origin_from_home_is_accepted(self):
		request = RequestFactory().get(reverse('projets:home'))
		url = Template('{% load navigation %}{% notification_url %}').render(Context({
			'request': request,
		}))
		self.assertEqual(url, self.url)
		for headers in ({}, {'HTTP_HX_REQUEST': 'true', 'HTTP_HX_TARGET': 'main-content'}):
			with self.subTest(headers=headers):
				response = self.client.get(
					url, {'breadcrumb': ''}, HTTP_REFERER=request.build_absolute_uri(),
					**headers,
				)
				self.assertEqual(response.status_code, 200)
				self.assertEqual(response.context['notification_origin'], '')
				self.assertEqual(response.context['breadcrumb_items'], [
					crumb('Tableau de bord', 'projets:home'), crumb('Notifications'),
				])

	def test_origin_navigation_is_rendered_in_full_page_and_htmx(self):
		for headers in ({}, {'HTTP_HX_REQUEST': 'true', 'HTTP_HX_TARGET': 'main-content'}):
			with self.subTest(headers=headers):
				response = self.client.get(self.url, {'breadcrumb': self.token}, **headers)
				self.assertEqual(response.status_code, 200)
				self.assertEqual(
					response.context['breadcrumb_items'],
					[*notification_origin_items(self.token), crumb('Notifications')],
				)
				self.assertContains(response, f'href="{escape(self.origin_url)}"')
				self.assertContains(response, f'hx-get="{escape(self.origin_url)}"')
				self.assertContains(response, f'data-notification-origin="{escape(self.token)}"')
				self.assertContains(response, 'aria-current="page" title="Notifications"')

	def test_filters_and_pagination_keep_origin(self):
		Notification.objects.bulk_create([
			Notification(utilisateur=self.user, titre=f'Notification {i}', message='Test')
			for i in range(21)
		])
		response = self.client.get(self.url, {'breadcrumb': self.token})
		for filter_type in ('all', 'unread', 'read', 'today', 'priority'):
			query = urlencode({'filter': filter_type, 'breadcrumb': self.token})
			self.assertContains(response, f'href="?{escape(query)}"')
			self.assertContains(response, f'hx-get="?{escape(query)}"')
		query = urlencode({'page': 2, 'filter': 'all', 'breadcrumb': self.token})
		self.assertContains(response, f'href="?{escape(query)}"')
		response = self.client.get(
			self.url, {'breadcrumb': self.token, 'filter': 'unread', 'page': 2},
			HTTP_HX_REQUEST='true', HTTP_HX_TARGET='notifications-container',
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['notification_origin'], self.token)
		self.assertEqual(len(response.context['notifications']), 1)
		self.assertNotContains(response, 'app-breadcrumb')

	def test_reopening_notifications_does_not_duplicate_navigation(self):
		context = Context({
			'request': RequestFactory().get(self.url, {'breadcrumb': self.token}),
			'breadcrumb_items': [*notification_origin_items(self.token), crumb('Notifications')],
			'notification_origin': self.token,
		})
		url = Template('{% load navigation %}{% notification_url %}').render(context)
		self.assertEqual(parse_qs(urlsplit(url).query)['breadcrumb'], [self.token])

	def test_tampered_origin_is_rejected(self):
		response = self.client.get(self.url, {'breadcrumb': self.token + 'tampered'})
		self.assertEqual(response.status_code, 400)

	def test_notification_panel_counts_only_current_user_unread_notifications(self):
		other = User.objects.create_user(username='other-notification-user')
		Notification.objects.create(utilisateur=other, titre='Private notification', message='Test')
		Notification.objects.create(utilisateur=self.user, titre='Already read', message='Test', lue=True)
		Notification.objects.bulk_create([
			Notification(utilisateur=self.user, titre=f'Unread {i}', message='Test')
			for i in range(7)
		])
		response = self.client.get(reverse('projets:notification_panel'), {'breadcrumb': self.token})
		self.assertContains(response, 'Notifications non lues (7)')
		self.assertContains(response, 'class="notification-item', count=5)
		self.assertNotContains(response, 'Private notification')
		self.assertNotContains(response, 'Already read')
		self.assertContains(response, escape(urlencode({'breadcrumb': self.token})))

	def test_notification_panel_refreshes_after_read_unread_and_delete(self):
		notification = Notification.objects.create(
			utilisateur=self.user, titre='Notification to update', message='Test',
		)
		panel_url = reverse('projets:notification_panel')
		for action, expected in (
			('mark_notification_as_read', 0),
			('mark_notification_as_unread', 1),
			('delete_notification', 0),
		):
			response = self.client.post(reverse(f'projets:{action}', args=[notification.id]))
			self.assertEqual(response.status_code, 200)
			self.assertContains(self.client.get(panel_url), f'Notifications non lues ({expected})')
		self.assertNotContains(self.client.get(panel_url), 'data-notification-count')

	def test_topbar_panel_does_not_use_paginated_list_as_its_source(self):
		Notification.objects.bulk_create([
			Notification(utilisateur=self.user, titre=f'Unread {i}', message='Test')
			for i in range(21)
		])
		response = self.client.get(self.url, {'page': 2})
		self.assertContains(response, 'Notifications non lues (21)')
		self.assertContains(response, 'data-action-url=')

	def test_notification_panel_requires_login_and_get(self):
		panel_url = reverse('projets:notification_panel')
		self.assertEqual(self.client.post(panel_url).status_code, 405)
		self.client.logout()
		self.assertEqual(self.client.get(panel_url).status_code, 302)


@override_settings(
	STORAGES={
		'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
		'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
	},
)
class AtelierPlanningNavigationTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_superuser(
			username='planning-admin', password='test-password',
		)
		self.client.force_login(self.user)
		self.projet = Projet.objects.create(
			nom='Projet Planning', objet='Test', numero='PLAN-01',
			maitre_ouvrage='MOA', localisation='Lieu',
		)
		self.atelier = Atelier.objects.create(
			projet=self.projet, code='01', libelle='Terrassement',
		)
		self.materiel = Materiel.objects.create(designation='Pelle', actif=True)
		self.affectation = AffectationRessource.objects.create(
			atelier=self.atelier, materiel=self.materiel,
			date_debut=date(2026, 10, 1), date_fin=date(2026, 10, 20),
		)
		self.filters = {
			'atelier': self.atelier.id, 'debut': '2026-10-01', 'fin': '2026-11-15',
		}

	def test_home_chart_data_is_current_in_full_and_htmx_responses(self):
		for headers, progress in (({}, 35), ({'HTTP_HX_REQUEST': 'true'}, 65)):
			with self.subTest(headers=headers):
				Projet.objects.filter(pk=self.projet.pk).update(avancement=progress)
				response = self.client.get(reverse('projets:home'), **headers)
				self.assertEqual(response.status_code, 200)
				data = json.loads(response.context['chart_data_json'])
				self.assertEqual(data['projets'][0]['avancement'], progress)
				self.assertEqual(response.context['chart_data'], data)
				self.assertContains(response, '1 projets récents')
				self.assertContains(response, 'id="avancementChart"')
				if headers:
					self.assertNotContains(response, '<html')

	def test_planning_controls_and_print_link_in_full_and_htmx_pages(self):
		for headers in ({}, {'HTTP_HX_REQUEST': 'true'}):
			with self.subTest(headers=headers):
				response = self.client.get(
					reverse('projets:planning_ateliers', args=[self.projet.id]),
					self.filters, **headers,
				)
				self.assertEqual(response.status_code, 200)
				self.assertContains(response, 'data-context-action="add-affectation"')
				self.assertContains(response, 'data-context-action="edit-atelier"')
				self.assertContains(response, 'data-context-action="delete-atelier"')
				self.assertContains(response, 'data-context-action="edit-affectation"')
				self.assertContains(response, 'data-context-action="delete-affectation"')
				self.assertContains(response, f'data-toggle-atelier="{self.atelier.id}"')
				self.assertContains(response, f'id="atelier-{self.atelier.id}-children"')
				preview = reverse('projets:apercu_impression_planning', args=[self.projet.id])
				self.assertContains(response, f'href="{escape(preview + "?" + urlencode(self.filters))}"')
				self.assertContains(response, 'target="_blank"')
				self.assertContains(response, 'hx-boost="false"')
				if headers:
					self.assertNotContains(response, '<html')
				else:
					self.assertContains(response, 'projets/js/ateliers-planning.js')

	def test_print_preview_uses_selected_period_and_atelier(self):
		response = self.client.get(
			reverse('projets:apercu_impression_planning', args=[self.projet.id]),
			self.filters,
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.context['debut'], date(2026, 10, 1))
		self.assertEqual(response.context['fin'], date(2026, 11, 15))
		self.assertEqual(response.context['atelier_selectionne'], self.atelier.id)
		self.assertEqual(response.context['nb_materiels_total'], 1)
		self.assertContains(response, 'window.print()')

	def test_edit_affectation_from_planning_persists_dates_and_comment(self):
		response = self.client.post(
			reverse('projets:modifier_affectation', args=[self.affectation.id]),
			{'materiel': self.materiel.id, 'date_debut': '2026-10-02',
			 'date_fin': '2026-10-21', 'commentaire': 'Updated from planning'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(response.json()['success'])
		self.affectation.refresh_from_db()
		self.assertEqual(self.affectation.date_debut, date(2026, 10, 2))
		self.assertEqual(self.affectation.date_fin, date(2026, 10, 21))
		self.assertEqual(self.affectation.commentaire, 'Updated from planning')

	def test_invalid_dates_return_errors_without_saving(self):
		response = self.client.post(
			reverse('projets:modifier_affectation', args=[self.affectation.id]),
			{'materiel': self.materiel.id, 'date_debut': '2026-10-20', 'date_fin': '2026-10-01'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 400)
		self.assertIn('date_fin', response.json()['errors'])
		self.affectation.refresh_from_db()
		self.assertEqual(self.affectation.date_debut, date(2026, 10, 1))


@override_settings(
	STORAGES={
		'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
		'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
	},
)
class UserManagementModalTests(TestCase):
	def setUp(self):
		self.admin = User.objects.create(username='modal-admin', is_superuser=True, is_staff=True)
		self.target = User.objects.create(username='modal-user', email='old@example.com')
		self.client.force_login(self.admin)
		self.headers = {'HTTP_HX_REQUEST': 'true', 'HTTP_HX_TARGET': 'user-modal-content'}
		self.urls = [
			reverse('projets:ajouter_utilisateur'),
			reverse('projets:modifier_utilisateur', args=[self.target.id]),
			reverse('projets:gerer_projets_utilisateur', args=[self.target.id]),
		]

	def test_list_has_home_breadcrumb_and_only_one_empty_modal(self):
		for headers in ({}, {'HTTP_HX_REQUEST': 'true'}):
			with self.subTest(headers=headers):
				response = self.client.get(reverse('projets:liste_utilisateurs'), **headers)
				self.assertEqual(response.status_code, 200)
				self.assertEqual(response.context['breadcrumb_items'], [
					crumb('Home', 'projets:home'), crumb('Utilisateurs'),
				])
				self.assertContains(response, 'id="user-management-dialog"', count=1)
				self.assertContains(response, '<div id="user-modal-content"></div>', count=1)
				self.assertContains(response, 'hx-target="#user-modal-content"')
				self.assertNotContains(response, 'name="password1"')

	def test_each_form_loads_on_demand_and_keeps_classic_page(self):
		for url in self.urls:
			with self.subTest(url=url):
				modal = self.client.get(url, **self.headers)
				self.assertEqual(modal.status_code, 200)
				self.assertContains(modal, 'hx-target="#user-modal-content"')
				self.assertNotContains(modal, '<html')
				self.assertContains(modal, 'data-user-modal-close')
				classic = self.client.get(url)
				self.assertEqual(classic.status_code, 200)
				self.assertContains(classic, 'hx-target="#main-content"')
				self.assertNotContains(classic, 'data-user-modal-close')

	def test_creation_error_stays_in_modal(self):
		response = self.client.post(self.urls[0], {'username': ''}, **self.headers)
		self.assertEqual(response.status_code, 400)
		self.assertContains(response, 'hx-target="#user-modal-content"', status_code=400)
		self.assertNotIn('HX-Location', response)
		self.assertFalse(User.objects.exclude(pk__in=[self.admin.pk, self.target.pk]).exists())

	def test_create_success_closes_modal_without_redirect(self):
		response = self.client.post(self.urls[0], {
			'username': 'created-in-modal',
			'password1': 'A-valid-password-123!',
			'password2': 'A-valid-password-123!',
			'role': 'UTILISATEUR',
		}, **self.headers)
		self.assertEqual(response.status_code, 204)
		self.assertIn('userModalSaved', json.loads(response['HX-Trigger']))
		self.assertNotIn('HX-Location', response)
		self.assertTrue(User.objects.filter(username='created-in-modal').exists())

	def test_modify_password_errors_stay_in_modal(self):
		for password, confirmation in [('mismatch-123', 'different-123'), ('short', 'short')]:
			with self.subTest(password=password):
				response = self.client.post(self.urls[1], {
					'password': password, 'confirm_password': confirmation,
					'email': 'new@example.com',
				}, **self.headers)
				self.assertEqual(response.status_code, 400)
				self.assertContains(response, 'hx-target="#user-modal-content"', status_code=400)
				self.target.refresh_from_db()
				self.assertEqual(self.target.email, 'old@example.com')

	def test_modify_success_persists_changes(self):
		response = self.client.post(self.urls[1], {
			'email': 'new@example.com', 'first_name': 'Updated',
			'role': 'POINTEUR', 'is_active': 'on',
		}, **self.headers)
		self.assertEqual(response.status_code, 204)
		self.target.refresh_from_db()
		self.assertEqual(self.target.email, 'new@example.com')
		self.assertEqual(self.target.profile.role, 'POINTEUR')

	def test_oversized_avatar_returns_modal_validation_error(self):
		response = self.client.post(self.urls[1], {
			'role': 'UTILISATEUR',
			'avatar': SimpleUploadedFile('large.png', b'x' * (5 * 1024 * 1024 + 1)),
		}, **self.headers)
		self.assertEqual(response.status_code, 400)
		self.assertContains(response, '5 Mo', status_code=400)
		self.assertContains(response, 'hx-target="#user-modal-content"', status_code=400)

	def test_project_assignment_preserves_projects_outside_manager_scope(self):
		manager = User.objects.create(username='modal-manager')
		manager.profile.role = 'GERANT'
		manager.profile.save()
		owned = Dossier.objects.create(nom='Owned', gerant=manager)
		other = Dossier.objects.create(nom='Other', gerant=self.admin)
		self.target.dossiers.add(owned, other)
		projects = []
		for index, dossier in enumerate([owned, owned, other]):
			projects.append(Projet.objects.create(
				nom=f'Project {index}', numero=f'UM-{index}', objet='Test',
				maitre_ouvrage='Client', localisation='Lieu', dossier=dossier,
			))
		self.target.projets.set([projects[0], projects[2]])
		self.client.force_login(manager)
		response = self.client.get(self.urls[2], **self.headers)
		self.assertContains(response, f'value="{projects[0].id}"')
		self.assertNotContains(response, f'value="{projects[2].id}"')
		self.assertEqual(response.context['projets_utilisateur_ids'], {projects[0].id})
		response = self.client.post(self.urls[2], {
			'projets': [projects[1].id, projects[2].id],
		}, **self.headers)
		self.assertEqual(response.status_code, 204)
		self.assertEqual(set(self.target.projets.values_list('id', flat=True)), {
			projects[1].id, projects[2].id,
		})

	def test_modal_requests_do_not_bypass_access_permissions(self):
		self.client.force_login(self.target)
		for url in [reverse('projets:liste_utilisateurs'), *self.urls]:
			with self.subTest(url=url):
				self.assertEqual(self.client.get(url, **self.headers).status_code, 403)

	def test_manager_cannot_open_other_users_forms(self):
		manager = User.objects.create(username='restricted-manager')
		manager.profile.role = 'GERANT'
		manager.profile.save()
		self.client.force_login(manager)
		for url in self.urls[1:]:
			with self.subTest(url=url):
				self.assertEqual(self.client.get(url, **self.headers).status_code, 403)

	def test_edit_preserves_dossiers_outside_manager_scope(self):
		manager = User.objects.create(username='dossier-manager')
		manager.profile.role = 'GERANT'
		manager.profile.save()
		owned = Dossier.objects.create(nom='Editable', gerant=manager)
		other = Dossier.objects.create(nom='Uneditable', gerant=self.admin)
		self.target.dossiers.add(owned, other)
		self.client.force_login(manager)
		response = self.client.post(self.urls[1], {
			'role': 'STAFF', 'dossiers': [owned.id],
		}, **self.headers)
		self.assertEqual(response.status_code, 204)
		self.assertEqual(set(self.target.dossiers.values_list('id', flat=True)), {owned.id, other.id})

	def test_self_password_change_keeps_authenticated_session(self):
		response = self.client.post(
			reverse('projets:modifier_utilisateur', args=[self.admin.id]),
			{'password': 'New-password-123!', 'confirm_password': 'New-password-123!'},
			**self.headers,
		)
		self.assertEqual(response.status_code, 204)
		response = self.client.get(reverse('projets:liste_utilisateurs'), HTTP_HX_REQUEST='true')
		self.assertEqual(response.status_code, 200)
		self.admin.refresh_from_db()
		self.assertTrue(self.admin.check_password('New-password-123!'))

	def test_classic_htmx_success_keeps_existing_navigation(self):
		response = self.client.post(self.urls[1], {
			'role': 'UTILISATEUR', 'is_active': 'on',
		}, HTTP_HX_REQUEST='true', HTTP_HX_TARGET='main-content')
		self.assertEqual(response.status_code, 200)
		self.assertIn('HX-Location', response)
		self.assertNotIn('userModalSaved', json.loads(response['HX-Trigger']))

	def test_modal_submission_keeps_csrf_protection(self):
		client = Client(enforce_csrf_checks=True)
		client.force_login(self.admin)
		self.assertEqual(client.post(self.urls[1], {
			'role': 'UTILISATEUR',
		}, **self.headers).status_code, 403)
		response = client.get(self.urls[1], **self.headers)
		self.assertContains(response, 'csrfmiddlewaretoken')
		response = client.post(self.urls[1], {
			'role': 'UTILISATEUR', 'is_active': 'on',
		}, HTTP_X_CSRFTOKEN=client.cookies['csrftoken'].value, **self.headers)
		self.assertEqual(response.status_code, 204)


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

	def test_superuser_et_chef_projet_gerent_les_categories(self):
		self.client.force_login(self.superuser)
		response = self.client.post(
			reverse('projets:ajouter_categorie_charge'),
			{'code': 'DIVERS_TEST', 'nom': 'Divers test', 'ordre': 30, 'actif': 'on'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(CategorieCharge.objects.filter(code='DIVERS_TEST').exists())

		chef = User.objects.create_user(username='chef-categories', password='test-password')
		chef.profile.role = 'CHEF_PROJET'
		chef.profile.save()
		self.client.force_login(chef)
		categorie = CategorieCharge.objects.get(code='DIVERS_TEST')
		response = self.client.post(
			reverse('projets:modifier_categorie_charge', args=[categorie.id]),
			{'code': 'DIVERS_TEST', 'nom': 'Divers modifié', 'ordre': 2, 'actif': 'on'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)
		categorie.refresh_from_db()
		self.assertEqual(categorie.nom, 'Divers modifié')
		self.assertEqual(categorie.ordre, 2)

		chef.profile.role = 'Chef de projet'
		chef.profile.save(update_fields=['role'])
		response = self.client.post(
			reverse('projets:modifier_categorie_charge', args=[categorie.id]),
			{'code': 'DIVERS_TEST', 'nom': 'Divers renommé', 'ordre': 3, 'actif': 'on'},
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)
		self.assertEqual(response.status_code, 200)

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
class AttachementPrecedentTests(TestCase):
	def setUp(self):
		self.projet = Projet.objects.create(
			nom='Projet Attachements',
			objet='Sélection chronologique',
			numero='ATT-DATES-001',
			maitre_ouvrage='MOA',
			localisation='Rabat',
		)
		self.utilisateur = User.objects.create_superuser(
			username='admin-attachements', password='test-password'
		)

	def creer_attachement(self, numero, date_debut, date_fin):
		return Attachement.objects.create(
			projet=self.projet,
			numero=numero,
			date_etablissement=date_fin,
			date_debut_periode=date_debut,
			date_fin_periode=date_fin,
		)

	def test_modification_prend_la_date_fin_eligible_la_plus_proche(self):
		plus_proche = self.creer_attachement('ATT-002', date(2026, 2, 1), date(2026, 3, 31))
		self.creer_attachement('ATT-001', date(2026, 1, 1), date(2026, 1, 31))
		courant = self.creer_attachement('ATT-003', date(2026, 4, 1), date(2026, 4, 30))
		self.creer_attachement('ATT-004', date(2026, 5, 1), date(2026, 5, 31))

		self.assertEqual(courant.get_previous_attachement(), plus_proche)

	def test_nouvel_attachement_prend_la_plus_grande_date_fin(self):
		plus_recent = self.creer_attachement('ATT-002', date(2026, 2, 1), date(2026, 3, 31))
		self.creer_attachement('ATT-001', date(2026, 1, 1), date(2026, 1, 31))

		self.assertEqual(Attachement.get_latest_attachement(self.projet), plus_recent)

	def test_vue_ajout_charge_les_quantites_du_dernier_attachement(self):
		lot = LotProjet.objects.create(projet=self.projet, nom='Lot test')
		ligne = LigneBordereau.objects.create(
			lot=lot,
			numero='1.1',
			designation='Ligne test',
			unite='u',
			quantite=Decimal('20'),
			prix_unitaire=Decimal('100'),
		)
		plus_recent = self.creer_attachement('ATT-002', date(2026, 2, 1), date(2026, 3, 31))
		plus_ancien = self.creer_attachement('ATT-001', date(2026, 1, 1), date(2026, 1, 31))
		for attachement, quantite in ((plus_recent, Decimal('7')), (plus_ancien, Decimal('3'))):
			LigneAttachement.objects.create(
				attachement=attachement,
				ligne_lot=ligne,
				numero=ligne.numero,
				designation=ligne.designation,
				unite=ligne.unite,
				quantite_initiale=ligne.quantite,
				prix_unitaire=ligne.prix_unitaire,
				quantite_realisee=quantite,
			)
		self.client.force_login(self.utilisateur)

		response = self.client.get(reverse('projets:ajouter_attachement', args=[self.projet.id]))

		self.assertEqual(response.status_code, 200)
		donnees_lignes = json.loads(response.context['lignes'])
		donnees_ligne = next(item for item in donnees_lignes if item['id'] == ligne.id)
		self.assertEqual(donnees_ligne['quantite_deja_realisee'], 7.0)
		self.assertEqual(response.context['date_debut_periode'], plus_recent.date_fin_periode)


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


class SituationMensuelleFormTests(TestCase):
	def _form(self, date_debut='2026-02-15', date_fin='2026-02-15'):
		return SituationMensuelleForm(data={
			'periode': '2026-02', 'annee': '2026', 'mois': '2',
			'date_debut': date_debut, 'date_fin': date_fin,
		})

	def test_accepte_des_dates_egales_dans_le_mois(self):
		self.assertTrue(self._form().is_valid())

	def test_refuse_une_date_de_fin_anterieure(self):
		form = self._form(date_debut='2026-02-20', date_fin='2026-02-19')

		self.assertFalse(form.is_valid())
		self.assertIn(
			'La date de fin doit être postérieure ou égale à la date de début.',
			form.errors['date_fin'],
		)

	def test_refuse_les_dates_hors_du_mois_selectionne(self):
		cas = (
			('date_debut', '2026-01-31', '2026-02-15'),
			('date_fin', '2026-02-15', '2026-03-01'),
		)
		for champ, date_debut, date_fin in cas:
			with self.subTest(champ=champ):
				form = self._form(date_debut=date_debut, date_fin=date_fin)

				self.assertFalse(form.is_valid())
				libelle = 'début' if champ == 'date_debut' else 'fin'
				self.assertIn(
					'La date de %s doit appartenir au mois sélectionné.' % libelle,
					form.errors[champ],
				)


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
		self.settings_ctx = override_settings(
			MEDIA_ROOT=self._media_root,
			STORAGES={
				'default': {
					'BACKEND': 'django.core.files.storage.FileSystemStorage',
				},
				'staticfiles': {
					'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
				},
			},
		)
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
			situation=situation, categorie='FOURNITURE', designation='Acier', montant_base=200,
		)
		stock = StockSituationMensuelle.objects.create(
			situation=situation, designation='Ciment', unite='sac',
			quantite=10, prix_unitaire=12,
		)
		self.assertEqual(situation.total_depenses, 200)
		self.assertEqual(stock.valeur, 120)
		self.assertEqual(situation.total_stock, 120)

	def test_situation_totalise_les_cessions_des_depenses(self):
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=9, chiffre_affaires=500,
		)
		depense = DepenseSituationMensuelle.objects.create(
			situation=situation,
			categorie='FOURNITURE',
			designation='Acier',
			montant_base=100,
			cession_entrante=25,
			cession_sortante=-40,
		)

		self.assertEqual(depense.montant, Decimal('85.00'))
		self.assertEqual(situation.total_depenses, Decimal('85.00'))

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

	def test_creation_rapport_ignore_un_stock_nouvellement_supprime(self):
		dossier = Dossier.objects.create(
			nom='Dossier Rapport Stock Supprime', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])

		response = self.client.post(
			reverse('projets:ajouter_rapport_journalier', args=[self.projet.id]),
			{
				'date': date.today().isoformat(),
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '1', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'stocks-0-designation': '', 'stocks-0-unite': '',
				'stocks-0-quantite_entree': '', 'stocks-0-quantite_sortie': '',
				'stocks-0-stock_restant': '', 'stocks-0-DELETE': 'on',
			},
		)

		self.assertRedirects(
			response,
			reverse('projets:rapports_journaliers', args=[self.projet.id]),
		)
		rapport = RapportJournalier.objects.get(projet=self.projet)
		self.assertFalse(StockRapportJournalier.objects.filter(rapport=rapport).exists())

	def test_rapport_utilise_une_categorie_de_charge_configurable(self):
		dossier = Dossier.objects.create(
			nom='Dossier Rapport Categorie Configurable', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		categorie = CategorieCharge.objects.create(
			code='DIVERS', nom='Divers', ordre=20,
		)

		response = self.client.post(
			reverse('projets:ajouter_rapport_journalier', args=[self.projet.id]),
			{
				'date': date.today().isoformat(),
				'depenses-TOTAL_FORMS': '1', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'depenses-0-categorie': 'DIVERS',
				'depenses-0-categorie_charge': str(categorie.id),
				'depenses-0-designation': 'Frais divers', 'depenses-0-quantite': '1',
				'depenses-0-unite': 'forfait', 'depenses-0-prix_unitaire': '125.00',
				'depenses-0-observations': '',
				'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertRedirects(
			response,
			reverse('projets:rapports_journaliers', args=[self.projet.id]),
		)
		rapport = RapportJournalier.objects.get(projet=self.projet)
		depense = rapport.depenses.get()
		self.assertEqual(depense.categorie_charge_id, categorie.id)
		self.assertEqual(depense.categorie, 'DIVERS')
		detail = self.client.get(
			reverse('projets:detail_rapport_journalier', args=[self.projet.id, rapport.id]),
		)
		self.assertContains(detail, 'Divers')

	def test_modification_rapport_ignore_un_stock_nouvellement_supprime(self):
		dossier = Dossier.objects.create(
			nom='Dossier Modification Rapport Stock Supprime', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		rapport = RapportJournalier.objects.create(
			projet=self.projet, date=date.today(),
		)

		response = self.client.post(
			reverse('projets:modifier_rapport_journalier', args=[self.projet.id, rapport.id]),
			{
				'date': date.today().isoformat(),
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '1', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'stocks-0-designation': '', 'stocks-0-unite': '',
				'stocks-0-quantite_entree': '', 'stocks-0-quantite_sortie': '',
				'stocks-0-stock_restant': '', 'stocks-0-DELETE': 'on',
			},
		)

		self.assertRedirects(
			response,
			reverse('projets:rapports_journaliers', args=[self.projet.id]),
		)
		self.assertFalse(StockRapportJournalier.objects.filter(rapport=rapport).exists())

	def test_modification_rapport_supprime_un_stock_valide(self):
		dossier = Dossier.objects.create(
			nom='Dossier Suppression Stock Valide', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		rapport = RapportJournalier.objects.create(
			projet=self.projet, date=date.today(),
		)
		stock = StockRapportJournalier.objects.create(
			rapport=rapport, designation='Ciment', unite='sac',
			quantite_entree=10, quantite_sortie=2, stock_restant=8,
		)

		response = self.client.post(
			reverse('projets:modifier_rapport_journalier', args=[self.projet.id, rapport.id]),
			{
				'date': date.today().isoformat(),
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '1', 'stocks-INITIAL_FORMS': '1',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'stocks-0-id': str(stock.id), 'stocks-0-designation': stock.designation,
				'stocks-0-unite': stock.unite, 'stocks-0-quantite_entree': '10',
				'stocks-0-quantite_sortie': '2', 'stocks-0-stock_restant': '8',
				'stocks-0-DELETE': 'on',
			},
		)

		self.assertRedirects(
			response,
			reverse('projets:rapports_journaliers', args=[self.projet.id]),
		)
		self.assertFalse(StockRapportJournalier.objects.filter(pk=stock.id).exists())

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
		self.assertContains(response, 'Erreurs:')
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

	def test_situation_utilise_une_categorie_de_charge_configurable(self):
		dossier = Dossier.objects.create(
			nom='Dossier Situation Categorie Configurable', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		categorie = CategorieCharge.objects.create(
			code='FRAIS_GENERAUX', nom='Frais généraux', ordre=21,
		)

		response = self.client.post(
			reverse('projets:ajouter_situation_mensuelle', args=[self.projet.id]),
			{
				'periode': '2027-01', 'annee': '2027', 'mois': '1',
				'depenses-TOTAL_FORMS': '1', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'depenses-0-categorie': 'FRAIS_GENERAUX',
				'depenses-0-categorie_charge': str(categorie.id),
				'depenses-0-designation': 'Frais administratifs',
				'depenses-0-montant_base': '250.00',
				'depenses-0-cession_entrante': '0.00',
				'depenses-0-cession_sortante': '0.00',
				'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'recettes-TOTAL_FORMS': '0', 'recettes-INITIAL_FORMS': '0',
				'recettes-MIN_NUM_FORMS': '0', 'recettes-MAX_NUM_FORMS': '1000',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertRedirects(
			response,
			reverse('projets:situations_mensuelles', args=[self.projet.id]),
		)
		situation = SituationMensuelle.objects.get(projet=self.projet, mois=1)
		depense = situation.depenses.get()
		self.assertEqual(depense.categorie_charge_id, categorie.id)
		apercu = self.client.get(
			reverse('projets:apercu_situation_mensuelle', args=[self.projet.id, situation.id]),
		)
		self.assertContains(apercu, 'Frais généraux')

	def test_situation_ignore_un_stock_nouvellement_supprime(self):
		dossier = Dossier.objects.create(
			nom='Dossier Stock Supprime', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])

		response = self.client.post(
			reverse('projets:ajouter_situation_mensuelle', args=[self.projet.id]),
			{
				'periode': '2026-12', 'annee': '2026', 'mois': '12',
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '1', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'stocks-0-designation': '', 'stocks-0-unite': '',
				'stocks-0-quantite': '', 'stocks-0-prix_unitaire': '',
				'stocks-0-DELETE': 'on',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertRedirects(response, reverse('projets:situations_mensuelles', args=[self.projet.id]))
		self.assertFalse(StockSituationMensuelle.objects.filter(situation__projet=self.projet).exists())

	def test_ajout_situation_sans_mois_affiche_une_erreur(self):
		dossier = Dossier.objects.create(
			nom='Dossier Situation Periode Invalide', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])

		response = self.client.post(
			reverse('projets:ajouter_situation_mensuelle', args=[self.projet.id]),
			{
				'periode': '', 'annee': '', 'mois': '',
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Sélectionnez un mois')

	def test_situation_accepte_les_rubriques_materiel_avec_montants_vides(self):
		dossier = Dossier.objects.create(
			nom='Dossier Situation Materiel', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		rubriques = [
			'Pelles hydraulique sur chenilles', 'Pelles hydraulique sur pneus',
			'Niveleuses', 'Compacteurs', 'Tractopelles', 'Bulldozers', 'Dumpers',
			'Chargeuses', 'Brises roche hydrauliques', 'Godets', 'Fraiseuses',
			'Alimentateurs', 'Finisseurs', 'Chariots téléscopiques',
			'Chariots élévateurs', 'Chariots hydrauliques de perforation', 'Grues',
			'Machines de marquage', 'Sonnettes à battage', 'Autobétonnières',
			'Tracteurs', 'Répandeuses', 'Groupes électrogènes', 'Compresseurs',
			'Petit matériel', 'Petit outillage', 'Outil de forage et tiges',
			'Véhicules légers',
		]
		post_data = {
			'annee': '2026', 'mois': '10', 'periode': '2026-10',
			'chiffre_affaires': '0',
			'depenses-TOTAL_FORMS': str(len(rubriques)),
			'depenses-INITIAL_FORMS': '0',
			'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
			'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
			'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
			'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
			'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
		}
		for index, designation in enumerate(rubriques):
			post_data.update({
				f'depenses-{index}-categorie': 'MATERIEL',
				f'depenses-{index}-designation': designation,
				f'depenses-{index}-montant': '',
			})

		response = self.client.post(
			reverse('projets:ajouter_situation_mensuelle', args=[self.projet.id]),
			post_data,
		)

		self.assertRedirects(
			response,
			reverse('projets:situations_mensuelles', args=[self.projet.id]),
		)
		situation = SituationMensuelle.objects.get(projet=self.projet, mois=10)
		self.assertEqual(situation.depenses.count(), len(rubriques))
		self.assertEqual(situation.total_depenses, Decimal('0.00'))

	def test_situation_enregistre_les_recettes_et_le_total(self):
		dossier = Dossier.objects.create(
			nom='Dossier Situation Recettes', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		response = self.client.post(
			reverse('projets:ajouter_situation_mensuelle', args=[self.projet.id]),
			{
				'annee': '2026', 'mois': '11', 'periode': '2026-11',
				'recettes-TOTAL_FORMS': '3', 'recettes-INITIAL_FORMS': '0',
				'recettes-MIN_NUM_FORMS': '0', 'recettes-MAX_NUM_FORMS': '1000',
				'recettes-0-rubrique': 'TRAVAUX_REALISES', 'recettes-0-montant': '1 200,00',
				'recettes-1-rubrique': 'REVISION_PRIX', 'recettes-1-montant': '150,00',
				'recettes-2-rubrique': 'REFACTURATION_EXTERNE', 'recettes-2-montant': '-50,00',
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)
		self.assertRedirects(response, reverse('projets:situations_mensuelles', args=[self.projet.id]))
		situation = SituationMensuelle.objects.get(projet=self.projet, mois=11)
		self.assertEqual(situation.recettes.count(), 3)
		self.assertEqual(situation.chiffre_affaires, Decimal('1300.00'))

	def test_nouvelle_situation_cree_toujours_les_rubriques_recettes(self):
		dossier = Dossier.objects.create(
			nom='Dossier Rubriques Recettes Obligatoires', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		response = self.client.post(
			reverse('projets:ajouter_situation_mensuelle', args=[self.projet.id]),
			{
				'annee': '2026', 'mois': '6', 'periode': '2026-06',
				'recettes-TOTAL_FORMS': '0', 'recettes-INITIAL_FORMS': '0',
				'recettes-MIN_NUM_FORMS': '0', 'recettes-MAX_NUM_FORMS': '1000',
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertRedirects(response, reverse('projets:situations_mensuelles', args=[self.projet.id]))
		situation = SituationMensuelle.objects.get(projet=self.projet, mois=6)
		self.assertEqual(
			set(situation.recettes.values_list('rubrique', flat=True)),
			{
				RecetteSituationMensuelle.Rubrique.TRAVAUX_REALISES,
				RecetteSituationMensuelle.Rubrique.REVISION_PRIX,
				RecetteSituationMensuelle.Rubrique.REFACTURATION_EXTERNE,
			},
		)
		self.assertEqual(situation.chiffre_affaires, Decimal('0.00'))

	def test_situation_affiche_l_erreur_pres_du_champ_invalide(self):
		dossier = Dossier.objects.create(
			nom='Dossier Erreurs Situation', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		response = self.client.post(
			reverse('projets:ajouter_situation_mensuelle', args=[self.projet.id]),
			{
				'annee': '2026', 'mois': '5', 'periode': '2026-05',
				'recettes-TOTAL_FORMS': '0', 'recettes-INITIAL_FORMS': '0',
				'recettes-MIN_NUM_FORMS': '0', 'recettes-MAX_NUM_FORMS': '1000',
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '1', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'stocks-0-designation': 'Ciment', 'stocks-0-unite': 'sac',
				'stocks-0-quantite': 'invalide', 'stocks-0-prix_unitaire': '10,00',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'stocks-0-quantite')
		self.assertContains(response, 'situation-invalid-cell')
		self.assertFalse(SituationMensuelle.objects.filter(projet=self.projet, mois=5).exists())

	def test_formset_recettes_affiche_les_rubriques_par_defaut_sans_lignes(self):
		dossier = Dossier.objects.create(
			nom='Dossier Recettes par défaut', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=7, chiffre_affaires='0.00',
		)

		formset = _recettes_formset(situation=situation)

		self.assertEqual(len(formset.forms), 3)
		self.assertEqual(
			[form.rubrique_label for form in formset.forms],
			[
				'Travaux réalisés',
				'Révision des prix',
				'Refacturation externe',
			],
		)

	def test_situations_affichent_resultat_et_pourcentage(self):
		cases = (
			(1, '1000.00', '250.00', Decimal('750.00'), Decimal('75.00')),
			(2, '100.00', '150.00', Decimal('-50.00'), Decimal('-50.00')),
			(3, '100.00', '100.00', Decimal('0.00'), Decimal('0.00')),
			(4, '0.00', '100.00', Decimal('-100.00'), None),
		)
		for mois, produits, charges, _, _ in cases:
			situation = SituationMensuelle.objects.create(
				projet=self.projet, annee=2026, mois=mois, chiffre_affaires=produits,
			)
			DepenseSituationMensuelle.objects.create(
				situation=situation, categorie='PERSONNEL', designation='Charges',
				montant_base=charges,
			)
		for headers in ({}, {'HTTP_HX_REQUEST': 'true'}):
			response = self.client.get(
				reverse('projets:situations_mensuelles', args=[self.projet.id]), **headers,
			)
			self.assertEqual(response.status_code, 200)
			by_month = {s.mois: s for s in response.context['situations']}
			for mois, _, _, resultat, pct in cases:
				self.assertEqual(by_month[mois].resultat, resultat)
				self.assertEqual(by_month[mois].pct_resultat, pct)
			self.assertContains(response, 'Résultat : 750,00 DH')
			self.assertContains(response, '75,00 %')
			self.assertContains(response, '-50,00 %')
			self.assertContains(response, '0,00 %')
			self.assertContains(response, 'non calculable lorsque les produits sont nuls')
			self.assertContains(response, 'app-badge-danger')

	def test_apercu_situation_mensuelle_affiche_le_detail_imprimable(self):
		dossier = Dossier.objects.create(
			nom='Dossier Apercu Situation', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=12, chiffre_affaires='1250.00',
		)
		RecetteSituationMensuelle.objects.create(
			situation=situation, rubrique='TRAVAUX_REALISES', montant='1250.00',
		)
		DepenseSituationMensuelle.objects.create(
			situation=situation, categorie='PERSONNEL', designation='Équipe', montant_base='100.00',
		)
		StockSituationMensuelle.objects.create(
			situation=situation, designation='Ciment', unite='sac', quantite=Decimal('10'), prix_unitaire=Decimal('50'),
		)

		response = self.client.get(
			reverse('projets:apercu_situation_mensuelle', args=[self.projet.id, situation.id]),
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, "Aperçu de situation mensuelle")
		self.assertContains(response, "Chiffre d'affaires")
		self.assertContains(response, 'Charges')
		self.assertContains(response, 'Total charges : 100,00 DH')
		self.assertContains(response, 'État des stocks')
		self.assertContains(response, 'Afficher le détail')
		self.assertContains(response, 'detailToggle')
		self.assertContains(response, 'window.print()')

	def test_modification_situation_supprime_une_depense_existante(self):
		dossier = Dossier.objects.create(
			nom='Dossier Situation Suppression Depense', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=10, chiffre_affaires='1000.00',
		)
		depense_a_garder = DepenseSituationMensuelle.objects.create(
			situation=situation, categorie='PERSONNEL', designation='Personnel interne Mensuel', montant_base='100.00',
		)
		depense_a_supprimer = DepenseSituationMensuelle.objects.create(
			situation=situation, categorie='PERSONNEL', designation='Frais de Personnel', montant_base='200.00',
		)

		response = self.client.post(
			reverse('projets:modifier_situation_mensuelle', args=[self.projet.id, situation.id]),
			{
				'periode': '2026-10', 'annee': '2026', 'mois': '10',
				'chiffre_affaires': '1 000,00', 'observations': '',
				'depenses-TOTAL_FORMS': '2', 'depenses-INITIAL_FORMS': '2',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'depenses-0-id': str(depense_a_garder.id), 'depenses-0-categorie': 'PERSONNEL',
				'depenses-0-designation': depense_a_garder.designation, 'depenses-0-montant': '100,00',
				'depenses-1-id': str(depense_a_supprimer.id), 'depenses-1-categorie': 'PERSONNEL',
				'depenses-1-designation': depense_a_supprimer.designation, 'depenses-1-montant': '200,00',
				'depenses-1-DELETE': 'on',
				'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'documents-TOTAL_FORMS': '1', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertRedirects(
			response,
			reverse('projets:modifier_situation_mensuelle', args=[self.projet.id, situation.id]),
			fetch_redirect_response=False,
		)
		self.assertEqual(
			[str(message) for message in get_messages(response.wsgi_request)],
			['Situation mensuelle modifiée.'],
		)
		self.assertTrue(DepenseSituationMensuelle.objects.filter(pk=depense_a_garder.id).exists())
		self.assertFalse(DepenseSituationMensuelle.objects.filter(pk=depense_a_supprimer.id).exists())

	def test_modification_situation_ignore_un_stock_nouvellement_supprime(self):
		dossier = Dossier.objects.create(
			nom='Dossier Modification Stock Supprime', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=6,
		)

		response = self.client.post(
			reverse('projets:modifier_situation_mensuelle', args=[self.projet.id, situation.id]),
			{
				'periode': '2026-06', 'annee': '2026', 'mois': '6',
				'date_debut': '', 'date_fin': '', 'observations': '',
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '1', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'stocks-0-designation': '', 'stocks-0-unite': '',
				'stocks-0-quantite': '', 'stocks-0-prix_unitaire': '',
				'stocks-0-DELETE': 'on',
				'recettes-TOTAL_FORMS': '0', 'recettes-INITIAL_FORMS': '0',
				'recettes-MIN_NUM_FORMS': '0', 'recettes-MAX_NUM_FORMS': '1000',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertRedirects(
			response,
			reverse('projets:modifier_situation_mensuelle', args=[self.projet.id, situation.id]),
			fetch_redirect_response=False,
		)
		self.assertFalse(StockSituationMensuelle.objects.filter(situation=situation).exists())

	def test_modification_situation_ne_notifie_qu_une_fois_par_utilisateur(self):
		dossier = Dossier.objects.create(
			nom='Dossier Notification Situation', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=7,
		)
		Notification.objects.filter(objet_id=situation.id).delete()

		response = self.client.post(
			reverse('projets:modifier_situation_mensuelle', args=[self.projet.id, situation.id]),
			{
				'periode': '2026-07', 'annee': '2026', 'mois': '7',
				'date_debut': '', 'date_fin': '', 'observations': 'Mise à jour',
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'recettes-TOTAL_FORMS': '0', 'recettes-INITIAL_FORMS': '0',
				'recettes-MIN_NUM_FORMS': '0', 'recettes-MAX_NUM_FORMS': '1000',
				'documents-TOTAL_FORMS': '0', 'documents-INITIAL_FORMS': '0',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
			},
		)

		self.assertEqual(response.status_code, 302)
		self.assertEqual(
			Notification.objects.filter(
				objet_id=situation.id,
				type_notification='SITUATION_MENSUELLE_MODIFIEE',
			).count(),
			1,
		)

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

	def test_modification_situation_affiche_le_nom_du_document_existant(self):
		dossier = Dossier.objects.create(
			nom='Dossier Document Situation', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=4,
		)
		DocumentSituationMensuelle.objects.create(
			situation=situation,
			fichier=SimpleUploadedFile('situation-avril.pdf', b'contenu'),
		)

		response = self.client.get(
			reverse('projets:modifier_situation_mensuelle', args=[self.projet.id, situation.id]),
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'situation-avril.pdf')
		self.assertContains(response, 'document-file-label')

	def test_modification_situation_supprime_un_document(self):
		dossier = Dossier.objects.create(
			nom='Dossier Suppression Document Situation', gerant=self.user,
			activite=Dossier.Activite.TRAVAUX,
		)
		self.projet.dossier = dossier
		self.projet.save(update_fields=['dossier'])
		situation = SituationMensuelle.objects.create(
			projet=self.projet, annee=2026, mois=5,
		)
		document = DocumentSituationMensuelle.objects.create(
			situation=situation,
			fichier=SimpleUploadedFile('situation-mai.pdf', b'contenu'),
		)

		response = self.client.post(
			reverse('projets:modifier_situation_mensuelle', args=[self.projet.id, situation.id]),
			{
				'periode': '2026-05', 'annee': '2026', 'mois': '5',
				'date_debut': '', 'date_fin': '', 'observations': '',
				'depenses-TOTAL_FORMS': '0', 'depenses-INITIAL_FORMS': '0',
				'depenses-MIN_NUM_FORMS': '0', 'depenses-MAX_NUM_FORMS': '1000',
				'stocks-TOTAL_FORMS': '0', 'stocks-INITIAL_FORMS': '0',
				'stocks-MIN_NUM_FORMS': '0', 'stocks-MAX_NUM_FORMS': '1000',
				'recettes-TOTAL_FORMS': '0', 'recettes-INITIAL_FORMS': '0',
				'recettes-MIN_NUM_FORMS': '0', 'recettes-MAX_NUM_FORMS': '1000',
				'documents-TOTAL_FORMS': '1', 'documents-INITIAL_FORMS': '1',
				'documents-MIN_NUM_FORMS': '0', 'documents-MAX_NUM_FORMS': '1000',
				'documents-0-id': str(document.id), 'documents-0-DELETE': 'on',
			},
		)

		self.assertRedirects(response, reverse('projets:situations_mensuelles', args=[self.projet.id]))
		self.assertFalse(DocumentSituationMensuelle.objects.filter(pk=document.id).exists())

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
