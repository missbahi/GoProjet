import re
from datetime import date
from unittest.mock import patch

from django.apps import apps
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import get_resolver, resolve, reverse, URLResolver

from goplan.forms import GPlanForm
from goplan.models import GPlan, GTask, GWorkCalendar
from projets.decorators import projets_accessibles
from projets.forms import UtilisateurCreationForm
from projets.models import DocumentAdministratif, Dossier, Notification, Projet, ProcessValidation
from projets.observer_access import (
    DOWNLOAD_SCOPES, OBJECT_SCOPES, observer_route_allowed, observer_url_patterns,
)
from projets.tests.test_attachements import AttachementTestData


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class ObservateurTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user('observateur', password='ObserverPassword432!')
        self.user.profile.role = 'OBSERVATEUR'
        self.user.profile.save()
        self.dossier = Dossier.objects.create(nom='Dossier autorise')
        self.dossier.utilisateurs.add(self.user)
        self.projet.dossier = self.dossier
        self.projet.save()
        self.autre = Projet.objects.create(nom='Projet confidentiel', numero='HORS-DOSSIER')
        self.autre.users.add(self.user)
        self.attachement = self.create_attachement(1, date(2025, 1, 10), date(2025, 1, 31))
        content_type = ContentType.objects.get_for_model(Projet)
        self.plan = GPlan.objects.create(
            nom='Planning autorise', date_debut=date(2025, 1, 10),
            content_type=content_type, object_id=self.projet.pk,
        )
        self.autre_plan = GPlan.objects.create(
            nom='Planning confidentiel', date_debut=date(2025, 1, 10),
            content_type=content_type, object_id=self.autre.pk,
        )
        self.group = GTask.objects.create(plan=self.plan, nom='Phase consultable', type_tache='GROUPE')
        GTask.objects.create(
            plan=self.plan, parent=self.group, nom='Travaux consultables',
            date_debut=date(2025, 1, 13), date_fin=date(2025, 1, 14), duree=2,
        )
        self.client.force_login(self.user)

    def test_scope_is_assigned_dossiers_only_and_revocation_is_immediate(self):
        self.assertEqual(list(projets_accessibles(self.user)), [self.projet])
        self.dossier.utilisateurs.remove(self.user)
        self.assertFalse(projets_accessibles(self.user).exists())
        self.assertEqual(self.client.get(reverse('projets:dashboard', args=[self.projet.pk])).status_code, 403)

    def test_login_always_opens_home_even_with_next(self):
        self.client.logout()
        response = self.client.post(reverse('login') + '?next=/admin/', {
            'username': self.user.username, 'password': 'ObserverPassword432!',
        })
        self.assertRedirects(response, reverse('projets:home'), fetch_redirect_response=False)

    def test_landing_opens_home(self):
        self.assertRedirects(self.client.get(reverse('projets:landing')),
                             reverse('projets:home'), fetch_redirect_response=False)

    def test_home_and_project_list_are_scoped_and_readonly(self):
        for name in ['home', 'liste_projets']:
            with self.subTest(name=name):
                response = self.client.get(reverse('projets:' + name))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, self.autre.nom)
                self.assertTrue(response.context['observer_readonly'])
                self.assertContains(response, 'observer-readonly.js')

    def test_project_modules_are_readable_without_initializing_workflow(self):
        routes = [
            ('dashboard', [self.projet.pk]), ('lots_projet', [self.projet.pk]),
            ('saisie_bordereau', [self.projet.pk, self.lot.pk]),
            ('apercu_impression_bordereau', [self.projet.pk]),
            ('export_bordereau_excel', [self.projet.pk]),
            ('liste_ca', [self.projet.pk]), ('documents', [self.projet.pk]),
            ('rapports_journaliers', [self.projet.pk]), ('situations_mensuelles', [self.projet.pk]),
            ('suivi_execution', [self.projet.pk]), ('ateliers_projet', [self.projet.pk]),
            ('planning_ateliers', [self.projet.pk]), ('ressources_projet', [self.projet.pk]),
            ('liste_taches_projet', [self.projet.pk]), ('liste_taches', []),
            ('liste_attachements', [self.projet.pk]),
            ('detail_attachement', [self.attachement.pk]),
            ('tracabilite_validation_attachement', [self.attachement.pk]),
            ('liste_decomptes', [self.projet.pk]), ('ordres_service', [self.projet.pk]),
        ]
        before = ProcessValidation.objects.count()
        domain_models = [model for model in apps.get_app_config('projets').get_models()
                         if model.__name__ != 'Profile']
        snapshot = {model: list(model.objects.order_by('pk').values()) for model in domain_models}
        for name, args in routes:
            with self.subTest(name=name):
                response = self.client.get(reverse('projets:' + name, args=args))
                self.assertEqual(response.status_code, 200)
        self.assertEqual(ProcessValidation.objects.count(), before)
        for model, rows in snapshot.items():
            with self.subTest(unchanged_model=model.__name__):
                self.assertEqual(list(model.objects.order_by('pk').values()), rows)

    def test_every_registered_nonpersonal_route_rejects_all_write_methods(self):
        def visit(resolver, namespace=''):
            for route in resolver.url_patterns:
                if isinstance(route, URLResolver):
                    yield from visit(route, route.namespace or namespace)
                elif route.name and namespace in {'projets', 'goplan'}:
                    yield namespace, route

        for namespace, route in visit(get_resolver()):
            if observer_route_allowed(namespace, route.name, 'POST'):
                continue
            # Middleware resolves the route before validating domain objects or request bodies.
            converters = route.pattern.converters
            kwargs = {key: ('attachement' if key == 'model_name' else
                            'example' if converter.regex == '[^/]+' else 1)
                      for key, converter in converters.items()}
            url = reverse(namespace + ':' + route.name, kwargs=kwargs)
            for method in ('post', 'put', 'patch', 'delete'):
                with self.subTest(route=route.name, method=method):
                    self.assertEqual(getattr(self.client, method)(url).status_code, 403)

    def test_get_mutation_admin_and_user_management_are_denied_even_with_staff_flag(self):
        self.user.is_staff = True
        self.user.save()
        urls = [
            '/admin/', reverse('projets:liste_utilisateurs'),
            reverse('projets:validation_attachement', args=[self.attachement.pk]),
            reverse('projets:changer_statut_attachement', args=[self.attachement.pk]),
            reverse('goplan:modifier_plan', args=[self.plan.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)
        self.assertFalse(ProcessValidation.objects.exists())

    def test_foreign_project_and_document_are_denied(self):
        for name in ['dashboard', 'lots_projet', 'liste_attachements', 'ordres_service', 'documents']:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse('projets:' + name, args=[self.autre.pk])).status_code, 403)
        url = reverse('projets:download_document', args=['Projet', self.autre.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        self.projet.dossier = None
        self.projet.save()
        url = reverse('projets:detail_attachement', args=[self.attachement.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_all_object_scope_paths_are_valid_model_relationships(self):
        for model_name, path in OBJECT_SCOPES.values():
            with self.subTest(model=model_name, path=path):
                apps.get_model('projets', model_name).objects.filter(**{path + '__in': [self.projet.pk]}).exists()
        for model_name, path in DOWNLOAD_SCOPES.items():
            with self.subTest(model=model_name, path=path):
                apps.get_model('projets', model_name).objects.filter(**{path + '__in': [self.projet.pk]}).exists()

    def test_nested_objects_must_belong_to_the_requested_project(self):
        second = Projet.objects.create(nom='Second projet autorise', numero='SECOND', dossier=self.dossier)
        url = reverse('projets:saisie_bordereau', args=[second.pk, self.lot.pk])
        self.assertEqual(self.client.get(url).status_code, 403)
        orphan = GPlan.objects.create(nom='Planning sans projet', date_debut=date(2025, 1, 1))
        self.assertEqual(self.client.get(reverse('goplan:gantt_plan', args=[orphan.pk])).status_code, 403)

    def test_document_download_requires_dossier_membership_not_direct_project_assignment(self):
        document = DocumentAdministratif.objects.create(
            projet=self.projet, fichier=SimpleUploadedFile('consultation.txt', b'Visible'),
        )
        url = reverse('projets:download_document', args=['DocumentAdministratif', document.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        document.projet = self.autre
        document.save()
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.get(reverse('projets:afficher_document', args=[document.pk])).status_code, 403)

    def test_calendar_list_contains_only_calendars_used_by_accessible_plans(self):
        calendar = GWorkCalendar.objects.create(nom='Calendrier autorise', jours_ouvres=[1, 2, 3, 4, 5])
        GWorkCalendar.objects.create(nom='Calendrier confidentiel')
        self.plan.calendrier = calendar
        self.plan.save()
        response = self.client.get(reverse('goplan:liste_calendriers'))
        self.assertContains(response, calendar.nom)
        self.assertNotContains(response, 'Calendrier confidentiel')

    def test_plan_list_and_details_are_scoped_and_reads_do_not_repair_dates(self):
        response = self.client.get(reverse('goplan:liste_plans'))
        self.assertContains(response, self.plan.nom)
        self.assertNotContains(response, self.autre_plan.nom)
        self.assertContains(response, '<form method="dialog" data-observer-safe>')
        task_snapshot = list(GTask.objects.filter(plan=self.plan).order_by('pk').values())
        with patch('goplan.views.gantt_views.repair_plan_dates') as repair:
            for name in ['gantt_plan', 'apercu_plan', 'export_mspdi']:
                with self.subTest(name=name):
                    self.assertEqual(self.client.get(reverse('goplan:' + name, args=[self.plan.pk])).status_code, 200)
                    self.assertEqual(self.client.get(reverse('goplan:' + name, args=[self.autre_plan.pk])).status_code, 403)
            repair.assert_not_called()
        self.assertEqual(list(GTask.objects.filter(plan=self.plan).order_by('pk').values()), task_snapshot)
        response = self.client.get(reverse('goplan:taches_inline', args=[self.plan.pk]), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.plan.nom)

    def test_notifications_are_scoped(self):
        Notification.objects.create(utilisateur=self.user, projet=self.projet, titre='Notification autorisee', message='Visible')
        Notification.objects.create(utilisateur=self.user, projet=self.autre, titre='Notification confidentielle', message='Secret')
        for name in ['home', 'liste_notifications', 'notifications_non_lues_api']:
            with self.subTest(name=name):
                response = self.client.get(reverse('projets:' + name))
                self.assertEqual(response.status_code, 200)
                self.assertNotContains(response, 'Notification confidentielle')

    def test_personal_theme_is_allowed_but_profile_and_dossier_mutations_are_not(self):
        response = self.client.post(reverse('projets:set_theme'), {'theme': 'light'})
        self.assertEqual(response.status_code, 200)
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.theme, 'light')
        self.assertEqual(self.client.post(reverse('projets:modifier_utilisateur', args=[self.user.pk]),
                                         {'role': 'CHEF_PROJET'}).status_code, 403)

    def test_creation_form_allows_observer_only_in_creators_dossiers(self):
        chief = User.objects.create_user('chef-observateur')
        chief.profile.role = 'CHEF_PROJET'
        chief.profile.save()
        self.dossier.gerant = chief
        self.dossier.save()
        forbidden = Dossier.objects.create(nom='Dossier autre responsable')
        data = {
            'username': 'nouvel-observateur', 'role': 'OBSERVATEUR',
            'password1': 'ObserverPassword432!', 'password2': 'ObserverPassword432!',
            'dossiers': [self.dossier.pk],
        }
        form = UtilisateurCreationForm(data=data, user=chief)
        self.assertTrue(form.is_valid(), form.errors)
        created = form.save()
        self.assertEqual(created.profile.role, 'OBSERVATEUR')
        self.assertFalse(created.is_staff)
        self.assertEqual(list(created.dossiers.all()), [self.dossier])
        data['username'] = 'observateur-interdit'
        data['dossiers'] = [forbidden.pk]
        self.assertFalse(UtilisateurCreationForm(data=data, user=chief).is_valid())

    def test_existing_superuser_access_is_preserved(self):
        self.user.is_superuser = True
        self.user.save()
        self.assertTrue(projets_accessibles(self.user).filter(pk=self.autre.pk).exists())
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('projets:liste_utilisateurs')).status_code, 200)

    def test_admin_can_assign_observer_and_clear_legacy_staff_status(self):
        admin = User.objects.create_superuser('administrateur-observateur')
        self.user.is_staff = True
        self.user.profile.role = 'STAFF'
        self.user.profile.save()
        self.user.save()
        self.client.force_login(admin)
        response = self.client.post(reverse('projets:modifier_utilisateur', args=[self.user.pk]), {
            'role': 'OBSERVATEUR', 'is_active': 'on', 'dossiers': [self.dossier.pk],
        })
        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_staff)
        self.assertEqual(self.user.profile.role, 'OBSERVATEUR')
        response = self.client.get(reverse('projets:liste_utilisateurs'), {'role': 'OBSERVATEUR'})
        self.assertContains(response, self.user.username)
        self.assertContains(response, 'Observateur')

    def test_ui_url_policy_matches_server_for_representative_routes(self):
        for name, args, method in [
            ('projets:home', [], 'GET'),
            ('projets:lots_projet', [self.projet.pk], 'GET'),
            ('projets:changer_statut_attachement', [self.attachement.pk], 'POST'),
            ('projets:set_theme', [], 'POST'),
            ('goplan:gantt_plan', [self.plan.pk], 'GET'),
        ]:
            url = reverse(name, args=args)
            match = resolve(url)
            ui_allowed = any(method in rule['methods'] and re.fullmatch(rule['pattern'], url)
                             for rule in observer_url_patterns())
            self.assertEqual(ui_allowed, observer_route_allowed(match.namespace, match.url_name, method))

    def test_existing_unlinked_plan_becomes_visible_after_manager_assigns_project(self):
        orphan = GPlan.objects.create(nom='Planning existant non rattache', date_debut=date(2025, 1, 1))
        url = reverse('goplan:liste_plans')
        self.assertNotContains(self.client.get(url), orphan.nom)
        chief = User.objects.create_user('responsable-planning')
        self.dossier.gerant = chief
        self.dossier.save()
        self.client.force_login(chief)
        edit_url = reverse('goplan:modifier_plan', args=[orphan.pk])
        for headers in [{}, {'HTTP_HX_REQUEST': 'true'}]:
            response = self.client.get(edit_url, **headers)
            self.assertContains(response, 'name="projet"')
            self.assertContains(response, self.projet.nom)
            self.assertNotContains(response, self.autre.nom)
        response = self.client.post(edit_url, {
            'nom': orphan.nom, 'date_debut': '2025-01-01', 'projet': self.projet.pk,
        })
        self.assertEqual(response.status_code, 302)
        orphan.refresh_from_db()
        self.assertEqual(orphan.source_object, self.projet)
        self.client.force_login(self.user)
        self.assertContains(self.client.get(url), orphan.nom)
        self.assertEqual(self.client.get(reverse('goplan:gantt_plan', args=[orphan.pk])).status_code, 200)
        self.assertEqual(self.client.post(edit_url, {'projet': self.autre.pk}).status_code, 403)

    def test_project_assignment_is_scoped_and_can_be_cleared_explicitly(self):
        chief = User.objects.create_user('responsable-rattachement')
        self.dossier.utilisateurs.add(chief)
        data = {'nom': 'Planning formulaire', 'date_debut': '2025-01-01', 'projet': self.autre.pk}
        form = GPlanForm(data=data, user=chief)
        self.assertFalse(form.is_valid())
        self.assertIn('projet', form.errors)
        data['projet'] = self.projet.pk
        form = GPlanForm(data=data, user=chief)
        self.assertTrue(form.is_valid(), form.errors)
        plan = form.save()
        self.assertEqual(plan.source_object, self.projet)
        self.assertEqual(GPlanForm(instance=plan, user=chief).initial['projet'], self.projet.pk)
        data.pop('projet')
        form = GPlanForm(data=data, instance=plan, user=chief)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().source_object, self.projet)
        data['projet'] = ''
        form = GPlanForm(data=data, instance=plan, user=chief)
        self.assertTrue(form.is_valid(), form.errors)
        plan = form.save()
        plan.refresh_from_db()
        self.assertIsNone(plan.content_type_id)
        self.assertIsNone(plan.object_id)

    def test_existing_foreign_project_link_cannot_be_changed_by_unassigned_user(self):
        outsider = User.objects.create_user('sans-dossier-planning')
        form = GPlanForm(
            data={'nom': self.plan.nom, 'date_debut': '2025-01-10', 'projet': ''},
            instance=self.plan, user=outsider,
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().source_object, self.projet)
