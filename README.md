# GoProjet

Application web Django de gestion et de suivi de projets de BTP. GoProjet centralise les donnees administratives, financieres et operationnelles des projets pour les bureaux d'etudes et equipes de chantier.

## Fonctionnalites

- Gestion des dossiers, projets, utilisateurs et droits d'acces.
- Referentiels metier : clients, ingenieurs, personnel, materiel, transport, locations, sous-traitance, fournitures et consommables.
- Lots et bordereaux de prix avec saisie structuree et export Excel.
- Attachements, decomptes, calcul des retards et processus de validation a plusieurs etapes.
- Ordres de service, notifications et suivi des echeances.
- Suivi d'execution avec rapports journaliers, depenses, stocks et pieces jointes.
- Situations mensuelles comprenant :
  - chiffre d'affaires detaille par travaux realises, revision des prix et refacturation externe ;
  - charges par categorie, avec montant, cession entrante, cession sortante et total ;
  - etat des stocks et documents associes ;
  - apercu imprimable en mode resume ou detaille.
- Gestion securisee des documents et telechargements proteges.
- Interface responsive et Progressive Web App (PWA).

## Stack technique

| Domaine | Technologies |
| --- | --- |
| Backend | Python, Django 5.2 |
| Base de donnees | SQLite en developpement, PostgreSQL en production |
| Serveur de production | Gunicorn, WhiteNoise |
| Exports | OpenPyXL, Pandas |
| Stockage documentaire | Systeme de fichiers local ou Cloudflare R2 compatible S3 |
| Deploiement | Railway via Nixpacks |

## Prerequis

- Python 3.10 ou version ulterieure
- `pip`
- PostgreSQL pour un environnement de production

## Installation locale

```bash
git clone https://github.com/missbahi/GoProjet.git
cd GoProjet

python -m venv venv
```

Sous Windows :

```powershell
.\venv\Scripts\Activate.ps1
```

Sous macOS ou Linux :

```bash
source venv/bin/activate
```

Installez ensuite les dependances et preparez la base locale :

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

L'application est alors disponible a l'adresse `http://127.0.0.1:8000/`.

## Configuration

La configuration est lue, dans l'ordre, depuis `.env.local` puis `.env`. Ne versionnez jamais ces fichiers lorsqu'ils contiennent des secrets.

Exemple minimal pour le developpement :

```env
SECRET_KEY=changez-cette-cle-en-developpement
DEBUG=True
PWA_ENABLED=True
```

En production, renseignez au minimum :

```env
SECRET_KEY=une-cle-secrete-robuste
DEBUG=False
DATABASE_URL=postgresql://utilisateur:motdepasse@hote:5432/base
```

### Stockage des documents avec Cloudflare R2

Le stockage R2 est activable avec `USE_R2_DOCUMENTS=true`. Ajoutez les variables suivantes dans l'environnement de deploiement :

```env
USE_R2_DOCUMENTS=true
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_BUCKET_NAME=...
R2_ENDPOINT_URL=https://<compte>.r2.cloudflarestorage.com
R2_REGION=auto
```

Les alias `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME` et `AWS_S3_ENDPOINT_URL` sont egalement pris en charge.

## Tests et controles

Executez la suite de tests Django :

```bash
python manage.py test
```

Verifiez la configuration du projet :

```bash
python manage.py check
```

## Deploiement Railway

Le fichier `railway.json` utilise Nixpacks et lance `start.sh`, qui applique les migrations, collecte les fichiers statiques et demarre Gunicorn :

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
gunicorn goProjet.wsgi:application
```

Pour deployer :

1. Connectez le depot GitHub au projet Railway.
2. Ajoutez une base PostgreSQL et renseignez `DATABASE_URL`.
3. Definissez `DEBUG=False` et une `SECRET_KEY` robuste.
4. Configurez eventuellement les variables R2 pour les documents.
5. Poussez une revision sur la branche suivie par Railway.

## Structure du projet

```text
goProjet/
├── goProjet/                    # Configuration Django (settings, URLs, WSGI/ASGI)
├── projets/
│   ├── models/                  # Modeles metier
│   ├── views/                   # Vues par domaine fonctionnel
│   ├── templates/               # Templates Django
│   ├── services/                # Services metier
│   ├── migrations/              # Historique du schema de donnees
│   └── tests.py                 # Tests de regression
├── manage.py
├── requirements.txt
├── railway.json
└── start.sh
```

## Licence

Ce depot est fourni sous licence MIT.
