---
name: adr
description: Gère le cycle de vie complet des ADR (Architecture Decision Records) — capture (mode défaut), supersede (remplacement explicite d'un ADR existant), amend (un seul point remplacé, l'ancien ADR reste en vigueur), deprecate (marque comme à éviter sans remplacement), list (liste avec status). Décisions immuables, on ne modifie jamais (on supersede ; un amend n'ajoute qu'un bandeau daté).
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(find:*), Bash(date:*), Bash(ls:*), Bash(grep:*), AskUserQuestion
disable-model-invocation: false
argument-hint: "[capture|supersede|amend|deprecate|list] <args>"
---

# /adr — Cycle de vie complet des Architecture Decision Records

> **Quand ne PAS utiliser** : décision locale à UNE feature → § `## Décisions` de son `plan.md` ·
> simple observation/pattern à mûrir → `/lecon`.
> **Réversibilité** : 🟢 crée fichier + index — mais un ADR accepté est **immuable** : on ne
> supprime ni ne modifie, on `supersede <NN>` (le seul undo légitime) ; quand un seul point change,
> `amend <NN>` n'y ajoute qu'un bandeau daté.

Ton rôle : orchestrer le cycle de vie des ADR dans `.claude/docs/adr/`.

## Modes disponibles

| Mode                                        | Quand l'invoquer                                       |
| ------------------------------------------- | ------------------------------------------------------ |
| `/adr <scope> "<titre>"` (défaut = capture) | Capturer une nouvelle décision tech structurante       |
| `/adr supersede <NNNN> <scope> "<titre>"`   | Remplacer un ADR existant par un nouveau               |
| `/adr amend <NNNN> <scope> "<titre>"`       | Remplacer un seul point d'un ADR qui reste en vigueur  |
| `/adr deprecate <NNNN> "<raison>"`          | Marquer un ADR comme déprécié (à éviter, pas remplacé) |
| `/adr list [scope]`                         | Lister tous les ADRs avec status (optionnel filtre)    |

**Scopes valides** : `cadrage`, `mvp`, `feature-00X`, `infra`, `operations`

## Détection du mode

Si premier arg ∈ `{supersede, amend, deprecate, list}` → mode explicite.
Sinon → mode `capture` par défaut (premier arg = scope).

---

## MODE 1 : `capture` (défaut)

### Usage

```
/adr mvp "Stack BDD : Postgres vs SQLite"
/adr infra "Stockage secrets : 1Password vs Vault"
/adr feature-001 "Pagination cursor vs offset"
```

### Étape 1 — Calculer le numéro suivant

```bash
ls .claude/docs/adr/[0-9]*.md 2>/dev/null | sort -r | head -1
```

Numéro suivant = max(existant) + 1, formaté sur 4 chiffres (`0001`, `0002`, ...).

> ⚠️ **Mode agent-teams (plusieurs sessions Claude concurrentes)** : `max(existant) + 1` n'est
> **pas concurrent-safe** — deux agents créant un ADR en même temps prendraient le même `00XX`.
> Convention : **seul le lead crée les ADR et alloue les numéros**. Un worker qui identifie une
> décision structurante la **propose au lead** (ou la capture en `/lecon` 🆕 new), il ne lance
> pas `/adr` en parallèle.

### Étape 2 — Scanner ADRs existants (pour helper)

```bash
for f in .claude/docs/adr/[0-9]*.md; do
  [ -f "$f" ] || continue
  NUM=$(basename "$f" | cut -d'-' -f1)
  STATUS=$(sed -n 's/^status: *\([^ #]*\).*/\1/p' "$f" | head -1)
  TITLE=$(grep "^# " "$f" | head -1 | sed 's/^# //')
  echo "  $NUM | $STATUS | $TITLE"
done
```

Garder cette liste pour proposer en Étape 3 si supersede.

### Étape 3 — Collecter via AskUserQuestion

1. **Contexte** : pourquoi cette décision arrive ? (contraintes, déclencheur)
2. **Options considérées** : min 2 (toujours inclure "ne rien faire")
3. **Décision** : option retenue + raison
4. **Conséquences** : ✅ avantages + ⚠️ risques
5. **Supersede ?** (optionnel) : si oui, afficher la liste collectée Étape 2 (filtrée sur `status: accepted`), user choisit le numéro

### Étape 4 — Créer le fichier ADR

Path : `.claude/docs/adr/<NNNN>-<scope>-<titre-kebab>.md`

```markdown
---
status: accepted
scope: <scope>
phase: YYYY-Qn
supersedes: null # ou 00XX
---

# <NNNN> — <Titre>

**Statut :** Accepted
**Date :** YYYY-MM-DD
**Décideur :** <nom>

## Contexte

<...>

## Options considérées

- **Option A** : ...
- **Option B** : ...
- **Option C — ne rien faire** : ...

## Décision

<...>

## Conséquences

- ✅ <...>
- ⚠️ <...>

## Liens

- [spec / feature concernée](...)
```

### Étape 5 — Update `.claude/docs/adr/README.md` (index)

Ajouter ligne dans la table du scope :

```markdown
| [<NNNN>](<NNNN>-<scope>-<titre>.md) | <Titre court> | Accepted |
```

### Étape 6 — Si supersede choisi → invoquer mode `supersede` automatiquement

Cf MODE 2 ci-dessous.

### Étape 7 — Append .claude/docs/CHANGELOG.md section `Decided`

```markdown
### Decided

- <Titre décision> ([ADR-<NNNN>](adr/<NNNN>-<scope>-<titre>.md))
```

### Étape 8 — Si l'ADR vient d'une leçon : update .claude/docs/lecons.md

Si l'ADR est créé suite à `/lecon promote` :

