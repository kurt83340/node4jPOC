// Q2 — Propose une équipe de 6 qui couvre les faiblesses de la mienne. (agent en plusieurs étapes)
// Pas de réponse figée (README) : une requête de contrôle. Pour chaque type d'attaque super efficace (×2 ou
// plus) contre au moins un membre de l'équipe de référence, l'équipe proposée doit compter un membre qui y
// résiste (×0,5 ou moins, immunité comprise). Formes par défaut ; 6 espèces distinctes.

// Les types qui menacent l'équipe de référence, et les membres qu'ils menacent.
WITH ['Florizarre', 'Dracaufeu', 'Tortank', 'Pikachu', 'Ronflex', 'Lokhlass'] AS reference
MATCH (t:Type)
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
WHERE p.nom IN reference
WITH t, p, reduce(m = 1.0, x IN COLLECT { MATCH (f)-[:A_LE_TYPE]->(y:Type) RETURN y } |
    m * coalesce(COLLECT { MATCH (t)-[e]->(x) RETURN e.facteur }[0], 1.0)) AS multiplicateur
WHERE multiplicateur >= 2.0
WITH t, p, multiplicateur
ORDER BY p.nom
RETURN t.nom AS menace, collect(p.nom + ' ×' + toString(multiplicateur)) AS membresMenaces
ORDER BY menace;

// Contrôle d'une équipe proposée : les types menaçants auxquels aucun membre ne résiste (liste vide =
// équipe qui couvre tout), et le nombre d'espèces reconnues (6 attendues). Pour contrôler une autre
// proposition, remplacer la liste proposee ; celle-ci est un exemple valide.
WITH ['Florizarre', 'Dracaufeu', 'Tortank', 'Pikachu', 'Ronflex', 'Lokhlass'] AS reference,
  ['Magnéton', 'Dracolosse', 'Flagadoss', 'Noadkoko', 'Staross', 'Parasect'] AS proposee
MATCH (t:Type)
WITH reference, proposee, t,
  COLLECT {
    MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
    WHERE p.nom IN reference
    RETURN reduce(m = 1.0, x IN COLLECT { MATCH (f)-[:A_LE_TYPE]->(y:Type) RETURN y } |
      m * coalesce(COLLECT { MATCH (t)-[e]->(x) RETURN e.facteur }[0], 1.0))
  } AS contreReference,
  COLLECT {
    MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
    WHERE p.nom IN proposee
    RETURN reduce(m = 1.0, x IN COLLECT { MATCH (f)-[:A_LE_TYPE]->(y:Type) RETURN y } |
      m * coalesce(COLLECT { MATCH (t)-[e]->(x) RETURN e.facteur }[0], 1.0))
  } AS contreProposee
ORDER BY t.nom
WITH proposee, collect(CASE
    WHEN any(m IN contreReference WHERE m >= 2.0) AND NOT any(m IN contreProposee WHERE m <= 0.5)
    THEN t.nom
  END) AS typesNonCouverts
WITH typesNonCouverts, COUNT { MATCH (p:Pokemon) WHERE p.nom IN proposee } AS especesReconnues
RETURN especesReconnues, typesNonCouverts, especesReconnues = 6 AND size(typesNonCouverts) = 0 AS equipeValide;
