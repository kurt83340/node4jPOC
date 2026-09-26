---
name: handoff
description: Met à jour .claude/docs/HANDOFF.md à la fin d'une session de travail. Génère un snapshot narratif court (status + échecs tentés + blockers + next steps) à partir du git status + tests + contexte chat courant. À invoquer à chaque fin de session pour préserver l'état entre sessions Claude Code.
allowed-tools: Read, Write, Edit, Bash(git status), Bash(git log:*), Bash(git diff:*), Bash(git branch:*), Bash(pytest:*), Bash(npm test:*), Bash(ruff:*), Bash(python3 .claude/skills/doc-health/scripts/context-budget.py:*)
disable-model-invocation: false
---

# /handoff — Snapshot fin de session

> **Quand ne PAS utiliser** : reprendre une session précise → `/resume` (natif, fidélité 100%) ·
> feature terminée à livrer → `/feature-done` · pattern technique appris → auto-memory ou `/lecon`.
> **Réversibilité** : 🟢 n'écrit que `.claude/docs/HANDOFF.md` (après confirmation) + 1 ligne appendée
> à `.claude/docs/HANDOFF-journal.md` — undo : `git checkout -- .claude/docs/HANDOFF.md .claude/docs/HANDOFF-journal.md`.

Ton rôle : générer une mise à jour propre de `.claude/docs/HANDOFF.md` qui permettra de reprendre le travail demain sans perdre le contexte.

## Étape 1 — Collecter l'état actuel

Lance en parallèle :

```bash
git status
git log -5 --oneline
git diff --stat main 2>/dev/null || git diff --stat   # (pas de branche main : changements en cours)
git branch --show-current
```

Si projet Python : `pytest --tb=no -q | tail -10` (rapide)
Si projet Node : `npm test -- --silent` (rapide)

## Étape 2 — Lire le HANDOFF actuel + détecter "fresh"

Lis `.claude/docs/HANDOFF.md`.

