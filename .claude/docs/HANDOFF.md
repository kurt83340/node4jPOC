# HANDOFF — 2026-10-12 02h05

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/002-phase-11`, poussée, tirée de `main` après les PR n°18 et n°19
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (34/35 tasks : il reste T11.3)
**Goal session** : T9.3, phase 10 (schéma anglais sur la base, verdict du FR/EN), phase 11 jusqu'au rapport, `/doc-health`

## Status

- ✅ 1 481 tests verts ; ruff, mypy, shellcheck, Prettier propres (relancés le 2026-10-12)
- ✅ PR n°18 (T9.3 : coût de `fr-1` recoupé à moins d'un centime) et n°19 (phase 10 : `en-1` à 19,17 de moyenne contre 20,67 pour `fr-1`, pas d'effet mesurable du schéma anglais, Δ = −1,5 pour un seuil de 2,5 ; contrôle à 21,5, dans [18,5 ; 23] ; base revenue au français, prouvée) fusionnées, CI verte ; NEO-21 à NEO-23 « Terminé »
- ✅ ADR-0015 (source d'un second tour), ADR-0016 (clé Anthropic dans « Default », limite de l'organisation à 20 $ par mois) ; T11.0 à T11.2 (Q18 noté sur deux tours, rapport `banc/resultats/technique-2.md`, doc du jalon 2)
- ✅ `/doc-health` du 2026-10-12 traité avec le doc-maintainer : glossaire, code-map à 2 893 jetons, cohérence des docs, trois leçons promues en rules (`textes-valides.md`, `git-workflow.md`, `testing.md`), une écartée

## Échecs tentés (à ne pas refaire)

- Script de mutation sans `finally` → arrêté en route, il a laissé le fichier muté : copie d'abord, motif unique vérifié, restauration dans un `finally`

## Blocked on

- Recoupement de la phase 10 : l'export BigQuery des heures de 17 h et 18 h UTC (`en-1`) et de 19 h UTC (`fr-controle`), le 2026-10-11 ; toujours absent à 23 h 41 UTC (délais vus jusqu'ici : 4 h 35 à 6 h 43)
- T11.3 : l'accord de Julien pour la fusion et le tag `jalon-2`

## Next (par ordre)

1. **Recoupement** (Gemini seul) : `facture.py detail`, puis une requête `bq` par heure ; attendu (entrée, cache lu, sortie) `en-1` 2 165 493, 1 334 367 et 209 294 jetons (2,759954 $), `fr-controle` 735 717, 364 599 et 64 065 (0,901313 $) ; écart au plan (D8), au rapport (§ Coût et § Limites), dans `tasks.md`
2. **T11.3** : `/feature-done 002-agent-text-to-cypher` (ROADMAP, CHANGELOG, HANDOFF) ; cocher US1, US2 et US4 de la spec (« traces à l'appui » d'US1 à préciser : le plan ne cite que D3 et T7.4) ; clés orphelines de `db.propertyKeys()` au jalon 4 de la ROADMAP ; PR de la phase 11 (NEO-24), fusion et tag `jalon-2` sur l'accord de Julien ; puis NEO-24 au format de clôture, résultats de NEO-2 (critères 1 et 2)
3. Plus tard : outillage de revue (`tirage.py`, `page.py`, `enregistrer.py`, scratchpad de la session `aac0f55f`) à promouvoir dans `banc/` ou à refaire au jalon 3 ; `/reload-skills`, instruction morte du skill scaffold, à corriger dans le template ; scratchpad à nettoyer
4. À trancher : ADR pour les précisions de l'ADR-0009 restées au plan 002 (plafonds invisibles, instructions ôtées, garde-fou, reprise) ? ; flag des équipes en portée user ; NEO-27 début décembre

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T11.3
Fichiers en cours: aucun
Bloqué sur: export BigQuery de en-1 et fr-controle, accord de Julien pour la fusion et le tag
Commande de reprise: uv run ~/.claude/skills/google-facture/scripts/facture.py detail

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
