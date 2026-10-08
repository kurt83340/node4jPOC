// Liste des espèces (spec 002, plan D4) : les 1 025 noms de Pokémon, tels que la base les porte. Pas une
// question : la notation du banc s'en sert pour reconnaître une espèce citée hors de l'ensemble attendu (intrus
// d'une longue liste, espèce hors table d'une question sémantique) et pour remettre les 6 noms de Q2 à leur
// orthographe exacte. Rejouée avec les 27 requêtes par scripts/questions.sh --verifier.
MATCH (p:Pokemon)
RETURN p.nom AS pokemon
ORDER BY pokemon;
