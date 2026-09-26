---
name: spec
description: Crée une nouvelle feature spec — scaffold les 4 fichiers research.md, spec.md, plan.md, tasks.md dans .claude/docs/specs/00X-titre/ depuis des templates bundlés. Update .claude/docs/ROADMAP.md avec la nouvelle entrée. À invoquer chaque fois que tu démarres une nouvelle feature.
allowed-tools: Read, Write, Edit, Glob, Bash(ls:*), Bash(find:*), Bash(mkdir:*), Bash(cp:*), Bash(date:*), AskUserQuestion
disable-model-invocation: false
argument-hint: "<id-optionnel> <titre>"
---

# /spec — Scaffold une nouvelle feature

> **Quand ne PAS utiliser** : le plan d'une spec existante → `/conception` · dérouler toute la
> chaîne d'une traite → `/feature` · petite modif/bugfix → pas de spec (commit + CHANGELOG).
> **Réversibilité** : 🟢 crée `specs/00X-slug/` (4 fichiers) + 1 ligne ROADMAP —
> undo : `rm -r` du dossier + retirer la ligne.

Ton rôle : créer le dossier `.claude/docs/specs/00X-titre/` avec ses 4 fichiers prêts à remplir, et update ROADMAP.

## Usage

```
/spec "Pagination cursor"
# Auto-calcule N suivant + crée specs/00X-pagination-cursor/{research,spec,plan,tasks}.md

/spec 005 "Export PDF"
# Force le numéro 005 (utile pour pivot ou réorganisation)
```

## Étape 1 — Calculer le numéro suivant

```bash
# Trouver le max existant
ls .claude/docs/specs/ 2>/dev/null | grep -oE "^[0-9]+" | sort -n | tail -1
```

Si aucune spec existante → `001`. Sinon `max + 1`, formaté sur 3 chiffres.

Si l'user a passé un ID en argument → l'utiliser (override).

> ⚠️ **Mode agent-teams (plusieurs sessions Claude concurrentes)** : le calcul `max + 1`
> n'est **pas concurrent-safe** — deux agents qui scaffoldent en même temps prendraient le
> même `00X`. Convention : **seul le lead scaffolde les specs et alloue les numéros**. Un
> worker qui a besoin d'une spec la demande au lead (il ne lance pas `/spec` en parallèle).

## Étape 2 — Demander confirmation titre + scope

Via AskUserQuestion :

1. **Titre court** (kebab-case auto) : ex. "Pagination cursor" → `pagination-cursor`
2. **Description en 1 phrase** : pour spec.md le user story
3. **Phase ROADMAP** : à quelle phase elle appartient (Phase 1 MVP, Phase 2, ...)

## Étape 3 — Créer le dossier + 4 fichiers

```bash
DIR=".claude/docs/specs/00X-<kebab>"
mkdir -p "$DIR"

# Copier les 4 templates bundlés
cp ${CLAUDE_SKILL_DIR}/templates/research.md "$DIR/"
cp ${CLAUDE_SKILL_DIR}/templates/spec.md "$DIR/"
cp ${CLAUDE_SKILL_DIR}/templates/plan.md "$DIR/"
cp ${CLAUDE_SKILL_DIR}/templates/tasks.md "$DIR/"
```

Substituer dans chaque fichier :

- `{{SPEC_ID}}` → ex. `004`
- `{{SPEC_TITRE}}` → ex. `Pagination cursor`
- `{{SPEC_KEBAB}}` → ex. `pagination-cursor`
- `{{SPEC_DATE}}` → date du jour ISO

## Étape 4 — Update .claude/docs/ROADMAP.md

Trouver la section phase indiquée par l'user, ajouter la ligne dans l'état qui correspond.

### Machine à états ROADMAP (contrat avec `/feature-done` et `/doc-health`)

```
[ ] pas commencé   →   [~] **EN COURS**   →   [x] livré YYYY-MM-DD
   (scaffold seul)      (feature démarrée)     (via /feature-done)
```

- **`/spec` pose `[ ]`** par défaut (spec scaffoldée mais pas démarrée), **OU `[~]`** si l'user enchaîne tout de suite (cf. Étape 5).
- **`/feature-done` lit l'état réel** (`[ ]` _ou_ `[~]`) et le passe à `[x]`.
- **`/doc-health` détecte les `[~]` stalled** (en cours depuis > 30j) **et les incohérences ROADMAP ↔ frontmatter**.

> 🔗 **Frontmatter `status:` de `spec.md` = source machine-readable, à garder synchrone** :
> `[ ]`↔`draft`/`validated` (validated = posé par `/conception` quand le plan est arrêté) ·
> `[~]`↔`in-progress` · `[x]`↔`done`. Le template est créé à `draft` — chaque transition
> ROADMAP s'accompagne de la MAJ du frontmatter (ici et dans `/feature-done`).

> ⚠️ Sans transition vers `[~]`, les greps de `/feature-done` et `/doc-health` (`[~] … **EN COURS**`) ne matchent jamais. C'est `/spec` (Étape 5) ou l'user qui pose `[~]` au démarrage.

Ligne par défaut (scaffold sans démarrer) :

```markdown
- [ ] [00X-<kebab>](specs/00X-<kebab>/spec.md) — pas commencé
```

## Étape 5 — Démarrage immédiat : poser `[~]` + update HANDOFF (optionnel)

Si l'user va commencer la feature **tout de suite**, proposer de :

1. Passer la ligne ROADMAP en **EN COURS** (format canonique attendu par `/feature-done` + `/doc-health`) :

   ```markdown
   - [~] [00X-<kebab>](specs/00X-<kebab>/spec.md) — **EN COURS** 0/Y tasks
   ```

   … et passer le frontmatter de `specs/00X-<kebab>/spec.md` à `status: in-progress` (sync).

2. Mettre à jour HANDOFF :

   ```markdown
   **Spec en cours** : [00X-<kebab>](specs/00X-<kebab>/spec.md) (0/Y tasks)
   **Goal session** : démarrer feature 00X-<kebab>
   ```

## Sortie attendue

```
✅ Feature 004-pagination-cursor scaffoldée

📂 Fichiers créés :
  - .claude/docs/specs/004-pagination-cursor/research.md
  - .claude/docs/specs/004-pagination-cursor/spec.md
  - .claude/docs/specs/004-pagination-cursor/plan.md
  - .claude/docs/specs/004-pagination-cursor/tasks.md

📝 .claude/docs/ROADMAP.md : ligne ajoutée Phase 1 — [ ] [004-pagination-cursor]

🚀 Prochaine étape :
   /conception 004-pagination-cursor
   → explore (code + docs + mémoire projet) → 2-3 options → décision → plan.md
     avec points de vérification + tasks.md partitionné + revue adverse.
   (Ou remplir les 4 fichiers à la main si la feature est triviale.)
```

## Anti-patterns

- ❌ Skip la numérotation continue (toujours max + 1, jamais reset)
- ❌ Créer la spec sans update ROADMAP (= drift)
- ❌ Remplir directement les fichiers sans demander au user
- ❌ Démarrer le code AVANT d'avoir au minimum spec.md + plan.md remplis
