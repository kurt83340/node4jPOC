// Q27 — Mon Pikachu doit battre un Tortank : quelle attaque lui conseilles-tu, et pourquoi ? (agent)
// Attaques que la forme par défaut de Pikachu peut apprendre, classées par puissance × multiplicateur contre
// les types de Tortank. Règle (README) : toute attaque Électrik puissante, avec l'explication (×2 contre l'Eau).
// La précision est affichée pour juger, pas classée : Élecanon (50 %) est en tête, une attaque plus sûre
// se défend aussi.
MATCH (:Pokemon {nom: 'Tortank'})-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:A_LE_TYPE]->(c:Type)
WITH collect(c) AS typesCible
MATCH (:Pokemon {nom: 'Pikachu'})-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:APPREND]->(a:Attaque)-[:A_LE_TYPE]->(t:Type)
WHERE a.puissance IS NOT NULL
WITH a, t, reduce(m = 1.0, c IN typesCible |
    m * coalesce(COLLECT { MATCH (t)-[e]->(c) RETURN e.facteur }[0], 1.0)) AS multiplicateur
RETURN a.nom AS attaque, t.nom AS type, a.puissance AS puissance, a.precision AS precision, multiplicateur,
  a.puissance * multiplicateur AS puissanceEffective
ORDER BY puissanceEffective DESC, attaque
LIMIT 5;
