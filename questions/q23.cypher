// Q23 — Quelle est la catégorie de Dracaufeu ? (toutes les techniques)
MATCH (p:Pokemon {nom: 'Dracaufeu'})
RETURN p.nom AS pokemon, p.categorie AS categorie;
