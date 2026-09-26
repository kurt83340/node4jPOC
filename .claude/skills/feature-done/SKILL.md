---
name: feature-done
description: Marque une feature comme livrée. Coche dans .claude/docs/ROADMAP.md, ajoute entry dans .claude/docs/CHANGELOG.md, met à jour .claude/docs/HANDOFF.md, suggère ADRs si décisions tech structurantes, vérifie que .claude/docs/code-map.md est à jour, propose la PR GitHub (gh — 1 spec = 1 PR, squash). À invoquer après livraison d'une feature (tous les tasks de specs/00X/tasks.md cochés).
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git status), Bash(git log:*), Bash(git diff:*), Bash(date:*)
disable-model-invocation: false
---

# /feature-done — Livraison d'une feature

> **Quand ne PAS utiliser** : session finie mais feature en cours → `/handoff` · tasks restants →
> continuer `/feature` · une décision isolée à documenter → `/adr`.
> **Réversibilité** : 🟢 édite ROADMAP/CHANGELOG/HANDOFF/spec frontmatter (ADR délégué à `/adr`) —
> undo : `git checkout --` des fichiers docs touchés.

Ton rôle : finaliser proprement une feature en synchronisant tous les fichiers vivants.

## Usage

```
/feature-done <spec-id>
# Exemple : /feature-done 001-erp-connector
```

## Étape 1 — Vérifier la spec

1. Lire `.claude/docs/specs/<spec-id>/tasks.md`
2. Vérifier que TOUS les tasks sont cochés `[x]`
3. Vérifier que le DoD est rempli
4. Si non → demander à l'user "Es-tu sûr que la feature est livrée ? Tasks restants : X, Y"

## Étape 2 — Détecter les décisions tech à promouvoir en ADR

Scan `.claude/docs/specs/<spec-id>/plan.md` pour mots-clés :

- "choisi", "retenu", "vs", "plutôt que", "rejeté"
- "decision", "pattern", "lib"

Si trouvé → liste les décisions au user :

```
🔍 Décisions tech détectées dans plan.md :
1. "On choisit httpx au lieu de requests parce que…"
2. "Pattern retry avec tenacity (3x backoff)"

Promouvoir en ADR ?
- (a) ADR-00XX-feature-001-http-client (utile si lib réutilisée ailleurs)
- (b) ADR-00YY-feature-001-retry-pattern
- (c) Laisser dans plan.md (décisions trop locales)
```

**Règle décision** (cf `.claude/docs/adr/README.md`) :

- Décision **cross-feature** ou qui **survit à la feature** → ADR global (créer fichier)
- Décision **locale à cette feature uniquement** → laisser dans `plan.md` section `## Décisions`

## Étape 2bis — Promotion en ADR : **déléguer à `/adr`** (ne pas ré-implémenter)

Pour chaque décision que l'user valide en ADR, **invoquer le skill `/adr`** :

```
/adr <scope> "<titre dérivé de la décision>"
```

`/adr` est le **seul foyer** de la logique ADR — il gère tout : numérotation `00XX`, création
du fichier (frontmatter + structure), index `adr/README.md`, pattern `supersede` (si la décision
remplace une ancienne), append `CHANGELOG.md` section `Decided`, et mise à jour du status de la
leçon source si la décision vient d'une entry `.claude/docs/lecons.md` (`🆕 new` → `📜 → ADR-00XX`).

→ Ici on se contente de **détecter + proposer** (Étape 2) puis **déléguer**. On ne crée PAS le
fichier ADR ni n'édite `adr/README.md`/`lecons.md` à la main (ce serait dupliquer `/adr` = drift).
C'est le même pattern que `/pivot` Étape 7 et `/lecon promote`, qui délèguent déjà à `/adr`.

## Étape 3 — Update .claude/docs/ROADMAP.md

Trouver la ligne de `<spec-id>` **quel que soit son état actuel** — `[ ]` (jamais marquée en
cours) **ou** `[~] … **EN COURS** X/Y tasks` (démarrée via `/spec` Étape 5). Machine à états :
`[ ] → [~] → [x]`.

- Passer l'état à `[x]` : `- [x] [<spec-id>](...) — livré YYYY-MM-DD`
- Retirer le **gras** `**EN COURS**` s'il était présent (plus en cours)
- **Sync frontmatter** de `specs/<spec-id>/spec.md` : `status: done` + `progress: Y/Y` (source
  machine-readable — `/doc-health` flagge toute ROADMAP incohérente avec lui)

## Étape 4 — Append entry dans .claude/docs/CHANGELOG.md

Format Keep a Changelog dans la section `## [Unreleased]` — section `### Added` uniquement :

