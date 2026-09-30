---
status: accepted
scope: cadrage
phase: 2026-Q3
supersedes: null
---

# 0002 — Environnement cible : Google Cloud, dbt hors POC

**Statut :** Accepted
**Date :** 2026-09-28
**Décideur :** Julien Leroy

## Contexte

Le brief voulait un POC neutre et laissait les briques Google Cloud hors périmètre « pour l'instant ». Julien précise que son entreprise est full Google Cloud, avec dbt pour les transformations, et qu'il veut un setup transposable, même s'il coûte un peu ([CR du pivot](../cadrage/reunions/2026-09-28-pivot.md)). L'exploration sourcée des coûts et des équivalents Google Cloud est dans [research.md](../conception/research.md).

## Options considérées

- **Option A — Rester neutre (ne rien faire)** : le périmètre du brief. Aucun coût Google Cloud, mais un POC que l'entreprise devra refaire sur ses propres briques.
- **Option B — Google Cloud, dbt compris** : BigQuery + dbt dès le jalon 1. Fidèle à l'entreprise, mais dbt ne sert aucune technique du banc d'essai et retarde le premier graphe chargé.
- **Option C — Google Cloud, dbt hors POC** : les techniques gagnent leurs variantes Google Cloud (agent ADK, embeddings Gemini, Agent Runtime, Gemini Enterprise) ; les briques data (Aura Graph Analytics, CDC → Pub/Sub, Virtual Graph en option) forment un jalon optionnel ; dbt reste dans l'équation de l'entreprise.

## Décision

**Option C.** Le POC devient transposable là où ça compte (agents, modèles, interface des utilisateurs) sans payer la mise en place de dbt, dont aucune technique ne dépend.

## Conséquences

- ✅ Chaque technique a sa variante Google Cloud, mesurée dans le même tableau comparatif.
- ✅ Budget quotidien proche de 0 € : AuraDB Free, franchises BigQuery et Agent Runtime, Aura Graph Analytics gratuit sur Free.
- ⚠️ Compte de facturation Google Cloud requis (BigQuery hors bac à sable, Agent Runtime, Marketplace).
- ⚠️ Des coûts peuvent tourner en tâche de fond : Aura Agent exposé (0,35 $ par heure d'agent), agent Agent Runtime laissé allumé, instance Business Critical pour le CDC (0,40 $/h). Tout éteindre ou supprimer après chaque session de mesure.
- ⚠️ Plusieurs briques sont en preview (agents de la Marketplace Gemini Enterprise, Virtual Graph, template Dataflow) : elles peuvent changer.
- ⚠️ Renommages récents (Vertex AI devenu Gemini Enterprise Agent Platform, dbt v2) : docs et exemples en retard.
- ⚠️ Transposition : en entreprise, les clés JSON de compte de service sont souvent bloquées ; préférer l'authentification OAuth (`gcloud auth application-default login`).

## Liens

- [CR du pivot](../cadrage/reunions/2026-09-28-pivot.md)
- [Exploration Google Cloud et dbt](../conception/research.md)
- [ROADMAP](../ROADMAP.md)
- [ADR-0001](0001-mvp-jeu-de-donnees-pokeapi.md) : jeu de données, inchangé
