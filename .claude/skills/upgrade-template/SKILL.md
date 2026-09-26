---
name: upgrade-template
description: Met à jour les fichiers de méthode du projet (hooks, skills, agents, rules, settings, index CLAUDE.md) vers la dernière version du template claude-Setup, par merge 3 voies — personnalisations locales préservées, conflits signalés jamais écrasés, doc projet migrée seulement par des migrations versionnées. Dry-run et validation utilisateur avant d'écrire - /upgrade-template [vX.Y.Z].
allowed-tools: Read, Glob, Grep, Edit, Write, AskUserQuestion, Bash(git status), Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git add:*), Bash(git commit:*), Bash(git clone:*), Bash(python3 .claude/skills/doc-health/scripts/context-budget.py:*)
disable-model-invocation: true
argument-hint: "[vX.Y.Z | chemin-du-template]"
---

# /upgrade-template — Mettre à jour la méthode du projet (merge 3 voies)

> **Quand ne PAS utiliser** : projet pas encore initialisé → `/init-from-template` · greffer le
> template sur un projet existant → `/adopt-template` · auditer la doc → `/doc-health`.
> **Réversibilité** : 🟠 réécrit des fichiers de méthode (jamais `.claude/docs/` hors migrations)
> sur un arbre git propre, en un commit — undo : `git revert <commit>` (ou `git checkout -- .` avant commit).

Le moteur est `scripts/upgrade.py` — **toujours exécuté depuis le template le plus récent** (la
logique de mise à jour elle-même profite des derniers correctifs). Il rejoue l'init de la version
du projet (base) et de la version cible avec le même profil, puis, fichier par fichier :
projet = base → la cible s'applique · template inchangé → la personnalisation reste · les deux
ont bougé → `git merge-file` (fusion JSON pour `settings.json`) ; conflit → fichier du projet
**gardé**, version cible déposée dans `.claude/.cache/upgrade-<version>/`.

## Étape 0 — Préconditions

```bash
git status --short          # doit être VIDE (hors .claude/.cache) : commit ou stash d'abord
cat .claude/template-version .claude/template-lock.json 2>/dev/null
```

Arbre sale → le dire, proposer de committer d'abord (le diff de mise à jour doit se relire seul).
Pas de `template-lock.json` (projet < 1.5.0) : normal — le profil sera déduit (à confirmer à l'Étape 2).

## Étape 1 — Récupérer le template

- L'utilisateur a un clone local du template (argument = chemin) → l'utiliser.
- Sinon cloner la source du lock (défaut : `https://github.com/kurt83340/claude-Setup`) :

```bash
TPL="$(mktemp -d)/claude-setup" && git clone --quiet https://github.com/kurt83340/claude-Setup "$TPL" && echo "$TPL"
```

## Étape 2 — Dry-run et lecture du plan

```bash
python3 "$TPL/.claude/skills/upgrade-template/scripts/upgrade.py" --project . --template "$TPL" --dry-run
```

(argument `vX.Y.Z` → ajouter `--to vX.Y.Z` ; sinon dernier tag.) Présente à l'utilisateur :
versions (de → vers), profil et mode (déduits ? → les faire confirmer ; `--profile <type>`,
`--mode greenfield|brownfield` sinon), fichiers
mis à jour / ajoutés / retirés / fusionnés, personnalisations gardées, **conflits**, changements de
`settings.json`, migrations de la doc. Résume les nouveautés depuis `"$TPL/.github/CHANGELOG.md"`
(sections entre les deux versions). **AskUserQuestion** : appliquer / ajuster le profil / annuler.

## Étape 3 — Appliquer

```bash
python3 "$TPL/.claude/skills/upgrade-template/scripts/upgrade.py" --project . --template "$TPL"
```

Code retour 0 = appliqué sans conflit · 1 = appliqué avec conflits · 2 = erreur (rien n'est écrit).

## Étape 4 — Conflits (si code 1)

Pour chaque fichier listé : lire la version du projet, `.claude/.cache/upgrade-<v>/<fichier>.template`
(cible) et `<fichier>.merge` (merge annoté, s'il existe). Proposer une fusion qui garde l'intention
locale ET le correctif amont, montrer le diff, **valider avec l'utilisateur**, puis écrire. Un hook
ou un script fusionné se re-teste (`python3 -m py_compile …`, `bash -n …`). Un chemin qui passe par
un **lien symbolique** (dossier partagé hors projet) n'est jamais modifié : le signaler, ne pas forcer.

Les conflits sont mémorisés dans `.claude/template-lock.json` (`pending_conflicts`, versionné) : une
relance les re-signale (code 1) tant qu'ils ne sont pas acquittés. Une fois TOUS résolus :

```bash
python3 "$TPL/.claude/skills/upgrade-template/scripts/upgrade.py" --project . --template "$TPL" --ack-conflicts
```

## Étape 5 — Vérifier et committer

```bash
python3 -m json.tool .claude/settings.json > /dev/null && echo "settings OK"
python3 .claude/skills/doc-health/scripts/context-budget.py --max 25000 --no-user | tail -3
git diff --stat
```

```bash
git add .claude/ CLAUDE.md .gitignore .pre-commit-config.yaml
git commit -m "chore(template): claude-Setup <de> → <vers>"
```

Puis dire à l'utilisateur : **relancer Claude Code** (hooks et settings sont lus au démarrage ;
les skills se rechargent à chaud), activer le garde-fou secrets s'il est nouveau
(`pre-commit install`), et supprimer `.claude/.cache/upgrade-<v>/` une fois les conflits réglés.

## Anti-patterns

- ❌ Lancer le moteur embarqué du projet quand un template plus récent est disponible (le moteur
  du template cible connaît toutes les versions précédentes)
- ❌ Écraser un fichier en conflit par la version du template « pour aller vite »
- ❌ Toucher à `.claude/docs/` à la main pendant l'upgrade (seules les migrations le font)
- ❌ Appliquer sans avoir montré le dry-run
