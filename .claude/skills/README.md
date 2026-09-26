# `.claude/skills/` — Inventaire et organisation

> 🗂️ **Inventaire canonique** (**17 skills cœur**) — source de vérité des skills du template, vérifiée
> par la CI (chaque dossier `.claude/skills/*` y figure ; compte déclaré = dossiers réels). Claude
> Code liste déjà nativement nom + description de chaque skill : cet inventaire sert aux humains et
> à la CI. Un skill ajouté au projet s'y recense.

## Skills du template

### Session & feature

- `/handoff` — réécrit HANDOFF.md en fin de session (≤ 40 lignes) + 1 ligne au journal
- `/spec "<titre>"` — scaffold d'une feature (4 fichiers) + ligne ROADMAP
- `/conception <spec-id|macro>` — explore (subagents code/docs/mémoire) → 2-3 options → décision → plan vérifiable + revue adverse
- `/feature "<titre>" [pipeline]` — déroule un pipeline complet (standard/tdd/n8n), gate utilisateur entre chaque étape
- `/feature-done <spec-id>` — livraison : ROADMAP, CHANGELOG, HANDOFF, ADR proposés, PR
- `/debug "<symptôme>"` — reproduire (test rouge) → explorer → hypothèses discriminées → fix minimal → leçon
- `/pivot "<raison>"` — pivot client orchestré (9 étapes, validation à chaque étape)
- `/archive-projet ["raison"]` — fin de vie : bilan, marquage archivé, commande de move (+ `restore`, `status`)
- `/upgrade-template [vX.Y.Z]` — met à jour la méthode du projet vers la dernière version du template (merge 3 voies, conflits signalés)

### Cycle de vie des artefacts (capture / promote / discard / archive)

- `/lecon [mode] <args>` — leçons : `<scope> "<titre>"` · `promote <date>` · `discard <date>` · `archive`
- `/adr [mode] <args>` — décisions immuables : `<scope> "<titre>"` · `supersede <NN>` · `deprecate <NN>` · `list`
- `/idee [mode] <args>` — idées internes : `"<titre>"` · `promote <date>` · `discard <date>` · `archive`

### Audit & technique

- `/doc-health` — audit hebdo (fraîcheur, ADR manquants, drift code-map, budget de contexte)
- `/codemap` — met à jour code-map.md (vue macro + couplage) et détecte les violations
- `/scaffold skill|agent|pipeline "<nom>"` — composant conforme aux conventions + référencement

### Bootstrap (usage unique — retirés du projet après usage)

- `/init-from-template` — initialise un projet depuis le template (from scratch)
- `/adopt-template` — greffe le template sur un projet EXISTANT (brownfield, merges non destructifs)

## Convention

```
.claude/skills/
├── <skill-1>/SKILL.md     # invocable via /<skill-1>
├── <skill-2>/SKILL.md     # invocable via /<skill-2>
└── ...
```

**Pas de sous-dossier de regroupement.** Claude Code scanne `.claude/skills/<nom>/SKILL.md` à **1 niveau seulement** (cf. [issue #18192](https://github.com/anthropics/claude-code/issues/18192) — feature request OPEN pour discovery récursive).

## Règles

1. **Le `name:` du frontmatter doit matcher le nom du dossier.**
   Ex : `.claude/skills/handoff/SKILL.md` avec `name: handoff` → invoque `/handoff`.

2. **Tout est dans le même espace de noms** (`.claude/skills/`, `~/.claude/skills/`, plugins). Si collision → Claude en utilise un (alphabétique). Rename le dossier + `name:` du moins prioritaire.

3. **Pour grouper des skills par thème, 2 options :**
   - **Préfixe le nom** : `n8n-deploy`, `n8n-test`, `n8n-lint` (simple, usage perso)
   - **Package en plugin** : `<plugin>/skills/<skill>/SKILL.md` → invocation `/<plugin>:<skill>` (officiel, namespacing préservé)

## Importer un skill externe

### Depuis GitHub

```bash
# Cloner dans un dossier temp
git clone <repo-url> /tmp/external-skills

# Copier chaque SKILL.md directement sous .claude/skills/
# (en préfixant le nom si tu veux marquer la provenance)
cp -r /tmp/external-skills/skills/foo .claude/skills/n8n-foo
# → édite SKILL.md pour aligner name: n8n-foo
```

### Depuis un MCP server

Les MCP servers exposent des "tools" automatiquement (sans SKILL.md). Pour wrapper un MCP tool comme skill invocable :

```bash
mkdir -p .claude/skills/mcp-<tool>
cat > .claude/skills/mcp-<tool>/SKILL.md <<'EOF'
---
name: mcp-<tool>
description: Wrapper pour le MCP tool X (server Y)
allowed-tools: mcp__<server>__<tool>
---

# Invocation du MCP tool <tool>
...
EOF
```

### Depuis un plugin Claude Code

Les plugins ont leur propre namespace automatiquement (`plugin-name:skill-name`). Pas besoin de copier dans `.claude/skills/` — l'invocation devient `/<plugin>:<skill>`.

## Skills stack et options = PLUGINS (marketplace `claude-setup`, dossier `plugins/` du repo template)

Pas livrés dans `.claude/skills/` — packagés en **plugins** installés par projet via `/plugin`
(auto-découverts, aucun inventaire à maintenir). Recensés ici pour visibilité.

| Plugin          | Skills                 | Install (selon type projet)                                     |
| --------------- | ---------------------- | --------------------------------------------------------------- |
| `n8n-mcp-skills` (**officiel**, [czlonkowski/n8n-skills](https://github.com/czlonkowski/n8n-skills)) | 14 skills n8n + hooks | `automation-n8n` → check-first `claude plugin list` (souvent déjà en user-scope) ; sinon marketplace add + install `--scope user` |
| `db-migration`  | `db-migration`         | `bdd-migration` → `/plugin install db-migration@claude-setup`   |
| `agent-teams`   | `/agent-teams:team` + rôles worker/front-end/back-end/tester | toute stack, **opt-in** → `/plugin install agent-teams@claude-setup`, puis `/agent-teams:team` (1er lancement = activation) |

## Skills built-in Claude Code (hors `.claude/skills/`)

Disponibles automatiquement : `/security-review`, `/code-review`, `/init`, `/resume`, `/compact`, `/doctor`. Pas besoin de SKILL.md.
