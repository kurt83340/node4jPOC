# USAGE — Comment utiliser ce template

> Guide pratique : skills + agent + hooks + workflows au quotidien.

---

## 🚀 Setup d'un nouveau projet (à lire EN PREMIER)

### Procédure complète (6 étapes, ~5 min)

```bash
# 1. Copier le template (exclut l'exemple ACME, test, la CI, et la source plugins/marketplace)
rsync -av --exclude='EXAMPLES/' --exclude='test/' --exclude='.github/' --exclude='.git/' \
  --exclude='plugins/' --exclude='.claude-plugin/' \
  /chemin/vers/template/ /chemin/vers/mon-nouveau-projet/

# 2. Aller dedans
cd /chemin/vers/mon-nouveau-projet/

# 3. Git init pour rollback possible
git init && git add . && git commit -m "chore: snapshot pre-init"

# 4. (Recommandé, une fois par machine) pre-commit — l'init active le garde-fou secrets (gitleaks)
pipx install pre-commit            # ou : uv tool install pre-commit

# 5. Lancer Claude Code
claude
```

> ℹ️ **Plus de `chmod +x`** (v1.5) : `settings.json` lance les hooks via `python3 …` / `bash …`.

> 🔌 **Prérequis recommandé : MCP `context7` connecté en user-level** (installé une fois,
> dispo dans toutes les sessions). La rule [`doc-lookup`](rules/doc-lookup.md) du
> template s'appuie dessus (doc officielle versionnée) pour `/conception`, `/debug`, les
> explorateurs et les teammates ; fallback automatique WebFetch/WebSearch s'il est absent.

Dans la session Claude :

```
/init-from-template
```

Claude va :

1. **Vérifier les prérequis** (git initialisé, python3 dispo)
2. **Poser 10 questions** via AskUserQuestion (3 batches) :
   - Batch 1 : `PROJECT_NAME`, `PROJECT_FOLDER`, **type de projet**
   - Batch 2 : `CLIENT_NAME`, `NOM_DECIDEUR`, `EMAIL_DECIDEUR`, `TON_NOM`, `TON_EMAIL`
   - Batch 3 : `COMMANDE_INSTALL`, `COMMANDE_TESTS`, `COMMANDE_RUN`
