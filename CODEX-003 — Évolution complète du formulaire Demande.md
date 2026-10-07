# CODEX-003 — Évolution complète du formulaire Demande

## Objectif

Faire évoluer le formulaire **Demande** d’Enrob’Eau afin de :

1. appliquer les nouvelles règles métier validées sur les champs et listes de valeurs ;
2. adapter le modèle de données local correspondant ;
3. gérer correctement les choix multiples et les nouveaux champs ;
4. réorganiser le formulaire en sections visuelles cohérentes ;
5. préserver le comportement existant non concerné ;
6. maintenir la compatibilité avec les demandes existantes.

Ce lot regroupe :

- `ENR-006` — Évolution métier des champs et listes de valeurs du formulaire Demande ;
- `ENR-007` — Adaptation du modèle de données Demande ;
- `ENR-008` — Réorganisation UI/UX du formulaire Demande.

---

# Contexte actuel

Enrob’Eau fonctionne actuellement avec des données métier locales.

Le formulaire Demande permet notamment :

- de créer une demande ;
- de la modifier ;
- de renseigner sa localisation ;
- d’associer des photos ;
- de suivre les informations métier nécessaires à son traitement.

Le dépôt doit être analysé avant toute modification afin d’identifier :

- les champs actuellement présents ;
- leurs noms techniques ;
- leur stockage ;
- leurs usages dans les services ;
- leurs usages dans les exports ;
- leurs usages dans les tests ;
- leurs usages dans les données locales d’exemple.

Ne pas supposer qu’un champ visible correspond exactement au nom technique attendu.

---

# ENR-006 — Évolution métier des champs et listes de valeurs

## Règles générales

Les champs concernés par cette évolution sont obligatoires sauf lorsque le présent document précise explicitement qu’ils sont conditionnels ou facultatifs.

Les valeurs autorisées doivent être limitées aux listes définies ci-dessous.

Ne pas ajouter d’autres valeurs.

---

## Type de voirie

### Type

Choix multiple.

### Obligatoire

Oui.

### Valeurs autorisées

- Pleine terre
- Chaussée
- Trottoir
- Autre

### Règle conditionnelle

Lorsque **Autre** est sélectionné :

- afficher un champ de précision libre ;
- cette précision devient obligatoire.

Lorsque **Autre** n’est pas sélectionné :

- cette précision ne doit pas être obligatoire.

---

## DICT / ATU

### Type

Choix unique.

### Obligatoire

Oui.

### Valeurs autorisées

- ATU immédiate
- ATU 72h
- ATU sous 9 jours
- DICT
- Sans terrassement

---

## Revêtement

### Type

Choix multiple.

### Obligatoire

Oui.

### Valeurs autorisées

- Enrobé
- Asphalte <= 3m2
- Asphalte > 3m2
- Béton désactivé
- Béton (résine) perméable
- Pleine terre
- Pavé

---

## Motif de la demande

### Type

Choix unique.

### Obligatoire

Oui.

### Valeurs autorisées

- Création branchement neuf
- Réparation de fuite branchement
- Renouvellement de branchement
- Suppression de branchement
- Modification de branchement
- Intervention bouche à clés
- Renouvellement de regard
- Réparation fuite réseau distribution
- Sondage
- Pose d'une vanne réseau
- Réparation une vanne réseau
- Renouvellement vanne réseau
- Création PI
- Renouvellement PI
- Pose Borne Moneca

---

## Coupure d’eau

### Type

Choix unique.

### Obligatoire

Oui.

### Valeurs autorisées

- Avec arrêt d'eau 1 jour
- Avec arrêt d'eau 1/2 journée
- Sans arrêt d'eau
- Autre

---

## Matériau signalé

### Type

Choix unique.

### Obligatoire

Oui.

### Valeurs autorisées

- Fonte
- PVC
- PEHD
- PEBD
- Cuivre
- Acier - Fer - Galva
- Plomb
- Non détectable
- Autre

---

## Domaine d’activité

### Type

Choix unique.

### Obligatoire

Oui.

### Valeurs autorisées

- En domaine public : en agglomération
- En domaine public : Route métropolitaine
- En domaine privé nécessitant RDV

---

## Impact sur la voirie

### Type

Choix multiple.

### Obligatoire

Oui.

### Valeurs autorisées

- Route barrée et déviation
- Alternat par feu
- Réduction sur chaussée
- Pose de panneaux interdit de stationner
- Travaux sur trottoir
- Aucun impact
- Autre

