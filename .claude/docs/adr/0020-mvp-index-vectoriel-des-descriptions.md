---
status: accepted
scope: mvp
phase: 2026-Q4
supersedes: null
---

# 0020 — Index vectoriel des descriptions : `gemini-embedding-001`, 3 072 dimensions, encodé par le plugin au chargement

**Statut :** Accepted
**Date :** 2026-10-13
**Décideur :** Julien Leroy

## Contexte

ARCHITECTURE (§ 8) prévoit depuis le cadrage un index vectoriel sur `Description.texte` avec `gemini-embedding-001`, « pour qu'un seul index serve aussi à Aura Agent (jalon 4) ». La conception de la [spec 003](../specs/003-graphrag-descriptions/spec.md) l'a éprouvé le 2026-10-12 ([research](../specs/003-graphrag-descriptions/research.md)) :

- le plugin GenAI d'Aura encode en Cypher (`ai.text.embedBatch`), deux textes par appel au moins ; `task_type` passe par `vendorOptions` en snake_case (`taskType` est ignoré sans erreur) ; ses vecteurs égalent ceux de google-genai à type de tâche égal ;
- `gemini-embedding-001` n'existe pas sur le point multirégion `eu` de Vertex (404) ; `europe-west1`, la région de l'instance, répond ;
- Aura Agent accepte `gemini-embedding-001`, réutilise un index existant par son nom, et n'offre aucun réglage de dimension ; une question encodée à une autre dimension que celle de l'index échoue ;
- quantification : `binary` par défaut depuis Neo4j 2026.08 ; 5 233 vecteurs de 3 072 dimensions pèsent 64 Mo sans quantification.

La décision lie le jalon 4 : elle survit à la spec 003.

## Options considérées

- **Option A — `gemini-embedding-001`, 3 072 dimensions, encodé par le plugin au chargement** (`cypher/07-embeddings.cypher`, `RETRIEVAL_DOCUMENT`, `europe-west1`), index `descriptions_texte` déclaré dans `cypher/00-contraintes.cypher`, `cosine`, sans quantification.
- **Option B — 768 ou 1 536 dimensions** : un index plus léger, mais Aura Agent encoderait probablement ses questions en 3 072 : réindexation au jalon 4.
- **Option C — Un autre modèle** : `text-multilingual-embedding-002` (768 au plus, l'ancienne génération) ou `gemini-embedding-2` (Preview) ; ni l'un ni l'autre n'est ce qu'ARCHITECTURE avait prévu pour Aura Agent.
- **Option D — Encoder en Python** (google-genai par lots, écriture par un driver) : contraire à l'[ADR-0003](0003-mvp-chargement-cypher-pur.md).
- **Option E — Ne rien faire** : pas d'index, pas de technique 3 ni d'outil de recherche pour Aura Agent.

## Décision

**Option A** (Julien : architecture et 3 072 dimensions le 2026-10-12, sur les préférences de Claude ; cet ADR le 2026-10-13). L'index `descriptions_texte` porte sur `Description.embedding` : 3 072 dimensions, similarité `cosine`, quantification `none` écrite en toutes lettres ; il est déclaré avant les données, dans `00-contraintes.cypher`, pour que la bascule de schéma (`charger.sh --schema`) le recrée. Les vecteurs viennent du plugin, dans la chaîne de chargement, en `RETRIEVAL_DOCUMENT` ; les questions s'encodent avec le même modèle, à la même dimension, en `RETRIEVAL_QUERY`. Changer de modèle, de dimension ou de quantification passe par un nouvel ADR, puis `DROP INDEX` et un nouvel encodage (environ 0,03 $).

## Conséquences

- ✅ Un seul index pour les jalons 3 et 4, rechargé et vérifié comme le reste du graphe (`verifier.sh`, idempotence).
- ✅ Le chargement reste en Cypher pur (ADR-0003).
- ⚠️ 64 Mo dans la mémoire d'Aura Free ; repli prévu : quantification `scalar`, notée datée au plan 003.
- ⚠️ La dimension qu'Aura Agent donne à ses questions n'est pas documentée : à vérifier au jalon 4.
- ⚠️ Les embeddings passent par `europe-west1`, sans la garantie de traitement dans l'UE du point `eu` ; les textes sont publics (PokéAPI).
- ⚠️ Le jeton que le plugin reçoit est réglé par l'[ADR-0019](0019-infra-jeton-vertex-du-plugin-genai.md).

## Liens

- [ARCHITECTURE § 8](../conception/ARCHITECTURE.md) ; [ADR-0003](0003-mvp-chargement-cypher-pur.md) ; [ADR-0019](0019-infra-jeton-vertex-du-plugin-genai.md)
- [Plan 003](../specs/003-graphrag-descriptions/plan.md) : D2, D3 ; [research 003](../specs/003-graphrag-descriptions/research.md) : test payant, explorations
