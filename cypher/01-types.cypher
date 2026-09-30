// Types et efficacités (spec 001, T4.2) : 18 types, puis 120 relations d'efficacité entre eux.
//
// Seuls les 18 types classiques (id 1 à 18) deviennent des nœuds : Stellaire (19), ??? (10001) et Obscur
// (10002) sont écartés (ARCHITECTURE § 5), et leurs noms avec eux, faute de nœud à trouver par MATCH.
// Idempotent : MERGE sur id (contrainte type_id), puis SET des autres propriétés ; une relance ne crée rien.

// Les 18 types, avec leur identifiant anglais de PokéAPI (plan D6).
LOAD CSV WITH HEADERS FROM $base + '/types.csv' AS ligne
WITH ligne, toInteger(ligne.id) AS id
WHERE id <= 18
MERGE (t:Type {id: id})
SET t.identifiantPokeapi = ligne.identifier;

// Leurs noms en français (langue 5).
LOAD CSV WITH HEADERS FROM $base + '/type_names.csv' AS ligne
WITH ligne
WHERE ligne.local_language_id = '5'
MATCH (t:Type {id: toInteger(ligne.type_id)})
SET t.nom = ligne.name;

// Efficacités (plan D13) : damage_factor est un pourcentage. 200 → SUPER_EFFICACE_CONTRE, 50 →
// PEU_EFFICACE_CONTRE, 0 → SANS_EFFET_CONTRE, avec un facteur décimal (2.0 ; 0.5 ; 0.0) ; 100, neutre (×1
// dans un produit), n'est pas chargé. Type de relation dynamique ($(…), Cypher 25) : une seule passe, et un
// pourcentage inattendu arrête le chargement (le CASE rend null, que MERGE refuse) au lieu d'être ignoré.
LOAD CSV WITH HEADERS FROM $base + '/type_efficacy.csv' AS ligne
WITH ligne, toInteger(ligne.damage_factor) AS pourcentage
WHERE pourcentage <> 100
MATCH (attaquant:Type {id: toInteger(ligne.damage_type_id)})
MATCH (cible:Type {id: toInteger(ligne.target_type_id)})
WITH attaquant, cible, pourcentage,
  CASE pourcentage
    WHEN 200 THEN 'SUPER_EFFICACE_CONTRE'
    WHEN 50 THEN 'PEU_EFFICACE_CONTRE'
    WHEN 0 THEN 'SANS_EFFET_CONTRE'
  END AS relation
MERGE (attaquant)-[r:$(relation)]->(cible)
SET r.facteur = pourcentage / 100.0;
