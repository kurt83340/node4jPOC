// Contraintes et index du graphe (spec 001, T4.1) : premier fichier du chargement, avant tout MERGE.
//
// Une contrainte d'unicité sur id (identifiant PokéAPI, plan D2) pour chaque label qui a une clé : un MERGE
// sur id ne peut plus créer de doublon, et l'index que Neo4j crée avec la contrainte rend ce MERGE rapide.
// Description n'a pas de clé : son MERGE porte sur le chemin (Pokémon, texte), que verifier.sh contrôle.
// Un index sur nom (plan D13) : la porte d'entrée de presque toutes les questions.
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
