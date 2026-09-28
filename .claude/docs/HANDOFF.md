# HANDOFF — 2026-09-28 21h05

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/001-socle-donnees`
**Spec en cours** : [001-socle-donnees](specs/001-socle-donnees/spec.md) (0/16 tasks, plan validé)
**Goal session** : cadrer le POC et planifier le jalon 1 (aucun code)

## Status

- ✅ Cadrage : brief archivé, pivot « environnement cible Google Cloud », ADR-0001 à 0004 acceptés
- ✅ Spec 001 : research (données mesurées au commit PokéAPI `168b1e8`), plan revu par `reviewer`, 16 tâches
- ⏳ Aucun code, aucun test : la phase 1 n'a pas commencé

## Échecs tentés (à ne pas refaire)

- Normaliser les descriptions avec `\n` seul → 5 240 textes au lieu de 5 233 : remplacer aussi U+202F
- Préfixer les requêtes par `CYPHER 25` → rejeté : régler la langue par défaut de la base (plan D7)
- Re-proposer le chargement Python en deux étages → non : Julien a choisi le Cypher pur (ADR-0003)

## Blocked on

- Actions de Julien : instance AuraDB Free et `.env` (bloquent la phase 2, pas la phase 1) ; projet Google Cloud avec facturation (avant le jalon 2)

## Next (par ordre)

1. **T1.1** : définir avec Julien les 10 questions de référence (3 déjà dans le cadrage)
2. **T1.2** : matrice questions → propriétés, modèle documenté dans `ARCHITECTURE.md`
3. **T1.3** : installer Java 21 et `cypher-shell` 2026.09.0 (`.deb` officiel, via `apt`)
4. **T2.1** : dès que l'instance et `.env` existent

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 001-socle-donnees
Task: T1.1
Fichiers en cours: aucun
Bloqué sur: rien pour la phase 1 ; instance AuraDB Free + .env pour la phase 2
Commande de reprise: lire .claude/docs/specs/001-socle-donnees/tasks.md puis démarrer T1.1 avec Julien

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
