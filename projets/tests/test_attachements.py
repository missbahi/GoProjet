import json
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.test import RequestFactory
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile

from projets.models import (
    Attachement,
    CorrectionPeriodesAttachement,
    Decompte,
    Dossier,
    LigneBordereau,
    LotProjet,
    OrdreService,
    Projet,
    ProcessValidation,
    TypeOrdreService,
)
from projets.services.attachement_service import (
    DonneesAttachementInvalides,
    enregistrer_lignes_attachement,
)
from projets.views.attachement_views import views as attachement_views


class AttachementTestData:
    def setUp(self):
        super().setUp()
        self.projet = Projet.objects.create(
            nom="Projet test",
            objet="Objet du marché",
            numero="TEST-ATT-001",
            maitre_ouvrage="Maître d'ouvrage",
            localisation="Localisation",
        )
        type_osc, _ = TypeOrdreService.objects.get_or_create(
            code='OSC',
            defaults={
                'nom': "OS de commencement",
                'description': "Commencement du projet",
                'ordre_min': 1,
                'ordre_max': 1,
            },
        )
        OrdreService.objects.create(
            projet=self.projet,
            type_os=type_osc,
            reference="OSC-001",
            titre="Commencement",
            description="Début des travaux",
            date_publication=date(2025, 1, 1),
            date_effet=date(2025, 1, 10),
            statut='NOTIFIE',
            ordre_sequence=1,
        )
        self.lot = LotProjet.objects.create(projet=self.projet, nom="Lot test")
        self.ligne_bordereau = LigneBordereau.objects.create(
            lot=self.lot,
            numero="1",
            designation="Travaux",
            unite="m",
            quantite=Decimal('100'),
            prix_unitaire=Decimal('10'),
        )

    def create_attachement(self, sequence, debut, fin, statut='BROUILLON'):
        attachement = Attachement(
            projet=self.projet,
            numero=f"custom-{sequence}",
            date_etablissement=fin,
            date_debut_periode=debut,
            date_fin_periode=fin,
            statut=statut,
        )
        attachement.save()
        return attachement

    def create_os(self, code, effet, statut='NOTIFIE'):
        type_os, _ = TypeOrdreService.objects.get_or_create(
            code=code, defaults={'nom': code, 'description': code},
        )
        return OrdreService.objects.create(
            projet=self.projet, type_os=type_os, reference=f'{code}-{effet}',
            titre=code, description=code, date_publication=date(2025, 1, 1),
            date_effet=effet, statut=statut,
        )


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class SupprimerDecompteTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username='suppression-decompte')
        self.client.force_login(self.user)
        self.attachement = self.create_attachement(
            1, date(2025, 1, 10), date(2025, 1, 31), 'VALIDE',
        )
        self.decompte = Decompte.objects.create(
            attachement=self.attachement, numero='DEC-TEST', date_emission=date(2025, 1, 31),
        )
        self.url = reverse('projets:supprimer_decompte', args=[self.decompte.pk])

    def test_get_displays_confirmation_without_deleting(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projets/decomptes/supprimer_decompte.html')
        self.assertContains(response, 'DEC-TEST')
        self.assertContains(response, 'csrfmiddlewaretoken')
        self.assertContains(response, reverse('projets:liste_decomptes', args=[self.projet.pk]))
        self.assertTrue(Decompte.objects.filter(pk=self.decompte.pk).exists())

    def test_post_deletes_and_redirects_without_changing_attachment(self):
        avant = Attachement.objects.filter(pk=self.attachement.pk).values().get()
        response = self.client.post(self.url)
        self.assertRedirects(
            response, reverse('projets:liste_decomptes', args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(Decompte.objects.filter(pk=self.decompte.pk).exists())
        self.assertEqual(avant, Attachement.objects.filter(pk=self.attachement.pk).values().get())

    def test_payment_warning_and_existing_deletion_behavior(self):
        for changement in [{'statut': 'PAYE'}, {'statut': 'PARTIEL'}, {'date_paiement': date(2025, 2, 1)}]:
            Decompte.objects.filter(pk=self.decompte.pk).update(statut='BROUILLON', date_paiement=None)
            Decompte.objects.filter(pk=self.decompte.pk).update(**changement)
            response = self.client.get(self.url)
            self.assertContains(response, "aucun paiement réel.")
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertFalse(Decompte.objects.filter(pk=self.decompte.pk).exists())

    def test_access_denied_outside_project_and_allowed_inside(self):
        user = User.objects.create_user(username='suppression-non-membre')
        self.client.force_login(user)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.assertTrue(Decompte.objects.filter(pk=self.decompte.pk).exists())
        self.projet.users.add(user)
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_anonymous_unsupported_method_and_csrf(self):
        from django.test import Client
        self.assertEqual(self.client.delete(self.url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.user)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 302)
        self.assertEqual(self.client.post(self.url).status_code, 302)
        self.assertTrue(Decompte.objects.filter(pk=self.decompte.pk).exists())


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class ValidationDirecteTravauxTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(username='validation-directe')
        self.chef = User.objects.create_user(username='chef-validation-directe')
        self.chef.profile.role = 'CHEF_PROJET'
        self.chef.profile.save()
        self.dossier = Dossier.objects.create(nom='Dossier Travaux test', activite='TRAVAUX', gerant=self.chef)
        self.projet.dossier = self.dossier
        self.projet.save()
        self.attachement = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        self.url = reverse('projets:modifier_attachement', args=[self.attachement.pk])
        self.client.force_login(self.chef)

    def payload(self):
        return {
            'numero': self.attachement.numero, 'statut': 'VALIDE',
            'date_etablissement': '2025-01-31', 'date_debut_periode': '2025-01-10',
            'date_fin_periode': '2025-01-31',
            'lignes_attachement': json.dumps([{'id': self.ligne_bordereau.pk, 'quantite_realisee': '10'}]),
        }

    def compte_payload(self):
        return {
            'attachement': self.attachement.pk, 'type_decompte': 'PROVISOIRE',
            'numero': 'DEC-DIRECT', 'date_emission': '2025-01-31',
            'statut': 'VALIDE', 'taux_tva': '20', 'taux_retenue_garantie': '10',
            'taux_ras': '0', 'autres_retenues': '0', 'montant_revision_prix': '0',
        }

    def test_list_buttons_validate_and_devalidate_without_form(self):
        url = reverse('projets:changer_statut_attachement', args=[self.attachement.pk])
        liste = reverse('projets:liste_attachements', args=[self.projet.pk])
        for user in (self.chef, self.admin):
            with self.subTest(user=user):
                self.client.force_login(user)
                self.assertContains(self.client.get(liste), 'value="valider"')
                avant = Attachement.objects.filter(pk=self.attachement.pk).values().get()
                response = self.client.post(url, {'action': 'valider'}, follow=True)
                self.assertRedirects(response, liste)
                self.assertContains(response, 'a été validé.')
                self.assertContains(response, 'value="devalider"')
                self.assertNotContains(response, 'value="valider"')
                self.attachement.refresh_from_db()
                self.assertEqual(self.attachement.statut, 'VALIDE')
                self.assertEqual(self.attachement.modifie_par, user)
                apres = Attachement.objects.filter(pk=self.attachement.pk).values().get()
                for champ in avant:
                    if champ not in {'statut', 'modifie_par_id'}:
                        self.assertEqual(avant[champ], apres[champ], champ)
                response = self.client.post(url, {'action': 'devalider'}, follow=True)
                self.assertRedirects(response, liste)
                self.assertContains(response, 'a été dévalidé et remis en brouillon.')
                self.attachement.refresh_from_db()
                self.assertEqual(self.attachement.statut, 'BROUILLON')
                self.assertEqual(self.attachement.modifie_par, user)

    def test_list_validation_rejects_stop_dates_and_broken_continuity(self):
        url = reverse('projets:changer_statut_attachement', args=[self.attachement.pk])
        self.create_os('OSA', date(2025, 1, 20))
        response = self.client.post(url, {'action': 'valider'}, follow=True)
        self.assertContains(response, "La date de fin se situe dans une période", html=False)
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'BROUILLON')
        self.create_os('OSR', date(2025, 1, 25))
        Attachement.objects.filter(pk=self.attachement.pk).update(
            date_debut_periode=date(2025, 1, 11),
        )
        response = self.client.post(url, {'action': 'valider'}, follow=True)
        self.assertContains(response, 'La date de début doit correspondre')
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'BROUILLON')

    def test_list_actions_enforce_permissions_and_hide_buttons(self):
        url = reverse('projets:changer_statut_attachement', args=[self.attachement.pk])
        liste = reverse('projets:liste_attachements', args=[self.projet.pk])
        autre = User.objects.create_user(username='lecteur-attachement')
        self.dossier.utilisateurs.add(autre)
        self.client.force_login(autre)
        self.assertNotContains(self.client.get(liste), 'value="valider"')
        self.assertEqual(self.client.post(url, {'action': 'valider'}).status_code, 403)
        Attachement.objects.filter(pk=self.attachement.pk).update(statut='VALIDE')
        self.assertNotContains(self.client.get(liste), 'value="devalider"')
        self.assertEqual(self.client.post(url, {'action': 'devalider'}).status_code, 403)
        self.dossier.utilisateurs.remove(autre)
        self.assertEqual(self.client.post(url, {'action': 'devalider'}).status_code, 403)
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'VALIDE')

    def test_list_validation_preserves_other_activities_workflow(self):
        url = reverse('projets:changer_statut_attachement', args=[self.attachement.pk])
        for activite in ('SERVICES', 'FOURNITURES'):
            with self.subTest(activite=activite):
                self.dossier.activite = activite
                self.dossier.save()
                self.assertEqual(self.client.post(url, {'action': 'valider'}).status_code, 403)
                self.attachement.refresh_from_db()
                self.assertEqual(self.attachement.statut, 'BROUILLON')

    def test_list_actions_require_post_and_csrf(self):
        from django.test import Client

        url = reverse('projets:changer_statut_attachement', args=[self.attachement.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.chef)
        self.assertEqual(csrf_client.post(url, {'action': 'valider'}).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.post(url, {'action': 'valider'}).status_code, 302)
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'BROUILLON')

    def test_list_devalidation_resets_existing_validation_steps(self):
        self.attachement.statut = 'VALIDE'
        self.attachement.save()
        validation = ProcessValidation.objects.create(
            attachement=self.attachement, type_validation='TECHNIQUE',
            ordre_validation=1, statut_validation='VALIDE', validateur=self.chef,
            demandeur_validation=self.chef, commentaires='Validé', motifs_rejet='Ancien rejet',
        )
        url = reverse('projets:changer_statut_attachement', args=[self.attachement.pk])
        self.client.post(url, {'action': 'devalider'})
        validation.refresh_from_db()
        self.assertEqual(validation.statut_validation, 'EN_ATTENTE')
        self.assertIsNone(validation.validateur)
        self.assertEqual(validation.commentaires, '')
        self.assertEqual(validation.motifs_rejet, '')

    def test_list_action_notifies_project_users(self):
        from projets.models import Notification

        self.projet.users.add(self.chef)
        url = reverse('projets:changer_statut_attachement', args=[self.attachement.pk])
        self.client.post(url, {'action': 'valider'})
        self.assertTrue(Notification.objects.filter(
            utilisateur=self.chef, projet=self.projet, type_notification='ATTACHEMENT_VALIDE',
        ).exists())
        self.client.post(url, {'action': 'devalider'})
        self.assertTrue(Notification.objects.filter(
            utilisateur=self.chef, projet=self.projet, type_notification='ATTACHEMENT_BROUILLON',
        ).exists())

    def test_chef_and_superuser_can_validate_by_status_or_button(self):
        for user, action in [(self.chef, {}), (self.admin, {'statut': 'BROUILLON', 'action': 'valider'})]:
            with self.subTest(user=user):
                Attachement.objects.filter(pk=self.attachement.pk).update(statut='BROUILLON')
                self.client.force_login(user)
                page = self.client.get(self.url)
                self.assertContains(page, 'value="valider"')
                self.assertContains(page, '<option value="VALIDE"', html=False)
                response = self.client.post(self.url, {**self.payload(), **action})
                self.assertEqual(response.status_code, 302)
                self.attachement.refresh_from_db()
                self.assertEqual(self.attachement.statut, 'VALIDE')
                self.assertEqual(self.attachement.modifie_par_id, user.pk)
                self.assertFalse(self.attachement.validations.exists())

    def test_signed_transmitted_refused_and_modified_can_be_validated(self):
        for statut in ['SIGNE', 'TRANSMIS', 'REFUSE', 'MODIFIE']:
            with self.subTest(statut=statut):
                Attachement.objects.filter(pk=self.attachement.pk).update(statut=statut)
                self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)
                self.attachement.refresh_from_db()
                self.assertEqual(self.attachement.statut, 'VALIDE')

    def test_creation_can_be_validated_directly(self):
        self.attachement.delete()
        response = self.client.post(
            reverse('projets:ajouter_attachement', args=[self.projet.pk]), self.payload(),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Attachement.objects.get(projet=self.projet).statut, 'VALIDE')

    def test_other_activities_keep_workflow(self):
        for activite in ['SERVICES', 'FOURNITURES']:
            self.dossier.activite = activite
            self.dossier.save()
            response = self.client.post(self.url, self.payload())
            self.assertEqual(response.status_code, 200)
            self.assertIn('statut', response.context['form'].errors)
            self.attachement.refresh_from_db()
            self.assertEqual(self.attachement.statut, 'BROUILLON')

    def test_unauthorized_role_or_project_cannot_validate(self):
        autre = User.objects.create_user(username='autre-validation')
        self.dossier.utilisateurs.add(autre)
        self.client.force_login(autre)
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertIn('statut', response.context['form'].errors)
        autre.profile.role = 'CHEF_PROJET'
        autre.profile.save()
        self.dossier.utilisateurs.remove(autre)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)

    def test_direct_validation_keeps_period_constraints(self):
        for changements in [{'date_debut_periode': '2025-01-11'}, {'date_fin_periode': '2025-01-09'}]:
            response = self.client.post(self.url, {**self.payload(), **changements})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].errors)
        self.create_os('OSA', date(2025, 1, 20))
        response = self.client.post(self.url, self.payload())
        self.assertIn('date_fin_periode', response.context['form'].errors)
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'BROUILLON')

    def test_workflow_page_does_not_create_steps_for_travaux(self):
        Attachement.objects.filter(pk=self.attachement.pk).update(statut='TRANSMIS')
        response = self.client.get(reverse('projets:validation_attachement', args=[self.attachement.pk]))
        self.assertRedirects(response, self.url, fetch_redirect_response=False)
        self.assertFalse(self.attachement.validations.exists())
        self.attachement.initialiser_processus_validation(self.chef)
        self.assertFalse(self.attachement.validations.exists())

    def test_existing_workflow_is_preserved_but_does_not_override_direct_validation(self):
        validation = ProcessValidation.objects.create(
            attachement=self.attachement, type_validation='TECHNIQUE',
            ordre_validation=1, statut_validation='REJETE', demandeur_validation=self.chef,
        )
        avant = ProcessValidation.objects.filter(pk=validation.pk).values().get()
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 302)
        self.assertEqual(avant, ProcessValidation.objects.filter(pk=validation.pk).values().get())
        validation.commentaires = 'Ancien workflow'
        validation.save()
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'VALIDE')

    def test_decompte_direct_status_and_button_require_authorized_role(self):
        url = reverse('projets:liste_decomptes', args=[self.projet.pk])
        for user, action in [(self.chef, {}), (self.admin, {'statut': 'BROUILLON', 'action_validation': 'valider'})]:
            self.client.force_login(user)
            response = self.client.post(url, {**self.compte_payload(), **action})
            self.assertEqual(response.status_code, 302)
            compte = Decompte.objects.get(attachement=self.attachement)
            self.assertEqual(compte.statut, 'VALIDE')
            compte.delete()
        autre = User.objects.create_user(username='compte-non-chef')
        self.dossier.utilisateurs.add(autre)
        self.client.force_login(autre)
        response = self.client.post(url, self.compte_payload())
        self.assertEqual(response.status_code, 200)
        self.assertIn('statut', response.context['form'].errors)
        self.assertFalse(Decompte.objects.filter(attachement=self.attachement).exists())

    def test_paid_decompte_cannot_be_reclassified_as_validated(self):
        compte = Decompte.objects.create(
            attachement=self.attachement, numero='PAYE', date_emission=date(2025, 1, 31), statut='PAYE',
        )
        response = self.client.post(
            reverse('projets:liste_decomptes', args=[self.projet.pk]),
            {**self.compte_payload(), 'decompte_id': compte.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('statut', response.context['form'].errors)
        compte.refresh_from_db()
        self.assertEqual(compte.statut, 'PAYE')


class AttachementArretTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.create_os('OSA', date(2025, 1, 20))
        self.create_os('OSR', date(2025, 1, 25))
        self.attachement = self.create_attachement(
            1, date(2025, 1, 10), date(2025, 1, 22),
        )

    def test_draft_remains_editable_but_transmission_is_blocked(self):
        self.attachement.observations = 'Brouillon'
        self.attachement.full_clean()
        self.attachement.save()
        self.attachement.statut = 'TRANSMIS'
        for operation in (self.attachement.full_clean, self.attachement.save):
            with self.subTest(operation=operation):
                with self.assertRaises(ValidationError) as caught:
                    operation()
                message = caught.exception.message_dict['date_fin_periode'][0]
                self.assertIn('19/01/2025', message)
                self.assertIn('25/01/2025', message)
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'BROUILLON')

    def test_stop_included_resume_excluded_and_other_dates_allowed(self):
        for jour in (19, 20, 24, 25, 26):
            with self.subTest(jour=jour):
                if 20 <= jour < 25:
                    with self.assertRaises(ValidationError):
                        self.attachement.verifier_fin_periode_hors_arret(date(2025, 1, jour))
                else:
                    self.attachement.verifier_fin_periode_hors_arret(date(2025, 1, jour))

    def test_begin_date_uses_same_stop_boundaries(self):
        for jour in (19, 20, 24, 25, 26):
            with self.subTest(jour=jour):
                if 20 <= jour < 25:
                    with self.assertRaises(ValidationError) as caught:
                        self.attachement.verifier_debut_periode_hors_arret(date(2025, 1, jour))
                    self.assertIn('date_debut_periode', caught.exception.message_dict)
                else:
                    self.attachement.verifier_debut_periode_hors_arret(date(2025, 1, jour))

    def test_following_attachment_starts_on_resume_when_continuity_falls_in_stop(self):
        self.attachement.date_fin_periode = date(2025, 1, 19)
        self.attachement.statut = 'SIGNE'
        self.attachement.save()

        suivant = self.create_attachement(
            2, date(2025, 1, 25), date(2025, 2, 1),
        )

        self.assertEqual(suivant.date_debut_periode, date(2025, 1, 25))

    def test_open_stop_and_multiple_periods(self):
        self.create_os('OSA', date(2025, 2, 10))
        with self.assertRaises(ValidationError) as caught:
            self.attachement.verifier_fin_periode_hors_arret(date(2025, 2, 28))
        message = caught.exception.message_dict['date_fin_periode'][0]
        self.assertIn('09/02/2025', message)
        self.assertIn('reprise', message)
        self.create_os('OSR', date(2025, 3, 5))
        self.attachement.verifier_fin_periode_hors_arret(date(2025, 3, 5))
        with self.assertRaises(ValidationError):
            self.attachement.verifier_fin_periode_hors_arret(date(2025, 2, 28))
        self.attachement.verifier_fin_periode_hors_arret(date(2025, 2, 9))

    def test_unnotified_or_undated_orders_are_ignored(self):
        self.create_os('OSR', date(2025, 1, 21), statut='BROUILLON')
        with self.assertRaises(ValidationError):
            self.attachement.verifier_fin_periode_hors_arret(date(2025, 1, 22))
        self.create_os('OSA', date(2025, 2, 10), statut='BROUILLON')
        self.create_os('OSR', date(2025, 2, 20), statut='BROUILLON')
        self.create_os('OSA', None)
        self.attachement.verifier_fin_periode_hors_arret(date(2025, 2, 15))

    def test_creation_as_transmitted_cannot_bypass_check(self):
        self.attachement.delete()
        with self.assertRaises(ValidationError):
            self.create_attachement(
                1, date(2025, 1, 10), date(2025, 1, 22), 'TRANSMIS',
            )

    def test_transmission_rejects_begin_date_during_stop(self):
        self.attachement.date_debut_periode = date(2025, 1, 22)
        self.attachement.statut = 'TRANSMIS'

        with self.assertRaises(ValidationError) as caught:
            self.attachement.full_clean()

        self.assertIn('date_debut_periode', caught.exception.message_dict)
        self.assertIn("période d'arrêt", caught.exception.message_dict['date_debut_periode'][0])

    def test_transmission_at_resume_is_allowed(self):
        self.attachement.date_fin_periode = date(2025, 1, 25)
        self.attachement.statut = 'TRANSMIS'
        self.attachement.full_clean()
        self.attachement.save()
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'TRANSMIS')


