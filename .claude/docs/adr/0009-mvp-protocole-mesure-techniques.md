---
status: accepted
scope: mvp
phase: 2026-Q4
supersedes: null
---

# 0009 — Protocole de mesure des techniques du banc d'essai

> ⚠️ **Point remplacé** (2026-10-08) : « tous sur Vertex » (Décision, plan croisé) → [ADR-0011](0011-infra-claude-par-api-anthropic.md) : les deux cellules Claude passent par l'API Anthropic, Gemini reste sur Vertex `eu`. Le reste de cet ADR reste en vigueur.

**Statut :** Accepted
**Date :** 2026-10-01
**Décideur :** Julien Leroy

## Contexte

Le banc d'essai pose 30 questions à chaque technique ([ADR-0006](0006-mvp-banc-essai-30-questions.md)), et la notation des questions sémantiques est fixée ([ADR-0008](0008-mvp-notation-questions-semantiques.md)). Il manquait la façon de mesurer une technique fondée sur un LLM : ce qu'elle reçoit, par où elle lit la base, comment ses réponses en texte libre sont notées, ce que veut dire « citer ses sources », combien de passes, et comment compter un échec. La conception de la spec 002 (agent text-to-Cypher, jalon 2) a comparé trois options proposées par des agents à angle imposé ; deux revues adverses ont ensuite corrigé le plan ([research de la spec 002](../specs/002-agent-text-to-cypher/research.md)). Le protocole servira aussi aux jalons 3 (GraphRAG) et 4 (Aura Agent, agent sur Agent Runtime) : il survit à la spec.

## Options considérées

- **Option A — Premier chiffre** : 2 cellules, 1 passe. Rapide et peu cher, mais un chiffre qu'on ne sait pas expliquer (client et modèle changent ensemble), noyé dans l'aléa des LLM.
- **Option B — Colle mince** : 3 cellules en plan croisé, 3 passes, notation mixte, en réutilisant au plus les outils existants.
- **Option C — Banc contrôlé** : pilote, puis 5 passes en ordre aléatoire, revue humaine à l'aveugle. Le plus rigoureux, pour deux fois l'effort de B.
- **Option D — Ne rien fixer (ne rien faire)** : chaque technique mesurée à sa façon ; le tableau comparatif du jalon 4 comparerait des protocoles, pas des techniques.

## Décision

**B′** (Julien, 2026-10-01) : l'option B, avec la passe pilote et la revue à l'aveugle de l'option C.

- **Plan croisé** : quand le client et le modèle peuvent varier, le même modèle passe dans deux clients et deux modèles dans le même client, pour séparer l'effet du client de celui du modèle. Au jalon 2 : Claude Code + Sonnet 5.5, ADK + Sonnet 5.5, ADK + Gemini 3.8 Flash, tous sur Vertex.
- **Même entrée pour tous** : une consigne générique et une fiche de schéma communes, données à l'identique, testées contre la contamination (aucun nom, aucune valeur attendue ni aucune requête du banc). Une technique ne lit jamais les fichiers du dépôt.
- **Un seul chemin vers la base par technique, en lecture seule** : les identifiants ne sont lus que là où la code-map le permet (au jalon 2, un lanceur de `scripts/`) ; le harnais ne les lit jamais. Les appels d'introspection du schéma sont comptés.
- **Notation mixte, sans juge LLM** : la réponse finit par « Réponse » et « Sources » ; pré-notation automatique (valeurs attendues, distracteurs, tables de l'ADR-0008, contrôle de Q2) ; revue humaine à l'aveugle du reste. Une décision de revue n'est réutilisée que pour une question dont la note ne dépend que de la réponse courte.
- **Source citée** : une requête exécutée pendant le tour, dont le résultat contient la réponse, ou une description renvoyée pendant le tour. Rien n'est exigé quand la bonne réponse est « ce n'est pas dans les données » (Q10), ni quand l'agent demande un critère (Q30).
- **Échec de l'agent contre panne** : un délai, un nombre de tours ou un budget dépassé compte faux, avec sa cause ; seule une panne d'infrastructure se relance, et toute la conversation avec. Un délai dû aux reprises internes du client compte comme panne.
- **Un pilote, puis 3 passes comptées** : le pilote ne règle que l'extraction, la notation et le coût. Tout autre changement se justifie sans citer une question du banc, et se note, daté, dans le plan de la spec.
- **Mesures** : versionnées sans prose (notes, causes, introspections, temps à l'horloge monotone, tokens, coût, versions, commit PokéAPI) ; traces brutes hors du dépôt ; coût = tokens × prix datés, par modèle, cache et réflexion compris, recoupé avec la facturation.

## Conséquences

- ✅ Le tableau comparatif compare des techniques, pas des protocoles : mêmes entrées, même notation, mêmes règles d'échec.
- ✅ Un écart s'explique (client ou modèle), et l'aléa se voit (3 passes).
- ✅ Rejouable et versionné ; aucun juge LLM pour biaiser la mesure de techniques fondées sur des LLM.
- ⚠️ Environ 3 h de revue humaine sur toute la spec 002 (~200 cas, estimation du plan) : à réduire par de meilleures règles automatiques.
- ⚠️ Avec 30 questions, seul un écart net départage deux techniques ; 2 ou 3 questions d'écart peuvent n'être que du bruit.
- ⚠️ Les techniques gérées du jalon 4 (Aura Agent) imposent leur client et leur accès à la base : le plan croisé et le chemin unique s'y réduisent à ce qui varie vraiment.
- ⚠️ Les seuils de l'ADR-0008 et ceux d'une comparaison (FR/EN) se fixent avant la mesure, jamais après.

## Liens

- [Research de la spec 002](../specs/002-agent-text-to-cypher/research.md) : options, décision, revues adverses
- [Plan de la spec 002](../specs/002-agent-text-to-cypher/plan.md) : D2, D4, D5, D7, D10, D13
- [ADR-0006](0006-mvp-banc-essai-30-questions.md) et [ADR-0008](0008-mvp-notation-questions-semantiques.md), que cet ADR précise sans les remplacer
