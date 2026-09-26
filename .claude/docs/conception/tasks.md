# Plan d'exécution MVP — {{PROJECT_NAME}}

> ⚠️ **Stable après design** — ne modifier que sur **pivot majeur** (sinon désync avec ROADMAP).
> Pour le status courant et les blockers → voir [../ROADMAP.md](../ROADMAP.md) (dashboard vivant).
>
> Ce fichier = **plan figé** décidé en phase conception : sous-phases, estimations, DoD.
> ROADMAP.md = **état dynamique** mis à jour à chaque session.

**Cible MVP :** {{YYYY-MM-DD}}
**Effort estimé total :** ~{{X}} jours-homme
**Pattern mirror :** ce fichier = équivalent macro de `specs/00X-feature/tasks.md`

---

## Phase 1 — MVP

### 1.1 — Composants (specs détaillées)

> Règles de découpe : **la spec 001 = tranche verticale minimale de bout en bout** (même
> moche — dé-risque l'archi, démo-able immédiat) · 1 spec = 1 livrable testable seul = 1 PR ·
> le transverse (erreurs, retry, monitoring) = sa propre spec.

| Spec                                                 | Estimation  | Status (voir ROADMAP) |
| ---------------------------------------------------- | ----------- | --------------------- |
| [001-{{feature-1}}](specs/001-{{feature-1}}/spec.md) | {{X jours}} | {{Pas commencé}}      |
| [002-{{feature-2}}](specs/002-{{feature-2}}/spec.md) | {{X jours}} | Pas commencé          |
| ...                                                  | ...         | ...                   |

### 1.2 — Intégration (assemblage)

- {{Workflow / assemblage des composants}} — **{{X jours}}**
- Tests E2E sur env {{staging}} — **{{X jour}}**
- Documentation flow dans [ARCHITECTURE.md section 4](ARCHITECTURE.md) — **0.5 jour**

### 1.3 — Validation & GO prod

- Smoke tests {{staging}} 48h sans erreur
- Demo {{décideur}} (prévu {{YYYY-MM-DD}})
- Validation écrite {{owner tech}}
- GO prod (deadline {{YYYY-MM-DD}})

### DoD Phase 1 (contrat figé)

- [ ] Toutes specs Phase 1 livrées (DoD individuelles cochées dans `specs/00X/tasks.md`)
- [ ] {{Tests pendant X heures stable}}
- [ ] {{Décideurs}} ont validé par écrit
- [ ] `RUNBOOK.md` créé (à la demande, au 1er déploiement prod) avec procédures rollback
- [ ] [../CHANGELOG.md](../CHANGELOG.md) à jour avec entry de release
- [ ] Coverage tests >= {{X}}%
- [ ] Monitoring opérationnel

---

## Phase 2 — {{Robustesse / Évolutions}} (post-MVP, cible {{date}})

### 2.1 — {{Sous-thème 1}}

- {{Item 1}}
- {{Item 2}}

### 2.2 — {{Sous-thème 2}}

- {{Item 1}}
- {{Item 2}}

### DoD Phase 2

- [ ] {{Critère 1}}
- [ ] {{Critère 2}}

---

## Phase 3 — Évolutions v2 (backlog, à discuter avec {{décideur}})

- {{Idée 1}} (voir [../idees/YYYY-MM-DD-...md](../idees/))
- {{Idée 2}}
- {{Idée 3}}

### DoD Phase 3

À définir lors du re-cadrage (impact PRD significatif).

---

## Cross-references

- **Status courant :** [../ROADMAP.md](../ROADMAP.md)
- **PRD source :** [PRD.md](PRD.md)
- **Architecture :** [ARCHITECTURE.md](ARCHITECTURE.md)
- **Specs détaillées par feature :** [specs/](../specs/)

## En cas de pivot

Si la hiérarchie demande un changement majeur :

1. Réunion documentée dans [../cadrage/reunions/YYYY-MM-DD-pivot.md](../cadrage/reunions/)
2. Update [../cadrage/README.md](../cadrage/README.md) (nouvelle direction)
3. Append section datée dans [research.md](research.md)
4. Bumper [PRD.md](PRD.md) (v1.0 → v2.0)
5. **Refonte de CE FICHIER** : nouvelle section `## Phase X — Refonte v2` avec son propre DoD
6. ROADMAP synchronisé avec les nouvelles phases
