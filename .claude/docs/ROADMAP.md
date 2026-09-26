# Roadmap — {{PROJECT_NAME}} (DASHBOARD)

> **Vue dynamique** : status courant + blockers + ce qui bouge.
> **Plan figé** (sous-phases, estimations, DoD) → [conception/tasks.md](conception/tasks.md).
> MAJ à chaque session ou via `/feature-done`.

**Dernière MAJ :** {{YYYY-MM-DD}}

## ✅ Phase 0 — Setup ({{livré YYYY-MM-DD | en cours}})

{{Cadrage + conception + setup local}}

## 🚧 Phase 1 — MVP (en cours, cible {{YYYY-MM-DD}})

**Plan détaillé :** [conception/tasks.md](conception/tasks.md) section Phase 1

### Composants

- [ ] [001-{{feature-1}}](specs/001-{{feature-1}}/spec.md) — {{0/Y tasks}}
- [ ] [002-{{feature-2}}](specs/002-{{feature-2}}/spec.md) — pas commencé
- [ ] ...

### Intégration

- [ ] {{Workflow / assemblage}}
- [ ] Tests E2E
- [ ] Validation {{décideurs}} → GO prod

### Risques courants

- {{Risque actif 1 : ex. accès en attente, VPN flaky}}
- {{Risque actif 2}}

## 📋 Phase 2 — {{Nom phase}} (post-MVP)

Voir [conception/tasks.md](conception/tasks.md) section Phase 2.

- [ ] {{Feature 004}}
- [ ] {{Feature 005}}
- [ ] {{Feature 006}}

## 💡 Backlog v2 (à discuter)

- {{Idée 1}} (voir [idees/YYYY-MM-DD-...md](idees/))
- {{Idée 2}}

---

## Conventions

- `[ ]` = planifié, pas commencé
- `[~]` = en cours (mettre en **gras**)
- `[x]` = livré
- Numéro de spec continue (001 → 002 → 003 → …) — pas de reset entre phases
- Format `X/Y tasks` = compté depuis `specs/00X/tasks.md`
