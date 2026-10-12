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

## Décisions de cette première itération

Le fichier existant **`pages/reporting.py` correspond à Réfection définitive**.
Le nouveau Reporting utilise donc `pages/reporting_collectivite.py`, une clé
de navigation `reporting` et l’URL `/reporting`. Son accès suit les profils internes.

La page comporte cinq sous-onglets conformes au visuel : Vue d’ensemble,
Performance, Dossiers, Photos et Export. La Vue d’ensemble est implémentée ;
les quatre autres restent des emplacements pour les prochaines itérations.

Le scénario fictif est centralisé dans `services/reporting_demo_service.py`.
Les composants HTML/SVG sont dans `components/reporting.py` et la présentation
adaptative dans `styles/reporting.css`. Aucune bibliothèque supplémentaire n’est
nécessaire. Le reporting ne charge pas les JSON métier ni les bases SQLite,
ce qui évite de mélanger les indicateurs de démonstration avec les dossiers saisis.

Les KPI, les répartitions et les séries utilisent une seule cohorte filtrée par
commune et date de création. Le scénario est figé au 7 octobre 2026 pour conserver
des échéances et des résultats reproductibles. Les périodes comprennent le mois
courant partiel. Les définitions de conformité, délais et échéances devront être
validées avant le raccordement aux données métier.

## Différences explicites avec le visuel

- L’en-tête et l’identité graphique restent ceux du projet existant.
- Les volumes mensuels sont calculés à partir des 13 dossiers : les totaux restent
  cohérents avec les KPI, contrairement à une reprise indépendante des barres du visuel.
- Les variations de période ne sont pas affichées : aucune base comparative
  n’est encore définie.
- La carte est un schéma local, avec des positions indicatives, sans fond géographique distant.
- Les six vignettes sont des illustrations SVG de chantier, identifiées comme telles.
- Les quatre futurs sous-onglets indiquent leur état ; aucun bouton ne prétend
  ouvrir un détail ou exporter un bilan qui n’existe pas encore.

## Vérifications et limites de validation

`tests/test_reporting.py` couvre la cohérence des agrégations pour chaque filtre,
les échéances, la sélection vide, les contrôles d’accès et le chargement Streamlit
sans accès aux données métier. `tests/test_refection_access.py` prend en compte
la nouvelle page dans les permissions internes et les refus d’accès externe.

Le contrôle `git diff --check` ne signale aucune erreur d’espacement. Les
inspections PyCharm ne signalent pas d’erreur dans le service de démonstration,
les composants HTML/SVG ou le CSS. Elles signalent des imports Streamlit non
résolus dans la page et les tests.

**Les tests et la vérification navigateur ne sont pas exécutés** : le SDK déclaré
par PyCharm pointe vers `E:/EnrobEau/.venv/Scripts/python.exe`, absent dans cet
environnement. Le répertoire du projet est `E:/EnrobEau_dev` et contient un
environnement `.venv`. Il reste à corriger le SDK du projet avant de lancer la
suite et de valider le rendu dans la session authentifiée.
