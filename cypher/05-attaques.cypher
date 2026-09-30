// Attaques (spec 001, T5.1) : 919 attaques et leur type, puis 99 509 relations APPREND agrégées depuis les
// 638 321 lignes de pokemon_moves.
//
// Idempotent : MERGE sur id (contrainte attaque_id) ou sur une relation entre nœuds déjà trouvés, puis SET ;
// APPREND agrège par union et par minimum, qui ne dépendent ni de l'ordre des lignes ni d'une relance (plan D3).

// Les attaques et leur type. Les 18 attaques Obscur (type 10002) tombent d'elles-mêmes : ce type n'est pas
// dans le graphe, le MATCH les écarte (aucun Pokémon ne les apprend). Catégorie en français (statut, physique,
// spéciale), jointe en mémoire. Puissance ou précision vide : toInteger('') rend null, SET n'écrit rien, la
// propriété reste absente.
LOAD CSV WITH HEADERS FROM $base + '/move_damage_class_prose.csv' AS ligne
WITH ligne
WHERE ligne.local_language_id = '5'
WITH collect({id: ligne.move_damage_class_id, nom: ligne.name}) AS categories
LOAD CSV WITH HEADERS FROM $base + '/moves.csv' AS ligne
MATCH (t:Type {id: toInteger(ligne.type_id)})
MERGE (a:Attaque {id: toInteger(ligne.id)})
SET a.identifiantPokeapi = ligne.identifier,
  a.puissance = toInteger(ligne.power),
  a.precision = toInteger(ligne.accuracy),
  a.pp = toInteger(ligne.pp),
  a.categorie = [c IN categories WHERE c.id = ligne.damage_class_id | c.nom][0]
MERGE (a)-[:A_LE_TYPE]->(t);

// Leur nom en français (langue 5). 18 noms restent en double, hérités des données : les attaques Z
// génériques, en variante physique et spéciale (gardées, décision de Julien le 2026-10-01).
LOAD CSV WITH HEADERS FROM $base + '/move_names.csv' AS ligne
WITH ligne
WHERE ligne.local_language_id = '5'
MATCH (a:Attaque {id: toInteger(ligne.move_id)})
SET a.nom = ligne.name;

// APPREND, agrégé par couple (forme, attaque) : methodes = union des méthodes en français (repli sur
// l'identifiant pour « train », sans nom français) ; niveau = le plus petit niveau de montée de niveau, tous
// jeux confondus (0 : appris à l'évolution), absent si l'attaque ne s'apprend pas ainsi. Lots de 5 000 lignes
// (plan D3) : chaque lot valide ses écritures ; après une coupure, une relance complète sans rien doubler.
LOAD CSV WITH HEADERS FROM $base + '/pokemon_move_methods.csv' AS ligne
WITH collect({id: ligne.id, identifiant: ligne.identifier}) AS identifiants
LOAD CSV WITH HEADERS FROM $base + '/pokemon_move_method_prose.csv' AS ligne
WITH identifiants,
  collect(CASE WHEN ligne.local_language_id = '5'
    THEN {id: ligne.pokemon_move_method_id, nom: ligne.name} END) AS nomsFr
WITH [m IN identifiants |
  {id: m.id, nom: coalesce([n IN nomsFr WHERE n.id = m.id | n.nom][0], m.identifiant)}] AS methodes
LOAD CSV WITH HEADERS FROM $base + '/pokemon_moves.csv' AS ligne
CALL (ligne, methodes) {
  MATCH (f:Forme {id: toInteger(ligne.pokemon_id)})
  MATCH (a:Attaque {id: toInteger(ligne.move_id)})
  WITH f, a, [m IN methodes WHERE m.id = ligne.pokemon_move_method_id | m.nom][0] AS methode,
    CASE WHEN ligne.pokemon_move_method_id = '1' THEN toInteger(ligne.level) END AS niveau
  MERGE (f)-[r:APPREND]->(a)
  SET r.methodes = CASE
      WHEN methode IN coalesce(r.methodes, []) THEN r.methodes
      ELSE coalesce(r.methodes, []) + methode
    END,
    r.niveau = CASE
      WHEN niveau IS NULL THEN r.niveau
      WHEN r.niveau IS NULL OR niveau < r.niveau THEN niveau
      ELSE r.niveau
    END
} IN TRANSACTIONS OF 5000 ROWS;
