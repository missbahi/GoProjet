"""Conditions météorologiques proposées dans les rapports journaliers.

Catalogue sans dépendance (utilisé par le modèle et les formulaires).
Les codes sont stockés dans ``RapportJournalier.meteo`` (CharField). Les anciennes
saisies en texte libre restent valides : elles sont affichées telles quelles.
"""

# (libellé du groupe, [(code, libellé, icône Font Awesome), ...])
METEO_GROUPES = [
    ('☀️ Ciel dégagé / nuageux', [
        ('CLEAR', 'Beau temps / Ensoleillé', 'fa-sun'),
        ('CLEAR_NIGHT', 'Nuit claire', 'fa-moon'),
        ('PARTLY_CLOUDY', 'Partiellement nuageux', 'fa-cloud-sun'),
        ('MOSTLY_CLOUDY', 'Très nuageux', 'fa-cloud'),
        ('OVERCAST', 'Couvert', 'fa-cloud'),
    ]),
    ('🌫️ Visibilité réduite', [
        ('FOG', 'Brouillard', 'fa-smog'),
        ('MIST', 'Brume', 'fa-smog'),
        ('HAZE', 'Brume sèche', 'fa-smog'),
        ('SMOKE', 'Fumée', 'fa-smog'),
        ('DUST', 'Poussière / Sable (chergui, sirocco…)', 'fa-wind'),
    ]),
    ('🌦️ Pluie', [
        ('DRIZZLE', 'Bruine', 'fa-cloud-rain'),
        ('LIGHT_RAIN', 'Pluie légère', 'fa-cloud-rain'),
        ('RAIN', 'Pluie modérée', 'fa-cloud-showers-heavy'),
        ('HEAVY_RAIN', 'Forte pluie', 'fa-cloud-showers-heavy'),
        ('SHOWERS', 'Averses', 'fa-cloud-sun-rain'),
        ('FREEZING_RAIN', 'Pluie verglaçante', 'fa-cloud-meatball'),
    ]),
    ('⛈️ Orages', [
        ('THUNDERSTORM', 'Orage', 'fa-cloud-bolt'),
        ('HEAVY_THUNDERSTORM', 'Orage violent', 'fa-cloud-bolt'),
        ('HAIL', 'Grêle', 'fa-cloud-meatball'),
    ]),
    ('❄️ Neige / Glace', [
        ('LIGHT_SNOW', 'Neige légère', 'fa-snowflake'),
        ('SNOW', 'Neige', 'fa-snowflake'),
        ('HEAVY_SNOW', 'Fortes chutes de neige', 'fa-snowflake'),
        ('SLEET', 'Neige fondue', 'fa-cloud-meatball'),
        ('BLIZZARD', 'Blizzard / Tempête de neige', 'fa-snowflake'),
        ('ICE', 'Verglas', 'fa-icicles'),
    ]),
    ('💨 Vent et phénomènes extrêmes', [
        ('WINDY', 'Venteux', 'fa-wind'),
        ('STORM', 'Tempête', 'fa-wind'),
        ('SANDSTORM', 'Tempête de sable', 'fa-wind'),
        ('TORNADO', 'Tornade', 'fa-tornado'),
        ('HURRICANE', 'Ouragan / Cyclone', 'fa-hurricane'),
    ]),
    ('🌡️ Températures', [
        ('HOT', 'Canicule / Très chaud', 'fa-temperature-high'),
        ('COLD', 'Grand froid', 'fa-temperature-low'),
        ('FROST', 'Gel / Gelée', 'fa-icicles'),
    ]),
]

#: Choix rapides proposés sous la liste (conditions les plus fréquentes).
METEO_RAPIDES = ['CLEAR', 'PARTLY_CLOUDY', 'OVERCAST', 'RAIN', 'WINDY', 'HOT']

METEO_ICONE_DEFAUT = 'fa-cloud-sun'

METEO = {
    code: {'code': code, 'libelle': libelle, 'icone': icone, 'groupe': groupe}
    for groupe, conditions in METEO_GROUPES
    for code, libelle, icone in conditions
}

#: Choix groupés au format Django (optgroups).
METEO_CHOICES = [
    (groupe, [(code, libelle) for code, libelle, _ in conditions])
    for groupe, conditions in METEO_GROUPES
]


def meteo_libelle(valeur):
    """Libellé d'un code météo ; une ancienne saisie libre est rendue telle quelle."""
    condition = METEO.get(valeur)
    return condition['libelle'] if condition else (valeur or '')


def meteo_icone(valeur):
    condition = METEO.get(valeur)
    return condition['icone'] if condition else METEO_ICONE_DEFAUT