**Détection "fresh"** : si le fichier contient > 5 placeholders `{{...}}` non substitués → considérer comme HANDOFF initial (post-init template), **ne PAS préserver de sections custom** (il n'y en a pas). Générer un HANDOFF complet from scratch en Étape 3.

```bash
PLACEHOLDERS=$(grep -cE '\{\{[^}]+\}\}' .claude/docs/HANDOFF.md)
if [ "$PLACEHOLDERS" -gt 5 ]; then
  echo "📝 HANDOFF fresh détecté ($PLACEHOLDERS placeholders) → regen complet"
fi
```

Sinon (HANDOFF déjà rempli) : le nouveau HANDOFF est **réécrit** au format strict de l'Étape 3 —
**jamais appendé**, jamais une section datée de plus. Sections hors format (heuristique : tout ce qui
n'est pas dans le format standard) : conservées **seulement si** elles sont **non datées** ET que le
fichier reste **≤ 40 lignes** ; sinon elles sont **déplacées telles quelles** dans `HANDOFF-journal.md`
sous `## Archive YYYY-MM-DD` (jamais supprimées, jamais résumées en silence — dis-le dans le diff).

> Vécu 2026-09-16 (projet hors template) : 55 sections datées « préservées » session après session →
> HANDOFF de 175 Ko auto-chargé à chaque appel, plafond 1M dépassé à la reprise, session bloquée.

```bash
wc -l -c .claude/docs/HANDOFF.md   # > 40 lignes ou > 12 000 octets → archiver en Étape 3, pas préserver
```

## Étape 3 — Composer le nouveau HANDOFF

Format strict — **réécriture complète**, ≤ 40 lignes (le fichier est auto-chargé à chaque session) :

```markdown
# HANDOFF — YYYY-MM-DD HHhMM

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `<branch>`
**Spec en cours** : [<spec-name>](specs/<spec>/spec.md) (X/Y tasks)
**Goal session** : <ce que je voulais faire>

## Status

- ✅/⏳/❌ <test command> : <résultat>
- ✅/⏳ <lint/type check> : <résultat>
- ✅/⏳ <autre check>

## Échecs tentés (à ne pas refaire)

- <approche A tentée> → <pourquoi KO>
- <approche B> → <pourquoi rejetée>

## Blocked on

- <bloqueur 1>
- <bloqueur 2>

## Next (par ordre)

1. **Task #N** : <description courte>
2. **Task #N+1** : ...
3. <étape suivante>

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: <00X-slug | aucune>
Task: <T2.3 | aucune>
Fichiers en cours: <chemins séparés par virgule | aucun>
Bloqué sur: <rien | description courte>
Commande de reprise: <la 1re commande à lancer en reprenant | aucune>

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
```

## Étape 3bis — Journal (fichier frère, append-only)

Le journal **ne vit plus dans HANDOFF.md** (v1.4 — budget contexte : HANDOFF est auto-chargé à
chaque session et le journal grossit sans borne ; mesuré 25k tokens sur un projet d'un mois).

1. Si `.claude/docs/HANDOFF-journal.md` n'existe pas → le créer :

```markdown
# Journal HANDOFF — append-only

> 1 ligne par session, ajoutée par `/handoff`, **jamais réécrite**. Non auto-chargé : lu à la demande.

## Journal

```

2. **Migration** (projet < v1.4) : si HANDOFF.md contient encore une section `## Journal` → déplacer
   ses entrées telles quelles dans le journal (jamais les perdre), puis remplacer la section par le pointeur.
3. **Appender** 1 ligne : `- YYYY-MM-DD — <ce qui a été fait cette session, en 1 phrase>`

> Le **Continuation State** duplique volontairement l'essentiel de « Next » en grammaire fixe :
> c'est le point de reprise **parseable** (par un agent frais ou un script) quand la prose ambiguë
> coûte cher. Toujours les 5 clés, même à `aucune` — une clé absente est indistinguable d'un oubli.

## Étape 4 — Présenter le diff au user

⚠️ **NE PAS écrire directement**. Présenter d'abord le diff proposé :

```
📋 Nouveau HANDOFF proposé :

<diff colorisé>

OK pour écrire ? (yes/edit/cancel)
```

Si user confirme → Write. Sinon → ajuster selon ses retours.

## Étape 5 — Bonus

Si feature livrée (toutes tasks ✅) :

- Suggérer d'enchaîner avec `/feature-done <spec-id>`

Si > 3 décisions tech récentes sans ADR :

- Suggérer `/lecon` pour capturer

Si HANDOFF n'a pas changé (rien de neuf) :

- Skip l'écriture, juste timestamp update

Budget contexte (si `/doc-health` est installé sur ce projet) :

```bash
[ -f .claude/skills/doc-health/scripts/context-budget.py ] && python3 .claude/skills/doc-health/scripts/context-budget.py --max 25000 --no-user | tail -3
```

- Seuil dépassé → 1 ligne au user avec le coupable (HANDOFF > 40 lignes ? code-map > 3k ? rule ré-importée ?)

## Anti-patterns à éviter

- ❌ Écrire un roman (HANDOFF court = **≤ 40 lignes**, il est auto-chargé à chaque session ; le **Journal** gagne 1 ligne/session mais dans `HANDOFF-journal.md`, pas ici)
- ❌ Réécrire/écraser le **Journal** : on APPEND seulement (1 ligne/session) → l'arc complet reste reconstructible depuis le journal
- ❌ Remettre le Journal dans HANDOFF.md « pour l'avoir sous les yeux » : c'est exactement ce qui gonfle le contexte
- ❌ Dupliquer ce qui est déjà dans CHANGELOG (factuel) ou auto-memory (patterns)
- ❌ Lister TOUS les commits (juste le sens général)
- ❌ Mentionner des credentials/secrets

## Note : filets automatiques (hooks) — complémentaires, pas remplaçants

Ce skill n'est **jamais** déclenché automatiquement. Deux hooks posent des filets minimaux dans
`.claude/.cache/` (git state + derniers messages humains, sans confirmation) : `PreCompact`
(avant compaction) et `SessionEnd` (session fermée SANS /handoff après avoir modifié le dépôt).
`/handoff` reste la version riche (échecs tentés, blockers, next) validée par l'utilisateur.

## Note : toujours dans le fil principal

`/handoff` se lance dans la session qui a travaillé : lui seul voit la conversation (échecs
tentés, goal, blockers). Un subagent (ex. `doc-maintainer`) démarre à contexte vide — il ne peut
ni remplir ces sections ni obtenir la validation de l'Étape 4. Ne pas lui déléguer le HANDOFF.

## Note : projets script-jetable

Sur un projet initialisé en `script-jetable`, `/feature-done` et l'agent `doc-maintainer` ne sont **pas installés** (cleanup). Ce skill reste pleinement autonome (aucune dépendance) — ignore simplement la suggestion `/feature-done` (Étape 5) sur ce type de projet.
