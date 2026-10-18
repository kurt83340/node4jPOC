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
  (`scripts/commun.sh:159`), `time.monotonic()` en Python. Sous WSL2, `date +%s`, `SECONDS`, `EPOCHREALTIME` reculent.
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
- ⚠️ `cypher/anglais/` — `correspondance.cypher`, `contraintes.cypher` et `questions/fiche-schema.en.md` sont produits
  de `correspondance.toml` par `uv run --directory banc python -m banc anglais` : jamais édités à la main (les tests
  « à jour » de `banc/tests/test_correspondance.py` échouent). `renommer.cypher` vaut dans les deux sens : rien de
  propre à une langue, tout passe par `$cartes[$langue]`.
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
  Depuis le 2026-10-17 (T7.1), `questions/consigne-contexte.md` aussi : la consigne d'une technique sans outil.
- ⚠️ `questions/fiche.cypher` — chaque requête cite en commentaire (`// fiche : « … »`) la phrase exacte de
  `questions/fiche-schema.md` qu'elle prouve et recopie ses valeurs dans l'ordre de la fiche (`valeurFiche`,
  `nombreFiche`) : `banc/tests/test_fiche_cypher.py` le vérifie sans base. Corriger la fiche, c'est corriger sa requête
  dans le même commit. Le CSV du commit figé écrit 0, et non l'absence, pour la puissance ou la précision de 18 attaques
  récentes, et la base n'a que 10 méthodes d'apprentissage : la fiche disait le contraire (vu le 2026-10-10, T7.3).
- ⚠️ `questions/recherche.cypher` — `SEARCH` (Cypher 25 seulement) veut un `MATCH` à une seule variable, sans autre
  élément, et un `LIMIT` ; le nom d'index ne peut pas être un paramètre (Cypher Manual, lu le 2026-10-17). Le `MATCH`
  du parcours ne garde pas l'ordre des espèces : le `RETURN` le refait. Ni `embedding` ni nœud entier dans aucun
  `RETURN`, sous-requêtes comprises, et pas de point-virgule final : `banc/tests/test_recherche_cypher.py` (T7.2).
- ⚠️ `questions/recherche.cypher`, `banc/src/banc/essai_recherche.py` — `read-cypher` préfixe lui-même `EXPLAIN`
  pour classer une requête (neo4j-mcp v1.6.0, `internal/database/service.go`, `GetQueryType`) : un « EXPLAIN de
  recherche.cypher » passé par lui deviendrait « EXPLAIN EXPLAIN ». Contrôle sur un vecteur factice, avant tout
  encodage ([plan 003, D6](specs/003-graphrag-descriptions/plan.md), précision du 2026-10-18).
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
  regex s'écrit par sa séquence d'échappement, sinon Write la rend invisible (vu encore le 2026-10-08). Un titre de
  jeu qui contient une espèce (« Let’s Go, Pikachu », graphie de la base ; les agents la recopient sans virgule ou
  avec l'apostrophe droite) est masqué par autant d'espaces, pour que les autres citations gardent leur place (pilote,
  2026-10-10).
- ⚠️ `banc/src/banc/notation.py` — tout doute mène à « à revoir », jamais à « juste » : un « juste » à tort gonfle
  un score en silence (revue adverse du 2026-10-08 : 12 constats). La notation ne lit que `banc/src/banc/trace.py`,
  jamais le JSONL ni le format d'un client. Un message d'erreur de Neo4j recopie la requête, noms compris : un appel
  en erreur n'est jamais une source. Un test d'exclusion emploie une entrée que le code accepterait sans elle.
- ⚠️ `banc/src/banc/trace.py` — contrat lu par la notation (choix de Julien du 2026-10-08) : T3.1 l'entoure (JSONL,
  masquage, mesures) ; y ajouter un champ, oui ; en changer le sens, jamais sans revoir `notation.py`.
