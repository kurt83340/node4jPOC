# Fiche de schéma : le graphe Pokémon

Données de PokéAPI, noms en français. Lecture seule, par l'outil `read-cypher`.

## Nœuds

- `Pokemon` : une espèce (1 025) ; propriétés `id`, `pokeapiIdentifier`, `name`, `category`.
- `Form` : une forme d'une espèce (1 351), sa forme par défaut ou l'une de ses variantes ; c'est la forme qui porte les types, les statistiques, les talents et les attaques. Propriétés `id`, `pokeapiIdentifier`, `name`, `isDefault`, `statHp`, `statAttack`, `statDefense`, `statSpecialAttack`, `statSpecialDefense`, `statSpeed`.
- `Type` : un type (18) ; propriétés `id`, `pokeapiIdentifier`, `name`.
- `Move` : une attaque (919) ; propriétés `id`, `pokeapiIdentifier`, `name`, `power`, `accuracy`, `pp`, `category`.
- `Ability` : un talent (313) ; propriétés `id`, `pokeapiIdentifier`, `name`.
- `Description` : un texte de description d'une espèce (5 233) ; propriétés `text` et `games`, les jeux où il paraît.

`pokeapiIdentifier` est l'identifiant anglais de PokéAPI (`gengar` pour l'espèce Ectoplasma). La forme par défaut porte le nom de son espèce.

## Relations

- `(:Pokemon)-[:HAS_DEFAULT_FORM]->(:Form)` : la forme par défaut de chaque espèce.
- `(:Form)-[:FORM_OF]->(:Pokemon)` : chaque forme vers son espèce, forme par défaut comprise.
- `(:Pokemon)-[:EVOLVES_INTO]->(:Pokemon)` : d'une espèce vers son évolution directe.
- `(:Form)-[:HAS_TYPE {slot}]->(:Type)` : `slot` vaut 1 pour le type principal, 2 pour le second.
- `(:Move)-[:HAS_TYPE]->(:Type)` : le type de l'attaque.
- `(:Type)-[:SUPER_EFFECTIVE_AGAINST|NOT_VERY_EFFECTIVE_AGAINST|NO_EFFECT_AGAINST {factor}]->(:Type)` : du type de l'attaque vers un type de la cible.
- `(:Form)-[:HAS_ABILITY {isHidden}]->(:Ability)` : `isHidden` est vrai pour le talent caché.
- `(:Form)-[:LEARNS {methods, level}]->(:Move)` : voir les règles.
- `(:Pokemon)-[:HAS_DESCRIPTION]->(:Description)`.

## Règles

- **Un Pokémon est une espèce, prise dans sa forme par défaut** (`HAS_DEFAULT_FORM`). Les autres formes ne comptent que si la question les nomme ; une réponse qui en ajoute le signale.
- **Apprendre une attaque**, c'est l'apprendre dans au moins un jeu, par n'importe quelle méthode : `LEARNS` réunit tous les jeux. `methods` liste les méthodes ; `level` est le plus petit niveau d'apprentissage par montée de niveau, tous jeux confondus (0 : appris en évoluant), et manque si l'attaque ne s'apprend pas ainsi.
- **Efficacité** : seules les relations non neutres existent. Sans relation entre deux types, le facteur vaut ×1. Contre une forme à deux types, les facteurs des deux types se multiplient (de ×0 à ×4).
- **`category` a deux sens** : sur un `Pokemon`, sa catégorie d'espèce (« Pokémon Ombre »), écrite sans le mot « Pokémon » pour les 120 espèces de la 9e génération (« Chat Plante ») ; sur une `Move`, « physique », « spéciale » ou « statut ».
- **Noms** : 62 noms portent l'apostrophe typographique ’ (« Écras’Face ») et 2 l'apostrophe droite ' ; une égalité écrite avec l'autre apostrophe ne les trouve pas. Quelques noms désignent deux nœuds (les 18 attaques Z génériques, en variante physique et spéciale ; le talent « Osmose Équine » ; deux noms de formes) : `id` les distingue.
- **Propriétés absentes** : une attaque sans puissance fixe (attaque de statut, puissance variable) ou sans précision n'a pas la propriété, sauf 18 attaques récentes, qui portent 0 à la place (17 puissances et 3 précisions).

