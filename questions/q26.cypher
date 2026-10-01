// Q26 — Quels Pokémon passent la majeure partie de leur temps à dormir ? (GraphRAG)
// Méthode des questions sémantiques (README). Filet : un mot de sommeil et un mot de durée ou de quantité dans
// la même description (la question porte sur le temps passé à dormir, pas sur les habitudes de sommeil).
// Grille écrite avant le tri (2026-10-01) :
//   obligatoire : il dort la plupart du temps, presque toujours, toute la journée, ou ne fait que dormir et
//                 manger ;
//   acceptable  : il dort beaucoup, longtemps ou souvent, sans dire « la plupart du temps » ;
//   écarté      : il endort les autres, un sommeil ponctuel, les rêves, le sommeil d'un autre.
// Les raisons résument, sans recopier les descriptions (ADR-0001).
WITH [
    {pokemon: 'Abra', ensemble: 'obligatoire', raison: 'dort 18 heures par jour'},
    {pokemon: 'Bulbizarre', ensemble: 'obligatoire', raison: 'passe son temps à faire la sieste'},
    {pokemon: 'Dodoala', ensemble: 'obligatoire', raison: 'passe sa vie entière à dormir'},
    {pokemon: 'Jirachi', ensemble: 'obligatoire', raison: 'dort mille ans, éveillé sept jours'},
    {pokemon: 'Mushana', ensemble: 'obligatoire', raison: 'sans cesse assoupi'},
    {pokemon: 'Parecool', ensemble: 'obligatoire', raison: 'dort 20 heures par jour'},
    {pokemon: 'Ronflex', ensemble: 'obligatoire', raison: 'ses journées se résument aux repas et aux siestes'},
    {pokemon: 'Strassie', ensemble: 'obligatoire', raison: 'sommeille sous terre depuis son apparition'},
    {pokemon: 'Groudon', ensemble: 'acceptable', raison: 'long et profond sommeil après son combat'},
    {pokemon: 'Luxray', ensemble: 'acceptable', raison: 'dort beaucoup'},
    {pokemon: 'Makuhita', ensemble: 'acceptable', raison: 'dort beaucoup'},
    {pokemon: 'Mimantis', ensemble: 'acceptable', raison: 'passe son temps à flâner et à faire la sieste'},
    {pokemon: 'Necrozma', ensemble: 'acceptable', raison: 'longtemps endormi sous terre'},
    {pokemon: 'Snubbull', ensemble: 'acceptable', raison: 'dort 12 heures par jour : la moitié'},
    {pokemon: 'Xerneas', ensemble: 'acceptable', raison: '1 000 ans endormi'},
    {pokemon: 'Girafarig', ensemble: 'écarté', raison: 'une de ses têtes ne dort jamais'},
    {pokemon: 'Lamantine', ensemble: 'écarté', raison: 'vu endormi par un marin : une anecdote'},
    {pokemon: 'Okéoké', ensemble: 'écarté', raison: 'dort la nuit en groupe : une habitude'},
    {pokemon: 'Rondoudou', ensemble: 'écarté', raison: 'endort ses adversaires'},
    {pokemon: 'Zacian', ensemble: 'écarté', raison: 'le long sommeil est celui de Zamazenta'}
  ] AS classement
CALL () {
  MATCH (p:Pokemon)
  WHERE EXISTS {
    (p)-[:A_POUR_DESCRIPTION]->(d:Description)
    WHERE d.texte =~ '(?iU).*\\b(dort|dorment|dormir|dormant|endormi\\w*|s.endor\\w*|sommeil\\w*|somnol\\w*|sieste\\w*|assoupi\\w*)\\b.*'
      AND d.texte =~ '(?iU).*(\\bheures? par jour|\\bh par jour|toute? (la journée|sa vie|le temps)|sans cesse|continuellement|constamment|\\bbeaucoup\\b|\\bsouvent\\b|longtemps|\\bdepuis\\b|passe (son temps|sa vie|ses journées)|ne fait (que|pas grand-chose|rien)|à part manger|se résument|mille ans|millions d.années|\\d[\\d\\s]*ans\\b|long sommeil|profond sommeil|sommeil millénaire).*'
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
