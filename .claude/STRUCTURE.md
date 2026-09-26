# Structure projet Claude Code — Template

> Convention 2026, basée sur Spec-Driven Development (Spec Kit GitHub) + retours d'expérience.
> Source de vérité pour démarrer un nouveau projet proprement.
> Adapté pour solo dev qui fait code + automatisations (n8n, Python, BDD, mini apps) pour différents clients/services.

## 🚀 Pour démarrer un nouveau projet

1. **Copie** tout le contenu de `template/` (racine) dans ton nouveau dossier projet
2. **Remplis les placeholders `{{...}}`** au fur et à mesure (cadrage → conception → impl)
3. **Tous les placeholders ne seront PAS utilisés sur tous les projets** :
   - Petit script Python jetable → tu utiliseras peut-être 30% (cadrage + spec rapide + HANDOFF)
   - Projet client moyen → 70-80% (tout sauf RUNBOOK si pas encore prod)
   - Gros projet enterprise → 100% + tu rajoutes STAKEHOLDERS.md
4. **Voir `EXAMPLES/acme-sync-erp-notion-docs/`** = exemple complet rempli (dans le **repo template** ; exclu de ton projet par l'init). Référence quand tu doutes « comment je remplis cette section ? ».
5. **Automatique** : lance `/init-from-template` (skill bundled) qui pose 10 questions (CORE placeholders : nom projet, client, décideur, commandes stack…), substitue auto + lance `cleanup-for-type.py` adapté au type de projet. Cf [USAGE.md](USAGE.md) section "Setup nouveau projet" pour la procédure complète.
6. **Projet déjà généré, template plus récent** → `/upgrade-template` : merge 3 voies des fichiers de méthode, doc projet intacte. Cf [USAGE.md](USAGE.md) section "Mettre à jour un projet existant".

## Arborescence complète

> 📌 **Convention :** seuls les fichiers de config et livrables sont à la racine.
> TOUT le reste (docs, specs, rules, agents, skills) vit dans `.claude/`.

```
mon-projet/
├── CLAUDE.md                       # index PROJET — résumé + nav doc + conventions (≤ 60 lignes, 2 `@` : HANDOFF + code-map ; méthode → .claude/CLAUDE.md)
├── README.md                       # setup local du projet (humain dev, comment lancer/tester/déployer)
├── .env.example                    # template des variables d'env (sans valeurs — vraies valeurs en .env gitignored)
├── .gitignore                      # exclusions Git : TOUS les .env* (sauf gabarits .env.example/.sample/.template), secrets.*, *.key/*.pem, build, cache…
├── .pre-commit-config.yaml         # garde-fou secrets au commit (gitleaks) — `pre-commit install` proposé par l'init
├── workflows/                      # livrables n8n exportés en JSON (versionnés pour history + rollback)
│   └── sync-erp.json               # 1 fichier par workflow, nom = fonction métier
│
└── .claude/                        # TOUTE la matière première (méthode + doc) — Claude y lit à la demande
    │
    ├── CLAUDE.md                   # index MÉTHODE mince (~2,5 Ko) : où est quoi, pipelines, agents, plugins, version (chargé EN PLUS du CLAUDE.md racine)
    │                               # (les anciennes "commands/" ont fusionné avec les skills → tout vit dans skills/)
    ├── USAGE.md                    # guide humain : setup, workflows, hooks, mise à jour (lu à la demande)
    ├── STRUCTURE.md                # CE fichier : arborescence + conventions (naming, ADR, statuts, diagrammes, quand créer)
    ├── template-version            # version du template qui a généré / mis à jour le projet (ex. 1.5.0)
    ├── template-lock.json          # écrit à l'init : version + profil + mode + source (JAMAIS les variables d'init) — base de /upgrade-template
    │
    ├── rules/                      # règles modulaires AUTO-chargées par Claude Code — jamais en `@` ; scopées `paths:` = chargées quand un fichier concerné est lu
    │   ├── code-style.md           # Python : outils + conventions (scopée *.py) — retirée par le profil web-app
    │   ├── testing.md              # Python : framework, structure des tests, coverage (scopée *.py) — retirée par web-app
    │   ├── code-style-web.md       # TS/JS : outils + conventions (scopée *.ts/*.js…) — retirée par les profils Python
    │   ├── testing-web.md          # TS/JS : framework, structure des tests (scopée) — retirée par les profils Python
    │   ├── git-workflow.md         # convention commits (Conventional Commits), branches, PRs, tags
    │   ├── doc-lookup.md           # recherche de doc externe : context7 (MCP) → MCP docs → web — SOURCE UNIQUE
    │   ├── template-maintenance.md # invariants d'écriture de la doc (scopée `paths: .claude/docs/**`) — formats → skills, conventions → CE fichier
    │   └── (agent-teams.md)        # OPT-IN — posée par le 1er `/agent-teams:team` (plugin) : invariants lead/teammate ; absente du cœur
    │
    ├── skills/                     # skills perso — À PLAT (Claude Code scanne 1 niveau, cf issue #18192)
    │   ├── README.md               # INVENTAIRE canonique des skills cœur (compte CI-vérifié) + conventions (préfixe, plugins, import)
    │   ├── handoff/SKILL.md        # /handoff
    │   ├── spec/SKILL.md           # /spec (scaffold feature)
    │   ├── conception/SKILL.md     # /conception — explore → options → plan arrêté + revue adverse
    │   ├── debug/SKILL.md          # /debug — reproduire (test rouge) → cause → fix minimal → leçon
    │   ├── feature/SKILL.md        # /feature — orchestrateur de pipeline (+ pipelines/ : standard, tdd, customs déposables)
    │   ├── feature-done/SKILL.md
    │   ├── adr/SKILL.md            # 4 modes : capture/supersede/deprecate/list
    │   ├── lecon/SKILL.md          # 4 modes : capture/promote/discard/archive
    │   ├── idee/SKILL.md           # 4 modes : capture/promote/discard/archive
    │   ├── doc-health/SKILL.md
    │   ├── codemap/SKILL.md
    │   ├── pivot/SKILL.md          # workflow 9 étapes
    │   ├── archive-projet/SKILL.md # /archive-projet — fin de vie : bilan, marquage archivé, move vers _archives/ (+ restore)
    │   ├── scaffold/SKILL.md       # /scaffold — générateur de composants conformes (skill/agent/pipeline)
    │   ├── upgrade-template/       # /upgrade-template — MAJ de la méthode par merge 3 voies (SKILL.md + scripts/upgrade.py)
    │   ├── adopt-template/SKILL.md # /adopt-template — greffe sur projet EXISTANT (bootstrap, retiré après usage)
    │   └── init-from-template/     # /init-from-template — bootstrap (SKILL.md + scripts/ render, cleanup-for-type), retiré après l'init
    │   # db-migration + agent-teams = PLUGINS maison (marketplace claude-setup) ; stack n8n = plugin OFFICIEL czlonkowski/n8n-skills → /plugin install, rien de copié
    │   # Pour grouper des skills : préfixe le nom, ou package en plugin (cf. plugins/ + .claude-plugin/marketplace.json)
    │
    ├── agents/                     # custom agents — à plat aussi (subagents ET rôles teammate)
    │   ├── README.md
    │   ├── doc-maintainer.md       # maintenance doc EN LOT (livraisons groupées, audit + actions, promotions) — subagent, jamais le HANDOFF
    │   ├── reviewer.md             # review lecture seule — revue adverse (/conception) + diffs d'équipe
    │   │                           # rôles d'exécution (worker/front-end/back-end/tester) + /team → plugin agent-teams
    │   └── explore-code.md / explore-docs.md / explore-memoire.md # explorateurs lecture seule réutilisables (/conception + investigations)
    │
    │   # ⚠️ Invocation skills/agents = via le `name:` du frontmatter (qui DOIT matcher le dossier/fichier).
    │   # Ex : `.claude/skills/handoff/SKILL.md` avec `name: handoff` → invoque `/handoff`.
    │
    ├── settings.json               # permissions (allow/ask/deny — secrets en deny à toute profondeur) + hooks
    ├── settings.local.json         # réglages perso, gitignoré — jamais touché par /upgrade-template
    ├── hooks/                      # scripts lancés par settings.json via `python3 …` / `bash …` (pas de chmod) — rôle : USAGE.md § hooks
    │   ├── sessionstart-inject-handoff.py  # startup|resume|clear|compact : marqueur de session, filets, ré-injection
    │   ├── sessionend-snapshot.py          # filet si session fermée SANS /handoff avec trace git
    │   ├── precompact-snapshot-handoff.py  # snapshot avant compaction
    │   ├── pretooluse-inject-codemap.py    # gotchas qui ciblent le fichier de code édité
    │   ├── posttooluse-growth-detection.py # API_KEY / deploy / RGPD → .growth-suggestions.md
    │   ├── stop-handoff-reminder.sh        # rappel /handoff (HANDOFF > 24h + arbre modifié) — 1×/session
    │   └── snapshot_common.py              # helpers partagés (snapshot, marqueurs de session)
    ├── .cache/                     # gitignoré : snapshots, marqueurs de session, conflits de mise à jour (upgrade-<v>/)
    ├── .growth-suggestions.md      # gitignoré : flags du hook PostToolUse, relus par /doc-health
    │
    ├── docs/                       # TOUTE la doc projet (vivante + stable + transversale)
    │   │
    │   ├── 📥 cadrage/             # capture client + évolutions/pivots (VIVANT — pas figé, s'enrichit au fil)
    │   │   ├── README.md           # synthèse vivante : verbatim demande + interlocuteurs + contraintes + risques + suite
    │   │   ├── tickets/            # tickets Jira/Linear/Asana reçus du client (1 fichier par ticket)
    │   │   ├── documents/          # docs reçus client (PDF, Excel, captures) — nommés YYYY-MM-DD-description.ext
    │   │   ├── reunions/           # comptes-rendus de réunions — nommés YYYY-MM-DD-titre.md (kickoff, validation, pivots)
    │   │   └── diagrams/           # schémas de synthèse business (flow client, processus, mindmaps)
    │   │       ├── README.md       # convention diagrammes (3 formats : ASCII / Excalidraw+SVG / PNG)
    │   │       └── flow-X.md       # diagramme ASCII inline OU paire .excalidraw + .svg
    │   │
    │   ├── 🎨 conception/          # design MACRO — le « PRD from scratch » (SEMI-STABLE — bumpé sur événement majeur)
    │   │   ├── README.md           # synthèse phase + pattern mirror macro/micro + statut + protocole pivot
    │   │   ├── research.md         # brainstorm macro projet : options explorées, alternatives, hypothèses + pivots datés
    │   │   ├── PRD.md              # spec produit (vision, scope, personas, métriques, user stories) — versionné v1.0, v2.0…
    │   │   ├── ARCHITECTURE.md     # plan technique macro (stack, modules, sécurité, flux, mapping champs)
    │   │   ├── tasks.md            # plan exécution MVP : sous-phases 1.1/1.2/1.3 + estimations + DoD figés (stable)
    │   │   └── diagrams/           # placeholder pour diagrammes techniques gros (> 50 lignes ASCII)
    │   │       └── README.md       # convention diagrammes (utiliser ici si trop gros pour ARCHITECTURE.md inline)
    │   │
    │   ├── 🧩 specs/               # design MICRO : 1 dossier par feature (frère de conception/ depuis v1.2 — la spec 001 = tranche verticale qui traverse tout)
    │   │   └── 001-feature/        # nommage : 001-, 002-, … (jamais de reset entre phases)
    │   │       ├── research.md     # brainstorm feature : options techniques explorées, libs envisagées, alternatives
    │   │       ├── spec.md         # PRD feature (QUOI/POURQUOI) : critères d'acceptation, user stories, scope + frontmatter status: (draft→validated→in-progress→done, miroir machine-readable de la ROADMAP)
    │   │       ├── plan.md         # plan technique feature (COMMENT) : architecture interne, patterns, libs + circuit breakers (conditions d'arrêt décidées à froid)
    │   │       ├── tasks.md        # checklist exécutable : tasks atomiques numérotées #1, #2… + DoD TYPÉE (command_passes:/file_exists:/manual:) + phases ~35 min max
    │   │       └── (diagrams/      # optionnel — créer si gros besoin de diagrammes spécifiques à cette feature)
    │   │
    │   ├── 🔄 HANDOFF.md           # ⭐ état de session — RÉÉCRIT par /handoff à chaque fin de session, ≤ 40 lignes (@-importé) : status, échecs, next, blockers
    │   ├── 🔄 HANDOFF-journal.md   # journal append-only (1 ligne/session via /handoff) — NON auto-chargé (v1.4)
    │   ├── 🔄 ROADMAP.md           # DASHBOARD vivant : status courant des features (synthèse de conception/tasks.md + specs/*/tasks.md)
    │   ├── 🔄 CHANGELOG.md         # historique features livrées + bugs fixés (format Keep a Changelog, versions = tags git)
    │   ├── 🔄 ACCESS.md            # checklist accès (API keys, comptes, VPN) : ✅ obtenu / ⏳ en attente / 🔒 OÙ trouver — jamais la valeur
    │   ├── 🔄 lecons.md            # journal bugs/patterns/observations — sas entre auto-memory et promotion (ADR/rule/discard)
    │   ├── 🔄 code-map.md          # ⭐ vue macro + règles de couplage + intention (non-déductibles, < 3k tokens, @-importé) — PAS de file-by-file
    │   ├── 🔄 code-map-gotchas.md  # pièges non évidents, entrées citant leur chemin — NON auto-chargé, injectés par le hook à l'édition du fichier ciblé
    │   ├── 🔄 stack.md             # inventaire technique (libs Python + services tiers + LLM + deploy + auth)
    │   │
    │   ├── 📚 adr/                 # Architecture Decision Records (transversal — décisions tech structurantes, IMMUABLES)
    │   │   ├── README.md           # index des ADR par scope (cadrage/mvp/feature/infra/operations) + section archived/superseded
    │   │   └── 00XX-<scope>-<titre-kebab>.md  # ex: 0007-mvp-stack-bdd.md — séquentiel sans reset, jamais modifier
    │   ├── 📚 idees/               # MES idées perso brutes non mûres (transversal — input interne, vs cadrage = externe)
    │   │   └── 2026-MM-DD-*.md     # 1 idée = 1 fichier daté (peut devenir une spec plus tard)
    │   │
    │   ├── GLOSSARY.md             # jargon métier du client/projet (créer si > 3 termes spécifiques)
    │   ├── RUNBOOK.md              # procédures ops (déploy, rollback, fix incident) — À CRÉER post-prod uniquement
    │   └── STAKEHOLDERS.md         # OPTIONNEL — qui fait quoi (sinon dans cadrage/README.md, sauf > 4-5 personnes)
    │
    └── (pas de src/ dans .claude/ — code source au top-level si projet code, créé naturellement)
