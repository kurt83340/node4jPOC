# HANDOFF — 2026-10-07 19h45

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `main`, avec 7 fichiers de doc non commités (HANDOFF, journal, ADR-0010, ACCESS, CHANGELOG, `adr/README`, `lecons`) : à committer sur `feature/002-phase-1`, jamais sur `main`
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (4/33 tasks : T7.1, T0.1, T0.3, T0.4)
**Goal session** : phase 0 de la spec 002 (T0.1 à T0.4) ; template claude-Setup publié en 1.6.0

## Status

- ✅ Phase 0 fusionnée (PR n°5), NEO-14 « Terminé » ; `banc/` : 38 tests, ruff et mypy strict propres ; shellcheck propre
- ⏳ T0.2 (NEO-15) : `banc acces` prêt, Gemini répond depuis `eu` ; Claude en parking. Budget de 100 € avec alertes ([ADR-0010](adr/0010-infra-plafond-de-depense.md))
- ✅ Template claude-Setup 1.6.0 (tag `v1.6.0`) : `/handoff` consigne avant de réécrire, `/feature-done` relit avant de clore ; node4jPOC encore en 1.5.0

## Échecs tentés (à ne pas refaire)

- Hausse du quota Claude par `gcloud beta quotas preferences` → refusée d'office : compte non éligible (mémoire globale `vertex-claude-quota`)
- Claude Code sous HOME temporaire avec le seul `CLOUDSDK_CONFIG` → ADC introuvable : `GOOGLE_APPLICATION_CREDENTIALS` requis
- Télécharger `neo4j-mcp_1.6.0_checksums.txt` sous son nom → bloqué par la règle deny `Neo4j-*.txt` ([leçon du 2026-10-07](lecons.md))

## Blocked on

- Claude sur Vertex : quota à 0 ; Julien penche pour l'API Anthropic directe, à trancher (clé dans Secret Manager, D2, ADR)

## Next (par ordre)

1. Sur `feature/002-phase-1` : committer les 7 fichiers de doc, puis `/upgrade-template` 1.5.0 → 1.6.0 (arbre propre exigé)
2. Décisions de Julien : voie pour Claude (API Anthropic : dépense hors budget GCP, limite à poser chez Anthropic) ; durée du cache à noter dans `plan.md` (D10)
3. Coupure automatique à 100 € (ADR-0010), branche à part, avant toute campagne ; **Phase 1** (NEO-16) : `banc.toml`, consigne et fiche, `$proposee`
4. Mineurs : resserrer la règle deny ; plafonner `CLAUDE_CODE_MAX_RETRIES` (T4.1) ; pre-commit (shellcheck, Prettier, pytest) ; Julien : 5 tables sémantiques, chrono de la technique 1

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T1.1
Fichiers en cours: .claude/docs/HANDOFF.md, .claude/docs/HANDOFF-journal.md, .claude/docs/ACCESS.md, .claude/docs/CHANGELOG.md, .claude/docs/adr/README.md, .claude/docs/adr/0010-infra-plafond-de-depense.md, .claude/docs/lecons.md (non commités)
Bloqué sur: voie pour Claude (T0.2, décision de Julien)
Commande de reprise: git switch main && git pull && git switch -c feature/002-phase-1

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
