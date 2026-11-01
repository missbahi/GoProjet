import json

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from projets.forms import BORDEREAU_APPEARANCE_DEFAULTS
from projets.models import LigneBordereau, LotProjet, Projet


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class BordereauAppearanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_superuser(
            username='bdp-appearance-test',
            email='bdp-appearance@example.invalid',
            password='test-password',
        )
        cls.projet = Projet.objects.create(
            nom='Projet configuration BPU',
            objet='Tests de configuration du bordereau',
            numero='TEST-BDP-APPEARANCE',
            maitre_ouvrage='Test',
            localisation='Test',
        )
        cls.lot = LotProjet.objects.create(projet=cls.projet, nom='Lot de test')

    def setUp(self):
        self.client.force_login(self.user)
        self.page_url = reverse('projets:saisie_bordereau', args=[self.projet.pk, self.lot.pk])
        self.save_url = reverse('projets:sauvegarder_config_bordereau', args=[self.projet.pk, self.lot.pk])

    def test_page_exposes_default_configuration_and_dialog(self):
        response = self.client.get(self.page_url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['appearance_data']['values'], BORDEREAU_APPEARANCE_DEFAULTS)
        self.assertContains(response, 'id="bdp-appearance-dialog"')
        self.assertContains(response, 'id="bdp-appearance-data"')

    def test_configuration_is_saved_per_lot_and_stale_revisions_are_rejected(self):
        page = self.client.get(self.page_url)
        revision = page.context['appearance_data']['revision']
        payload = {**BORDEREAU_APPEARANCE_DEFAULTS, 'revision': revision, 'row_height': 32}

        response = self.client.post(self.save_url, payload)

        self.assertEqual(response.status_code, 200)
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.bordereau_config['row_height'], 32)
        self.assertEqual(response.json()['values']['row_height'], 32)

        stale = self.client.post(self.save_url, payload)
        self.assertEqual(stale.status_code, 409)

    def test_invalid_colors_and_dimensions_are_rejected(self):
        page = self.client.get(self.page_url)
        payload = {
            **BORDEREAU_APPEARANCE_DEFAULTS,
            'revision': page.context['appearance_data']['revision'],
            'row_color': 'red',
            'row_height': 200,
        }

        response = self.client.post(self.save_url, payload)

        self.assertEqual(response.status_code, 400)
        self.assertIn('row_color', response.json()['errors'])
        self.assertIn('row_height', response.json()['errors'])
        self.lot.refresh_from_db()
        self.assertEqual(self.lot.bordereau_config, {})

    def test_new_lines_are_expanded_by_default(self):
        ligne = LigneBordereau.objects.create(
            lot=self.lot, designation='Groupe', quantite=0, prix_unitaire=0,
        )
        self.assertTrue(ligne.expanded)
        page = self.client.get(self.page_url)
        data = json.loads(page.context['lignes'])
        self.assertTrue(data[0]['_expanded'])

    def test_fold_states_are_saved_and_reloaded_for_another_user(self):
        payload = [
            {'id': 'group', 'designation': 'Groupe', 'est_titre': True, '_expanded': False},
            {'id': 'nested', 'parent_id': 'group', 'designation': 'Sous-groupe',
             'est_titre': True, '_expanded': True},
            {'id': 'leaf', 'parent_id': 'nested', 'designation': 'Prix',
             'quantite': 2, 'prix_unitaire': 10, '_expanded': True},
        ]
        url = reverse('projets:sauvegarder_lignes_bordereau', args=[self.lot.pk])
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        ids = response.json()['lignes']
        group = LigneBordereau.objects.get(pk=ids['group'])
        self.assertFalse(group.expanded)
        self.assertEqual(group.montant, 20)

        other_user = get_user_model().objects.create_superuser(
            username='bdp-fold-reader', email='reader@example.invalid', password='test-password',
        )
        self.client.force_login(other_user)
        page = self.client.get(self.page_url)
        data = {row['id']: row for row in json.loads(page.context['lignes'])}
        self.assertFalse(data[ids['group']]['_expanded'])
        self.assertTrue(data[ids['nested']]['_expanded'])
        self.assertEqual(data[ids['leaf']]['montant'], 20)

        for row in payload:
            row['id'] = ids[row['id']]
            if row.get('parent_id'):
                row['parent_id'] = ids[row['parent_id']]
        payload[0]['_expanded'] = True
        payload[1]['_expanded'] = False
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        group.refresh_from_db()
        self.assertTrue(group.expanded)
        self.assertFalse(LigneBordereau.objects.get(pk=ids['nested']).expanded)

        # Old clients do not overwrite saved fold states when omitting the field.
        for row in payload:
            del row['_expanded']
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LigneBordereau.objects.get(pk=ids['nested']).expanded)

    def test_invalid_fold_state_is_rejected_before_writing_lines(self):
        url = reverse('projets:sauvegarder_lignes_bordereau', args=[self.lot.pk])
        payload = [
            {'id': 'valid', 'designation': 'Valide', '_expanded': True},
            {'id': 'invalid', 'designation': 'Invalide', '_expanded': 'false'},
        ]
        response = self.client.post(url, payload, content_type='application/json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()['status'], 'error')
        self.assertFalse(self.lot.lignes.exists())