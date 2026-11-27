"""Météo en ligne d'une journée de chantier, via Open-Meteo (https://open-meteo.com).

Conditions d'utilisation (à respecter avant d'activer en production) :
- l'API gratuite est réservée à un usage NON commercial ; une application
  commerciale doit souscrire un abonnement et renseigner ``METEO_API_KEY``
  (les appels passent alors par les hôtes ``customer-*``) ;
- données sous licence CC BY 4.0 : la source doit être citée à l'écran.

Réglages (settings / variables d'environnement) :
- ``METEO_EN_LIGNE`` : active la fonctionnalité (désactivée par défaut) ;
- ``METEO_API_KEY`` : clé d'abonnement commercial (facultative) ;
- ``METEO_PAYS`` : code pays ISO pour lever les ambiguïtés de géocodage (« MA »).

Fonctionnement : la localisation du projet est géocodée (résultat mis en cache
30 jours), puis la météo de la journée est lue sur l'API de prévision, qui
couvre les 92 derniers jours et les 16 prochains (cache : 7 jours pour une date
passée, 1 heure sinon). Aucun appel réseau en dehors de cette fenêtre.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

from .conditions import METEO

logger = logging.getLogger(__name__)

ATTRIBUTION = 'Données météo : Open-Meteo.com (CC BY 4.0)'

JOURS_PASSES_MAX = 92
JOURS_FUTURS_MAX = 16
TIMEOUT_S = 4

# ---------------------------------------------------------------------------
# Codes WMO (utilisés par Open-Meteo) -> codes du catalogue des conditions
# ---------------------------------------------------------------------------
WMO_VERS_CONDITION: dict[int, str] = {
    0: 'CLEAR',
    1: 'PARTLY_CLOUDY',        # principalement dégagé
    2: 'MOSTLY_CLOUDY',
    3: 'OVERCAST',
    45: 'FOG',
    48: 'FOG',                 # brouillard givrant
    51: 'DRIZZLE', 53: 'DRIZZLE', 55: 'DRIZZLE',
    56: 'FREEZING_RAIN', 57: 'FREEZING_RAIN',
    61: 'LIGHT_RAIN',
    63: 'RAIN',
    65: 'HEAVY_RAIN',
    66: 'FREEZING_RAIN', 67: 'FREEZING_RAIN',
    71: 'LIGHT_SNOW',
    73: 'SNOW',
    75: 'HEAVY_SNOW',
    77: 'LIGHT_SNOW',          # grains de neige
    80: 'SHOWERS', 81: 'SHOWERS',
    82: 'HEAVY_RAIN',          # averses violentes
    85: 'LIGHT_SNOW',
    86: 'HEAVY_SNOW',
    95: 'THUNDERSTORM',
    96: 'HAIL',                # orage avec grêle
    99: 'HEAVY_THUNDERSTORM',
}

# Seuils des conditions « dérivées » (valeurs de la journée)
SEUIL_VENT_FORT = 40       # km/h, rafales soutenues -> Venteux
SEUIL_TEMPETE = 75         # km/h -> Tempête
SEUIL_CANICULE = 38        # °C (maximum du jour)
SEUIL_GEL = 0              # °C (minimum du jour)

CONDITIONS_CALMES = {'CLEAR', 'PARTLY_CLOUDY', 'MOSTLY_CLOUDY', 'OVERCAST'}


class MeteoIndisponible(Exception):
    """Météo en ligne impossible à obtenir (désactivée, lieu inconnu, réseau…)."""


def determiner_condition(code_wmo: Optional[int], temperature_max: Optional[float],
                         temperature_min: Optional[float], vent_max_kmh: Optional[float]) -> Optional[str]:
    """Code du catalogue pour une journée. Les phénomènes actifs restent prioritaires."""
    condition = WMO_VERS_CONDITION.get(code_wmo)
    vent = vent_max_kmh or 0
    if vent >= SEUIL_TEMPETE:
        return 'STORM'
    if condition in CONDITIONS_CALMES:
        if vent >= SEUIL_VENT_FORT:
            return 'WINDY'
        if temperature_max is not None and temperature_max >= SEUIL_CANICULE:
            return 'HOT'
        if temperature_min is not None and temperature_min <= SEUIL_GEL:
            return 'FROST'
    return condition


@dataclass
class MeteoDuJour:
    jour: date
    lieu: str
    code: Optional[str]              # code du catalogue (None si non déterminé)
    code_wmo: Optional[int]
    temperature_max: Optional[float]
    temperature_min: Optional[float]
    vent_max_kmh: Optional[float]

    @property
    def libelle(self) -> str:
        return METEO[self.code]['libelle'] if self.code in METEO else ''

    @property
    def icone(self) -> str:
        return METEO[self.code]['icone'] if self.code in METEO else 'fa-cloud-sun'

    def as_dict(self) -> dict:
        return {
            'jour': self.jour.isoformat(), 'lieu': self.lieu, 'code': self.code,
            'libelle': self.libelle, 'icone': self.icone, 'code_wmo': self.code_wmo,
            'temperature_max': self.temperature_max, 'temperature_min': self.temperature_min,
            'vent_max_kmh': self.vent_max_kmh, 'attribution': ATTRIBUTION,
        }


# ---------------------------------------------------------------------------
# Configuration et appels réseau
# ---------------------------------------------------------------------------
def meteo_en_ligne_active() -> bool:
    return bool(getattr(settings, 'METEO_EN_LIGNE', False))


def _hote(service: str) -> str:
    """Hôte gratuit, ou hôte « customer- » avec une clé d'abonnement."""
    prefixe = 'customer-' if getattr(settings, 'METEO_API_KEY', '') else ''
    return f'https://{prefixe}{service}.open-meteo.com/v1'