## Valeurs possibles

- `Type.name` : Acier, Combat, Dragon, Eau, Électrik, Fée, Feu, Glace, Insecte, Normal, Plante, Poison, Psy, Roche, Sol, Spectre, Ténèbres, Vol.
- `Move.category` : physique, spéciale, statut.
- `LEARNS.methods` : « Montée de niveau », « Œuf », « Enseigné », « Capsule », « Changement de Forme », « train » (sans nom français), et 4 méthodes rares, propres à un jeu ou à un événement.
- `factor` : 2.0 (`SUPER_EFFECTIVE_AGAINST`), 0.5 (`NOT_VERY_EFFECTIVE_AGAINST`), 0.0 (`NO_EFFECT_AGAINST`).
- `HAS_TYPE.slot` : 1 ou 2. `HAS_ABILITY.isHidden` et `Form.isDefault` : vrai ou faux.

## Recherche d'un nom approché

L'index plein texte `names_fulltext` couvre la propriété `name` des labels `Pokemon`, `Form`, `Type`, `Move` et `Ability`, sans casse ni accents. Un `~` après un mot cherche aussi les mots proches : un nom mal orthographié retrouve le bon (exemple 6).

## Exemples

1. Quel est le type principal d'Ectoplasma ?

```cypher
MATCH (:Pokemon {name: 'Ectoplasma'})-[:HAS_DEFAULT_FORM]->(:Form)-[:HAS_TYPE {slot: 1}]->(t:Type)
RETURN t.name AS typePrincipal
```

2. Quelles formes de Deoxys ont une défense plus haute que sa forme par défaut ?

```cypher
MATCH (p:Pokemon {name: 'Deoxys'})-[:HAS_DEFAULT_FORM]->(d:Form)
MATCH (f:Form)-[:FORM_OF]->(p)
WHERE f.statDefense > d.statDefense
RETURN f.name AS forme, f.statDefense AS defense
ORDER BY defense DESC
```

3. De quelle espèce Tartard est-il l'évolution ?

```cypher
MATCH (avant:Pokemon)-[:EVOLVES_INTO]->(:Pokemon {name: 'Tartard'})
RETURN avant.name AS evolueDe
```

4. Quel facteur ont les attaques de type Fée contre le type Insecte ? Aucune relation : ×1.

```cypher
MATCH (attaque:Type {name: 'Fée'}), (cible:Type {name: 'Insecte'})
OPTIONAL MATCH (attaque)-[e]->(cible)
RETURN coalesce(e.factor, 1.0) AS facteur
```

5. Quelles attaques Noarfang apprend-il par montée de niveau, et à quel niveau au plus tôt ?

```cypher
MATCH (:Pokemon {name: 'Noarfang'})-[:HAS_DEFAULT_FORM]->(:Form)-[r:LEARNS]->(a:Move)
WHERE 'Montée de niveau' IN r.methods
RETURN a.name AS attaque, r.level AS niveau
ORDER BY niveau, attaque
```

6. Quel nom ressemble à « ectoplsma » ?

```cypher
CALL db.index.fulltext.queryNodes('names_fulltext', 'ectoplsma~') YIELD node, score
RETURN labels(node) AS labels, node.name AS nom, score
ORDER BY score DESC
LIMIT 5
```

7. Que disent de ses fruits les descriptions de Tropius, et dans quels jeux ?

```cypher
MATCH (:Pokemon {name: 'Tropius'})-[:HAS_DESCRIPTION]->(d:Description)
WHERE d.text CONTAINS 'fruit'
RETURN d.text AS description, d.games AS jeux
```

8. Quelles attaques ont un nom qui commence par « Ball’ » ?

```cypher
MATCH (a:Move)
WHERE a.name STARTS WITH 'Ball’'
RETURN a.name AS attaque
ORDER BY attaque
```
