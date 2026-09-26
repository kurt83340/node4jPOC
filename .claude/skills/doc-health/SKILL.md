---
name: doc-health
description: Audit hebdo de la doc projet, en lecture seule : budget de contexte, fraîcheur du HANDOFF, ADR manquants, ACCESS/RUNBOOK à créer, drift code-map, leçons en attente, cohérence ROADMAP/specs, instructions mortes, patterns auto-memory à promouvoir. Produit un rapport priorisé sans rien modifier.
allowed-tools: Read, Glob, Grep, Bash(find:*), Bash(stat:*), Bash(git log:*), Bash(date:*), Bash(python3 .claude/skills/doc-health/scripts/context-budget.py:*)
disable-model-invocation: false
---

# /doc-health — Audit hebdomadaire du template

> **Quand ne PAS utiliser** : agir/écrire les corrections → agent `doc-maintainer` (scan + diffs) ·
> seulement resynchroniser la carte du code → `/codemap`.
> **Réversibilité** : 🟢 lecture seule — ne modifie RIEN (rapport uniquement).

Ton rôle : scanner la santé documentaire du projet et produire un rapport actionnable.

## Étape 0 — Budget de contexte auto-chargé (v1.4)

```bash
python3 .claude/skills/doc-health/scripts/context-budget.py --max 25000
```

Liste ce que Claude Code charge **sans qu'on le lui demande** au démarrage (CLAUDE.md + `@-imports`,
`.claude/CLAUDE.md`, rules non scopées ; user et auto-memory à part) avec l'estimation calibrée
(tokens ≈ chars/2). Seuil **25k tokens** (projet) → au-delà, 🔴 dans le rapport avec les coupables :

- HANDOFF > 40 lignes → journal dans `HANDOFF-journal.md` (`/handoff` Étape 3bis le fait)
- code-map > 3k tokens → gotchas dans `code-map-gotchas.md`, § « Quand mettre à jour » = 3 lignes
- rule scopée (`paths:`) importée en `@` → retirer le `@` (scoping court-circuité)
- ROADMAP en `@` → lien simple (les skills la lisent explicitement)
- projet généré < v1.4 → `python3 <template>/.claude/skills/init-from-template/scripts/slim-context.py --root . --dry-run`

## Étape 1 — Fraîcheur des fichiers vivants

```bash
# Date de dernière modif des fichiers vivants
stat -c "%y %n" .claude/docs/HANDOFF.md
stat -c "%y %n" .claude/docs/ROADMAP.md
stat -c "%y %n" .claude/docs/CHANGELOG.md
stat -c "%y %n" .claude/docs/ACCESS.md
stat -c "%y %n" .claude/docs/cadrage/README.md
```

Seuils :
| Fichier | Vert | 🟠 Orange | 🔴 Rouge |
|---|---|---|---|
| .claude/docs/HANDOFF.md | < 3j | 3-7j | > 7j |
| .claude/docs/ROADMAP.md | < 7j | 7-14j | > 14j |
| .claude/docs/CHANGELOG.md | < 14j (si livraison récente) | — | > 30j sans entry |
| .claude/docs/ACCESS.md | — | — | > 30j (peut-être obsolète) |

## Étape 2 — Growth opportunities

Détecter les triggers de création de nouveaux fichiers :

```bash
# Credentials/API/OAuth mentionnés sans .claude/docs/ACCESS.md riche
grep -rE "API_KEY|token|secret|OAuth|credentials" .claude/docs/conception/ src/ 2>/dev/null | head -5

# Mentions de déploiement/prod sans .claude/docs/RUNBOOK.md
grep -rE "deploy|prod|production|incident|rollback" .claude/docs/conception/ src/ 2>/dev/null | head -5

# Termes métier répétés sans GLOSSARY enrichi
# (heuristique : mots en majuscules ou jargons spécifiques détectés > 3 fois)
```

Si triggers détectés ET fichier vide/minimal :

- 🟢 Suggérer d'enrichir .claude/docs/ACCESS.md / .claude/docs/RUNBOOK.md / .claude/docs/GLOSSARY.md

