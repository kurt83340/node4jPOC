// Q3 — Quel Pokémon vit près des volcans ? (GraphRAG)
// Méthode des questions sémantiques (README) : filet de mots-clés en mots entiers sur les descriptions, puis
// table de classement explicite, tirée d'une grille écrite avant le tri (2026-10-01) :
//   obligatoire : une description dit que l'espèce vit, habite ou se trouve dans, sur ou près d'un volcan
//                 (ou d'une région, d'un cratère, d'une grotte ou d'un massif volcanique) ;
//   acceptable  : elle la place dans la lave ou le magma, ou au contact d'un volcan, sans dire qu'elle y vit ;
//   écarté      : le mot y est, pas l'habitat (trait du corps, légende, verbe « laver », cratère de météorite).
// Un candidat absent de la table sort « à classer » ; une espèce de la table que le filet ne trouve plus sort
// « plus trouvée ». Les raisons résument, sans recopier les descriptions (ADR-0001).
WITH [
    {pokemon: 'Boumata', ensemble: 'obligatoire', raison: 'vit dans les volcans'},
    {pokemon: 'Camérupt', ensemble: 'obligatoire', raison: 'vit dans les cratères des volcans'},
    {pokemon: 'Carchacrok', ensemble: 'obligatoire', raison: 'vit dans les massifs volcaniques'},
    {pokemon: 'Flamajou', ensemble: 'obligatoire', raison: 'vit dans les cratères des volcans'},
    {pokemon: 'Heatran', ensemble: 'obligatoire', raison: 'hante les grottes volcaniques'},
    {pokemon: 'Limagma', ensemble: 'obligatoire', raison: 'commun dans les régions volcaniques'},
    {pokemon: 'Maganon', ensemble: 'obligatoire', raison: 'vit dans les cratères des volcans'},
    {pokemon: 'Magby', ensemble: 'obligatoire', raison: 'vit près des volcans'},
    {pokemon: 'Magmar', ensemble: 'obligatoire', raison: 'se trouve près des bouches de volcans'},
    {pokemon: 'Pyronille', ensemble: 'obligatoire', raison: 'vit au pied des volcans'},
    {pokemon: 'Tritox', ensemble: 'obligatoire', raison: 'habite les volcans'},
    {pokemon: 'Entei', ensemble: 'acceptable', raison: 'né d’une éruption volcanique, sans habitat dit'},
    {pokemon: 'Groudon', ensemble: 'acceptable', raison: 'dormait dans le magma souterrain'},
    {pokemon: 'Sabelette', ensemble: 'acceptable', raison: 'va se sécher près d’un volcan'},
    {pokemon: 'Sulfura', ensemble: 'acceptable', raison: 'se soigne dans le magma d’un volcan'},
    {pokemon: 'Volcaropod', ensemble: 'acceptable', raison: 'plonge dans le magma'},
    {pokemon: 'Chamallot', ensemble: 'écarté', raison: 'magma et lave dans son corps : un trait'},
    {pokemon: 'Lippouti', ensemble: 'écarté', raison: 'verbe laver'},
    {pokemon: 'Miaouss', ensemble: 'écarté', raison: 'verbe laver'},
    {pokemon: 'Pyrax', ensemble: 'écarté', raison: 'cendres d’un volcan dans une légende'},
    {pokemon: 'Regice', ensemble: 'écarté', raison: 'résiste au magma : un trait'},
    {pokemon: 'Regigigas', ensemble: 'écarté', raison: 'a créé des Pokémon à partir de magma : une légende'},
    {pokemon: 'Rhinastoc', ensemble: 'écarté', raison: 'résiste à une éruption : un trait'},
    {pokemon: 'Rhinoféros', ensemble: 'écarté', raison: 'résiste au magma et à la lave : un trait'},
    {pokemon: 'Séléroc', ensemble: 'écarté', raison: 'cratère de météorite'},
    {pokemon: 'Tylton', ensemble: 'écarté', raison: 'verbe laver'}
  ] AS classement
CALL () {
  MATCH (p:Pokemon)
  WHERE EXISTS {
    (p)-[:A_POUR_DESCRIPTION]->(d:Description)
    WHERE d.texte =~ '(?iU).*\\b(volcans?|volcaniques?|laves?|magmas?|cratères?|éruptions?)\\b.*'
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
