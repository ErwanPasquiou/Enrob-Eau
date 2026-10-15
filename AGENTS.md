# AGENTS.md — Enrob’Eau

## 1. Objet du fichier

Ce fichier définit les règles de fonctionnement à respecter par tout agent de développement travaillant sur le repository **Enrob’Eau**.

Il s’applique notamment à :

- Codex ;
- ChatGPT Work ;
- tout autre agent automatisé amené à analyser ou modifier le code.

L’objectif est de préserver la cohérence du projet, d’éviter les hypothèses non validées et de s’assurer que toute évolution est correctement :

- analysée ;
- implémentée ;
- testée ;
- documentée ;
- versionnée.

---

# 2. Contexte du projet

Enrob’Eau est une application métier permettant de gérer et suivre :

- les demandes de travaux ;
- les interventions ;
- les prestations ;
- les réfections ;
- les photos associées ;
- les données de suivi opérationnel.

L’application est développée principalement avec :

- Python 3.11 ;
- Streamlit ;
- Databricks Apps.

Le développement s’appuie sur :

- GitHub ;
- une branche `dev` pour le développement ;
- une branche `main` pour le code validé ;
- Databricks pour le déploiement.

Le fichier `README.md` constitue une source de référence majeure concernant l’état actuellement implémenté du projet.

Ne jamais considérer qu’une fonctionnalité future décrite dans la documentation est déjà implémentée.

---

# 3. Lecture obligatoire avant toute modification

Avant toute modification significative, lire impérativement :

1. `AGENTS.md` ;
2. `README.md` ;
3. le fichier Markdown décrivant le lot d’implémentation demandé, lorsqu’il existe ;
4. toute documentation du repository utile au périmètre concerné.

Avant d’écrire du code, analyser l’existant.

Ne pas commencer par réécrire ou refactoriser le projet.

Identifier d’abord :

- ce qui existe déjà ;
- les fichiers réellement concernés ;
- les règles métier déjà appliquées ;
- les dépendances entre composants ;
- les tests existants ;
- les structures de données utilisées ;
- les éventuelles contradictions avec la demande.

---

# 4. Ordre de priorité des sources

Lorsqu’une tâche doit être interprétée, respecter cet ordre de priorité :

1. les instructions explicites du lot courant ;
2. `AGENTS.md` ;
3. `README.md` ;
4. le comportement existant couvert par les tests ;
5. l’architecture et les conventions du code existant.

En cas de contradiction entre deux sources :

- ne pas arbitrer silencieusement ;
- identifier la contradiction ;
- la signaler dans le compte rendu ;
- ne pas inventer de règle fonctionnelle.

Ne jamais inventer :

- une règle métier ;
- une colonne ;
- une table ;
- une relation ;
- une valeur autorisée ;
- un statut ;
- un profil ;
- un droit ;
- un comportement de workflow.

---

# 5. Modèle métier principal

La hiérarchie principale est :

```text
Demande
└── Intervention(s)
    └── Prestation(s)
```

Une demande peut avoir plusieurs interventions.

Une intervention peut avoir plusieurs prestations.

Les photos sont actuellement associées :

- aux demandes ;
- aux prestations.

Préserver systématiquement l’intégrité de ces relations.

---

# 6. Références des interventions

Les interventions distinguent deux références :

- `WorkOrderReferenceEnrobEau`
- `WorkOrderReferenceSaur`

## `WorkOrderReferenceEnrobEau`

Il s’agit de l’identifiant technique stable de l’intervention.

Il doit :

- rester stable pendant toute la vie de l’intervention ;
- être utilisé pour les relations internes Enrob’Eau ;
- ne pas changer lorsque la référence SI SAUR est modifiée.

## `WorkOrderReferenceSaur`

Il s’agit de la référence métier SI SAUR.

Elle est :

- obligatoire ;
- unique ;
- modifiable.

Ne jamais utiliser `WorkOrderReferenceSaur` comme clé technique interne des relations entre entités.

---

# 7. Références générées automatiquement

Les références générées automatiquement respectent actuellement les formats suivants :

```text
RequestReference               DEM-000001
WorkOrderReferenceEnrobEau     INT-000001
ServiceReference               PR-000001
```

Règles :

- séquences indépendantes par entité ;
- six chiffres ;
- zéro-padding ;
- unicité ;
- aucune réutilisation volontaire d’une référence déjà consommée.

