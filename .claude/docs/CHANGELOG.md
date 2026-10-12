# Changelog — node4jPOC

Format : [Keep a Changelog](https://keepachangelog.com/). Versionning : `vYYYY.MM.DD-HHMM` (tag de déploiement).

## [Unreleased]

### Added

- Initialisation du projet depuis le template claude-Setup v1.5.0 (2026-09-26)
- Page d'initiative du POC dans le [README](../../README.md) : objectif, pourquoi, vue d'ensemble, jalons, critères de réussite, périmètre, risques, décisions (2026-09-30)
- Schéma d'ensemble fait avec diagram-design : source [vue-ensemble.html](conception/diagrams/vue-ensemble.html) et export [vue-ensemble.png](conception/diagrams/vue-ensemble.png) côte à côte, en PNG parce que GitHub ne charge pas les polices d'un SVG affiché en image (2026-09-30)
- Suivi dans Jira, [projet NEO](https://frjulienleroy.atlassian.net/jira/software/projects/NEO/boards/40) (Kanban géré par l'équipe) : un epic par jalon (NEO-1 à NEO-4) ; pour le jalon 1, un ticket par phase de la spec 001, plus NEO-6 « Créer l'instance AuraDB Free » (NEO-5 à NEO-12) ; une story seulement quand il y a un résultat à montrer ; le dépôt fait foi (2026-09-30)
- [Dépôt GitHub privé](https://github.com/kurt83340/node4jPOC) `kurt83340/node4jPOC` relié à NEO par l'application GitHub for Atlassian : une clé de ticket dans un message de commit ou un titre de PR fait remonter le travail dans le ticket (2026-09-30)
- Job `reveil-aura` sur Google Cloud ([`infra/reveil-aura/`](../../infra/reveil-aura/), NEO-13) : Cloud Scheduler lance chaque jour à 9 h un job Cloud Run qui envoie `RETURN 1` à Aura, pour que l'instance Free ne se mette pas en pause ; toute erreur envoie un e-mail (alerte Cloud Monitoring sur journaux). Exploitation : [RUNBOOK](RUNBOOK.md) (2026-09-30)
- Socle de données du jalon 1 ([spec 001](specs/001-socle-donnees/spec.md)) : graphe Pokémon chargé en Cypher pur depuis le commit PokéAPI figé, 8 859 nœuds et 113 700 relations (`scripts/charger.sh --tout`, journal dans `logs/`) ; vérification écrite d'abord (`scripts/verifier.sh`) ; preuve d'idempotence en une commande (`charger.sh --idempotence`) ; 27 requêtes de référence et leur rejeu (`scripts/questions.sh`) (2026-10-01)
- Suivi Jira du jalon 2 sous l'epic [NEO-2](https://frjulienleroy.atlassian.net/browse/NEO-2) : NEO-14 à NEO-24, un ticket par phase de la [spec 002](specs/002-agent-text-to-cypher/tasks.md) (les plus petites regroupées), une story (NEO-21, la mesure) et deux actions de Julien (NEO-15, NEO-22) (2026-10-01)
- Tests du socle : `verifier.sh` 33 contrôles conformes ; `charger.sh --idempotence` IDEMPOTENT (chargement sur base vide en 37 s, second chargement sans aucune création) ; `questions.sh --verifier` 27 questions conformes ; `shellcheck` propre sur `scripts/`
- CI GitHub Actions (`.github/workflows/ci.yml`, NEO-25) : à chaque PR et push sur `main`, banc et `reveil-aura` (ruff, mypy strict, pytest), shellcheck, Prettier 3.9.8 et gitleaks sur tout l'historique ; aucun secret ni accès au cloud ; pas de CD (2026-10-10)
- Coupure automatique de Vertex ([`infra/coupure-vertex/`](../../infra/coupure-vertex/), NEO-26, ADR-0010 et ADR-0013) : le budget de 100 € publie dans le sujet Pub/Sub `coupure-vertex`, et la fonction Cloud Run du même nom désactive `aiplatform.googleapis.com` dès 100 % ; rôle personnalisé `coupureVertex` (lire l'état d'un service, le désactiver) ; alertes par e-mail (coupure, échec) ; plafond natif de 30 € par mois sur Vertex (Preview). Essai réel : Vertex coupé en moins d'une minute, e-mail reçu, réactivé ([RUNBOOK](RUNBOOK.md)) (2026-10-10)
- Technique 2 du banc d'essai, jalon 2 ([spec 002](specs/002-agent-text-to-cypher/spec.md), [rapport](../../banc/resultats/technique-2.md)) : un agent text-to-Cypher branché sur le graphe par `neo4j-mcp` v1.6.0 en lecture seule, mesuré dans trois cellules sur les 30 questions, 3 passes comptées ; sur 30 : Claude Code + Sonnet 5.5 27,5, ADK + Sonnet 5.5 27,8, ADK + Gemini 3.8 Flash 20,7 ; un schéma aux identifiants anglais n'apporte rien de mesurable à Gemini (Δ = −1,5, sous le seuil de 2,5 fixé avant la mesure). Avec elle : le harnais `banc/` (`banc lancer`, `revoir`, `rapport`, `traduire`), réutilisable aux jalons 3 et 4 ; la consigne et la fiche de schéma communes ; l'index plein texte `noms_plein_texte` ; la bascule `charger.sh --schema en|fr` (2026-10-12)
- Tests de la spec 002 : 1 481 tests du banc verts, couverture 95 %, sans aucun appel réel (faux serveurs, fausses API) ; contrôles sur la base : 34 contrôles, 28 requêtes, 23 valeurs et 10 exemples de la fiche ; coût LLM de toute la spec : environ 14,0 $ (Claude 6,45 $, Gemini 7,51 $), sous le budget de 35 $

### Changed

- Pivot 2026-09-28 : environnement cible Google Cloud, découpage en 6 jalons ([CR](cadrage/reunions/2026-09-28-pivot.md))
- [Règles git](../rules/git-workflow.md) : clé du ticket Jira à la fin du sujet des commits, clé de l'epic du jalon à la fin du titre des PR, aucune clé dans le nom des branches, commits et PR au seul nom de Julien (2026-09-30)
- [Règles git](../rules/git-workflow.md) : une branche et une PR par phase, fusion en merge commit (seul mode permis par le dépôt, branche supprimée à la fusion), tag `jalon-N` à la livraison d'un jalon ; le titre d'une PR finit par la clé du ticket de sa phase (2026-10-01)
- [Règles git](../rules/git-workflow.md) : on ne fusionne qu'une PR dont `gh pr checks` est vert, GitHub Free ne protégeant aucune branche d'un dépôt privé ; branches `chore/` pour l'outillage du dépôt (2026-10-10)
- Méthode : template claude-Setup 1.5.0 → 1.6.1 (2026-10-07), puis 1.7.0 (2026-10-09)

### Decided

- Jeu de données : Pokémon, CSV PokéAPI en français ([ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md))
- Environnement cible : Google Cloud, dbt hors POC ([ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md))
- Chargement des données en Cypher pur ([ADR-0003](adr/0003-mvp-chargement-cypher-pur.md))
- Modèle du graphe : espèce + toutes les formes ([ADR-0004](adr/0004-mvp-modele-espece-formes.md))
- Conventions de nommage du schéma : camelCase, `Pokemon`, relation vers la forme par défaut ([ADR-0005](adr/0005-mvp-conventions-nommage-schema.md))
- Banc d'essai : 30 questions de référence en 6 catégories ([ADR-0006](adr/0006-mvp-banc-essai-30-questions.md))
- Secrets dans Secret Manager, plus de `.env` ; services gérés, le poste local n'est qu'un client, plus de repli Docker ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md))
- Notation des questions sémantiques : grille écrite avant le tri, trois ensembles (obligatoire, acceptable, écarté), table de classement rejouable, règle du cœur de la question ([ADR-0008](adr/0008-mvp-notation-questions-semantiques.md))
- Protocole de mesure des techniques : plan croisé client × modèle, consigne et fiche communes, un seul chemin vers la base en lecture seule, notation mixte sans juge LLM, source citée vérifiée sur la trace, échec de l'agent compté faux, pilote puis 3 passes ([ADR-0009](adr/0009-mvp-protocole-mesure-techniques.md))
- Plafond de dépense : budget de 100 € sur `jleroy-labo` jusqu'au 2026-12-31, alertes par palier, coupure automatique de l'API Vertex à construire avant toute campagne ([ADR-0010](adr/0010-infra-plafond-de-depense.md))
- Claude par l'API Anthropic pour les deux cellules Claude, Gemini sur Vertex `eu` ; crédits prépayés sans recharge automatique comme plafond ([ADR-0011](adr/0011-infra-claude-par-api-anthropic.md))
- Second tour d'une paire après un échec du premier : faux d'office, sans relance ni nouvelle session ([ADR-0012](adr/0012-mvp-second-tour-apres-echec.md))
- Plafond natif de 30 € par mois sur Vertex, en plus de la coupure de l'option C ; retard réel d'un budget (jusqu'à un jour, parfois plus), rôle personnalisé, expiration du budget de 100 € au 2026-12-31 ([ADR-0013](adr/0013-infra-plafond-natif-de-vertex.md), amende l'ADR-0010)
- Revue assistée des cas « à revoir » : pré-analyse de Claude à l'aveugle, vérifiée par script, validée par Julien, et contre-épreuve de 8 cas tirés au sort qu'il revoit seul avant de voir les propositions ; `fr-1` garde ses décisions, la règle vaut pour la phase 10 et les jalons 3 et 4 ([ADR-0014](adr/0014-mvp-revue-assistee.md), amende l'ADR-0009)
- Source d'un second tour de paire (Q18, Q28) : une requête exécutée au tour précédent de la même conversation compte, si son résultat contient la réponse ; Q28 dès la revue de `en-1`, Q18 après la phase 10 (T11.0) ([ADR-0015](adr/0015-mvp-source-du-tour-precedent.md), amende l'ADR-0009)
- Clé Anthropic du banc dans le workspace « Default » ; dépense Claude bornée par la limite mensuelle de l'organisation, ramenée à 20 $, et par le solde des crédits ; remplace le workspace dédié de l'ADR-0011 ([ADR-0016](adr/0016-infra-limite-anthropic-organisation.md))
- Précisions du protocole de mesure, sans en remplacer aucun point : plafonds de l'agent (10 appels au modèle et 180 s par question, 0,50 $ par conversation) tenus par la cellule et jamais annoncés ; entrée réduite à la consigne, la fiche et l'outil de lecture, instructions du serveur ôtées ; garde-fou sur un gros résultat d'outil ; 2 reprises au plus pour tout client, règles des pannes et de la reprise d'une campagne ([ADR-0017](adr/0017-mvp-precisions-protocole-mesure.md), précise l'ADR-0009)
- Technique sans outil (GraphRAG, jalon 3) : la même fiche et une consigne de contexte, sans ce qui parle de l'outil ; des descriptions citées valent source si, réunies, leurs entrées du contexte portent toutes les valeurs de la réponse ; question encodée à la création de la campagne, hors du chrono, latence rapportée à côté du temps ([ADR-0018](adr/0018-mvp-technique-sans-outil.md), précise l'ADR-0009)
- Jeton Vertex remis au plugin GenAI d'Aura au chargement : compte de service `aura-genai` limité à la prédiction, jeton emprunté de 15 minutes, pris seulement s'il reste à encoder, passé sur stdin et masqué ([ADR-0019](adr/0019-infra-jeton-vertex-du-plugin-genai.md), précise l'ADR-0007)
- Index vectoriel des descriptions commun aux jalons 3 et 4 : `gemini-embedding-001`, 3 072 dimensions, `cosine`, sans quantification, encodé par le plugin GenAI dans la chaîne de chargement, en `europe-west1` ([ADR-0020](adr/0020-mvp-index-vectoriel-des-descriptions.md))

---

## Conventions

- **Added** : nouvelle feature
- **Changed** : modification d'une feature existante
- **Deprecated** : feature qui va disparaître
- **Removed** : feature supprimée
- **Fixed** : bug fix
- **Security** : correctif de sécurité
- **Decided** : décision tech structurante (lien vers ADR)

Bugs fixés et features livrées vont **dans le même fichier** (pas de bugs log séparé).
