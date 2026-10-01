// Q6 — Quels sont les types de Méga-Dracaufeu X, et en quoi diffèrent-ils de ceux de Dracaufeu ?
// (text-to-Cypher) La question nomme une forme : on compare la forme Méga-Dracaufeu X à la forme par défaut.
MATCH (:Pokemon {nom: 'Dracaufeu'})-[:A_POUR_FORME_PAR_DEFAUT]->(d:Forme)
MATCH (x:Forme {nom: 'Méga-Dracaufeu X'})
WITH COLLECT { MATCH (x)-[r:A_LE_TYPE]->(t:Type) RETURN t.nom ORDER BY r.rang } AS typesMegaX,
  COLLECT { MATCH (d)-[r:A_LE_TYPE]->(t:Type) RETURN t.nom ORDER BY r.rang } AS typesDracaufeu
RETURN typesMegaX, typesDracaufeu,
  [t IN typesMegaX WHERE NOT t IN typesDracaufeu] AS gagnes,
  [t IN typesDracaufeu WHERE NOT t IN typesMegaX] AS perdus;
