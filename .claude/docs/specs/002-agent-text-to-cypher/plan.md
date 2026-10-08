# Plan — Agent text-to-Cypher

> COMMENT on implémente la feature `002-agent-text-to-cypher`.

**Date :** 2026-10-01
**Option retenue :** B′ ([research § Décision](research.md)), corrigée par la revue adverse puis par la contre-revue ([research § Revue adverse](research.md))

## Approche technique

Un seul chemin vers la base pour toutes les cellules : `scripts/mcp-neo4j.sh` lit le secret, règle `neo4j/mcp` v1.6.0 en lecture seule et sans télémétrie, puis le lance en stdio. Le harnais `banc/` (Python 3.14, uv) ne lit jamais le secret. Pour chaque conversation, il démarre l'agent avec la même consigne et la même fiche, attend que le serveur soit connecté, pose la question, chronomètre à l'horloge monotone, enregistre la trace, puis note. Trois cellules en plan croisé : Claude Code (Agent SDK) + Sonnet 5.5 et ADK + Sonnet 5.5 par l'API Anthropic, ADK + Gemini 3.8 Flash sur Vertex (`eu`, ADC), alternées question par question ([ADR-0011](../../adr/0011-infra-claude-par-api-anthropic.md)). Une passe pilote cale la notation et le coût, puis viennent 3 passes comptées. Le schéma anglais se mesure en dernier, par une bascule de l'instance prouvée dans les deux sens. Protocole : [ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md).

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

| Fichier                                                          | Action  | Notes                                                                                                                                                                                                                           |
| ---------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `scripts/mcp-neo4j.sh`                                           | nouveau | lanceur : `lire_identifiants` (gcloud sans stdin), `NEO4J_MCP_*`, `READ_ONLY`, `TELEMETRY=false`, rien sur stdout avant l'exec, stderr filtré, stdout masqué (identifiant, T3.1) ; retire `ANTHROPIC_API_KEY` avant `neo4j-mcp` |
| `scripts/banc.sh`                                                | nouveau | lit la clé Anthropic (secret `anthropic-api-banc`) et lance le harnais avec `ANTHROPIC_API_KEY` dans l'environnement, sans jamais l'afficher ([ADR-0011](../../adr/0011-infra-claude-par-api-anthropic.md))                     |
| `scripts/transactions.sh`                                        | nouveau | arrête la lecture d'un agent abandonné (`SHOW`, puis `TERMINATE TRANSACTIONS`), si Aura Free le permet (T7.4)                                                                                                                   |
| `scripts/charger.sh`                                             | modif   | `--schema fr\|en` (carte de paramètres versionnée, sans Python au chargement), `--explain` ; refuse `--tout` sur une base anglaise                                                                                              |
| `scripts/questions.sh`, `questions/q02.cypher`                   | modif   | `$proposee` toujours passé (défaut : l'équipe actuelle) ; `--dossier` ; `--exemples` (exemples de la fiche et `dracofeu~`)                                                                                                      |
| `questions/banc.toml`                                            | nouveau | 30 questions : texte exact, catégorie, mode de notation, tour précédent, valeurs attendues, distracteurs                                                                                                                        |
| `questions/consigne.md`, `fiche-schema.md`, `fiche-schema.en.md` | nouveau | consigne commune et générique ; fiche française ; fiche anglaise produite par la table                                                                                                                                          |
| `cypher/00-contraintes.cypher`, `cypher/90-verification.cypher`  | modif   | index plein texte ; 34e contrôle : présence de l'index                                                                                                                                                                          |
| `cypher/anglais/`                                                | nouveau | `correspondance.toml` (table unique, identifiants communs aux deux langues compris), `correspondance.cypher` (carte produite, versionnée), `renommer.cypher`                                                                    |
| `.claude/docs/code-map.md`                                       | modif   | règles de couplage de `banc.sh` (T0.2), de `transactions.sh` (PR de la phase 4) et de `charger.sh --schema` (PR de la phase 6), puis relecture en T11.2                                                                         |
| `banc/`                                                          | nouveau | harnais : questions, cellules, orchestration, traces, notation, coût, revue, traduction, rapport, et leurs tests                                                                                                                |
| doc                                                              | modif   | stack, ARCHITECTURE, RUNBOOK, ACCESS, README, ROADMAP                                                                                                                                                                           |

## Flux de données (une conversation)

1. Le harnais lit la question dans `banc.toml` ; pour Q2, il ajoute « Mon équipe : … » en tête du message.
2. Il ouvre la cellule en `env -i`, avec une liste blanche (HOME temporaire, `CLOUDSDK_CONFIG`, PATH vers `gcloud` et `neo4j-mcp`, puis la clé Anthropic pour une cellule Claude, les variables Vertex pour Gemini), dans un dossier vide hors du dépôt. L'agent démarre `scripts/mcp-neo4j.sh` en stdio.
3. Avant le chrono, la connexion est établie : côté SDK, `connect()` puis `get_mcp_status()` jusqu'à « connected », avec `read-cypher` seul ; côté ADK, `get_tools()`. Sinon : panne, la conversation est relancée.
4. Chrono à l'horloge monotone : question, appels `read-cypher`, réponse finale ; plafonds de 10 tours, 180 s et un budget par conversation ; les reprises internes des clients (429, 5xx) sont journalisées.
5. Trace : messages, Cypher envoyés, résultats, appels d'introspection du schéma (`apoc.meta.*`, `db.labels()`, `db.propertyKeys()`…), tokens par appel et par modèle, effort effectif, durée ; identifiant de l'instance masqué ; dans `logs/banc/`.
6. Second tour (Q18 après Q2, Q28 après Q27) : même session ; une relance rejoue toujours la paire.
7. Notation : sections « Réponse » et « Sources », valeurs attendues et distracteurs, tables ADR-0008, contrôle de Q2 ; un cas « à revoir » passe en revue humaine à l'aveugle.
8. Une ligne dans `banc/mesures/<campagne>.csv` : cellule, passe, question, note, cause d'un échec, source citée, introspections, durée, tokens, coût, versions, commit PokéAPI.

## Erreurs / cas limites

| Cas                                                                              | Comportement attendu                                                                                                                 |
| -------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Panne d'infrastructure (serveur MCP, 429 ou 5xx de Vertex ou de l'API Anthropic) | relance de la conversation, ou de la paire pour Q18 et Q28 ; plus de 2 pannes dans une passe : passe invalide                        |
| Crédits Anthropic épuisés, limite de dépense atteinte                            | arrêt de la campagne ; la conversation interrompue se rejoue après recharge (`--reprendre`) ; question à Julien avant toute recharge |
| Échec de l'agent (180 s, 10 tours, budget)                                       | réponse **fausse**, cause notée ; groupe de processus tué, lecture arrêtée côté Aura                                                 |
| Délai dépassé à cause des reprises internes du client                            | panne, pas échec de l'agent                                                                                                          |
| L'agent tente une écriture                                                       | refusée par `read-cypher` (EXPLAIN préalable) ; visible dans la trace                                                                |
| L'agent interroge le schéma (`apoc.meta.schema`…)                                | permis par `read-cypher`, compté comme introspection                                                                                 |
| Serveur pas « connected » avant le chrono                                        | panne : l'agent ne doit jamais répondre de mémoire                                                                                   |
| Réponse sans section « Réponse », ou distracteur cité                            | pré-note « à revoir »                                                                                                                |
| Espèce hors table (question sémantique)                                          | « à revoir », puis correction sur preuve ([ADR-0008](../../adr/0008-mvp-notation-questions-semantiques.md))                          |
| Noms de Q2 mal formés, ou non reconnus par le contrôle                           | jamais passés à `-P` s'ils sont mal formés ; « à revoir »                                                                            |
| La bascule anglaise échoue                                                       | `charger.sh --schema fr`, sinon `charger.sh --purge` puis `--tout`                                                                   |

