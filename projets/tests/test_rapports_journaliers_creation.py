from datetime import date
from decimal import Decimal

from django.urls import reverse

from projets.models.suivi_projet import (
    DepenseRapportJournalier, RapportJournalier, StockRapportJournalier,
)
from projets.tests.test_rapports_journaliers import RapportJournalierTestBase
from projets.views.reporting_views.views import _date_rapport_par_defaut


class DateParDefautTests(RapportJournalierTestBase):
    AUJOURDHUI = date(2026, 11, 27)

    def test_aucun_rapport_aujourd_hui(self):
        self.assertEqual(_date_rapport_par_defaut(self.projet, self.AUJOURDHUI), self.AUJOURDHUI)

    def test_dernier_rapport_du_mois_lendemain(self):
        RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 12))
        RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 20))
        self.assertEqual(
            _date_rapport_par_defaut(self.projet, self.AUJOURDHUI), date(2026, 11, 21),
        )

    def test_dernier_rapport_d_un_autre_mois_aujourd_hui(self):
        RapportJournalier.objects.create(projet=self.projet, date=date(2026, 10, 31))
        self.assertEqual(_date_rapport_par_defaut(self.projet, self.AUJOURDHUI), self.AUJOURDHUI)

    def test_meme_mois_d_une_autre_annee_aujourd_hui(self):
        RapportJournalier.objects.create(projet=self.projet, date=date(2025, 11, 20))
        self.assertEqual(_date_rapport_par_defaut(self.projet, self.AUJOURDHUI), self.AUJOURDHUI)


class DoublonEtReproductionTests(RapportJournalierTestBase):
    def _url_ajout(self):
        return reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk])

    def test_meme_date_demande_confirmation(self):
        RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22), activite='Voirie')
        payload = self._payload()
        payload['activite'] = 'Assainissement'

        response = self.client.post(self._url_ajout(), payload)

        self.assertEqual(response.status_code, 400)
        self.assertEqual(RapportJournalier.objects.count(), 1)
        self.assertContains(response, 'name="confirmer_doublon"', status_code=400)
        self.assertContains(response, 'Voirie', status_code=400)

    def test_meme_date_creee_apres_confirmation(self):
        RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22), activite='Voirie')
        payload = self._payload()
        payload.update({'activite': 'Assainissement', 'confirmer_doublon': '1'})

        response = self.client.post(self._url_ajout(), payload)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            set(RapportJournalier.objects.filter(date=date(2026, 11, 22))
                .values_list('activite', flat=True)),
            {'Voirie', 'Assainissement'},
        )

    def test_modification_vers_une_date_prise_demande_confirmation(self):
        RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22))
        autre = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 23))

        response = self.client.post(
            reverse('projets:modifier_rapport_journalier', args=[self.projet.pk, autre.pk]),
            self._payload(),
        )

        self.assertEqual(response.status_code, 400)
        autre.refresh_from_db()
        self.assertEqual(autre.date, date(2026, 11, 23))

    def test_reproduction_dupplique_depenses_et_stocks_seulement(self):
        source = RapportJournalier.objects.create(
            projet=self.projet, date=date(2026, 11, 22), activite='Voirie',
            meteo='Pluie', observations='Ne pas recopier',
        )
        DepenseRapportJournalier.objects.create(
            rapport=source, categorie=self.transport.code, categorie_charge=self.transport,
            designation='Camion 8x4', quantite=Decimal('2'), unite='J', prix_unitaire=Decimal('1200'),
        )
        StockRapportJournalier.objects.create(
            rapport=source, designation='Ciment', unite='T', quantite_entree=Decimal('10'),
            quantite_sortie=Decimal('4'), stock_restant=Decimal('22.5'),
        )

        response = self.client.get(self._url_ajout(), {'depuis': source.pk})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['source'], source)
        form = response.context['form']
        self.assertEqual(form.initial['activite'], 'Voirie')
        self.assertNotIn('meteo', form.initial)
        # Dépense rangée dans sa catégorie, avec son total.
        groupes = {code: (forms, total) for code, _, forms, total, _, _ in response.context['depenses_groupees']}
        self.assertEqual(len(groupes['TRANSPORT'][0]), 1)
        self.assertEqual(groupes['TRANSPORT'][1], Decimal('2400'))
        self.assertContains(response, 'value="Camion 8x4"')
        # Stock : le restant devient le point de départ.
        stock_initial = response.context['stocks'].forms[0].initial
        self.assertEqual(stock_initial['stock_restant'], Decimal('22.5'))
        self.assertEqual(stock_initial['quantite_entree'], Decimal('0'))
        self.assertEqual(response.context['travaux'].total_form_count(), 0)

    def test_reproduction_d_un_rapport_d_un_autre_projet_refusee(self):
        from projets.models import Projet
        autre_projet = Projet.objects.create(
            dossier=self.dossier, nom='Autre', objet='x', numero='AUTRE-1',
            maitre_ouvrage='MO', localisation='Site',
        )
        etranger = RapportJournalier.objects.create(projet=autre_projet, date=date(2026, 11, 22))

        response = self.client.get(self._url_ajout(), {'depuis': etranger.pk})

        self.assertEqual(response.status_code, 404)

    def test_apercu_numerote_les_rapports_d_une_meme_date(self):
        premier = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22))
        second = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22))

        response = self.client.get(reverse(
            'projets:apercu_rapport_journalier', args=[self.projet.pk, second.pk],
        ))

        self.assertEqual(response.context['numero'], 2)
        self.assertEqual(response.context['precedent'].pk, premier.pk)
        self.assertIsNone(response.context['suivant'])


class MeteoTests(RapportJournalierTestBase):
    def test_code_meteo_enregistre_et_affiche_en_clair(self):
        payload = self._payload()
        payload['meteo'] = 'SANDSTORM'

        self.client.post(reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]), payload)

        rapport = RapportJournalier.objects.get(projet=self.projet)
        self.assertEqual(rapport.meteo, 'SANDSTORM')
        self.assertEqual(rapport.meteo_libelle, 'Tempête de sable')
        detail = self.client.get(reverse('projets:detail_rapport_journalier', args=[self.projet.pk, rapport.pk]))
        self.assertContains(detail, 'Tempête de sable')
        self.assertContains(detail, 'fa-wind')

    def test_texte_libre_refuse_a_la_creation(self):
        payload = self._payload()
        payload['meteo'] = 'Il fait beau'

        response = self.client.post(reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]), payload)

        self.assertEqual(response.status_code, 400)
        self.assertFalse(RapportJournalier.objects.exists())

    def test_ancienne_saisie_libre_conservee_a_la_modification(self):
        rapport = RapportJournalier.objects.create(
            projet=self.projet, date=date(2026, 11, 22), meteo='Ensoleillé le matin',
        )
        url = reverse('projets:modifier_rapport_journalier', args=[self.projet.pk, rapport.pk])

        page = self.client.get(url)
        self.assertContains(page, '<option value="Ensoleillé le matin" selected>')

        payload = self._payload()
        payload['meteo'] = 'Ensoleillé le matin'
        response = self.client.post(url, payload)

        self.assertEqual(response.status_code, 302)
        rapport.refresh_from_db()
        self.assertEqual(rapport.meteo_libelle, 'Ensoleillé le matin')

    def test_liste_groupee_et_choix_rapides(self):
        page = self.client.get(reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]))
        self.assertContains(page, '<optgroup label="⛈️ Orages">')
        self.assertContains(page, 'data-meteo="CLEAR"')
        self.assertContains(page, 'id="meteo-icones"')
