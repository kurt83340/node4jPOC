// Renommage du schéma, vers l'anglais ou retour au français (spec 002, plan D8) : labels, types de relation
// et clés, d'après la carte de paramètres (correspondance.cypher, produite par banc depuis correspondance.toml).
// Lancé par scripts/charger.sh --schema en|fr, qui passe $cartes (la carte) et $langue (le sens) ; il supprime
// avant les contraintes et les index, puis les recrée après, depuis leur fichier (00-contraintes.cypher ou
// contraintes.cypher).
//
// Cypher 25 pur, sans APOC (ADR-0003 ; mécanisme choisi en T7.5 par charger.sh --sonde-renommage) : labels,
// types et clés dynamiques, par lots de 10 000 lignes pour ménager la mémoire d'Aura Free. Un type de relation
// ne se renomme pas en place : chaque relation est recréée sous son nouveau nom, clés traduites, puis
// supprimée. Chaque requête ne voit que ce qui porte encore un nom de l'autre langue, et la table refuse un
// nom à la fois français et anglais : après une coupure, on relance, rien ne se fait deux fois.

// Labels des nœuds.
WITH $cartes[$langue] AS carte
MATCH (n)
WHERE any(label IN labels(n) WHERE label IN keys(carte.labels))
CALL (n, carte) {
  UNWIND [label IN labels(n) WHERE label IN keys(carte.labels)] AS ancien
  SET n:$(carte.labels[ancien])
  REMOVE n:$(ancien)
} IN TRANSACTIONS OF 10000 ROWS;

// Clés des nœuds.
WITH $cartes[$langue] AS carte
MATCH (n)
WHERE any(cle IN keys(n) WHERE cle IN keys(carte.cles))
CALL (n, carte) {
  UNWIND [cle IN keys(n) WHERE cle IN keys(carte.cles)] AS ancienne
  SET n[carte.cles[ancienne]] = n[ancienne]
  REMOVE n[ancienne]
} IN TRANSACTIONS OF 10000 ROWS;

// Relations d'un type renommé : recréées sous le nouveau type, avec leurs clés traduites.
WITH $cartes[$langue] AS carte
MATCH (a)-[r]->(b)
WHERE type(r) IN keys(carte.types)
CALL (a, r, b, carte) {
  CREATE (a)-[s:$(carte.types[type(r)])]->(b)
  SET s = properties(r)
  DELETE r
  WITH s, carte
  UNWIND [cle IN keys(s) WHERE cle IN keys(carte.cles)] AS ancienne
  SET s[carte.cles[ancienne]] = s[ancienne]
  REMOVE s[ancienne]
} IN TRANSACTIONS OF 10000 ROWS;

// Relations d'un type commun aux deux langues : leurs clés seules (aucun type commun aujourd'hui).
WITH $cartes[$langue] AS carte
MATCH ()-[r]->()
WHERE NOT type(r) IN keys(carte.types) AND any(cle IN keys(r) WHERE cle IN keys(carte.cles))
CALL (r, carte) {
  UNWIND [cle IN keys(r) WHERE cle IN keys(carte.cles)] AS ancienne
  SET r[carte.cles[ancienne]] = r[ancienne]
  REMOVE r[ancienne]
} IN TRANSACTIONS OF 10000 ROWS;
