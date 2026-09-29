# HANDOFF — 2026-09-29 02h02

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/001-socle-donnees`
**Spec en cours** : [001-socle-donnees](specs/001-socle-donnees/spec.md) (3/16 tasks, phase 1 terminée)
**Goal session** : audit doc-health, puis phase 1 de la spec 001 (questions, modèle, outillage)

## Status

- ✅ Audit doc-health traité (PRD et plan macro en renvois, leçon classée, `workflows/` retiré)
- ✅ T1.1 : 30 questions de référence en 6 catégories ([questions/README.md](../../questions/README.md))
- ✅ T1.2 : modèle v2 validé après recherche (ADR-0005) ; T1.3 : Java 21 et `cypher-shell` 2026.09.0
- ⏳ Aucun chargement ni test : la phase 2 attend l'instance Aura

## Échecs tentés (à ne pas refaire)

- Normaliser les descriptions avec `\n` seul → 5 240 textes au lieu de 5 233 : remplacer aussi U+202F
- Préfixer les requêtes par `CYPHER 25` → rejeté : langue par défaut de la base (plan D7)
- Re-proposer le chargement Python ou le nommage v1 (`Espece`, snake_case) → non : ADR-0003 et ADR-0005

## Blocked on

- Actions de Julien : instance AuraDB Free et `.env` à la racine (bloquent T2.1) ; projet Google Cloud avec facturation (avant le jalon 2)

## Next (par ordre)

1. **T2.1** : `.env.example`, `ACCESS.md`, protection de `Neo4j-*.txt`, `scripts/charger.sh --ping` ; noter la vraie limite
2. **T2.2** : go/no-go (LOAD CSV depuis GitHub, multilignes, gros fichiers, `MATCH (t:Type)`, Cypher 25 par défaut)
3. **T3.1** : `verifier.sh` d'abord (rouge sur base vide), puis la phase 4

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 001-socle-donnees
Task: T2.1
Fichiers en cours: aucun
Bloqué sur: instance AuraDB Free + .env (action de Julien)
Commande de reprise: test -f .env, puis démarrer T2.1 selon .claude/docs/specs/001-socle-donnees/tasks.md

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
