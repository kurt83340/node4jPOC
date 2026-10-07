# Plan — Agent text-to-Cypher

> COMMENT on implémente la feature `002-agent-text-to-cypher`.

**Date :** 2026-10-01
**Option retenue :** B′ ([research § Décision](research.md)), corrigée par la revue adverse puis par la contre-revue ([research § Revue adverse](research.md))

## Approche technique

Un seul chemin vers la base pour toutes les cellules : `scripts/mcp-neo4j.sh` lit le secret, règle `neo4j/mcp` v1.6.0 en lecture seule et sans télémétrie, puis le lance en stdio. Le harnais `banc/` (Python 3.14, uv) ne lit jamais le secret. Pour chaque conversation, il démarre l'agent avec la même consigne et la même fiche, attend que le serveur soit connecté, pose la question, chronomètre à l'horloge monotone, enregistre la trace, puis note. Trois cellules en plan croisé, toutes sur Vertex (`eu`, ADC) : Claude Code (Agent SDK) + Sonnet 5.5, ADK + Sonnet 5.5, ADK + Gemini 3.8 Flash, alternées question par question. Une passe pilote cale la notation et le coût, puis viennent 3 passes comptées. Le schéma anglais se mesure en dernier, par une bascule de l'instance prouvée dans les deux sens. Protocole : [ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md).

## Architecture

```
questions/banc.toml · consigne.md · fiche-schema.md
              │
              ▼
banc/ (harnais, ne lit jamais le secret ; agents lancés en env -i, hors du dépôt)
  ├─ cellule claude-code : Agent SDK, préréglage claude_code + fiche, Sonnet 5.5 ─┐
  ├─ cellule adk-claude  : ADK Runner, Sonnet 5.5 ────────────────────────────────┤ stdio, read-cypher seul
  └─ cellule adk-gemini  : ADK Runner, Gemini 3.8 Flash ──────────────────────────┤
              │                                                                    ▼
              │                        scripts/mcp-neo4j.sh : secret → NEO4J_MCP_*, READ_ONLY, sans télémétrie
              │                                                                    │ exec neo4j-mcp v1.6.0
              │                                                                    ▼
              │                                     AuraDB Free (français ; anglais le temps d'US4,
              │                                     par charger.sh --schema en|fr)
              ├─► logs/banc/<campagne>/ : traces brutes, identifiant masqué (non versionné)
              └─► banc/mesures/<campagne>.csv : notes, temps, tokens, coût, versions (versionné, sans prose)

Notation : valeurs attendues et distracteurs + tables ADR-0008 + contrôle de Q2 ($proposee)
           + revue humaine à l'aveugle
Mode « faux serveur » (avant le 2026-10-04) : serveur MCP, validation des noms et contrôle de Q2 simulés,
           sans gcloud ni cypher-shell dans le PATH
```

## Modules / fichiers impactés