## Étape 2bis — Review `.growth-suggestions.md` (auto-flag du hook PostToolUse)

Le hook PostToolUse écrit dans `.claude/.growth-suggestions.md` à chaque détection de growth trigger pendant les Edit/Write. Ce fichier peut grossir indéfiniment sans review.

```bash
# Lire les suggestions auto-flag
if [ -f .claude/.growth-suggestions.md ]; then
  ENTRIES=$(grep -c "^-" .claude/.growth-suggestions.md)
  AGE_DAYS=$((($(date +%s) - $(stat -c %Y .claude/.growth-suggestions.md)) / 86400))
  echo "📝 $ENTRIES suggestions auto-flag, dernière MAJ il y a ${AGE_DAYS}j"
fi
```

**Reporter dans le rapport** :

- Si > 10 entries → 🟠 "Review et trie : action OU discard. Tronquer le fichier après."
- Si > 30 entries → 🔴 "Backlog growth important, action urgente"

**Action proposée à l'user** : pour chaque entry, soit `→ action (créer .claude/docs/ACCESS.md, etc.)` soit `→ discard` (ajouter ligne `~~strikethrough~~` dans le fichier).

Quand toutes les entries sont actées/discardées : truncate le fichier (garder le header).

## Étape 3 — ADRs manquants (décisions CROSS-feature uniquement)

> ⚠️ Les décisions **locales à une feature** (lib choisie pour cette spec) vivent dans la section `## Décisions` de son `plan.md` et **n'ont PAS besoin d'ADR**. Ne flagge QUE les décisions qui impactent > 1 spec ou survivent à la feature.

```bash
# Mentions de choix dans les plan.md, HORS d'une section "## Décisions" (déjà documentées localement)
grep -rnE "choisi|retenu|plutôt que| vs " .claude/docs/specs/*/plan.md 2>/dev/null \
  | grep -vi "décisions" | head -10
```

Si une décision **cross-feature** non capturée ressort → suggérer `/adr`. **Ignore** celles déjà dans un `## Décisions` de plan.md (légitimement locales).

## Étape 4 — Leçons en attente de décision

```bash
# Leçons RÉELLES en attente : status 🆕 new sous un header daté réel (## 20XX-…),
# en EXCLUANT le bloc exemple du template (header ## YYYY-MM-DD).
awk '/^## [0-9][0-9][0-9][0-9]-/{real=1} /^## YYYY/{real=0} real&&/🆕 new/{n++} END{print n+0}' .claude/docs/lecons.md
```

- Si > 5 entries `🆕 new` → 🟢 review hebdo (`/lecon promote` / `discard`)
- Si une `🆕 new` date de > 14j → 🟠 "en attente de décision depuis > 14j → review urgent"

## Étape 5 — Drift code-map vs code

```bash
# Date code-map vs date dernier commit dans src/
stat -c %Y .claude/docs/code-map.md
git log -1 --format=%ct -- src/ 2>/dev/null
```

Si dernier commit src/ > date code-map → 🟠 "code-map peut être stale, lancer /codemap pour resync"

## Étape 6 — Sections cassées / TODO non remplis

```bash
# Placeholders non remplis ({{...}})
grep -rE "\{\{[^}]+\}\}" .claude/docs/ | head -10

# TODO non décrochés
grep -rE "^- \[ \].*TODO|TODO :" .claude/docs/ | head -10
```

## Étape 7 — ADRs sans status valide

```bash
# ADRs où le frontmatter status manque ou est vide
for f in .claude/docs/adr/[0-9]*.md; do
  if ! grep -q "^status:" "$f"; then
    echo "🔴 $f : pas de status"
  fi
done

# ADRs status: superseded mais pas archivés dans le README
grep -l "^status: superseded" .claude/docs/adr/[0-9]*.md 2>/dev/null
# Vérifier que chacun est listé dans la section "archived / superseded" du README
```

## Étape 8 — Specs stalled + liens ROADMAP cassés

