from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from projets.models import ChiffreAffaire, LigneChiffreAffaire
from projets.models.decomptes import LigneAttachement
from projets.models.suivi_projet import LigneTravailRapportJournalier, RapportJournalier
from projets.services.realise_bordereau import realise_par_ligne
from projets.tests.test_attachements import AttachementTestData


class RealiseBordereauTests(AttachementTestData, TestCase):
    """réalisé = cumul officiel le plus récent + rapports postérieurs (à la date de référence)."""

    def attachement(self, sequence, fin, quantite, statut='VALIDE', debut=None):
        # Continuité imposée : le 1er attachement part de l'OS de commencement (10/01/2025).
        debut = debut or date(2025, 1, 10)
        att = self.create_attachement(sequence, debut, fin, statut)
        LigneAttachement.objects.bulk_create([LigneAttachement(
            attachement=att, ligne_lot=self.ligne_bordereau, numero='1', designation='Travaux',
            unite='m', quantite_initiale=100, prix_unitaire=10,
            quantite_realisee=quantite, quantite_cumulee=quantite,
        )])
        return att

    def ca(self, mois, quantite, statut='VALIDE'):
        ca = ChiffreAffaire.objects.create(projet=self.projet, periode=mois, statut=statut)
        LigneChiffreAffaire.objects.create(
            ca=ca, ligne_bordereau=self.ligne_bordereau, numero='1', designation='Travaux',
            unite='m', quantite_marche=100, prix_unitaire=10, quantite_cumulee=quantite,
        )
        return ca

    def rapport(self, jour, quantite):
        rapport = RapportJournalier.objects.create(projet=self.projet, date=jour)
        LigneTravailRapportJournalier.objects.create(
            rapport=rapport, ligne_bordereau=self.ligne_bordereau, designation='Travaux', quantite=Decimal(quantite),
        )
        return rapport

    def realise(self, jour, **kwargs):
        return realise_par_ligne(self.projet, jour, **kwargs).get(self.ligne_bordereau.pk)

    def test_sans_officiel_tous_les_rapports_jusqu_a_la_date(self):
        self.rapport(date(2025, 3, 3), '10')
        self.rapport(date(2025, 3, 4), '5')
        self.rapport(date(2025, 3, 20), '99')  # postérieur à la date de référence

        r = self.realise(date(2025, 3, 10))

        self.assertEqual(r.realise, Decimal('15'))
        self.assertEqual(r.officiel, 0)
        self.assertEqual(r.source, '')

    def test_attachement_valide_plus_rapports_posterieurs(self):
        self.attachement(1, date(2025, 2, 28), 500)
        self.rapport(date(2025, 2, 20), '40')   # déjà couvert par l'attachement
        self.rapport(date(2025, 3, 3), '30')
        self.rapport(date(2025, 3, 4), '20')

        r = self.realise(date(2025, 3, 10))

        self.assertEqual(r.officiel, Decimal('500'))
        self.assertEqual(r.rapports_apres, Decimal('50'))
        self.assertEqual(r.realise, Decimal('550'))
        self.assertEqual(r.date_base, date(2025, 2, 28))
        self.assertIn('Attachement', r.source)

    def test_attachement_non_valide_ou_periode_non_close_ignore(self):
        self.attachement(1, date(2025, 2, 28), 500, statut='SIGNE')  # signé, pas validé
        self.attachement(2, date(2025, 3, 31), 800, debut=date(2025, 3, 1))  # période close après la date
        self.rapport(date(2025, 3, 3), '30')

        r = self.realise(date(2025, 3, 10))

        self.assertEqual(r.officiel, 0)
        self.assertEqual(r.realise, Decimal('30'))

    def test_plus_grand_officiel_retenu_et_sa_date_de_base(self):
        self.attachement(1, date(2025, 1, 31), 300)
        self.ca(date(2025, 2, 1), 450, statut='BROUILLON')
        self.rapport(date(2025, 2, 15), '25')   # couvert par le CA de février
        self.rapport(date(2025, 3, 5), '12')

        r = self.realise(date(2025, 3, 10))

        self.assertEqual(r.officiel, Decimal('450'))
        self.assertEqual(r.date_base, date(2025, 2, 28))
        self.assertTrue(r.provisoire)
        self.assertEqual(r.realise, Decimal('462'))

    def test_ca_du_mois_en_cours_ignore(self):
        self.ca(date(2025, 3, 1), 900)
        self.rapport(date(2025, 3, 5), '12')

        self.assertEqual(self.realise(date(2025, 3, 10)).realise, Decimal('12'))
        # Le dernier jour du mois, le CA de ce mois est clos.
        self.assertEqual(self.realise(date(2025, 3, 31)).realise, Decimal('900'))

    def test_rapport_exclu(self):
        self.rapport(date(2025, 3, 3), '10')
        ouvert = self.rapport(date(2025, 3, 4), '5')

        r = self.realise(date(2025, 3, 10), exclure_rapport_id=ouvert.pk)

        self.assertEqual(r.realise, Decimal('10'))

    def test_nombre_de_requetes_constant(self):
        self.attachement(1, date(2025, 1, 31), 300)
        self.ca(date(2025, 1, 1), 280)
        for jour in range(1, 15):
            self.rapport(date(2025, 2, jour), '1')
        with CaptureQueriesContext(connection) as ctx:
            realise_par_ligne(self.projet, date(2025, 2, 20))
        self.assertLessEqual(len(ctx.captured_queries), 5)