- ⚠️ `infra/reveil-aura/` — le job : secret monté en fichier par Cloud Run, sous un compte qui ne lit que lui ; tout
  message passe par `masquer` (`infra/reveil-aura/reveil.py:161`) ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md)).
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
  `NEO4J_MCP_LOG_LEVEL` vaut `warning`, pas `warn` (invalide : retour à `info`, qui écrit chaque requête en clair
  sur stderr, et ADK le laisse passer jusqu'au terminal du banc ; vu au pilote, 2026-10-10).
- ⚠️ `scripts/mcp-neo4j.sh` — son stdout masqué est le canal MCP, un message JSON par ligne : le filtre rend chaque
  ligne aussitôt (`$| = 1` de perl), sinon le client attend sa réponse sans fin ; il ne peut pas non plus retirer
  une ligne (même blocage) ; l'identifiant lui arrive par l'environnement, jamais en argument (`ps`) (vu le 2026-10-08).
- ⚠️ `scripts/mcp-neo4j.sh` — le masque du stdout ôte aussi les instructions du serveur (elles citent `get-schema`) :
  Claude Code 2.1.292 les injecte dans la conversation alors que l'outil est masqué ; perl ôte ce membre sur la seule
  ligne qui porte `serverInfo`. Chaque cellule ne reçoit que la consigne, la fiche et les descriptions des outils
  (choix de Julien ; [plan 002, D1](specs/002-agent-text-to-cypher/plan.md), T4.1, vu le 2026-10-09).
- ⚠️ `banc/mesures/revues.toml` — `gel` s'écrit en date-heure sans fuseau (`gel = 2026-10-20T10:00:00`), tout en
  haut, avant toute table, avec la campagne pilote, exigée (`pilote = "pilote"`) : une date seule ou un gel sans
  pilote laisseraient réutiliser une décision du pilote. Une décision se corrige ou se complète dans le fichier,
  jamais par une seconde décision au même cas (refusée) ([plan 002, D4](specs/002-agent-text-to-cypher/plan.md),
  vu le 2026-10-08).
- ⚠️ `banc/tests/` — gitleaks (pre-commit) prend un SHA de 40 caractères hexadécimaux affecté à un nom qui contient
  « api » (`commit_pokeapi="…"`) pour une clé d'API (generic-api-key) : lire le commit par
  `banc.mesures.commit_pokeapi()` plutôt que l'écrire (commit refusé le 2026-10-08). Même règle pour une clé en
  « …tokens » dont la valeur est une expression (`self.ecrit_5m + self.ecrit_1h`, sous la clé d'écriture en cache de
  l'API) : passer par une variable ou une propriété ; ne pas recopier non plus la forme fautive dans la doc (commit
  refusé deux fois le 2026-10-09).
- ⚠️ `banc/src/banc/isolement.py` — ADK (`mcp` 2.3.0, `client/stdio.py`) lance le serveur MCP dans sa propre session
  et, sans `env` explicite, ne lui passe que HOME, LOGNAME, PATH, SHELL, TERM et USER : donner la liste blanche à
  ses paramètres de lancement, et arrêter le lanceur par son propre groupe (relevé le 2026-10-08, réglé en T4.2 dans
  `banc/src/banc/cellule_adk.py`).
- ⚠️ `banc/src/banc/mesures.py` — `ModelUsage` de Claude Code (SDK 0.2.164) et l'usage d'ADK (2.11.0) ne séparent
  pas l'écriture du cache à 5 min et à 1 h, facturée 1,6 fois plus cher à 1 h : sa part vient des messages de
  l'assistant ou de `ContextCacheConfig`. `output_tokens` d'Anthropic comprend la réflexion,
  `candidates_token_count` d'ADK non. `ModelUsage` cumule en outre toute la session : le tour se tire de deux
  relevés par `usage_du_tour`, sinon Q18 compte Q2 (vu le 2026-10-08).
- ⚠️ `banc/src/banc/mesures.py` — `ecrire` ajoute des lignes au CSV d'une campagne : un test qui réécrit un CSV le
  supprime d'abord, sinon les lignes se doublent et la revue refuse « ligne en double » (vu le 2026-10-13, T1.1).
- ⚠️ `banc/tests/test_lanceur.py` — un faux outil écrit en Python ajoute `LC_CTYPE` à son `os.environ` quand aucune
  locale n'est fixée (PEP 538) : lire l'environnement reçu à l'exec dans `/proc/self/environ` (vu le 2026-10-07).
- ⚠️ `banc/src/banc/isolement.py` — Claude Code choisit son accès dans un ordre fixe : fournisseur cloud
  (`CLAUDE_CODE_USE_VERTEX`…), puis `ANTHROPIC_AUTH_TOKEN`, puis `ANTHROPIC_API_KEY`… Une variable Vertex dans la
  liste blanche ferait passer la cellule par Vertex malgré la clé. La source réelle se lit dans le message `init`
  (`apiKeySource`), que la sonde exige à `ANTHROPIC_API_KEY` ([ADR-0011](adr/0011-infra-claude-par-api-anthropic.md), vu le 2026-10-08).
- ⚠️ `banc/prix.toml` — l'identifiant d'un modèle dépend de la voie : `claude-haiku-4-5-20251001` sur l'API,
  `claude-haiku-4-5@20251001` chez Google ; Sonnet 5.5 garde `claude-sonnet-5-5` des deux côtés, d'où la clé `acces`
  (vu le 2026-10-08).
- ⚠️ `banc/src/banc/cellule_sdk.py` — Claude Code 2.1.292 : `--max-budget-usd` montre son budget à l'agent après chaque
  appel (le compter hors du client) ; `model_usage` cumule la session et oublie l'appel coupé par `interrupt()` (le flux
  le donne) ; `init` annonce `effort: null` alors que la requête porte l'effort ; `receive_response()` est un générateur
  déclaré `AsyncIterator`, à refermer par `aclosing` (vu le 2026-10-09, [plan 002, D13](specs/002-agent-text-to-cypher/plan.md)).