```bash
# Specs marquées [~] EN COURS dans ROADMAP mais pas de commit récent
grep -E "\[~\].*EN COURS" .claude/docs/ROADMAP.md
# Pour chaque spec en cours, vérifier la dernière modif des fichiers
find .claude/docs/specs/*/tasks.md -mtime +30 2>/dev/null

# Liens spec cassés : chaque spec référencée dans ROADMAP doit exister sur disque
grep -oE "specs/[0-9a-z-]+/spec\.md" .claude/docs/ROADMAP.md | while read -r p; do
  [ -f ".claude/docs/$p" ] || echo "🔴 ROADMAP référence une spec absente : $p"
done
```

- Si `[~]` depuis > 30j → 🟠 "spec stalled, refresh ou archive"
- Si spec référencée absente → 🔴 "lien ROADMAP cassé"

**Cohérence ROADMAP ↔ frontmatter `status:`** (la ROADMAP est un dashboard — le frontmatter
de chaque `spec.md` est la source machine-readable ; s'ils divergent, l'un des deux ment) :

```bash
for f in .claude/docs/specs/[0-9]*/spec.md; do
  [ -f "$f" ] || continue
  st=$(grep -m1 "^status:" "$f" | awk '{print $2}')
  id=$(basename "$(dirname "$f")")
  case "$st" in
    in-progress) grep -qE "\[~\].*$id" .claude/docs/ROADMAP.md || echo "🟠 $id : status: in-progress mais ROADMAP ≠ [~]" ;;
    done)        grep -qE "\[x\].*$id" .claude/docs/ROADMAP.md || echo "🟠 $id : status: done mais ROADMAP ≠ [x]" ;;
    parked)      grep -qE "\[~\].*$id" .claude/docs/ROADMAP.md && echo "🟠 $id : status: parked mais ROADMAP encore [~]" ;;
  esac
done
```

- Spec sans frontmatter `status:` (antérieure à v0.19) → 🟢 "ajouter le frontmatter au prochain passage"

## Étape 9 — Idées âgées sans décision

```bash
# Idées dans idees/ > 30 jours sans status décidé
find .claude/docs/idees/ -name "*.md" -mtime +30 2>/dev/null | head -10
```

Si > 5 idées vieilles → 🟢 "review idées : promouvoir / discard / archiver"

## Étape 10 — Auto-memory : patterns à consolider

