---
name: idee
description: Gère le cycle de vie des idées perso (.claude/docs/idees/) — capture (mode défaut, crée fichier daté), promote (vers une spec via /spec), discard (abandonné), archive (déplace les vieilles). Une idée = brainstorm interne (vs cadrage = input externe client). Symétrique avec /lecon.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(date:*), Bash(ls:*), Bash(mkdir:*), Bash(mv:*), AskUserQuestion
disable-model-invocation: false
argument-hint: "[capture|promote|discard|archive] <args>"
---

# /idee — Cycle de vie complet des idées perso

> **Quand ne PAS utiliser** : input reçu du client/collègue/ticket → `cadrage/` (provenance
> externe — ne JAMAIS mélanger) · observation/pattern technique → `/lecon`.
> **Réversibilité** : 🟢 crée `idees/YYYY-MM-DD-titre.md` — undo : `discard` ou supprimer le fichier.

Ton rôle : orchestrer le cycle de vie des fichiers dans `.claude/docs/idees/`.

## Modes disponibles

| Mode                                 | Quand l'invoquer                                     |
| ------------------------------------ | ---------------------------------------------------- |
| `/idee "<titre>"` (défaut = capture) | Capturer une idée brute → crée fichier daté          |
| `/idee promote <date>`               | Promouvoir une idée mûre vers une spec (via `/spec`) |
| `/idee discard <date> "<raison>"`    | Marquer une idée comme `❌ Abandonné`                |
| `/idee archive`                      | Déplacer toutes les idées discarded > 3 mois         |

## Différence avec autres dossiers (IMPORTANT)

- **`idees/`** = ce que **MOI** je brainstorme (input INTERNE, pas mûr)
- **`cadrage/`** = ce que le **CLIENT** me file (input EXTERNE, ticket, mail, doc)
- **`conception/research.md`** = brainstorm structuré projet (post-cadrage)
- **`specs/00X/research.md`** = brainstorm structuré feature

→ JAMAIS mélanger `idees/` et `cadrage/`.

## Détection du mode

Si premier arg ∈ `{capture, promote, discard, archive}` → mode explicite.
Sinon → mode `capture` par défaut (premier arg = titre).

---

## MODE 1 : `capture` (défaut)

### Usage

```
/idee "Sync inverse Notion → Prestashop"
/idee capture "Cache Redis pour latence < 50ms"
```

### Étape 1 — Vérifier que le dossier existe

```bash
mkdir -p .claude/docs/idees
```

### Étape 2 — Demander via AskUserQuestion

- **Source** : d'où vient l'idée ? (discussion avec X, après tel article, en codant, etc.)
- **Pitch** : 1-2 phrases — quelle valeur pour qui ?
- **Use case** : 1 scénario concret
- **Effort estimé** : `Petit (<1j)` / `Moyen (~1 sem)` / `Gros (>1 sem)`
- **Statut initial** : `💡 Backlog` (défaut), `À promouvoir en spec`, `Discuter avec X`

### Étape 3 — Créer le fichier

Path : `.claude/docs/idees/YYYY-MM-DD-<titre-kebab>.md`

```markdown
# Idée — <Titre>

**Date :** YYYY-MM-DD
**Source :** <discussion / article / en codant / ...>

## Pitch

<1-2 phrases. Quelle valeur pour qui ?>

## Use case

<Scénario concret>

## Effort estimé

<Petit | Moyen | Gros>

## Statut

💡 <Backlog | À promouvoir en spec | Discuter avec X | Abandonné>
```

### Étape 4 — Suggérer review si > 5 idées non décidées

→ "lance `/doc-health` pour review les idées en attente"

---

## MODE 2 : `promote`

### Usage

```
/idee promote 2026-05-22
```

### Étape 1 — Trouver l'idée

```bash
ls .claude/docs/idees/2026-05-22-*.md
```

Si plusieurs matches → demander à l'user de préciser le titre.
Si pas trouvée → demander la date exacte ou le titre.

### Étape 2 — Lire l'idée

Pour pré-remplir la spec :

- Pitch → vision/scope de la spec
- Use case → user story
- Effort → phase ROADMAP (Petit = Phase 1, Gros = Phase 2+)

### Étape 3 — Invoquer `/spec`

Lance `/spec "<titre de l'idée>"` avec pré-remplissage :

- `research.md` : copier le contenu de l'idée comme "Brainstorm initial"
- `spec.md` : pitch → vision, use case → US1
- `plan.md` : laissé vide à remplir
- `tasks.md` : laissé vide à remplir

### Étape 4 — Update l'idée source

```markdown
## Statut

✅ Promu en spec 00X-<kebab> — YYYY-MM-DD
```

Garder le fichier idée comme trace historique.

### Étape 5 — Suggérer la suite

→ "Spec 00X-<kebab> créée. Continue avec : remplir plan.md + tasks.md"

---

## MODE 3 : `discard`

### Usage

```
/idee discard 2026-05-22 "Trop coûteux pour la valeur"
```

### Action

1. Trouver le fichier idée par date
2. Update statut :

   ```markdown
   ## Statut

   ❌ Abandonné YYYY-MM-DD — <raison>
   ```

Garder le fichier (pas supprimer) pour trace historique.

---

## MODE 4 : `archive`

### Usage

```
/idee archive
```

### Action — batch cleanup

1. Scanner `.claude/docs/idees/*.md`
2. Pour chaque idée avec statut `❌ Abandonné` ou `✅ Promu` :
   - Si fichier > 3 mois → candidate pour archive
3. Présenter la liste à l'user : "X idées stables > 3 mois, archive ?"
4. Si OK :
   - Créer `.claude/docs/idees/archived/` (mkdir si besoin)
   - `mv` les fichiers candidates vers `archived/`

---

## Workflow de cycle de vie

```
   Capture (/idee "<titre>")
       ↓
   💡 Backlog
       ↓ (review : valeur claire, effort acceptable)
       ├─► ✅ Promu en spec 00X  (via /idee promote, déclenche /spec)
       └─► ❌ Abandonné          (via /idee discard)
       ↓ (post-décision, > 3 mois)
   📦 archived/                  (via /idee archive)
```

**Détection auto** : `/doc-health` étape 9 flag les idées sans décision > 30j.

---

## Anti-patterns

- ❌ Mettre une demande client dans `idees/` (= confondre interne/externe → `cadrage/`)
- ❌ Idée sans date dans le filename (perd la traçabilité chronologique)
- ❌ Supprimer une idée discarded (perdre l'historique des "non, pas ça parce que...")
- ❌ Promouvoir une idée sans `/spec` (= drift entre idees/ et specs/)
- ❌ Archiver une idée encore en `💡 Backlog` (= perdre une piste potentielle)
