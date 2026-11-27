from datetime import timedelta
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from projets.services.meteo import open_meteo
from projets.services.meteo.open_meteo import MeteoIndisponible, determiner_condition, meteo_du_jour
from projets.tests.test_rapports_journaliers import RapportJournalierTestBase

GEOCODAGE = {'results': [{'latitude': 33.59, 'longitude': -7.62, 'name': 'Casablanca'}]}


def reponse_quotidienne(code_wmo=63, tmax=21.4, tmin=12.0, vent=18.0):
    return {'daily': {
        'time': ['2026-11-27'], 'weather_code': [code_wmo],
        'temperature_2m_max': [tmax], 'temperature_2m_min': [tmin], 'wind_speed_10m_max': [vent],
    }}


class FauxOpenMeteo:
    """Remplace _get_json : enregistre les appels, aucun accès réseau."""

    def __init__(self, quotidien=None):
        self.appels = []
        self.quotidien = quotidien or reponse_quotidienne()

    def __call__(self, url, params):
        self.appels.append((url, params))
        return GEOCODAGE if '/search' in url else self.quotidien


class DeterminerConditionTests(SimpleTestCase):
    def test_phenomene_actif_prioritaire(self):
        self.assertEqual(determiner_condition(95, 40, 20, 50), 'THUNDERSTORM')

    def test_tempete_prime_sur_tout(self):
        self.assertEqual(determiner_condition(63, 20, 10, 80), 'STORM')

    def test_conditions_derivees_par_ciel_calme(self):
        self.assertEqual(determiner_condition(0, 25, 15, 45), 'WINDY')
        self.assertEqual(determiner_condition(1, 41, 25, 10), 'HOT')
        self.assertEqual(determiner_condition(0, 8, -2, 5), 'FROST')
        self.assertEqual(determiner_condition(0, 22, 12, 10), 'CLEAR')

    def test_code_inconnu(self):
        self.assertIsNone(determiner_condition(999, 20, 10, 5))


@override_settings(METEO_EN_LIGNE=True, METEO_API_KEY='', METEO_PAYS='MA')
class MeteoDuJourTests(SimpleTestCase):
    def setUp(self):
        cache.clear()
        self.aujourd_hui = timezone.localdate()

    def test_desactivee_par_defaut(self):
        with override_settings(METEO_EN_LIGNE=False), self.assertRaises(MeteoIndisponible):
            meteo_du_jour('Casablanca', self.aujourd_hui)

    def test_meteo_du_jour_et_cache(self):
        faux = FauxOpenMeteo()
        with patch.object(open_meteo, '_get_json', faux):
            meteo = meteo_du_jour('Casablanca', self.aujourd_hui)
            meteo_du_jour('Casablanca', self.aujourd_hui)

        self.assertEqual(meteo.code, 'RAIN')
        self.assertEqual(meteo.libelle, 'Pluie modérée')
        self.assertEqual(meteo.temperature_max, 21.4)
        self.assertEqual(meteo.lieu, 'Casablanca')
        self.assertEqual(len(faux.appels), 2)  # 1 géocodage + 1 météo, le 2e appel vient du cache
        url_geo, params_geo = faux.appels[0]
        self.assertEqual(url_geo, 'https://geocoding-api.open-meteo.com/v1/search')
        self.assertEqual(params_geo['countryCode'], 'MA')
        _, params_meteo = faux.appels[1]
        self.assertEqual(params_meteo['start_date'], self.aujourd_hui.isoformat())

    def test_cle_commerciale_utilise_les_hotes_customer(self):
        faux = FauxOpenMeteo()
        with override_settings(METEO_API_KEY='cle-test'), patch.object(open_meteo, '_get_json', faux):
            meteo_du_jour('Casablanca', self.aujourd_hui)
        self.assertTrue(all(url.startswith('https://customer-') for url, _ in faux.appels))

    def test_date_hors_fenetre_sans_appel_reseau(self):
        faux = FauxOpenMeteo()
        with patch.object(open_meteo, '_get_json', faux), self.assertRaises(MeteoIndisponible):
            meteo_du_jour('Casablanca', self.aujourd_hui - timedelta(days=200))
        self.assertEqual(faux.appels, [])

    def test_lieu_introuvable_memorise(self):
        appels = []

        def faux(url, params):
            appels.append(url)
            return {}

        with patch.object(open_meteo, '_get_json', faux):
            for _ in range(2):
                with self.assertRaises(MeteoIndisponible):
                    meteo_du_jour('Lieu imaginaire', self.aujourd_hui)
        self.assertEqual(len(appels), 1)


class ApiMeteoRapportTests(RapportJournalierTestBase):
    def setUp(self):
        super().setUp()
        cache.clear()
        self.url = reverse('projets:api_meteo_rapport', args=[self.projet.pk])
        self.url_ajout = reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk])

    def test_desactivee_aucun_bouton_et_reponse_explicite(self):
        page = self.client.get(self.url_ajout)
        self.assertNotContains(page, 'data-meteo-url')
        reponse = self.client.get(self.url, {'date': timezone.localdate().isoformat()}).json()
        self.assertFalse(reponse['success'])

    @override_settings(METEO_EN_LIGNE=True)
    def test_activee_bouton_et_donnees(self):
        page = self.client.get(self.url_ajout)
        self.assertContains(page, 'data-meteo-url')
        self.assertContains(page, 'data-meteo-auto="1"')

        with patch.object(open_meteo, '_get_json', FauxOpenMeteo()):
            reponse = self.client.get(self.url, {'date': timezone.localdate().isoformat()}).json()

        self.assertTrue(reponse['success'])
        self.assertEqual(reponse['code'], 'RAIN')
        self.assertIn('Open-Meteo', reponse['attribution'])

    @override_settings(METEO_EN_LIGNE=True)
    def test_date_invalide(self):
        self.assertEqual(self.client.get(self.url, {'date': 'demain'}).status_code, 400)