## Décisions (locales à cette feature)

> Le protocole de mesure (D2, D4, D5, D7, D10, D13) sert aux jalons 3 et 4 : il est fixé par l'[ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md).

### D1 — Un seul chemin vers la base : `neo4j/mcp` local, lancé par `scripts/`

**Choix :** `neo4j/mcp` v1.6.0 en stdio, lancé par `scripts/mcp-neo4j.sh` (chemin absolu) ; seul `read-cypher` est exposé aux agents ; `get-schema` retiré. Les noms des variables (`NEO4J_MCP_*` ou anciens noms) sont lus dans le source du tag v1.6.0, pas sur `main` (T0.3).
**Pourquoi :** lecture seule garantie côté serveur, aucun identifiant dans une configuration, même chemin pour toutes les cellules ; le schéma arrive par la fiche, et toute introspection par `read-cypher` est comptée.
**Alternatives écartées :** MCP for Aura (OAuth humain sans renouvellement, outil d'écriture exposé), à revoir au jalon 4 ; transport HTTP local (un serveur de plus à faire tourner, contraire à l'[ADR-0007](../../adr/0007-infra-secrets-et-services-geres.md)).

**Relevé du tag v1.6.0 (T0.3, 2026-10-07)** : source au commit `e4e2208` ; binaire dans `~/.local/share/neo4j-mcp/v1.6.0/`, seul dans son dossier, tiré de l'archive Linux x86_64 vérifiée par `sha256sum -c` (aucune attestation de provenance publiée : la somme prouve un téléchargement intact, pas une release saine).

