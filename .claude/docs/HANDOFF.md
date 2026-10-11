# HANDOFF — 2026-10-11 03h39

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/002-phase-9`, PR de la phase 9 ouverte, à fusionner après T9.3 (sur accord de Julien)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (23/33 tasks : phases 0 à 5, 7, 8, T9.1 et T9.2)
**Goal session** : pilote (phase 8), puis campagne comptée `fr-1` et sa revue (phase 9)

## Status

- ✅ Campagne `fr-1` : 3 passes, 7,60 $, aucune panne, `banc rapport --complet` complète ; scores 27,5, 27,8 et 20,7 sur 30 (claude-code, adk-claude, adk-gemini), écarts 0, 0,5 et 2,5
- ✅ Revue (T9.2) : 95 cas, décisions de Julien validées en bloc sur la pré-analyse de Claude, écart à l'ADR-0008 noté au plan (D7)
- ✅ `banc rapport` (TDD, 17 tests) ; 1 130 tests, ruff, mypy, shellcheck, Prettier, gitleaks
- ⏳ T9.3 : Console vérifiée pour le pilote (1,79 $ = calcul) ; export BigQuery encore sans le pilote le 2026-10-11 à 0 h 35

## Échecs tentés (à ne pas refaire)

- `tmux send-keys` vers une fenêtre désignée par son nom → Julien y avait relancé Claude Code : touches envoyées comme un message (vérifier `pane_current_command` avant)
- Script de mutation sans `finally` → arrêté en route, il a laissé le fichier muté : copie d'abord, motif unique vérifié, restauration dans un `finally`

## Blocked on

- T9.3 attend l'export BigQuery (Gemini : pilote 0,87 $, `fr-1` 2,94 $), quelques heures à un jour de retard

## Next (par ordre)

1. **T9.3** : coût recoupé (Console pour Claude, 4,66 $ de `fr-1` ; `/google-facture` pour Gemini), écart noté au plan (D7), puis fusion de la PR et NEO-21 au format de clôture (critères 2 et 3)
2. **Phase 6 (NEO-19)** : schéma anglais sans base (T6.1 à T6.3), puis phase 10 (NEO-23) ; NEO-22 reste ouvert pour les revues des passes anglaises et de contrôle
3. À trancher : ADR qui amende l'ADR-0008 (revue assistée) ? ; Poissirène dans la table de Q9 (écarté, eau douce) ; ADR qui précise l'ADR-0009 ? ; leçons en rules ; flag des équipes ; NEO-27 début décembre

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T9.3
Fichiers en cours: aucun
Bloqué sur: export BigQuery du pilote et de fr-1 (Gemini)
Commande de reprise: uv run ~/.claude/skills/google-facture/scripts/facture.py detail

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
