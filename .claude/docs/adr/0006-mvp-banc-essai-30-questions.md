---
status: accepted
scope: mvp
phase: 2026-Q3
supersedes: null
---

# 0006 — Banc d'essai : 30 questions de référence en 6 catégories

**Statut :** Accepted
**Date :** 2026-09-29
**Décideur :** Julien Leroy

## Contexte

Le brief prévoyait 10 questions de référence, posées à toutes les techniques du POC ([ADR-0001](0001-mvp-jeu-de-donnees-pokeapi.md)). Avec 10 questions, une technique n'est testée que sur 1 à 3 questions ciblées : un seul raté fausse son score. Ce banc d'essai sert à tous les jalons, de 1 à 6 : la décision survit à la spec 001, où elle était notée D12.

## Options considérées

- **Option A — 10 questions (le brief, ne rien faire)** : le moins de travail, mais un comparatif fragile.
- **Option B — 20 questions** : meilleure couverture, mais sans structure par catégorie.
- **Option C — 30 questions en 6 catégories de 5** : faits simples, multi-sauts, agrégats et négations, sémantique, raisonnement et mémoire, robustesse.

## Décision

**Option C** (Julien). Questions, règles de notation et premiers calculs : [questions/README.md](../../../questions/README.md). L'équipe de référence de Q2 et Q18 est fixée ; Q18 et Q28 sont des seconds tours de conversation ; Q10, Q29 et Q30 se notent par une règle, sans requête.

## Conséquences

- ✅ Un score par technique et par catégorie, plus parlant qu'un score global.
- ✅ Des pièges volontaires (formes, définitions, prémisse fausse, question vague) mesurent la fiabilité des agents, pas seulement leur justesse.
- ⚠️ 27 requêtes de référence à écrire (T7.1) et 5 ensembles « obligatoire / acceptable » à trier à la main.
- ⚠️ Chaque passage du banc d'essai coûte environ trois fois plus en LLM qu'avec 10 questions (quelques dollars).

## Liens

- [questions/README.md](../../../questions/README.md)
- [Plan de la spec 001, D12](../specs/001-socle-donnees/plan.md)
