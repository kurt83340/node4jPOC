---
name: pivot
description: Orchestre le workflow pivot client (9 étapes) — quand le client change d'avis ou la direction change. Capture la réunion pivot, update cadrage, append research dated, bump PRD, refonte tasks, update ROADMAP v2, crée ADR pivot si technique, append leçon, update HANDOFF. Validation user à chaque étape (jamais d'overwrite silencieux).
allowed-tools: Read, Write, Edit, Glob, Bash(date:*), Bash(ls:*), AskUserQuestion
disable-model-invocation: false
argument-hint: "<raison-courte>"
---

# /pivot — Workflow pivot client (9 étapes)

> **Quand ne PAS utiliser** : une idée à explorer (pas un changement de cap acté) → `/idee` ·
> changement local à UNE feature → `/conception <spec-id>` (re-planifier la spec).
> **Réversibilité** : 🟠 réorganise cadrage/PRD/ROADMAP/specs — chaque étape validée en diff,
> l'historique est préservé par design (append datés, jamais d'overwrite) ; undo via git.

Ton rôle : orchestrer le changement de direction d'un projet sans casser l'historique. Chaque étape demande validation à l'user.

> 🧭 **Foyer unique du workflow pivot.** L'agent `doc-maintainer` ne redéfinit PAS ces étapes :
> il **invoque ce skill**. Toute évolution du pivot se fait ici (et nulle part ailleurs).

## Usage

```
/pivot "Client veut passer en SaaS au lieu d'on-premise"
/pivot "Sortie de Notion v2 → ré-architecture nécessaire"
```

## Quand l'utiliser

- Le décideur change la priorité majeure (scope ou direction)
- Une nouvelle contrainte technique invalide l'archi (ex. service tiers déprécié)
- Le marché bouge → on doit pivoter le produit

**Quand NE PAS l'utiliser** :

- Petit ajustement de feature (utiliser `/feature-done` puis nouvelle spec)
- Changement de lib interne (utiliser section `## Décisions` dans `plan.md`)
- Bug fix (utiliser `/lecon` puis correction)

## Pré-requis

1. La réunion pivot a déjà eu lieu (ou est documentée par mail/Slack)
2. L'user a une idée claire de la nouvelle direction

## Étape 1 — Capturer la réunion pivot

```bash
DATE=$(date +%Y-%m-%d)
FILE=".claude/docs/cadrage/reunions/${DATE}-pivot.md"
```

Demander à l'user (AskUserQuestion ou prompt libre) :

- **Participants** : qui était là ?
- **Décisions prises** : 3-5 points clés
- **Nouvelle direction** : 1 paragraphe
- **Risques nouveaux**

Créer le fichier `reunions/YYYY-MM-DD-pivot.md`. Présenter le diff au user avant write.

## Étape 2 — Update `.claude/docs/cadrage/README.md`

Section "Demande exprimée" : append en bas :

```markdown
## Pivot YYYY-MM-DD — {{Raison courte}}

**Avant** : {{ancien scope}}
**Après** : {{nouveau scope}}
**Raison** : {{justification}}
**Décideur** : {{nom}}
**CR pivot** : [reunions/YYYY-MM-DD-pivot.md](reunions/YYYY-MM-DD-pivot.md)
```

Présenter le diff. Si user OK → write.

## Étape 3 — Append section pivot dans `.claude/docs/conception/research.md`

Si `research.md` existe (peut être absent pour script-jetable) :

```markdown
## Pivot YYYY-MM-DD — {{Raison}}

**Contexte** : {{ce qui a changé depuis le research initial}}
**Nouvelles options à explorer** :

- Option A' — {{...}}
- Option B' — {{...}}

**Décision préliminaire** : {{...}}
```

## Étape 4 — Bumper `.claude/docs/conception/PRD.md`

Si `.claude/docs/conception/PRD.md` existe :

- Trouver la version actuelle (`v1.0`, `v2.0`, etc.) dans le header
- Bumper la version majeure (`v1.0` → `v2.0`)
- Ajouter en haut une section :

  ```markdown
  ## Changelog PRD

  - **v2.0** ({{YYYY-MM-DD}}) : pivot — {{raison}}
  - **v1.0** ({{date initiale}}) : version initiale
  ```

