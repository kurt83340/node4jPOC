// Q25 — Quel type compte le plus de Pokémon ? (text-to-Cypher)
// Espèces dont la forme par défaut a ce type, en premier ou second type ; les trois premiers.
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:A_LE_TYPE]->(t:Type)
RETURN t.nom AS type, count(DISTINCT p) AS pokemon
ORDER BY pokemon DESC, type
LIMIT 3;
