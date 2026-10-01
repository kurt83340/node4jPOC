// Q22 — Contre quel type les attaques Normal n'ont-elles aucun effet ? (toutes les techniques)
MATCH (:Type {nom: 'Normal'})-[:SANS_EFFET_CONTRE]->(t:Type)
RETURN t.nom AS type
ORDER BY type;
