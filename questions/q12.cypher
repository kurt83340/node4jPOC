// Q12 — Quel Pokémon a le plus de PV ? (text-to-Cypher)
// Règle (README) : Leuphorie ; Éthernatos Infinimax est accepté s'il est signalé comme une forme. On liste
// donc toutes les formes au maximum de PV, la forme par défaut (le Pokémon) d'abord.
MATCH (f:Forme)
WITH max(f.statPv) AS pvMax
MATCH (f:Forme {statPv: pvMax})-[:FORME_DE]->(p:Pokemon)
RETURN p.nom AS pokemon, f.nom AS forme, f.parDefaut AS formeParDefaut, f.statPv AS pv
ORDER BY formeParDefaut DESC, forme;
