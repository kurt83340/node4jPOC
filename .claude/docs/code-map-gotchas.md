# Gotchas — pièges non évidents (injectés à la demande)

> **Non auto-chargé** (budget contexte v1.4). Le hook `pretooluse-inject-codemap.py` injecte,
> à l'édition d'un fichier de code, UNIQUEMENT les entrées qui **le ciblent** — une fois
> par session et par fichier. Une entrée cible un fichier en citant en backticks un chemin, un
> nom de fichier ou un dossier : `` `src/sync/notion.py` ``, `` `notion.py` ``, `` `src/sync/` ``
> (un heading `### src/sync/` cible toutes ses entrées). Une entrée sans chemin cité n'est
> injectée que sous le heading « Globaux » — à garder rare et court.
> Un piège qui t'a coûté du temps → ici (1 bullet, `chemin:ligne` si possible). Décision structurante → ADR.

## Globaux (injectés pour TOUTE édition de code — max 5 lignes)

- ⚠️ {{Piège transversal : ex. les montants sont en centimes int partout — jamais float}}

## Par zone

- ⚠️ `{{src/module/fichier.py}}` — {{comportement contre-intuitif : ex. l'API renvoie 200 même en erreur, vérifier le body}}
- ⚠️ `{{src/autre/}}` — {{effet de bord : ex. modifier un fichier de ce dossier invalide le cache de X}}
