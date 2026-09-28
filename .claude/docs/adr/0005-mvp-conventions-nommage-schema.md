---
status: accepted
scope: mvp
phase: 2026-Q3
supersedes: null
---

# 0005 — Conventions de nommage du schéma

**Statut :** Accepted
**Date :** 2026-09-29
**Décideur :** Julien Leroy

## Contexte

Le schéma du graphe est la seule chose que voient les agents text-to-Cypher : `get-schema` de `neo4j/mcp` ne transmet que les labels, les relations et les propriétés typées. Avant le chargement, une recherche sur les pratiques actuelles de Neo4j (manuel Cypher, GraphAcademy) et sur les études publiées (text-to-SQL et text-to-Cypher) a relevé un écart de nommage et quatre points qui gênent un LLM ([research de la spec 001](../specs/001-socle-donnees/research.md)). Cet ADR précise l'[ADR-0004](0004-mvp-modele-espece-formes.md) (deux niveaux, espèce et formes) sans le remplacer.

## Options considérées

- **Option A — Garder le nommage v1 (ne rien faire)** : `Espece`, propriétés en snake_case, clé étrangère `especeId` sur `Description`, règle de la forme par défaut portée par une seule propriété.
- **Option B — Nommage v2, aligné sur la doc Neo4j et sur les mots des questions** (détail ci-dessous).
- **Option C — Schéma en anglais** : les LLM ont surtout vu du Cypher anglais, mais les questions sont en français et l'effet n'a jamais été mesuré. Reporté en mesure au jalon 2.

## Décision

**Option B** (Julien) :

- labels en PascalCase, relations en SCREAMING_SNAKE_CASE, **propriétés en camelCase**, identifiants sans accents (manuel Cypher : conventions de nommage et styleguide) ;
- le niveau espèce s'appelle **`Pokemon`**, le mot de 13 questions sur 30 ; `Forme` reste ;
- une relation spécialisée **`(:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)`** rend visible la règle « Pokémon = forme par défaut », à côté de `FORME_DE` et de la propriété `parDefaut` ;
- des noms sans ambiguïté : stats préfixées (`statPv`, `statAttaque`, `statDefense`, `statAttaqueSpeciale`, `statDefenseSpeciale`, `statVitesse`), `identifiantPokeapi`, `rang` au lieu de `slot` ;
- pas de clé étrangère : `Description` n'est rattachée que par sa relation ;
- `facteur` toujours décimal (2.0 ; 0.5 ; 0.0).

## Conséquences

- ✅ Les mots des questions se retrouvent dans le schéma (« Pokémon », « forme par défaut »), ce qui aide un LLM à relier la question au schéma.
- ✅ Conforme aux conventions de Neo4j.
- ⚠️ `Type` est un mot-clé de Cypher, déconseillé comme label : testé au go/no-go, renommé seulement si ça casse.
- ⚠️ `get-schema` ne transmet toujours ni les règles ni les valeurs possibles : une fiche de schéma commune à toutes les techniques est prévue au jalon 2.
- ⚠️ Le français du schéma reste une hypothèse : mesure « schéma français contre anglais » au jalon 2.

## Liens

- [Conventions de nommage du manuel Cypher](https://neo4j.com/docs/cypher-manual/current/syntax/naming/) · [styleguide](https://neo4j.com/docs/cypher-manual/current/styleguide/)
- [GraphAcademy — relations spécifiques](https://graphacademy.neo4j.com/courses/modeling-fundamentals/7-using-specific-relationships/1-specific-relationships/)
- [SNAILS, PACMMOD 2025](https://dl.acm.org/doi/10.1145/3709727) : identifiants naturels et justesse du text-to-SQL
- [ARCHITECTURE § 5](../conception/ARCHITECTURE.md)
