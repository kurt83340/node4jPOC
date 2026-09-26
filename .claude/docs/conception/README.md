# Conception — Phase de design (macro + micro)

> Cette phase prend les inputs du `cadrage/` (brief + intake) et produit **tout le design** du projet :
>
> - **Design macro** (research, PRD, ARCHITECTURE, tasks) à la racine de ce dossier
> - **Design micro par feature** dans `../specs/` (dossier FRÈRE — remonté en v1.2)
>
> ⚠️ Le **ROADMAP n'est PAS ici** — il vit à la racine `../ROADMAP.md` car c'est un **dashboard vivant** lu/MAJ tous les jours.

## Ce que contient ce dossier

### Niveau MACRO (projet entier)

| Fichier                              | Quoi                                                  | Quand l'écrire                         |
| ------------------------------------ | ----------------------------------------------------- | -------------------------------------- |
| [`research.md`](research.md)         | Brainstorm initial + options explorées + pivots datés | Avant le PRD, append au fil des pivots |
| [`PRD.md`](PRD.md)                   | Spec produit (vision, scope, personas, métriques)     | Quand le brainstorm est mûr            |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Plan technique macro (stack, modules, sécurité, flux) | Après PRD validé                       |
| [`tasks.md`](tasks.md)               | Plan d'exécution MVP (sous-phases + DoD figés)        | Après PRD + ARCHITECTURE               |

### Niveau MICRO (une feature)

| Dossier                        | Quoi                                                       |
| ------------------------------ | ---------------------------------------------------------- |
| [`specs/00X-feature/`](../specs/) | 1 dossier par feature avec `{research,spec,plan,tasks}.md` |

### Diagrammes

| Cas                                                           | Où le mettre                                   |
| ------------------------------------------------------------- | ---------------------------------------------- |
| Diagramme technique simple (composants, séquence < 50 lignes) | Inline ASCII dans `ARCHITECTURE.md`            |
| Diagramme technique gros / éditable                           | `diagrams/X.excalidraw` + export `.svg` à côté |
| Diagramme feature simple                                      | Inline dans `specs/00X/plan.md`                |
| Diagramme feature gros                                        | `specs/00X/diagrams/` (créer si besoin)        |

Convention diagrammes détaillée : voir [diagrams/README.md](diagrams/README.md).

## Statut courant

- {{[ ] ou ✅}} Research initial : voir [research.md](research.md)
- {{[ ] ou ✅}} PRD v1.0 validé {{décideur}} le {{YYYY-MM-DD}}
- {{[ ] ou ✅}} Architecture validée {{owner tech}} le {{YYYY-MM-DD}}
- {{[ ] ou ✅}} Plan MVP : voir [tasks.md](tasks.md)
- {{🚧}} Specs en cours : voir [../ROADMAP.md](../ROADMAP.md) pour status courant

## Pattern mirror MACRO ↔ MICRO

Tu apprends UN pattern, tu l'appliques à 2 niveaux : macro ici (`conception/`) ↔ micro par feature (`specs/00X-feature/`) — `research`↔`research`, `PRD`↔`spec`, `ARCHITECTURE`↔`plan`, `tasks`↔`tasks`.

> 📋 **Table canonique** (correspondance ligne à ligne + colonne « question ») → **[STRUCTURE.md § Les 4 buckets dans docs/](../../STRUCTURE.md#les-4-buckets-dans-docs)** _(source unique — ne pas recopier ici pour éviter le drift)_.

→ `../ROADMAP.md` (racine) = **dashboard vivant** qui agrège le status (sync depuis `specs/00X/tasks.md`).

## Pivots éventuels

Si la hiérarchie demande un pivot, suivre ce protocole :

1. Capturer la réunion dans `../cadrage/reunions/YYYY-MM-DD-pivot.md`
2. Update `../cadrage/README.md` (nouvelle direction)
3. Append section `## Pivot YYYY-MM-DD` dans [research.md](research.md)
4. Bumper [PRD.md](PRD.md) (v1.0 → v2.0)
5. **Refonte** de [tasks.md](tasks.md) avec nouvelle section `## Phase X — Refonte v2`
6. Update [../ROADMAP.md](../ROADMAP.md) (nouvelle section v2 dashboard)
7. Si pivot technique : ADR dans `../adr/00XX-pivot-stack.md` qui supersede les anciens
