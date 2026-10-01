// Q19 — Quels sont les types de Dracofeu ? (faute de frappe voulue ; robustesse)
// La réponse de référence reconnaît Dracaufeu : la faute éprouve la technique, pas cette requête.
MATCH (p:Pokemon {nom: 'Dracaufeu'})-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
RETURN p.nom AS pokemon, COLLECT { MATCH (f)-[r:A_LE_TYPE]->(t:Type) RETURN t.nom ORDER BY r.rang } AS types;
