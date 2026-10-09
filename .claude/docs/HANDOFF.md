# HANDOFF — 2026-10-09 00h48

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/002-phase-4` (tirée de `main` après la PR n°9 ; porte ce handoff)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (12/33 tasks : phases 0 à 3, T7.1)
**Goal session** : phase 3 (T3.1, T3.2) en TDD, revue adverse, PR de fin de phase, NEO-17

## Status

- ✅ `banc/` : 705 tests, ruff, mypy strict, shellcheck propres ; couverture de `banc.mesures` et `banc.revue` 100 % ; aucun appel LLM
- ✅ Phase 3 fusionnée (PR n°9, merge `2f92d79`) : trace JSONL et CSV sans prose (`banc.mesures`), identifiant masqué par le lanceur (perl sur le stdout de `neo4j-mcp`), revue à l'aveugle `banc revoir` (`banc.revue`) ; NEO-17 « Terminé », risque de revue de NEO-2 relevé (~230 cas)
- ✅ Revue adverse à contexte frais : 13 constats, tous traités (plan, D4 et D10) ; 94 + 82 fautes injectées, toutes détectées ; leçon des tests d'exclusion promue en règle ([testing](../rules/testing.md))

## Échecs tentés (à ne pas refaire)

- `model_usage` de Claude Code lu comme l'usage d'un tour : il cumule la session, Q18 comptait Q2 → `usage_du_tour`
- Tests d'exclusion passés par une règle voisine (`match=` trop large, gel invalide refusé faute de pilote) → règle de test
- SHA de commit écrit en clair sous un nom en « api » dans un test → commit refusé par gitleaks ([gotcha](code-map-gotchas.md))

## Blocked on

- Rien

## Next (par ordre)

1. **Phase 4 (NEO-18)** : T4.1 cellule Agent SDK, T4.2 cellules ADK, T4.3 orchestration, avec le relevé de la revue adverse (plan, D13 : usage cumulé et `interrupt()`, `env` et session du serveur MCP sous ADK, `fin` à l'échéance, Q18 fausse d'office si Q2 échoue)
2. Avant toute campagne payante (au plus tard T5.1) : coupure automatique de l'ADR-0010, branche à part
3. T4.1 : fixer `permissionMode`, couper la socket `/tmp/cc-socks/` si possible, plafonner `CLAUDE_CODE_MAX_RETRIES` (plan, D3 et D13)
4. Mineurs : code-map à 3,3k tokens (cible < 3k, T11.2) ; pre-commit (shellcheck, Prettier, pytest) ; flag des équipes en portée user

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T4.1
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch feature/002-phase-4 && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
