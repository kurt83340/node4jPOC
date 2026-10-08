# HANDOFF — 2026-10-08 17h23

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/002-phase-3` (tirée de `main` après la PR n°8 ; porte ce handoff)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (10/33 tasks : phases 0 à 2, T7.1)
**Goal session** : phase 2 (T2.1, T2.2) en TDD, PR de fin de phase, NEO-17

## Status

- ✅ `banc/` : 501 tests, ruff et mypy strict propres ; shellcheck propre ; couverture de `banc.notation` 99,7 % ; aucun appel LLM
- ✅ Phase 2 fusionnée (PR n°8, merge commit `98480dc`) : `banc.lecture`, `banc.notation`, `banc.trace` (contrat minimal d'un tour), liste des 1 025 espèces tirée de la base (`--verifier` 28/28), `questions.sh --controle` ; NEO-17 « En cours » (couvre aussi la phase 3)
- ✅ Revue adverse à contexte frais : 12 constats (dont des « juste » à tort), tous corrigés ; Q27 et Q28 passées en revue systématique (choix de Julien, plan D4)

## Échecs tentés (à ne pas refaire)

- Tolérance de Q8 vérifiée position par position : des glissements cumulés sortaient justes → échanges entre espèces proches seulement ([plan, D4](specs/002-agent-text-to-cypher/plan.md))
- Juger une explication par la présence d'un mot (« Électrik » pour le signalement de Q28) → revue humaine
- Tests d'exclusion passés pour une autre raison que la règle visée → les mutations les ont trouvés ([leçon](lecons.md))

## Blocked on

- Rien

## Next (par ordre)

1. **Phase 3 (NEO-17)** : T3.1 trace JSONL autour de `banc/trace.py` (sans en changer le sens), masquage, CSV sans prose (note, motifs, source, introspections), coût par modèle ; T3.2 revue à l'aveugle (« à revoir », sources « à revoir », Q10 et Q27 à Q30) ; à la clôture de NEO-17, remonter dans NEO-2 la revue relevée d'une trentaine de cas
2. Avant toute campagne payante (au plus tard T5.1) : coupure automatique de l'ADR-0010, branche à part
3. T4.1 : fixer `permissionMode`, couper la socket `/tmp/cc-socks/` si possible, plafonner `CLAUDE_CODE_MAX_RETRIES` (plan, D3 et D13)
4. Mineurs : code-map à 3,3k tokens (cible < 3k, T11.2) ; 2 leçons 🆕 à décider (règle deny ; tests d'exclusion → rule testing ?) ; pre-commit (shellcheck, Prettier, pytest) ; flag des équipes en portée user

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T3.1
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch feature/002-phase-3 && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