---

## Matricule Compteur

### Libellé utilisateur

`Matricule Compteur`

### Nom technique validé

`MeterReference`

### Type de données

Texte / chaîne de caractères.

### Règle métier

Le champ devient obligatoire uniquement lorsque :

`Motif de la demande = Renouvellement de branchement`

Dans les autres cas :

- il est facultatif ;
- son absence doit être représentée par `null` dans le modèle de données.

Le stockage doit donc accepter l’absence de valeur même si l’interface le rend obligatoire dans le cas conditionnel décrit ci-dessus.

---

## Impact sur les transports

Le champ **Impact sur les transports** est explicitement retiré de cette évolution.

S’il existe actuellement dans le formulaire ou dans une logique UI liée à cette évolution :

- ne plus le proposer dans le formulaire Demande concerné.

Avant de supprimer une donnée historique ou une colonne technique existante, analyser le dépôt et les données afin d’éviter une perte involontaire.

Ne pas réaliser de suppression de modèle irréversible uniquement parce que le champ n’est plus affiché sans vérifier son usage réel.

---

# ENR-007 — Adaptation du modèle de données Demande

## Objectif

Adapter le modèle local de la Demande aux décisions métier ci-dessus.

---

## Nouveau champ

Ajouter au modèle Demande :

`MeterReference`

avec les caractéristiques suivantes :

- type logique : chaîne ;
- nullable ;
- valeur absente : `null`.

Son libellé utilisateur reste :

`Matricule Compteur`

---

## Choix multiples

Les champs définis comme choix multiples doivent pouvoir stocker plusieurs valeurs sans perte d’information.

Sont concernés dans ce lot :

- Type de voirie ;
- Revêtement ;
- Impact sur la voirie.

Analyser la manière dont le modèle local représente déjà les valeurs multiples avant d’introduire une nouvelle convention.

Privilégier la cohérence avec le modèle existant lorsque celui-ci possède déjà un format adapté.

Ne pas inventer une structure incompatible avec la future migration sans nécessité.

---

## Compatibilité des données existantes

Analyser les données locales existantes avant adaptation.

Le lot doit préserver autant que possible les demandes déjà présentes.

Les demandes historiques qui ne possèdent pas `MeterReference` doivent rester chargeables.

Dans ce cas :

`MeterReference = null`

doit être considéré comme valide.

---

## Lecture et écriture

Adapter tous les flux réellement concernés :

- chargement des demandes ;
- création ;
- modification ;
- validation ;
- sérialisation ;
- désérialisation ;
- exports si les champs concernés y sont exposés ;
- tests ;
- données d’exemple si nécessaire.

---

## Migration locale

Si une adaptation des données locales est requise :

- préserver toutes les demandes existantes ;
- préserver leurs références ;
- préserver les liens avec les interventions ;
- préserver les liens avec les photos ;
- ne pas inventer une valeur métier pour un champ historique absent ;
- utiliser `null` lorsque la donnée n’existe pas et que le modèle l’autorise.

---

## Databricks

Ce lot ne doit pas connecter le formulaire Demande à de nouvelles tables métier Databricks.

Ne pas :

- créer de nouvelle connexion aux tables `datapf_prod_featured.core...` ;
- remplacer les JSON locaux par Databricks ;
- développer une synchronisation ;
- créer une migration métier distante.

Le travail doit rester compatible avec le fonctionnement local actuel.

---

# ENR-008 — Réorganisation UI/UX du formulaire Demande

## Principe

Le formulaire reste sur **une seule page**.

Ne pas transformer le formulaire en assistant multi-étapes ou wizard.

Le formulaire vertical existant doit être réorganisé sous forme de cartes ou sections visuellement distinctes.

---

## Sections validées

Utiliser exactement les cinq familles suivantes :

### 1. Localisation des travaux

Regrouper les informations relatives à la localisation de la demande.

### 2. Informations sur la demande

Regrouper les informations générales permettant de qualifier la demande.

### 3. Caractéristiques des travaux

Regrouper les informations décrivant la nature des travaux à réaliser.

### 4. Contraintes et préparation du chantier

Regrouper les informations liées aux contraintes opérationnelles et à la préparation de l’intervention.

### 5. Commentaire complémentaire

Regrouper l’espace de commentaire complémentaire.

---

## Limites de la décision UI

Seul le principe suivant est validé :

