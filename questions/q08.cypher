// Q8 — En dehors de sa propre famille d'évolution, quels Pokémon ont le répertoire d'attaques le plus
// proche de celui de Dracaufeu ? (Aura Graph Analytics) Règle (README) : similarité de Jaccard sur les
// attaques apprises par les formes par défaut, famille d'évolution exclue ; top 5, avec une tolérance sur
// l'ordre quand les scores sont à moins de 0,01 (la tolérance sert à noter les techniques, pas ce rejeu).
MATCH (d:Pokemon {nom: 'Dracaufeu'})-[:A_POUR_FORME_PAR_DEFAUT]->(fd:Forme)
MATCH (racine:Pokemon)-[:EVOLUE_EN*0..]->(d)
WHERE NOT EXISTS { ()-[:EVOLUE_EN]->(racine) }
WITH COLLECT { MATCH (racine)-[:EVOLUE_EN*0..]->(m:Pokemon) RETURN m } AS famille,
  COLLECT { MATCH (fd)-[:APPREND]->(a:Attaque) RETURN a } AS attaquesDracaufeu
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
WHERE NOT p IN famille
WITH p, size(attaquesDracaufeu) AS nbDracaufeu,
  COUNT { (f)-[:APPREND]->(a:Attaque) WHERE a IN attaquesDracaufeu } AS communes,
  COUNT { (f)-[:APPREND]->(:Attaque) } AS nbAutre
WITH p, communes, nbDracaufeu + nbAutre - communes AS reunion
RETURN p.nom AS pokemon, communes, reunion, round(1.0 * communes / reunion, 3) AS jaccard
ORDER BY jaccard DESC, pokemon
LIMIT 5;
