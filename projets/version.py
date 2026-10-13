"""Version de l'application et changelog."""

# ⚠️ Bump cette valeur à chaque release notable
from marshal import version


APP_VERSION = "1.2.0"

# Semver : MAJOR.MINOR.PATCH
# MAJOR = changement breaking / grosse feature
# MINOR = nouvelle feature
# PATCH = correctif


# Changelog : le plus récent EN PREMIER
# Une entrée = ce que voit l'utilisateur au login
CHANGELOG = {
    "1.2.0": {
        "date": "2026-10-14",
        "titre": "Ressources : recherche et navigation rapides",
        "highlights": [
            "Filtrez les ressources en tapant le code ou une partie du nom",
            "Les engins sont affichés « Code - Nom » pour les distinguer",
            "L'onglet actif est maintenant clairement mis en évidence",
            "Ouvrez directement un type de ressource via un lien partagé",
        ],
        "niveau": "info",  # info | warning | critical
    },
    "1.1.0": {
        "date": "2026-10-13",
        "titre": "Gestion des ressources du projet",
        "highlights": [
            "Affectez du personnel, matériel, locations, sous-traitances "
            "et fournitures à un projet",
            "Les rapports journaliers ne proposent plus que les ressources "
            "réellement mobilisées sur le chantier",
            "Validation automatique : impossible d'affecter 2 fois la même "
            "ressource sur des périodes qui se chevauchent",
        ],
        "niveau": "info",  # info | warning | critical
    },
}


def get_version_info(version=None):
    """Retourne les infos d'une version (ou de la version courante)."""
    v = version or APP_VERSION
    return {
        "version": v,
        "date": CHANGELOG.get(v, {}).get("date", ""),
        "titre": CHANGELOG.get(v, {}).get("titre", ""),
        "highlights": CHANGELOG.get(v, {}).get("highlights", []),
        "niveau": CHANGELOG.get(v, {}).get("niveau", "info"),
    }


def get_versions_between(old_version, new_version):
    """Retourne toutes les versions > old_version (utile si l'utilisateur
    ne s'est pas connecté depuis longtemps)."""
    if not old_version:
        return [get_version_info(new_version)]
    # Ordre décroissant dans CHANGELOG, donc on filtre simplement
    return [
        {"version": v, **info}
        for v, info in CHANGELOG.items()
        if _semver_gt(v, old_version)
    ]


def _semver_gt(a, b):
    """Compare 2 versions semver. Retourne True si a > b."""
    def parse(v):
        try:
            return tuple(int(x) for x in v.split("."))
        except (ValueError, AttributeError):
            return (0, 0, 0)
    return parse(a) > parse(b)