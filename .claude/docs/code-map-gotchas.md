# Gotchas — pièges non évidents (injectés à la demande)

> **Non auto-chargé** (budget contexte v1.4). Le hook `pretooluse-inject-codemap.py` injecte,
> à l'édition d'un fichier de code, UNIQUEMENT les entrées qui **le ciblent** — une fois
> par session et par fichier. Une entrée cible un fichier en citant en backticks un chemin, un
> nom de fichier ou un dossier : `` `src/sync/notion.py` ``, `` `notion.py` ``, `` `src/sync/` ``
> (un heading `### src/sync/` cible toutes ses entrées). Une entrée sans chemin cité n'est
> injectée que sous le heading « Globaux » — à garder rare et court.
> Un piège qui t'a coûté du temps → ici (1 bullet, `chemin:ligne` si possible). Décision structurante → ADR.

## Globaux (injectés pour TOUTE édition de code — max 5 lignes)

- ⚠️ Mesurer une durée (journal, temps de réponse du banc d'essai) : horloge monotone, `/proc/uptime` en bash
  (`scripts/commun.sh:121`), `time.monotonic()` en Python. Sous WSL2, `date +%s`, `SECONDS`, `EPOCHREALTIME` reculent.
- ⚠️ Write, Edit et Bash (heredoc de commit compris) décodent la séquence d'échappement de l'espace fine insécable
  U+202F en vrai caractère, invisible. Fichier : écrire un marqueur, le remplacer via Python par `chr(92) + "u202F"`,
  vérifier qu'aucun `chr(0x202F)` ne reste. Commit, doc, chat : écrire « U+202F » (vu le 2026-09-29 et le 2026-10-01).

## Par zone

- ⚠️ `cypher/06-descriptions.cypher` — la normalisation remplace `\n` ET U+202F
  ([plan 001, D4](specs/001-socle-donnees/plan.md)) : avec `\n` seul, 5 240 descriptions au lieu de 5 233. Une formule
  qui semble remplacer une espace par une espace trahit une séquence d'échappement décodée (piège global ci-dessus).
- ⚠️ `scripts/commun.sh` — sur Aura, l'utilisateur et la base portent l'identifiant de l'instance,
  pas `neo4j` : les lire dans le secret (`NEO4J_USERNAME`, `NEO4J_DATABASE`), rien en dur. Toute sortie
  de `cypher-shell` passe par `filtrer` (mot de passe → arrêt, identifiant → ‹instance›) ; jamais de
  `set -x`, de `--debug`, ni de mot de passe en argument ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md)).
- ⚠️ `scripts/charger.sh` — `dbms.components()` annonce Neo4j « 5.27-aura » quand la console affiche
  2026.09 : ce n'est pas le signe d'un vieux Neo4j. Cypher 25 est disponible et déjà la langue par
  défaut de la base (`SHOW DATABASES`).
- ⚠️ `cypher/90-verification.cypher` — un `RETURN` qui mêle des constantes et un agrégat groupe par ces
  constantes : sur une base vide, aucune ligne au lieu d'une ligne à 0. Agréger d'abord dans un `WITH` sans
  clé. Pas d'échappement `''` en Cypher : un texte avec apostrophe s'écrit entre guillemets doubles.
- ⚠️ `cypher/90-verification.cypher` — Cypher 25 : `SHOW CONSTRAINTS` renvoie le type
  `NODE_PROPERTY_UNIQUENESS` (`UNIQUENESS` en Cypher 5) ; les index sur `nom` sont de type `RANGE`.
- ⚠️ `scripts/charger.sh` — un `exit` dans une boucle alimentée par `< <(fonction)` ne sort que du
  sous-shell de la fonction : lire d'abord dans un tableau (`lire_noms`), puis boucler dans le shell principal.
- ⚠️ `scripts/charger.sh` — journal et `--idempotence` lisent les statistiques de `--format verbose`, passé après
  le `--format plain` de `cypher_fichier` : le dernier l'emporte (cypher-shell 2026.09.0, vérifié le 2026-10-01).
  Sans statistiques, `--idempotence` s'arrête en erreur technique au lieu de conclure à vide.
- ⚠️ `scripts/commun.sh` — gitleaks (règle `generic-api-key`) prend `COMMIT_POKEAPI` pour une clé : « API » dans
  le nom, valeur hexadécimale. Faux positif marqué `# gitleaks:allow` sur sa seule ligne ; jamais `--no-verify`.
- ⚠️ `questions/` — les filets des questions sémantiques s'écrivent `(?iU)` puis `\\b` : sans `U`, le `\b` de
  Java ne connaît pas les lettres accentuées (« lavé » passerait pour « lave »). Après écriture, vérifier qu'aucun
  outil n'a changé les barres obliques (aucun caractère de contrôle). Rien de recopié des descriptions (ADR-0001).
