from contextlib import redirect_stdout
from datetime import date
from io import StringIO
from unittest import TestCase

from django.db import connections
from django.db.backends.sqlite3.base import DatabaseWrapper
from django.db.migrations.executor import MigrationExecutor


class CatalogueMigrationTests(TestCase):
    """Run the real historical graph on a dedicated, disposable in-memory database."""

    def test_shared_rows_split_without_losing_snapshots_workshops_or_unowned_rows(self):
        alias = 'default'
        original_connection = connections[alias]
        config = dict(connections['default'].settings_dict)
        config.update(NAME=':memory:', ENGINE='django.db.backends.sqlite3')
        connection = DatabaseWrapper(config, alias)
        connections[alias] = connection
        try:
            executor = MigrationExecutor(connection)
            before = [('projets', '0087_remove_retired_profile_role_choices'), ('goplan', '0011_performance_indexes')]
            executor.migrate(before)
            apps = executor.loader.project_state(before).apps

            def model(name, app='projets'):
                return apps.get_model(app, name).objects.using(alias)

            alpha = model('Dossier').create(nom='Alpha')
            beta = model('Dossier').create(nom='Beta')
            enterprise = model('Entreprise').create(nom='Entreprise commune')
            orphan = model('Materiel').create(designation='Sans usage')
            machine = model('Materiel').create(designation='Machine commune', prix_unitaire=42)
            category = model('CategorieCharge').get(code='MATERIEL')
            category.nom = 'Libellé historique'
            category.save(using=alias)
            projects = []
            resources = []
            workshops = []
            expense_ids = []
            monthly_expense_ids = []
            readings = []
            other_resources = []
            for dossier in (alpha, beta):
                project = model('Projet').create(
                    nom=dossier.nom, numero=dossier.nom, dossier_id=dossier.pk,
                    entreprise_id=enterprise.pk,
                )
                projects.append(project)
                workshop = model('Atelier').create(projet_id=project.pk, code='01', libelle='Atelier')
                workshops.append(model('AffectationRessource').create(
                    atelier_id=workshop.pk, materiel_id=machine.pk, date_debut=date(2026, 1, 1)))
                resources.append(model('RessourceAffectee').create(
                    projet_id=project.pk, categorie_charge_id=category.pk, objet_id=machine.pk,
                    designation='Snapshot conservé', unite='heure', tarif=123,
                    date_debut=date(2026, 1, 1), atelier_id=workshop.pk,
                ))
                report = model('RapportJournalier').create(projet_id=project.pk, date=date(2026, 1, 1))
                expense_ids.append(model('DepenseRapportJournalier').create(
                    rapport_id=report.pk, categorie_charge_id=category.pk,
                    categorie='MATERIEL', designation='Charge historique', prix_unitaire=91).pk)
                readings.append(model('ReleveMateriel').create(
                    rapport_id=report.pk, materiel_id=machine.pk, etat='MARCHE', heures=5).pk)
                situation = model('SituationMensuelle').create(projet_id=project.pk, annee=2026, mois=1)
                monthly_expense_ids.append(model('DepenseSituationMensuelle').create(
                    situation_id=situation.pk, categorie_charge_id=category.pk,
                    categorie='MATERIEL', designation='Charge mensuelle').pk)
            for name, code in (
                ('Personnel', 'PERSONNEL'), ('Location', 'LOCATION'), ('Transport', 'TRANSPORT'),
                ('SousTraitance', 'SOUS_TRAITANCE'), ('Consommable', 'CONSOMMABLE'), ('Fourniture', 'FOURNITURE'),
            ):
                field = 'nom' if name == 'Personnel' else 'designation'
                source = model(name).create(**{field: name + ' partagé'})
                resource_category = model('CategorieCharge').get(code=code)
                for project in projects:
                    assigned = model('RessourceAffectee').create(
                        projet_id=project.pk, categorie_charge_id=resource_category.pk, objet_id=source.pk,
                        designation='Snapshot ' + name, date_debut=date(2026, 1, 1))
                    other_resources.append((name, assigned.pk, project.dossier_id))
            unowned_project = model('Projet').create(nom='À classer', numero='ORPHELIN')
            unowned_assignment = model('RessourceAffectee').create(
                projet_id=unowned_project.pk, categorie_charge_id=category.pk, objet_id=machine.pk,
                designation='Snapshot sans dossier', date_debut=date(2026, 1, 1))
            content_type = model('ContentType', 'contenttypes')
            machine_type = content_type.create(app_label='projets', model='materiel')
            project_type = content_type.create(app_label='projets', model='projet')
            wrapper = model('GResource', 'goplan').create(
                nom='Planning machine', content_type_id=machine_type.pk, object_id=machine.pk)
            assignment_ids = []
            for project in projects:
                plan = model('GPlan', 'goplan').create(
                    nom=project.nom, date_debut=date(2026, 1, 1),
                    content_type_id=project_type.pk, object_id=project.pk)
                task = model('GTask', 'goplan').create(plan_id=plan.pk, nom='Tâche')
                assignment_ids.append(model('GTaskAssignment', 'goplan').create(
                    tache_id=task.pk, ressource_id=wrapper.pk).pk)

            executor = MigrationExecutor(connection)
            target = [('projets', '0088_catalogues_dossier')]
            output = StringIO()
            with redirect_stdout(output):
                executor.migrate(target)
            apps = executor.loader.project_state(target).apps
            seen = set()
            for index, dossier in enumerate((alpha, beta)):
                resource = model('RessourceAffectee').get(pk=resources[index].pk)
                scoped_machine = model('Materiel').get(pk=resource.objet_id)
                self.assertEqual(scoped_machine.dossier_id, dossier.pk)
                self.assertEqual(model('CategorieCharge').get(pk=resource.categorie_charge_id).dossier_id, dossier.pk)
                self.assertEqual(model('CategorieCharge').get(pk=resource.categorie_charge_id).nom, 'Libellé historique')
                self.assertEqual((resource.designation, resource.unite, resource.tarif),
                                 ('Snapshot conservé', 'heure', 123))
                self.assertEqual(model('AffectationRessource').get(pk=workshops[index].pk).materiel_id, scoped_machine.pk)
                self.assertEqual(model('ReleveMateriel').get(pk=readings[index]).materiel_id, scoped_machine.pk)
                self.assertEqual(model('DepenseRapportJournalier').get(pk=expense_ids[index]).categorie_charge_id,
                                 resource.categorie_charge_id)
                self.assertEqual(model('DepenseSituationMensuelle').get(pk=monthly_expense_ids[index]).categorie_charge_id,
                                 resource.categorie_charge_id)
                project = model('Projet').get(pk=projects[index].pk)
                self.assertEqual(model('Entreprise').get(pk=project.entreprise_id).dossier_id, dossier.pk)
                assignment = model('GTaskAssignment', 'goplan').get(pk=assignment_ids[index])
                self.assertEqual(model('GResource', 'goplan').get(pk=assignment.ressource_id).object_id, scoped_machine.pk)
                seen.add(scoped_machine.pk)
            self.assertEqual(len(seen), 2)
            for name, assignment_id, dossier_id in other_resources:
                assigned = model('RessourceAffectee').get(pk=assignment_id)
                self.assertEqual(model(name).get(pk=assigned.objet_id).dossier_id, dossier_id)
            self.assertIsNone(model('Materiel').get(pk=machine.pk).dossier_id)
            self.assertEqual(model('RessourceAffectee').get(pk=unowned_assignment.pk).objet_id, machine.pk)
            self.assertIsNone(model('Materiel').get(pk=orphan.pk).dossier_id)
            self.assertEqual(model('Materiel').filter(designation='Sans usage').count(), 1)
            self.assertIn('Materiel', output.getvalue())
            self.assertEqual(model('CategorieCharge').filter(dossier_id=alpha.pk).count(), 7)
            self.assertTrue(model('CategorieCharge').filter(dossier__isnull=True, code='MATERIEL').exists())
        finally:
            connection.close()
            connections[alias] = original_connection
