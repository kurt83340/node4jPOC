# Tasks — Socle de données

> Checklist d'exécution pour `001-socle-donnees`. Coche au fur et à mesure.
> **DoD typée** : chaque tâche finit sur un critère VÉRIFIABLE, jamais une impression.
> 3 types : `command_passes:` (commande qui exit 0) · `file_exists:` (chemin présent) ·
> `manual:` (validation humaine explicite — dernier recours, à minimiser).
> **Budget : ~35 min de travail agent par phase max** — au-delà, l'agent ne se trompe plus,
> il « perd le fil » (échecs ×4 constatés en télémétrie, Morph 2026) → découper la phase.

**Date :** 2026-09-28 (revue adverse intégrée)
**Status :** [~] 6/16 tasks → MAJ au fil de l'eau

## Phase 1 — Préparer (sans instance)

- [x] **T1.1** : définir avec Julien les questions de référence : 30, en 6 catégories de 5, validées le 2026-09-29 ([questions/README.md](../../../../questions/README.md))
  - DoD : `manual: Julien valide questions/README.md`
- [x] **T1.2** : matrice question → labels et propriétés ; modèle v2 documenté dans `ARCHITECTURE.md` et validé le 2026-09-29, après une recherche sur les bonnes pratiques de modélisation (ADR-0005)
  - DoD : `manual: Julien valide le modèle documenté`
- [x] **T1.3** : installer Java 21 (`apt`) et `cypher-shell` 2026.09.0 (`.deb` de dist.neo4j.org, `sudo apt install ./…deb` en arrière-plan)
  - DoD : `command_passes: cypher-shell --version`

## Phase 2 — Accès et go/no-go (nécessite l'instance de Julien)

- [x] **T2.1** : `Neo4j-*.txt` ignoré par git et interdit en lecture (`/update-config`), `scripts/charger.sh` (lit le secret `neo4j-aura-poc` au lancement et n'en passe que les 4 variables `NEO4J_*` à `cypher-shell`, `set +x`, contrôle de sa propre sortie) ([ADR-0007](../../adr/0007-infra-secrets-et-services-geres.md)) ; `.claude/docs/ACCESS.md` et vraie limite (200 000 nœuds, 400 000 relations) faits le 2026-09-30 (NEO-6)
  - DoD : `command_passes: scripts/charger.sh --ping`
- [x] **T2.2** : go/no-go étendu, en lecture seule : `languages.csv` (14 lignes), descriptions FR (7 116 lignes, dont 7 115 multilignes), `pokemon_moves.csv` (638 321 lignes), `count(toInteger(trim(row.slot)))` = 2 943 sur `pokemon_abilities.csv` ; `MATCH (t:Type)` accepté sans backticks (`TYPE` est un mot-clé) ; Cypher 25 par défaut, contrôlé par `SHOW DATABASES` (déjà le cas : pas d'`ALTER`, voir D7). GO le 2026-09-30 ; `trim` inutile pour `LOAD CSV`, qui gère les fins de ligne Windows, mais gardé par prudence
  - DoD : `command_passes: scripts/charger.sh --go-no-go`

## Phase 3 — Vérification d'abord

- [x] **T3.1** : `cypher/90-verification.cypher` (33 contrôles en 8 sections : comptes par motif, empreintes, noms en double, volume sous la limite ; valeurs attendues calculées depuis les CSV par `LOAD CSV` en lecture seule) et `scripts/verifier.sh` (codes retour 0 / 1 / 2, `--section`) ; option `charger.sh --purge`, essayée sur un jeu jetable ; fonctions partagées dans `scripts/commun.sh`. Code 1 sur la base vide le 2026-09-30 (31 écarts sur 33)
  - DoD : `command_passes: scripts/verifier.sh; test $? -eq 1` (écart constaté sur base vide, pas une erreur technique)

## Phase 4 — Nœuds de référence

- [ ] **T4.1** : `cypher/00-contraintes.cypher`
  - DoD : `command_passes: scripts/verifier.sh --section contraintes`
- [ ] **T4.2** : `cypher/01-types.cypher` (18 types, 120 efficacités)
  - DoD : `command_passes: scripts/verifier.sh --section types`
- [ ] **T4.3** : `cypher/02-pokemon.cypher` (1 025 Pokémon, noms et catégories ; 484 `EVOLUE_EN` en seconde passe)
  - DoD : `command_passes: scripts/verifier.sh --section pokemon`
- [ ] **T4.4** : `cypher/03-formes.cypher` (1 351 formes, `FORME_DE`, `A_POUR_FORME_PAR_DEFAUT`, stats, `A_LE_TYPE`, règle des noms)
  - DoD : `command_passes: scripts/verifier.sh --section formes`
- [ ] **T4.5** : `cypher/04-talents.cypher` (313 talents utilisés, `A_LE_TALENT`)
  - DoD : `command_passes: scripts/verifier.sh --section talents`

## Phase 5 — Gros volumes (en arrière-plan, journal horodaté)

- [ ] **T5.1** : `cypher/05-attaques.cypher` (919 attaques, type, puissance, catégorie ; `APPREND` agrégé par lots)
  - DoD : `command_passes: scripts/verifier.sh --section attaques`
- [ ] **T5.2** : `cypher/06-descriptions.cypher` (5 233 descriptions normalisées, liste des jeux)
  - DoD : `command_passes: scripts/verifier.sh --section descriptions`

## Phase 6 — Idempotence

- [ ] **T6.1** : purge, chargement complet, empreinte, second chargement, même empreinte
  - DoD : `command_passes: scripts/verifier.sh --idempotence`

## Phase 7 — Questions de référence et clôture

- [ ] **T7.1** : `questions/qNN.cypher` × 27 (Q10, Q29 et Q30 se notent par une règle, sans requête) et `scripts/questions.sh` (format déterministe, SHA du commit en en-tête) ; Q1 = Roche ×4 contre Dracaufeu
  - DoD : `command_passes: scripts/questions.sh --verifier`
- [ ] **T7.2** : `code-map.md`, `stack.md` et la section Stack du `README.md` à jour, ADR-0003 à ADR-0005 vérifiés, puis `/feature-done 001-socle-donnees`
  - DoD : `manual: Julien valide la livraison`

## Definition of Done (global)

La feature est livrée quand :

- [ ] Tous les critères d'acceptation de [spec.md](spec.md) cochés
- [ ] `verifier.sh` conforme, idempotence prouvée (T6.1), questions rejouables (T7.1)
- [ ] Pas de TODO ni de `// FIXME` dans les scripts
- [ ] Aucun identifiant dans le dépôt ni dans une sortie de commande
- [ ] Documentation à jour (modèle, code-map, stack, décisions du plan)
- [ ] Commit sur la branche `feature/001-socle-donnees`

## Blockers / questions

- Aucun : instance AuraDB Free créée et identifiants dans Secret Manager le 2026-09-30 (NEO-6).
