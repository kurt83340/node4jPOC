// Recherche de la technique 3, GraphRAG (spec 003, plan D6) : la cellule la lance par read-cypher avec le vecteur
// de la question ($vecteur : gemini-embedding-001, RETRIEVAL_QUERY, 3 072 dimensions, encodé par le banc, D5) ; son
// résultat est le contexte du seul appel au LLM (ADR-0018). Recherche vectorielle seule : les 60 descriptions les
// plus proches dans l'index descriptions_texte, regroupées par espèce et classées par meilleur score, 20 espèces au
// plus, chacune avec ses 2 meilleures descriptions ; puis le parcours de chaque espèce depuis sa forme par défaut.
// Un enregistrement par espèce (D9) ; jamais embedding ni un nœud entier. Ces seuils viennent des données (5,1
// descriptions par espèce en moyenne), pas des questions du banc. SEARCH : Cypher 25 seulement, depuis Neo4j
// 2026.01 (Cypher Manual) ; pas de point-virgule final, la requête part telle quelle. Testée sans base par
// banc/tests/test_recherche_cypher.py ; EXPLAIN et forme du résultat sur la base : banc essai-recherche (T8.2).
CYPHER 25
MATCH (d:Description)
  SEARCH d IN (VECTOR INDEX descriptions_texte FOR $vecteur LIMIT 60) SCORE AS score
MATCH (p:Pokemon)-[:A_POUR_DESCRIPTION]->(d)
WITH p, d, score
ORDER BY score DESC
WITH p, collect({texte: d.texte, jeux: d.jeux, score: round(score, 4)})[..2] AS descriptions, max(score) AS meilleur
ORDER BY meilleur DESC
LIMIT 20
MATCH (p)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
RETURN p.nom AS espece, p.categorie AS categorie,
  COLLECT { MATCH (f)-[r:A_LE_TYPE]->(t:Type) RETURN t.nom ORDER BY r.rang } AS types,
  COLLECT { MATCH (f)-[r:A_LE_TALENT]->(t:Talent) RETURN {nom: t.nom, cache: r.cache} ORDER BY r.cache, t.nom }
    AS talents,
  f {.statPv, .statAttaque, .statDefense, .statAttaqueSpeciale, .statDefenseSpeciale, .statVitesse} AS statistiques,
  COLLECT { MATCH (avant:Pokemon)-[:EVOLUE_EN]->(p) RETURN avant.nom ORDER BY avant.nom } AS evolueDe,
  COLLECT { MATCH (p)-[:EVOLUE_EN]->(apres:Pokemon) RETURN apres.nom ORDER BY apres.nom } AS evolueEn,
  descriptions
ORDER BY meilleur DESC
