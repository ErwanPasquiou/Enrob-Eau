# Analyse du projet et intégration du Reporting

## Statut de cette description

Au cadrage du 15 octobre 2026, le Reporting reste un support exploratoire de présentation : aucun périmètre ni indicateur définitif n'est arrêté. Ce document décrit l'implémentation actuelle et ne vaut pas validation métier des évolutions futures. Le [README](README.md) distingue le fonctionnement actuel du cadrage cible.

## Architecture existante

Enrob’Eau est une application Python / Streamlit 1.38 destinée à Databricks Apps.
`app.py` charge le thème et le fond, récupère l’identité, vérifie le compte et son
profil, puis construit les pages autorisées avec `st.navigation`. Le menu HTML
de `components/header.py` utilise la même liste `PAGES` que le routeur.

| Couche | Responsabilité et fichiers principaux |
| --- | --- |
| Écrans | `pages/accueil.py`, `forms.py`, `gestion_des_dossiers.py`, `reporting.py`, `export.py`, `administration.py` |
| Composants | En-tête et fond communs, formulaire Demande, formulaires de dossier, recherche d’adresse, consultation et édition des photos |
| Modèle | `services/data_model.py` définit les colonnes, libellés, dates et booléens ; `request_model.py` porte les listes et validations du formulaire Demande |
| Services métier | `business_data_service.py` lit et filtre les données ; `dossier_edit_service.py` contrôle et enregistre les changements ; `home_service.py` et `refection_service.py` préparent les vues |
| Présentation | `styles/main.css`, `header.css` et feuilles propres aux écrans ; assets locaux pour logo, bannière et vagues |
| Déploiement | `app.yaml`, `.streamlit/config.toml`, `requirements.txt` ; `manifest.yaml` conserve les métadonnées initiales |
| Vérifications | `unittest` pour les services et `streamlit.testing.v1.AppTest` pour les interactions |

## Données, droits et contraintes

Le modèle relie une **Demande** à plusieurs **Interventions**, puis une intervention
à plusieurs **Prestations**. Les trois tables métier sont stockées dans les JSON
de `data/exemples/`. Les photos des demandes et des prestations sont dans une base
SQLite distincte, avec chargement des binaires à la consultation. L’administration
utilise Databricks SQL avec un secours SQLite temporaire. Le reporting métier
Databricks n’existe pas encore. Seule la table d'administration est réelle dans Databricks ; les autres tables sont prévues après le GO projet. Le secours SQLite est destiné au développement uniquement, mais le code actuel n'impose pas encore cette restriction par une garde d'environnement.

Les références locales sont gérées par un service dédié. La référence SI SAUR est
modifiable, tandis que l’identifiant Enrob’Eau préserve les rattachements. Les
écritures JSON utilisent un verrou de processus, un remplacement atomique et un
contrôle des versions ; les mises à jour sur plusieurs fichiers sont compensées
en cas d’erreur. Ce fonctionnement ne garantit pas une transaction distribuée
ou une persistance après redéploiement.

Les profils reconnus sont `agent`, `ordonnanceur`, `agent externe` et
`administrateur`. Les agents externes accèdent uniquement à Réfection définitive.
Le nom « Reporting collectivité » ne crée pas de nouveau profil : le rôle
historique `collectivité` n’est plus reconnu. Les droits sont contrôlés par
`services/access_service.py`, aussi bien pour le menu que pour chaque page.

La cible communiquée prévoit un accès collectivité limité au Reporting et un accès agent limité à Demandes. Cette cible reste à implémenter dans un lot dédié ; les règles détaillées seront précisées ultérieurement. Les autres orientations sont : administrateur partout, ordonnanceur partout sauf Administration, agent externe uniquement dans Réfection définitive.

Le formulaire Demande comprend cinq sections sur une page, des listes métier,
des choix multiples, un compteur conditionnel et la compatibilité des données
historiques. Ces comportements sont décrits dans le README ; l'ancien document
de lot CODEX-003 a été retiré avec les autres documents de lots historiques.
L’ajout du Reporting ne nécessite aucune nouvelle migration de ces données.

## Reporting raccordé aux données de l’application

La route `/reporting` utilise `pages/reporting_collectivite.py` et reste accessible
aux profils internes. La Réfection définitive conserve son fichier `pages/reporting.py`.
Les cinq sous-onglets sont conservés ; seule la Vue d’ensemble est construite.

`services/reporting_service.py` reçoit le même `load_store()` que les autres pages.
Il sélectionne les demandes par `RequestDate` et `ReportedCity`, rattache les
interventions par `RequestReference`, puis les prestations par
`WorkOrderReferenceEnrobEau`. Chaque indicateur conserve le niveau de sa table.
Le scénario indépendant de la première version a été supprimé.

Les périodes glissantes couvrent 12, 6, 3 ou 1 mois, ainsi que les 7 derniers jours.
La date de référence est celle du serveur à chaque exécution. Le README décrit
les formules et règles de filtrage de chacun des cinq KPI.

La conformité des données utilise les validations existantes des fiches, notamment
celles du formulaire Demande. Elle ne mesure pas la qualité physique des travaux et ne modifie pas les
fiches historiques. Les dossiers ayant des données à compléter sont consultables
avec les motifs des validations échouées.

Les graphiques et icônes de `components/reporting.py` sont des images SVG encodées,
avec espace de noms et styles embarqués. La carte est un composant PyDeck natif
identique dans son principe à celui de l’accueil : positions enregistrées,
regroupement des points superposés, fond Carto et compteur de demandes non localisées.
Les photos sont lues depuis les tables SQLite existantes, en limitant les binaires
aux six dernières photos affichées. Aucune illustration ou échéance inventée ne
subsiste. Les styles sont limités à la page Reporting dans `styles/reporting.css`.

## Vérifications

`tests/test_reporting.py` couvre les jointures, la conservation des niveaux de
comptage avec plusieurs enfants, les périodes glissantes et les sélections vides,
les SVG encodés, les nouveaux filtres Streamlit et le refus des accès non autorisés.
Les tests d’accès à Réfection définitive restent applicables.

La suite automatisée a été exécutée le 15 octobre 2026 sous Windows avec Python
3.11.9 : 101 tests réussis. La commande de référence et les limites des tests
Streamlit sont décrites dans le README. Le rendu navigateur, la caméra sur les
appareils terrain et l'intégration réelle Databricks restent à vérifier.
