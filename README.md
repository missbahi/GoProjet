![Django](https://img.shields.io/badge/Django-5.2.5-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

# GoProjet

Application Django de gestion de projets de BTP pour bureaux d'études marocains.

## Fonctionnalités

- Projets, lots, documents administratifs et ordres de service
- Bordereaux de prix hiérarchiques (Handsontable), décomptes et attachements
- Suivi d'exécution, situations mensuelles, planning des ateliers, ressources
- Workflow de validation, utilisateurs, notifications
- Export Excel et PDF
- **GoPlan** : plannings, diagramme de Gantt, import/export XML MS Project et
  impression A4 à A0 — voir [goplan/README.md](goplan/README.md)

La version et les nouveautés affichées à la connexion sont définies dans
[projets/version.py](projets/version.py).

### Avenants de délai des ordres de service

Après notification de l'OS de commencement, le type **OSVD — OS d'avenant de
délai** permet de saisir une durée supplémentaire entière en jours ou en mois
calendaires et son motif. La durée positive, le motif et la date d'effet sont
obligatoires pour notifier l'OS. Les brouillons et les OS annulés n'allongent
pas le délai ; les OS notifiés sont pris en compte à partir de leur date d'effet.
Le délai initial du marché est conservé, et les arrêts/reprises gardent leur
calcul actuel.

Le motif `CIRCULAIRE_09_2022` plafonne les prolongations cumulées du marché à
**six mois calendaires**, jamais à un forfait de 180 jours. Les quantités en
mois et en jours relevant de la circulaire sont cumulées séparément, puis
comparées à six mois depuis l'échéance contractuelle précédant le premier avenant
de ce motif (prolongations antérieures incluses, arrêts exclus). Cette référence
reste fixe pour ne pas renouveler le plafond à chaque notification. Les autres motifs ne
consomment pas ce plafond. Un mois ajouté conserve le jour si possible, sinon
utilise le dernier jour du mois ; aucune journée n'est soustraite à l'extension.
L'annulation d'un avenant retire sa contribution sans modifier le délai initial.

Après mise à jour, exécuter `python manage.py migrate` pour créer les champs et
le nouveau type d'OS.

## Technologies

Django 5.2.5 · HTML/CSS/JavaScript · Handsontable · Tailwind CSS ·
SQLite (développement) / PostgreSQL (production)

## Installation

```bash
git clone https://github.com/missbahi/GoProjet.git
cd GoProjet
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Accédez à http://localhost:8000

## Structure

```text
goProjet/   Configuration Django
projets/    Application principale
goplan/     Plannings et Gantt
manage.py
requirements.txt
```

## Tests

```bash
python manage.py test
node --test goplan/tests/
```

## Auteur et licence

**missbahi** — projet sous licence MIT.
