# HANDOFF — 2026-09-30 16h29

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/001-socle-donnees` (poussée, à jour avec GitHub)
**Spec en cours** : [001-socle-donnees](specs/001-socle-donnees/spec.md) (6/16 tasks, phase 3 terminée)
**Goal session** : NEO-13 (job de réveil d'Aura), puis NEO-8 (T3.1, vérification d'abord)

## Status

- ✅ NEO-13 : job `reveil-aura` déployé (Cloud Run et Scheduler, `europe-west9`, chaque jour à 9 h) ; exécution manuelle, lancement par Scheduler et e-mail sur échec provoqué vérifiés ([RUNBOOK](RUNBOOK.md)). Reste « En cours » jusqu'à une période creuse de 72 h
- ✅ NEO-8 (Terminé) : `scripts/verifier.sh` rend 1 sur base vide (31 écarts sur 33) ; `charger.sh --purge` essayée ; fonctions partagées dans `scripts/commun.sh`
- ✅ `infra/reveil-aura` : 19 tests, ruff, mypy strict ; `shellcheck` propre sur `scripts/`
- ⏳ Base toujours vide. `Bash(rm:*)` passe de `deny` à `ask` ; PR du template claude-Setup en cours (hors projet)

## Échecs tentés (à ne pas refaire)

- Re-proposer le chargement Python ou le nommage v1 → non : ADR-0003 et ADR-0005
- Normaliser les descriptions avec `\n` seul → 5 240 textes au lieu de 5 233 : remplacer aussi U+202F
- `RETURN` qui mêle constantes et agrégat → aucune ligne sur base vide : agréger dans un `WITH` sans clé

## Blocked on

- Rien

## Next (par ordre)

1. **NEO-9, phase 4** : T4.1 `cypher/00-contraintes.cypher`, puis types, Pokémon, formes et talents, chacun validé par `verifier.sh --section` ; trancher en T4.5 et T5.1 les noms en double (18 attaques Z, « Osmose Équine »), que `verifier.sh` attend pour l'instant
2. NEO-13 : « Terminé » après une période creuse de 72 h, si l'instance est « Running » ; corriger alors le commentaire Jira qui dit « samedi »
3. Relire et fusionner la PR du template (`rm` en `ask`)

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 001-socle-donnees
Task: T4.1 (NEO-9)
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: scripts/charger.sh --ping, puis scripts/verifier.sh --section contraintes (rouge), puis écrire cypher/00-contraintes.cypher

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
