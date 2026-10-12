# Analyse du projet et intégration du Reporting

## Architecture existante

Enrob’Eau est une application Python / Streamlit 1.38 destinée à Databricks Apps.
`app.py` charge le thème et le fond, récupère l’identité, vérifie le compte et son
profil, puis construit les pages autorisées avec `st.navigation`. Le menu HTML
de `components/header.py` utilise la même liste `PAGES` que le routeur.

| Couche | Responsabilité et fichiers principaux |
| --- | --- |
| Écrans | `pages/accueil.py`, `forms.py`, `gestion_des_dossiers.py`, `reporting.py`, `export.py`, `administration.py` |
| Composants | En-tête et fond communs, formulaire Demande, formulaires de dossier, recherche d’adresse, consultation et édition des photos |
| Modèle | `services/data_model.py` définit les colonnes, libellés, dates et booléens ; `request_model.py` porte les listes et validations CODEX-003 |
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
Databricks n’existe pas encore.

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

Le document CODEX-003 concerne le formulaire Demande : cinq sections sur une
page, listes métier, choix multiples, compteur conditionnel, compatibilité des
données historiques. Le README et le code ont déjà intégré ces évolutions.
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
CODEX-003. Elle ne mesure pas la qualité physique des travaux et ne modifie pas les
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

Les inspections statiques sont effectuées dans PyCharm. Le SDK déclaré pointe
encore vers `E:/EnrobEau/.venv/Scripts/python.exe`, absent dans cet environnement,
alors que le projet est dans `E:/EnrobEau_dev`. Les tests automatisés et le rendu
navigateur restent à exécuter avec un interpréteur et une session fonctionnels.