- ⚠️ `questions/fiche-schema.md`, `questions/consigne.md` — vont tels quels dans le prompt de chaque conversation :
  chaque bloc de code `cypher` est un exemple, exécuté par `scripts/questions.sh --exemples` (T7.3) et comparé aux
  27 requêtes de référence ; une majuscule nouvelle (nom, mot en tête de phrase) s'ajoute, relue, à la liste blanche
  de `banc/tests/test_contamination.py`. Pas de tableau Markdown : Prettier l'aligne d'espaces, payés en tokens.
- ⚠️ `questions/banc.toml`, `questions/README.md` — `banc/tests/test_banc_toml.py` les tient cohérents entre eux et
  avec `questions/attendu/` (texte posé, catégorie, tour précédent, équipe de Q2, scores de Q8 cités par le README) :
  changer l'un, c'est mettre l'autre à jour dans le même commit.
- ⚠️ `banc/src/banc/` — texte français : une élision (d', l', qu'…) colle l'apostrophe au nom qui suit (« d'Évoli ») ;
  la détacher avant de chercher des noms, mais garder l'apostrophe d'un nom PokéAPI (« Écras’Face »). Vu le
  2026-10-08 dans `banc/tests/test_contamination.py` : sans cela, « d'Évoli » échappait au contrôle des noms propres.
- ⚠️ `questions/attendu/especes.txt` — la liste des espèces n'est pas une réponse : `banc/tests/test_contamination.py` ne
  lit que `attendu/q*.txt`. Renommée en `q…`, elle interdirait à la fiche les 1 025 noms, ses exemples compris.
- ⚠️ `scripts/questions.sh` — avec `--controle`, stdout ne porte que la réponse, que le harnais relit : tout autre
  message passe sur stderr (`ping_aura >&2`). `FORME_EQUIPE` est une ERE entre guillemets doubles de bash : `\\[`
  y devient `\[` ; testée en locale C (celle des tests) et UTF-8 (vu le 2026-10-08).
- ⚠️ `banc/src/banc/lecture.py` — liste des espèces : un nom collé par un tiret au mot suivant n'est pas cité
  (Draco-Météore) ; restent « Ronflex » dans « Gare au Ronflex » et « Épine-de-Fer » dans le talent « Épine de Fer »,
  que la notation envoie « à revoir ». `♀` et `♂` restent dans le mot, sinon Nidoran♀ et Nidoran♂ se confondent.
  Les positions des citations sont celles du texte mis en NFC (`prose`, `citations`). L'espace fine U+202F d'une
  regex s'écrit par sa séquence d'échappement, sinon Write la rend invisible (vu encore le 2026-10-08).
- ⚠️ `banc/src/banc/notation.py` — tout doute mène à « à revoir », jamais à « juste » : un « juste » à tort gonfle
  un score en silence (revue adverse du 2026-10-08 : 12 constats). La notation ne lit que `banc/src/banc/trace.py`,
  jamais le JSONL ni le format d'un client. Un message d'erreur de Neo4j recopie la requête, noms compris : un appel
  en erreur n'est jamais une source. Un test d'exclusion emploie une entrée que le code accepterait sans elle.
- ⚠️ `banc/src/banc/trace.py` — contrat lu par la notation (choix de Julien du 2026-10-08) : T3.1 l'entoure (JSONL,
  masquage, mesures) ; y ajouter un champ, oui ; en changer le sens, jamais sans revoir `notation.py`.
- ⚠️ `infra/reveil-aura/reveil.py` — la Query API d'Aura répond 202 même quand la requête échoue ; seul un
  refus d'authentification donne 401. Lire `errors` dans le corps, jamais le seul code HTTP
  ([doc Query API](https://neo4j.com/docs/query-api/current/query/), lue le 2026-09-30).
- ⚠️ `infra/reveil-aura/reveil.py` — le code vise Python 3.14 : `ruff format` y écrit `except A, B:` sans
  parenthèses (PEP 758), invalide avant 3.14. L'image et `requires-python` restent en 3.14 ou plus.
- ⚠️ `infra/reveil-aura/deploy.sh` — gcloud n'a pas de commande GA pour les canaux de notification (composant
  `beta`) ; `monitoring policies update` attend `--set-notification-channels`, pas `--notification-channels`.
  Un job Cloud Run n'a ni `--no-build` ni choix du compte de build : le compte Compute par défaut construit, avec
  `roles/run.builder`, qui met quelques minutes à se propager (premier build refusé le 2026-09-30).
- ⚠️ `infra/reveil-aura/alerte.json` — un job en échec écrit « Container called exit(N). » en WARNING seulement ;
  l'échec de l'exécution est l'entrée d'audit `system_event` en ERROR (« Execution … has failed to complete ») :
  filtrer sur `severity>=ERROR`, pas sur un texte (observé le 2026-09-30). Un extracteur `labelExtractors` sur
  `jsonPayload.message` a donné « (null) » dans l'e-mail : l'incident peut naître de l'entrée d'audit, qui n'a
  pas ce champ ; l'e-mail renvoie donc aux journaux.
- ⚠️ `scripts/mcp-neo4j.sh` — `neo4j-mcp` v1.6.0 : un booléen invalide (« oui ») prend le défaut, soit l'écriture
  permise et la télémétrie active ; ses options passent avant l'environnement ; un `NEO4J_MCP_*` vide retombe sur
  l'ancien nom ; un échec de connexion au démarrage sort avec le code 0 (lire le statut MCP). stdout est le canal
  MCP : rien n'y passe avant l'`exec` ([plan 002, D1](specs/002-agent-text-to-cypher/plan.md), vu le 2026-10-07).
- ⚠️ `scripts/mcp-neo4j.sh` — son stdout masqué est le canal MCP, un message JSON par ligne : le filtre rend chaque
  ligne aussitôt (`$| = 1` de perl), sinon le client attend sa réponse sans fin ; il ne peut pas non plus retirer
  une ligne (même blocage) ; l'identifiant lui arrive par l'environnement, jamais en argument (`ps`) (vu le 2026-10-08).
- ⚠️ `banc/mesures/revues.toml` — `gel` s'écrit en date-heure sans fuseau (`gel = 2026-10-20T10:00:00`), tout en
  haut, avant toute table, avec la campagne pilote, exigée (`pilote = "pilote"`) : une date seule ou un gel sans
  pilote laisseraient réutiliser une décision du pilote. Une décision se corrige ou se complète dans le fichier,
  jamais par une seconde décision au même cas (refusée) ([plan 002, D4](specs/002-agent-text-to-cypher/plan.md),
  vu le 2026-10-08).
- ⚠️ `banc/tests/` — gitleaks (pre-commit) prend un SHA de 40 caractères hexadécimaux affecté à un nom qui contient
  « api » (`commit_pokeapi="…"`) pour une clé d'API (generic-api-key) : lire le commit par
  `banc.mesures.commit_pokeapi()` plutôt que l'écrire (commit refusé le 2026-10-08).
- ⚠️ `banc/src/banc/isolement.py` — ADK (`mcp` 2.3.0, `client/stdio.py`) lance le serveur MCP dans sa propre session
  et, sans `env` explicite, ne lui passe que HOME, LOGNAME, PATH, SHELL, TERM et USER : donner la liste blanche à
  ses paramètres de lancement, et arrêter le lanceur par son propre groupe (relevé le 2026-10-08, pour T4.2).
- ⚠️ `banc/src/banc/mesures.py` — `ModelUsage` de Claude Code (SDK 0.2.164) et l'usage d'ADK (2.11.0) ne séparent
  pas l'écriture du cache à 5 min et à 1 h, facturée 1,6 fois plus cher à 1 h : sa part vient des messages de
  l'assistant ou de `ContextCacheConfig`. `output_tokens` d'Anthropic comprend la réflexion,
  `candidates_token_count` d'ADK non. `ModelUsage` cumule en outre toute la session : le tour se tire de deux
  relevés par `usage_du_tour`, sinon Q18 compte Q2 (vu le 2026-10-08).
- ⚠️ `banc/tests/test_lanceur.py` — un faux outil écrit en Python ajoute `LC_CTYPE` à son `os.environ` quand aucune
  locale n'est fixée (PEP 538) : lire l'environnement reçu à l'exec dans `/proc/self/environ` (vu le 2026-10-07).
- ⚠️ `banc/src/banc/isolement.py` — Claude Code choisit son accès dans un ordre fixe : fournisseur cloud
  (`CLAUDE_CODE_USE_VERTEX`…), puis `ANTHROPIC_AUTH_TOKEN`, puis `ANTHROPIC_API_KEY`… Une variable Vertex dans la
  liste blanche ferait passer la cellule par Vertex malgré la clé. La source réelle se lit dans le message `init`
  (`apiKeySource`), que la sonde exige à `ANTHROPIC_API_KEY` ([ADR-0011](adr/0011-infra-claude-par-api-anthropic.md), vu le 2026-10-08).
- ⚠️ `banc/prix.toml` — l'identifiant d'un modèle dépend de la voie : `claude-haiku-4-5-20251001` sur l'API,
  `claude-haiku-4-5@20251001` chez Google ; Sonnet 5.5 garde `claude-sonnet-5-5` des deux côtés, d'où la clé `acces`
  (vu le 2026-10-08).
