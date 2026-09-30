// Formes (spec 001, T4.4) : 1 351 formes reliées à leur Pokémon, avec leur nom, leurs 6 stats et leurs types.
//
// La forme porte ce qui varie (ADR-0004) : chaque Pokémon a une forme par défaut (1 025), les 326 autres sont
// ses variantes (Méga, Gigamax, formes régionales…). Les formes cosmétiques de pokemon_forms (les 28 motifs
// de Zarbi) ne deviennent pas des nœuds (ARCHITECTURE § 8). Idempotent : MERGE sur id (contrainte forme_id)
// ou sur une relation entre nœuds déjà trouvés, puis SET ; une relance ne crée rien.

// Les 1 351 formes, chacune reliée à son Pokémon ; parDefaut repère la forme par défaut.
LOAD CSV WITH HEADERS FROM $base + '/pokemon.csv' AS ligne
MATCH (p:Pokemon {id: toInteger(ligne.species_id)})
MERGE (f:Forme {id: toInteger(ligne.id)})
SET f.identifiantPokeapi = ligne.identifier, f.parDefaut = (ligne.is_default = '1')
MERGE (f)-[:FORME_DE]->(p);

// Forme par défaut, déduite du graphe : la relation spécialisée (ADR-0005) et le nom du Pokémon (« Zarbi »,
// pas le motif « Zarbi A » ; règle de Julien du 2026-10-01).
MATCH (f:Forme {parDefaut: true})-[:FORME_DE]->(p:Pokemon)
MERGE (p)-[:A_POUR_FORME_PAR_DEFAUT]->(f)
SET f.nom = p.nom;

// Formes alternatives : le nom français de leur pokemon_form par défaut, sinon de l'unique (8 formes de
// Koraidon et Miraidon n'ont qu'une pokemon_form, marquée non par défaut). Jointure en mémoire des deux CSV :
// la pokemon_form retenue pour chaque forme, puis les noms français qui la citent. Deux noms restent en
// double, hérités des données (« Zygarde Forme 10 % », « Méga-Mistigrix ») : verifier.sh les attend.
LOAD CSV WITH HEADERS FROM $base + '/pokemon_forms.csv' AS ligne
WITH toInteger(ligne.pokemon_id) AS forme, collect(ligne) AS candidates
WITH forme, coalesce([c IN candidates WHERE c.is_default = '1'][0],
    CASE WHEN size(candidates) = 1 THEN candidates[0] END) AS retenue
WITH collect({forme: forme, pokemonForme: retenue.id}) AS choix
LOAD CSV WITH HEADERS FROM $base + '/pokemon_form_names.csv' AS ligne
WITH choix, ligne
WHERE ligne.local_language_id = '5'
UNWIND [c IN choix WHERE c.pokemonForme = ligne.pokemon_form_id] AS c
MATCH (f:Forme {id: c.forme, parDefaut: false})
SET f.nom = ligne.pokemon_name;

// Les 6 stats de base, pivotées en propriétés (une ligne de pokemon_stats par forme et par stat). Clé de
// propriété dynamique, calculée par un CASE : un stat_id inattendu donne une clé nulle, que SET refuse.
LOAD CSV WITH HEADERS FROM $base + '/pokemon_stats.csv' AS ligne
MATCH (f:Forme {id: toInteger(ligne.pokemon_id)})
WITH f, ligne,
  CASE ligne.stat_id
    WHEN '1' THEN 'statPv'
    WHEN '2' THEN 'statAttaque'
    WHEN '3' THEN 'statDefense'
    WHEN '4' THEN 'statAttaqueSpeciale'
    WHEN '5' THEN 'statDefenseSpeciale'
    WHEN '6' THEN 'statVitesse'
  END AS cle
SET f[cle] = toInteger(ligne.base_stat);

// Types de chaque forme, avec leur rang (slot : 1 = type principal, 2 = second type).
LOAD CSV WITH HEADERS FROM $base + '/pokemon_types.csv' AS ligne
MATCH (f:Forme {id: toInteger(ligne.pokemon_id)})
MATCH (t:Type {id: toInteger(ligne.type_id)})
MERGE (f)-[r:A_LE_TYPE]->(t)
SET r.rang = toInteger(ligne.slot);
