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
- ⚠️ `banc/tests/test_lanceur.py` — un faux outil écrit en Python ajoute `LC_CTYPE` à son `os.environ` quand aucune
  locale n'est fixée (PEP 538) : lire l'environnement reçu à l'exec dans `/proc/self/environ` (vu le 2026-10-07).
