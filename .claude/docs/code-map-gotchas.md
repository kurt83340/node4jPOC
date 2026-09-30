# Gotchas — pièges non évidents (injectés à la demande)

> **Non auto-chargé** (budget contexte v1.4). Le hook `pretooluse-inject-codemap.py` injecte,
> à l'édition d'un fichier de code, UNIQUEMENT les entrées qui **le ciblent** — une fois
> par session et par fichier. Une entrée cible un fichier en citant en backticks un chemin, un
> nom de fichier ou un dossier : `` `src/sync/notion.py` ``, `` `notion.py` ``, `` `src/sync/` ``
> (un heading `### src/sync/` cible toutes ses entrées). Une entrée sans chemin cité n'est
> injectée que sous le heading « Globaux » — à garder rare et court.
> Un piège qui t'a coûté du temps → ici (1 bullet, `chemin:ligne` si possible). Décision structurante → ADR.

## Globaux (injectés pour TOUTE édition de code — max 5 lignes)

_(aucun pour l'instant)_

## Par zone

- ⚠️ `cypher/06-descriptions.cypher` — les outils d'écriture Write et Edit décodent la séquence
  d'échappement de l'espace fine insécable U+202F en vrai caractère, invisible : la formule de
  normalisation semble alors remplacer une espace par une espace. Écrire la séquence littérale via
  Python (`chr(92) + "u202F"`), puis vérifier que le fichier ne contient aucun `chr(0x202F)`. La
  formule doit remplacer `\n` ET U+202F ([plan 001, D4](specs/001-socle-donnees/plan.md)) : avec
  `\n` seul, 5 240 descriptions au lieu de 5 233.
