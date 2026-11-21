"""Catalogue des modules activables par utilisateur (maintenance, mises à jour)."""

MODULES = {
    'lots': {
        'label': 'Lots et bordereaux',
        'routes': {
            'lots_projet', 'ajouter_lot', 'modifier_lot', 'supprimer_lot', 'saisie_bordereau',
            'sauvegarder_config_bordereau', 'sauvegarder_lignes_bordereau',
            'export_bordereau_excel', 'apercu_impression_bordereau',
        },
    },
    'documents': {
        'label': 'Documents administratifs',
        'routes': {
            'documents', 'ajouter_document', 'supprimer_document',
            'telecharger_document', 'afficher_document',
        },
    },
    'os': {
        'label': 'Ordres de service',
        'routes': {
            'ordres_service', 'apercu_impression_ordres_service', 'modifier_ordre_service',
            'supprimer_ordre_service', 'details_ordre_service', 'notifier_ordre_service',
            'annuler_ordre_service', 'inserer_sequence_arret_reprise', 'corriger_sequence_os',
        },
    },
    'situations': {
        'label': 'Situations mensuelles',
        'routes': {
            'situations_mensuelles', 'ajouter_situation_mensuelle', 'apercu_situation_mensuelle',
            'modifier_situation_mensuelle', 'supprimer_situation_mensuelle',
            'supprimer_document_situation_mensuelle', 'valider_situation_mensuelle',
            'devalider_situation_mensuelle',
        },
    },
    'attachements': {
        'label': 'Attachements',
        'routes': {
            'liste_attachements', 'apercu_impression_attachements', 'ajouter_attachement',
            'modifier_attachement', 'detail_attachement', 'tracabilite_validation_attachement',
            'changer_statut_attachement', 'supprimer_attachement', 'corriger_periodes_attachements',
            'validation_attachement', 'reouvrir_attachement', 'transmettre_validation_attachement',
            'validation_technique_attachement', 'valider_etape', 'passer_etape', 'modifier_etape',
            'reinitialiser_etape', 'supprimer_etape', 'ajouter_etape',
        },
    },
    'suivi': {
        'label': "Suivi d'exécution",
        'routes': {
            'suivi_execution', 'ajouter_suivi', 'modifier_suivi', 'supprimer_suivi',
            'afficher_fichier_suivi', 'telecharger_fichier_suivi', 'supprimer_fichier_suivi',
            'ajouter_fichier_suivi',
        },
    },
    'ressources': {
        'label': 'Ressources',
        'routes': {
            'ressources_projet', 'ajouter_ressource', 'modifier_ressource', 'supprimer_ressource',
            'api_options_ressource', 'api_ateliers_projet',
        },
    },
    'rapports_journaliers': {
        'label': 'Rapports journaliers',
        'routes': {
            'rapports_journaliers', 'ajouter_rapport_journalier', 'formulaire_rapport_journalier',
            'detail_rapport_journalier', 'modifier_rapport_journalier',
            'supprimer_rapport_journalier', 'supprimer_document_rapport_journalier',
        },
    },
    'ateliers': {
        'label': 'Ateliers et planning des ateliers',
        'routes': {
            'ateliers_projet', 'ajouter_atelier', 'modifier_atelier', 'supprimer_atelier',
            'materiels_atelier', 'ajouter_affectation', 'modifier_affectation',
            'supprimer_affectation', 'planning_ateliers', 'apercu_impression_planning',
        },
    },
    'fiche_controle': {
        'label': "Fiche de contrôle d'attachements",
        'routes': {'fiche_controle'},
    },
    'decomptes': {
        'label': 'Décomptes',
        'routes': {
            'liste_decomptes', 'projet_ajouter_decompte', 'detail_decompte', 'modifier_decompte',
            'supprimer_decompte', 'calcul_retard_decompte', 'attachements_ajouter_decompte',
        },
    },
    'revision_prix': {
        'label': 'Révision des prix',
        'routes': {
            'gestion_revision_prix', 'creer_formule_revision',
            'modifier_formule_revision', 'supprimer_formule_revision',
            'affecter_formules_revision', 'enregistrer_mois_base_revision',
            'enregistrer_valeurs_indexes',
            'calculer_revision_attachement', 'note_calcul_revision_attachement',
            'calculer_tous_attachements_revision',
            'rapport_revision_tous_attachements',
        },
    },
    'ca': {
        'label': "Chiffre d'affaires mensuel",
        'routes': {
            'liste_ca', 'ajouter_ca', 'modifier_ca', 'valider_ca', 'devalider_ca', 'supprimer_ca',
        },
    },
    'taches': {
        'label': 'Tâches',
        'routes': {
            'liste_taches_projet', 'liste_taches', 'creer_tache', 'detail_tache',
            'modifier_tache', 'supprimer_tache', 'get_form_data',
        },
    },
    'goplan': {
        'label': 'Plannings GoPlan',
        'namespaces': {'goplan'},
    },
}

MODULE_CHOICES = [(key, module['label']) for key, module in MODULES.items()]


def module_pour_route(namespace, url_name):
    """Clé du module protégeant cette route, ou None si elle est hors catalogue."""
    for key, module in MODULES.items():
        if namespace in module.get('namespaces', ()):
            return key
        if namespace == 'projets' and url_name in module.get('routes', ()):
            return key
    return None


def modules_desactives(user):
    profile = getattr(user, 'profile', None)
    if user.is_superuser or profile is None:
        return frozenset()
    return frozenset(profile.modules_desactives or [])
