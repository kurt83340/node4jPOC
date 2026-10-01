# Accès — node4jPOC

> Checklist des accès du POC : ✅ obtenu · ⏳ en attente · 🔒 où le trouver. **Jamais une valeur ici** :
> les secrets vivent dans GCP Secret Manager, lus au moment de servir, jamais affichés ni écrits sur le disque
> ([ADR-0007](adr/0007-infra-secrets-et-services-geres.md)).

**Dernière MAJ :** 2026-09-30

## Checklist

| Accès                       | État          | 🔒 Où le trouver                                                                             |
| --------------------------- | ------------- | -------------------------------------------------------------------------------------------- |
| Projet Google Cloud du POC  | ✅            | `jleroy-labo`, facturation active                                                            |
| Console Aura                | ✅ 2026-09-30 | https://console.neo4j.io, connexion Google avec fr.julienleroy@gmail.com                     |
| Instance AuraDB Free        | ✅ 2026-09-30 | console Aura → Instances → « Free instance »                                                 |
| Identifiants de l'instance  | ✅ 2026-09-30 | secret `neo4j-aura-poc` du projet `jleroy-labo`                                              |
| Job de réveil `reveil-aura` | ✅ 2026-09-30 | projet `jleroy-labo` (`europe-west9`), compte `reveil-aura`, qui ne lit que `neo4j-aura-poc` |

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

## Recréer l'instance

1. Console Aura → « Create instance » → AuraDB Free ; télécharger le fichier d'identifiants hors du dépôt.
2. `gcloud secrets versions add neo4j-aura-poc --project=jleroy-labo --data-file=<fichier>`, puis
   `gcloud secrets versions destroy <ancienne version> --secret=neo4j-aura-poc --project=jleroy-labo` une fois la
   nouvelle vérifiée : une version seulement désactivée reste facturée comme active.
3. Supprimer le fichier, relancer le chargement complet, puis noter ici la date et la limite lue.