class AttachementContinuiteArretTests(AttachementTestData, TestCase):
    def test_first_attachment_starts_on_resume_if_project_start_falls_in_stop(self):
        self.create_os('OSA', date(2025, 1, 10))
        self.create_os('OSR', date(2025, 1, 25))

        attachement = self.create_attachement(
            1, date(2025, 1, 25), date(2025, 2, 1),
        )

        self.assertEqual(attachement.date_debut_periode, date(2025, 1, 25))

    def test_first_attachment_waits_for_notified_resume_during_open_stop(self):
        self.create_os('OSA', date(2025, 1, 10))
        attachement = Attachement(
            projet=self.projet,
            numero='custom-1',
            date_etablissement=date(2025, 1, 31),
            date_debut_periode=date(2025, 1, 10),
            date_fin_periode=date(2025, 1, 31),
        )

        with self.assertRaises(ValidationError) as caught:
            attachement.save()

        self.assertIn('date_debut_periode', caught.exception.message_dict)

@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class AttachementTableViewTemplateTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username='tableview-test')
        self.client.force_login(self.user)
        self.attachement = self.create_attachement(
            1, date(2025, 1, 10), date(2025, 1, 31),
        )
        self.url = reverse('projets:modifier_attachement', args=[self.attachement.pk])

    def test_creation_prefills_resume_date_when_next_day_falls_into_stop(self):
        self.attachement.date_fin_periode = date(2025, 1, 19)
        self.attachement.statut = 'SIGNE'
        self.attachement.save()
        self.create_os('OSA', date(2025, 1, 20))
        self.create_os('OSR', date(2025, 1, 25))

        response = self.client.get(
            reverse('projets:ajouter_attachement', args=[self.projet.pk]),
        )

        self.assertEqual(response.context['date_debut_periode'], date(2025, 1, 25))

    def test_default_form_uses_direct_tableview_template(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projets/decomptes/attachement_form.html')
        self.assertContains(response, 'js/table-view.js')
        self.assertNotContains(response, 'new Handsontable(')

    def test_tableview_form_reuses_fields_without_loading_handsontable(self):
        response = self.client.get(self.url, {'tableview': '1'})
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'projets/decomptes/_attachement_form_content_test.html')
        self.assertContains(response, 'js/table-view.js')
        self.assertContains(response, 'js/attachement-tableview.js')
        self.assertContains(response, 'id="attachement-tableview"')
        self.assertContains(response, 'id="date_fin_periode"')
        self.assertContains(response, 'id="save-btn"')
        self.assertNotContains(response, 'handsontable')
        self.assertNotContains(response, 'new Handsontable(')

    def test_create_form_can_also_use_tableview(self):
        response = self.client.get(
            reverse('projets:ajouter_attachement', args=[self.projet.pk]),
            {'tableview': '1'},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="attachement-tableview"')
        self.assertNotContains(response, 'new Handsontable(')

    def test_tableview_post_saves_existing_payload(self):
        response = self.client.post(f'{self.url}?tableview=1', {
            'numero': self.attachement.numero,
            'date_etablissement': '2025-01-31',
            'date_debut_periode': '2025-01-10',
            'date_fin_periode': '2025-01-31',
            'statut': 'BROUILLON',
            'observations': 'Essai TableView',
            'lignes_attachement': json.dumps([
                {'id': self.ligne_bordereau.pk, 'quantite_realisee': 12.345},
            ]),
        })
        self.assertRedirects(
            response,
            reverse('projets:liste_attachements', args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        self.assertEqual(
            self.attachement.lignes_attachement.get().quantite_realisee,
            Decimal('12.345'),
        )

    def test_invalid_post_keeps_tableview_variant(self):
        response = self.client.post(f'{self.url}?tableview=1', {})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="attachement-tableview"')
        self.assertNotContains(response, 'new Handsontable(')

    def test_creation_errors_render_without_internal_keys_or_double_escaping(self):
        url = reverse('projets:ajouter_attachement', args=[self.projet.pk])
        payload = {
            'numero': 'DP02',
            'date_etablissement': '2025-02-28',
            'date_debut_periode': '2025-02-01',
            'date_fin_periode': '2025-02-28',
            'statut': 'BROUILLON',
        }
        for suffix in ('', '?tableview=1'):
            with self.subTest(suffix=suffix):
                response = self.client.post(url + suffix, payload)
                self.assertEqual(response.status_code, 200)
                self.assertContains(
                    response,
                    "<li>L'attachement précédent doit être signé ou validé avant de créer le suivant.</li>",
                    html=True,
                )
                self.assertNotContains(response, '__all__')
                self.assertNotContains(response, '&amp;#x27;')

    def test_field_errors_show_human_readable_labels(self):
        response = self.client.post(self.url, {})
        self.assertContains(response, 'Date fin période')
        self.assertContains(response, 'Ce champ est obligatoire.')
        self.assertContains(response, 'data-persistent-action-message')

    def test_transmission_displays_stop_period_error_on_end_date(self):
        self.create_os('OSA', date(2025, 1, 20))
        self.create_os('OSR', date(2025, 2, 5))
        payload = {
            'numero': self.attachement.numero, 'statut': 'BROUILLON',
            'date_etablissement': '2025-01-31',
            'date_debut_periode': '2025-01-10',
            'date_fin_periode': '2025-01-31',
        }
        self.assertEqual(self.client.post(self.url, payload).status_code, 302)
        response = self.client.post(self.url, {**payload, 'statut': 'TRANSMIS'})
        self.assertContains(response, '19/01/2025')
        self.assertContains(response, '05/02/2025')
        self.assertIn('date_fin_periode', response.context['form'].errors)
        self.attachement.refresh_from_db()
        self.assertEqual(self.attachement.statut, 'BROUILLON')

    def test_existing_inconsistent_dates_can_be_saved_but_not_transmitted(self):
        Attachement.objects.filter(pk=self.attachement.pk).update(
            date_debut_periode=date(2025, 1, 11),
        )
        payload = {
            'numero': self.attachement.numero,
            'date_etablissement': '2025-01-31',
            'date_debut_periode': '2025-01-11',
            'date_fin_periode': '2025-01-31',
            'statut': 'BROUILLON',
            'observations': 'Modification autorisée',
        }
        for suffix in ('', '?tableview=1'):
            with self.subTest(suffix=suffix):
                response = self.client.post(self.url + suffix, payload)
                self.assertEqual(response.status_code, 302)
                payload['statut'] = 'TRANSMIS'
                response = self.client.post(self.url + suffix, payload)
                self.assertContains(response, 'La date de début doit correspondre')
                self.attachement.refresh_from_db()
                self.assertEqual(self.attachement.statut, 'BROUILLON')
                payload['statut'] = 'BROUILLON'

    def test_previous_attachment_is_identified_in_both_forms(self):
        self.attachement.statut = 'SIGNE'
        self.attachement.save()
        suivant = self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))
        url = reverse('projets:modifier_attachement', args=[suivant.pk])
        for suffix in ('', '?tableview=1'):
            with self.subTest(suffix=suffix):
                response = self.client.get(url + suffix)
                self.assertEqual(response.context['attachement_precedent'], self.attachement)
                self.assertContains(response, 'Attachement précédent')
                self.assertContains(response, 'DP01')
                self.assertContains(response, '31/01/2025')
                self.assertContains(
                    response,
                    reverse('projets:detail_attachement', args=[self.attachement.pk]),
                )


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class CorrectionPeriodesTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username='correction-admin')
        self.client.force_login(self.user)
        self.premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31), 'VALIDE')
        self.suivant = self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28), 'VALIDE')
        enregistrer_lignes_attachement(
            self.suivant,
            json.dumps([{'id': self.ligne_bordereau.pk, 'quantite_realisee': '10'}]),
        )
        self.validation = ProcessValidation.objects.create(
            attachement=self.premier, type_validation='TECHNIQUE',
            ordre_validation=1, statut_validation='VALIDE', validateur=self.user,
            demandeur_validation=self.user,
        )
        self.url = reverse('projets:corriger_periodes_attachements', args=[self.projet.pk])

    def payload(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        return {
            'instantane': response.context['form']['instantane'].value(),
            'motif': 'Régularisation des périodes historiques',
            f'date_debut_periode_{self.premier.pk}': '2025-01-10',
            f'date_fin_periode_{self.premier.pk}': '2025-01-30',
            f'date_debut_periode_{self.suivant.pk}': '2025-01-31',
            f'date_fin_periode_{self.suivant.pk}': '2025-02-28',
            'action': 'apercu',
        }

    def test_historical_preview_rejects_end_date_during_stop(self):
        self.create_os('OSA', date(2025, 1, 20))
        self.create_os('OSR', date(2025, 2, 5))
        response = self.client.post(self.url, self.payload())
        self.assertIn(
            f'date_fin_periode_{self.premier.pk}', response.context['form'].errors,
        )
        self.assertContains(response, '19/01/2025')
        self.assertFalse(response.context['apercu'])
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_historical_preview_accepts_day_before_stop_and_resume(self):
        self.create_os('OSA', date(2025, 1, 20))
        self.create_os('OSR', date(2025, 2, 5))
        for fin, debut_suivant in [('2025-01-19', '2025-02-05'), ('2025-02-05', '2025-02-06')]:
            with self.subTest(fin=fin):
                payload = self.payload()
                payload.update({
                    f'date_fin_periode_{self.premier.pk}': fin,
                    f'date_debut_periode_{self.suivant.pk}': debut_suivant,
                })
                response = self.client.post(self.url, payload)
                self.assertTrue(response.context['apercu'], response.context['form'].errors)
                self.premier.refresh_from_db()
                self.assertEqual(self.premier.date_fin_periode, date(2025, 1, 31))

    def test_historical_confirmation_rechecks_new_stop(self):
        payload = self.payload()
        preview = self.client.post(self.url, payload)
        self.assertTrue(preview.context['apercu'])
        self.create_os('OSA', date(2025, 1, 20))
        response = self.client.post(self.url, {
            **payload, 'action': 'confirmer',
            'confirmation': preview.context['confirmation_token'],
        })
        self.assertIn(
            f'date_fin_periode_{self.premier.pk}', response.context['form'].errors,
        )
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.date_fin_periode, date(2025, 1, 31))

    def test_preview_confirmation_and_audit_preserve_validations_and_finances(self):
        avant = list(Attachement.objects.filter(projet=self.projet).values(
            'id', 'statut', 'montant_ht', 'date_etablissement', 'modifie_par_id',
        ))
        lignes_avant = list(self.suivant.lignes_attachement.values())
        validation_avant = ProcessValidation.objects.filter(pk=self.validation.pk).values().get()
        payload = self.payload()
        response = self.client.post(self.url, payload)
        self.assertTrue(response.context['apercu'])
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.date_fin_periode, date(2025, 1, 31))
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())
        payload.update(action='confirmer', confirmation=response.context['confirmation_token'])
        response = self.client.post(self.url, payload)
        self.assertRedirects(response, self.url)
        self.premier.refresh_from_db()
        self.suivant.refresh_from_db()
        self.assertEqual(self.premier.date_fin_periode, date(2025, 1, 30))
        self.assertEqual(self.suivant.date_debut_periode, date(2025, 1, 31))
        self.assertEqual(avant, list(Attachement.objects.filter(projet=self.projet).values(
            'id', 'statut', 'montant_ht', 'date_etablissement', 'modifie_par_id',
        )))
        self.assertEqual(lignes_avant, list(self.suivant.lignes_attachement.values()))
        self.assertEqual(validation_avant, ProcessValidation.objects.filter(pk=self.validation.pk).values().get())
        journal = CorrectionPeriodesAttachement.objects.get()
        self.assertEqual(journal.auteur, self.user)
        self.assertEqual(journal.motif, payload['motif'])
        self.assertEqual(len(journal.modifications), 2)
        self.assertEqual(journal.modifications[0]['ancienne_fin'], '2025-01-31')
        self.assertEqual(journal.modifications[0]['nouvelle_fin'], '2025-01-30')
        self.assertContains(self.client.get(self.url), payload['motif'])

    def test_staff_is_not_authorized_even_with_post(self):
        staff = User.objects.create_user(username='staff-correction', is_staff=True)
        payload = self.payload()
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, payload).status_code, 403)
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_inconsistent_chain_inverted_dates_and_missing_reason_are_rejected(self):
        payload = self.payload()
        for field, value in [
            (f'date_debut_periode_{self.suivant.pk}', '2025-02-01'),
            (f'date_fin_periode_{self.premier.pk}', '2025-01-09'),
            ('motif', ''),
            (f'date_debut_periode_{self.premier.pk}', '2025-01-11'),
        ]:
            with self.subTest(field=field):
                response = self.client.post(self.url, {**payload, field: value})
                self.assertTrue(response.context['form'].errors)
                self.assertFalse(response.context['apercu'])
                self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_confirmation_requires_unchanged_preview(self):
        payload = self.payload()
        direct = self.client.post(self.url, {**payload, 'action': 'confirmer'})
        self.assertTrue(direct.context['form'].errors)
        preview = self.client.post(self.url, payload)
        payload.update(action='confirmer', confirmation=preview.context['confirmation_token'], motif='Autre motif')
        response = self.client.post(self.url, payload)
        self.assertContains(response, 'La correction a changé.')
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_concurrent_period_or_status_change_is_rejected(self):
        for changement in [{'statut': 'BROUILLON'}, {'date_fin_periode': date(2025, 3, 1)}]:
            with self.subTest(changement=changement):
                payload = self.payload()
                preview = self.client.post(self.url, payload)
                payload.update(action='confirmer', confirmation=preview.context['confirmation_token'])
                Attachement.objects.filter(pk=self.suivant.pk).update(**changement)
                response = self.client.post(self.url, payload)
                self.assertContains(response, "Les attachements ont changé")
                self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_audit_failure_rolls_back_all_dates(self):
        payload = self.payload()
        preview = self.client.post(self.url, payload)
        payload.update(action='confirmer', confirmation=preview.context['confirmation_token'])
        with patch.object(CorrectionPeriodesAttachement.objects, 'create', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, payload)
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.date_fin_periode, date(2025, 1, 31))
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_return_to_editing_does_not_save(self):
        payload = self.payload()
        preview = self.client.post(self.url, payload)
        response = self.client.post(self.url, {
            **payload, 'action': 'modifier', 'confirmation': preview.context['confirmation_token'],
        })
        self.assertFalse(response.context['apercu'])
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_expired_or_tampered_snapshot_is_rejected(self):
        payload = self.payload()
        response = self.client.post(self.url, {**payload, 'instantane': payload['instantane'] + 'invalid'})
        self.assertContains(response, 'La session de correction a expiré.')
        from django.core import signing
        with patch.object(signing.time, 'time', return_value=signing.time.time() + 3601):
            response = self.client.post(self.url, payload)
        self.assertContains(response, 'La session de correction a expiré.')
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class CorrectionOrdreTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(username='admin-ordre')
        self.client.force_login(self.admin)
        self.attachements = []
        self.decomptes = []
        for rang, debut, fin, cumul in [
            (1, date(2025, 1, 10), date(2025, 1, 31), '20'),
            (2, date(2025, 2, 1), date(2025, 2, 28), '10'),
            (3, date(2025, 3, 1), date(2025, 3, 31), '30'),
        ]:
            attachement = self.create_attachement(rang, debut, fin, 'VALIDE')
            enregistrer_lignes_attachement(attachement, json.dumps([
                {'id': self.ligne_bordereau.pk, 'quantite_realisee': cumul},
            ]))
            self.attachements.append(attachement)
            self.decomptes.append(Decompte.objects.create(
                attachement=attachement, numero=f'D{rang}', date_emission=fin,
                taux_tva=20, taux_retenue_garantie=10, taux_ras=2,
                montant_revision_prix=5, autres_retenues=3, statut='VALIDE',
            ))
        self.a, self.b, self.c = self.attachements
        self.validation = ProcessValidation.objects.create(
            attachement=self.a, type_validation='TECHNIQUE', ordre_validation=1,
            statut_validation='VALIDE', validateur=self.admin, demandeur_validation=self.admin,
        )
        self.url = reverse('projets:corriger_periodes_attachements', args=[self.projet.pk])

    def payload(self, reordonner=True):
        page = self.client.get(self.url)
        payload = {
            'instantane': page.context['form']['instantane'].value(),
            'motif': 'Corriger le classement historique', 'action': 'apercu',
        }
        ordre = [self.b, self.a, self.c] if reordonner else self.attachements
        for attachement, debut, fin in zip(ordre, ['2025-01-10', '2025-02-01', '2025-03-01'],
                                          ['2025-01-31', '2025-02-28', '2025-03-31']):
            payload[f'date_debut_periode_{attachement.pk}'] = debut
            payload[f'date_fin_periode_{attachement.pk}'] = fin
        return payload

    def etat(self):
        return (
            list(Attachement.objects.filter(projet=self.projet).order_by('pk').values()),
            list(Decompte.objects.filter(attachement__projet=self.projet).order_by('pk').values()),
        )

    def confirmer(self, payload, preview):
        return self.client.post(self.url, {
            **payload, 'action': 'confirmer', 'confirmation': preview.context['confirmation_token'],
        })

    def test_preview_sorts_new_dates_and_displays_finances_without_writes(self):
        avant = self.etat()
        preview = self.client.post(self.url, self.payload())
        self.assertTrue(preview.context['apercu'], preview.context['form'].errors)
        self.assertEqual([l['attachement'].pk for l in preview.context['lignes']],
                         [self.b.pk, self.a.pk, self.c.pk])
        self.assertEqual([l['proposition']['numero'] for l in preview.context['lignes']],
                         ['DP01', 'DP02', 'DP03'])
        self.assertContains(preview, 'Impacts financiers')
        self.assertContains(preview, 'Décompte D1')
        self.assertContains(preview, f'ID {self.b.pk}')
        self.assertEqual(self.etat(), avant)
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_confirmation_rebuilds_chain_numbers_and_all_affected_finances(self):
        lignes_avant = list(self.a.lignes_attachement.values())
        validation_avant = ProcessValidation.objects.filter(pk=self.validation.pk).values().get()
        payload = self.payload()
        preview = self.client.post(self.url, payload)
        self.assertRedirects(self.confirmer(payload, preview), self.url)
        ordre = list(Attachement.objects.filter(projet=self.projet).order_by('sequence'))
        self.assertEqual([a.pk for a in ordre], [self.b.pk, self.a.pk, self.c.pk])
        self.assertEqual([a.numero for a in ordre], ['DP01', 'DP02', 'DP03'])
        self.assertEqual([a.sequence for a in ordre], [1, 2, 3])
        self.assertEqual([a.precedent_id for a in ordre], [None, self.b.pk, self.a.pk])
        self.assertEqual([a.montant_ht for a in ordre], [Decimal('100')] * 3)
        for decompte in self.decomptes:
            decompte.refresh_from_db()
            self.assertEqual(decompte.montant_ht, Decimal('105'))
            self.assertEqual(decompte.montant_tva, Decimal('21'))
            self.assertEqual(decompte.montant_ttc, Decimal('126'))
            self.assertEqual(decompte.montant_net_a_payer, Decimal('110.40'))
            self.assertEqual(decompte.statut, 'VALIDE')
        self.assertEqual(lignes_avant, list(self.a.lignes_attachement.values()))
        self.assertEqual(validation_avant, ProcessValidation.objects.filter(pk=self.validation.pk).values().get())
        self.assertEqual([a.statut for a in ordre], ['VALIDE'] * 3)
        journal = CorrectionPeriodesAttachement.objects.get()
        changement_b = next(m for m in journal.modifications if m['id'] == self.b.pk)
        self.assertEqual(changement_b['nouveau_numero'], 'DP01')
        self.assertEqual(changement_b['nouvelle_sequence'], 1)
        self.assertIsNone(changement_b['nouveau_precedent_id'])
        self.assertTrue(changement_b['decompte'])
        self.assertContains(self.client.get(self.url), 'séquence 2 → 1')

    def test_broken_links_and_sequence_gaps_are_repaired_without_changing_dates(self):
        Attachement.objects.filter(pk=self.a.pk).update(sequence=7, precedent=self.c, numero='Ancien-A')
        Attachement.objects.filter(pk=self.b.pk).update(sequence=9, precedent=None, numero='Ancien-B')
        Attachement.objects.filter(pk=self.c.pk).update(sequence=2147483647, precedent=self.a)
        payload = self.payload(reordonner=False)
        preview = self.client.post(self.url, payload)
        self.assertTrue(preview.context['apercu'], preview.context['form'].errors)
        self.assertRedirects(self.confirmer(payload, preview), self.url)
        ordre = list(Attachement.objects.filter(projet=self.projet).order_by('sequence'))
        self.assertEqual([a.pk for a in ordre], [self.a.pk, self.b.pk, self.c.pk])
        self.assertEqual([a.sequence for a in ordre], [1, 2, 3])
        self.assertEqual([a.precedent_id for a in ordre], [None, self.a.pk, self.b.pk])
        self.assertEqual([a.numero for a in ordre], ['DP01', 'DP02', 'DP03'])

    def test_paid_accounts_or_payment_date_block_reordering_without_writes(self):
        for decompte in self.decomptes:
            for paiement in [{'statut': 'PAYE'}, {'statut': 'PARTIEL'}, {'date_paiement': date(2025, 4, 1)}]:
                with self.subTest(decompte=decompte.pk, paiement=paiement):
                    Decompte.objects.filter(pk=decompte.pk).update(**paiement)
                    avant = self.etat()
                    preview = self.client.post(self.url, self.payload())
                    self.assertFalse(preview.context['apercu'])
                    self.assertContains(preview, 'Correction bloquée')
                    self.assertEqual(self.etat(), avant)
                    Decompte.objects.filter(pk=decompte.pk).update(statut='VALIDE', date_paiement=None)

    def test_paid_unaffected_successor_does_not_block_reordering(self):
        dernier = self.create_attachement(4, date(2025, 4, 1), date(2025, 4, 30), 'VALIDE')
        enregistrer_lignes_attachement(dernier, json.dumps([
            {'id': self.ligne_bordereau.pk, 'quantite_realisee': '40'},
        ]))
        compte = Decompte.objects.create(
            attachement=dernier, numero='D4', date_emission=date(2025, 4, 30), statut='PAYE',
        )
        avant = Decompte.objects.filter(pk=compte.pk).values().get()
        payload = self.payload()
        payload.update({
            f'date_debut_periode_{dernier.pk}': '2025-04-01',
            f'date_fin_periode_{dernier.pk}': '2025-04-30',
        })
        preview = self.client.post(self.url, payload)
        self.assertTrue(preview.context['apercu'], preview.context['form'].errors)
        self.assertRedirects(self.confirmer(payload, preview), self.url)
        self.assertEqual(avant, Decompte.objects.filter(pk=compte.pk).values().get())

    def test_financial_or_link_change_invalidates_confirmation(self):
        changements = [
            (Decompte.objects.filter(pk=self.decomptes[0].pk), {'taux_tva': Decimal('19')}),
            (self.a.lignes_attachement.all(), {'quantite_realisee': Decimal('21')}),
            (Attachement.objects.filter(pk=self.c.pk), {'precedent_id': self.a.pk}),
        ]
        for queryset, changement in changements:
            with self.subTest(changement=changement):
                payload = self.payload()
                preview = self.client.post(self.url, payload)
                self.assertTrue(preview.context['apercu'], preview.context['form'].errors)
                queryset.update(**changement)
                avant = self.etat()
                response = self.confirmer(payload, preview)
                self.assertContains(response, 'Les attachements ont changé')
                self.assertEqual(self.etat(), avant)
                self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_audit_failure_rolls_back_order_numbers_dates_and_finances(self):
        avant = self.etat()
        payload = self.payload()
        preview = self.client.post(self.url, payload)
        with patch.object(CorrectionPeriodesAttachement.objects, 'create', side_effect=RuntimeError('audit failed')):
            with self.assertRaises(RuntimeError):
                self.confirmer(payload, preview)
        self.assertEqual(avant, self.etat())

    def test_duplicate_start_dates_are_rejected_without_writes(self):
        payload = self.payload()
        payload[f'date_debut_periode_{self.a.pk}'] = '2025-01-10'
        avant = self.etat()
        preview = self.client.post(self.url, payload)
        self.assertTrue(preview.context['form'].errors)
        self.assertFalse(preview.context['apercu'])
        self.assertEqual(avant, self.etat())

    def test_manager_can_repair_only_authorized_project(self):
        manager = User.objects.create_user(username='manager-ordre')
        manager.profile.role = 'CHEF_PROJET'
        manager.profile.save()
        payload = self.payload()
        self.client.force_login(manager)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, payload).status_code, 403)
        self.projet.users.add(manager)
        payload = self.payload()
        preview = self.client.post(self.url, payload)
        self.assertTrue(preview.context['apercu'], preview.context['form'].errors)
        self.assertRedirects(self.confirmer(payload, preview), self.url)

    def test_confirmation_does_not_accept_a_changed_order_or_no_preview(self):
        payload = self.payload()
        avant = self.etat()
        direct = self.client.post(self.url, {**payload, 'action': 'confirmer'})
        self.assertIn(
            "Affichez l'aperçu avant de confirmer la correction.",
            direct.context['form'].non_field_errors(),
        )
        preview = self.client.post(self.url, payload)
        changed = {
            **payload,
            f'date_fin_periode_{self.b.pk}': '2025-01-30',
            f'date_debut_periode_{self.a.pk}': '2025-01-31',
        }
        response = self.confirmer(changed, preview)
        self.assertContains(response, 'La correction a changé')
        self.assertEqual(avant, self.etat())


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class CorrectionExceptionnelleTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.admin = User.objects.create_superuser(username='admin-exception')
        self.client.force_login(self.admin)
        self.premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31), 'VALIDE')
        enregistrer_lignes_attachement(
            self.premier, json.dumps([{'id': self.ligne_bordereau.pk, 'quantite_realisee': '10'}]),
        )
        self.suivant = self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28), 'VALIDE')
        enregistrer_lignes_attachement(
            self.suivant, json.dumps([{'id': self.ligne_bordereau.pk, 'quantite_realisee': '20'}]),
        )
        self.validation = ProcessValidation.objects.create(
            attachement=self.premier, type_validation='TECHNIQUE',
            ordre_validation=1, statut_validation='VALIDE', validateur=self.admin,
            demandeur_validation=self.admin,
        )
        self.decompte = Decompte.objects.create(
            attachement=self.premier, numero='D1', date_emission=date(2025, 1, 31),
        )
        self.decompte_suivant = Decompte.objects.create(
            attachement=self.suivant, numero='D2', date_emission=date(2025, 2, 28),
        )
        self.url = reverse('projets:modifier_attachement', args=[self.premier.pk])

    def payload(self, quantite='15'):
        return {
            'numero': self.premier.numero, 'statut': 'BROUILLON',
            'date_etablissement': '2025-01-31', 'date_debut_periode': '2025-01-10',
            'date_fin_periode': '2025-01-31', 'observations': 'Correction autorisée',
            'lignes_attachement': json.dumps([
                {'id': self.ligne_bordereau.pk, 'quantite_realisee': quantite},
            ]),
        }

    def test_exceptional_preview_rejects_stop_period_even_if_dates_unchanged(self):
        self.create_os('OSA', date(2025, 1, 20))
        self.create_os('OSR', date(2025, 2, 5))
        response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 400)
        self.assertIn('19/01/2025', response.json()['erreur'])
        self.assertIn('05/02/2025', response.json()['erreur'])
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.total_montant_ht, Decimal('100'))

    def test_exceptional_confirmation_rechecks_new_stop(self):
        preview = self.client.post(self.url, self.payload())
        self.assertEqual(preview.status_code, 200)
        self.create_os('OSA', date(2025, 1, 20))
        response = self.client.post(self.url, {
            **self.payload(), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertEqual(response.status_code, 400)
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.total_montant_ht, Decimal('100'))

    def test_superuser_can_open_validated_form_without_403(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['correction_exceptionnelle'])
        self.assertContains(response, 'data-correction="true"')
        self.assertNotContains(response, 'id="transmettre-btn"')
        self.assertNotContains(response, 'id="delete-btn"')

    def test_signed_attachment_is_editable_without_reopening(self):
        Attachement.objects.filter(pk=self.premier.pk).update(statut='SIGNE')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="save-btn"')
        self.assertContains(response, 'data-editable="true"')
        self.assertNotContains(response, 'id="reouvrir-btn"')
        preview = self.client.post(self.url, self.payload('0'))
        self.assertEqual(preview.status_code, 200, preview.content)
        response = self.client.post(self.url, {
            **self.payload('0'), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertTrue(response.json()['enregistre'])
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.statut, 'SIGNE')
        self.assertEqual(self.premier.montant_ht, Decimal('0'))

    def test_later_successor_is_not_changed(self):
        troisieme = self.create_attachement(3, date(2025, 3, 1), date(2025, 3, 31), 'VALIDE')
        enregistrer_lignes_attachement(
            troisieme, json.dumps([{'id': self.ligne_bordereau.pk, 'quantite_realisee': '25'}]),
        )
        avant = Attachement.objects.filter(pk=troisieme.pk).values().get()
        preview = self.client.post(self.url, self.payload())
        response = self.client.post(self.url, {
            **self.payload(), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertTrue(response.json()['enregistre'])
        self.assertEqual(avant, Attachement.objects.filter(pk=troisieme.pk).values().get())

    def test_payment_date_alone_blocks_financial_correction(self):
        Decompte.objects.filter(pk=self.decompte.pk).update(date_paiement=date(2025, 2, 1))
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 400)

    def test_out_of_range_financial_amount_is_rejected_at_preview(self):
        response = self.client.post(self.url, self.payload('1000000000'))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.premier.total_montant_ht, Decimal('100'))

    def test_write_failure_rolls_back_metadata_and_lines(self):
        preview = self.client.post(self.url, self.payload())
        with patch(
            'projets.services.correction_attachement.LigneAttachement.objects.bulk_create',
            side_effect=RuntimeError('write failed'),
        ):
            with self.assertRaises(RuntimeError):
                self.client.post(self.url, {
                    **self.payload(), 'confirmation_correction': preview.json()['confirmation'],
                })
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.total_montant_ht, Decimal('100'))
        self.assertEqual(self.premier.observations, '')

    def test_tampered_and_expired_confirmation_are_rejected(self):
        preview = self.client.post(self.url, self.payload())
        token = preview.json()['confirmation']
        self.assertEqual(self.client.post(self.url, {
            **self.payload(), 'confirmation_correction': token + 'corrompu',
        }).status_code, 400)
        import time
        with patch('django.core.signing.time.time', return_value=time.time() + 1801):
            self.assertEqual(self.client.post(self.url, {
                **self.payload(), 'confirmation_correction': token,
            }).status_code, 400)

    def test_preview_then_confirmation_updates_current_and_next_not_validations(self):
        validation_avant = ProcessValidation.objects.filter(pk=self.validation.pk).values().get()
        preview = self.client.post(self.url, self.payload())
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertIn('Décompte D2', [i['objet'] for i in preview.json()['impacts']])
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.total_montant_ht, Decimal('100'))
        response = self.client.post(self.url, {
            **self.payload(), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertTrue(response.json()['enregistre'])
        self.premier.refresh_from_db()
        self.suivant.refresh_from_db()
        self.decompte.refresh_from_db()
        self.decompte_suivant.refresh_from_db()
        self.assertEqual(self.premier.montant_ht, Decimal('150'))
        self.assertEqual(self.suivant.montant_ht, Decimal('50'))
        self.assertEqual(self.decompte.montant_ht, Decimal('150'))
        self.assertEqual(self.decompte_suivant.montant_ht, Decimal('50'))
        self.assertEqual(self.premier.statut, 'VALIDE')
        self.assertEqual(self.suivant.statut, 'VALIDE')
        self.assertEqual(validation_avant, ProcessValidation.objects.filter(pk=self.validation.pk).values().get())
        self.assertFalse(CorrectionPeriodesAttachement.objects.exists())

    def test_paid_or_partially_paid_current_or_next_blocks_financial_correction(self):
        for decompte in (self.decompte, self.decompte_suivant):
            for statut in ('PAYE', 'PARTIEL'):
                with self.subTest(decompte=decompte.pk, statut=statut):
                    Decompte.objects.filter(pk=decompte.pk).update(statut=statut)
                    response = self.client.post(self.url, self.payload())
                    self.assertEqual(response.status_code, 400)
                    self.assertIn('payé', response.json()['erreur'])
                    Decompte.objects.filter(pk=decompte.pk).update(statut='BROUILLON')
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.total_montant_ht, Decimal('100'))

    def test_metadata_can_change_without_recalculating_paid_decompte(self):
        Decompte.objects.filter(pk=self.decompte.pk).update(statut='PAYE')
        avant = Decompte.objects.filter(pk=self.decompte.pk).values().get()
        preview = self.client.post(self.url, self.payload('10'))
        self.assertEqual(preview.status_code, 200, preview.content)
        response = self.client.post(self.url, {
            **self.payload('10'), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertTrue(response.json()['enregistre'])
        self.assertEqual(avant, Decompte.objects.filter(pk=self.decompte.pk).values().get())

    def test_stale_preview_and_modified_payload_cannot_be_confirmed(self):
        preview = self.client.post(self.url, self.payload())
        response = self.client.post(self.url, {
            **self.payload('16'), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertEqual(response.status_code, 400)
        Decompte.objects.filter(pk=self.decompte_suivant.pk).update(statut='PAYE')
        response = self.client.post(self.url, {
            **self.payload(), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.premier.total_montant_ht, Decimal('100'))

    def test_project_manager_can_only_correct_authorized_projects(self):
        manager = User.objects.create_user(username='manager-exception')
        manager.profile.role = 'CHEF_PROJET'
        manager.profile.save()
        self.client.force_login(manager)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)
        self.projet.users.add(manager)
        self.assertEqual(self.client.get(self.url).status_code, 200)
        preview = self.client.post(self.url, self.payload())
        self.assertEqual(preview.status_code, 200)
        response = self.client.post(self.url, {
            **self.payload(), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertTrue(response.json()['enregistre'])
        self.assertEqual(self.client.get(reverse(
            'projets:corriger_periodes_attachements', args=[self.projet.pk],
        )).status_code, 200)

    def test_staff_without_manager_role_cannot_override_validated_status(self):
        staff = User.objects.create_user(username='staff-exception', is_staff=True)
        self.projet.users.add(staff)
        self.client.force_login(staff)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.client.post(self.url + '?correction=1', self.payload()).status_code, 403)

    def test_invalid_period_or_negative_quantity_is_rejected(self):
        for changement in [
            {'date_fin_periode': '2025-01-09'},
            {'date_fin_periode': '2025-01-30'},
            {'lignes_attachement': json.dumps([{'id': self.ligne_bordereau.pk, 'quantite_realisee': '-1'}])},
        ]:
            response = self.client.post(self.url, {**self.payload(), **changement})
            self.assertEqual(response.status_code, 400)

    def test_existing_price_snapshots_are_preserved(self):
        self.ligne_bordereau.prix_unitaire = Decimal('99')
        self.ligne_bordereau.save()
        preview = self.client.post(self.url, self.payload())
        response = self.client.post(self.url, {
            **self.payload(), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertTrue(response.json()['enregistre'])
        self.assertEqual(self.premier.lignes_attachement.get().prix_unitaire, Decimal('10'))

    def test_file_stays_untouched_until_confirmation(self):
        def payload():
            return {**self.payload(), 'fichier': SimpleUploadedFile('preuve.txt', b'preuve de correction')}
        preview = self.client.post(self.url, payload())
        self.assertEqual(preview.status_code, 200, preview.content)
        self.premier.refresh_from_db()
        self.assertFalse(self.premier.fichier)
        response = self.client.post(self.url, {
            **payload(), 'confirmation_correction': preview.json()['confirmation'],
        })
        self.assertTrue(response.json()['enregistre'])
        self.premier.refresh_from_db()
        self.assertEqual(self.premier.original_filename, 'preuve.txt')
        self.assertEqual(self.premier.fichier.read(), b'preuve de correction')
        preview = self.client.post(self.url, self.payload('15'))
        self.assertEqual(preview.status_code, 200, preview.content)
        self.assertNotIn('Fichier joint', [i['champ'] for i in preview.json()['impacts']])


class AttachementSequenceTests(AttachementTestData, TestCase):
    def test_editing_dates_defers_continuity_until_transmission(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        premier.date_debut_periode = date(2025, 1, 11)
        premier.full_clean()
        premier.save()
        premier.statut = 'TRANSMIS'
        with self.assertRaises(ValidationError):
            premier.full_clean()
        with self.assertRaises(ValidationError):
            premier.save()
        premier.date_debut_periode = date(2025, 1, 10)
        premier.save()
        premier.refresh_from_db()
        self.assertEqual(premier.statut, 'TRANSMIS')

    def test_transmettre_rejects_legacy_inconsistent_period_before_creating_validations(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31), 'SIGNE')
        Attachement.objects.filter(pk=premier.pk).update(date_debut_periode=date(2025, 1, 11))
        premier.refresh_from_db()
        with self.assertRaises(ValidationError):
            premier.transmettre(None)
        premier.refresh_from_db()
        self.assertEqual(premier.statut, 'SIGNE')
        self.assertFalse(premier.validations.exists())

    def test_inverted_period_still_rejected_during_edit(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        premier.date_fin_periode = date(2025, 1, 9)
        with self.assertRaises(ValidationError):
            premier.full_clean()
        with self.assertRaises(ValidationError):
            premier.save()

    def test_creation_uses_os_date_and_links_sequentially(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        self.assertEqual(premier.sequence, 1)
        self.assertEqual(premier.numero, "DP01")
        self.assertIsNone(premier.precedent)

        premier.statut = 'SIGNE'
        premier.save()
        suivant = self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))
        self.assertEqual(suivant.sequence, 2)
        self.assertEqual(suivant.numero, "DP02")
        self.assertEqual(suivant.precedent_id, premier.id)
        self.assertEqual(suivant.get_previous_attachement(), premier)

    def test_creation_rejects_missing_os_wrong_dates_or_unapproved_predecessor(self):
        with self.assertRaises(ValidationError):
            self.create_attachement(1, date(2025, 1, 11), date(2025, 1, 31))

        self.projet.ordres_service.update(statut='BROUILLON')
        with self.assertRaises(ValidationError):
            self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        self.projet.ordres_service.update(statut='NOTIFIE')

        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        with self.assertRaises(ValidationError):
            self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))

        premier.statut = 'VALIDE'
        premier.save()
        with self.assertRaises(ValidationError):
            self.create_attachement(2, date(2025, 1, 31), date(2025, 2, 28))

    def test_previous_attachment_with_successor_cannot_be_changed_or_deleted(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31), 'SIGNE')
        suivant = self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))

        premier.date_fin_periode = date(2025, 2, 1)
        with self.assertRaises(ValidationError):
            premier.save()
        with self.assertRaises(ValidationError):
            premier.delete()

        self.assertEqual(suivant.precedent_id, premier.id)

    def test_commencement_order_cannot_change_after_first_attachment(self):
        self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        osc = self.projet.ordres_service.get(type_os__code='OSC')
        osc.date_effet = date(2025, 1, 11)
        with self.assertRaises(ValidationError):
            osc.save()
        with self.assertRaises(ValidationError):
            osc.delete()

    def test_deleting_project_cascades_through_the_entire_attachment_chain(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31), 'SIGNE')
        self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))

        self.projet.delete()

        self.assertFalse(Attachement.objects.filter(pk=premier.pk).exists())

