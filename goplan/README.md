# GoPlan

Plannings de travaux : tâches hiérarchiques, calendriers ouvrés, diagramme de
Gantt, échanges XML MS Project (MSPDI) et impression A4 à A0.

## Édition inline des tâches

La barre d'outils agit sur la tâche sélectionnée, y compris les tâches racines
et les nouvelles lignes non encore enregistrées. Indenter rattache la tâche
à sa sœur précédente ; désindenter la place après son ancien parent.

Les enfants restent attachés : les quatre actions déplacent le sous-arbre
complet. Un jalon ou une tâche récurrente ne peut pas devenir parent.

Un parent devient automatiquement un groupe, puis redevient une tâche simple
lorsqu'il perd son dernier enfant.

L'arbre JavaScript est la source de vérité pendant l'édition ; les champs
cachés transmettent les clés de ligne, les parents et l'ordre au formset.
La sauvegarde valide la hiérarchie soumise et crée les parents avant leurs
enfants, dans une transaction. 

Les règles de type sont vérifiées sur les enfants soumis pour l'édition inline, et sur les enfants enregistrés pour l'administration.

Supprimer un groupe demande confirmation et supprime tout son sous-arbre.
Dans le Gantt, les recalculs après suppression portent uniquement sur les tâches restantes ; supprimer la dernière tâche renvoie un diagramme vide.
Une ligne supplémentaire laissée vide n'est pas enregistrée.

### Collage depuis Excel

Dans le tableau inline, Ctrl+V reconnaît les données tabulées, y compris dans
les champs Code et Nom. Un texte simple reste un collage normal dans le champ.
Sur un tableau vide, cliquez sur le cadre du tableau avant de coller.
Le format attendu, sans en-tête, est : Code, Nom, Type, Durée, Début.
Le code peut être vide ; les cellules Excel entre guillemets peuvent contenir
des tabulations, des retours à la ligne et des guillemets doublés.
Les colonnes supplémentaires et les conversions de type sont signalées.

Un aperçu permet de confirmer ou d'annuler. Les lignes remplacent les tâches
visibles depuis la sélection ; le surplus est ajouté à la racine, en fin de
tableau. Sans sélection, toutes les lignes sont ajoutées. Une ligne invalide
est ignorée sans décaler les suivantes ni modifier sa tâche cible.
Les groupes existants conservent leur type, leurs enfants et leurs dates
calculées : seuls leur code et leur nom sont remplacés.

Une durée vide vaut un jour ; sinon elle doit être positive, par pas de
0,5 jour. Les jalons ont une durée nulle et une fin égale au début.
Les dates acceptées sont `AAAA-MM-JJ` et `JJ/MM/AAAA` (aussi avec `-` ou `.`).
Un début vide conserve celui de la cible, ou utilise le début du planning
pour une création. Les dates de fin sont recalculées selon le calendrier ouvré.
Le collage ne sauvegarde pas : cliquez ensuite sur « Enregistrer ».

Les dates sont corrigées automatiquement à l'ouverture de l'éditeur inline,
du Gantt et de l'aperçu : le début est ramené au prochain jour ouvré et la fin est recalculée en conservant la durée en jours. 
Les corrections, les synthèses des groupes et les conséquences sur les liaisons sont enregistrées dans une transaction ; un message indique le nombre de tâches corrigées. 
Une contrainte incompatible annule les corrections et affiche une erreur.
La sauvegarde inline et celle d'une tâche du Gantt appliquent la même priorité début + durée sur la fin saisie. 
Une durée absente reste calculable depuis les deux dates. 
Les durées sont exprimées en jours : passer de 7 h/j à 8 h/j ne
convertit pas la durée et ne décale pas les dates à jours ouvrés identiques.

Le chevron à gauche du nom replie ou déplie un groupe. Cet état (`GTask.replie`) est partagé avec le Gantt et l'aperçu d'impression, et enregistré
immédiatement, sans passer par « Enregistrer » ; il n'affecte ni le formulaire ni les contrôles de modification concurrente. Le repli d'une ligne non encore enregistrée vaut pour la page en cours seulement. 

