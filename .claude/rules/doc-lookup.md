# Doc-lookup — recherche de documentation externe (SOURCE UNIQUE)

> Politique unique pour TOUTE recherche de doc externe (lib, framework, API, service, CLI).
> Auto-chargée dans chaque session — lead, teammates — et reprise par les skills/agents qui
> en ont besoin (`/conception` étape Explore, `/debug` étape 2, `explore-docs`, skills stack…).

## La règle

1. **Jamais de réponse de mémoire** pour une API, une signature, une option de config ou un
   comportement versionné — la mémoire du modèle date, la lib a bougé depuis.
2. **Ordre des canaux** :
   1. **context7 (MCP)** — doc officielle versionnée (`resolve-library-id` → `query-docs`).
      Supposé connecté en **user-level** (installé une fois, dispo dans toutes les sessions) ;
   2. autres MCP de docs connectés au projet ;
   3. `WebFetch` / `WebSearch` — doc officielle d'abord, blogs/SO en dernier recours.
3. **Sourcer** : chaque affirmation tirée d'une doc = **version exacte + URL** (ou id context7).
   Une réponse non sourcée sur une API externe ne vaut rien en revue.
4. **Qui cherche** : ta session a les outils (`mcp__context7`, web) → cherche toi-même ;
   recherche large ou contexte à préserver → spawne **`explore-docs`** (subagent lecture seule).

## Déclencheurs typiques

- Choix de lib / planification technique (`/conception`) — comparer sur les **versions actuelles**
- Bug impliquant une lib externe (`/debug`) — le « bug » est parfois un changement d'API documenté
- Écriture de code contre une API tierce ; montée de version ; erreur cryptique d'un framework
- Doute entre ta mémoire et la doc à jour → **la doc gagne, toujours**
