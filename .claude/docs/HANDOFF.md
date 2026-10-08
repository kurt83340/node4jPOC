# HANDOFF — 2026-10-08 02h09

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/002-phase-1` (12 commits, poussée sur GitHub, pas encore de PR)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (5/33 tasks : T7.1, T0.1 à T0.4)
**Goal session** : reprise (doc, template 1.6.1, plugin `agent-teams`), voie pour Claude, T0.2

## Status

- ✅ `banc/` : 75 tests, ruff et mypy strict propres ; shellcheck propre ; `scripts/banc.sh acces` passe (5 clients, 0,0027 $)
- ✅ Phase 0 terminée : NEO-14 et NEO-15 « Terminé » ; NEO-16 (phase 1) « En cours »
- ✅ Claude par l'API Anthropic ([ADR-0011](adr/0011-infra-claude-par-api-anthropic.md)) : secret `anthropic-api-banc`, 20 $ de crédits sans recharge
- ✅ Template claude-Setup 1.6.1 publié et appliqué (sans conflit) ; plugin `agent-teams` 1.2.1 actif

## Échecs tentés (à ne pas refaire)

- Claude sur Vertex : quota à 0, hausse refusée d'office (mémoire globale `vertex-claude-quota`) → API Anthropic
- Saisie masquée vide (ou « jj ») à l'invite `read -rs` → secret sans version, puis conflit à la recréation ([ACCESS](ACCESS.md))

## Blocked on

- Rien

## Next (par ordre)

1. **Phase 1 (NEO-16)** : T1.1 `questions/banc.toml` en TDD ; T1.2 consigne et fiche (test de contamination, relecture de Julien) ; T1.3 `$proposee`, `--dossier`, `--exemples`
2. Avant toute campagne payante (au plus tard T5.1) : coupure automatique de l'ADR-0010, branche à part
3. T4.1 : fixer `permissionMode`, couper la socket `/tmp/cc-socks/` si possible, plafonner `CLAUDE_CODE_MAX_RETRIES` (plan, D3 et D13)
4. Mineurs : code-map à 3,3k tokens (cible < 3k, T11.2) ; règle deny ([leçon](lecons.md)) ; pre-commit (shellcheck, Prettier, pytest) ; flag des équipes en portée user (mémoire globale)

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T1.1
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch feature/002-phase-1 && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
