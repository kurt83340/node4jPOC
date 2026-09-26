---
name: adopt-template
description: Greffe le template sur un projet EXISTANT (brownfield) — jamais d'overwrite - état des lieux (stack/structure/outillage détectés), merges diff-par-diff des collisions (CLAUDE.md, settings.json, .gitignore existants), questions CORE pré-remplies depuis l'existant, puis RÉTRO-REMPLISSAGE de la doc depuis le projet (stack.md ← manifests, code-map ← /codemap, HANDOFF ← git log, ADRs rétroactifs optionnels). Réutilise render.py + cleanup-for-type.py (mêmes scripts que /init-from-template). À exécuter UNE FOIS, après le rsync --ignore-existing.
allowed-tools: Read, Write, Edit, Grep, Glob, AskUserQuestion, Skill, Bash(git status), Bash(git log:*), Bash(git diff:*), Bash(git add:*), Bash(git commit:*), Bash(find:*), Bash(grep:*), Bash(cat:*), Bash(python3 .claude/skills/init-from-template/scripts/render.py:*), Bash(python3 .claude/skills/init-from-template/scripts/cleanup-for-type.py:*)
disable-model-invocation: true
---

# /adopt-template — Greffer le template sur un projet existant

> **Quand ne PAS utiliser** : projet vierge (copie fraîche du template) → `/init-from-template` ·
> projet déjà adopté → jamais deux fois (one-shot).
> **Réversibilité** : 🟠 merges non-destructifs, deletes confinés à `.claude/` — commit de
> pré-adoption exigé ; undo : `git reset --hard` sur ce commit.

Pendant brownfield de `/init-from-template`. **Règle d'or : l'existant est sacré** — on
n'écrase RIEN, on fusionne diff par diff, et la doc se remplit DEPUIS le projet, pas depuis
des placeholders.

**Deux autres règles** : tout trou d'information = une **question ciblée** (AskUserQuestion),
jamais une invention. Et l'utilisateur peut **pré-seeder le cadrage** (déposer docs, tickets,
transcriptions dans `cadrage/` après le rsync, AVANT de lancer le skill) — c'est **ingéré**,
jamais écrasé.

## Prérequis (l'utilisateur l'a fait AVANT, sinon guide-le)

```bash
# Depuis le projet existant — copie SANS ÉCRASEMENT (les fichiers existants gagnent toujours)
rsync -av --ignore-existing \
  --exclude='EXAMPLES/' --exclude='test/' --exclude='.github/' \
  --exclude='plugins/' --exclude='.claude-plugin/' \
  --exclude='.git/' --exclude='README.md' --exclude='.env.example' \
  /chemin/vers/template/ .

# (Optionnel, recommandé) Déposer les matériaux AVANT de lancer le skill :
#   docs client → .claude/docs/cadrage/documents/     tickets → .claude/docs/cadrage/tickets/
#   transcriptions de réunions → .claude/docs/cadrage/reunions/
```

## Étape 0 — Sécurité

