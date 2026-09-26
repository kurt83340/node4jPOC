# Tasks — {{SPEC_TITRE}}

> Checklist d'exécution pour `{{SPEC_ID}}-{{SPEC_KEBAB}}`. Coche au fur et à mesure.
> **DoD typée** : chaque tâche finit sur un critère VÉRIFIABLE, jamais une impression.
> 3 types : `command_passes:` (commande qui exit 0) · `file_exists:` (chemin présent) ·
> `manual:` (validation humaine explicite — dernier recours, à minimiser).
> **Budget : ~35 min de travail agent par phase max** — au-delà, l'agent ne se trompe plus,
> il « perd le fil » (échecs ×4 constatés en télémétrie, Morph 2026) → découper la phase.

**Date :** {{SPEC_DATE}}
**Status :** [ ] 0/N tasks → MAJ au fil de l'eau

## Phase 1 — {{nom phase, ex: Setup}}

- [ ] **T1.1** : {{description courte}}
  - DoD : `command_passes: {{pytest tests/test_x.py -q}}`
- [ ] **T1.2** : {{...}}
  - DoD : `file_exists: {{src/module.py}}`
- [ ] **T1.3** : {{...}}
  - DoD : `manual: {{si non automatisable — ex. le client valide la maquette}}`

## Phase 2 — {{nom phase, ex: Implémentation}}

- [ ] **T2.1** : {{...}}
  - DoD : `command_passes: {{...}}`
- [ ] **T2.2** : {{...}}
  - DoD : `command_passes: {{...}}`

## Phase 3 — Tests + livraison

- [ ] **T3.1** : tests unitaires verts — DoD : `command_passes: {{pytest -q (couverture >= X%)}}`
- [ ] **T3.2** : tests d'intégration verts — DoD : `command_passes: {{scénario principal}}`
- [ ] **T3.3** : lint / type check OK — DoD : `command_passes: {{ruff check && mypy src/}}`
- [ ] **T3.4** : update .claude/docs/code-map.md si nouveaux modules
- [ ] **T3.5** : `/feature-done {{SPEC_ID}}-{{SPEC_KEBAB}}`

## Definition of Done (global)

La feature est livrée quand :

- [ ] Tous les critères d'acceptation de [spec.md](spec.md) cochés
- [ ] Tests verts (unit + integration)
- [ ] Pas de TODO ou `// FIXME` dans le code
- [ ] Pas de leak credentials/secrets
- [ ] Documentation à jour (code-map, plan.md décisions)
- [ ] ADRs créés pour les décisions structurantes
- [ ] Commit + tag git

## Blockers / questions

- {{Blocker actif 1 : besoin accès / décision client}}
- {{Question ouverte sur point technique X}}
