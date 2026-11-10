from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from projets.models import ChiffreAffaire, LigneBordereau, LigneChiffreAffaire, LotProjet
from projets.models.decomptes import LigneAttachement
from projets.services.avancement_projet import avancement_ttc
from projets.tests.test_attachements import AttachementTestData


@override_settings(STORAGES={
    'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
    'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
})
class AvancementProjetTests(AttachementTestData, TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create_superuser(username='dashboard-production')
        self.client.force_login(self.user)
        self.today = date(2025, 2, 15)
        self.lot.taux_tva = Decimal('20')
        self.lot.save()

    def ca(self, month, quantity, montant, status='VALIDE'):
        ca = ChiffreAffaire.objects.create(
            projet=self.projet, periode=date(2025, month, 1),
            montant_mensuel=montant, statut=status,
        )
        LigneChiffreAffaire.objects.create(
            ca=ca, ligne_bordereau=self.ligne_bordereau, numero='1', designation='Travaux',
            unite='m', quantite_marche=100, prix_unitaire=10, quantite_cumulee=quantity,
        )
        return ca

    def attachment(self, sequence, quantity):
        att = self.create_attachement(sequence, date(2025, 1, 10), date(2025, 1, 31), 'VALIDE')
        LigneAttachement.objects.bulk_create([LigneAttachement(
            attachement=att, ligne_lot=self.ligne_bordereau, numero='1', designation='Travaux',
            unite='m', quantite_initiale=100, prix_unitaire=10,
            quantite_realisee=quantity, quantite_cumulee=quantity,
        )])

    def test_latest_ca_cumulative_not_monthly_and_tax_by_lot(self):
        self.ca(1, '40', '400')
        ca = self.ca(2, '50', '100', status='BROUILLON')
        other_lot = LotProjet.objects.create(projet=self.projet, nom='Exonere', taux_tva=0)
        line = LigneBordereau.objects.create(lot=other_lot, numero='2', designation='Autre', unite='m', quantite=100, prix_unitaire=10)
        LigneChiffreAffaire.objects.create(
            ca=ca, ligne_bordereau=line, numero='2', designation='Autre', unite='m',
            quantite_marche=100, prix_unitaire=10, quantite_cumulee=20,
        )
        result = avancement_ttc(self.projet, list(self.projet.lots.all()), Decimal('2200'), self.today)
        self.assertEqual(result['montant_ttc'], Decimal('800'))
        self.assertAlmostEqual(result['pourcentage'], Decimal('800') / 22)
        self.assertTrue(result['provisoire'])

    def test_missing_data_and_zero_market(self):
        lots = list(self.projet.lots.all())
        self.assertIsNone(avancement_ttc(self.projet, lots, Decimal('0'), self.today)['montant_ttc'])
        self.ca(1, '0', '0')
        result = avancement_ttc(self.projet, lots, Decimal('0'), self.today)
        self.assertEqual(result['montant_ttc'], 0)
        self.assertIsNone(result['pourcentage'])

    def test_validated_attachment_fallback_and_future_ca_exclusion(self):
        self.attachment(1, 30)
        self.ca(3, '80', '800')
        result = avancement_ttc(self.projet, [self.lot], Decimal('1200'), self.today)
        self.assertEqual(result['montant_ttc'], Decimal('360'))
        self.assertEqual(result['pourcentage'], 30)
        self.assertIn('Attachement', result['source'])

    def test_dashboard_full_and_htmx_show_summary(self):
        self.ca(1, '50', '500')
        url = reverse('projets:dashboard', args=[self.projet.pk])
        for headers in [{}, {'HTTP_HX_REQUEST': 'true'}]:
            response = self.client.get(url, **headers)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context['avancement_production']['montant_ttc'], Decimal('600'))
            self.assertContains(response, 'CA cumulé TTC')
            self.assertContains(response, '50,0 %')