- ⚠️ `banc/tests/fixtures/` — un faux outil lancé en processus hérite du HOME et du `CLAUDE_CONFIG_DIR` du poste : n'y lire
  que les dossiers du bac (un `rglob` de tout le HOME coûtait 7 s par test, vu le 2026-10-09).
- ⚠️ `banc/src/banc/isolement.py` — sans locale, Python fixe `LC_CTYPE` (PEP 538) et l'ajoute à l'environnement de tout
  ce qu'il lance : la liste blanche la déclare (`C.UTF-8`), sinon elle n'est plus exacte (vu le 2026-10-09).
- ⚠️ `banc/src/banc/cellule_adk.py` — ADK 2.11.0 : le délai de `StdioConnectionParams` borne aussi chaque appel d'outil
  (5 s par défaut) ; une consigne en texte est un gabarit (`{rang}` de la fiche → KeyError) : la passer par une
  fonction ; ADK relit la liste des outils à chaque appel du modèle (`tool_list_cache_ttl_seconds`) et relance seul un
  serveur perdu ; en flux, Gemini joint l'usage aux morceaux partiels : ne compter que l'événement final ; `run_config`
  ne réexporte pas `StreamingMode` (mypy strict) (vu le 2026-10-09).
- ⚠️ `banc/src/banc/cellule_adk.py` — google-genai 2.28.0 passe par aiohttp dès qu'il est installé : un crochet httpx ne
  voit rien ; ses reprises se lisent dans le journal de tenacity (`google_genai._api_client`, niveau INFO), qui note
  aussi sa reprise d'une erreur de connexion d'aiohttp (1 à 10 s). Le SDK Anthropic 1.11.0 a un middleware public,
  appelé à chaque tentative (`retries_taken`) (vu le 2026-10-09).
- ⚠️ `banc/src/banc/encodage.py` — google-genai 2.28.0 envoie `gemini-embedding-001`, et lui seul, par `:predict`
  (`instances[]`) ; tout autre modèle Gemini d'embeddings passe par `:embedContent`, sous une autre forme de corps et de
  jetons (`_transformers.t_is_vertex_embed_content_model`) : changer de modèle change le contrat, et les tests de la
  fausse API. `google.auth.default()` rend un `Credentials` de base : `with_quota_project` n'existe que sur
  `CredentialsWithQuotaProject` (vu le 2026-10-17, T8.1).
- ⚠️ `banc/tests/fixtures/` — Vertex hermétique : une ADC `authorized_user` impose le vrai point de jeton de Google ;
  une ADC de compte de service factice (clé RSA générée, `token_uri` vers la fausse API) l'évite, et
  `GOOGLE_VERTEX_BASE_URL` pointe google-genai vers la fausse API. google-genai ne lit pas un commentaire SSE
  (`: ping`) : UnknownApiResponseError (vu le 2026-10-09).
- ⚠️ `banc/src/banc/cellule_adk.py` — ADK 2.11.0 : une erreur annoncée dans un flux ouvert remonte en
  `httpx2.ResponseNotRead`, sans l'erreur d'origine ; une réponse de Gemini sans aucune part sort sans contenu
  (MALFORMED_FUNCTION_CALL) ou ne sort pas du tout (STOP vide) : l'usage se compte dans `after_model_callback`, qu'ADK
  appelle pour chaque réponse, morceaux compris, avant de décider d'en faire un événement ; une connexion MCP coupée par
  un délai laisse sa session hors du pool d'ADK, que `McpToolset.close()` ne ferme pas : annuler les tâches nées pendant
  la conversation, et elles seules (vu le 2026-10-09, revue adverse).
