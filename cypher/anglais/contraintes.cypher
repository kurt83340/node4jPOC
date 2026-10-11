// Contraintes et index du schéma anglais (spec 002, plan D8) : 00-contraintes.cypher
// traduit par correspondance.toml, produit par
// `uv run --directory banc python -m banc anglais` : ne pas l'éditer.
// scripts/charger.sh --schema en le joue après le renommage des données ; --schema fr
// rejoue cypher/00-contraintes.cypher.

CREATE CONSTRAINT type_id IF NOT EXISTS FOR (n:Type) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pokemon_id IF NOT EXISTS FOR (n:Pokemon) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT form_id IF NOT EXISTS FOR (n:Form) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ability_id IF NOT EXISTS FOR (n:Ability) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT move_id IF NOT EXISTS FOR (n:Move) REQUIRE n.id IS UNIQUE;

CREATE INDEX type_name IF NOT EXISTS FOR (n:Type) ON (n.name);
CREATE INDEX pokemon_name IF NOT EXISTS FOR (n:Pokemon) ON (n.name);
CREATE INDEX form_name IF NOT EXISTS FOR (n:Form) ON (n.name);
CREATE INDEX ability_name IF NOT EXISTS FOR (n:Ability) ON (n.name);
CREATE INDEX move_name IF NOT EXISTS FOR (n:Move) ON (n.name);

CREATE FULLTEXT INDEX names_fulltext IF NOT EXISTS
FOR (n:Type|Pokemon|Form|Ability|Move) ON EACH [n.name]
OPTIONS {indexConfig: {`fulltext.analyzer`: 'standard-folding'}};
