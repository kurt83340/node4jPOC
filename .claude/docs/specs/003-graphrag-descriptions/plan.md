# Plan — GraphRAG sur les descriptions

> COMMENT on implémente la feature `003-graphrag-descriptions`.

**Date :** 2026-10-12
**Option retenue :** A′ ([research § Décision](research.md)), choix de Julien du 2026-10-12 ; corrigé après la revue adverse et sa contre-vérification ([research § Revue adverse](research.md)) ; plan validé par Julien le 2026-10-13

## Approche technique

Les descriptions sont encodées une fois, au chargement, par le plugin GenAI d'Aura (`ai.text.embedBatch`, `gemini-embedding-001`, 3 072 dimensions, `europe-west1`), dans un fichier `cypher/07-embeddings.cypher` lancé par `scripts/charger.sh` : le chargement reste en Cypher pur ([ADR-0003](../../adr/0003-mvp-chargement-cypher-pur.md)), avec le jeton éphémère d'un compte de service limité à la prédiction. Un index vectoriel `descriptions_texte` les sert. À la création d'une campagne, le harnais encode les messages posés (google-genai, même modèle, `RETRIEVAL_QUERY`). Pour chaque question, une cellule GraphRAG (ADK sans outil, Claude Sonnet 5.5 ou Gemini 3.8 Flash) lance la requête de recherche `questions/recherche.cypher` par `read-cypher`, le vecteur en paramètre : `SEARCH` dans l'index, regroupement par espèce, parcours du graphe autour de chaque espèce ; le résultat devient le contexte du seul appel au LLM, qui rédige la réponse. Le reste est le banc du jalon 2 : chemin unique en lecture seule, trace, notation, pilote, 3 passes comptées, revue assistée avec contre-épreuve ([ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md) et ses précisions), plus les précisions d'une technique sans outil (D5, D8, D9, [ADR-0018](../../adr/0018-mvp-technique-sans-outil.md)).

## Architecture

```
CHARGEMENT (une fois, puis à chaque rechargement)
scripts/charger.sh ─ secret Aura (Secret Manager) ─► cypher-shell ─► 00 à 06, puis 07 :
  ├─ 00-contraintes.cypher : index vectoriel descriptions_texte (3 072, cosine, sans quantification)
  └─ 07-embeddings.cypher  : compte fait juste avant 07, après 06 ; s'il reste des descriptions sans
                             vecteur, jeton aura-genai (emprunt, 15 min, rôle « prédiction » seul) par :param ;
                             ai.text.embedBatch par lots de 100 ─► Vertex europe-west1
                             (gemini-embedding-001, RETRIEVAL_DOCUMENT) ─► SET d.embedding (VECTOR)

CAMPAGNE
banc lancer ─ création : verifier.sh --section embeddings (index complet) ; chaque message posé encodé
              par google-genai (ADC de Julien, projet jleroy-labo, europe-west1, RETRIEVAL_QUERY, 3 072)
              ─► logs/banc/<campagne>/encodages.json (vecteurs, jetons, latence) ; preuve de symétrie
              sur une description (vecteur stocké contre google-genai, similarité ≥ 0,9999)
  └─ par conversation, alternées : cellule graphrag-claude (clé Anthropic, aucune variable Vertex)
                                   cellule graphrag-gemini (ADC Vertex eu, aucune clé Anthropic)
       1. read-cypher(recherche.cypher, {vecteur}) ─► scripts/mcp-neo4j.sh ─► neo4j-mcp ─► AuraDB Free
          SEARCH (60 descriptions) → espèces (≤ 20) → types, talents, statistiques, évolutions, descriptions
       2. ADK, aucun outil : consigne de contexte + fiche, message = question + contexte (JSON du résultat)
          ─► Claude (API Anthropic) ou Gemini (Vertex eu) : un appel, « Réponse » et « Sources »
       3. trace (appel read-cypher, empreinte du vecteur, résultat, tokens) ─► notation, revue, CSV
```

## Modules / fichiers impactés