```

> 📌 **Note `src/`** : le dossier code source vit **au top-level du projet** (racine, à côté de `workflows/`), pas dans `.claude/`. Il est créé naturellement quand tu commences à coder — pas besoin de le pré-créer dans le template.

## Convention diagrammes

| Format                         | Quand                                          | Lisible par Claude ?        |
| ------------------------------ | ---------------------------------------------- | --------------------------- |
| **ASCII inline** dans le `.md` | Par défaut — flow, arbre, séquence simple      | ✅ parfait                  |
| **Excalidraw + export SVG**    | Schéma visuel complexe (> ~50 lignes d'ASCII)  | ⚠️ SVG via Read explicite   |
| **PNG / JPG**                  | Screenshots, photos uniquement                 | ⚠️ pas fiable               |

**Règle d'or** : commit la **source éditable ET l'export** côte à côte (`flow-X.excalidraw` + `flow-X.svg`).

⚠️ Un `![](path)` dans un `.md` n'est **pas** suivi par Claude : pour qu'il « voie » un schéma image, Read explicite ou version ASCII.

**Où placer les diagrammes ?**

- Simple → **inline** dans le .md pertinent (business → `cadrage/README.md` ; technique → `ARCHITECTURE.md` ; feature → `plan.md`)
- Gros / éditable → dossier `diagrams/` local à la section (cadrage/diagrams/, conception/diagrams/, specs/00X/diagrams/ — rare)

## Pourquoi tout dans `.claude/` ?

- **Un seul dossier de matière première** — Claude y lit à la demande (jamais tout en `@` : seuls HANDOFF + code-map sont auto-chargés)
- **Racine propre** : seuls les vrais livrables sont visibles
- **Convention claire** : `.claude/` = matière première (pour toi + Claude), root = artefacts
- **Gitignore facile** : tu peux choisir ce qui se commit dans `.claude/` finement

## Les 4 buckets dans docs/

| Bucket                                                  | Contenu                              | Comportement                          |
| ------------------------------------------------------- | ------------------------------------ | ------------------------------------- |
| 📥 `cadrage/`                                           | Capture client (intake) + pivots     | **Vivant bordel** — append au fil     |
| 🎨 `conception/`                                        | Design output (research, PRD, archi) | **Semi-stable** — bumpé sur événement |
| 🔄 Racine `docs/` (HANDOFF, ROADMAP, CHANGELOG, ACCESS) | Fichiers vivants tracking            | **MAJ tous les jours**                |
| 📚 Transversaux (adr/, idees/)                          | Spans tous les phases                | À l'occasion                          |

**Pattern mirror macro ↔ micro (macro dans `conception/`, micro dans `specs/` — dossiers frères) :**

| Macro (`conception/`) | Micro (`specs/00X-feature/`) | Question                                |
| --------------------- | --------------------------------------- | --------------------------------------- |
| `research.md`         | `research.md`                           | Quelles options on a explorées ?        |
| `PRD.md`              | `spec.md`                               | Qu'est-ce qu'on construit et pourquoi ? |
| `ARCHITECTURE.md`     | `plan.md`                               | Comment on l'implémente ?               |
| `tasks.md` (plan MVP) | `tasks.md`                              | Quoi exécuter et dans quel ordre ?      |

→ `docs/ROADMAP.md` (racine de `docs/`) = **dashboard vivant** qui synthétise l'état (status + blockers).

---

## À créer quand ?

**Règle d'or :** un fichier qu'on ne met pas à jour ment. Crée à la demande, JAMAIS préventivement.

| Déclencheur                                                | Fichier (sous `.claude/docs/`)                                                                                 |
| ---------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| 1er credential / accès à obtenir                           | `ACCESS.md` — OÙ trouver l'accès, jamais la valeur                                                             |
| Déploiement prod imminent                                  | `RUNBOOK.md` (modèle ci-dessous)                                                                               |
| Terme métier récurrent non expliqué (> 3 fois)             | `GLOSSARY.md`                                                                                                  |
| ≥ 5 interlocuteurs / plusieurs équipes client              | `STAKEHOLDERS.md` (modèle ci-dessous) — sinon § Interlocuteurs de `cadrage/README.md`                          |
| Démarrage d'une feature                                    | `specs/00X-<slug>/{research,spec,plan,tasks}.md` via `/spec`                                                   |
| Décision qui survit à la feature OU touche plusieurs specs | ADR via `/adr` (§ ADR ci-dessous)                                                                              |
| Décision locale à UNE feature                              | `specs/00X/plan.md` § Décisions (pas d'ADR)                                                                    |
| Idée perso pas mûre                                        | `idees/YYYY-MM-DD-<titre>.md` via `/idee`                                                                      |
| Bug, piège, observation à décider plus tard                | entrée datée dans `lecons.md` via `/lecon` (statut 🆕 new)                                                     |
| Piège lié à un fichier / une zone du code                  | bullet dans `code-map-gotchas.md` (chemin cité en backticks)                                                   |
| Nouvelle règle de couplage / contrainte d'archi            | `code-map.md` (jamais de description fichier par fichier : déductible et ça dérive)                            |
| Nouvelle lib, service tiers, LLM                           | table de `stack.md`                                                                                            |
| Doc / ticket / compte-rendu reçus du client                | `cadrage/documents/` · `cadrage/tickets/` · `cadrage/reunions/` (verbatim, daté — cf. § Conventions de naming) |
| Diagramme                                                  | ASCII inline par défaut — cf. § Convention diagrammes                                                          |

Vue actionnable jour-1 / plus-tard → checklist « Démarrer un nouveau projet » en fin de ce doc.

**❌ À NE PAS créer** : bug log séparé (→ CHANGELOG), backups HANDOFF / archives (git suffit), « notes générales » (→ `idees/` daté).

---

## Les 2 niveaux à distinguer

| Niveau                  | Quoi                                 | Où                                            |
| ----------------------- | ------------------------------------ | --------------------------------------------- |
| **Macro (app entière)** | Vision, archi, plan d'exécution MVP  | `.claude/docs/conception/` (+ ROADMAP racine) |
| **Micro (une feature)** | Recherche, spec, plan, tasks feature | `.claude/docs/specs/00X-feature/`  |

---

## Distinction critique : `cadrage/` vs `idees/`

`cadrage/` = ce qu'**on te file** (client, Jira, mail — input externe). `idees/` = ce que **toi** brainstormes (input interne). Ne JAMAIS mélanger : tickets/docs reçus ≠ tes notes perso.

Test simple : « j'ai eu une idée » → `idees/` ; « voici la doc / le ticket / le compte-rendu » → `cadrage/` (verbatim, daté).

---

## Conventions de naming

| Quoi                   | Format                                                                |
| ---------------------- | --------------------------------------------------------------------- |
| Specs                  | `specs/001-<slug>/`, `002-…` — séquentiel, jamais de reset            |
| ADR                    | `adr/00XX-<scope>-<titre-court>.md` (ex. `0007-mvp-stack-bdd.md`)     |
| Réunions / pivots      | `cadrage/reunions/YYYY-MM-DD-<titre>.md`                              |
| Docs reçus du client   | `cadrage/documents/YYYY-MM-DD-<description>.<ext>`                    |
| Tickets client         | `cadrage/tickets/<ID>-<titre>.md` (ex. `JIRA-1234-export-clients.md`) |
| Idées perso            | `idees/YYYY-MM-DD-<titre-court>.md`                                   |
| Leçons                 | entrée `## YYYY-MM-DD — <titre>` dans `lecons.md`                     |
| Tags git (déploiement) | `vYYYY.MM.DD-HHMM`                                                    |