> L'auto-memory (layer 2) est **machine-locale et non versionnée** — un cache. La durabilité
> (« n'oublie rien ») vient de la **promotion** vers les docs versionnées (rule / leçon / ADR).

1. Localise la mémoire : `autoMemoryDirectory` dans `.claude/settings.json` si défini, sinon
   `~/.claude/projects/<clé>/memory/MEMORY.md` où `<clé>` = le chemin absolu du repo avec
   chaque caractère non-alphanumérique remplacé par `-` (ex. `/mnt/e/proj/x` → `-mnt-e-proj-x`).
   (Keyée par repo git : les worktrees partagent la même mémoire.) Lis-la avec le tool Read.
2. Lis `MEMORY.md` (l'index) + les fichiers de mémoire pointés qui semblent stables.
3. Flag pour le rapport :
   - Pattern répété/confirmé sur plusieurs sessions → 🟢 « promouvoir en rule (`.claude/rules/`) ou leçon (`/lecon`) »
   - Décision structurante apprise → 🟢 « promouvoir en ADR (`/adr`) »
   - Mémoire contredite par le code actuel → 🟠 « stale : corriger ou supprimer le fichier mémoire »
   - Pas de MEMORY.md → ✅ RAS (rien d'appris ou auto-memory désactivée)

## Étape 10bis — Instructions mortes dans skills & rules (no-op audit)

> Les instructions rotent comme du code : une consigne qui pointe vers un skill supprimé ou un
> chemin disparu ne fait pas « rien » — elle **dégrade** l'agent (routage faux, confiance érodée).
> Constat mesuré chez Citadel : la doc d'instruction stale nuit activement, elle n'est pas neutre.

```bash
# 1. Références `/skill` dans skills + rules du projet → chacune doit exister
grep -rhoE '`/[a-z][a-z0-9_:-]+' .claude/skills/*/SKILL.md .claude/rules/*.md 2>/dev/null | sort -u
ls .claude/skills/   # + plugins installés (/plugin list) + builtins (/resume, /plugin, /clear, /init…)

# 2. Chemins .claude/... référencés par les skills → doivent exister
#    Whitelist création-différée (absents = NORMAL) : ACCESS.md, RUNBOOK.md, GLOSSARY.md,
#    STAKEHOLDERS.md, idees/archived/, specs/00X (exemples génériques)
grep -rhoE '\.claude/[a-zA-Z0-9_./-]+' .claude/skills/*/SKILL.md 2>/dev/null | sort -u \
  | while read -r p; do [ -e "$p" ] || echo "$p"; done \
  | grep -vE "ACCESS|RUNBOOK|GLOSSARY|STAKEHOLDERS|archived|00X|<" | head -10
```

- Référence vers un skill **inexistant** (ni local, ni plugin, ni builtin) → 🟠 "instruction morte : `/x` n'existe plus — corriger ou retirer"
- Chemin référencé absent (hors whitelist) → 🟠 "chemin mort dans <skill>"
- Skill maison avec placeholders `{{...}}` restants ou section vide → 🟢 "compléter ou dégraisser"

⚠️ **Exclusions du scan** (faux positifs connus, vécu E2E v0.19) : CE fichier (doc-health) —
ses exemples `/deploy-x`, `/vieux-skill`, `/mon-skill` sont illustratifs ; les blocs d'exemple
de `/scaffold` (`/skill-voisin`, `/autre`, `/nom`) ; et tout `/…` dans un bloc de code bash.
En priorité, scanner les **quote blocks « Quand ne PAS utiliser »** (grammaire fixe) et les
skills **ajoutés par le projet** — c'est là que vivent les vraies instructions mortes.

> ℹ️ Sur le **repo template**, la partie mécanique de cet audit tourne en CI (`test/test_skills.py`).
> Ici sa valeur = les **projets générés**, qui ajoutent leurs propres skills sans CI de template.

## Étape 11 — Rapport synthétique

Format type :

```markdown
# 📊 Doc Health Report — YYYY-MM-DD

## 🔴 Critique (à faire cette semaine)

- .claude/docs/HANDOFF.md > 7 jours (dernière MAJ 2026-05-15) → lancer /handoff
- 8 entries .claude/docs/lecons.md statut 🆕 new → review + promotion

## 🟠 Attention

- .claude/docs/code-map.md pas MAJ depuis le dernier refacto (commit abc123) → /codemap
- .claude/docs/ROADMAP.md ligne `[~] 002-notion-writer` en cours depuis 14j → status réel ?
- 003-export-pdf : frontmatter `status: done` mais ROADMAP encore `[~]` → resync
- skill maison `/deploy-x` référence `/vieux-skill` supprimé → instruction morte

## 🟢 Suggestions

- 5 mentions de "API_KEY" dans plan.md mais .claude/docs/ACCESS.md vide → enrichir ?
- 3 "choisi vs" dans 001/plan.md sans ADR → promouvoir en ADR ?
- 2 placeholders {{...}} non remplis (CLAUDE.md ligne 12, README.md ligne 8)
- 1 pattern auto-memory stable (« retry API en 3× ») → promouvoir en rule ou leçon ?

## ✅ Tout va bien

- .claude/docs/CHANGELOG.md à jour (dernière entry 2026-05-22)
- Pas d'ADR superseded sans archivage
- Glossary à jour
```

## Anti-patterns

- ❌ Modifier les fichiers (juste audit, pas write)
- ❌ Reporter sans priorité (toujours 🔴/🟠/🟢)
- ❌ Faux positifs (vérifier que le fichier est vraiment stale, pas juste pas modifié)
- ❌ Bloquer sur un seul check (continuer le scan même si une étape échoue)

## Note : invocation par agent doc-maintainer

Le skill `/doc-health` est l'invocation manuelle directe. L'agent `doc-maintainer` (Task tool) peut faire le même scan + proposer les diffs (vs juste rapporter). Utilise l'agent pour "scan + agir", utilise le skill pour "juste scanner". Le HANDOFF stale, lui, se traite par `/handoff` dans le fil principal (l'agent n'a pas la conversation).
