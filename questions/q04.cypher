// Q4 — Quels sont les types et les talents de Lucario, dont son talent caché ? (toutes les techniques)
// Forme par défaut ; types dans l'ordre de leur rang, talents par ordre alphabétique, le caché à part.
MATCH (p:Pokemon {nom: 'Lucario'})-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
RETURN p.nom AS pokemon,
  COLLECT { MATCH (f)-[r:A_LE_TYPE]->(t:Type) RETURN t.nom ORDER BY r.rang } AS types,
  COLLECT { MATCH (f)-[r:A_LE_TALENT]->(t:Talent) WHERE NOT r.cache RETURN t.nom ORDER BY t.nom } AS talents,
  COLLECT { MATCH (f)-[r:A_LE_TALENT]->(t:Talent) WHERE r.cache RETURN t.nom ORDER BY t.nom } AS talentCache;
