// Q18 — (2e tour, juste après Q2) Et dans mon équipe, lequel est le plus vulnérable aux attaques Roche ?
// (mémoire de conversation) Équipe de référence (README) : Florizarre, Dracaufeu, Tortank, Pikachu,
// Ronflex, Lokhlass. Multiplicateur de l'attaque Roche contre la forme par défaut de chacun.
MATCH (roche:Type {nom: 'Roche'})
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
WHERE p.nom IN ['Florizarre', 'Dracaufeu', 'Tortank', 'Pikachu', 'Ronflex', 'Lokhlass']
WITH p, reduce(m = 1.0, x IN COLLECT { MATCH (f)-[:A_LE_TYPE]->(t:Type) RETURN t } |
    m * coalesce(COLLECT { MATCH (roche)-[e]->(x) RETURN e.facteur }[0], 1.0)) AS multiplicateur
RETURN p.nom AS pokemon, multiplicateur
ORDER BY multiplicateur DESC, pokemon;
