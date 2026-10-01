// Q9 — Quels Pokémon vivent dans les profondeurs de l'océan, et de quels types sont-ils ? (GraphRAG + graphe)
// Méthode des questions sémantiques (README). Filet : une description qui parle de profondeur et de mer.
// Grille écrite avant le tri (2026-10-01) :
//   obligatoire : il vit, habite ou se trouve dans les profondeurs de la mer ou de l'océan, au fond des mers,
//                 dans les abysses ;
//   acceptable  : il vit en mer et descend en profondeur (chasser, s'y cacher) sans y habiter, ou y vivait
//                 autrefois (fossile) ;
//   écarté      : eaux peu profondes, profondeur hors de la mer, origine plutôt qu'habitat, autre sens.
// Types de la forme par défaut (exacts). Les raisons résument, sans recopier les descriptions (ADR-0001).
WITH [
    {pokemon: 'Aquali', ensemble: 'obligatoire', raison: 'peut vivre dans les fonds marins'},
    {pokemon: 'Crustabri', ensemble: 'obligatoire', raison: 'se déplace dans les fonds marins'},
    {pokemon: 'Hyporoi', ensemble: 'obligatoire', raison: 'vit au fin fond des profondeurs océaniques'},
    {pokemon: 'Kokiyas', ensemble: 'obligatoire', raison: 'dort dans le sable des fonds marins'},
    {pokemon: 'Kyogre', ensemble: 'obligatoire', raison: 'somnolait dans une fosse marine'},
    {pokemon: 'Lanturn', ensemble: 'obligatoire', raison: 'Pokémon des abysses'},
    {pokemon: 'Loupio', ensemble: 'obligatoire', raison: 'vit dans les profondeurs marines'},
    {pokemon: 'Lugia', ensemble: 'obligatoire', raison: 'vit dans les profondeurs océaniques'},
    {pokemon: 'Luminéon', ensemble: 'obligatoire', raison: 'vit tout au fond de l’océan'},
    {pokemon: 'Mamanbo', ensemble: 'obligatoire', raison: 'dérive dans les courants océaniques profonds'},
    {pokemon: 'Prédastérie', ensemble: 'obligatoire', raison: 'arpente le fond des océans'},
    {pokemon: 'Relicanth', ensemble: 'obligatoire', raison: 'découvert dans les abysses'},
    {pokemon: 'Rosabyss', ensemble: 'obligatoire', raison: 'vit dans les profondeurs des mers du sud'},
    {pokemon: 'Sarmuraï', ensemble: 'obligatoire', raison: 'vit au fond de l’océan'},
    {pokemon: 'Serpang', ensemble: 'obligatoire', raison: 'habite dans les profondeurs de l’océan'},
    {pokemon: 'Sovkipou', ensemble: 'obligatoire', raison: 'vit dans les fonds marins'},
    {pokemon: 'Stari', ensemble: 'obligatoire', raison: 'vit au fond de la mer'},
    {pokemon: 'Vacilys', ensemble: 'obligatoire', raison: 'erre dans les profondeurs de l’océan'},
    {pokemon: 'Venalgue', ensemble: 'obligatoire', raison: 'reste tapi au fond des océans'},
    {pokemon: 'Vorastérie', ensemble: 'obligatoire', raison: 'rampe le long des fonds marins'},
    {pokemon: 'Amonita', ensemble: 'acceptable', raison: 'vivait dans les profondeurs marines : un fossile'},
    {pokemon: 'Kabutops', ensemble: 'acceptable', raison: 'plongeait dans les profondeurs pour chasser'},
    {pokemon: 'Lilia', ensemble: 'acceptable', raison: 'vivait au fond de la mer : un fossile'},
    {pokemon: 'Moyade', ensemble: 'acceptable', raison: 'entraîne ses proies dans les abysses'},
    {pokemon: 'Viskuse', ensemble: 'acceptable', raison: 'entraîne ses proies à plus de 8 000 m'},
    {pokemon: 'Écayon', ensemble: 'acceptable', raison: 'se retire dans les abysses la nuit'},
    {pokemon: 'Concombaffe', ensemble: 'écarté', raison: 'eaux peu profondes'},
    {pokemon: 'Lovdisc', ensemble: 'écarté', raison: 'mers peu profondes'},
    {pokemon: 'Sinistrail', ensemble: 'écarté', raison: 'né d’algues du fond de l’océan : une origine'},
    {pokemon: 'Tadmorv', ensemble: 'écarté', raison: 'né de la vase des fonds marins : une origine'}
  ] AS classement
CALL () {
  MATCH (p:Pokemon)
  WHERE EXISTS {
    (p)-[:A_POUR_DESCRIPTION]->(d:Description)
    WHERE d.texte =~ '(?iU).*\\b(profond\\w*|abyss\\w*|fosses?|grands fonds|fonds marins|fond (de la mer|de l.océan|des mers|des océans|de l.eau|des eaux))\\b.*'
      AND d.texte =~ '(?iU).*\\b(mers?|océans?|océaniques?|marins?|marines?|sous-marin\\w*|abyss\\w*)\\b.*'
  }
  RETURN collect(p.nom) AS trouves
}
UNWIND trouves + [c IN classement WHERE NOT c.pokemon IN trouves | c.pokemon] AS nom
WITH nom, nom IN trouves AS trouve, [c IN classement WHERE c.pokemon = nom][0] AS c
OPTIONAL MATCH (:Pokemon {nom: nom})-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
RETURN nom AS pokemon,
  CASE WHEN NOT trouve THEN 'plus trouvée' WHEN c IS NULL THEN 'à classer' ELSE c.ensemble END AS ensemble,
  COLLECT { MATCH (f)-[r:A_LE_TYPE]->(t:Type) RETURN t.nom ORDER BY r.rang } AS types,
  coalesce(c.raison, '') AS raison
ORDER BY CASE ensemble
    WHEN 'obligatoire' THEN 1 WHEN 'acceptable' THEN 2 WHEN 'écarté' THEN 3 WHEN 'à classer' THEN 4 ELSE 5
  END, pokemon;
