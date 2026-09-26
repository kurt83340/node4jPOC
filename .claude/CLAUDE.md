# {{PROJECT_NAME}} — Méthode (template claude-Setup)

> Comment ce projet est outillé pour Claude Code. Le [`CLAUDE.md` racine](../CLAUDE.md) décrit le
> **projet** (résumé, doc, conventions). Les deux sont chargés à chaque session : ce fichier reste court
> (les skills et agents sont déjà listés nativement par Claude Code, avec leur description).

## Où est quoi

- **Doc projet** (`.claude/docs/`) : la rule [template-maintenance](rules/template-maintenance.md) (invariants
  d'écriture) se charge d'elle-même dès qu'un fichier de doc est lu (scopée `paths:` — jamais en `@`).
- **Skills** : inventaire + conventions → [skills/README.md](skills/README.md). Un skill ajouté au projet s'y recense.
- Nouveau skill / agent / pipeline conforme aux conventions → `/scaffold`.
- **Guides humains** (lus à la demande) : [USAGE.md](USAGE.md) (workflows) · [STRUCTURE.md](STRUCTURE.md) (arborescence, conventions).

## 🔁 Pipelines récurrents (orchestrés par `/feature`)

- `/feature "<titre>" [standard|tdd|n8n]` : Planifier (`/spec` + `/conception`) → Coder → Tester → Review adverse → Vérifier → Persister (`/feature-done`). 1 pipeline = 1 fichier de `skills/feature/pipelines/`.
- Bug non trivial → `/debug` : reproduire (test rouge) → explorer → hypothèses discriminées → fix minimal → leçon.

## Agent perso (`.claude/agents/`)

- `explore-code` · `explore-docs` · `explore-memoire` : explorateurs lecture seule (étape Explore de `/conception`, toute investigation) ; `reviewer` : revue adverse (plans et diffs).
- `doc-maintainer` : maintenance doc **en lot** (plusieurs livraisons, audit + actions) — jamais le HANDOFF (il faut la conversation). Détail : [agents/README.md](agents/README.md).

## Plugins (stack et options — marketplace `claude-setup`)

- Marketplace (une fois) : `/plugin marketplace add kurt83340/claude-Setup`
- n8n → plugin officiel `n8n-mcp-skills` (check-first `claude plugin list` : souvent déjà en user-scope)
- BDD Alembic → `claude plugin install db-migration@claude-setup --scope project`
- Équipe d'agents (opt-in) → `claude plugin install agent-teams@claude-setup --scope project`, puis `/agent-teams:team` : le 1er lancement l'active (flag + mode d'affichage + rule d'équipe), relance de Claude Code requise.

## Version du template

`.claude/template-version`. Mise à jour des fichiers de méthode (hooks, skills, agents, rules, settings) sans toucher à la doc projet → `/upgrade-template` (merge 3 voies, conflits signalés, jamais d'écrasement silencieux).