Les flèches ↑/↓ sautent les lignes repliées ; indenter dans un groupe replié, ou une erreur de saisie dans une ligne cachée, déplie ses parents.
Le champ `GTask.masquee` est réservé à une prochaine version (masquer une
ligne) et n'est pas encore utilisé.

Les tâches se gèrent dans cet éditeur et dans la ligne de saisie du Gantt ; les anciens écrans de détail et formulaires individuels, ainsi que leurs URL et API Gantt, sont retirés. 
Les boutons Gantt des cartes et de l'éditeur ouvrent le Gantt avec sa ligne d'édition. 

La liste, la création et la modification des plannings sont
conservées et ouvrent l'éditeur inline.

Les écritures du Gantt verrouillent le planning et ses tâches dans une
transaction. Le verrou du planning exclut le calendrier optionnel chargé par
jointure, pour rester compatible avec PostgreSQL même sans calendrier associé.

Le Gantt reçoit ses données depuis Django (JSON intégré, sans ancienne API).
L'en-tête du calendrier et celui de la liste des tâches restent visibles lors
du défilement vertical du diagramme. Les dates suivent le défilement horizontal
et restent synchronisées avec le zoom et les changements de vue.
Le champ « Couleur » du formulaire personnalise la barre d'une tâche, d'un
groupe ou d'un jalon après enregistrement. 
Le bouton de réinitialisation adjacent rétablit la couleur automatique du type. Ce choix est conservé au rechargement ; il ne modifie ni la forme de la barre ni les dates calculées des groupes.
Un panneau « Couleur » regroupe 24 couleurs prédéfinies, le sélecteur personnalisé (mélangeur natif du navigateur) et la réinitialisation. La pastille sélectionnée est encadrée et reste synchronisée avec le sélecteur et l'aperçu du formulaire.
Le panneau se ferme avec sa croix, Échap ou un clic à l'extérieur, sans perdre le choix en cours ; enregistrez la tâche pour appliquer la couleur au diagramme.
Le bouton « Enregistrer » du panneau reste désactivé à l'ouverture et tant que la couleur n'a pas changé. Il enregistre le formulaire complet de la tâche et ferme le panneau uniquement en cas de succès ; en cas d'erreur, la saisie et le panneau restent disponibles pour correction.

L'icône palette de la barre d'outils ouvre « Apparence du planning » :
- arrondi des barres : rectangle, arrondi ou capsule ;
- épaisseur : fine, normale ou épaisse, sans changer la hauteur des lignes ;
- groupes : crochets de synthèse ou bande simple ;
- jalons : losange, cercle ou triangle ;
- liaisons : angles droits, angles arrondis, tirets ou pointillés ;
- couleur commune des traits, flèches et libellés de liaison.

Les changements sont prévisualisés immédiatement. « Appliquer » les enregistre pour ce planning ; « Annuler » ou Échap restaure l'apparence enregistrée. « Valeurs par défaut » prépare une remise à zéro à confirmer par « Appliquer ».
La couleur propre à chaque tâche reste prioritaire sur les couleurs par type,
et les liaisons conservent leurs extrémités métier. L'aperçu ne modifie ni les tâches ni le brouillon en cours ; le zoom, le défilement et les replis sont conservés. Les modifications concurrentes de l'apparence sont refusées avec un message invitant à recharger.

Appliquer la migration `0007_plan_gantt_appearance` avant d'utiliser cette
version. Les plannings existants gardent l'apparence par défaut précédente.
Ces préférences sont propres à GoPlan et ne sont pas exportées en XML MSPDI.

## Aperçu et impression du planning