3. **Substituer les CORE placeholders** auto (10 substitutions sur ~370 placeholders — le reste est CONTENT à remplir au fil de l'eau)
4. **Lancer `cleanup-for-type.py`** selon le type : adapte le template **et retire les artefacts de maintenance DU template** (`.github/` self-CI, `test/`, `EXAMPLES/`, skills bootstrap `init-from-template`/`adopt-template`) → le projet généré démarre **propre, sans CI héritée** ; écrit `.claude/template-lock.json` (version + profil + source — **aucune** de tes réponses : base de `/upgrade-template`)
5. **Plugin stack** si pertinent — type `automation-n8n` : **check-first** `claude plugin list` (plugin **officiel** `n8n-mcp-skills` souvent déjà en user-scope → confirmation en 1 ligne, rien à cloner) ; sinon proposer l'install user-scope (`claude plugin marketplace add czlonkowski/n8n-skills` + install `--scope user`). Type `bdd-migration` → `db-migration@claude-setup`
6. **Activer le garde-fou secrets** : `pre-commit install` si pre-commit est dispo (sinon te le signale en 1 ligne)
7. **Te proposer le commit initial** (après relecture de `git status --short` : aucun `.env*` ni secret) : `feat: init projet <nom> depuis template`

### Les 6 types de projet (impact sur cleanup)

| Type             | Impact   | Skills installés                                                 | Rules de code gardées | Use case                                         |
| ---------------- | -------- | ---------------------------------------------------------------- | --------------------- | ------------------------------------------------ |
| `script-jetable` | **-80%** | minimum vital (handoff, lecon, archive-projet, upgrade-template) | Python + web          | 1-shot Python, < 1 jour                          |
| `python-app`     | moyen    | cœur (post-init)                                                 | Python                | App Python (FastAPI, scripts...)                 |
| `web-app`        | moyen    | cœur (post-init)                                                 | web (TS/JS)           | Next.js, React, etc.                             |
| `automation-n8n` | léger    | cœur + plugin officiel `n8n-mcp-skills`                          | Python                | Workflow n8n + helpers Python                    |
| `bdd-migration`  | léger    | cœur + plugin `db-migration`                                     | Python                | Migration BDD avec Alembic                       |
| `other`          | aucun    | cœur (rien n'est retiré)                                         | Python + web          | Hors cases (Go, Rust, data…) — ajuster à la main |

> Les rules de code sont scopées `paths:` : une rule Python ne se charge que quand Claude lit un `.py` —
> celle de l'autre langage reste inerte ; le profil la retire quand la stack est claire.

### Vérification post-init

> ℹ️ L'init a déjà vérifié les CORE (`render.py --check`) **avant** le cleanup — le script est
> ensuite retiré avec le scaffolding du template. Re-check possible sans script :

```bash
# 1. Aucun placeholder CORE restant ? (rien trouvé = ✅). Périmètre SUBSTITUÉ uniquement :
#    les templates bundlés de /spec ({{SPEC_*}}) et STRUCTURE/USAGE gardent leurs {{...}} d'exemple — normal.
grep -rEn '\{\{[A-Z]{2,}_[A-Z][A-Z0-9_]+\}\}' CLAUDE.md README.md .env.example .claude/CLAUDE.md .claude/docs/ .claude/rules/ 2>/dev/null && echo "❌ CORE restants" || echo "✅ aucun CORE restant"

# 2. Premier commit du projet rempli (relire d'abord : aucun .env* ni secret dans la liste)
git status --short
git add -A
git commit -m "feat: init projet <nom> depuis template"
```

### Prochaines étapes après init

1. **Remplir `cadrage/README.md`** (verbatim demande client + interlocuteurs)
2. **Planifier le kickoff** → archiver compte-rendu dans `cadrage/reunions/`
3. **Quand brief mûr** → remplir `conception/PRD.md`
4. **Quand archi décidée** → `conception/ARCHITECTURE.md`
5. **Démarrer 1ère feature** : `/spec "<titre>"`

### Projet EXISTANT (brownfield) → `/adopt-template`

Ton projet a déjà du code et une histoire ? **Ne pas** utiliser `/init-from-template`. À la place :

```bash
cd /chemin/vers/projet-existant     # working tree PROPRE (commit/stash avant)
rsync -av --ignore-existing \
  --exclude='EXAMPLES/' --exclude='test/' --exclude='.github/' \
  --exclude='plugins/' --exclude='.claude-plugin/' \
  --exclude='.git/' --exclude='README.md' --exclude='.env.example' \
  /chemin/vers/template/ .
# (Recommandé) Dépose MAINTENANT tes matériaux — le skill les ingère :
#   docs client → .claude/docs/cadrage/documents/   tickets → cadrage/tickets/
#   transcriptions → cadrage/reunions/
claude   # puis : /adopt-template
```

`--ignore-existing` = **l'existant gagne toujours** (tes CLAUDE.md / settings.json /
.gitignore ne sont pas touchés). Le skill propose ensuite : merges des collisions **en diff**
(jamais d'overwrite — dont les lignes secrets `.env*` du `.gitignore` et les deny de
`settings.json`), questions CORE **pré-remplies** depuis tes manifests, et
**rétro-remplissage** de la doc depuis le projet (stack.md ← manifests, code-map ←
`/codemap`, cadrage ← README existant, HANDOFF ← git log, ADRs rétroactifs optionnels).

### Troubleshooting init

- **Hook en erreur `python3: command not found`** → Python 3 absent du PATH (les hooks sont lancés via `python3`)
- **`render.py: 0 fichiers à scanner`** → le rsync n'a rien copié (vérifie source)
- **`/init-from-template` pas trouvé** → relance `claude` (skills scannés au démarrage)
- **CORE manquants après render** → ajoute-les au vars.json et relance

## 🔄 Mettre à jour un projet existant (`/upgrade-template`)

Projet généré avec une version plus ancienne du template → `/upgrade-template [vX.Y.Z]` met à jour ses
**fichiers de méthode** (hooks, skills, agents, rules, `settings.json`, les deux `CLAUDE.md`, USAGE/STRUCTURE,
`.gitignore`, `.pre-commit-config.yaml`) par **merge 3 voies** :

- **base** = l'init de TA version rejouée depuis le tag git du template (même profil) · **cible** = l'init de la
  nouvelle version · **nous** = ton projet. Profil, mode et source lus dans `.claude/template-lock.json` (écrit à
  l'init, sans aucune variable d'init) ; absent (projet < 1.5) → profil et mode déduits, à confirmer.
- Fichier jamais touché → la cible s'applique · template inchangé → ta personnalisation reste · les deux ont
  bougé → `git merge-file` (fusion clé par clé pour `settings.json`, règles de permission et hooks compris ;
  projet adopté : les hooks et règles du template qui lui manquent sont ajoutés).
- **Jamais touché** : la doc projet `.claude/docs/` (seules des migrations versionnées y écrivent — ex. 1.4.0 :
  journal HANDOFF et gotchas sortis des fichiers auto-chargés), ton code, `README.md`, `.env.example`,
  `settings.local.json`. Équipe d'agents activée → flag et `teammateMode` conservés, rule d'équipe mise à jour depuis le plugin.
- Toujours un `--dry-run` montré et validé d'abord, sur un arbre git propre, en un seul commit (`git revert` pour annuler).
- **Conflit** (ex. modifié des deux côtés sans fusion propre) → ton fichier est **gardé tel quel** ; la version cible
  (`<fichier>.template`) et le merge annoté (`<fichier>.merge`) atterrissent dans `.claude/.cache/upgrade-<version>/`
  avec un `REPORT.md` — Claude propose une fusion, tu valides. Les conflits restent inscrits dans le lock
  (`pending_conflicts`) et sont re-signalés jusqu'à `--ack-conflicts`. Un chemin via lien symbolique
  (dossier partagé) n'est jamais modifié.

Projet **< 1.5** (le skill n'existe pas encore chez toi) : lancer le moteur du template le plus récent.

```bash
git clone --quiet https://github.com/kurt83340/claude-Setup /tmp/claude-setup && python3 /tmp/claude-setup/.claude/skills/upgrade-template/scripts/upgrade.py --project . --template /tmp/claude-setup --dry-run
# plan relu → appliquer (sans re-cloner) — code retour : 0 = OK · 1 = conflits à régler · 2 = erreur, rien écrit
python3 /tmp/claude-setup/.claude/skills/upgrade-template/scripts/upgrade.py --project . --template /tmp/claude-setup
```

Après coup : relancer Claude Code (hooks et settings lus au démarrage), `pre-commit install` si le garde-fou est
nouveau, supprimer `.claude/.cache/upgrade-<version>/` une fois les conflits réglés.

---

## 🧠 Comprendre AVANT d'utiliser : 3 mémoires, 3 usages

Au-dessus de tout, les **instructions stables** que tu écris (`CLAUDE.md` racine + `.claude/CLAUDE.md` + `.claude/rules/*`,
versionnées). Puis 3 mémoires à ne pas confondre : **`.claude/docs/`** (état, décisions, specs, leçons — partagé,
versionné, `HANDOFF.md` en tête), **auto-memory** (patterns techniques — cache machine-local, écrit par Claude) et
**`/resume`** (transcript : reprise exacte d'UNE session).

→ Table canonique (contenu / qui écrit / versionné) : [rules/template-maintenance.md § 3 mémoires, 3 usages](rules/template-maintenance.md) — la rule que Claude charge dès qu'il lit `.claude/docs/`.

**`/resume` vs HANDOFF.md** : `/resume` (built-in) garde 100 % du contexte de la session précédente (reprise même journée) ; `HANDOFF.md` sert quand tu changes de machine, clones ailleurs, partages, ou démarres à froid après plusieurs jours. **Complémentaires.**

## 📅 Workflow quotidien

### Démarrer une session

1. Lance Claude Code : `claude` (ou `claude --resume` si reprise même journée)
2. Claude charge automatiquement (≈ 6,5k tokens sur un template vierge) :
   - `CLAUDE.md` (racine — index projet) **+** `.claude/CLAUDE.md` (index méthode) — chargés nativement, sans `@`
   - via les **2 seuls `@`** du CLAUDE.md racine : `.claude/docs/HANDOFF.md` (où tu en étais) + `.claude/docs/code-map.md` (couplage + intention)
   - les rules `.claude/rules/*.md` non scopées (les scopées `paths:` attendent qu'un fichier concerné soit lu)
   - hook SessionStart : filet fin-de-session (si la dernière session s'est fermée sans `/handoff` après avoir touché au dépôt) + alerte si le contexte auto-chargé dépasse 25k tokens
   - ROADMAP, PRD, ADR… = **liens lus à la demande**, pas auto-chargés
3. **Workflow manuel recommandé** (5 étapes) :
   ```
   1. HANDOFF.md (déjà en contexte) → reprendre où on en est
   2. Lire ROADMAP.md       → vue d'avion du projet
   3. Lire la spec en cours (lien dans HANDOFF)
   4. git status + git log -5 → ce qui s'est passé
   5. Ask user : "on continue sur X ? ou autre chose ?"
   ```

### Pendant que tu codes

**Automatique (hooks)** :

- 📖 **PreToolUse** : à l'édition d'un fichier de code → Claude reçoit les **gotchas de `code-map-gotchas.md` qui ciblent ce fichier** (1×/fichier/session, juste après l'édition) — **tu ne fais RIEN** (détail : § Comprendre les hooks automatiques)
- 🔍 **PostToolUse** : si tu écris du code mentionnant `API_KEY`, `deploy`, `RGPD`, `OAuth`, etc. → flag automatique dans `.claude/.growth-suggestions.md`
- 💾 **Auto-memory** (natif, actif par défaut) : Claude apprend tes patterns (machine-local, dans `~/.claude/projects/.../memory/`)

**Manuel (si besoin)** :

- `/lecon <scope> "<titre>"` → capture rapide d'une observation/bug
- `/adr <scope> "<titre>"` → capture une décision tech structurante
- `/codemap` → après gros refacto, régénère la code-map

### Fin de session

⚠️ **CRITIQUE** : toujours faire ça avant de fermer Claude.

```
/handoff
```

Claude va :

1. Lire git status + log + diff + tests
2. Lire HANDOFF.md actuel
3. Te proposer un nouveau HANDOFF **réécrit** (≤ 40 lignes, jamais empilé : status / échecs / blockers / next steps
   + **Continuation State** : 5 clés `Clé: valeur` machine-readable — le point de reprise parseable)
4. Te demander confirmation avant d'écrire, puis ajouter 1 ligne à `HANDOFF-journal.md` (non auto-chargé)

Toujours **dans la session qui a travaillé** : elle seule a la conversation (échecs tentés, blockers) — jamais
délégué à un subagent comme `doc-maintainer`.

**Si tu oublies** : le hook `Stop` te le rappelle (1×/session) si HANDOFF > 24h avec changements git pending ;
si tu fermes quand même sans `/handoff` après avoir touché au dépôt, le filet `SessionEnd` capture l'état et
le réinjecte au démarrage suivant.

### Si Claude compacte le contexte (auto ~90% ou via `/compact`)

Tu ne fais RIEN. Les hooks gèrent :

1. `PreCompact` → snapshot (git state + derniers messages humains) écrit dans `.claude/.cache/` (non-versionné) + marker dans `/tmp/`
2. Claude compacte
3. `SessionStart` (source `compact`) → re-inject le snapshot et ré-arme l'injection des gotchas
4. Tu continues comme si rien ne s'était passé

## ✅ Livraison d'une feature

Quand tous les tasks de `specs/00X-feature/tasks.md` sont cochés :

```
/feature-done 001-erp-connector
```

Claude va :

1. Vérifier que tous les tasks sont `[x]` + DoD rempli (sinon demande confirmation)
2. Scanner `plan.md` pour détecter les **décisions tech à promouvoir en ADR** (mots-clés : choisi, retenu, vs, plutôt que)
   - Règle : cross-feature OU survit à la feature → ADR global ; sinon laisser dans `plan.md`
3. **Si ADR créé** : créer fichier + update `docs/adr/README.md` (index par scope) + gérer supersede
4. **Marquer les leçons promues** : `🆕 new` → `📜 → ADR-00XX`
5. **Update ROADMAP.md** : `[~]` → `[x] livré YYYY-MM-DD`
6. **Append CHANGELOG.md** : entry Keep a Changelog (Added/Decided/Fixed)
7. **Update HANDOFF.md** : status feature livrée + next
8. **Update code-map** (seulement le non-déductible) : règle de couplage → `code-map.md`, gotcha → `code-map-gotchas.md`
9. **Archiver l'idée source** (si la feature vient d'une `idees/YYYY-MM-DD.md`) : status `💡 Backlog` → `✅ Promu en spec 00X`
10. **Suggère commit (chemins explicites) + PR + tag git** : `v$(date +%Y.%m.%d-%H%M)`

## 🩺 Audit hebdomadaire (~5 min)

```
/doc-health
```

Audit complet qui scanne sans modifier :

| Check                                                   | Seuil                          | Priorité |
| ------------------------------------------------------- | ------------------------------ | -------- |
| Budget de contexte auto-chargé (`context-budget.py`)    | > 25k tokens                   | 🔴       |
| Fraîcheur HANDOFF                                       | > 7j                           | 🔴       |
| Growth triggers (API_KEY → ACCESS.md, deploy → RUNBOOK) | > 5 hits                       | 🟢       |
| ADRs manquants (décisions dans plan.md sans ADR)        | ratio > 5                      | 🟢       |
| Leçons `🆕 new` en attente                              | > 5 ou >14j                    | 🟠       |
| Drift code-map vs code                                  | dernier commit > date code-map | 🟠       |
| Placeholders **CORE** non remplis (`{{UPPER_SNAKE}}`)   | > 0                            | 🔴       |
| Placeholders **CONTENT** non remplis (`{{libre}}`)      | informationnel — pas un signal | 🟢       |
| ADRs sans status valide                                 | > 0                            | 🔴       |
| Specs `[~]` EN COURS stalled                            | > 30j                          | 🟠       |
| Incohérence ROADMAP ↔ frontmatter `status:` des specs   | > 0                            | 🟠       |
| Instructions mortes dans les skills (refs `/x`, chemins) | > 0                            | 🟠       |
| Idées sans décision                                     | > 30j                          | 🟢       |
| Liens cassés dans docs                                  | > 0                            | 🔴       |
| Patterns auto-memory stables non consolidés             | informationnel                 | 🟢       |

Rapport généré → tu suis les actions par priorité.

## 📋 Cheat sheet — Quand utiliser quoi

| Situation                                  | Skill / Action                                                                |
| ------------------------------------------ | ----------------------------------------------------------------------------- |
| Nouveau projet                             | `/init-from-template`                                                         |
| Adopter le template sur un projet EXISTANT | `/adopt-template` (brownfield — merges non-destructifs + rétro-remplissage)   |
| Mettre à jour la méthode (template récent) | `/upgrade-template [vX.Y.Z]` — merge 3 voies, conflits signalés, doc intacte  |
| Démarrer une feature                       | `/spec "<titre>"` (scaffold 4 fichiers + ROADMAP)                             |
| Dérouler le pipeline complet (avec gates)  | `/feature "<titre>" [standard·tdd·custom]` — enchaîne spec→conception→code→tests→review→done                             |
| Arrêter le plan d'une feature              | `/conception <spec-id>` (explore → options → décision → plan + revue adverse) |
| Fin de session                             | `/handoff`                                                                    |
| Feature livrée                             | `/feature-done <spec-id>`                                                     |
| Décision tech structurante (cross-feature) | `/adr <scope> "<titre>"`                                                      |
| Décision tech locale à 1 feature           | Section `## Décisions` dans `specs/00X/plan.md`                               |
| Bug/observation à noter rapidement         | `/lecon <scope> "<titre>"`                                                    |
| Débugger un bug non trivial                | `/debug "<symptôme>"` (repro → cause → fix minimal → leçon)                   |
| Idée perso à capturer                      | `/idee "<titre>"`                                                             |
| Refacto majeur sur le code                 | `/codemap`                                                                    |
| Créer un skill / agent / pipeline conforme | `/scaffold skill·agent·pipeline "<nom>"` — conventions + référencement auto  |
| Audit hebdo                                | `/doc-health`                                                                 |
| BDD migration (Alembic)                    | plugin `db-migration` (`/plugin install db-migration@claude-setup`)          |
| Doc en lot (livraisons, audit + actions)   | agent `doc-maintainer` (Task) — jamais le HANDOFF                             |
| Déléguer une feature à une équipe          | `/agent-teams:team <spec-id>` (plugin, opt-in — le 1er lancement active l'équipe) |
| Pivot client                               | `/pivot "<raison>"` (workflow 9 étapes orchestrées)                           |
| Promotion leçon → ADR / rule               | `/lecon promote <date>`                                                       |
| Promotion idée → spec                      | `/idee promote <date>`                                                        |
| Supersede un ADR                           | `/adr supersede <NN> <scope> "<titre>"`                                       |
| Lister tous les ADRs                       | `/adr list [scope]`                                                           |
| Archiver leçons/idées vieilles             | `/lecon archive` ou `/idee archive`                                           |
| Projet terminé/abandonné → archiver        | `/archive-projet "<raison>"` — bilan + marquage + move vers `_archives/`      |
| Reprendre un projet archivé                | `/archive-projet restore`                                                     |
| Reprendre exactement où on en était        | `/resume` (built-in Claude)                                                   |
| Compaction context (auto)                  | RIEN — hooks gèrent                                                           |
| Édition fichier code (auto)                | RIEN — hook injecte les gotchas qui ciblent ce fichier                        |
| Mention API_KEY/deploy dans code (auto)    | RIEN — hook flag dans growth-suggestions                                      |

## 🔁 Workflow type pour une feature complète

```
1. Lire ROADMAP.md → choisir la prochaine feature
       ↓
2. /spec "Export PDF"
   → scaffold auto : specs/004-export-pdf/{research,spec,plan,tasks}.md
   → update ROADMAP.md auto
       ↓
3. /conception 004-export-pdf
   → explore (subagents : code + docs + mémoire projet) → 2-3 options → tu tranches
   → plan.md (points de vérification + circuit breakers) + tasks.md (DoD typée
     command_passes/file_exists/manual, phases ~35 min, partitionné) + revue adverse
       ↓
4. CODE → hooks auto : gotchas du fichier édité + growth detection
       ↓
5. Cocher les tasks au fur et à mesure dans tasks.md
       ↓
6. Si décision tech structurante surgit → /adr <scope> "<titre>"
       ↓
7. Si bug/observation → /lecon <scope> "<titre>"
       ↓
8. /handoff entre les sessions (ou hook auto si oubli)
       ↓
9. Tests verts + DoD rempli → /feature-done 004-export-pdf
       ↓
10. (Optionnel) /doc-health pour audit complet
```

## 🌳 Workflow cadrage (début projet)

**Important** : `.claude/docs/cadrage/` = ce que le CLIENT te file (input EXTERNE). Ne confonds pas avec `.claude/docs/idees/` (tes idées perso, input INTERNE).

```
Demande client reçue
       ↓
1. Update cadrage/README.md (verbatim demande, interlocuteurs, contraintes)
       ↓
2. Si ticket reçu → cadrage/tickets/TICKET-XXX-titre.md
   Si docs reçus → cadrage/documents/YYYY-MM-DD-doc.pdf
   Si réunion → cadrage/reunions/YYYY-MM-DD-kickoff.md
       ↓
3. Une fois cadrage mûr (interlocuteurs OK, contraintes claires) :
   → conception/research.md (brainstorm options)
       ↓
4. Quand approche claire :
   → conception/PRD.md (vision + scope + métriques)
       ↓
5. Validation PRD par décideur :
   → conception/ARCHITECTURE.md (plan technique)
       ↓
6. Architecture validée :
   → conception/tasks.md (plan MVP figé : sous-phases + DoD)
       ↓
7. ROADMAP.md créée à partir de tasks.md
       ↓
8. Specs par feature dans specs/00X-feature/
```

## 🔄 Workflow pivot (client change d'avis)

⚠️ **Workflow rare mais critique**. Protocole **9 étapes** (orchestré par `/pivot`) :

```
1. cadrage/reunions/YYYY-MM-DD-pivot.md (capture réunion)
       ↓
2. cadrage/README.md (update : nouvelle direction)
       ↓
3. conception/research.md (append ## Pivot YYYY-MM-DD)
       ↓
4. conception/PRD.md (version bump v1.0 → v2.0)
       ↓
5. conception/tasks.md (refonte : ## Phase X — Refonte v2)
       ↓
6. ROADMAP.md (nouvelle section v2 dashboard)
       ↓
7. Si pivot technique : /adr cadrage "Pivot stack" (supersede les anciens ADRs)
       ↓
8. /lecon cadrage "Pourquoi le pivot" (status 🆕 new pour review post-mortem)
       ↓
9. /handoff (snapshot HANDOFF.md : nouvelle direction + next steps)
```

→ `/pivot "<raison>"` orchestre ces 9 étapes avec validation à chaque étape (l'agent `doc-maintainer` peut le pré-remplir depuis le compte-rendu de réunion).

## 📜 Quand créer un ADR (cf section `/adr` plus bas pour comment)

**Règle courte** : décision **cross-feature** OU qui **survit à la feature** → ADR global (`/adr <scope> "<titre>"`). Décision **locale à une feature** → section `## Décisions` dans `specs/00X/plan.md` (pas d'ADR).

→ **Convention (ADR vs `plan.md`, naming, 5 scopes, frontmatter, statuts)** : [STRUCTURE.md § ADR](STRUCTURE.md#adr--architecture-decision-record). Le « comment » (capture / supersede / deprecate / list) → section `/adr` ci-dessous.

## 📝 Workflow leçons (`/lecon`)

Skill unifié avec 4 sous-modes pour gérer tout le cycle de vie d'une leçon :

```bash
# Capture (défaut)
/lecon mvp "Notion rate limit"

# Promotion vers ADR ou rule (après review)
/lecon promote 2026-05-24
/lecon promote 2026-05-24 adr      # force destination
/lecon promote 2026-05-24 rule

# Discard (pas pertinent finalement)
/lecon discard 2026-05-24 "Résolu par mise à jour SDK"

# Archive (batch des stables > 3 mois)
/lecon archive
```

### Cycle de vie

```
   /lecon mvp "Notion rate limit"
       ↓
   🆕 new
       ↓ (review hebdo /doc-health → /lecon promote)
       ├─► 📜 → ADR-NNNN  (créé via /adr auto)
       ├─► 🔧 → rule       (créé dans .claude/rules/)
       ├─► 🧠 memory only  (laissé à auto-memory)
       └─► ❌ discarded    (via /lecon discard)
       ↓ (> 3 mois post-promotion stable)
   📦 archived  (via /lecon archive)
```

**Quand promouvoir ?**

- Pattern apparu **2+ fois** dans le projet → 🔧 rule
- Décision **cross-feature** ou **structurante** → 📜 ADR
- Pattern technique **mineur, contextuel** → 🧠 memory only
- Idée erronée → ❌ discarded

Détection auto : `/doc-health` flag les `🆕 new` > 14j.

## 💡 Workflow idées (`/idee`)

Skill unifié avec 4 sous-modes (symétrique à `/lecon`) :

```bash
# Capture (défaut) — crée fichier daté
/idee "Sync inverse Notion → Prestashop"

# Promotion vers spec (déclenche /spec)
/idee promote 2026-05-22

# Discard (abandonné)
/idee discard 2026-05-22 "Trop coûteux"

# Archive (batch des stables > 3 mois)
/idee archive
```

### Cycle de vie

```
   /idee "<titre>"
       ↓
   💡 Backlog (fichier idees/YYYY-MM-DD-titre.md créé)
       ↓ (review : valeur claire + effort acceptable)
       ├─► ✅ Promu en spec 00X  (via /idee promote, déclenche /spec auto)
       └─► ❌ Abandonné          (via /idee discard)
       ↓ (post-décision, > 3 mois)
   📦 archived/                  (via /idee archive)
```

**Important** : `idees/` = brainstorm **INTERNE** (toi). Ne pas confondre avec `cadrage/` = input **EXTERNE** (client).

Détection auto : `/doc-health` étape 9 flag les idées sans décision > 30j.

## 📜 Workflow ADRs (`/adr`)

Skill unifié avec 4 sous-modes :

```bash
# Capture (défaut)
/adr mvp "Stack BDD : Postgres vs SQLite"

# Supersede explicite (remplace ADR-0003)
/adr supersede 0003 mvp "Nouvelle stack httpx"

# Deprecate (marque comme à éviter, pas remplacé)
/adr deprecate 0005 "API tierce dépréciée"

# Lister (avec filtre optionnel)
/adr list
/adr list mvp        # filtre scope
/adr list accepted   # filtre status
```

### Pattern supersede

Un ADR est **immuable**. Si décision change :

1. `/adr supersede <NN> <scope> "<titre>"` (orchestration auto)
2. Le skill :
   - Crée le nouvel ADR avec `supersedes: <NN>`
   - Update l'ancien : `status: superseded` + `superseded_by: <new NN>`
   - Update `adr/README.md` : déplace ancien vers section "archived / superseded"
   - Append CHANGELOG section `Decided`

### Pattern deprecate (vs supersede)

- **supersede** : décision remplacée par une autre (avec lien)
- **deprecate** : décision encore là mais on n'élargit plus l'usage (pas de remplaçant)

→ Promotions d'ADR en lot (plusieurs décisions mûres d'un coup) : agent `doc-maintainer` (Task tool).

## 🤖 Agent doc-maintainer

L'agent `doc-maintainer` (Task tool) fait la **maintenance doc EN LOT, hors conversation** : il scanne l'état
global, séquence les skills doc (`/feature-done`, `/adr`, `/lecon`, `/idee`, `/codemap`) et **propose tous les
diffs en une fois** — sans ré-implémenter leur logique. Il **n'écrit jamais le HANDOFF** : un subagent démarre à
contexte vide (ni échecs tentés, ni blockers) et ne peut pas obtenir ta validation → `/handoff` dans le fil principal.

### Quand préférer l'agent vs un skill

| Tu veux                                                 | Préfère                                  |
| ------------------------------------------------------- | ---------------------------------------- |
| 1 action ciblée rapide (< 1 min)                        | Skill (`/adr`, `/lecon`, etc.)           |
| Fin de session (HANDOFF)                                | `/handoff` — toujours dans le fil principal |
| Plusieurs specs livrées d'un coup (ROADMAP + CHANGELOG) | Agent `doc-maintainer`                   |
| Pivot client (9 étapes)                                 | `/pivot` (l'agent peut le pré-remplir)   |
| Audit + actions (vs juste audit)                        | Agent                                    |
| Promotion multiple leçons → ADRs en une passe           | Agent                                    |

### Comment l'invoquer

```
Lance l'agent doc-maintainer pour faire l'audit complet du projet et proposer toutes les MAJ.
```

(Claude utilisera le Task tool automatiquement)

### Règles de l'agent

- **JAMAIS d'overwrite silencieux** : toujours diff par diff
- **Ton concis**, factuel
- **Dates ISO** (YYYY-MM-DD)
- **Préserve les sections custom** de l'user (heuristique : non-templated → ne pas toucher)

## 🧑‍🤝‍🧑 Agent teams — déléguer à une équipe (opt-in)

**Rien n'est câblé dans le cœur** (v1.5) : le flag expérimental monte une équipe à chaque session et la rule
d'équipe pesait sur chaque session, même solo. Le skill `/agent-teams:team`, les rôles d'exécution
(`worker`/`front-end`/`back-end`/`tester`) et le hook de trace viennent du **plugin `agent-teams`** ;
`reviewer` et les `explore-*` restent dans le cœur (utilisables en subagents sans équipe).

```
/plugin install agent-teams@claude-setup   # une fois (marketplace kurt83340/claude-Setup)
/agent-teams:team 001-erp-connector       # 1er lancement = ACTIVATION, puis relance de Claude Code
```

**Activation** (1er lancement, avec ton accord) : copie la rule d'équipe du plugin dans `.claude/rules/agent-teams.md`
(invariants lead/teammate, auto-chargée), pose `env.CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` + `teammateMode: "auto"`
dans `settings.json` (ou `settings.local.json` si tu ne veux pas le partager), puis demande une **relance** (flag lu au
démarrage) — rappelle ensuite `/agent-teams:team <id>`. `auto` = un pane tmux par teammate si la session tourne
**dans** tmux (`tmux new -s <projet>` avant `claude`), sinon teammates in-process dans le terminal courant.
⚠️ En mode panes, le corps d'une définition d'agent **remplace** le system prompt par défaut du teammate (en
in-process il s'y ajoute) : chaque rôle du plugin porte donc son propre « Cadre de travail ».

Le lead propose un **plan d'équipe** (rôles préconfigurés `worker`/`front-end`/`back-end`/
`tester`/`reviewer` ou agents ad-hoc, 1 worktree par codeur, topologie de communication),
attend ta **validation**, spawne, suit (task list native + rapports SendMessage +
`.claude/.cache/team-progress.log`), merge, **débriefe la mémoire** et clôt proprement.

**Cycle de vie** : un teammate spawné par le lead de sa propre initiative est fermé par lui à
la clôture (lead-owned) ; un teammate que TU as demandé **persiste** — seul toi décides de le
fermer (user-owned). **Topologie** : par défaut chaque teammate ne parle qu'au lead
(hub-and-spoke) ; le mesh (teammates qui s'écrivent entre eux) est opt-in, scopé, décidé au spawn.

**Sessions sans prompts (sandbox uniquement)** : les teammates **héritent du mode de
permission du lead** au spawn → un seul levier. Soit le flag ponctuel
(`tmux new -s <projet> 'claude --resume --dangerously-skip-permissions'`), soit persistant
dans `.claude/settings.local.json` (non versionné) :
`{ "permissions": { "defaultMode": "bypassPermissions" } }`. Les règles `deny` (rm -rf,
`.env`…) restent appliquées. ⚠️ À réserver aux bacs à essai — sur un projet client, garde le
mode normal (les `allow`/`ask` du template existent pour ça).

→ Invariants : `.claude/rules/agent-teams.md` (posée par l'activation) · protocole complet : `skills/team/protocole.md` du plugin (lu par `/agent-teams:team`).

## 🤖 Comprendre les hooks automatiques

| Hook                       | Quand ça se déclenche         | Ce que ça fait                            |
| -------------------------- | ----------------------------- | ----------------------------------------- |
| `PreCompact`               | Avant compaction du contexte  | Snapshot (git + derniers messages humains) dans `.claude/.cache/` (non-versionné) + marker `/tmp/` |
| `SessionStart` (compact)   | Reprise après compaction      | Re-inject le snapshot + ré-arme l'injection des gotchas |
| `SessionEnd`               | Fin de session **sans `/handoff`** ayant laissé une trace git (commit ou arbre modifié) | Filet « n'oublie rien » : snapshot (git + derniers messages humains) dans `.claude/.cache/`. Rien après un `/handoff` ni après une session sans trace (v1.5 : fini la fausse alerte à chaque démarrage) |
| `SessionStart` (startup)   | Nouveau démarrage             | Marqueur de début de session (heure + empreinte git) ; purge du cache par-session > 7 j ; injecte le filet fin-de-session s'il est plus frais que HANDOFF.md, puis le consomme ; **filet budget** : surface auto-chargée > 25k tokens → coupables + remède injectés (`CLAUDE_CONTEXT_BUDGET_MAX`, 0 = off) |
| `SessionStart` (resume · clear) | `claude --resume`, `/clear` | Marqueur de début de session (base du filet `SessionEnd`) |
| `PreToolUse(Edit\|Write)`  | Édition d'un fichier de code du projet (hors `.claude/`, docs, config) | Gotchas de `code-map-gotchas.md` qui **ciblent ce fichier**, 1×/fichier/session (ré-armé après compaction) — arrivent avec le résultat de l'outil, juste après l'édition. Couplage + intention : déjà en contexte via `code-map.md` |
| `PostToolUse(Edit\|Write)` | Après Edit/Write fichier      | Détecte API_KEY/deploy/RGPD → flag growth |
| `Stop`                     | Fin de tour Claude            | Rappel `/handoff` si HANDOFF > 24h + changements git — **1×/session** ; **garde-fou taille** : HANDOFF > 12 Ko → rappel 1×/session (`CLAUDE_HANDOFF_MAX_BYTES`, 0 = off) |
| `TaskCreated`/`TaskCompleted`/`TeammateIdle` | Événements d'équipe (plugin `agent-teams`) | Trace JSON dans `.claude/.cache/team-progress.log` |

**Tous non-bloquants** : si un hook échoue, Claude continue. Lancés via `python3 …` / `bash …` depuis
`settings.json` — pas de `chmod +x` à faire.

**Debug** : `claude --debug` pour voir les hooks en action.

## 📐 Conventions (source unique : STRUCTURE.md)

- **Quand créer un fichier** (à la demande, JAMAIS préventivement) → [STRUCTURE.md § À créer quand ?](STRUCTURE.md#à-créer-quand-)
- **Naming** (specs, ADR, réunions, docs reçus, idées, leçons, tags git) → [STRUCTURE.md § Conventions de naming](STRUCTURE.md#conventions-de-naming)
- **Diagrammes** (3 formats, où les placer) → [STRUCTURE.md § Convention diagrammes](STRUCTURE.md#convention-diagrammes)
- **Statuts** : ROADMAP `[ ]`/`[~]`/`[x]` ↔ `status:` des specs → [STRUCTURE.md § ROADMAP](STRUCTURE.md#roadmapmd-vivant--exemple) · ADR → [§ ADR](STRUCTURE.md#adr--architecture-decision-record) · leçons / idées → leurs workflows ci-dessus

## 🔐 Permissions (`settings.json`)

3 niveaux dans `.claude/settings.json` :

```json
{
  "permissions": {
    "allow": [...],   // exécuté sans demander
    "ask": [...],     // demande confirmation à chaque fois
    "deny": [...]     // refus systématique
  }
}
```

**Defaults du template** :

- `allow` : pytest, ruff, mypy, alembic, uv, npm, `git add/commit/tag/branch`, `git worktree add/list/prune`, `git init`, `cp`, `date`, scripts du template (render, cleanup, archive-projet), `Edit(./**)` — les lectures (Read, `git status/log/diff`, grep…) sont déjà autorisées nativement : plus listées (v1.5)
- `ask` : `git push`, `git reset`, `git merge`, `git branch -d/-D`, `git tag -d`, `git worktree remove`, `alembic downgrade`, `./scripts/deploy`
- `deny` : `rm -rf`, `Read(.env)` + `Read(.env.*)` **à toute profondeur** avec exceptions pour les gabarits (`Read(!.env.example)`, `!.env.sample`, `!.env.template`), `secrets.*`, `*.pem`, `*.key` — `ACCESS.md` n'est **pas** en deny : y référencer les accès par NOM (où trouver quoi), jamais les valeurs

**Secrets — 3 filets** (v1.5) : `.gitignore` ignore **tous** les `.env*` sauf les gabarits (`.env.example/.sample/.template`),
ainsi que `secrets.*`, `*.key`, `*.pem`, `credentials.json` · deny `Read` ci-dessus · **gitleaks** au commit (`.pre-commit-config.yaml`,
activé par `pre-commit install` — proposé à l'init ; scan complet : `pre-commit run --all-files`). Les skills committent
par chemins explicites (`git add <chemins>`), jamais `git add -A` à l'aveugle.

> ⚠️ **Le deny `Read(...)` n'est qu'une première barrière** : d'après la doc officielle des permissions, il couvre les outils
> fichiers intégrés et les commandes fichier que Claude Code reconnaît dans Bash (`cat`, `head`, `tail`, `sed`, `tee`, redirections)
> — **pas** un `grep -r` lancé depuis le dossier, ni un script Python/Node qui ouvre le fichier. Barrière au niveau de l'OS →
> activer le [sandbox](https://code.claude.com/docs/en/sandboxing).

**Customiser par projet** : édite `.claude/settings.json` pour ajouter tes commandes spécifiques (ex: `n8n:*`, `docker compose:*`) ; réglages perso non partagés → `.claude/settings.local.json` (gitignoré).

## 📁 Organisation skills / agents

Skills et agents sont **à plat** : `.claude/skills/<nom>/SKILL.md`, `.claude/agents/<nom>.md` — Claude Code ne scanne
qu'**1 niveau** ([issue #18192](https://github.com/anthropics/claude-code/issues/18192)). Plus de dossier `commands/` : les
custom commands ont fusionné avec les skills ([doc officielle](https://code.claude.com/docs/en/skills) : « Skills are recommended »).

- **Invocation = nom du dossier** (`.claude/skills/handoff/` → `/handoff`) ; `name:` du frontmatter identique par convention (exception : SKILL.md à la racine d'un plugin, où `name:` compte). Un agent s'invoque via le Task tool, jamais en `/nom`.
- **Grouper par thème** : préfixe (`n8n-deploy`, `n8n-test` — usage perso) ou plugin (`/<plugin>:<skill>` — distribution, namespacing officiel). Pas de sous-dossier.
- **Conflits de noms** : un seul espace (`.claude/skills/`, `~/.claude/skills/`, plugins) — Claude n'en garde qu'un → renomme dossier + `name:` du moins prioritaire.
- Inventaire canonique des skills (compte CI-vérifié), import depuis GitHub / MCP / plugin : [skills/README.md](skills/README.md) · agents : [agents/README.md](agents/README.md).

## 🛠️ Customisation

### Désactiver un hook

Édite `.claude/settings.json` et retire/vide la section concernée. Ex pour désactiver le rappel HANDOFF :

```json
"Stop": []
```

### Adapter un skill

Édite directement le `.claude/skills/<nom>/SKILL.md` (ex: `.claude/skills/handoff/SKILL.md`). Le frontmatter `allowed-tools` contrôle ce que Claude peut faire.

### Ajouter un nouveau skill (custom)

> 🏗️ **Le plus simple : `/scaffold skill "<nom>"`** — il pose les bonnes questions (sensible ?
> outils ?), crée le fichier conforme ET l'ajoute à l'inventaire `skills/README.md`. La procédure
> manuelle ci-dessous reste valable (penser à recenser le skill dans l'inventaire).

```bash
mkdir -p .claude/skills/mon-skill
cat > .claude/skills/mon-skill/SKILL.md <<'EOF'
---
name: mon-skill
description: Description claire pour que Claude sache quand l'invoquer
allowed-tools: Read, Write, Bash(...)
---

# Body du skill (instructions à Claude)
EOF
```

→ **Invocation** : `/mon-skill`. Le `name:` doit matcher le nom du dossier.

### Ajouter des skills depuis ailleurs (GitHub, MCP, autres repos)

Copie à plat dans `.claude/skills/<nom>/` (préfixe de provenance si besoin) — pas-à-pas : [skills/README.md § Importer un skill externe](skills/README.md#importer-un-skill-externe).

### Désactiver un skill (sans le supprimer)

Frontmatter : `disable-model-invocation: true` (Claude ne le suggérera plus, mais `/skill-name` manuel marche encore).

### Ajouter une slash command projet (ex. `/deploy`)

= un skill (« Ajouter un nouveau skill » ci-dessus : `mkdir -p .claude/skills/deploy` + SKILL.md). ⚠️ Action sensible
(deploy, push prod) → `disable-model-invocation: true` au frontmatter : invocation **uniquement** via `/deploy`,
jamais déclenchée par Claude tout seul.

## ❌ Anti-patterns à éviter

- ❌ Créer un fichier "au cas où" (= ça pourrit)
- ❌ Mélanger `cadrage/` (input externe) et `idees/` (input interne)
- ❌ **Modifier un ADR passé** (créer un nouveau qui le supersede)
- ❌ Mettre des credentials dans le repo (tous les `.env*` sont gitignorés sauf les gabarits, gitleaks bloque au commit — valeurs ailleurs)
- ❌ `git add -A` sans relire `git status --short` (un fichier sensible non ignoré part au commit)
- ❌ Bug log séparé (tout va dans CHANGELOG)
- ❌ Skip le `/handoff` en fin de session (= perte de contexte garantie)
- ❌ Créer RUNBOOK avant la première mise en prod (= ça pourrit)
- ❌ Créer STAKEHOLDERS.md si < 5 personnes (= dans cadrage/README suffit)
- ❌ Cocher tasks `[x]` sans vérifier le DoD
- ❌ Promouvoir trop d'ADRs (décision locale = `## Décisions` dans plan.md, pas ADR)
- ❌ ADR sans frontmatter YAML (illisible machine, rate les audits doc-health)
- ❌ Ajouter un `@` dans CLAUDE.md (rule ou doc) : rechargé à CHAQUE appel — lien simple à la place
- ❌ Déléguer le HANDOFF à un subagent (il n'a pas la conversation) — `/handoff` dans le fil principal

## ✅ Bonnes pratiques

- ✅ Partir du HANDOFF au démarrage de chaque session (déjà en contexte via `@`)
- ✅ `/handoff` à la fin de chaque session
- ✅ Numéroter spec/ADR continûment (jamais de reset)
- ✅ Dater les fichiers de `idees/`, `cadrage/reunions/`, `cadrage/documents/`
- ✅ Référencer les ADRs depuis les specs concernées
- ✅ MAJ ROADMAP **à chaque** changement d'état de feature
- ✅ Garder le `CLAUDE.md` racine court & centré projet (< 60 lignes, 2 `@` max) ; méthode → `.claude/CLAUDE.md` (index mince) ; conventions → `.claude/rules/*.md` (auto-chargées, jamais en `@`)
- ✅ Préférer un ADR à un long commit message pour les décisions structurantes
- ✅ Diff par diff (l'agent doc-maintainer le fait par défaut)

## 🐛 Troubleshooting

### Les skills n'apparaissent pas dans `/skills`

- Vérifier que le fichier est `SKILL.md` (majuscules) dans `.claude/skills/<nom>/` (à plat, 1 niveau seulement — Claude Code ne scanne pas récursivement, [issue #18192](https://github.com/anthropics/claude-code/issues/18192))
- Frontmatter valide (`name:` + `description:` minimum)
- Le `name:` du frontmatter doit matcher le nom du dossier
- Relancer Claude Code (les skills sont scannés au démarrage)
- Lancer `/doctor` pour voir les erreurs

### Un hook ne se déclenche pas

- Vérifier le chemin du script dans `settings.json` (utiliser `"${CLAUDE_PROJECT_DIR}"` — **quoté**, sinon ça casse dès que le chemin du projet contient un espace)
- Vérifier que `python3` (et `bash` pour `Stop`) est dans le PATH — les hooks sont lancés via `python3 …` / `bash …`, pas besoin de `chmod`
- Relancer Claude Code après une modif de `settings.json` (hooks lus au démarrage)
- Vérifier le `matcher` (regex `Edit|Write` est correct, pas `Edit\\|Write`)
- Lancer `claude --debug` et regarder les logs

### Le hook code-map injecte rien

- Normal s'il n'y a aucun gotcha pour ce fichier : le hook n'injecte QUE les entrées de `code-map-gotchas.md` qui
  le ciblent (chemin, nom de fichier ou dossier cité en backticks, ou heading `###` ; section « Globaux » = toute
  édition de code) — 1×/fichier/session. Projet < 1.4 sans `code-map-gotchas.md` → § Gotchas de `code-map.md`
- Rien pour `.claude/`, les docs et la config (`.md`, `.json`, `.yaml`…) ; tout autre fichier du projet compte (plus
  de liste fixe `src/`/`tests/`/`lib/`/`app/`)
- L'injection arrive **avec le résultat** de l'Edit/Write (juste après l'édition), pas avant

### Le contexte est déjà à 15-20 % au premier prompt

Le projet a grossi et les docs **auto-chargées** avec lui (HANDOFF avec son journal, code-map avec
tous ses gotchas, ROADMAP…) — mesuré v1.4 : 144k tokens au 1er tour sur un projet d'un mois. Repère v1.5 :
template vierge ≈ 6,5k tokens auto-chargés (11k en v1.4.1) + ≈ 2,2k pour la liste des skills (nom + description).

```bash
python3 .claude/skills/doc-health/scripts/context-budget.py          # qui pèse quoi (tokens ≈ chars/2)
python3 <template>/.claude/skills/init-from-template/scripts/slim-context.py --root . --dry-run   # projet < v1.4
```

Projet < v1.4 : `/upgrade-template` applique cette migration (1.4.0) tout seul.

Remèdes : journal → `HANDOFF-journal.md`, gotchas → `code-map-gotchas.md`, ROADMAP en lien simple,
jamais de `@` sur une rule scopée `paths:`. Le socle hors projet (`~/.claude/CLAUDE.md`, hooks de
plugins, MCP) se voit aussi dans le rapport (`user, hors projet`).

### `/init-from-template` ne marche pas

- Vérifier que tu es dans un projet copié (pas dans le template original)
- Lancer manuellement : `python3 .claude/skills/init-from-template/scripts/render.py --list-placeholders`

### Auto-memory ne sauvegarde pas

- Natif et actif par défaut — le template ne le règle plus (v1.5) : vérifier qu'il n'a pas été coupé (`/memory`, ou `"autoMemoryEnabled": false` dans tes settings)
- Vérifier que `~/.claude/projects/<encoded-path>/memory/` est créé
- Auto-memory ne sauvegarde que tous les ~5-10 messages (pas chaque turn)

### Agent doc-maintainer pas trouvé

- Vérifier `.claude/agents/doc-maintainer.md` existe (à plat dans `agents/`, pas de sous-dossier)
- Frontmatter valide (`name`, `description`, `tools`, `model: inherit`)
- Invoquer via Task tool, pas `/doc-maintainer` (les agents ne sont pas des slash commands)

## 📚 Skills built-in Claude utiles

| Skill                | Pour quoi                                                           |
| -------------------- | ------------------------------------------------------------------- |
| `/security-review`   | Avant chaque push prod (vérif sécurité changes courants)            |
| `/code-review`       | Avant merge d'une feature complexe                                  |
| `/resume`            | Reprendre session précise (fidélité 100%)                           |
| `/loop 10m /handoff` | Auto-update HANDOFF toutes les 10 min en session longue (optionnel) |
| `/init`              | ❌ **NE PAS utiliser** (ce template a déjà CLAUDE.md)               |
| `/compact`           | Force la compaction manuelle (rare, sinon auto à ~90%)              |
| `/clear`             | Reset complet du contexte (perd auto-memory volatile)               |
| `/doctor`            | Diagnostic des skills/hooks/agents                                  |

## 📚 Aller plus loin

| Fichier                                                                        | Pour quoi                                                       |
| ------------------------------------------------------------------------------ | --------------------------------------------------------------- |
| [STRUCTURE.md](STRUCTURE.md)                                                   | **Référence** : arborescence + conventions (naming, ADR, statuts, diagrammes, quand créer) |
| [CLAUDE.md](../CLAUDE.md)                                                      | Index **projet** : résumé + nav doc + conventions               |
| [.claude/CLAUDE.md](CLAUDE.md)                                         | Index **méthode** (mince) : où est quoi, pipelines, agents, plugins, version |
| [.claude/skills/README.md](skills/README.md)                           | Inventaire canonique des skills (CI-vérifié) + conventions      |
| [.claude/rules/template-maintenance.md](rules/template-maintenance.md) | Invariants d'écriture de la doc (chargée quand Claude lit `.claude/docs/`) |
| [.claude/docs/adr/README.md](docs/adr/README.md)                       | Convention ADRs détaillée                                       |
| [.claude/docs/conception/README.md](docs/conception/README.md)         | Pattern mirror macro/micro                                      |
| [.claude/docs/cadrage/README.md](docs/cadrage/README.md)               | Template cadrage initial                                        |
| `EXAMPLES/acme-sync-erp-notion-docs/`                                          | Exemple rempli (repo template ; exclu de ton projet par l'init) |

## 🎯 Philosophie

**3 principes** :

1. **Documenter au fur et à mesure**, pas à la fin (sinon tu oublies)
2. **Laisser les skills faire le boulot répétitif** (handoff, feature-done, doc-health, adr)
3. **Faire confiance aux hooks** pour ce qui doit toujours se passer (snapshots, gotchas ciblés, growth detection)

**Anti-pattern** : essayer de tout faire manuellement → tu vas te démotiver. Le template existe pour automatiser l'ennuyeux.

**Rappel** : le but du template c'est qu'**en 30 secondes**, n'importe quelle session démarre avec l'essentiel auto-chargé (HANDOFF + code-map) et le reste à un lien de distance. **HANDOFF.md** est la clé de voûte.

**Mémoires complémentaires** = redondance saine. Si auto-memory perd un truc, HANDOFF rattrape. Si HANDOFF est stale, le code parle. Si le code est obscur, CLAUDE.md + rules cadrent.