- Trouver l'entry leçon source
- Update status : `🆕 new` → `📜 → [ADR-<NNNN>](../adr/<NNNN>-...md)`

---

## MODE 2 : `supersede`

### Usage

```
/adr supersede 0003 mvp "Nouvelle stack httpx (remplace requests)"
```

### Action

Combine MODE 1 (création nouvel ADR) + pattern supersede automatique :

1. Lance MODE `capture` avec le scope+titre fournis (frontmatter inclut `supersedes: 0003` auto-pré-rempli)
2. **Update l'ADR superseded (0003)** :
   - Frontmatter : `status: superseded` + `superseded_by: <nouveau NNNN>`
   - Ajouter en haut : `⚠️ SUPERSEDED by <NNNN>` (visible)
3. **Update `adr/README.md`** :
   - Retirer ligne de 0003 de sa table de scope
   - Ajouter dans section "archived / superseded" :
     ```
     | 0003 → NNNN | <pourquoi> | YYYY-MM-DD |
     ```

---

## MODE 3 : `amend`

### Usage

```
/adr amend 0009 infra "Claude par l'API Anthropic (remplace « tous sur Vertex »)"
```

### Quand

Un nouvel ADR remplace **un seul point** d'un ADR qui reste en vigueur pour tout le reste.
Différent de `supersede`, où toute la décision change : l'ancien garde `status: accepted`.

### Action

1. Lance MODE `capture` avec le scope+titre fournis ; frontmatter : `supersedes: null` et
   `amends: 0009` (auto-pré-rempli). Sa section « Décision » nomme le point remplacé.
2. **Dans l'ADR amendé (0009), un seul ajout**, en tête du corps, juste après le frontmatter. C'est
   la seule écriture permise dans un ADR accepté :

   ```
   > ⚠️ **Point remplacé** (YYYY-MM-DD) : « <le point> » → [ADR-NNNN](NNNN-<scope>-<titre>.md) : <la nouvelle règle, en une phrase>. Le reste de cet ADR reste en vigueur.
   ```

   Rien d'autre ne change : ni le frontmatter (`status: accepted`), ni le corps.

3. **Update `adr/README.md`** : la ligne de 0009 reste dans sa table, au statut
   `Accepted (point amendé par [NNNN](NNNN-<scope>-<titre>.md))` ; le nouvel ADR s'ajoute dans sa
   table de scope (Étape 5 du mode capture).
4. **CHANGELOG** : section `Decided`, comme le mode capture (Étape 7).

> Vécu (node4jPOC, 2026-10-08) : un ADR « Claude par l'API Anthropic » amende le protocole de
> mesure, qui faisait tout passer par Vertex ; le reste du protocole tient. Un supersede aurait
> archivé tout le protocole pour un seul point.

---

## MODE 4 : `deprecate`

### Usage

```
/adr deprecate 0005 "API tierce déprécié, on garde mais on n'élargit plus l'usage"
```

### Quand

Quand un ADR est encore valide MAIS on veut signaler "ne plus s'appuyer dessus". Différent de `supersede` (pas de remplaçant).

### Action

1. Lire `adr/<NNNN>-...md`
2. Update frontmatter : `status: accepted` → `status: deprecated`
3. Ajouter en haut du fichier :
   ```markdown
   ⚠️ **DEPRECATED** YYYY-MM-DD — <raison>
   ```
4. Update `adr/README.md` :
   - Conserver dans la table du scope mais changer "Accepted" → "Deprecated"
   - OU déplacer vers section "archived / superseded" selon préférence projet

---

## MODE 5 : `list`

### Usage

```
/adr list           # tous
/adr list mvp       # filtre sur scope mvp
/adr list accepted  # filtre sur status
```

### Action

```bash
# Format : NUM | scope | status | titre
for f in .claude/docs/adr/[0-9]*.md; do
  [ -f "$f" ] || continue
  NUM=$(basename "$f" | cut -d'-' -f1)
  SCOPE=$(sed -n 's/^scope: *\([^ #]*\).*/\1/p' "$f" | head -1)
  STATUS=$(sed -n 's/^status: *\([^ #]*\).*/\1/p' "$f" | head -1)
  TITLE=$(grep "^# " "$f" | head -1 | sed "s/^# ${NUM} — //")
  echo "$NUM | $SCOPE | $STATUS | $TITLE"
done | sort
```

Affichage formaté en table markdown.

---

## Règle clé : ADR vs `## Décisions` dans `plan.md`

| Niveau de décision                          | Où l'écrire                                      |
| ------------------------------------------- | ------------------------------------------------ |
| Cross-feature (impacte > 1 spec)            | ADR global `.claude/docs/adr/`                   |
| Survit à la mort de la feature              | ADR global `.claude/docs/adr/`                   |
| Locale à UNE feature (lib, pattern interne) | Section `## Décisions` dans `specs/00X/plan.md`  |
| Devient cross-feature plus tard             | **Promouvoir** depuis plan.md → créer ADR global |

---

## Anti-patterns

- ❌ Modifier un ADR existant : toujours en créer un nouveau, qui le supersede, ou qui l'amende (seul ajout permis :
  le bandeau daté du mode `amend`)
- ❌ Amender quand toute la décision change (c'est un supersede), ou amender sans bandeau dans l'ancien (son lecteur
  ignorerait qu'un point a changé)
- ❌ ADR sans frontmatter YAML (illisible machine, rate les audits)
- ❌ ADR pour décision locale à UNE feature (utiliser `## Décisions` dans plan.md)
- ❌ Numérotation reset entre projets/phases (séquentiel global du projet)
- ❌ Oublier d'update `adr/README.md` (index = source de vérité)
- ❌ Supersede sans archiver l'ancien dans le README
- ❌ Deprecate sans raison claire (pourquoi futur dev devrait l'éviter ?)
