---
name: codemap
description: Met à jour .claude/docs/code-map.md — la vue macro (sous-systèmes), les règles de couplage et les gotchas du projet. NE génère PAS de description fichier-par-fichier (Claude la retrouve seul via grep ; ça drifterait). Détecte aussi les violations de couplage par grep des imports. À invoquer après un refacto qui change le découpage ou les contraintes d'architecture.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(find:*), Bash(tree:*), Bash(ls:*)
disable-model-invocation: false
---

# /codemap — Met à jour .claude/docs/code-map.md

> **Quand ne PAS utiliser** : audit doc complet (fraîcheur, ADRs, leçons…) → `/doc-health` ·
> documenter le rôle fichier-par-fichier → personne (déductible, ça drifte).
> **Réversibilité** : 🟢 réécrit `code-map.md` (+ `code-map-gotchas.md`, diff présenté avant) —
> undo : `git checkout -- .claude/docs/code-map.md .claude/docs/code-map-gotchas.md`.

Ton rôle : tenir à jour la partie **non-déductible** du code (vue macro, règles de
couplage, intention, gotchas) et **détecter les violations de couplage**.

> ⚠️ Principe directeur ([best-practices Anthropic](https://code.claude.com/docs/en/best-practices)) :
> on ne re-décrit PAS la structure fichier-par-fichier (rôle, « dépend de X », tests).
> Claude la retrouve seul (agentic search), et ça pourrit immédiatement quand le code change.
> Ce skill ne produit QUE ce que Claude ne peut pas inférer.

## Étape 1 — Découvrir le découpage macro

```bash
find . -type d -not -path "*/node_modules/*" -not -path "*/.venv/*" \
  -not -path "*/.git/*" -not -path "*/.claude/*" -maxdepth 3
```

→ Identifier les **sous-systèmes** (pas les fichiers) : qui parle à qui, dans quel sens.

## Étape 2 — Extraire le graphe d'imports (pour DÉTECTER les violations, pas pour le documenter)

```bash
# Python
grep -rE "^(from|import) " src/ --include="*.py"
# TS/JS
grep -rE "^(import|require)" src/ --include="*.ts"
```

Le graphe sert **uniquement** à vérifier les règles de couplage (étape 4).
On ne le recopie pas dans le fichier (déductible + périssable).

## Étape 3 — Mettre à jour les sections non-déductibles

Dans `.claude/docs/code-map.md`, mettre à jour / proposer :
- **Vue d'ensemble macro** : sous-systèmes + sens des flux (1 ligne chacun)
- **Règles de couplage** : les `❌ A ne doit jamais importer B` et le sens des dépendances
- **Intention & décisions locales** : le POURQUOI du découpage, les patterns imposés (avec pointers `fichier:ligne`)
- **Gotchas** : pièges non évidents découverts → dans **`code-map-gotchas.md`** (v1.4, non auto-chargé),
  chaque entrée **citant en backticks le chemin/fichier/dossier** qu'elle concerne (c'est ce que le hook
  utilise pour n'injecter que les gotchas du fichier édité) ; transversal → § Globaux (max 5 lignes)

❌ NE PAS créer de section « Fichier par fichier » ni de listes « Dépend de » / « Tests ».

## Étape 4 — Détecter les violations de couplage (la vraie valeur ajoutée)

Croiser le graphe d'imports (étape 2) avec les règles de couplage existantes :

```
⚠️ VIOLATION COUPLAGE détectée :
- src/sap_connector/client.py importe notion_writer.exceptions
- Règle : « sap_connector ne doit JAMAIS importer notion_writer »
→ Refacto, OU mettre à jour la règle si le couplage est volontaire
```

## Étape 5 — Présenter le diff (ne jamais écrire sans validation)

```
📝 Diff .claude/docs/code-map.md :

~ Règles de couplage : + « les modules feuilles n'importent pas l'orchestrateur »
+ Gotcha : src/notion_writer/client.py:88 — l'API renvoie 200 même en erreur

OK pour écrire ?
```

## Anti-patterns

- ❌ Gonfler `code-map.md` (auto-chargé à chaque session) : budget **< 3k tokens** — gotchas et
  historique vont dans `code-map-gotchas.md` ; § « Quand mettre à jour » reste à 3 lignes

- ❌ Re-générer une carte fichier-par-fichier (rôle/dépendances/tests) — déductible, drift garanti, c'est ce qu'Anthropic dit d'exclure
- ❌ Recopier la liste des imports dans le fichier (le graphe sert à détecter les violations, pas à être archivé)
- ❌ Écrire sans que le user valide les « intentions » et « gotchas » (faux positifs)
- ✅ Préférer des pointers `chemin:ligne` aux copies de code
