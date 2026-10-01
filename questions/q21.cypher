// Q21 — Qui est le plus rapide entre Dracaufeu et Tortank ? (toutes les techniques)
// Stat de Vitesse de la forme par défaut.
MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)
WHERE p.nom IN ['Dracaufeu', 'Tortank']
RETURN p.nom AS pokemon, f.statVitesse AS vitesse
ORDER BY vitesse DESC, pokemon;