Dates ISO `YYYY-MM-DD` partout, liens relatifs. Numéros specs/ADR = max + 1, jamais réutilisés (en agent team : alloués par le lead seul).

---

## Mapping des étapes vers les fichiers

| Étape                          | Quoi                                  | Où                                                                                                                |
| ------------------------------ | ------------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 0. Demande client/ticket       | Input externe brut                    | `.claude/docs/cadrage/tickets/`, `cadrage/documents/`                                                             |
| 1. Synthèse cadrage            | Verbatim demande + interlocuteurs     | `.claude/docs/cadrage/README.md`                                                                                  |
| 2. Idée perso brute            | Mes notes/idées non mûres             | `.claude/docs/idees/2026-MM-DD-truc.md`                                                                           |
| 3. Brainstorm macro projet     | Exploration options, alternatives     | `.claude/docs/conception/research.md`                                                                             |
| 4. **PRD macro**               | Quoi/pourquoi projet, personas, scope | `.claude/docs/conception/PRD.md`                                                                                  |
| 5. **Plan technique macro**    | Stack, archi, modules, infra          | `.claude/docs/conception/ARCHITECTURE.md`                                                                         |
| 6. **Plan exécution MVP**      | Sous-phases + estimations + DoD figés | `.claude/docs/conception/tasks.md`                                                                                |
| 7. **Roadmap (dashboard)**     | Status + blockers + vue d'avion       | `.claude/docs/ROADMAP.md` (vivant, racine, synthétise tasks.md)                                                   |
| 8. Accès à obtenir             | API keys, comptes, OAuth scopes       | `.claude/docs/ACCESS.md`                                                                                          |
| 9. Interlocuteurs              | Qui demande, qui valide               | Section dans `.claude/docs/cadrage/README.md` (sauf gros projet → `STAKEHOLDERS.md`)                              |
| 10. Principes immuables        | Conventions, règles métier            | `.specify/memory/constitution.md` (Spec Kit)                                                                      |
| 11. Brainstorm d'UNE feature   | Recherche, options                    | `.claude/docs/specs/00X/research.md`                                                                   |
| 12. PRD d'UNE feature          | Spec détaillée                        | `.claude/docs/specs/00X/spec.md`                                                                       |
| 13. Plan technique feature     | Comment implémenter                   | `.claude/docs/specs/00X/plan.md`                                                                       |
| 14. Checklist feature          | Tasks atomiques à cocher              | `.claude/docs/specs/00X/tasks.md`                                                                      |
| 15. Décisions structurantes    | Choix tech irréversibles              | `.claude/docs/adr/00XX-*.md`                                                                                      |
| 16. Réunion / décision verbale | Compte-rendu                          | `.claude/docs/cadrage/reunions/2026-MM-DD-titre.md`                                                               |
| 17. Pivot demandé              | Nouvelle direction (hiérarchie)       | Réunion dans cadrage/reunions/ + section dans `conception/research.md` + bump PRD + refonte `conception/tasks.md` |
| 18. Procédure ops              | Comment déployer, rollback, fix       | `.claude/docs/RUNBOOK.md` (post-prod uniquement)                                                                  |
| 19. Reprise de session         | Où j'en suis                          | `.claude/docs/HANDOFF.md` (vivant, racine)                                                                        |
| 20. Livré                      | Historique versionné                  | `.claude/docs/CHANGELOG.md` (vivant, racine)                                                                      |

