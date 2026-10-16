// Vecteurs des descriptions (spec 003, T4.1 ; plan D3) : chaque Description sans embedding reçoit le vecteur de son
// texte, calculé par le plugin GenAI d'Aura (ai.text.embedBatch) : gemini-embedding-001 sur Vertex AI, le modèle des
// questions, en RETRIEVAL_DOCUMENT, 3 072 dimensions, celles de l'index descriptions_texte (00-contraintes.cypher).
// task_type s'écrit en snake_case, le seul que le plugin transmet : taskType est ignoré sans erreur (test payant du
// 2026-10-12). Région europe-west1, celle de l'instance : eu renvoie 404 pour ce modèle.
//
// Seules les descriptions sans vecteur partent : une relance n'encode que ce qui manque, sans repayer. Lots de 100
// textes (environ 3 300 jetons, loin des 250 textes et 20 000 jetons d'une requête), un par transaction, l'un après
// l'autre : sans le CONCURRENT de l'exemple de la doc du plugin, car des appels en parallèle s'exposent aux 429.
// Un lot refusé arrête le fichier ; les lots déjà écrits restent, et la relance reprend où il s'est arrêté. Chaque
// vecteur rejoint sa description par l'index que rend le plugin, jamais par le texte : celui des six Ultra-Chimères
// est en double.
//
// Paramètres, passés par charger.sh : $jeton, le jeton du compte aura-genai (15 minutes, rôle predictionVertex), par
// une ligne :param sur le stdin de cypher-shell, jamais en argument (ADR-0019) ; $projet, le projet Google de
// commun.sh (GCP_PROJET), celui du compte emprunté : rien en dur ici (code-map). Rend le nombre de descriptions
// encodées, 0 si aucune ne manque, puis attend l'index : 10 minutes, le seuil du circuit breaker du plan.
MATCH (d:Description) WHERE d.embedding IS NULL
WITH collect(d) AS descriptions, count(*) AS total
UNWIND range(0, total - 1, 100) AS debut
CALL (descriptions, debut) {
  WITH descriptions[debut .. debut + 100] AS lot
  CALL ai.text.embedBatch([d IN lot | d.texte], 'vertexai', {
    model: 'gemini-embedding-001',
    project: $projet,
    region: 'europe-west1',
    token: $jeton,
    vendorOptions: {task_type: 'RETRIEVAL_DOCUMENT', outputDimensionality: 3072}
  }) YIELD index, vector
  WITH lot[index] AS d, vector
  SET d.embedding = vector
  RETURN count(*) AS encodees
} IN TRANSACTIONS OF 1 ROW
RETURN sum(encodees) AS encodees;

CALL db.awaitIndex('descriptions_texte', 600);