class AttachementCumulativeQuantityTests(AttachementTestData, TestCase):
    def test_quantities_are_cumulative_and_can_be_reduced_to_zero(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        enregistrer_lignes_attachement(
            premier,
            json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '10'}]),
        )
        self.assertEqual(
            premier.lignes_attachement.get().quantite_cumulee,
            Decimal('10'),
        )
        self.assertEqual(premier.montant_ht, Decimal('100.00'))

        premier.statut = 'SIGNE'
        premier.save()
        suivant = self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))
        enregistrer_lignes_attachement(
            suivant,
            json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '4'}]),
        )
        self.assertEqual(suivant.total_montant_ht, Decimal('40'))
        self.assertEqual(suivant.montant_situation, Decimal('-60'))
        decompte = Decompte.objects.create(
            attachement=suivant,
            numero="DEC-002",
            date_emission=date(2025, 2, 28),
        )
        self.assertEqual(decompte.montant_ht, Decimal('-60'))
        self.assertEqual(decompte.montant_net_a_payer, Decimal('0'))

        enregistrer_lignes_attachement(
            suivant,
            json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '0'}]),
        )
        ligne_suivante = suivant.lignes_attachement.get()
        self.assertEqual(ligne_suivante.quantite_realisee, Decimal('0'))
        self.assertEqual(ligne_suivante.quantite_cumulee, Decimal('0'))
        self.assertEqual(suivant.montant_ht, Decimal('-100.00'))

    def test_omitted_predecessor_line_is_carried_forward_unchanged(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        enregistrer_lignes_attachement(
            premier,
            json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '10'}]),
        )
        premier.statut = 'SIGNE'
        premier.save()

        suivant = self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))
        enregistrer_lignes_attachement(suivant, '[]')

        ligne_suivante = suivant.lignes_attachement.get()
        self.assertEqual(ligne_suivante.quantite_realisee, Decimal('10'))
        self.assertEqual(ligne_suivante.quantite_cumulee, Decimal('10'))

    def test_edit_table_prefills_missing_current_line_from_predecessor(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31), 'SIGNE')
        enregistrer_lignes_attachement(
            premier,
            json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '10'}]),
        )
        suivant = self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))

        request = RequestFactory().get('/attachements/modifier/')
        request.user = SimpleNamespace(
            is_authenticated=True,
            is_superuser=True,
            is_staff=True,
        )
        with patch.object(attachement_views, 'render', side_effect=lambda request, template, context: context):
            context = attachement_views.modifier_attachement(request, suivant.pk)

        ligne = next(
            row for row in json.loads(context['lignes'])
            if row['id'] == self.ligne_bordereau.id
        )
        self.assertEqual(ligne['quantite_deja_realisee'], 10.0)
        self.assertEqual(ligne['quantite_realisee'], 10.0)

    def test_negative_cumulative_quantity_is_rejected(self):
        attachement = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        with self.assertRaises(DonneesAttachementInvalides):
            enregistrer_lignes_attachement(
                attachement,
                json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '-1'}]),
            )

    def test_successor_prevents_changing_predecessor_quantities(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31), 'SIGNE')
        enregistrer_lignes_attachement(
            premier,
            json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '10'}]),
        )
        self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))

        with self.assertRaises(DonneesAttachementInvalides):
            enregistrer_lignes_attachement(
                premier,
                json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '11'}]),
            )

    def test_successor_prevents_replacing_predecessor_line_snapshots(self):
        premier = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31), 'SIGNE')
        enregistrer_lignes_attachement(
            premier,
            json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '10'}]),
        )
        self.create_attachement(2, date(2025, 2, 1), date(2025, 2, 28))
        self.ligne_bordereau.prix_unitaire = Decimal('11')
        self.ligne_bordereau.save()

        with self.assertRaises(DonneesAttachementInvalides):
            enregistrer_lignes_attachement(
                premier,
                json.dumps([{'id': self.ligne_bordereau.id, 'quantite_realisee': '10'}]),
            )

        self.assertEqual(premier.lignes_attachement.get().prix_unitaire, Decimal('10'))
