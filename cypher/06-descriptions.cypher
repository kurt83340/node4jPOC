// Descriptions (spec 001, T5.2) : 5 233 textes français distincts par Pokémon, tirés des 7 116 lignes de
// pokemon_species_flavor_text, chacun avec la liste des jeux où il apparaît.
//
// Normalisation (plan D4) : sauts de ligne et espaces fines insécables (U+202F) deviennent des espaces, puis
// trim ; sans la seconde substitution, on obtient 5 240 textes au lieu de 5 233. Description n'a pas de clé
// (plan D2) : le MERGE porte sur le chemin (Pokémon, texte), qui rend chaque texte unique pour son Pokémon ;
// un même texte chez deux Pokémon donne deux descriptions. jeux = union des noms français des jeux (repli sur
// l'identifiant), pour citer ses sources. Lots de 1 000 lignes (plan, Performance). Idempotent : une relance
// ne crée rien et n'allonge aucune liste.
LOAD CSV WITH HEADERS FROM $base + '/versions.csv' AS ligne
WITH collect({id: ligne.id, identifiant: ligne.identifier}) AS identifiants
LOAD CSV WITH HEADERS FROM $base + '/version_names.csv' AS ligne
WITH identifiants,
  collect(CASE WHEN ligne.local_language_id = '5' THEN {id: ligne.version_id, nom: ligne.name} END) AS nomsFr
WITH [v IN identifiants |
  {id: v.id, nom: coalesce([n IN nomsFr WHERE n.id = v.id | n.nom][0], v.identifiant)}] AS versions
LOAD CSV WITH HEADERS FROM $base + '/pokemon_species_flavor_text.csv' AS ligne
WITH versions, ligne
WHERE ligne.language_id = '5'
CALL (ligne, versions) {
  MATCH (p:Pokemon {id: toInteger(ligne.species_id)})
  WITH p, [v IN versions WHERE v.id = ligne.version_id | v.nom][0] AS jeu,
    trim(replace(replace(ligne.flavor_text, '\n', ' '), '\u202F', ' ')) AS texte
  MERGE (p)-[:A_POUR_DESCRIPTION]->(d:Description {texte: texte})
  SET d.jeux = CASE
      WHEN jeu IN coalesce(d.jeux, []) THEN d.jeux
      ELSE coalesce(d.jeux, []) + jeu
    END
} IN TRANSACTIONS OF 1000 ROWS;
