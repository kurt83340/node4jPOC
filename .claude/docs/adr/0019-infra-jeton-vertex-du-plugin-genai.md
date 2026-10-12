---
status: accepted
scope: infra
phase: 2026-Q4
supersedes: null
---

# 0019 — Jeton Vertex remis au plugin GenAI d'Aura : compte de service limité à la prédiction, 15 minutes

**Statut :** Accepted
**Date :** 2026-10-13
**Décideur :** Julien Leroy

## Contexte

L'[ADR-0007](0007-infra-secrets-et-services-geres.md) range les secrets dans Secret Manager : un script les lit au lancement et les passe « par l'environnement du processus, sans l'afficher ni l'écrire » ; en entreprise, l'accès passe par un compte de service, pas par un compte personnel. Il ne dit rien d'un jeton Google remis à un tiers.

Au jalon 3, le chargement encode les descriptions par le plugin GenAI d'Aura ([spec 003](../specs/003-graphrag-descriptions/spec.md), [ADR-0020](0020-mvp-index-vectoriel-des-descriptions.md)) : `ai.text.embedBatch` appelle Vertex AI avec le `token` (ou l'`apiKey`) que lui donne sa configuration, depuis les serveurs d'Aura. Relevé le 2026-10-12 et le 2026-10-13 :

- la doc du plugin masque sa configuration dans le query.log, sauf pour une requête mal formée ;
- `cypher-shell` 2026.09.0 n'a que deux voies pour un paramètre, et toutes deux l'évaluent côté serveur (`:param {t: datetime()}` rend l'heure du serveur) : `-P`, qui passe aussi par la ligne de commande, visible par `ps`, et `:param` sur stdin ; le jeton arrive donc chez Aura comme littéral d'une requête `RETURN`, hors du masquage du plugin ;
- `roles/aiplatform.user` compte 459 permissions ; `aiplatform.endpoints.predict`, celle d'un appel `:predict`, peut entrer seule dans un rôle personnalisé (`gcloud iam list-testable-permissions`, GA) ;
- un jeton emprunté vaut une heure par défaut, moins avec `--lifetime` ; un chargement complet dure quelques minutes.

## Options considérées

- **Option A — Compte de service dédié, rôle limité à la prédiction, jeton de 15 minutes, par `:param` sur stdin.**
- **Option B — Le jeton de Julien** (`gcloud auth print-access-token`) : tous ses droits Google, une heure, chez Aura.
- **Option C — Une clé d'API Vertex** rangée dans Secret Manager : sans échéance.
- **Option D — L'API Query d'Aura** (HTTP) : le jeton devient un vrai paramètre, masqué par le plugin ; mais une requête de plusieurs minutes en HTTP, et un client de plus pour le chargement.
- **Option E — Ne rien faire** : pas d'encodage par le plugin ; le chargement passerait par Python, contre l'[ADR-0003](0003-mvp-chargement-cypher-pur.md).

## Décision

**Option A** (Julien : compte de service le 2026-10-12, pour le test payant ; rôle et durée le 2026-10-13, sur la préférence de Claude) :

- compte `aura-genai@jleroy-labo.iam.gserviceaccount.com`, avec un rôle personnalisé `predictionVertex` qui ne contient que `aiplatform.endpoints.predict`, à la place de `roles/aiplatform.user` posé pour le test ; Julien seul peut l'emprunter (`roles/iam.serviceAccountTokenCreator` sur ce compte) ;
- `scripts/charger.sh` prend le jeton juste avant `07`, après `06`, seulement s'il reste des descriptions sans vecteur (`--impersonate-service-account`, `--lifetime=900`, fonction de `scripts/commun.sh`) : une purge suivie d'un chargement en recrée 5 233 ; il le passe au seul `cypher/07-embeddings.cypher`, par une ligne `:param` sur le stdin de `cypher-shell`, jamais en argument ni dans un fichier ; `filtrer` le masque dans toute sortie et dans le journal du chargement ;
- jamais pour le harnais, une cellule ou un agent ; jamais écrit sur le disque.

## Conséquences

- ✅ Une fuite chez Aura n'ouvre que la prédiction sur `jleroy-labo`, pendant 15 minutes au plus ; la coupure de l'[ADR-0010](0010-infra-plafond-de-depense.md) et le plafond de l'[ADR-0013](0013-infra-plafond-natif-de-vertex.md) bornent encore la dépense.
- ✅ Un rechargement sans purge n'emprunte rien quand tout est encodé : il marche même Vertex coupé.
- ⚠️ Une reconstruction (purge puis chargement, ou preuve d'idempotence) réencode tout : elle exige Vertex et l'emprunt, et coûte environ 0,03 $.
- ⚠️ Risque restant, accepté : le jeton passe chez Aura en littéral, hors du masquage du plugin.
- ⚠️ Un chargement qui encode exige l'ADC de Julien et Vertex actif ; il échoue après le 2026-12-31 si le budget n'est pas prolongé (NEO-27).
- ⚠️ La permission du rôle se confirme au premier chargement ; une erreur 403 la corrige, sans élargir au rôle prédéfini.

## Liens

- [ADR-0007](0007-infra-secrets-et-services-geres.md) (secrets, que cet ADR précise sans le remplacer) ; [ADR-0003](0003-mvp-chargement-cypher-pur.md) ; [ADR-0020](0020-mvp-index-vectoriel-des-descriptions.md)
- [Plan 003](../specs/003-graphrag-descriptions/plan.md) : D4 ; [research 003](../specs/003-graphrag-descriptions/research.md) : test payant, revue adverse
