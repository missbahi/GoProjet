import json
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from projets.forms import SituationMensuelleForm
from projets.models import (
    ChiffreAffaire, Dossier, LigneBordereau, LotProjet, Projet,
    RecetteSituationMensuelle, SituationMensuelle,
)
from projets.services.chiffre_affaire import (
    enregistrer_ca, lignes_pour_ca, mois_voisin, synchroniser_situation_ca,
)


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ChiffreAffaireTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='admin-ca')
        self.chef = User.objects.create_user(username='chef-ca')
        self.chef.profile.role = 'CHEF_PROJET'
        self.chef.profile.save()
        self.dossier = Dossier.objects.create(nom='Travaux CA', activite='TRAVAUX', gerant=self.chef)
        self.projet = Projet.objects.create(
            dossier=self.dossier, nom='Projet CA', objet='Travaux', numero='CA-TEST',
            maitre_ouvrage='MO', localisation='Site',
        )
        self.lot = LotProjet.objects.create(projet=self.projet, nom='Lot CA')
        self.ligne = LigneBordereau.objects.create(
            lot=self.lot, numero='1', designation='Production', unite='m',
            quantite=Decimal('100'), prix_unitaire=Decimal('10'),
        )
        self.client.force_login(self.user)

    def candidate(self, month=1, year=2025, **kwargs):
        return ChiffreAffaire(projet=self.projet, periode=date(year, month, 1), **kwargs)

    def payload(self, quantity='10', initial='0'):
        return json.dumps([{
            'id': self.ligne.pk, 'quantite_cumulee': quantity, 'cumul_initial': initial,
        }])

    def save_ca(self, ca=None, quantity='10', initial='0', action='valider', user=None):
        ca = ca or self.candidate()
        data = self.payload(quantity, initial)
        user = user or self.user
        preview = enregistrer_ca(ca, data, user, action=action)
        result = enregistrer_ca(ca, data, user, action=action, confirmation=preview['confirmation'])
        return ChiffreAffaire.objects.get(pk=result['id'])

    def situation(self, month=1, amount='999', status='BROUILLON'):
        situation = SituationMensuelle.objects.create(
            projet=self.projet, annee=2025, mois=month, statut=status,
            chiffre_affaires=Decimal(amount),
        )
        for rubrique, montant in [('TRAVAUX_REALISES', amount), ('REVISION_PRIX', '20'), ('REFACTURATION_EXTERNE', '5')]:
            RecetteSituationMensuelle.objects.create(situation=situation, rubrique=rubrique, montant=Decimal(montant))
        return situation

    def test_calendar_leap_and_year_transition(self):
        ca = self.candidate(month=2, year=2024)
        self.assertEqual(ca.date_fin, date(2024, 2, 29))
        self.assertEqual(mois_voisin(date(2024, 12, 1), 1), date(2025, 1, 1))
        december = self.save_ca(self.candidate(month=12, year=2024), quantity='20')
        january = self.save_ca(self.candidate(), quantity='23')
        self.assertEqual(december.montant_mensuel, Decimal('200'))
        self.assertEqual(january.montant_mensuel, Decimal('30'))

    def test_preview_has_no_writes_and_confirmation_saves(self):
        ca = self.candidate()
        preview = enregistrer_ca(ca, self.payload(), self.user)
        self.assertFalse(ChiffreAffaire.objects.exists())
        self.assertEqual(preview['impacts'][0]['apres'], '100.00')
        result = enregistrer_ca(ca, self.payload(), self.user, confirmation=preview['confirmation'])
        self.assertTrue(result['enregistre'])
        ca.refresh_from_db()
        self.assertEqual(ca.statut, 'BROUILLON')
        self.assertEqual(ca.cree_par, self.user)

    def test_reprise_baseline_and_next_month(self):
        first = self.save_ca(self.candidate(origine='REPRISE'), quantity='50', initial='40')
        second = self.save_ca(self.candidate(month=2), quantity='55')
        self.assertEqual(first.montant_mensuel, Decimal('100'))
        self.assertEqual(second.montant_mensuel, Decimal('50'))
        self.assertEqual(Decimal(lignes_pour_ca(second)[0]['cumul_precedent']), Decimal('50'))

    def test_missing_month_previous_draft_and_duplicate_rejected(self):
        first = self.save_ca(action='enregistrer')
        with self.assertRaisesMessage(ValidationError, 'précédent'):
            self.save_ca(self.candidate(month=2))
        self.save_ca(first)
        for ca in [self.candidate(month=3), self.candidate()]:
            with self.assertRaises(ValidationError):
                enregistrer_ca(ca, self.payload(), self.user)

    def test_initial_balance_only_first_reprise(self):
        with self.assertRaisesMessage(ValidationError, 'cumul initial'):
            self.save_ca(initial='2')
        self.save_ca()
        with self.assertRaisesMessage(ValidationError, 'cumul initial'):
            self.save_ca(self.candidate(month=2), initial='2')

    def test_negative_partial_requires_observations(self):
        self.save_ca()
        second = self.candidate(month=2)
        with self.assertRaisesMessage(ValidationError, 'observations'):
            enregistrer_ca(second, self.payload('8'), self.user)
        second.observations = 'Correction de mesure'
        preview = enregistrer_ca(second, self.payload('8'), self.user)
        self.assertEqual(preview['regularisations'], ['1'])
        second = self.save_ca(second, quantity='8')
        self.assertEqual(second.montant_mensuel, Decimal('-20'))

    def test_prices_and_designation_frozen(self):
        self.save_ca()
        LigneBordereau.objects.filter(pk=self.ligne.pk).update(prix_unitaire=99, designation='Modifie')
        second = self.save_ca(self.candidate(month=2), quantity='15')
        self.assertEqual(second.montant_mensuel, Decimal('50'))
        self.assertEqual(second.lignes.get().designation, 'Production')
        with patch('projets.views.lot_views.views._iter_lignes_bordereau_hierarchiques', return_value=[]):
            self.assertEqual(lignes_pour_ca(second)[0]['id'], self.ligne.pk)

    def test_existing_rows_frozen_new_bordereau_line_only_enters_next_month(self):
        first = self.save_ca()
        added = LigneBordereau.objects.create(
            lot=self.lot, numero='2', designation='Nouveaux travaux', unite='m',
            quantite=1, prix_unitaire=20,
        )
        self.assertEqual([l['id'] for l in lignes_pour_ca(first)], [self.ligne.pk])
        first = self.save_ca(first, quantity='12')
        next_ca = self.candidate(month=2)
        self.assertEqual({l['id'] for l in lignes_pour_ca(next_ca)}, {self.ligne.pk, added.pk})

    def test_total_rounding_at_half_cent(self):
        LigneBordereau.objects.filter(pk=self.ligne.pk).update(prix_unitaire=Decimal('0.50'))
        ca = self.save_ca(quantity='0.01')
        self.assertEqual(ca.montant_mensuel, Decimal('0.01'))

    def test_invalid_quantities_rejected_atomically(self):
        for value in ['NaN', 'Infinity', '-1', '0.0001', '1000000000000', None, 'abc']:
            with self.subTest(value=value), self.assertRaises(ValidationError):
                enregistrer_ca(self.candidate(), self.payload(value), self.user)
        self.assertFalse(ChiffreAffaire.objects.exists())

    def test_invalid_ids_and_payloads(self):
        row = json.loads(self.payload())[0]
        for data in ['{', '{}', '[]', json.dumps([row, row]), json.dumps([{**row, 'id': 999999}]),
                     json.dumps([{**row, 'id': True}])]:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                enregistrer_ca(self.candidate(), data, self.user)
        self.assertFalse(ChiffreAffaire.objects.exists())

    def test_tampered_expired_changed_payload_and_user_tokens(self):
        ca = self.candidate()
        preview = enregistrer_ca(ca, self.payload(), self.user)
        for token, payload, user in [
            (preview['confirmation'] + 'x', self.payload(), self.user),
            (preview['confirmation'], self.payload('11'), self.user),
            (preview['confirmation'], self.payload(), self.chef),
        ]:
            with self.assertRaises(ValidationError):
                enregistrer_ca(ca, payload, user, confirmation=token)
        with patch('django.core.signing.time.time', return_value=9999999999), self.assertRaises(ValidationError):
            enregistrer_ca(ca, self.payload(), self.user, confirmation=preview['confirmation'])
        self.assertFalse(ChiffreAffaire.objects.exists())

    def test_stale_database_invalidates_preview(self):
        first = self.save_ca()
        preview = enregistrer_ca(first, self.payload('11'), self.user)
        ChiffreAffaire.objects.filter(pk=first.pk).update(observations='Autre modification')
        with self.assertRaisesMessage(ValidationError, 'données ont changé'):
            enregistrer_ca(first, self.payload('11'), self.user, confirmation=preview['confirmation'])

    def test_current_and_next_draft_recalculated(self):
        first = self.save_ca()
        second = self.save_ca(self.candidate(month=2), quantity='20', action='enregistrer')
        first = self.save_ca(first, quantity='12')
        second.refresh_from_db()
        self.assertEqual(first.montant_mensuel, Decimal('120'))
        self.assertEqual(second.montant_mensuel, Decimal('80'))

    def test_negative_successor_impact_requires_explanation_and_is_displayed(self):
        first = self.save_ca()
        self.save_ca(self.candidate(month=2), quantity='20', action='enregistrer')
        with self.assertRaisesMessage(ValidationError, 'observations'):
            enregistrer_ca(first, self.payload('22'), self.user)
        first.observations = 'Repartition corrigee entre les mois'
        preview = enregistrer_ca(first, self.payload('22'), self.user)
        self.assertIn('02/2025 : 1', preview['regularisations'])

    def test_deleted_creator_does_not_prevent_authorized_correction(self):
        first = self.save_ca()
        self.user.delete()
        first.refresh_from_db()
        self.assertIsNone(first.cree_par_id)
        first = self.save_ca(first, quantity='12', user=self.chef)
        self.assertIsNone(first.cree_par_id)
        self.assertEqual(first.modifie_par, self.chef)

    def test_linked_next_draft_situation_recalculated(self):
        first = self.save_ca()
        second = self.save_ca(self.candidate(month=2), quantity='20')
        situation = self.situation(month=2)
        synchroniser_situation_ca(situation)
        self.save_ca(second, quantity='20', action='devalider')
        self.save_ca(first, quantity='12')
        situation.refresh_from_db()
        self.assertEqual(situation.ca_id, second.pk)
        self.assertEqual(situation.chiffre_affaires, Decimal('105'))

    def test_validated_situation_blocks_zero_net_quantity_changes(self):
        other = LigneBordereau.objects.create(
            lot=self.lot, numero='2', designation='Autres travaux', unite='m',
            quantite=100, prix_unitaire=10,
        )
        ca = self.candidate()
        data = json.dumps([
            {'id': self.ligne.pk, 'quantite_cumulee': '10'},
            {'id': other.pk, 'quantite_cumulee': '10'},
        ])
        preview = enregistrer_ca(ca, data, self.user, action='valider')
        enregistrer_ca(ca, data, self.user, action='valider', confirmation=preview['confirmation'])
        situation = self.situation()
        synchroniser_situation_ca(situation)
        situation.statut = 'VALIDEE'
        situation.save()
        data = json.dumps([
            {'id': self.ligne.pk, 'quantite_cumulee': '12'},
            {'id': other.pk, 'quantite_cumulee': '8'},
        ])
        with self.assertRaisesMessage(ValidationError, 'situation'):
            enregistrer_ca(ca, data, self.user, action='valider')

    def test_validated_successor_blocks_change_then_devalidation_allows(self):
        first = self.save_ca()
        second = self.save_ca(self.candidate(month=2), quantity='20')
        with self.assertRaisesMessage(ValidationError, 'mois suivant'):
            self.save_ca(first, quantity='12')
        with self.assertRaisesMessage(ValidationError, 'mois suivant'):
            self.save_ca(first, action='devalider')
        self.save_ca(second, quantity='20', action='devalider')
        first = self.save_ca(first, quantity='12', action='devalider')
        self.assertEqual(first.montant_mensuel, Decimal('120'))
        self.assertEqual(first.statut, ChiffreAffaire.Statut.BROUILLON)

    def test_manual_revenue_replaced_only_after_confirm_preserving_other_recipes(self):
        situation = self.situation()
        ca = self.candidate()
        preview = enregistrer_ca(ca, self.payload(), self.user, action='valider')
        situation.refresh_from_db()
        self.assertIsNone(situation.ca_id)
        self.assertEqual(situation.chiffre_affaires, Decimal('999'))
        self.assertTrue(any(i['avant'] == '999.00' for i in preview['impacts']))
        enregistrer_ca(ca, self.payload(), self.user, action='valider', confirmation=preview['confirmation'])
        situation.refresh_from_db()
        self.assertEqual(situation.ca_id, ca.pk)
        self.assertEqual(situation.chiffre_affaires, Decimal('125'))
        self.assertEqual(situation.resultat, Decimal('125'))
        self.assertEqual(situation.recettes.get(rubrique='REVISION_PRIX').montant, Decimal('20'))

    def test_validated_situation_protection(self):
        situation = self.situation()
        first = self.save_ca()
        SituationMensuelle.objects.filter(pk=situation.pk).update(statut='VALIDEE')
        for action in ['valider', 'devalider']:
            with self.assertRaisesMessage(ValidationError, 'situation'):
                self.save_ca(first, quantity='12', action=action)
        with self.assertRaisesMessage(ValidationError, 'situation'):
            self.save_ca(first, action='devalider')
        self.assertEqual(self.save_ca(first).montant_mensuel, Decimal('100'))

    def test_preexisting_validated_manual_situation_blocks_link(self):
        self.situation(status='VALIDEE')
        with self.assertRaisesMessage(ValidationError, 'situation'):
            self.save_ca()
        self.assertFalse(ChiffreAffaire.objects.exists())

    def test_situation_revenue_overflow_rejected_during_preview(self):
        situation = self.situation()
        situation.recettes.filter(rubrique='REVISION_PRIX').update(montant=Decimal('9999999999999.99'))
        with self.assertRaises(ValidationError):
            enregistrer_ca(self.candidate(), self.payload(), self.user, action='valider')
        self.assertFalse(ChiffreAffaire.objects.exists())

    def test_devalidated_ca_keeps_draft_source_and_blocks_situation_validation(self):
        situation = self.situation()
        first = self.save_ca()
        self.save_ca(first, action='devalider')
        situation.refresh_from_db()
        self.assertEqual(situation.ca_id, first.pk)
        response = self.client.post(reverse('projets:valider_situation_mensuelle', args=[self.projet.pk, situation.pk]))
        self.assertEqual(response.status_code, 400)
        self.assertIn('CA', response.json()['message'])

    def test_legacy_situation_unchanged_without_ca(self):
        situation = self.situation()
        synchroniser_situation_ca(situation)
        situation.refresh_from_db()
        self.assertEqual(situation.chiffre_affaires, Decimal('999'))
        self.assertIsNone(situation.ca_id)

    def test_linked_month_and_validated_edit_blocked(self):
        situation = self.situation()
        self.save_ca()
        situation.refresh_from_db()
        form = SituationMensuelleForm(
            {'periode': '2025-02', 'annee': 2025, 'mois': 2}, instance=situation, projet=self.projet,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('periode', form.errors)
        situation.refresh_from_db()
        situation.statut = 'VALIDEE'
        situation.save()
        form = SituationMensuelleForm(
            {'periode': '2025-01', 'annee': 2025, 'mois': 1}, instance=situation, projet=self.projet,
        )
        self.assertFalse(form.is_valid())
        self.assertIn('__all__', form.errors)

    def test_sync_failure_rolls_back_ca_lines_and_recipes(self):
        situation = self.situation()
        ca = self.candidate()
        preview = enregistrer_ca(ca, self.payload(), self.user, action='valider')
        with patch('projets.services.chiffre_affaire.synchroniser_situation_ca', side_effect=ValidationError('Echec')):
            with self.assertRaises(ValidationError):
                enregistrer_ca(ca, self.payload(), self.user, action='valider', confirmation=preview['confirmation'])
        self.assertFalse(ChiffreAffaire.objects.exists())
        situation.refresh_from_db()
        self.assertEqual(situation.chiffre_affaires, Decimal('999'))

    def test_ca_http_preview_confirm_and_readonly_permissions(self):
        url = reverse('projets:ajouter_ca', args=[self.projet.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        data = {'mois': '2025-01', 'origine': 'DEBUT', 'observations': '', 'lignes': self.payload(), 'action': 'valider'}
        self.client.force_login(self.chef)
        preview = self.client.post(url, data)
        self.assertEqual(preview.status_code, 200, preview.content)
        data['confirmation'] = preview.json()['confirmation']
        saved = self.client.post(url, data)
        self.assertEqual(saved.status_code, 200, saved.content)
        ca_url = saved.json()['redirect']
        viewer = User.objects.create_user(username='viewer-ca')
        self.dossier.utilisateurs.add(viewer)
        self.client.force_login(viewer)
        self.assertEqual(self.client.get(ca_url).status_code, 200)
        self.assertEqual(self.client.post(ca_url, data).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 403)
        outsider = User.objects.create_user(username='outside-ca')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(ca_url).status_code, 403)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(ca_url, data).status_code, 403)

    def test_list_full_page_and_htmx_fragment_do_not_nest_layout(self):
        self.save_ca()
        url = reverse('projets:liste_ca', args=[self.projet.pk])
        full = self.client.get(url)
        self.assertEqual(full.status_code, 200)
        self.assertTemplateUsed(full, 'projets/ca/liste.html')
        self.assertContains(full, 'id="main-content"', count=1)
        partial = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertEqual(partial.status_code, 200)
        self.assertTemplateUsed(partial, 'projets/ca/_liste_content.html')
        self.assertTemplateNotUsed(partial, 'projets/home/base_project.html')
        self.assertNotContains(partial, '<html')
        self.assertNotContains(partial, 'id="main-content"')
        self.assertContains(partial, reverse('projets:modifier_ca', args=[self.projet.pk, ChiffreAffaire.objects.get().pk]))

    def ca_action(self, ca, action, **kwargs):
        return self.client.post(reverse(f'projets:{action}_ca', args=[self.projet.pk, ca.pk]), **kwargs)

    def test_list_actions_validate_and_devalidate_without_quantity_changes(self):
        situation = self.situation()
        ca = self.save_ca(action='enregistrer')
        quantities = list(ca.lignes.values_list('quantite_cumulee', 'cumul_initial', 'prix_unitaire'))
        response = self.ca_action(ca, 'valider')
        self.assertEqual(response.status_code, 200, response.content)
        ca.refresh_from_db()
        situation.refresh_from_db()
        self.assertEqual(ca.statut, 'VALIDE')
        self.assertEqual(situation.ca_id, ca.pk)
        self.assertEqual(situation.chiffre_affaires, Decimal('125'))
        self.assertEqual(quantities, list(ca.lignes.values_list('quantite_cumulee', 'cumul_initial', 'prix_unitaire')))
        self.assertEqual(self.ca_action(ca, 'valider').status_code, 400)
        self.assertEqual(self.ca_action(ca, 'devalider').status_code, 200)
        ca.refresh_from_db()
        self.assertEqual(ca.statut, 'BROUILLON')
        self.assertEqual(self.ca_action(ca, 'supprimer').status_code, 400)

    def test_delete_only_last_unlinked_draft_and_cascades_lines(self):
        first = self.save_ca()
        self.assertEqual(self.ca_action(first, 'supprimer').status_code, 400)
        second = self.save_ca(self.candidate(month=2), quantity='20', action='enregistrer')
        self.assertEqual(self.ca_action(first, 'devalider').status_code, 400)
        self.assertEqual(self.ca_action(second, 'supprimer').status_code, 200)
        self.assertFalse(ChiffreAffaire.objects.filter(pk=second.pk).exists())
        self.assertFalse(second.lignes.exists())
        self.assertTrue(ChiffreAffaire.objects.filter(pk=first.pk).exists())
        self.save_ca(first, action='devalider')
        self.assertEqual(self.ca_action(first, 'supprimer').status_code, 200)

    def test_list_actions_preserve_validated_situation(self):
        situation = self.situation(status='VALIDEE')
        ca = self.save_ca(action='enregistrer')
        response = self.ca_action(ca, 'valider')
        self.assertEqual(response.status_code, 400)
        ca.refresh_from_db()
        situation.refresh_from_db()
        self.assertEqual(ca.statut, 'BROUILLON')
        self.assertEqual(situation.chiffre_affaires, Decimal('999'))
        self.assertIsNone(situation.ca_id)

    def test_list_actions_require_post_authorization_and_csrf(self):
        ca = self.save_ca(action='enregistrer')
        for action in ['valider', 'devalider', 'supprimer']:
            url = reverse(f'projets:{action}_ca', args=[self.projet.pk, ca.pk])
            self.assertEqual(self.client.get(url).status_code, 405)
            csrf = Client(enforce_csrf_checks=True)
            csrf.force_login(self.user)
            self.assertEqual(csrf.post(url).status_code, 403)
        viewer = User.objects.create_user(username='action-viewer')
        self.dossier.utilisateurs.add(viewer)
        self.client.force_login(viewer)
        for action in ['valider', 'devalider', 'supprimer']:
            self.assertEqual(self.ca_action(ca, action).status_code, 403)
        self.client.force_login(self.chef)
        self.assertEqual(self.ca_action(ca, 'valider').status_code, 200)

    def test_list_icons_follow_status_and_dependencies(self):
        first = self.save_ca()
        second = self.save_ca(self.candidate(month=2), quantity='20', action='enregistrer')
        url = reverse('projets:liste_ca', args=[self.projet.pk])
        response = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertContains(response, reverse('projets:supprimer_ca', args=[self.projet.pk, second.pk]))
        self.assertContains(response, reverse('projets:valider_ca', args=[self.projet.pk, second.pk]))
        self.assertNotContains(response, reverse('projets:devalider_ca', args=[self.projet.pk, first.pk]))
        self.situation(month=2)
        self.ca_action(second, 'valider')
        response = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertNotContains(response, reverse('projets:devalider_ca', args=[self.projet.pk, first.pk]))
        self.ca_action(second, 'devalider')
        response = self.client.get(url, HTTP_HX_REQUEST='true')
        self.assertContains(response, reverse('projets:devalider_ca', args=[self.projet.pk, first.pk]))
        self.assertNotContains(response, reverse('projets:supprimer_ca', args=[self.projet.pk, second.pk]))
        self.assertEqual(self.ca_action(first, 'devalider').status_code, 200)

    def test_service_permissions_and_non_travaux(self):
        outsider = User.objects.create_user(username='denied-ca')
        with self.assertRaises(ValidationError):
            self.save_ca(user=outsider)
        self.dossier.activite = 'SERVICES'
        self.dossier.save()
        with self.assertRaises(ValidationError):
            self.save_ca()
        self.assertEqual(self.client.get(reverse('projets:liste_ca', args=[self.projet.pk])).status_code, 403)

    def situation_post(self):
        data = {
            'periode': '2025-01', 'annee': '2025', 'mois': '1',
            'date_debut': '2025-01-10', 'date_fin': '2025-01-31',
            'observations': '', 'chiffre_affaires': '99999',
        }
        for prefix in ['depenses', 'stocks', 'documents']:
            data.update({
                f'{prefix}-TOTAL_FORMS': '0', f'{prefix}-INITIAL_FORMS': '0',
                f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000',
            })
        return data

    def test_situation_created_after_ca_uses_calculated_revenue(self):
        ca = self.save_ca()
        response = self.client.post(reverse('projets:ajouter_situation_mensuelle', args=[self.projet.pk]), self.situation_post())
        self.assertEqual(response.status_code, 302, response.context and response.context['form'].errors)
        situation = SituationMensuelle.objects.get(projet=self.projet)
        self.assertEqual(situation.ca_id, ca.pk)
        self.assertEqual(situation.chiffre_affaires, Decimal('100'))
        self.assertEqual(situation.date_debut, date(2025, 1, 10))

    def test_situation_creation_without_ca_preserves_manual_work_revenue(self):
        response = self.client.post(reverse('projets:ajouter_situation_mensuelle', args=[self.projet.pk]), self.situation_post())
        self.assertEqual(response.status_code, 302)
        situation = SituationMensuelle.objects.get(projet=self.projet)
        self.assertIsNone(situation.ca_id)
        self.assertEqual(situation.chiffre_affaires, Decimal('99999'))

    def situation_edit_post(self, situation):
        data = self.situation_post()
        data['recettes-TOTAL_FORMS'] = '3'
        data['recettes-INITIAL_FORMS'] = '3'
        for i, recipe in enumerate(situation.recettes.order_by('pk')):
            data.update({
                f'recettes-{i}-id': recipe.pk,
                f'recettes-{i}-rubrique': recipe.rubrique,
                f'recettes-{i}-montant': {'TRAVAUX_REALISES': '99999', 'REVISION_PRIX': '22', 'REFACTURATION_EXTERNE': '6'}[recipe.rubrique],
            })
        return data

    def test_situation_edit_ignores_tampered_manual_work_revenue(self):
        situation = self.situation()
        self.save_ca()
        situation.refresh_from_db()
        response = self.client.post(
            reverse('projets:modifier_situation_mensuelle', args=[self.projet.pk, situation.pk]),
            self.situation_edit_post(situation),
        )
        self.assertEqual(response.status_code, 302, response.context and response.context['validation_errors'])
        situation.refresh_from_db()
        self.assertEqual(situation.chiffre_affaires, Decimal('128'))
        self.assertEqual(situation.recettes.get(rubrique='TRAVAUX_REALISES').montant, Decimal('100'))

    def test_situation_validated_after_form_read_cannot_be_overwritten(self):
        situation = self.situation()
        self.save_ca()
        situation.refresh_from_db()
        original_save = SituationMensuelleForm.save

        def validate_before_transaction(form, *args, **kwargs):
            instance = original_save(form, *args, **kwargs)
            SituationMensuelle.objects.filter(pk=instance.pk).update(statut='VALIDEE')
            return instance

        with patch.object(SituationMensuelleForm, 'save', new=validate_before_transaction):
            response = self.client.post(
                reverse('projets:modifier_situation_mensuelle', args=[self.projet.pk, situation.pk]),
                self.situation_edit_post(situation),
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Dévalidez la situation')
        situation.refresh_from_db()
        self.assertEqual(situation.statut, 'VALIDEE')
        self.assertEqual(situation.chiffre_affaires, Decimal('125'))
        self.assertEqual(situation.recettes.get(rubrique='REVISION_PRIX').montant, Decimal('20'))