---

## Workflow complet d'un nouveau projet client

```
─── 📥 PHASE CADRAGE (vivant) ───
0. Demande reçue    → .claude/docs/cadrage/tickets/JIRA-1234-xxx.md
   (ticket/mail)         + .claude/docs/cadrage/documents/ (docs joints)
                        ↓
1. Kickoff client   → .claude/docs/cadrage/reunions/2026-MM-DD-kickoff.md
                        ↓
2. Synthèse cadrage → .claude/docs/cadrage/README.md
                        (verbatim demande + interlocuteurs + contexte + contraintes)
                        ↓
3. Accès            → .claude/docs/ACCESS.md
                        (checklist : API keys, comptes, VPN…)
                        ↓
─── 🎨 PHASE CONCEPTION (semi-stable) ───
4. Brainstorm macro → .claude/docs/conception/research.md
                        (options explorées, alternatives, hypothèses)
                        ↓
5. PRD macro        → .claude/docs/conception/PRD.md
                        (Claude le propre depuis le cadrage + research)
                        ↓
6. Plan technique   → .claude/docs/conception/ARCHITECTURE.md
                        (stack, modules, intégrations)
                        ↓
─── 🔄 PHASE TRACKING (racine vivante) ───
7. Roadmap          → .claude/docs/ROADMAP.md
                        (Phase 1, Phase 2…)
                        ↓
8. Glossary         → .claude/docs/GLOSSARY.md (si jargon métier)
                        ↓
─── boucle par feature (specs/) ───
9. Pick feature     → .claude/docs/specs/001-xxx/research.md   (= mirror conception/research)
                   → .claude/docs/specs/001-xxx/spec.md       (= mirror conception/PRD)
                   → .claude/docs/specs/001-xxx/plan.md       (= mirror conception/ARCHITECTURE)
                   → .claude/docs/specs/001-xxx/tasks.md      (= mirror docs/ROADMAP)
                   → CODE
                   → CHANGELOG.md MAJ (racine)
                   → HANDOFF.md MAJ (racine, fin session)
                   → feature suivante
                        ↓
─── 🚀 PHASE POST-PROD ───
10. Mise en prod    → .claude/docs/RUNBOOK.md (procédures déploy/rollback)
                        ← À CRÉER À CE MOMENT PRÉCIS, pas avant

─── EN CAS DE PIVOT (hiérarchie demande changement) ───
∞. Pivot demandé    → .claude/docs/cadrage/reunions/YYYY-MM-DD-pivot.md
                   → MAJ .claude/docs/cadrage/README.md (nouvelle direction)
                   → Append section datée dans conception/research.md
                   → Bump PRD (v1.0 → v2.0)
                   → Refonte ROADMAP (nouvelle section v2)
                   → ADR si pivot technique
```

