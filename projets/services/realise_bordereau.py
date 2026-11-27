"""Quantité réalisée à date par ligne du bordereau.

Règle (par ligne de bordereau, à une date de référence) :

    réalisé = cumul officiel le plus récent + quantités des rapports journaliers postérieurs

- Cumul officiel : le plus grand des deux cumuls disponibles à la date de référence,
    * dernier attachement VALIDÉ dont la période est close (date_fin_periode <= date) ;
    * dernier CA mensuel (brouillon compris, signalé provisoire) dont le mois est
      terminé (fin de mois <= date) — un CA du mois en cours inclurait des jours
      postérieurs à la date.
  La source retenue fixe la date de base : seuls les rapports postérieurs à la fin
  de sa période s'y ajoutent (sans officiel, tous les rapports jusqu'à la date).
- Rapports journaliers : lignes de travaux liées à la ligne du bordereau, datées
  jusqu'à la date de référence ; un rapport peut être exclu (celui en cours de saisie).

Nombre de requêtes constant (4), quel que soit le nombre de lignes.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Optional

from projets.models import Attachement, ChiffreAffaire
from projets.models.chiffre_affaire import LigneChiffreAffaire
from projets.models.decomptes import LigneAttachement
from projets.models.suivi_projet import LigneTravailRapportJournalier

ZERO = Decimal('0')


@dataclass
class RealiseLigne:
    realise: Decimal = ZERO             # officiel + rapports postérieurs
    officiel: Decimal = ZERO
    source: str = ''                    # « Attachement n° 3 (validé) », « CA 10/2026 (brouillon) », ''
    date_base: Optional[date] = None    # fin de période de la source officielle
    rapports_apres: Decimal = ZERO
    provisoire: bool = False            # source officielle = CA en brouillon

    def as_dict(self) -> dict:
        return {
            'realise': str(self.realise), 'officiel': str(self.officiel), 'source': self.source,
            'date_base': self.date_base.isoformat() if self.date_base else None,
            'rapports_apres': str(self.rapports_apres), 'provisoire': self.provisoire,
        }


def _fin_de_mois(jour: date) -> date:
    return date(jour.year, jour.month, calendar.monthrange(jour.year, jour.month)[1])


def realise_par_ligne(projet, date_ref: date, exclure_rapport_id=None) -> dict[int, RealiseLigne]:
    """{id de ligne de bordereau: RealiseLigne} pour les lignes ayant un réalisé."""
    # 1. Dernier attachement validé dont la période est close.
    attachement = (
        Attachement.objects
        .filter(projet=projet, statut='VALIDE', date_fin_periode__lte=date_ref)
        .order_by('-sequence').first()
    )
    officiels = defaultdict(list)  # ligne -> [(quantité, date_base, libellé, provisoire)]
    if attachement:
        libelle = f'Attachement n° {attachement.numero} (validé)'
        for ligne_id, quantite in (
            LigneAttachement.objects.filter(attachement=attachement)
            .values_list('ligne_lot_id', 'quantite_cumulee')
        ):
            officiels[ligne_id].append((quantite or ZERO, attachement.date_fin_periode, libelle, False))

    # 2. Dernier CA mensuel dont le mois est terminé à la date de référence.
    dernier_mois_clos = (
        date_ref.replace(day=1) if date_ref == _fin_de_mois(date_ref)
        else (date_ref.replace(day=1) - date.resolution).replace(day=1)
    )
    ca = (
        ChiffreAffaire.objects
        .filter(projet=projet, periode__lte=dernier_mois_clos)
        .order_by('-periode').first()
    )
    if ca:
        brouillon = ca.statut == ChiffreAffaire.Statut.BROUILLON
        libelle = f"CA {ca.periode:%m/%Y} ({'brouillon' if brouillon else 'validé'})"
        for ligne_id, quantite in (
            LigneChiffreAffaire.objects.filter(ca=ca, est_titre=False)
            .values_list('ligne_bordereau_id', 'quantite_cumulee')
        ):
            officiels[ligne_id].append((quantite or ZERO, _fin_de_mois(ca.periode), libelle, brouillon))

    # 3. Rapports journaliers jusqu'à la date, par ligne et par jour.
    rapports = LigneTravailRapportJournalier.objects.filter(
        rapport__projet=projet, rapport__date__lte=date_ref, ligne_bordereau__isnull=False,
    )
    if exclure_rapport_id:
        rapports = rapports.exclude(rapport_id=exclure_rapport_id)
    par_jour = defaultdict(list)
    for ligne_id, jour, quantite in rapports.values_list('ligne_bordereau_id', 'rapport__date', 'quantite'):
        par_jour[ligne_id].append((jour, quantite or ZERO))

    resultat = {}
    for ligne_id in set(officiels) | set(par_jour):
        realise = RealiseLigne()
        candidats = officiels.get(ligne_id)
        if candidats:
            # Le plus grand cumul ; à égalité, le plus récent.
            quantite, date_base, libelle, provisoire = max(candidats, key=lambda c: (c[0], c[1]))
            realise.officiel, realise.date_base = quantite, date_base
            realise.source, realise.provisoire = libelle, provisoire
        realise.rapports_apres = sum(
            (q for jour, q in par_jour.get(ligne_id, []) if realise.date_base is None or jour > realise.date_base),
            ZERO,
        )
        realise.realise = realise.officiel + realise.rapports_apres
        resultat[ligne_id] = realise
    return resultat