| Fichier                                                                                         | Action         | Notes                                                                                                                                                                                                                                                                       |
| ----------------------------------------------------------------------------------------------- | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `cypher/00-contraintes.cypher`                                                                  | modif          | index vectoriel `descriptions_texte`, créé avant les données ; recréé par `--schema` (D2)                                                                                                                                                                                   |
| `cypher/07-embeddings.cypher`                                                                   | nouveau        | lots de `ai.text.embedBatch`, descriptions sans vecteur seulement, vecteur rattaché par `index` ; rend le nombre encodé (D3)                                                                                                                                                |
| `cypher/90-verification.cypher`, `scripts/verifier.sh`                                          | modif          | section `embeddings` (liste `SECTIONS`) : 5 233 vecteurs de 3 072 dimensions, index en ligne avec ses options (D3)                                                                                                                                                          |
| `scripts/commun.sh`, `scripts/charger.sh`                                                       | modif          | jeton `aura-genai` emprunté (15 min) juste avant `07`, seulement s'il reste des descriptions sans vecteur, passé sur stdin au seul `07`, masqué ; `--idempotence` exige « 0 encodée » au second chargement ; `--langue` et `--explain` voient les index vectoriels (D3, D4) |
| `cypher/anglais/correspondance.toml`, `cypher/anglais/`                                         | modif          | `embedding` parmi les noms communs ; l'index traduit avec `00-contraintes.cypher` (`banc anglais`)                                                                                                                                                                          |
| `questions/fiche-schema.md`, `fiche.cypher`, `fiche-schema.en.md`                               | modif          | `embedding` sur la ligne `Description` et puce « Vecteurs » dans « Règles », textes validés (D8) ; requête de la ligne mise à jour ; fiche anglaise régénérée                                                                                                               |
| `questions/consigne-contexte.md`                                                                | nouveau        | consigne d'une technique sans outil, texte validé (D8, ADR)                                                                                                                                                                                                                 |
| `questions/recherche.cypher`                                                                    | nouveau        | requête de recherche de la technique 3, `CYPHER 25`, testée contre la contamination (D6)                                                                                                                                                                                    |
| `banc/src/banc/contre_epreuve.py`, gabarit HTML, `__main__.py`                                  | nouveau, modif | `banc contre-epreuve` : tirage, page à l'aveugle, taux d'accord (D15)                                                                                                                                                                                                       |
| `banc/src/banc/revue.py`                                                                        | modif          | un gel et un pilote par jalon ; l'ancien en-tête lu tel quel ; réutilisation des décisions (D15)                                                                                                                                                                            |
| `banc/src/banc/encodage.py`                                                                     | nouveau        | encodage des messages d'une campagne, jetons, latence, preuve de symétrie (D5)                                                                                                                                                                                              |
| `banc/src/banc/essai_recherche.py`, `__main__.py`                                               | nouveau, modif | `banc essai-recherche` : `EXPLAIN`, deux phrases maison, forme et taille du contexte, symétrie (D6)                                                                                                                                                                         |
| `banc/src/banc/cellule_graphrag.py`                                                             | nouveau        | cellule ADK sans outil, recherche par `read-cypher` avant l'appel (D7, D9, D10)                                                                                                                                                                                             |
| `banc/src/banc/orchestration.py`, `cellule.py`, `isolement.py`, `mesures.py`, `faux_serveur.py` | modif          | deux cellules ; `campagne.json` format 4 ; vecteurs dans la commande ; index vérifié avant la campagne ; empreinte du vecteur dans la trace ; résultat de recherche fixe du faux serveur (D9, D11)                                                                          |
| `banc/src/banc/notation.py`                                                                     | modif          | source citée d'une technique sans outil (D9, ADR)                                                                                                                                                                                                                           |
| `banc/src/banc/controle_traces.py`, `__main__.py`                                               | nouveau, modif | `banc controle-traces` : lectures seules, aucune clause d'écriture, aucun jeton Google, aucun vecteur (US1, US4)                                                                                                                                                            |
| `scripts/traces.sh`                                                                             | nouveau        | identifiant de l'instance cherché dans `logs/banc/<campagne>/`, comptes seuls, jamais la valeur (code-map : `banc/` ne voit jamais l'identifiant)                                                                                                                           |
| `banc/src/banc/recherche_seule.py`, `rapport.py`                                                | nouveau, modif | mesure de la recherche seule (US2) sur les traces ; rapport de la technique 3 (D13)                                                                                                                                                                                         |
| `banc/prix.toml`                                                                                | modif          | tarif daté de `gemini-embedding-001`, voie `vertex-europe-west1` (D11)                                                                                                                                                                                                      |
| `banc/tests/`                                                                                   | nouveau, modif | un test par comportement ; vrai ADK et vrai google-genai contre de fausses API ; faux `gcloud` et `cypher-shell` (rule `testing`)                                                                                                                                           |
| `.claude/docs/adr/`                                                                             | nouveau        | [ADR-0018](../../adr/0018-mvp-technique-sans-outil.md) (D5, D8, D9), [ADR-0019](../../adr/0019-infra-jeton-vertex-du-plugin-genai.md) (D4), [ADR-0020](../../adr/0020-mvp-index-vectoriel-des-descriptions.md) (D2)                                                         |
| `.claude/docs/RUNBOOK.md`                                                                       | modif          | dès la phase 3 : réindexer, retirer les vecteurs, changer la quantification (`DROP INDEX`)                                                                                                                                                                                  |
| doc                                                                                             | modif          | code-map (couplage), stack, ARCHITECTURE § 8, ACCESS (`aura-genai`), README, ROADMAP                                                                                                                                                                                        |

## Flux de données (une conversation)

1. À la création de la campagne : `verifier.sh --section embeddings` doit passer (un index incomplet amputerait la recherche sans bruit) ; chaque message posé (question, préambule de Q2 compris) est encodé ; `encodages.json` garde, par message, son empreinte, le vecteur, les jetons et la latence ; une description encodée par google-genai est comparée à son vecteur stocké ; `--reprendre` relit le fichier, sans réencoder.
2. L'orchestration lance la cellule (liste blanche, dossier neuf hors du dépôt) avec sa commande : questions, vecteurs, plafonds, empreinte du prompt et de la requête de recherche.
3. Avant le chrono : connexion au serveur MCP (comme au jalon 2) et au modèle.
4. Chrono à l'horloge monotone : `read-cypher` avec `recherche.cypher` et `{vecteur}` ; garde-fou sur la taille du résultat ; message = question + contexte ; un appel au LLM ; réponse finale.
5. Trace : l'appel `read-cypher` (requête, paramètres avec l'empreinte du vecteur à sa place), son résultat tel que le LLM l'a reçu, les tokens, la durée.
6. Second tour (Q18, Q28) : même session ADK ; la recherche part du texte du tour ; l'historique garde le message précédent, son contexte et sa réponse.
7. Notation (source citée selon D9), revue, CSV : comme au jalon 2 ; l'encodage des questions se compte par campagne, sa latence se rapporte à côté du temps (D11).

## Erreurs / cas limites

