from datetime import date, timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from projets.models import CategorieCharge, Notification, RessourceAffectee
from projets.models.suivi_projet import DepenseRapportJournalier, RapportJournalier
from projets.tests.test_rapports_journaliers import RapportJournalierTestBase


class RapportJournalierDepensesTests(RapportJournalierTestBase):
    """Dépenses, référentiel et performances du rapport journalier."""

    def test_creation_avec_depenses(self):
        payload = self._payload()
        payload['depenses-TOTAL_FORMS'] = '2'
        payload.update(self._depense(0, self.personnel))
        payload.update(self._depense(1, self.transport, 'Camion', '2', '300'))

        response = self.client.post(
            reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]), payload,
        )

        self.assertEqual(response.status_code, 302)
        rapport = RapportJournalier.objects.get(projet=self.projet)
        self.assertEqual(rapport.depenses.count(), 2)
        self.assertEqual(rapport.total_depenses, Decimal('800.00'))

    def test_categorie_d_un_autre_dossier_refusee(self):
        from projets.models import Dossier
        autre = Dossier.objects.create(nom='Autre dossier', activite='TRAVAUX')
        etrangere = CategorieCharge.objects.get(dossier=autre, code='PERSONNEL')
        payload = self._payload()
        payload['depenses-TOTAL_FORMS'] = '1'
        payload.update(self._depense(0, etrangere))

        response = self.client.post(
            reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]), payload,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(RapportJournalier.objects.exists())

    def test_edition_nombre_de_requetes_independant_du_nombre_de_lignes(self):
        petit = self._rapport_avec_depenses(1)
        grand = self._rapport_avec_depenses(15, jour=date(2026, 11, 23))

        def compter(rapport):
            with CaptureQueriesContext(connection) as ctx:
                response = self.client.get(reverse(
                    'projets:modifier_rapport_journalier', args=[self.projet.pk, rapport.pk],
                ))
            self.assertEqual(response.status_code, 200)
            return len(ctx.captured_queries)

        self.assertEqual(compter(petit), compter(grand))

    def test_referentiel_couvre_transport_et_conserve_designation_retiree(self):
        RessourceAffectee.objects.create(
            projet=self.projet, categorie_charge=self.transport, objet_id=1,
            designation='Camion 8x4', unite='J', tarif=Decimal('1200'),
            date_debut=date(2026, 11, 1),
        )
        rapport = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22))
        DepenseRapportJournalier.objects.create(
            rapport=rapport, categorie=self.transport.code, categorie_charge=self.transport,
            designation='Ancien camion', quantite=Decimal('1'), prix_unitaire=Decimal('900'),
        )

        response = self.client.get(reverse(
            'projets:modifier_rapport_journalier', args=[self.projet.pk, rapport.pk],
        ))

        self.assertContains(response, 'id="referentiel-data-TRANSPORT"')
        self.assertContains(response, 'Camion 8x4')
        # La valeur enregistrée reste sélectionnée même hors référentiel.
        self.assertContains(response, '<option value="Ancien camion" selected>')

    def test_liste_paginee(self):
        debut = date(2026, 1, 1)
        RapportJournalier.objects.bulk_create([
            RapportJournalier(projet=self.projet, date=debut + timedelta(days=i))
            for i in range(35)
        ])
        url = reverse('projets:rapports_journaliers', args=[self.projet.pk])

        page1 = self.client.get(url)
        page2 = self.client.get(url, {'page': 2})

        self.assertEqual(len(page1.context['rapports']), 30)
        self.assertEqual(len(page2.context['rapports']), 5)
        self.assertContains(page1, '35 rapports')

    def test_enregistrement_notifie_les_utilisateurs(self):
        rapport = RapportJournalier.objects.create(projet=self.projet, date=date(2026, 11, 22))
        self.assertTrue(Notification.objects.filter(
            objet_type='rapport_journalier', objet_id=rapport.pk,
            utilisateur=self.user, type_notification='NOUVEAU_RAPPORT_JOURNALIER',
        ).exists())

    def test_apercu_impression(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from projets.models.suivi_projet import DocumentRapportJournalier, LigneTravailRapportJournalier
        self._rapport_avec_depenses(0, jour=date(2026, 11, 20))
        rapport = self._rapport_avec_depenses(2, jour=date(2026, 11, 22))
        rapport.evenements = 'Visite du maître d\'ouvrage'
        rapport.save()
        LigneTravailRapportJournalier.objects.create(
            rapport=rapport, designation='Pose de bordure', quantite=Decimal('1250.5'), unite='ML',
        )
        DocumentRapportJournalier.objects.create(
            rapport=rapport, fichier=SimpleUploadedFile('chantier.jpg', b'\xff\xd8\xff'),
            original_filename='chantier.jpg',
        )
        DocumentRapportJournalier.objects.create(
            rapport=rapport, fichier=SimpleUploadedFile('pv.pdf', b'%PDF'), original_filename='pv.pdf',
        )

        response = self.client.get(reverse(
            'projets:apercu_rapport_journalier', args=[self.projet.pk, rapport.pk],
        ))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['numero'], 2)
        self.assertIsNotNone(response.context['precedent'])
        self.assertIsNone(response.context['suivant'])
        self.assertEqual([d.nom for d in response.context['photos']], ['chantier.jpg'])
        self.assertEqual([d.nom for d in response.context['autres_documents']], ['pv.pdf'])
        self.assertEqual(response.context['total_depenses'], Decimal('20.00'))
        self.assertContains(response, 'Rapport n°<strong>002</strong>')
        self.assertContains(response, 'Pose de bordure')
        self.assertContains(response, 'Néant.')  # stocks et observations vides
        self.assertContains(response, "Visa du maître d")

    def test_taille_document_memorisee(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        payload = self._payload()
        payload['documents'] = [SimpleUploadedFile('plan.pdf', b'%PDF-1.4 abc')]

        self.client.post(
            reverse('projets:ajouter_rapport_journalier', args=[self.projet.pk]), payload,
        )

        document = RapportJournalier.objects.get(projet=self.projet).documents_joints.get()
        self.assertEqual(document.taille, len(b'%PDF-1.4 abc'))
