// Q5 — Quelles sont toutes les évolutions possibles d'Évoli ? (text-to-Cypher)
// Toutes les espèces atteignables depuis Évoli, en une étape ou plus.
MATCH (:Pokemon {nom: 'Évoli'})-[:EVOLUE_EN*1..]->(e:Pokemon)
RETURN DISTINCT e.nom AS evolution
ORDER BY evolution;
