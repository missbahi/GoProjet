from datetime import date
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from projets.models import CategorieCharge, Dossier, Projet
from projets.models.suivi_projet import (
    DepenseRapportJournalier,
    DocumentRapportJournalier,
    LigneTravailRapportJournalier,
    RapportJournalier,
)


@override_settings(
    DEFAULT_FILE_STORAGE='django.core.files.storage.InMemoryStorage',
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    },
)
class RapportJournalierTestBase(TestCase):
    """Données et helpers communs, sans test (hérité par les classes de tests)."""

    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin-rapport",
            email="rapport@example.com",
            password="secret",
        )
        self.dossier = Dossier.objects.create(
            nom="Dossier rapports",
            activite="TRAVAUX",
            gerant=self.user,
        )
        self.projet = Projet.objects.create(
            dossier=self.dossier,
            nom="Projet rapports",
            objet="Travaux",
            numero="RAPPORT-001",
            maitre_ouvrage="Maître d'ouvrage",
            localisation="Site",
        )
        self.client.force_login(self.user)
        self.personnel = CategorieCharge.objects.get(dossier=self.dossier, code='PERSONNEL')
        self.transport = CategorieCharge.objects.get(dossier=self.dossier, code='TRANSPORT')

    def _payload(self):
        return {
            "date": "2026-11-22",
            "meteo": "CLEAR",
            "temperature": "22",
            "evenements": "",
            "observations": "RAS",
            "redacteur": "Admin",
            "depenses-TOTAL_FORMS": "0",
            "depenses-INITIAL_FORMS": "0",
            "depenses-MIN_NUM_FORMS": "0",
            "depenses-MAX_NUM_FORMS": "1000",
            "stocks-TOTAL_FORMS": "0",
            "stocks-INITIAL_FORMS": "0",
            "stocks-MIN_NUM_FORMS": "0",
            "stocks-MAX_NUM_FORMS": "1000",
            "lignes_travaux-TOTAL_FORMS": "2",
            "lignes_travaux-INITIAL_FORMS": "0",
            "lignes_travaux-MIN_NUM_FORMS": "0",
            "lignes_travaux-MAX_NUM_FORMS": "1000",
            "lignes_travaux-0-designation": "Pose de bordure",
            "lignes_travaux-0-quantite": "150.000",
            "lignes_travaux-0-unite": "ML",
            "lignes_travaux-0-observations": "Section 1",
            "lignes_travaux-0-ordre": "0",
            "lignes_travaux-1-designation": "Giratoire",
            "lignes_travaux-1-quantite": "1.000",
            "lignes_travaux-1-unite": "U",
            "lignes_travaux-1-observations": "Giratoire 3",
            "lignes_travaux-1-ordre": "1",
        }

    def _depense(self, index, categorie, designation='Manœuvre', quantite='8', prix='25'):
        return {
            f'depenses-{index}-categorie': categorie.code,
            f'depenses-{index}-categorie_charge': str(categorie.pk),
            f'depenses-{index}-designation': designation,
            f'depenses-{index}-quantite': quantite,
            f'depenses-{index}-unite': 'H',
            f'depenses-{index}-prix_unitaire': prix,
            f'depenses-{index}-observations': '',
        }

    def _rapport_avec_depenses(self, nombre, jour=date(2026, 11, 22)):
        rapport = RapportJournalier.objects.create(projet=self.projet, date=jour)
        for index in range(nombre):
            DepenseRapportJournalier.objects.create(
                rapport=rapport, categorie=self.personnel.code,
                categorie_charge=self.personnel, designation=f'Ouvrier {index}',
                quantite=Decimal('1'), prix_unitaire=Decimal('10'),
            )
        return rapport


