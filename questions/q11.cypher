// Q11 — Pourquoi Carapuce encaisse-t-il mieux les attaques Feu que Bulbizarre ? (agent, explication)
// Facteur de l'attaque Feu contre chaque type de la forme par défaut (×1 sans relation), puis leur produit.
MATCH (feu:Type {nom: 'Feu'})
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
WHERE p.nom IN ['Bulbizarre', 'Carapuce']
WITH p, COLLECT {
    MATCH (f)-[r:A_LE_TYPE]->(t:Type)
    RETURN {type: t.nom, facteurFeu: coalesce(COLLECT { MATCH (feu)-[e]->(t) RETURN e.facteur }[0], 1.0)}
    ORDER BY r.rang
  } AS types
RETURN p.nom AS pokemon, types, reduce(m = 1.0, x IN types | m * x.facteurFeu) AS multiplicateurFeu
ORDER BY pokemon;
