# Gotchas — pièges non évidents (injectés à la demande)

> **Non auto-chargé** (budget contexte v1.4). Le hook `pretooluse-inject-codemap.py` injecte,
> à l'édition d'un fichier de code, UNIQUEMENT les entrées qui **le ciblent** — une fois
> par session et par fichier. Une entrée cible un fichier en citant en backticks un chemin, un
> nom de fichier ou un dossier : `` `src/sync/notion.py` ``, `` `notion.py` ``, `` `src/sync/` ``
> (un heading `### src/sync/` cible toutes ses entrées). Une entrée sans chemin cité n'est
> injectée que sous le heading « Globaux » — à garder rare et court.
> Un piège qui t'a coûté du temps → ici (1 bullet, `chemin:ligne` si possible). Décision structurante → ADR.

## Globaux (injectés pour TOUTE édition de code — max 5 lignes)

- ⚠️ Mesurer une durée (journal de chargement, temps de réponse du banc d'essai) : horloge monotone,
  `read -r t _ </proc/uptime` en bash (`scripts/charger.sh:118`), `time.monotonic()` en Python. Sous
  WSL2, l'horloge murale recule par à-coups : `EPOCHREALTIME`, `SECONDS` et `date +%s` donnent des
  durées fausses, voire négatives (« 0,-1 s » au go/no-go du 2026-09-30).

## Par zone

- ⚠️ `cypher/06-descriptions.cypher` — les outils d'écriture Write et Edit décodent la séquence
  d'échappement de l'espace fine insécable U+202F en vrai caractère, invisible : la formule de
  normalisation semble alors remplacer une espace par une espace. Écrire la séquence littérale via
  Python (`chr(92) + "u202F"`), puis vérifier que le fichier ne contient aucun `chr(0x202F)`. La
  formule doit remplacer `\n` ET U+202F ([plan 001, D4](specs/001-socle-donnees/plan.md)) : avec
  `\n` seul, 5 240 descriptions au lieu de 5 233.
- ⚠️ `scripts/charger.sh` — sur Aura, l'utilisateur et la base portent l'identifiant de l'instance,
  pas `neo4j` : les lire dans le secret (`NEO4J_USERNAME`, `NEO4J_DATABASE`), rien en dur. Toute sortie
  de `cypher-shell` passe par `filtrer` (mot de passe → arrêt, identifiant → ‹instance›) ; jamais de
  `set -x`, de `--debug`, ni de mot de passe en argument ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md)).
- ⚠️ `scripts/charger.sh` — `dbms.components()` annonce Neo4j « 5.27-aura » quand la console affiche
  2026.09 : ce n'est pas le signe d'un vieux Neo4j. Cypher 25 est disponible et déjà la langue par
  défaut de la base (`SHOW DATABASES`).
