# Research — Conception macro projet

> Brainstorm initial + exploration d'options + capture des pivots ultérieurs.
> Au niveau **projet entier** (pas au niveau d'une feature — celui-là vit dans `specs/00X-feature/research.md`).

## 2026-09-28 — Brainstorm initial

### Question de départ

Quelles techniques de l'écosystème agentique de Neo4j répondent le mieux à des questions en français sur un même graphe, selon cinq critères : réponse juste, sources citées, temps de réponse, coût, effort de mise en place ? Demande d'origine : [cadrage](../cadrage/README.md).

### Faits relevés (brief)

> Relevés le 2026-09-26 et transmis dans le [brief](../cadrage/documents/2026-09-28-brief-poc.md). **À revérifier dans la doc à jour avant d'utiliser chaque brique** : les versions sont très récentes et la doc est parfois en retard.
> Quand un fait est revérifié, ajouter « (revérifié le YYYY-MM-DD) » ; s'il a changé, le barrer et noter la nouvelle valeur.

#### Techniques candidates

| Brique                             | Faits                                                                                                                                                                                                                                          | Source                                                                                                                                                     |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `neo4j/mcp` (serveur MCP officiel) | v1.6.0 du 2026-09-10 ; outils `get-schema`, `read-cypher`, `write-cypher`, `list-gds-procedures` ; mode lecture seule possible ; nécessite APOC. La v1.6.0 déprécie les variables `NEO4J_*` au profit de `NEO4J_MCP_*`, doc pas encore à jour. | [release v1.6.0](https://github.com/neo4j/mcp/releases/tag/v1.6.0) · [configuration des clients](https://neo4j.com/docs/mcp/current/client-configuration/) |
| MCP for Aura (hébergé)             | Inclus dans l'offre Free, connexion OAuth. Tout client MCP s'y branche : Claude Code, n8n (en HTTP streamable), ADK…                                                                                                                           | [MCP for Aura](https://neo4j.com/docs/mcp/current/mcp-for-aura/)                                                                                           |
| `neo4j-graphrag` (Python)          | v1.21.0 ; Claude via `AnthropicLLM` ; pas d'embedder Anthropic. L'embedder par défaut (all-MiniLM-L6-v2) ne gère que l'anglais : il faut un embedder multilingue.                                                                              | [PyPI](https://pypi.org/project/neo4j-graphrag/)                                                                                                           |
| Recherche vectorielle en Cypher    | Clause `SEARCH` ; `db.index.vector.queryNodes` déprécié depuis 2026.04.                                                                                                                                                                        | [Cypher manual — vector indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)                                    |
| Aura Agent                         | Solution gérée, disponible depuis le 2026-02-03 ; agent généré à partir du schéma, déployé en MCP ou en REST. Sur AuraDB Free : lecture seule, pas d'historique des conversations.                                                             | [Aura Agent](https://neo4j.com/docs/aura/aura-agent/)                                                                                                      |
| `neo4j-agent-memory` (option)      | Python 0.6.0, TypeScript 0.5.0 ; expérimental.                                                                                                                                                                                                 | [Neo4j Labs](https://neo4j.com/labs/agent-memory/)                                                                                                         |
| Pub/Sub (hors périmètre)           | Passe par du CDC, réservé aux offres Enterprise.                                                                                                                                                                                               | [CDC](https://neo4j.com/docs/cdc/current/)                                                                                                                 |

#### Jeu de données — PokéAPI (CSV)

Source : [data/v2/csv](https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv). Tous les chiffres ci-dessous ont été revérifiés le 2026-09-28 sur le commit figé `168b1e8` (détail : [spec 001](../specs/001-socle-donnees/research.md)). Licence BSD-3 pour PokéAPI ; l'univers Pokémon appartient à Nintendo, donc usage d'apprentissage perso uniquement.

| Fait                                                                                                               | Fichier                           |
| ------------------------------------------------------------------------------------------------------------------ | --------------------------------- |
| Le français correspond à `language_id = 5`                                                                         | `languages.csv`                   |
| 1 025 espèces, toutes avec leur nom français                                                                       | `pokemon_species_names.csv`       |
| 1 351 lignes, formes alternatives comprises                                                                        | `pokemon.csv`                     |
| Types traduits en français ; garder les 18 types classiques, ignorer Stellaire, ??? et Obscur                      | `type_names.csv`                  |
| Table des faiblesses : 324 lignes (18 × 18)                                                                        | `type_efficacy.csv`               |
| 7 116 descriptions en français couvrant 898 espèces, souvent répétées d'un jeu à l'autre                           | `pokemon_species_flavor_text.csv` |
| 638 321 lignes (une par jeu et par méthode d'apprentissage), soit 99 509 couples Pokémon–attaque distincts         | `pokemon_moves.csv`               |
| `moves` 937 lignes · `abilities` 374 · `pokemon_types` 2 116 · `pokemon_abilities` 2 943 · `pokemon_evolution` 676 | fichiers du même nom              |
| Graphe complet estimé : environ 10 000 nœuds et 113 000 relations                                                  | calcul du brief                   |

#### Infrastructure

| Fait                                                                                                                                                                                                                                                                                    | Source                                                                                                                    |
| --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| Limites d'AuraDB Free contradictoires : 200 000 nœuds et 400 000 relations (FAQ), 50 000 et 175 000 (page produit). Vraie limite à noter à la création. Au 2026-09-28 : les chiffres de la page produit reprennent l'annonce de lancement de 2021, et aucune page de la doc n'en donne. | [FAQ](https://neo4j.com/cloud/platform/aura-graph-database/faq/) · [page produit](https://neo4j.com/free-graph-database/) |
| L'instance Free se met en pause après 72 h sans activité, puis elle est supprimée après 30 jours de pause ; une seule instance Free par compte (revérifié le 2026-09-28)                                                                                                                | [doc Aura — instance actions](https://neo4j.com/docs/aura/managing-instances/instance-actions/)                           |
| Repli : Neo4j en local avec Docker, image `neo4j:2026.09.0`, sans limite                                                                                                                                                                                                                | brief (tag à confirmer sur Docker Hub)                                                                                    |

### Techniques à comparer (les « options » de ce POC)

Ici, les options ne s'excluent pas : le POC les compare toutes sur les mêmes questions. Leurs pour et contre se **mesurent**, ils ne se supposent pas.

1. **Cypher à la main** (jalon 1) : vérité de référence.
2. **Agent text-to-Cypher via MCP** (jalon 2) : `neo4j/mcp` en local ou MCP for Aura hébergé.
3. **GraphRAG sur les descriptions** (jalon 3) : embedder multilingue à choisir.
4. **Aura Agent** (jalon 4).
5. _(option)_ **Mémoire d'agent**.

### Modèle de données proposé (à challenger au jalon 1)

- Nœuds : `Pokemon`, `Type`, `Attaque`, `Talent`, `Description`.
- Relations aux noms explicites en français, ce qui aide aussi le text-to-Cypher : `A_LE_TYPE` ; entre types, `SUPER_EFFICACE_CONTRE`, `PEU_EFFICACE_CONTRE` et `SANS_EFFET_CONTRE` ; `EVOLUE_EN` ; `APPREND` (une relation par couple Pokémon–attaque, méthodes et niveau en propriétés) ; `A_LE_TALENT` ; `A_POUR_DESCRIPTION`.
- Statistiques (PV, attaque, défense, vitesse…) en propriétés du nœud `Pokemon`.

### Questions ouvertes initiales

- Espèces ou formes (Méga, Alola…) ? Commencer par les formes par défaut ? → jalon 1 (options de modèle)
- Vraie limite d'AuraDB Free ? → 200 000 nœuds et 400 000 relations, lue le 2026-09-30 ([ACCESS](../ACCESS.md))
- Descriptions répétées : dédoublonner avant la recherche vectorielle ? → jalon 1 (modèle), jalon 3 (recherche)
- Quel embedder multilingue ? → jalon 3
- Les 7 autres questions de référence ? → réglé le 2026-09-29 : 30 questions en 6 catégories ([questions/README.md](../../../questions/README.md))

### Hypothèses retenues

- Textes en français uniquement (`language_id = 5`).
- Les 18 types classiques.
- AuraDB Free d'abord (Aura Agent en a besoin), Docker local en repli.
- Chargement idempotent : relancer le script ne crée pas de doublons.

### Décisions issues du brainstorm

1. Jeu de données PokéAPI → [ADR-0001](../adr/0001-mvp-jeu-de-donnees-pokeapi.md)
2. Langage du script de chargement et variante du modèle → à décider au jalon 1

## 2026-09-28 — Exploration : Google Cloud et dbt

> **Déclencheur** : l'entreprise de Julien est « full GCP avec dbt » ; il veut un setup transposable, quitte à payer un peu (échange du 2026-09-28). Le périmètre reste à trancher (pivot).
> **Sources** : trois rapports `explore-docs` du 2026-09-28 (pages officielles consultées ce jour). Prix en USD hors taxes relevés ce jour, à recouper dans la console de facturation.

### Renommages à connaître

- Vertex AI s'appelle **Gemini Enterprise Agent Platform** depuis le 2026-04-22 ; Agent Engine devient **Agent Runtime** (ressource API `ReasoningEngine`). SDK : `google-cloud-aiplatform` 2.0.1 (module `runtimes`) et `google-genai` avec `genai.Client(enterprise=True)`. [blog Google](https://cloud.google.com/blog/products/ai-machine-learning/introducing-gemini-enterprise-agent-platform)
- dbt v2 est sorti le 2026-09-14 : le moteur Fusion s'appelle désormais « dbt » (gratuit, licence propriétaire) et dbt Core devient « dbt OSS » (Apache 2.0). PyPI : `dbt` 2.0.6 (Python ≥ 3.11), ou la voie 1.x `dbt-core` 1.12.5 + `dbt-bigquery` 1.12.1. [licences](https://www.getdbt.com/licenses-faq) · [versions](https://docs.getdbt.com/docs/dbt-versions/core)

### Coût des briques pour ce POC

| Brique                                           | Coût                                                                                                                                             | Point d'attention                                                                                                          | Source                                                                                                                                                                          |
| ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| AuraDB Free                                      | 0 $                                                                                                                                              | hébergée uniquement sur GCP (europe-west1, us-central1, asia-southeast1)                                                   | [doc Aura](https://neo4j.com/docs/aura/security/ip-addresses/)                                                                                                                  |
| AuraDB Professional via Google Cloud Marketplace | 65 $/mois (0,09 $/h), essai de 14 jours                                                                                                          | facturé sur la note GCP ; rôle Billing Account Administrator ; impossible depuis un compte GCP en essai gratuit            | [pricing](https://neo4j.com/pricing/) · [Marketplace](https://neo4j.com/docs/aura/cloud-providers/)                                                                             |
| BigQuery + dbt                                   | 0 $ (franchise mensuelle : 1 Tio de requêtes, 10 Gio de stockage)                                                                                | compte de facturation requis ; le bac à sable sans carte fait expirer les tables à 60 jours et interdit le DML             | [sandbox](https://docs.cloud.google.com/bigquery/docs/sandbox) · [free](https://docs.cloud.google.com/free/docs/free-cloud-features)                                            |
| dbt platform (ex-dbt Cloud)                      | 0 $ (offre Developer, 1 siège)                                                                                                                   | dbt en local suffit                                                                                                        | [pricing](https://www.getdbt.com/pricing)                                                                                                                                       |
| Embeddings `gemini-embedding-001`                | ~0,03 $ pour les 5 200 descriptions                                                                                                              | 0,15 $ par million de tokens                                                                                               | [prix](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)                                                                                         |
| LLM pour ~100 questions                          | ~1 à 7 $ (Gemini Flash, Claude Sonnet 5) ; ~13 $ avec Claude Opus 5.5                                                                            | Claude sur l'endpoint `eu` : +10 %                                                                                         | [prix Claude](https://platform.claude.com/docs/en/about-claude/pricing)                                                                                                         |
| Agent ADK sur Agent Runtime                      | 0 $ dans la franchise mensuelle (50 vCPU-heures, 100 Go-heures)                                                                                  | régler `min_instances=0` : sinon jusqu'à ~270 $/mois si l'instance allumée est facturée (non confirmé)                     | [prix agents](https://cloud.google.com/products/gemini-enterprise-agent-platform/pricing)                                                                                       |
| Memory Bank                                      | < 1 $                                                                                                                                            | facturé depuis le 2026-09-01 ; souvenirs stockés hors du graphe                                                            | [setup](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup)                                                                                 |
| Aura Agent exposé en MCP ou REST                 | 0,35 $ par « heure d'agent » (unité exacte non confirmée)                                                                                        | un agent interne est gratuit ; l'éteindre après les mesures                                                                | [blog Neo4j](https://neo4j.com/blog/agentic-ai/neo4j-launches-aura-agent/)                                                                                                      |
| Gemini Enterprise                                | essai de 30 jours (vu seulement en extrait de recherche), puis 21 $ (Business) à 30 $ (Standard) par siège et par mois                           | publier un agent ADK maison : GA ; agents de la Marketplace (dont « Neo4j Agent ») : Preview                               | [éditions](https://docs.cloud.google.com/gemini/enterprise/docs/editions) · [agent ADK](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-an-adk-agent)  |
| Aura Graph Analytics                             | 0 $ sur Free (sessions de 2 Go, 4 h maximum) ; sinon 0,40 $ par Go et par heure                                                                  | pas de connecteur BigQuery natif : BigQuery → pandas → session → résultats réécrits dans BigQuery                          | [AGA](https://neo4j.com/docs/aura/graph-analytics/)                                                                                                                             |
| Neo4j Virtual Graph                              | au tarif d'Aura Professional depuis le 2026-09-01                                                                                                | Cypher traduit en SQL sur BigQuery, sans copie des données ; Preview depuis le 2026-07-23                                  | [blog](https://neo4j.com/blog/auradb/neo4j-virtual-graph-is-now-in-public-preview/)                                                                                             |
| CDC → Pub/Sub                                    | 0,40 $/h sur Business Critical (2 Go minimum : créer, tester, supprimer), ou 0 $ en local (édition développeur d'Enterprise + Kafka sous Docker) | pas de connecteur natif : Neo4j Connector for Kafka → Kafka Connect géré soi-même → Pub/Sub ; une pause remet le CDC à OFF | [CDC Aura](https://neo4j.com/docs/cdc/current/get-started/aura/) · [blog Pub/Sub](https://neo4j.com/blog/graph-database/seamless-data-pipeline-neo4j-and-google-cloud-pub-sub/) |

### Équivalents GCP des techniques du banc d'essai

- **Agent text-to-Cypher** : agent ADK (`google-adk` 2.10.0) avec `McpToolset` en HTTP streamable vers `neo4j/mcp` v1.6.0 (identifiants transmis à chaque requête ; variables `NEO4J_MCP_TRANSPORT_MODE` et `NEO4J_MCP_READ_ONLY`), ou vers **MCP Toolbox for Databases** v1.13.1, qui a une source `neo4j` (outils `neo4j-execute-cypher` avec `readOnly`, `neo4j-schema`). [ADK MCP](https://adk.dev/tools-custom/mcp-tools/) · [Toolbox Neo4j](https://mcp-toolbox.dev/integrations/neo4j/source/) · [Labs ADK](https://neo4j.com/labs/genai-ecosystem/genai-frameworks/google-adk/)
- **GraphRAG** : `neo4j-graphrag` 1.21.0 avec `GeminiEmbedder` (`gemini-embedding-001`, 768 dimensions, `enterprise=True`) et `GeminiLLM` (toujours préciser `model_name`). Les classes `VertexAI*` sont en voie de dépréciation. `neo4j-graphrag` n'appelle pas Claude via Vertex : il faudrait une sous-classe `AnthropicVertex`, non testée. [PyPI](https://pypi.org/project/neo4j-graphrag/) · [CHANGELOG](https://github.com/neo4j/neo4j-graphrag-python/blob/main/CHANGELOG.md)
- **Agent géré** : agent ADK hébergé sur Agent Runtime et publiable dans Gemini Enterprise (une app `eu` exige une région `europe-*` ; Model Armor requis). « Neo4j Agent » de la Marketplace est un agent partenaire A2A (code de référence Neo4j Labs : ADK + A2A sur Cloud Run), distinct d'Aura Agent. [doc GE](https://docs.cloud.google.com/gemini/enterprise/docs/register-and-manage-marketplace-agents)
- **Mémoire d'agent** : Memory Bank (géré, hors du graphe) face à `neo4j-agent-memory` 0.6.0 (dans le graphe, avec un `Neo4jMemoryService` pour ADK).
- **Chargement** : aucun adaptateur dbt pour Neo4j. Voies BigQuery → Neo4j : script Python, template Dataflow `Google_Cloud_to_Neo4j` (Preview), import Aura depuis BigQuery. Détail : [spec 001](../specs/001-socle-donnees/research.md).

### Pièges pour l'entreprise

- Les clés JSON de compte de service sont bloquées par défaut dans les organisations GCP créées depuis le 2024-05-03 : préférer `gcloud auth application-default login` (OAuth) pour dbt et les scripts. [doc IAM](https://docs.cloud.google.com/iam/docs/keys-create-delete)
- dbt v2 n'est stable que depuis le 2026-09-16 : l'entreprise tourne probablement en 1.x (même langage de projet).
- dbt v2 exige la Storage Read API (`roles/bigquery.readSessionUser`) ; sa compatibilité avec le bac à sable n'est pas documentée.

### Restent hors périmètre

- « Graph Data Science for BigQuery » (expérimental), Spanner Graph (ce n'est plus Neo4j), Composer / Airflow géré (trop lourd pour un POC).

## Pivot 2026-09-28 — Environnement cible Google Cloud

**Contexte** : l'entreprise de Julien est full GCP avec dbt ; il veut un setup transposable, même payant ([CR](../cadrage/reunions/2026-09-28-pivot.md)). Faits et coûts : § « Exploration : Google Cloud et dbt » ci-dessus.

**Options explorées** :

- Option A' — Rester neutre (brief) : briques Google Cloud hors périmètre. Non transposable.
- Option B' — Google Cloud avec dbt dans le POC. dbt ne sert aucune technique du banc d'essai et retarde le premier graphe chargé.
- Option C' — Google Cloud, dbt hors POC : chaque technique gagne sa variante Google Cloud, les briques data forment un jalon optionnel.

**Décision** : C' → [ADR-0002](../adr/0002-cadrage-environnement-cible-google-cloud.md). Découpage en 6 jalons : [ROADMAP](../ROADMAP.md).

---

## Template pour pivots ultérieurs

Si la hiérarchie demande un pivot, append ici une section datée :

```markdown
## YYYY-MM-DD — Pivot [titre]

### Contexte du pivot

Pourquoi on doit changer (réunion, mail, ticket → voir cadrage/reunions/)

### Nouvelles options explorées

- Option A : ...
- Option B : ...

### Décision retenue

- ...

### Conséquences

- PRD bumpé v1.0 → v2.0
- ROADMAP refondu (voir ../ROADMAP.md section v2)
- ADR-00XX créé si pivot tech
```
