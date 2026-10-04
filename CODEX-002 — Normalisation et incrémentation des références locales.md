# CODEX-002 — Normalisation et incrémentation des références locales

## Objectif

Mettre en œuvre `ENR-004` dans le fonctionnement local actuel d’Enrob’Eau.

L’objectif est de normaliser les références générées automatiquement pour les principales entités métier et de mettre en place une incrémentation fiable et indépendante pour chaque type d’entité.

Le lot doit rester entièrement local.

Aucune connexion aux futures tables métier Databricks ne doit être ajoutée dans cette étape.

## Contexte actuel

Enrob’Eau fonctionne actuellement avec des données métier locales.

Le modèle métier suit la hiérarchie :

`Demande → Intervention → Prestation`

Le précédent lot `CODEX-001` a notamment introduit la distinction entre :

- `WorkOrderReferenceEnrobEau` : identifiant technique stable d’une intervention ;
- `WorkOrderReferenceSaur` : référence métier SI SAUR, distincte et modifiable.

Ce lot doit conserver cette séparation.

Les nouvelles références automatiques doivent être cohérentes avec ce modèle.

## Demande incluse

- `ENR-004` — Normaliser et incrémenter les références des entités métier

## Références concernées

Les références générées automatiquement doivent respecter les formats suivants.

### Demande

Champ :

`RequestReference`

Format :

`DEM-000001`

Puis :

`DEM-000002`

`DEM-000003`

etc.

### Intervention Enrob’Eau

Champ :

`WorkOrderReferenceEnrobEau`

Format :

`INT-000001`

Puis :

`INT-000002`

`INT-000003`

etc.

### Prestation

Champ :

`ServiceReference`

Format :

`PR-000001`

Puis :

`PR-000002`

`PR-000003`

etc.

## Format commun

Chaque référence automatique respecte :

`PREFIXE-NNNNNN`

avec :

- préfixe fixe propre à l’entité ;
- tiret séparateur ;
- séquence numérique sur 6 chiffres ;
- remplissage avec des zéros à gauche.

Exemples :

- `DEM-000001`
- `INT-000027`
- `PR-001254`

## Séquences

Les séquences sont indépendantes.

Il doit donc exister conceptuellement trois compteurs distincts :

- demandes ;
- interventions ;
- prestations.

L’incrémentation d’une demande ne doit pas modifier le compteur des interventions ou prestations.

## Valeur initiale

Une séquence vide commence à :

`000001`

## Unicité

Chaque référence doit être unique dans son propre type d’entité.

Le mécanisme doit empêcher la génération d’une référence déjà existante.

La logique ne doit pas reposer uniquement sur le nombre d’éléments actuellement présents.

Par exemple, la présence de :

- `DEM-000001`
- `DEM-000003`

ne doit pas entraîner la création de `DEM-000003`.

Le prochain numéro cohérent doit être déterminé selon la stratégie retenue après analyse du stockage local existant.

## Non-réutilisation des références

Une référence déjà attribuée ne doit pas être réutilisée.

Le système ne doit pas recycler volontairement les anciennes références.

Si des données historiques sont retirées ou deviennent inactives selon le fonctionnement du projet, cela ne doit pas faire revenir le compteur en arrière.

## Référence SI SAUR

`WorkOrderReferenceSaur` est explicitement hors du mécanisme de génération automatique.

Elle reste :

- saisie manuellement ;
- obligatoire ;
- unique ;
- modifiable.

Ne pas lui appliquer de format automatique `INT-xxxxxx`.

## Identité technique de l’intervention

`WorkOrderReferenceEnrobEau` reste l’identifiant technique stable de l’intervention.

La génération automatique doit produire cet identifiant à la création.

Une modification de `WorkOrderReferenceSaur` ne doit jamais provoquer la régénération ou la modification de `WorkOrderReferenceEnrobEau`.

## Données locales existantes

Commencer par analyser les données locales actuellement présentes.

Identifier notamment :

- les références actuelles des demandes ;
- les références actuelles des interventions ;
- les références actuelles des prestations ;
- les relations entre les entités ;
- les références utilisées dans les données photos ;
- les éventuels formats hérités.

## Migration / mise en conformité

Si les références locales existantes ne respectent pas encore les nouveaux formats, adapter les données de manière cohérente.

La migration doit préserver :

