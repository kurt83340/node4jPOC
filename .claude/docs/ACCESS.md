# Accès — node4jPOC

> Checklist des accès du POC : ✅ obtenu · ⏳ en attente · 🔒 où le trouver. **Jamais une valeur ici** :
> les secrets vivent dans GCP Secret Manager, lus au moment de servir, jamais affichés ni écrits sur le disque
> ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md)).

**Dernière MAJ :** 2026-10-08

## Checklist

| Accès                           | État          | 🔒 Où le trouver                                                                                                            |
| ------------------------------- | ------------- | --------------------------------------------------------------------------------------------------------------------------- |
| Projet Google Cloud du POC      | ✅            | `jleroy-labo`, facturation active                                                                                           |
| Console Aura                    | ✅ 2026-09-30 | https://console.neo4j.io, connexion Google avec fr.julienleroy@gmail.com                                                    |
| Instance AuraDB Free            | ✅ 2026-09-30 | console Aura → Instances → « Free instance »                                                                                |
| Identifiants de l'instance      | ✅ 2026-09-30 | secret `neo4j-aura-poc` du projet `jleroy-labo`                                                                             |
| Job de réveil `reveil-aura`     | ✅ 2026-09-30 | projet `jleroy-labo` (`europe-west9`), compte `reveil-aura`, qui ne lit que `neo4j-aura-poc`                                |
| Vertex AI (Agent Platform)      | ✅ 2026-10-07 | API `aiplatform.googleapis.com` activée sur `jleroy-labo`                                                                   |
| Claude dans Model Garden        | ✅ 2026-10-07 | Sonnet 5.5, Sonnet 5 et Haiku 4.5 : conditions acceptées (ci-dessous)                                                       |
| Quota de Claude en `eu`         | ❌ refusé     | 0, hausse refusée le 2026-10-07 ; Claude passe par l'API Anthropic ([ADR-0011](adr/0011-infra-claude-par-api-anthropic.md)) |
| Budget plafond de 100 €         | ✅ 2026-10-07 | « Plafond jleroy-labo 100 EUR (oct-dec 2026) », [ADR-0010](adr/0010-infra-plafond-de-depense.md)                            |
| API Anthropic (cellules Claude) | ✅ 2026-10-08 | https://platform.claude.com, workspace `node4jpoc-banc` : crédits sans recharge automatique, limite de 20 $ par mois        |
| Clé Anthropic du banc           | ✅ 2026-10-08 | secret `anthropic-api-banc` du projet `jleroy-labo` (`europe-west9`), lu par `scripts/banc.sh`                              |
| `neo4j-mcp` v1.6.0              | ✅ 2026-10-07 | `~/.local/share/neo4j-mcp/v1.6.0/neo4j-mcp`, somme vérifiée (plan 002, D1)                                                  |

## Instance AuraDB Free (NEO-6)

- **Création** : en un clic depuis l'accueil de la console (« Create a free instance »). Rien n'est proposé :
  nom « Free instance », Graph Analytics et Vector optimization à leur valeur par défaut.
- **Hébergement** : GCP `europe-west1` (Belgique), 1 Go de mémoire, 2 Go de stockage, Neo4j 2026.09.
- **Limite réelle : 200 000 nœuds et 400 000 relations.** La console n'affiche qu'un pourcentage. Les
  valeurs viennent de son API interne (`limits.max_node_limit`, `limits.max_relationship_limit`).
  Le graphe prévu (~10 000 nœuds, ~113 000 relations) en occupe ~5 % et ~28 %.
- **Points d'accès** (valeurs dans la console, panneau « Inspect ») : Bolt `neo4j+s://`, Query API v2, et une
  URL MCP propre à l'instance, pour le jalon 2.
- **Compte Aura** : organisation « MindToReal », projet « New project », noms posés par Aura. Questions
  d'accueil : objectif « personal or student project », rôle « Other : Personal learning project », cas
  d'usage « Generative AI ». Société pré-remplie (« Mindtorea »), laissée telle quelle. Aucun moyen de
  paiement : rien ne peut être facturé.

⚠️ **Pièges**

- L'utilisateur **et** la base portent l'identifiant de l'instance, pas `neo4j` : lire `NEO4J_USERNAME` et
  `NEO4J_DATABASE`, ne jamais coder `neo4j` en dur.
- Pause automatique après 72 h sans activité, suppression après 30 jours de pause : la relancer depuis
  le menu de l'instance, sinon la recréer (ci-dessous) et tout recharger. Le job `reveil-aura` l'évite
  (ci-dessous).
