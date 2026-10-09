# HANDOFF — 2026-10-09 14h59

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/002-phase-4` (T4.1 en 2 commits, plus ce handoff)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (13/33 tasks : phases 0 à 3, T4.1, T7.1)
**Goal session** : T4.1, la cellule Claude Code (Agent SDK) isolée, vérifiée sur le vrai binaire

## Status

- ✅ `banc/` : 801 tests, ruff, mypy strict, shellcheck, gitleaks propres ; couverture de `banc.cellule` 100 %, de `banc.cellule_sdk` 99 % ; aucun appel LLM
- ✅ T4.1 : `banc.cellule` (commande JSON d'une conversation, plafonds) et `banc.cellule_sdk` (un processus à la liste blanche par conversation) ; 80 fautes injectées, toutes détectées
- ✅ Vrai Claude Code 2.1.292 relevé contre une fausse API (plan, D3 et D13), gardé en 5 tests hermétiques ; choix de Julien : instructions du serveur ôtées par le lanceur, budget de 0,50 $ par conversation compté sur le flux

## Échecs tentés (à ne pas refaire)

- `--max-budget-usd` natif → l'agent voit « USD budget: … remaining » à chaque appel : budget compté par la cellule
- Faux outil lancé en processus qui liste le HOME → il hérite de celui du poste, 7 s par test ([gotcha](code-map-gotchas.md))
- `"…_tokens": self.a + self.b` dans un test → commit refusé par gitleaks (generic-api-key) : variable intermédiaire

## Blocked on

- Rien

## Next (par ordre)

1. **T4.2 (NEO-18)** : cellules ADK sur `banc.cellule` (même commande, mêmes plafonds, budget hors du client) ; `McpToolset` avec la liste blanche en `env` et son propre groupe (gotcha `mcp` 2.3.0) ; refaire l'essai réel contre une fausse API là où c'est possible ([leçon du 2026-10-09](lecons.md))
2. **T4.3** : orchestration (groupe de processus, `scripts/transactions.sh`, relances, ligne de Q18 après l'échec de Q2 selon l'ADR-0012, alternance, `--reprendre`), puis PR de la phase 4 `(NEO-18)`
3. Avant toute campagne payante (au plus tard T5.1) : coupure automatique de l'ADR-0010, branche à part
4. À trancher et mineurs : un ADR qui précise l'ADR-0009 (plafonds invisibles de l'agent, instructions du serveur ôtées) ? ; pre-commit (shellcheck, Prettier, pytest) ; flag des équipes en portée user

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T4.2
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch feature/002-phase-4 && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
