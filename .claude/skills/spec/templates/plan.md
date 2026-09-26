# Plan — {{SPEC_TITRE}}

> COMMENT on implémente la feature `{{SPEC_ID}}-{{SPEC_KEBAB}}`.

**Date :** {{SPEC_DATE}}

## Approche technique

{{Description de l'approche en 3-5 phrases. Pattern principal utilisé.}}

## Architecture

```
{{Diagramme ASCII inline ou ref vers diagrams/}}
```

## Modules / fichiers impactés

| Fichier     | Action                | Notes                    |
| ----------- | --------------------- | ------------------------ |
| `src/...`   | nouveau / modif / del | {{role}}                 |
| `tests/...` | nouveau               | tests unit + integration |

## Flux de données

1. {{Étape 1 : input → process → output}}
2. {{Étape 2}}
3. {{Étape 3}}

## Erreurs / cas limites

| Cas                    | Comportement attendu                   |
| ---------------------- | -------------------------------------- |
| {{Input invalide}}     | {{validation upstream, message clair}} |
| {{Service tiers down}} | {{retry 3x, fallback X, log Sentry}}   |
| {{Rate limit atteint}} | {{sleep + retry, alert si > 5 min}}    |

## ## Décisions (locales à cette feature)

> Décisions tech **locales** à cette spec uniquement. Si cross-feature → promouvoir en ADR via `/adr`.

### D1 — {{titre}}

**Choix :** {{option retenue}}
**Pourquoi :** {{1-2 phrases}}
**Alternatives écartées :** {{...}}

### D2 — {{titre}}

...

## Sécurité

- {{Authent / autoris}}
- {{Données sensibles : où / comment}}
- {{Logs : ne pas leak credentials/PII}}

## Performance

- {{Cibles : latence, throughput, memory}}
- {{Bottleneck connu}}

## Tests

- **Unit** : {{couverture cible, fichiers tests}}
- **Integration** : {{scénarios E2E principaux}}
- **Load** : {{si applicable}}

## Circuit breakers (conditions d'arrêt — à définir AVANT de coder)

> Si une condition se déclenche : STOP — on ne s'acharne pas. Retour `/conception {{SPEC_ID}}-{{SPEC_KEBAB}}`
> (replanifier) ou parking documenté (ROADMAP + HANDOFF § Blocked on). Au-delà du breaker,
> l'agent ne produit plus du code faux mais du code hors-sujet.

- {{3 échecs consécutifs sur la même tâche → l'approche est mauvaise, replanifier}}
- {{Le fix d'un test en casse ≥ 2 autres, deux fois de suite → conflit d'archi, remonter}}
- {{Accès/dépendance externe manquant (ACCESS.md) → parking + relance client}}

## Liens

- Spec : [spec.md](spec.md)
- Research : [research.md](research.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : {{liste}}
