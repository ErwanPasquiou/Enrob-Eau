# Enrob'Eau

Application de suivi des demandes de travaux, des interventions et des prestations de réfection, développée en Python avec Streamlit pour un usage dans Databricks Apps.

Elle permet de signaler des travaux, de suivre leur avancement, de gérer les photos associées et d'exporter les données métier.

## Sommaire

- [État actuel du projet](#état-actuel-du-projet)
- [Navigation et fonctionnalités](#navigation-et-fonctionnalités)
- [Photos](#photos)
- [Adresses, carte et exports](#adresses-carte-et-exports)
- [Identification et droits](#identification-et-droits)
- [Installation et lancement](#installation-et-lancement)
- [Données et stockage](#données-et-stockage)
- [Organisation du code](#organisation-du-code)
- [Tests](#tests)
- [Limites et points de vigilance](#limites-et-points-de-vigilance)
- [Dépannage](#dépannage)

## État actuel du projet

Le projet est un **prototype fonctionnel avec données d'exemple**. Son stockage est réparti comme suit :

| Données | Stockage actuel |
| --- | --- |
| Comptes utilisateurs et profils | Table d'administration Databricks, via SQL Warehouse ; secours temporaire SQLite en cas d'erreur de récupération du profil |
| Demandes, interventions et prestations | Fichiers JSON dans `data/exemples/` |
| Photos des demandes et prestations | Deux tables SQLite avec contenu binaire, dans `data/exemples/photos.sqlite3` |

Les formulaires modifient réellement les fichiers locaux du prototype. Les dossiers et les photos ne sont pas encore enregistrés dans des tables métier Databricks.

Le stockage local ne doit pas être considéré comme persistant après un redéploiement. Conserver les JSON et les bases SQLite si les essais doivent être sauvegardés. Le fonctionnement actuel vise une seule instance de l'application.

## Navigation et fonctionnalités

| Page | Fonctionnalités |
| --- | --- |
| **Accueil** | Indicateurs cliquables : demandes à traiter, interventions en cours, prestations en cours et prestations en attente de réfection définitive. Carte des interventions en cours disposant de coordonnées. |
| **Demandes** | Liste des demandes de l'utilisateur connecté, cartes avec statut, recherche et filtre par statut. Création, consultation complète, modification de ses demandes et gestion de leurs photos. |
| **Gestion des dossiers** | Recherche et filtres, détail des dossiers, mode grand écran, fil d'avancement, gestion des demandes/interventions/prestations et de leurs photos. Export d'un dossier. |
| **Export** | Choix des tables et colonnes, filtres par dossier et téléchargement des données au format CSV. |
| **Administration** | Création et modification des comptes, activation/désactivation et suppression. Réservée aux administrateurs. |
| **Réfection définitive** | Espace du sous-traitant : tableau filtrable des prestations, modification des fiches, gestion de leurs photos et consultation des photos de la demande en lecture seule. Remplace Reporting. |

### Créer et suivre sa demande dans la page Demandes

1. Ouvrir **Demandes**, puis cliquer sur **Nouveau**.
2. Rechercher l'adresse ou choisir la saisie libre.
3. Renseigner le motif et les informations relatives aux travaux. L'e-mail du demandeur provient du compte connecté.
4. Ajouter des photos si nécessaire, puis enregistrer la demande.
5. Depuis **Mes demandes**, utiliser **Voir la demande** pour consulter le dossier, **Modifier ma demande** pour le corriger et **Retour à mes demandes** pour revenir à la liste.

La liste est triée des demandes les plus récentes aux plus anciennes. Le filtre personnel compare l'e-mail connecté à `RequesterReference`, sans tenir compte de la casse ou des espaces en début/fin.

Le formulaire de création s'affiche sur une colonne pour l'usage mobile. Demandes vérifie le propriétaire de la demande lors de la consultation et des écritures.

Les demandes fournies avec le projet utilisent des e-mails fictifs : elles n'apparaîtront pas dans la page Demandes si elles n'appartiennent pas au compte connecté. Elles restent disponibles dans Gestion des dossiers.

### Formulaire Demande — CODEX-003

La création et la modification partagent un formulaire sur **une seule page**, organisé en cinq sections bordées :

1. **Localisation des travaux** : recherche d'adresse ou saisie libre, commune, repères/GPS et rues concernées.
2. **Informations sur la demande** : date, demandeur, client, domaine d'activité, fiche fuite, motif et Matricule Compteur.
3. **Caractéristiques des travaux** : matériau, diamètre, types de voirie, revêtements et durée estimée.
4. **Contraintes et préparation du chantier** : DICT / ATU, coupure d'eau, impacts sur la voirie, sécurité et conditions particulières.
5. **Commentaire complémentaire** : commentaire de la demande.

Les huit listes ci-dessous sont obligatoires à la création et à l'enregistrement du formulaire de modification. Aucun choix métier n'est présélectionné pour une nouvelle demande.

| Champ | Sélection | Valeurs autorisées |
| --- | --- | --- |
| Type de voirie | Multiple | Pleine terre ; Chaussée ; Trottoir ; Autre |
| DICT / ATU | Unique | ATU immédiate ; ATU 72h ; ATU sous 9 jours ; DICT ; Sans terrassement |
| Revêtement | Multiple | Enrobé ; Asphalte <= 3m2 ; Asphalte > 3m2 ; Béton désactivé ; Béton (résine) perméable ; Pleine terre ; Pavé |
| Motif de la demande | Unique | Création branchement neuf ; Réparation de fuite branchement ; Renouvellement de branchement ; Suppression de branchement ; Modification de branchement ; Intervention bouche à clés ; Renouvellement de regard ; Réparation fuite réseau distribution ; Sondage ; Pose d'une vanne réseau ; Réparation une vanne réseau ; Renouvellement vanne réseau ; Création PI ; Renouvellement PI ; Pose Borne Moneca |
| Coupure d'eau | Unique | Avec arrêt d'eau 1 jour ; Avec arrêt d'eau 1/2 journée ; Sans arrêt d'eau ; Autre |
| Matériau signalé | Unique | Fonte ; PVC ; PEHD ; PEBD ; Cuivre ; Acier - Fer - Galva ; Plomb ; Non détectable ; Autre |
| Domaine d'activité | Unique | En domaine public : en agglomération ; En domaine public : Route métropolitaine ; En domaine privé nécessitant RDV |
| Impact sur la voirie | Multiple | Route barrée et déviation ; Alternat par feu ; Réduction sur chaussée ; Pose de panneaux interdit de stationner ; Travaux sur trottoir ; Aucun impact ; Autre |

Choisir **Autre** parmi les types de voirie affiche une précision obligatoire, stockée dans `ReportedRoadTypeOther`. Ce champ est facultatif lorsque ce choix est absent ; une précision déjà saisie est conservée. Aucun champ de précision supplémentaire n'est imposé aux autres listes contenant « Autre ».

**Matricule Compteur** (`MeterReference`) est un texte nullable : une saisie vide ou composée d'espaces est enregistrée en `null`, et les zéros initiaux sont conservés. Il devient obligatoire uniquement pour le motif **Renouvellement de branchement**. Le formulaire indique cette obligation dès le changement du motif ; le service la contrôle à l'enregistrement.

**Impact sur les transports** n'est plus proposé dans le formulaire. La colonne historique `ImpactTransport` reste conservée, consultable et exportable ; modifier les autres champs ne l'efface pas. Les listes et validations communes sont définies dans [services/request_model.py](services/request_model.py).

### Gérer les travaux

Le modèle suit cette hiérarchie :

```text
Demande (RequestReference)
├── Photos de la demande
└── Intervention(s) (WorkOrderReferenceEnrobEau)
    └── Prestation(s) (ServiceReference)
        └── Photos de la prestation
```

Une demande peut avoir plusieurs interventions ; une intervention peut avoir plusieurs prestations.

Dans **Gestion des dossiers**, sélectionner une demande, créer une intervention, puis cliquer sur **Créer une prestation**, à côté des actions de la demande. C'est l'unique point d'entrée de création d'une prestation. Choisir l'intervention concernée dans la fenêtre, à partir de sa référence SI SAUR. Ce bouton nécessite une intervention disponible ; les blocages des demandes et interventions en attente ou clôturées restent applicables. Les boutons Modifier et Supprimer sont alignés côte à côte dans les fiches d'intervention et de prestation.

La **référence d'intervention SI SAUR (`WorkOrderReferenceSaur`) est obligatoire, unique et modifiable après création**. Elle est saisie par l'utilisateur et affichée dans les fiches, la sélection d'intervention, les indicateurs et la carte. L'unicité est contrôlée à la création et à la modification, sans considérer la valeur de l'intervention en cours comme un doublon. Les espaces en début et fin sont retirés à l'enregistrement ; la comparaison reste sensible à la casse, comme auparavant.

Chaque intervention possède aussi un **identifiant technique stable (`WorkOrderReferenceEnrobEau`)**, généré automatiquement pour les nouvelles interventions. Les prestations sont liées par cet identifiant : modifier la référence SI SAUR ne change ni leur rattachement ni leur contenu. Les références de demande et de prestation restent automatiques. L'identifiant technique est disponible dans les exports, mais n'est pas présenté dans les fiches usuelles.

Les liens vers les fiches parentes sont renseignés automatiquement et ne sont plus modifiables après création. Les dates `CreatedAt` sont conservées lors des modifications ; `UpdatedAt` est actualisé.

Le fil d'avancement présente : **Demande → Intervention → Prestation → Réfection provisoire → Réfection définitive → Clôture**. Il synthétise les éléments liés au dossier. Une réfection définitive active les deux bulles de réfection, même en l'absence de réfection provisoire. La bulle Demande devient rouge avec une croix lorsque la demande est refusée. La dernière bulle indique la clôture de la demande.

Le formulaire d'intervention sépare la référence et le suivi de l'intervention, le **suivi de la DICT / de l'ATU**, l'information de la commune et celle des abonnés. `IssuedAt` et `ReceivedAt` correspondent à l'émission et à la réception de la DICT/ATU ; ces dates sont facultatives. Aucun formulaire métier ne demande d'heure : les dates saisies dans les champs horodatés sont enregistrées à `00:00:00`. Les dates techniques de création/modification conservent leur horodatage réel.

### Espace Réfection définitive

1. Filtrer le tableau par recherche, commune, statut et réfection **À réaliser / Réalisée**.
2. Choisir une prestation sous le tableau. Les références de la prestation, de l'intervention et de la demande permettent d'identifier le dossier.
3. Utiliser **Modifier la prestation** pour renseigner les travaux et leurs dates. Les règles métier et la clôture ascendante sont les mêmes que dans Gestion des dossiers.
4. Dans **Photos de la prestation**, ajouter, consulter, modifier ou supprimer les photos.
5. Dans **Photos de la demande · lecture seule**, ouvrir les photos du signalement initial, sans ajout, modification ni suppression.

La page présente toutes les prestations du prototype, sans affectation individuelle à un sous-traitant. Les binaires des photos restent chargés uniquement à l'ouverture d'une photo. L'URL est `refection-definitive` pour les profils internes ; il s'agit de la page racine pour l'agent externe. Le script reste nommé `pages/reporting.py`.

### Règles métier principales

| Élément | Règle |
| --- | --- |
| Statut de demande | À traiter, En cours, En attente, Refusée ou Clôturée. |
| Statut d'intervention | À planifier, En cours, En attente ou Clôturée. |
| Statut de prestation | À planifier, En cours, En attente ou Terminée. |
| Mise en attente ou refus d'une demande | Motif obligatoire, ajouté à `RequestComment`. |
| Demande en attente, refusée ou clôturée | Reprendre son traitement avant de créer de nouveaux travaux. Les éléments existants restent consultables et modifiables. |
| Intervention en attente ou clôturée | Réactiver l'intervention avant d'y ajouter une prestation. |
| Béton 2 cm / réfection provisoire : Oui | La date correspondante reprend automatiquement la date de remblaiement, qui doit être renseignée. |
| Béton 2 cm / réfection provisoire : Non | La date correspondante doit être saisie manuellement. « Non renseigné » permet de laisser l'information en attente. |
| Dates des travaux | Elles doivent respecter l'ordre chronologique contrôlé par le service métier. |
| Date de clôture d'intervention | La saisie d'une date fait automatiquement passer l'intervention à Clôturée. |
| Toutes les prestations terminées | L'intervention se clôture automatiquement, avec la date de dernière réfection définitive, à 00:00. Une intervention sans prestation ne se clôture pas par cette règle. |
| Toutes les interventions clôturées | La demande se clôture automatiquement. Une demande sans intervention ne se clôture pas par cette règle. Une décision Refusée est conservée. |
| Prestation terminée | Le statut et la date de réfection définitive doivent être renseignés ensemble. |
| Suppression d'une intervention | Possible seulement lorsqu'elle n'a plus de prestations ; la condition est revérifiée au moment de la suppression. |
| Suppression d'une prestation | Supprimer d'abord ses photos. |

Les changements de statut d'une demande ne changent pas automatiquement les statuts de ses interventions ou prestations. Les suppressions d'interventions et de prestations nécessitent une confirmation et conservent la demande parente. La suppression des demandes n'est pas proposée.

La clôture ascendante est recalculée lors de l'enregistrement ou de la suppression d'une intervention/prestation, sur le dossier concerné. Le statut final d'une prestation reste nommé **Terminée** dans le modèle. Les modifications des différents fichiers sont compensées si une écriture échoue ; elles ne constituent pas une transaction distribuée. La réouverture ne se propage pas automatiquement : les parents clôturés doivent être repris explicitement si de nouveaux travaux sont nécessaires.

## Photos

Les photos peuvent être associées aux demandes et aux prestations.

1. Cliquer sur **Ajouter une photo** pour ouvrir la fenêtre d'ajout.
2. Choisir **Document / galerie** ou **Appareil photo**.
3. Sélectionner plusieurs fichiers ou prendre des photos successives.
4. Donner un **nom obligatoire** à chaque photo. Les aperçus permettent de vérifier la sélection et de retirer une image.
5. Cliquer sur **Terminer** pour revenir au formulaire.
6. Pour une nouvelle fiche, enregistrer la demande ou la prestation. Pour une fiche existante, cliquer sur **Enregistrer les photos**.

**Terminer ne sauvegarde pas à lui seul les photos en base.** La sélection reste dans la session jusqu'à l'enregistrement. Lorsqu'un formulaire est déjà ouvert dans une fenêtre, cette même fenêtre accueille l'éditeur photo puis revient au formulaire.

Ce parcours est commun à Demandes et aux demandes/prestations de Gestion des dossiers. Les captures s'accumulent dans la sélection ; la caméra se réinitialise après chaque prise sans perdre les images précédentes ni les champs saisis. Le nom de chaque photo est obligatoire indépendamment du nom du fichier. Le lot est validé avant l'enregistrement de la fiche parente.

| Paramètre | Valeur actuelle |
| --- | --- |
| Formats | JPEG, PNG et WebP |
| Taille maximale | 15 Mo par photo |
| Nombre par ajout | Jusqu'à 20 photos, dont plusieurs captures successives |
| Stockage | Octets originaux en colonne `Content` de type BLOB, sans encodage Base64 |
| Traitement | Validation du contenu ; pas de compression ou de redimensionnement de l'original |

La liste affiche uniquement les métadonnées. **Ouvrir ↗** charge la photo sélectionnée dans un nouvel onglet avec possibilité de télécharger l'original. Les actions **Modifier** et **Supprimer** permettent de renommer la photo, changer sa légende, remplacer son fichier ou la supprimer après confirmation.

La visionneuse passe par `app.py`, qui réauthentifie l'utilisateur. Elle lit une seule image à partir de sa référence et de celle de son parent ; les liens depuis Demandes vérifient aussi le propriétaire de la demande. L'accueil et les exports métier ne chargent jamais les tables photos.

Les tables `PhotoDemande` et `PhotoPrestation` sont créées automatiquement au premier accès, à partir de [data/photos.sql](data/photos.sql). Elles sont initialement vides ; aucune photo d'exemple n'est livrée. Les anciennes bases sans `PhotoName` sont migrées automatiquement en reprenant le nom du fichier comme nom initial.

L'accès à la caméra dépend des autorisations du navigateur. Les essais sur les appareils utilisés sur le terrain restent nécessaires.

## Adresses, carte et exports

### Recherche d'adresse

La recherche d'adresse utilise le service IGN Géoplateforme depuis le navigateur, via `https://data.geopf.fr/geocodage/search`, dès trois caractères et après 350 ms sans frappe. Seul le texte de recherche d'adresse est envoyé au service, sans les autres champs du formulaire.

Une proposition sélectionnée renseigne `ReportedAdress`, `ReportedCity` et les coordonnées GPS seules dans `LocationLandmark` lorsqu'elles existent. Les coordonnées peuvent aussi être saisies librement ; aucun point remarquable voisin n'est inventé. Le mode **Autre / saisie libre** reste utilisable si le réseau ou le service est indisponible. Voir la [documentation du géocodage IGN](https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/geocodage/).

### Carte

La carte de l'accueil utilise les coordonnées des prestations (`WorkCoordinates`), puis celles de la demande si aucune position de prestation n'est disponible pour l'intervention. Seules les interventions en cours disposant d'une position valide sont cartographiées. Plusieurs interventions peuvent se superposer.

### Exports CSV

La page Export sélectionne les dossiers par recherche, commune, statut et période de demande. Les filtres se propagent aux interventions et prestations liées. Le choix des tables et des colonnes est indépendant pour chaque CSV.

Les exports produisent un CSV par table métier, avec les noms techniques des colonnes, un séparateur `;` et un encodage UTF-8 avec BOM pour Excel. L'aperçu est limité à 1 000 lignes par table, mais le téléchargement comprend toutes les lignes filtrées. Les textes susceptibles d'être interprétés comme des formules sont préfixés par une apostrophe dans le CSV, sans modifier les données sources. Les photos ne sont pas incluses dans les exports CSV.

Les choix multiples d'une demande sont exportés sous forme de tableau JSON dans chaque cellule CSV, par exemple `["Chaussée", "Trottoir"]`, pour conserver toutes les valeurs sans ambiguïté. `MeterReference` et `ReportedRoadTypeOther` font partie des colonnes sélectionnables. Les fiches de consultation affichent les choix multiples séparés par des virgules. Le préremplissage d'une prestation les reprend également comme texte, sans changer le modèle de la prestation.

## Identification et droits

[app.py](app.py) récupère l'e-mail transmis dans l'en-tête `X-Forwarded-Email`, puis recherche le compte dans la table d'administration. L'accès nécessite un compte actif avec l'un des profils suivants :

| Profil stocké | Page à l'ouverture | Accès |
| --- | --- | --- |
| `agent` | Demandes | Toutes les pages métier, sans Administration. |
| `ordonnanceur` | Accueil | Toutes les pages, sauf Administration. |
| `agent externe` | Réfection définitive | Uniquement Réfection définitive et la consultation des photos associées. Modification des prestations et gestion de leurs photos ; photos des demandes en lecture seule. |
| `administrateur` | Accueil | Toutes les pages, y compris Administration. |

Le rôle `collectivité` est supprimé. **Les comptes existants portant ce rôle doivent être réaffectés par un administrateur** ; ils ne sont pas automatiquement convertis en agents externes. Pour créer un compte sous-traitant, choisir **Agent externe** dans Administration (valeur stockée : `agent externe`).

La politique commune de [services/access_service.py](services/access_service.py) contrôle le menu et l'accès direct aux pages. L'agent conserve ses accès métier mais arrive directement dans la page Demandes. Le filtrage de la page Demandes limite cette page aux demandes du compte connecté ; Gestion des dossiers et Export ne sont pas limités à ses propres demandes.

Un e-mail absent, un compte inconnu ou inactif ou un profil non reconnu bloque l'accès. Les e-mails dupliqués dans la table d'administration sont également refusés, sans déclencher le secours.

### Mode dégradé temporaire de l'administration

Une exception technique pendant la récupération du profil Databricks active automatiquement le stockage local pour la session. Un bandeau **Mode dégradé temporaire** indique cette bascule. Les lectures, créations, modifications, activations/désactivations et suppressions des comptes utilisent alors `data/exemples/administration.sqlite3`, avec les mêmes formulaires et validations. L'erreur initiale est journalisée côté serveur.

La base est créée au premier accès avec un seul compte actif : **Erwan Pasquiou**, **erwan.pasquiou@saur.com**, profil **administrateur**. Ce compte n'est pas recréé après sa modification ou sa suppression. Les autres identités doivent correspondre à un compte local actif ; elles ne récupèrent pas les droits du compte initial. L'en-tête d'identité Databricks reste obligatoire.

Le mode reste local pendant toute la session, même si Databricks redevient disponible, pour éviter de mélanger les deux jeux de comptes. Une nouvelle session (ou un changement d'identité) tente à nouveau Databricks. Les comptes locaux sont partagés par les sessions dégradées de la même instance et conservés sur disque ; leur persistance après redéploiement n'est pas garantie. **Aucune synchronisation ni écriture des comptes locaux vers Databricks n'est effectuée.** Une erreur d'écriture locale est affichée sans changement de stockage.

Pour retirer ce contournement : supprimer la branche de secours dans `services/auth_service.py`, le routage local dans `_get_table_name()` et `get_connection()` de `services/administration_service.py`, le bandeau dans `app.py` et le module `services/administration_fallback.py`. La base locale peut ensuite être archivée ou supprimée. Les données métier JSON et les photos restent indépendantes de ce mécanisme.

## Installation et lancement

### Environnement Python

Le projet a été vérifié avec **Python 3.11**. Les dépendances sont décrites dans [requirements.txt](requirements.txt), notamment Streamlit 1.38, Pandas, Pillow et les connecteurs Databricks. SQLite et `unittest` font partie de la bibliothèque standard Python.

Depuis la racine du projet, pour une première installation sous Windows PowerShell :

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Si un environnement existe déjà, utiliser son interpréteur sans le recréer. Dans PyCharm, sélectionner l'interpréteur configuré pour le projet.

**Le lancement local seul ne permet pas de se connecter.** Sans l'en-tête d'identité fourni par Databricks Apps, l'application affiche « Identification impossible ». Aucun mode de connexion fictive n'est intégré à `app.py`. Les tests locaux simulent les sessions nécessaires sans modifier l'authentification de l'application.

### Configuration prévue pour Databricks Apps

[app.yaml](app.yaml) définit la commande `streamlit run app.py` et les paramètres suivants :

| Variable | Source dans `app.yaml` | Utilisation |
| --- | --- | --- |
| `DATABRICKS_WAREHOUSE_ID` | Ressource `sql-warehouse` | Identifiant du SQL Warehouse utilisé pour l'administration. |
| `ADMINISTRATION_TABLE` | Ressource `administration_table` | Nom complet de la table : `catalogue.schema.table`. |
| `STREAMLIT_GATHER_USAGE_STATS` | Valeur `false` | Désactivation des statistiques d'usage Streamlit. |

Avant de démarrer l'application dans l'environnement cible :

1. Associer les ressources référencées par `app.yaml` et vérifier les valeurs injectées.
2. Préparer la table d'administration. Le code attend les colonnes `id`, `nom`, `prenom`, `email`, `profil`, `actif` et `date_creation`.
3. Prévoir la génération de `id` et la valeur de `date_creation` dans la table : les insertions de l'application ne fournissent pas ces deux champs.
4. Donner à l'identité de l'application l'accès au SQL Warehouse et les droits nécessaires pour lire et modifier cette table.
5. Préparer un premier compte administrateur actif correspondant à l'e-mail professionnel utilisé pour ouvrir l'application.
6. Inclure les dossiers `assets`, `styles`, `components`, `services`, `pages`, `data` et `.streamlit` avec les sources déployées.

L'application utilise `databricks.sdk.core.Config()` pour les informations de connexion et l'authentification du connecteur SQL. Elle ne crée ni la table d'administration ni le premier administrateur dans Databricks. Le compte initial du mode dégradé existe uniquement dans la base SQLite locale.

Le fichier [manifest.yaml](manifest.yaml) contient encore les métadonnées du modèle initial (« Hello world »). Le lancement est décrit dans `app.yaml`.

## Données et stockage

### Fichiers métier et relations

Les trois fichiers JSON de [data/exemples/](data/exemples/) contiennent les données métier du prototype :

| Fichier | Entité du modèle | Référence unique | Lien vers le parent |
| --- | --- | --- | --- |
| [demandes.json](data/exemples/demandes.json) | REQUEST | `RequestReference` | — |
| [interventions.json](data/exemples/interventions.json) | WorkOrderEnrobEau | `WorkOrderReferenceEnrobEau` | `RequestReference` |
| [prestations.json](data/exemples/prestations.json) | Service | `ServiceReference` | `WorkOrderReferenceEnrobEau` |

`WorkOrderReferenceSaur` appartient uniquement aux interventions. Les écrans de prestations la retrouvent par jointure en mémoire ; elle n'est pas dupliquée dans `prestations.json` ni ajoutée au schéma CSV des prestations. Le modèle local issu du schéma cible de CODEX-001 intègre les évolutions du formulaire Demande de CODEX-003 décrites ci-dessous. Les sources `datapf_prod_featured.core...` restent hors périmètre : aucune connexion ni synchronisation métier n'est implémentée.

Le jeu d'exemple comprend 12 demandes et illustre des demandes sans intervention, plusieurs interventions pour une demande et plusieurs prestations pour une intervention. Les liens sont vérifiés au chargement. Les statuts présents dans les exemples illustrent le prototype ; les règles applicables sont décrites dans la section [Règles métier principales](#règles-métier-principales).

Le chargement général couvre uniquement ces trois tables. Les photos sont lues séparément à la demande et l'entité `Permit` n'est pas chargée. Les dossiers et les exports n'utilisent aucune connexion Databricks. Les comptes suivent le fonctionnement décrit dans [Identification et droits](#identification-et-droits).

### Formats et conventions

Chaque enregistrement contient les champs définis dans [services/data_model.py](services/data_model.py). Les fichiers sont encodés en UTF-8 et respectent les conventions suivantes :

| Élément | Convention |
| --- | --- |
| Références | Chaînes de caractères uniques. |
| Dates | ISO `AAAA-MM-JJ`. |
| Horodatages | ISO `AAAA-MM-JJTHH:MM:SS` ; dates métier saisies à minuit, horodatages techniques réels. |
| Valeurs absentes | `null`. |
| Booléens | `true` ou `false`. |
| Adresse signalée | `ReportedAdress` conserve volontairement l'orthographe du modèle existant. |
| Demandeur | `RequesterReference` contient l'e-mail du compte connecté à la création ; `RequestReference` identifie le dossier. |
| Choix multiples de la Demande | `ReportedRoadType`, `ReportedSurfaceType`, `RoadImpact` : tableaux JSON de chaînes pour les nouveaux enregistrements. |
| DICT / ATU et coupure d'eau | `DictAtuIndicator` et `WaterShutdownIndicator` : chaînes choisies dans les listes CODEX-003. |
| Matricule Compteur et précision de voirie | `MeterReference` et `ReportedRoadTypeOther` : texte ou `null`. |
| Coordonnées des prestations | `WorkCoordinates` contient une chaîne `latitude,longitude` dans les exemples. |

### Compatibilité des anciennes demandes — CODEX-003

Aucune migration destructive ni réécriture au chargement n'est nécessaire. Le lecteur complète en mémoire les champs `MeterReference` et `ReportedRoadTypeOther` absents avec `null`, et transforme les anciens textes de voirie/revêtement/impact en tableaux contenant le texte original, sans découpage ni interprétation métier.

Les anciens booléens de `RoadImpact` et `WaterShutdownIndicator`, ainsi que les anciens libellés hors référentiel, restent lisibles et conservés. Par exemple, `Communale`, `Eau potable`, `ATU` ou une coupure d'eau à `true` ne permettent pas de déduire les nouveaux choix : aucune conversion métier automatique n'est appliquée. À l'édition, le formulaire affiche la valeur historique à requalifier et ne propose que les nouvelles listes ; l'utilisateur doit compléter les champs obligatoires avant d'enregistrer. Une ancienne demande sans compteur reste chargeable, même si son motif impose désormais ce champ à l'enregistrement du formulaire.

Les données d'exemple historiques sont conservées sur disque pour illustrer cette compatibilité. Lors d'une écriture de `demandes.json`, les champs complétés en mémoire et les tableaux sont sérialisés avec la table ; les anciennes valeurs des autres demandes restent conservées, avec leurs références, dates, statuts et liens. Les interventions et les photos ne sont pas migrées par CODEX-003. Le changement de statut seul reste utilisable sur les anciennes demandes : il ne permet de modifier que le statut et son commentaire, sans contourner les validations d'un formulaire complet.

Après déploiement, rouvrir les formulaires des sessions déjà actives. Les copies locales restent à sauvegarder selon les limites de persistance du prototype.

### Écritures et concurrence

Les formulaires enregistrent directement les changements dans les JSON. Pour ajuster les données d'essai, il est aussi possible de modifier les fichiers puis d'actualiser la page, en conservant les champs et les relations attendus.

Les écritures remplacent atomiquement le fichier de la table concernée. Une modification est refusée si la fiche a changé depuis l'ouverture du formulaire. Le verrou protège les sessions d'un même processus ; il ne coordonne pas plusieurs serveurs. Les compensations en cas d'échec et les limites de persistance sont détaillées dans [Limites et points de vigilance](#limites-et-points-de-vigilance).

### Migration des anciens JSON — CODEX-001

Les fichiers d'exemple livrés sont déjà au nouveau modèle : 12 demandes, 9 interventions et 9 prestations. La procédure ci-dessous concerne les autres copies locales encore basées sur l'ancien modèle.

Le chargement refuse les anciens fichiers contenant `WorkOrderReference` avec un message indiquant la migration à effectuer. Il ne réécrit pas les données implicitement. L'outil [services/local_model_migration.py](services/local_model_migration.py) vérifie les trois tables avant toute écriture et refuse les clés vides ou dupliquées, les parents inexistants, les colonnes inattendues et les mélanges de versions.

Pour un ancien jeu de données, **arrêter l'application et toute édition des JSON**, puis utiliser l'interpréteur du projet depuis la racine :

```powershell
# Vérification seule, sans écriture
.\.venv\Scripts\python.exe -m services.local_model_migration
# Sauvegarde et application
.\.venv\Scripts\python.exe -m services.local_model_migration --apply
```

L'option `--data-dir "chemin/vers/les/json"` permet de traiter un autre dossier. La migration :

1. conserve l'ancienne valeur `WorkOrderReference` dans `WorkOrderReferenceEnrobEau` et dans `WorkOrderReferenceSaur` pour chaque intervention ; ces champs sont indépendants, même si leurs valeurs initiales sont identiques ;
2. renomme la clé de rattachement des prestations en `WorkOrderReferenceEnrobEau`, sans changer sa valeur ;
3. conserve les demandes, références de prestations, dates, statuts et autres valeurs métier ;
4. sauvegarde les trois JSON originaux dans `data/exemples/backups/CODEX-001-<horodatage>/`, puis écrit uniquement les tables modifiées.

Une seconde exécution sur un jeu déjà migré est sans effet. Les écritures sont atomiques par fichier et compensées en cas d'erreur ; elles ne forment pas une transaction entre fichiers. En cas d'interruption ou d'échec, vérifier les trois JSON et, si nécessaire, restaurer ensemble les originaux depuis la sauvegarde avant de relancer la migration et l'application. Les bases SQLite ne sont pas modifiées : les références des demandes et des prestations utilisées par les photos sont conservées. Les sessions déjà ouvertes doivent être recréées après cette évolution du modèle.

La migration ne complète pas les informations métier manquantes et ne corrige pas les dates ou statuts des exemples. Les validations des formulaires restent applicables lorsqu'une fiche existante est enregistrée.

### Structure des photos

Le schéma [data/photos.sql](data/photos.sql) définit `PhotoDemande`, liée par `RequestReference`, et `PhotoPrestation`, liée par `ServiceReference`. Chaque table contient les champs suivants, en plus de la référence du parent :

| Champs | Contenu |
| --- | --- |
| `PhotoReference` | Identifiant unique de la photo. |
| `PhotoName` | Nom obligatoire donné par l'utilisateur. |
| `FileName`, `MimeType`, `SizeBytes` | Nom du fichier, type et taille. |
| `Content` | Octets originaux dans un BLOB, sans Base64. |
| `Caption`, `CreatedBy` | Légende et auteur. |
| `CreatedAt`, `UpdatedAt`, `Version` | Suivi des modifications et détection des changements concurrents. |

La base `data/exemples/photos.sqlite3` est générée au premier accès et exclue de Git. Ce sont des tables SQLite locales, pas des tables Delta Databricks. Un futur branchement Databricks devra conserver les filtres par référence et la séparation des requêtes de métadonnées et de contenu binaire. Le parcours d'ajout, de consultation et de modification est décrit dans [Photos](#photos).

### Comptes locaux de secours

La base `data/exemples/administration.sqlite3` est indépendante des JSON et de la base photos. Elle est générée à la première utilisation du secours et exclue de Git. Son initialisation, ses règles d'accès et sa suppression future sont décrites dans [Mode dégradé temporaire de l'administration](#mode-dégradé-temporaire-de-ladministration).

## Organisation du code

```text
app.py                         Point d'entrée, identité et navigation
app.yaml                       Commande et paramètres Databricks Apps
requirements.txt               Dépendances Python
.streamlit/config.toml         Thème Streamlit
pages/                         Écrans de l'application
components/                    Formulaires, photos, adresses, en-tête et vues communes
components/address_picker/     Composant navigateur de recherche d'adresse
services/                      Accès aux données, validations et écritures
styles/                        Feuilles CSS globales et par page
assets/                        Logo, bannière et fond graphique
data/exemples/                 Données métier JSON et bases SQLite générées à l'usage
data/photos.sql                Schéma des deux tables photos SQLite
README.md                      Documentation de l'application et de ses données
tests/                        Tests métier et interactions Streamlit
Modif.md                       Notes de modifications demandées
```

Points d'entrée utiles pour la maintenance :

- [services/data_model.py](services/data_model.py) : colonnes métier, libellés et types de champs.
- [services/request_model.py](services/request_model.py) : listes CODEX-003, adaptation à la lecture et validations de la Demande.
- [components/request_form.py](components/request_form.py) : les cinq sections du formulaire et ses champs conditionnels.
- [services/business_data_service.py](services/business_data_service.py) : chargement des JSON, liens, filtres et exports.
- [services/dossier_edit_service.py](services/dossier_edit_service.py) : création, validation, modification et suppression des fiches.
- [services/local_model_migration.py](services/local_model_migration.py) : vérification, sauvegarde et migration explicite des anciens JSON pour CODEX-001.
- [services/photo_service.py](services/photo_service.py) : stockage binaire, validation et contrôle de version des photos.
- [services/auth_service.py](services/auth_service.py) et [services/administration_service.py](services/administration_service.py) : identité et comptes Databricks.
- [services/administration_fallback.py](services/administration_fallback.py) : stockage SQLite temporaire des comptes en mode dégradé.
- [components/photos.py](components/photos.py) : fenêtre d'ajout et actions sur les photos.

## Tests

Depuis la racine, avec les dépendances installées :

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La suite couvre notamment les filtres, les exports, les relations entre fiches, les validations de dates, les modifications concurrentes, la page Demandes, les opérations photos, le chargement des images à la demande et le CRUD de l'administration en mode dégradé. Les tests CODEX-001 vérifient également la migration, l'unicité et la modification de la référence SI SAUR, la stabilité des rattachements et le parcours unique de création des prestations.

Les tests de photos génèrent leurs images en mémoire et utilisent des dossiers temporaires. Ils ne déposent pas d'images d'exemple dans l'application. Les tests d'interface utilisent `streamlit.testing.v1.AppTest` ; ils ne remplacent pas une vérification du rendu et de la caméra sur un navigateur réel.

Les tests CODEX-003 couvrent les listes et obligations, la précision « Autre », le compteur conditionnel, la persistance des choix multiples, la lecture des anciens JSON, les exports, les liens et photos, la concurrence, les cinq sections, le géocodage simulé et la conservation des saisies au retour de l'éditeur photo. Les tests de widgets créant des brouillons utilisent un stockage temporaire pour ne pas consommer les compteurs du projet.

## Limites et points de vigilance

- **Persistance** : JSON et SQLite sont locaux. Un stockage durable est à mettre en place avant un usage de production.
- **Concurrence** : les écritures JSON sont atomiques au niveau du fichier et protégées par un verrou dans le processus. Ce mécanisme ne constitue pas une gestion distribuée entre plusieurs instances.
- **Enregistrement fiche + photos** : une erreur d'écriture des photos déclenche une restauration de la fiche JSON. Cela ne remplace pas une transaction commune aux deux stockages en cas d'arrêt brutal.
- **Chargement** : les données métier JSON sont chargées en mémoire. Les binaires photos sont lus séparément, à la consultation d'une image.
- **Périmètre** : les données métier ne sont pas encore connectées à des tables Databricks. L'espace Réfection définitive partage toutes les prestations avec les agents externes ; aucune affectation par entreprise ou par utilisateur n'est encore définie.

## Dépannage

| Symptôme | Vérifications |
| --- | --- |
| « Identification impossible » | Ouvrir l'application depuis Databricks Apps avec le compte professionnel ; vérifier la transmission de l'identité. |
| Accès refusé | Vérifier l'e-mail, l'état actif et le profil dans la table d'administration. |
| Service de vérification des accès indisponible | Vérifier le Warehouse, les variables de configuration, les droits d'accès et l'absence de comptes dupliqués. |
| Mode dégradé temporaire | La récupération du profil Databricks a échoué. Les comptes utilisent SQLite ; consulter les journaux serveur pour la cause initiale. Après réparation, ouvrir une nouvelle session pour retenter Databricks. |
| Aucune demande dans la page Demandes | Vérifier que `RequesterReference` correspond à l'e-mail connecté et retirer les éventuels filtres. |
| Données d'exemple impossibles à charger | Vérifier la présence des trois JSON, leur structure et leurs références parent/enfant. |
| Ancien modèle local détecté | Arrêter l'application et appliquer la migration CODEX-001 décrite ci-dessus, après vérification des données. |
| Photo impossible à enregistrer | Vérifier le nom obligatoire, le format, la taille, le nombre de photos et les droits d'écriture dans `data/exemples/`. |
| Caméra indisponible | Vérifier les autorisations du navigateur et du système pour le site de l'application. |
| Fiche ou photo modifiée par ailleurs | Fermer puis rouvrir la fiche ou actualiser la liste avant de recommencer. |
