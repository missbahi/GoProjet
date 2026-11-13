![Django](https://img.shields.io/badge/Django-5.2.5-green)
![Python](https://img.shields.io/badge/Python-3.8+-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

# GoProjet

Application Django de gestion de projets de BTP pour bureaux d'études marocains.

## Fonctionnalités

- Projets, lots, documents administratifs et ordres de service
- Bordereaux de prix hiérarchiques, décomptes et attachements
  En édition du bordereau, le bouton plein écran agrandit la page entière et masque
  l'en-tête et la navigation. La barre d'outils et le total restent visibles pendant
  le défilement du tableau. Échap rétablit l'affichage normal.
  Le formulaire d'attachement reprend les boutons à icônes du bordereau, la somme
  sélectionnée à droite et le total séparé du formulaire. Son mode plein écran
  garde les actions et le total visibles pendant le défilement.
  Les champs d'identification, dates et observations ainsi que le titre du tableau
  sont masqués en plein écran ; ils réapparaissent à la sortie, sans perdre la saisie.
- Suivi d'exécution, situations mensuelles, planning des ateliers, ressources
- Workflow de validation, utilisateurs, notifications
- Export Excel et PDF
- **GoPlan** : plannings, diagramme de Gantt, import/export XML MS Project et
  impression A4 à A0 — voir [goplan/README.md](goplan/README.md)
  Le bouton « Plein écran » des vues inline et Gantt agrandit l'espace de travail
  en gardant la barre d'outils accessible. Cliquez à nouveau ou appuyez sur Échap
  pour revenir à l'affichage normal, sans perdre la saisie en cours.

La version et les nouveautés affichées à la connexion sont définies dans
[projets/version.py](projets/version.py).

### Rôle Observateur

- Le superutilisateur ou le chef de projet/gérant peut créer un **Observateur**
  et l'affecter aux dossiers qu'il est autorisé à gérer, depuis **Utilisateurs**.
  Le rôle est également disponible lors de la modification d'un utilisateur.
- Après connexion, l'Observateur arrive sur **Home**, même si une autre page
  était demandée. Il consulte uniquement les projets des dossiers auxquels il
  est affecté ; une affectation directe à un projet ne suffit pas.
- Les données, documents, attachements, décomptes, CA, OS, suivis et plannings
  rattachés à ces projets sont consultables. Téléchargements, exports et
  impressions restent disponibles. Les tâches GoPlan sont présentées dans
  leur aperçu tabulaire ; le Gantt et le bordereau sont en lecture seule.
- Les créations, modifications, suppressions, validations, paiements et accès
  à l'administration sont refusés côté serveur, y compris par URL directe.
  Les nouvelles routes sont refusées par défaut et doivent être explicitement
  ajoutées à la politique de consultation dans `projets/observer_access.py`.
  Les plannings sans projet rattaché et les référentiels globaux ne sont pas
  accessibles.
- Le thème, les préférences d'affichage, le mot de passe, la session et la lecture
  des notifications restent personnels : leur modification ne change aucune donnée du dossier.
  Les notifications affichées sont limitées aux projets autorisés.
- Un superutilisateur conserve ses privilèges, quel que soit son rôle de profil.
  Pour un compte Observateur ordinaire, même un ancien indicateur staff ne
  contourne pas la lecture seule.
- Déploiement : exécuter `python manage.py migrate` pour la migration
  `0085_profile_observateur`, puis la collecte des fichiers statiques habituelle.

### CA mensuel de production (Travaux)

Depuis les situations mensuelles, **Chiffres d'affaires** ouvre le suivi du CA.
Les modèles `ChiffreAffaire` et `LigneChiffreAffaire` sont créés par la migration
`0084_chiffre_affaire_mensuel` : exécuter `python manage.py migrate`.
Aucune donnée historique n'est convertie ou modifiée par cette migration.

- Un CA par projet et mois calendaire complet, indépendamment des OSA/OSR.
  Les mois sont consécutifs ; le précédent doit être validé avant le suivant.
- TableView autorise seulement les quantités cumulées (trois décimales).
  Le tableau reprend le style du Bordereau (fond clair, en-têtes, bordures et
  montants), avec une feuille de styles partagée limitée aux tableaux.
  Les lignes parentes restent sans fond spécifique ni bordures ; les toggles
  natifs TableView, identiques à ceux du Bordereau, masquent
  ou affichent leurs descendants uniquement à l'écran, sans sauvegarde.
  Le bouton global reprend aussi les icônes développer/réduire du Bordereau.
  Les désignations restent sur une seule ligne et les montants sont verts.
  Les quantités invalides ou supérieures au marché sont signalées en rouge
  (le dépassement seul reste un avertissement), les cumuls diminués en orange.
  L'en-tête
  du formulaire utilise les couleurs du thème clair ou sombre.
  Le formulaire est compact, avec observations sur une ligne et aide dans une
  modale ouverte par le bouton d'information. Les actions enregistrer/valider/
  dévalider utilisent des icônes dans la barre du tableau ; seul le total mensuel
  reste sous le tableau.
  Valider est désactivé pour un CA déjà validé. Enregistrer est désactivé sur
  un CA enregistré sans changement ; revenir aux valeurs initiales le désactive
  à nouveau. Le pliage et la sélection ne modifient pas cet état.
  L'encadré de somme partage les styles du Bordereau, à droite de cette barre.
  Il affiche somme, moyenne et nombre de cellules numériques
  lorsque plus d'une cellule numérique est sélectionnée :
  Ctrl permet des sélections disjointes, Maj une plage. Les titres et textes
  sont exclus ; les zéros et régularisations négatives sont inclus.
  Quantité du mois = cumul N moins cumul N-1 ; le montant HT utilise les prix
  figés des lignes, avec arrondi du total au centime (demi supérieur).
  Les lignes d'un CA enregistré sont figées ; les nouvelles lignes du bordereau
  sont intégrées à la création du mois suivant.
  Le changement d'année ne remet pas les cumuls à zéro.
- Le premier CA peut partir de zéro ou d'une **Reprise** : renseigner alors le
  cumul initial à la fin du mois précédent. Un ancien montant financier ne
  permet pas de reconstituer automatiquement ces quantités.
  La colonne Cumul initial est visible uniquement sur le premier CA en mode
  Reprise, y compris en consultation. Elle suit immédiatement le changement
  d'origine, sans effacer les quantités saisies.
- Les régularisations négatives sont permises avec observations.
  Toute sauvegarde/validation depuis le formulaire impose une vérification serveur
  puis une confirmation simple, sans rapport en bas de page. La confirmation reste
  signée et invalidée si les données changent. Les erreurs ramènent le défilement
  vers le message en haut du formulaire.
- Le superutilisateur et le chef de projet/gérant autorisé peuvent gérer et
  valider les CA ; les autres membres consultent en lecture seule.
- La liste propose les icônes Modifier/Consulter, Valider, Dévalider et
  Supprimer, avec confirmation simple comme les Situations. La validation
  depuis la liste utilise les quantités déjà enregistrées et avertit du
  remplacement des recettes Travaux réalisés ; les protections métier restent
  appliquées. Seul le dernier CA en brouillon sans situation liée est supprimable.
  Les modifications de quantités dans le formulaire gardent leur vérification signée.
- La validation alimente uniquement **Travaux réalisés** de la situation du
  même mois. Révision des prix et refacturation restent indépendantes.
  La confirmation avertit de la mise à jour des situations concernées.
  Une situation créée ensuite reprend automatiquement son CA validé.
- Corriger un cumul recalcule ce mois et le mois suivant en brouillon.
  Une situation validée concernée doit d'abord être dévalidée. Un CA suivant
  validé bloque les corrections de cumuls : dévalider les CA depuis le dernier
  mois en remontant jusqu'au successeur à corriger, puis revalider dans l'ordre.
  Seul le dernier CA peut être dévalidé. Une situation liée à un CA dévalidé
  conserve sa source mais ne peut pas être validée avant celui-ci.

Le CA de production est indépendant des attachements et des décomptes
contractuels. Les situations historiques sans CA conservent leur saisie manuelle.

### Indicateurs de la page Home

Le tableau de bord individuel affiche le marché TTC, le CA cumulé TTC du dernier
CA (brouillons signalés), et le ratio cumul TTC / marché TTC. Sans CA, il utilise
le dernier attachement validé. Les périodes futures sont exclues. Le TTC applique
le taux de TVA actuel de chaque lot, y compris les lots exonérés ; ce montant de
pilotage ne remplace pas un décompte fiscal. Sans source ou marché positif, les
indicateurs correspondants sont indiqués comme non disponibles.

Sous le slogan « Vos projets, une vision claire. », la Home est centrée sur
l'exécution des travaux : projets en cours, CA annuel, production CA cumulée
et attachements validés. Les encadrés Appels d'offres et Réceptions validées
ne sont plus affichés ; les données et fonctionnalités métier restent conservées.

La Home calcule ses indicateurs en lecture seule sur les projets accessibles.
L'avancement de production est le cumul HT des quantités du dernier CA
(brouillons inclus et signalés), divisé par le total HT du bordereau actuel.
En absence de CA, le dernier attachement validé est utilisé. Les autres statuts
d'attachement ne servent pas de repli. Aucun CA ni attachement futur n'est retenu
(le mois courant du CA est inclus).

Le CA annuel additionne uniquement les montants mensuels des CA de l'année,
avec la part en brouillon affichée séparément. La production CA cumulée utilise
uniquement le dernier cumul de chaque projet, reprise initiale comprise.
Les attachements validés présentent également le dernier cumul de chaque
projet : ces deux indicateurs ne doivent pas être additionnés.
Les recettes manuelles des anciennes situations ne sont pas assimilées à des CA.

Tableau, moyenne des projets en cours et graphique utilisent le même calcul.
Les projets sans source ou sans bordereau HT positif affichent « Non disponible »
et ne sont pas inclus dans la moyenne. Les dépassements de 100 % restent visibles
en chiffres et dans le graphique ; seules les barres de progression sont bornées.
Les séries fictives ont été supprimées. Les échéances à venir sont limitées
aux tâches non terminées des projets accessibles.

### Menu contextuel du bordereau des prix

Le bordereau utilise TableView sur les données du lot. Le gestionnaire ne prend
plus en charge Handsontable ni le paramètre de choix du renderer.
L'ancien template `saisie_bordereau_.html` est conservé comme archive, mais n'est
plus compatible avec le gestionnaire actuel. Handsontable reste utilisé dans
les formulaires d'attachements ; ses ressources ne sont pas supprimées.

### Essai TableView pour les attachements

Lors de la modification d'un attachement existant, la continuité de sa date
de début est contrôlée au passage au statut Transmis, et non à chaque sauvegarde.
Le formulaire affiche l'attachement précédent avec sa période et un lien de
consultation. Les contrôles à la création, l'ordre début/fin et le verrouillage
des périodes ayant un successeur restent inchangés.

À la transmission, la date de fin ne peut pas tomber dans un arrêt notifié :
la date d'effet de l'OSA est incluse, celle de l'OSR est exclue.
Le message propose la veille de l'OSA ou le jour de la reprise ; sans OSR
notifié, seule la veille de l'arrêt est proposée. Les OS non notifiés ou sans
date d'effet sont ignorés. Ce contrôle s'applique aussi aux aperçus et aux
confirmations des corrections exceptionnelles et des périodes historiques.
La sauvegarde en brouillon reste possible ; aucune date n'est corrigée
automatiquement et la continuité avec l'attachement suivant reste inchangée.

Pour régulariser les anciennes périodes déjà validées, un superutilisateur ou
un gérant/chef de projet ayant accès au projet peut
ouvrir **Corriger les périodes historiques** depuis la liste des attachements
ou le formulaire. Cette action dédiée affiche toute la chaîne et impose un
motif, un aperçu puis une confirmation. Elle vérifie la continuité depuis l'OS
de commencement et refuse une confirmation si les données ont changé depuis
l'ouverture (session valable une heure). L'ordre est déduit des nouvelles dates
saisies, même si les anciennes séquences ou les liens précédents sont erronés.
L'aperçu présente l'ancien et le nouvel ordre avec les identifiants stables.
La confirmation reconstruit les séquences de 1 à N, les liens précédents et les
numéros DP01, DP02… ; les chevauchements et les trous de périodes sont refusés.
Les cumuls des lignes restent inchangés. Les situations sont recalculées à partir
du cumul du nouveau prédécesseur et les décomptes concernés sont recalculés avec
leurs taux et retenues existants. Un décompte payé, partiellement payé ou portant
une date de paiement bloque une correction qui le concerne.
Les statuts et validations sont conservés. Les changements de lignes, décomptes
ou OS depuis l'ouverture invalident également la confirmation.
Chaque opération est journalisée avec auteur, date, motif, anciennes/nouvelles
périodes, numéros, séquences, prédécesseurs et impacts financiers ; l'historique
est visible sur la même page. Les documents déjà émis ne sont pas régénérés automatiquement ;
l'incidence des nouvelles périodes sur les calculs dérivés doit être examinée.
Exécuter `python manage.py migrate` pour créer ce journal.

#### Validation simplifiée des dossiers Travaux

Pour les projets rattachés à un dossier d'activité **Travaux**, le superutilisateur
ou le chef de projet/gérant autorisé sur le projet peut valider les attachements
et décomptes directement : bouton **Valider**, ou statut **Validé** puis
enregistrement. La validation d'un attachement sauvegarde également les lignes
saisies et contrôle la continuité, les dates et les arrêts OSA/OSR.
La liste des attachements propose également **Valider** sans ouvrir le formulaire,
avec les mêmes contrôles de période. Les actions **Valider** et **Dévalider**
demandent confirmation en indiquant le numéro de l'attachement ; annuler ne
modifie rien. Le bouton **Dévalider** remet l'attachement
en brouillon et réinitialise ses étapes de validation. Il est accessible aux
utilisateurs autorisés à rouvrir l'attachement, ainsi qu'aux chefs de projet
autorisés à le valider directement. Une notification confirme le résultat dans
la liste ; les notifications habituelles du projet sont conservées.
Les attachements déjà validés conservent le mode de correction exceptionnelle.
Les décomptes payés ou partiellement payés ne peuvent pas être reclassés en Validé.

Le workflow multiétapes n'est pas initialisé pour les dossiers Travaux.
Ses anciennes étapes sont conservées comme historique mais ne pilotent plus
le statut de l'attachement. Les projets sans dossier, Fournitures et Services
gardent leur fonctionnement antérieur.

#### Suppression d'un décompte

La suppression d'un décompte ouvre une page de confirmation, puis s'effectue
uniquement par POST avec protection CSRF et contrôle d'accès au projet.
Après suppression, l'utilisateur revient à la liste des décomptes.
Un avertissement spécifique signale les décomptes payés, partiellement payés ou
portant une date de paiement : supprimer cet enregistrement n'annule aucun
paiement réel. L'attachement et ses validations sont conservés.

#### Correction exceptionnelle d'un attachement

Le superutilisateur et le gérant/chef de projet autorisé sur le projet peuvent
ouvrir directement **Modifier** sur un attachement signé ou validé.
Le formulaire passe automatiquement en **correction exceptionnelle** ;
le lien **Correction exceptionnelle** (`?correction=1`) permet également
d'activer ce mode pour les autres statuts.

Dates, observations, fichier joint et cumuls sont modifiables sans rouvrir
le workflow : statuts et validations sont conservés. Les prix et autres
instantanés des lignes existantes sont conservés. **Vérifier la correction**
affiche les changements et l'incidence sur les situations et décomptes.
Seul **Confirmer la correction** enregistre, dans une transaction.
L'aperçu expire après 30 minutes et devient caduc si les données changent.
Une correction du cumul recalcule la situation courante et celle du successeur
direct, ainsi que leurs décomptes ; les cumuls suivants restent inchangés.
Les modifications financières ou de période sont bloquées si un décompte
concerné est payé, partiellement payé ou porte une date de paiement.
Une correction d'observations ou de fichier seule reste possible.
Un cumul entièrement nul est accepté dans ce mode.

Les périodes doivent rester continues avec les voisines : pour déplacer une
frontière entre plusieurs attachements, utiliser l'écran des périodes
historiques. Aucun motif ni journal supplémentaire n'est imposé pour cette
édition complète ; le journal de l'écran historique reste distinct.
Les documents déjà émis ne sont pas régénérés automatiquement.

Pour les essais approfondis, les vues de création et de modification chargent
directement `attachement_form.html`, qui utilise
`_attachement_form_content_test.html` sans paramètre d'URL.
L'enveloppe `attachement_form.html` conserve les deux moteurs, avec TableView
via `?tableview=1` et Handsontable sinon, mais n'est plus utilisée par ces vues.
Le mode d'essai charge uniquement TableView ; les champs, les actions et le format envoyé au
serveur sont partagés avec le formulaire habituel. **Les enregistrements et
les suppressions sont réels**, il est donc conseillé d'utiliser un projet de test.

Seul le nouveau cumul des lignes de travaux est modifiable. Le tableau conserve
les montants, le total, la sélection multiple, sa somme et sa moyenne, le
copier-coller et le repérage des cellules modifiées. Les valeurs négatives,
non numériques ou dépassant trois décimales sont refusées ; le collage ne peut
pas créer de lignes. La dernière cellule éditée est validée avant soumission.
Comme le formulaire habituel, cette variante exige au moins une quantité
strictement positive pour enregistrer. Les largeurs sont redimensionnables,
mais ne sont pas persistées ; le redimensionnement individuel des lignes de
Handsontable n'est pas reproduit.

Sur une cellule TableView sélectionnée, taper un caractère commence directement
la saisie en remplaçant son contenu. Entrée, F2 et le double-clic conservent
l'ouverture de l'éditeur avec la valeur actuelle ; les raccourcis Ctrl/Cmd
restent disponibles. Dans l'essai d'attachement, le marquage compare les quantités
numériquement à leur valeur au chargement : `0` et `0.000` sont équivalents, et
revenir à la valeur initiale retire le marquage, y compris après un collage.

Le clic droit ouvre les actions de la sélection ou cible la cellule cliquée :
insérer une ligne avant, supprimer, monter ou descendre d'un cran parmi les lignes
sœurs, indenter et désindenter. Les commandes, icônes et états désactivés sont
partagés avec la barre d'outils. L'insertion crée une sœur juste avant la ligne
courante, avec le même parent et le même niveau, sans écraser les lignes
existantes. Sans sélection, elle crée une ligne de la racine (`Root`).
Supprimer un groupe demande confirmation pour ses
sous-lignes. Le clic droit seul ne supprime rien.

En thème clair, les boutons disponibles de la barre d'outils utilisent l'accent
bleu, comme les icônes du thème sombre. Les boutons désactivés sont grisés et
atténués pour distinguer immédiatement les actions indisponibles.

Réduire ou développer les lignes conserve la position de lecture et le
défilement horizontal. Si la ligne affichée est masquée par la réduction,
la vue reste ancrée sur son premier parent encore visible.

L'état réduit/développé est partagé entre les utilisateurs et sauvegardé avec
le bouton **Enregistrer**. Réduire ou développer un groupe active ce bouton ;
sans enregistrement, ces changements sont perdus à la fermeture. Les nouvelles
lignes sont développées par défaut. Pendant la sauvegarde, le bouton affiche
uniquement une icône tournante.

Après mise à jour, exécuter `python manage.py migrate` pour ajouter le champ
de mémorisation de l'état des lignes.

Maj + clic sélectionne une plage rectangulaire : toutes ses cellules, y compris
les cellules intermédiaires, sont teintées et encadrées. La cellule active a un
cadre plus épais. Les cellules ne sont plus mises en évidence au survol.

Le menu se ferme avec Échap, un clic extérieur ou un défilement. Les flèches
haut/bas, Début/Fin et Entrée permettent de l'utiliser au clavier.

Une seule ligne vide est ajoutée automatiquement en fin de bordereau, à la
racine. Dès qu'elle contient une donnée, une nouvelle ligne vide prend le
relais. Le bouton **+**, à gauche du pied des totaux, ajoute une ligne vide
supplémentaire à la fin et y place le curseur. Les lignes vides ajoutées
volontairement sont conservées pendant l'édition.

### TableView et apparence du bordereau

Le bordereau utilise le composant générique `goProjet/static/projets/js/table-view.js`.
Les largeurs de colonnes se règlent directement en tirant le bord droit des
en-têtes ; leur bord inférieur permet de régler la hauteur des en-têtes.
Le dialogue d'apparence permet de personnaliser les couleurs et les dimensions.
Cliquer sur **Appliquer** enregistre les réglages et les dimensions courantes
pour le lot ; les redimensionnements seuls ne sont pas sauvegardés.

Le socle expose `getConfiguration()`, `applyConfiguration()` et
`TableView.mountConfiguration()` sans dépendance Django. Les colonnes numériques
acceptent `locale`, `decimals`, `useGrouping` et `hideZero`. `getValue` permet
les cellules calculées ; les hooks de lignes/cellules restent côté adaptateur.
Avec `liveEdit`, `onDataChange` distingue `preview`, `commit` et `rollback` :
ne pas sauvegarder les aperçus. `onCellChange` reste réservé à la validation finale.
Une exception de ce hook est journalisée et signalée par `onValidationError` :
la valeur avant appel est restaurée et le brouillon reste modifiable/annulable.
Le hook reste synchrone et doit laisser les autres données métier intactes en cas
de rejet ; TableView ne peut pas annuler ses effets externes.

`preview` modifie immédiatement la donnée partagée. Seule la ligne éditée est
rafraîchie par TableView ; les `refreshRow()` ciblés sur les lignes dépendantes
restent à la charge de l'application. `coalescePreview: 'raf'` (ou `true`) regroupe le
rafraîchissement et la notification du dernier aperçu valide en un seul appel
par frame (rAF), sans différer la mutation. Valider vide la file avant `commit` ;
annuler, masquer la ligne éditée, remplacer les données/colonnes, appliquer une
configuration ou détruire l'instance supprime l'aperçu en attente et émet `rollback`.
`undefined`, `'none'` et `false` notifient immédiatement ; toute autre valeur
est refusée. Les exceptions synchrones de `onDataChange`, dans les quatre phases,
sont journalisées et affichées dans une alerte sans bloquer l'éditeur. Le hook
facultatif `onDataChangeError({ error, event, table })` permet à l'application de
signaler une désynchronisation. Ce hook est une notification, pas une validation :
une erreur ne peut annuler les données acceptées ni les effets externes déjà produits.
La bannière est retirée lorsqu'une notification ultérieure réussit ; ce retrait
ne garantit pas à lui seul la réparation des effets externes d'une notification échouée.

`mountConfiguration` exige un `onApply` atomique : une exception ou un rejet
doit laisser la cible inchangée, ou l'adaptateur doit restaurer son état avant
de rejeter. Le formulaire ne peut pas annuler des mutations externes partielles.
Il fournit une copie de la configuration candidate et garde son dernier état
accepté ainsi que le brouillon en cas de rejet.

Ces options restent facultatives et sont configurées par l'adaptateur métier :

- `rowKey` : propriété d'identité unique (chaîne non vide ou nombre fini).
  `setData()` conserve sélection et masquage par identité, même après réordonnancement ;
  une identité supprimée ne sélectionne pas automatiquement sa voisine.
- `selectionMode: 'single' | 'range' | 'multi'` (défaut : `single`).
  `getSelection()` expose les plages, indices et clés ; `getSelectedCellValues()`
  retourne les valeurs calculées via `getValue`, sans doublons ni lignes masquées.
  Par défaut, `null`, `undefined` et `''` sont conservés sans conversion.
  `omitNullValues: true` exclut uniquement `null` et `undefined`, jamais `''` ni zéro.
  `getSelectedCellValues({ structured: true, omitNullValues: false })` renvoie
  `{ values, cells }` avec les mêmes positions dans les deux listes. Chaque cellule
  expose `rowIndex`, `columnIndex`, `rowKey`, `columnKey`, `row`, `column` et `value`.
  `row` est la donnée partagée ; `column` est une copie superficielle.
- `setHiddenRows(indices)` et `getHiddenRows()` : masquage réversible, navigation
  limitée aux lignes visibles. Masquer une cellule en édition annule son aperçu.
- `hierarchy: { columnKey, isGroup, getLevel, isExpanded, onToggle }` :
  indentation à partir de zéro et boutons accessibles ; l'adaptateur gère les descendants.
  L'éditeur reste dans `.tv-hierarchy-content` avec indentation et chevron conservés,
  même après `render()`. Une colonne référencée absente désactive la fonctionnalité
  avec un avertissement ; son retour la réactive sans modifier les options de l'appelant.
- `rowActions: { columnKey, contextMenu, items, onAction }` : actions en cellule
  et/ou menu clavier. `items` est un tableau ou une fonction recevant
  `{ row, rowIndex, table, selection }`. Chaque action définit `id`, `label`,
  et éventuellement `symbol`, `enabled`, `inline`, `group`.
- `isRowEditable`, `renderCell` (contenu uniquement, retourner `true` pour remplacer
  le rendu par défaut), `refreshRow()` et `setAppearance()` complètent les hooks.
  `allowEmpty: false` interdit explicitement une valeur vide sans modifier le défaut.
- `onAppearanceChange(appearance)` reçoit une copie après un changement effectif
  accepté, via `setAppearance` ou `applyConfiguration`. `onConfigurationChange`
  reçoit la configuration après application, remplacement des colonnes et
  redimensionnement manuel (fin de geste ou pas clavier) ; `onColumnResize` reste disponible.
  `onAppearanceChange` couvre uniquement l'apparence globale, pas les largeurs
  ni le schéma des colonnes ; utiliser `onConfigurationChange` pour persister la disposition.
- `getColumns()` renvoie des copies superficielles avec les largeurs effectives
  et les callbacks. `setColumns(definitions)` remplace les colonnes sans recréer
  l'instance : validation préalable, annulation de l'édition, sélection remappée
  par clé et conservation des largeurs des clés existantes si omises. Les colonnes
  retirées disparaissent de la sélection ; une plage devenue discontinue est
  divisée sans sélectionner les nouvelles colonnes intercalées. La cellule active
  devient nulle si sa colonne est retirée. Données et masquage sont conservés.
  Au moins une colonne est obligatoire ; les définitions invalides (dont les clés
  dupliquées) sont refusées sans mutation. Les références manquantes de
  `hierarchy`/`rowActions` avertissent et désactivent seulement la fonctionnalité concernée.

### Interactions TableView : clipboard, tri et colonnes

- `clipboard: { copy: true, paste: true, parseTsv: true }` active les événements
  copier/coller natifs du navigateur sur les cellules sélectionnées. Dans un
  éditeur, le copier/coller de texte reste natif. Échap ou Entrée permet de
  revenir à la grille avant de coller un bloc. `copyText()` et `pasteText(text)`
  fournissent les mêmes opérations par API. `TableView.parseTsv` /
  `stringifyTsv` gèrent tabulations, CR/LF, champs entre guillemets et guillemets
  doublés. Les valeurs calculées sont copiées ; `null` devient un champ vide.
  Plusieurs sélections sont copiées dans leur rectangle englobant, avec des
  champs vides dans les trous ; les lignes masquées sont exclues.
- Le collage part de la cellule active, saute par défaut les lignes masquées et ignore
  les cellules en lecture seule sans décaler les colonnes. Un dépassement de
  colonnes est refusé ; un dépassement de lignes ajoute des lignes via
  `createRow({ rowIndex, table })`, ou des objets vides avec une identité UUID si
  `rowKey` est défini. La fabrique doit être sans effet externe.
  Pour un tableau métier, `createRow` doit renvoyer un nouvel objet complet :
  identité unique, niveaux/indicateurs hiérarchiques, valeurs numériques initiales,
  objets imbriqués et tous les champs nécessaires aux renderers, validateurs et
  `getValue`. Le défaut minimal n'est adapté qu'aux tableaux simples sans ces exigences.
  Toutes les cellules sont parsées et validées avant mutation. Le hook synchrone
  `onPaste({ changes, newRows, data, source, table })` peut refuser par `false`
  ou exception, sans modifier la cible. Il doit être sans effet de bord.
  `onCellChange` n'est pas appelé cellule par cellule pour éviter des mutations
  externes partielles ; après acceptation, `onDataChange` reçoit une notification
  de lot avec `phase: 'paste'`, `changes` et `newRows`. L'adaptateur y synchronise
  son modèle métier. Les erreurs des événements sont journalisées, affichées
  dans une alerte et transmises à `onClipboardError(error)` ; `pasteText` lève
  directement l'erreur. Le collage ne déclenche aucune sauvegarde réseau.
  `clipboard.includeHiddenRows: true` parcourt toute la liste plate à partir
  de la cellule cible, y compris les lignes masquées, sans se limiter aux frères.
  Cette option est activée dans le bordereau : les lignes
  existantes gardent leur parent ; après la fin de la liste plate, les lignes
  supplémentaires sont créées sous Root. Le masquage et les protections de
  lecture seule restent inchangés ; le tri hiérarchique n'est pas modifié.
- `column.sortable: true` active le tri au clic sur l'en-tête (ou Entrée/Espace
  sur son bouton). `sortBy(key, 'asc' | 'desc')` expose le tri par API.
  Le tri est stable, utilise `getValue`, compare les nombres numériquement et
  les chaînes avec `Intl.Collator`. Les valeurs nulles viennent après les valeurs
  renseignées en ordre croissant. Avec `hierarchy.getLevel`, les frères sont triés
  récursivement en conservant chaque sous-arbre ; les niveaux doivent être des
  entiers positifs ou nuls dans une liste préordonnée.
  TableView est seul responsable du calcul de l'ordre. Le hook synchrone
  `onSort({ column, direction, rows })` reçoit cet ordre avant son application et
  les notifications de sélection. Il doit le recopier dans le modèle existant,
  sans retrier, changer les parents, reconstruire les données ni rappeler
  `setData`/`sortBy`. `false` refuse le tri ; une exception se propage. En cas de
  rejet, l'adaptateur doit laisser son modèle inchangé. Les promesses sont interdites.
  Dans le bordereau, il réordonne directement les enfants existants du
  `LineManager` : ce changement sera enregistré au prochain Enregistrer.
  Le tri est une opération ponctuelle ; il n'est pas réappliqué automatiquement
  après édition ou collage.
- `setFilter(predicate)` compose le filtre avec le masquage manuel existant ;
  `setFilter(null)` retire uniquement le filtre. `getHiddenRows()` retourne
  l'union des deux masques. Le filtre est réévalué lors de `setData`, du tri,
  du collage et des modifications validées ; utiliser une fonction pure.
  Les titres ne sont pas automatiquement conservés si seuls leurs enfants
  correspondent : l'adaptateur définit la politique hiérarchique du filtre.
- `freezeColumns: n` fige les n premières colonnes par `position: sticky`.
  `rowHeaders: true` ajoute des en-têtes de lignes numérotés selon la position
  dans la liste courante ; `rowHeaders: (row, rowIndex) => texte` personnalise
  leur libellé. Désactivés par défaut, ils ne changent pas les indices des
  colonnes métier, les données, le tri ni le clipboard. Un clic sélectionne
  toute la ligne sans éditer ; Maj étend aux lignes intermédiaires en mode
  range/multi, Ctrl/Cmd ajoute en mode multi. Les lignes masquées restent exclues.
  Les boutons sont accessibles au clavier (Entrée/Espace) et au menu contextuel.
  `rowHeaderWidth: 44` règle leur largeur ; `freezeRowHeaders: true` les fige
  horizontalement, indépendamment de `freezeColumns` (défaut : false).
  Le bordereau ne les active pas, pour éviter une seconde numérotation sur mobile.
  Leur visibilité peut désormais être réglée dans la configuration générique
  (`configuration.rowHeaders`) et dans le dialogue Apparence du bordereau
  (« Afficher les en-têtes de lignes »). Ce dernier conserve le réglage par lot,
  avec aperçu, annulation et retour aux valeurs par défaut (masqué).
  La croix de fermeture et Échap annulent l'aperçu comme le bouton Annuler ;
  la fermeture est désactivée pendant l'enregistrement.
  Les deux formulaires alignent les paramètres dans des tables ; les contrôles
  couleur et HEX sont compacts, avec un texte HEX nuancé en thème sombre.
  Les offsets suivent les redimensionnements et les remplacements de colonnes.
  Le double-clic sur une poignée ajuste la largeur au contenu visible et à
  l'en-tête, dans les limites `minWidth` / `maxWidth`, puis émet les hooks habituels.
- `column.group` (chaîne) regroupe les colonnes contiguës sous une seconde
  rangée d'en-têtes. Un groupe traversant la frontière figée est scindé pour
  conserver un défilement cohérent ; les en-têtes restent fixes verticalement.
- En mode `range` ou `multi`, maintenir le bouton gauche sur une cellule et
  glisser sélectionne un rectangle dans toutes les directions, sans sélectionner
  le texte ni ouvrir l'éditeur. Maj étend depuis l'ancre ; Ctrl/Cmd conserve les
  autres plages en mode `multi`. Le clic simple conserve son comportement
  d'activation ; la saisie dans un éditeur reste indépendante du glisser de grille.

Un clic active la cellule et lui donne le focus en **mode Navigation**, sans
ouvrir l'éditeur ni sélectionner son texte. Les quatre flèches déplacent la
cellule active (en sautant les lignes masquées), sans ouvrir l'éditeur ; aux
bords du tableau, elles restent sur place sans faire défiler la page.
Un double-clic ouvre le **mode Édition** et sélectionne le contenu de l'éditeur
natif. Entrée/F2 restent disponibles pour ouvrir l'édition au clavier.
Dans l'éditeur, les flèches restent natives (curseur, sélection de texte).
Seuls Tab/Maj+Tab valident puis déplacent le focus vers la cellule suivante/
précédente en mode Navigation, avec passage à la ligne et saut des lignes
masquées. Une validation refusée conserve l'éditeur ; aux extrémités, le focus
reste sur la cellule courante. Entrée valide sans déplacement, Échap annule.
L'ancienne option `editOnClick` est ignorée, même lorsqu'elle vaut `true`.

Le bordereau actif utilise le clipboard et le tri hiérarchique, sans colonnes
figées (`freezeColumns: 0`) : N° et désignation défilent avec les autres colonnes,
y compris sur petits écrans. Le défilement horizontal et vertical reste dans
le conteneur interne TableView. Les colonnes numériques des
titres sont en lecture seule. Les nouvelles lignes collées sont créées à la racine.

Le défilement est ancré sur l'identité de ligne lors d'un `setData()` ou d'un rendu
(`viewport: false` désactive cet ancrage). `destroy()` retire les écouteurs globaux.

`TableView.version` expose la version du composant (`0.3.0`), distincte du
schéma de configuration. Les options, colonnes et contrats de callbacks sont
décrits par les typedefs JSDoc en tête du composant.

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
node --test goplan/tests/
```

## Auteur et licence

**missbahi** — projet sous licence MIT.
