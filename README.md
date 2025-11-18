![Django](https://img.shields.io/badge/Django-5.2.5-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)


GoProjet

Application Django de gestion de projets avec bordereaux de prix interactifs.

## 🚀 Fonctionnalités

- Gestion hiérarchique des projets et lots
- Bordereaux de prix avec Handsontable (tableaux interactifs)
- Interface moderne avec design glassmorphism
- Export Excel et PDF
- Système de hiérarchie des lignes de prix (indentation/désindentation)
- Gestion des décomptes et attachements
- Workflow de validation multi-étapes
- Suivi d'exécution des projets
- Gestion des ordres de service
- Système de notifications

## 🛠️ Technologies

- **Backend** : Django 5.2.5
- **Frontend** : HTML, CSS, JavaScript, Handsontable
- **Styling** : Tailwind CSS, Glassmorphism design
- **Base de données** : SQLite (développement)
- **Export** : Excel (xlsx), PDF (jsPDF)

## 📦 Installation

\`\`\`bash
# Cloner le projet
git clone https://github.com/missbahi/GoProjet.git
cd GoProjet

# Installer les dépendances
pip install -r requirements.txt

# Appliquer les migrations
python manage.py migrate

# Créer un superutilisateur
python manage.py createsuperuser

# Lancer le serveur de développement
python manage.py runserver
\`\`\`

Accédez à http://localhost:8000

## 📁 Structure du projet

\`\`\`
GoProjet/
├── goProjet/          # Configuration du projet Django
├── projets/           # Application principale
│   ├── models.py      # Modèles : Projet, Lot, LigneBordereau, Décompte, etc.
│   ├── views.py       # Vues et logique métier
│   ├── static/        # CSS, JS, images
│   ├── templates/     # Templates HTML
│   └── templatetags/  # Filtres personnalisés
├── manage.py
└── requirements.txt
\`\`\`

## 🎯 Utilisation

1. **Créer un projet** via l'interface administrateur
2. **Ajouter des lots** au projet
3. **Saisir les bordereaux de prix** avec le système hiérarchique
4. **Gérer les décomptes** et les attachements
5. **Suivre l'exécution** des travaux

## 👤 Auteur

**missbahi** - Développement Django full-stack

## 📄 Licence

Ce projet est sous licence MIT.
" > README.md
