# Fiche de schéma : le graphe Pokémon

Données de PokéAPI, noms en français. Lecture seule, par l'outil `read-cypher`.

## Nœuds

- `Pokemon` : une espèce (1 025) ; propriétés `id`, `identifiantPokeapi`, `nom`, `categorie`.
- `Forme` : une forme d'une espèce (1 351), sa forme par défaut ou l'une de ses variantes ; c'est la forme qui porte les types, les statistiques, les talents et les attaques. Propriétés `id`, `identifiantPokeapi`, `nom`, `parDefaut`, `statPv`, `statAttaque`, `statDefense`, `statAttaqueSpeciale`, `statDefenseSpeciale`, `statVitesse`.
- `Type` : un type (18) ; propriétés `id`, `identifiantPokeapi`, `nom`.
- `Attaque` : une attaque (919) ; propriétés `id`, `identifiantPokeapi`, `nom`, `puissance`, `precision`, `pp`, `categorie`.
- `Talent` : un talent (313) ; propriétés `id`, `identifiantPokeapi`, `nom`.
- `Description` : un texte de description d'une espèce (5 233) ; propriétés `texte` et `jeux`, les jeux où il paraît.

`identifiantPokeapi` est l'identifiant anglais de PokéAPI (`gengar` pour l'espèce Ectoplasma). La forme par défaut porte le nom de son espèce.

## Relations

- `(:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)` : la forme par défaut de chaque espèce.
- `(:Forme)-[:FORME_DE]->(:Pokemon)` : chaque forme vers son espèce, forme par défaut comprise.
- `(:Pokemon)-[:EVOLUE_EN]->(:Pokemon)` : d'une espèce vers son évolution directe.
- `(:Forme)-[:A_LE_TYPE {rang}]->(:Type)` : `rang` vaut 1 pour le type principal, 2 pour le second.
- `(:Attaque)-[:A_LE_TYPE]->(:Type)` : le type de l'attaque.
- `(:Type)-[:SUPER_EFFICACE_CONTRE|PEU_EFFICACE_CONTRE|SANS_EFFET_CONTRE {facteur}]->(:Type)` : du type de l'attaque vers un type de la cible.
- `(:Forme)-[:A_LE_TALENT {cache}]->(:Talent)` : `cache` est vrai pour le talent caché.
- `(:Forme)-[:APPREND {methodes, niveau}]->(:Attaque)` : voir les règles.
- `(:Pokemon)-[:A_POUR_DESCRIPTION]->(:Description)`.

## Règles

- **Un Pokémon est une espèce, prise dans sa forme par défaut** (`A_POUR_FORME_PAR_DEFAUT`). Les autres formes ne comptent que si la question les nomme ; une réponse qui en ajoute le signale.
- **Apprendre une attaque**, c'est l'apprendre dans au moins un jeu, par n'importe quelle méthode : `APPREND` réunit tous les jeux. `methodes` liste les méthodes ; `niveau` est le plus petit niveau d'apprentissage par montée de niveau, tous jeux confondus (0 : appris en évoluant), et manque si l'attaque ne s'apprend pas ainsi.
- **Efficacité** : seules les relations non neutres existent. Sans relation entre deux types, le facteur vaut ×1. Contre une forme à deux types, les facteurs des deux types se multiplient (de ×0 à ×4).
- **`categorie` a deux sens** : sur un `Pokemon`, sa catégorie d'espèce (« Pokémon Ombre »), écrite sans le mot « Pokémon » pour les 120 espèces de la 9e génération (« Chat Plante ») ; sur une `Attaque`, « physique », « spéciale » ou « statut ».
- **Noms** : 62 noms portent l'apostrophe typographique ’ (« Écras’Face ») ; une égalité écrite avec l'apostrophe droite ' ne les trouve pas. Quelques noms désignent deux nœuds (les 18 attaques Z génériques, en variante physique et spéciale ; le talent « Osmose Équine » ; deux noms de formes) : `id` les distingue.
- **Propriétés absentes** : une attaque sans puissance fixe (attaque de statut, puissance variable) ou sans précision n'a pas la propriété.

