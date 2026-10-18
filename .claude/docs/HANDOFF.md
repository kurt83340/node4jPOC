# HANDOFF — 2026-10-18 22h29

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/003-phase-13` (PR n°38 ; fusion après ce handoff, feu vert de Julien)
**Spec en cours** : [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) (22/35 tasks)
**Goal session** : phases 11 à 13 du jalon 3 (NEO-32) : seconds tours, isolement, source citée, orchestration, contrôles à la création, répétition générale

## Status

- ✅ Phases 11 et 12 fusionnées (PR n°36, n°37) : seconds tours, liste blanche, source citée (descriptions réunies ; requêtes et descriptions jugées à part, choix de Julien) ; cellules enregistrées, `campagne.json` format 4, `encodages.json`
- ✅ Phase 13 (PR n°38) : index et preuve de symétrie vérifiés à la création ; faux serveur à recherche fixe et neutre ; `repetition-3` (Q19, Q2, Q18, choix de Julien) : 0,044 $, rien n'a touché Aura, délai de `graphrag-gemini` éprouvé ; `banc rapport` corrigé ; banc 1 837 tests verts
- ⏳ NEO-32 : clôture des phases 11 à 13 montrée à Julien, publiée, puis « Terminé » après sa relecture (`--relu`) ; NEO-3 : coût de la répétition ajouté

## Échecs tentés (à ne pas refaire)

- `EXPLAIN` passé par `read-cypher` : il le préfixe déjà (neo4j-mcp v1.6.0) → contrôle sur un vecteur factice
- Attendus de test tirés des constantes du module : un réglage faux passe inaperçu → valeurs de la spec en clair
- Deux mutations de même taille dans la même seconde partageaient un `.pyc` → outil corrigé (gotcha) ; ni commit ni édition pendant un lancement

## Blocked on

- T2.2 (NEO-29) attend la nouvelle clé de Julien (avant le pilote, phase 14 ; l'actuelle expire le 2026-11-07)

## Next (par ordre)

1. **T2.2** dès la clé de Julien : dépôt par le presse-papier (pipe, sans affichage) ; `banc.sh acces` (~0,003 $, feu vert) ; sa propre PR (NEO-29)
2. **Phase 14, T14.1** (NEO-33) : pilote `pilote-3`, une passe des deux cellules (≈ 1,5 $, plafond 3,5 $, feu vert de Julien) ; la règle de la source relue sur des réponses qui citent des descriptions
3. **T14.2** : gel du protocole du jalon 3 en tête de `revues.toml`, plafond de `g-1` au plan

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 003-graphrag-descriptions
Task: T2.2
Fichiers en cours: aucun
Bloqué sur: nouvelle clé Anthropic de Julien (T2.2, NEO-29)
Commande de reprise: git switch main && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
