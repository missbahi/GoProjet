# projets/services/dashboard_contexte.py
"""
Construction du contexte du dashboard projet, filtré par les modules actifs.

Chaque builder est une fonction `(user, projet) -> dict`. Le registry associe
une clé de module à un builder ; seuls les modules actifs sont exécutés.
"""

from decimal import Decimal

from django.db.models import Q

from projets.decorators import peut_gerer_projet
from projets.models import (
    Attachement, Decompte, DocumentAdministratif, OrdreService,
    SuiviExecution,
)
from projets.modules import modules_desactives
from projets.services.avancement_projet import avancement_ttc
from projets.services.revision_readiness import indicateur_revision_tableau_bord
from projets.utils.navigation import project_crumbs


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _formater_montant(montant):
    if not montant:
        return '0.00'
    return '{:,.2f}'.format(montant).replace(',', ' ')


def _osc_de_reference(ordre_services):
    """OSC notifié le plus ancien (point de départ du délai contractuel)."""
    return min(
        (
            ordre for ordre in ordre_services.filter(
                statut='NOTIFIE', date_effet__isnull=False,
            ).select_related('type_os').order_by('date_effet', 'ordre_sequence')
            if ordre.type_os.code == 'OSC'
        ),
        key=lambda ordre: ordre.ordre_sequence,
        default=None,
    )


# ─────────────────────────────────────────────────────────────
# Builders par module
# ─────────────────────────────────────────────────────────────

def _builder_rapports_journaliers(user, projet):
    rapports = projet.rapports_journaliers.all()
    return {
        'rapports_journaliers': rapports,
        'dernier_rapport_journalier': rapports.first(),
    }


def _builder_situations(user, projet):
    situations = projet.situations_mensuelles.all()
    return {
        'situations_mensuelles': situations,
        'derniere_situation_mensuelle': situations.first(),
    }


def _builder_ressources(user, projet):
    return {'ressources_count': projet.ressources_affectees.count()}


def _builder_lots(user, projet):
    """Lots + montant total : utiles dès qu'un module financier est actif."""
    lots = projet.lots.all()
    montant_total = sum((lot.montant_total_ttc for lot in lots), Decimal('0'))
    return {
        'lots': lots,
        'montant_total': _formater_montant(montant_total),
    }


def _builder_decomptes(user, projet):
    decomptes = Decompte.objects.filter(attachement__projet=projet)
    return {
        'total_decomptes': decomptes.count(),
        'decomptes_payes': decomptes.filter(statut='PAYE').count(),
        'decomptes_emis': decomptes.filter(statut='EMIS').count(),
        'decomptes_retard': decomptes.filter(statut='EN_RETARD').count(),
        'decomptes_recents': decomptes.order_by('-date_emission')[:5],
    }


def _builder_attachements(user, projet):
    return {'attachements': Attachement.objects.filter(projet=projet)}


def _builder_documents(user, projet):
    return {
        'documents_administratifs': DocumentAdministratif.objects.filter(projet=projet),
    }


def _builder_ordres_service(user, projet):
    ordre_services = OrdreService.objects.filter(projet=projet)
    return {
        'ordre_services': ordre_services,
        'osc': _osc_de_reference(ordre_services),
    }


def _builder_suivi(user, projet):
    return {'suivis_execution': SuiviExecution.objects.filter(projet=projet)}


def _builder_revision_prix(user, projet):
    return {'indicateur_revision': indicateur_revision_tableau_bord(projet)}


def _builder_avancement(user, projet):
    """Avancement production : nécessite lots + montant total + OSC."""
    lots = list(projet.lots.all())
    montant_total = sum((lot.montant_total_ttc for lot in lots), Decimal('0'))
    from django.utils import timezone
    today = timezone.localdate()
    return {
        'avancement_production': avancement_ttc(projet, lots, montant_total, today),
    }


# ─────────────────────────────────────────────────────────────
# Registry : clé module → liste de builders
# ─────────────────────────────────────────────────────────────
#
# Plusieurs modules peuvent partager un builder (ex. 'lots' est utile à
# 'decomptes', 'attachements', 'os'…). On évite les doublons via un set.
#
BUILDERS_PAR_MODULE = {
    'rapports_journaliers': [_builder_rapports_journaliers],
    'situations': [_builder_situations],
    'ressources': [_builder_ressources],
    'decomptes': [_builder_decomptes, _builder_lots, _builder_avancement],
    'attachements': [_builder_attachements, _builder_lots],
    'documents': [_builder_documents],
    'os': [_builder_ordres_service, _builder_lots],
    'suivi': [_builder_suivi],
    'revision_prix': [_builder_revision_prix],
}


def construire_contexte_dashboard(user, projet):
    """
    Retourne le dict de contexte du dashboard, limité aux modules actifs.

    Le contexte de base (projet, permissions, breadcrumb) est toujours inclus.
    Chaque builder n'est exécuté qu'une seule fois, même si plusieurs modules
    actifs le référencent.
    """
    desactives = modules_desactives(user)
    afficher_decomptes = 'etat_decomptes_dashboard' not in desactives
    ctx = {
        'projet': projet,
        'can_handler': peut_gerer_projet(user),
        'afficher_decomptes': afficher_decomptes,
        'breadcrumb_items': project_crumbs(projet),
    }

    builders_executes = set()
    for module_key, builders in BUILDERS_PAR_MODULE.items():
        if module_key in desactives:
            continue
        if module_key == 'decomptes' and not afficher_decomptes:
            continue
        for builder in builders:
            if builder in builders_executes:
                continue
            builders_executes.add(builder)
            ctx.update(builder(user, projet))

    return ctx