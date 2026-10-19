---
status: in-progress # draft | validated | in-progress | done | parked
progress: 24/35 # X/Y tasks (compté depuis tasks.md) — MAJ par /feature-done ou à la main
---

# Spec — GraphRAG sur les descriptions

> Vision micro : QUOI on construit et POURQUOI. Pas de "comment" (c'est dans plan.md).
> Le frontmatter `status:` = source **machine-readable** de l'état. La ROADMAP doit lui rester
> cohérente (`[ ]`=draft/validated · `[~]`=in-progress · `[x]`=done — audité par `/doc-health`).

**ID :** `003-graphrag-descriptions`
**Date :** 2026-10-12
**Jira :** epic [NEO-3](https://frjulienleroy.atlassian.net/browse/NEO-3)

## Vision

Mesurer la technique 3 du banc d'essai : un GraphRAG qui retrouve par le sens les descriptions françaises des Pokémon (index vectoriel, embeddings Gemini multilingues), parcourt le graphe autour des Pokémon trouvés, puis fait rédiger la réponse par un LLM à partir de ce contexte, sur les 30 questions de référence et avec le protocole du jalon 2. Pour Julien, qui veut savoir ce que la recherche par le sens apporte face au text-to-Cypher, d'abord sur les cinq questions sémantiques, et ce qu'elle coûte à mettre en place.

## User stories

### US1 — Mesurer le GraphRAG sur les 30 questions

**En tant que** Julien,
**je veux** poser les 30 questions à la technique GraphRAG, en lecture seule sur la base,
**afin de** la noter sur les cinq critères (réponse juste, sources citées, temps de réponse, coût, effort de mise en place), comme les autres techniques.

**Critères d'acceptation :**

- [ ] 3 passes comptées des 30 questions pour les deux cellules, Claude Sonnet 5.5 et Gemini 3.8 Flash, déjà mesurés au jalon 2 (comparaison des techniques à modèle égal) ; Q18 et Q28 posées au second tour de leur conversation ([ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md), [ADR-0012](../../adr/0012-mvp-second-tour-apres-echec.md))
- [ ] pendant les questions : aucune écriture dans la base, aucune lecture des fichiers du dépôt, un seul chemin vers la base (traces à l'appui)
- [ ] chaque réponse notée (juste, partielle, fausse), avec la source citée vérifiée sur la trace (règle d'une technique sans outil, [plan](plan.md), D9), la durée, les tokens et le coût ; l'encodage des questions compté par campagne, sa latence rapportée à côté du temps (plan, D5) ; revue assistée avec sa contre-épreuve de 8 cas ([ADR-0014](../../adr/0014-mvp-revue-assistee.md))
- [ ] un score par cellule et par catégorie, avec l'écart entre passes, comparé à celui de la technique 2 à modèle égal, avec les seuils fixés au plan avant la mesure (D12) ([rapport de la technique 2](../../../../banc/resultats/technique-2.md))

### US2 — Trouver les candidats par le sens

**En tant que** Julien,
**je veux** que les questions sémantiques (Q3, Q9, Q16, Q17, Q26) trouvent leurs candidats par le sens, pas seulement par mots-clés,
**afin de** savoir ce que l'index vectoriel apporte là où le text-to-Cypher cherche par mots.

**Critères d'acceptation :**

- [ ] pour chacune des 5 questions, la recherche seule (sans LLM) est mesurée : part des espèces obligatoires et acceptables de sa grille ([ADR-0008](../../adr/0008-mvp-notation-questions-semantiques.md)) présentes parmi les espèces retrouvées, avec le plafond de chaque question (20 espèces au plus)
- [ ] les espèces retrouvées que le filet de mots-clés de la requête de référence ne trouve pas sont relevées et classées avec la grille (la preuve d'une recherche par le sens)

### US3 — Un index vectoriel reproductible sur les descriptions

**En tant que** Julien,
**je veux** les embeddings des 5 233 descriptions et leur index vectoriel créés par la chaîne de chargement,
**afin que** la technique 3, puis Aura Agent au jalon 4, s'appuient sur un index reproductible et vérifié.

**Critères d'acceptation :**

- [ ] embeddings calculés avec `gemini-embedding-001`, index vectoriel en ligne, contrôlés par `verifier.sh` ; une relance ne recalcule rien et ne crée rien (idempotence)
- [ ] base de référence intacte : `verifier.sh` conforme, `questions.sh --verifier` conforme (27 réponses et la liste des espèces)
- [ ] coût du chargement mesuré et recoupé avec l'export de facturation

### US4 — Aucun vecteur dans une réponse

**En tant que** Julien,
**je veux** qu'aucune technique ne reçoive le vecteur d'une description, ni par la fiche de schéma commune ni par une recherche,
**afin qu'**un vecteur de plusieurs centaines de nombres ne remplisse jamais un contexte, ni ne fausse un coût.

**Critères d'acceptation :**

- [ ] la fiche de schéma nomme le vecteur de `Description` et interdit de renvoyer un nœud `Description` entier ou son vecteur : ajouts dont Julien a validé le texte, datés au plan ; ses valeurs et ses exemples se vérifient toujours sur la base (`questions.sh --exemples`)
- [ ] aucun contexte ni résultat d'outil de la campagne ne contient de vecteur, et la trace ne garde du vecteur de la question que son empreinte (traces à l'appui)

## Scope IN

- les embeddings `gemini-embedding-001` des descriptions (3 072 dimensions), calculés par le plugin GenAI d'Aura dans la chaîne de chargement, en Cypher pur, et leur index vectoriel
- la recherche vectorielle dans les descriptions, le parcours du graphe et la réponse rédigée par un LLM (Claude Sonnet 5.5, Gemini 3.8 Flash), mesurés par le harnais `banc/` avec le protocole du banc ([ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md) et ses précisions)
- la mesure de la recherche seule sur les 5 questions sémantiques
- la règle « aucun vecteur » de la fiche de schéma
- les préalables de la [ROADMAP](../../ROADMAP.md) : contre-épreuve de l'[ADR-0014](../../adr/0014-mvp-revue-assistee.md) promue dans `banc/`, en TDD ; clé Anthropic du banc renouvelée
- les résultats de la technique 3 et son effort de mise en place, prêts pour le tableau comparatif

## Scope OUT

- Aura Agent, Agent Runtime, Gemini Enterprise (jalon 4) ; mémoire d'agent (jalon 5)
- la recherche hybride, vecteur et plein texte ; `neo4j-graphrag` dans le banc (option B écartée, [research](research.md))
- un agent qui mêle recherche vectorielle et Cypher écrit par le LLM (outils au choix, `Text2CypherRetriever`, `ToolsRetriever`) : il brouillerait la comparaison avec la technique 2
- la construction d'un graphe de connaissances à partir des textes (extraction d'entités) : le graphe existe déjà
- une comparaison de modèles d'embedding ; tout réglage de la recherche sur les questions du banc (contamination, [ADR-0009](../../adr/0009-mvp-protocole-mesure-techniques.md))
- un juge LLM

## Métriques de succès

- toutes les séries comptées (cellules × 3 passes) notées et versionnées
- coût total (embeddings et LLM, pilote compris) d'au plus 10 $, estimé à 8 $ au [plan](plan.md), recoupé avec la Console Anthropic et l'export de facturation BigQuery
- base de référence intacte à la fin : `verifier.sh` et `questions.sh --verifier` conformes
- revue contenue : contre-épreuve de 8 cas et validation de la pré-analyse par campagne

## Dépendances

- spec [002-agent-text-to-cypher](../002-agent-text-to-cypher/spec.md) livrée (banc, protocole, fiche, résultats de la technique 2) : fait le 2026-10-12
- clé Anthropic du banc renouvelée avant la première campagne : elle expire le 2026-11-07 (workspace « Default », limite de l'organisation à 20 $ par mois, [ADR-0016](../../adr/0016-infra-limite-anthropic-organisation.md)) — précision du 2026-10-19 (choix de Julien) : la clé actuelle, valable jusqu'au 2026-11-07, sert au pilote et à la campagne ; la nouvelle est à poser avant cette date, et avant `g-1` si la campagne risque de déborder (plan, D15)
- Vertex AI sur `jleroy-labo`, sous la coupure de l'[ADR-0010](../../adr/0010-infra-plafond-de-depense.md) et le plafond natif de l'[ADR-0013](../../adr/0013-infra-plafond-natif-de-vertex.md) ; le budget de 100 € expire le 2026-12-31 (NEO-27)

## Liens

- Research : [research.md](research.md)
- Plan technique : [plan.md](plan.md)
- Tasks : [tasks.md](tasks.md)
- ADRs liés : [0001](../../adr/0001-mvp-jeu-de-donnees-pokeapi.md) (aucun texte de description versionné), [0003](../../adr/0003-mvp-chargement-cypher-pur.md) (chargement en Cypher pur), [0006](../../adr/0006-mvp-banc-essai-30-questions.md), [0007](../../adr/0007-infra-secrets-et-services-geres.md), [0008](../../adr/0008-mvp-notation-questions-semantiques.md), [0010](../../adr/0010-infra-plafond-de-depense.md), [0013](../../adr/0013-infra-plafond-natif-de-vertex.md), [0016](../../adr/0016-infra-limite-anthropic-organisation.md) ; protocole de mesure : [0009](../../adr/0009-mvp-protocole-mesure-techniques.md), amendé par [0011](../../adr/0011-infra-claude-par-api-anthropic.md), [0014](../../adr/0014-mvp-revue-assistee.md) et [0015](../../adr/0015-mvp-source-du-tour-precedent.md), précisé par [0012](../../adr/0012-mvp-second-tour-apres-echec.md) et [0017](../../adr/0017-mvp-precisions-protocole-mesure.md), et pour une technique sans outil par [0018](../../adr/0018-mvp-technique-sans-outil.md) ; jeton Vertex du chargement : [0019](../../adr/0019-infra-jeton-vertex-du-plugin-genai.md) ; index des descriptions : [0020](../../adr/0020-mvp-index-vectoriel-des-descriptions.md)