| Cas                                                              | Comportement attendu                                                                      |
| ---------------------------------------------------------------- | ----------------------------------------------------------------------------------------- |
| Vertex refuse un lot du chargement (taille, 429)                 | arrêt au fichier `07` (code 2) ; relance : seules les descriptions sans vecteur repartent |
| Jeton expiré pendant le chargement                               | arrêt ; la relance prend un nouveau jeton et reprend où le chargement s'est arrêté        |
| Plus rien à encoder (rechargement sans purge)                    | aucun jeton pris : le rechargement marche même Vertex coupé                               |
| Reconstruction (purge puis chargement, ou `--idempotence`)       | `06` recrée 5 233 descriptions sans vecteur : jeton pris, tout se réencode ; Vertex exigé |
| Index en POPULATING après le chargement                          | `07` attend l'index (`db.awaitIndex`) ; `verifier.sh` le veut ONLINE                      |
| Index incomplet (chargement interrompu)                          | `banc lancer` refuse une campagne GraphRAG (`verifier.sh --section embeddings`)           |
| Encodage ou preuve de symétrie en échec à la création            | erreur technique : la campagne ne démarre pas, rien n'est dépensé côté LLM                |
| `read-cypher` en erreur ou serveur perdu                         | panne, conversation rejouée (ADR-0017)                                                    |
| Contexte trop gros pour le budget                                | échec « budget » avant l'appel, comme le garde-fou d'un résultat d'outil (ADR-0017)       |
| La recherche ne ramène rien d'utile, second tour elliptique      | mesuré tel quel : rien n'est corrigé                                                      |
| Crédits Anthropic, limite de l'organisation ou coupure de Vertex | arrêt de la campagne, question à Julien (ADR-0010, 0016)                                  |

## Décisions (locales à cette feature)

> Le protocole du banc ([ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md), précisé par les ADR-0012, 0014, 0015 et 0017) vaut tel quel ; les précisions propres à une technique sans outil (D5, D8, D9) passent par l'[ADR-0018](../../adr/0018-mvp-technique-sans-outil.md), qui précise l'ADR-0009.

### D1 — Architecture A′

