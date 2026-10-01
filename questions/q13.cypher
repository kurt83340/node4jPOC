// Q13 — Quelle attaque de type Feu est apprise par le plus de Pokémon ? (text-to-Cypher)
// Règle (README) : Zénith, toutes catégories d'attaques confondues ; Lance-Flammes est accepté si l'agent
// précise qu'il ne compte que les attaques offensives. Pokémon = espèce (forme par défaut). Deux lignes :
// une troisième couperait des ex æquo au hasard de l'ordre alphabétique.
MATCH (a:Attaque)-[:A_LE_TYPE]->(:Type {nom: 'Feu'})
WITH a, COUNT { (:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:APPREND]->(a) } AS pokemon
RETURN a.nom AS attaque, a.categorie AS categorie, pokemon
ORDER BY pokemon DESC, attaque
LIMIT 2;

// Les attaques offensives seulement (physiques ou spéciales).
MATCH (a:Attaque)-[:A_LE_TYPE]->(:Type {nom: 'Feu'})
WHERE a.categorie <> 'statut'
WITH a, COUNT { (:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:APPREND]->(a) } AS pokemon
RETURN a.nom AS attaqueOffensive, a.categorie AS categorie, pokemon
ORDER BY pokemon DESC, attaqueOffensive
LIMIT 3;
