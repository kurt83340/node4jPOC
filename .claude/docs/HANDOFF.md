# HANDOFF — 2026-09-30 13h01

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/001-socle-donnees`
**Spec en cours** : [001-socle-donnees](specs/001-socle-donnees/spec.md) (5/16 tasks, phase 2 terminée)
**Goal session** : débloquer NEO-6 (instance Aura), puis NEO-7 (ADR-0007, T2.1, T2.2)

## Status

- ✅ NEO-6 : instance AuraDB Free (GCP europe-west1, 200 000 nœuds et 400 000 relations au plus), identifiants dans le secret `neo4j-aura-poc` ([ACCESS](ACCESS.md))
- ✅ NEO-7 : ADR-0007 (Secret Manager, plus de `.env` ni de repli Docker) ; `charger.sh --go-no-go` GO (6 contrôles en lecture seule, `shellcheck` propre, aucune fuite même sous `bash -x`)
- ⏳ Base vide. L'instance se met en pause après 72 h sans activité : si `charger.sh --ping` renvoie 2, la relancer depuis la console

## Échecs tentés (à ne pas refaire)

- Normaliser les descriptions avec `\n` seul → 5 240 textes au lieu de 5 233 : remplacer aussi U+202F
- Préfixer les requêtes par `CYPHER 25` → inutile : la base est déjà en Cypher 25 par défaut (D7)
- Re-proposer le chargement Python ou le nommage v1 → non : ADR-0003 et ADR-0005
- Mesurer une durée avec `EPOCHREALTIME` → négative sous WSL2 (recul d'horloge) : lire `/proc/uptime`

## Blocked on

- Rien

## Next (par ordre)

1. **NEO-8, T3.1** : `cypher/90-verification.cypher` et `scripts/verifier.sh` (codes 0 / 1 / 2), rouge sur base vide ; `charger.sh --purge` ; NEO-8 En cours, commits `(NEO-8)`
2. **NEO-9, phase 4** : contraintes, types, Pokémon, formes, talents, chacun validé par `verifier.sh --section`
3. Idée à mûrir : mises à jour automatiques des données PokéAPI, avec alerting ([idée](idees/2026-09-30-mises-a-jour-des-donnees.md))

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 001-socle-donnees
Task: T3.1
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: scripts/charger.sh --ping, puis écrire scripts/verifier.sh (T3.1, NEO-8)

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
