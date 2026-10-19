# HANDOFF — 2026-10-19 20h15

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/003-phase-17-recherche-seule` (PR n°41 ; fusion après ce handoff, feu vert de Julien)
**Spec en cours** : [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) (23/35 tasks)
**Goal session** : sans la clé de T2.2, T16.3 en partie puis T17.1 en TDD, sans dépense (choix de Julien)

## Status

- ✅ T16.3 en partie (PR n°40, fusionnée) : `gemini-embedding-001` facturé au jeton (export BigQuery) ; phase 6 recoupée, 0,0479 $ pour 0,0498 $ estimés (plan, D11 ; RUNBOOK) ; section publiée dans NEO-33
- ✅ T17.1 en partie (PR n°41) : `banc recherche-seule` en TDD, 33 tests, 33 mutations détectées ; suite complète 1 928 tests ; choix validés par Julien (plan, D13) ; la mesure attend `g-1`
- ⏳ NEO-35 « En cours » : « Résultats du 2026-10-19 (T17.1, en partie) » montrés à Julien, publiés après la fusion

## Échecs tentés (à ne pas refaire)

- `EXPLAIN` passé par `read-cypher` : il le préfixe déjà (neo4j-mcp v1.6.0) → contrôle sur un vecteur factice
- Attendus de test tirés des constantes du module : un réglage faux passe inaperçu → valeurs de la spec en clair
- Deux mutations de même taille dans la même seconde partageaient un `.pyc` → outil corrigé (gotcha) ; ni commit ni édition pendant un lancement
- D'autres commandes pendant la suite complète : `test_serveur_perdu_en_fin_de_tour` échoue sous la charge (gotcha) → la suite seule

## Blocked on

- T2.2 (NEO-29) attend la nouvelle clé de Julien (avant le pilote, phase 14 ; l'actuelle expire le 2026-11-07)

## Next (par ordre)

1. **T2.2** dès la clé de Julien : dépôt par le presse-papier (pipe, sans affichage) ; `banc.sh acces` (~0,003 $, feu vert) ; sa propre PR (NEO-29)
2. **Phase 14, T14.1** (NEO-33) : pilote `pilote-3`, une passe des deux cellules (≈ 1,5 $, plafond 3,5 $, feu vert de Julien), PATH normal, crédits et limite de 20 $ vérifiés avant ; la règle de la source relue sur des réponses qui citent des descriptions
3. **T14.2** : gel du jalon 3, table `[[jalon]]` de `revues.toml` (ligne `gel = AAAA-MM-JJTHH:MM:SS`, que `banc recherche-seule` retrouve par `git log -S`), commit noté au plan ; plafond de `g-1` ; puis T15.2, T15.3 et la mesure de T17.1 sur `g-1`

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 003-graphrag-descriptions
Task: T2.2
Fichiers en cours: aucun
Bloqué sur: nouvelle clé Anthropic de Julien (T2.2, NEO-29)
Commande de reprise: git switch main && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
