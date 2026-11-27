from datetime import date
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from projets.models import LigneBordereau, LotProjet, Projet
from projets.models.suivi_projet import LigneTravailRapportJournalier, RapportJournalier
from projets.tests.test_rapports_journaliers import RapportJournalierTestBase


class LignesBpuTests(RapportJournalierTestBase):
    def setUp(self):
        super().setUp()
        self.lot = LotProjet.objects.create(projet=self.projet, nom='Lot 1 Voirie')
        self.titre = self._ligne('1', 'TERRASSEMENTS', Decimal('0'), est_titre=True)
        self.deblai = self._ligne('1.1', 'Déblai en terrain meuble', Decimal('35'), unite='M3', quantite=Decimal('1000'))
        self.bordure = self._ligne('2.1', 'Bordure T3', Decimal('120'), unite='ML', quantite=Decimal('500'))
        self.pour_memoire = self._ligne('2.2', 'Prix pour mémoire', Decimal('0'), unite='U')

    def _ligne(self, numero, designation, prix, unite='', quantite=Decimal('1'), est_titre=False, lot=None):
        return LigneBordereau.objects.create(
            lot=lot or self.lot, numero=numero, designation=designation, unite=unite,
            quantite=quantite, prix_unitaire=prix, est_titre=est_titre,
        )

    def _payload_avec_bpu(self, ligne_id, designation='Déblai en terrain meuble', quantite='120'):
        payload = self._payload()
        payload['lignes_travaux-TOTAL_FORMS'] = '1'
        for cle in [k for k in payload if k.startswith('lignes_travaux-1-')]:
            del payload[cle]
        payload.update({
            'lignes_travaux-0-ligne_bordereau': str(ligne_id),
            'lignes_travaux-0-designation': designation,
            'lignes_travaux-0-quantite': quantite,
            'lignes_travaux-0-unite': 'M3',
            'lignes_travaux-0-observations': '',
            'lignes_travaux-0-ordre': '0',
        })
        return payload

    def test_creation_avec_ligne_liee_au_bordereau(self):
        response = self.client.post(
            reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]),
            self._payload_avec_bpu(self.deblai.pk),
        )

        self.assertEqual(response.status_code, 302)
        ligne = LigneTravailRapportJournalier.objects.get()
        self.assertEqual(ligne.ligne_bordereau, self.deblai)
        self.assertEqual(ligne.designation, 'Déblai en terrain meuble')
        self.assertEqual(ligne.quantite, Decimal('120'))

    def test_prix_d_un_autre_projet_refuse(self):
        autre = Projet.objects.create(
            dossier=self.dossier, nom='Autre', objet='x', numero='AUTRE-BPU',
            maitre_ouvrage='MO', localisation='Site',
        )
        etrangere = self._ligne('9.9', 'Prix étranger', Decimal('10'),
                                lot=LotProjet.objects.create(projet=autre, nom='Lot X'))

        response = self.client.post(
            reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]),
            self._payload_avec_bpu(etrangere.pk),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(RapportJournalier.objects.exists())

    def test_lignes_proposees_et_realise_cumule(self):
        rapports = {}
        for jour, quantite in ((20, '100'), (21, '50.5'), (25, '7')):
            rapport = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, jour))
            LigneTravailRapportJournalier.objects.create(
                rapport=rapport, ligne_bordereau=self.deblai, designation='Déblai', quantite=Decimal(quantite),
            )
            rapports[jour] = rapport

        page = self.client.get(reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]))
        self.assertContains(page, 'ouvrirModalBPU()')
        self.assertContains(page, 'data-url="%s"' % reverse('projets:api_lignes_bpu_rapport', args=[self.projet.pk]))

        # Réalisé au 22/11, en excluant le rapport du 21 (rapport « ouvert ») : 100 seulement.
        reponse = self.client.get(
            reverse('projets:api_lignes_bpu_rapport', args=[self.projet.pk]),
            {'date': '2026-11-22', 'rapport': rapports[21].pk},
        ).json()

        lignes = {l['numero']: l for l in reponse['lignes']}
        # Titres et prix nuls exclus.
        self.assertEqual(set(lignes), {'1.1', '2.1'})
        self.assertEqual(Decimal(lignes['1.1']['realise']), Decimal('100'))
        self.assertEqual(Decimal(lignes['1.1']['quantite_marche']), Decimal('1000'))
        self.assertEqual(lignes['1.1']['source'], '')
        self.assertEqual(Decimal(lignes['2.1']['realise']), Decimal('0'))
        self.assertEqual(lignes['2.1']['lot'], 'Lot 1 Voirie')

    def test_api_lignes_bpu_date_invalide(self):
        reponse = self.client.get(
            reverse('projets:api_lignes_bpu_rapport', args=[self.projet.pk]), {'date': 'hier'},
        )
        self.assertEqual(reponse.status_code, 400)

    def test_sans_ligne_a_prix_pas_de_bouton(self):
        LigneBordereau.objects.filter(prix_unitaire__gt=0).update(prix_unitaire=0)
        response = self.client.get(reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]))
        self.assertNotContains(response, 'ouvrirModalBPU()')
        self.assertNotContains(response, 'id="modalBPU"')

    def test_lien_conserve_si_le_prix_passe_a_zero(self):
        rapport = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22))
        LigneTravailRapportJournalier.objects.create(
            rapport=rapport, ligne_bordereau=self.bordure, designation='Bordure', quantite=Decimal('10'),
        )
        self.bordure.prix_unitaire = Decimal('0')
        self.bordure.save()
        payload = self._payload_avec_bpu(self.bordure.pk, designation='Bordure', quantite='12')
        payload.update({'lignes_travaux-INITIAL_FORMS': '1',
                        'lignes_travaux-0-id': str(rapport.lignes_travaux.get().pk)})

        response = self.client.post(
            reverse('projets:modifier_rapport_journalier', args=[self.projet.pk, rapport.pk]), payload,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(rapport.lignes_travaux.get().ligne_bordereau, self.bordure)

    def test_edition_requetes_constantes_avec_lignes_liees(self):
        def rapport_avec(nb, jour):
            rapport = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, jour))
            for i in range(nb):
                LigneTravailRapportJournalier.objects.create(
                    rapport=rapport, ligne_bordereau=self.deblai, designation=f'L{i}', quantite=Decimal('1'),
                )
            return rapport

        def compter(rapport):
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(reverse('projets:modifier_rapport_journalier', args=[self.projet.pk, rapport.pk]))
            return len(ctx.captured_queries)

        self.assertEqual(compter(rapport_avec(1, 10)), compter(rapport_avec(12, 11)))

    def test_detail_et_apercu_affichent_le_prix(self):
        rapport = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22))
        LigneTravailRapportJournalier.objects.create(
            rapport=rapport, ligne_bordereau=self.bordure, designation='Bordure T3 côté Nord', quantite=Decimal('10'),
        )
        for nom in ('detail_rapport_journalier', 'apercu_rapport_journalier'):
            response = self.client.get(reverse(f'projets:{nom}', args=[self.projet.pk, rapport.pk]))
            self.assertContains(response, '2.1')
            self.assertContains(response, 'Bordure T3 côté Nord')