- Mot de passe perdu : menu de l'instance → « Recover Database Credentials », avant de penser à recréer.

## Explorer le graphe (console Aura, outil Query)

Pour les jalons 2 à 4 (constaté le 2026-10-01).

- **Connexion** : Query s'ouvre déconnecté (« No instance connected ») : « connect to instance », « Free instance »,
  « Connect ». Le compte Aura suffit, sans mot de passe de base (par défaut pour une organisation créée après le
  2025-05-29, [doc Aura](https://neo4j.com/docs/aura/security/tool-auth/)) ; il peut écrire : n'y lancer que des lectures.
- **Visites guidées** par-dessus : « Try the new instance explorer » → Skip ; « Work in tabs » → Dismiss.
- **Relations** : renvoyer des chemins (`MATCH chemin = (…)-[…]->(…) RETURN chemin`) ; des nœuds seuls n'en montrent aucune.
- **Légende** : les bulles affichent `id` ; panneau « Results overview », pastille du label, « Caption », puis `nom`.
  Le pilotage automatique de ce panneau échoue (la page se redessine sans cesse) : le faire à la main.
- **Sans connexion** : [page de visualisation](https://claude.ai/artifact/PtTfvzP9uXHWQGF9j2rbeB) (artefact privé, 3 extraits).

## Secret `neo4j-aura-poc`

- Projet `jleroy-labo` ; API Secret Manager activée le 2026-09-30 pour ce secret.
- Réplication `user-managed` en `europe-west9` (Paris), comme `jira-api-token`. Elle ne se change plus
  après la création : `gcloud secrets update` n'a pas d'option pour ça.
- Contenu : le fichier d'identifiants d'Aura entier, soit 6 clés (`NEO4J_URI`, `NEO4J_USERNAME`,
  `NEO4J_PASSWORD`, `NEO4J_DATABASE`, `AURA_INSTANCEID`, `AURA_INSTANCENAME`) et une ligne de commentaire.
- Lecture : `gcloud secrets versions access latest --secret=neo4j-aura-poc --project=jleroy-labo`, dans le
  script qui s'en sert, sans afficher la sortie.
- Dépôt du 2026-09-30 : version 1, depuis le fichier téléchargé par le Chrome piloté, jamais ouvert, puis
  supprimé.

## Job `reveil-aura` (NEO-13)

Déployé le 2026-09-30 par [`infra/reveil-aura/deploy.sh`](../../infra/reveil-aura/deploy.sh), réexécutable ;
exploitation : [RUNBOOK](RUNBOOK.md).

- **Compte de service** `reveil-aura@jleroy-labo.iam.gserviceaccount.com` : `roles/secretmanager.secretAccessor`
  sur le seul secret `neo4j-aura-poc`, et `roles/run.invoker` sur le seul job, pour que Cloud Scheduler le lance.
- **Job Cloud Run** `reveil-aura`, région `europe-west9` : le secret y est monté en fichier
  (`/secrets/neo4j-aura-poc`, version `latest`, relue à chaque exécution) ; le script n'en journalise rien.
- **Cloud Scheduler** `reveil-aura`, même région : chaque jour à 9 h (`Europe/Paris`), avec un jeton OAuth du
  compte ci-dessus ; 2 reprises si l'appel à Cloud Run échoue.
- **Alerte** « reveil-aura : réveil d'Aura en échec » (Cloud Monitoring, condition sur journaux) et canal e-mail
  vers fr.julienleroy@gmail.com, actif sans vérification ; expéditeur `alerting-noreply@google.com`.
- **Construction de l'image** : Cloud Build, sous le compte Compute Engine par défaut
  `848118418359-compute@developer.gserviceaccount.com`, créé à l'activation de Cloud Run. Il a `roles/editor`,
  posé par Google (projet sans organisation), et `roles/run.builder`, posé par `deploy.sh`. Image dans le dépôt
  Artifact Registry `cloud-run-source-deploy` (les 2 dernières versions sont gardées), sources dans le bucket
  `run-sources-jleroy-labo-europe-west9`.
- **Poste local** : composant `beta` de gcloud, installé le 2026-09-30 ; seul `beta` sait créer un canal e-mail.

⚠️ **Pièges**

- Premier déploiement : le build a échoué, le rôle `run.builder` posé une minute plus tôt n'étant pas encore
  propagé. Relancer `deploy.sh` a suffi.
- Un compte de service tout juste créé met quelques secondes à être visible de l'IAM : `deploy.sh` réessaie.

## Vertex AI et Model Garden (NEO-15)

Ouverts le 2026-10-07 pour la spec 002 ; appels par l'ADC de fr.julienleroy@gmail.com, sans clé API.

- **API** `aiplatform.googleapis.com` activée sur `jleroy-labo` (`gcloud services enable`).
- **Claude dans Model Garden** : Sonnet 5.5, Sonnet 5 et Haiku 4.5. Conditions de Google Cloud Marketplace et
  d'Anthropic acceptées par Julien sur la page « Agreements » (accords `anthropic-915`, `anthropic-896`,
  `anthropic-867`). Questionnaire rempli à l'identique pour les trois : Julien Leroy, https://github.com/kurt83340,
  fr.julienleroy@gmail.com, France, « Education », « Internal employees », POC d'apprentissage (banc text-to-Cypher,
  données publiques PokéAPI, base en lecture seule, faible volume), « No » aux exigences de la politique d'usage.
- **Identifiants des modèles** : `claude-sonnet-5-5`, `claude-sonnet-5`, `claude-haiku-4-5@20251001` ;
  `gemini-3.8-flash` répond sans activation ni demande de quota.
- **Quotas** : Claude à 0 en `eu` comme en `global` ; hausse demandée et refusée d'office le 2026-10-07 (préférences
  `eu-claude-*`, compte jugé non éligible). Détail et suite : [plan 002](specs/002-agent-text-to-cypher/plan.md),
  relevé de T0.2.
