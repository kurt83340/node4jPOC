# Glossaire — node4jPOC

> Vocabulaire du banc d'essai, une ligne par terme. Le pourquoi vit dans les ADR et dans le
> [plan 002](specs/002-agent-text-to-cypher/plan.md) (D1 à D13).

**Dernière MAJ :** 2026-10-09

## Banc d'essai

- **Technique** : une façon de répondre aux 30 questions (Cypher à la main, agent text-to-Cypher par MCP, GraphRAG, agents gérés) ; un jalon par technique ([README](../../README.md)).
- **Banc d'essai** : les 30 questions de référence en 6 catégories et leurs réponses attendues ([ADR-0006](adr/0006-mvp-banc-essai-30-questions.md)).
- **Espèce, forme** : « Pokémon » désigne l'espèce ; une forme (méga-évolution, forme régionale…) se rattache à son espèce ([ADR-0004](adr/0004-mvp-modele-espece-formes.md)).
- **Fiche de schéma, consigne** : `questions/fiche-schema.md` et `questions/consigne.md`, données à l'identique à toutes les techniques ; la **contamination** (un nom, une valeur attendue ou une requête du banc) y est interdite et testée (D5).

## Mesure

- **Cellule** : un couple client × modèle ; au jalon 2, Claude Code + Sonnet 5.5, ADK + Sonnet 5.5, ADK + Gemini 3.8 Flash (D2).
- **Plan croisé** : le même modèle dans deux clients, deux modèles dans le même client, pour séparer l'effet du client de celui du modèle ([ADR-0009](adr/0009-mvp-protocole-mesure-techniques.md)).
- **Harnais** : `banc/`, qui pose les questions, chronomètre, trace et note ; il ne lit jamais le secret de la base.
- **Lanceur** : `scripts/mcp-neo4j.sh`, seul chemin des agents vers la base : `neo4j-mcp` en lecture seule, sans télémétrie (D1), identifiant de l'instance masqué (D10).
- **Campagne** : un lancement du harnais, désigné par son nom : traces dans `logs/banc/<campagne>/`, mesures dans `banc/mesures/<campagne>.csv` (D10).
- **Passe** : les 30 questions posées une fois à une cellule. La **passe pilote**, non comptée, ne règle que l'extraction, la notation et le coût ; viennent ensuite 3 **passes comptées** (D7).
- **Gel** : le protocole figé par un commit après le pilote ; dans `banc/mesures/revues.toml`, la date-heure à partir de laquelle une décision de revue se réutilise (D4, D7).
- **Essai** : une tentative d'une conversation ; après une panne ou un arrêt, un nouvel essai la remplace, et seul le dernier est retenu (D4).
- **Second tour** : Q18 après Q2, Q28 après Q27, dans la même session ; une relance rejoue la paire ; si le premier tour échoue, le second compte faux d'office ([ADR-0012](adr/0012-mvp-second-tour-apres-echec.md)).
- **Panne** : incident d'infrastructure (serveur MCP absent, 429 ou 5xx du fournisseur, délai dû aux reprises internes du client) ; la conversation se relance, et plus de 2 pannes invalident la passe (D13).
- **Échec de l'agent** : 180 s, 10 tours ou budget dépassés ; la réponse compte fausse, avec sa cause, et ne se relance pas (D13).
- **Mode faux serveur** : serveur MCP, validation des noms et contrôle de Q2 simulés, sans `gcloud` ni `cypher-shell` (T5.1).
- **Introspection** : un appel qui lit le schéma (`apoc.meta.*`, `db.labels()`, `db.propertyKeys()`…) ; compté, pas pénalisé (D4).

## Notation

- **Réponse courte** : la section « Réponse » de la réponse de l'agent, que note le mode de la question ; normalisée, son empreinte sert à la revue.
- **Pré-notation** : la note automatique d'un tour (juste, partielle, fausse ou « à revoir ») : valeurs attendues, distracteurs, tables de l'[ADR-0008](adr/0008-mvp-notation-questions-semantiques.md), contrôle de Q2.
- **À revoir** : la pré-note d'un cas douteux, tranchée par la revue humaine ; tout doute y mène, jamais à « juste ».
- **Distracteur** : une valeur dont la présence dans la réponse courte impose la revue (erreur probable, ou variante acceptée si elle est signalée) (D4).
- **Longue liste** : Q7 et Q14 ; liste complète, ou compte exact avec un extrait sans intrus.
- **Source citée** : une requête de « Sources » exécutée pendant le tour, dont le résultat contient la réponse, ou une description renvoyée pendant le tour ([ADR-0009](adr/0009-mvp-protocole-mesure-techniques.md)).
- **Revue à l'aveugle** : `banc revoir`, qui présente les cas « à revoir » sans cellule, modèle, passe, essai, durée ni coût (D4).
- **Réutilisation** : la note d'une revue reprise pour la même question et la même réponse courte normalisée, à partir du gel ; jamais pour les 13 questions dont la note dépend d'autre chose (D4).
