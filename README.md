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