| Fichier                                                          | Action  | Notes                                                                                                                                                        |
| ---------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `scripts/mcp-neo4j.sh`                                           | nouveau | lanceur : `lire_identifiants` (gcloud sans stdin), `NEO4J_MCP_*`, `READ_ONLY`, `TELEMETRY=false`, rien sur stdout, stderr filtré                             |
| `scripts/transactions.sh`                                        | nouveau | arrête la lecture d'un agent abandonné (`SHOW`, puis `TERMINATE TRANSACTIONS`), si Aura Free le permet (T7.4)                                                |
| `scripts/charger.sh`                                             | modif   | `--schema fr\|en` (carte de paramètres versionnée, sans Python au chargement), `--explain` ; refuse `--tout` sur une base anglaise                           |
| `scripts/questions.sh`, `questions/q02.cypher`                   | modif   | `$proposee` toujours passé (défaut : l'équipe actuelle) ; `--dossier` ; `--exemples` (exemples de la fiche et `dracofeu~`)                                   |
| `questions/banc.toml`                                            | nouveau | 30 questions : texte exact, catégorie, mode de notation, tour précédent, valeurs attendues, distracteurs                                                     |
| `questions/consigne.md`, `fiche-schema.md`, `fiche-schema.en.md` | nouveau | consigne commune et générique ; fiche française ; fiche anglaise produite par la table                                                                       |
| `cypher/00-contraintes.cypher`, `cypher/90-verification.cypher`  | modif   | index plein texte ; 34e contrôle : présence de l'index                                                                                                       |
| `cypher/anglais/`                                                | nouveau | `correspondance.toml` (table unique, identifiants communs aux deux langues compris), `correspondance.cypher` (carte produite, versionnée), `renommer.cypher` |
| `.claude/docs/code-map.md`                                       | modif   | règles de couplage de `transactions.sh` (PR de la phase 4) et de `charger.sh --schema` (PR de la phase 6), puis relecture en T11.2                           |
| `banc/`                                                          | nouveau | harnais : questions, cellules, orchestration, traces, notation, coût, revue, traduction, rapport, et leurs tests                                             |
| doc                                                              | modif   | stack, ARCHITECTURE, RUNBOOK, ACCESS, README, ROADMAP                                                                                                        |

## Flux de données (une conversation)

1. Le harnais lit la question dans `banc.toml` ; pour Q2, il ajoute « Mon équipe : … » en tête du message.
2. Il ouvre la cellule en `env -i`, avec une liste blanche (HOME temporaire, `CLOUDSDK_CONFIG`, PATH vers `gcloud` et `neo4j-mcp`, variables Vertex), dans un dossier vide hors du dépôt. L'agent démarre `scripts/mcp-neo4j.sh` en stdio.
3. Avant le chrono, la connexion est établie : côté SDK, `connect()` puis `get_mcp_status()` jusqu'à « connected », avec `read-cypher` seul ; côté ADK, `get_tools()`. Sinon : panne, la conversation est relancée.
4. Chrono à l'horloge monotone : question, appels `read-cypher`, réponse finale ; plafonds de 10 tours, 180 s et un budget par conversation ; les reprises internes des clients (429, 5xx) sont journalisées.
5. Trace : messages, Cypher envoyés, résultats, appels d'introspection du schéma (`apoc.meta.*`, `db.labels()`, `db.propertyKeys()`…), tokens par appel et par modèle, effort effectif, durée ; identifiant de l'instance masqué ; dans `logs/banc/`.
6. Second tour (Q18 après Q2, Q28 après Q27) : même session ; une relance rejoue toujours la paire.
7. Notation : sections « Réponse » et « Sources », valeurs attendues et distracteurs, tables ADR-0008, contrôle de Q2 ; un cas « à revoir » passe en revue humaine à l'aveugle.
8. Une ligne dans `banc/mesures/<campagne>.csv` : cellule, passe, question, note, cause d'un échec, source citée, introspections, durée, tokens, coût, versions, commit PokéAPI.

## Erreurs / cas limites

| Cas                                                     | Comportement attendu                                                                                          |
| ------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Panne d'infrastructure (serveur MCP, Vertex 429 ou 5xx) | relance de la conversation, ou de la paire pour Q18 et Q28 ; plus de 2 pannes dans une passe : passe invalide |
| Échec de l'agent (180 s, 10 tours, budget)              | réponse **fausse**, cause notée ; groupe de processus tué, lecture arrêtée côté Aura                          |
| Délai dépassé à cause des reprises internes du client   | panne, pas échec de l'agent                                                                                   |
| L'agent tente une écriture                              | refusée par `read-cypher` (EXPLAIN préalable) ; visible dans la trace                                         |
| L'agent interroge le schéma (`apoc.meta.schema`…)       | permis par `read-cypher`, compté comme introspection                                                          |
| Serveur pas « connected » avant le chrono               | panne : l'agent ne doit jamais répondre de mémoire                                                            |
| Réponse sans section « Réponse », ou distracteur cité   | pré-note « à revoir »                                                                                         |
| Espèce hors table (question sémantique)                 | « à revoir », puis correction sur preuve ([ADR-0008](../../adr/0008-mvp-notation-questions-semantiques.md))   |
| Noms de Q2 mal formés, ou non reconnus par le contrôle  | jamais passés à `-P` s'ils sont mal formés ; « à revoir »                                                     |
| La bascule anglaise échoue                              | `charger.sh --schema fr`, sinon `charger.sh --purge` puis `--tout`                                            |

## Décisions (locales à cette feature)

> Le protocole de mesure (D2, D4, D5, D7, D10, D13) sert aux jalons 3 et 4 : il est fixé par l'[ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md).

### D1 — Un seul chemin vers la base : `neo4j/mcp` local, lancé par `scripts/`

**Choix :** `neo4j/mcp` v1.6.0 en stdio, lancé par `scripts/mcp-neo4j.sh` (chemin absolu) ; seul `read-cypher` est exposé aux agents ; `get-schema` retiré. Les noms des variables (`NEO4J_MCP_*` ou anciens noms) sont lus dans le source du tag v1.6.0, pas sur `main` (T0.3).
**Pourquoi :** lecture seule garantie côté serveur, aucun identifiant dans une configuration, même chemin pour toutes les cellules ; le schéma arrive par la fiche, et toute introspection par `read-cypher` est comptée.
**Alternatives écartées :** MCP for Aura (OAuth humain sans renouvellement, outil d'écriture exposé), à revoir au jalon 4 ; transport HTTP local (un serveur de plus à faire tourner, contraire à l'[ADR-0007](../../adr/0007-infra-secrets-et-services-geres.md)).

### D2 — Plan croisé de 3 cellules, toutes sur Vertex

**Choix :** Claude Code (Agent SDK, préréglage `claude_code`) + Sonnet 5.5 ; ADK + Sonnet 5.5 ; ADK + Gemini 3.8 Flash ; Vertex multirégion `eu`, ADC. Effort `high` des deux côtés Claude (`AnthropicGenerateContentConfig` dans ADK), `thinking_level` fixé pour Gemini ; la valeur effective est journalisée. Le petit modèle que Claude Code appelle pour ses tâches annexes est figé (`ANTHROPIC_DEFAULT_HAIKU_MODEL`, Haiku 4.5 activé dans Model Garden) et compté.
**Pourquoi :** le même modèle dans deux clients isole l'effet du client ; deux modèles dans le même client isolent l'effet du modèle ; les coûts sont réels et comparables.
**Alternatives écartées :** 2 cellules (option A) ; des modèles plus chers (Opus 5.5, Gemini 3.1 Pro), reportés. Repli : Sonnet 5 pour les **deux** cellules Claude si Sonnet 5.5 bute dans l'une d'elles.

### D3 — Claude Code par l'Agent SDK, isolé

**Choix :** lancé en `env -i` avec une liste blanche : HOME temporaire, `CLOUDSDK_CONFIG` vers la configuration `gcloud` (identifiants ADC), PATH vers `gcloud` et `neo4j-mcp`, variables Vertex, `CLAUDE_CODE_USE_VERTEX`, `CLAUDE_CODE_EFFORT_LEVEL=high`, `ANTHROPIC_DEFAULT_HAIKU_MODEL` ; `CLAUDE_CONFIG_DIR` temporaire ; `setting_sources=[]`, `tools=[]`, `read-cypher` seul ; dossier de travail vide hors du dépôt ; budget par conversation. La connexion au serveur est établie avant le chrono : `connect()`, puis `get_mcp_status()` jusqu'à « connected », car le message `init` n'arrive qu'au début de chaque requête.
**Pourquoi :** le SDK fusionne l'environnement du parent avec le sien, et la session de Claude Code qui lance le harnais exporte ses propres variables ; sans isolement, l'agent hériterait de réglages, d'identifiants OAuth et de la doc du dépôt, qui décrit le schéma et les réponses. Sans connexion préalable, le premier tour de la seule cellule SDK compterait le démarrage du serveur.
**Alternative écartée :** `claude -p --bare` (clé API exigée ou non, `--mcp-config` lu ou non en mode `--bare`, à vérifier), gardé pour un contrôle ponctuel.

### D4 — Notation mixte, sans juge LLM ; source citée vérifiée sur la trace

**Choix :**

- La consigne demande de finir par « Réponse : … » et « Sources : … ».
- Pré-notation automatique : valeurs attendues ; **distracteurs** par question (une réponse comparative cite forcément l'autre Pokémon) → « à revoir » ; règle des longues listes (Q7, Q14 : compte ou extrait) écrite avant le pilote ; tables de l'ADR-0008 ; contrôle de Q2.
- Revue humaine à l'aveugle des « à revoir » et de Q10, Q29 et Q30. Une décision n'est réutilisée, par réponse courte normalisée, que pour les questions à valeur, dont la note ne dépend que de la réponse courte ; jamais quand la règle exige une explication (Q11, Q27), un signalement (Q7, Q12, Q13, Q28) ou la correction d'une prémisse (Q29). Les décisions sont datées à partir du gel ; aucune n'est héritée du pilote. Estimation : ~200 cas sur toute la spec, environ 3 h pour Julien.
- **Source citée** : au moins une requête de « Sources » a été exécutée pendant le tour (aux espaces près) et son résultat contient les valeurs de la réponse ; une description citée doit avoir été renvoyée par un `read-cypher` du tour. Pas de source exigée pour Q10 (« pas dans les données », fondé sur un résultat vide) ni pour Q30 quand l'agent demande un critère.
- Les appels d'introspection du schéma sont comptés, pas pénalisés.

**Pourquoi :** rejouable et identique pour toutes les techniques ; juge LLM écarté par l'ADR-0008.

### D5 — Fiche et consigne communes, génériques, testées contre la contamination

**Choix :** `questions/fiche-schema.md` (modèle, règles, valeurs possibles, cas limites, index plein texte, 6 à 8 exemples hors banc) et `questions/consigne.md` (rôle, réponse tirée du graphe, format de fin), ajoutées telles quelles au prompt système. Test sur les deux fichiers entiers : aucun nom propre hors d'une liste blanche (les 18 types, les catégories d'attaque, les méthodes) ; aucune valeur citée dans `questions/attendu/` hors de cette liste, ce qui écarte les exemples naturels de la ROADMAP (la catégorie de Q23, l'apostrophe de Q1) au profit d'autres cas ; aucun exemple dont la structure, littéraux masqués, recoupe l'une des 27 requêtes. Chaque liste de valeurs est vérifiée par une requête (T7.3).
**Pourquoi :** `get-schema` ne transmet ni règles ni valeurs ; une fiche ou une consigne qui soufflerait les réponses fausserait toute la mesure.

### D6 — Q2 : l'équipe dans le message, le contrôle paramétré

**Choix :** Q2 est posée avec « Mon équipe : … » (l'équipe de référence). `q02.cypher` lit `$proposee` ; `questions.sh` le passe toujours, avec l'équipe actuelle par défaut, car Cypher n'a pas de paramètre optionnel. Les 6 noms extraits de la réponse sont validés (caractères permis) puis échappés dans une liste littérale ; leur existence se lit dans le contrôle lui-même (espèces reconnues). En mode faux serveur, validation et contrôle sont simulés. Sur la base anglaise, la version traduite de `q02.cypher` est utilisée.
**Pourquoi :** sans l'équipe, la question n'a pas de réponse ; placée dans la consigne, elle empêcherait Q18 de mesurer la mémoire ; un texte libre ne doit jamais devenir du Cypher.

### D7 — Un pilote, puis 3 passes comptées ; protocole gelé entre les deux

**Choix :** la passe pilote, non comptée, ne règle que l'extraction, la notation et le coût. Tout changement de fond de la consigne ou de la fiche se justifie sans citer une question du banc, et se note dans ce plan, daté. On gèle ensuite le protocole (commit), on fixe les seuils de décision du FR/EN, puis on lance 3 passes comptées, cellules alternées question par question, avec reprise possible (`--reprendre`).
**Pourquoi :** repérer les questions instables sans payer 5 passes, et ne pas régler la technique sur le jeu de test.

### D8 — Schéma anglais par bascule prouvée de l'instance

**Choix :**

- Une seule table, `cypher/anglais/correspondance.toml` (labels, relations, propriétés ; valeurs inchangées), avec la liste relue des identifiants communs aux deux langues (`Pokemon`, `Type`, `Description`, `id`, `pp`…), écartés des contrôles « aucun identifiant français ».
- La carte de paramètres `cypher/anglais/correspondance.cypher` est produite par `banc` hors chargement et versionnée ; un test vérifie qu'elle suit la table. `charger.sh --schema en|fr` la lit par `cypher-shell` : ni Python au chargement ([ADR-0003](../../adr/0003-mvp-chargement-cypher-pur.md)), ni secret dans le harnais.
- Renommage en Cypher pur : labels et types dynamiques de Cypher 25, ou `apoc.refactor.rename.*`, choisi par `charger.sh --schema en --explain` sur la vraie base (T7.5) ; relations recréées par lots ; contraintes et index (plage et plein texte) recréés dans la langue visée ; `--tout` refusé tant que la base est en anglais.
- Preuve d'isomorphisme : `banc traduire` écrit dans `logs/anglais/` les 27 requêtes traduites, les exemples traduits (dont `dracofeu~`) et une requête de balayage avec sa réponse attendue ; les 27 rendent `attendu/` à l'identique, `dracofeu~` trouve Dracaufeu par l'index anglais, et le balayage des labels, types et clés portés ne trouve plus aucun identifiant français. `db.propertyKeys()` est relevé en T10.1 et T10.3 : Neo4j garde les noms de propriétés orphelins, effet de bord à vérifier au jalon 4 avant qu'Aura Agent ne lise le schéma.
- Mesure : 3 passes ADK + Gemini avec la fiche anglaise. Retour par `--schema fr`, prouvé par `verifier.sh`, `questions.sh --verifier` et `--exemples`, puis une passe Gemini française de contrôle (dérive du modèle).

**Pourquoi :** une seule instance Free ; une copie entrerait en collision sur `Pokemon`, `Type` et `Description` ; ni paiement ni second secret.
**Repli :** `charger.sh --purge`, puis `--tout`. **Limite :** la conclusion ne vaut que pour Gemini 3.8 Flash.

### D9 — Index plein texte dans la chaîne de chargement

**Choix :** un index plein texte sur `nom` des 5 labels, analyseur `standard-folding` si `db.index.fulltext.listAvailableAnalyzers()` le propose, dans `cypher/00-contraintes.cypher` ; le 34e contrôle de `verifier.sh` vérifie sa présence ; la recherche `dracofeu~` passe dans `questions.sh --exemples`, pour qu'une base sans index rende un écart (1) et non une erreur (2). La fiche l'enseigne avec une autre faute.
**Pourquoi :** seul le chargement écrit (code-map) ; `get-schema` ne montre pas les index.

### D10 — Mesures versionnées sans prose ; coût calculé

**Choix :** `banc/mesures/*.csv` versionné (notes, cause d'un échec, introspections, temps, tokens, coût, versions, empreinte de la réponse) ; traces brutes dans `logs/banc/`. Coût = tokens × `banc/prix.toml` (prix datés de Vertex `eu`), **par modèle**, avec le cache lu et écrit, les tokens de réflexion et le petit modèle de Claude Code ; recoupé avec l'export de facturation BigQuery.
**Pourquoi :** aucune description republiée ([ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md)) ; un même calcul pour toutes les cellules, sans rien oublier de ce que Google facture.

### D11 — Effort de mise en place

**Choix :** par technique, les heures du journal, les lignes propres (`git diff --numstat`), les étapes hors code (Model Garden, rôles IAM, installations) et une note de 1 à 3 ; le socle commun est compté à part.

### D12 — Mode d'exécution

**Choix :** TDD pour le déterministe (notation, `banc.toml`, traduction du Cypher, carte de paramètres, coût, traces) ; tests après et essais réels ciblés pour les cellules et le lanceur. Les tests n'ont accès à aucun outil réel (PATH réduit aux faux outils, HOME temporaire) ; le test du lanceur tourne sous la liste blanche de D3. La répétition générale (T5.1) emploie les vrais LLM et le mode faux serveur, sans `gcloud` ni `cypher-shell` dans le PATH : rien ne touche Aura avant le 2026-10-04.

### D13 — Échec de l'agent contre panne d'infrastructure

**Choix :** une panne d'infrastructure (serveur MCP absent, Vertex 429 ou 5xx) relance la conversation, ou la paire ; un échec de l'agent (180 s, 10 tours, budget dépassé) compte **faux**, avec sa cause. Les reprises internes des clients sont journalisées ; un délai dépassé à cause d'elles compte comme panne (comportement de reprise relevé en T0.2). À l'abandon, le harnais tue le groupe de processus, et `scripts/transactions.sh` arrête la lecture restée active sur Aura (`neo4j/mcp` n'impose aucun délai, #293).
**Pourquoi :** sinon, une requête coûteuse, comme un produit cartésien, sortirait du score au lieu de compter, et continuerait de tourner sur l'instance ; à l'inverse, une lenteur de Vertex ne doit pas compter contre l'agent.

### LLM choisi, raison et coût estimé

| Cellule                     | Modèle                      | Prix Vertex `eu` (entrée / sortie, $ par million) | Coût par passe    |
| --------------------------- | --------------------------- | ------------------------------------------------- | ----------------- |
| Claude Code, ADK + Claude   | `claude-sonnet-5-5`         | à relever en T0.2 (Sonnet 5 : 2,20 / 11)          | 1,5 à 3 $         |
| Claude Code, tâches annexes | `claude-haiku-4-5@20251001` | 1,10 / 5,50                                       | quelques centimes |
| ADK + Gemini                | `gemini-3.8-flash`          | 0,825 / 4,125 jusqu'au 2026-12-31                 | ~0,5 $            |

Total : pilote, 3 passes comptées, 3 passes anglaises et 1 passe de contrôle, soit 25 à 35 $. Revue humaine : ~200 cas, environ 3 h.

## Sécurité

- Seul `scripts/mcp-neo4j.sh` lit le secret (avec `gcloud` sans stdin, car stdin est le canal MCP) ; il passe les variables par l'environnement du processus, jamais en argument, retire les anciens noms, n'écrit rien sur stdout et filtre stderr.
- Aucune configuration MCP sur le disque : le harnais la passe en mémoire au SDK et à ADK.
- Agents isolés : `env -i` et liste blanche (D3), `CLAUDE_CONFIG_DIR` temporaire, dossier vide hors du dépôt, ni outil de fichiers ni shell.
- Lecture seule : `READ_ONLY` (outil d'écriture non enregistré, EXPLAIN préalable, transaction en lecture), vérifié sur la vraie base (T7.4).
- Chargement : `charger.sh --schema` ne lance aucun Python après avoir lu le secret ; il lit la carte de paramètres versionnée.
- Traces : identifiant de l'instance masqué ; `logs/` ignoré par git ; gitleaks au pre-commit.

## Performance

- Temps mesuré de l'envoi de la question à la réponse finale, serveur déjà connecté ; plafonds de 10 tours, 180 s et un budget par conversation.
- Pas de cible : c'est une mesure.

## Tests

- **Unitaires (TDD)** : notation, `banc.toml` et sa cohérence avec le README et `attendu/`, contamination, traduction du Cypher, carte de paramètres, coût, masquage ; au moins 80 % de couverture sur la notation.
- **Intégration sans base ni réseau** : lanceur sous la liste blanche, avec de faux `gcloud` et `neo4j-mcp` ; cellules avec un faux serveur MCP, un faux LLM et un faux `cli_path` ; répétition générale en mode faux serveur, sans `gcloud` ni `cypher-shell` dans le PATH.
- **Sur la base, à partir du 2026-10-04** : `verifier.sh` (34/34), `--idempotence`, `questions.sh --verifier` (27/27) et `--exemples`, essai du lanceur (lecture acceptée, écriture refusée, lecture lente arrêtée), `charger.sh --schema en --explain`, passe pilote.

## Circuit breakers (conditions d'arrêt — à définir AVANT de coder)

- Le pilote coûte plus de 1,5 fois l'estimation : arrêt, replanifier.
- `neo4j/mcp` v1.6.0 ignore `NEO4J_MCP_READ_ONLY`, ou la télémétrie ne se coupe pas : arrêt, aucune mesure.
- Le lanceur ou `neo4j/mcp` échoue 3 fois de suite sur le même point : replanifier (replis : transport HTTP, ou `mcp-neo4j-cypher`).
- L'Agent SDK ne passe pas par Vertex : parking, et question à Julien (son abonnement rendrait le coût non mesurable).
- La preuve d'isomorphisme échoue après 2 corrections de la table : abandon du FR/EN, retour au français, FR/EN documenté comme non mesuré.
- 3 échecs consécutifs sur la même tâche : replanifier.

## Liens

- Spec : [spec.md](spec.md)
- Research : [research.md](research.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : [0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md), [0002](../../adr/0002-cadrage-environnement-cible-google-cloud.md), [0003](../../adr/0003-mvp-chargement-cypher-pur.md), [0005](../../adr/0005-mvp-conventions-nommage-schema.md), [0006](../../adr/0006-mvp-banc-essai-30-questions.md), [0007](../../adr/0007-infra-secrets-et-services-geres.md), [0008](../../adr/0008-mvp-notation-questions-semantiques.md), [0009](../../adr/0009-mvp-protocole-mesure-techniques.md)