1. `git status` : working tree PROPRE exigé (sinon → commit/stash d'abord). Puis commit
   snapshot : `chore: snapshot pre-adopt` (rollback garanti).
2. `python3 --version` (les hooks sont appelés via `python3`/`bash` — pas de `chmod` requis).

## Étape 1 — État des lieux (détecter, pas demander)

Scanne et présente à l'utilisateur :

- **Stack** : manifests présents (`package.json`, `pyproject.toml`/`requirements*.txt`,
  `composer.json`, `docker-compose*`, lockfiles) → langages, frameworks, commandes
  install/test/run **pré-déduites**.
- **Structure** : `src/`/`app/`/`lib/`, `tests/`, CI existante (`.github/workflows/`).
- **Outillage Claude préexistant** : `CLAUDE.md` ?, `.claude/` (settings, skills, commands,
  hooks à lui) ? → liste les collisions (fichiers que le rsync n'a PAS copiés car existants).
- **Matériaux déposés** : scanne `.claude/docs/cadrage/{documents,tickets,reunions}/` — tout
  ce que l'utilisateur y a déposé (docs client, tickets, transcriptions) est la matière
  première du cadrage (Étape 4). Liste ce qui a été trouvé, fichier par fichier.

## Étape 2 — Merges des collisions (diff par diff, JAMAIS d'overwrite silencieux)

**Aucune collision** (projet sans `CLAUDE.md` ni `.claude/` préexistants — cas fréquent) ?
Rien à merger : le rsync a tout posé, passe directement à l'Étape 3.

- **`CLAUDE.md` existant** : préserver 100 % du contenu user ; proposer d'y AJOUTER l'index
  just-in-time du template (2 `@-import` : HANDOFF/code-map — ROADMAP en lien simple — + liens à la demande).
  ⚠️ Max 2 `@-import` au total — si l'existant en a déjà, arbitrer avec l'utilisateur.
- **`.claude/settings.json` existant** : merge JSON proposé en diff — unions des
  `permissions.allow/ask/deny` (dont les deny de secrets `Read(.env)`, `Read(.env.*)` + exceptions
  `!.env.example`…), append des hooks du template (sans doublon). Pas de flag d'équipe : les agent
  teams sont opt-in (activées par `/agent-teams:team` si le plugin est installé).
- **`.gitignore`** : append des lignes template manquantes (`.claude/.cache/`,
  `.claude/settings.local.json`, `.claude/.growth-suggestions.md`, `.env`, `.env.*` +
  `!.env.example`, `secrets.*`…).
- **`.pre-commit-config.yaml` existant** : proposer d'y ajouter le hook gitleaks du template
  (sinon le fichier du template a été posé par le rsync).
- **Skills/commands maison en collision de nom** : les siens gagnent ; proposer un préfixe
  pour la variante template.

## Étape 3 — Questions CORE (pré-remplies) + render + cleanup

Comme `/init-from-template`, avec les réponses **pré-déduites de l'Étape 1**
(PROJECT*NAME = nom du repo, COMMANDE*\* = manifests) — l'utilisateur corrige au lieu de
saisir. Puis, mêmes scripts (source unique — ne pas ré-implémenter) :

```bash
python3 .claude/skills/init-from-template/scripts/render.py --vars <vars.json>
python3 .claude/skills/init-from-template/scripts/render.py --check   # AVANT le cleanup
python3 .claude/skills/init-from-template/scripts/cleanup-for-type.py --type <type> --brownfield
```

> ⚠️ **`--brownfield` OBLIGATOIRE ici.** Sans lui, le cleanup retirerait les « artefacts de
> maintenance du template »… or sur un projet EXISTANT, `.github/`, `test/`, `plugins/` sont
> à l'**UTILISATEUR** (le rsync d'adopt exclut ceux du template) → destruction de sa CI et de
> ses tests. Avec le flag : aucun strip, suppressions de profil confinées à `.claude/`,
> permissions et inventaires **non** purgés. (Des sentinelles côté script protègent aussi par
> défaut — ceinture ET bretelles.) Les skills bootstrap restent donc en place : leur retrait
> manuel est proposé à l'Étape 5.

(La substitution ne touche que les `{{CORE}}` du squelette copié — les .md du projet
existant n'en contiennent pas.)

## Étape 4 — Rétro-remplissage depuis l'existant (la vraie valeur)

1. **`stack.md`** ← manifests scannés (langage + version, frameworks, services tiers, LLM)
   + ligne d'en-tête `> Template claude-Setup vX.Y.Z (adopté le YYYY-MM-DD)` (version : `.claude/template-version`).
2. **`code-map.md`** ← **délègue `/codemap`** (foyer unique : vue macro + couplages depuis le code).
3. **`cadrage/README.md`** ← synthèse des **matériaux déposés** (Étape 1 — extraire des
   documents/tickets/transcriptions : verbatim de la demande, interlocuteurs, contraintes,
   risques) + README existant. Chaque trou restant = une **question ciblée**
   (AskUserQuestion) ; jamais d'invention — au pire marquer « à reconstituer ».
4. **`ROADMAP.md`** ← `## ✅ Phase 0 — Existant (adopté YYYY-MM-DD)` + scan `TODO|FIXME`
   (→ candidats backlog, proposés pas imposés).
5. **`HANDOFF.md`** ← `git log -10` + état réel (branche, tests s'ils tournent) — premier
   handoff honnête, pas un placeholder.
6. **ADRs rétroactifs (optionnel, max 2-3)** : les choix structurants ÉVIDENTS de l'existant
   (BDD, framework, hébergement) → proposer `/adr cadrage "<choix>"` chacun. Pas
   d'archéologie exhaustive — le reste se capturera au fil des `/conception`.

## Étape 5 — Vérifs + commit

1. `render.py --check` → 0 CORE restant ; `.claude/template-lock.json` écrit (mode `brownfield` —
   base de `/upgrade-template` pour les futures mises à jour).
2. Garde-fou secrets : `pre-commit install` si pre-commit est disponible ; suggérer `/doctor` au
   prochain démarrage.
3. Commit : `chore: adoption template claude-Setup` (lister les merges dans le corps).
4. Next : remplir `cadrage/README.md` si lacunaire → première feature via `/spec` + `/conception`.
5. Proposer de retirer `/adopt-template` + `/init-from-template` (usage unique tous les deux).

## Anti-patterns

- ❌ Écraser un fichier existant (CLAUDE.md, settings, README) — TOUT passe par un diff validé
- ❌ Re-poser une question dont la réponse est dans un manifest (pré-remplir, faire corriger)
- ❌ Rétro-documenter exhaustivement (ADRs pour tout l'historique = archéologie qui pourrit)
- ❌ Ré-implémenter render/cleanup ici (scripts partagés avec /init-from-template = source unique)
- ❌ Lancer sur un working tree sale (pas de rollback propre)