- **Variables** (`internal/config/config.go`) : `NEO4J_MCP_URI`, `_USERNAME`, `_PASSWORD`, `_DATABASE` (défaut `neo4j`), `_READ_ONLY` (défaut `false`), `_TELEMETRY` (défaut `true`), `_TRANSPORT_MODE` (défaut `stdio`), `_LOG_LEVEL`, `_LOG_FORMAT`, `_SCHEMA_SAMPLE_SIZE`. Le nom canonique l'emporte, mais vide il retombe sur l'ancien nom (14 alias, `NEO4J_URI`…, chacun signalé sur stderr). Un booléen invalide (« oui ») prend le défaut, soit l'écriture permise et la télémétrie active : le lanceur écrit `true` et `false`. Les options `--password`… existent : jamais employées (argument visible de `ps`).
- **Lecture seule** : `write-cypher` non enregistré (`internal/server/tools_register.go`) ; `read-cypher` préfixe `EXPLAIN` et refuse tout type autre que `r`, puis exécute vers les lecteurs (`internal/tools/cypher/read_cypher_handler.go`, `internal/database/service.go`). `get-schema` reste enregistré, aucune variable ne le retire : filtre côté client (`allowed_tools`, `tool_filter`). Les instructions du serveur citent encore `get-schema` : à vérifier dans le prompt de la cellule SDK (T4.1).
- **Télémétrie** : `NEO4J_MCP_TELEMETRY=false` appelle `Disable()` avant tout envoi ; plus aucun événement vers MixPanel (démarrage, connexion, appel d'outil), ni la requête `dbms.components()` qui l'alimente (`cmd/neo4j-mcp/main.go`, `internal/analytics/analytics.go`).
- **Démarrage en stdio** : `RETURN 1` (délai de 5 s), présence d'`apoc.meta.schema`, `gds.version()` (absent sur Aura Free, donc pas d'outil GDS). Un échec s'écrit sur stderr et le processus sort avec le code **0** : la panne se lit dans le statut MCP, pas dans le code retour.
- **Sorties** : stdout ne porte que MCP ; journal sur stderr, chaque requête de `read-cypher` en clair au niveau `info`. Chaque transaction porte la métadonnée `app: MCP4NEO4J/v1.6.0`, de quoi viser les lectures des agents dans `scripts/transactions.sh` (D13).
- Circuit breaker non déclenché : lecture seule et télémétrie se règlent.

### D2 — Plan croisé de 3 cellules : Claude par l'API Anthropic, Gemini sur Vertex

**Choix :** Claude Code (Agent SDK, préréglage `claude_code`) + Sonnet 5.5 et ADK + Sonnet 5.5 (`AnthropicLlm`), par l'API Anthropic avec la clé d'un workspace dédié ; ADK + Gemini 3.8 Flash sur Vertex multirégion `eu`, ADC. Voie de Claude changée le 2026-10-08 ([ADR-0011](../../adr/0011-infra-claude-par-api-anthropic.md)) : Vertex refusait le quota. Effort `high` des deux côtés Claude (`AnthropicGenerateContentConfig` dans ADK), `thinking_level` fixé pour Gemini ; la valeur effective est journalisée. Le petit modèle que Claude Code appelle pour ses tâches annexes est figé (`ANTHROPIC_DEFAULT_HAIKU_MODEL=claude-haiku-4-5-20251001`) et compté.
**Pourquoi :** le même modèle dans deux clients isole l'effet du client ; deux modèles dans le même client isolent l'effet du modèle ; les coûts sont réels et comparables.
**Limite :** ADK + Sonnet (API) et ADK + Gemini (Vertex `eu`) passent par deux points d'accès : un écart de temps ne tient pas qu'au modèle.
**Alternatives écartées :** 2 cellules (option A) ; des modèles plus chers (Opus 5.5, Gemini 3.1 Pro), reportés. Repli : Sonnet 5 pour les **deux** cellules Claude si Sonnet 5.5 bute dans l'une d'elles.

**Relevé T0.2 (2026-10-07)** : `banc acces` fait un appel minimal par client.

