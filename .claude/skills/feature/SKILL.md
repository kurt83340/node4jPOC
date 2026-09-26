---
name: feature
description: Déroule une feature de bout en bout en enchaînant les skills existants (spec → conception → code → tests → review adverse → vérif → feature-done) selon un pipeline nommé (standard, tdd, n8n ou custom de pipelines/), avec validation utilisateur entre chaque étape - /feature "<titre>" [pipeline].
allowed-tools: Read, Write, Edit, Grep, Glob, Agent, Skill, AskUserQuestion, Bash(ls:*), Bash(git status), Bash(git log:*), Bash(git diff:*), Bash(pytest:*), Bash(npm test:*)
disable-model-invocation: false
---

# /feature — dérouler un pipeline complet

> **Quand ne PAS utiliser** : un bug → `/debug` · planifier sans exécuter → `/spec` + `/conception` ·
> feature déjà codée à livrer → `/feature-done`.
> **Réversibilité** : 🟠 orchestre code + docs sur plusieurs maillons — gate utilisateur entre
> chaque étape ; undo par étape via git (rien n'est poussé sans validation).

Une commande = toute la chaîne. Ce skill n'implémente RIEN lui-même : il **enchaîne les
maillons existants** (source unique — `/spec`, `/conception`, `/agent-teams:team`,
`reviewer`, `/feature-done`…) et tient le fil entre eux. Chaque étape se termine par un
**gate** : tu valides, tu ajustes, ou tu t'arrêtes proprement.

**Arguments** : `/feature "<titre>"` (pipeline auto/demandé) · `/feature "<titre>" tdd` (explicite)

## Étape 0 — Choisir le pipeline

1. Liste les pipelines disponibles : `ls .claude/skills/feature/pipelines/*.md`
   (**1 pipeline = 1 fichier déposable** — la liste n'est jamais en dur ici).
2. Choix, dans l'ordre de priorité :
   - **argument explicite** (`/feature "<titre>" tdd`) ;
   - la spec existe déjà et `plan.md § Décisions` note un mode d'exécution (TDD/SDD,
     arrêté par `/conception` étape 4) → **le respecter** ;
   - sinon **AskUserQuestion** avec la liste trouvée (défaut : `standard`).
3. Lis le fichier pipeline retenu : c'est TA feuille de route. Si une étape référence un
   maillon absent (ex. plugin `agent-teams` non installé) → le dire, proposer l'install
   ou la variante solo — jamais d'échec silencieux.

## Étapes 1..N — dérouler la feuille de route

Pour chaque étape du fichier pipeline :

1. **Annonce** (1 ligne) : ce qu'on fait + le critère de sortie.
2. **Exécute** via le maillon indiqué (Skill / subagent / commande) — JAMAIS de
   réimplémentation locale de ce qu'un skill fait déjà.
3. **Vérifie le critère de sortie**, puis **gate** : AskUserQuestion
   « ✅ continuer / 🔧 ajuster cette étape / 🛑 stop ».

**Stop = propre** : les artefacts produits restent (spec/plan/code/tests). Relancer
`/feature "<titre>"` plus tard → détecte l'avancement (spec existante, tasks cochées,
ROADMAP) et propose de **reprendre à l'étape suivante**, pas de repartir de zéro.

## Ajouter un pipeline (au fil de l'eau)

Dépose `.claude/skills/feature/pipelines/<nom>.md` — il apparaît à l'Étape 0 sans rien
recâbler. Format :

```markdown
# <nom> — <une ligne : QUAND utiliser ce pipeline>

> <la séquence en flèches, lisible d'un coup d'œil>

1. **<Étape>** — action : <maillon existant : skill `/x`, subagent `y`, ou commande> — sortie : <critère VÉRIFIABLE>
2. ...
N. **Persister** — action : `/feature-done` (+ `/lecon` si pièges) — sortie : mémoire à jour
```

Règles : chaque action pointe un maillon **existant** ; chaque étape a un **critère de
sortie vérifiable** ; l'étape **Persister est obligatoire en dernière position** — un
pipeline qui n'écrit pas sa mémoire n'a pas eu lieu.

## Anti-patterns

- ❌ Réimplémenter un maillon ici (le pipeline ORCHESTRE, les skills FONT)
- ❌ Sauter un gate (l'utilisateur tranche entre les étapes)
- ❌ Pipeline sans étape Persister finale
- ❌ Coder pendant l'étape Planifier (le plan d'abord — `/conception` l'interdit déjà)
