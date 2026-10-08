# HANDOFF — 2026-10-08 11h45

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/002-phase-2` (tirée de `main` après la PR n°7 ; porte ce handoff)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (8/33 tasks : phases 0 et 1, T7.1)
**Goal session** : phase 1 (T1.1 à T1.3), PR de fin de phase, NEO-16

## Status

- ✅ `banc/` : 257 tests, ruff et mypy strict propres ; shellcheck propre ; aucun appel LLM, rien sur Aura
- ✅ Phase 1 fusionnée (PR n°7, merge commit `738970c`) : `questions/banc.toml` (distracteurs validés par Julien), consigne et fiche relues et validées, `questions.sh` (`$proposee`, `--dossier`, `--exemples`)
- ✅ Jira : NEO-16 « Terminé » ; NEO-2 rafraîchi (Claude par l'API, vérifications de la phase 0, crédits prépayés)
- ⏳ Sur la base plus tard : index `noms_plein_texte` et `$proposee` (T7.2), exemples de la fiche (T7.3)

## Échecs tentés (à ne pas refaire)

- Seuil de ressemblance des exemples fixé à 0,7 sans mesure : faux, des requêtes courtes sans rapport atteignent 0,80 → mesurer sur les références d'abord ([plan, D5](specs/002-agent-text-to-cypher/plan.md))
- Tokeniseur qui garde l'apostrophe dans le mot : « d'Évoli » échappait au contrôle → détacher l'élision ([gotchas](code-map-gotchas.md))

## Blocked on

- Rien

## Next (par ordre)

1. **Phase 2 (NEO-17, à passer « En cours »)** : T2.1 lecture des réponses en TDD (sections « Réponse » et « Sources », normalisation, élisions, 6 noms de Q2 validés puis échappés, voie vers `questions.sh`) ; T2.2 notation selon les modes de `banc.toml` (couverture ≥ 80 %)
2. Avant toute campagne payante (au plus tard T5.1) : coupure automatique de l'ADR-0010, branche à part
3. T4.1 : fixer `permissionMode`, couper la socket `/tmp/cc-socks/` si possible, plafonner `CLAUDE_CODE_MAX_RETRIES` (plan, D3 et D13)
4. Mineurs : code-map à 3,3k tokens (cible < 3k, T11.2) ; règle deny ([leçon](lecons.md)) ; pre-commit (shellcheck, Prettier, pytest) ; flag des équipes en portée user (mémoire globale)

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T2.1
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch feature/002-phase-2 && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
