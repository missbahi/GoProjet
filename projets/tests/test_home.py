from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from projets.models import ChiffreAffaire, Dossier, LigneChiffreAffaire, Projet, Tache
from projets.models.decomptes import LigneAttachement
from projets.services.home_indicators import indicateurs_home
from projets.tests.test_attachements import AttachementTestData


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class HomeIndicatorsTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username='home-admin')
        self.dossier = Dossier.objects.create(nom='Home Travaux', activite='TRAVAUX', gerant=self.user)
        self.projet.dossier = self.dossier
        self.projet.statut = 'COURS'
        self.projet.date_debut = date(2025, 1, 10)
        self.projet.delai = 10
        self.projet.save()
        Projet.objects.filter(pk=self.projet.pk).update(avancement=99, en_retard=False)
        self.client.force_login(self.user)
        self.today = date(2025, 2, 15)

    def ca(self, month, quantity, montant, status='VALIDE', year=2025, initial='0'):
        ca = ChiffreAffaire.objects.create(
            projet=self.projet, periode=date(year, month, 1), statut=status,
            montant_mensuel=Decimal(montant), origine='REPRISE' if Decimal(initial) else 'DEBUT',
        )
        LigneChiffreAffaire.objects.create(
            ca=ca, ligne_bordereau=self.ligne_bordereau, numero='1', designation='Travaux',
            unite='m', quantite_marche=100, prix_unitaire=10,
            quantite_cumulee=Decimal(quantity), cumul_initial=Decimal(initial),
        )
        return ca

    def attachment(self, sequence, quantity, status='VALIDE'):
        att = self.create_attachement(
            sequence, date(2025, 1, 10) if sequence == 1 else date(2025, 2, 1),
            date(2025, 1, 31) if sequence == 1 else date(2025, 2, 14), status,
        )
        LigneAttachement.objects.bulk_create([LigneAttachement(
            attachement=att, ligne_lot=self.ligne_bordereau, numero='1', designation='Travaux',
            unite='m', quantite_initiale=100, prix_unitaire=10,
            quantite_realisee=quantity, quantite_cumulee=quantity,
        )])
        return att

    def home(self, htmx=False):
        with patch('projets.views.site_views.views.timezone.localdate', return_value=self.today):
            return self.client.get(reverse('projets:home'), **({'HTTP_HX_REQUEST': 'true'} if htmx else {}))

    def test_latest_ca_includes_draft_and_reprise_not_sum_of_cumuls(self):
        self.ca(1, '50', '100', initial='40')
        self.ca(2, '55', '50', status='BROUILLON')
        data = indicateurs_home([self.projet], self.today)
        self.assertEqual(self.projet.home_avancement, Decimal('55'))
        self.assertEqual(self.projet.home_cumul_ht, Decimal('550'))
        self.assertTrue(self.projet.home_provisoire)
        self.assertEqual(data['production_ca'], Decimal('550'))
        self.assertEqual(data['ca_annuel'], Decimal('150'))
        self.assertEqual(data['ca_annuel_brouillon'], Decimal('50'))
        self.assertEqual(data['nb_ca_brouillons'], 1)

    def test_year_boundaries_and_future_periods(self):
        self.ca(12, '40', '400', year=2024)
        self.ca(1, '50', '100')
        self.ca(2, '48', '-20', status='BROUILLON')
        self.ca(3, '80', '320', status='BROUILLON')
        data = indicateurs_home([self.projet], self.today)
        self.assertEqual(data['ca_annuel'], Decimal('80'))
        self.assertEqual(data['production_ca'], Decimal('480'))
        self.assertEqual(self.projet.home_avancement, Decimal('48'))

    def test_attachment_fallback_latest_validated_not_summed_with_ca(self):
        self.attachment(1, 30)
        second = self.attachment(2, 45, status='BROUILLON')
        data = indicateurs_home([self.projet], self.today)
        self.assertEqual(self.projet.home_avancement, Decimal('30'))
        self.assertEqual(data['attachements_valides'], Decimal('300'))
        type(second).objects.filter(pk=second.pk).update(statut='VALIDE')
        data = indicateurs_home([self.projet], self.today)
        self.assertEqual(data['attachements_valides'], Decimal('450'))
        self.assertEqual(self.projet.home_avancement, Decimal('45'))
        self.ca(1, '60', '600')
        data = indicateurs_home([self.projet], self.today)
        self.assertEqual(self.projet.home_avancement, Decimal('60'))
        self.assertEqual(data['attachements_valides'], Decimal('450'))
        self.assertEqual(data['ca_annuel'], Decimal('600'))

    def test_no_data_is_not_zero_and_zero_ca_does_not_use_attachment(self):
        indicateurs_home([self.projet], self.today)
        self.assertIsNone(self.projet.home_avancement)
        self.attachment(1, 30)
        self.ca(1, '0', '0')
        indicateurs_home([self.projet], self.today)
        self.assertEqual(self.projet.home_avancement, Decimal('0'))
        self.assertIn('CA', self.projet.home_source)

    def test_future_validated_attachment_does_not_replace_current_snapshot(self):
        self.attachment(1, 30)
        future = self.attachment(2, 45)
        type(future).objects.filter(pk=future.pk).update(date_fin_periode=date(2025, 3, 31))
        data = indicateurs_home([self.projet], self.today)
        self.assertEqual(self.projet.home_avancement, Decimal('30'))
        self.assertEqual(data['attachements_valides'], Decimal('300'))

    def test_missing_market_unknown_and_overrun_preserved(self):
        self.ca(1, '120', '1200')
        indicateurs_home([self.projet], self.today)
        self.assertEqual(self.projet.home_avancement, Decimal('120'))
        self.assertEqual(self.projet.home_progress, Decimal('100'))
        type(self.ligne_bordereau).objects.filter(pk=self.ligne_bordereau.pk).update(montant_calcule=0)
        indicateurs_home([self.projet], self.today)
        self.assertIsNone(self.projet.home_avancement)

    def test_home_table_chart_cards_agree_and_never_write_models(self):
        self.ca(1, '50', '500')
        self.ca(2, '55', '50', status='BROUILLON')
        with CaptureQueriesContext(connection) as queries:
            response = self.home()
        self.assertEqual(response.status_code, 200)
        writes = [q['sql'] for q in queries if q['sql'].lstrip().upper().startswith(('UPDATE', 'INSERT', 'DELETE'))]
        self.assertEqual(writes, [])
        project = response.context['projets_recents'][0]
        chart = response.context['chart_data']
        self.assertEqual(project.home_avancement, Decimal('55'))
        self.assertEqual(chart['projets'][0]['avancement'], 55)
        self.assertEqual(chart['stats']['avancement_moyen'], 55)
        self.assertNotIn('mensuel', chart)
        self.assertEqual(len(response.context['resume_cartes']), 4)
        self.assertContains(response, 'provisoire')
        self.assertContains(response, '55,0 %')
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.avancement, Decimal('99'))

    def test_htmx_fragment_no_nested_shell(self):
        response = self.home(htmx=True)
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<html')
        self.assertContains(response, 'Non disponible')
        self.assertNotContains(response, '% décomptes validés')

    def test_user_project_scope_and_upcoming_tasks(self):
        other = Projet.objects.create(nom='Secret', numero='HOME-SECRET', objet='Secret', maitre_ouvrage='MO', localisation='Site')
        ChiffreAffaire.objects.create(projet=other, periode=date(2025, 1, 1), montant_mensuel=99999)
        Tache.objects.create(projet=other, titre='Secret task', date_debut=self.today, date_fin=self.today)
        Tache.objects.create(projet=self.projet, titre='Finished task', date_debut=self.today, date_fin=self.today, terminee=True)
        Tache.objects.create(projet=self.projet, titre='Visible task', date_debut=self.today, date_fin=self.today)
        viewer = User.objects.create_user(username='home-viewer')
        self.dossier.utilisateurs.add(viewer)
        self.client.force_login(viewer)
        response = self.home()
        self.assertEqual(response.context['chart_data']['stats']['nb_projets'], 1)
        self.assertEqual(response.context['indicateurs_home']['ca_annuel'], Decimal('0'))
        self.assertContains(response, 'Visible task')
        self.assertNotContains(response, 'Secret task')
        self.assertNotContains(response, 'Finished task')
        self.assertNotContains(response, 'HOME-SECRET')

    def test_deadline_refreshed_without_stored_progress(self):
        self.ca(1, '100', '1000')
        indicateurs_home([self.projet], self.today)
        self.assertFalse(self.projet.home_en_retard)
        ChiffreAffaire.objects.get().lignes.update(quantite_cumulee=50)
        indicateurs_home([self.projet], self.today)
        self.assertTrue(self.projet.home_en_retard)

    def test_unknown_projects_excluded_from_mean(self):
        Projet.objects.create(nom='Sans suivi', numero='HOME-NONE', objet='Travaux', maitre_ouvrage='MO', localisation='Site', statut='COURS')
        self.ca(1, '40', '400')
        response = self.home()
        self.assertEqual(response.context['chart_data']['stats']['avancement_moyen'], 40)
        self.assertContains(response, '1/2 renseignés')

    def test_home_focuses_on_execution_with_general_slogan(self):
        response = self.home()
        self.assertContains(response, 'Vos projets, une vision claire.')
        self.assertContains(response, 'Pilotez vos travaux')
        self.assertNotContains(response, "Bureau d'Études Techniques")
        self.assertNotContains(response, "depuis l'appel d'offres")
        titles = [card['titre'] for card in response.context['resume_cartes']]
        self.assertEqual(len(titles), 4)
        self.assertNotIn("Appels d'offres", titles)
        self.assertNotIn('Réceptions validées', titles)
        self.assertNotIn('nouveaux_ao', response.context)
        self.assertNotIn('receptions_validees', response.context)

    def test_empty_portfolio_no_fake_progress_or_financial_bars(self):
        viewer = User.objects.create_user(username='home-empty')
        self.client.force_login(viewer)
        response = self.home()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['chart_data']['projets'], [])
        self.assertIsNone(response.context['chart_data']['stats']['avancement_moyen'])
        self.assertEqual(response.context['indicateurs_home']['ca_annuel'], Decimal('0'))
        self.assertContains(response, 'Aucun projet récent')

    def test_invalid_service_order_deadline_is_explicitly_reported(self):
        with patch.object(Projet, 'date_fin_previsionnelle', side_effect=ValidationError('Prolongation invalide')):
            response = self.home()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['nb_echeances_a_verifier'], 1)
        self.assertContains(response, 'Prolongation invalide')
        self.assertContains(response, 'empêchent le calcul du retard')
