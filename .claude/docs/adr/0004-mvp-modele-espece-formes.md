---
status: accepted
scope: mvp
phase: 2026-Q3
supersedes: null
---

# 0004 — Modèle du graphe : espèce + toutes les formes

**Statut :** Accepted
**Date :** 2026-09-28
**Décideur :** Julien Leroy

## Contexte

PokéAPI sépare l'**espèce** (nom, catégorie, descriptions, évolutions) de la **forme** (types, stats, talents, attaques). 326 formes alternatives (Méga, Gigamax, régionales, Totem…) concernent 224 espèces, et toutes ont un nom français. Le brief laissait la question ouverte. Toutes les techniques du banc d'essai interrogeront ce modèle. Mesures : [research de la spec 001](../specs/001-socle-donnees/research.md).

## Options considérées

- **Option M1 — Espèces seules (le modèle du brief tel quel)** : un nœud `Pokemon` par espèce, avec les données de sa forme par défaut. Le plus simple, mais sans les formes ; les ajouter plus tard changerait le sens de `Pokemon`.
- **Option M2 — Espèce + toutes les formes** : deux niveaux, `Espece` et `Forme` reliés par `FORME_DE`.
- **Option M3 — Espèce + formes par défaut** : le schéma de M2 avec 1 025 formes seulement ; sa complexité sans son bénéfice.

## Décision

**Option M2** (Julien). Fidèle à la source, et c'est la vraie leçon de modélisation : une identité et ses variantes, comme un produit et ses références en entreprise. Le volume reste loin des limites d'AuraDB Free (~8 850 nœuds, ~112 700 relations).

## Conséquences

- ✅ Toutes les questions sont possibles, y compris sur les formes.
- ✅ Les données d'espèce (descriptions, évolutions) ne sont pas dupliquées sur chaque forme.
- ⚠️ Requêtes à deux niveaux, plus exigeantes pour le text-to-Cypher : « Dracaufeu » a quatre formes, dont Méga-Dracaufeu X, qui n'a pas les mêmes types. Les réponses de référence doivent préciser la forme (par défaut : `par_defaut = true`).
- ⚠️ Les formes Gigamax et Totem, surtout des mécaniques de jeu, alourdissent les résultats ; on les garde par fidélité.

## Liens

- [Spec 001 — research](../specs/001-socle-donnees/research.md) · [plan](../specs/001-socle-donnees/plan.md)
- [ADR-0001](0001-mvp-jeu-de-donnees-pokeapi.md) (jeu de données)