---

## cadrage/README.md — Contexte initial

Le BRIEF capture la demande **brute**, avant que tu la transformes en PRD propre. Différent du PRD : c'est le verbatim de ce qu'on t'a demandé, pas ta version structurée.

```markdown
# Brief — Automatisation sync ERP→Notion

**Date :** 2026-05-20
**Demandeur :** Marie (CEO, ACME Corp)
**Canal :** Réunion kickoff 20/05 (voir reunions/2026-05-20-kickoff.md)
**Tickets liés :** [JIRA-1234](tickets/JIRA-1234-export-clients.md)

## Interlocuteurs

| Nom    | Rôle        | Contact        | Pour quoi                  |
| ------ | ----------- | -------------- | -------------------------- |
| Marie  | CEO ACME    | marie@acme.fr  | Validation business, scope |
| Paul   | IT ACME     | paul@acme.fr   | Accès techniques, ERP, n8n |
| Sophie | Commerciale | sophie@acme.fr | UAT, retours utilisateur   |

**Décisionnaire final :** Marie
**Cadence :** point hebdo vendredis 10h, Slack `#projet-sync-erp`

## Demande exprimée (verbatim)

"On a besoin que les nouvelles commandes de notre ERP remontent
automatiquement dans Notion pour que l'équipe commerciale les voit
sans se connecter à l'ERP."

## Contexte

- ERP : SAP Business One (API REST disponible, doc fournie en documents/)
- Notion : workspace existant, DB "Commandes" déjà créée
- Volume : ~50 commandes/jour
- Fréquence souhaitée : temps réel idéal, sinon < 15 min

## Contraintes

- Budget : forfait défini, pas de coût récurrent SaaS au-delà
- Sécurité : credentials ERP en lecture seule uniquement
- Délai : MVP pour 2026-06-15

## Ce qui N'EST PAS demandé

- Sync bidirectionnel (lecture seule)
- Notifications Slack (peut-être plus tard)

## Suite

→ PRD.md une fois validé avec Marie
```

---

## ACCESS.md — Checklist accès

Critique pour automatisations : sans ça tu bloques 3 jours à chasser des credentials.

```markdown
# Accès requis — Sync ERP→Notion

## ✅ Obtenus

