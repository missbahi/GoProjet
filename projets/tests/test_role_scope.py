from datetime import date
from decimal import Decimal
from importlib import import_module

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.forms.models import model_to_dict
from django.test import TestCase, override_settings
from django.urls import reverse

from goplan.models import GCalendarException, GPlan, GWorkCalendar
from goplan.forms import GPlanForm
from projets.decorators import projets_accessibles
from projets.forms import ProjetForm
from projets.models import Dossier, Notification, ProcessValidation, Projet
from projets.tests.test_attachements import AttachementTestData


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class RoleScopeTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.dossier = Dossier.objects.create(nom='Dossier principal')
        self.autre_dossier = Dossier.objects.create(nom='Dossier distinct')
        self.projet.dossier = self.dossier
        self.projet.save(update_fields=['dossier'])
        self.autre_projet = Projet.objects.create(
            nom='Projet non affecte', numero='ROLE-NON-AFFECTE', dossier=self.dossier,
        )
        self.projet_externe = Projet.objects.create(
            nom='Projet externe', numero='ROLE-EXTERNE', dossier=self.autre_dossier,
        )
        self.admin = User.objects.create_superuser('admin-global-roles')
        self.responsable = self.actor('admin-dossier-roles', 'ADMIN_DOSSIER')
        self.directeur = self.actor('directeur-roles', 'DIRECTEUR_PROJET')
        self.chef = self.actor('chef-roles', 'CHEF_PROJET')
        self.externe = self.actor(
            'admin-externe-roles', 'ADMIN_DOSSIER', dossier=self.autre_dossier,
        )
        self.projet.users.add(self.directeur, self.chef)

    def actor(self, username, role, dossier=None):
        actor = User.objects.create_user(username)
        actor.profile.role = role
        actor.profile.save()
        (dossier or self.dossier).utilisateurs.add(actor)
        return actor

    def test_project_visibility_is_role_and_assignment_scoped(self):
        self.assertCountEqual(
            projets_accessibles(self.admin), [self.projet, self.autre_projet, self.projet_externe],
        )
        self.assertCountEqual(
            projets_accessibles(self.responsable), [self.projet, self.autre_projet],
        )
        for actor in [self.directeur, self.chef]:
            with self.subTest(role=actor.profile.role):
                self.assertCountEqual(projets_accessibles(actor), [self.projet])
                self.client.force_login(actor)
                response = self.client.get(reverse('projets:liste_projets'))
                self.assertContains(response, self.projet.nom)
                self.assertNotContains(response, self.autre_projet.nom)
                self.assertNotContains(response, self.projet_externe.nom)
                for project in [self.autre_projet, self.projet_externe]:
                    self.assertEqual(self.client.get(reverse(
                        'projets:lots_projet', args=[project.pk],
                    )).status_code, 403)

    def test_project_creation_deletion_and_configuration_are_separate_permissions(self):
        for actor, can_create, can_delete, can_configure in [
            (self.responsable, True, True, True),
            (self.directeur, True, False, False),
            (self.chef, False, False, False),
        ]:
            with self.subTest(role=actor.profile.role):
                self.client.force_login(actor)
                response = self.client.get(reverse('projets:ajouter_projet_modal'))
                self.assertEqual(response.status_code, 200 if can_create else 403)
                listing = self.client.get(reverse('projets:liste_projets'))
                self.assertEqual(listing.context['can_create_project'], can_create)
                self.assertEqual(listing.context['can_delete_project'], can_delete)
                config = self.client.get(reverse('projets:data_view'))
                self.assertEqual(config.status_code, 200 if can_configure else 403)
                if not can_delete:
                    response = self.client.post(reverse('projets:supprimer_projet', args=[self.projet.pk]))
                    self.assertEqual(response.status_code, 403)
                    self.assertTrue(Projet.objects.filter(pk=self.projet.pk).exists())
                if not can_configure:
                    response = self.client.post(reverse('projets:ajouter_client'), {'nom': 'Interdit'})
                    self.assertEqual(response.status_code, 403)
        self.client.force_login(self.responsable)
        self.assertEqual(self.client.get(reverse(
            'projets:supprimer_projet', args=[self.projet.pk],
        )).status_code, 405)
        response = self.client.post(reverse('projets:supprimer_projet', args=[self.autre_projet.pk]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Projet.objects.filter(pk=self.autre_projet.pk).exists())

    def test_project_managers_can_write_modules_but_not_foreign_projects(self):
        for actor in [self.responsable, self.directeur, self.chef]:
            with self.subTest(role=actor.profile.role):
                self.client.force_login(actor)
                code = f'A{actor.pk}'
                response = self.client.post(
                    reverse('projets:ajouter_atelier', args=[self.projet.pk]),
                    {'code': code, 'libelle': 'Atelier autorise', 'actif': 'on'},
                )
                self.assertIn(response.status_code, [200, 302])
                self.assertTrue(self.projet.ateliers.filter(code=code).exists())
                response = self.client.post(
                    reverse('projets:ajouter_atelier', args=[self.projet_externe.pk]),
                    {'code': 'EXTERNE', 'libelle': 'Atelier interdit', 'actif': 'on'},
                )
                self.assertEqual(response.status_code, 403)
                self.assertFalse(self.projet_externe.ateliers.exists())
                dashboard = self.client.get(reverse('projets:dashboard', args=[self.projet.pk]))
                self.assertEqual(dashboard.status_code, 200)
                self.assertTrue(dashboard.context['can_handler'])

    def test_local_dossier_edit_returns_to_accessible_page(self):
        self.client.force_login(self.responsable)
        response = self.client.post(
            reverse('projets:modifier_dossier', args=[self.dossier.pk]),
            {'nom': 'Dossier renomme', 'description': '', 'activite': self.dossier.activite},
        )
        self.assertRedirects(response, reverse('projets:home'), fetch_redirect_response=False)
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.nom, 'Dossier renomme')
        self.assertTrue(self.dossier.utilisateurs.filter(pk=self.responsable.pk).exists())

    def test_local_user_creation_inherits_dossier_without_selector(self):
        url = reverse('projets:ajouter_utilisateur')
        for actor, role in [(self.responsable, 'ADMIN_DOSSIER'), (self.directeur, 'CHEF_PROJET')]:
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                self.assertNotContains(self.client.get(url), 'name="dossiers"')
                data = {
                    'username': f'herite-{actor.pk}', 'role': role,
                    'password1': 'ScopePassword432!', 'password2': 'ScopePassword432!',
                }
                response = self.client.post(url, data)
                self.assertEqual(response.status_code, 302)
                created = User.objects.get(username=data['username'])
                self.assertEqual(list(created.dossiers.all()), [self.dossier])
                for selection in ['', str(self.dossier.pk), str(self.autre_dossier.pk)]:
                    data.update(username=f'interdit-{actor.pk}', dossiers=selection)
                    response = self.client.post(url, data, HTTP_HX_REQUEST='true')
                    self.assertEqual(response.status_code, 400)
                    self.assertFalse(User.objects.filter(username=data['username']).exists())

    def test_local_user_edits_cannot_change_any_dossier_membership(self):
        target = self.actor('membre-a-editer', 'CHEF_CHANTIER')
        self.projet.users.add(target)
        for actor in [self.responsable, self.directeur]:
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                url = reverse('projets:modifier_utilisateur', args=[target.pk])
                self.assertNotContains(self.client.get(url), 'name="dossiers"')
                data = {'first_name': 'Modifie', 'role': target.profile.role}
                if actor == self.responsable:
                    data['is_active'] = 'on'
                self.assertEqual(self.client.post(url, data).status_code, 302)
                for selection in ['', str(self.dossier.pk), str(self.autre_dossier.pk)]:
                    response = self.client.post(url, {**data, 'dossiers': selection})
                    self.assertEqual(response.status_code, 403)
                    self.assertEqual(list(target.dossiers.all()), [self.dossier])
        self.client.force_login(self.responsable)
        url = reverse('projets:modifier_utilisateur', args=[self.responsable.pk])
        self.assertNotContains(self.client.get(url), 'name="dossiers"')
        self.assertEqual(self.client.post(url, {
            'first_name': 'Personnel',
        }).status_code, 302)
        self.assertEqual(self.client.post(url, {
            'dossiers': self.autre_dossier.pk,
        }).status_code, 403)
        self.assertEqual(list(self.responsable.dossiers.all()), [self.dossier])

    def test_local_project_creation_inherits_dossier_and_cannot_be_forged(self):
        data = model_to_dict(self.projet, fields=ProjetForm._meta.fields)
        data = {field: value for field, value in data.items() if value is not None}
        data.pop('dossier')
        data.update(objet='Objet du projet', date_debut='2025-01-10', delai='12')
        url = reverse('projets:ajouter_projet_modal')
        for actor in [self.responsable, self.directeur]:
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                form = self.client.get(url).context['form']
                self.assertTrue(form.fields['dossier'].disabled)
                self.assertTrue(form.fields['dossier'].widget.is_hidden)
                data.update(nom=f'Projet herite {actor.pk}', numero=f'HERITE-{actor.pk}')
                response = self.client.post(url, data, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertTrue(response.json()['success'], response.content)
                project = Projet.objects.get(numero=data['numero'])
                self.assertEqual(project.dossier_id, self.dossier.pk)
                self.assertTrue(project.users.filter(pk=actor.pk).exists())
                data['numero'] = f'INTERDIT-{actor.pk}'
                response = self.client.post(url, {
                    **data, 'dossier': self.autre_dossier.pk,
                }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
                self.assertFalse(response.json()['success'])
                self.assertIn('dossier', response.json()['errors'])
                self.assertFalse(Projet.objects.filter(numero=data['numero']).exists())
        self.client.force_login(self.chef)
        response = self.client.post(
            reverse('projets:modifier_projet_modal', args=[self.projet.pk]),
            {**data, 'dossier': self.autre_dossier.pk},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.dossier_id, self.dossier.pk)

    def test_local_dossier_metadata_cannot_reassign_users_or_projects(self):
        self.client.force_login(self.responsable)
        url = reverse('projets:modifier_dossier', args=[self.dossier.pk])
        response = self.client.get(url)
        self.assertNotContains(response, 'name="gerant"')
        self.assertNotContains(response, 'name="projets"')
        original_members = set(self.dossier.utilisateurs.values_list('pk', flat=True))
        for field, value in [
            ('gerant', self.externe.pk), ('utilisateurs', self.externe.pk),
            ('projets', self.projet_externe.pk),
        ]:
            response = self.client.post(url, {
                'nom': 'Nom refuse', 'activite': self.dossier.activite, field: value,
            })
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context['form'].non_field_errors())
            self.dossier.refresh_from_db()
            self.assertEqual(self.dossier.nom, 'Dossier principal')
            self.assertEqual(set(self.dossier.utilisateurs.values_list('pk', flat=True)), original_members)
        self.projet_externe.refresh_from_db()
        self.assertEqual(self.projet_externe.dossier_id, self.autre_dossier.pk)

    def test_only_global_admin_can_edit_observer_dossier_memberships(self):
        observer = self.actor('observateur-affectations', 'OBSERVATEUR')
        self.client.force_login(self.admin)
        url = reverse('projets:modifier_utilisateur', args=[observer.pk])
        self.assertContains(self.client.get(url), 'name="dossiers"')
        response = self.client.post(url, {
            'role': 'OBSERVATEUR', 'is_active': 'on',
            'dossiers': [self.dossier.pk, self.autre_dossier.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.assertCountEqual(observer.dossiers.all(), [self.dossier, self.autre_dossier])

    def test_attachment_workflow_permissions_are_project_scoped(self):
        attachment = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        validation = ProcessValidation.objects.create(
            attachement=attachment, type_validation='TECHNIQUE',
            demandeur_validation=self.responsable, statut_validation='EN_ATTENTE',
        )
        for actor in [self.responsable, self.directeur, self.chef]:
            self.assertTrue(validation.peut_etre_valide_par(actor))
        self.assertFalse(validation.peut_etre_valide_par(self.externe))
        self.externe.is_staff = True
        self.externe.save()
        self.assertFalse(validation.peut_etre_valide_par(self.externe))
        self.client.force_login(self.externe)
        self.assertEqual(self.client.get(reverse(
            'projets:modifier_attachement', args=[attachment.pk],
        )).status_code, 403)

    def test_default_validation_does_not_assign_or_notify_foreign_staff(self):
        self.dossier.activite = 'SERVICES'
        self.dossier.save(update_fields=['activite'])
        self.admin.is_staff = False
        self.admin.save(update_fields=['is_staff'])
        self.externe.is_staff = True
        self.externe.save(update_fields=['is_staff'])
        attachment = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        attachment.initialiser_processus_validation(self.chef)
        self.assertEqual(
            attachment.validations.get(type_validation='TECHNIQUE').validateur,
            self.responsable,
        )
        self.assertEqual(
            attachment.validations.get(type_validation='FINANCIERE').validateur,
            self.admin,
        )
        self.assertFalse(Notification.objects.filter(utilisateur=self.externe).exists())

    def test_planning_lists_and_direct_access_follow_project_scope(self):
        content_type = ContentType.objects.get_for_model(Projet)
        own = GPlan.objects.create(
            nom='Planning affecte', date_debut=date(2025, 1, 1),
            content_type=content_type, object_id=self.projet.pk,
        )
        foreign = GPlan.objects.create(
            nom='Planning non affecte', date_debut=date(2025, 1, 1),
            content_type=content_type, object_id=self.autre_projet.pk,
        )
        orphan = GPlan.objects.create(nom='Planning non rattache', date_debut=date(2025, 1, 1))
        self.client.force_login(self.directeur)
        listing = self.client.get(reverse('goplan:liste_plans'))
        self.assertContains(listing, own.nom)
        self.assertNotContains(listing, foreign.nom)
        self.assertNotContains(listing, orphan.nom)
        for plan in [foreign, orphan]:
            self.assertEqual(self.client.get(reverse(
                'goplan:modifier_plan', args=[plan.pk],
            )).status_code, 403)

    def test_private_calendars_cannot_be_edited_from_another_dossier(self):
        calendar = GWorkCalendar.objects.create(
            dossier=self.dossier, nom='Calendrier prive', jours_ouvres=[1, 2, 3, 4, 5],
        )
        self.client.force_login(self.externe)
        response = self.client.post(reverse('goplan:supprimer_calendrier', args=[calendar.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(GWorkCalendar.objects.filter(pk=calendar.pk).exists())

    def test_local_planning_requires_authorized_project_and_calendar(self):
        private_calendar = GWorkCalendar.objects.create(
            dossier=self.autre_dossier, nom='Calendrier externe', jours_ouvres=[1, 2, 3, 4, 5],
        )
        data = {'nom': 'Planning local', 'date_debut': '2025-01-01', 'projet': ''}
        form = GPlanForm(data=data, user=self.directeur)
        self.assertFalse(form.is_valid())
        self.assertIn('projet', form.errors)
        data['projet'] = self.autre_projet.pk
        form = GPlanForm(data=data, user=self.directeur)
        self.assertFalse(form.is_valid())
        self.assertIn('projet', form.errors)
        data.update(projet=self.projet.pk, calendrier=private_calendar.pk)
        form = GPlanForm(data=data, user=self.directeur)
        self.assertFalse(form.is_valid())
        self.assertIn('calendrier', form.errors)
        data.pop('calendrier')
        form = GPlanForm(data=data, user=self.directeur)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().source_object, self.projet)

    def test_calendar_migration_splits_shared_history_without_losing_exceptions(self):
        calendar = GWorkCalendar.objects.create(
            nom='Calendrier historique partage', jours_ouvres=[1, 2, 3, 4, 5],
        )
        GCalendarException.objects.create(
            calendrier=calendar, date=date(2025, 1, 2), heures=Decimal('4.0'),
        )
        standard = GWorkCalendar.objects.create(
            nom='Standard partage', jours_ouvres=[1, 2, 3, 4, 5], is_default=True,
        )
        content_type = ContentType.objects.get_for_model(Projet)
        own = GPlan.objects.create(
            nom='Historique local', date_debut=date(2025, 1, 1),
            content_type=content_type, object_id=self.projet.pk, calendrier=calendar,
        )
        foreign = GPlan.objects.create(
            nom='Historique externe', date_debut=date(2025, 1, 1),
            content_type=content_type, object_id=self.projet_externe.pk, calendrier=calendar,
        )
        migration = import_module('goplan.migrations.0012_calendar_dossier')
        migration.rattacher_calendriers(apps, connection.schema_editor(atomic=False))
        own.refresh_from_db()
        foreign.refresh_from_db()
        self.assertEqual(own.calendrier.dossier_id, self.dossier.pk)
        self.assertEqual(foreign.calendrier.dossier_id, self.autre_dossier.pk)
        self.assertNotEqual(own.calendrier_id, foreign.calendrier_id)
        self.assertTrue(GWorkCalendar.objects.filter(pk=calendar.pk, dossier__isnull=True).exists())
        standard.refresh_from_db()
        self.assertIsNone(standard.dossier_id)
        for copy in [own.calendrier, foreign.calendrier, calendar]:
            self.assertEqual(
                list(copy.exceptions.values_list('date', 'heures')),
                [(date(2025, 1, 2), Decimal('4.0'))],
            )

    def test_xml_replacement_preserves_authorized_project_and_rejects_foreign_selection(self):
        plan = GPlan.objects.create(
            nom='Planning avant import', date_debut=date(2025, 1, 1),
            content_type=ContentType.objects.get_for_model(Projet), object_id=self.projet.pk,
        )
        self.client.force_login(self.directeur)
        url = reverse('goplan:replace_mspdi', args=[plan.pk])
        xml = (
            b'<Project xmlns="http://schemas.microsoft.com/project">'
            b'<Name>Planning importe</Name><StartDate>2025-01-01T08:00:00</StartDate>'
            b'<Tasks></Tasks></Project>'
        )
        preview = self.client.post(url, {
            'fichier': SimpleUploadedFile('planning.xml', xml, content_type='application/xml'),
            'accepter_remplacement': 'on',
        })
        self.assertEqual(preview.status_code, 200)
        self.assertIn('import_token', preview.context)
        payload = {
            'import_token': preview.context['import_token'], 'nom': 'Planning remplace',
            'description': '', 'projet': self.autre_projet.pk, 'accepter_remplacement': 'on',
        }
        rejected = self.client.post(url, payload)
        self.assertEqual(rejected.status_code, 200)
        self.assertIn('projet', rejected.context['final_form'].errors)
        plan.refresh_from_db()
        self.assertEqual(plan.nom, 'Planning avant import')
        self.assertEqual(plan.source_object, self.projet)
        payload['projet'] = self.projet.pk
        response = self.client.post(url, payload)
        self.assertEqual(response.status_code, 302)
        plan.refresh_from_db()
        self.assertEqual(plan.nom, 'Planning remplace')
        self.assertEqual(plan.source_object, self.projet)

    def test_pending_role_and_staff_flag_do_not_grant_domain_administration(self):
        pending = self.actor('ancien-chef-roles', 'A_RECLASSER')
        self.projet.users.add(pending)
        self.assertFalse(projets_accessibles(pending).exists())
        self.client.force_login(pending)
        self.assertContains(self.client.get(reverse('projets:home')), 'réaffecté')
        self.assertEqual(self.client.get(reverse(
            'projets:lots_projet', args=[self.projet.pk],
        )).status_code, 403)
        self.chef.is_staff = True
        self.chef.save()
        self.client.force_login(self.chef)
        self.assertEqual(self.client.get('/admin/').status_code, 403)