**Choix :** plugin GenAI au chargement, question encodée par le harnais, recherche par `read-cypher` avec le vecteur en paramètre (Julien, 2026-10-12, sur la préférence de Claude).
**Pourquoi :** les ADR-0003, 0007 et 0009 et les règles de couplage tiennent ; tout ce que le jalon 2 a prouvé sert tel quel ; l'encodage des questions se mesure ; le plugin et google-genai rendent le même vecteur à type de tâche égal (test payant du 2026-10-12, [research](research.md)).
**Alternatives écartées :** A (jeton Google à chaque question, dans la trace et dans Aura), B (`neo4j-graphrag` : identifiants dans le harnais, procédures dépréciées sur « 5.27-aura »), C (contraire à l'ADR-0003).

### D2 — Index vectoriel

**Choix :** `CREATE VECTOR INDEX descriptions_texte IF NOT EXISTS FOR (d:Description) ON d.embedding`, avec `vector.dimensions` 3 072 (Julien, 2026-10-12), `vector.similarity_function` `cosine`, `vector.quantization.type` `none` (choix délégué par Julien) ; dans `00-contraintes.cypher`, avant les données, pour que `--schema` le recrée ; `scripts/charger.sh --langue` et `--explain` reconnaissent `CREATE VECTOR INDEX` (leur expression ne voit aujourd'hui que les index plein texte, `charger.sh:346`).
**Pourquoi :** 3 072 est la dimension par défaut du modèle, la seule qu'Aura Agent servira à coup sûr au jalon 4 (aucun réglage de dimension de son côté) ; `cosine` ne dépend pas de la norme (les vecteurs de 3 072 dimensions sont normalisés, ceux qu'on réduit ne le sont pas : normes 0,59 en 768 au test) ; sans quantification : le défaut est passé de `scalar` à `binary` en 2026.08 et rogne le rappel, alors que 5 233 vecteurs ne pèsent que 64 Mo.
**Retour arrière :** changer la quantification ou la dimension exige `DROP INDEX descriptions_texte` (`IF NOT EXISTS` garderait l'ancien sans rien dire) ; retirer les vecteurs, `REMOVE d.embedding` par lots ; tous deux au RUNBOOK dès la phase 3.
**Alternatives écartées :** 768 ou 1 536 dimensions (réindexation probable au jalon 4) ; quantification `scalar` (gardée en repli, circuit breaker).
**ADR :** l'index lie aussi le jalon 4 : [ADR-0020](../../adr/0020-mvp-index-vectoriel-des-descriptions.md) (Julien, 2026-10-13).

### D3 — Embeddings au chargement

**Choix :** `cypher/07-embeddings.cypher` compte d'abord les descriptions sans `embedding` ; s'il en reste, il les prend par lots de 100 (`UNWIND range(…)` puis `CALL … IN TRANSACTIONS OF 1 ROW`, sans `CONCURRENT`), appelle `ai.text.embedBatch` avec `{model: 'gemini-embedding-001', project: 'jleroy-labo', region: 'europe-west1', token: $jeton, vendorOptions: {task_type: 'RETRIEVAL_DOCUMENT', outputDimensionality: 3072}}`, rattache chaque vecteur à son nœud par l'`index` rendu (jamais par le texte : celui des six Ultra-Chimères est en double), écrit `SET d.embedding = vector`, puis rend le nombre encodé et attend l'index. Les doublons restent : le texte commun aux six Ultra-Chimères est encodé six fois (choix délégué par Julien).
**Pourquoi :** relancer n'encode que ce qui manque (idempotence, sans repayer) ; `task_type` en snake_case, le seul que le plugin transmet (`taskType` est ignoré sans erreur, test payant) ; des lots séquentiels évitent les 429 ; 100 textes font environ 3 300 jetons, loin des 250 textes et 20 000 jetons d'une requête ; les doublons ne coûtent que 5 vecteurs, et la recherche regroupe par espèce (D6), où les six espèces arrivent ensemble à bon droit.
**Jeton au bon moment :** `charger.sh` compte les descriptions sans vecteur juste avant `07`, après `06` : une purge suivie d'un chargement en recrée 5 233, que `07` doit encoder (D4).
**Vérification d'abord :** la section `embeddings` de `verifier.sh` s'écrit avant `07`, rouge sur la base actuelle (méthode du plan 001, D8) : 5 233 descriptions à vecteur, toutes de 3 072 dimensions (`vector_dimension_count`), index ONLINE avec ses options. Chaque preuve d'idempotence repaie un encodage complet (environ 0,03 $), puisqu'elle commence par une purge : on n'en fait qu'une par changement du chargement.

### D4 — Jeton du chargement

**Choix :** le compte de service `aura-genai@jleroy-labo.iam.gserviceaccount.com` (créé le 2026-10-12 pour le test payant, choix de Julien), emprunté par Julien (`roles/iam.serviceAccountTokenCreator` sur ce seul compte). `scripts/charger.sh` prend le jeton juste avant `07`, après `06`, et seulement s'il reste des descriptions sans vecteur : `gcloud auth print-access-token --impersonate-service-account=… --lifetime=900` (fonction de `scripts/commun.sh`). Il le passe au seul `07` par une ligne `:param` sur le stdin de `cypher-shell`, jamais en argument ; `filtrer` le masque dans toute sortie et dans le journal. Le rôle `roles/aiplatform.user`, posé pour le test, est remplacé par un rôle personnalisé `predictionVertex` limité à la prédiction (`aiplatform.endpoints.predict`, permise dans un rôle personnalisé, `gcloud iam list-testable-permissions` du 2026-10-13 ; `roles/aiplatform.user` en compte 459), comme le rôle `coupureVertex` de l'ADR-0013 ; jeton de 15 minutes (Julien, 2026-10-13, sur la préférence de Claude). L'[ADR-0019](../../adr/0019-infra-jeton-vertex-du-plugin-genai.md) précise l'[ADR-0007](../../adr/0007-infra-secrets-et-services-geres.md).
**Constat du 2026-10-12 :** `cypher-shell` 2026.09.0 évalue `:param` côté serveur (`:param {t: datetime()}` rend l'heure du serveur ; `-P` fait de même, en argument en plus) : le jeton arrive chez Aura comme littéral d'une requête `RETURN`, hors du masquage que le plugin applique à sa configuration. D'où un jeton de 15 minutes, qui ne vaut que pour la prédiction ; risque restant écrit dans l'ADR.
**Pourquoi :** aucune cellule ni le harnais ne reçoivent ce jeton ; ce qu'il ouvre et sa durée bornent ce que coûterait une fuite chez Aura.
**Alternatives écartées :** le jeton de Julien (tous ses droits Google) ; une `apiKey` Vertex (sans échéance) ; l'API Query d'Aura (`curl`), où le jeton serait un vrai paramètre, mais une requête de plusieurs minutes en HTTP et un client de plus pour le chargement.

### D5 — Encodage des questions

**Choix :** à la création d'une campagne, `banc.encodage` encode chaque message posé avec google-genai (`gemini-embedding-001`, `europe-west1`, `RETRIEVAL_QUERY`, 3 072, ADC de Julien comme la cellule Gemini, projet de quota `jleroy-labo` fixé, celui de l'ADC du poste étant `jleroy-outils`) ; `logs/banc/<campagne>/encodages.json` garde vecteur, jetons et latence par message ; les cellules reçoivent leurs vecteurs dans la commande ; une description lue par `read-cypher`, encodée en `RETRIEVAL_DOCUMENT`, est comparée à son vecteur stocké (similarité ≥ 0,9999, sinon la campagne ne démarre pas : le modèle aurait dérivé) ; en mode faux serveur, rien ne touche Aura : la vérification de l'index et la preuve de symétrie sont sautées, comme le contrôle de langue (`moyens_faux_serveur`, `orchestration.py:654`) ; `verifier.sh` se lance sans `ANTHROPIC_*`, comme `transactions.sh` (choix délégué par Julien).
**Pourquoi :** la règle d'isolement interdit Vertex dans la cellule Claude ; un message donne toujours le même vecteur ; le coût (une trentaine d'encodages par campagne, moins de 0,001 $) et la latence se mesurent à part.
**Écart au protocole, réglé par l'[ADR-0018](../../adr/0018-mvp-technique-sans-outil.md) :** le temps de réponse mesuré exclut l'encodage de la question ; le rapport et le tableau comparatif donnent sa latence médiane à côté du temps, qu'Aura Agent comptera, lui, dans le sien au jalon 4.
**Alternatives écartées :** un encodeur par conversation, dans le chrono (un processus de plus, deux voies de prix par conversation) ; l'encodage dans la cellule (règle d'isolement) ; le plugin à chaque question (option A).

### D6 — Recherche et parcours

**Choix :** recherche vectorielle seule (Julien, 2026-10-12). `questions/recherche.cypher`, préfixé `CYPHER 25` : `SEARCH d IN (VECTOR INDEX descriptions_texte FOR $vecteur LIMIT 60) SCORE AS score` ; regroupement par espèce (`A_POUR_DESCRIPTION`), classées par meilleur score, 20 au plus, chacune avec ses 2 meilleures descriptions (`texte`, `jeux`, score) ; parcours : nom, catégorie, types de la forme par défaut (par `rang`), talents (caché ou non), les 6 statistiques, espèce d'origine et évolutions directes. Jamais `embedding`, jamais un nœud entier. Fixé avant le pilote (choix délégué par Julien).
**Pourquoi :** une espèce a 5,1 descriptions en moyenne (5 233 pour 1 025), souvent proches d'un jeu à l'autre : sans regroupement, quelques espèces rempliraient le contexte. Ces valeurs viennent des données, pas des questions du banc ([ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md)).
**Taille du contexte :** de 4 000 à 6 000 jetons selon l'estimation (la revue adverse compte 18 000 caractères de JSON pour 20 espèces) ; `banc essai-recherche` la mesure sur deux phrases maison, et l'estimation du coût est refaite avant le feu vert du pilote.
**Alternatives écartées :** hybride vecteur + plein texte `french` (WRRF) : la méthode officielle, mais elle mêle mots et sens (Julien) ; un contexte de passages sans regroupement.

