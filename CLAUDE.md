# {{PROJECT_NAME}}

{{1-2 phrases qui résument le projet : "Automatisation X pour Y" / "App de gestion Z" / etc.}}

> 🧭 **Comment marche & vit ce template** (skills, structure, workflow, agent) → [.claude/CLAUDE.md](.claude/CLAUDE.md)

## Documentation projet

> 🪶 **Chargement just-in-time** : seuls les **2** docs d'état vivant ci-dessous sont auto-chargés (`@`) ; le reste = **liens simples** lus à la demande (un `@` recharge le fichier à CHAQUE appel). Budget : `python3 .claude/skills/doc-health/scripts/context-budget.py` (seuil 25k).

### 🔄 Auto-chargés (`@` — état vivant, toujours en contexte)

- Reprise session : @.claude/docs/HANDOFF.md ⭐ (≤ 40 lignes — journal append-only dans [HANDOFF-journal.md](.claude/docs/HANDOFF-journal.md), lu à la demande)
- **Code map** : @.claude/docs/code-map.md ⭐ (vue macro + règles de couplage + intention, < 3k tokens — les gotchas vivent dans [code-map-gotchas.md](.claude/docs/code-map-gotchas.md), injectés par le hook pour le seul fichier édité)

### 📂 Lus à la demande (liens — pas auto-chargés)

- 🗺️ **Roadmap** (dashboard) : [ROADMAP.md](.claude/docs/ROADMAP.md) — lu par `/spec`, `/conception`, `/feature-done`, `/doc-health`
- 📥 **Cadrage** : [cadrage/README.md](.claude/docs/cadrage/README.md)
- 🎨 **Conception** : [research](.claude/docs/conception/research.md) · [PRD](.claude/docs/conception/PRD.md) · [ARCHITECTURE](.claude/docs/conception/ARCHITECTURE.md) · [tasks (plan MVP)](.claude/docs/conception/tasks.md) · specs → `.claude/docs/specs/00X-feature/`
- 🔄 **Suivi** : [ACCESS](.claude/docs/ACCESS.md) · [CHANGELOG](.claude/docs/CHANGELOG.md) · [leçons](.claude/docs/lecons.md) · [stack](.claude/docs/stack.md)
- 📚 **Transversaux** : [ADR](.claude/docs/adr/) · [GLOSSARY](.claude/docs/GLOSSARY.md) · [RUNBOOK](.claude/docs/RUNBOOK.md)

## Conventions techniques

> Les règles dans `.claude/rules/*.md` sont **déjà auto-chargées** par Claude Code — pas besoin de `@-import` ici (ce serait du double chargement). Idéalement, scope-les par chemin (frontmatter `paths:`) pour qu'elles ne chargent que sur les fichiers concernés.

- [code-style Python](.claude/rules/code-style.md) · [testing Python](.claude/rules/testing.md) · [code-style web](.claude/rules/code-style-web.md) · [testing web](.claude/rules/testing-web.md) · [git-workflow](.claude/rules/git-workflow.md) · [doc-lookup](.claude/rules/doc-lookup.md)

## Reminders critiques

- Credentials **JAMAIS** dans le repo (stockage : `.claude/docs/ACCESS.md`)
- `.claude/docs/HANDOFF.md` à update **à chaque fin de session** (via `/handoff`)
- Décision tech structurante → créer un ADR (via `/adr`)
- ADR **immuable** : on ne modifie jamais, on crée un nouveau qui supersede

---

> ℹ️ **Tous les placeholders ne sont pas obligatoires** — adapte selon ton projet (script jetable = 30%, projet client = 70-80%, enterprise = 100%). Supprime les sections non pertinentes.
