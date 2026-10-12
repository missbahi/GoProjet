from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from projets.models import FichierSuivi, Projet, SuiviExecution


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SuiviMigrationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='suivi-admin', password='test-password')
        self.client.force_login(self.user)
        self.projet = Projet.objects.create(
            nom='Projet Suivi', objet='Test', numero='SUIVI-01',
            maitre_ouvrage='MOA', localisation='Lieu',
        )
        self.url = reverse('projets:suivi_execution', args=[self.projet.pk])
        self.add_url = reverse('projets:ajouter_suivi', args=[self.projet.pk])
        self.data = {
            'date': '2026-10-12', 'titre': 'Coordination sans fichiers',
            'type_suivi': 'reunion', 'importance': 'moyenne',
            'commentaire': 'Compte rendu de coordination', 'redacteur': 'Test',
            'action': 'save_and_close',
        }

    def test_list_renders_history_and_bound_form_in_full_and_htmx_pages(self):
        SuiviExecution.objects.create(projet=self.projet, **{
            key: value for key, value in self.data.items() if key != 'action'
        })
        for headers in ({}, {'HTTP_HX_REQUEST': 'true'}):
            with self.subTest(headers=headers):
                response = self.client.get(self.url, **headers)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'Coordination sans fichiers')
                self.assertContains(response, '1 entrée(s)')
                self.assertContains(response, "Suivi d'exécution")
                self.assertContains(response, 'name="type_suivi"')
                self.assertNotContains(response, 'bg-[#3B3B3B]')
                if headers:
                    self.assertNotContains(response, '<html')
                else:
                    self.assertContains(response, 'projets/js/suivi.js')

    def test_add_without_files_does_not_access_attachment_storage(self):
        storage = FichierSuivi._meta.get_field('fichier').storage
        with patch.object(storage, 'save', side_effect=AssertionError('Storage write forbidden')), \
                patch.object(storage, 'open', side_effect=AssertionError('Storage read forbidden')), \
                patch.object(storage, 'delete', side_effect=AssertionError('Storage delete forbidden')):
            response = self.client.post(
                self.add_url, self.data, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json()['success'])
            self.assertFalse(response.json()['open_files'])
            self.assertEqual(response.json()['url'], self.url)
            suivi = SuiviExecution.objects.get(projet=self.projet)
            self.assertEqual(suivi.titre, self.data['titre'])
            self.assertEqual(suivi.fichiers.count(), 0)
            self.assertContains(self.client.get(self.url, HTTP_HX_REQUEST='true'), suivi.titre)

    def test_open_files_action_returns_destination_without_upload(self):
        response = self.client.post(
            self.add_url, {**self.data, 'action': 'save_and_open_files'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        suivi = SuiviExecution.objects.get(projet=self.projet)
        self.assertEqual(response.json()['url'], reverse(
            'projets:ajouter_fichier_suivi', args=[self.projet.pk, suivi.pk],
        ))
        self.assertTrue(response.json()['open_files'])
        self.assertEqual(FichierSuivi.objects.count(), 0)

    def test_invalid_input_stays_visible_without_creating_record(self):
        for headers in ({}, {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}):
            with self.subTest(headers=headers):
                response = self.client.post(
                    self.add_url, {**self.data, 'date': 'invalid', 'titre': ''}, **headers,
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(SuiviExecution.objects.count(), 0)
                if headers:
                    self.assertIn('date', response.json()['errors'])
                    self.assertIn('titre', response.json()['errors'])
                else:
                    self.assertContains(response, 'Compte rendu de coordination', status_code=400)
                    self.assertNotContains(response, 'id="suiviFormContainer" class="app-card p-4 md:p-6 mb-6 hidden"', status_code=400)

    def test_classic_submission_preserves_redirect_behavior(self):
        response = self.client.post(self.add_url, self.data)
        self.assertRedirects(
            response, reverse('projets:dashboard', args=[self.projet.pk]),
            fetch_redirect_response=False,
        )

    def test_unauthenticated_add_is_rejected(self):
        self.client.logout()
        self.assertEqual(self.client.post(self.add_url, self.data).status_code, 302)
        self.assertEqual(SuiviExecution.objects.count(), 0)

    def create_suivi(self):
        return SuiviExecution.objects.create(projet=self.projet, **{
            key: value for key, value in self.data.items() if key != 'action'
        })

    def test_edit_form_loads_inline_and_keeps_classic_access(self):
        suivi = self.create_suivi()
        edit_url = reverse('projets:modifier_suivi', args=[self.projet.pk, suivi.pk])
        response = self.client.get(
            edit_url, HTTP_HX_REQUEST='true', HTTP_HX_TARGET='suiviEditContainer',
        )
        self.assertContains(response, 'id="editSuiviForm"')
        self.assertContains(response, 'id="edit_titre"')
        self.assertContains(response, 'value="Coordination sans fichiers"')
        self.assertContains(response, 'data-cancel-suivi-edit')
        self.assertNotContains(response, '<html')
        self.assertNotContains(response, 'value="save_and_open_files"')
        self.assertContains(self.client.get(edit_url), '<html')
        listing = self.client.get(self.url)
        self.assertContains(listing, 'hx-target="#suiviEditContainer"')
        self.assertContains(listing, 'hx-push-url="false"')
        self.assertContains(listing, 'app-btn app-btn-danger suivi-delete-btn')

    def test_edit_persists_fields_without_touching_existing_attachment_storage(self):
        suivi = self.create_suivi()
        attachment = FichierSuivi.objects.create(
            suivi=suivi, fichier='test-existing-reference.pdf', description='Unchanged',
        )
        storage = FichierSuivi._meta.get_field('fichier').storage
        with patch.object(storage, 'save', side_effect=AssertionError('Storage write forbidden')), \
                patch.object(storage, 'open', side_effect=AssertionError('Storage read forbidden')), \
                patch.object(storage, 'delete', side_effect=AssertionError('Storage delete forbidden')):
            response = self.client.post(
                reverse('projets:modifier_suivi', args=[self.projet.pk, suivi.pk]),
                {**self.data, 'titre': 'Titre modifié', 'importance': 'elevee', 'date': '2026-10-13'},
                HTTP_X_REQUESTED_WITH='XMLHttpRequest',
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['url'], self.url)
            suivi.refresh_from_db()
            self.assertEqual(suivi.titre, 'Titre modifié')
            self.assertEqual(suivi.importance, 'elevee')
            self.assertEqual(str(suivi.date), '2026-10-13')
            attachment.refresh_from_db()
            self.assertEqual(attachment.fichier.name, 'test-existing-reference.pdf')
            self.assertEqual(attachment.description, 'Unchanged')
            self.assertEqual(suivi.fichiers.count(), 1)

    def test_invalid_edit_returns_errors_and_preserves_record(self):
        suivi = self.create_suivi()
        edit_url = reverse('projets:modifier_suivi', args=[self.projet.pk, suivi.pk])
        for headers in ({}, {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}):
            with self.subTest(headers=headers):
                response = self.client.post(edit_url, {**self.data, 'titre': '', 'date': 'invalid'}, **headers)
                self.assertEqual(response.status_code, 400)
                suivi.refresh_from_db()
                self.assertEqual(suivi.titre, self.data['titre'])
                if headers:
                    self.assertIn('titre', response.json()['errors'])
                else:
                    self.assertContains(response, 'data-suivi-errors', status_code=400)

    def test_edit_is_scoped_to_the_current_project(self):
        suivi = self.create_suivi()
        other = Projet.objects.create(nom='Other', numero='OTHER', objet='Test',
                                     maitre_ouvrage='MOA', localisation='Lieu')
        response = self.client.get(
            reverse('projets:modifier_suivi', args=[other.pk, suivi.pk]), HTTP_HX_REQUEST='true',
        )
        self.assertEqual(response.status_code, 404)

    def test_classic_edit_redirects_back_to_history(self):
        suivi = self.create_suivi()
        response = self.client.post(
            reverse('projets:modifier_suivi', args=[self.projet.pk, suivi.pk]),
            {**self.data, 'titre': 'Classic edit'},
        )
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        suivi.refresh_from_db()
        self.assertEqual(suivi.titre, 'Classic edit')