- une seule page ;
- cinq cartes / sections ;
- les cinq intitulés ci-dessus.

Ne pas considérer comme imposés sans justification du dépôt :

- une mise en page précise à deux colonnes ;
- une barre de progression ;
- un assistant étape par étape ;
- une nouvelle navigation ;
- un déplacement arbitraire des boutons ;
- de nouvelles règles d’affichage non définies dans les règles métier.

Codex peut adapter raisonnablement la présentation à l’architecture UI existante, sans refonte générale.

---

# Comportement attendu

## Création d’une demande

Lors de la création :

- les nouveaux champs et listes sont proposés ;
- les champs obligatoires sont contrôlés ;
- les choix multiples peuvent être sélectionnés correctement ;
- la précision du Type de voirie est obligatoire si `Autre` est sélectionné ;
- `MeterReference` devient obligatoire lorsque le motif est `Renouvellement de branchement` ;
- les données sont enregistrées dans le modèle local adapté.

---

## Modification d’une demande

Lors de l’édition :

- les valeurs déjà enregistrées sont correctement préchargées ;
- les choix multiples existants sont restaurés ;
- les mêmes validations que lors de la création sont appliquées ;
- `MeterReference` est correctement affiché et modifiable ;
- les règles conditionnelles restent applicables.

---

# Architecture / contraintes techniques

Avant modification, rechercher dans le dépôt :

- la définition du modèle Demande ;
- les constantes ou listes de valeurs ;
- les formulaires de création et modification ;
- les validations métier ;
- les services de lecture/écriture ;
- les données d’exemple ;
- les exports ;
- les tests ;
- les styles ou composants utilisés pour structurer le formulaire.

Préserver la séparation existante :

- `pages/` pour les écrans ;
- `components/` pour les composants réutilisables ;
- `services/` pour les règles, validations et accès aux données ;
- `styles/` pour la présentation.

Éviter de placer des listes métier dupliquées directement à plusieurs endroits dans l’UI si elles peuvent être centralisées proprement.

Ne pas refactoriser des zones non concernées sans nécessité.

---

# Modifications attendues

Après analyse du dépôt, adapter uniquement les fichiers réellement concernés.

Cela peut inclure :

- modèle de données Demande ;
- constantes ou référentiels de valeurs ;
- services de validation ;
- composants du formulaire ;
- formulaire de création ;
- formulaire de modification ;
- données locales d’exemple ;
- exports ;
- tests ;
- documentation.

Ne pas forcer la modification de tous ces éléments si certains ne sont pas concernés dans l’implémentation réelle.

---

# Compatibilité et non-régression

Préserver notamment :

- génération de `RequestReference` ;
- identité du demandeur connecté ;
- recherche d’adresse ;
- géocodage ;
- gestion des photos ;
- consultation des demandes ;
- modification par le propriétaire ;
- contrôles d’accès ;
- relations Demande → Intervention ;
- relations des photos avec la demande ;
- mécanismes de concurrence existants ;
- exports existants hors adaptation nécessaire ;
- navigation actuelle.

---

# Critères d’acceptation

Le lot est accepté lorsque :

1. le formulaire Demande reste sur une seule page ;
2. les cinq sections validées sont présentes ;
3. Type de voirie accepte plusieurs valeurs parmi la liste validée ;
4. Type de voirie est obligatoire ;
5. sélectionner `Autre` pour Type de voirie rend la précision obligatoire ;
6. DICT / ATU est un choix unique obligatoire avec les valeurs validées ;
7. Revêtement est un choix multiple obligatoire avec les valeurs validées ;
8. Motif de la demande est un choix unique obligatoire avec les valeurs validées ;
9. Coupure d’eau est un choix unique obligatoire avec les valeurs validées ;
10. Matériau signalé est un choix unique obligatoire avec les valeurs validées ;
11. Domaine d’activité est un choix unique obligatoire avec les valeurs validées ;
12. Impact sur la voirie est un choix multiple obligatoire avec les valeurs validées ;
13. `Impact sur les transports` n’est plus présenté dans l’évolution du formulaire ;
14. `MeterReference` existe dans le modèle ;
15. `MeterReference` est nullable ;
16. `MeterReference` devient obligatoire dans l’UI lorsque le motif est `Renouvellement de branchement` ;
17. les demandes historiques sans `MeterReference` restent chargeables ;
18. les choix multiples sont correctement persistés et restaurés ;
19. la création d’une demande reste fonctionnelle ;
20. la modification d’une demande reste fonctionnelle ;
21. les relations existantes avec interventions et photos sont préservées ;
22. aucune connexion métier Databricks supplémentaire n’est introduite ;
23. les comportements non concernés ne régressent pas ;
24. les tests pertinents passent.

