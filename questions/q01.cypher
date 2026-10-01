// Q1 — Quelles attaques font le plus mal à Dracaufeu ? (technique visée : Cypher)
// Règle (README) : le type le plus efficace contre Dracaufeu, puis ses attaques les plus puissantes qu'au
// moins une forme peut apprendre ; les capacités Z, jamais apprises, sont exclues. Multiplicateur : produit
// des facteurs d'efficacité sur les types de la forme par défaut (×1 sans relation). La précision est
// affichée pour juger les réponses, pas classée.
MATCH (:Pokemon {nom: 'Dracaufeu'})-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:A_LE_TYPE]->(c:Type)
WITH collect(c) AS typesCible
MATCH (a:Attaque)-[:A_LE_TYPE]->(t:Type)
WHERE a.puissance IS NOT NULL AND EXISTS { (:Forme)-[:APPREND]->(a) }
WITH a, t, reduce(m = 1.0, c IN typesCible |
    m * coalesce(COLLECT { MATCH (t)-[e]->(c) RETURN e.facteur }[0], 1.0)) AS multiplicateur
RETURN a.nom AS attaque, t.nom AS type, a.puissance AS puissance, a.precision AS precision, multiplicateur,
  a.puissance * multiplicateur AS puissanceEffective
ORDER BY puissanceEffective DESC, attaque
LIMIT 5;
