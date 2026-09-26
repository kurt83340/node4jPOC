---
name: lecon
description: Gère le cycle de vie complet des leçons (.claude/docs/lecons.md) — capture (mode défaut), promote (vers ADR/rule), discard, archive. Une leçon = une observation/bug/pattern à décider plus tard. 5 statuts possibles — 🆕 new → 📜 ADR / 🔧 rule / 🧠 memory / ❌ discarded → 📦 archived.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(date:*), Bash(grep:*), AskUserQuestion
disable-model-invocation: false
argument-hint: "[capture|promote|discard|archive] <args>"
---

# /lecon — Cycle de vie complet des leçons

> **Quand ne PAS utiliser** : décision structurante d'architecture → `/adr` (une leçon peut y
> être promue ensuite) · idée produit/feature → `/idee`.
> **Réversibilité** : 🟢 append une entry dans `lecons.md` (statuts gérés par sous-modes) —
> undo : sous-mode `discard` (ou retirer l'entry à la main).

Ton rôle : orchestrer le cycle de vie des entries dans `.claude/docs/lecons.md`.

## Modes disponibles

| Mode                                | Quand l'invoquer                                                           |
| ----------------------------------- | -------------------------------------------------------------------------- |
| `/lecon <scope> "<titre>"` (défaut) | Capturer une observation/bug rapide → status `🆕 new`                      |
| `/lecon promote <date>`             | Promouvoir une leçon `🆕 new` vers ADR ou rule                             |
| `/lecon discard <date> "<raison>"`  | Marquer une leçon comme `❌ discarded` (pas pertinent)                     |
| `/lecon archive`                    | Déplacer toutes les leçons stables (`📜`/`🔧`) > 3 mois vers `## Archived` |

**Scopes valides** : `cadrage`, `mvp`, `feature-00X`, `infra`, `operations`

## Détection du mode

Si premier arg ∈ `{capture, promote, discard, archive}` → mode explicite.
Sinon → mode `capture` par défaut (le premier arg = scope, le second = titre).

---

## MODE 1 : `capture` (défaut)

### Usage

```
/lecon mvp "Notion rate limit"
/lecon capture mvp "Notion rate limit"
```

### Étape 1 — Lire .claude/docs/lecons.md actuel

Préserver les entries existantes.

### Étape 2 — Demander le contenu (AskUserQuestion)

- **Contexte** : qu'est-ce qui s'est passé / quel bug ?
- **Solution** (si déjà trouvée) : sinon "à creuser"
- **Décision intuitive** : 🆕 new (défaut)

### Étape 3 — Append (4 lignes max)

```markdown
## YYYY-MM-DD — <titre>

**scope:** <scope> | **status:** 🆕 new

<Contexte en 1-2 lignes.>
<Solution si trouvée, sinon "À creuser".>
→ <Décision intuitive : promouvoir ADR / rule / discard / memory only>
```

Append en haut de la section entries (juste après le `---`).

### Étape 4 — Suggérer review si > 5 entries `🆕 new`

→ "lance `/doc-health` pour review les leçons en attente"

---

## MODE 2 : `promote`

### Usage

```
/lecon promote 2026-05-24
/lecon promote 2026-05-24 adr      # force destination
/lecon promote 2026-05-24 rule
```

### Étape 1 — Trouver l'entry

```bash
grep -A 5 "^## ${DATE} —" .claude/docs/lecons.md
```

Si pas trouvée → demander à l'user de préciser le titre.

### Étape 2 — Demander destination (si non fournie)

Via AskUserQuestion :

- **`📜 ADR`** : décision structurante cross-feature ou survit à la feature
- **`🔧 rule`** : convention récurrente à appliquer (pattern vu 2+ fois)
- **`🧠 memory only`** : pattern technique mineur, auto-memory s'en charge
- **`❌ discarded`** : pas pertinent finalement

### Étape 3 — Selon destination :

#### Si `📜 ADR` :

- Invoquer `/adr <scope> "<titre dérivé de la leçon>"` avec pré-remplissage :
  - Contexte = corps de la leçon
  - Décision préliminaire = la solution mentionnée
- Une fois ADR créé (NNNN) : update status leçon
  ```
  status: 🆕 new → 📜 → [ADR-NNNN](../adr/NNNN-<scope>-<titre>.md)
  ```

#### Si `🔧 rule` :

- Demander à l'user : nouveau fichier rule OU append à existant ?
- Créer/append `.claude/rules/<nom>.md` avec la convention extraite de la leçon
- Update status leçon
  ```
  status: 🆕 new → 🔧 → [rule](../rules/<nom>.md)
  ```

#### Si `🧠 memory only` :

- Update status leçon (pas d'autre action — auto-memory fait le job)
  ```
  status: 🆕 new → 🧠 memory only
  ```

#### Si `❌ discarded` :

- → utiliser plutôt le mode `discard` direct (voir ci-dessous)

---

## MODE 3 : `discard`

### Usage

```
/lecon discard 2026-05-24 "Finalement résolu par mise à jour du SDK"
```

### Action

1. Trouver l'entry par date
2. Update status :
   ```
   status: 🆕 new → ❌ discarded (raison : <raison>)
   ```

---

## MODE 4 : `archive`

### Usage

```
/lecon archive
```

### Action — batch cleanup

1. Scanner toutes les entries dans `.claude/docs/lecons.md` (parse les headers `## YYYY-MM-DD —`)
2. Pour chaque entry avec status `📜 → ADR-XXX` ou `🔧 → rule` :
   - Si date entry > 3 mois → candidate pour archive
3. Présenter la liste à l'user : "X leçons promues + stables depuis > 3 mois, archive ?"
4. Si OK :
   - Créer/ajouter section `## 📦 Archived` à la fin de `.claude/docs/lecons.md`
   - Déplacer les entries candidates vers cette section
   - Update status → `📦 archived` (garde le lien promotion)

---

## Workflow de cycle de vie

```
   Capture
       ↓
   🆕 new
       ↓ (review hebdo /doc-health, ou /lecon promote)
       ├─► 📜 → ADR-NNNN  (créé via /adr)
       ├─► 🔧 → rule       (créé dans .claude/rules/)
       ├─► 🧠 memory only  (laissé à auto-memory)
       └─► ❌ discarded    (via /lecon discard)
       ↓ (post-promotion stable, > 3 mois)
   📦 archived  (via /lecon archive)
```

**Détection auto** : `/doc-health` flag les `🆕 new` > 14j (force décision).

---

## Anti-patterns

- ❌ Entry trop longue (> 5 lignes = c'est un ADR, pas une leçon)
- ❌ Statut autre que `🆕 new` au moment de la capture (l'user décide au promote)
- ❌ Promouvoir sans lien (la leçon doit pointer vers l'ADR/rule créé)
- ❌ Archiver sans promotion préalable (les `🆕 new` doivent être décidées avant)
- ❌ Modifier le corps d'une leçon archivée (immuable, comme un ADR)
