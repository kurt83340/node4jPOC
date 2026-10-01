// Q24 — Quels sont le type, la puissance et la catégorie de l'attaque Séisme ? (toutes les techniques)
MATCH (a:Attaque {nom: 'Séisme'})-[:A_LE_TYPE]->(t:Type)
RETURN a.nom AS attaque, t.nom AS type, a.puissance AS puissance, a.categorie AS categorie;
