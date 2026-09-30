// Pokémon, niveau espèce (spec 001, T4.3) : 1 025 Pokémon, leur nom et leur catégorie, puis 484 évolutions.
//
// Le Pokémon porte l'identité, la forme ce qui varie (ADR-0004) : types, stats et talents arrivent avec les
// formes (03). Idempotent : MERGE sur id (contrainte pokemon_id), puis SET ; une relance ne crée rien.

// Les 1 025 Pokémon, avec leur identifiant anglais de PokéAPI (plan D6).
LOAD CSV WITH HEADERS FROM $base + '/pokemon_species.csv' AS ligne
MERGE (p:Pokemon {id: toInteger(ligne.id)})
SET p.identifiantPokeapi = ligne.identifier;

// Leur nom et leur catégorie en français (langue 5 : name et genus), tels quels (Q23 : « Pokémon Flamme »).
LOAD CSV WITH HEADERS FROM $base + '/pokemon_species_names.csv' AS ligne
WITH ligne
WHERE ligne.local_language_id = '5'
MATCH (p:Pokemon {id: toInteger(ligne.pokemon_species_id)})
SET p.nom = ligne.name, p.categorie = ligne.genus;

// Évolutions, en seconde passe : 17 Pokémon évoluent d'une espèce placée plus loin dans le CSV, des bébés
// ajoutés après coup (Pichu, 172, évolue en Pikachu, 25) ; en une seule passe, leur source n'existerait pas
// encore. Sans evolves_from_species_id, toInteger rend null : la ligne est écartée.
LOAD CSV WITH HEADERS FROM $base + '/pokemon_species.csv' AS ligne
WITH ligne, toInteger(ligne.evolves_from_species_id) AS avantId
WHERE avantId IS NOT NULL
MATCH (avant:Pokemon {id: avantId})
MATCH (apres:Pokemon {id: toInteger(ligne.id)})
MERGE (avant)-[:EVOLUE_EN]->(apres);
