# Roadmap — node4jPOC (DASHBOARD)

> **Vue dynamique** : status courant + blockers + ce qui bouge.
> **Plan détaillé** (phases, DoD) → le `tasks.md` de chaque spec ; pas de plan macro séparé ([conception/tasks.md](conception/tasks.md)).
> MAJ à chaque session ou via `/feature-done`.

**Dernière MAJ :** 2026-10-14

## 🔄 Pivot 2026-09-28 — Environnement cible Google Cloud

→ [CR du pivot](cadrage/reunions/2026-09-28-pivot.md) · [ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md)

Le POC devient transposable à une entreprise full Google Cloud ; dbt reste hors POC. Aucune spec abandonnée : la spec 001 reste valable.

## ✅ Phase 0 — Setup (terminée le 2026-09-30)

- [x] Template claude-Setup v1.5.0 installé (2026-09-26)
- [x] Cadrage : brief archivé, synthèse dans [cadrage/README.md](cadrage/README.md) (2026-09-28)
- [x] Faits et sources consignés dans [conception/research.md](conception/research.md) (2026-09-28)
- [x] [ADR-0001](adr/0001-mvp-jeu-de-donnees-pokeapi.md) — choix du jeu de données : Pokémon, CSV PokéAPI (2026-09-28)
- [x] Pivot : environnement cible Google Cloud, [ADR-0002](adr/0002-cadrage-environnement-cible-google-cloud.md) (2026-09-28)
- [x] Instance AuraDB Free créée (GCP europe-west1), vraie limite notée, identifiants dans Secret Manager (2026-09-30) → [ACCESS](ACCESS.md)
- [x] Projet Google Cloud avec compte de facturation : `jleroy-labo`, facturation active (constaté le 2026-09-30)

## ✅ Jalon 1 — Socle de données (technique 1 : Cypher à la main), livré le 2026-10-01, clos le 2026-10-07

Instance créée ; données chargées en Cypher pur (`LOAD CSV`) par un script réexécutable sans doublons ; modèle espèce + formes documenté ; 30 questions de référence ([questions/README.md](../../questions/README.md)) avec leurs réponses attendues, calculées en Cypher pour 27 d'entre elles (Q10, Q29 et Q30, comportementales, se notent par une règle). Ces requêtes servent de vérité de référence aux jalons suivants.

- [x] [001-socle-donnees](specs/001-socle-donnees/spec.md) — livré 2026-10-01 (démarrée le 2026-09-29) : 8 859 nœuds et 113 700 relations, idempotence prouvée, 27 réponses de référence rejouables
- [x] Garder l'instance Aura éveillée : job planifié `reveil-aura` et alerte par e-mail sur Google Cloud (NEO-13) — livré 2026-10-07 : déployé et testé le 2026-09-30 ; du 2026-10-01 au 2026-10-07, aucune requête humaine, 7 exécutions réussies sur 7, l'instance n'est jamais passée en pause

## ✅ Jalon 2 — Agent text-to-Cypher via MCP, livré le 2026-10-12

La fiche de schéma reprend les règles de réponse du banc d'essai ([questions/README.md](../../questions/README.md) : « Pokémon » = espèce, sens de « apprendre ») et les cas limites gardés tels quels du [plan 001](specs/001-socle-donnees/plan.md) : noms en double (18 attaques Z, « Osmose Équine », 2 formes), `categorie` sans « Pokémon » pour la 9e génération, apostrophe typographique dans 62 noms. La propriété `categorie` a deux sens : « Pokémon Flamme » sur un Pokémon ; « physique », « spéciale » ou « statut » sur une attaque. Index plein texte sur les noms prévu ([ARCHITECTURE § 8](conception/ARCHITECTURE.md)) ; en place depuis le 2026-10-10 (`noms_plein_texte`, T7.2).