`WorkOrderReferenceSaur` est exclue de cette génération automatique.

---

# 8. Stockage des données

## État actuel

Le projet fonctionne encore partiellement avec du stockage local.

Selon l’état réel du repository, cela peut notamment comprendre :

- JSON pour les données métier ;
- SQLite pour les photos ;
- Databricks SQL pour l’administration et les profils.

Toujours analyser le repository avant de supposer le mécanisme exact actuellement en place.

## Règle importante

Ne pas ajouter de nouvelle connexion métier vers :

```text
datapf_prod_featured.core...
```

sauf si le lot d’implémentation le demande explicitement.

Ne pas anticiper une migration Databricks future en ajoutant de l’infrastructure inutile au besoin courant.

---

# 9. Databricks

Databricks Apps constitue l’environnement cible d’exécution.

Le projet peut utiliser notamment :

- Databricks SQL ;
- Unity Catalog ;
- SQL Warehouse ;
- ressources déclarées dans `app.yaml`.

Ne jamais affaiblir l’authentification ou les contrôles d’accès pour faciliter le développement local.

Ne jamais coder en dur :

- URL de workspace ;
- token ;
- secret ;
- mot de passe ;
- identifiant sensible.

Utiliser les mécanismes de configuration existants.

---

# 10. Architecture du projet

Respecter autant que possible la séparation actuelle :

```text
app.py
pages/
components/
services/
styles/
assets/
tests/
data/
```

## `app.py`

Responsabilités principales :

- point d’entrée ;
- identité utilisateur ;
- navigation globale ;
- routage principal.

Éviter d’y placer de la logique métier détaillée.

## `pages/`

Responsabilités principales :

- composition des écrans ;
- orchestration de la page ;
- interaction avec l’utilisateur.

Éviter :

- SQL direct ;
- logique métier dupliquée ;
- validations dispersées.

## `components/`

Responsabilités principales :

- composants UI réutilisables ;
- formulaires ;
- widgets ;
- blocs d’affichage partagés.

## `services/`

Responsabilités principales :

- règles métier ;
- validations ;
- persistance ;
- accès aux données ;
- transformations ;
- contrôles d’autorisation lorsque pertinent.

La logique métier doit être privilégiée dans les services plutôt que dans les pages.

## `styles/`

Responsabilités principales :

- CSS ;
- présentation.

## `tests/`

Contient les tests automatisés.

Privilégier la réutilisation avant la duplication.

---

# 11. Principes UI / UX

Enrob’Eau est une application métier professionnelle.

Préserver :

- la clarté ;
- la cohérence ;
- une navigation simple ;
- des actions principales visibles ;
- un nombre limité de clics ;
- les composants réutilisables ;
- l’usage mobile lorsque nécessaire sur le terrain.

Ne pas engager une refonte générale de l’interface sauf demande explicite.

Respecter l’identité visuelle et les assets existants.

---

# 12. Authentification et profils

Les profils actuellement reconnus sont :

- `agent` ;
- `ordonnanceur` ;
- `agent externe` ;
- `administrateur`.

Ne pas réintroduire un ancien rôle sans nouvelle décision métier explicite.

Une restriction visuelle dans l’interface ne constitue pas à elle seule un contrôle d’accès.

Lorsqu’une page ou action est sensible, vérifier :

- sa visibilité dans la navigation ;
- l’accès direct à la route ;
- les contrôles dans les services concernés.

---

# 13. Sécurité

Ne jamais committer ni exposer :

- token GitHub ;
- token Databricks ;
- mot de passe ;
- secret ;
- fichier `.env` contenant des credentials ;
- clé privée ;
- configuration locale sensible.

Avant chaque commit et push :

- relire le diff ;
- vérifier l’absence de données sensibles ;
- respecter le `.gitignore`.

Ne pas versionner sans nécessité explicite :

- `.venv` ;
- caches Python ;
- fichiers temporaires IDE ;
- bases locales générées ;
- fichiers utilisateur ;
- secrets.

---

# 14. Règles métier

Ne pas dupliquer une règle métier entre plusieurs pages.

Lorsqu’une règle doit être appliquée à la création et à la modification, la centraliser autant que possible.

Lorsqu’une règle métier évolue :

- identifier les tests concernés ;
- analyser les impacts sur les entités parentes/enfants ;
- vérifier les statuts ;
- vérifier les exports ;
- vérifier les formulaires ;
- vérifier les données historiques.

