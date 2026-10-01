// Q14 — Quels Pokémon de type Feu ne peuvent apprendre aucune attaque de type Eau ? (text-to-Cypher)
// Forme par défaut de type Feu (en premier ou second type), sans aucune attaque Eau parmi celles qu'elle
// peut apprendre.
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)-[:A_LE_TYPE]->(:Type {nom: 'Feu'})
WHERE NOT EXISTS { (f)-[:APPREND]->(:Attaque)-[:A_LE_TYPE]->(:Type {nom: 'Eau'}) }
RETURN p.nom AS pokemon
ORDER BY pokemon;
