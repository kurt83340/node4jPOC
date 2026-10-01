// Q20 — Si les attaques de type Roche disparaissaient, quels Pokémon perdraient le plus d'attaques ?
// (text-to-Cypher) Nombre d'attaques Roche que la forme par défaut peut apprendre ; les deux meilleurs
// scores, ex æquo compris.
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:APPREND]->(a:Attaque)-[:A_LE_TYPE]->(:Type {nom: 'Roche'})
WITH p, count(a) AS attaquesRoche
WITH collect({pokemon: p.nom, n: attaquesRoche}) AS scores
WITH scores, COLLECT { UNWIND scores AS s RETURN DISTINCT s.n AS n ORDER BY n DESC LIMIT 2 } AS meilleurs
UNWIND scores AS s
WITH s
WHERE s.n IN meilleurs
RETURN s.pokemon AS pokemon, s.n AS attaquesRoche
ORDER BY attaquesRoche DESC, pokemon;
