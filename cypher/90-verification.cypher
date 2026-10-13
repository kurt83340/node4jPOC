// Vérification du graphe (spec 001, plan D8), lancée par scripts/verifier.sh en lecture seule.
// Chaque ligne de résultat : « section|contrôle|attendu|obtenu » ; un attendu vide est une information.
//
// Valeurs attendues calculées le 2026-09-30 depuis les CSV du commit PokéAPI 168b1e8, par LOAD CSV en
// lecture seule, jamais depuis le graphe : un autre commit donne d'autres valeurs (ADR-0001).
// Noms en double hérités des données : 18 attaques Z génériques (variantes physique et spéciale d'un
// même nom), un talent (« Osmose Équine », variantes Blizzeval et Spectreval) et deux noms de formes
// (« Zygarde Forme 10 % », avec ou sans Rassemblement ; « Méga-Mistigrix », mâle et femelle).
// Empreintes (sommes des rangs, des stats, des tailles de listes) : elles changent si une relance fait
// grossir une liste sans changer les comptes.
// Chaque contrôle agrège dans un WITH sans clé : une base vide donne une ligne à 0, pas une ligne absente.

// Contraintes et index (ARCHITECTURE § 5) : unicité de id et index sur nom, pour 5 labels ; index plein texte.
SHOW CONSTRAINTS YIELD type, labelsOrTypes, properties
WHERE type = 'NODE_PROPERTY_UNIQUENESS' AND properties = ['id']
  AND labelsOrTypes[0] IN ['Attaque', 'Forme', 'Pokemon', 'Talent', 'Type']
WITH count(*) AS c
RETURN 'contraintes|unicité de id : Attaque, Forme, Pokemon, Talent, Type|5|' + toString(c) AS ligne;

SHOW INDEXES YIELD type, entityType, labelsOrTypes, properties, owningConstraint
WHERE type = 'RANGE' AND entityType = 'NODE' AND properties = ['nom'] AND owningConstraint IS NULL
  AND labelsOrTypes[0] IN ['Attaque', 'Forme', 'Pokemon', 'Talent', 'Type']
WITH count(*) AS c
RETURN 'contraintes|index sur nom : Attaque, Forme, Pokemon, Talent, Type|5|' + toString(c) AS ligne;

// Index plein texte (spec 002, D9) : sa définition seulement, lue par SHOW INDEXES ; qu'il trouve un nom approché
// se vérifie dans scripts/questions.sh --exemples (dracofeu~), pour qu'une base sans index rende un écart et non
// une erreur. Analyseur et état compris : IF NOT EXISTS garderait sans rien dire un index du même nom réglé autrement.
SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, options, state
WHERE name = 'noms_plein_texte' AND type = 'FULLTEXT' AND entityType = 'NODE' AND properties = ['nom']
  AND size(labelsOrTypes) = 5
  AND all(label IN labelsOrTypes WHERE label IN ['Attaque', 'Forme', 'Pokemon', 'Talent', 'Type'])
  AND options.indexConfig.`fulltext.analyzer` = 'standard-folding' AND state = 'ONLINE'
WITH count(*) AS c
RETURN 'contraintes|index plein texte noms_plein_texte sur nom (standard-folding, en ligne) : Attaque, Forme, Pokemon, Talent, Type|1|'
  + toString(c) AS ligne;

