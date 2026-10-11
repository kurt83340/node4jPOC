---
status: accepted
scope: mvp
phase: 2026-Q4
supersedes: null
amends: 0009
---

# 0014 — Revue assistée : pré-analyse de Claude, décision de Julien, contre-épreuve

**Statut :** Accepted
**Date :** 2026-10-11
**Décideur :** Julien Leroy

## Contexte

L'[ADR-0009](0009-mvp-protocole-mesure-techniques.md) note les réponses du banc d'essai en deux temps : une pré-notation automatique, puis une « revue humaine à l'aveugle du reste », sans juge LLM ; l'[ADR-0008](0008-mvp-notation-questions-semantiques.md) avait déjà écarté un juge LLM pour les questions sémantiques. `banc revoir` montre chaque cas à l'aveugle (cellule, modèle et passe masqués), environ 200 lignes par cas.

Au pilote (27 cas, non comptés), Julien a demandé à Claude de faire la revue ; ses décisions ne se réutilisent jamais. Pour la campagne comptée `fr-1` (95 cas, T9.2), Claude a rendu les cas à l'aveugle par `banc.revue`, vérifié par script ce qui pouvait l'être (longues listes de Q7 et Q14, équipe de Q2 par la requête de contrôle), puis proposé une décision par cas, avec sa raison ; Julien les a validées en bloc, et elles sont enregistrées comme les siennes, avec une note en tête de leurs tables. Le plan l'a noté comme un écart au protocole ([plan 002, D7](../specs/002-agent-text-to-cypher/plan.md)).

Restent la phase 10 (trois passes anglaises et une passe française de contrôle, Gemini seul : environ 27 cas au rythme de `fr-1`, qui en a donné 20 pour Gemini en 3 passes), puis les jalons 3 et 4. Le verdict du FR/EN compare les passes anglaises à `fr-1` : revoir les unes et l'autre de deux façons différentes ferait entrer la méthode de revue dans l'écart mesuré.

## Options considérées

- **Option A — Revue humaine stricte** (l'ADR-0009 tel quel) : aucun ADR ; mais `fr-1` a été revue autrement, et un écart FR/EN propre demanderait de revoir aussi à la main ses 20 cas Gemini, soit une cinquantaine de cas pour Julien.
- **Option B — Revue assistée, comme pour `fr-1`** : pré-analyse de Claude, décision de Julien.
- **Option C — B, plus une contre-épreuve** : avant de voir les propositions, Julien revoit seul, à l'aveugle, quelques cas tirés au sort ; le taux d'accord est noté.
- **Option D — Juge LLM seul** : Claude décide sans validation. Écarté par les ADR-0008 et 0009 (biais d'un juge LLM sur des techniques fondées sur des LLM, Claude jugeant Claude dans les cellules Claude).
- **Option E — Ne rien faire** : `fr-1` reste un écart, et la revue de la phase 10 une question ouverte.

## Décision

**Option C** (Julien, 2026-10-11 : « ok pour tout », sur la préférence de Claude). Elle remplace dans l'ADR-0009 le point « revue humaine à l'aveugle du reste » ; le reste du protocole tient, pré-notation automatique et réutilisation des décisions comprises.

- **Pré-analyse** : Claude rend chaque cas « à revoir » tel que `banc revoir` le montre, à l'aveugle ; il vérifie par script ce qui se vérifie (listes contre `questions/attendu/`, contrôle de Q2, nombres) ; il propose pour chaque cas une note, une source et un motif, avec une raison d'une ligne.
- **Décision** : Julien valide, en bloc ou cas par cas ; les décisions s'enregistrent comme les siennes dans `banc/mesures/revues.toml`, par `banc.revue.revoir`, avec en tête des tables de la campagne une note qui dit qu'elles viennent d'une pré-analyse validée.
- **Contre-épreuve** : avant de voir les propositions, Julien revoit seul, à l'aveugle, 8 cas tirés au sort parmi ceux de la campagne (tous s'il y en a moins). Le taux d'accord (même note) et chaque désaccord vont dans le relevé de la campagne, au plan ; un désaccord se tranche par Julien, et sa raison se rejoue sur les cas semblables de la campagne.
- **Portée** : `fr-1` garde ses 95 décisions, prises ainsi, sans contre-épreuve ; la règle vaut pour les campagnes suivantes : passes anglaises et passe de contrôle de la phase 10, puis jalons 3 et 4.

## Conséquences

- ✅ Une même méthode de revue des deux côtés du FR/EN : l'écart mesuré ne mêle pas deux façons de juger.
- ✅ Une quinzaine de minutes de Julien par campagne (8 cas, puis la validation), au lieu d'environ deux minutes par cas.
- ✅ La contre-épreuve mesure, campagne après campagne, l'écart entre la pré-analyse et le jugement de Julien ; le tableau comparatif le rapporte.
- ⚠️ Valider en bloc ancre le jugement sur la proposition ; la contre-épreuve, faite avant de la voir, le limite sans l'annuler.
- ⚠️ Dans les cellules Claude, Claude pré-analyse les réponses de Claude : l'aveugle masque la cellule, pas le style ; les vérifications par script passent d'abord, et la contre-épreuve couvre une part du risque.
- ⚠️ 8 cas font un petit échantillon : un accord de 8 sur 8 ne prouve pas l'absence de biais, il sert d'alarme.
- ⚠️ Des décisions enregistrées comme celles de Julien viennent d'une pré-analyse : la note en tête des tables et le tableau comparatif le disent.

## Liens

- [Plan 002](../specs/002-agent-text-to-cypher/plan.md) : D4 (notation, réutilisation des décisions), D7 (revue de `fr-1`)
- [ADR-0009](0009-mvp-protocole-mesure-techniques.md) (point remplacé), [ADR-0008](0008-mvp-notation-questions-semantiques.md) (grille, juge LLM écarté)
- `banc/mesures/revues.toml` : décisions des revues, notes en tête des tables
