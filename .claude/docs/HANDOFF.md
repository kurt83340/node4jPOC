# HANDOFF — 2026-10-19 00h45

> Court, narratif, versionné. Patterns techniques → auto-memory. Reprise précise → /resume.

**Branche** : `feature/003-phase-15-traces` (PR n°39 ; fusion après ce handoff, feu vert de Julien)
**Spec en cours** : [003-graphrag-descriptions](specs/003-graphrag-descriptions/spec.md) (23/35 tasks)
**Goal session** : T15.1 (NEO-33) avant le pilote, la clé de T2.2 n'étant pas encore là (choix de Julien)

## Status

- ✅ T15.1 (PR n°39) : `banc controle-traces` (outils, écritures, jetons Google, vecteurs) et `scripts/traces.sh` (identifiant de l'instance, totaux seuls) ; 58 tests, 44 mutations détectées ; banc 1 895 tests verts ; DoD : `fr-1` et `repetition-3` conformes
- ✅ Choix de T15.1 validés par Julien (plan, D9) : seuil de 100 nombres, procédures non lues, entrée non fichier en erreur, `logs/banc/<campagne>.log` lu par `traces.sh`
- ⏳ NEO-33 « En cours » : « Résultats du 2026-10-19 (T15.1) » relus par Julien, publiés après la fusion

## Échecs tentés (à ne pas refaire)

- `EXPLAIN` passé par `read-cypher` : il le préfixe déjà (neo4j-mcp v1.6.0) → contrôle sur un vecteur factice
- Attendus de test tirés des constantes du module : un réglage faux passe inaperçu → valeurs de la spec en clair
- Deux mutations de même taille dans la même seconde partageaient un `.pyc` → outil corrigé (gotcha) ; ni commit ni édition pendant un lancement

## Blocked on

- T2.2 (NEO-29) attend la nouvelle clé de Julien (avant le pilote, phase 14 ; l'actuelle expire le 2026-11-07)

## Next (par ordre)

1. **T2.2** dès la clé de Julien : dépôt par le presse-papier (pipe, sans affichage) ; `banc.sh acces` (~0,003 $, feu vert) ; sa propre PR (NEO-29)
2. **Phase 14, T14.1** (NEO-33) : pilote `pilote-3`, une passe des deux cellules (≈ 1,5 $, plafond 3,5 $, feu vert de Julien), PATH normal, crédits et limite de 20 $ vérifiés avant ; la règle de la source relue sur des réponses qui citent des descriptions
3. **T14.2** : gel du protocole du jalon 3 en tête de `revues.toml`, plafond de `g-1` au plan ; puis T15.2 (`g-1`, ses traces contrôlées) et T15.3

## Continuation State (machine-readable — grammaire fixe `Clé: valeur`, 1 ligne chacune)

Spec: 003-graphrag-descriptions
Task: T2.2
Fichiers en cours: aucun
Bloqué sur: nouvelle clé Anthropic de Julien (T2.2, NEO-29)
Commande de reprise: git switch main && git pull

→ **Journal des sessions** (append-only) : [HANDOFF-journal.md](HANDOFF-journal.md) — non auto-chargé.