// Nœuds, relations par motif, empreintes, noms. $limiteNoeuds et $limiteRelations : limite réelle de
// l'instance, passée par verifier.sh.
CALL () {
  MATCH (n:Type)
  WITH count(n) AS c
  RETURN 'types' AS section, '(:Type)' AS controle, '18' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Type)-[r:SUPER_EFFICACE_CONTRE]->(:Type)
  WITH count(r) AS c
  RETURN 'types' AS section, '(:Type)-[:SUPER_EFFICACE_CONTRE]->(:Type)' AS controle, '51' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Type)-[r:PEU_EFFICACE_CONTRE]->(:Type)
  WITH count(r) AS c
  RETURN 'types' AS section, '(:Type)-[:PEU_EFFICACE_CONTRE]->(:Type)' AS controle, '61' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Type)-[r:SANS_EFFET_CONTRE]->(:Type)
  WITH count(r) AS c
  RETURN 'types' AS section, '(:Type)-[:SANS_EFFET_CONTRE]->(:Type)' AS controle, '8' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Type)-[r:SUPER_EFFICACE_CONTRE|PEU_EFFICACE_CONTRE|SANS_EFFET_CONTRE]->(:Type)
  WITH sum(r.facteur) AS s
  RETURN 'types' AS section, "somme des facteurs d'efficacité" AS controle, '132.5' AS attendu,
    toString(s) AS obtenu
  UNION ALL
  MATCH (n:Type)
  WITH count(n.nom) AS c, count(DISTINCT n.nom) AS d
  RETURN 'types' AS section, 'noms (renseignés, en double)' AS controle, '18, 0' AS attendu,
    toString(c) + ', ' + toString(c - d) AS obtenu
  UNION ALL
  MATCH (n:Pokemon)
  WITH count(n) AS c
  RETURN 'pokemon' AS section, '(:Pokemon)' AS controle, '1025' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Pokemon)-[r:EVOLUE_EN]->(:Pokemon)
  WITH count(r) AS c
  RETURN 'pokemon' AS section, '(:Pokemon)-[:EVOLUE_EN]->(:Pokemon)' AS controle, '484' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (n:Pokemon)
  WITH count(n.nom) AS c, count(DISTINCT n.nom) AS d
  RETURN 'pokemon' AS section, 'noms (renseignés, en double)' AS controle, '1025, 0' AS attendu,
    toString(c) + ', ' + toString(c - d) AS obtenu
  UNION ALL
  MATCH (n:Pokemon)
  WITH count(n.categorie) AS c
  RETURN 'pokemon' AS section, 'catégories renseignées' AS controle, '1025' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (n:Forme)
  WITH count(n) AS c
  RETURN 'formes' AS section, '(:Forme)' AS controle, '1351' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Forme)-[r:FORME_DE]->(:Pokemon)
  WITH count(r) AS c
  RETURN 'formes' AS section, '(:Forme)-[:FORME_DE]->(:Pokemon)' AS controle, '1351' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Pokemon)-[r:A_POUR_FORME_PAR_DEFAUT]->(:Forme)
  WITH count(r) AS c
  RETURN 'formes' AS section, '(:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(:Forme)' AS controle, '1025' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (n:Forme {parDefaut: true})
  WITH count(n) AS c
  RETURN 'formes' AS section, 'formes par défaut (parDefaut)' AS controle, '1025' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Forme)-[r:A_LE_TYPE]->(:Type)
  WITH count(r) AS c, sum(r.rang) AS s
  RETURN 'formes' AS section, '(:Forme)-[:A_LE_TYPE]->(:Type) (relations, somme des rangs)' AS controle, '2116, 2881' AS attendu,
    toString(c) + ', ' + toString(s) AS obtenu
  UNION ALL
  MATCH (n:Forme)
  WITH sum(n.statPv + n.statAttaque + n.statDefense + n.statAttaqueSpeciale
      + n.statDefenseSpeciale + n.statVitesse) AS s
  RETURN 'formes' AS section, 'somme des 6 stats de base' AS controle, '610867' AS attendu,
    toString(s) AS obtenu
  UNION ALL
  MATCH (n:Forme)
  WITH count(n.nom) AS c, count(DISTINCT n.nom) AS d
  RETURN 'formes' AS section, 'noms (renseignés, en double)' AS controle, '1351, 2' AS attendu,
    toString(c) + ', ' + toString(c - d) AS obtenu
  UNION ALL
  MATCH (n:Talent)
  WITH count(n) AS c
  RETURN 'talents' AS section, '(:Talent)' AS controle, '313' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Forme)-[r:A_LE_TALENT]->(:Talent)
  WITH count(r) AS c, count(CASE WHEN r.cache THEN 1 END) AS k
  RETURN 'talents' AS section, '(:Forme)-[:A_LE_TALENT]->(:Talent) (relations, cachés)' AS controle, '2943, 988' AS attendu,
    toString(c) + ', ' + toString(k) AS obtenu
  UNION ALL
  MATCH (n:Talent)
  WITH count(n.nom) AS c, count(DISTINCT n.nom) AS d
  RETURN 'talents' AS section, 'noms (renseignés, en double)' AS controle, '313, 1' AS attendu,
    toString(c) + ', ' + toString(c - d) AS obtenu
  UNION ALL
  MATCH (n:Attaque)
  WITH count(n) AS c
  RETURN 'attaques' AS section, '(:Attaque)' AS controle, '919' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Attaque)-[r:A_LE_TYPE]->(:Type)
  WITH count(r) AS c
  RETURN 'attaques' AS section, '(:Attaque)-[:A_LE_TYPE]->(:Type)' AS controle, '919' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (:Forme)-[r:APPREND]->(:Attaque)
  WITH count(r) AS c, sum(size(r.methodes)) AS m
  RETURN 'attaques' AS section, '(:Forme)-[:APPREND]->(:Attaque) (relations, somme des tailles de methodes)' AS controle, '99509, 142257' AS attendu,
    toString(c) + ', ' + toString(m) AS obtenu
  UNION ALL
  MATCH (:Forme)-[r:APPREND]->(:Attaque)
  WITH count(r.niveau) AS c, sum(r.niveau) AS s
  RETURN 'attaques' AS section, 'APPREND.niveau (renseignés, somme)' AS controle, '22573, 439583' AS attendu,
    toString(c) + ', ' + toString(s) AS obtenu
  UNION ALL
  MATCH (n:Attaque)
  WITH count(n.nom) AS c, count(DISTINCT n.nom) AS d
  RETURN 'attaques' AS section, 'noms (renseignés, en double)' AS controle, '919, 18' AS attendu,
    toString(c) + ', ' + toString(c - d) AS obtenu
  UNION ALL
  MATCH (n:Description)
  WITH count(n) AS c, sum(size(n.jeux)) AS j
  RETURN 'descriptions' AS section, '(:Description) (nœuds, somme des tailles de jeux)' AS controle, '5233, 7116' AS attendu,
    toString(c) + ', ' + toString(j) AS obtenu
  UNION ALL
  MATCH (:Pokemon)-[r:A_POUR_DESCRIPTION]->(:Description)
  WITH count(r) AS c
  RETURN 'descriptions' AS section, '(:Pokemon)-[:A_POUR_DESCRIPTION]->(:Description)' AS controle, '5233' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (p:Pokemon)-[:A_POUR_DESCRIPTION]->(d:Description)
  WITH p, d.texte AS texte, count(*) AS fois WHERE fois > 1
  WITH count(*) AS c
  RETURN 'descriptions' AS section, 'couples (Pokémon, texte) en double' AS controle, '0' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH (n)
  WITH count(n) AS c
  RETURN 'global' AS section, 'nœuds au total' AS controle, '8859' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  MATCH ()-[r]->()
  WITH count(r) AS c
  RETURN 'global' AS section, 'relations au total' AS controle, '113700' AS attendu,
    toString(c) AS obtenu
  UNION ALL
  CALL () { MATCH (n) RETURN count(n) AS noeuds }
  CALL () { MATCH ()-[r]->() RETURN count(r) AS relations }
  RETURN 'global' AS section, "volume sous la limite de l'instance" AS controle, 'oui' AS attendu,
    CASE WHEN noeuds <= $limiteNoeuds AND relations <= $limiteRelations THEN 'oui' ELSE 'non' END AS obtenu
  UNION ALL
  CALL () { MATCH (n) RETURN count(n) AS noeuds }
  CALL () { MATCH ()-[r]->() RETURN count(r) AS relations }
  RETURN 'global' AS section, "part de la limite de l'instance (nœuds, relations)" AS controle,
    '' AS attendu, replace(toString(round(100.0 * noeuds / $limiteNoeuds, 1)) + ' %, '
      + toString(round(100.0 * relations / $limiteRelations, 1)) + ' %', '.', ',') AS obtenu
}
RETURN section + '|' + controle + '|' + attendu + '|' + obtenu AS ligne;

