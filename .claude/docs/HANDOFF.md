# HANDOFF — 2026-09-30 03h32

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/001-socle-donnees` (repartie de `main` après la PR n°1)
**Spec en cours** : [001-socle-donnees](specs/001-socle-donnees/spec.md) (3/16 tasks, phase 1 terminée)
**Goal session** : outiller Jira et GitHub avant de reprendre la spec 001

## Status

- ✅ Jira NEO : epics NEO-1 à NEO-4 = jalons 1 à 4 ; tickets du jalon 1 NEO-5 à NEO-12 (NEO-5 fait)
- ✅ Dépôt privé kurt83340/node4jPOC relié à NEO : la clé d'un commit ou d'un titre de PR remonte
- ✅ `main` : doc de la phase 1 et README « initiative » (PR n°1) ; historique sans attribution à Claude
- ⏳ Aucun chargement ni test : la phase 2 attend l'instance Aura (NEO-6)

## Échecs tentés (à ne pas refaire)

- Normaliser les descriptions avec `\n` seul → 5 240 textes au lieu de 5 233 : remplacer aussi U+202F
- Préfixer les requêtes par `CYPHER 25` → rejeté : langue par défaut de la base (plan D7)
- Re-proposer le chargement Python ou le nommage v1 → non : ADR-0003 et ADR-0005

## Blocked on

- Action de Julien : NEO-6, instance AuraDB Free et identifiants dans Secret Manager (bloque NEO-7)

## Next (par ordre)

1. **NEO-6** (Julien) : créer l'instance, noter la vraie limite, identifiants dans Secret Manager (`jleroy-labo`)
2. **NEO-7** : ADR-0007 (secrets et services gérés, plus de `.env`), T2.1 adaptée, puis T2.2 ; commits `(NEO-7)`
3. **NEO-8** : T3.1, `verifier.sh` d'abord (rouge sur base vide), puis la phase 4

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 001-socle-donnees
Task: T2.1
Fichiers en cours: aucun
Bloqué sur: instance AuraDB Free + secret neo4j-aura-poc (NEO-6, action de Julien)
Commande de reprise: gcloud secrets versions list neo4j-aura-poc --project=jleroy-labo, puis écrire l'ADR-0007 (NEO-7)

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