---

# Tests attendus

## Listes de valeurs

Tester que seules les valeurs autorisées sont proposées ou acceptées pour :

- Type de voirie ;
- DICT / ATU ;
- Revêtement ;
- Motif ;
- Coupure d’eau ;
- Matériau ;
- Domaine d’activité ;
- Impact sur la voirie.

---

## Choix multiples

Tester au minimum :

- plusieurs Types de voirie ;
- plusieurs Revêtements ;
- plusieurs Impacts sur la voirie ;
- sauvegarde ;
- rechargement ;
- modification.

---

## Type de voirie — Autre

Tester :

- `Autre` sélectionné sans précision → refus ;
- `Autre` sélectionné avec précision → accepté ;
- `Autre` non sélectionné → précision non obligatoire.

---

## Matricule Compteur

Tester :

### Motif différent de Renouvellement de branchement

- champ vide accepté ;
- stockage `null`.

### Motif = Renouvellement de branchement

- champ vide refusé ;
- champ renseigné accepté.

### Modification

- demande historique sans valeur chargeable ;
- changement du motif vers Renouvellement de branchement déclenche la validation ;
- changement vers un autre motif ne rend plus le champ obligatoire.

---

## Données existantes

Tester le chargement des demandes existantes ne possédant pas le nouveau champ.

Vérifier qu’aucune migration ne casse :

- les références ;
- les interventions liées ;
- les photos liées.

---

## UI

Vérifier :

- présence des cinq sections ;
- formulaire sur une seule page ;
- affichage correct des listes ;
- affichage conditionnel de la précision Type de voirie ;
- comportement conditionnel de Matricule Compteur.

---

## Régression

Exécuter les tests ciblés puis la suite complète existante du projet.

Utiliser la commande définie dans le dépôt si elle est toujours valide, par exemple :

`python -m unittest discover -s tests -v`

ou l’équivalent utilisant l’interpréteur du projet.

Les tests automatisés ne remplacent pas une vérification navigateur lorsque le comportement visuel ou conditionnel doit être validé.

---

# Documentation à mettre à jour

Après implémentation réussie, mettre à jour la documentation réellement concernée.

Documenter notamment :

- les nouvelles listes de valeurs ;
- les champs à choix multiple ;
- `MeterReference` / Matricule Compteur ;
- sa règle conditionnelle ;
- la suppression de `Impact sur les transports` du formulaire ;
- la nouvelle organisation du formulaire en cinq sections ;
- les éventuelles adaptations du modèle local.

Ne documenter que le comportement réellement implémenté.

---

# Hors périmètre

Ce lot ne comprend pas :

- migration générale des demandes vers Databricks ;
- connexion à `datapf_prod_featured.core...` ;
- refonte générale de l’application ;
- modification des profils ou droits ;
- modification du workflow Intervention / Prestation non liée au formulaire Demande ;
- refonte de la gestion des photos ;
- assistant de saisie multi-étapes ;
- nouvelle règle métier non explicitement décrite dans ce document.

---

# Résultat attendu de Codex

À la fin de la tâche, fournir un compte rendu structuré.

## Implémentation

- résumé des changements réalisés ;
- comportement final obtenu.

## Fichiers

- fichiers créés ;
- fichiers modifiés ;
- fichiers supprimés.

## Modèle et données

- modifications du modèle Demande ;
- format retenu pour les choix multiples ;
- adaptation éventuelle des données locales ;
- traitement des anciennes demandes sans `MeterReference`.

## UI

- composants/formulaires modifiés ;
- organisation finale des cinq sections ;
- règles conditionnelles mises en œuvre.

## Décisions techniques

- décisions prises après analyse du dépôt ;
- différences éventuelles entre les hypothèses du présent document et l’architecture réellement rencontrée.

## Tests

- tests ajoutés ou adaptés ;
- commandes exécutées ;
- résultats.

## Éléments non réalisés

- éléments partiels ;
- limitations ;
- éventuels écarts au lot.

## Risques et suivi

- risques identifiés ;
- dette technique éventuelle ;
- actions de suivi recommandées.

Ne pas déclarer le lot terminé si les tests pertinents échouent sans documenter clairement les causes.