# HANDOFF — 2026-10-10 23h17

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `main`, après fusion de la [PR n°15](https://github.com/kurt83340/node4jPOC/pull/15) (phase 8, T8.1 validée par Julien)
**Spec en cours** : [002-agent-text-to-cypher](specs/002-agent-text-to-cypher/spec.md) (21/33 tasks : phases 0 à 5, 7 et 8)
**Goal session** : le pilote (T8.1) : passe non comptée, revue, coût, cache, seuils du FR/EN, gel du protocole

## Status

- ✅ Pilote : 2,51 $ pour 2,36 $ estimés (1,06 fois), 84 conversations sans panne ; revue des 27 cas faite par Claude à la demande de Julien ; scores non comptés 28,0, 26,5 et 18,5 sur 30 (Gemini : 9 échecs « tours »)
- ✅ Réglés : titres de jeux à l'extraction, journal de neo4j-mcp en `warning` ; cache 5 min, plafond de 10 appels gardé, seuils du FR/EN (plan D8) ; protocole gelé (`banc/mesures/revues.toml`)
- ✅ 1 113 tests, ruff, mypy, shellcheck, Prettier, gitleaks ; CI verte ; `banc essai-serveur` 12/12
- ⏳ Coût du pilote à recouper : Console (Claude, environ 1,79 $ le 10 octobre), export BigQuery du 11 (Gemini, 0,87 $)

## Échecs tentés (à ne pas refaire)

- `tmux send-keys` vers une fenêtre désignée par son nom → Julien y avait relancé Claude Code : touches envoyées comme un message (vérifier `pane_current_command` avant)
- Script de mutation sans `finally` → arrêté en route, il a laissé le fichier muté : copie d'abord, motif unique vérifié, restauration dans un `finally`

## Blocked on

- Rien

## Next (par ordre)

1. **Phase 9 (NEO-21, T9.1)** : 3 passes comptées (`scripts/banc.sh lancer --campagne <id> --passes 3`), sans `--cache-1h` ; plafond à proposer (pilote : 2,51 $ la passe) ; NEO-22 → En cours pour la revue
2. **T9.2 (NEO-22)** : revue humaine des « à revoir » (environ 80 cas) : pré-analyse par Claude, décision de Julien (ADR-0008)
3. **T9.3** : coût recoupé (Console, BigQuery) ; puis phase 6 (NEO-19), schéma anglais, avant la phase 10
4. À trancher : ADR qui précise l'ADR-0009 ? ; leçons du 2026-10-09 et du 2026-10-10 en rules ; flag des équipes en portée user ; NEO-27 début décembre (budget de 100 € au-delà du 2026-12-31)

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 002-agent-text-to-cypher
Task: T9.1
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch main && git pull && git switch -c feature/002-phase-9

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
