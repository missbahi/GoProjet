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

### Suivi d'exécution

La liste et le formulaire d'ajout utilisent les composants et couleurs du thème.
Les actions restent opérationnelles après les swaps HTMX, sans réinitialisation
des scripts. L'enregistrement actualise l'historique et ferme le formulaire.
Les pièces jointes sont sélectionnées au bas du formulaire d'ajout, sans
glisser-déposer, en une ou plusieurs sélections. Chaque fichier peut être
remplacé ou retiré avant l'envoi ; la limite est de 10 Mo par fichier.
Les fichiers sont envoyés avec le suivi au moment de l'enregistrement.
Si le stockage échoue après la création du suivi, l'erreur indique les fichiers
déjà enregistrés et propose la gestion des fichiers sans recréer le suivi.
Les erreurs de validation et de réseau restent visibles dans le formulaire.
La modification ouvre un formulaire prérempli dans la même page, chargé à la
demande par HTMX et réutilisant les champs de l'ajout. Annuler ferme ce panneau
sans navigation ; enregistrer actualise l'historique sans toucher aux fichiers
joints. L'accès direct à la page de modification reste disponible.

### Situations mensuelles

Les cartes des situations mensuelles affichent le résultat (produits moins
charges) et son pourcentage des produits, en vert pour un bénéfice, rouge pour
une perte et neutre à zéro. Le pourcentage est non calculable si les produits
sont nuls.

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

### Messages d'action

Les pages classiques, les réponses HTMX et AJAX, ainsi que les modales utilisent
le même composant toast. Les messages Django sont transmis par l'en-tête
`X-App-Messages` lors des requêtes asynchrones ; les redirections conservent
leurs messages jusqu'à la page de destination. Les réponses JSON d'action
peuvent fournir `message` ou `error`. Les erreurs de champs (`errors`) restent
traitées dans les formulaires, dont les alertes persistantes sont conservées.
Les toasts sont dédupliqués tant qu'ils sont visibles, limités à cinq et
affichés dans le dialogue ouvert pour rester accessibles au-dessus des modales.
Les templates actifs utilisent un rendu commun des messages d'action :
succès et informations ne créent plus de bandeaux permanents, tandis que les
erreurs et avertissements restent visibles sans fermeture automatique.
Les vues peuvent conserver `messages.success()` avec redirection ; le message
est consommé à destination et ne revient pas au prochain chargement.
Les pages autonomes actives partagent aussi ces assets ; les sauvegardes de
templates et les aperçus d'impression ne sont pas modifiés.

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
