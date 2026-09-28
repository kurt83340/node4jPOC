# Roadmap — node4jPOC (DASHBOARD)

> **Vue dynamique** : status courant + blockers + ce qui bouge.
> **Plan détaillé** (phases, DoD) → le `tasks.md` de chaque spec ; pas de plan macro séparé ([conception/tasks.md](conception/tasks.md)).
> MAJ à chaque session ou via `/feature-done`.

**Dernière MAJ :** 2026-09-28

## 🔄 Pivot 2026-09-28 — Environnement cible Google Cloud

→ [CR du pivot](cadrage/reunions/2026-09-28-pivot.md) · [ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md)

Le POC devient transposable à une entreprise full Google Cloud ; dbt reste hors POC. Aucune spec abandonnée : la spec 001 reste valable.

## 🚧 Phase 0 — Setup (en cours)

- [x] Template claude-Setup v1.5.0 installé (2026-09-26)
- [x] Cadrage : brief archivé, synthèse dans [cadrage/README.md](cadrage/README.md) (2026-09-28)
- [x] Faits et sources consignés dans [conception/research.md](conception/research.md) (2026-09-28)
- [x] [ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md) — choix du jeu de données : Pokémon, CSV PokéAPI (2026-09-28)
- [x] Pivot : environnement cible Google Cloud, [ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md) (2026-09-28)
- [ ] Instance AuraDB Free créée, vraie limite notée, identifiants dans `.env`
- [ ] Projet Google Cloud avec compte de facturation (avant le jalon 2)

## 📋 Jalon 1 — Socle de données (technique 1 : Cypher à la main)

Instance créée ; données chargées en Cypher pur (`LOAD CSV`) par un script réexécutable sans doublons ; modèle espèce + formes documenté ; 30 questions de référence ([questions/README.md](../../questions/README.md)) avec leurs réponses attendues, calculées en Cypher. Ces requêtes servent de vérité de référence aux jalons suivants.

- [~] [001-socle-donnees](specs/001-socle-donnees/spec.md) — **EN COURS** 1/16 tasks (démarrée le 2026-09-29)

## 📋 Jalon 2 — Agent text-to-Cypher via MCP

- [ ] `neo4j/mcp` branché sur Claude Code et sur un agent ADK (LLM à choisir : Gemini ou Claude via Vertex), mesuré sur les 30 questions

## 📋 Jalon 3 — GraphRAG sur les descriptions

- [ ] Recherche vectorielle dans les descriptions en français (embeddings Gemini multilingues), puis parcours du graphe, mesurée sur les 30 questions

## 📋 Jalon 4 — Agents gérés et tableau comparatif

- [ ] Aura Agent face à un agent ADK hébergé sur Agent Runtime et publié dans Gemini Enterprise, mesurés sur les 30 questions
- [ ] Tableau comparatif final, technique × question : réponse juste, sources citées, temps de réponse, coût, effort de mise en place

## 💡 Jalon 5 (option) — Mémoire d'agent

- [ ] `neo4j-agent-memory` (mémoire dans le graphe) face à Memory Bank (mémoire gérée par Google)

## 💡 Jalon 6 (option) — Briques data Google Cloud

- [ ] Aura Graph Analytics avec BigQuery (gratuit sur Free)
- [ ] CDC → Pub/Sub (en local d'abord ; Business Critical à l'heure si besoin)
- [ ] Virtual Graph, si le prix horaire affiché par la console se confirme

### Risques courants

- Limite réelle d'AuraDB Free inconnue (50 000 nœuds / 175 000 relations, ou 200 000 / 400 000) : à noter à la création
- Instance Free en pause après 72 h sans activité, supprimée après 30 jours de pause : garder le script de chargement réexécutable
- Coûts qui tournent en tâche de fond : éteindre Aura Agent exposé, l'agent Agent Runtime (`min_instances=0`) et toute instance Business Critical après chaque session de mesure

## 🚫 Hors POC

- dbt : équation de l'entreprise (le POC reste compatible)
- Graph Data Science for BigQuery (expérimental), Spanner Graph (ce n'est plus Neo4j)

---

## Conventions

- `[ ]` = planifié, pas commencé
- `[~]` = en cours (mettre en **gras**)
- `[x]` = livré
- Numéro de spec continue (001 → 002 → 003 → …) — pas de reset entre phases
- Format `X/Y tasks` = compté depuis `specs/00X/tasks.md`
