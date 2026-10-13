# HANDOFF — 2026-10-13 21h02

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `main` (phases 1 et 2 fusionnées : PR n°22 et n°23 ; ce handoff, par sa propre PR)
**Spec en cours** : [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) (2/35 tasks)
**Goal session** : phases 1 et 2 du jalon 3 (contre-épreuve dans le banc, gels par jalon, clé Anthropic)

## Status

- ✅ Phase 1 (T1.1, PR n°22) : `banc contre-epreuve` (tirage, `--accord`, `--enregistrer`), 60 tests, 52 mutations détectées ; tirages d'`en-1` et de `fr-controle` refaits à l'identique
- ✅ Phase 2 (T2.1, PR n°23) : `[[jalon]]` (gel, pilote) dans `revues.toml`, réutilisation dès le premier gel, jamais un pilote ; banc 1 555 tests, CI verte ; NEO-28 « Terminé » (relu par Julien)
- ⏳ T2.2 (NEO-29 « À faire ») : clé Anthropic reportée, Julien la change cette semaine (l'actuelle expire le 2026-11-07) ; sa propre PR
- ⚠️ Légende « Source » de la page de contre-épreuve : règle de la technique 2, à compléter avec l'ADR-0018 avant la revue de `g-1` (T16.1)

## Échecs tentés (à ne pas refaire)

- Mutation sans `finally` → fichier laissé muté : copie d'abord, motif unique, restauration dans un `finally` (`logs/outils/mutations/mutations.py`)
- Script de vérification lancé par `uv run --directory banc` avec un chemin relatif → fichiers écrits dans `banc/` : chemins absolus vers le scratchpad
- Toutes les PR fusionnées avant le `/handoff` → une PR de plus pour lui : le faire sur la branche de la dernière phase, avant sa fusion

## Blocked on

- Rien pour la phase 3 ; T2.2 attend la nouvelle clé de Julien (avant le pilote, phase 14)

## Next (par ordre)

1. **Phase 3, T3.1** (NEO-30 « En cours » dès le début) : section `embeddings` de `verifier.sh` et de `90-verification.cypher`, vérification d'abord, branche `feature/003-phase-3`
2. **T3.2 et T3.3** : rôle `predictionVertex` pour `aura-genai` (IAM, annoncé), jeton par `commun.sh` jamais en argument ; `charger.sh --langue`/`--explain` et l'index vectoriel ; RUNBOOK
3. **T2.2** dès la clé de Julien : dépôt par le presse-papier (pipe, sans affichage) ou sa saisie masquée ; `banc.sh acces` (~0,003 $, feu vert)

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 003-graphrag-descriptions
Task: T3.1
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch main && git pull && git switch -c feature/003-phase-3

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
