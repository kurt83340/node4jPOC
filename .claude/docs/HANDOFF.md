# HANDOFF — 2026-10-18 20h45

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/003-phase-12` (PR n°37 ; fusion après ce handoff, feu vert de Julien ; la n°36 est fusionnée)
**Spec en cours** : [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) (20/35 tasks)
**Goal session** : phases 11 et 12 du jalon 3, sans dépense : seconds tours, isolement, source citée, puis orchestration des campagnes GraphRAG (NEO-32)

## Status

- ✅ Phase 11 fusionnée (PR n°36) : seconds tours prouvés avec le vrai ADK ; liste blanche des cellules GraphRAG ; source citée de l'ADR-0018 (descriptions réunies, toutes les valeurs ; requêtes et descriptions jugées chacune à part, choix de Julien), colonne source de `fr-1` inchangée ; 14 mutations, toutes détectées
- ✅ Phase 12 (PR n°37) : cellules enregistrées (technique 2 par défaut, une technique par campagne, validé par Julien), `campagne.json` format 4, `encodages.json` à la création, vecteurs et empreinte de la requête dans la commande ; banc 1 819 tests, ruff, mypy verts ; 34 mutations, toutes détectées
- ⏳ NEO-32 « En cours » : formats de clôture des phases 11 et 12 montrés à Julien après la fusion de la n°37, puis publiés ; il ne se clôt qu'à la phase 13

## Échecs tentés (à ne pas refaire)

- `EXPLAIN` passé par `read-cypher` : il le préfixe déjà (neo4j-mcp v1.6.0) → contrôle sur un vecteur factice
- Attendus de test tirés des constantes du module : un réglage faux passe inaperçu → valeurs de la spec en clair
- Deux mutations de même taille dans la même seconde partageaient un `.pyc` : une mutation crue survivante → outil corrigé (gotcha), les 143 mutations Python passées rejouées (142 détectées, la survivante connue) ; ni commit ni édition pendant un lancement

## Blocked on

- T2.2 (NEO-29) attend la nouvelle clé de Julien (avant le pilote, phase 14 ; l'actuelle expire le 2026-11-07)

## Next (par ordre)

1. **Phase 13, T13.1** (sans dépense) : à la création d'une campagne GraphRAG, `verifier.sh --section embeddings` sans `ANTHROPIC_*` et preuve de symétrie, sautés en faux serveur ; résultat de recherche fixe du faux serveur ; bout en bout avec les vraies cellules contre de fausses API
2. **T13.2** : répétition générale (≈ 0,2 $, feu vert de Julien) ; règle de la source relue sur les réponses obtenues
3. **T2.2** dès la clé de Julien : dépôt par le presse-papier (pipe, sans affichage) ; `banc.sh acces` (~0,003 $, feu vert) ; sa propre PR

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 003-graphrag-descriptions
Task: T13.1
Fichiers en cours: aucun
Bloqué sur: rien
Commande de reprise: git switch main && git pull && git switch -c feature/003-phase-13

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
