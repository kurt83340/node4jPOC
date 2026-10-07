---
status: in-progress # draft | validated | in-progress | done | parked
progress: 1/33 # X/Y tasks (compté depuis tasks.md) — MAJ par /feature-done ou à la main
---

# Spec — Agent text-to-Cypher

> Vision micro : QUOI on construit et POURQUOI. Pas de "comment" (c'est dans plan.md).
> Le frontmatter `status:` = source **machine-readable** de l'état. La ROADMAP doit lui rester
> cohérente (`[ ]`=draft/validated · `[~]`=in-progress · `[x]`=done — audité par `/doc-health`).

**ID :** `002-agent-text-to-cypher`
**Date :** 2026-10-01
**Jira :** epic [NEO-2](https://frjulienleroy.atlassian.net/browse/NEO-2)

## Vision

Mesurer la technique 2 du banc d'essai : un agent LLM qui écrit lui-même le Cypher des 30 questions de référence, branché sur le graphe par le serveur MCP officiel de Neo4j, dans Claude Code puis dans un agent ADK (Google Cloud). Pour Julien, qui veut savoir, preuves à l'appui, ce que vaut un agent text-to-Cypher face au Cypher écrit à la main, et pourquoi : grâce au client ou grâce au modèle.

## User stories

### US1 — Mesurer Claude Code branché sur le graphe

**En tant que** Julien,
**je veux** poser les 30 questions à Claude Code, relié à la base par `neo4j/mcp` en lecture seule,
**afin de** noter sa justesse, ses sources, son temps de réponse et son coût, comme pour les autres techniques.

**Critères d'acceptation :**

- [ ] 3 passes comptées des 30 questions, Q18 et Q28 posées au second tour de leur conversation
- [ ] aucune lecture des fichiers du dépôt par l'agent, aucune écriture dans la base, aucune réponse sans le serveur connecté (traces à l'appui)
- [ ] chaque réponse notée (juste, partielle, fausse), avec la source citée vérifiée sur la trace, la durée, les tokens et le coût

### US2 — Séparer l'effet du client de celui du modèle

**En tant que** Julien,
**je veux** poser les mêmes questions à un agent ADK, avec le même Claude puis avec Gemini,
**afin de** savoir si un écart vient de Claude Code ou du modèle.

**Critères d'acceptation :**

- [ ] 3 passes comptées pour ADK + Claude Sonnet 5.5 et pour ADK + Gemini 3.8 Flash, avec la même consigne, la même fiche et le même serveur MCP
- [ ] un score par cellule et par catégorie ([ADR-0006](../../adr/0006-mvp-banc-essai-30-questions.md)), avec l'écart entre passes

### US3 — Une fiche de schéma commune

**En tant que** Julien,
**je veux** une fiche de schéma unique (modèle, règles, valeurs possibles, exemples), donnée à l'identique à toutes les techniques des jalons 2 à 4,
**afin que** la comparaison ne dépende pas de ce que chaque outil devine du schéma.

**Critères d'acceptation :**

- [ ] la fiche reprend les règles et cas limites listés sous le jalon 2 de la [ROADMAP](../../ROADMAP.md), avec des valeurs vérifiées dans la base
- [ ] 6 à 8 exemples qui s'exécutent, dont aucun ne cite une entité des 30 questions ni de leurs réponses (test)

### US4 — Mesurer l'effet d'un schéma anglais

**En tant que** Julien,
**je veux** comparer la même cellule sur le schéma français et sur un schéma aux identifiants anglais, valeurs inchangées,
**afin de** trancher l'hypothèse laissée ouverte par l'[ADR-0005](../../adr/0005-mvp-conventions-nommage-schema.md).

**Critères d'acceptation :**

- [ ] bascule prouvée : les 27 requêtes de référence, traduites, rendent `questions/attendu/` à l'identique
- [ ] 3 passes ADK + Gemini sur le schéma anglais, comparées question par question aux passes françaises
- [ ] retour au français prouvé : `verifier.sh` et `questions.sh --verifier` conformes

### US5 — Retrouver un nom mal orthographié

**En tant que** Julien,
**je veux** un index plein texte sur les noms,
**afin que** « Dracofeu » (Q19) mène à Dracaufeu.

**Critères d'acceptation :**

- [ ] index créé par la chaîne de chargement, contrôlé par `verifier.sh` (34 contrôles), idempotence intacte
- [ ] la recherche approchée `dracofeu~` renvoie Dracaufeu

## Scope IN

- `neo4j/mcp` v1.6.0 en local, en lecture seule, lancé par `scripts/` ; Claude via Vertex pour toutes les cellules Claude
- le harnais `banc/` (Python), la liste `questions/banc.toml`, la consigne et la fiche communes, la notation mixte, les traces et les mesures
- l'index plein texte ; le paramètre `$proposee` du contrôle de Q2
- la mesure FR/EN par bascule de l'instance
- les résultats de la technique 2 et son effort de mise en place, prêts pour le tableau comparatif

## Scope OUT

- MCP for Aura, Agent Runtime, Gemini Enterprise et Aura Agent (jalon 4) ; GraphRAG (jalon 3) ; mémoire d'agent (jalon 5)
- d'autres modèles (Opus 5.5, Gemini 3.1 Pro), la variante « `get-schema` sans fiche », le client n8n
- un juge LLM ; le chronométrage de la technique 1 (tâche à part)

## Métriques de succès

- 9 séries comptées (3 cellules × 3 passes), 3 séries anglaises et 1 passe française de contrôle, notées et versionnées
- coût LLM total d'au plus 35 $, pilote compris, recoupé avec l'export de facturation
- base de référence intacte à la fin : 34/34 contrôles, 27/27 réponses
- revue humaine contenue : environ 200 cas sur toute la spec, soit environ 3 h

## Dépendances

- NEO-13 clos (période creuse de 72 h) avant toute requête sur la base : fait le 2026-10-07
- accès aux modèles Claude sur Vertex (Model Garden) pour `jleroy-labo`
- spec [001-socle-donnees](../001-socle-donnees/spec.md) livrée (graphe, `questions/attendu/`)

## Liens

- Research : [research.md](research.md)
- Plan technique : [plan.md](plan.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : [0002](../../adr/0002-cadrage-environnement-cible-google-cloud.md), [0005](../../adr/0005-mvp-conventions-nommage-schema.md), [0006](../../adr/0006-mvp-banc-essai-30-questions.md), [0007](../../adr/0007-infra-secrets-et-services-geres.md), [0008](../../adr/0008-mvp-notation-questions-semantiques.md) ; protocole de mesure : [0009](../../adr/0009-mvp-protocole-mesure-techniques.md)
