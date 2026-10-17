// Ce que la fiche de schéma affirme, vérifié sur la base (spec 002, T7.3 ; plan D5), en lecture seule. Lancé par
// scripts/questions.sh --exemples, avant les exemples. Chaque requête rend une ligne « affirmation|attendu|obtenu »,
// et un attendu vide est une information, sans verdict.
//
// La fiche (questions/fiche-schema.md) est la seule source de schéma des agents des jalons 2 à 4 : une valeur fausse
// fausserait toutes les techniques. Chaque requête cite, en commentaire « // fiche : « … » », la phrase exacte de la
// fiche qu'elle prouve ; les valeurs de la fiche y sont recopiées dans l'ordre de la fiche (valeurFiche,
// nombreFiche). banc/tests/test_fiche_cypher.py vérifie, sans base, que chaque phrase citée figure dans la fiche, que
// les valeurs recopiées sont les siennes et que chaque ligne des sections Nœuds et Valeurs possibles est citée.
// Listes comparées triées des deux côtés : seul l'ensemble compte.

// fiche : « ## Nœuds »
// Aucun label hors de la fiche : un label inconnu des agents serait un schéma caché.
CALL () {
  UNWIND ['Pokemon', 'Forme', 'Type', 'Attaque', 'Talent', 'Description'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN collect(valeurFiche) AS attendus
}
CALL () {
  MATCH (n)
  UNWIND labels(n) AS label
  WITH DISTINCT label ORDER BY label
  RETURN collect(label) AS obtenus
}
RETURN 'labels des nœuds|' + reduce(s = '', x IN attendus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x)
  + '|' + reduce(s = '', x IN obtenus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `Pokemon` : une espèce (1 025) ; propriétés `id`, `identifiantPokeapi`, `nom`, `categorie`. »
CALL () {
  UNWIND ['id', 'identifiantPokeapi', 'nom', 'categorie'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN 1025 AS nombreFiche, collect(valeurFiche) AS attendues
}
CALL () {
  MATCH (n:Pokemon)
  RETURN count(n) AS noeuds
}
CALL () {
  MATCH (n:Pokemon)
  UNWIND keys(n) AS cle
  WITH DISTINCT cle ORDER BY cle
  RETURN collect(cle) AS obtenues
}
RETURN 'Pokemon : nœuds ; propriétés|' + toString(nombreFiche) + ' ; '
  + reduce(s = '', x IN attendues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + '|' + toString(noeuds) + ' ; '
  + reduce(s = '', x IN obtenues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `Forme` : une forme d'une espèce (1 351), sa forme par défaut ou l'une de ses variantes ; c'est la forme qui porte les types, les statistiques, les talents et les attaques. Propriétés `id`, `identifiantPokeapi`, `nom`, `parDefaut`, `statPv`, `statAttaque`, `statDefense`, `statAttaqueSpeciale`, `statDefenseSpeciale`, `statVitesse`. »
CALL () {
  UNWIND ['id', 'identifiantPokeapi', 'nom', 'parDefaut', 'statPv', 'statAttaque', 'statDefense',
    'statAttaqueSpeciale', 'statDefenseSpeciale', 'statVitesse'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN 1351 AS nombreFiche, collect(valeurFiche) AS attendues
}
CALL () {
  MATCH (n:Forme)
  RETURN count(n) AS noeuds
}
CALL () {
  MATCH (n:Forme)
  UNWIND keys(n) AS cle
  WITH DISTINCT cle ORDER BY cle
  RETURN collect(cle) AS obtenues
}
RETURN 'Forme : nœuds ; propriétés|' + toString(nombreFiche) + ' ; '
  + reduce(s = '', x IN attendues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + '|' + toString(noeuds) + ' ; '
  + reduce(s = '', x IN obtenues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `Type` : un type (18) ; propriétés `id`, `identifiantPokeapi`, `nom`. »
CALL () {
  UNWIND ['id', 'identifiantPokeapi', 'nom'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN 18 AS nombreFiche, collect(valeurFiche) AS attendues
}
CALL () {
  MATCH (n:Type)
  RETURN count(n) AS noeuds
}
CALL () {
  MATCH (n:Type)
  UNWIND keys(n) AS cle
  WITH DISTINCT cle ORDER BY cle
  RETURN collect(cle) AS obtenues
}
RETURN 'Type : nœuds ; propriétés|' + toString(nombreFiche) + ' ; '
  + reduce(s = '', x IN attendues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + '|' + toString(noeuds) + ' ; '
  + reduce(s = '', x IN obtenues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `Attaque` : une attaque (919) ; propriétés `id`, `identifiantPokeapi`, `nom`, `puissance`, `precision`, `pp`, `categorie`. »
CALL () {
  UNWIND ['id', 'identifiantPokeapi', 'nom', 'puissance', 'precision', 'pp', 'categorie'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN 919 AS nombreFiche, collect(valeurFiche) AS attendues
}
CALL () {
  MATCH (n:Attaque)
  RETURN count(n) AS noeuds
}
CALL () {
  MATCH (n:Attaque)
  UNWIND keys(n) AS cle
  WITH DISTINCT cle ORDER BY cle
  RETURN collect(cle) AS obtenues
}
RETURN 'Attaque : nœuds ; propriétés|' + toString(nombreFiche) + ' ; '
  + reduce(s = '', x IN attendues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + '|' + toString(noeuds) + ' ; '
  + reduce(s = '', x IN obtenues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `Talent` : un talent (313) ; propriétés `id`, `identifiantPokeapi`, `nom`. »
CALL () {
  UNWIND ['id', 'identifiantPokeapi', 'nom'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN 313 AS nombreFiche, collect(valeurFiche) AS attendues
}
CALL () {
  MATCH (n:Talent)
  RETURN count(n) AS noeuds
}
CALL () {
  MATCH (n:Talent)
  UNWIND keys(n) AS cle
  WITH DISTINCT cle ORDER BY cle
  RETURN collect(cle) AS obtenues
}
RETURN 'Talent : nœuds ; propriétés|' + toString(nombreFiche) + ' ; '
  + reduce(s = '', x IN attendues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + '|' + toString(noeuds) + ' ; '
  + reduce(s = '', x IN obtenues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `Description` : un texte de description d'une espèce (5 233) ; propriétés `texte` et `jeux`, les jeux où il paraît ; `embedding`, le vecteur de son texte (voir les règles). »
// `embedding` ajouté le 2026-10-17 (spec 003, T6.1 ; plan D8) : le vecteur qu'écrit cypher/07-embeddings.cypher.
CALL () {
  UNWIND ['texte', 'jeux', 'embedding'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN 5233 AS nombreFiche, collect(valeurFiche) AS attendues
}
CALL () {
  MATCH (n:Description)
  RETURN count(n) AS noeuds
}
CALL () {
  MATCH (n:Description)
  UNWIND keys(n) AS cle
  WITH DISTINCT cle ORDER BY cle
  RETURN collect(cle) AS obtenues
}
RETURN 'Description : nœuds ; propriétés|' + toString(nombreFiche) + ' ; '
  + reduce(s = '', x IN attendues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + '|' + toString(noeuds) + ' ; '
  + reduce(s = '', x IN obtenues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `identifiantPokeapi` est l'identifiant anglais de PokéAPI (`gengar` pour l'espèce Ectoplasma). »
MATCH (p:Pokemon {identifiantPokeapi: 'gengar'})
WITH collect(p.nom) AS noms
RETURN 'Pokemon.identifiantPokeapi gengar|Ectoplasma|'
  + reduce(s = '', x IN noms | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « La forme par défaut porte le nom de son espèce. »
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
WITH count(*) AS paires, count(CASE WHEN f.nom <> p.nom THEN 1 END) AS autres
RETURN 'forme par défaut au nom de son espèce : paires, noms différents|1025, 0|' + toString(paires) + ', '
  + toString(autres) AS ligne;

// fiche : « ## Relations »
// Chaque motif (label de départ, type, label d'arrivée, propriétés portées) : la fiche les donne tous, aucun autre.
// Les trois relations d'efficacité, écrites en une ligne par la fiche, sont ici séparées. Un identifiant par
// littéral, et le motif recomposé ici, clés triées comme celles de la base : la traduction anglaise (banc traduire,
// spec 002 D8) traduit un littéral qui est en entier un identifiant, jamais un morceau de texte.
CALL () {
  UNWIND [
    ['Pokemon', 'A_POUR_FORME_PAR_DEFAUT', 'Forme'],
    ['Forme', 'FORME_DE', 'Pokemon'],
    ['Pokemon', 'EVOLUE_EN', 'Pokemon'],
    ['Forme', 'A_LE_TYPE', 'Type', 'rang'],
    ['Attaque', 'A_LE_TYPE', 'Type'],
    ['Type', 'SUPER_EFFICACE_CONTRE', 'Type', 'facteur'],
    ['Type', 'PEU_EFFICACE_CONTRE', 'Type', 'facteur'],
    ['Type', 'SANS_EFFET_CONTRE', 'Type', 'facteur'],
    ['Forme', 'A_LE_TALENT', 'Talent', 'cache'],
    ['Forme', 'APPREND', 'Attaque', 'methodes', 'niveau'],
    ['Pokemon', 'A_POUR_DESCRIPTION', 'Description']
  ] AS valeurFiche
  WITH valeurFiche, COLLECT { UNWIND valeurFiche[3..] AS cle RETURN cle ORDER BY cle } AS cles
  WITH '(:' + valeurFiche[0] + ')-[:' + valeurFiche[1]
    + CASE WHEN cles = [] THEN '' ELSE ' {' + reduce(s = '', x IN cles | s + CASE s WHEN '' THEN '' ELSE ', ' END + x)
    + '}' END + ']->(:' + valeurFiche[2] + ')' AS motif
  ORDER BY motif
  RETURN collect(motif) AS attendus
}
CALL () {
  MATCH (a)-[r]->(b)
  WITH labels(a) AS de, type(r) AS t, labels(b) AS vers, collect(DISTINCT keys(r)) AS jeux
  CALL (jeux) {
    UNWIND jeux AS jeu
    UNWIND jeu AS cle
    WITH DISTINCT cle ORDER BY cle
    RETURN collect(cle) AS cles
  }
  WITH '(:' + reduce(s = '', x IN de | s + CASE s WHEN '' THEN '' ELSE ':' END + x) + ')-[:' + t
    + CASE WHEN cles = [] THEN '' ELSE ' {' + reduce(s = '', x IN cles | s + CASE s WHEN '' THEN '' ELSE ', ' END + x)
    + '}' END + ']->(:' + reduce(s = '', x IN vers | s + CASE s WHEN '' THEN '' ELSE ':' END + x) + ')' AS motif
  ORDER BY motif
  RETURN collect(motif) AS obtenus
}
RETURN 'motifs des relations|' + reduce(s = '', x IN attendus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x)
  + '|' + reduce(s = '', x IN obtenus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « **Un Pokémon est une espèce, prise dans sa forme par défaut** (`A_POUR_FORME_PAR_DEFAUT`). »
CALL () {
  MATCH (p:Pokemon)
  RETURN count(p) AS especes,
    count(CASE WHEN COUNT { (p)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme) } <> 1 THEN 1 END) AS sansUneSeule
}
CALL () {
  MATCH (:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
  RETURN count(CASE WHEN coalesce(f.parDefaut, false) <> true THEN 1 END) AS nonMarquees
}
RETURN 'espèces : nombre, sans exactement une forme par défaut, forme par défaut sans parDefaut vrai|1025, 0, 0|'
  + toString(especes) + ', ' + toString(sansUneSeule) + ', ' + toString(nonMarquees) AS ligne;

// fiche : « `niveau` est le plus petit niveau d'apprentissage par montée de niveau, tous jeux confondus (0 : appris en évoluant), et manque si l'attaque ne s'apprend pas ainsi. »
MATCH (:Forme)-[r:APPREND]->(:Attaque)
WITH count(CASE WHEN (r.niveau IS NOT NULL) <> ('Montée de niveau' IN r.methodes) THEN 1 END) AS ecarts,
  count(CASE WHEN r.niveau = 0 THEN 1 END) AS auNiveau0
RETURN 'APPREND : niveau présent sans « Montée de niveau » ou absent avec, niveau 0 présent|0, oui|'
  + toString(ecarts) + ', ' + CASE WHEN auNiveau0 > 0 THEN 'oui' ELSE 'non' END AS ligne;

// fiche : « **Efficacité** : seules les relations non neutres existent. »
MATCH (:Type)-[e:SUPER_EFFICACE_CONTRE|PEU_EFFICACE_CONTRE|SANS_EFFET_CONTRE]->(:Type)
WITH count(e) AS relations, count(CASE WHEN e.facteur = 1.0 THEN 1 END) AS neutres
RETURN 'efficacité : relations, dont neutres (×1)|120, 0|' + toString(relations) + ', ' + toString(neutres) AS ligne;

// fiche : « sur un `Pokemon`, sa catégorie d'espèce (« Pokémon Ombre »), écrite sans le mot « Pokémon » pour les 120 espèces de la 9e génération (« Chat Plante ») »
// 9e génération : espèces 906 à 1025 de PokéAPI (plan 001).
MATCH (p:Pokemon)
WITH count(CASE WHEN NOT p.categorie STARTS WITH 'Pokémon ' THEN 1 END) AS sansLeMot,
  min(CASE WHEN NOT p.categorie STARTS WITH 'Pokémon ' THEN p.id END) AS premiere,
  max(CASE WHEN NOT p.categorie STARTS WITH 'Pokémon ' THEN p.id END) AS derniere,
  count(CASE WHEN p.categorie = 'Pokémon Ombre' THEN 1 END) AS ombre,
  count(CASE WHEN p.categorie = 'Chat Plante' THEN 1 END) AS chat
RETURN 'Pokemon.categorie : sans « Pokémon » (nombre, première et dernière espèce), Pokémon Ombre et Chat Plante présents|120, 906, 1025, oui, oui|'
  + toString(sansLeMot) + ', ' + coalesce(toString(premiere), '-') + ', ' + coalesce(toString(derniere), '-') + ', '
  + CASE WHEN ombre > 0 THEN 'oui' ELSE 'non' END + ', ' + CASE WHEN chat > 0 THEN 'oui' ELSE 'non' END AS ligne;

// fiche : « 62 noms portent l'apostrophe typographique ’ (« Écras’Face ») et 2 l'apostrophe droite ' »
MATCH (n)
WHERE n.nom IS NOT NULL
WITH count(CASE WHEN n.nom CONTAINS '’' THEN 1 END) AS typographique,
  count(CASE WHEN n.nom = 'Écras’Face' THEN 1 END) AS exemple, count(CASE WHEN n.nom CONTAINS "'" THEN 1 END) AS droite
RETURN 'noms à l’apostrophe typographique ’ (nombre, Écras’Face présent), à l’apostrophe droite|62, oui, 2|'
  + toString(typographique) + ', ' + CASE WHEN exemple > 0 THEN 'oui' ELSE 'non' END + ', ' + toString(droite) AS ligne;

// fiche : « Quelques noms désignent deux nœuds (les 18 attaques Z génériques, en variante physique et spéciale ; le talent « Osmose Équine » ; deux noms de formes) : `id` les distingue. »
CALL () {
  MATCH (a:Attaque)
  WITH a.nom AS nom, collect(a.categorie) AS categories
  WHERE size(categories) > 1
  RETURN count(*) AS attaques,
    count(CASE WHEN size(categories) = 2 AND 'physique' IN categories AND 'spéciale' IN categories THEN 1 END)
      AS physiqueEtSpeciale
}
CALL () {
  MATCH (t:Talent)
  WITH t.nom AS nom, count(*) AS noeuds
  WHERE noeuds > 1
  WITH nom, noeuds ORDER BY nom
  RETURN collect(nom + ' ×' + toString(noeuds)) AS talents
}
CALL () {
  MATCH (f:Forme)
  WITH f.nom AS nom, count(*) AS noeuds
  WHERE noeuds > 1
  RETURN count(*) AS formes, count(CASE WHEN noeuds = 2 THEN 1 END) AS formesParDeux
}
RETURN 'noms en double : attaques (dont en physique et spéciale), talents, formes (dont par deux)|18 (18), Osmose Équine ×2, 2 (2)|'
  + toString(attaques) + ' (' + toString(physiqueEtSpeciale) + '), '
  + reduce(s = '', x IN talents | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + ', '
  + toString(formes) + ' (' + toString(formesParDeux) + ')' AS ligne;

// fiche : « **Propriétés absentes** : une attaque sans puissance fixe (attaque de statut, puissance variable) ou sans précision n'a pas la propriété, sauf 18 attaques récentes, qui portent 0 à la place (17 puissances et 3 précisions). »
// Le CSV de PokéAPI au commit figé écrit 0 pour ces 18 attaques (identifiants 829 à 913), chargées telles quelles.
MATCH (a:Attaque)
WITH count(CASE WHEN a.puissance = 0 THEN 1 END) AS puissances, count(CASE WHEN a.precision = 0 THEN 1 END) AS precisions,
  count(CASE WHEN a.puissance = 0 OR a.precision = 0 THEN 1 END) AS attaques,
  count(CASE WHEN a.categorie = 'statut' AND a.puissance <> 0 THEN 1 END) AS statutAvecPuissance
RETURN 'attaques à 0 : puissances, précisions, attaques ; de statut avec une autre puissance que 0|17, 3, 18 ; 0|'
  + toString(puissances) + ', ' + toString(precisions) + ', ' + toString(attaques) + ' ; '
  + toString(statutAvecPuissance) AS ligne;

// fiche : « `Type.nom` : Acier, Combat, Dragon, Eau, Électrik, Fée, Feu, Glace, Insecte, Normal, Plante, Poison, Psy, Roche, Sol, Spectre, Ténèbres, Vol. »
CALL () {
  UNWIND ['Acier', 'Combat', 'Dragon', 'Eau', 'Électrik', 'Fée', 'Feu', 'Glace', 'Insecte', 'Normal', 'Plante',
    'Poison', 'Psy', 'Roche', 'Sol', 'Spectre', 'Ténèbres', 'Vol'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN collect(valeurFiche) AS attendus
}
CALL () {
  MATCH (t:Type)
  WITH t.nom AS nom ORDER BY nom
  RETURN collect(nom) AS obtenus
}
RETURN 'Type.nom|' + reduce(s = '', x IN attendus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x)
  + '|' + reduce(s = '', x IN obtenus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `Attaque.categorie` : physique, spéciale, statut. »
CALL () {
  UNWIND ['physique', 'spéciale', 'statut'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN collect(valeurFiche) AS attendues
}
CALL () {
  MATCH (a:Attaque)
  WITH DISTINCT a.categorie AS categorie ORDER BY categorie
  RETURN collect(categorie) AS obtenues
}
RETURN 'Attaque.categorie|' + reduce(s = '', x IN attendues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x)
  + '|' + reduce(s = '', x IN obtenues | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `APPREND.methodes` : « Montée de niveau », « Œuf », « Enseigné », « Capsule », « Changement de Forme », « train » (sans nom français), et 4 méthodes rares, propres à un jeu ou à un événement. »
// Nombre : les 6 méthodes nommées et les 4 rares.
CALL () {
  UNWIND ['Montée de niveau', 'Œuf', 'Enseigné', 'Capsule', 'Changement de Forme', 'train'] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN 10 AS nombreFiche, collect(valeurFiche) AS nommees
}
CALL () {
  MATCH (:Forme)-[r:APPREND]->(:Attaque)
  UNWIND r.methodes AS methode
  WITH DISTINCT methode ORDER BY methode
  RETURN collect(methode) AS toutes
}
RETURN 'APPREND.methodes : nombre ; méthodes nommées par la fiche|' + toString(nombreFiche) + ' ; '
  + reduce(s = '', x IN nommees | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + '|' + toString(size(toutes)) + ' ; '
  + reduce(s = '', x IN [m IN nommees WHERE m IN toutes] | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// Information : les méthodes rares, que la fiche ne nomme pas (certaines citent des entités du banc, plan D5).
MATCH (:Forme)-[r:APPREND]->(:Attaque)
UNWIND r.methodes AS methode
WITH methode, count(*) AS relations
WHERE NOT methode IN ['Montée de niveau', 'Œuf', 'Enseigné', 'Capsule', 'Changement de Forme', 'train']
WITH methode, relations ORDER BY relations DESC, methode
WITH collect(methode + ' (' + toString(relations) + ')') AS rares
RETURN 'méthodes rares (relations)||' + reduce(s = '', x IN rares | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `facteur` : 2.0 (`SUPER_EFFICACE_CONTRE`), 0.5 (`PEU_EFFICACE_CONTRE`), 0.0 (`SANS_EFFET_CONTRE`). »
CALL () {
  UNWIND [['SUPER_EFFICACE_CONTRE', 2.0], ['PEU_EFFICACE_CONTRE', 0.5], ['SANS_EFFET_CONTRE', 0.0]] AS valeurFiche
  WITH valeurFiche[0] + ' ' + toString(valeurFiche[1]) AS valeur ORDER BY valeur
  RETURN collect(valeur) AS attendus
}
CALL () {
  MATCH (:Type)-[e]->(:Type)
  WITH DISTINCT type(e) + ' ' + toString(e.facteur) AS valeur ORDER BY valeur
  RETURN collect(valeur) AS obtenus
}
CALL () {
  MATCH (:Type)-[e]->(:Type)
  WITH DISTINCT valueType(e.facteur) AS genre ORDER BY genre
  RETURN collect(genre) AS genres
}
RETURN 'facteur par type de relation ; type de valeur|'
  + reduce(s = '', x IN attendus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + ' ; FLOAT NOT NULL|'
  + reduce(s = '', x IN obtenus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + ' ; '
  + reduce(s = '', x IN genres | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `A_LE_TYPE.rang` : 1 ou 2. »
CALL () {
  UNWIND [1, 2] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN collect(toString(valeurFiche)) AS attendus
}
CALL () {
  MATCH (:Forme)-[r:A_LE_TYPE]->(:Type)
  WITH DISTINCT r.rang AS rang, valueType(r.rang) AS genre ORDER BY rang
  RETURN collect(coalesce(toString(rang), 'absent') + ' (' + genre + ')') AS obtenus
}
RETURN 'A_LE_TYPE.rang (type de valeur)|'
  + reduce(s = '', x IN attendus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x + ' (INTEGER NOT NULL)') + '|'
  + reduce(s = '', x IN obtenus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;

// fiche : « `A_LE_TALENT.cache` et `Forme.parDefaut` : vrai ou faux. »
// Des booléens, pas des textes : `{cache: true}` les trouve.
CALL () {
  UNWIND [true, false] AS valeurFiche
  WITH valeurFiche ORDER BY valeurFiche
  RETURN collect(toString(valeurFiche)) AS attendus
}
CALL () {
  MATCH (:Forme)-[r:A_LE_TALENT]->(:Talent)
  WITH DISTINCT r.cache AS valeur, valueType(r.cache) AS genre ORDER BY valeur
  RETURN collect(coalesce(toString(valeur), 'absent') + ' (' + genre + ')') AS caches
}
CALL () {
  MATCH (f:Forme)
  WITH DISTINCT f.parDefaut AS valeur, valueType(f.parDefaut) AS genre ORDER BY valeur
  RETURN collect(coalesce(toString(valeur), 'absent') + ' (' + genre + ')') AS parDefaut
}
WITH reduce(s = '', x IN attendus | s + CASE s WHEN '' THEN '' ELSE ', ' END + x + ' (BOOLEAN NOT NULL)') AS attendu,
  caches, parDefaut
RETURN 'A_LE_TALENT.cache ; Forme.parDefaut (type de valeur)|' + attendu + ' ; ' + attendu + '|'
  + reduce(s = '', x IN caches | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) + ' ; '
  + reduce(s = '', x IN parDefaut | s + CASE s WHEN '' THEN '' ELSE ', ' END + x) AS ligne;
