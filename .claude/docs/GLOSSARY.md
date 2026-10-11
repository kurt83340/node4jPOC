# Glossaire — node4jPOC

> Vocabulaire du banc d'essai, une ligne par terme. Le pourquoi vit dans les ADR et dans le
> [plan 002](specs/002-agent-text-to-cypher/plan.md) (D1 à D13).

**Dernière MAJ :** 2026-10-12

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
- **Empreinte du prompt** : le SHA-256 du prompt d'une campagne (consigne et fiche, que le gel fige toutes deux), noté avec la langue du schéma dans `logs/banc/<campagne>/campagne.json` (format 3) ; un prompt changé depuis la création arrête la campagne, à la reprise et dans chaque cellule avant toute trace ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md), T10.0).
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
- **Source d'un second tour** (depuis le 2026-10-11) : au second tour d'une paire (Q18, Q28), une requête exécutée au tour précédent de la même conversation compte aussi comme source, si son résultat contient la réponse ; Q28 se juge ainsi en revue, Q18 par la pré-notation depuis T11.0 ([ADR-0015](adr/0015-mvp-source-du-tour-precedent.md)).
- **Revue à l'aveugle** : `banc revoir`, qui présente les cas « à revoir » sans cellule, modèle, passe, essai, durée ni coût (D4).
- **Réutilisation** : la note d'une revue reprise pour la même question et la même réponse courte normalisée, à partir du gel ; jamais pour les 13 questions dont la note dépend d'autre chose (D4).
- **Revue assistée** (depuis le 2026-10-11) : Claude pré-analyse chaque cas « à revoir », à l'aveugle, vérifie par script ce qui se vérifie et propose une note, une source et un motif ; Julien décide ([ADR-0014](adr/0014-mvp-revue-assistee.md)).
- **Contre-épreuve** : deux sens. En revue : 8 cas tirés au sort par campagne, que Julien revoit seul, à l'aveugle, avant de voir les propositions ; le taux d'accord va au relevé de la campagne ([ADR-0014](adr/0014-mvp-revue-assistee.md)). Au schéma anglais : le balayage joué sur la base française, où il doit lister les identifiants français (T10.0).
- **Pré-analyse scellée** : en revue assistée, l'empreinte SHA-256 de la pré-analyse de Claude, notée avant les réponses de Julien à la contre-épreuve ; ses 8 cas sont tirés au sort par une graine (pour `en-1`, les 16 premiers caractères du SHA-256 du CSV de la campagne finie) ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md), T10.2, T10.3).

## Schéma anglais

- **Table de correspondance** : `cypher/anglais/correspondance.toml`, seule source des noms anglais (labels, types, clés, index ; valeurs inchangées), avec la liste relue des identifiants communs aux deux langues (D8, T6.1).
- **Bascule** : le renommage du schéma de l'instance, du français vers l'anglais ou retour, par `scripts/charger.sh --schema en|fr` ; `--tout` est refusé tant que la base est en anglais (D8).
- **Traducteur** : `banc.traduction`, qui traduit chaque identifiant d'une requête Cypher selon sa place ; un littéral ne change que s'il est en entier un identifiant ; alias et expressions régulières inchangés ; `banc traduire --vers <dossier>` (T6.2).
- **Balayage** : la requête jointe à `fiche.cypher` traduit, qui cherche les labels, types et clés hors du schéma anglais ; attendu « aucun » (T6.2).
- **Fiche anglaise** : `questions/fiche-schema.en.md`, produite de la table par `python -m banc anglais` : identifiants traduits ; prose, valeurs et alias inchangés (T6.3).
- **Langue de la base** : ce que lit `scripts/charger.sh --langue`, en lecture seule, avant de créer ou de reprendre une campagne : `fr` ou `en` si les noms sont d'une seule langue et que ses contraintes et index sont présents et en ligne ; sinon « mixte » ou « incomplète », et `banc lancer` refuse de partir ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md), T10.0).
- **Preuve d'isomorphisme** : ce qui montre qu'une bascule vers l'anglais n'a changé que les noms : les 27 requêtes traduites rendent `attendu/` à l'identique, `dracofeu~` trouve Dracaufeu par l'index anglais, et le balayage ne trouve aucun identifiant français ; le retour se prouve par `verifier.sh`, `questions.sh --verifier` et `--exemples` ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md), T10.1, T10.3).
- **Clé orpheline** : un nom de propriété que `db.propertyKeys()` liste encore alors qu'aucune donnée ne le porte : Neo4j garde le nom d'une clé, et après une bascule les 18 clés de l'autre langue y restent ; relevé en T10.1 et T10.3, à revoir avant qu'Aura Agent lise le schéma (jalon 4) ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md)).

## Verdict du FR/EN

- **Passe de contrôle** : une passe française d'ADK + Gemini, jouée après le retour de la base au français (`fr-controle`, T10.3) ; elle sépare l'effet du schéma d'une dérive du modèle : hors de [min FR − 1 ; max FR + 1], le verdict est « non concluant » ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md)).
- **Bruit R, effet Δ** : sur les scores d'ADK + Gemini (justes, plus la moitié des partielles, sur 30), R est l'écart entre la meilleure et la moins bonne des 3 passes françaises, et Δ la moyenne des passes anglaises moins celle des passes françaises ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md)).
- **Verdict du FR/EN** : la règle fixée au pilote, avant toute passe comptée : passe de contrôle hors de sa fourchette, non concluant ; sinon Δ ≥ max(2, R), le schéma anglais aide ; Δ ≤ −max(2, R), il nuit ; entre les deux, pas d'effet mesurable à cette taille (30 questions, 3 passes, un modèle). Au jalon 2 : pas d'effet mesurable, Δ = −1,5 pour un seuil de 2,5 ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md), [rapport](../../banc/resultats/technique-2.md)).
- **Question qui bascule** : une question juste dans 2 passes sur 3 d'un côté du FR/EN et fausse dans 2 sur 3 de l'autre ; rapportée hors verdict (au jalon 2 : Q8 et Q27) ; à ne pas confondre avec la bascule du schéma ([plan 002, D8](specs/002-agent-text-to-cypher/plan.md), [rapport](../../banc/resultats/technique-2.md)).
