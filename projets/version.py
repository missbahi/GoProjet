"""Version de l'application et changelog."""

# Bump cette valeur à chaque release notable
APP_VERSION = "2.3.2"

# Semver : MAJOR.MINOR.PATCH
# MAJOR = changement breaking / grosse feature
# MINOR = nouvelle feature
# PATCH = correctif


# Changelog : le plus récent EN PREMIER
# Une entrée = ce que voit l'utilisateur au login
CHANGELOG = {
    "2.3.2": {
        "date": "2026-11-11",
        "titre": "Validation depuis la liste des attachements",
        "highlights": [
            "Validation et dévalidation directement depuis la liste pour les utilisateurs autorisés",
            "Confirmation avant chaque action avec le numéro de l'attachement",
            "Notification du résultat et maintien des contrôles de période",
        ],
        "niveau": "info",
    },
    "2.3.1": {
        "date": "2026-11-11",
        "titre": "Continuité des attachements après arrêt",
        "highlights": [
            "La date de début d'un attachement tient compte des arrêts et reprises notifiés",
            "Le début attendu est reporté à la reprise lorsqu'il tombe dans une période d'arrêt",
            "Les corrections de périodes et la date proposée à la création suivent la même règle",
        ],
        "niveau": "info",
    },
    "2.3.0": {
        "date": "2026-11-10",
        "titre": "CA mensuel et suivi des travaux",
        "highlights": [
            "Suivi mensuel du chiffre d'affaires par quantités cumulées et alimentation des situations",
            "Formulaire CA compact avec tableau hiérarchique, contrôles de saisie et somme de sélection",
            "Édition des attachements avec TableView et corrections encadrées des périodes et cumuls",
            "Accueil et tableaux de bord actualisés avec la production et l'avancement des projets",
            "Validation simplifiée des dossiers travaux et actions de gestion des CA",
        ],
        "niveau": "info",
    },
    "2.2.0": {
        "date": "2026-11-07",
        "titre": "Bordereau de prix amélioré",
        "highlights": [
            "Tableau du bordereau modernisé avec sélection multiple et copier-coller",
            "Réglage direct des colonnes et de la hauteur des en-têtes",
            "Personnalisation et sauvegarde de l'apparence par lot",
        ],
        "niveau": "info",
    },
    "2.1.1": {
        "date": "2026-10-24",
        "titre": "Correctifs mineurs",
        "highlights": [
            "Correction de bugs mineurs",
            "Correction erreur de modification des liaisons de tâches",
        ],
        "niveau": "info",
    },
    "2.1.0": {
        "date": "2026-10-23",
        "titre": "Améliorations et correctifs",
        "highlights": [
            "Ajout de nouvelles fonctionnalités pour l'importation XML",
            "Amélioration de l'importation des fichiers XML existants",
            "Ajout d'une fonctionnalité d'Ordre de service pour avanant de prolongation de délai",
            "Amélioration des performances de l'interface",
            "Correction de bugs mineurs",
        ],
        "niveau": "info",
    },
    "2.0.0": {
        "date": "2026-10-22",
        "titre": "GoPlan : plannings et diagrammes de Gantt",
        "highlights": [
            "Créez vos plannings avec des calendriers de travail (jours chômés, exceptions)",
            "Saisissez les tâches en ligne : indentation, déplacement, repli des groupes",
            "Diagramme de Gantt interactif : liaisons, couleurs, forme des barres et des liaisons",
            "Importez et exportez vos plannings au format XML MS Project",
            "Imprimez en A4 à A0, sur plusieurs pages, avec en-têtes et pieds personnalisés",
            "Réglages d'impression enregistrés par planning : onglets, fond, largeur des colonnes",
        ],
        "niveau": "info",
    },
    "1.3.0": {
        "date": "2026-10-15",
        "titre": "Notifications système et validation des situations",
        "highlights": [
            "Recevez des notifications système sur votre bureau",
            "Le titre de l'onglet affiche le nombre de notifications non lues",
            "Validez une situation mensuelle en un clic : elle devient verrouillée et non modifiable",
            "Un administrateur peut rouvrir une situation validée si nécessaire",
        ],
        "niveau": "info",
    },
    "1.2.1": {
        "date": "2026-10-15",
        "titre": "Correctifs mineurs et améliorations",
        "highlights": [
            "Correction de bugs mineurs",
            "Amélioration des performances de l'interface",
        ],
        "niveau": "info",  # info | warning | critical
    },
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