- [x] ERP SAP B1 : compte API readonly (reçu 2026-05-21)
- [x] Notion : integration token (Marie l'a créé, reçu 2026-05-22)

## ⏳ En attente

- [ ] n8n cloud : compte admin sur leur tenant (demandé 2026-05-23 à Paul IT)
- [ ] VPN : accès au réseau interne pour atteindre l'ERP (ticket IT #4523)

## 🔒 Stockage des credentials

- Credentials : 1Password vault "ACME"
- .env local : copier depuis .env.example, demander valeurs à Marie
- n8n credentials : stockés dans n8n directement (chiffrés)
- ❌ JAMAIS de credentials dans le repo

## Contacts accès

- Marie (CEO) : tout ce qui est Notion + validation business
- Paul (IT) : tout ce qui est ERP + VPN + n8n infra
```

---

## STAKEHOLDERS.md — Qui fait quoi (OPTIONNEL)

> ⚠️ **Par défaut, mets les interlocuteurs DIRECTEMENT dans `cadrage/README.md`** (section Interlocuteurs).
> Créer un fichier `STAKEHOLDERS.md` séparé seulement si :
>
> - Plus de 4-5 personnes impliquées
> - Plusieurs équipes côté client (dev, métier, sécu, légal)
> - Projet long (> 6 mois) avec roulement d'équipe
> - Tu jongles tellement entre clients que tu mélanges les noms

Si tu décides d'en créer un :

```markdown
# Stakeholders — ACME Corp

## Équipe ACME

| Nom          | Rôle        | Contact        | Pour quoi                         |
| ------------ | ----------- | -------------- | --------------------------------- |
| Marie Dupont | CEO         | marie@acme.fr  | Validation business, accès Notion |
| Paul Martin  | IT          | paul@acme.fr   | Accès techniques, ERP, VPN, n8n   |
| Sophie L.    | Commerciale | sophie@acme.fr | UAT, retours utilisateur          |

## Décisionnaire final

Marie (toute décision archi ou changement scope passe par elle)

## Validations requises

- PRD : Marie
- Choix techniques : Paul + Julien
- Mise en prod : Marie + Paul

## Cadence

- Point hebdo : tous les vendredis 10h (visio)
- Slack channel : #projet-sync-erp
```

---

## RUNBOOK.md — Procédures ops (À CRÉER POST-PROD)

> ⚠️ **À créer le jour du 1er déploiement prod, pas avant.**
> Tant que le projet est en dev/MVP, ce fichier est inutile et va pourrir.
> Indispensable dès qu'un truc tourne en continu. Le but : que toi (ou un collègue) puisse intervenir à 22h sans avoir à tout réapprendre.

```markdown
# Runbook — Sync ERP→Notion

## Déploiement

- Workflow n8n : "Sync ERP Commandes" dans tenant ACME
- Trigger : Schedule toutes les 10min
- Déployé via : import API n8n (cf. `workflows/README.md`) ou un skill projet `/deploy`
- Versionning : workflow JSON exporté dans `workflows/sync-erp.json`

## Monitoring

- Dashboard n8n : tenant ACME > workflow > Executions
- Alertes : email à julien@x.fr si > 3 erreurs consécutives
- Logs : conservés 30 jours dans n8n

## Si ça casse

### Symptôme : pas de nouvelles commandes dans Notion depuis X heures

1. Check n8n executions : tenant ACME > workflow > Executions
2. Si erreur 401 ERP → refresh token (procédure ci-dessous)
3. Si erreur 429 → rate limit, augmenter interval dans Schedule node
4. Si erreur 5xx Notion → check status.notion.com, retry auto fait 3x

### Refresh token ERP

1. SSH bastion ACME : `ssh acme-bastion`
2. `cd /opt/sap && ./refresh-token.sh`
3. Copier le nouveau token affiché
4. Mettre à jour credential n8n "SAP B1 Token"

### Rollback workflow

- Restore : import du JSON depuis `workflows/sync-erp.json` dans n8n
- Remap les credentials (n8n ne re-link pas automatiquement)
```

---

## GLOSSARY.md — Jargon métier

Utile dès que le client a un vocabulaire spécifique. Évite de re-demander 5 fois "c'est quoi un BL ?".

```markdown
# Glossaire — Projet ACME

| Terme   | Définition                                                            |
| ------- | --------------------------------------------------------------------- |
| **BL**  | Bon de Livraison — doc émis à l'expédition d'une commande             |
| **OF**  | Ordre de Fabrication — déclenche la production d'un article           |
| **SKU** | Stock Keeping Unit — identifiant unique d'un article                  |
| **EDI** | Échange de Données Informatisé — protocole B2B (clients gros comptes) |
| **WMS** | Warehouse Management System — leur logiciel d'entrepôt (Manhattan)    |

## Spécificités ACME

- Une "commande" = peut être facturée en plusieurs fois (acomptes)
- Le terme "client" recouvre 2 réalités : prospect (CRM) vs client actif (ERP)
```

---

## ROADMAP.md vivant — exemple

```markdown
# Roadmap

## ✅ v1.0 — Livrée 2026-04-15

- [x] [001-auth](specs/001-auth/spec.md) — JWT + refresh
- [x] [002-users-crud](specs/002-users-crud/spec.md)
- [x] [003-dashboard](specs/003-dashboard/spec.md)

## 🚧 v1.1 — En cours (cible 2026-06-15)

- [~] [004-export-pdf](specs/004-export-pdf/spec.md) — **EN COURS**
- [ ] [005-notifications-email](specs/005-notifications-email/spec.md)

## 📋 v1.2 — Planifiée

- [ ] 006-mode-sombre — pas de spec encore
- [ ] 007-recherche-globale

## 💡 Backlog (pas encore prio)

- mode-offline (voir [idees/2026-05-22-mode-offline.md](idees/2026-05-22-mode-offline.md))
- intégration Slack
```

**Conventions de statut** (machine à états `[ ]` → `[~]` → `[x]`) :

- `[ ]` = planifié, pas commencé
- `[~]` = en cours (mettre en **gras** : `**EN COURS**`)
- `[x]` = livré (`[x] livré YYYY-MM-DD`)
- Miroir machine-readable : frontmatter `status:` de chaque `specs/00X/spec.md` — `draft`/`validated` ↔ `[ ]` · `in-progress` ↔ `[~]` · `done` ↔ `[x]` · `parked` ; posé par `/spec`, `/conception` (validated) et `/feature-done` (done) ; incohérence ROADMAP ↔ frontmatter flaggée par `/doc-health`
- Lien vers `.claude/docs/specs/00X/spec.md` dès que la spec existe
- Lien vers `.claude/docs/idees/...` tant que c'est juste une idée

---

## ADR — Architecture Decision Record

Fichier court (≤ 1 page) qui capture **une décision technique structurante** + contexte + conséquences, créé via `/adr <scope> "<titre>"`.

**ADR ou section `## Décisions` de `plan.md` ?**

| Niveau de décision                          | Où l'écrire                                  |
| ------------------------------------------- | -------------------------------------------- |
| Cross-feature (impacte > 1 spec)            | ADR global `.claude/docs/adr/`               |
| Survit à la mort de la feature              | ADR global `.claude/docs/adr/`               |
| Locale à UNE feature (lib, pattern interne) | Section `## Décisions` de `specs/00X/plan.md` |
| Devient cross-feature plus tard             | **Promouvoir** depuis `plan.md` → ADR global |

- **Naming** : `00XX-<scope>-<titre-court>.md` — scope dans le nom, séquentiel sans reset.
- **5 scopes** : `cadrage` (contraintes imposées au départ, souvent par le client) · `mvp` (structurant, projet entier) · `feature-00X` (réutilisable, propre à une feature — rare) · `infra` (hébergement, déploiement, secrets, monitoring) · `operations` (post-prod, incidents, runbook).
- **Frontmatter YAML obligatoire** (lu par `/adr list` et `/doc-health`) : `status` (`proposed` · `accepted` · `deprecated` · `superseded`), `scope`, `phase`, `supersedes` — cf. exemple ci-dessous.
- **Immuable** : on ne l'édite jamais. Changement d'avis → nouvel ADR `supersedes: 00XX`, l'ancien passe `status: superseded` (+ `superseded_by:`) via `/adr supersede` ; décision qu'on cesse d'étendre, sans remplaçant → `deprecated` (`/adr deprecate`).
- Critères OUI / NON détaillés : `.claude/docs/adr/README.md` (index du projet).

### Template d'un ADR (`adr/0002-mvp-auth-jwt.md`)

```markdown
---
status: accepted # proposed | accepted | deprecated | superseded
scope: mvp # cadrage | mvp | feature-00X | infra | operations
phase: 2026-Q2
supersedes: null # ou 0001
---

# 0002 — Authentification : JWT plutôt que sessions

**Statut :** Accepted
**Date :** 2026-05-15
**Décideur :** Julien

## Contexte

On a besoin d'authentifier les users sur l'API. L'app sera consommée
par un front Next.js + une app mobile.

## Options considérées

- **Sessions cookie** : simple, sécurisé par défaut, mais lié au navigateur
- **JWT** : stateless, marche sur mobile, mais revocation à gérer
- **Auth provider (Clerk, Auth0)** : rapide mais coûteux + vendor lock-in

## Décision

On part sur **JWT avec refresh tokens** stockés en httpOnly cookie côté
web et SecureStore côté mobile. Lib : `python-jose`.

## Conséquences

- Marche pour web ET mobile sans changer le backend
- Stateless = scaling horizontal facile
- Faut gérer une blacklist Redis pour la revocation
- Refresh token rotation à implémenter

## Liens

- specs/001-auth/spec.md
- https://docs.python-jose.dev/
```

### Index `adr/README.md`

```markdown
# Architecture Decision Records

| #    | Titre                        | Statut             |
| ---- | ---------------------------- | ------------------ |
| 0001 | Stack FastAPI + Postgres     | Accepted           |
| 0002 | Auth JWT plutôt que sessions | Superseded by 0007 |
| 0003 | Celery pour jobs async       | Accepted           |
| 0004 | Secrets via Doppler          | Accepted           |
| 0007 | Migration JWT → Clerk        | Accepted           |
```

---

## HANDOFF.md — Reprise de session

Le fichier qui sauve les sessions multi-jours. **Réécrit** (jamais empilé) par `/handoff` **à chaque fin de session**, ≤ 40 lignes — l'historique part dans `HANDOFF-journal.md` (append-only, non auto-chargé).

```markdown
# HANDOFF — 2026-05-24 18h

**Branche** : feature/004-export-pdf
**Goal** : export PDF des rapports utilisateur
**Status** : tasks.md 4/7 done, template HTML validé, manque la génération
**Build/test** : ✅ npm test, ⏳ génération PDF KO sur tables imbriquées
**Décisions récentes** : choix puppeteer vs weasyprint → puppeteer (voir adr/0008)
**Échecs tentés** : split en 2 PDFs (UX moche), abandonné
**Next** : task #5 (génération PDF tables imbriquées), puis task #6 (cache)
**Blocked on** : aucun (ou : "attente accès staging Paul IT")

## Continuation State (machine-readable — 5 clés fixes, toujours présentes)

Spec: 004-export-pdf
Task: T2.5
Fichiers en cours: src/pdf/renderer.py
Bloqué sur: rien
Commande de reprise: pytest tests/pdf/ -q
```

À placer dans le CLAUDE.md :

```markdown
- Reprise de session : @.claude/docs/HANDOFF.md
```

→ Claude le charge automatiquement au démarrage.

---

## Compte-rendu de réunion — Template

À placer dans `.claude/docs/cadrage/reunions/2026-MM-DD-titre.md` :

```markdown
# Kickoff — Sync ERP→Notion

**Date :** 2026-05-20 14h-15h
**Présents :** Marie (ACME), Paul (ACME IT), Julien (moi)
**Format :** Visio Meet

## Sujets abordés

- Besoin métier : voir cadrage/README.md
- Stack technique : n8n on-prem retenu (vs n8n cloud), voir adr/0001
- Timeline : MVP pour 2026-06-15

## Décisions prises

- ✅ Lecture seule uniquement (pas de sync inverse pour v1)
- ✅ Cadence sync : 10min (compromis temps-réel/charge ERP)
- ✅ Julien gère credentials via 1Password partagé

## Actions / Next steps

- [ ] Paul : créer compte n8n admin pour Julien (avant 2026-05-25)
- [ ] Marie : valider PRD une fois écrit
- [ ] Julien : envoyer PRD pour validation avant 2026-05-28

## Points en suspens

- Notifications Slack ? À rediscuter en v2
```

---

## CLAUDE.md — Template minimal (split racine / `.claude`)

Deux fichiers, **tous deux chargés** à chaque session. **Racine = le projet** (résumé, 2 `@`, liens doc, conventions) · **`.claude/CLAUDE.md` = la méthode** — index mince (~2,5 Ko) : Claude Code liste déjà nativement chaque skill (nom + description) ; l'inventaire humain et CI-vérifié vit dans `.claude/skills/README.md`.

### `CLAUDE.md` (racine — le projet, ≤ 60 lignes)

```markdown
# Projet ACME — Sync ERP Notion

Automatisation n8n pour synchroniser les commandes SAP B1 → Notion DB.

> 🧭 Fonctionnement du template (skills, structure) → [.claude/CLAUDE.md](CLAUDE.md)

## Documentation

> 🪶 Just-in-time : **2 `@` maximum** (état vivant), tout le reste en liens simples lus à la demande.
> Mesuré v1.4 : tout charger en `@` → 144k tokens au 1er tour sur un projet d'un mois.

- Reprise session : @.claude/docs/HANDOFF.md ⭐ (≤ 40 lignes — journal dans HANDOFF-journal.md)
- Code map : @.claude/docs/code-map.md ⭐ (< 3k tokens — gotchas dans code-map-gotchas.md)
- Roadmap (dashboard) : [ROADMAP](.claude/docs/ROADMAP.md) · Cadrage : [cadrage/README](.claude/docs/cadrage/README.md)
- Conception : [PRD](.claude/docs/conception/PRD.md) · [ARCHITECTURE](.claude/docs/conception/ARCHITECTURE.md)
- Accès : [ACCESS](.claude/docs/ACCESS.md) · ADR : [adr/](.claude/docs/adr/) · [GLOSSARY](.claude/docs/GLOSSARY.md) · [RUNBOOK](.claude/docs/RUNBOOK.md)

## Conventions

> Les rules `.claude/rules/*.md` sont **déjà auto-chargées** (sauf celles scopées `paths:`, chargées
> à la demande) — **jamais** de `@` dessus (double chargement / scoping court-circuité).

- [code-style](.claude/rules/code-style.md) · [testing](.claude/rules/testing.md) · [git-workflow](.claude/rules/git-workflow.md)

## Reminders critiques

- Credentials JAMAIS dans le repo (stockage : `.claude/docs/ACCESS.md`)
- `.claude/docs/HANDOFF.md` à update à chaque fin de session (via /handoff)
```

### `.claude/CLAUDE.md` (la méthode — index mince)

```markdown
# Projet ACME — Méthode (template claude-Setup)

> Comment ce projet est outillé pour Claude Code. Le CLAUDE.md racine décrit le projet ; ce fichier reste court.

## Où est quoi

- Doc projet : la rule [template-maintenance](rules/template-maintenance.md) se charge seule dès qu'un fichier de `.claude/docs/` est lu (scopée `paths:` — jamais en `@`)
- Skills : inventaire + conventions → [skills/README.md](skills/README.md) · nouveau composant conforme → `/scaffold`
- Guides humains : [USAGE.md](USAGE.md) (workflows) · [STRUCTURE.md](STRUCTURE.md) (arborescence, conventions)

## 🔁 Pipelines récurrents (orchestrés par `/feature`)

- `/feature "<titre>" [standard|tdd|n8n]` · bug non trivial → `/debug`

## Agent perso (`.claude/agents/`)

- `explore-code` · `explore-docs` · `explore-memoire` · `reviewer` · `doc-maintainer` (doc en lot — jamais le HANDOFF)

## Plugins (marketplace `claude-setup`)

- n8n → `n8n-mcp-skills` (officiel, souvent déjà en user-scope) · BDD → `db-migration` · équipe (opt-in) → `agent-teams`

## Version du template

`.claude/template-version` · mise à jour de la méthode → `/upgrade-template`
```

---

## Cycle de vie d'une feature

```
1. INBOX           docs/idees/2026-05-20-export-pdf.md
   (idée brute)         ↓ "ok je veux le faire un jour"

2. ROADMAP         ajouté en backlog/phase X (sans spec encore)
   (planifié)          ↓ "je commence maintenant"

3. SPEC créée      specs/004-export-pdf/{research,spec,plan,tasks}.md
   (in progress)       + roadmap mise à jour pour LINKER la spec
                       ↓ "feature livrée"

4. DONE            roadmap : [x] coché
                       + CHANGELOG.md : entrée ajoutée
                       + spec/ reste comme archive
```

---

## Quand ajouter une feature après la "fin" de la roadmap

La roadmap n'est **jamais finie** — c'est un document vivant.

```markdown
## ✅ v1.0 — Livrée 2026-04-15

[...features livrées, read-only...]

## v1.1 — Demandes utilisateurs (en cours)

- [~] [006-export-csv](specs/006-export-csv/spec.md) — **EN COURS**
- [ ] [007-recherche-globale](specs/007-recherche-globale/spec.md)
```

Le numéro de spec **continue** (006, 007...) — jamais de reset.

Pour un gros pivot (v2, refonte), 2 options :

- **Option A** (recommandé solo) : tout dans le même ROADMAP avec section `## v2 — Refonte`
- **Option B** (gros projets) : archive `.claude/docs/archive/ROADMAP-v1.md` + nouvelle roadmap

---

## Adaptations par taille de projet

| Taille                      | Structure                                                              |
| --------------------------- | ---------------------------------------------------------------------- |
| **Script one-shot**         | Juste un `README.md`. Pas de specs/, pas d'ADR.                        |
| **Projet moyen**            | Structure complète ci-dessus                                           |
| **Multi-projets (atelier)** | Monorepo avec `python/`, `n8n/`, `db/` + HANDOFF.md global à la racine |

→ Profils d'init (`script-jetable`, `python-app`, `web-app`, `automation-n8n`, `bdd-migration`, `other`) et ce que chacun retire : [USAGE.md](USAGE.md) § Setup.

---

## Adaptations par type de projet

| Type                 | Spécificité                                                                                                                                           |
| -------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Python**           | `pyproject.toml`, `tests/`. Plan.md documente modules et dépendances                                                                                  |
| **Scripts**          | `spec.md` souvent inutile → juste `README.md` + commentaires en tête                                                                                  |
| **n8n**              | `.claude/docs/specs/00X/spec.md` = logique métier, `tasks.md` = checklist de nœuds. JSON exporté dans `workflows/`. RUNBOOK indispensable. |
| **BDD**              | ADRs **obligatoires** pour migrations de schéma. Dossier `db/migrations/` avec scripts numérotés                                                      |
| **Client/freelance** | Brief (`cadrage/README.md`), ACCESS, STAKEHOLDERS, RUNBOOK = **obligatoires**. Pour projet perso, optionnels.                                         |

---

## Outils recommandés

| Outil                     | URL                                      | Usage                                                                                                                                                                                                                                                                                                                                          |
| ------------------------- | ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **GitHub Spec Kit**       | github.com/github/spec-kit               | `uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@vX.Y.Z` (tag requis) puis `specify init <NAME>` → structure + commandes préfixées `/speckit.*` : constitution, specify, clarify, plan, tasks, analyze, implement, converge (+ taskstoissues, checklist). ⚠️ pas de `npx` (outil distribué via le repo, pas npm) |
| **handoff plugin**        | github.com/thepushkarp/handoff           | Auto-génère `HANDOFF.md` en fin de session                                                                                                                                                                                                                                                                                                     |
| **claude-code-templates** | github.com/davila7/claude-code-templates | Bibliothèque de skills PM/PRD prêts à coller                                                                                                                                                                                                                                                                                                   |

À éviter pour solo dev : BMAD-METHOD (multi-agents PM/Architect/Dev = overkill), claude-flow (orchestration trop complexe).

---

## Règles mentales

- **Crée à la demande, pas préventivement** — un fichier non maintenu ment
- **`.claude/docs/` = stratégie** (l'app entière), **`.claude/docs/specs/` = tactique** (une feature à la fois)
- **`cadrage/` = ce qu'on me file**, **`idees/` = ce que je brainstorme** — ne JAMAIS mélanger
- **Roadmap** = ta vue d'avion, **specs** = tes vues détaillées
- **Un ADR** si la décision impacte plusieurs features OU est dure à défaire
- **Rien ne se perd** : tout circule de `idees/` → `.claude/docs/specs/00X/research → spec → plan → tasks`
- **HANDOFF.md ⭐** mis à jour à chaque fin de session — c'est ce qui sauve la continuité (fichier le plus utile)
- **CLAUDE.md** est un INDEX, pas la doc elle-même (≤ 60 lignes, 2 `@` max) ; les rules sont auto-chargées — jamais en `@`
- **CHANGELOG.md** est UN SEUL fichier — features ET bug fixes (pas de fichier bugs séparé)
- **Interlocuteurs dans le BRIEF** — `STAKEHOLDERS.md` séparé seulement si > 4-5 personnes
- **ACCESS.md** dès le jour 1 — pas après avoir bloqué 2 jours sur un OAuth
- **RUNBOOK.md** dès la mise en prod — pas avant (sinon il pourrit), pas après (sinon c'est le premier incident à 22h)
- **Credentials JAMAIS dans le repo** — `.env.example` pour le template, valeurs ailleurs (1Password, Doppler, n8n credentials)

---

## Démarrer un nouveau projet — checklist

> 🟢 **Étapes obligatoires** / 🟡 **Quand un besoin émerge** / 🔴 **Plus tard**

### 🟢 Setup initial (jour 1)

1. [ ] Copier ce template (contenu de `template/` racine) dans ton nouveau projet
2. [ ] Remplir `.claude/docs/cadrage/README.md` (verbatim demande + interlocuteurs)
3. [ ] Dump des inputs reçus dans `.claude/docs/cadrage/{tickets,documents,reunions}/`
4. [ ] Compte-rendu kickoff dans `.claude/docs/cadrage/reunions/YYYY-MM-DD-kickoff.md`
5. [ ] `.claude/docs/ACCESS.md` (checklist accès — DÈS LE JOUR 1, pas après)

### 🟡 Quand le besoin émerge

6. [ ] `CLAUDE.md` (index, ≤ 60 lignes) — dès que tu commences à coder
7. [ ] `README.md` (setup local) — si projet code
8. [ ] `.env.example` — si variables d'env
9. [ ] `specify init <NAME>` (via `uv tool install specify-cli`) ou structure perso — quand tu démarres l'archi
10. [ ] `.claude/docs/conception/PRD.md` — quand brief mûr et validé
11. [ ] `.claude/docs/conception/ARCHITECTURE.md` — quand stack décidée
12. [ ] `.claude/docs/ROADMAP.md` — quand tu peux découper en > 2 features
13. [ ] `.claude/docs/adr/00XX-<scope>-<titre>.md` — à la 1ère vraie décision tech (via `/adr`)
14. [ ] `.claude/docs/specs/001-*/` — quand tu démarres la 1ère feature
15. [ ] `.claude/docs/HANDOFF.md` ⭐ — fin de la 1ère session de code (via `/handoff`)
16. [ ] `.claude/docs/CHANGELOG.md` — à la 1ère feature livrée (via `/feature-done`)
17. [ ] `.claude/docs/GLOSSARY.md` — si jargon métier (sinon skip)

### 🔴 Plus tard

18. [ ] `.claude/docs/RUNBOOK.md` — **jour du 1er déploiement prod**
19. [ ] `.claude/docs/STAKEHOLDERS.md` — seulement si > 4-5 interlocuteurs