- [x] [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) — livré 2026-10-12 (35/35 tasks) : conception validée le 2026-10-01 ([ADR-0009](adr/0009-mvp-protocole-mesure-techniques.md)), phases 0 à 3 faites (socle sans base, banc lisible par le harnais, notation, mesures et revue ; la dernière fusionnée le 2026-10-09), T7.1 faite avec la clôture de NEO-13 ; phase 4 (cellules, NEO-18) : T4.1 à T4.3, fusionnée le 2026-10-10 (PR n°10) ; prérequis de la phase 5 en place le 2026-10-10 : CI GitHub Actions (NEO-25), coupure automatique de Vertex et plafond natif (NEO-26, ADR-0013) ; phase 5 (répétition générale, NEO-18) : T5.1 faite le 2026-10-10 (`banc lancer --faux-serveur`, vrais LLM, 0,195 $) ; phase 7 (retour sur la base, NEO-20), avant la 6 : T7.2 à T7.5 faites le 2026-10-10 (index plein texte et rechargement, 34/34 ; fiche vérifiée sur la base et corrigée sur trois points ; `banc essai-serveur` conforme, arrêt des lectures prouvé sur Aura Free ; renommage par Cypher 25 retenu) ; phase 8 (pilote, NEO-21) : T8.1 faite le 2026-10-10 (2,51 $, 1,06 fois l'estimation ; cache à 5 min, seuils du FR/EN fixés, protocole gelé) ; phase 9 (campagne, NEO-21 et NEO-22) : T9.1 à T9.3 faites le 2026-10-11 (`fr-1`, 3 passes, 7,60 $, recoupés à la Console et dans l'export de facturation ; scores 27,5, 27,8 et 20,7 sur 30 ; revue assistée validée par Julien) ; phase 6 (schéma anglais sans base, NEO-19) : T6.1 à T6.3 faites le 2026-10-11 (table de correspondance, `charger.sh --schema`, traducteur, fiche anglaise ; PR n°17, fusionnée avec la n°16 le 2026-10-11) ; T10.0 ajoutée le 2026-10-11 (constats de la revue adverse de la phase 6) ; phase 10 (schéma anglais sur la base, NEO-23) : T10.0 à T10.3 faites le 2026-10-11 (constats réglés, base basculée en anglais puis revenue, prouvée ; `en-1`, 3 passes, 2,76 $, scores 19,5, 19,5 et 18,5 sur 30 ; passe de contrôle 21,5 ; verdict : pas d'effet mesurable du schéma anglais, Δ = −1,5 pour un seuil de 2,5) ; T11.0 ajoutée et faite le 2026-10-11 (ADR-0015 : source de Q18 au tour précédent, une source de `fr-1` changée) ; T11.1 et T11.2 faites le 2026-10-11 ([rapport de la technique 2](../../banc/resultats/technique-2.md), doc à jour) ; T11.3 faite le 2026-10-12 (livraison, PR n°20, tag `jalon-2`). Elle couvre tout le jalon :
  - `neo4j/mcp` branché sur Claude Code et sur un agent ADK (Claude Sonnet 5.5 par l'API Anthropic, [ADR-0011](adr/0011-infra-claude-par-api-anthropic.md) ; Gemini 3.8 Flash sur Vertex `eu`), mesuré sur les 30 questions
  - Fiche de schéma commune à toutes les techniques (règles, valeurs, exemples) et mesure « schéma français contre anglais » ([ADR-0005](adr/0005-mvp-conventions-nommage-schema.md))

## 📋 Jalon 3 — GraphRAG sur les descriptions

- [~] [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) — **EN COURS** 5/35 tasks : conception validée le 2026-10-13 (18 phases ; NEO-28 à NEO-35 sous l'epic NEO-3) : option A′ (plugin GenAI au chargement, question encodée par le banc, recherche par `read-cypher`), deux cellules (Claude Sonnet 5.5, Gemini 3.8 Flash), index de 3 072 dimensions ([ADR-0018](adr/0018-mvp-technique-sans-outil.md) à [ADR-0020](adr/0020-mvp-index-vectoriel-des-descriptions.md)) ; coût estimé à 8 $ ; phases 1 et 2 fusionnées le 2026-10-13 (PR n°22 et n°23 : contre-épreuve dans le banc, un gel et un pilote par jalon ; NEO-28 clos) ; phase 3 fusionnée le 2026-10-13 (PR n°25 : vérification des vecteurs écrite d'abord, jeton du chargement, rôle `predictionVertex`) ; T2.2 (clé Anthropic, NEO-29) attend la nouvelle clé
- [ ] Recherche vectorielle dans les descriptions en français (embeddings Gemini multilingues), puis parcours du graphe, mesurée sur les 30 questions
- [ ] Préalables, repris du jalon 2 : avant la première campagne, la contre-épreuve de l'[ADR-0014](adr/0014-mvp-revue-assistee.md) promue dans `banc/`, en TDD, et la clé Anthropic du banc renouvelée (elle expire le 2026-11-07). Le protocole du banc, précisé le 2026-10-12 par l'[ADR-0017](adr/0017-mvp-precisions-protocole-mesure.md), vaut tel quel — contre-épreuve promue le 2026-10-13 (T1.1, PR n°22) ; clé : T2.2, en attente

## 📋 Jalon 4 — Agents gérés et tableau comparatif

- [ ] Aura Agent face à un agent ADK hébergé sur Agent Runtime et publié dans Gemini Enterprise, mesurés sur les 30 questions
- [ ] Tableau comparatif final, technique × question : réponse juste, sources citées, temps de réponse, coût, effort de mise en place
- [ ] Avant qu'Aura Agent lise le schéma : vérifier l'effet des clés orphelines de `db.propertyKeys()`, 18 noms anglais qu'aucune donnée ne porte, restés sur la base française après la bascule FR/EN de la spec 002 ([plan 002](specs/002-agent-text-to-cypher/plan.md), D8)

## 💡 Jalon 5 (option) — Mémoire d'agent

- [ ] `neo4j-agent-memory` (mémoire dans le graphe) face à Memory Bank (mémoire gérée par Google)

## 💡 Jalon 6 (option) — Briques data Google Cloud

- [ ] Aura Graph Analytics avec BigQuery (gratuit sur Free)
- [ ] CDC → Pub/Sub, sur une instance Business Critical louée à l'heure (plus de local : [ADR-0007](adr/0007-infra-secrets-et-services-geres.md))
- [ ] Virtual Graph, si le prix horaire affiché par la console se confirme

### Risques courants

- Limite d'AuraDB Free : 200 000 nœuds et 400 000 relations (lue le 2026-09-30) ; le graphe chargé en occupe 4,4 % et 28,4 %
- Instance Free en pause après 72 h sans activité, supprimée après 30 jours de pause : garder le script de chargement réexécutable ; le job de réveil quotidien `reveil-aura` l'évite (NEO-13, vérifié du 2026-10-01 au 2026-10-07)
- Coûts qui tournent en tâche de fond : éteindre Aura Agent exposé, l'agent Agent Runtime (`min_instances=0`) et toute instance Business Critical après chaque session de mesure
- Dépense LLM : coupure automatique de Vertex ([ADR-0010](adr/0010-infra-plafond-de-depense.md)) à construire avant la première campagne payante (au plus tard T5.1) ; Claude plafonné par 20 $ de crédits sans recharge automatique ([ADR-0011](adr/0011-infra-claude-par-api-anthropic.md)) ; coupure en place depuis le 2026-10-10, avec un plafond natif de 30 € par mois sur Vertex ([ADR-0013](adr/0013-infra-plafond-natif-de-vertex.md), NEO-26) ; précision du 2026-10-12 : Claude est borné par des crédits offerts sans recharge automatique (31,61 $ le 2026-10-11) et par la limite de l'organisation, 20 $ par mois depuis le 2026-10-11 ([ACCESS](ACCESS.md))

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
