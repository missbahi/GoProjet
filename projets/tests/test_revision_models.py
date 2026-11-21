from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.conf import settings
from django.urls import reverse

from projets.models import (
    Attachement,
    Decompte,
    FormuleRevision,
    IndexReference,
    IndexRevisionProjet,
    IndexValeur,
    LigneAttachement,
    LigneBordereau,
    LotProjet,
    OrdreService,
    Projet,
    TermeFormule,
    TypeOrdreService,
)
from projets.models.revision import StatutIndex, TypeTerme
from projets.services.revision_readiness import indicateur_revision_tableau_bord
from projets.services.revision_presets import FORMULES_REVISION_PREDEFINIES
from projets.services.revision_readiness import (
    controle_indexes_revision,
    index_ids_tableur,
)


@override_settings(STORAGES={
    **settings.STORAGES,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
})
class RevisionModelsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.projet = Projet.objects.create(
            nom="Projet de révision",
            objet="Marché de travaux",
            numero="REV-001",
            maitre_ouvrage="Maître d'ouvrage",
            localisation="Site",
            revisable=True,
            montant=Decimal("2500000.00"),
            montant_soumission=Decimal("2500000.00"),
            epoque_base=date(2026, 1, 1),
        )
        type_osc, _ = TypeOrdreService.objects.get_or_create(
            code="OSC",
            defaults={
                "nom": "OS de commencement",
                "description": "Commencement des travaux",
                "ordre_min": 1,
                "ordre_max": 1,
                "unique_dans_projet": True,
            },
        )
        cls.osc = OrdreService.objects.create(
            projet=cls.projet,
            type_os=type_osc,
            reference="OSC-001",
            titre="Commencement",
            description="Commencement",
            date_publication=date(2026, 6, 1),
            date_effet=date(2026, 6, 1),
            statut="NOTIFIE",
            ordre_sequence=1,
        )
        cls.index, _ = IndexReference.objects.get_or_create(
            symbole="BAT6",
            defaults={
                "libelle": "Bâtiment tous corps d'état",
                "famille": "Bâtiment",
            },
        )

    def _formule_avec_terme(self):
        formule = FormuleRevision.objects.create(
            projet=self.projet,
            code="F-BAT6",
            k=Decimal("0.1500"),
        )
        TermeFormule.objects.create(
            formule=formule,
            type_terme=TypeTerme.SIMPLE,
            coefficient=Decimal("0.8500"),
            index_simple=self.index,
        )
        return formule

    def test_publication_normalise_le_mois_et_garde_le_definitif(self):
        provisoire, _ = IndexValeur.publier(
            self.index, date(2026, 2, 18), Decimal("100.1000")
        )
        self.assertEqual(provisoire.mois, date(2026, 2, 1))

        IndexValeur.publier(
            self.index,
            date(2026, 2, 28),
            Decimal("100.2000"),
            StatutIndex.IND_DEF,
        )
        IndexValeur.publier(
            self.index,
            date(2026, 2, 1),
            Decimal("99.9999"),
            StatutIndex.IND_PRO,
        )

        valeur = IndexValeur.objects.get(index=self.index, mois=date(2026, 2, 1))
        self.assertEqual(valeur.valeur, Decimal("99.9999"))
        self.assertEqual(valeur.statut, StatutIndex.IND_PRO)

    def test_formule_reprend_les_regles_du_moteur(self):
        formule = self._formule_avec_terme()
        self.assertEqual(formule.mois_base, date(2026, 1, 1))
        self.assertIn(r"\frac{\mathrm{BAT6}}{\mathrm{BAT6}_0}", formule.formule_latex)
        self.assertEqual(formule.valider(), [])

        formule.k = Decimal("0.10")
        with self.assertRaises(ValidationError):
            formule.valider()

    def test_formule_globale_exige_un_seul_terme_simple(self):
        formule = self._formule_avec_terme()
        formule.est_index_global = True
        formule.valider()

        autre_index, _ = IndexReference.objects.get_or_create(symbole="ING")
        TermeFormule.objects.create(
            formule=formule,
            coefficient=Decimal("0.0001"),
            index_simple=autre_index,
        )
        with self.assertRaises(ValidationError):
            formule.valider()

    def test_ligne_refuse_une_formule_d_un_autre_projet(self):
        autre_projet = Projet.objects.create(
            nom="Autre projet",
            objet="Autre marché",
            numero="REV-002",
            maitre_ouvrage="Maître d'ouvrage",
            localisation="Site",
            revisable=True,
        )
        lot = LotProjet.objects.create(projet=autre_projet, nom="Lot unique")
        formule = self._formule_avec_terme()
        ligne = LigneBordereau(
            lot=lot,
            designation="Poste",
            quantite=Decimal("1"),
            prix_unitaire=Decimal("100"),
            formule_revision=formule,
        )

        with self.assertRaises(ValidationError):
            ligne.full_clean()

    def test_indicateur_est_cree_une_seule_fois_puis_mis_en_cache(self):
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        racine = LigneBordereau.objects.create(
            lot=lot,
            designation="Section technique",
            quantite=Decimal("0"),
            prix_unitaire=Decimal("0"),
            est_titre=True,
        )
        principale_a = LigneBordereau.objects.create(
            lot=lot,
            parent=racine,
            designation="Terrassements",
            quantite=Decimal("1"),
            prix_unitaire=Decimal("100"),
            montant_calcule=Decimal("100"),
        )
        principale_b = LigneBordereau.objects.create(
            lot=lot,
            parent=racine,
            designation="Voirie",
            quantite=Decimal("1"),
            prix_unitaire=Decimal("200"),
            montant_calcule=Decimal("200"),
        )

        indicateur = indicateur_revision_tableau_bord(self.projet)
        self.assertEqual(indicateur.statut, "INCOMPLET")
        self.assertEqual(indicateur.details["nombre_lignes_non_couvertes"], 2)

        formule = self._formule_avec_terme()
        principale_a.formule_revision = formule
        principale_a.save()
        principale_b.formule_revision = formule
        principale_b.save()
        self.projet.refresh_from_db()
        indicateur.refresh_from_db()
        self.assertEqual(indicateur.statut, "A_CONTROLER")

        indicateur = indicateur_revision_tableau_bord(self.projet)
        self.assertEqual(indicateur.statut, "PRET")
        self.assertEqual(indicateur.details["nombre_lignes_non_couvertes"], 0)
        dernier_controle = indicateur.dernier_controle
        indicateur = indicateur_revision_tableau_bord(self.projet)
        self.assertEqual(indicateur.dernier_controle, dernier_controle)

    def test_projet_non_revisable_ne_cree_pas_d_indicateur(self):
        self.projet.revisable = False
        self.projet.save()
        self.assertIsNone(indicateur_revision_tableau_bord(self.projet))
        self.assertFalse(hasattr(self.projet, "indicateur_revision"))

    def test_page_cree_une_formule_et_affecte_les_lignes_principales(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-revision",
            email="revision@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        parent = LigneBordereau.objects.create(
            lot=lot,
            designation="Travaux",
            quantite=Decimal("0"),
            prix_unitaire=Decimal("0"),
        )
        principale = LigneBordereau.objects.create(
            lot=lot,
            parent=parent,
            designation="Gros oeuvre",
            quantite=Decimal("1"),
            prix_unitaire=Decimal("100"),
            montant_calcule=Decimal("100"),
        )

        creation = self.client.post(
            reverse("projets:creer_formule_revision", args=[self.projet.pk]),
            {
                "code": "F-BAT6-UI",
                "libelle": "Bâtiment",
                "k": "0.1500",
                "est_index_global": "on",
                "termes-TOTAL_FORMS": "1",
                "termes-INITIAL_FORMS": "0",
                "termes-MIN_NUM_FORMS": "0",
                "termes-MAX_NUM_FORMS": "1000",
                "termes-0-type_terme": "SIMPLE",
                "termes-0-coefficient": "0.8500",
                "termes-0-index_simple": str(self.index.pk),
            },
        )
        self.assertRedirects(
            creation,
            reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        formule = FormuleRevision.objects.get(projet=self.projet, code="F-BAT6-UI")
        self.assertEqual(formule.mois_base, date(2026, 1, 1))
        terme = formule.termes.get()
        modification = self.client.post(
            reverse(
                "projets:modifier_formule_revision",
                args=[self.projet.pk, formule.pk],
            ),
            {
                "code": formule.code,
                "libelle": "Bâtiment personnalisée",
                "k": "0.1500",
                "est_index_global": "on",
                "termes-TOTAL_FORMS": "1",
                "termes-INITIAL_FORMS": "1",
                "termes-MIN_NUM_FORMS": "0",
                "termes-MAX_NUM_FORMS": "1000",
                "termes-0-id": str(terme.pk),
                "termes-0-formule": str(formule.pk),
                "termes-0-type_terme": "SIMPLE",
                "termes-0-coefficient": "0.8500",
                "termes-0-index_simple": str(self.index.pk),
            },
        )
        self.assertRedirects(
            modification,
            reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        formule.refresh_from_db()
        self.assertEqual(formule.libelle, "Bâtiment personnalisée")
        self.assertEqual(formule.mois_base, date(2026, 1, 1))

        storages = {
            **settings.STORAGES,
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
        with self.settings(STORAGES=storages):
            response = self.client.get(
                reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            )
            self.assertContains(response, "Gros oeuvre")
            self.assertNotContains(response, f'name="formule_ligne_{parent.pk}"')

        affectation = self.client.post(
            reverse("projets:affecter_formules_revision", args=[self.projet.pk]),
            {f"formule_ligne_{principale.pk}": str(formule.pk)},
        )
        self.assertRedirects(
            affectation,
            reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        principale.refresh_from_db()
        self.assertEqual(principale.formule_revision, formule)

    def test_formules_predefinies_sont_equilibrees_et_pre_remplies(self):
        self.assertEqual(len(FORMULES_REVISION_PREDEFINIES), 8)
        for predefinie in FORMULES_REVISION_PREDEFINIES:
            total = predefinie["k"] + sum(
                terme[1] for terme in predefinie["termes"]
            )
            self.assertEqual(total, Decimal("1.00"))

        admin = get_user_model().objects.create_superuser(
            username="admin-presets",
            email="presets@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        storages = {
            **settings.STORAGES,
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }
        with self.settings(STORAGES=storages):
            response = self.client.get(
                reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
                {"preset": "ALIMENTATION_EAU_POTABLE"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["formule_form"]["code"].value(),
                         "ALIMENTATION_EAU_POTABLE")
        self.assertEqual(response.context["termes_formset"].total_form_count(), 5)
        self.assertIn("P = P_0", response.context["formules_predefinies"][3]["latex"])
        self.assertIn("katex", response.content.decode())
        self.assertIn("formule-revision-texte", response.content.decode())
        self.assertIn("formules-predefinies-toggle", response.content.decode())

    def test_mois_base_unique_est_controle_et_confirme(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-mois-base",
            email="mois-base@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        url = reverse(
            "projets:enregistrer_mois_base_revision",
            args=[self.projet.pk],
        )

        trop_tard = self.client.post(
            url, {"epoque_base": "2026-06"},
        )
        self.assertEqual(trop_tard.status_code, 400)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.mois_base_revision, date(2026, 1, 1))

        sans_confirmation = self.client.post(
            url, {"epoque_base": "2026-05"},
        )
        self.assertEqual(sans_confirmation.status_code, 400)
        self.assertContains(
            sans_confirmation,
            "remplacera le mois de base unique",
            status_code=400,
        )

        modifie = self.client.post(
            url,
            {
                "epoque_base": "2026-05",
                "confirmer_modification": "on",
            },
        )
        self.assertRedirects(
            modifie,
            reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.mois_base_revision, date(2026, 5, 1))

    def test_mois_base_depasse_six_mois_exige_confirmation(self):
        self.projet.epoque_base = None
        self.projet.save()
        admin = get_user_model().objects.create_superuser(
            username="admin-mois-ancien",
            email="mois-ancien@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        url = reverse(
            "projets:enregistrer_mois_base_revision",
            args=[self.projet.pk],
        )
        response = self.client.post(
            url, {"epoque_base": "2025-10"},
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response,
            "plus de six mois",
            status_code=400,
        )

        response = self.client.post(
            url,
            {
                "epoque_base": "2025-10",
                "confirmer_modification": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.mois_base_revision, date(2025, 10, 1))

    def test_revision_inaccessible_sans_os_commencement(self):
        self.osc.delete()
        admin = get_user_model().objects.create_superuser(
            username="admin-sans-osc",
            email="sans-osc@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        self.assertIsNone(indicateur_revision_tableau_bord(self.projet))
        response = self.client.get(
            reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
        )
        self.assertRedirects(
            response,
            reverse("projets:dashboard", args=[self.projet.pk]),
            fetch_redirect_response=False,
        )

    def test_suppression_formule_avec_affectation_exige_confirmation(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-suppression-formule",
            email="suppression-formule@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        formule = self._formule_avec_terme()
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        ligne = LigneBordereau.objects.create(
            lot=lot,
            designation="Travaux",
            quantite=Decimal("0"),
            prix_unitaire=Decimal("0"),
            formule_revision=formule,
        )
        enfant_a = LigneBordereau.objects.create(
            lot=lot,
            parent=ligne,
            designation="Terrassements",
            quantite=Decimal("1"),
            prix_unitaire=Decimal("100"),
            montant_calcule=Decimal("100"),
        )
        enfant_b = LigneBordereau.objects.create(
            lot=lot,
            parent=ligne,
            designation="Voirie",
            quantite=Decimal("1"),
            prix_unitaire=Decimal("200"),
            montant_calcule=Decimal("200"),
        )
        url = reverse(
            "projets:supprimer_formule_revision",
            args=[self.projet.pk, formule.pk],
        )

        response = self.client.post(url)
        self.assertRedirects(
            response,
            reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        self.assertTrue(FormuleRevision.objects.filter(pk=formule.pk).exists())
        ligne.refresh_from_db()
        self.assertEqual(ligne.formule_revision, formule)
        with self.settings(STORAGES={
            **settings.STORAGES,
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }):
            page = self.client.get(
                reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            )
        self.assertContains(
            page,
            "Cette formule est affectée à 2 lignes.",
        )

        response = self.client.post(url, {"confirmer_suppression": "on"})
        self.assertRedirects(
            response,
            reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(FormuleRevision.objects.filter(pk=formule.pk).exists())
        ligne.refresh_from_db()
        self.assertIsNone(ligne.formule_revision_id)
        enfant_a.refresh_from_db()
        enfant_b.refresh_from_db()
        self.assertIsNone(enfant_a.formule_revision_id)
        self.assertIsNone(enfant_b.formule_revision_id)

    def test_suppression_formule_sans_affectation_est_immediate(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-suppression-simple",
            email="suppression-simple@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        formule = self._formule_avec_terme()

        response = self.client.post(
            reverse(
                "projets:supprimer_formule_revision",
                args=[self.projet.pk, formule.pk],
            ),
        )
        self.assertRedirects(
            response,
            reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            fetch_redirect_response=False,
        )
        self.assertFalse(FormuleRevision.objects.filter(pk=formule.pk).exists())

    def test_calcul_revision_attachement_et_mise_a_jour_decompte(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-calcul-revision",
            email="calcul-revision@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        formule = self._formule_avec_terme()
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        parent = LigneBordereau.objects.create(
            lot=lot,
            designation="Travaux",
            quantite=Decimal("0"),
            prix_unitaire=Decimal("0"),
        )
        principale = LigneBordereau.objects.create(
            lot=lot,
            parent=parent,
            designation="Terrassements",
            quantite=Decimal("10"),
            prix_unitaire=Decimal("100"),
            montant_calcule=Decimal("1000"),
            formule_revision=formule,
        )
        attachement = Attachement.objects.create(
            projet=self.projet,
            date_etablissement=date(2026, 6, 30),
            date_debut_periode=date(2026, 6, 1),
            date_fin_periode=date(2026, 6, 30),
            statut="BROUILLON",
        )
        LigneAttachement.objects.create(
            attachement=attachement,
            ligne_lot=principale,
            designation=principale.designation,
            quantite_initiale=principale.quantite,
            prix_unitaire=principale.prix_unitaire,
            quantite_realisee=Decimal("10"),
            quantite_cumulee=Decimal("10"),
        )
        decompte = Decompte.objects.create(
            attachement=attachement,
            numero="DP-REV-01",
            date_emission=date(2026, 6, 30),
            montant_revision_prix=Decimal("0"),
        )
        IndexValeur.objects.create(
            index=self.index,
            mois=date(2026, 1, 1),
            valeur=Decimal("100"),
            statut=StatutIndex.IND_DEF,
        )
        IndexValeur.objects.create(
            index=self.index,
            mois=date(2026, 6, 1),
            valeur=Decimal("110"),
            statut=StatutIndex.IND_DEF,
        )

        detail = self.client.get(
            reverse("projets:detail_attachement", args=[attachement.pk]),
        )
        self.assertContains(
            detail,
            reverse(
                "projets:calculer_revision_attachement",
                args=[attachement.pk],
            ),
        )
        response = self.client.post(
            reverse(
                "projets:calculer_revision_attachement",
                args=[attachement.pk],
            ),
        )
        self.assertRedirects(
            response,
            reverse("projets:detail_attachement", args=[attachement.pk]),
            fetch_redirect_response=False,
        )
        attachement.refresh_from_db()
        decompte.refresh_from_db()
        self.assertEqual(attachement.montant_revision_prix, Decimal("85.00"))
        self.assertEqual(decompte.montant_revision_prix, Decimal("85.00"))
        self.assertEqual(attachement.detail_calcul_revision["provisoire"], False)
        self.assertIsNotNone(attachement.date_calcul_revision)
        self.assertEqual(
            attachement.detail_calcul_revision["lignes"][0]["mois"][0]
            ["termes"][0]["indices"][0]["base"],
            "100.0000",
        )
        self.assertEqual(
            attachement.detail_calcul_revision["lignes"][0]["mois"][0]
            ["termes"][0]["contribution_revision_ht"],
            "85.00",
        )

        note = self.client.get(
            reverse(
                "projets:note_calcul_revision_attachement",
                args=[attachement.pk],
            ),
        )
        self.assertEqual(note.status_code, 200)
        self.assertContains(note, "Calcul de la révision des prix")
        self.assertContains(note, "Coefficients de révision")
        self.assertContains(note, "Récapitulatif mensuel")
        self.assertContains(note, "Contribution des index HT")
        self.assertContains(note, "85,00")

    def test_controle_indexes_exige_m0_et_mois_attachements(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-grille-index",
            email="grille-index@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        formule = self._formule_avec_terme()
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        ligne = LigneBordereau.objects.create(
            lot=lot,
            designation="Travaux",
            quantite=Decimal("1"),
            prix_unitaire=Decimal("100"),
            montant_calcule=Decimal("100"),
            formule_revision=formule,
        )
        Attachement.objects.bulk_create([Attachement(
            projet=self.projet,
            sequence=1,
            numero="DP01",
            date_etablissement=date(2026, 11, 30),
            date_debut_periode=date(2026, 10, 1),
            date_fin_periode=date(2026, 11, 30),
        )])
        controle = controle_indexes_revision(self.projet)
        self.assertFalse(controle["pret"])
        self.assertEqual(
            controle["dernier_attachement_mois"],
            date(2026, 11, 1),
        )
        self.assertEqual(len(controle["manquants"]), 7)

        for mois in [
            date(2026, 1, 1),
            date(2026, 6, 1),
            date(2026, 7, 1),
            date(2026, 8, 1),
            date(2026, 9, 1),
            date(2026, 10, 1),
            date(2026, 11, 1),
        ]:
            IndexValeur.objects.create(
                index=self.index,
                mois=mois,
                valeur=Decimal("100"),
                statut=StatutIndex.IND_PRO
                if mois == date(2026, 11, 1)
                else StatutIndex.IND_DEF,
            )
        controle = controle_indexes_revision(self.projet)
        self.assertTrue(controle["pret"])
        self.assertTrue(controle["bulletin_a_jour"])
        self.assertEqual(len(controle["provisoires"]), 1)

        with self.settings(STORAGES={
            **settings.STORAGES,
            "staticfiles": {
                "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
            },
        }):
            page = self.client.get(
                reverse("projets:gestion_revision_prix", args=[self.projet.pk]),
            )
        self.assertContains(page, "revision-index-tableview")
        self.assertContains(page, "revision-index-resize-handle")
        self.assertContains(page, "data-add-index-row")
        self.assertContains(page, "data-add-index-column")
        self.assertContains(page, "data-index-paste-status")
        self.assertContains(page, 'value="100.0000"')
        self.assertNotContains(page, 'value="100,0000"')
        self.assertNotContains(page, "IND_DEF</span>")
        self.assertEqual(len(page.context["grille_indexes"]), 1)
        self.assertEqual(
            [
                item["statut"] for item in page.context["statuts_mois"]
            ],
            [
                "IND_DEF",
                "IND_DEF",
                "IND_DEF",
                "IND_DEF",
                "IND_DEF",
                "IND_DEF",
                "IND_PRO",
            ],
        )
        self.assertEqual(
            page.context["controle_indexes"]["mois_tableur"],
            [
                date(2026, 1, 1),
                date(2026, 6, 1),
                date(2026, 7, 1),
                date(2026, 8, 1),
                date(2026, 9, 1),
                date(2026, 10, 1),
                date(2026, 11, 1),
            ],
        )

    def test_ajout_ligne_et_colonne_index_depuis_tableur(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-ajout-index",
            email="ajout-index@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        self._formule_avec_terme()

        response = self.client.post(
            reverse("projets:enregistrer_valeurs_indexes", args=[self.projet.pk]),
            {
                "nouvel_index_n1_symbole": "  ",
                "nouvel_index_n1_libelle": "Ignoré",
                "nouveau_mois_vide": "",
                "nouvel_index_n2_symbole": "NIDX",
                "nouvel_index_n2_libelle": "Nouvel index",
                "nouveau_mois_c1": "2026-07",
                "statut_mois_col_c1": "IND_PRO",
                "valeur_nouvelle_ligne_n2_col_c1": "123,45",
                "source_bulletin": "Test",
            },
        )
        self.assertEqual(response.status_code, 302)
        index = IndexReference.objects.get(symbole="NIDX")
        self.assertTrue(
            IndexRevisionProjet.objects.filter(
                projet=self.projet,
                index=index,
            ).exists()
        )
        valeur = IndexValeur.objects.get(
            index=index,
            mois=date(2026, 7, 1),
        )
        self.assertEqual(valeur.valeur, Decimal("123.4500"))
        self.assertEqual(valeur.statut, StatutIndex.IND_PRO)
        self.assertFalse(
            IndexReference.objects.filter(libelle="Ignoré").exists(),
        )
        controle = controle_indexes_revision(self.projet)
        self.assertIn(date(2026, 7, 1), controle["mois_tableur"])
        self.assertIn(index.pk, index_ids_tableur(self.projet, controle))

    def test_mise_a_jour_definitif_devient_provisoire(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-update-index",
            email="update-index@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        self._formule_avec_terme()
        Attachement.objects.bulk_create([Attachement(
            projet=self.projet,
            sequence=1,
            numero="DP01",
            date_etablissement=date(2026, 7, 31),
            date_debut_periode=date(2026, 6, 1),
            date_fin_periode=date(2026, 7, 31),
        )])
        premier = IndexValeur.objects.create(
            index=self.index,
            mois=date(2026, 6, 1),
            valeur=Decimal("100.0000"),
            statut=StatutIndex.IND_DEF,
        )
        second = IndexValeur.objects.create(
            index=self.index,
            mois=date(2026, 7, 1),
            valeur=Decimal("101.0000"),
            statut=StatutIndex.IND_DEF,
        )

        response = self.client.post(
            reverse(
                "projets:enregistrer_valeurs_indexes",
                args=[self.projet.pk],
            ),
            {
                "statut_mois_202601": StatutIndex.IND_DEF,
                f"valeur_index_{self.index.pk}_202601": "",
                "statut_mois_202606": StatutIndex.IND_PRO,
                f"valeur_index_{self.index.pk}_202606": "110.5000",
                "statut_mois_202607": StatutIndex.IND_PRO,
                f"valeur_index_{self.index.pk}_202607": "111.2500",
            },
        )
        self.assertEqual(response.status_code, 302)
        premier.refresh_from_db()
        second.refresh_from_db()
        self.assertEqual(
            (premier.valeur, premier.statut),
            (Decimal("110.5000"), StatutIndex.IND_PRO),
        )
        self.assertEqual(
            (second.valeur, second.statut),
            (Decimal("111.2500"), StatutIndex.IND_PRO),
        )

    def test_calcul_revision_bloque_si_ligne_principale_non_couverte(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-calcul-incomplet",
            email="calcul-incomplet@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        parent = LigneBordereau.objects.create(
            lot=lot,
            designation="Travaux",
            quantite=Decimal("0"),
            prix_unitaire=Decimal("0"),
        )
        LigneBordereau.objects.create(
            lot=lot,
            parent=parent,
            designation="Terrassements",
            quantite=Decimal("10"),
            prix_unitaire=Decimal("100"),
            montant_calcule=Decimal("1000"),
        )
        attachement = Attachement.objects.create(
            projet=self.projet,
            date_etablissement=date(2026, 6, 30),
            date_debut_periode=date(2026, 6, 1),
            date_fin_periode=date(2026, 6, 30),
            statut="BROUILLON",
        )

        detail = self.client.get(
            reverse("projets:detail_attachement", args=[attachement.pk]),
        )
        self.assertNotContains(
            detail,
            reverse(
                "projets:calculer_revision_attachement",
                args=[attachement.pk],
            ),
        )
        response = self.client.post(
            reverse(
                "projets:calculer_revision_attachement",
                args=[attachement.pk],
            ),
        )
        self.assertEqual(response.status_code, 302)
        attachement.refresh_from_db()
        self.assertIsNone(attachement.date_calcul_revision)

    def test_calcul_agrege_les_descendantes_sur_la_ligne_affectee(self):
        formule = self._formule_avec_terme()
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        parent = LigneBordereau.objects.create(
            lot=lot,
            designation="Ouvrages",
            quantite=Decimal("0"),
            prix_unitaire=Decimal("0"),
            formule_revision=formule,
        )
        enfant_a = LigneBordereau.objects.create(
            lot=lot,
            parent=parent,
            designation="Terrassements",
            quantite=Decimal("10"),
            prix_unitaire=Decimal("100"),
            montant_calcule=Decimal("1000"),
        )
        enfant_b = LigneBordereau.objects.create(
            lot=lot,
            parent=parent,
            designation="Voirie",
            quantite=Decimal("5"),
            prix_unitaire=Decimal("200"),
            montant_calcule=Decimal("1000"),
        )
        attachement = Attachement.objects.bulk_create([Attachement(
            projet=self.projet,
            sequence=1,
            numero="DP01",
            date_etablissement=date(2026, 6, 30),
            date_debut_periode=date(2026, 6, 1),
            date_fin_periode=date(2026, 6, 30),
        )])[0]
        for enfant in (enfant_a, enfant_b):
            LigneAttachement.objects.create(
                attachement=attachement,
                ligne_lot=enfant,
                designation=enfant.designation,
                quantite_initiale=enfant.quantite,
                prix_unitaire=enfant.prix_unitaire,
                quantite_realisee=enfant.quantite,
                quantite_cumulee=enfant.quantite,
            )
        IndexValeur.objects.create(
            index=self.index,
            mois=date(2026, 1, 1),
            valeur=Decimal("100"),
            statut=StatutIndex.IND_DEF,
        )
        IndexValeur.objects.create(
            index=self.index,
            mois=date(2026, 6, 1),
            valeur=Decimal("110"),
            statut=StatutIndex.IND_DEF,
        )

        from projets.services.revision_service import calculer_revision_attachement
        montant, detail = calculer_revision_attachement(attachement)

        self.assertEqual(montant, Decimal("170.00"))
        self.assertEqual(len(detail["lignes"]), 1)
        self.assertEqual(detail["lignes"][0]["ligne"], "Ouvrages")
        self.assertEqual(detail["lignes"][0]["montant_ht"], "2000.00")
        self.assertEqual(
            detail["lignes"][0]["nombre_lignes_descendantes"],
            2,
        )

    def test_calcul_global_prepare_rapport_tous_attachements(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-revision-global",
            email="revision-global@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        liste_attachements = self.client.get(
            reverse("projets:liste_attachements", args=[self.projet.pk]),
        )
        self.assertContains(liste_attachements, "data-calcul-revision-overlay")
        formule = self._formule_avec_terme()
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        principale = LigneBordereau.objects.create(
            lot=lot,
            designation="Ouvrages",
            quantite=Decimal("10"),
            prix_unitaire=Decimal("100"),
            montant_calcule=Decimal("1000"),
            formule_revision=formule,
        )
        attachement = Attachement.objects.bulk_create([Attachement(
            projet=self.projet,
            sequence=1,
            numero="DP01",
            date_etablissement=date(2026, 7, 31),
            date_debut_periode=date(2026, 6, 1),
            date_fin_periode=date(2026, 7, 31),
        )])[0]
        LigneAttachement.objects.create(
            attachement=attachement,
            ligne_lot=principale,
            designation=principale.designation,
            quantite_initiale=principale.quantite,
            prix_unitaire=principale.prix_unitaire,
            quantite_realisee=Decimal("10"),
            quantite_cumulee=Decimal("10"),
        )
        IndexValeur.objects.create(
            index=self.index,
            mois=date(2026, 1, 1),
            valeur=Decimal("100"),
            statut=StatutIndex.IND_DEF,
        )
        for mois in (date(2026, 6, 1), date(2026, 7, 1)):
            IndexValeur.objects.create(
                index=self.index,
                mois=mois,
                valeur=Decimal("110"),
                statut=StatutIndex.IND_PRO,
            )

        osa_type, _ = TypeOrdreService.objects.get_or_create(
            code="OSA",
            defaults={
                "nom": "OS d'arrêt",
                "description": "Arrêt",
                "ordre_min": 2,
                "ordre_max": 10,
            },
        )
        osr_type, _ = TypeOrdreService.objects.get_or_create(
            code="OSR",
            defaults={
                "nom": "OS de reprise",
                "description": "Reprise",
                "ordre_min": 2,
                "ordre_max": 10,
            },
        )
        OrdreService.objects.create(
            projet=self.projet,
            type_os=osa_type,
            reference="OSA-REV",
            titre="Arrêt",
            description="Arrêt",
            date_publication=date(2026, 6, 15),
            date_effet=date(2026, 6, 16),
            statut="NOTIFIE",
            ordre_sequence=2,
        )
        OrdreService.objects.create(
            projet=self.projet,
            type_os=osr_type,
            reference="OSR-REV",
            titre="Reprise",
            description="Reprise",
            date_publication=date(2026, 6, 30),
            date_effet=date(2026, 7, 1),
            statut="NOTIFIE",
            ordre_sequence=3,
        )

        response = self.client.post(
            reverse(
                "projets:calculer_tous_attachements_revision",
                args=[self.projet.pk],
            ),
        )
        self.assertRedirects(
            response,
            reverse(
                "projets:rapport_revision_tous_attachements",
                args=[self.projet.pk],
            ),
            fetch_redirect_response=False,
        )
        rapport = self.client.get(
            reverse(
                "projets:rapport_revision_tous_attachements",
                args=[self.projet.pk],
            ),
        )
        self.assertContains(rapport, "Ventilation des montants partiels par mois")
        self.assertContains(rapport, "Calcul de la révision des prix")
        self.assertContains(rapport, "Montants relatifs aux formules")
        self.assertContains(rapport, "P / P0")
        self.assertContains(rapport, "TOTAL RÉVISIONS")
        self.assertNotContains(rapport, "<small>P</small>", html=True)
        self.assertNotContains(rapport, "<small>D</small>", html=True)
        self.assertContains(rapport, "Provisoire")
        self.assertContains(rapport, "06/2026")
        attachement.refresh_from_db()
        self.assertTrue(attachement.date_calcul_revision)
        self.assertEqual(
            attachement.detail_calcul_revision["lignes"][0]["mois"][0]["jours_travailles"],
            15,
        )
        self.assertEqual(
            attachement.detail_calcul_revision["lignes"][0]["mois"][1]["jours_travailles"],
            31,
        )

    def test_affectation_commune_remonte_sur_le_parent(self):
        admin = get_user_model().objects.create_superuser(
            username="admin-affectation-parent",
            email="affectation-parent@example.com",
            password="secret",
        )
        self.client.force_login(admin)
        formule = self._formule_avec_terme()
        lot = LotProjet.objects.create(projet=self.projet, nom="Lot principal")
        parent = LigneBordereau.objects.create(
            lot=lot,
            designation="Ouvrages",
            quantite=Decimal("0"),
            prix_unitaire=Decimal("0"),
        )
        enfants = [
            LigneBordereau.objects.create(
                lot=lot,
                parent=parent,
                designation=designation,
                quantite=Decimal("1"),
                prix_unitaire=Decimal("100"),
                montant_calcule=Decimal("100"),
            )
            for designation in ("Terrassements", "Voirie")
        ]

        response = self.client.post(
            reverse(
                "projets:affecter_formules_revision",
                args=[self.projet.pk],
            ),
            {
                f"formule_ligne_{enfant.pk}": str(formule.pk)
                for enfant in enfants
            },
        )
        self.assertEqual(response.status_code, 302)
        parent.refresh_from_db()
        self.assertEqual(parent.formule_revision, formule)
        self.assertFalse(
            LigneBordereau.objects.filter(
                pk__in=[enfant.pk for enfant in enfants],
                formule_revision__isnull=False,
            ).exists()
        )

