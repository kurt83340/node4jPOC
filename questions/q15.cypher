// Q15 — Donne toute la famille d'évolution de Pikachu. (text-to-Cypher)
// Les espèces de la famille, de la racine à toutes ses évolutions, par stade ; avec leurs formes, car une
// réponse qui ajoute les formes alternatives est acceptée si elle le signale (README).
MATCH (pikachu:Pokemon {nom: 'Pikachu'})
MATCH (racine:Pokemon)-[:EVOLUE_EN*0..]->(pikachu)
WHERE NOT EXISTS { ()-[:EVOLUE_EN]->(racine) }
MATCH chemin = (racine)-[:EVOLUE_EN*0..]->(membre:Pokemon)
RETURN membre.nom AS pokemon, length(chemin) + 1 AS stade,
  COLLECT { MATCH (f:Forme)-[:FORME_DE]->(membre) RETURN f.nom ORDER BY f.parDefaut DESC, f.nom } AS formes
ORDER BY stade, pokemon;