## Valeurs possibles

- `Type.nom` : Acier, Combat, Dragon, Eau, Électrik, Fée, Feu, Glace, Insecte, Normal, Plante, Poison, Psy, Roche, Sol, Spectre, Ténèbres, Vol.
- `Attaque.categorie` : physique, spéciale, statut.
- `APPREND.methodes` : « Montée de niveau », « Œuf », « Enseigné », « Capsule », « Changement de Forme », « train » (sans nom français), et 6 méthodes rares, propres à un jeu ou à un événement.
- `facteur` : 2.0 (`SUPER_EFFICACE_CONTRE`), 0.5 (`PEU_EFFICACE_CONTRE`), 0.0 (`SANS_EFFET_CONTRE`).
- `A_LE_TYPE.rang` : 1 ou 2. `A_LE_TALENT.cache` et `Forme.parDefaut` : vrai ou faux.

## Recherche d'un nom approché

L'index plein texte `noms_plein_texte` couvre la propriété `nom` des labels `Pokemon`, `Forme`, `Type`, `Attaque` et `Talent`, sans casse ni accents. Un `~` après un mot cherche aussi les mots proches : un nom mal orthographié retrouve le bon (exemple 6).

## Exemples

1. Quel est le type principal d'Ectoplasma ?

```cypher
MATCH (:Pokemon {nom: 'Ectoplasma'})-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:A_LE_TYPE {rang: 1}]->(t:Type)
RETURN t.nom AS typePrincipal
```

2. Quelles formes de Deoxys ont une défense plus haute que sa forme par défaut ?

```cypher
MATCH (p:Pokemon {nom: 'Deoxys'})-[:A_POUR_FORME_PAR_DEFAUT]->(d:Forme)
MATCH (f:Forme)-[:FORME_DE]->(p)
WHERE f.statDefense > d.statDefense
RETURN f.nom AS forme, f.statDefense AS defense
ORDER BY defense DESC
```

3. De quelle espèce Tartard est-il l'évolution ?

```cypher
MATCH (avant:Pokemon)-[:EVOLUE_EN]->(:Pokemon {nom: 'Tartard'})
RETURN avant.nom AS evolueDe
```

4. Quel facteur ont les attaques de type Fée contre le type Insecte ? Aucune relation : ×1.

```cypher
MATCH (attaque:Type {nom: 'Fée'}), (cible:Type {nom: 'Insecte'})
OPTIONAL MATCH (attaque)-[e]->(cible)
RETURN coalesce(e.facteur, 1.0) AS facteur
```

5. Quelles attaques Noarfang apprend-il par montée de niveau, et à quel niveau au plus tôt ?

```cypher
MATCH (:Pokemon {nom: 'Noarfang'})-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[r:APPREND]->(a:Attaque)
WHERE 'Montée de niveau' IN r.methodes
RETURN a.nom AS attaque, r.niveau AS niveau
ORDER BY niveau, attaque
```

6. Quel nom ressemble à « ectoplsma » ?

```cypher
CALL db.index.fulltext.queryNodes('noms_plein_texte', 'ectoplsma~') YIELD node, score
RETURN labels(node) AS labels, node.nom AS nom, score
ORDER BY score DESC
LIMIT 5
```

7. Que disent de ses fruits les descriptions de Tropius, et dans quels jeux ?

```cypher
MATCH (:Pokemon {nom: 'Tropius'})-[:A_POUR_DESCRIPTION]->(d:Description)
WHERE d.texte CONTAINS 'fruit'
RETURN d.texte AS description, d.jeux AS jeux
```

8. Quelles attaques ont un nom qui commence par « Ball’ » ?

```cypher
MATCH (a:Attaque)
WHERE a.nom STARTS WITH 'Ball’'
RETURN a.nom AS attaque
ORDER BY attaque
```