### D7 — Cellules

**Choix :** deux cellules (Julien, 2026-10-12) : `graphrag-claude` (Claude Sonnet 5.5 par l'API Anthropic) et `graphrag-gemini` (Gemini 3.8 Flash sur Vertex `eu`), dans ADK sans outil, avec les réglages des cellules ADK du jalon 2 (effort `high`, `max_tokens` 128 000, réflexion adaptative ; `thinking_level` HIGH ; cache de 5 min ; 2 reprises) ; plafonds de l'[ADR-0017](../../adr/0017-mvp-precisions-protocole-mesure.md) ; alternées conversation par conversation.
**Pourquoi :** même client et même modèle que `adk-claude` et `adk-gemini` : l'écart avec la technique 2 tient à la technique ; deux modèles donnent l'effet du modèle.
**Alternatives écartées :** une seule cellule (moins cher, sans comparaison à modèle égal ou sans effet du modèle) ; le SDK du modèle sans ADK (un client de plus à comparer).

### D8 — Consigne et fiche

**Choix :** la fiche reste commune ; la consigne d'une technique sans outil est `questions/consigne-contexte.md`, précision de l'[ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md) (« même entrée ») par l'[ADR-0018](../../adr/0018-mvp-technique-sans-outil.md), comme l'avait fait l'ADR-0017. Textes validés par Julien le 2026-10-13, sur la proposition de Claude (ajouts datés au plan à leur entrée dans la fiche) :

- `questions/consigne-contexte.md` (la consigne commune, sans ce qui parle de l'outil) :

  > Tu réponds en français à des questions sur les Pokémon. Ta seule source est un graphe Neo4j, décrit par la fiche de schéma qui suit : chaque question arrive avec le résultat d'une recherche dans ce graphe, le contexte.
  >
  > - Ta réponse vient de ce contexte, pas de ta mémoire.
  > - Termine toujours par ces deux sections :
  >   - **Réponse :** la réponse courte, avec les noms et les valeurs demandés, et la raison quand la question en demande une ;
  >   - **Sources :** les descriptions citées, avec leurs jeux.

- `questions/fiche-schema.md`, ligne `Description` de « Nœuds », complétée (ajout en fin de ligne) :

  > - `Description` : un texte de description d'une espèce (5 233) ; propriétés `texte` et `jeux`, les jeux où il paraît ; `embedding`, le vecteur de son texte (voir les règles).

- `questions/fiche-schema.md`, une puce de plus à la fin de « Règles » :

  > - **Vecteurs** : ne renvoie jamais un nœud `Description` entier ni sa propriété `embedding`, qui compte des milliers de nombres ; demande `texte` et `jeux`.

**Pourquoi :** la consigne commune parle de l'outil `read-cypher` et dit d'interroger « autant de fois qu'il le faut » ; un LLM sans outil recevrait une consigne fausse. `questions/fiche.cypher` prouve sur la base la liste des propriétés de `Description` (`keys(n)` contre `['jeux', 'texte']`, l. 129-147) : une fois les vecteurs chargés, la ligne de « Nœuds » doit les nommer, et sa requête suit. La puce protège les techniques qui écrivent du Cypher (jalon 4) ; « des milliers » reste vrai sans recopier un chiffre que `fiche.cypher` devrait prouver. Ni la consigne ni les ajouts ne soufflent une question (Q10, Q29, Q30 : rien sur l'honnêteté, les prémisses, les questions vagues) ; tests de contamination étendus à la consigne et à `recherche.cypher`. Le seul exemple de la fiche qui touche `Description` (Tropius) ne renvoie que `texte` et `jeux`.
**Ordre :** la fiche change avec le chargement (phase 6) : `questions.sh --exemples` reste rouge entre les deux, vérification d'abord. La fiche anglaise se régénère ; l'empreinte du prompt de la technique 2 change (ses campagnes sont closes).

### D9 — Trace et source citée

**Choix :** la recherche s'écrit dans la trace comme un appel `read-cypher` (requête, paramètres, résultat) ; à la place du vecteur, ses paramètres portent son empreinte (`sha256:…`, 3 072 dimensions). Le garde-fou de l'ADR-0017 s'applique au contexte avant l'appel. Source citée, tranchée par Julien le 2026-10-13 (sur la préférence de Claude) et écrite dans l'[ADR-0018](../../adr/0018-mvp-technique-sans-outil.md) :

- constat de la revue adverse : `banc.notation` valide une description citée si l'enregistrement qui la porte contient une valeur juste (`any`, `notation.py:462-494`), alors qu'une requête citée doit porter toutes les valeurs (`all`) ; avec un enregistrement par espèce (D6), citer n'importe quelle description de la bonne espèce validerait tout fait sur elle ;
- règle retenue : des descriptions citées valent source si, réunies, les enregistrements qui les portent (une espèce par enregistrement dans le contexte de la technique 3) contiennent toutes les valeurs de la réponse (la règle `all` des requêtes, appliquée à ce qui est cité) ; au second tour, les lectures du tour précédent comptent ([ADR-0015](../../adr/0015-mvp-source-du-tour-precedent.md)) ; contrôlée sur les réponses de la répétition générale ;
- même règle pour toutes les techniques dans le tableau (constat de la contre-vérification : appliquée à la seule technique 3, elle la désavantagerait sur Q9, Q17 et Q26, où une seule description suffisait à la technique 2) : la colonne source de `fr-1` est relue avec elle, depuis les traces, ajout daté au rapport de la technique 2 ; les scores n'en dépendent pas ; `t2-controle` est noté directement avec elle ;
- résidu assumé, dit dans le rapport : pour une réponse à une seule valeur, une description quelconque de la bonne espèce suffit encore ;
- alternatives écartées : une description par enregistrement, les faits du graphe à part (un fait du graphe n'aurait alors aucune source citable) ; déclarer le critère « sources » de la technique 3 non comparable.

**Pourquoi :** la trace et la notation du jalon 2 servent ; un vecteur de 3 072 nombres alourdirait chaque trace sans rien apprendre ; une règle de source plus lâche que celle de la technique 2 fausserait le tableau.

### D10 — Seconds tours

**Choix :** même session ADK ; la recherche part du texte du tour, sans réécriture par l'historique ; l'historique garde le message précédent, son contexte et sa réponse.
**Pourquoi :** c'est le GraphRAG simple que mesure le jalon ; une réécriture de la question serait une autre technique. Q18 et Q28 restent mesurées telles quelles ([ADR-0012](../../adr/0012-mvp-second-tour-apres-echec.md)).

### D11 — Mesures et coût

**Choix :** colonnes du CSV inchangées : la durée est celle du chrono, le coût d'une ligne celui du LLM ; l'encodage des questions se compte par campagne (jetons rendus par Vertex × tarif) et sa latence médiane se rapporte à côté du temps (D5, ADR) ; le chargement s'estime (caractères ÷ 3,85, ratio du test payant) puis se recoupe dans l'export de facturation BigQuery. `banc/prix.toml` reçoit `gemini-embedding-001`, voie `vertex-europe-west1`, 0,15 $ par million, daté et sourcé (unité à confirmer à la facture).
**Pourquoi :** un modèle sans tarif arrête la mesure ; une seule voie de prix par conversation reste la règle du code.

### D12 — Pilote, gel, campagne, seuils

**Choix :** pilote `pilote-3` (une passe des deux cellules, non comptée, plafond 3,5 $), qui ne règle que l'extraction, la notation et le coût ; gel du protocole du jalon 3, en tête de `revues.toml` dans un format étendu (un gel et un pilote par jalon, l'ancien en-tête lu tel quel) ; campagne `g-1` (3 passes, plafond = 1,5 × l'estimation tirée du pilote + 1 $).
**Seuils, fixés ici avant la mesure** : le score d'une passe est le nombre de justes plus la moitié des partielles, sur 30 ; à modèle égal (`graphrag-claude` contre `adk-claude`, `graphrag-gemini` contre `adk-gemini` de `fr-1`), Δ = moyenne des 3 passes de la technique 3 moins celle de la technique 2 ; R = le plus grand des deux bruits (écart entre la meilleure et la moins bonne passe de chaque technique) ; un effet compte si |Δ| ≥ max(2, R) (règle du FR/EN, plan 002, D8).
**Passe de contrôle de la technique 2** (Julien, 2026-10-13, sur la préférence de Claude) : `adk-claude` et `adk-gemini`, une passe, environ 1,6 $, les mêmes jours que `g-1`. Elle mesure la technique 2 dans les conditions du jalon 3 : modèles du jour, fiche complétée (D8), base qui porte des vecteurs ; elle ne sépare pas ces effets. Écrit avant la mesure : Δ′ = moyenne des 3 passes de la technique 3 moins le score de la passe de contrôle, à modèle égal ; un effet compte si |Δ′| ≥ max(2, R), avec le même R ; la passe sort de la technique 2 de `fr-1` si son score tombe hors de [min − 1 ; max + 1] de ses passes. Lecture : si Δ et Δ′ concluent pareil, l'effet tient ; sinon, le rapport donne les deux, sans trancher. Alternative écartée : une passe avec la fiche de `fr-1`, sur une base qui porte des vecteurs (une condition qui n'existe plus).
**Pourquoi :** la méthode du jalon 2, rejouée ; un seuil choisi après coup ne vaudrait rien.

### D13 — Recherche seule (US2)

**Choix :** pour Q3, Q9, Q16, Q17 et Q26, sur les traces de `g-1` : part des espèces obligatoires et acceptables de chaque grille ([ADR-0008](../../adr/0008-mvp-notation-questions-semantiques.md)) présentes parmi les espèces retrouvées, avec le plafond de chaque question, min(20, taille de la grille) (Q9 compte 26 espèces obligatoires et acceptables : 77 % au plus) ; espèces retrouvées hors du filet de mots-clés de la requête de référence, classées avec la grille (pré-classement de Claude, accord de Julien), consignées dans le résultat d'US2 sans toucher aux tables. Tables lues telles qu'au commit du gel du jalon 3 (`git show <commit>:questions/attendu/qNN.txt`), même si T16.2 les a changées depuis. La recherche, identique pour les deux cellules et les trois passes, se vérifie par l'empreinte de son résultat, question par question. Calculé après le gel, sans aucun appel de plus (`banc.recherche_seule`, TDD).
**Pourquoi :** c'est la preuve d'une recherche par le sens (NEO-3) ; la faire après le gel interdit de régler la recherche sur les questions du banc ; des tables figées évitent qu'une espèce nouvelle change le dénominateur pendant la mesure.

### D14 — Tables des questions sémantiques pendant la campagne

**Choix :** la notation de la campagne suit l'[ADR-0008](../../adr/0008-mvp-notation-questions-semantiques.md) : une espèce hors table, citée avec la description qui la justifie et conforme à la grille, entre dans sa table (`questions/qNN.cypher`, `attendu/`), datée, avec l'accord de Julien ; les réponses de `fr-1`, de `g-1` et de `t2-controle` aux questions touchées sont alors renotées sur la table à jour, et les écarts de score rapportés (comme pour Poissirène le 2026-10-11, plan 002, D4) ; pour `fr-1`, l'écart s'ajoute, daté, au rapport de la technique 2, texte validé.
**Pourquoi :** les deux techniques se comparent sur les mêmes tables ; la recherche par le sens trouvera sans doute des espèces que le filet de mots-clés ignore.

### D15 — Préalables de la ROADMAP et réutilisation des décisions

**Choix :** avant le pilote : la contre-épreuve promue dans `banc/` en TDD (`banc contre-epreuve` : tirage de 8 cas, graine = 16 premiers caractères hexadécimaux du SHA-256 du CSV fini, page à l'aveugle, taux d'accord et désaccords), à partir des scripts de `logs/outils/` ; la clé Anthropic du banc renouvelée (elle expire le 2026-11-07 ; action de Julien) ; le budget de Vertex revu comme l'ADR-0010 le demande « avant les jalons 3 et 4 » : il court jusqu'au 2026-12-31, le jalon 3 s'y tient, NEO-27 le prolonge début décembre. Crédits Anthropic : 31,61 $ le 2026-10-11, aucune dépense Claude depuis ; octobre comptait 6,45 $ sous la limite de 20 $ par mois ; le jalon 3 en prévoit environ 4 $.
**Réutilisation des décisions de revue** (format de T2.1) : comme au jalon 2, la note seule, jamais la source, pour une même question et une même réponse courte normalisée ; une décision se réutilise si elle date d'après le gel de son jalon et ne vient pas d'un pilote, y compris d'un jalon à l'autre.

**Précision du 2026-10-13 (T1.1, choix délégué par Julien)** : `banc contre-epreuve` promeut les cinq scripts du jalon 2 en trois temps. Le tirage écrit dans `logs/revues/<campagne>/` (hors git : les pièces citent les réponses des agents) la page à l'aveugle, `tous.txt` (tous les cas à revoir, R1…Rn dans l'ordre de `banc revoir`, pour la pré-analyse) et, à part, `cles.json`. `--accord "<réponses copiées de la page>"` compare les réponses de Julien à `preanalyse.json`, dont il affiche le SHA-256 (le sceau) : notes et sources comptées à part, « je ne sais pas » hors de la comparaison, code 1 dès un désaccord. `--enregistrer [<fichier>]` passe les décisions validées par `banc.revue.revoir`, cas après cas, avec la note de l'ADR-0014 en tête de leurs tables ; des décisions qui s'écartent de la pré-analyse vont dans un autre fichier, pour qu'elle garde son sceau. Garde-fous : le tirage refuse une campagne incomplète (`banc rapport --complet`), déjà revue en partie, ou déjà tirée (ses numéros lient les réponses de Julien aux cas) ; une note tranchée par une décision réutilisée ne se redemande pas. Les tirages d'`en-1` et de `fr-controle` se refont à l'identique (graines `98dcbd7d875aff90` et `94cf111db62ab236`, mêmes cas, même ordre : test sur les CSV versionnés), leurs pièces aussi, à deux évolutions près (le nom de la campagne dans la page ; les lectures du tour précédent d'un second tour, venues avec l'ADR-0015 après le tirage de `fr-controle`). La légende « Source » de la page décrit la règle de la technique 2 : à compléter avec celle de l'ADR-0018 avant la revue de `g-1` (T16.1). `chiffres.py` (chiffres du rapport de la technique 2) attend T18.1 sous `logs/outils/`. Écarté : s'en tenir au tirage, à la page et à l'accord ; l'enregistrement serait resté pour T16.1 un script non testé, qui s'arrête sur un cas dont seule la source est à revoir.

