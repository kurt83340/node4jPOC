// Contraintes et index du graphe (spec 001, T4.1) : premier fichier du chargement, avant tout MERGE.
//
// Une contrainte d'unicité sur id (identifiant PokéAPI, plan D2) pour chaque label qui a une clé : un MERGE
// sur id ne peut plus créer de doublon, et l'index que Neo4j crée avec la contrainte rend ce MERGE rapide.
// Description n'a pas de clé : son MERGE porte sur le chemin (Pokémon, texte), que verifier.sh contrôle.
// Un index sur nom (plan D13) : la porte d'entrée de presque toutes les questions.
//
// Un index plein texte sur nom (spec 002, D9) : la recherche d'un nom approché (« dracofeu~ » trouve
// Dracaufeu), que la fiche de schéma enseigne aux agents. Analyseur standard-folding : sans casse ni accents
// (« electrik » trouve Électrik) ; charger.sh --go-no-go vérifie qu'Aura le propose. Créé avant les données,
// il se tient à jour à chaque écriture ; IF NOT EXISTS ne dit rien d'un index du même nom réglé autrement :
// verifier.sh contrôle son analyseur et son état.
//
// Un index vectoriel sur embedding de Description (spec 003, D2) : la recherche par le sens, du GraphRAG
// (jalon 3) comme d'Aura Agent (jalon 4). 3 072 dimensions, le défaut de gemini-embedding-001 ; cosine ; sans
// quantification (le défaut binary rogne le rappel, et 5 233 vecteurs ne pèsent que 64 Mo). 07-embeddings.cypher
// le remplit. Changer un réglage passe par DROP INDEX (RUNBOOK) : IF NOT EXISTS garderait l'ancien sans rien
// dire ; verifier.sh --section embeddings contrôle ses réglages et son état.
//
// IF NOT EXISTS : une relance ne fait rien, sans erreur. Noms explicites, comme le conseille le manuel
// Cypher, faits de lettres, de chiffres et de _ : charger.sh --purge refuse tout autre nom. Les labels
// suivent l'ordre du chargement (01 types, 02 Pokémon, 03 formes, 04 talents, 05 attaques).

CREATE CONSTRAINT type_id IF NOT EXISTS FOR (n:Type) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pokemon_id IF NOT EXISTS FOR (n:Pokemon) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT forme_id IF NOT EXISTS FOR (n:Forme) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT talent_id IF NOT EXISTS FOR (n:Talent) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT attaque_id IF NOT EXISTS FOR (n:Attaque) REQUIRE n.id IS UNIQUE;

CREATE INDEX type_nom IF NOT EXISTS FOR (n:Type) ON (n.nom);
CREATE INDEX pokemon_nom IF NOT EXISTS FOR (n:Pokemon) ON (n.nom);
CREATE INDEX forme_nom IF NOT EXISTS FOR (n:Forme) ON (n.nom);
CREATE INDEX talent_nom IF NOT EXISTS FOR (n:Talent) ON (n.nom);
CREATE INDEX attaque_nom IF NOT EXISTS FOR (n:Attaque) ON (n.nom);

CREATE FULLTEXT INDEX noms_plein_texte IF NOT EXISTS
FOR (n:Type|Pokemon|Forme|Talent|Attaque) ON EACH [n.nom]
OPTIONS {indexConfig: {`fulltext.analyzer`: 'standard-folding'}};

CREATE VECTOR INDEX descriptions_texte IF NOT EXISTS
FOR (d:Description) ON d.embedding
OPTIONS {indexConfig: {`vector.dimensions`: 3072, `vector.similarity_function`: 'cosine',
  `vector.quantization.type`: 'none'}};