« Aperçu / Imprimer » sur les cartes, ou l'icône d'imprimante du Gantt, ouvre
un aperçu graphique autonome. Le bouton « Paramètres d'impression » ouvre une
fenêtre flottante non bloquante, fermable par « Terminé », « Fermer » ou Échap.
Les réglages y sont répartis en quatre onglets : 
**Page** (format, orientation, marges, pages et lisibilité), 
**Contenu** (échelle, période, tâches, colonnes), 
**Affichage** et **Textes** (en-tête, pied de page, typographie). 
Le dernier onglet ouvert est mémorisé dans le navigateur ; une pastille orange signale un onglet aux modifications non enregistrées, une pastille rouge un réglage refusé à l'enregistrement (l'onglet concerné s'ouvre automatiquement). 
←/→, Début et Fin naviguent entre les onglets.
Choisissez A4, A3, A2, A1 ou A0 en portrait ou paysage, puis le calendrier Jour, Semaine ou Mois. 
Le diagramme remplit toute la largeur imprimable ; il n'est jamais étiré verticalement, si bien que le texte des tâches garde ses proportions et suit la hauteur des lignes.
L'aperçu à l'écran s'adapte à la largeur disponible (jusqu'à 110 % de la
taille naturelle). Le curseur sur le papier devient une loupe : un clic
agrandit progressivement, puis revient à l'ajustement au maximum. Le curseur
de zoom et les boutons +/− permettent un réglage précis, dont 100 % pour
la taille naturelle et 110 % au maximum. « Ajuster à la largeur » restaure
le cadrage initial. Ce zoom ne change ni le format ni l'échelle imprimés.

**Pages et lisibilité** : la **hauteur maximale des lignes** (7 mm par défaut,
de 5 à 15 mm) fixe la taille du texte des tâches (7 mm ≈ 7,4 pt) : un papier
plus grand contient davantage de lignes au lieu de les agrandir (avec
91 tâches en Mois : 21 lignes par feuille en A4, 34 en A3, 51 en A2, 76 en A1).
Le tableau des tâches garde ses proportions ; la largeur restante élargit
seulement le calendrier, sans déformer textes, jalons ni flèches.
« Pages en hauteur » répartit les tâches sur 1 à 20
feuilles : chaque feuille est remplie en hauteur avant de passer à la suivante,
la dernière reçoit le reste (si moins de pages suffisent, l'aperçu l'indique).
Chaque feuille répète l'en-tête, le calendrier et
le pied de page (« 1 / 3 »…). « Automatique » choisit le plus petit nombre de
pages qui respecte la **taille minimale du texte** (7 pt par défaut, réglable
de 5 à 12 pt). Si le texte passe sous ce minimum, un bandeau l'indique et
propose « Passer à N pages en hauteur ». Lorsque c'est la largeur qui limite
(par exemple beaucoup de semaines sur une feuille A4), ajouter des pages ne
suffit pas : choisissez un papier plus grand, l'échelle Mois ou une période
plus courte.