- Adapter les user stories impactées (mentionner ce qui change)

## Étape 5 — Refonte `.claude/docs/conception/tasks.md`

Si `tasks.md` existe :

- Marquer les sous-phases inachevées comme `[~] ABANDONNÉ (pivot YYYY-MM-DD)`
- Ajouter une nouvelle section :

  ```markdown
  ## Phase X — Refonte v2 ({{cible YYYY-MM-DD}})

  Suite au pivot du {{date}} : nouvelle direction.

  ### Sous-phase X.1 — {{nom}}

  - [ ] T1 : {{...}}
    - DoD : {{...}}
  ```

## Étape 6 — Update `.claude/docs/ROADMAP.md`

Si `.claude/docs/ROADMAP.md` existe :

- Ajouter section en haut :

  ```markdown
  ## 🔄 Pivot YYYY-MM-DD — {{Raison}}

  → Voir [conception/tasks.md](conception/tasks.md) section "Refonte v2"
  → Voir [cadrage/reunions/YYYY-MM-DD-pivot.md](cadrage/reunions/...)

  ### Status pivot

  - [~] **Refonte v2 EN COURS** (0/N tasks)
  - [~] Specs v1 archivées
  ```

- Marquer les specs v1 inachevées avec ⚠️ comme "ABANDONNÉ pivot YYYY-MM-DD"

## Étape 7 — ADR si pivot technique

Si le pivot impacte la **stack technique** ou l'**architecture** :

```
/adr cadrage "Pivot stack {{description}}"
```

Le skill `/adr` gérera :

- Création du nouveau ADR
- Pattern supersede (les anciens ADRs `mvp` impactés deviennent `status: superseded`)
- Update du `adr/README.md` (archived section)

Si l'user n'est pas sûr → proposer "non, pas d'ADR pour l'instant, on verra plus tard".

## Étape 8 — Append leçon post-mortem

Pour capitaliser sur le pivot (pourquoi est-ce arrivé, comment l'éviter) :

```
/lecon cadrage "Pivot YYYY-MM-DD — {{raison courte}}"
```

Contenu suggéré : signaux faibles qu'on aurait pu voir avant.

## Étape 9 — Update .claude/docs/HANDOFF.md

```markdown
**Goal session** : pivot du projet → refonte v2
**Next** :

1. Démarrer specs v2 depuis tasks.md "Refonte v2"
2. Communiquer aux stakeholders (mail récap)
3. Update .claude/docs/CHANGELOG.md (section Changed : "pivot vYYYY.MM.DD")
```

## Sortie attendue

```
✅ Pivot {{raison}} orchestré

📝 Fichiers créés :
- .claude/docs/cadrage/reunions/2026-06-15-pivot.md

📝 Fichiers mis à jour :
- .claude/docs/cadrage/README.md (section Pivot ajoutée)
- .claude/docs/conception/research.md (section pivot append)
- .claude/docs/conception/PRD.md (v1.0 → v2.0, changelog ajouté)
- .claude/docs/conception/tasks.md (refonte v2 section ajoutée)
- .claude/docs/ROADMAP.md (section pivot en haut, specs v1 archivées)

📚 ADRs :
- ADR-0007-cadrage-pivot-stack.md créé (supersede ADR-0003)

📝 Leçon :
- .claude/docs/lecons.md : entry "Pivot 2026-06-15" status 🆕 new

📋 Communication :
- Penser à : email récap décideur + update CHANGELOG section Changed
```

## Anti-patterns

- ❌ Pivoter sans capture de réunion (perte de traçabilité)
- ❌ Supprimer les anciens fichiers/ADRs au lieu de les marquer superseded
- ❌ Skip l'update PRD version (perte de l'historique des décisions)
- ❌ Refaire toutes les specs from scratch (le code v1 reste partiellement réutilisable)
- ❌ Skip la leçon post-mortem (l'user va re-pivoter dans 3 mois sans rien apprendre)
