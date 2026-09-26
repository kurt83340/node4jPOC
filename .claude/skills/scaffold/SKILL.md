---
name: scaffold
description: Crée un skill, un agent ou un pipeline /feature conforme aux conventions du template (frontmatter, SendMessage pour les teammates, grammaire des pipelines, maillons existants) et le référence dans l'inventaire (skills/README.md, agents/README.md). Vérifie d'abord qu'un composant existant ne couvre pas déjà le besoin - /scaffold skill|agent|pipeline "<nom>".
allowed-tools: Read, Write, Edit, Grep, Glob, AskUserQuestion, Bash(ls:*), Bash(grep:*), Bash(find:*)
disable-model-invocation: false
---

# /scaffold — créer un composant conforme (skill · agent · pipeline)

> **Quand ne PAS utiliser** : une feature applicative → `/spec` (specs, pas composants template) ·
> installer le template entier → `/init-from-template` ou `/adopt-template`.
> **Réversibilité** : 🟢 crée 1 fichier composant + 1 ligne d'inventaire —
> undo : supprimer le fichier + retirer la ligne.

Les conventions du template sont gardées par la CI (inventaire, SendMessage…) — CE skill les
rend **impossibles à oublier** : il les encode à la création. Tu ne retiens plus les règles.

**Arguments** : `/scaffold skill "<nom>"` · `/scaffold agent "<nom>"` · `/scaffold pipeline "<nom>"`

## Étape 0 — Anti-doublon + contexte (toujours)

1. **« Un composant existant couvre-t-il déjà ce besoin ? »** — scanne `.claude/skills/`,
   `.claude/agents/`, `.claude/skills/feature/pipelines/`, plugins installés (`/plugin list`).
   Si oui → le montrer et proposer d'**étendre** plutôt que créer (un doublon ment).
2. Détecte le contexte : **repo template** (`.claude-plugin/marketplace.json` présent) ou
   **projet généré** → adapte les rappels de fin de run.

## Mode `skill` — `/scaffold skill "<nom>"`

1. Questions (AskUserQuestion) : rôle en 1 phrase (→ la `description`, qui pilote
   l'auto-invocation : « À invoquer quand… ») ; **action sensible** (deploy, push prod,
   suppression) ? → `disable-model-invocation: true` (slash-only) ; outils nécessaires
   (`allowed-tools` **minimal** — pas de Bash(*) par confort).
2. Crée `.claude/skills/<nom>/SKILL.md` — ⚠️ `name:` = **nom du dossier** (c'est le dossier
   qui fait le `/nom`), dossier À PLAT (1 niveau).
3. **Bloc anti-mauvais-routage (exigé par `test/test_skills.py` sur le repo template)** — sous
   le H1, un quote de 2 entrées :
   - `> **Quand ne PAS utiliser** : <cas> → \`/skill-voisin\` · <cas> → \`/autre\`.` — nomme
     **1-2 skills voisins existants** (c'est ce qui évite le mauvais routage, pas la description) ;
   - `> **Réversibilité** : 🟢|🟠|🔴 <ce que ça écrit> — undo : <commande littérale>.`
4. **Référence (exigé par la CI)** : ajoute la ligne `- \`/<nom>\` — <1 ligne>` dans l'inventaire
   de [`.claude/skills/README.md`](../README.md), dans la section adaptée.
5. Rappels : fichiers de support possibles (`templates/`, `scripts/`) ; pris en compte à chaud
   (ou `/reload-skills`) ; **sur le repo template**, un scénario benchmark
   `test/benchmarks/<nom>/<cas>.md` est bienvenu (format : `test/benchmarks/README.md`).

## Mode `agent` — `/scaffold agent "<nom>"`

1. Questions : **teammate** (session visible, écrit/code, rapporte au lead) ou **subagent pur**
   (one-shot lecture/analyse, résultat = retour du Task tool) ? · touche à des **libs/API
   externes** ? · doit **invoquer des skills** ?
2. Compose le `tools:` minimal, avec les règles du template :
   - teammate → **`SendMessage` OBLIGATOIRE** (sinon rapport perdu + zombie — la CI le refuse)
   - libs externes → `mcp__context7` (rule `doc-lookup`)
   - invoque des skills → `Skill`
3. Crée `.claude/agents/<nom>.md` — frontmatter `name`/`description`/`tools`/`model: inherit`,
   body = **sa spécialité uniquement** (le protocole d'équipe vit dans la rule `agent-teams.md` du plugin `agent-teams`,
   ne pas dupliquer).
4. **Référence** : ligne dans la table de [`.claude/agents/README.md`](../../agents/README.md).
5. Rappel : rôle d'**exécution d'équipe** générique ? → il a peut-être sa place dans le plugin
   `agent-teams` plutôt que dans le projet.

## Mode `pipeline` — `/scaffold pipeline "<nom>"` (2 façons, demander d'abord)

**A. Dirigé — tu dictes.** Tu donnes l'ordre des étapes et, pour chacune, le maillon
(skill `/x`, subagent `y`, outil MCP, commande). Le skill :
- **vérifie que CHAQUE maillon existe** (skills cœur, plugins installés, agents, MCP
  connectés) — maillon absent = le dire + proposer l'alternative (install du plugin, variante) ;
- complète chaque étape d'un **critère de sortie vérifiable** (proposé, tu ajustes) ;
- impose **Persister** en dernière étape.

**B. Proposé — il conçoit.** Tu décris la tâche récurrente (1-3 phrases). Le skill :
- inventorie les maillons **disponibles ici** (skills, agents, plugins, MCP) ;
- mappe sur la **grammaire** `Planifier → Exécuter → Tester → Review adverse → Vérifier →
  Persister` en instanciant chaque étape avec les maillons les plus adaptés (une étape peut
  changer de nature selon le contexte — cf. pipeline `n8n` vs `tdd`) ;
- propose LE pipeline (+ 1 variante seulement si un vrai trade-off existe), **justification
  par étape** ; tu ajustes, il fige.

Dans les deux cas, à la fin :
- **validation structurelle** : maillons existants, un critère par étape, Persister final ;
- crée `.claude/skills/feature/pipelines/<nom>.md` (format du SKILL `/feature`) —
  **auto-découvert** par `/feature`, rien d'autre à câbler ;
- propose d'ajouter la ligne dans la section « 🔁 Pipelines » de `.claude/CLAUDE.md` (visibilité).

## Fin de run — rappels selon le contexte

- **Repo template** : bump le compte « N skills cœur » dans `.claude/skills/README.md` (SEUL endroit
  chiffré — la CI vérifie compte = dossiers) + entrée CHANGELOG + bump `.claude/template-version` ;
  composant dans un plugin maison → **bump la `version` de son `plugin.json`** (sinon les projets
  ne voient pas la MAJ) ; overkill pour un 1-shot → l'ajouter à `SCRIPT_JETABLE` (cleanup-for-type.py).
- **Projet généré** : rien de plus — le référencement est fait, il n'y a pas de CI d'inventaire.

## Anti-patterns

- ❌ Créer sans avoir vérifié l'existant (Étape 0 n'est pas optionnelle)
- ❌ Agent teammate sans `SendMessage` · pipeline sans Persister · maillon inventé
- ❌ Auto-éditer les grosses tables de `template-maintenance.md` (rappeler, n'écrire que l'exigé)
- ❌ `allowed-tools` par confort (chaque outil accordé = de la surface en plus)