### D16 — Effort de mise en place

**Choix :** comme au plan 002 (D11) : heures du journal, lignes propres (`git diff --numstat`), étapes hors code (compte de service, rôles IAM), note de 1 à 3 ; le socle commun compté à part.

### D17 — Mode d'exécution

**Choix :** TDD pour le déterministe (contre-épreuve, format des gels, encodage contre une fausse API Vertex, empreinte du vecteur, source citée, contrôle des traces, recherche seule, rapport) ; le vrai ADK et le vrai google-genai contre de fausses API et un faux serveur MCP pour la cellule (rule `testing`) ; faux `gcloud` et `cypher-shell` pour les scripts (jeton factice hors du motif `ya29.`, que gitleaks prendrait pour un vrai) ; essais réels ciblés et annoncés pour le chargement et la recherche. Aucun test n'appelle Vertex, Anthropic ni Aura. Des tâches qui touchent les mêmes fichiers restent dans l'ordre de `tasks.md`.

### LLM choisi, raison et coût estimé

| Usage                               | Modèle                                 | Prix ($ par million)              | Coût                                    |
| ----------------------------------- | -------------------------------------- | --------------------------------- | --------------------------------------- |
| `graphrag-claude`                   | `claude-sonnet-5-5`, API Anthropic     | 2 / 10 (`banc/prix.toml`)         | environ 0,9 $ la passe                  |
| `graphrag-gemini`                   | `gemini-3.8-flash`, Vertex `eu`        | 0,825 / 4,125 jusqu'au 2026-12-31 | environ 0,6 $ la passe                  |
| Passe de contrôle de la technique 2 | `adk-claude`, `adk-gemini`             | idem                              | environ 1,6 $                           |
| Questions d'une campagne            | `gemini-embedding-001`, `europe-west1` | 0,15                              | moins de 0,001 $                        |
| Chargement (5 233 descriptions)     | `gemini-embedding-001` par le plugin   | 0,15                              | environ 0,03 $ (166 000 jetons estimés) |

