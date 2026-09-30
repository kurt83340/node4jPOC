---
status: accepted
scope: mvp
phase: 2026-Q3
supersedes: null
---

# 0003 — Chargement des données : Cypher pur (`LOAD CSV`)

**Statut :** Accepted
**Date :** 2026-09-28
**Décideur :** Julien Leroy

## Contexte

Le jalon 1 demande un chargement réexécutable sans doublons : l'instance AuraDB Free se met en pause après 72 h et disparaît après 30 jours de pause, donc on rechargera souvent. dbt est hors du POC ([ADR-0002](0002-cadrage-environnement-cible-google-cloud.md)). L'objectif n°1 du projet est d'apprendre Neo4j. Options et mesures : [research de la spec 001](../specs/001-socle-donnees/research.md).

## Options considérées

- **Option A — Pipeline d'entreprise** (BigQuery + dbt + chargeur) : contredit « dbt hors POC ».
- **Option B — Python en deux étages** (transformations → tables en forme de graphe → chargeur) : nettoyage et tests faciles, compatible dbt, mais le Cypher se limite à `UNWIND … MERGE`.
- **Option C — Cypher pur** : des fichiers `.cypher` lisent les CSV du commit figé depuis GitHub (`LOAD CSV`) et écrivent par `MERGE`, en lots (`CALL … IN TRANSACTIONS`), exécutés par `cypher-shell`.
- **Option D — Ne rien faire de scripté** (import sans code de la console Aura) : pas de script versionné, aucune agrégation possible.

## Décision

**Option C** (Julien, contre la recommandation B). C'est l'option qui fait le plus pratiquer Neo4j : contraintes, `LOAD CSV`, `MERGE` idempotent, découpage en lots. La transposabilité du script ne compte plus puisque dbt sort du POC ; ce qui se transpose en entreprise, ce sont les motifs Cypher.

## Conséquences

- ✅ Tout le chargement se lit en Cypher, sans code applicatif.
- ✅ Idempotence par `MERGE` sur des clés contraintes : relancer ne crée aucun doublon.
- ⚠️ Java 21 et `cypher-shell` à installer.
- ⚠️ Dépend de la lecture https par Aura : test go/no-go d'abord ; repli : URL signée Cloud Storage, passée en paramètre (un bucket public republierait les données, contraire à l'ADR-0001).
- ⚠️ Agrégation de 638 321 lignes (`APPREND`) dans la mémoire d'Aura Free : lots et coupe-circuit prévus.
- ⚠️ Nettoyage des textes limité aux fonctions Cypher (pas d'expressions régulières sans APOC).
- ⚠️ Pas de framework de test : la vérification passe par des comptes attendus.

## Liens

- [Spec 001 — research](../specs/001-socle-donnees/research.md) · [plan](../specs/001-socle-donnees/plan.md)
- [ADR-0001](0001-mvp-jeu-de-donnees-pokeapi.md) (commit figé) · [ADR-0002](0002-cadrage-environnement-cible-google-cloud.md) (dbt hors POC)
- [LOAD CSV](https://neo4j.com/docs/cypher-manual/current/clauses/load-csv/) · [CALL … IN TRANSACTIONS](https://neo4j.com/docs/cypher-manual/current/subqueries/subqueries-in-transactions/)
