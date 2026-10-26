from datetime import date, timedelta

from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from projets.forms import OrdreServiceForm
from projets.models import OrdreService, Projet, TypeOrdreService
from projets.models.projet import ajouter_mois_calendaires


class AvenantDelaiTests(TestCase):
    def setUp(self):
        self.projet = Projet.objects.create(
            nom="Avenant", numero="AV-1", objet="Travaux", maitre_ouvrage="MO",
            localisation="Site", delai=30, unite_delai="JOURS",
        )
        self.os("OSN", 1, date(2026, 1, 1))
        self.os("OSC", 2, date(2026, 1, 1))

    def os(self, code, sequence, effet, **kwargs):
        return OrdreService.objects.create(
            projet=self.projet, type_os=TypeOrdreService.objects.get(code=code),
            reference=f"OS-{sequence}", titre="Ordre", description="Justification",
            date_publication=date(2026, 1, 1), date_effet=effet,
            ordre_sequence=sequence, **{"statut": "NOTIFIE", **kwargs},
        )

    def avenant(self, duree=1, unite="MOIS", motif="CIRCULAIRE_09_2022", sequence=3):
        return OrdreService(
            projet=self.projet, type_os=TypeOrdreService.objects.get(code="OSVD"),
            reference=f"AV-{sequence}", titre="Avenant", description="Justification",
            date_publication=date(2026, 1, 1), date_effet=date(2026, 2, 1),
            ordre_sequence=sequence, duree_extension=duree, unite_extension=unite,
            motif=motif, statut="NOTIFIE",
        )

    def notify(self, ordre):
        ordre.full_clean()
        ordre.save()
        return ordre

    def test_migration_seeds_type_and_prerequisite(self):
        type_os = TypeOrdreService.objects.get(code="OSVD")
        self.assertFalse(type_os.unique_dans_projet)
        self.assertEqual(list(type_os.precedent_obligatoire.values_list("code", flat=True)), ["OSC"])

    def test_draft_and_cancelled_have_no_effect_and_initial_delay_is_preserved(self):
        ordre = self.avenant(10, "JOURS", "AUTRE")
        ordre.statut = "BROUILLON"
        ordre.save()
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 1, 31))
        ordre.statut = "NOTIFIE"
        self.notify(ordre)
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 2, 10))
        ordre.save()
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 2, 10))
        ordre.statut = "ANNULE"
        ordre.save()
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 1, 31))
        self.projet.refresh_from_db()
        self.assertEqual(self.projet.delai, 30)

    def test_effect_date_controls_historical_calculation(self):
        self.notify(self.avenant(1))
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 1, 31)), date(2026, 1, 31))
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 2, 1)), date(2026, 2, 28))

    def test_calendar_months_use_end_of_month_without_subtracting_a_day(self):
        self.assertEqual(ajouter_mois_calendaires(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(ajouter_mois_calendaires(date(2028, 1, 31), 1), date(2028, 2, 29))
        self.notify(self.avenant(6))
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 7, 31))

    def test_circulaire_days_are_compared_to_six_calendar_months_not_180_days(self):
        exact = (date(2026, 7, 31) - date(2026, 1, 31)).days
        self.assertEqual(exact, 181)
        self.notify(self.avenant(exact, "JOURS"))
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 7, 31))
        extra = self.avenant(1, "JOURS", sequence=4)
        with self.assertRaisesMessage(ValidationError, "six mois calendaires"):
            extra.full_clean()

    def test_month_limit_is_cumulative_and_excludes_other_motifs(self):
        self.notify(self.avenant(2))
        self.notify(self.avenant(8, motif="AUTRE", sequence=4))
        self.notify(self.avenant(4, sequence=5))
        with self.assertRaisesMessage(ValidationError, "six mois calendaires"):
            self.avenant(1, sequence=6).full_clean()

    def test_mixed_units_and_edits_are_validated_without_counting_self_twice(self):
        first = self.notify(self.avenant(5))
        self.notify(self.avenant(28, "JOURS", sequence=4))
        first.full_clean()
        first.duree_extension = 6
        with self.assertRaisesMessage(ValidationError, "six mois calendaires"):
            first.full_clean()

    def test_positive_duration_motif_effect_and_commencement_are_required(self):
        for name, value in [
            ("duree_extension", 0), ("duree_extension", -1),
            ("duree_extension", None), ("motif", ""), ("date_effet", None),
            ("date_effet", date(2025, 12, 1)),
        ]:
            with self.subTest(name=name, value=value):
                ordre = self.avenant()
                setattr(ordre, name, value)
                with self.assertRaises(ValidationError):
                    ordre.full_clean()
        self.projet.ordres_service.filter(type_os__code="OSC").update(statut="BROUILLON")
        with self.assertRaises(ValidationError):
            self.avenant().full_clean()

    def test_stops_and_resumes_keep_their_existing_duration(self):
        self.os("OSA", 3, date(2026, 1, 10))
        self.os("OSR", 4, date(2026, 1, 20))
        self.notify(self.avenant(1, sequence=5))
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 3, 10))
        self.assertEqual(self.projet.jours_decoules_depuis_demarrage(date(2026, 2, 1)), 21)

    def test_avenant_does_not_allow_two_consecutive_stops(self):
        self.os("OSA", 3, date(2026, 1, 10))
        self.notify(self.avenant(sequence=4))
        second = self.os("OSA", 5, date(2026, 2, 10), statut="BROUILLON")
        second.statut = "NOTIFIE"
        with self.assertRaisesMessage(ValidationError, "autre OS d'arrêt"):
            second.full_clean()

    def test_form_sets_project_before_model_validation_and_keeps_legacy_unit_default(self):
        data = {
            "type_os": TypeOrdreService.objects.get(code="OSVD").pk,
            "reference": "FORM", "titre": "Avenant", "description": "Justification",
            "date_publication": "2026-01-01", "date_effet": "2026-02-01",
            "statut": "NOTIFIE", "duree_extension": "7", "unite_extension": "MOIS",
            "motif": "CIRCULAIRE_09_2022",
        }
        form = OrdreServiceForm(data, projet=self.projet)
        self.assertFalse(form.is_valid())
        self.assertIn("duree_extension", form.errors)
        data.update(
            type_os=TypeOrdreService.objects.get(code="AUTRE").pk,
            statut="BROUILLON", duree_extension="0", unite_extension="", motif="",
        )
        form = OrdreServiceForm(data, projet=self.projet)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["unite_extension"], "JOURS")

    def test_prior_ordinary_extension_sets_calendar_reference(self):
        self.notify(self.avenant(10, "JOURS", "AUTRE"))
        # 10 février + six mois = 10 août, soit 181 jours en 2026.
        exact = (date(2026, 8, 10) - date(2026, 2, 10)).days
        self.notify(self.avenant(exact, "JOURS", sequence=4))
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 8, 10))
        with self.assertRaises(ValidationError):
            self.avenant(1, "JOURS", sequence=5).full_clean()

    def test_cancelled_extension_releases_the_circulaire_budget(self):
        ordre = self.notify(self.avenant(6))
        ordre.statut = "ANNULE"
        ordre.save()
        self.notify(self.avenant(6, sequence=4))
        self.assertEqual(self.projet.date_fin_previsionnelle(date(2026, 3, 1)), date(2026, 7, 31))

    def test_large_duration_is_a_validation_error_not_an_unhandled_date_overflow(self):
        for motif in ["AUTRE", "CIRCULAIRE_09_2022"]:
            with self.subTest(motif=motif):
                with self.assertRaises(ValidationError):
                    self.avenant(1000000, "MOIS", motif).full_clean()

    def test_notification_and_cancellation_refresh_the_project_delay_flag(self):
        today = date.today()
        start = today - timedelta(days=30)
        self.projet.date_debut = start
        self.projet.delai = 15
        self.projet.statut = Projet.Statut.EN_COURS
        self.projet.save()
        self.projet.ordres_service.filter(type_os__code="OSC").update(date_effet=start)
        self.assertTrue(self.projet.en_retard)
        ordre = self.avenant(60, "JOURS", "AUTRE")
        ordre.date_effet = today
        self.notify(ordre)
        self.projet.refresh_from_db()
        self.assertFalse(self.projet.en_retard)
        ordre.statut = "ANNULE"
        ordre.save()
        self.projet.refresh_from_db()
        self.assertTrue(self.projet.en_retard)

    @override_settings(STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_view_exposes_extension_and_both_notification_routes_enforce_cumulative_cap(self):
        user = get_user_model().objects.create_superuser(username="os-admin")
        self.client.force_login(user)
        url = reverse("projets:ordres_service", args=[self.projet.pk])
        response = self.client.get(url)
        self.assertContains(response, "OSVD")
        self.assertContains(response, "CIRCULAIRE_09_2022")
        first = self.avenant(6)
        first.statut = "BROUILLON"
        first.save()
        self.client.post(url, {"notifier_os": first.pk})
        first.refresh_from_db()
        self.assertEqual(first.statut, "NOTIFIE")
        second = self.avenant(1, sequence=4)
        second.statut = "BROUILLON"
        second.save()
        notify_url = reverse("projets:notifier_ordre_service", args=[self.projet.pk, second.pk])
        self.client.post(notify_url)
        second.refresh_from_db()
        self.assertEqual(second.statut, "BROUILLON")
        self.client.post(url, {"notifier_os": second.pk})
        second.refresh_from_db()
        self.assertEqual(second.statut, "BROUILLON")
