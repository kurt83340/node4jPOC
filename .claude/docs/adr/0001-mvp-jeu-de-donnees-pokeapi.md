---
status: accepted
scope: mvp
phase: 2026-Q3
supersedes: null
---

# 0001 — Jeu de données : Pokémon (CSV PokéAPI, en français)

**Statut :** Accepted
**Date :** 2026-09-28
**Décideur :** Julien Leroy

## Contexte

Le POC compare plusieurs techniques de l'écosystème agentique de Neo4j (Cypher à la main, agent text-to-Cypher via MCP, GraphRAG, Aura Agent) sur **un jeu de données commun** et 10 questions de référence ([cadrage](../cadrage/README.md)). Ce jeu doit offrir :

- du texte en français, pour le GraphRAG sur des descriptions ;
- beaucoup de relations, pour des questions qui demandent plusieurs sauts dans le graphe ;
- des réponses faciles à vérifier, puisque les requêtes Cypher écrites à la main servent de vérité de référence ;
- une taille qui tient dans AuraDB Free (Aura Agent en a besoin).

## Options considérées

> Le brief retenait Pokémon d'emblée. Les alternatives ci-dessous ont été examinées le 2026-09-28, pour documenter le choix.

- **Option A — PokéAPI (CSV publics)** : textes en français (`language_id = 5`), graphe naturel, domaine connu. Effort : script de chargement et modélisation à écrire.
- **Option B — Jeux d'exemple Neo4j** (Movies, Northwind…) : prêts à l'emploi, mais en anglais, peu de texte descriptif, et un modèle déjà fait (pas d'exercice de modélisation).
- **Option C — Open data français** (data.gouv.fr…) : en français, mais surtout tabulaire, nettoyage lourd, et réponses de référence difficiles à vérifier.
- **Option D — Données perso ou pro** : réalistes, mais confidentialité à gérer et vérité de référence à construire de zéro.
- **Option E — Ne rien faire** : chaque technique testée sur ses propres données de tutoriel. Aucun chargement à écrire, mais plus aucune comparaison possible.

## Décision

**Option A** : PokéAPI, fichiers CSV publics (licence BSD-3), textes en français (`language_id = 5`).

Raisons :

- graphe naturel : types, faiblesses entre types, évolutions, attaques, talents ;
- 7 116 descriptions en français (898 espèces), la matière du GraphRAG ;
- domaine connu, donc réponses vérifiables (par exemple Roche ×4 contre Dracaufeu, qui est Feu et Vol) ;
- environ 10 000 nœuds et 113 000 relations : tient dans les deux limites annoncées pour AuraDB Free.

## Conséquences

- ✅ Même base pour toutes les techniques : la comparaison est juste.
- ✅ Vrai exercice de modélisation (aucun modèle tout fait).
- ⚠️ Univers Pokémon © Nintendo : usage d'apprentissage perso, ne pas publier les données.
- ⚠️ Descriptions répétées d'un jeu à l'autre : à dédoublonner.
- ⚠️ `APPREND` (~99 500 relations) pèse lourd : surveiller la limite d'AuraDB Free.
- ⚠️ Les CSV évoluent à chaque nouveau jeu : figer un commit PokéAPI pour que les réponses de référence restent justes.
- ⚠️ Domaine ludique : la transposition à un cas métier reste à juger.

## Liens

- [Brief (texte intégral)](../cadrage/documents/2026-09-28-brief-poc.md)
- [Faits et sources](../conception/research.md)
- [PokéAPI — data/v2/csv](https://github.com/PokeAPI/pokeapi/tree/master/data/v2/csv)
