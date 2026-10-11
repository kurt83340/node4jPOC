# node4jPOC · Banc d'essai agentique Neo4j

> **Initiative** · porteur : Julien Leroy · lancée le 2026-09-28 · **jalon 1 livré le 2026-10-01 et clos le 2026-10-07 (tag `jalon-1`), jalon 2 en cours**
>
> Suivi : [tableau Jira NEO](https://frjulienleroy.atlassian.net/jira/software/projects/NEO/boards/40) · [chronologie](https://frjulienleroy.atlassian.net/jira/software/projects/NEO/boards/40/timeline) · [ROADMAP](.claude/docs/ROADMAP.md)

## 🎯 Objectif

Choisir, preuves à l'appui, les techniques agentiques de Neo4j qui valent le coup. Quatre techniques répondent aux mêmes 30 questions, sur le même graphe Pokémon en français. Un tableau comparatif les départage sur cinq critères : réponse juste, sources citées, temps de réponse, coût, effort de mise en place.

## 🧭 Pourquoi

- **Apprendre en construisant.** Aucune stack n'est imposée : c'est le POC qui tranche, et chaque choix est expliqué.
- **Pouvoir le transposer** à une entreprise full Google Cloud ([ADR-0002](.claude/docs/adr/0002-cadrage-environnement-cible-google-cloud.md)). Chaque technique est mesurée dans sa variante Google Cloud : ADK, embeddings Gemini, Agent Runtime, Gemini Enterprise. dbt reste hors POC.

## 🗺️ Vue d'ensemble

![Les CSV de PokéAPI sont chargés dans un graphe AuraDB, que quatre techniques interrogent avec les mêmes 30 questions ; leurs mesures remplissent le tableau comparatif](.claude/docs/conception/diagrams/vue-ensemble.png)

Le graphe est chargé une seule fois, en Cypher pur, par un script rejouable. Les techniques ne font que le lire, avec les mêmes questions : seul l'écart entre leurs réponses compte. Composants et modèle du graphe : [ARCHITECTURE](.claude/docs/conception/ARCHITECTURE.md).

## 🚩 Jalons

Un jalon, c'est un epic Jira et une technique mesurée.

| Jalon | Résultat visé                                                  | Technique                         | Spec                                                                            | Jira                                                      | État      |
| ----- | -------------------------------------------------------------- | --------------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------- | --------- |
| 1     | Le graphe chargé et vérifié, avec les 30 réponses de référence | Cypher à la main                  | [001-socle-donnees](.claude/docs/specs/001-socle-donnees/spec.md)               | [NEO-1](https://frjulienleroy.atlassian.net/browse/NEO-1) | livré     |
| 2     | Un agent text-to-Cypher mesuré sur les 30 questions            | `neo4j/mcp`, agent ADK            | [002-agent-text-to-cypher](.claude/docs/specs/002-agent-text-to-cypher/spec.md) | [NEO-2](https://frjulienleroy.atlassian.net/browse/NEO-2) | en cours  |
| 3     | GraphRAG sur les descriptions, mesuré sur les 30 questions     | vecteurs Gemini et graphe         | à écrire                                                                        | [NEO-3](https://frjulienleroy.atlassian.net/browse/NEO-3) | à venir   |
| 4     | Les agents gérés mesurés, le tableau comparatif livré          | Aura Agent, Agent Runtime         | à écrire                                                                        | [NEO-4](https://frjulienleroy.atlassian.net/browse/NEO-4) | à venir   |
| 5     | La mémoire d'agent                                             | `neo4j-agent-memory`, Memory Bank | —                                                                               | —                                                         | en option |
| 6     | Les briques data Google Cloud                                  | Graph Analytics, CDC → Pub/Sub    | —                                                                               | —                                                         | en option |

**Jalon 2, résultats** ([rapport de la technique 2](banc/resultats/technique-2.md)) : avec Claude Sonnet 5.5, l'agent
text-to-Cypher obtient 27,5 (Claude Code) et 27,8 (ADK) sur 30 ; avec Gemini 3.8 Flash, 20,7, faute de conclure
dans ses 10 appels au modèle. Le client compte peu, le modèle beaucoup ; un schéma aux identifiants anglais n'apporte
rien de mesurable.

## ✅ Critères de réussite

1. **Une vérité de référence** : les 30 questions ont leur réponse attendue, calculée en Cypher pour 27 d'entre elles ; Q10, Q29 et Q30, comportementales, se notent par une règle (jalon 1).
2. **Une mesure par technique** : chacune passe les 30 questions, notées sur les cinq critères, avec un score par catégorie ([ADR-0006](.claude/docs/adr/0006-mvp-banc-essai-30-questions.md)).
3. **Un tableau comparatif** qui croise technique et question, livré au jalon 4.
4. **Tout se rejoue** : le chargement ne crée aucun doublon, et les questions se relancent par script.

## 📦 Périmètre

| Dans l'initiative                                                   | Hors de l'initiative                                                                                            |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| Les quatre techniques et leurs variantes Google Cloud               | dbt, qui relève de l'entreprise ([ADR-0002](.claude/docs/adr/0002-cadrage-environnement-cible-google-cloud.md)) |
| Les données PokéAPI, textes en français                             | Graph Data Science for BigQuery, encore expérimental                                                            |
| Les offres gratuites d'abord (AuraDB Free) : le coût est un critère | Spanner Graph, qui n'est plus Neo4j                                                                             |
| En option, à décider plus tard : les jalons 5 et 6                  | Tout usage hors apprentissage perso : l'univers Pokémon appartient à Nintendo                                   |

## ⚠️ Risques

- **La limite d'AuraDB Free** : 200 000 nœuds et 400 000 relations (lue à la création de l'instance, le 2026-09-30). Le graphe chargé en occupe 4,4 % et 28,4 %.
- **Une instance Free se met en pause** après 72 h sans activité, et disparaît après 30 jours de pause. Le job quotidien `reveil-aura` l'évite ; le chargement rejouable sert de filet.
- **Des coûts peuvent tourner en tâche de fond** : Aura Agent exposé, agent sur Agent Runtime, instance Business Critical. Tout éteindre après chaque session de mesure.
- **Plusieurs briques sont récentes ou en preview**, et leur doc est en retard : se fier aux notes de version.

## 🧱 Décisions

| ADR                                                                       | Décision                                                                              |
| ------------------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| [0001](.claude/docs/adr/0001-mvp-jeu-de-donnees-pokeapi.md)               | Jeu de données : Pokémon, CSV PokéAPI en français                                     |
| [0002](.claude/docs/adr/0002-cadrage-environnement-cible-google-cloud.md) | Environnement cible Google Cloud, dbt hors POC                                        |
| [0003](.claude/docs/adr/0003-mvp-chargement-cypher-pur.md)                | Chargement en Cypher pur (`LOAD CSV`)                                                 |
| [0004](.claude/docs/adr/0004-mvp-modele-espece-formes.md)                 | Modèle du graphe : l'espèce et toutes ses formes                                      |
| [0005](.claude/docs/adr/0005-mvp-conventions-nommage-schema.md)           | Conventions de nommage du schéma                                                      |
| [0006](.claude/docs/adr/0006-mvp-banc-essai-30-questions.md)              | Banc d'essai : 30 questions en 6 catégories                                           |
| [0007](.claude/docs/adr/0007-infra-secrets-et-services-geres.md)          | Secrets dans Secret Manager, services gérés seulement                                 |
| [0008](.claude/docs/adr/0008-mvp-notation-questions-semantiques.md)       | Notation des questions sémantiques : grille, trois ensembles                          |
| [0009](.claude/docs/adr/0009-mvp-protocole-mesure-techniques.md)          | Protocole de mesure : plan croisé, notation mixte sans juge LLM, pilote puis 3 passes |
| [0010](.claude/docs/adr/0010-infra-plafond-de-depense.md)                 | Plafond de dépense : budget de 100 €, coupure automatique de Vertex                   |
| [0011](.claude/docs/adr/0011-infra-claude-par-api-anthropic.md)           | Claude par l'API Anthropic, plafonné par des crédits prépayés                         |
| [0012](.claude/docs/adr/0012-mvp-second-tour-apres-echec.md)              | Second tour d'une paire après un échec : faux d'office                                |
| [0013](.claude/docs/adr/0013-infra-plafond-natif-de-vertex.md)            | Plafond natif mensuel de Vertex, en plus de la coupure de l'option C                  |
| [0014](.claude/docs/adr/0014-mvp-revue-assistee.md)                       | Revue assistée : pré-analyse de Claude, décision de Julien, contre-épreuve            |
| [0015](.claude/docs/adr/0015-mvp-source-du-tour-precedent.md)             | Source d'un second tour : une requête du tour précédent compte                        |

## 🔗 Suivi et documentation

- **Jira NEO** : le [tableau](https://frjulienleroy.atlassian.net/jira/software/projects/NEO/boards/40) et la [chronologie](https://frjulienleroy.atlassian.net/jira/software/projects/NEO/boards/40/timeline). Un epic par jalon, un ticket par phase de travail.
- **Dans le dépôt** : la [ROADMAP](.claude/docs/ROADMAP.md) pour l'état des jalons, le [cadrage](.claude/docs/cadrage/README.md) pour le besoin, les [30 questions](questions/README.md), l'[ARCHITECTURE](.claude/docs/conception/ARCHITECTURE.md).

## 🛠️ Démarrer

Prérequis : Java 21, `cypher-shell` 2026.09.0, une instance AuraDB Free et `gcloud` connecté au compte qui lit les secrets du projet `jleroy-labo` ([ACCESS](.claude/docs/ACCESS.md)).

```bash
git clone https://github.com/kurt83340/node4jPOC.git
cd node4jPOC
gcloud auth login             # identifiants lus dans Secret Manager : aucun fichier de secrets
pre-commit install            # garde-fou secrets : gitleaks avant chaque commit
scripts/charger.sh --ping     # Aura répond ? 0 oui, 2 erreur technique
scripts/charger.sh --go-no-go # contrôles en lecture seule avant chargement : 0 go, 1 no-go, 2 erreur technique
scripts/charger.sh --tout     # charge les fichiers cypher/ dans l'ordre ; une relance ne crée rien ; journal dans logs/
scripts/verifier.sh           # compare la base aux valeurs attendues : 0 conforme, 1 écart, 2 erreur technique
scripts/charger.sh --idempotence # efface, charge deux fois et compare : 0 idempotent, 1 écart, 2 erreur technique
scripts/questions.sh --verifier  # rejoue les 27 questions de référence : 0 conforme, 1 écart, 2 erreur technique
```

Un fichier `cypher/` par groupe de données : `scripts/verifier.sh --section <nom>` n'en contrôle qu'un (`types`, `pokemon`, `attaques`…).

Mesurer une technique (jalon 2, payant : [RUNBOOK](.claude/docs/RUNBOOK.md)) :

```bash
scripts/banc.sh lancer --campagne <id> --passes 3 --plafond-usd <$>    # clé Anthropic lue dans Secret Manager
uv run --directory banc python -m banc rapport --campagne <id> --complet # scores, temps, coût
```

Prérequis du banc, en plus : uv, `neo4j-mcp` v1.6.0, la clé Anthropic du banc et l'ADC de gcloud pour Vertex ([ACCESS](.claude/docs/ACCESS.md)).

## Contact

- Owner technique : Julien Leroy (fr.leroyjulien@gmail.com)
- Owner business POC interne : Julien Leroy (fr.leroyjulien@gmail.com)

---

> 💡 Ce projet utilise le **[template Claude Code](.claude/STRUCTURE.md)** (convention 2026). Usage quotidien : [USAGE.md](.claude/USAGE.md).