def _get_json(url: str, params: dict) -> dict:
    cle = getattr(settings, 'METEO_API_KEY', '')
    if cle:
        params = {**params, 'apikey': cle}
    requete = urllib.request.Request(
        f'{url}?{urllib.parse.urlencode(params)}',
        headers={'User-Agent': 'GoProjet/1.0'},
    )
    try:
        with urllib.request.urlopen(requete, timeout=TIMEOUT_S) as reponse:
            return json.loads(reponse.read().decode('utf-8'))
    except (urllib.error.URLError, TimeoutError, ValueError) as erreur:
        logger.warning('Open-Meteo indisponible : %s', erreur)
        raise MeteoIndisponible('Service météo en ligne indisponible.') from erreur


def geocoder(localisation: str) -> tuple[float, float, str]:
    """Localisation du projet -> (latitude, longitude, lieu affiché). Résultat en cache."""
    texte = (localisation or '').strip()
    if not texte:
        raise MeteoIndisponible("La localisation du projet n'est pas renseignée.")
    pays = getattr(settings, 'METEO_PAYS', '') or ''
    cle_cache = f'meteo:geo:{pays}:{texte.lower()}'
    position = cache.get(cle_cache)
    if position is None:
        params = {'name': texte, 'count': 1, 'language': 'fr', 'format': 'json'}
        if pays:
            params['countryCode'] = pays
        resultats = _get_json(f"{_hote('geocoding-api')}/search", params).get('results') or []
        # Mémorise aussi l'échec, pour ne pas réinterroger un lieu introuvable.
        position = (
            [resultats[0]['latitude'], resultats[0]['longitude'], resultats[0]['name']]
            if resultats else []
        )
        cache.set(cle_cache, position, 30 * 24 * 3600)
    if not position:
        raise MeteoIndisponible(f'Lieu introuvable pour la météo : « {texte} ».')
    return position[0], position[1], position[2]


def meteo_du_jour(localisation: str, jour: date) -> MeteoDuJour:
    """Météo d'une journée de chantier à la localisation du projet."""
    if not meteo_en_ligne_active():
        raise MeteoIndisponible('La météo en ligne est désactivée.')
    aujourd_hui = timezone.localdate()
    if not (aujourd_hui - timedelta(days=JOURS_PASSES_MAX) <= jour <= aujourd_hui + timedelta(days=JOURS_FUTURS_MAX)):
        raise MeteoIndisponible(
            f'Météo en ligne disponible du {JOURS_PASSES_MAX}e jour passé au {JOURS_FUTURS_MAX}e jour à venir.'
        )

    latitude, longitude, lieu = geocoder(localisation)
    cle_cache = f'meteo:jour:{latitude:.3f}:{longitude:.3f}:{jour.isoformat()}'
    quotidien = cache.get(cle_cache)
    if quotidien is None:
        donnees = _get_json(f"{_hote('api')}/forecast", {
            'latitude': latitude,
            'longitude': longitude,
            'daily': 'weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max',
            'timezone': 'auto',
            'start_date': jour.isoformat(),
            'end_date': jour.isoformat(),
        })
        jours = donnees.get('daily') or {}
        quotidien = {cle: (valeurs or [None])[0] for cle, valeurs in jours.items() if cle != 'time'}
        cache.set(cle_cache, quotidien, 7 * 24 * 3600 if jour < aujourd_hui else 3600)

    code_wmo = quotidien.get('weather_code')
    code_wmo = int(code_wmo) if code_wmo is not None else None
    temperature_max = quotidien.get('temperature_2m_max')
    temperature_min = quotidien.get('temperature_2m_min')
    vent = quotidien.get('wind_speed_10m_max')
    return MeteoDuJour(
        jour=jour, lieu=lieu,
        code=determiner_condition(code_wmo, temperature_max, temperature_min, vent),
        code_wmo=code_wmo, temperature_max=temperature_max,
        temperature_min=temperature_min, vent_max_kmh=vent,
    )
