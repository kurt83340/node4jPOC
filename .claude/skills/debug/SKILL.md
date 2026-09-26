---
name: debug
description: Pipeline de debugging méthodique — capturer le symptôme exact (verbatim), REPRODUIRE avant de corriger (test rouge minimal), explorer (explore-code + git log + leçons), hypothèses discriminées par instrumentation, fix minimal, le test de repro reste dans la suite, leçon capturée. À invoquer sur un bug non trivial - /debug "<symptôme>".
allowed-tools: Read, Write, Edit, Grep, Glob, Agent, Skill, mcp__context7, Bash(git log:*), Bash(git diff:*), Bash(git status), Bash(pytest:*), Bash(npm test:*), Bash(ruff:*), Bash(grep:*), Bash(find:*)
disable-model-invocation: false
---

# /debug — Pipeline de debugging (reproduire → comprendre → corriger → pérenniser)

> **Quand ne PAS utiliser** : bug trivial reproduit en une ligne → fix direct + CHANGELOG ·
> nouvelle capacité à construire → `/feature` · re-planifier une approche → `/conception`.
> **Réversibilité** : 🟠 écrit un fix minimal + un test de repro pérennisé — undo : git ;
> le test rouge archivé reste la preuve du bug.

Le « template debugging » du projet — symétrique de `/conception` pour les bugs.
**Règle d'or : pas de repro = pas de fix.**

## Étape 0 — Capturer le symptôme (verbatim)

- Quoi : commande/action exacte, attendu vs obtenu — messages d'erreur **VERBATIM**, jamais paraphrasés.
- Depuis quand : dernier état connu-bon (commit/date) si identifiable.
- Note-le en tête de session : il finira dans la leçon (Étape 6).

## Étape 1 — REPRODUIRE (test rouge minimal)

- Écris le test qui échoue (ou le script de repro minimal) **AVANT toute correction**.
- Pas reproductible ? On n'avance pas : réduis (données, env, versions) jusqu'à isoler les
  conditions. Un bug non reproductible est un bug non compris.
- Délégable à `tester` (subagent, ou teammate visible) si la repro demande du volume.

## Étape 2 — Explorer (contexte propre)

En parallèle (subagents) :

- `explore-code` sur la zone suspecte → chemins:lignes, couplages, gotchas code-map ;
- `git log` / `git diff` sur la fenêtre depuis le connu-bon → qu'est-ce qui a **changé** ? ;
- `explore-memoire` → ce piège a-t-il déjà été payé ? (`lecons.md` a peut-être la réponse) ;
- `explore-docs` (si une **lib/API externe** est en jeu) → doc officielle À JOUR — context7 →
  MCP docs → web (rule [doc-lookup](../../rules/doc-lookup.md)) : le « bug » est parfois un
  changement d'API documenté ou un comportement de version connu.

## Étape 3 — Hypothèses discriminées (pas de fix au pif)

- 2-3 hypothèses classées par probabilité, avec pour CHACUNE : « quelle observation la
  confirmerait / l'éliminerait ? » → instrumente (log ciblé, assert, bisect) et tranche.
- ❌ Interdit : « essayons ça pour voir » sans prédiction observable.

## Étape 4 — Fix minimal

- Le fix corrige la **cause**, pas le symptôme — et rien d'autre : pas de refacto
  opportuniste dans le même geste (le refacto est un geste séparé, après le vert).

## Étape 5 — Vérifier

- Test de repro : rouge → vert. Suite complète : verte (pas de régression ailleurs).

## Étape 6 — Pérenniser (le « n'oublie rien »)

- Le test de repro **RESTE** dans la suite — c'est le vaccin.
- Piège non-évident ou > 30 min perdues → `/lecon <scope> "<titre>"` (symptôme verbatim + cause + fix).
- Effet de bord / piège lié à un fichier → gotcha dans `code-map-gotchas.md` (1 bullet citant le
  fichier en backticks — injecté par le hook quand on le réédite) ; règle de couplage → `code-map.md`.
- User-facing → entry CHANGELOG (`### Fixed`).

## Anti-patterns

- ❌ Corriger sans avoir reproduit (tu corriges peut-être un AUTRE bug)
- ❌ Fix + refacto dans le même geste (impossible d'attribuer une régression)
- ❌ Supprimer/ignorer le test de repro après coup
- ❌ « Ça remarche » sans savoir pourquoi (le bug reviendra — comprendre AVANT de fermer)
- ❌ Paraphraser le message d'erreur (verbatim ou rien)