Ne jamais supprimer ou assouplir silencieusement une règle existante.

---

# 15. Formulaire Demande

Le formulaire Demande est un parcours central de l’application.

Toute évolution peut impacter :

- les champs ;
- les listes de valeurs ;
- les validations ;
- le modèle de données ;
- la sérialisation ;
- les données existantes ;
- les exports ;
- les tests ;
- la documentation.

Lors d’une modification du formulaire :

1. analyser le modèle existant ;
2. préserver autant que possible les demandes historiques ;
3. ne pas inventer de valeur par défaut métier ;
4. utiliser `null` lorsque cela correspond au modèle ;
5. appliquer les mêmes règles sur création et modification lorsque nécessaire.

---

# 16. Photos

Les photos sont associées aux demandes et aux prestations.

Préserver :

- le rattachement à l’entité parente ;
- les droits d’accès ;
- le chargement à la demande si déjà utilisé ;
- la validation des fichiers ;
- les métadonnées ;
- les contrôles de version et de concurrence existants.

Ne pas charger inutilement l’ensemble des binaires.

Ne pas modifier la stratégie de stockage sans demande explicite.

---

# 17. Tests

Toute modification significative doit faire l’objet d’une analyse de l’impact sur les tests.

Avant de modifier :

- rechercher les tests existants ;
- comprendre leur couverture.

Après modification :

1. exécuter les tests ciblés ;
2. corriger les régressions directement liées au changement ;
3. exécuter la suite complète pertinente.

Utiliser la commande définie dans le repository.

Si elle reste applicable :

```bash
python -m unittest discover -s tests -v
```

ou l’équivalent avec l’interpréteur du projet.

Selon le périmètre, couvrir notamment :

- règles métier ;
- relations ;
- validations ;
- CRUD ;
- droits ;
- exports ;
- migrations ;
- logique UI ;
- modifications concurrentes.

Les tests automatisés ne remplacent pas les vérifications réelles navigateur lorsque celles-ci sont nécessaires.

Ne jamais déclarer une tâche terminée si des tests pertinents échouent sans expliquer clairement pourquoi.

---

# 18. Documentation

Après toute modification significative, vérifier si la documentation doit évoluer.

Examiner notamment :

- `README.md` ;
- les fichiers `CODEX-XXX_*.md` ;
- la documentation du modèle de données ;
- les éventuelles décisions d’architecture.

La documentation doit refléter l’état réellement implémenté.

Toujours distinguer :

- état actuel ;
- décision validée ;
- cible future ;
- limitation connue.

Ne jamais documenter comme existante une fonctionnalité seulement prévue.

---

# 19. Workflow Git

Le workflow standard est :

```text
dev
→ validation
→ main
```

## Branche de développement

Le développement doit être réalisé sur :

```text
dev
```

Ne pas développer directement sur `main`.

Avant de commencer :

```bash
git checkout dev
git pull origin dev
git status
```

Vérifier que la branche locale est à jour avant toute modification.

---

# 20. Commit et push

Après implémentation :

1. relire le diff complet ;
2. supprimer les modifications parasites ;
3. vérifier l’absence de secrets ;
4. exécuter les tests attendus ;
5. créer un commit explicite ;
6. pousser sur `origin/dev`.

Exemple :

```bash
git add .
git commit -m "feat: évolution du formulaire demande"
git push origin dev
```

Utiliser des messages de commit explicites.

Éviter les messages génériques du type :

```text
update
fix
changes
modif
```

---

# 21. Branche `main`

Ne pas pousser directement du développement sur `main`.

Ne pas fusionner `dev` vers `main` sauf :

- demande explicite de l’utilisateur ;
- tâche explicitement dédiée à la promotion.

Workflow attendu :

```text
Développement sur dev
→ tests
→ validation fonctionnelle
→ merge dev vers main
→ déploiement
```

---

# 22. GitHub

Le repository Enrob’Eau est privé.

Préserver son caractère privé.

Ne pas :

- créer un second repository sans besoin explicite ;
- réécrire l’historique Git ;
- faire de `force push` sans autorisation ;
- supprimer une branche sans autorisation explicite.

Si une autorisation GitHub est nécessaire, demander uniquement l’autorisation minimale requise.

---

# 23. Respect strict du périmètre

Implémenter uniquement ce qui est demandé.

Ne pas ajouter une fonctionnalité voisine simplement parce qu’elle semble utile.

