"""Rôles : passation entre administrateurs de dossier, menus et rôle par défaut."""
from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from projets.models import Dossier


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class PassationAdminDossierTests(TestCase):
    def setUp(self):
        self.dossier = Dossier.objects.create(nom='Dossier passation')
        self.ancien = self.compte('admin-ancien', 'ADMIN_DOSSIER')
        self.nouveau = self.compte('admin-nouveau', 'ADMIN_DOSSIER')

    def compte(self, username, role, dossier=None):
        user = User.objects.create_user(username)
        user.profile.role = role
        user.profile.save()
        (dossier or self.dossier).utilisateurs.add(user)
        return user

    def modifier(self, actor, target, data, **headers):
        self.client.force_login(actor)
        return self.client.post(reverse('projets:modifier_utilisateur', args=[target.pk]), data, **headers)

    def role(self, user):
        user.profile.refresh_from_db()
        return user.profile.role

    def test_un_admin_ne_touche_pas_au_compte_d_un_collegue(self):
        url = reverse('projets:supprimer_utilisateur', args=[self.nouveau.pk])
        self.client.force_login(self.ancien)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(self.modifier(self.ancien, self.nouveau, {'role': 'CHEF_PROJET'}).status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.nouveau.pk, is_active=True).exists())
        self.assertEqual(self.role(self.nouveau), 'ADMIN_DOSSIER')

    def test_passation_un_admin_renonce_a_son_role(self):
        self.client.force_login(self.ancien)
        page = self.client.get(reverse('projets:modifier_utilisateur', args=[self.ancien.pk]))
        self.assertContains(page, 'name="role"')
        self.assertContains(page, 'Passation')

        response = self.modifier(self.ancien, self.ancien, {'role': 'CHEF_PROJET'})

        # Un chef de projet n'a plus accès à la liste des comptes : retour à l'accueil.
        self.assertRedirects(response, reverse('projets:home'), fetch_redirect_response=False)
        self.assertEqual(self.role(self.ancien), 'CHEF_PROJET')
        self.assertEqual(list(self.ancien.dossiers.all()), [self.dossier])

    def test_le_dernier_admin_actif_ne_peut_pas_renoncer(self):
        self.nouveau.is_active = False
        self.nouveau.save()
        self.client.force_login(self.ancien)
        page = self.client.get(reverse('projets:modifier_utilisateur', args=[self.ancien.pk]))
        self.assertNotContains(page, 'name="role"')

        response = self.modifier(self.ancien, self.ancien, {'role': 'CHEF_PROJET'})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.role(self.ancien), 'ADMIN_DOSSIER')

    def test_un_admin_d_un_autre_dossier_ne_compte_pas(self):
        self.nouveau.dossiers.clear()
        self.compte('admin-ailleurs', 'ADMIN_DOSSIER', dossier=Dossier.objects.create(nom='Ailleurs'))

        response = self.modifier(self.ancien, self.ancien, {'role': 'CHEF_PROJET'})

        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.role(self.ancien), 'ADMIN_DOSSIER')

    def test_la_gerance_historique_est_cedee_au_collegue(self):
        # Admin rattaché uniquement par le champ gérant (lien historique).
        self.ancien.dossiers.clear()
        self.dossier.gerant = self.ancien
        self.dossier.save()

        response = self.modifier(self.ancien, self.ancien, {'role': 'DIRECTEUR_PROJET'},
                                 HTTP_HX_REQUEST='true')

        self.assertEqual(response['HX-Redirect'], reverse('projets:liste_utilisateurs'))
        self.dossier.refresh_from_db()
        self.assertEqual(self.dossier.gerant, self.nouveau)
        # L'ancien admin reste membre du dossier, sans perdre l'accès.
        self.assertEqual(list(self.ancien.dossiers.all()), [self.dossier])
        self.assertEqual(self.role(self.ancien), 'DIRECTEUR_PROJET')


class MenusEtRoleParDefautTests(TestCase):
    def setUp(self):
        self.dossier = Dossier.objects.create(nom='Dossier menus')

    def compte(self, username, role):
        user = User.objects.create_user(username)
        user.profile.role = role
        user.profile.save()
        self.dossier.utilisateurs.add(user)
        return user

    def test_lien_utilisateurs_seulement_si_la_page_est_accessible(self):
        liste = reverse('projets:liste_utilisateurs')
        for role, autorise in [('ADMIN_DOSSIER', True), ('DIRECTEUR_PROJET', True),
                               ('CHEF_PROJET', False), ('CHEF_CHANTIER', False)]:
            with self.subTest(role=role):
                self.client.force_login(self.compte(f'menu-{role.lower()}', role))
                accueil = self.client.get(reverse('projets:home'))
                self.assertEqual(accueil.context['can_manage_users'], autorise)
                self.assertEqual(self.client.get(liste).status_code, 200 if autorise else 403)

    def test_role_par_defaut_sans_acces(self):
        user = User.objects.create_user('cree-hors-formulaire')
        self.assertEqual(user.profile.role, 'A_RECLASSER')