class RapportJournalierTravauxDocumentsTests(RapportJournalierTestBase):
    def test_creation_supporte_lignes_travaux_et_documents_multiples(self):
        payload = self._payload()
        payload["documents"] = [
            SimpleUploadedFile("plan.pdf", b"%PDF-1.4", content_type="application/pdf"),
            SimpleUploadedFile("photo.jpg", b"\xff\xd8\xff", content_type="image/jpeg"),
        ]

        response = self.client.post(
            reverse(
                "projets:ajouter_rapport_journalier",
                args=[self.projet.pk],
            ),
            payload,
        )

        self.assertEqual(response.status_code, 302)
        rapport = RapportJournalier.objects.get(projet=self.projet)
        self.assertEqual(rapport.lignes_travaux.count(), 2)
        premiere = rapport.lignes_travaux.first()
        self.assertEqual(premiere.designation, "Pose de bordure")
        self.assertEqual(premiere.quantite, Decimal("150.000"))
        self.assertEqual(rapport.documents_joints.count(), 2)
        self.assertSetEqual(
            set(rapport.documents_joints.values_list("original_filename", flat=True)),
            {"plan.pdf", "photo.jpg"},
        )

        detail = self.client.get(
            reverse(
                "projets:detail_rapport_journalier",
                args=[self.projet.pk, rapport.pk],
            ),
        )
        self.assertContains(detail, "Pose de bordure")
        self.assertContains(detail, "plan.pdf")
        self.assertContains(detail, "photo.jpg")

    def test_photo_camera_cree_un_document_joint(self):
        payload = self._payload()
        payload["document_camera"] = SimpleUploadedFile(
            "camera.jpg",
            b"\xff\xd8\xff",
            content_type="image/jpeg",
        )

        response = self.client.post(
            reverse(
                "projets:ajouter_rapport_journalier",
                args=[self.projet.pk],
            ),
            payload,
        )

        self.assertEqual(response.status_code, 302)
        rapport = RapportJournalier.objects.get(projet=self.projet)
        document = rapport.documents_joints.get()
        self.assertEqual(document.original_filename, "camera.jpg")

    def test_suppression_document_conserve_le_rapport(self):
        rapport = RapportJournalier.objects.create(
            projet=self.projet,
            date=date(2026, 11, 22),
            redacteur="Admin",
        )
        document = DocumentRapportJournalier.objects.create(
            rapport=rapport,
            fichier=SimpleUploadedFile("preuve.pdf", b"%PDF"),
            original_filename="preuve.pdf",
        )

        payload = self._payload()
        payload["supprimer_document"] = [str(document.pk)]

        response = self.client.post(
            reverse(
                "projets:modifier_rapport_journalier",
                args=[self.projet.pk, rapport.pk],
            ),
            payload,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(RapportJournalier.objects.filter(pk=rapport.pk).exists())
        self.assertFalse(
            DocumentRapportJournalier.objects.filter(pk=document.pk).exists()
        )

    def test_fichier_hors_champs_prevus_est_ignore(self):
        """Un fichier envoyé sous un autre nom de champ ne contourne pas la validation."""
        payload = self._payload()
        payload["document"] = SimpleUploadedFile(
            "piege.html", b"<script>alert(1)</script>", content_type="text/html",
        )

        response = self.client.post(
            reverse("projets:ajouter_rapport_journalier", args=[self.projet.pk]),
            payload,
        )

        self.assertEqual(response.status_code, 302)
        rapport = RapportJournalier.objects.get(projet=self.projet)
        self.assertFalse(rapport.documents_joints.exists())

    def test_extension_non_autorisee_est_refusee(self):
        payload = self._payload()
        payload["documents"] = [
            SimpleUploadedFile("piege.html", b"<p>x</p>", content_type="text/html"),
        ]

        response = self.client.post(
            reverse("projets:ajouter_rapport_journalier", args=[self.projet.pk]),
            payload,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(RapportJournalier.objects.filter(projet=self.projet).exists())

    def test_pages_completes_liste_et_detail(self):
        rapport = RapportJournalier.objects.create(
            projet=self.projet, date=date(2026, 11, 22), redacteur="Admin",
        )
        liste = self.client.get(
            reverse("projets:rapports_journaliers", args=[self.projet.pk]),
        )
        detail = self.client.get(
            reverse("projets:detail_rapport_journalier", args=[self.projet.pk, rapport.pk]),
        )
        self.assertEqual(liste.status_code, 200)
        self.assertEqual(detail.status_code, 200)
        self.assertNotContains(detail, "projets/js/rapports.js")
