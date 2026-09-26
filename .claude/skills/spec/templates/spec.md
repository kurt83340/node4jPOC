---
status: draft # draft | validated | in-progress | done | parked
progress: 0/0 # X/Y tasks (compté depuis tasks.md) — MAJ par /feature-done ou à la main
---

# Spec — {{SPEC_TITRE}}

> Vision micro : QUOI on construit et POURQUOI. Pas de "comment" (c'est dans plan.md).
> Le frontmatter `status:` = source **machine-readable** de l'état. La ROADMAP doit lui rester
> cohérente (`[ ]`=draft/validated · `[~]`=in-progress · `[x]`=done — audité par `/doc-health`).

**ID :** `{{SPEC_ID}}-{{SPEC_KEBAB}}`
**Date :** {{SPEC_DATE}}

## Vision

{{En 1-2 phrases : qu'est-ce que cette feature apporte ? Pour qui ?}}

## User stories

### US1 — {{titre}}

**En tant que** {{persona}},
**je veux** {{action}},
**afin de** {{bénéfice}}.

**Critères d'acceptation :**

- [ ] {{critère 1 mesurable}}
- [ ] {{critère 2}}

### US2 — {{titre}}

...

## Scope IN

- {{Ce qui est dans la feature}}
- {{...}}

## Scope OUT

- {{Ce qui est explicitement HORS feature (peut-être v2)}}
- {{...}}

## Métriques de succès

- {{Métrique 1 : ex. P95 latence < 200ms}}
- {{Métrique 2 : ex. zero error rate sur 1 semaine}}

## Dépendances

- {{Feature 00X-... doit être livrée avant}}
- {{Accès XYZ requis (voir .claude/docs/ACCESS.md)}}

## Liens

- Research : [research.md](research.md)
- Plan technique : [plan.md](plan.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : {{liste}}