- ⚠️ `banc/tests/fixtures/` — un flux coupé se simule en chunked : sans, fermer la connexion termine normalement un corps
  sans longueur. Le faux serveur MCP lancé dans le processus des tests hérite de l'environnement du poste, secrets
  compris : n'en écrire que les noms (`noter_env` pour le test de la liste blanche) (vu le 2026-10-09).
- ⚠️ `banc/src/banc/orchestration.py` — chaque cellule tourne dans sa propre session : un Ctrl-C au terminal ne l'atteint
  pas, l'orchestration l'arrête elle-même (SIGTERM au groupe, SIGKILL après la grâce ou à la première interruption, puis
  les groupes de ses descendants relevés dans `/proc`, car le serveur MCP d'ADK vit dans sa propre session) ; SIGTERM et
  SIGHUP au harnais suivent ce chemin, SIGHUP restant ignoré sous nohup. Claude Code 2.1.292 garde son serveur MCP dans
  son groupe, celui de la cellule (relevé T4.3). Une trace complète restée sans ligne se note, jamais ne se rejoue (un
  échec effacé fausserait le score, revue adverse) ; une trace fautive (un tour après un tour sans réponse) bloque la
  reprise jusqu'à ce qu'on la renomme en `.jsonl.ecartee`. Lire `/proc/<pid>/stat` d'un processus qui s'achève lève
  ESRCH (`ProcessLookupError`). La progression n'affiche jamais la note : revue à l'aveugle (vu le 2026-10-09).
- ⚠️ `scripts/transactions.sh` — neo4j-mcp v1.6.0 (mcp-go v0.56.0), stdin fermé, attend la fin des appels en cours, et son
  driver Go ne voit une annulation qu'au morceau suivant du serveur : une lecture lente survit à sa cellule. SHOW et
  TERMINATE TRANSACTIONS se composent (YIELD aux colonnes nommées, puis RETURN, exigés ; `metaData` ne sort que par
  YIELD) ; TERMINATE est asynchrone, d'où les relectures. Un résultat vide de cypher-shell n'écrit rien, pas même
  l'en-tête. Mode lecture et droit d'arrêter sur Aura Free : vérifiés le 2026-10-10 (`banc essai-serveur`, T7.4) ; un
  serveur tué voit sa lecture arrêtée par Aura elle-même, le script reste pour celui qui survit à sa cellule.
- ⚠️ `banc/src/banc/essai_serveur.py` — `stdio_client` de `mcp` 2.3.0 lance le serveur dans sa propre session sans
  rendre son processus : son groupe se lit dans `/proc` (`orchestration.descendants`), avant et après l'ouverture, pour
  ne tuer que lui. anyio regroupe les erreurs de ses tâches (ExceptionGroup), et `return` est interdit dans un
  `except*`. La lecture lente s'étalonne sur la base : bornée à quelques minutes si l'arrêt échouait (vu le 2026-10-10).
- ⚠️ `banc/src/banc/__init__.py` — le filtre de l'avertissement `[EXPERIMENTAL]` d'ADK reste ici, avant tout import d'ADK :
  ADK avertit dès son import (classe expérimentale PLUGGABLE_AUTH créée au chargement) ; posé dans le `main()` d'une
  cellule, il arrivait trop tard (bruit vu en T5.1, corrigé le 2026-10-10).
- ⚠️ `banc/src/banc/cellule_adk.py` — ADK 2.11.0 journalise deux fois l'épuisement des appels du modèle, trace comprise
  (`google_adk.google.adk.workflow._node_runner`, `google_adk.google.adk.runners`), `LlmCallsLimitExceededError` pour
  erreur : `SansLesToursEpuises` ne retire que ces enregistrements, et la cellule ne recopie plus cet événement. Le
  vérifier en lançant la cellule comme l'orchestration (sous-processus) : en processus, rien n'est filtré (2026-10-10).
- ⚠️ `banc/tests/test_cellule_adk.py` — un port « libre » se prend une fois la fausse API lancée (`port_libre()`) : avant,
  le système peut redonner ce port à la fausse API, et la connexion qu'on voulait refusée aboutit (vu le 2026-10-10).
- ⚠️ `cypher/00-contraintes.cypher` — `standard-folding` d'Aura Free : analyseur standard anglais qui retire les accents,
  donc mots vides anglais ôtés (« a », « in », « on »…) et symboles hors ASCII découpés (♀, ’) ; un nom exact se cherche
  par égalité, pas par l'index plein texte (vu le 2026-10-10).
- ⚠️ `scripts/charger.sh` — `--sonde-renommage` : l'`EXPLAIN` d'une écriture passe en `--access-mode read` sur Aura Free
  (planifiée, jamais exécutée) ; Cypher 25 dynamique et `apoc.refactor.rename.*` y sont tous deux planifiés (2026-10-10).
- ⚠️ `banc/tests/test_orchestration.py` — un test qui envoie un signal au processus de pytest pose d'abord un gestionnaire
  refuge : sinon, une mutation qui retire celui du harnais tue pytest. Une mutation tuée au délai laisse ses fausses
  cellules dormir 600 s dans leur session : les arrêter par leur pid (vu le 2026-10-09).
- ⚠️ `.github/workflows/ci.yml` — la CI ne reçoit aucun secret et ne joint ni Google Cloud, ni Anthropic, ni Aura : ses
  tests ne parlent qu'à des faux, et un test qui exige un vrai service reste hors CI. Le hook gitleaks du pre-commit ne
  lit que les changements indexés (`--staged`) : la CI scanne tout l'historique avec le binaire de la même version,
  vérifié par son empreinte. GitHub Free et dépôt privé : la CI ne bloque pas une fusion, `gh pr checks` le fait (NEO-25).
- ⚠️ `banc/tests/` — un test qui veut un outil absent du PATH pointe le PATH vers un dossier vide, jamais vers
  `/usr/bin:/bin` : les machines de la CI (ubuntu-24.04) y ont leur propre `gcloud`. Vu le 2026-10-10 à la première
  exécution de la CI (`test_outils_des_agents`), alors que la suite passait sur le poste, même sans HOME ni PATH.
- ⚠️ `infra/coupure-vertex/` — une alerte sur journaux tout juste créée ne voit rien pendant quelques minutes : le
  premier essai de coupure, 75 s après la création des alertes, n'a envoyé aucun e-mail ; le second, 8 min après, en a
  envoyé un dans la minute (2026-10-10). Le déclencheur Eventarc est refusé quelques minutes après l'activation de
  l'API (« Eventarc service agent is not ready ») : `deploy.sh` réessaie. gcloud n'a pas d'option pour détacher un
  sujet Pub/Sub d'un budget : console. Les tests cherchent le gestionnaire du journal par son format : pytest 9 ajoute
  ses collecteurs aux journaux qui ne remontent pas à la racine (`propagate = False`).
- ⚠️ `infra/reveil-aura/deploy.sh` et `infra/coupure-vertex/deploy.sh` — le composant `beta` de gcloud passe à l'état
  « Update Available » dès qu'une version plus récente de gcloud sort : un test contre « Installed » seul arrêtait le
  déploiement (vu le 2026-10-10, gcloud 587 face à 588).
- ⚠️ `cypher/00-contraintes.cypher`, `scripts/charger.sh` — l'`EXPLAIN` d'un `CREATE VECTOR INDEX` ne valide pas ses
  options : une option inconnue, une quantification invalide y sont planifiées (sondé sur Aura le 2026-10-13). `--explain`
  ne prouve que la syntaxe ; seule `scripts/verifier.sh --section embeddings` contrôle dimension, similarité et
  quantification, une fois l'index créé.
- ⚠️ `cypher/00-contraintes.cypher` — un index ajouté exige son nom anglais dans `[index]` de
  `cypher/anglais/correspondance.toml`, puis `banc anglais`, dans le même commit : sinon `TraductionError` et
  `test_produits_a_jour` rouge. `banc/tests/schema_francais.py` lit les noms par une expression qui ne connaît que
  `FULLTEXT` et `VECTOR` : un autre genre d'index y serait invisible. `charger.sh --explain` nomme une requête par le
  commentaire collé au-dessus (`lire_requetes`) : les commentaires vont dans l'en-tête, suivi d'une ligne vide (T4.1).
- ⚠️ `logs/outils/` — un script lancé par `uv run --directory banc` résout ses chemins relatifs depuis `banc/`, et y
  écrirait ses fichiers : lui passer des chemins absolus (scratchpad). Une mutation passe par
  `logs/outils/mutations/mutations.py` (motif unique, copie d'abord, restauration dans un `finally`, empreinte
  revérifiée) : faite à la main, un échec laissait le fichier muté (vu le 2026-10-13).
- ⚠️ `logs/outils/mutations/mutations.py` — Python valide un `.pyc` par la date (à la seconde) et la taille de sa
  source : deux mutations de même taille, dans la même seconde, faisaient tourner le code de la précédente ; une
  mutation passait pour survivante, ou pour tuée à tort. L'outil n'écrit plus de bytecode, date chaque fichier muté
  par l'empreinte de son contenu et rend sa date au fichier restauré (vu le 2026-10-18, T11.2).
- ⚠️ `logs/outils/mutations/mutations.py` — pendant un lancement, ni commit ni édition du fichier visé : le hook
  pre-commit met de côté les changements non indexés, fichier muté compris, et les remet après, au risque de
  rétablir la mutation après la restauration ; une édition serait écrasée par le fichier tel qu'il a été lu
  (relevé le 2026-10-18).
- ⚠️ `banc/tests/test_charger_sh.py` — les faux `gcloud` et `cypher-shell` sont du code Python dans des chaînes, où un
  saut de ligne s'écrit déjà échappé : un remplacement par script qui vise ce code rate son motif. Écrire le motif en
  chaîne brute, sans barre oblique finale (vu le 2026-10-13).
- ⚠️ `cypher/07-embeddings.cypher`, `scripts/charger.sh` — `charger.sh` saute `07` quand aucune description n'est sans
  vecteur (`a_encoder`) : ce que `07` fait d'autre que l'encodage (l'attente de l'index) ne se fait alors pas, et
  `a_encoder` le refait lui-même (`db.awaitIndexes`). Toute requête ajoutée à `07` relève de la même règle (T5.1).
- ⚠️ `scripts/commun.sh` — `cypher-shell` 2026.09.0, `:param` sur stdin (`cypher_fichier_avec_jeton`) : la valeur
  n'est pas réécrite dans la sortie, et la première requête en erreur arrête la suite, code 1 (sondé le 2026-10-13) ;
  mais `:param` s'évalue côté serveur, le jeton arrive chez Aura en littéral (vu le 2026-10-12,
  [ADR-0019](adr/0019-infra-jeton-vertex-du-plugin-genai.md)).
