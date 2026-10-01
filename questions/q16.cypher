// Q16 — Quel Pokémon est capable de faire le tour de la planète en moins d'une journée ? (GraphRAG, paraphrase)
// Méthode des questions sémantiques (README). Filet : tour ou parcours du monde, de la Terre, de la planète
// ou du globe, et distances parcourues (le piège d'Arcanin). Grille écrite avant le tri (2026-10-01) :
//   obligatoire : il fait le tour du monde, de la Terre ou du globe en moins de 24 heures ;
//   acceptable  : il en fait le tour avec une durée ou une vitesse compatible avec moins d'une journée ;
//   écarté      : les mots y sont, pas l'exploit (tour sans durée, parcourir le monde, autre sens).
// Règle commune du 2026-10-01 (README) : un acceptable touche le cœur de la question, ici la durée ; un tour
// du monde sans durée n'y touche pas (Cotovol et Scorvol, d'abord acceptables, passent en écarté).
// Les raisons résument, sans recopier les descriptions (ADR-0001).
WITH [
    {pokemon: 'Dracolosse', ensemble: 'obligatoire', raison: 'fait le tour de la planète en seize heures'},
    {pokemon: 'Arcanin', ensemble: 'écarté', raison: '10 000 km en 24 heures : un quart du tour de la Terre'},
    {pokemon: 'Cotovol', ensemble: 'écarté', raison: 'fait le tour du globe au gré des vents, sans durée'},
    {pokemon: 'Entei', ensemble: 'écarté', raison: 'parcourt le monde, sans en faire le tour'},
    {pokemon: 'Hoothoot', ensemble: 'écarté', raison: 'sent la rotation de la planète'},
    {pokemon: 'Keldeo', ensemble: 'écarté', raison: 'parcourt le monde, sans en faire le tour'},
    {pokemon: 'Nirondelle', ensemble: 'écarté', raison: '300 km par jour : bien loin du tour de la Terre'},
    {pokemon: 'Registeel', ensemble: 'écarté', raison: 'viendrait d’une autre planète'},
    {pokemon: 'Scorvol', ensemble: 'écarté', raison: 'peut faire le tour du monde en planant, sans durée'},
    {pokemon: 'Steelix', ensemble: 'écarté', raison: 'creuse vers le centre de la planète'},
    {pokemon: 'Togetic', ensemble: 'écarté', raison: 'parcourt le monde, sans en faire le tour'}
  ] AS classement
CALL () {
  MATCH (p:Pokemon)
  WHERE EXISTS {
    (p)-[:A_POUR_DESCRIPTION]->(d:Description)
    WHERE d.texte =~ '(?iU).*\\b(tour du (monde|globe)|tour de la (terre|planète)|autour (du (monde|globe)|de la (terre|planète))|planète|globe|parcour\\w* (le monde|\\d[\\d\\s]*km))\\b.*'
  }
  RETURN collect(p.nom) AS trouves
}
UNWIND trouves + [c IN classement WHERE NOT c.pokemon IN trouves | c.pokemon] AS nom
WITH nom, nom IN trouves AS trouve, [c IN classement WHERE c.pokemon = nom][0] AS c
RETURN nom AS pokemon,
  CASE WHEN NOT trouve THEN 'plus trouvée' WHEN c IS NULL THEN 'à classer' ELSE c.ensemble END AS ensemble,
  coalesce(c.raison, '') AS raison
ORDER BY CASE ensemble
    WHEN 'obligatoire' THEN 1 WHEN 'acceptable' THEN 2 WHEN 'écarté' THEN 3 WHEN 'à classer' THEN 4 ELSE 5
  END, pokemon;
