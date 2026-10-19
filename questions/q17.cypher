// Q17 — Parmi les Pokémon de type Eau, lesquels sont décrits comme dangereux pour les humains ?
// (GraphRAG + filtre) Méthode des questions sémantiques (README). Filtre exact : la forme par défaut a le type
// Eau. Filet : « dangereux », « redouté » ou « redoutable », ou bien une cible humaine (gens, pêcheurs,
// marins, navires…) et un verbe d'agression dans la même description. Grille écrite avant le tri (2026-10-01) :
//   obligatoire : il attaque, noie, blesse ou menace des humains, ou il est dit dangereux pour eux ;
//   acceptable  : il est dangereux pour ce qui entoure les humains (bateaux, villes) ;
//   écarté      : danger pour ses seules proies ou ses adversaires, humains cités sans danger (sauvetage, jeu).
// Règle commune du 2026-10-01 (README) : un acceptable touche le cœur de la question, ici les humains ; une
// attaque « redoutable » contre ses adversaires n'y touche pas (Amphinobi, Crustabri, Poissirène et
// Tentacruel, d'abord acceptables, passent en écarté et restent dans la table comme pièges).
// Les raisons résument, sans recopier les descriptions (ADR-0001).
// Hors filet (horsFilet) : une espèce que le filet ne trouve pas, classée sur preuve, datée ; la requête la rend avec
// son ensemble, sans la chercher. Akwakwak (2026-10-19, pilote du jalon 3, choix de Julien) : acceptable, d'après des
// légendes, ceux qu'il noyait ne sont pas dits humains.
WITH [
    {pokemon: 'Carvanha', ensemble: 'obligatoire', raison: 'coule des navires ; les marins fuient ses eaux'},
    {pokemon: 'Hypocéan', ensemble: 'obligatoire', raison: 'pique les pêcheurs de coraux'},
    {pokemon: 'Kaiminus', ensemble: 'obligatoire', raison: 'sa morsure peut gravement blesser quelqu’un'},
    {pokemon: 'Léviator', ensemble: 'obligatoire', raison: 'brutal et dangereux, il rase des villes'},
    {pokemon: 'Moyade', ensemble: 'obligatoire', raison: 'aspire l’énergie vitale des marins'},
    {pokemon: 'Tentacool', ensemble: 'obligatoire', raison: 'arrose d’acide les pêcheurs'},
    {pokemon: 'Akwakwak', ensemble: 'acceptable', raison: 'noyait, selon des légendes, ceux qui souillaient sa rivière',
      horsFilet: true},
    {pokemon: 'Gamblast', ensemble: 'acceptable', raison: 'peut couler un navire-citerne'},
    {pokemon: 'Sharpedo', ensemble: 'acceptable', raison: 'attaque tous les navires sur son territoire'},
    {pokemon: 'Amphinobi', ensemble: 'écarté', raison: 'shuriken redoutables contre ses adversaires'},
    {pokemon: 'Crustabri', ensemble: 'écarté', raison: 'dards redoutables contre ses adversaires'},
    {pokemon: 'Mustéflott', ensemble: 'écarté', raison: 'sauve les gens qui se noient'},
    {pokemon: 'Poissirène', ensemble: 'écarté', raison: 'coups de corne redoutables contre ses adversaires'},
    {pokemon: 'Qwilfish', ensemble: 'écarté', raison: 'aucun danger pour les humains dit'},
    {pokemon: 'Sovkipou', ensemble: 'écarté', raison: 'aucun danger pour les humains dit'},
    {pokemon: 'Tentacruel', ensemble: 'écarté', raison: 'filet venimeux redoutable contre ses adversaires'},
    {pokemon: 'Wailmer', ensemble: 'écarté', raison: 'effraie les gens pour jouer'}
  ] AS classement
CALL () {
  MATCH (p:Pokemon)
  WHERE EXISTS { (p)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)-[:A_LE_TYPE]->(:Type {nom: 'Eau'}) }
    AND EXISTS {
      (p)-[:A_POUR_DESCRIPTION]->(d:Description)
      WHERE d.texte =~ '(?iU).*\\b(dangereu\\w*|redouté\\w*|redoutable\\w*)\\b.*'
        OR (d.texte =~ '(?iU).*\\b(humains?|hommes?|gens|enfants?|pêcheurs?|nageurs?|baigneurs?|marins|bateaux?|navires?|navire-citerne)\\b.*'
          AND d.texte =~ '(?iU).*\\b(attaqu\\w*|coul(e|ent|er|é|ée|és|ées)|bless\\w*|tu(e|ent|er|é)|noi(e|ent)|noy(er|é|ée|és|ées|ade)|piqu\\w*|arros\\w*|aspir\\w*|mord\\w*|englout\\w*|ras(e|ent|er|é|ée|és|ées)|détrui\\w*|effray\\w*)\\b.*')
    }
  RETURN collect(p.nom) AS trouves
}
UNWIND trouves + [c IN classement WHERE NOT c.pokemon IN trouves | c.pokemon] AS nom
WITH nom, nom IN trouves AS trouve, [c IN classement WHERE c.pokemon = nom][0] AS c
RETURN nom AS pokemon,
  CASE WHEN NOT trouve AND NOT coalesce(c.horsFilet, false) THEN 'plus trouvée' WHEN c IS NULL THEN 'à classer'
    ELSE c.ensemble END AS ensemble,
  coalesce(c.raison, '') AS raison
ORDER BY CASE ensemble
    WHEN 'obligatoire' THEN 1 WHEN 'acceptable' THEN 2 WHEN 'écarté' THEN 3 WHEN 'à classer' THEN 4 ELSE 5
  END, pokemon;