Estimation par question : consigne et fiche (2 500 jetons, en cache côté Claude) ; contexte de 4 000 à 6 000 jetons ; réponse et réflexion d'environ 1 500 jetons (Claude) à 3 000 (Gemini). Total de la spec : environ 8 $ (répétition 0,2 $, pilote 1,5 $, campagne 4,5 $, passe de contrôle 1,6 $, deux indexations 0,06 $, essais), dont 4 à 5 $ pour Claude, sous la limite de 20 $ par mois. Plafond du pilote : 3,5 $ ; celui de la campagne se fixe sur le coût réel du pilote, après la mesure du contexte (T8.2).

## Sécurité

- Identifiants d'Aura : lus par `scripts/` seulement ; le harnais et les cellules ne les voient jamais (code-map).
- Jeton `aura-genai` : pris par `scripts/charger.sh` juste avant `07` s'il reste à encoder, 15 minutes, sur stdin, masqué ; jamais pour le harnais ni une cellule ; il arrive chez Aura comme littéral, d'où un rôle limité à la prédiction (D4).
- Encodage des questions : ADC de Julien dans le harnais, comme la cellule Gemini ; seuls les messages posés et une description de contrôle partent chez Google.
- Isolement des cellules inchangé : `graphrag-claude` a la clé Anthropic sans variable Vertex, `graphrag-gemini` l'ADC sans la clé.
- Lecture seule : les fonctions du plugin sont classées en lecture (`EXPLAIN` : READ_ONLY) ; sans jeton, un agent qui les appellerait par `read-cypher` ne peut rien dépenser.
- Aucun texte de description dans le dépôt ([ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md)) ; aucun vecteur dans les traces (D9) ; `banc controle-traces` le vérifie, avec l'absence de jeton Google ; l'identifiant de l'instance se cherche par `scripts/traces.sh`, qui ne rend que des comptes ; `logs/` hors git ; gitleaks.

