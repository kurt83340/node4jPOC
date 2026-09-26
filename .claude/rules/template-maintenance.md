---
paths:
  - ".claude/docs/**"
---

# Doc projet — comment la faire vivre (chargée dès qu'un fichier de `.claude/docs/` est lu)

> Invariants et déclencheurs seulement. Les FORMATS vivent dans les skills qui écrivent (source
> unique — ne pas les redupliquer ici) :
- HANDOFF → `/handoff` · leçon → `/lecon`
- spec → `/spec` + `/conception` · livraison → `/feature-done` · pivot client → `/pivot`
- ADR → `/adr` · idée → `/idee` · code-map → `/codemap` · audit → `/doc-health`

> Arborescence complète, modèles de fichiers, exemples : [STRUCTURE.md](../STRUCTURE.md).

## 3 mémoires, 3 usages

| Mémoire | Contenu | Qui écrit | Versionné |
| --- | --- | --- | --- |
| `.claude/docs/` | état du projet, décisions, specs, leçons — **partagé** | skills doc, validés par l'utilisateur | ✅ |
| auto-memory (`~/.claude/projects/…/memory/`) | patterns techniques, préférences — **cache machine** | Claude, au fil de l'eau | ❌ |
| `/resume` (transcript) | reprise exacte d'UNE session | natif | ❌ |

Un pattern stable de l'auto-memory se **promeut** en rule / leçon / ADR (`/doc-health` le propose) :
le « n'oublie rien » durable passe par `.claude/docs/`.

## Budget de contexte (fichiers auto-chargés)

- `HANDOFF.md` : **réécrit** à chaque `/handoff`, ≤ 40 lignes — jamais empilé ; historique → `HANDOFF-journal.md` (append-only, non chargé).
- `code-map.md` : vue macro + règles de couplage + intention, < 3k tokens. Les gotchas vont dans `code-map-gotchas.md` (non chargé ; le hook injecte ceux du fichier édité).
- Tout autre doc = **lien simple** depuis CLAUDE.md, jamais `@` (un `@` recharge le fichier à CHAQUE appel). Contrôle : `python3 .claude/skills/doc-health/scripts/context-budget.py`.

## Quand créer un fichier (à la demande, JAMAIS préventivement)

| Déclencheur | Fichier |
| --- | --- |
| 1er credential / accès à obtenir | `ACCESS.md` — OÙ trouver l'accès, jamais la valeur |
| 1er déploiement prod | `RUNBOOK.md` |
| Terme métier récurrent non expliqué (> 3 fois) | `GLOSSARY.md` |
| ≥ 5 interlocuteurs / plusieurs équipes client | `STAKEHOLDERS.md` (modèle : STRUCTURE.md) — sinon § Interlocuteurs de `cadrage/README.md` |
| Démarrage d'une feature | `specs/00X-<slug>/` via `/spec` |
| Décision qui survit à la feature ou touche plusieurs specs | ADR via `/adr` (`adr/00XX-<scope>-<titre>.md`) |
| Décision locale à UNE feature | `specs/00X/plan.md` § Décisions (pas d'ADR) |
| Idée pas mûre | `idees/YYYY-MM-DD-<titre>.md` via `/idee` |
| Bug, piège, observation à décider plus tard | entrée dans `lecons.md` via `/lecon` |
| Piège lié à un fichier / une zone du code | bullet dans `code-map-gotchas.md` (citer le chemin en backticks) |
| Nouvelle règle de couplage / contrainte d'archi | `code-map.md` (jamais de description fichier par fichier) |
| Nouvelle lib, service tiers, LLM | table de `stack.md` |
| Doc, ticket, compte-rendu reçus du client | `cadrage/documents/` · `cadrage/tickets/<ID>-<titre>.md` · `cadrage/reunions/YYYY-MM-DD-<sujet>.md` (verbatim) |
| Diagramme | ASCII inline par défaut ; gros schéma → `diagrams/<x>.excalidraw` + export `.svg` à côté |

## Invariants

1. Jamais d'overwrite silencieux : diff montré → validation de l'utilisateur → écriture.
2. ADR **immuable** : on ne l'édite pas, on le supersede (`supersedes: 00XX` ; l'ancien passe `superseded`).
3. Numérotation continue `00X` (specs) / `00XX` (ADR) : max + 1, jamais réutilisée.
4. ROADMAP = machine à états `[ ]` → `[~] **EN COURS**` → `[x] livré YYYY-MM-DD`, synchronisée avec le frontmatter `status:` de `spec.md`.
5. Dates ISO `YYYY-MM-DD` ; liens relatifs.
6. Rien de déductible du code dans la doc (rôle des fichiers, imports, signatures) — ça dérive.
7. Aucun secret dans `.claude/docs/`.
8. `cadrage/` = entrées externes (client, tickets, réunions — verbatim, statiques hors pivot) ; `idees/` = brainstorm interne.
9. En agent team : seul le lead écrit HANDOFF, ROADMAP, CHANGELOG, code-map (+ gotchas), `adr/README.md`, `lecons.md` et alloue les numéros — les teammates rapportent.

## Session

- Début : HANDOFF et code-map sont déjà en contexte — lire la spec en cours si besoin, pas tout `.claude/docs/`.
- Fin : `/handoff`, dans le fil principal (lui seul a la conversation : échecs tentés, blockers).
- Feature terminée : `/feature-done` (ROADMAP, CHANGELOG, HANDOFF, ADR proposés).
- Chaque semaine : `/doc-health` (fraîcheur, ADR manquants, drift code-map, budget de contexte).
