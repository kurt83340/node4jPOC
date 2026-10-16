# Tasks — GraphRAG sur les descriptions

> Checklist d'exécution pour `003-graphrag-descriptions`. Coche au fur et à mesure.
> **DoD typée** : chaque tâche finit sur un critère VÉRIFIABLE, jamais une impression.
> 3 types : `command_passes:` (commande qui exit 0) · `file_exists:` (chemin présent) ·
> `manual:` (validation humaine explicite — dernier recours, à minimiser).
> **Budget : ~35 min de travail agent par phase max** — au-delà, l'agent ne se trompe plus,
> il « perd le fil » (échecs ×4 constatés en télémétrie, Morph 2026) → découper la phase.

**Date :** 2026-10-12
**Status :** [ ] 8/35 tasks → MAJ au fil de l'eau

> Les tests n'appellent aucun service réel (Vertex, Anthropic, Aura) : faux outils, fausses API, HOME temporaire.
> Une dépense passe par le feu vert de Julien, annoncée avec son estimation : phases 2, 6, 8, 13, 14 et 15.
> Une branche et une PR par phase ([rule git-workflow](../../../rules/git-workflow.md)) ; le titre de la PR finit par
> la clé Jira de la phase, sous l'epic [NEO-3](https://frjulienleroy.atlassian.net/browse/NEO-3) (NEO-28 à NEO-35, créés le 2026-10-13 ; clé de chaque phase dans son titre).
> Commandes du banc : `uv run --directory banc python -m banc <commande>` (abrégé `banc <commande>`) ; `scripts/banc.sh` quand il faut la clé Anthropic.
> Des tâches qui touchent les mêmes fichiers (`charger.sh`, `test_charger_sh.py`, `test_contamination.py`, `cellule.py`, `orchestration.py`) se font dans cet ordre, jamais en parallèle.

## Phase 1 — Contre-épreuve dans le banc (sans base, sans dépense ; NEO-28)