// Vecteurs des descriptions (spec 003, plan D3), rangés par 07-embeddings.cypher : un VECTOR de 3 072 dimensions
// par description, que l'index sert. Un vecteur absent ou d'une autre dimension échappe à l'index : la recherche
// l'ignorerait sans bruit. Attendus : les 5 233 descriptions de la section descriptions, la dimension du plan (D2).
// Le prédicat de type juge type et dimension sans erreur, et ne compte pas une description sans vecteur ;
// vector_dimension_count() arrêterait toute la vérification sur une liste (22N27, sondé le 2026-10-13).
MATCH (d:Description)
WITH count(d.embedding) AS vecteurs, count(CASE WHEN d.embedding IS NOT :: VECTOR(3072) THEN 1 END) AS autres
UNWIND ['embeddings|(:Description) à embedding|5233|' + toString(vecteurs),
  'embeddings|embedding hors VECTOR de 3 072 dimensions|0|' + toString(autres)] AS ligne
RETURN ligne;

// Index vectoriel descriptions_texte (00-contraintes.cypher, plan D2), lu par SHOW INDEXES : sa définition en clair,
// pour qu'un écart dise laquelle. IF NOT EXISTS garderait sans rien dire un index du même nom réglé autrement
// (dimension, similarité, quantification, binary par défaut depuis Neo4j 2026.08). SHOW INDEXES écrit similarité et
// quantification en capitales (« COSINE ») : elles se comparent en minuscules. Sans index : « aucun ».
SHOW INDEXES YIELD name, type, entityType, labelsOrTypes, properties, options, state
WHERE name = 'descriptions_texte'
WITH options.indexConfig AS config, type, entityType, labelsOrTypes, properties, state
WITH collect(type + ', '
  + CASE WHEN entityType = 'NODE' AND labelsOrTypes = ['Description'] AND properties = ['embedding']
      THEN 'Description.embedding' ELSE 'autre schéma' END + ', '
  + coalesce(toString(config.`vector.dimensions`), '-') + ', '
  + coalesce(toLower(config.`vector.similarity_function`), '-') + ', '
  + coalesce(toLower(config.`vector.quantization.type`), '-') + ', ' + state) AS index
RETURN 'embeddings|index descriptions_texte (type, schéma, dimensions, similarité, quantification, état)|VECTOR, Description.embedding, 3072, cosine, none, ONLINE|'
  + coalesce(index[0], 'aucun') AS ligne;