Éviter :

- refactorings sans rapport ;
- renommages non demandés ;
- migrations non nécessaires ;
- refonte d’écrans hors périmètre ;
- infrastructure spéculative.

Un petit refactoring est acceptable s’il est réellement nécessaire pour réaliser la modification proprement.

---

# 24. Refactoring

Préserver l’architecture existante sauf raison claire de la faire évoluer.

Avant un refactoring structurel :

- vérifier qu’il est nécessaire ;
- analyser le risque de régression ;
- limiter le périmètre ;
- exécuter les tests ;
- documenter la raison.

Éviter la sur-ingénierie.

Privilégier des solutions :

- simples ;
- lisibles ;
- maintenables ;
- robustes ;
- cohérentes avec l’existant.

---

# 25. Gestion des ambiguïtés

Lorsqu’un choix est purement technique et n’a pas d’impact fonctionnel, l’agent peut retenir la solution la plus simple et cohérente avec le projet.

Lorsqu’une décision métier ou fonctionnelle manque :

- ne pas inventer ;
- signaler le point bloquant ;
- conserver le comportement existant si cela est sûr.

Exemples nécessitant une clarification :

- valeur métier non définie ;
- règle de statut absente ;
- champ obligatoire ou facultatif non défini ;
- relation de données ambiguë ;
- contradiction entre deux documents.

---

# 26. Fichiers de lot Codex

Les changements importants peuvent être décrits dans des fichiers de type :

```text
CODEX-XXX_nom-court.md
```

Lorsqu’un tel fichier existe :

- le lire avant toute modification ;
- respecter son objectif ;
- respecter ses critères d’acceptation ;
- respecter son hors périmètre ;
- ne pas élargir le scope sans justification.

Le fichier décrit le résultat attendu.

Il ne doit pas nécessairement dicter l’implémentation ligne par ligne.

L’agent doit analyser le repository et retenir l’implémentation technique la plus adaptée dans les limites définies.

---

# 27. Definition of Done d’une tâche d’implémentation

Une tâche ne doit pas être considérée comme terminée tant que les éléments applicables suivants ne sont pas satisfaits :

- [ ] Le comportement demandé est implémenté
- [ ] Les comportements non concernés sont préservés
- [ ] Les relations de données restent valides
- [ ] Les validations métier sont respectées
- [ ] Les contrôles d’accès sont préservés
- [ ] Les tests ciblés passent
- [ ] La suite de tests pertinente passe
- [ ] Les vérifications navigateur nécessaires sont réalisées ou identifiées
- [ ] La documentation est mise à jour si nécessaire
- [ ] Le diff Git ne contient aucun fichier parasite
- [ ] Aucun secret n’est présent
- [ ] Les modifications sont committées
- [ ] Les modifications sont poussées sur `origin/dev`
- [ ] Les limitations restantes sont documentées

---

# 28. Compte rendu final obligatoire

À la fin de chaque tâche d’implémentation, fournir un compte rendu structuré.

## Résumé

Indiquer :

- l’objectif demandé ;
- le résultat obtenu.

## Git

Indiquer :

- la branche utilisée ;
- le message de commit ;
- le hash du commit ;
- le statut du push.

## Fichiers

Lister :

- fichiers créés ;
- fichiers modifiés ;
- fichiers supprimés.

## Implémentation

Décrire :

- les principales modifications ;
- les décisions techniques importantes.

## Données

Si concerné, préciser :

- évolution du modèle ;
- migration locale ;
- compatibilité avec les données existantes.

## Tests

Indiquer :

- commandes exécutées ;
- tests ajoutés ou modifiés ;
- résultats.

## Documentation

Préciser :

- les documents mis à jour ;
- ou qu’aucune mise à jour n’était nécessaire.

## Éléments restant à traiter

Lister :

- éléments partiels ;
- limitations ;
- tests manuels restant à effectuer.

## Risques

Lister :

- risques techniques ;
- risques sur les données ;
- actions de suivi éventuelles.

---

# 29. Principe directeur

Toujours respecter cette séparation :

```text
Les conversations spécialisées définissent.
MASTER consolide, coordonne et prépare les lots.
Les agents de code implémentent.
Les tests vérifient.
La documentation décrit l’état réellement atteint.
```

Ne jamais confondre :

- demandé ;
- validé ;
- planifié ;
- implémenté ;
- testé ;
- terminé.