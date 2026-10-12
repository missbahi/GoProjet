![Django](https://img.shields.io/badge/Django-5.2.5-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)


GoProjet

Application Django pour bureaux d'études marocains de gestion complète de projets de BTP.

## 🚀 Fonctionnalités

- Gestion des projets avec documents administratifs
- Bordereaux de prix avec Handsontable (tableaux interactifs)
- Interface moderne avec design glassmorphism
- Export Excel et PDF
- Système de hiérarchie des lignes de prix (indentation/désindentation)
- Gestion des décomptes et attachements
- Workflow de validation multi-étapes
- Suivi d'exécution des projets
- Gestion des ordres de service avec la logique de succession 
- Système de notifications

### Navigation vers les notifications

Depuis une page affichant `{% breadcrumb %}`, les liens de la cloche
transmettent le fil d'Ariane courant via le paramètre signé `breadcrumb`.
La page Notifications reprend cette navigation et rend la page appelante
cliquable, avec ses paramètres de requête. Le contexte est conservé lors
des filtres, de la pagination et des rechargements, y compris avec HTMX.
Sans fil d'Ariane sur la page appelante, « Tableau de bord › Notifications »
est affiché, avec un lien vers Home sur « Tableau de bord ».
Un paramètre signé altéré est rejeté avec une réponse HTTP 400.
La liste des tâches fournit « Home › Taches » en accès direct et avec HTMX.
La cloche et son menu relisent le nombre exact de notifications non lues
après navigation HTMX, retour dans l'historique et modification des notifications,
ainsi qu'à l'ouverture du menu. Aucun polling permanent n'est ajouté.

### Tableau de bord Home

Le graphique charge ses dépendances à la demande, y compris lorsque Home est
ouvert par HTMX depuis un autre module. Les anciennes instances et leurs
écouteurs sont nettoyés ; le graphique est reconstruit après restauration
de l'historique. Les états vides et erreurs de chargement sont affichés.
Ces actualisations ne nécessitent pas de rechargement global.

### Planning des ateliers

La soumission des modales identifie les formulaires par sélecteur DOM :
les champs cachés nommés `id` ne doivent pas masquer leur identification.

Les styles et scripts des ateliers sont aussi chargés par le chargeur central
HTMX de la famille projet. Le menu contextuel permet de modifier ou supprimer
un atelier ou une affectation, et d'affecter du matériel à l'atelier sélectionné.
Le repli des lignes est conservé après filtrage et navigation HTMX.
L'aperçu avant impression s'ouvre dans un nouvel onglet avec les filtres courants,
y compris sans JavaScript.
Les erreurs de modification d'affectation (validation, conflit de matériel,
réseau ou réponse HTTP) restent visibles dans la modale, sans dépendre des
notifications temporaires. Le matériel sélectionné est transmis par son ID.

### Liste des décomptes

Les cartes, les montants de synthèse et les badges de la liste utilisent les
styles communs du projet, adaptés aux thèmes clair et sombre. Les statuts
payé, validé, émis/partiel, en retard et brouillon utilisent respectivement
les badges succès, information, avertissement, danger et neutre.

### Gestion des utilisateurs

La liste affiche « Home › Utilisateurs ». L'ajout, la modification et
l'affectation des projets se font dans une modale unique, chargée à la demande
par HTMX et vidée à la fermeture. Aucun formulaire n'est préchargé par ligne.
Les erreurs de validation restent dans la modale ; après enregistrement,
seule la liste est actualisée, en conservant les filtres et la page courante.
Les pages classiques restent accessibles par leurs URL sans JavaScript.
Les autorisations existantes sont conservées et les projets hors du périmètre
du gestionnaire ne sont pas retirés lors de l'enregistrement.

## 🛠️ Technologies

- **Backend** : Django 5.2.5
- **Frontend** : HTML, CSS, JavaScript, Handsontable
- **Styling** : Tailwind CSS, Glassmorphism design
- **Base de données** : SQLite (développement) PostegreSQL (production)
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