- chaque demande ;
- chaque intervention ;
- chaque prestation ;
- la relation demande → intervention ;
- la relation intervention → prestation ;
- les relations avec les photos ;
- les autres références fonctionnelles existantes.

Ne pas effectuer de migration partielle laissant des références incohérentes entre fichiers.

## Relations à préserver

La relation Demande → Intervention repose sur :

`RequestReference`

La relation Intervention → Prestation repose sur :

`WorkOrderReferenceEnrobEau`

Les photos liées aux demandes ou prestations doivent continuer à pointer vers les bonnes entités après une éventuelle adaptation des références.

Analyser les services photo et les données correspondantes avant de modifier les identifiants.

## Gestion des compteurs en local

Le projet fonctionne actuellement avec des données locales.

Mettre en place un mécanisme local suffisamment robuste pour conserver l’état des séquences.

Le choix précis de l’implémentation est laissé à Codex après analyse du dépôt.

Le mécanisme doit néanmoins :

- être centralisé ;
- éviter la duplication de logique entre formulaires ou services ;
- produire une référence unique ;
- conserver la progression entre deux créations ;
- résister à la présence de trous dans les références ;
- être compatible avec le fonctionnement local actuel ;
- rester simple et maintenable.

Éviter une sur-ingénierie destinée à anticiper dès maintenant Databricks.

## Concurrence

Analyser les protections déjà présentes pour les écritures locales.

Le mécanisme de génération ne doit pas introduire une régression évidente permettant à deux créations concurrentes dans le même environnement pris en charge par le prototype de recevoir la même référence.

Réutiliser autant que possible les mécanismes de verrouillage ou d’écriture existants.

## Databricks

Le modèle futur pourra utiliser une gestion différente des séquences lors du passage aux tables Databricks.

Ce lot ne doit pas implémenter cette cible.

Ne pas :

- ajouter une table Databricks de séquences ;
- connecter les données métier à Databricks ;
- ajouter de requêtes vers `datapf_prod_featured.core...` ;
- préparer une synchronisation distante ;
- remplacer le stockage local actuel.

L’objectif est uniquement de fournir le comportement attendu dans la version locale actuelle.

## Architecture / contraintes techniques

Commencer par rechercher dans le dépôt toutes les fonctions qui :

- génèrent une référence ;
- créent une demande ;
- créent une intervention ;
- créent une prestation ;
- valident les identifiants ;
- chargent les données ;
- enregistrent les données ;
- manipulent les photos ;
- exportent les données ;
- affichent ou filtrent sur les références.

Centraliser la génération si la logique est actuellement dispersée.

Préserver la séparation existante entre :

- pages ;
- composants ;
- services ;
- modèle de données.

La logique de génération des références ne doit pas être implémentée directement dans les pages si elle peut être placée proprement dans un service.

## Modifications attendues

Après analyse du dépôt, modifier uniquement les éléments réellement concernés.

Cela peut inclure :

- service de génération des références ;
- services de création métier ;
- données d’exemple ;
- validations ;
- chargement des relations ;
- tests ;
- exports ;
- documentation.

Ne pas forcer artificiellement la création d’un nouveau fichier si une abstraction existante correspond déjà au besoin.

## Compatibilité et non-régression

Préserver notamment :

- les règles métier actuelles ;
- les statuts ;
- la clôture ascendante ;
- les validations de dates ;
- les droits d’accès ;
- la gestion des photos ;
- la distinction `WorkOrderReferenceEnrobEau` / `WorkOrderReferenceSaur` ;
- la navigation ;
- les exports, hormis l’évolution normale des valeurs de référence ;
- les protections existantes contre les modifications concurrentes.

## Critères d’acceptation

Le lot est accepté lorsque :

1. une nouvelle demande reçoit automatiquement une référence de type `DEM-000001` ;
2. une nouvelle intervention reçoit automatiquement une référence de type `INT-000001` ;
3. une nouvelle prestation reçoit automatiquement une référence de type `PR-000001` ;
4. les séquences sont indépendantes ;
5. les références sont uniques ;
6. les numéros progressent correctement ;
7. une référence déjà consommée n’est pas volontairement réutilisée ;
8. les trous éventuels dans les données ne provoquent pas de collision ;
9. `WorkOrderReferenceSaur` reste manuel et indépendant ;
10. `WorkOrderReferenceEnrobEau` reste stable pendant toute