- [x] **T1.1** : contre-épreuve de l'[ADR-0014](../../adr/0014-mvp-revue-assistee.md) promue dans `banc/`, en TDD, à partir de `logs/outils/` (`tirage.py`, `page.py`, `page-modele.html`, `tous-les-cas.py`, `enregistrer.py`) : `banc contre-epreuve --campagne <id>` tire 8 cas (graine = 16 premiers caractères hexadécimaux du SHA-256 du CSV fini), écrit la page à l'aveugle et les clés à part, puis rend le taux d'accord et les désaccords une fois les réponses de Julien relevées (plan, D15) — fait le 2026-10-13 : `banc contre-epreuve` en trois temps (tirage, `--accord`, `--enregistrer`, ce dernier par `banc.revue.revoir` et le décideur de sa `Console`), gabarit de la page dans le paquet ; 60 tests écrits d'abord, rouges puis verts ; 52 mutations, toutes détectées ; suite complète (1 541 tests), ruff et mypy verts ; tirages d'`en-1` et de `fr-controle` refaits à l'identique ; périmètre et garde-fous au plan (D15, précision du 2026-10-13)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_contre_epreuve.py` (écrit d'abord, rouge, puis vert : même CSV, mêmes 8 cas ; moins de 8 cas, tous ; ni cellule, ni passe, ni modèle dans les cas ni dans la page ; clés dans un fichier à part ; stockage local de la page propre à la campagne ; accord = même note, désaccords listés), puis `uv run --directory banc pytest -q && uv run --directory banc ruff check && uv run --directory banc mypy .` ; chaque règle désactivée fait échouer son test

## Phase 2 — Gels par jalon et clé Anthropic (environ 0,003 $ ; NEO-28 ; T2.2 : NEO-29)

- [x] **T2.1** : `revues.toml` accepte un gel et un pilote par jalon ; l'en-tête actuel (`gel`, `pilote`) se lit tel quel ; une décision d'un pilote ne se réutilise jamais ; une décision prise après le gel de son jalon se réutilise d'un jalon à l'autre (note seule, même question, même réponse courte) (plan, D15), en TDD — fait le 2026-10-13 : une table `[[jalon]]` (gel, pilote) par jalon après le premier, dont l'en-tête se lit tel quel ; pilotes de tous les jalons jamais réutilisés ; réutilisation dès le premier gel, d'un jalon à l'autre ; 14 tests ajoutés, rouges puis verts ; 11 mutations, toutes détectées ; `banc revoir --campagne fr-1 --verifier` : 0 cas à revoir ; notes reprises des campagnes du jalon 2 inchangées ; format au plan (D15, précision du 2026-10-13)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_revue.py && uv run --directory banc python -m banc revoir --campagne fr-1 --verifier`
- [ ] **T2.2** : clé Anthropic du banc renouvelée avant le pilote (elle expire le 2026-11-07) : nouvelle clé dans le workspace « Default », nouvelle version du secret `anthropic-api-banc` (skill `secret-manager`, rappel d'expiration), ancienne clé révoquée, [ACCESS](../../ACCESS.md) à jour ; action de Julien — précision du 2026-10-13 : reportée par Julien, qui change la clé dans la semaine ; elle aura sa propre PR (NEO-29), la phase 2 ne livrant que T2.1
  - DoD : `manual: Julien crée la clé dans la Console et la range dans Secret Manager`, puis `command_passes: scripts/banc.sh acces` (sondes, environ 0,003 $, annoncées)

## Phase 3 — Garde-fous du chargement (sans dépense ; NEO-30)

- [x] **T3.1** : vérification d'abord : section `embeddings` de `cypher/90-verification.cypher` et de `scripts/verifier.sh` (liste `SECTIONS`) : 5 233 descriptions à `embedding`, toutes de 3 072 dimensions, index `descriptions_texte` (VECTOR, `Description`, `embedding`, 3 072, `cosine`, sans quantification) ONLINE (plan, D3) — fait le 2026-10-13 : section en fin de `90-verification.cypher`, trois contrôles (5 233 vecteurs ; aucun hors `VECTOR(3072)`, par prédicat de type ; index lu par son nom, rendu en clair), `embeddings` dans `SECTIONS` ; 15 tests écrits d'abord, rouges puis verts ; 14 mutations, toutes détectées ; shellcheck avec `-x` (seul, `verifier.sh` lève SC1091, niveau info, sur le `source` de `commun.sh`, déjà sur `main`) ; sur la base, 2 écarts sur 3, code 1, les 34 autres contrôles conformes ; choix au plan (D3, précision du 2026-10-13)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_verifier_sh.py && shellcheck scripts/verifier.sh` (faux `cypher-shell` : section conforme, puis chaque écart jugé), puis, en lecture sur la base : `command_passes: scripts/verifier.sh --section embeddings; test $? -eq 1`
- [x] **T3.2** : jeton du chargement (plan, D4) : rôle personnalisé `predictionVertex` (`aiplatform.endpoints.predict`) pour `aura-genai`, à la place de `roles/aiplatform.user` (choix de Julien du 2026-10-13) ; fonction de `scripts/commun.sh` qui emprunte le compte (`--lifetime=900`) et passe le jeton par une ligne `:param` sur le stdin de `cypher-shell`, jamais en argument ; `filtrer` le masque dans la sortie et le journal — fait le 2026-10-13 : `cypher_fichier_avec_jeton` (emprunt de 15 minutes, syntaxe du jeton vérifiée, `:param` sur stdin, jamais exporté, masqué par `filtrer`) ; 6 tests écrits d'abord, rouges puis verts ; 8 mutations, toutes détectées ; `predictionVertex` posé et `roles/aiplatform.user` retiré (feu vert de Julien), DoD vérifiée ; journal : par `SORTIE` filtrée, de bout en bout en T5.1 ; précision au plan (D4)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_charger_sh.py && shellcheck scripts/*.sh` (faux `gcloud` qui rend un jeton factice hors du motif `ya29.`, faux `cypher-shell` qui note ses arguments et son stdin : jeton absent des arguments, du journal et de la sortie), puis `command_passes: test "$(gcloud projects get-iam-policy jleroy-labo --flatten='bindings[].members' --filter='bindings.members:serviceAccount:aura-genai@jleroy-labo.iam.gserviceaccount.com' --format='value(bindings.role)')" = "projects/jleroy-labo/roles/predictionVertex"`
- [x] **T3.3** : `scripts/charger.sh --langue` et `--explain` reconnaissent `CREATE VECTOR INDEX` ; RUNBOOK : réindexer, retirer les vecteurs, changer la quantification ou la dimension (`DROP INDEX`), et une reconstruction complète exige Vertex et l'emprunt — fait le 2026-10-13 : expression de `--langue` étendue à `CREATE VECTOR INDEX` ; `--explain` le planifiait déjà (test) ; 2 tests sur une copie du dépôt qui porte l'index de T4.1, 1 mutation détectée ; sur la base, `--langue` inchangé ; RUNBOOK : section « Index vectoriel des descriptions » ; précision au plan (D2)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_charger_sh.py && grep -q 'descriptions_texte' .claude/docs/RUNBOOK.md`

## Phase 4 — Index et fichier d'encodage, sans base (aucune dépense ; NEO-30)

- [x] **T4.1** : `cypher/00-contraintes.cypher` (index `descriptions_texte`, D2) ; `cypher/07-embeddings.cypher` (lots de 100 descriptions sans vecteur, `ai.text.embedBatch`, `task_type: 'RETRIEVAL_DOCUMENT'`, `outputDimensionality: 3072`, `europe-west1`, `$jeton`, vecteur rattaché par `index`, nombre encodé rendu, attente de l'index, D3), testés sur leur texte (clés de configuration, `task_type` en snake_case, aucun littéral de jeton, aucun `CONCURRENT`) — fait le 2026-10-16 : index traduit dans le même commit (`descriptions_text` dans `correspondance.toml`, `schema_francais.py` qui voit `CREATE VECTOR INDEX`, `contraintes.cypher` régénéré ; choix de Julien) ; `07` en une requête (lots de 100, `IN TRANSACTIONS OF 1 ROW`, fournisseur `'vertexai'`, `$jeton` et `$projet` en paramètres, choix de Julien), puis `db.awaitIndex` (600 s) ; 17 tests écrits d'abord, rouges puis verts ; 29 mutations, toutes détectées ; comptes de `--langue` (12 index) et de `--explain` (17 requêtes) à jour, le test de T3.3 sur `--langue` fondu dans celui des deux langues ; suite complète (1 594 tests), ruff, mypy, shellcheck et Prettier verts ; ARCHITECTURE § 5 complétée (ajout daté) ; précisions au plan (D2, D3)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_cypher_embeddings.py && uv run --directory banc pytest -q`

## Phase 5 — Aiguillage du chargement, sans base (aucune dépense ; NEO-30)

- [x] **T5.1** : `scripts/charger.sh` compte les descriptions sans vecteur juste avant `07`, après `06`, et n'emprunte le compte que s'il en reste ; `--idempotence` exige « 0 encodée » au second chargement — fait le 2026-10-16 : `a_encoder` (compte en lecture après `06` ; s'il en reste, emprunt et `07` avec `$jeton` sur stdin et `$projet` par `-P` ; sinon `07` sauté, sans emprunt, et attente des index, choix de Claude) ; `--idempotence` refuse, sans emprunt, un second chargement qui encoderait (quatrième contrôle) ; jeton absent du journal, prouvé de bout en bout ; tests sur une copie du dépôt ; 11 tests (10 écrits d'abord, rouges puis verts ; l'attente des index validée par mutation) ; 15 mutations, toutes détectées ; suite complète (1 605 tests), ruff, mypy, shellcheck verts ; précision au plan (D4), RUNBOOK
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_charger_sh.py` (base entièrement encodée : aucun emprunt ; purge puis chargement : emprunt juste avant `07` ; second chargement qui encoderait encore : refusé)
- [x] **T5.2** : schéma anglais : `embedding` dans `cypher/anglais/correspondance.toml`, l'index traduit avec `00-contraintes.cypher` (`banc anglais`) — précision du 2026-10-16 : l'index est traduit dès T4.1 (plan, D2, choix de Julien) ; reste `embedding` : `[communs]` de la table, `COMMUNS` de `banc/tests/schema_francais.py`, et ARCHITECTURE § 5 (ligne `Description`), où `schema_francais` lit les clés (ajout daté, montré à Julien) — fait le 2026-10-16 : `embedding` commun aux deux langues, ARCHITECTURE § 5 complétée (texte validé par Julien) ; `banc anglais` ne change aucun fichier produit ; 1 test ajouté et 1 compte mis à jour d'abord, rouges puis verts ; 3 mutations, toutes détectées ; suite complète (1 606 tests) verte ; précision au plan (D2)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_correspondance.py tests/test_traduction.py && uv run --directory banc pytest -q`

## Phase 6 — Index sur la base et fiche à jour (environ 0,06 $, feu vert de Julien ; NEO-30)

- [ ] **T6.1** : fiche : la ligne `Description` et la puce « Vecteurs » de D8, telles que Julien les a validées, datées au plan ; requête de la ligne dans `questions/fiche.cypher` ; fiche anglaise régénérée
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_contamination.py tests/test_fiche_cypher.py tests/test_fiche_anglaise.py`, puis, avant le chargement, une seule ligne en écart, celle de `Description` : `command_passes: test "$(scripts/questions.sh --exemples | grep -c '^✗')" -eq 1 && scripts/questions.sh --exemples | grep -q '^✗ Description : nœuds ; propriétés'`
- [ ] **T6.2** : `scripts/verifier.sh --section embeddings` rouge ; chargement complet, qui encode les 5 233 descriptions ; base conforme, fiche comprise
  - DoD : `manual: feu vert de Julien (environ 0,03 $)`, puis `command_passes: scripts/charger.sh --tout && scripts/verifier.sh && scripts/questions.sh --verifier && scripts/questions.sh --exemples`
- [ ] **T6.3** : preuve d'idempotence : la purge recrée les descriptions sans vecteur, le premier chargement emprunte et réencode (environ 0,03 $), le second n'encode rien ; dépense estimée notée au plan, recoupée en T16.3
  - DoD : `command_passes: scripts/charger.sh --idempotence` (IDEMPOTENT)

## Phase 7 — Consigne de contexte et requête de recherche (sans dépense ; NEO-31)

- [ ] **T7.1** : `questions/consigne-contexte.md`, le texte de D8 validé par Julien ; une cellule GraphRAG reçoit cette consigne et la fiche ; empreinte du prompt par technique ; contamination
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_contamination.py tests/test_cellule.py`
- [ ] **T7.2** : `questions/recherche.cypher` (plan, D6), préfixé `CYPHER 25` : `SEARCH` de 60 descriptions, 20 espèces au plus, 2 descriptions chacune, parcours ; jamais `embedding` ni un nœud entier dans le résultat ; contamination (aucune entité ni valeur du banc)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_recherche_cypher.py` (`EXPLAIN` sur la base en T8.2)

## Phase 8 — Encodage des questions et essai de la recherche (environ 0,001 $, feu vert de Julien ; NEO-31)

- [ ] **T8.1** : `banc.encodage` (plan, D5), en TDD : vrai google-genai contre une fausse API Vertex (modèle, `europe-west1`, projet de quota `jleroy-labo`, `RETRIEVAL_QUERY`, 3 072 dimensions, jetons, latence ; un vecteur d'une autre dimension refusé) ; `banc/prix.toml` : `gemini-embedding-001`, voie `vertex-europe-west1`, daté et sourcé (D11)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_encodage.py tests/test_prix.py`
- [ ] **T8.2** : `banc essai-recherche`, sur la vraie base et sans LLM, son code retour portant chaque contrôle : `EXPLAIN` de `recherche.cypher` ; deux phrases maison (hors banc) encodées, cherchées par `read-cypher` (au plus 20 espèces et 2 descriptions chacune, ni vecteur ni nœud entier, taille du contexte et latence relevées) ; preuve de symétrie sur une vraie description (similarité ≥ 0,9999) ; puis estimation du coût refaite au plan sur la taille mesurée
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_essai_recherche.py` (faux serveur), puis `manual: feu vert de Julien (3 encodages)` et `command_passes: uv run --directory banc python -m banc essai-recherche`

## Phase 9 — Cellule GraphRAG : recherche et trace (sans dépense ; NEO-32)

- [ ] **T9.1** : `banc.cellule_graphrag` (plan, D9) : commande avec les vecteurs, connexion au serveur MCP avant le chrono, recherche par `read-cypher` avec `{vecteur}`, trace avec l'empreinte du vecteur à sa place (`banc.mesures`), garde-fou sur la taille du contexte ; faux serveur MCP qui répond à la recherche
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_cellule_graphrag.py tests/test_mesures.py`

## Phase 10 — Cellule GraphRAG : appel au modèle et plafonds (sans dépense ; NEO-32)

- [ ] **T10.1** : ADK sans outil, consigne de contexte et fiche, message = question + contexte, réglages et comptes des cellules ADK du jalon 2 (plan, D7), plafonds et issues comme `banc.cellule_adk` ; vrai ADK contre de fausses API Anthropic et Vertex
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_cellule_graphrag.py && uv run --directory banc pytest -q && uv run --directory banc ruff check && uv run --directory banc mypy .`

## Phase 11 — Seconds tours, isolement et source citée (sans dépense ; NEO-32)

- [ ] **T11.1** : seconds tours dans la même session ADK, la recherche partant du texte du tour (plan, D10) ; isolement des deux cellules (`banc.isolement`)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_cellule_graphrag.py tests/test_isolement.py`
- [ ] **T11.2** : source citée (plan, D9, [ADR-0018](../../adr/0018-mvp-technique-sans-outil.md)), en TDD, pour toutes les techniques : des descriptions citées valent source si, réunies, les enregistrements qui les portent (au tour, ou au tour précédent d'un second tour) contiennent toutes les valeurs de la réponse
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_notation.py` ; la règle désactivée fait échouer son test, qui cite une description dont l'enregistrement ne porte qu'une partie de la réponse

## Phase 12 — Orchestration : campagnes et encodages (sans dépense ; NEO-32)

- [ ] **T12.1** : orchestration : les deux cellules enregistrées ; `campagne.json` format 4 (consigne de contexte, empreinte de la requête de recherche) ; `encodages.json` écrit à la création par `banc.encodage` et relu par `--reprendre`, sans réencoder ; vecteurs dans la commande
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_orchestration.py`

## Phase 13 — Contrôles à la création et répétition générale (environ 0,2 $, feu vert de Julien ; NEO-32)

- [ ] **T13.1** : à la création d'une campagne GraphRAG : `verifier.sh --section embeddings`, lancé sans `ANTHROPIC_*`, et preuve de symétrie ; tous deux sautés en mode faux serveur, comme le contrôle de langue ; résultat de recherche fixe du faux serveur ; bout en bout avec les vraies cellules contre de fausses API
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_orchestration.py && uv run --directory banc pytest -q`
- [ ] **T13.2** : répétition générale : vrais LLM, faux serveur (contexte fixe), rien ne touche Aura ; règle de la source citée relue sur les réponses obtenues
  - DoD : `manual: feu vert de Julien (environ 0,2 $)`, puis `command_passes: scripts/banc.sh lancer --campagne repetition-3 --faux-serveur --cellules graphrag-claude,graphrag-gemini --plafond-usd 1.2 && uv run --directory banc python -m banc rapport --campagne repetition-3 --complet`

## Phase 14 — Pilote et gel (environ 1,5 $, plafond 3,5 $, feu vert de Julien ; NEO-33)

- [ ] **T14.1** : pilote `pilote-3`, une passe des deux cellules, non comptée ; revue du pilote (décisions jamais réutilisées) ; réglages limités à l'extraction, la notation et le coût, notés datés au plan ; estimation de la campagne
  - DoD : `manual: feu vert de Julien`, puis `command_passes: scripts/banc.sh lancer --campagne pilote-3 --cellules graphrag-claude,graphrag-gemini --plafond-usd 3.5 && uv run --directory banc python -m banc rapport --campagne pilote-3 --complet && uv run --directory banc python -m banc revoir --campagne pilote-3 --verifier`
- [ ] **T14.2** : gel du protocole du jalon 3 en tête de `revues.toml` (format de T2.1), son commit noté au plan ; seuils de D12 rappelés ; plafond de la campagne fixé (1,5 × l'estimation + 1 $), au plan
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_revue.py`, puis `manual: gel du jalon 3 dans revues.toml et plafond au plan, relus par Julien`

## Phase 15 — Campagne comptée, passe de contrôle et contrôle des traces (environ 6 $, feu vert de Julien ; NEO-33)

- [ ] **T15.1** : contrôle des traces, en TDD : `banc controle-traces --campagne <id>` (seuls des appels `read-cypher`, aucune clause d'écriture, aucun jeton Google `ya29.`, aucun vecteur dans les paramètres, résultats et contextes) ; `scripts/traces.sh --campagne <id>` cherche l'identifiant de l'instance dans `logs/banc/<campagne>/` et ne rend que des comptes (US1, US4)
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_controle_traces.py tests/test_traces_sh.py && uv run --directory banc python -m banc controle-traces --campagne fr-1 && scripts/traces.sh --campagne fr-1`
- [ ] **T15.2** : campagne `g-1`, 3 passes des deux cellules, puis contrôle de ses traces
  - DoD : `manual: feu vert de Julien (plafond de T14.2)`, puis `command_passes: scripts/banc.sh lancer --campagne g-1 --passes 3 --cellules graphrag-claude,graphrag-gemini --plafond-usd <plafond de T14.2> && uv run --directory banc python -m banc rapport --campagne g-1 --complet && uv run --directory banc python -m banc controle-traces --campagne g-1 && scripts/traces.sh --campagne g-1`
- [ ] **T15.3** : passe de contrôle de la technique 2 (plan, D12, choix de Julien du 2026-10-13) : `adk-claude` et `adk-gemini`, une passe, les mêmes jours que `g-1`, dans les conditions du jalon 3 ; Δ′ et la sortie de [min − 1 ; max + 1] calculés comme D12 les fixe
  - DoD : `manual: feu vert de Julien (environ 1,6 $)`, puis `command_passes: scripts/banc.sh lancer --campagne t2-controle --cellules adk-claude,adk-gemini --plafond-usd 3 && uv run --directory banc python -m banc rapport --campagne t2-controle --complet && uv run --directory banc python -m banc controle-traces --campagne t2-controle`

## Phase 16 — Revue, tables et recoupement (NEO-34 ; T16.3 : NEO-33)

- [ ] **T16.1** : revue assistée ([ADR-0014](../../adr/0014-mvp-revue-assistee.md)) de `g-1` et `t2-controle` : `banc contre-epreuve` (8 cas par campagne, que Julien revoit seul, avant toute proposition) ; pré-analyse scellée (SHA-256 annoncé) ; validation ; taux d'accord et désaccords au plan, chaque désaccord présenté avant d'être enregistré
  - DoD : `command_passes: uv run --directory banc python -m banc revoir --campagne g-1 --verifier && uv run --directory banc python -m banc revoir --campagne t2-controle --verifier`
- [ ] **T16.2** : tables des questions sémantiques (plan, D14) : espèces nouvelles citées dans une réponse, classées avec la grille, accord de Julien, ajoutées datées ; réponses de `fr-1`, `g-1` et `t2-controle` aux questions touchées renotées ; écarts de score au plan, et pour `fr-1` en ajout daté au rapport de la technique 2
  - DoD : `command_passes: scripts/questions.sh --verifier && uv run --directory banc pytest -q tests/test_banc_toml.py tests/test_attendu.py && uv run --directory banc python -m banc revoir --campagne fr-1 --verifier && uv run --directory banc python -m banc revoir --campagne g-1 --verifier && uv run --directory banc python -m banc revoir --campagne t2-controle --verifier`, puis `manual: écarts de renotation relus par Julien`
- [ ] **T16.3** : recoupement des coûts : Console Anthropic (jours UTC) ; export de facturation BigQuery heure par heure (Gemini, encodages, chargements de la phase 6 : unité de facturation de l'embedding tranchée) ; écarts au plan
  - DoD : `manual: écarts sous 1 centime, ou expliqués au plan`

## Phase 17 — Recherche seule (US2 ; NEO-35)

- [ ] **T17.1** : `banc.recherche_seule` (plan, D13), en TDD, puis la mesure sur les traces de `g-1` : tables lues au commit du gel, plafond min(20, grille) par question, recherche identique d'une trace à l'autre (empreinte du résultat) ; espèces retrouvées hors du filet classées avec la grille (pré-classement de Claude, accord de Julien), consignées dans le résultat d'US2
  - DoD : `command_passes: uv run --directory banc pytest -q tests/test_recherche_seule.py && uv run --directory banc python -m banc recherche-seule --campagne g-1`, puis `manual: classement des espèces hors filet validé par Julien`

## Phase 18 — Rapport et livraison (NEO-35)

- [ ] **T18.1** : rapport `banc/resultats/technique-3.md` : scores par cellule et par catégorie, écart entre passes, technique 3 contre technique 2 à modèle égal (Δ contre `fr-1`, Δ′ contre `t2-controle`, seuils de D12), recherche seule, sources (règle de l'ADR-0018 ; colonne source de `fr-1` relue avec elle, en ajout daté au rapport de la technique 2), coût, latence de l'encodage à côté du temps, effort
  - DoD : `command_passes: uv run --directory banc python -m banc rapport --campagne g-1 --complet`, `file_exists: banc/resultats/technique-3.md`, puis `manual: Julien relit le rapport`
- [ ] **T18.2** : doc : code-map (règles de couplage du jeton, de l'encodage, de la recherche, de `scripts/traces.sh`), stack, ARCHITECTURE § 8, ACCESS (`aura-genai`, `predictionVertex`), RUNBOOK, README
  - DoD : `command_passes: python3 .claude/skills/doc-health/scripts/context-budget.py`
- [ ] **T18.3** : `/feature-done` : critères de la [spec](spec.md) cochés, ROADMAP, CHANGELOG, dernière PR, tag `jalon-3`
  - DoD : `command_passes: git describe --tags --exact-match origin/main` (rend `jalon-3`, après la fusion)

## Definition of Done (global)

La feature est livrée quand :

- [ ] Tous les critères d'acceptation de [spec.md](spec.md) cochés
- [ ] Tests verts (unitaires, intégration sans base, contrôles sur la base), ruff, mypy, shellcheck, Prettier
- [ ] Pas de TODO ou `# FIXME` dans le code
- [ ] Pas de fuite : gitleaks sur l'historique ; `banc controle-traces` et `scripts/traces.sh` conformes sur `g-1` et `t2-controle` (aucun jeton Google, aucun vecteur, aucun identifiant de l'instance)
- [ ] Base de référence intacte : `verifier.sh` (sections du jalon 2 et `embeddings`), `questions.sh --verifier` et `--exemples` conformes
- [ ] Documentation à jour (code-map, plan.md décisions)
- [ ] ADR créés avec la PR de conception : [0018](../../adr/0018-mvp-technique-sans-outil.md), [0019](../../adr/0019-infra-jeton-vertex-du-plugin-genai.md), [0020](../../adr/0020-mvp-index-vectoriel-des-descriptions.md)
- [ ] Commit + PR, une par phase ; tag `jalon-3`

## Blockers / questions

- Clé Anthropic du banc : elle expire le 2026-11-07 ; T2.2 avant le pilote.
- Budget Vertex de 100 € jusqu'au 2026-12-31 (NEO-27, début décembre) : les campagnes du jalon 3 s'y tiennent.
- Unité de facturation de `gemini-embedding-001` (« per 1,000 count » : jetons ou caractères) : tranchée par l'export de facturation (T16.3) ; moins de 0,30 $ par indexation dans tous les cas.
- Dimension des questions d'Aura Agent (jalon 4), inconnue : l'index en 3 072 vise son défaut ; à vérifier au jalon 4.