## Performance

- Chargement : environ 53 requêtes à Vertex, quelques minutes ; l'index, 64 Mo sans quantification, doit tenir dans Aura Free.
- Temps mesuré : de l'envoi du message à la réponse finale, recherche comprise, encodage rapporté à part (D5). Pas de cible : c'est une mesure.

## Tests

- **Unitaires (TDD)** : contre-épreuve, format des gels, encodage (vrai google-genai contre une fausse API Vertex), empreinte du vecteur, source citée, contrôle des traces, recherche seule, rapport, prix.
- **Intégration sans base ni réseau** : `verifier.sh`, `charger.sh` et `commun.sh` avec de faux `gcloud` et `cypher-shell` (section `embeddings`, jeton jamais en argument, toujours masqué, pris juste avant `07` seulement s'il reste à encoder, purge puis rechargement compris) ; cellule GraphRAG (vrai ADK contre de fausses API Anthropic et Vertex, faux serveur MCP qui répond à la recherche) ; orchestration de bout en bout ; contamination de la consigne, de la fiche et de la requête.
- **Sur la base, annoncés** : `verifier.sh --section embeddings` rouge puis vert, chargement, `--idempotence`, `questions.sh --verifier` et `--exemples`, `banc essai-recherche`, répétition générale (`--faux-serveur`, vrais LLM), pilote.

## Circuit breakers (conditions d'arrêt — à définir AVANT de coder)

- Le pilote coûte plus de 1,5 fois l'estimation : arrêt, replanifier.
- Un lot de 100 textes est refusé (taille, un texte par requête) : lots de 20, puis un à un (`ai.text.embed`), la relance reprenant où elle s'est arrêtée ; si rien ne passe, arrêt et retour au plan.
- L'index reste en POPULATING plus de 10 minutes, ou Aura Free le refuse (mémoire) : `DROP INDEX`, quantification `scalar`, notée datée ; sinon arrêt.
- La preuve de symétrie échoue (similarité sous 0,9999), en T8.2 ou à la création d'une campagne : arrêt, l'architecture A′ ne tient plus.
- Crédits Anthropic, limite de l'organisation ou coupure de Vertex : arrêt, question à Julien.
- Dépense cumulée de la spec au-delà de 10 $ (plafond de la spec) : arrêt avant toute nouvelle campagne, question à Julien.
- 3 échecs consécutifs sur la même tâche : replanifier.

## Liens

- Spec : [spec.md](spec.md)
- Research : [research.md](research.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : [0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md), [0003](../../adr/0003-mvp-chargement-cypher-pur.md), [0006](../../adr/0006-mvp-banc-essai-30-questions.md), [0007](../../adr/0007-infra-secrets-et-services-geres.md), [0008](../../adr/0008-mvp-notation-questions-semantiques.md), [0009](../../adr/0009-mvp-protocole-mesure-techniques.md), [0010](../../adr/0010-infra-plafond-de-depense.md), [0011](../../adr/0011-infra-claude-par-api-anthropic.md), [0012](../../adr/0012-mvp-second-tour-apres-echec.md), [0013](../../adr/0013-infra-plafond-natif-de-vertex.md), [0014](../../adr/0014-mvp-revue-assistee.md), [0015](../../adr/0015-mvp-source-du-tour-precedent.md), [0016](../../adr/0016-infra-limite-anthropic-organisation.md), [0017](../../adr/0017-mvp-precisions-protocole-mesure.md), [0018](../../adr/0018-mvp-technique-sans-outil.md), [0019](../../adr/0019-infra-jeton-vertex-du-plugin-genai.md), [0020](../../adr/0020-mvp-index-vectoriel-des-descriptions.md)