- **Budget** « Plafond jleroy-labo 100 EUR (oct-dec 2026) » ([ADR-0010](adr/0010-infra-plafond-de-depense.md)) :
  100 € cumulés du 2026-10-01 au 2026-12-31, filtré sur `jleroy-labo`, e-mails à 25, 50, 75, 90 et 100 % aux
  administrateurs de la facturation (compte `019774-B0D77F-72CED7`). Vue : `/google-facture`. Coupure
  automatique de Vertex : à construire.

⚠️ **Pièges**

- Le questionnaire ne suffit pas : c'est la page « Agreements » qui suit qui vaut acceptation. La page de prix de
  Google ne liste pas encore Sonnet 5.5 : ses prix se lisent sur cet accord, lieu `eu`.
- L'ADC du poste a `jleroy-outils` pour projet de quota : un agent fixe `GOOGLE_CLOUD_QUOTA_PROJECT=jleroy-labo`,
  et `GOOGLE_APPLICATION_CREDENTIALS` sous un HOME temporaire (liste blanche du banc).

## API Anthropic (NEO-15)

Ouverte le 2026-10-08 pour les deux cellules Claude, à la place de Vertex ([ADR-0011](adr/0011-infra-claude-par-api-anthropic.md)).

- **Console** : https://platform.claude.com, compte de Julien ; workspace dédié `node4jpoc-banc` (le workspace par
  défaut n'accepte pas de limite de dépense).
- **Dépense** : 20 $ de crédits prépayés, recharge automatique coupée : à zéro, l'API s'arrête. Limite mensuelle du
  workspace : 20 $. Recharge à la main, sur décision de Julien, après le pilote. Usage visible dans la Console en
  5 min environ.
- **Clé** : créée dans ce workspace ; secret `anthropic-api-banc` du projet `jleroy-labo` (réplication `europe-west9`),
  déposé par Julien en saisie masquée, lu au lancement par `scripts/banc.sh` et passé au harnais par l'environnement.
  Contrôle sans affichage : taille et préfixe `sk-ant-` (skill `secret-manager`).
- **Renouveler la clé** : en créer une dans le workspace, l'ajouter en version (`gcloud secrets versions add
anthropic-api-banc --project=jleroy-labo --data-file=-`, saisie masquée), relancer `scripts/banc.sh acces`, puis
  révoquer l'ancienne dans la Console et détruire son ancienne version.

⚠️ **Piège** : l'invite masquée de `read -rs` attend la valeur de la clé, pas un nom. Une saisie vide crée le secret sans
version (« Created secret » sans « Created version ») ; la création suivante échoue alors sur un conflit : ajouter une
version au lieu de recréer (vu le 2026-10-08).

## Recréer l'instance

1. Console Aura → « Create instance » → AuraDB Free ; télécharger le fichier d'identifiants hors du dépôt.
2. `gcloud secrets versions add neo4j-aura-poc --project=jleroy-labo --data-file=<fichier>`, puis
   `gcloud secrets versions destroy <ancienne version> --secret=neo4j-aura-poc --project=jleroy-labo` une fois la
   nouvelle vérifiée : une version seulement désactivée reste facturée comme active.
3. Supprimer le fichier, relancer le chargement complet, puis noter ici la date et la limite lue.
