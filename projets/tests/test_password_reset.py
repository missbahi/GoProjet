import re

from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
)
class PasswordResetTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user('alice', 'alice@example.test', 'Ancien-mdp-123')
        User.objects.create_user('inactif', 'inactif@example.test', 'x', is_active=False)

    def setUp(self):
        cache.clear()
        self.url = reverse('password_reset')

    def test_reponse_identique_pour_compte_connu_et_inconnu(self):
        connu = self.client.post(self.url, {'email': 'alice@example.test'})
        inconnu = self.client.post(self.url, {'email': 'personne@example.test'})
        self.assertRedirects(connu, reverse('password_reset_done'))
        self.assertRedirects(inconnu, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['alice@example.test'])

    def test_compte_inactif_ne_recoit_rien(self):
        self.client.post(self.url, {'email': 'inactif@example.test'})
        self.assertEqual(len(mail.outbox), 0)

    def test_limite_de_demandes_par_adresse(self):
        for _ in range(7):
            response = self.client.post(self.url, {'email': 'alice@example.test'})
            self.assertRedirects(response, reverse('password_reset_done'))
        self.assertEqual(len(mail.outbox), 5)

    def test_parcours_complet_et_lien_a_usage_unique(self):
        self.client.post(self.url, {'email': 'alice@example.test'})
        corps = mail.outbox[0].body
        self.assertIn('3 jours', corps)
        lien = re.search(r'/accounts/reset/[^\s]+', corps).group(0)
        reponse = self.client.get(lien, follow=True)
        formulaire = reponse.redirect_chain[-1][0]
        reponse = self.client.post(formulaire, {
            'new_password1': 'Nouveau-mdp-9876!', 'new_password2': 'Nouveau-mdp-9876!',
        })
        self.assertRedirects(reponse, reverse('password_reset_complete'))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password('Nouveau-mdp-9876!'))
        self.assertContains(self.client.get(lien), 'invalide', status_code=200)

    def test_jeton_invalide_refuse(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        reponse = self.client.get(reverse('password_reset_confirm', args=[uid, 'abc-def']))
        self.assertContains(reponse, 'invalide')
        self.assertFalse(default_token_generator.check_token(self.user, 'abc-def'))
