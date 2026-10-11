---
status: accepted
scope: infra
phase: 2026-Q4
supersedes: null
amends: 0009
---

> ⚠️ **Point remplacé** (2026-10-12) : « la clé d'un workspace dédié au banc », « 20 $ d'abord » et « limite mensuelle du workspace » → [ADR-0016](0016-infra-limite-anthropic-organisation.md) : la clé reste dans le workspace « Default », et la dépense Claude est bornée par la limite mensuelle de l'organisation, 20 $, et par le solde des crédits, sans recharge automatique. Le reste de cet ADR reste en vigueur.

# 0011 — Claude par l'API Anthropic, plafonné par des crédits prépayés

**Statut :** Accepted
**Date :** 2026-10-08
**Décideur :** Julien Leroy

## Contexte

L'[ADR-0009](0009-mvp-protocole-mesure-techniques.md) fait passer les trois cellules du jalon 2 par Vertex. Le 2026-10-07 (T0.2), le quota de Claude est à 0 sur `jleroy-labo`, en `eu` comme en `global`, et les six demandes de hausse ont été refusées d'office : compte jugé non éligible, revue manuelle de Google nécessaire, délai inconnu ([plan 002](../specs/002-agent-text-to-cypher/plan.md), relevé de T0.2). Gemini répond depuis `eu`. Aucune étude publique ne départage Sonnet 5.5 et Gemini 3.8 Flash pour un agent text-to-Cypher par MCP : les bancs text-to-Cypher datent de 2024-2025 ; le plus proche, un banc SQL à un coup ([AIMultiple](https://aimultiple.com/text-to-sql), 2026-10-01), place Gemini 3.8 Flash (77,2 %) devant Sonnet 5.5 (73,8 %). La mesure du POC garde donc son objet.

## Options considérées

- **Option A — API Anthropic directe** pour les deux cellules Claude ; Gemini reste sur Vertex `eu`.
- **Option B — attendre Vertex** : revue manuelle chez Google, délai inconnu ; T0.2 et les cellules Claude restent bloqués.
- **Option C — Gemini d'abord** : mesurer ADK + Gemini, ajouter Claude plus tard ; le plan croisé reste incomplet d'ici là.
- **Option D — l'abonnement Claude de Julien** : coût non mesurable (circuit breaker du plan 002).
- **Option E — ne rien faire** : la spec 002 s'arrête à T0.2.

## Décision

**Option A** (Julien, 2026-10-08). Elle remplace « tous sur Vertex » dans l'ADR-0009 ; le reste du protocole tient.

- **Cellules** : Claude Code + Sonnet 5.5 et ADK + Sonnet 5.5 par l'API Anthropic (`claude-sonnet-5-5` ; petit modèle de Claude Code `claude-haiku-4-5-20251001`) ; ADK + Gemini 3.8 Flash sur Vertex `eu`, inchangé.
- **Clé** : celle d'un workspace dédié au banc, rangée dans Secret Manager (`jleroy-labo`), lue par un script de `scripts/` et passée par l'environnement, jamais sur le disque ni en argument ; le lanceur la retire avant `neo4j-mcp`. L'isolement de Claude Code perd ses variables Vertex (`CLAUDE_CODE_USE_VERTEX` passerait avant la clé) ; la sonde exige que le message `init` désigne la clé (`apiKeySource`), jamais l'abonnement.
- **Plafond chez Anthropic** : crédits prépayés, recharge automatique coupée (à zéro, l'API s'arrête) ; 20 $ d'abord, pour T0.2, la répétition générale et le pilote ; recharge à la main après le pilote, une fois le coût d'une passe connu. Limite mensuelle du workspace en plus.
- **Total des plafonds** : pas de règle commune pour l'instant (Julien : « on verra, mais ça ne doit pas me coûter cher »). Le budget Google reste à 100 € ([ADR-0010](0010-infra-plafond-de-depense.md)) ; les crédits, sans recharge automatique, bornent la dépense Claude, et chaque recharge est une décision de Julien.
- **Prix** : `banc/prix.toml` distingue l'accès (API ou Vertex `eu`). Prix de l'API = prix Vertex `eu` divisés par 1,1 : Sonnet 5.5 à 2 $ / 10 $ par million de tokens, Haiku 4.5 à 1 / 5 ; lecture du cache de Sonnet 5.5 comptée à 0,20 $ (la doc dit 0,10 ou 0,20), à vérifier sur la première facture.

## Conséquences

- ✅ T0.2 se débloque sans attendre Google. Le plan croisé tient : Sonnet 5.5 passe par la même voie dans les deux clients, l'effet du client reste isolé.
- ✅ Environ 9 % moins cher que Vertex `eu`, avec un plafond dur (les crédits) et un usage visible en 5 min environ dans la Console.
- ⚠️ Données traitées hors UE : l'API n'a pas d'option UE (traitement possible aux États-Unis, en Europe, en Asie ou en Australie ; stockage aux États-Unis ; pas d'entraînement par défaut ; 30 jours de rétention au plus). Sans enjeu pour des questions Pokémon sur des données publiques ; pour l'entreprise, Vertex `eu` reste la référence.
- ⚠️ ADK + Sonnet (API) contre ADK + Gemini (Vertex `eu`) mêle deux points d'accès : les temps de réponse ne comparent plus seulement les modèles. À dire dans le tableau comparatif.
- ⚠️ Un second fournisseur : une console, une clé à faire tourner, une facture de plus, que le budget de l'ADR-0010 ne voit pas.
- ⚠️ Haiku 4.5 est actif ; son retrait, pas avant le 2026-10-15, sera annoncé au moins 60 jours à l'avance : à revérifier avant le pilote.

## Liens

- [Plan 002](../specs/002-agent-text-to-cypher/plan.md) : D2, D3, D10, D13, relevé de T0.2
- [ADR-0009](0009-mvp-protocole-mesure-techniques.md) (point remplacé), [ADR-0010](0010-infra-plafond-de-depense.md) (plafond Google), [ADR-0007](0007-infra-secrets-et-services-geres.md) (secrets)
- Doc Anthropic, lue les 2026-10-07 et 2026-10-08 : [prix](https://platform.claude.com/docs/en/about-claude/pricing), [résidence des données](https://platform.claude.com/docs/en/manage-claude/data-residency), [limites de dépense](https://platform.claude.com/docs/en/api/rate-limits#setting-your-own-spend-limit), [workspaces](https://platform.claude.com/docs/en/manage-claude/workspaces#workspace-limits), [retraits de modèles](https://platform.claude.com/docs/en/about-claude/model-deprecations), [authentification de Claude Code](https://code.claude.com/docs/en/authentication#authentication-precedence)
- Bancs publics : [Neo4j Text2Cypher (2024)](https://neo4j.com/blog/developer/benchmarking-neo4j-text2cypher-dataset/), [CypherBench](https://arxiv.org/abs/2412.18702), [AIMultiple text-to-SQL](https://aimultiple.com/text-to-sql)
