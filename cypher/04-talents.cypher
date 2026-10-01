// Talents (spec 001, T4.5) : les 313 talents portés par au moins une forme, et leurs 2 943 relations.
//
// Seuls les talents utilisés deviennent des nœuds (ARCHITECTURE § 5) : un talent naît de sa relation à une
// forme, pas d'abilities.csv, qui en compte 374. Idempotent : MERGE sur id (contrainte talent_id) et sur la
// relation entre nœuds déjà trouvés, puis SET ; une relance ne crée rien.

// Les relations (forme, talent), et les talents avec elles ; cache repère le talent caché. Ce fichier a des
// fins de ligne Windows : LOAD CSV les gère (go/no-go, T2.2), trim avant conversion par prudence (plan).
LOAD CSV WITH HEADERS FROM $base + '/pokemon_abilities.csv' AS ligne
MATCH (f:Forme {id: toInteger(trim(ligne.pokemon_id))})
MERGE (t:Talent {id: toInteger(trim(ligne.ability_id))})
MERGE (f)-[r:A_LE_TALENT]->(t)
SET r.cache = (trim(ligne.is_hidden) = '1');

// Leur identifiant anglais de PokéAPI (plan D6) ; le MATCH écarte les talents qu'aucune forme ne porte.
LOAD CSV WITH HEADERS FROM $base + '/abilities.csv' AS ligne
MATCH (t:Talent {id: toInteger(ligne.id)})
SET t.identifiantPokeapi = ligne.identifier;

// Leur nom en français (langue 5). Un nom reste en double, hérité des données : « Osmose Équine », porté
// par les variantes Blizzeval et Spectreval (gardé, décision de Julien le 2026-10-01) ; verifier.sh l'attend.
LOAD CSV WITH HEADERS FROM $base + '/ability_names.csv' AS ligne
WITH ligne
WHERE ligne.local_language_id = '5'
MATCH (t:Talent {id: toInteger(ligne.ability_id)})
SET t.nom = ligne.name;

// Repli pour les 3 talents récents sans nom français (eelevate, fire-mane, aura-guard) : leur identifiant
// anglais (plan, cas limites).
MATCH (t:Talent)
WHERE t.nom IS NULL
SET t.nom = t.identifiantPokeapi;
