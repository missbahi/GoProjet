"""Version de l'application et changelog."""

# Bump cette valeur à chaque release notable
APP_VERSION = "2.10.0"

# Semver : MAJOR.MINOR.PATCH
# MAJOR = changement breaking / grosse feature
# MINOR = nouvelle feature
# PATCH = correctif


# Changelog : le plus récent EN PREMIER
# Une entrée = ce que voit l'utilisateur au login
CHANGELOG = {
    "2.10.0": {
        "date": "2026-11-27",
        "titre": "Lignes BPU dans les rapports et passation entre administrateurs",
        "highlights": [
            "Rapports journaliers : bouton « Lignes BPU » pour ajouter des prestations du bordereau, liées à leur prix",
            "Réalisé à date par prix : dernier attachement validé ou CA, complété par les rapports journaliers postérieurs",
            "Passation : un administrateur de dossier peut renoncer à son rôle s'il laisse un autre administrateur actif",
            "Le menu Utilisateurs n'apparaît plus pour les rôles qui n'y ont pas accès",
            "Les comptes créés hors de l'application n'ont aucun accès tant qu'un rôle ne leur est pas attribué",
        ],
        "niveau": "info",
    },
    "2.9.0": {
        "date": "2026-11-27",
        "titre": "Rapports journaliers : impression, reproduction et météo",
        "highlights": [
            "Aperçu avant impression du rapport journalier : cartouche, photos, signatures, montants détaillés, en synthèse ou masqués",
            "Reproduire un rapport existant : dépenses et stocks pré-remplis, le stock restant devient le point de départ",
            "Date proposée automatiquement (lendemain du dernier rapport du mois) et plusieurs rapports possibles le même jour, distingués par activité",
            "Choix de la météo dans une liste de conditions avec icônes et choix rapides",
            "Correction : la création d'un rapport avec des dépenses fonctionne à nouveau",
            "Formulaires et listes plus rapides (pagination, requêtes optimisées)",
        ],
        "niveau": "info",
    },
    "2.8.2": {
        "date": "2026-11-22",
        "titre": "Améliorations diverses",
        "highlights": [
            "Optimisations de performance et corrections de bugs mineurs",
            "Amélioration de la gestion des utilisateurs et des modules",
        ],
        "niveau": "info",
    },
    "2.8.1": {
        "date": "2026-11-21",
        "titre": "Correction de la modification des projets",
        "highlights": [
            "Le modal de modification d'un projet fonctionne à nouveau sans exiger les paramètres de révision masqués",
            "La configuration de révision existante est conservée lors des modifications générales",
        ],
        "niveau": "info",
    },
    "2.8.0": {
        "date": "2026-11-21",
        "titre": "Révision des prix et barres d'outils partagées",
        "highlights": [
            "Nouveau module de révision des prix : formules prédéfinies, affectation aux lignes principales et contrôle de couverture",
            "Saisie matricielle des index avec copier-coller, mois extensibles, statuts définitifs/provisoires et contrôles de fraîcheur",
            "Calcul d'un ou de tous les attachements, prise en compte des arrêts/reprises et notes de calcul imprimables",
            "Barres d'outils factorisées pour le bordereau, les attachements, le contrôle et le chiffre d'affaires",
        ],
        "niveau": "info",
    },
    "2.7.3": {
        "date": "2026-11-17",
        "titre": "Envoi des e-mails",
        "highlights": [
            "Les e-mails de l'application partent désormais du domaine vérifié goprojet.ma",
        ],
        "niveau": "info",
    },
    "2.7.2": {
        "date": "2026-11-17",
        "titre": "Mot de passe oublié sécurisé",
        "highlights": [
            "La réinitialisation ne révèle plus si une adresse possède un compte",
            "Nombre de demandes de réinitialisation limité",
        ],
        "niveau": "info",
    },
    "2.7.1": {
        "date": "2026-11-16",
        "titre": "Tâches : notifications et visibilité",
        "highlights": [
            "Seul le responsable est notifié d'une tâche ; le créateur est prévenu à l'achèvement",
            "Les tâches ne sont visibles que par les personnes concernées",
            "Page de détail d'une tâche améliorée (fil d'Ariane, modification)",
        ],
        "niveau": "info",
    },
    "2.7.0": {
        "date": "2026-11-16",
        "titre": "Modules disponibles par utilisateur",
        "highlights": [
            "Le super-administrateur peut choisir les modules accessibles à chaque utilisateur",
            "Les modules indisponibles sont masqués du tableau de bord et inaccessibles",
        ],
        "niveau": "info",
    },
    "2.6.0": {
        "date": "2026-11-16",
        "titre": "Ordres de service : insertion de séquences et impressions",
        "highlights": [
            "Insertion d'une paire OSA/OSR (arrêt puis reprise, ou reprise puis arrêt) à l'intérieur de la séquence, avec renumérotation automatique",
            "Unicité de la numérotation des ordres de service par projet et aide métier intégrée",
            "Aperçus d'impression dédiés pour la liste des attachements (avec total HT) et la liste des ordres de service",
        ],
        "niveau": "info",
    },
    "2.5.0": {
        "date": "2026-11-14",
        "titre": "Rôles, dossiers et responsables des tâches",
        "highlights": [
            "Nouveaux rôles Administrateur de dossier et Directeur de projet, avec accès limités aux dossiers et projets autorisés",
            "Catalogues, ressources et calendriers privés au dossier ; consultation de toutes les catégories affectées pour l'Observateur",
            "Responsables des tâches filtrés par projet et hiérarchie, auto-rappels et chargement automatique des choix",
            "Avancement actualisable par le responsable de la tâche et conservation des affectations historiques",
            "Éditeurs CA et attachements harmonisés : plein écran, totaux visibles, colonne N° fixe et lignes hiérarchiques",
        ],
        "niveau": "info",
    },
    "2.4.0": {
        "date": "2026-11-11",
        "titre": "Observateur et consultation des dossiers",
        "highlights": [
            "Nouveau rôle Observateur : consultation des dossiers attribués, sans modification",
            "Ouverture sur Home après connexion et accès limité aux projets autorisés",
            "Bordereaux et plannings en lecture seule, avec impressions et exports",
            "Rattachement des plannings à un projet depuis leur formulaire pour les rendre visibles aux Observateurs du dossier",
        ],
        "niveau": "info",
    },
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