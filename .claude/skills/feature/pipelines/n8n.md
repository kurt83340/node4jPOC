# n8n — implémentation d'un workflow d'automatisation (type `automation-n8n`)

> Planifier → Construire → Valider → Tester en réel → Review adverse → Persister (export versionné)

> Prérequis : plugin **officiel** [`n8n-mcp-skills`](https://github.com/czlonkowski/n8n-skills) installé
> — check-first `claude plugin list` (souvent déjà en **user-scope** → rien à faire) ; sinon
> `/plugin marketplace add czlonkowski/n8n-skills` puis install `--scope user`
> — 14 skills + hooks d'enforcement, maintenu par czlonkowski (MIT). MCP **n8n-mcp** connecté
> si dispo (sinon fallback UI n8n + export manuel).

1. **Planifier** — action : `/spec "<titre>"` puis `/conception <id>` — le pattern d'architecture se choisit avec `/n8n-mcp-skills:n8n-workflow-patterns` (webhook ? schedule ? AI agent ? batch ?) — sortie : plan gelé, pattern retenu, nœuds pressentis, tasks partitionnées
2. **Construire** — action : bâtir le workflow (outils n8n-mcp — cf. `/n8n-mcp-skills:n8n-mcp-tools-expert` — sinon UI n8n), en s'appuyant sur `/n8n-mcp-skills:n8n-node-configuration` (config par opération), `/n8n-mcp-skills:n8n-expression-syntax` (mappings `{{ }}`), `/n8n-mcp-skills:n8n-code-javascript` ou `/n8n-mcp-skills:n8n-code-python` (Code nodes) — sortie : workflow construit, nœuds configurés, credentials référencées (JAMAIS en dur)
3. **Valider** — action : validation n8n-mcp + `/n8n-mcp-skills:n8n-validation-expert` pour interpréter erreurs/warnings (et écarter les faux positifs) — sortie : 0 erreur de validation, warnings arbitrés
4. **Tester en réel** — action : exécutions manuelles/webhook-test sur données représentatives — cas nominal ET cas d'erreur (payload malformé, API tierce en 4xx/5xx, rate limit — appui : `/n8n-mcp-skills:n8n-error-handling`) ; inspecter la sortie de CHAQUE nœud — sortie : run vert de bout en bout + comportement d'erreur vérifié (retry/continue/fail assumé)
5. **Review adverse** — action : subagent `reviewer` sur l'**export JSON** du workflow — axes : secrets/credentials absents du JSON, gestion d'erreurs, idempotence (re-run sûr ?), rate limits, nommage des nœuds — sortie : findings 🔴 corrigés, 🟠 arbitrés
6. **Persister** — action : export JSON versionné dans `workflows/<fonction-metier>.json` (cf. `workflows/README.md`) + `/feature-done <id>` (+ `/lecon` si pièges ; + **RUNBOOK.md si mise en prod** — règle du template) — sortie : JSON commité, ROADMAP/CHANGELOG/HANDOFF à jour
