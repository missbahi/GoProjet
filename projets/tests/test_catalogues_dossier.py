from datetime import date
from decimal import Decimal
from io import StringIO
import json

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.core.management import call_command

from projets.catalogues import initialiser_categories_dossier
from projets.forms import (
    CategorieChargeForm, DepenseRapportJournalierForm,
    DepenseSituationMensuelleForm, MaterielForm, RessourceAffecteeForm,
)
from projets.models import CategorieCharge, Dossier, Materiel, Projet, RessourceAffectee


@override_settings(
    STORAGES={
        'default': {'BACKEND': 'django.core.files.storage.InMemoryStorage'},
        'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'},
    },
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
)
class CatalogueDossierTests(TestCase):
    def setUp(self):
        self.dossier = Dossier.objects.create(nom='Alpha')
        self.autre = Dossier.objects.create(nom='Beta')
        initialiser_categories_dossier(self.dossier)
        initialiser_categories_dossier(self.autre)
        self.projet = Projet.objects.create(nom='Projet Alpha', numero='ALPHA', dossier=self.dossier)
        self.categorie = CategorieCharge.objects.get(dossier=self.dossier, code='MATERIEL')
        self.autre_categorie = CategorieCharge.objects.get(dossier=self.autre, code='MATERIEL')
        self.materiel = Materiel.objects.create(dossier=self.dossier, designation='Machine Alpha', immatriculation='P001')
        self.etranger = Materiel.objects.create(dossier=self.autre, designation='Machine secrète', immatriculation='P001')
        self.admin = User.objects.create_user('admin-alpha')
        self.admin.profile.role = 'ADMIN_DOSSIER'
        self.admin.profile.save()
        self.dossier.utilisateurs.add(self.admin)
        self.projet.users.add(self.admin)
        self.client.force_login(self.admin)

    def affectation_data(self, **overrides):
        data = {
            'categorie_charge': self.categorie.pk, 'objet_id': self.materiel.pk,
            'date_debut': '2026-01-01', 'tarif': '100', 'actif': 'on',
        }
        data.update(overrides)
        return data

    def test_config_lists_and_crud_are_scoped_including_forged_ids(self):
        response = self.client.get(reverse('projets:partial_materiel'))
        self.assertContains(response, 'Machine Alpha')
        self.assertContains(response, 'de Alpha')
        self.assertNotContains(response, 'Machine secrète')
        response = self.client.post(reverse('projets:modifier_materiel', args=[self.etranger.pk]), {
            'designation': 'Vol', 'prix_unitaire': '0',
        })
        self.assertEqual(response.status_code, 404)
        self.etranger.refresh_from_db()
        self.assertEqual(self.etranger.designation, 'Machine secrète')
        self.assertEqual(self.client.get(reverse('projets:partial_materiel') + f'?dossier={self.autre.pk}').status_code, 403)

    def test_assignment_rejects_foreign_resource_and_category(self):
        valid = RessourceAffecteeForm(self.affectation_data(), projet=self.projet)
        self.assertTrue(valid.is_valid(), valid.errors)
        for overrides in (
            {'objet_id': self.etranger.pk}, {'categorie_charge': self.autre_categorie.pk},
            {'categorie_charge': 'forged'},
        ):
            form = RessourceAffecteeForm(self.affectation_data(**overrides), projet=self.projet)
            self.assertFalse(form.is_valid())

    def test_project_writers_can_pick_but_not_configure(self):
        for role in ('DIRECTEUR_PROJET', 'CHEF_PROJET'):
            self.admin.profile.role = role
            self.admin.profile.save()
            self.assertEqual(self.client.get(reverse('projets:partial_materiel')).status_code, 403)
            self.assertEqual(self.client.get(reverse('projets:data_view')).status_code, 403)
            response = self.client.get(
                reverse('projets:api_options_ressource', args=[self.projet.pk]), {'code': 'MATERIEL'})
            self.assertEqual(response.status_code, 200)
            self.assertEqual([row['id'] for row in response.json()['options']], [self.materiel.pk])

    def test_expense_forms_reject_foreign_category(self):
        forms = (
            DepenseRapportJournalierForm({
                'categorie_charge': self.autre_categorie.pk, 'designation': 'Charge',
                'quantite': '1', 'unite': 'u', 'prix_unitaire': '10',
            }, projet=self.projet),
            DepenseSituationMensuelleForm({
                'categorie_charge': self.autre_categorie.pk, 'designation': 'Charge',
                'montant_base': '10',
            }, projet=self.projet),
        )
        for form in forms:
            self.assertFalse(form.is_valid())
            self.assertIn('categorie_charge', form.errors)

    def test_used_category_code_cannot_change(self):
        RessourceAffectee.objects.create(
            projet=self.projet, categorie_charge=self.categorie, objet_id=self.materiel.pk,
            designation='Historique', date_debut=date(2026, 1, 1), tarif=Decimal('99'),
        )
        form = CategorieChargeForm(
            {'code': 'NOUVEAU', 'nom': 'Matériel', 'ordre': 0, 'actif': 'on'},
            instance=self.categorie, dossier=self.dossier)
        self.assertFalse(form.is_valid())
        self.assertIn('code', form.errors)

    def test_global_admin_must_choose_and_sees_unowned_inventory(self):
        global_admin = User.objects.create_superuser('global', 'global@example.com', 'password')
        self.client.force_login(global_admin)
        orphan = Materiel.objects.create(designation='Ancien non classé')
        response = self.client.get(reverse('projets:data_view'))
        self.assertContains(response, 'choisir un dossier')
        self.assertContains(response, orphan.designation)
        self.assertContains(response, 'Alpha')
        self.assertContains(response, 'Beta')
        self.assertIsNone(Materiel.objects.get(pk=orphan.pk).dossier_id)

    def test_project_picker_uses_project_dossier_not_global_admin_session(self):
        global_admin = User.objects.create_superuser('global-picker', 'picker@example.com', 'password')
        self.client.force_login(global_admin)
        session = self.client.session
        session['dossier_id'] = self.autre.pk
        session.save()
        response = self.client.get(
            reverse('projets:api_options_ressource', args=[self.projet.pk]), {'code': 'MATERIEL'})
        self.assertEqual([row['id'] for row in response.json()['options']], [self.materiel.pk])

    def test_material_uniqueness_and_save_are_per_dossier_and_global_types_are_protected(self):
        self.etranger.immatriculation = 'BETA-ONLY'
        self.etranger.save()
        form = MaterielForm({
            'designation': 'Nouvelle machine', 'immatriculation': 'BETA-ONLY',
            'prix_unitaire': '20', 'dossier': self.autre.pk, 'actif': 'on',
        }, dossier=self.dossier)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save().dossier, self.dossier)
        for route in ('partial_types_materiel', 'ajouter_type_materiel'):
            response = self.client.post(reverse('projets:' + route), {'nom': 'Type interdit'})
            self.assertEqual(response.status_code, 403)

    def test_resource_edit_and_delete_cannot_cross_project_perimeter(self):
        foreign_project = Projet.objects.create(nom='Beta', numero='BETA', dossier=self.autre)
        resource = RessourceAffectee.objects.create(
            projet=foreign_project, categorie_charge=self.autre_categorie,
            objet_id=self.etranger.pk, designation='Historique Beta', date_debut=date(2026, 1, 1),
        )
        for name in ('modifier_ressource', 'supprimer_ressource'):
            response = self.client.post(reverse('projets:' + name, args=[resource.pk]), self.affectation_data())
            self.assertIn(response.status_code, (403, 404))
        self.assertTrue(RessourceAffectee.objects.filter(pk=resource.pk).exists())

    def test_inventory_reports_only_unowned_catalog_rows_without_assigning_them(self):
        orphan = Materiel.objects.create(designation='Sans propriétaire')
        output = StringIO()
        call_command('inventorier_catalogues_dossier', '--json', stdout=output)
        inventory = json.loads(output.getvalue())
        self.assertEqual(inventory['Materiel'], [{'id': orphan.pk, 'libelle': orphan.designation}])
        orphan.refresh_from_db()
        self.assertIsNone(orphan.dossier_id)

    def test_new_dossier_seeds_only_baseline_not_private_or_global_customizations(self):
        CategorieCharge.objects.create(code='GLOBAL_PRIVE', nom='Ne pas copier')
        CategorieCharge.objects.create(dossier=self.dossier, code='ALPHA_PRIVE', nom='Alpha seulement')
        new_dossier = Dossier.objects.create(nom='Gamma')
        categories = CategorieCharge.objects.filter(dossier=new_dossier)
        self.assertEqual(categories.count(), 7)
        self.assertFalse(categories.filter(code__in=['GLOBAL_PRIVE', 'ALPHA_PRIVE']).exists())
        self.assertFalse(Materiel.objects.filter(dossier=new_dossier).exists())
