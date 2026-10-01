---
status: done # draft | validated | in-progress | done | parked
progress: 16/16 # X/Y tasks (compté depuis tasks.md) — MAJ par /feature-done ou à la main
---

# Spec — Socle de données

> Vision micro : QUOI on construit et POURQUOI. Pas de "comment" (c'est dans plan.md).
> Le frontmatter `status:` = source **machine-readable** de l'état. La ROADMAP doit lui rester
> cohérente (`[ ]`=draft/validated · `[~]`=in-progress · `[x]`=done — audité par `/doc-health`).

**ID :** `001-socle-donnees`
**Date :** 2026-09-28

## Vision

Un graphe Pokémon fiable dans AuraDB, chargé par un script réexécutable, et 30 questions de référence résolues en Cypher : la vérité contre laquelle on mesurera les autres techniques du banc d'essai (jalons 2 à 4). C'est aussi la technique n°1 du comparatif, « Cypher à la main ».

## User stories

### US1 — Charger les données

**En tant qu'**apprenant de l'écosystème Neo4j,
**je veux** charger les CSV PokéAPI (textes en français) dans AuraDB par un script,
**afin d'**avoir un graphe à interroger avec toutes les techniques.

**Critères d'acceptation :**

- [x] Le script charge les nœuds et relations du modèle retenu, depuis un commit PokéAPI figé ([ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md)).
- [x] Une 2e exécution ne crée aucun doublon : mêmes nombres de nœuds et de relations.
- [x] Les identifiants sont lus dans Secret Manager au lancement, jamais affichés, écrits sur le disque ni committés ([ADR-0007](../../adr/0007-infra-secrets-et-services-geres.md)).

### US2 — Documenter le modèle

**En tant qu'**apprenant,
**je veux** un modèle de graphe documenté (nœuds, relations, propriétés, et le pourquoi de chaque choix),
**afin de** comprendre les compromis de modélisation et d'aider le text-to-Cypher des jalons suivants.

**Critères d'acceptation :**

- [x] Schéma du modèle et justification de chaque choix (espèces ou formes, descriptions, attaques…) documentés.
- [x] Une contrainte d'unicité par type de nœud, sauf `Description` (sans clé : couple (Pokémon, texte) unique par `MERGE`, contrôlé par `verifier.sh`, plan D2).

### US3 — Questions de référence

**En tant qu'**apprenant,
**je veux** 30 questions de référence (6 catégories de 5) avec leur réponse attendue calculée en Cypher,
**afin de** mesurer les autres techniques contre une vérité établie.

**Critères d'acceptation :**

- [x] 30 questions en 6 catégories, chacune avec sa technique visée ([questions/README.md](../../../../questions/README.md)).
- [x] Chaque question a sa requête Cypher (ou, pour Q10, Q29 et Q30, sa règle de notation) et sa réponse attendue, rejouables.
- [x] Q1 (« Quelles attaques font le plus mal à Dracaufeu ? ») donne bien Roche ×4.

## Scope IN

- Instance AuraDB Free (créée par Julien) et vraie limite notée.
- Chargement idempotent en Cypher pur (`LOAD CSV` depuis le commit figé), exécuté par `cypher-shell` ([ADR-0003](../../adr/0003-mvp-chargement-cypher-pur.md)).
- Modèle espèce + toutes les formes ([ADR-0004](../../adr/0004-mvp-modele-espece-formes.md)), documenté.
- 30 questions de référence : 27 requêtes Cypher et 3 règles de notation, avec leurs réponses attendues.

## Scope OUT

- Agent text-to-Cypher via MCP (jalon 2).
- Embeddings et index vectoriel (jalon 3) : les descriptions sont chargées, pas vectorisées.
- Aura Agent et tableau comparatif (jalon 4).

## Métriques de succès

- Nombres de nœuds et de relations chargés = nombres attendus, calculés depuis les CSV.
- 2e exécution du script : 0 nœud et 0 relation créés.
- 30 questions sur 30 avec une réponse attendue rejouable (requête ou règle).
- Volume total sous la vraie limite d'AuraDB Free.

## Dépendances

- Instance AuraDB Free créée et identifiants dans Secret Manager : fait le 2026-09-30 (NEO-6).
- [ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md) : jeu de données PokéAPI.

## Liens

- Research : [research.md](research.md)
- Plan technique : [plan.md](plan.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : [ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md) · [ADR-0002](../../adr/0002-cadrage-environnement-cible-google-cloud.md) · [ADR-0003](../../adr/0003-mvp-chargement-cypher-pur.md) · [ADR-0004](../../adr/0004-mvp-modele-espece-formes.md) · [ADR-0005](../../adr/0005-mvp-conventions-nommage-schema.md) · [ADR-0006](../../adr/0006-mvp-banc-essai-30-questions.md)
- Cadrage : [../../cadrage/README.md](../../cadrage/README.md)
