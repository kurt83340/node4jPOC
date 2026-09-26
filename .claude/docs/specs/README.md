# specs/ — Design micro par feature

> 1 sous-dossier par feature, numéroté séquentiellement (`001-`, `002-`, …).
> Pattern mirror du macro `conception/` : research → spec → plan → tasks.

## Convention

```
specs/
├── 001-<feature-slug>/
│   ├── research.md      # brainstorm feature : options techniques, libs envisagées
│   ├── spec.md          # PRD feature (QUOI/POURQUOI) : CDA, user stories
│   ├── plan.md          # plan technique feature (COMMENT) : archi interne, libs, patterns
│   ├── tasks.md         # checklist exécutable : #1, #2, … + DoD feature
│   ├── data-model.md    # OPTIONNEL : schéma BDD ou modèle de données
│   └── diagrams/        # OPTIONNEL : si gros besoin de diagrammes spécifiques
├── 002-<feature-slug>/
│   └── ...
└── README.md            # ce fichier
```

## Naming

- **Numérotation séquentielle continue** : 001, 002, 003, … jamais de reset entre phases
- **Slug court en kebab-case** : `001-auth-jwt`, `002-export-pdf`, `003-rate-limit`

## Quand créer une spec

✅ Tu démarres une nouvelle feature → crée `00X-feature-slug/` + les 4 fichiers de base
❌ Petite modif / bug fix → pas besoin de spec (juste commit + entry CHANGELOG)

## Pattern mirror macro ↔ micro

Chaque fichier d'une spec a son équivalent macro dans `conception/` : `research`↔`research`, `spec`↔`PRD`, `plan`↔`ARCHITECTURE`, `tasks`↔`tasks`.

> 📋 **Table canonique** (correspondance ligne à ligne + colonne « question ») → **[STRUCTURE.md § Les 4 buckets dans docs/](../../STRUCTURE.md#les-4-buckets-dans-docs)** _(source unique — ne pas recopier ici pour éviter le drift)_.

## Cross-références

- **ROADMAP global** : [`../ROADMAP.md`](../ROADMAP.md) agrège le status des features
- **Plan MVP figé** : [`../tasks.md`](../conception/tasks.md) montre où s'inscrivent les features dans le plan
- **Promotion ADR** : si une décision dans `plan.md` survit à la feature OU impacte plusieurs specs → créer ADR dans [`../adr/`](../adr/)

## Démarrer une nouvelle spec

**Le plus simple : `/spec "<titre>"`** (skill) — scaffolde les 4 fichiers + met à jour la ROADMAP. À la main :

```bash
# 1. Créer le dossier
mkdir -p .claude/docs/specs/00X-feature-slug

# 2. Copier les 4 templates bundlés du skill /spec
cp .claude/skills/spec/templates/{research,spec,plan,tasks}.md \
   .claude/docs/specs/00X-feature-slug/
# 3. Remplir research.md d'abord (exploration), puis spec.md, plan.md, tasks.md
# 4. Cocher la feature dans .claude/docs/ROADMAP.md
```

## Template d'une spec (à copier dans 00X-feature/)

Source de vérité = les templates bundlés `.claude/skills/spec/templates/`.
Exemple rempli (référence optionnelle) : `EXAMPLES/acme-sync-erp-notion-docs/specs/001-erp-connector/` — dans le **repo template claude-Setup** (exclu des projets générés).
