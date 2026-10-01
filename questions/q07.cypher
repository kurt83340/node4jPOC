// Q7 — Quels Pokémon peuvent apprendre Séisme et ne craignent pas du tout les attaques Électrik ?
// (text-to-Cypher) Forme par défaut qui apprend Séisme et dont un type est immunisé contre l'Électrik
// (SANS_EFFET_CONTRE, multiplicateur nul). Règle (README) : ensemble exact sur les types ; les immunités
// dues à un talent (Paratonnerre, Absorb Volt, Motorisé) ne comptent pas ici.
MATCH (electrik:Type {nom: 'Électrik'})
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)-[:APPREND]->(:Attaque {nom: 'Séisme'})
WHERE EXISTS { (f)-[:A_LE_TYPE]->(:Type)<-[:SANS_EFFET_CONTRE]-(electrik) }
RETURN p.nom AS pokemon
ORDER BY pokemon;
