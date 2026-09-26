# HANDOFF — {{YYYY-MM-DD HHhMM}}

> Court, narratif, versionné. **Patterns techniques** → auto-memory (Claude le gère).
> **Reprise précise** → utilise `/resume`. Ce fichier = "où j'en suis" pour démarrage à froid.

**Branche** : `{{feature/00X-name | main}}`
**Spec en cours** : [{{00X-feature}}/](specs/{{00X-feature}}/spec.md) ({{X/Y tasks}})
**Goal session** : {{ce que je voulais faire cette session}}

## Status

- {{✅ ou ⏳}} {{Tests : commande + résultat}}
- {{✅ ou ⏳}} {{Lint / type check}}
- {{✅ ou ⏳}} {{Autre check}}

## Échecs tentés (à ne pas refaire)

- {{Approche A tentée → pourquoi KO}}
- {{Approche B → pourquoi rejetée}}

## Blocked on

- {{Bloqueur 1 : attente accès / dépendance externe / question}}
- {{Bloqueur 2}}

## Next (par ordre)

1. **{{Task #N}}** : {{description courte}}
2. **{{Task #N+1}}** : ...
3. {{Étape suivante}}

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: {{00X-slug | aucune}}
Task: {{T2.3 | aucune}}
Fichiers en cours: {{src/a.py, tests/test_a.py | aucun}}
Bloqué sur: {{rien | description courte}}
Commande de reprise: {{/conception 00X | /feature "..." | pytest tests/ -q | aucune}}