- **Quotas** : Claude à 0 sur `jleroy-labo`, en `eu` comme en `global` (Sonnet 5 et 5.5 comptés sous `anthropic-claude-sonnet`, Haiku 4.5 sous `anthropic-claude-haiku-4-5`). Hausse demandée le 2026-10-07 par `gcloud beta quotas preferences` (20 requêtes, 300 000 tokens d'entrée et 30 000 de sortie par minute pour Sonnet ; 10, 100 000 et 10 000 pour Haiku), **refusée** dans les minutes qui ont suivi (« Quota request denied », refus automatique) : circuit breaker « Claude injoignable par Vertex », parking et question à Julien. Ces quotas borneraient aussi la vitesse de dépense (environ 1 $ par minute au pire).
- **Gemini 3.8 Flash** répond depuis `eu` (ADK, `thinking_level` HIGH : 139 tokens de réflexion pour un « OK »).
- **Prix** : `banc/prix.toml` ; Sonnet 5.5 relevé sur son SKU Marketplace, absent de la page de prix de Google.
- **ADK + Claude** : l'effort ne joue qu'avec la réflexion adaptative (`thinking_budget=-1`) ; le cache n'est demandé qu'avec un `ContextCacheConfig`, sur 1 h (écriture à 2 fois l'entrée) dès que son TTL atteint 3 600 s. À régler en T4.2, sinon la cellule paierait toute son entrée à chaque tour.
- **Relevé du 2026-10-08, par l'API Anthropic** ([ADR-0011](../../adr/0011-infra-claude-par-api-anthropic.md)) : les 5 sondes répondent en 1 à 2 s, pour 0,0027 $ en tout. Le coût calculé par `banc/prix.toml` égale celui qu'annonce Claude Code (`total_cost_usd` : 0,000888 $ avec Sonnet 5.5, 0,000881 $ avec Haiku 4.5) : prix de l'API vérifiés pour l'entrée et la sortie, pas encore pour le cache. `per_turn_effort_active` : vrai avec Sonnet 5.5, faux avec Haiku 4.5. Réflexion sur « OK » : 0 token pour ADK + Claude (adaptative), 150 pour Gemini. Limites de débit : palier de l'organisation à lire dans la Console (doc : palier Start, 1 000 requêtes, 2 M tokens d'entrée et 400 k de sortie par minute et par modèle).

### D3 — Claude Code par l'Agent SDK, isolé

**Choix :** lancé en `env -i` avec une liste blanche : HOME temporaire, `CLOUDSDK_CONFIG` vers la configuration `gcloud` (le lanceur y lit le secret de la base), PATH vers `gcloud` et `neo4j-mcp`, `ANTHROPIC_API_KEY`, `CLAUDE_CODE_EFFORT_LEVEL=high`, `ANTHROPIC_DEFAULT_HAIKU_MODEL` ; aucune variable Vertex (`CLAUDE_CODE_USE_VERTEX` passerait avant la clé) ; `CLAUDE_CONFIG_DIR` temporaire ; `setting_sources=[]`, `tools=[]`, `read-cypher` seul ; dossier de travail vide hors du dépôt ; budget par conversation. La connexion au serveur est établie avant le chrono : `connect()`, puis `get_mcp_status()` jusqu'à « connected », car le message `init` n'arrive qu'au début de chaque requête. La clé est lue dans Secret Manager par `scripts/banc.sh`, jamais par le harnais ; `mcp-neo4j.sh` la retire avant `neo4j-mcp` ; la sonde exige que le message `init` désigne la clé (`apiKeySource`), jamais l'abonnement.
**Pourquoi :** le SDK fusionne l'environnement du parent avec le sien, et la session de Claude Code qui lance le harnais exporte ses propres variables ; sans isolement, l'agent hériterait de réglages, d'identifiants OAuth et de la doc du dépôt, qui décrit le schéma et les réponses. Sans connexion préalable, le premier tour de la seule cellule SDK compterait le démarrage du serveur.
**Alternative écartée :** `claude -p --bare` (clé API exigée ou non, `--mcp-config` lu ou non en mode `--bare`, à vérifier), gardé pour un contrôle ponctuel.
**Relevé T0.2 (2026-10-07)** : liste blanche dans `banc/src/banc/isolement.py`, complétée de `GOOGLE_APPLICATION_CREDENTIALS` (Claude Code, en Node, ne cherche l'ADC que sous HOME et ignore `CLOUDSDK_CONFIG`), de `GOOGLE_CLOUD_QUOTA_PROJECT=jleroy-labo` (l'ADC du poste a `jleroy-outils` pour projet de quota) et de `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` (ni mise à jour du binaire figé, ni télémétrie). Le Claude Code mesuré est celui qu'embarque `claude-agent-sdk` 0.2.164 : la version 2.1.292. Depuis l'ADR-0011, `GOOGLE_APPLICATION_CREDENTIALS` et `GOOGLE_CLOUD_QUOTA_PROJECT` ne servent plus qu'à la cellule Gemini. Relevé du 2026-10-08 (API) : `apiKeySource` vaut `ANTHROPIC_API_KEY`, `analytics_disabled` vrai. À régler en T4.1 : `permissionMode` annoncé `auto` avec Sonnet 5.5 et `default` avec Haiku 4.5, à fixer dans la cellule ; Claude Code ouvre une socket de messagerie entre sessions dans `/tmp/cc-socks/`, hors du HOME temporaire, à couper si une variable le permet.

### D4 — Notation mixte, sans juge LLM ; source citée vérifiée sur la trace

**Choix :**

- La consigne demande de finir par « Réponse : … » et « Sources : … ».
- Pré-notation automatique : valeurs attendues ; **distracteurs** par question (une réponse comparative cite forcément l'autre Pokémon) → « à revoir » ; règle des longues listes (Q7, Q14 : compte ou extrait) écrite avant le pilote ; tables de l'ADR-0008 ; contrôle de Q2.
- Revue humaine à l'aveugle des « à revoir » et de Q10, Q29 et Q30 (et de Q27 et Q28 depuis T2.2). Une décision n'est réutilisée, par réponse courte normalisée, que pour les questions à valeur, dont la note ne dépend que de la réponse courte ; jamais quand la règle exige une explication (Q11, Q27), un signalement (Q7, Q12, Q13, Q28) ou la correction d'une prémisse (Q29). Les décisions sont datées à partir du gel ; aucune n'est héritée du pilote. Estimation : ~200 cas sur toute la spec, environ 3 h pour Julien.
- **Source citée** : au moins une requête de « Sources » a été exécutée pendant le tour (aux espaces près) et son résultat contient les valeurs de la réponse ; une description citée doit avoir été renvoyée par un `read-cypher` du tour. Pas de source exigée pour Q10 (« pas dans les données », fondé sur un résultat vide) ni pour Q30 quand l'agent demande un critère.
- Les appels d'introspection du schéma sont comptés, pas pénalisés.

**Fixé en T1.1 (2026-10-08, relu par Julien)** : `questions/banc.toml` donne à chaque question son mode (valeur, ensemble, liste ordonnée, longue liste, sémantique, contrôle, revue) ; un nombre attendu se compare comme un nombre. Un distracteur est une valeur dont la présence dans la réponse courte impose la revue : erreur probable (la capacité Z de Q1, la famille de Q8, l'autre Pokémon de Q18 et Q21, une attaque Électrik gardée à Q28) ou variante que le README accepte si elle est signalée (formes de Q12, Q14 et Q15, talents et formes de Q7, Lance-Flammes de Q13) ; tous relevés dans les CSV du commit figé. Écartés exprès, plus coûteux en revue qu'utiles : Normal à Q25 (l'Eau gagne sous toutes les lectures), Poison à Q11, « spéciale » à Q24, « Pokémon Lézard » à Q23. Longues listes : liste complète, ou compte exact avec un extrait sans intrus (README). Q27 et Q28 : une réponse incomplète passe à revoir, car une autre attaque expliquée peut être juste (Nœud Herbe fait ×4 contre Onix, plus que Surf). Q8 : la tolérance admet Braségali et Typhlosion en 5e place.

**Fixé en T2.1 (2026-10-08, choix de Julien)** : une espèce citée se reconnaît par la liste des 1 025 noms tirée de la base (`questions/especes.cypher`, réponse dans `attendu/especes.txt`, rejouée par `questions.sh --verifier`), par la plus longue correspondance en mots entiers. Un intrus de longue liste, une espèce hors table ou hors du classement de Q8 se voient donc. Écartée : s'en tenir aux distracteurs et aux tables, où une espèce inconnue restait invisible, d'où des « juste » à tort (précision surestimée), sauf à revoir toutes les réponses justes de ces questions. Faux positifs relevés : « Draco » dans 12 attaques Draco-…, « Ronflex » dans « Gare au Ronflex », « Épine-de-Fer » dans le talent « Épine de Fer » ; ils mènent à « à revoir », jamais à « juste ».

**Fixé en T2.2 (2026-10-08)** : `banc.notation` pré-note un tour ; tout doute mène à « à revoir », jamais à « juste ».

- **Trace** (choix de Julien) : la notation ne lit qu'un contrat minimal, `banc/trace.py` : la réponse finale du tour et ses appels, dans l'ordre (outil, requête, paramètres, résultat tel que l'agent l'a reçu, erreur). T3.1 l'entoure (JSONL, masquage, mesures) sans le changer. Écartés : le résultat stocké déjà décodé (dépendant du format de neo4j-mcp), et tout le format de T3.1 dès la phase 2 (phase doublée).
- **Pluriel** (choix de Julien) : sous les seuils de l'ADR-0008, partielle avec au moins une espèce juste, fausse sinon (README).
- **Q27 et Q28 en revue systématique** (choix de Julien, après la revue adverse) : un mot attendu présent ne prouvait ni le signalement de Q28 ni l'absence d'une autre attaque conseillée. Remplace pour elles « une réponse incomplète passe à revoir » (T1.1) ; `un_parmi` et `revoir_si_incomplete` restent dans le format, sans question. Revue : une trentaine de cas de plus.
- **Q8** : la tolérance permet des échanges entre espèces à moins de 0,01, jamais des glissements cumulés (Reshiram oublié et la liste remontée d'un cran : partiel) ; une espèce de tête sans score passe « à revoir ». **Q9** : types exacts, écrits avec leur majuscule (« l'eau » d'une raison n'est pas le type Eau) ; un écart passe « à revoir ».
- **Espèces** : un nom collé par un tiret au mot suivant n'est pas cité (Draco-Météore) ; une espèce nommée comme une forme (Méga-…, … d'Alola, Motisma Lavage) passe « à revoir » dans les modes à espèces ; Q2 aussi quand l'équipe compte un membre de la référence. Le code recopié dans « Réponse » ne compte pas comme dit.
- **Source citée** : valeurs à retrouver, les valeurs justes de la réponse, à défaut les espèces qu'elle avance (une réponse fausse n'obtient pas « oui » plus facilement qu'une juste) ; requête exécutée sans erreur dans le tour, aux espaces et commentaires `//` près, résultats porteurs de ces valeurs ; description renvoyée par un enregistrement qui porte aussi l'une d'elles ; rien à vérifier, ou citation introuvable à côté d'une source valable : « à revoir ». Q10 exemptée ; Q27 à Q30 jugées en revue.
- **Revue adverse** (agent `reviewer`, contexte frais) : 12 constats rejoués dans le code, tous traités ; mutations : 33 fautes sur la première version, 59 sur la version corrigée, toutes détectées.

**Pourquoi :** rejouable et identique pour toutes les techniques ; juge LLM écarté par l'ADR-0008.

### D5 — Fiche et consigne communes, génériques, testées contre la contamination

**Choix :** `questions/fiche-schema.md` (modèle, règles, valeurs possibles, cas limites, index plein texte, 6 à 8 exemples hors banc) et `questions/consigne.md` (rôle, réponse tirée du graphe, format de fin), ajoutées telles quelles au prompt système. Test sur les deux fichiers entiers : aucun nom propre hors d'une liste blanche (les 18 types, les catégories d'attaque, les méthodes) ; aucune valeur citée dans `questions/attendu/` hors de cette liste, ce qui écarte les exemples naturels de la ROADMAP (la catégorie de Q23, l'apostrophe de Q1) au profit d'autres cas ; aucun exemple dont la structure, littéraux masqués, recoupe l'une des 27 requêtes. Chaque liste de valeurs est vérifiée par une requête (T7.3).
**Pourquoi :** `get-schema` ne transmet ni règles ni valeurs ; une fiche ou une consigne qui soufflerait les réponses fausserait toute la mesure.

**Fixé en T1.2 (2026-10-08)** : la consigne ne donne ni « corrige une prémisse fausse » ni « dis si la question est vague », qui souffleraient Q29 et Q30. La fiche ne nomme que 6 des 12 méthodes d'apprentissage : les autres (« Pichu Électacle », « Stadium: Pikachu Surfeur », « Boîte Zygarde ») citent des entités du banc. Elle évite les tableaux Markdown, que Prettier aligne d'espaces payés en tokens à chaque conversation. Test (`tests/test_contamination.py`) : tout mot à majuscule en liste blanche explicite (types, catégories, méthodes, schéma, outils, entités des exemples, mots de tête de phrase) ; aucune valeur de `attendu/`, aucun nom des questions, du README ni de `banc.toml` ; un exemple « recoupe » une requête de référence si, littéraux et variables masqués, il lui ressemble à 0,85 ou plus, ou en contient d'un bloc 80 % : seuils mesurés sur les 31 requêtes de référence, où deux requêtes de même gabarit vont de 0,88 à 1 et deux requêtes courtes sans rapport atteignent 0,80.

### D6 — Q2 : l'équipe dans le message, le contrôle paramétré

**Choix :** Q2 est posée avec « Mon équipe : … » (l'équipe de référence). `q02.cypher` lit `$proposee` ; `questions.sh` le passe toujours, avec l'équipe actuelle par défaut, car Cypher n'a pas de paramètre optionnel. Les 6 noms extraits de la réponse sont validés (caractères permis) puis échappés dans une liste littérale ; leur existence se lit dans le contrôle lui-même (espèces reconnues). En mode faux serveur, validation et contrôle sont simulés. Sur la base anglaise, la version traduite de `q02.cypher` est utilisée.
**Pourquoi :** sans l'équipe, la question n'a pas de réponse ; placée dans la consigne, elle empêcherait Q18 de mesurer la mémoire ; un texte libre ne doit jamais devenir du Cypher.

**Fait en T1.3 (2026-10-08)** : `questions.sh` passe `$proposee` à chaque requête, une équipe valide par défaut. Reste à ouvrir, avec la lecture des réponses (T2.1), la voie qui lui passe les 6 noms extraits, validés puis échappés.

**Fait en T2.1 (2026-10-08)** : les 6 noms sont les espèces citées dans « Réponse », remises à leur orthographe exacte par la liste des espèces (D4) ; s'il y en a plus de 6, l'équipe de référence citée dans l'explication est écartée ; sans exactement 6 noms, « à revoir », rien n'est envoyé. Validés (caractères des 1 025 noms réels : lettres, chiffres, espace, point, deux-points, tiret, ♀, ♂) puis échappés par `banc.lecture.liste_cypher`, ils passent à `questions.sh --controle`, qui revérifie la forme avant tout appel (6 chaînes sans apostrophe, antislash ni caractère de contrôle) ; stdout n'y porte que la réponse, relue par `banc.attendu`.

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

**Contrat de `--dossier` (T1.3, 2026-10-08)** : `questions.sh --dossier D` lit `D/qNN.cypher` (et `D/especes.cypher` s'il existe, depuis T2.1) et, pour `--exemples`, `D/exemples/*.cypher`, dont `D/exemples/dracofeu.cypher` ; `banc traduire --vers D` (T6.2) écrit sous cette forme.

### D9 — Index plein texte dans la chaîne de chargement

**Choix :** un index plein texte sur `nom` des 5 labels, analyseur `standard-folding` si `db.index.fulltext.listAvailableAnalyzers()` le propose, dans `cypher/00-contraintes.cypher` ; le 34e contrôle de `verifier.sh` vérifie sa présence ; la recherche `dracofeu~` passe dans `questions.sh --exemples`, pour qu'une base sans index rende un écart (1) et non une erreur (2). La fiche l'enseigne avec une autre faute.
**Pourquoi :** seul le chargement écrit (code-map) ; `get-schema` ne montre pas les index.

**Nom fixé en T1.2 (2026-10-08)** : `noms_plein_texte`, cité par la fiche et par `questions.sh` (`dracofeu~`). La fiche annonce une recherche sans casse ni accents : à corriger en T7.2 si `standard-folding` manque.

### D10 — Mesures versionnées sans prose ; coût calculé

**Choix :** `banc/mesures/*.csv` versionné (notes, cause d'un échec, introspections, temps, tokens, coût, versions, empreinte de la réponse) ; traces brutes dans `logs/banc/`. Coût = tokens × `banc/prix.toml` (prix datés, par accès : API Anthropic pour Claude, Vertex `eu` pour Gemini), **par modèle**, avec le cache lu et écrit, les tokens de réflexion et le petit modèle de Claude Code ; recoupé avec l'usage de la Console Anthropic et l'export de facturation BigQuery.
**Cache :** durée du cache à trancher au pilote (T8.1), même politique pour les deux cellules Claude : `ENABLE_PROMPT_CACHING_1H=1` pour Claude Code et `ContextCacheConfig(ttl_seconds=3600)` pour ADK, ou les deux à 5 min ; en 1 h, compter la part 1 h de `usage.cache_creation`.
**Pourquoi :** aucune description republiée ([ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md)) ; un même calcul pour toutes les cellules, sans rien oublier de ce que Google et Anthropic facturent.

**Fixé en T3.1 (2026-10-08)** : `banc.mesures`.

- **Trace** : `logs/banc/<campagne>/<cellule>-p<passe>-<questions>-e<essai>.jsonl`, un événement par ligne, vidé dès son écriture (une conversation tuée garde tout ce qui précède). Types fermés : en-tête (campagne, cellule, passe, essai, questions, modèle, voie, jour, effort, versions, commit PokéAPI), `question`, `llm` (tokens d'un modèle, réflexion, usage brut), `appel` puis `resultat` (appariés par l'identifiant du client : une lecture en cours reste lisible), `reprise`, `fin` (issue `reponse`, `echec`, `panne` ou `arret`, cause codée, réponse finale). Temps à l'horloge monotone depuis l'ouverture. Relue, elle redonne les tours de `banc/trace.py`, inchangé ; la relecture applique les règles de l'écriture.
- **Identifiant de l'instance** (choix de Julien) : masqué par le lanceur sur le stdout de `neo4j-mcp`, par perl (une ligne par message MCP, rendue aussitôt ; l'identifiant par l'environnement, jamais en argument). Ni l'agent, ni le fournisseur du LLM, ni la trace ne le voient, et le harnais n'a pas à le connaître (ADR-0009). Écartés : le passer au harnais par `banc.sh` (l'agent le voit encore) ; un masque par motif de 8 caractères hexadécimaux (heuristique, alors que la renotation relit la trace).
- **CSV** `banc/mesures/<campagne>.csv` : une ligne par tour et par essai, pannes et arrêts compris, sans note (une passe à plus de 2 pannes se voit) ; un échec compte faux, avec sa cause. Colonnes fixes (`banc.mesures.COLONNES`) ; sans prose vérifiée à l'écriture (ensembles fermés, motifs en codes, aucune espace ailleurs) ; empreinte de la réponse courte normalisée (SHA-256, 16 caractères), pour la revue (T3.2).
- **Coût par modèle** (choix de Julien) : les colonnes de tokens portent sur le modèle de la cellule ; `cout_usd` sur tous les modèles appelés, `cout_annexe_usd` sur les autres (le petit modèle de Claude Code) ; détail par modèle dans la trace. Un modèle sans tarif arrête la mesure. Écarté : un second CSV, par modèle.
- **Tokens** (source des versions figées) : l'API Anthropic détaille l'écriture en cache par durée (`cache_creation`) et la réflexion (`output_tokens_details`, comprise dans `output_tokens`) ; `ModelUsage` de Claude Code et l'usage d'ADK ne séparent pas 5 min et 1 h : la part à 1 h viendra des messages de l'assistant (T4.1) et de `ContextCacheConfig` (T4.2).
- **Vérifié** : 84 tests, couverture 100 % ; 84 fautes injectées dans `banc.mesures` et le lanceur, toutes détectées ; une survivante en cours de route (une question reposée après la dernière, que le test laissait à un autre contrôle), corrigée.

### D11 — Effort de mise en place

**Choix :** par technique, les heures du journal, les lignes propres (`git diff --numstat`), les étapes hors code (Model Garden, rôles IAM, installations) et une note de 1 à 3 ; le socle commun est compté à part.

### D12 — Mode d'exécution

**Choix :** TDD pour le déterministe (notation, `banc.toml`, traduction du Cypher, carte de paramètres, coût, traces) ; tests après et essais réels ciblés pour les cellules et le lanceur. Les tests n'ont accès à aucun outil réel (PATH réduit aux faux outils, HOME temporaire) ; le test du lanceur tourne sous la liste blanche de D3. La répétition générale (T5.1) emploie les vrais LLM et le mode faux serveur, sans `gcloud` ni `cypher-shell` dans le PATH : rien ne touche Aura avant le 2026-10-04.

### D13 — Échec de l'agent contre panne d'infrastructure

**Choix :** une panne d'infrastructure (serveur MCP absent, 429 ou 5xx de Vertex ou de l'API Anthropic) relance la conversation, ou la paire ; un échec de l'agent (180 s, 10 tours, budget dépassé) compte **faux**, avec sa cause. Les reprises internes des clients sont journalisées ; un délai dépassé à cause d'elles compte comme panne (comportement de reprise relevé en T0.2). À l'abandon, le harnais tue le groupe de processus, et `scripts/transactions.sh` arrête la lecture restée active sur Aura (`neo4j/mcp` n'impose aucun délai, #293).
**Pourquoi :** sinon, une requête coûteuse, comme un produit cartésien, sortirait du score au lieu de compter, et continuerait de tourner sur l'instance ; à l'inverse, une lenteur du fournisseur ne doit pas compter contre l'agent. Un plafond de dépense atteint (crédits épuisés, limite du workspace) n'est ni une panne ni un échec : la campagne s'arrête, et la conversation interrompue se rejoue après recharge.
**Reprises internes relevées (T0.2, source des versions figées)** : Claude Code reprend jusqu'à 10 fois (`CLAUDE_CODE_MAX_RETRIES`, 10 min au plus par appel) : sur un 429 persistant, il dépasse les 180 s (vu le 2026-10-07), la cellule plafonnera donc cette variable (T4.1). Le client Anthropic d'ADK : 2 reprises (0,5 à 8 s) sur 408, 409, 429 et 5xx. Gemini dans ADK : aucune reprise par défaut (`retry_options` vide), sinon 5 essais (1 à 60 s) sur 408, 429, 500, 502, 503 et 504.

### LLM choisi, raison et coût estimé

| Cellule                     | Modèle                      | Prix (entrée / sortie, $ par million)          | Coût par passe    |
| --------------------------- | --------------------------- | ---------------------------------------------- | ----------------- |
| Claude Code, ADK + Claude   | `claude-sonnet-5-5`         | 2 / 10, API Anthropic (`banc/prix.toml`)       | 1,4 à 2,7 $       |
| Claude Code, tâches annexes | `claude-haiku-4-5-20251001` | 1 / 5, API Anthropic                           | quelques centimes |
| ADK + Gemini                | `gemini-3.8-flash`          | 0,825 / 4,125 jusqu'au 2026-12-31, Vertex `eu` | ~0,5 $            |

Total : pilote, 3 passes comptées, 3 passes anglaises et 1 passe de contrôle, soit 24 à 33 $ (Claude 9 % moins cher par l'API que sur Vertex `eu`). Revue humaine : ~200 cas, environ 3 h (une trentaine de plus depuis que Q27 et Q28 sont revues, T2.2).

## Sécurité

- Seul `scripts/mcp-neo4j.sh` lit le secret (avec `gcloud` sans stdin, car stdin est le canal MCP) ; il passe les variables par l'environnement du processus, jamais en argument, retire les anciens noms, n'écrit rien sur stdout et filtre stderr.
- Aucune configuration MCP sur le disque : le harnais la passe en mémoire au SDK et à ADK.
- La clé Anthropic : lue dans Secret Manager par `scripts/banc.sh`, passée par l'environnement aux seules cellules Claude, retirée par `mcp-neo4j.sh` avant `neo4j-mcp` ; jamais sur le disque ni en argument ([ADR-0011](../../adr/0011-infra-claude-par-api-anthropic.md)).
- Agents isolés : `env -i` et liste blanche (D3), `CLAUDE_CONFIG_DIR` temporaire, dossier vide hors du dépôt, ni outil de fichiers ni shell.
- Lecture seule : `READ_ONLY` (outil d'écriture non enregistré, EXPLAIN préalable, transaction en lecture), vérifié sur la vraie base (T7.4).
- Chargement : `charger.sh --schema` ne lance aucun Python après avoir lu le secret ; il lit la carte de paramètres versionnée.
- Identifiant de l'instance : masqué par le lanceur sur le stdout de `neo4j-mcp` (T3.1), donc absent des traces ; `logs/` ignoré par git ; gitleaks au pre-commit.

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
- L'Agent SDK ne passe pas par la clé API (`apiKeySource` du message `init`) : parking, et question à Julien (son abonnement rendrait le coût non mesurable).
- Crédits Anthropic épuisés ou limite du workspace atteinte : arrêt, et question à Julien avant toute recharge (ADR-0011).
- La preuve d'isomorphisme échoue après 2 corrections de la table : abandon du FR/EN, retour au français, FR/EN documenté comme non mesuré.
- 3 échecs consécutifs sur la même tâche : replanifier.

## Liens

- Spec : [spec.md](spec.md)
- Research : [research.md](research.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : [0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md), [0002](../../adr/0002-cadrage-environnement-cible-google-cloud.md), [0003](../../adr/0003-mvp-chargement-cypher-pur.md), [0005](../../adr/0005-mvp-conventions-nommage-schema.md), [0006](../../adr/0006-mvp-banc-essai-30-questions.md), [0007](../../adr/0007-infra-secrets-et-services-geres.md), [0008](../../adr/0008-mvp-notation-questions-semantiques.md), [0009](../../adr/0009-mvp-protocole-mesure-techniques.md)