Le diagramme imprimé réutilise le rendu SVG du Gantt, sans capture raster :
couleurs personnalisées, avancement, formes des groupes et jalons, styles et
couleurs des liaisons, hiérarchie, calendrier et jours non travaillés sont
conservés. L'apparence des barres et des liaisons reste réglée dans le Gantt
(une seule source) ; l'aperçu ne règle que la mise en page. La préparation ne
modifie aucune donnée (ni l'état replié enregistré). Un rendu invalide
désactive l'impression avec un message explicite.

Réglages d'impression (modèle `GPlanPrintSettings`, un par planning) :

- **Mise en page** : format, orientation, marges (0 à 30 mm), centrage
  vertical d'un petit planning.
- **Échelle et période** : Jour/Semaine/Mois ; toute la période, période
  personnalisée (recadrage inclusif) ou période relative autour de la
  **date d'état** (N semaines avant / après, 2 et 6 par défaut).
- **Tâches** : niveau hiérarchique maximal ; groupes repliés dans l'éditeur ou
  le Gantt respectés (option activée par défaut) ; tâches non datées listées
  sans barre en bas (optionnel).
- **Colonnes** : nom toujours imprimé ; code, durée, début, fin, avancement et
  prédécesseurs au choix (`FD`/`DD`/`FF`/`DF` et décalage, ex. `1.2DD+2 j`).
  Largeur maximale imprimée de la colonne Nom (25 à 250 mm) et des autres
  colonnes (8 à 80 mm) ; 0 = automatique. Les textes plus longs sont tronqués
  « … » (nom complet en info-bulle dans l'aperçu).
- **Affichage** : noms sur les barres, liaisons, avancement, jours non
  travaillés, grille, aujourd'hui, ligne de date d'état, légende (seuls les
  éléments présents), date d'impression, avertissements, pied de page, couleur
  de fond du dessin (`#f8f6ef` par défaut, avec ou sans grille) : huit teintes
  claires prédéfinies au-dessus du sélecteur libre (`BACKGROUND_PRESETS`).
- **Textes** : titre, sous-titre, texte centré en haut de page (plusieurs
  lignes possibles) et pied de page, avec les variables
  `{plan}`, `{description}`, `{date_impression}`, `{date_etat}`,
  `{periode}`, `{format}` et `{calendrier}`. Une variable inconnue est
  refusée à l'enregistrement.
- **Typographie** : police (Arial, Calibri, Verdana, Tahoma, Georgia, Times),
  taille, gras et couleur du titre, tailles du sous-titre, du texte centré
  (avec gras) et du pied de page, en points.

Toute modification s'applique immédiatement à l'aperçu. « Enregistrer pour ce
planning » la conserve en base (partagée entre postes et utilisateurs) ;
« Par défaut » supprime les réglages enregistrés après confirmation. Un
indicateur signale les modifications non enregistrées. Une modification
concurrente est refusée (rechargez la page). Les paramètres d'URL `format`,
`view` et `orientation` priment sur les réglages enregistrés pour la visite.

La date d'état (`GPlan.date_etat`, `StatusDate` MSPDI) se saisit dans les
informations du planning ; elle est importée, exportée et conservée lors d'un
remplacement par import XML. Appliquer les migrations
`0008_plan_status_date_print_settings`, `0009_print_typography_pages` et
`0010_print_layout_fold` avant d'utiliser ces fonctions.

« Imprimer / PDF » ouvre la boîte de dialogue du navigateur. Utilisez le même
papier, l'orientation choisie, une échelle de 100 % et désactivez les en-têtes
et pieds de page du navigateur. Les grands formats nécessitent une imprimante
compatible ou une destination PDF ; la feuille CSS ne peut pas imposer les
capacités du pilote. L'ancien aperçu tabulaire reste disponible par le lien
« Tableau des tâches » (`?mode=tasks`).
Il affiche les tâches datées dans l'ordre hiérarchique, les groupes et les
jalons, avec vues jour/semaine/mois et sélection par clic ou clavier.
Les tâches sans dates complètes ou aux dates inversées sont signalées et
exclues, sans dates inventées. L'axe reste calendaire : les dates inclusives,
les durées ouvrées et l'avancement sont les valeurs enregistrées.
Sous la barre d'outils, une seule ligne permet de modifier la tâche active
ou de créer une tâche avec « Nouvelle tâche ». La liste « Tâche active »
donne aussi accès aux tâches sans barre (dates manquantes).
L'ajout à la fin crée une racine après le dernier sous-arbre. L'ajout avant
la tâche active crée une soeur de même parent, avant tout son sous-arbre.
La sélection reste le repère pour les insertions successives ; aucun lien
de dépendance n'est créé ni modifié automatiquement.
Les règles de calendrier sont partagées avec l'éditeur inline.
Les dates d'un groupe ne sont pas recalculées à partir de ses enfants.
Un changement de tâche avec une saisie modifiée propose d'enregistrer,
d'abandonner ou de rester. La croix en haut à droite restaure la tâche ou
vide le brouillon ; l'icône à droite du nom de la tâche dans la barre d'outils
enregistre la modification (disquette) ou ajoute la nouvelle tâche (plus).
Une corbeille apparaît à côté de cette icône lorsqu'une tâche est sélectionnée.
Après confirmation, elle supprime la tâche et son sous-arbre, avec les
liaisons et affectations associées. Le dernier enfant supprimé transforme
son groupe parent en tâche simple. Les successeurs restants sont recalculés
selon leurs autres liaisons ; sans prédécesseur, ils conservent leurs dates.
La suppression refuse les états périmés et reste transactionnelle.
Un séparateur vertical précède l'icône « Nouvelle tâche ».
Après un ajout, la ligne est prête pour le suivant ; après modification,
elle reste sur la tâche enregistrée. La sauvegarde unitaire est transactionnelle
et refuse un état périmé du planning. Une erreur conserve la saisie.
Le Gantt n'est rafraîchi qu'après confirmation du serveur, en conservant
le zoom et le défilement ; le déplacement des barres reste désactivé.
L'icône de liaison ouvre les prédécesseurs de la tâche active : création,
modification et suppression des liens FS (fin-début), SS (début-début),
FF (fin-fin) et SF (début-fin), avec décalage entier signé en jours ouvrés.
Le même formulaire et le même contrôleur de liaisons sont utilisés dans
l'éditeur inline et le Gantt. En inline, sélectionnez une tâche enregistrée
puis l'icône de chaîne ; une saisie ou une hiérarchie modifiée doit d'abord
être enregistrée (aucune sauvegarde automatique). Une nouvelle tâche doit
également être enregistrée avant d'être liée. Après ajout, modification ou
suppression d'un lien, les dates, groupes et choix possibles sont actualisés
sans recharger la page.
La colonne « Liaisons (prédécesseurs) » affiche le code (ou le nom) du
prédécesseur, le type DD/DF/FD/FF et le décalage signé en jours ouvrés.
Un clic dans cette colonne ouvre la gestion des liaisons de la ligne.
Le formulaire Gantt affiche la même synthèse pour la tâche en cours.
Les barres d'outils restent visibles pendant le défilement vertical ; dans
le Gantt, le formulaire reste avec sa barre. L'icône de chevron à droite de
la barre Gantt affiche/masque ce formulaire sans abandonner la saisie.
Sélectionner une tâche ou choisir une nouvelle tâche le réaffiche, tout
comme une tentative d'enregistrement ou une erreur de validation.
Les flèches utilisent les extrémités correspondantes et affichent type/décalage.
Le choix des prédécesseurs exclut la tâche active, ses parents et ancêtres,
ses descendants, les tâches non datées et les choix créant un cycle
(y compris via la synthèse des groupes). Cette interdiction hiérarchique
s'applique dans les deux sens, pour les quatre types de liaison, et est
vérifiée côté serveur. Les anciennes liaisons incompatibles restent visibles
pour pouvoir être supprimées, mais ne peuvent plus être modifiées.
Une liaison FS sans décalage commence au jour ouvré suivant la fin inclusive
du prédécesseur. Les autres types imposent une borne sur le début ou la fin.
Le recalcul conserve les durées (arrondies au jour supérieur pour les dates),
applique la borne la plus contraignante et propage aux successeurs,
y compris après une édition des tâches dans le Gantt ou l'éditeur inline.
Les tâches sans prédécesseur gardent leurs dates ; supprimer leur dernière
liaison conserve donc leur position. Les cycles et liens hors planning sont
refusés, sans sauvegarde partielle. Une date fixe incompatible bloque
l'opération ; « au plus tard » est explicitement refusé pour une tâche
à recalculer, le calcul complet des marges n'étant pas disponible.
Les groupes sont des synthèses : début au plus tôt des enfants, fin au plus
tard, durée ouvrée inclusive entre ces deux dates (et non somme des durées
des enfants qui peuvent se chevaucher). Le calcul remonte les groupes
imbriqués et propage les changements aux successeurs liés aux groupes.
Les jalons participent aux liaisons avec durée zéro.
« Aujourd'hui » centre la date courante si elle est
dans la période affichée, sinon indique qu'elle est hors période.
Frappe Gantt 0.6.1 est chargé depuis jsDelivr ; un échec de chargement est
signalé dans la page.
Le Gantt reprend le fond papier, l'en-tête bleu pâle et les bordures du
tableau inline, avec un pas de ligne commun de 35 px. Les tâches utilisent
des barres bleues arrondies, les groupes des barres de synthèse vertes à
extrémités marquées, les jalons des losanges violets et les tâches récurrentes
des barres ambre à bordure discontinue. La sélection, le clavier et le zoom
conservent ces distinctions.
La liste des noms et le diagramme partagent un seul conteneur de défilement :
un ascenseur vertical à droite et une barre horizontale en bas. Les noms restent
visibles à gauche lors du défilement horizontal, sans ascenseur indépendant.
Les lignes et leurs séparateurs sont alignés après chaque changement de vue.
La liste conserve le même thème papier que le diagramme, y compris en thème sombre.
Les boutons de zoom avant/arrière règlent l'échelle horizontale de 75 % à 200 %
(75, 100, 125, 150, 200 %), en conservant le centre de la période visible.
Le niveau est conservé lors des replis, changements de vue et enregistrements.
Une ligne sépare les deux niveaux de l'en-tête ; les débuts de semaine (lundi),
de mois et d'année ont des séparateurs verticaux de force croissante.
Les jours non travaillés sont ombrés sous les barres, selon le calendrier du
planning : jours de repos, exceptions fériées et weekends exceptionnellement
travaillés sont pris en compte sans changer les dates ou durées des tâches.
Le chevron devant un groupe masque/affiche ses descendants dans la liste et
le diagramme simultanément, sans changer les dates, les durées ou les liaisons.
Les replis des sous-groupes sont conservés lors du dépliage du parent, du zoom
et des enregistrements. Cliquer sur le nom continue d'ouvrir son édition ;
replier un groupe ne perd pas la saisie en cours. Choisir une tâche masquée
dans la liste « Tâche active » déplie automatiquement ses ancêtres.

Le bouton « Calendriers », à côté de « Nouveau plan », ouvre leur gestion :
nom, jours ouvrés, heures par jour, calendrier par défaut et exceptions
saisies par date/heures. Une date ne peut avoir qu'une exception ; les heures
doivent être comprises entre 0 et 24 (strictement positives pour la journée
standard). Choisir un calendrier par défaut remplace le précédent, sans
modifier les affectations explicites des plannings. Un calendrier affecté
à un planning ou une ressource ne peut pas être supprimé depuis cette page.
Les heures positives rendent une exception ouvrée, mais ne proratisent pas
les durées des tâches.
Les exceptions sont désormais des lignes `GCalendarException`, uniques par
calendrier et date (migration du JSON existant). La représentation envoyée au
navigateur reste un dictionnaire date/heures ; les règles de calcul sont
inchangées, y compris les demi-journées et les bornes de dates.

### Échanges XML MS Project (MSPDI)

`goplan.services.mspdi_import.import_mspdi_to_new_plan(xml_bytes)` crée un nouveau
planning dans une transaction unique. Le service exclut la synthèse projet
(ID 0) et les lignes `IsNull`, conserve l'ordre hiérarchique, les dates, durées,
notes, WBS et les quatre types de liaisons. Il choisit le calendrier désigné par
`CalendarUID`, résout son calendrier de base et développe les plages
d'exceptions en dates individuelles. Les durées et décalages utilisent les
heures par jour du fichier, pas une constante de 8 h.
Chaque tâche importée reçoit un code numérique séquentiel (`1`, `2`, `3`...),
selon son ordre d'affichage initial, groupes et jalons compris. Les lignes XML
vides et la synthèse projet exclues de l'import ne créent pas de trous dans
cette numérotation. Le code reste ensuite éditable et n'est pas renuméroté lors
des déplacements de tâches.

Les contraintes MSPDI 4 à 7 sont conservées avec une `date_contrainte` distincte :
début/fin au plus tôt/au plus tard le. Cette date est éditable en inline et dans
le Gantt. Le serveur vérifie les bornes lors de l'édition et du recalcul des
liaisons, et les réexporte sans les convertir en dates fixes.
Appliquer la migration `0006_task_constraint_dates` avant d'utiliser ces champs.

L'export est disponible sur la route `goplan:export_mspdi`. L'import est accessible depuis le bouton « Importation XML » de la liste des
plannings. Sélectionnez un XML MSPDI (5 Mo maximum), puis finalisez le titre et
la description dans le formulaire proposé. Les dates et le calendrier importés
sont verrouillés pendant cette étape uniquement. Aucun planning ni calendrier
n'est créé avant cette confirmation ; annuler ne laisse pas de données.

Depuis une carte, l'éditeur inline ou le Gantt, « Importation XML » propose le
remplacement complet du planning. Une acceptation explicite est requise lors de
la sélection puis à la confirmation finale. L'identifiant et les URL restent
les mêmes, mais les tâches, liaisons, affectations, titre, description, dates et
calendrier sont remplacés. Le rattachement projet est effacé (absent du XML).
Un ancien calendrier partagé reste disponible pour les autres plannings.
Un fichier invalide ou un échec d'enregistrement conserve intégralement les
données précédentes. Une modification concurrente du planning invalide la
confirmation. Celle-ci est signée, liée à l'utilisateur et à sa session, à usage
unique et valable 30 minutes. Les ressources/affectations non importées sont
signalées à l'écran avant validation. Le fichier `goplan/exemples/planning-achevement-amdl-20-10-26xml.xml`
est couvert par un test d'import réel puis export/réimport : 91 tâches utiles
(18 groupes), 55 liaisons et un calendrier de 7 h/jour.

Limites de cette première version : granularité des dates au jour (pas de
conservation des heures de début/fin ni des plages horaires originales),
calendrier unique par planning, exceptions datées non récurrentes,
décalages de liaisons en jours ouvrés entiers. Les calendriers spécifiques aux
tâches, les décalages fractionnaires, durées/décalages écoulés ou en pourcentage,
liaisons externes et données invalides sont refusés
explicitement, sans laisser de planning partiel.
Les ressources et affectations ne sont pas encore importées/exportées ; leur
présence est signalée dans les journaux d'import.
Ce n'est donc pas encore un aller-retour intégral de toutes les données MS Project.

Les flèches Haut/Bas passent à la ligne visible précédente/suivante dans la
même colonne, sans modifier la valeur des nombres, dates ou listes.
La position du curseur dans les champs texte est conservée. Aux extrémités,
le curseur reste dans la ligne. Alt + Haut/Bas conserve le comportement
natif du champ.

Le calendrier du planning est partagé par le navigateur et le serveur ;
à défaut, le calendrier marqué par défaut est utilisé, sinon lundi-vendredi.
Les exceptions à zéro heure sont chômées, celles à heures positives sont
ouvrées même le week-end. Un calendrier configuré sans jours ouvrés ou avec
des exceptions invalides est signalé et bloque la sauvegarde.
Le début d'une tâche est ramené au prochain jour ouvré. Les durées restent
en demi-journées, avec arrondi supérieur pour déterminer la date de fin
inclusive : 1,5 jour occupe deux dates ouvrées. Un jalon dure zéro et finit
à sa date de début, même un jour chômé. Modifier la fin recalcule la durée
en jours ouvrés entiers et ramène la fin au dernier jour ouvré de la période.
Le serveur rejette les triplets début/durée/fin incohérents.
Pour un groupe, type, durée et dates sont désactivés dans les éditeurs inline
et Gantt ; le serveur calcule ces valeurs depuis les enfants, sans accepter
de valeurs manuelles. L'éditeur inline recalcule les parents dès la saisie
ou un changement de hiérarchie. Les deux pages recalculent aussi à la lecture
les anciens groupes dont les valeurs enregistrées sont périmées, sans écrire
lors d'un GET ; l'enregistrement persiste les synthèses. Un groupe sans enfant
daté reste sans dates avec une durée nulle. Après retrait du dernier enfant,
la tâche redevient une tâche ordinaire et ses champs redeviennent modifiables.

Tests ciblés :

```text
python manage.py test goplan.tests
node --test goplan/tests/
```
