# Research — GraphRAG sur les descriptions

> Brainstorm options pour la feature `003-graphrag-descriptions`.
> Rempli avec méthode par `/conception 003-graphrag-descriptions` (explore → options → décision → revue adverse) — ou à la main en suivant les sections.
> Append des sections datées au fil des pivots/explorations ultérieures.

**Date :** 2026-10-12

## Problème à résoudre

La technique 3 du banc d'essai retrouve par le sens les descriptions françaises des Pokémon, parcourt le graphe autour des Pokémon trouvés, puis fait rédiger la réponse par un LLM ; elle se mesure sur les 30 questions avec le protocole des jalons 2 à 4. Il faut choisir où se calculent les embeddings (au chargement et pour chaque question), qui interroge la base et quel LLM répond, sans casser les règles du projet : chargement en Cypher pur, identifiants cantonnés à `scripts/`, un seul chemin vers la base, en lecture seule. Pour Julien, qui veut savoir ce que la recherche par le sens apporte face au text-to-Cypher et ce qu'elle coûte à mettre en place.

## Contraintes retenues

> Ce qui borne le plan AVANT d'explorer : cadrage client, règles de couplage (code-map.md),
> ADRs applicables (immuables), leçons déjà payées (lecons.md).

- [ADR-0003](../../adr/0003-mvp-chargement-cypher-pur.md) : chargement en Cypher pur par `cypher-shell` ; tout écart passe par Julien et par un nouvel ADR.
- [ADR-0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md) : aucun texte de description dans le dépôt (traces hors dépôt ; aucune requête de référence ne recopie un texte).
- [ADR-0007](../../adr/0007-infra-secrets-et-services-geres.md) et règles de couplage de la [code-map](../../code-map.md) : seuls `scripts/` et `infra/reveil-aura/` lisent les identifiants ; un secret passe par l'environnement, jamais en argument (visible par `ps`) ni sur le disque ; toute sortie de `cypher-shell` passe par `filtrer` ; `banc/` ne voit jamais l'identifiant d'Aura et ne lit jamais Secret Manager ; les agents ne joignent la base que par `scripts/mcp-neo4j.sh` ; seul le chargement écrit dans la base.
- [ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md), amendé par les ADR-0011, 0014 et 0015, précisé par les ADR-0012 et 0017 : même entrée pour toutes les techniques (consigne et fiche communes), un seul chemin vers la base, notation mixte sans juge LLM, source citée (une description renvoyée pendant le tour compte), pilote puis 3 passes comptées, plafonds invisibles (10 appels, 180 s, 0,50 $ par conversation), reprises, revue assistée avec contre-épreuve de 8 cas ; tout changement se justifie sans citer une question du banc.
- [ADR-0008](../../adr/0008-mvp-notation-questions-semantiques.md) : grille des questions sémantiques (obligatoire, acceptable, écarté) et notation au singulier ou au pluriel.
- Dépenses ([ADR-0010](../../adr/0010-infra-plafond-de-depense.md), [ADR-0013](../../adr/0013-infra-plafond-natif-de-vertex.md), [ADR-0016](../../adr/0016-infra-limite-anthropic-organisation.md)) : Vertex coupé à 100 € cumulés (budget jusqu'au 2026-12-31, NEO-27) et plafonné à 30 € par mois ; Claude borné par des crédits offerts sans recharge et par la limite de l'organisation (20 $ par mois) ; `banc lancer --plafond-usd` exigé (réserve de 1 $) ; aucun appel payant sans le feu vert de Julien.
- [Leçons](../../lecons.md) : un texte validé ne se reformule pas, on ajoute, daté (rule `textes-valides`) ; une affirmation de la fiche a sa requête sur le graphe chargé (`questions/fiche.cypher`) ; le vrai client contre une fausse API montre ce que sa doc tait, et un test d'exclusion emploie une entrée que le code accepterait sans elle (rule `testing`).

## Défrichage du 2026-10-12 (agent `explore-docs`, rapport partiel)

Agent lancé le 2026-10-12 vers 01 h 50 UTC, arrêté à la demande de Julien après environ 1 h 30 ; lecture seule, aucun appel payant. Rapport versé tel quel, regroupé ; les points « non vérifié » sont repris par les vérifications et les recherches bornées qui suivent.

**`neo4j-graphrag`**

- Dernière version 1.22.0, publiée le 2026-10-01 ([PyPI JSON](https://pypi.org/pypi/neo4j-graphrag/json)) ; 1.21.0 le 2026-09-23 ; pas de 1.20.0 sur PyPI (section présente dans le [CHANGELOG](https://github.com/neo4j/neo4j-graphrag-python/blob/main/CHANGELOG.md)).
- `Requires-Python: <3.15,>=3.10.0` ; README : 3.10 à 3.14 (seul l'extra `nlp`, spaCy, est exclu sous 3.14).
- Extras : `google` (Vertex AI, `google-cloud-aiplatform<2.0.0,>=1.66.0`), `google-genai` (`google-genai<3.0.0,>=1.62.0`, LLM et embeddings Gemini), `anthropic` (`anthropic<2.0.0,>=0.77.0`) ; pas d'extra `vertexai`. Base : `neo4j<7,>=6.3.1`, numpy 2.x, scipy, pydantic, pypdf, pyyaml, tenacity, json-repair, `fsspec<2026.9.0` ; pas de torch.
- Retrievers ([API, page « current »](https://neo4j.com/docs/neo4j-graphrag-python/current/api.html)) : `VectorRetriever`, `VectorCypherRetriever(driver, index_name, retrieval_query, embedder=None, …)`, `HybridRetriever`, `HybridCypherRetriever`, `Text2CypherRetriever`, `ToolsRetriever` ; hybride : `ranker` `NAIVE` (défaut) ou `LINEAR` avec `alpha`.
- Embedders et LLM : `GeminiEmbedder(model='gemini-embedding-001', embedding_dim=768, …)`, `VertexAIEmbeddings(model='text-embedding-004')`, `VertexAILLM(model_name='gemini-2.5-flash')`, `GeminiLLM`, `AnthropicLLM` (sans modèle par défaut) ; aucun embedder Anthropic.
- CHANGELOG : 1.22.0 chargement paresseux des fournisseurs ; 1.20.0 `GeminiLLM` remplit `LLMResponse.usage` ; 1.19.0 retrievers vectoriels en `CYPHER 25` + `SEARCH` sur Neo4j ≥ 2026, repli sur la procédure sinon.

**Index vectoriel sur AuraDB Free (Cypher 25)**

- `CREATE VECTOR INDEX` ([Cypher Manual](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/)) : `vector.dimensions` de 1 à 4 096 ; `cosine` (défaut) ou `euclidean` ; `vector.quantization.type` `none`, `scalar` ou `binary` depuis 2026.06, `binary` par défaut depuis 2026.08 ; `vector.hnsw.m` 16, `ef_construction` 100 ; filtres `WITH [n.prop]` (2026.01) ; remplissage asynchrone (POPULATING puis ONLINE). Type `VECTOR` depuis 2025.10 ; `db.create.setNodeVectorProperty` toujours documenté.
- Clause `SEARCH` ([page](https://neo4j.com/docs/cypher-manual/current/clauses/search/)) : Cypher 25 seulement ; vectoriel depuis 2026.01, plein texte depuis 2026.09 ; `WHERE` interne en vectoriel seulement ; nom d'index vectoriel jamais en paramètre. `db.index.vector.queryNodes` déprécié depuis 2026.04. Hybride : pas d'opérateur natif, chaque source se classe à part.
- Aura Free : « Vector optimization » réservée aux instances de 4 Go et plus ([doc Aura](https://neo4j.com/docs/aura/managing-instances/vector-optimization/)) ; aucune limite vectorielle propre à Free documentée ; ordre de grandeur : 5 233 vecteurs × 768 × 4 octets ≈ 16 Mo (≈ 64 Mo en 3 072).

**Embeddings calculés dans Cypher (plugin GenAI)**

- `ai.text.embed(resource, provider, configuration) :: VECTOR` et `ai.text.embedBatch(...)`, depuis 2025.11, en Cypher 25 ([embeddings](https://neo4j.com/docs/genai/plugin/current/embeddings/), [référence](https://neo4j.com/docs/genai/plugin/current/reference/functions-procedures/), [changelog](https://neo4j.com/docs/genai/plugin/current/reference/changelog/)) ; `genai.vector.encode` et `encodeBatch` dépréciés depuis 2025.11.
- « In Neo4j Aura, the GenAI plugin is enabled by default » ([intro](https://neo4j.com/docs/genai/plugin/current/)) ; [changelog Aura de décembre 2025](https://aura.feedback.neo4j.com/changelog/neo4j-aura-database-december-release-update-1) : déployé « starting with AuraDB Free ».
- Configuration Vertex : `model`, `project`, `region`, `publisher` (`'google'`), `apiKey` ou `token` (un seul), `maxBatchSize` (en jetons, 2026.04), `vendorOptions` (passé à `models.predict`) ; exemple officiel : `gemini-embedding-001`, `outputDimensionality: 1024`. Conséquence : le chargement peut rester en Cypher pur, par un `cypher/07-…`.

**Embeddings Gemini sur Vertex AI**

- Modèles ([Get text embeddings](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/embeddings/get-text-embeddings), MAJ 2026-10-09 ; [API](https://docs.cloud.google.com/gemini-enterprise-agent-platform/reference/models/text-embeddings-api)) : `gemini-embedding-001` (≤ 3 072 dimensions, 2 048 jetons, multilingue), `gemini-embedding-2` (≤ 3 072, 8 192 jetons, multimodal), `text-multilingual-embedding-002` (≤ 768), `text-embedding-005` (anglais) ; `text-embedding-004`, défaut de `VertexAIEmbeddings`, n'est plus listé.
- Types de tâche : `RETRIEVAL_QUERY` (défaut), `RETRIEVAL_DOCUMENT`, `SEMANTIC_SIMILARITY`, `CLASSIFICATION`, `CLUSTERING`, `QUESTION_ANSWERING`, `FACT_VERIFICATION`, `CODE_RETRIEVAL_QUERY` ; `task_type` par texte, `outputDimensionality` et `autoTruncate` par requête ; 3 072 dimensions par défaut.
- Limites : 250 textes et 20 000 jetons par requête, 2 048 par texte (troncature silencieuse) ; contradiction : les notes REST disent « un texte par requête » pour `gemini-embedding-001`. SDK : `google-genai`, `GOOGLE_GENAI_USE_ENTERPRISE=True`.

**Coût** : formule N × (caractères ÷ 4) × prix par jeton (heuristique non sourcée) ; prix relevé le 2026-09-28 : 0,15 $ par million de jetons ([prix](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing)), à revérifier ; estimation : moins de 0,10 $ pour les descriptions, environ 0,0001 $ pour 30 questions ; chaque réindexation coûte autant.

**Pièges relevés**

1. `neo4j-graphrag` teste `version >= (2026, 1, 0)` sur `dbms.components()` : avec « 5.27-aura », il passe par `db.index.vector.queryNodes` (déprécié), et l'hybride par les procédures (lu sur `main` : `utils/version_utils.py`, `retrievers/vector.py`).
2. `GeminiEmbedder` ne règle jamais `task_type` (tout en `RETRIEVAL_QUERY`), sans lot, `config` en dur (`embeddings/google_genai.py`).
3. `VertexAIEmbeddings` : `vertexai.language_models`, `aiplatform<2.0.0`, défaut disparu : à éviter.
4. Le jeton Vertex transite par Aura en paramètre : jamais en argument (ADR-0007) ; un agent MCP ne doit pas le recevoir.
5. Attendre ONLINE ; `cosine` ; à 5 000 vecteurs, `quantization.type: 'none'` envisageable.
6. La fiche de schéma devra exclure `embedding` des retours (ARCHITECTURE § 8).
7. Doublons : un même texte sur deux Pokémon fait deux nœuds (`cypher/06-descriptions.cypher`), donc deux vecteurs identiques ex æquo.

**Trois architectures** : A, tout dans Neo4j (`ai.text.embedBatch` au chargement, `ai.text.embed($q)` puis `SEARCH` à chaque question) ; B, chargement comme A et recherche en Python avec `neo4j-graphrag` 1.22.0 (préférence de l'agent) ; C, Python de bout en bout (contraire à l'ADR-0003).

## Vérifications du 2026-10-12, sans dépense

**Dépendances** (`uv` 0.12.19, sur une copie jetable de `banc/pyproject.toml` et `banc/uv.lock`) : `uv add --no-sync 'neo4j-graphrag[anthropic,google-genai]==1.22.0'` résout 91 paquets. Il en ajoute 9 (`neo4j-graphrag` 1.22.0, `neo4j` 6.4.0, `fsspec` 2026.7.0, sous le plafond `<2026.9.0`, `numpy` 2.5.4, `scipy` 1.18.1, `pypdf` 6.20.0, `json-repair` 0.64.0, `pytz` 2026.5, `types-pyyaml`) et ne change la version d'aucun paquet déjà verrouillé (`google-genai` 2.28.0 et `anthropic` 1.11.0 tiennent dans les bornes des extras). `google-cloud-aiplatform` n'arrive pas (seul l'extra `google` le tire). uv ignore la borne haute `<3.15` de `neo4j-graphrag` face au `>=3.14` du banc ; il marque `numpy` et `scipy` pour Python < 3.15.

**Instance AuraDB Free** (lecture seule, `--access-mode read`, par `scripts/commun.sh` ; un `EXPLAIN` n'exécute rien) :

- `dbms.components()` : noyau « 5.27-aura », Cypher 5 et 25 ; langage par défaut de la base : CYPHER 25. Le piège 1 se confirme : `neo4j-graphrag` y prendrait le chemin des procédures.
- Plugin GenAI présent : fonctions `ai.text.embed`, `ai.text.completion`, `ai.text.chat`, `ai.text.structuredCompletion`, `ai.text.aggregateCompletion`, `ai.text.chunkByTokenLimit`, `ai.text.tokenCount`, `ai.image.embed`, `genai.vector.encode` ; procédures `ai.text.embedBatch`, `ai.file.embedBatch`, `ai.image.embedBatch`, `genai.vector.encodeBatch` et les `….providers`.
- `ai.text.embed.providers()` : Azure-OpenAI, Bedrock-Titan, OpenAI, VertexAI. VertexAI exige `model`, `project`, `region` ; facultatifs : `token`, `apiKey`, `publisher` (défaut `google`), `maxBatchSize` (défaut −1), `vendorOptions` (défaut `{}`) ; aucune clé de type de tâche.
- Index : aucun index vectoriel ; `noms_plein_texte` (plein texte, `nom` de Type, Pokemon, Forme, Talent, Attaque), ONLINE.
- `EXPLAIN` d'un `SEARCH` plein texte sur `noms_plein_texte` : plan accepté (Cypher 25, `READ_ONLY`) ; exécuté, `dracofeu~` rend Dracaufeu (espèce et forme), puis Dracaufeu Gigamax. `EXPLAIN` d'un `SEARCH` vectoriel, avec un vecteur littéral ou calculé par `ai.text.embed` (jeton factice, rien d'envoyé) : syntaxe reconnue, refus `22N69` « index does not exist », attendu sans index.
- Descriptions : 5 233 nœuds, 638 797 caractères (56 à 237 par texte), 5 228 textes distincts (638 182 caractères). Un seul texte se répète : celui des six Ultra-Chimères d'Ultra-Soleil et Ultra-Lune (123 caractères), soit six vecteurs identiques qui arriveraient ensemble dans une recherche.
- Lecture seule des fonctions du plugin : `EXPLAIN` de `RETURN ai.text.embed(…)`, de `CALL ai.text.embedBatch(…)` et d'un lot sur les nœuds `Description` sans vecteur : `Statement: READ_ONLY` (Cypher 25) ; `neo4j-mcp` en lecture seule, qui refuse tout autre type, les laisserait passer. Signatures : `ai.text.embedBatch(resources :: LIST<STRING>, provider :: STRING, configuration = {} :: MAP) :: (index :: INTEGER, resource :: STRING, vector :: VECTOR)`, mode DEFAULT ; `ai.text.embed(resource :: STRING, provider :: STRING, configuration = {} :: MAP) :: VECTOR` ; `ai.text.tokenCount(input :: STRING, provider = OpenAI :: STRING, configuration = {} :: MAP) :: INTEGER`.
- Secret sans argument : `:param {jeton: "…"}` envoyé sur le stdin de `cypher-shell` (valeur factice), puis `RETURN size($jeton)` : la valeur arrive (11, égalité vraie), sans jamais paraître dans la ligne de commande.

**`neo4j-mcp` v1.6.0 et les paramètres** (vrai serveur, lancé comme par une cellule avec la mécanique de `banc essai-serveur`, sans modèle) : le schéma d'entrée de `read-cypher` déclare `params` (« Parameters to pass to the Cypher query », objet libre) ; `RETURN $x` avec `{x: 42}` rend 42 ; sans le paramètre, `Neo.ClientError.Statement.ParameterMissing` ; un vecteur de 768 nombres arrive entier (`size($v)` = 768) ; une chaîne accentuée aussi.

## Test payant du 2026-10-12 (feu vert de Julien)

Fait le 2026-10-12 de 16 h 30 à 16 h 31 UTC (heure d'un en-tête HTTP de Google : l'horloge de WSL2 retardait alors d'environ 1 h 50), pour environ 90 jetons, soit de l'ordre de 0,00001 $. Deux phrases maison, aucun texte de description ; lecture seule ; jeton passé sur le stdin de `cypher-shell` et masqué dans toute sortie.

- **Jeton** : compte de service `aura-genai@jleroy-labo.iam.gserviceaccount.com`, créé pour l'occasion (choix de Julien) : rôle `roles/aiplatform.user` sur `jleroy-labo`, et `roles/iam.serviceAccountTokenCreator` sur ce seul compte pour Julien ; jeton par `gcloud auth print-access-token --impersonate-service-account=…` (une heure), actif après environ une minute de propagation.
- **`eu` refusé** : côté Python (google-genai 2.28.0, `location="eu"`, point `aiplatform.eu.rep.googleapis.com`), 404 « Publisher model `projects/jleroy-labo/locations/eu/publishers/google/models/gemini-embedding-001` was not found » ; côté plugin (`region: 'eu'`), 404 de Google sur `/v1/projects/jleroy-labo/locations/eu/publishers/google/models/gemini-embedding-001:predict`. Une 404 n'est pas facturée. `europe-west1` répond des deux côtés.
- **Python** (`europe-west1`, `embed_content`, 768 dimensions) : 13 jetons pour la phrase de 50 caractères, dans les deux types de tâche (`statistics.token_count`), sans troncature.
- **Plugin** (`europe-west1`) :
  - `ai.text.embedBatch` de deux textes en un appel : deux lignes, 768 dimensions chacune (`outputDimensionality` par `vendorOptions` appliqué) ; normes 0,587 et 0,594 : vecteurs non normalisés, sans effet en similarité `cosine` ;
  - sans type de tâche : vecteur identique à celui de Python en `RETRIEVAL_QUERY` (`vector.similarity.cosine` = 1,0 ; 0,937 contre `RETRIEVAL_DOCUMENT`) : le défaut de Vertex ;
  - `vendorOptions: {task_type: 'RETRIEVAL_DOCUMENT'}` : appliqué, vecteur identique à celui de Python en `RETRIEVAL_DOCUMENT` (1,0) ;
  - `vendorOptions: {taskType: 'RETRIEVAL_DOCUMENT'}` : **ignoré sans erreur**, vecteur identique au défaut.
- **Conséquences** : un même texte donne le même vecteur par le plugin et par Python, à type de tâche égal ; descriptions et questions peuvent donc être encodées par deux voies ; `task_type` s'écrit en snake_case ; les embeddings passent par une région (`europe-west1`, celle de l'instance), pas par `eu` comme Gemini 3.8 Flash.

## Recherches bornées du 2026-10-12 (agents `explore-docs`, 25 min, 15 lectures)

**Embeddings Gemini en Europe** (pages Google lues le 2026-10-12)

- Prix ([page des prix](https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing), trop lourde pour WebFetch, lue par le résumé d'une recherche limitée à cloud.google.com) : `gemini-embedding-001` à 0,00015 $ les 1 000 unités en ligne (0,15 $ le million), 0,00012 $ en lot, sortie gratuite ; l'unité est écrite « per 1,000 count », jetons ou caractères non tranchés. `gemini-embedding-2` (Preview) : 0,20 $ le million de jetons. Ordre de grandeur pour les 638 797 caractères : 0,02 à 0,10 $ par indexation, moins de 0,30 $ dans le pire cas.
- Régions ([emplacements](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/learn/locations), MAJ 2026-10-10) : les deux modèles sont listés en « Global », « Multi-region » (`us`, `eu`) et « Europe », cases illisibles ; seul le point multirégion `eu` (`aiplatform.eu.rep.googleapis.com`) promet un traitement dans l'UE ; « Requests for gemini-embedding-001 and gemini-embedding-2 are subject to global quotas » ([quotas](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/quotas), MAJ 2026-10-09).
- Limites ([Get text embeddings](https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/embeddings/get-text-embeddings), MAJ 2026-10-09) : 250 textes et 20 000 jetons par requête, 2 048 jetons par texte (« any excess is silently truncated ») ; mais aussi, section REST : « For `gemini-embedding-001`, each request can only include a single input text. » Lecture probable : un texte par requête `:predict` (la voie du plugin), 250 par `embedContent` (SDK). Quotas mondiaux : 100 millions de jetons et 100 000 requêtes par minute.
- Normalisation ([doc de l'API Gemini](https://ai.google.dev/gemini-api/docs/embeddings), MAJ 2026-10-09) : « If you are using gemini-embedding-001, you must manually normalize non-3072 dimensions » ; sans effet avec la similarité `cosine`.

**Plugin GenAI avec Vertex AI** ([embeddings](https://neo4j.com/docs/genai/plugin/current/embeddings/), « Version 25 (Current) » ; [changelog](https://neo4j.com/docs/genai/plugin/current/reference/changelog/), dernière entrée 2026.05)

- Configuration : « Exactly one of `apiKey` or `token` must be provided » ; `apiKey` depuis 2025.12. Aucune liste de régions, URL non décrite ; l'hôte Google documenté est régional (`https://${REGION}-aiplatform.googleapis.com/…:predict`) : `eu` et `global` ne sont garantis nulle part.
- Jeton : jeton d'accès OAuth (« Bearer »), une heure ; celui d'un compte de service, une heure par défaut ([types de jetons](https://docs.cloud.google.com/docs/authentication/token-types), MAJ 2026-10-09). L'argument `configuration` est masqué dans query.log, sauf requête mal formée (« logged without obfuscation ») ; la colonne `parameters` de `SHOW TRANSACTIONS` montre les paramètres au même utilisateur ([Cypher Manual](https://neo4j.com/docs/cypher-manual/current/clauses/transaction-clauses/)). Règle : le jeton toujours en `$paramètre`, jamais en littéral.
- `task_type` : absent de l'API actuelle ; « `vendorOptions` … will be passed on as-is in the request to Vertex (… models.predict) », seul exemple : `outputDimensionality` (un champ de `parameters`) ; Vertex attend `task_type` dans chaque `instances[]` (« If left blank, the default used is RETRIEVAL_QUERY ») : probablement ignoré, à prouver.
- `ai.text.embedBatch` : « attempts to generate embeddings for all supplied resources in a single API request » ; `maxBatchSize` compté en jetons (défaut −1 : aucun découpage) ; rien de prévu si le modèle n'accepte qu'un texte par requête, sinon `ai.text.embed`, « one API request every time it is called » ; patron officiel : `UNWIND range(0, total-1, batchSize)` puis `CALL … IN CONCURRENT TRANSACTIONS OF 1 ROW` (appels en parallèle, exposés aux 429).
- Écriture : `SET n.embedding = vector` range un `VECTOR` (format « block », celui d'Aura) ; `db.create.setNodeVectorProperty(…, toFloatList(vector))` pour une `LIST<FLOAT>`.

**`neo4j-graphrag` au tag 1.22.0** (code brut de `https://raw.githubusercontent.com/neo4j/neo4j-graphrag-python/1.22.0/src/neo4j_graphrag/`, lu le 2026-10-12 ; numéros de ligne exacts pour les fichiers lus en entier)

- Chemin de requête : `get_version` coupe « 5.27-aura » en `(5, 27, 0)` (`utils/version_utils.py:47-61`) ; `supports_search_clause` exige `>= (2026, 1, 0)` (l. 156-180) : sur l'instance, `VectorCypherRetriever` passe par `CALL db.index.vector.queryNodes(…)` suivi de la `retrieval_query` (`neo4j_queries.py:38-43`) ; `HybridCypherRetriever` réunit les deux procédures dans un `CALL () { … UNION … }`, scores normalisés par le maximum de chaque index, et ne prend jamais `SEARCH … FULLTEXT`. Cypher Manual ([dépréciations](https://neo4j.com/docs/cypher-manual/current/deprecations-additions-removals-compatibility/)) : procédures vectorielles dépréciées en 2026.04, aucun retrait annoncé.
- `GeminiEmbedder(model="gemini-embedding-001", embedding_dim=768, …)` : un texte par appel (`contents=[text]`), aucun lot, `EmbedContentConfig(output_dimensionality=…)` en dur, sans `task_type` (`embeddings/google_genai.py:51-104`) : une sous-classe est nécessaire.
- `GeminiLLM` remplit `usage` (entrée, sortie, total) sans lire `thoughts_token_count` ; `AnthropicLLM` n'a ni modèle ni `max_tokens` par défaut et ne lit aucun champ de cache.
- `GraphRAG(retriever, llm, prompt_template=RagTemplate())` : synchrone ; contexte = `"\n".join(item.content …)`, chaque enregistrement rendu par `str(record)` ; gabarit par défaut en anglais (« Answer the user question using the provided context. », `generation/prompts.py:96`), remplaçable ; `search()` ne garde que `answer` et `retriever_result` : l'`usage` du LLM est perdu. Avec une `retrieval_query`, rien n'exclut `embedding` : la requête doit projeter.

## Explorations (rapports sourcés)

> Produits par les subagents parallèles de `/conception` — du factuel, jamais des impressions.

Trois teammates en lecture seule, visibles dans tmux (`explo-code`, `explo-docs`, `explo-memoire`), le 2026-10-12, 25 min visées chacun.

- **Code** (`explo-code`, 26 lectures) :
  - Cellule : un processus `python -m banc.<module>`, commande JSON sur stdin, sa propre trace ; enregistrement dans `CELLULES`, `PROGRAMMES`, `CLAUDE` (`banc/src/banc/orchestration.py:116-124`) et `environnement_agent` (`banc/src/banc/isolement.py:64-125`). Plafonds tenus par la cellule (`cellule.py:40-57`) ; `--plafond-usd` et réserve de deux budgets (`orchestration.py:149-152, 895-908`).
  - Trace : `Journal.appel` refuse tout outil autre que `read-cypher` et `get-schema` (`mesures.py:62, 224-225`) et écrit les `parametres` (`mesures.py:229`). Notation de la source : lectures `read-cypher` sans erreur ; une description citée vaut source si l'enregistrement qui la contient porte aussi une valeur juste (`notation.py:475-507`) : une recherche notée comme un appel `read-cypher` se note telle quelle.
  - Le harnais sait appeler `read-cypher` sans LLM, avec `params` (`essai_serveur.py:218-229`). Coût : une seule voie d'accès par conversation (`mesures.py:461`, `prix.py:78-83`) ; un modèle d'embedding entrerait comme modèle annexe (`Entete.annexes`, `mesures.py:97-99`). Isolement : la clé Anthropic jamais avec une variable Vertex (`isolement.py:8-10`, `test_isolement.py:102`).
  - Seconds tours : Q18 et Q28 sont elliptiques (`questions/banc.toml:184, 256`) ; la recherche sur leur seul texte ne retrouve ni l'équipe ni Pikachu, d'où l'historique de la conversation.
  - Chargement : `--tout` joue `cypher/[0-8][0-9]-*.cypher` dans l'ordre (`charger.sh:584-599`) : un `07-…` s'insère seul. `--idempotence` commence par une purge (`charger.sh:626`), donc repaie les embeddings, et ne voit pas un recalcul (« Set » permis, `:643`). `--schema` supprime les index hors de `00-contraintes.cypher` (`charger.sh:458-471`) : l'index vectoriel y va. `-P` passe par argv, visible par `ps` (`commun.sh:87, 96`) ; `filtrer` ne masque ni jeton ni clé (`commun.sh:74-80`).
  - Fiche : une règle va dans « Règles » (`questions/fiche-schema.md:28-35`), car chaque ligne de « Nœuds » exige sa requête (`test_fiche_cypher.py:205-212`) ; 8 exemples, le maximum (`test_contamination.py:230`) ; la fiche anglaise se régénère (`test_fiche_anglaise.py`) ; l'empreinte du prompt change (`cellule.py:111-114`).
  - Contre-épreuve : rien dans `banc/` (tirage, graine, page, taux d'accord) ; `revue.py` couvre la revue elle-même (`revue.py:193-449`) ; à créer en TDD : `banc/tests/test_contre_epreuve.py`, `banc/src/banc/contre_epreuve.py` avec le gabarit HTML dans le paquet, `banc contre-epreuve`. `revues.toml` n'accepte qu'un `gel` et un `pilote` (`revue.py:207-219`, vérifié par le lead) : un second pilote demande d'étendre le format.
- **Docs externes** (`explo-docs`, 15 lectures) :
  - Aura Agent ([page](https://neo4j.com/docs/aura/aura-agent/), sans date) : son outil Similarity Search accepte `gemini-embedding-001` (et `text-embedding-005`, multilingue), réutilise un index existant par son nom, avec un Top K et une requête de « connected graph data » ; modèles hébergés par Neo4j, aucune clé du client ([modèles](https://neo4j.com/docs/reference/license/agent-ai-model/)) ; aucun réglage de dimension, et « querying the index with a vector of a different dimension returns an error » : seul un index à 3 072 dimensions (le défaut du modèle) le sert à coup sûr ; sinon, essai au jalon 4.
  - Index ([vector indexes](https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/), Cypher 25) : quantification `binary` par défaut depuis 2026.08, `scalar` avant : à fixer explicitement ; un seul index par label et propriété ; seuls les vecteurs de la dimension déclarée sont indexés. Mémoire ([Operations Manual](https://neo4j.com/docs/operations-manual/current/performance/vector-index-memory-configuration/), 2026.09) : 4 × d × N octets sans quantification, soit 16, 32 ou 64 Mo pour 768, 1 536 ou 3 072 dimensions, plus 0,7 Mo de graphe HNSW.
  - Hybride ([guide](https://neo4j.com/developer/genai-ecosystem/hybrid-search/), sans date, « require Neo4j 2026.09 or later and Cypher 25 ») : une branche `UNION ALL` par source (`SEARCH … LIMIT $sourceK`), fusion par rangs pondérés (`weight / (60 + rang)`), sans normaliser les scores bruts. Analyseur `french` présent sur l'instance (« French analyzer with stemming and stop word filtering », 45 analyseurs, vérifié par le lead).
  - `neo4j-mcp` : v1.6.0 du 2026-09-10, dernière ([releases](https://github.com/neo4j/mcp/releases)) ; aucun outil vectoriel ; le README avertit que des fonctions classées en lecture par Neo4j passent le contrôle.
- **Mémoire projet** (`explo-memoire`, 26 lectures) :
  - Rien sur GraphRAG, les embeddings ou l'index dans les ADR, leçons et idées ; ARCHITECTURE § 8 avait prévu l'index sur `Description.texte` avec `gemini-embedding-001` « pour qu'un seul index serve aussi à Aura Agent ».
  - Même entrée : la consigne s'adresse à un agent muni de `read-cypher` (« Interroge le graphe autant de fois qu'il le faut ») ; un LLM rédacteur sans outil est un écart que seuls les ADR du jalon 4 prévoient : préciser l'ADR-0009, comme l'ADR-0017. Plan croisé : avec un pipeline unique, seul le modèle varie ; reprendre les réglages du jalon 2 (effort `high`, `max_tokens` 128 000, `thinking_level` HIGH, cache de 5 min).
  - Couplage : B contredit l'ADR-0009 (« le harnais ne les lit jamais ») et trois règles de la code-map, perd la lecture seule côté serveur (T7.4) et le masquage de l'identifiant : ADR qui amende l'ADR-0009. C contredit l'ADR-0003, choisi par Julien contre une recommandation Python. A remet un jeton Google à Aura à chaque question (trace, reprises hors ADR-0017) : ADR conseillé, qui précise l'ADR-0007. A′ : une décision de plan et la code-map suffisent ; reste le jeton du chargement.
  - Coûts : budget Vertex de 100 € jusqu'au 2026-12-31 (l'ADR-0010 dit de le revoir « avant les jalons 3 et 4 ») ; promotion de 50 % sur Gemini jusqu'à la même date ; plafond natif de 30 € compté sans les crédits ; clé Anthropic jusqu'au 2026-11-07 ; « un modèle sans tarif arrête la mesure » : `gemini-embedding-001` à ajouter à `banc/prix.toml` ; estimer sur de vrais contextes (Q2 seule avait coûté 0,62 $ au pilote du jalon 2).

## Options considérées

Les trois architectures du défrichage, plus A′, née des explorations (règles de couplage, contrat de trace) et confirmée par le test payant. Pas de génération d'options par agents à angle imposé : six agents venaient d'explorer le sujet. Dans toutes, le chargement des embeddings passe par le plugin, sauf C ; la technique mesurée est la même : recherche vectorielle dans les descriptions, parcours du graphe, un appel au LLM.

| Option | Approche                                                                                                                  | Coût                                                       | Risques                                                                                                                                          | Réversibilité | Conforme couplage/ADR ?                                    |
| ------ | ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ | ------------- | ---------------------------------------------------------- |
| A      | Plugin au chargement et à chaque question (`ai.text.embed` dans la requête de recherche, par `read-cypher`)               | ~0,1 $ par indexation ; encodage des questions non mesuré  | jeton Google dans les paramètres, la trace et Aura à chaque question ; jeton d'une heure à renouveler en campagne ; reprises de Vertex dans Aura | moyenne       | ⚠️ ADR conseillé (précise l'ADR-0007) ; isolement à revoir |
| A′     | Plugin au chargement ; question encodée par le harnais (google-genai) ; recherche par `read-cypher`, vecteur en paramètre | ~0,1 $ par indexation ; questions mesurées (jetons rendus) | vecteur dans les paramètres de la trace ; deux voies d'encodage à garder identiques (prouvé par le test)                                         | bonne         | ✅ ; une décision de plan pour l'encodage hors cellule     |
| B      | Plugin au chargement ; `neo4j-graphrag` 1.22.0 dans `banc/`, avec un driver                                               | idem                                                       | procédures dépréciées sur « 5.27-aura » ; quatre contournements ; trace et notation à étendre                                                    | faible        | ❌ amende l'ADR-0009 et trois règles de la code-map        |
| C      | Python de bout en bout (google-genai par lots, écriture par le driver)                                                    | idem                                                       | perte de l'apprentissage du plugin                                                                                                               | faible        | ❌ amende ou remplace l'ADR-0003                           |

### Option A — Tout dans la base

- **Comment** : `cypher/07-embeddings.cypher` (plugin, `task_type: 'RETRIEVAL_DOCUMENT'`) au chargement ; à chaque question, la requête de recherche calcule `ai.text.embed($question, 'VertexAI', {…, token: $jeton})`, puis `SEARCH` et le parcours, en un seul appel `read-cypher`.
- **Pros** : technique entièrement Neo4j (le plugin à la question, comme Aura Agent le fait en interne) ; un seul aller-retour.
- **Cons** : le jeton du compte de service part dans les paramètres de chaque question (trace à masquer, canal MCP, Aura) et doit être remis à la cellule Claude ; il expire au bout d'une heure, en pleine campagne ; Vertex reprend ses appels dans Aura, hors de l'ADR-0017 ; le coût de l'encodage des questions n'apparaît que dans la facture.
- **Effort** : Moyen.
- **Réversibilité** : moyenne (la requête de recherche change de forme si l'on revient à A′).
- **Conforme couplage/ADR ?** : ⚠️ jeton Google remis à un tiers à chaque question : un ADR qui précise l'ADR-0007 ; règle d'isolement à revoir.
- **Statut** : 🤔 alternative.

### Option A′ — Plugin au chargement, question encodée par le harnais, recherche par `read-cypher`

- **Comment** : même chargement que A ; la question est encodée par google-genai (`gemini-embedding-001`, `europe-west1`, `RETRIEVAL_QUERY`), hors de la cellule Claude ; la requête de recherche (`SEARCH` puis parcours) part par `read-cypher` avec le vecteur en paramètre ; un seul appel au LLM rédige la réponse.
- **Pros** : aucun secret dans les paramètres ; tout ce que le jalon 2 a prouvé reste en place (chemin unique en lecture seule, identifiant masqué, contrat de trace, notation de la source, isolement) ; jetons de l'encodage mesurés ; reprises de google-genai dans le cadre de l'ADR-0017 ; plugin et Python rendent le même vecteur à type de tâche égal (test payant).
- **Cons** : le vecteur passe dans les paramètres de la trace (à tracer par son empreinte) ; deux voies d'encodage à garder alignées (modèle, dimension, type de tâche) ; l'encodage ne peut pas se faire dans la cellule Claude (isolement).
- **Effort** : Moyen.
- **Réversibilité** : bonne (l'encodage de la question se déplace sans toucher à l'index).
- **Conforme couplage/ADR ?** : ✅ ADR-0003, 0007 et 0009 tenus ; une décision de plan pour l'encodage hors cellule.
- **Statut** : 🤔 préférence de Claude.

### Option B — `neo4j-graphrag` dans le harnais

- **Comment** : même chargement ; `VectorCypherRetriever` (sous-classe de `GeminiEmbedder` pour `task_type`), `GraphRAG` avec un gabarit français, `AnthropicLLM` et `GeminiLLM`, un driver Neo4j dans `banc/`.
- **Pros** : la bibliothèque officielle de Neo4j ; historique de conversation tout fait.
- **Cons** : le harnais lirait les identifiants (dont l'identifiant de l'instance) ; plus de lecture seule côté serveur ni de masquage ; sur « 5.27-aura », procédures dépréciées au lieu de `SEARCH` ; quatre contournements (embedder, gabarit, projection sans `embedding`, `usage` perdu par `GraphRAG.search`) ; trace et notation à étendre ; neuf paquets de plus.
- **Effort** : Gros.
- **Réversibilité** : faible.
- **Conforme couplage/ADR ?** : ❌ un ADR qui amende l'ADR-0009 et trois règles de la code-map.
- **Statut** : 🤔 alternative ; `neo4j-graphrag` peut s'apprendre hors du banc, sans mesure.

### Option C — Python de bout en bout

- **Comment** : embeddings calculés par google-genai par lots de 250, écrits par le driver ; recherche comme A′ ou B.
- **Pros** : contrôle total des lots, des reprises et du type de tâche.
- **Cons** : contraire à l'ADR-0003, choisi par Julien contre une recommandation Python ; on perd l'apprentissage du plugin, qui marche (test payant).
- **Effort** : Gros.
- **Réversibilité** : faible.
- **Conforme couplage/ADR ?** : ❌ un ADR qui amende ou remplace l'ADR-0003.
- **Statut** : ❌ écarté : le plugin tient le chargement en Cypher pur.

## Décision

**Option A′** (Julien, 2026-10-12, sur la préférence de Claude) : plugin GenAI au chargement, question encodée par le harnais, recherche par `read-cypher` avec le vecteur en paramètre. Elle tient les ADR-0003, 0007 et 0009 et les règles de couplage, réutilise ce que le jalon 2 a prouvé (chemin unique en lecture seule, masquage, trace, notation de la source), mesure l'encodage des questions, et le test payant a montré que le plugin et google-genai rendent le même vecteur à type de tâche égal.

- Pas A : un jeton Google à chaque question, dans la trace et dans Aura, qui expire en pleine campagne ; reprises de Vertex hors de l'ADR-0017.
- Pas B : le harnais lirait les identifiants (ADR-0009 à amender), procédures dépréciées sur « 5.27-aura », quatre contournements.
- Pas C : l'ADR-0003 tient grâce au plugin.

Choix du même jour (Julien, sur les préférences de Claude) : deux cellules, Claude Sonnet 5.5 et Gemini 3.8 Flash (comparaison à modèle égal avec la technique 2, effet du modèle) ; recherche vectorielle seule (fidèle à NEO-3, mesurée face au filet de mots-clés des requêtes de référence) ; vecteurs de 3 072 dimensions (l'index sert tel quel à Aura Agent au jalon 4). Le détail, et les choix délégués, sont au [plan](plan.md) (§ Décisions).

Choix du 2026-10-13, après la revue adverse (Julien, sur les préférences de Claude) : source citée d'une technique sans outil = les descriptions citées, réunies, portent toutes les valeurs de la réponse ; passe de contrôle de la technique 2 les mêmes jours que la campagne ; jeton du chargement limité à la prédiction, 15 minutes ; trois ADR avec la PR de conception (technique sans outil, jeton Vertex remis au plugin, index des descriptions).

Plan validé par Julien le 2026-10-13, avec les textes de D8 (consigne de contexte, ligne `Description` et puce « Vecteurs » de la fiche) et les ADR [0018](../../adr/0018-mvp-technique-sans-outil.md), [0019](../../adr/0019-infra-jeton-vertex-du-plugin-genai.md) et [0020](../../adr/0020-mvp-index-vectoriel-des-descriptions.md) ; tickets NEO-28 à NEO-35 publiés sous NEO-3. Deux ADR à écrire avec la PR de conception : l'un précise l'ADR-0009 (technique sans outil), l'autre l'ADR-0007 (jeton Vertex remis au plugin au chargement).

## Revue adverse

> Findings de l'agent frais qui a challengé le plan (étape 5 de /conception) — garder la trace
> de ce qui a été attrapé évite de le re-payer.

Agent `reviewer` à contexte frais, teammate visible, le 2026-10-12 (environ 27 lectures, lecture seule) : 1 🔴, 9 🟠, 14 🟢. Le lead a revérifié les points qui changeaient le plan : `questions/fiche.cypher` (l. 129-147) compare les propriétés de `Description` à `['jeux', 'texte']` ; les grilles comptent 16, 26, 1, 8 et 15 espèces obligatoires et acceptables pour Q3, Q9, Q16, Q17 et Q26 ; `cypher-shell` 2026.09.0 évalue `:param` côté serveur (`:param {t: datetime()}` rend l'heure du serveur) ; le seul exemple de la fiche sur `Description` (Tropius) ne renvoie que `texte` et `jeux`.

- 🔴 La fiche dit que `Description` n'a que `texte` et `jeux` ; une fois les vecteurs chargés, `questions.sh --exemples` échoue → la ligne « Nœuds » nomme `embedding` (texte à valider), sa requête suit, la fiche change avec le chargement (phase 6), vérification d'abord (D8, T6.1).
- 🟠 Source citée presque automatique : une description vaut source dès que son enregistrement porte une valeur juste (`any`), une requête toutes (`all`) → tranché par Julien le 2026-10-13 : les descriptions citées valent source si, réunies, leurs espèces portent toutes les valeurs de la réponse ; dans l'ADR (D9, T11.2).
- 🟠 Spec et plan se contredisaient sur la durée et le coût de l'encodage des questions → latence rapportée à côté du temps, coût par campagne, écart dans l'ADR (D5, D11, US1).
- 🟠 Seuils mal définis et dérive des modèles non traitée → Δ, R et le score écrits ; passe de contrôle de la technique 2, retenue par Julien le 2026-10-13 (D12, T15.3).
- 🟠 `roles/aiplatform.user` trop large pour un jeton remis à Aura → rôle limité à la prédiction, retenu par Julien le 2026-10-13 (D4, T3.2).
- 🟠 `:param` évalué côté serveur : le jeton arrive chez Aura en littéral → constat vérifié, jeton de 15 minutes, risque écrit dans l'ADR (D4).
- 🟠 Aucun contrôle de l'index avant une campagne ; `--langue` ne voit pas `CREATE VECTOR INDEX` → `verifier.sh --section embeddings` à la création, expression étendue (D2, T3.3, T13.1).
- 🟠 Recherche seule : plafond (Q9 : 77 % au plus) et tables qui changeraient sous la technique 2 → plafond rapporté, tables du gel pour US2, renotation de `fr-1` et `g-1` si une table change (D13, D14, T16.2).
- 🟠 Phases trop longues → 16 phases au lieu de 10.
- 🟠 DoD qui ne pouvaient pas échouer, preuves « traces à l'appui » sans commande → `test_verifier_sh.py`, rouge sur la base dès T3.1, `banc essai-recherche` et `banc controle-traces` avec leurs contrôles dans le code retour (T3.1, T8.2, T15.1).
- 🟢 Pris en compte : fichiers manquants au tableau ; contexte de 4 000 à 6 000 jetons, mesuré en T8.2 ; preuve de symétrie à chaque campagne ; projet de quota `jleroy-labo` ; vecteur rattaché par `index` ; jeton pris seulement s'il reste à encoder ; retour arrière au RUNBOOK dès la phase 3 ; `CYPHER 25` ; jeton factice hors du motif `ya29.` ; recherche identique d'une trace à l'autre ; réutilisation des décisions entre jalons ; fichiers communs à plusieurs tâches ; phases à dépense ; critère d'US2 rangé dans US1 ; justification de `cosine` ; troisième ADR pour l'index, retenu par Julien le 2026-10-13.

**Contre-vérification** (même relecteur, 2026-10-13, 6 lectures) : R1, O2, O4, O5, O6 et O9 corrigés ; O1, O3, O7 et O8 en partie ; 8 nouveaux 🟠, nés des corrections, tous repris :

- 🟠 Jeton décidé « au lancement » : après une purge, `07` n'aurait pas de jeton (`ParameterMissing`) → compte juste avant `07`, après `06` (D3, D4, T5.1) ; une reconstruction exige Vertex (RUNBOOK, ADR-0019).
- 🟠 Règle de source appliquée à la seule technique 3 : biais contre elle sur Q9, Q17 et Q26 → même règle pour toutes les techniques dans le tableau, colonne source de `fr-1` relue, en ajout daté (D9, ADR-0018, T11.2, T18.1).
- 🟠 Passe de contrôle mêlant dérive et changement de fiche, sans formule → elle mesure la technique 2 dans les conditions du jalon 3 ; Δ′, son seuil et la lecture des deux écarts écrits avant la mesure (D12).
- 🟠 `banc controle-traces` ne peut pas chercher l'identifiant de l'instance → `scripts/traces.sh`, comptes seuls (T15.1).
- 🟠 Mode faux serveur contre les contrôles à la création → vérification de l'index et preuve de symétrie sautées en faux serveur (D5, T13.1).
- 🟠 DoD de T3.2 qui ne pouvait pas échouer → comparaison au rôle `predictionVertex`.
- 🟠 US2 et D13 contradictoires → espèces retrouvées hors filet classées avec la grille, accord de Julien, sans toucher aux tables (D13, T17.1).
- 🟠 Phases 4 et 11 encore longues → coupées : 18 phases, 35 tâches.
- 🟢 Pris en compte : estimation de 8 $ dans la spec et coupe-circuit sur le total de 10 $ ; rouge de T6.1 limité à la ligne `Description` ; feu vert dans la DoD de la passe de contrôle ; renotation prouvée sur les trois campagnes ; `verifier.sh` lancé sans `ANTHROPIC_*` ; tables lues au commit du gel ; écart de `fr-1` ajouté daté au rapport de la technique 2 ; résidu de la règle de source dit dans le rapport ; ADR numérotés 0018 à 0020.

## Liens externes

- {{Lien doc / blog / RFC pertinents}}
