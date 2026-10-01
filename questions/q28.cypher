// Q28 — (2e tour, juste après Q27) Et si l'adversaire remplace Tortank par Onix ? (agent + mémoire)
// Règle (README) : l'agent doit signaler que l'Électrik est sans effet contre Onix (Roche et Sol) ; Surf est
// attendu, une autre attaque ×4 ou ×2 est acceptée avec son explication.

// Le piège : le multiplicateur de l'Électrik contre Onix.
MATCH (:Pokemon {nom: 'Onix'})-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:A_LE_TYPE]->(c:Type)
WITH collect(c) AS typesCible
MATCH (t:Type {nom: 'Électrik'})
RETURN t.nom AS typeAttaque, [c IN typesCible | c.nom] AS typesOnix,
  reduce(m = 1.0, c IN typesCible | m * coalesce(COLLECT { MATCH (t)-[e]->(c) RETURN e.facteur }[0], 1.0))
    AS multiplicateur;

// Les attaques de Pikachu classées par puissance × multiplicateur contre Onix (précision affichée, pas classée).
MATCH (:Pokemon {nom: 'Onix'})-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:A_LE_TYPE]->(c:Type)
WITH collect(c) AS typesCible
MATCH (:Pokemon {nom: 'Pikachu'})-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:APPREND]->(a:Attaque)-[:A_LE_TYPE]->(t:Type)
WHERE a.puissance IS NOT NULL
WITH a, t, reduce(m = 1.0, c IN typesCible |
    m * coalesce(COLLECT { MATCH (t)-[e]->(c) RETURN e.facteur }[0], 1.0)) AS multiplicateur
RETURN a.nom AS attaque, t.nom AS type, a.puissance AS puissance, a.precision AS precision, multiplicateur,
  a.puissance * multiplicateur AS puissanceEffective
ORDER BY puissanceEffective DESC, attaque
LIMIT 5;