```markdown
### Added

- <nom feature> ([spec](specs/<spec-id>/spec.md))
- Tests : X tests verts, coverage Y%
```

> ℹ️ La section `### Decided` (liens ADR) est écrite par **`/adr`** (Étape 2bis), pas ici —
> ne pas la dupliquer, sinon double entry dans le CHANGELOG.

## Étape 5 — Update .claude/docs/HANDOFF.md

Section "Status" :

- ✅ Feature `<spec-id>` livrée YYYY-MM-DD

Section "Next" :

- Suggérer la feature suivante (depuis ROADMAP)
- Ou suggérer phase suivante

## Étape 6 — Update code-map (si applicable)

⚠️ Seulement si la feature a introduit du **non-déductible** : nouvelle règle de
couplage, contrainte d'archi, ou gotcha. Le rôle des fichiers / leurs imports / leurs
tests ne se documentent PAS ici (Claude les retrouve seul, et ça drifterait).

- Nouvelle **règle de couplage** (ex. « le nouveau module ne doit pas importer X ») ? →
  `.claude/docs/code-map.md` (auto-chargé : budget < 3k tokens)
- Nouveau **gotcha** rencontré pendant la feature ? → `.claude/docs/code-map-gotchas.md`
  (1 bullet citant le fichier/dossier en backticks + `fichier:ligne` — injecté par le hook
  à l'édition de ce fichier ; **jamais** dans code-map.md, qui est auto-chargé)
- Découpage en sous-systèmes changé ? → revoir la vue macro
- Présenter le diff au user ; si refacto large → `/codemap` (régénère macro + détecte violations)

## Étape 7 — Archiver les idées promues (si applicable)

Si la feature est issue d'une `.claude/docs/idees/YYYY-MM-DD-titre.md` :

1. Update le statut dans l'idée : `Statut: 💡 Backlog` → `✅ Promu en spec 00X — livré YYYY-MM-DD`
2. Optionnel : déplacer vers `.claude/docs/idees/archived/` (créer le dossier si besoin)

## Étape 8 — Suggérer commit + PR + tag

```bash
git status --short                      # relire : aucun fichier sensible / hors périmètre
git add <fichiers de la feature> .claude/docs/
git commit -m "feat(<spec-id>): <titre court>"
```

**PR GitHub (si remote + `gh` dispo)** — règle git-workflow : **1 spec = 1 PR, squash merge** :

```bash
git push -u origin feature/<spec-id>   # push = permission « ask » → confirmation user
gh pr create --title "feat(<spec-id>): <titre court>" \
  --body "Spec : .claude/docs/specs/<spec-id>/spec.md · Tasks X/X ✅ · Tests : <résultat>"
```

- CI verte obligatoire avant merge ; squash merge (1 commit par feature dans main).
- Pas de remote / pas de `gh` / solo sans PR → rester sur le commit local, et si release :

```bash
git tag -a v$(date +%Y.%m.%d-%H%M) -m "Feature <spec-id> livrée"
```

## Sortie attendue

```
✅ Feature 001-erp-connector marquée comme livrée

📝 Fichiers mis à jour :
- .claude/docs/ROADMAP.md : [~] → [x] livré 2026-06-10
- .claude/docs/CHANGELOG.md : entry "Client SAP B1 (auth + fetch + pagination)" ajoutée
- .claude/docs/HANDOFF.md : status mis à jour
- .claude/docs/code-map.md : section sap_connector ajoutée

📚 ADRs proposés :
- ADR-0004-mvp-pattern-retry-tenacity ← user à valider

🔀 PR : feature/001-erp-connector → main proposée (gh pr create) — squash après CI verte

🚀 Suivant : démarrer feature 002-notion-writer ? (lance /spec ou créer manuellement)
```

## Anti-patterns

- ❌ Cocher [x] sans vérifier le DoD
- ❌ Promouvoir trop d'ADRs (chaque décision **locale** = pas un ADR — garder dans plan.md)
- ❌ Auto-commit sans demander
- ❌ Ajouter des descriptions fichier-par-fichier dans code-map.md (déductible — Claude le retrouve seul)
- ❌ Ré-implémenter la création d'ADR ici (fichier + `adr/README.md` + supersede) — **déléguer à `/adr`**
- ❌ Dupliquer la section `### Decided` du CHANGELOG (c'est `/adr` qui l'écrit)

## Note : invocation par agent doc-maintainer

Tu peux aussi déléguer ce workflow à l'agent `doc-maintainer` (Task tool) qui scanne l'état + propose tous les diffs en une fois. Le skill `/feature-done` est l'invocation manuelle directe ; l'agent est la version "scan auto + tout proposer".