- ⚠️ `banc/src/banc/cellule_graphrag.py` — `ClientSession.call_tool` de mcp 2.3.0 relit la liste des outils au premier
  appel d'un outil qu'il n'a pas vu sur la session (`validate_tool_result`) : la lire avant le chrono, sur la même
  session (`_connecter` de `banc.cellule_adk`), sinon elle tombe dans le temps mesuré. Un serveur mort lève `MCPError`
  « Connection closed », à l'appel en cours comme au suivant. Aucun test ne prouve `boite.close()` :
  `_arreter_les_restes` arrête aussi le serveur (mutation survivante, de même dans `banc/src/banc/cellule_adk.py`)
  (vu le 2026-10-18, T9.1).
- ⚠️ `banc/src/banc/cellule_graphrag.py` — l'appel au modèle passe par `_lire` de `banc/src/banc/cellule_adk.py`, qui
  pose sa propre échéance (envoi du message, plus le délai) : sous celle du tour GraphRAG, posée avant la recherche et
  donc plus tôt, l'annulation traverse `_lire` en `CancelledError`, et c'est l'échéance du tour qui la note en
  « délai ». Ne pas rattraper `CancelledError` dans la rédaction (`test_le_delai_couvre_la_recherche`, T10.1).
- ⚠️ `banc/src/banc/controle_traces.py`, `banc/tests/test_controle_traces.py` — neo4j-mcp v1.6.0 écrit un vecteur
  stocké (`VECTOR`) sous la forme `{"Elems": [...]}`, en JSON indenté, un nombre par ligne ; dans la ligne de la trace,
  ces sauts de ligne sont échappés (`\n`). Un contrôle ou un test de vecteur vise cette forme, pas une liste nue :
  `AVEC_VECTEURS` de `banc/tests/test_cellule_graphrag.py` ne sert qu'au garde-fou du coût, qui ne lit que la
  longueur. Relevé en lecture sur Aura le 2026-10-18 (T15.1).
