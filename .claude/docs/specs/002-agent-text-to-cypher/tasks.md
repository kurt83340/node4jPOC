# Tasks — Agent text-to-Cypher

> Checklist d'exécution pour `002-agent-text-to-cypher`. Coche au fur et à mesure.
> **DoD typée** : chaque tâche finit sur un critère VÉRIFIABLE, jamais une impression.
> 3 types : `command_passes:` (commande qui exit 0) · `file_exists:` (chemin présent) ·
> `manual:` (validation humaine explicite — dernier recours, à minimiser).
> **Budget : ~35 min de travail agent par phase max** — au-delà, l'agent ne se trompe plus,
> il « perd le fil » (échecs ×4 constatés en télémétrie, Morph 2026) → découper la phase.

**Date :** 2026-10-01
**Status :** [~] 10/33 tasks → MAJ au fil de l'eau

> Phases 0 à 6 : sans la base (prévues pendant la période creuse de NEO-13, close le 2026-10-07). Phases 7 à 11 : sur la base.
> Les tests n'appellent aucun outil réel : PATH réduit aux faux outils, HOME temporaire.
> Une branche et une PR par phase ([rule git-workflow](../../../rules/git-workflow.md)) ; le titre de la PR finit par
> la clé Jira indiquée dans le titre de la phase (epic [NEO-2](https://frjulienleroy.atlassian.net/browse/NEO-2)).

## Phase 0 — Socle sans base (NEO-14 ; T0.2 : NEO-15)

- [x] **T0.1** : projet `banc/` (uv, Python 3.14 ; `google-adk`, `claude-agent-sdk` et `anthropic[vertex]` à versions figées ; ruff, mypy, pytest) ; compatibilité de 3.14 vérifiée, sinon 3.13 et la raison notée — fait le 2026-10-07 : Python 3.14.7 ; `google-adk[mcp]` 2.11.0 (MCP est un extra depuis la v2), `claude-agent-sdk` 0.2.164 (Claude Code 2.1.292 embarqué), `anthropic[vertex]` 1.11.0 ; 3.14 gardée : toutes les dépendances ont une roue 3.14 (rien de compilé), et `tests/test_compatibilite.py` importe les points d'entrée des cellules, car `claude-agent-sdk` ne déclare que 3.13 (sa CI ne teste que 3.12)
  - DoD : `command_passes: uv run --directory banc pytest -q && uv run --directory banc ruff check && uv run --directory banc mypy .`
- [x] **T0.2** : accès par les 3 vrais clients, Claude Code et `AnthropicLlm` d'ADK par l'API Anthropic, Gemini dans ADK par Vertex `eu` ([ADR-0011](../../adr/0011-infra-claude-par-api-anthropic.md)) : un appel minimal chacun, `apiKeySource` = la clé ; Haiku 4.5 compris, petit modèle de Claude Code ; limites de débit de l'API, effort effectif et reprises internes des clients (429, 5xx) relevés ; prix datés (cache et réflexion compris) dans `banc/prix.toml` — en cours le 2026-10-07 : conditions de Model Garden acceptées, `banc acces` prêt (prix datés, liste blanche, sondes) ; Gemini répond, Claude bute sur un quota à 0 en `eu` : hausse demandée puis refusée le jour même (refus automatique), T0.2 en parking pour Claude ; relevé dans `plan.md` (D2, D3, D13) ; voie tranchée le 2026-10-08 : API Anthropic, 20 $ de crédits sans recharge automatique ; fait le 2026-10-08 : `scripts/banc.sh acces` passe (5 clients, 0,0027 $), `apiKeySource` = la clé, coût calculé égal à celui de Claude Code ; relevé dans `plan.md` (D2, D3)
  - DoD : `manual: Julien crée le workspace du banc, ses 20 $ de crédits (recharge automatique coupée) et sa clé, rangée dans Secret Manager (anthropic-api-banc)`, puis `command_passes: scripts/banc.sh acces`
- [x] **T0.3** : `neo4j-mcp` v1.6.0 installé depuis la release GitHub, sans le lancer (il interroge la base au démarrage) ; noms des variables, lecture seule et télémétrie lus dans le source du tag v1.6.0, et notés dans `plan.md` § D1 — fait le 2026-10-07 : somme vérifiée, binaire dans `~/.local/share/neo4j-mcp/v1.6.0/` ; lecture seule et télémétrie se règlent, circuit breaker non déclenché
  - DoD : `command_passes: sha256sum -c <fichier des sommes publié avec la release v1.6.0> --ignore-missing`
- [x] **T0.4** : `scripts/mcp-neo4j.sh` : chemin absolu, secret lu par `commun.sh` avec `gcloud` sans stdin, variables du tag, `READ_ONLY` et télémétrie coupée, anciens noms retirés, rien sur stdout, stderr filtré, puis `exec` — fait le 2026-10-07 : 12 tests, PATH réduit à bash et aux deux faux outils ; aucun argument transmis (les options de `neo4j-mcp` passent avant l'environnement), tout `NEO4J_*` hérité retiré ; chaque propriété vérifiée par mutation (10 fautes injectées, 10 détectées) ; `trouver_outils` accepte une liste d'outils, `filtrer_flux` filtre un flux
  - DoD : `command_passes: uv run --directory banc pytest tests/test_lanceur.py -q` (sous la liste blanche de D3, faux `gcloud` et faux `neo4j-mcp` : variables présentes, aucune valeur sur stdout, mot de passe jamais en argument, stdin intact)

## Phase 1 — Banc lisible par le harnais (NEO-16)

- [x] **T1.1** : `questions/banc.toml` : les 30 questions (texte exact, catégorie, mode de notation, tour précédent, valeurs attendues, distracteurs, règle des longues listes pour Q7 et Q14), en TDD — fait le 2026-10-08 : distracteurs tirés des CSV du commit figé, relus et validés par Julien ; règle des longues listes et tolérance de Q8 (Typhlosion) ajoutées au README ; `banc.questions` refuse tout champ hors de son mode, `banc.attendu` relit `attendu/` ; 102 tests de cohérence, 15 fautes injectées, toutes détectées
  - DoD : `command_passes: uv run --directory banc pytest tests/test_banc_toml.py -q` (cohérence avec les tableaux du README et avec `questions/attendu/`)
- [x] **T1.2** : `questions/consigne.md` et `questions/fiche-schema.md` : modèle, règles et cas limites (liste du jalon 2 de la ROADMAP, plus le niveau minimal d'`APPREND` et « pas de relation d'efficacité = ×1 »), illustrés par d'autres cas que ceux du banc ; valeurs possibles, index plein texte, 6 à 8 exemples hors banc
  - DoD : `command_passes: uv run --directory banc pytest tests/test_contamination.py -q` (fichiers entiers ; liste blanche ; aucune valeur citée dans `questions/attendu/` hors liste blanche ; exemples comparés aux 27 requêtes, littéraux masqués), puis `manual: Julien relit la fiche et la consigne` — le 2026-10-08 : fichiers écrits, test vert (25 tests ; seuils mesurés sur les 31 requêtes de référence ; 13 contaminations injectées, toutes détectées) ; relues et validées par Julien le 2026-10-08
- [x] **T1.3** : `questions/q02.cypher` lit `$proposee` ; `scripts/questions.sh` le passe toujours (défaut : l'équipe actuelle), et accepte `--dossier` et `--exemples` (exemples de la fiche et `dracofeu~`) — fait le 2026-10-08 : un exemple en échec ou sans ligne, index absent compris, est un écart (1) ; `--dossier` lit `D/qNN.cypher` et `D/exemples/*.cypher` (forme à suivre en T6.2), refusé avec `--enregistrer` ; `tests/test_questions_sh.py` sans base (15 tests, 5 fautes injectées, toutes détectées)
  - DoD : `command_passes: bash -n scripts/questions.sh` (contrôle sur la base en T7.2 et T7.3)

## Phase 2 — Notation, en TDD (NEO-17)

- [x] **T2.1** : lecture des réponses : sections « Réponse » et « Sources », normalisation (casse, accents, apostrophes), extraction des 6 noms de Q2, validés (caractères permis) puis échappés en liste littérale — fait le 2026-10-08 : `banc.lecture` (la dernière section l'emporte, aucun en-tête lu dans un bloc de code ; élisions détachées par le découpage en mots) ; espèces reconnues par la liste tirée de la base (`questions/especes.cypher`, `attendu/especes.txt`, 1 025 noms rejoués par `--verifier`, choix de Julien) ; Q2 : espèces citées, référence écartée au-delà de 6, validées puis échappées, passées à `questions.sh --controle`, qui revérifie la forme ; `pytest-cov` 7.1.0 figé ; 82 tests, 27 fautes injectées, toutes détectées
  - DoD : `command_passes: uv run --directory banc pytest tests/test_lecture.py -q`
- [x] **T2.2** : règles de notation : modes (valeur, ensemble, liste ordonnée, nombre), distracteurs, longues listes, tables de l'ADR-0008 (rappel, précision, seuils), source citée (requête exécutée dans le tour dont le résultat contient la réponse ; description renvoyée dans le tour ; exceptions de Q10 et Q30), introspections comptées — fait le 2026-10-08 : `banc.notation` et `banc.trace` (contrat minimal d'un tour, choix de Julien ; T3.1 l'entoure) ; au pluriel, partiel avec une espèce juste (choix de Julien) ; revue adverse à contexte frais : 12 constats, dont des « juste » à tort (Q8, Q9, Q27, Q28, formes, source citée), tous corrigés, et Q27 et Q28 passées en revue systématique (choix de Julien) ; 119 tests, couverture 99,7 % ; 33 puis 59 fautes injectées, toutes détectées
  - DoD : `command_passes: uv run --directory banc pytest tests/test_notation.py -q --cov=banc.notation --cov-fail-under=80`

## Phase 3 — Mesures et revue (NEO-17)

- [ ] **T3.1** : traces et mesures : une trace JSONL par conversation (identifiant masqué), une ligne CSV sans prose (cause d'un échec, introspections), coût par modèle avec cache, réflexion et petit modèle de Claude Code
  - DoD : `command_passes: uv run --directory banc pytest tests/test_mesures.py -q`
- [ ] **T3.2** : revue humaine à l'aveugle (`banc revoir`) : décisions datées à partir du gel, aucune héritée du pilote ; réutilisées par réponse courte normalisée pour les seules questions à valeur (jamais Q7, Q11, Q12, Q13, Q27, Q28, Q29), dans `banc/mesures/revues.toml`
  - DoD : `command_passes: uv run --directory banc pytest tests/test_revue.py -q`

## Phase 4 — Cellules (NEO-18)

- [ ] **T4.1** : cellule Agent SDK : `env -i` et liste blanche (HOME temporaire, `CLOUDSDK_CONFIG`, PATH, `ANTHROPIC_API_KEY` sans variable Vertex, effort `high`, petit modèle figé), `CLAUDE_CONFIG_DIR` temporaire, `setting_sources=[]`, `tools=[]`, `read-cypher` seul ; `connect()` puis `get_mcp_status()` jusqu'à « connected » avant le chrono ; budget par conversation
  - DoD : `command_passes: uv run --directory banc pytest tests/test_cellule_sdk.py -q` (faux `cli_path` : aucune variable hors liste blanche, aucun fichier de réglages lu, chrono lancé après la connexion)
- [ ] **T4.2** : cellules ADK (Claude par `AnthropicLlm` et l'API Anthropic, Gemini par Vertex `eu`) : `McpToolset` en stdio sur le lanceur, `get_tools()` avant le chrono, `tool_filter`, délai de 30 s, effort et `thinking_level` fixés, budget par conversation
  - DoD : `command_passes: uv run --directory banc pytest tests/test_cellule_adk.py -q` (faux serveur MCP, faux LLM)
- [ ] **T4.3** : orchestration : même session au second tour ; plafonds (10 tours, 180 s, budget) ; panne relancée (la paire pour Q18 et Q28), échec de l'agent noté faux avec sa cause, délai dû aux reprises internes compté comme panne ; groupe de processus tué, `scripts/transactions.sh` appelé ; cellules alternées question par question ; `--reprendre` ; règle de couplage de `transactions.sh` dans la code-map
  - DoD : `command_passes: uv run --directory banc pytest tests/test_orchestration.py -q && bash -n scripts/transactions.sh`

## Phase 5 — Répétition générale (NEO-18)

- [ ] **T5.1** : vrais LLM, mode faux serveur (serveur MCP, validation des noms et contrôle de Q2 simulés) : 3 cellules sur Q19, puis Q2 suivie de Q18 ; un délai dépassé noté faux
  - DoD : `command_passes: uv run --directory banc python -m banc lancer --faux-serveur --questions Q19,Q2,Q18`, lancé avec un PATH sans `gcloud` ni `cypher-shell` (traces, CSV et coût produits)

## Phase 6 — Schéma anglais, partie sans base (NEO-19)

- [ ] **T6.1** : `cypher/anglais/correspondance.toml` (table unique, liste relue des identifiants communs aux deux langues) ; carte `correspondance.cypher` produite par `banc` et versionnée ; `renommer.cypher` (relations recréées par lots, contraintes et index de la langue visée) ; `charger.sh --schema fr|en` et `--explain`, sans Python au chargement, qui refuse `--tout` sur une base anglaise ; règle de couplage de `--schema` dans la code-map
  - DoD : `command_passes: bash -n scripts/charger.sh && uv run --directory banc pytest tests/test_correspondance.py -q` (carte à jour avec la table)
- [ ] **T6.2** : traducteur du Cypher, en TDD, et `banc traduire --vers <dossier>` : les 27 requêtes (dont la q02) et `especes.cypher`, les exemples de la fiche (dont `dracofeu~`) et une requête de balayage avec sa réponse attendue ; identifiants traduits ; littéraux, alias et expressions régulières inchangés
  - DoD : `command_passes: uv run --directory banc pytest tests/test_traduction.py -q` (contrôle contre une liste française tirée d'ARCHITECTURE § 5, indépendante de la table, identifiants communs écartés)
- [ ] **T6.3** : `questions/fiche-schema.en.md` produite par la table (et produite de nouveau après le gel du protocole)
  - DoD : `command_passes: uv run --directory banc pytest tests/test_fiche_anglaise.py -q` (aucun identifiant de la liste française indépendante, hors identifiants communs)

## Phase 7 — Retour sur la base, à partir du 2026-10-04 (NEO-20 ; T7.1 : NEO-13)

- [x] **T7.1** : NEO-13 : instance toujours « Running » après 72 h sans requête humaine — fait le 2026-10-07 : aucune requête humaine depuis le 2026-10-01, `reveil-aura` réussi 7 fois sur 7, NEO-13 « Terminé »
  - DoD : `manual: console Aura « Running », NEO-13 passé à « Terminé »`
- [ ] **T7.2** : index plein texte (analyseur vérifié d'abord par `listAvailableAnalyzers()`) dans `cypher/00-contraintes.cypher`, 34e contrôle (présence de l'index) dans `cypher/90-verification.cypher`, rechargement complet, `$proposee` par défaut
  - DoD : `command_passes: scripts/charger.sh --tout && scripts/verifier.sh && scripts/charger.sh --idempotence && scripts/questions.sh --verifier`
- [ ] **T7.3** : valeurs de la fiche vérifiées dans la base (une requête par liste) ; exemples et `dracofeu~` exécutés en lecture, chacun avec un résultat non vide
  - DoD : `command_passes: scripts/questions.sh --exemples`
- [ ] **T7.4** : lanceur sur la vraie base : `read-cypher` répond, une écriture est refusée, les agents ne voient que `read-cypher` ; une lecture lente est arrêtée côté Aura par `scripts/transactions.sh`
  - DoD : `command_passes: uv run --directory banc python -m banc essai-serveur`
- [ ] **T7.5** : mécanisme de renommage choisi sur la vraie base, sans rien écrire : labels et types dynamiques de Cypher 25, sinon `apoc.refactor.rename.*`
  - DoD : `command_passes: scripts/charger.sh --schema en --explain`

## Phase 8 — Pilote (NEO-21)

- [ ] **T8.1** : passe pilote (3 cellules × 30 questions, non comptée) ; revue ; coût comparé à l'estimation (arrêt au-delà de 1,5 fois) ; seuls l'extraction, la notation et le coût sont réglés, tout autre changement justifié sans question du banc et noté dans `plan.md` ; seuils du FR/EN fixés ; gel du protocole (commit)
  - DoD : `manual: Julien valide le rapport du pilote, les seuils et le gel`

## Phase 9 — Campagne (NEO-21 ; T9.2 : NEO-22)

- [ ] **T9.1** : 3 passes comptées, cellules alternées question par question, reprise possible
  - DoD : `command_passes: uv run --directory banc python -m banc rapport --campagne <id> --complet` (9 séries, aucune panne non relancée)
- [ ] **T9.2** : revue humaine des « à revoir »
  - DoD : `command_passes: uv run --directory banc python -m banc revoir --campagne <id> --verifier` (aucun cas restant)
- [ ] **T9.3** : coût recoupé avec l'export de facturation BigQuery (`/google-facture`), le lendemain
  - DoD : `manual: écart noté dans le rapport de campagne`

## Phase 10 — Schéma anglais, sur la base (NEO-23)

- [ ] **T10.1** : bascule vers l'anglais, puis preuve d'isomorphisme : les 27 requêtes traduites rendent `attendu/` à l'identique, `dracofeu~` trouve Dracaufeu par l'index anglais, le balayage ne trouve aucun identifiant français ; `db.propertyKeys()` relevé
  - DoD : `command_passes: uv run --directory banc python -m banc traduire --vers logs/anglais && scripts/charger.sh --schema en && scripts/questions.sh --verifier --dossier logs/anglais && scripts/questions.sh --exemples --dossier logs/anglais`
- [ ] **T10.2** : 3 passes ADK + Gemini avec la fiche anglaise, puis leur revue
  - DoD : `command_passes: uv run --directory banc python -m banc rapport --campagne <id-anglais> --complet && uv run --directory banc python -m banc revoir --campagne <id-anglais> --verifier`
- [ ] **T10.3** : retour au français, prouvé, `db.propertyKeys()` relevé ; puis une passe Gemini française de contrôle, et sa revue
  - DoD : `command_passes: scripts/charger.sh --schema fr && scripts/verifier.sh && scripts/questions.sh --verifier && scripts/questions.sh --exemples`, puis `command_passes: uv run --directory banc python -m banc rapport --campagne <id-controle> --complet && uv run --directory banc python -m banc revoir --campagne <id-controle> --verifier`

## Phase 11 — Résultats et livraison (NEO-24)

- [ ] **T11.1** : rapport de la technique 2 : score par cellule et par catégorie, écart entre passes, causes d'échec, introspections, temps, coût, sources citées, FR/EN (seuils fixés d'avance, limite à un modèle), effort de mise en place
  - DoD : `file_exists: banc/resultats/technique-2.md`
- [ ] **T11.2** : doc : code-map (relecture des règles du lanceur, du harnais, de `--schema` et de `transactions.sh`), stack (bibliothèques, LLM, coûts), ARCHITECTURE, RUNBOOK (lancer une campagne, basculer en anglais, revenir), ACCESS (Model Garden), README (jalon 2)
  - DoD : `command_passes: python3 .claude/skills/doc-health/scripts/context-budget.py`
- [ ] **T11.3** : `/feature-done 002-agent-text-to-cypher` : dernière PR, fusion, puis tag `jalon-2` sur `main`
  - DoD : `command_passes: git rev-parse jalon-2`, et `manual: ROADMAP et CHANGELOG à jour`

## Definition of Done (global)

La feature est livrée quand :

- [ ] Tous les critères d'acceptation de [spec.md](spec.md) cochés
- [ ] Tests verts (unitaires, intégration sans base, contrôles sur la base)
- [ ] Pas de TODO ou `# FIXME` dans le code
- [ ] Pas de fuite d'identifiants (gitleaks, traces masquées, agents en `env -i`)
- [ ] Base de référence intacte : 34/34 contrôles, 27/27 réponses, exemples conformes
- [ ] Documentation à jour (code-map, plan.md décisions)
- [x] ADR du protocole de mesure créé ([ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md), 2026-10-01)
- [ ] Commit + PR

## Blockers / questions

- NEO-13 clos le 2026-10-07 : la base est de nouveau utilisable.
- Quotas Claude à 0 sur `jleroy-labo` : hausse demandée le 2026-10-07 et refusée automatiquement ; Claude injoignable par Vertex, parking et décision de Julien (prix et reprises internes relevés). Tranché le 2026-10-08 : API Anthropic ([ADR-0011](../../adr/0011-infra-claude-par-api-anthropic.md)).
- Compatibilité de Python 3.14 avec ADK et l'Agent SDK : vérifiée le 2026-10-07 (T0.1).
- `TERMINATE TRANSACTIONS` permis sur Aura Free ? (T7.4)
- Noms de propriétés orphelins après la bascule (`db.propertyKeys()`) : à vérifier au jalon 4, avant qu'Aura Agent ne lise le schéma.
