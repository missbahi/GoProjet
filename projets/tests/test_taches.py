from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from projets.forms import TacheForm
from projets.models import Dossier, Notification, Projet, Tache
from projets.signals.tache_echeances import check_echeances_taches_quotidien
from projets.task_policy import responsables_eligibles


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class TacheResponsableTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dossier = Dossier.objects.create(nom='Dossier tâches')
        cls.autre_dossier = Dossier.objects.create(nom='Dossier extérieur')
        cls.projet = Projet.objects.create(nom='Projet A', numero='TACHE-A', dossier=cls.dossier)
        cls.autre = Projet.objects.create(nom='Projet B', numero='TACHE-B', dossier=cls.dossier)

        def membre(username, role, projet=None, dossier=None, actif=True):
            user = User.objects.create_user(username, is_active=actif)
            user.profile.role = role
            user.profile.save()
            (dossier or cls.dossier).utilisateurs.add(user)
            if projet:
                projet.users.add(user)
            return user

        cls.directeur = membre('directeur', 'DIRECTEUR_PROJET', cls.projet)
        cls.autre.users.add(cls.directeur)
        cls.administrateur = membre('administrateur', 'ADMIN_DOSSIER')
        cls.responsable = membre('chantier', 'CHEF_CHANTIER', cls.projet)
        cls.responsable.first_name = 'Ali'
        cls.responsable.last_name = 'Chantier'
        cls.responsable.email = 'chantier@example.test'
        cls.responsable.save()
        cls.chef_b = membre('chef-b', 'CHEF_PROJET', cls.autre)
        cls.observateur = membre('observateur', 'OBSERVATEUR', cls.projet)
        cls.pointeur = membre('pointeur', 'POINTEUR', cls.projet)
        cls.inactif = membre('inactif', 'CHEF_PROJET', cls.projet, actif=False)
        cls.exterieur = membre('exterieur', 'CHEF_PROJET', cls.projet, cls.autre_dossier)
        cls.admin_global = User.objects.create_superuser('admin-global-taches')
        cls.tache = Tache.objects.create(
            projet=cls.projet, responsable=cls.responsable, titre='Tâche à suivre',
            description='Suivi du chantier', date_debut=timezone.localdate() - timedelta(days=1),
            date_fin=timezone.localdate(),
        )

    def payload(self, **changes):
        data = {
            'projet': self.projet.pk, 'responsable': self.responsable.pk,
            'titre': self.tache.titre, 'description': self.tache.description,
            'date_debut': self.tache.date_debut.isoformat(),
            'date_fin': self.tache.date_fin.isoformat(),
            'priorite': 'NORMALE', 'avancement': 0,
        }
        data.update(changes)
        return data

    def test_api_and_form_share_project_specific_candidates(self):
        expected = {self.directeur.pk, self.administrateur.pk, self.responsable.pk, self.admin_global.pk}
        self.assertEqual(set(responsables_eligibles(self.projet).values_list('pk', flat=True)), expected)
        self.client.force_login(self.admin_global)
        response = self.client.get('/api/get-form-data/', {'projet_id': self.projet.pk})
        self.assertEqual(response.status_code, 200)
        self.assertEqual({user['id'] for user in response.json()['responsables']}, expected)
        self.assertIn('Ali Chantier', next(
            user['label'] for user in response.json()['responsables'] if user['id'] == self.responsable.pk
        ))
        self.client.force_login(self.directeur)
        response = self.client.get('/api/get-form-data/', {'projet_id': self.projet.pk})
        assignables = {self.directeur.pk, self.responsable.pk}
        self.assertEqual({user['id'] for user in response.json()['responsables']}, assignables)
        self.assertEqual(set(TacheForm(user=self.directeur, projet=self.projet).fields[
            'responsable'
        ].queryset.values_list('pk', flat=True)), assignables)
        for user in [self.administrateur, self.chef_b, self.observateur,
                     self.pointeur, self.inactif, self.exterieur, self.admin_global]:
            with self.subTest(user=user.username):
                form = TacheForm(self.payload(responsable=user.pk), user=self.directeur, projet=self.projet)
                self.assertFalse(form.is_valid())
                self.assertIn('responsable', form.errors)
        self.tache.responsable = self.chef_b
        with self.assertRaises(ValidationError):
            self.tache.full_clean()

    def test_creation_defaults_to_only_project_and_self_and_accepts_global_self_reminder(self):
        self.client.force_login(self.chef_b)
        response = self.client.get('/api/get-form-data/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['projet_id'], self.autre.pk)
        self.assertTrue(data['projet_unique'])
        self.assertEqual([user['id'] for user in data['responsables']], [self.chef_b.pk])
        payload = self.payload()
        del payload['projet']
        del payload['responsable']
        form = TacheForm(payload, user=self.chef_b)
        self.assertTrue(form.fields['projet'].disabled)
        self.assertTrue(form.fields['responsable'].disabled)
        self.assertTrue(form.is_valid(), form.errors)
        created = self.client.post(
            reverse('projets:creer_tache', args=[self.autre.pk]), payload,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(created.status_code, 200)
        task = Tache.objects.get(pk=created.json()['tache_id'])
        self.assertEqual(task.projet_id, self.autre.pk)
        self.assertEqual(task.responsable_id, self.chef_b.pk)
        forged = TacheForm(dict(payload, responsable=self.directeur.pk), user=self.chef_b)
        self.assertFalse(forged.is_valid())
        self.assertIn('responsable', forged.errors)
        forged = TacheForm(dict(payload, projet=self.projet.pk), user=self.chef_b)
        self.assertFalse(forged.is_valid())
        self.assertIn('projet', forged.errors)
        form = TacheForm(self.payload(responsable=self.admin_global.pk),
                         user=self.admin_global, projet=self.projet)
        self.assertTrue(form.is_valid(), form.errors)
        task = form.save()
        self.assertEqual(task.responsable_id, self.admin_global.pk)
        task.full_clean()

    def test_admin_creation_loads_candidates_with_multiple_projects_and_allows_switching(self):
        for actor in [self.administrateur, self.admin_global]:
            with self.subTest(role='GLOBAL' if actor.is_superuser else 'ADMIN_DOSSIER'):
                self.client.force_login(actor)
                response = self.client.get('/api/get-form-data/')
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(data['projet_id'], self.projet.pk)
                self.assertFalse(data['projet_unique'])
                self.assertIn(actor.pk, {user['id'] for user in data['responsables']})
                self.assertIn(self.responsable.pk, {user['id'] for user in data['responsables']})
                self.assertNotIn(self.chef_b.pk, {user['id'] for user in data['responsables']})
                form = TacheForm(user=actor)
                self.assertFalse(form.fields['projet'].disabled)
                self.assertEqual(form.initial['projet'], self.projet.pk)
                self.assertEqual(
                    set(form.fields['responsable'].queryset.values_list('pk', flat=True)),
                    {user['id'] for user in data['responsables']},
                )
                response = self.client.get('/api/get-form-data/', {'projet_id': self.autre.pk})
                data = response.json()
                self.assertEqual(data['projet_id'], self.autre.pk)
                self.assertFalse(data['projet_unique'])
                self.assertIn(actor.pk, {user['id'] for user in data['responsables']})
                self.assertIn(self.chef_b.pk, {user['id'] for user in data['responsables']})
                self.assertNotIn(self.responsable.pk, {user['id'] for user in data['responsables']})
                created = self.client.post(
                    reverse('projets:creer_tache', args=[self.autre.pk]),
                    self.payload(projet=self.autre.pk, responsable=actor.pk),
                    HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                )
                self.assertEqual(created.status_code, 200)
                task = Tache.objects.get(pk=created.json()['tache_id'])
                self.assertEqual(task.projet_id, self.autre.pk)
                self.assertEqual(task.responsable_id, actor.pk)

    def test_operational_responsible_only_updates_progress_and_project_stays_locked(self):
        form = TacheForm({'avancement': 20}, instance=self.tache, user=self.responsable)
        self.assertTrue(form.is_valid(), form.errors)
        Tache.objects.filter(pk=self.tache.pk).update(description='Description actualisée')
        form.save()
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.description, 'Description actualisée')
        url = reverse('projets:modifier_tache', args=[self.projet.pk, self.tache.pk])
        self.client.force_login(self.responsable)
        response = self.client.post(url, {'avancement': 35}, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 200)
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.avancement, 35)
        response = self.client.post(url, {
            'avancement': 35, 'responsable': self.directeur.pk, 'titre': 'Modification interdite',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.responsable_id, self.responsable.pk)
        self.assertEqual(self.tache.titre, 'Tâche à suivre')
        self.assertEqual(self.client.post(reverse(
            'projets:creer_tache', args=[self.projet.pk],
        ), self.payload()).status_code, 403)
        self.assertEqual(self.client.delete(reverse(
            'projets:supprimer_tache', args=[self.projet.pk, self.tache.pk],
        )).status_code, 403)
        self.client.force_login(self.directeur)
        response = self.client.post(url, self.payload(projet=self.autre.pk),
                                    HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.projet_id, self.projet.pk)
        form = TacheForm({'avancement': 50}, instance=self.tache, user=self.responsable)
        self.assertTrue(form.is_valid(), form.errors)
        Tache.objects.filter(pk=self.tache.pk).update(responsable=self.directeur)
        with self.assertRaises(PermissionDenied):
            form.save()
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.avancement, 35)

    def test_ineligible_responsible_requires_reassignment_but_completed_history_survives(self):
        self.responsable.is_active = False
        self.responsable.save()
        self.assertTrue(self.tache.responsable_a_reaffecter)
        self.client.force_login(self.directeur)
        response = self.client.get(reverse('projets:liste_taches_projet', args=[self.projet.pk]))
        self.assertContains(response, 'Responsable à réaffecter')
        form = TacheForm(self.payload(), instance=self.tache, user=self.directeur)
        self.assertFalse(form.is_valid())
        Notification.objects.filter(utilisateur=self.responsable).delete()
        with override_settings(SEND_EMAIL_NOTIFICATIONS=True), patch(
            'projets.signals.tache_echeances.send_email_notification',
        ) as send_email:
            check_echeances_taches_quotidien()
        send_email.assert_not_called()
        self.assertFalse(Notification.objects.filter(utilisateur=self.responsable).exists())
        self.tache.terminee = True
        self.tache.avancement = 100
        self.tache.save()
        form = TacheForm(self.payload(terminee='on', avancement=100),
                         instance=self.tache, user=self.directeur)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        self.tache.refresh_from_db()
        self.assertEqual(self.tache.responsable_id, self.responsable.pk)
        form = TacheForm(self.payload(avancement=50), instance=self.tache, user=self.directeur)
        self.assertFalse(form.is_valid())
        self.assertIn('responsable', form.errors)

    def test_model_visibility_uses_project_assignments_not_just_dossier_membership(self):
        other_task = Tache.objects.create(
            projet=self.autre, responsable=self.chef_b, titre='Tâche B', description='Autre projet',
            date_debut=self.tache.date_debut, date_fin=self.tache.date_fin,
        )
        self.assertFalse(other_task.est_accessible_par(self.responsable))
        self.assertEqual(list(Tache.accessibles(self.responsable)), [self.tache])
        self.assertCountEqual(Tache.accessibles(self.administrateur), [self.tache, other_task])
