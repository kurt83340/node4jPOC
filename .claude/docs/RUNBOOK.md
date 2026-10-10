# Runbook — node4jPOC

> Procédures d'exploitation des services déployés : redéployer, lancer, lire les journaux, réagir à une
> alerte, couper. Accès et identifiants : [ACCESS.md](ACCESS.md). Aucun secret ici.

**Dernière MAJ :** 2026-10-10

## Job `reveil-aura` (NEO-13)

Chaque jour à 9 h (heure de Paris), Cloud Scheduler lance le job Cloud Run `reveil-aura` (projet
`jleroy-labo`, région `europe-west9`). Le job envoie `RETURN 1` à la Query API d'Aura, en lecture seule,
pour que l'instance Free ne se mette pas en pause au bout de 72 h. Toute erreur du job ou de son
déclencheur envoie un e-mail à fr.julienleroy@gmail.com (expéditeur `alerting-noreply@google.com`), au
plus un par heure. Code et configuration : [`infra/reveil-aura/`](../../infra/reveil-aura/).

Dans les commandes ci-dessous, `gcloud` doit être dans le PATH (`~/google-cloud-sdk/bin`).

### Redéployer

```bash
infra/reveil-aura/deploy.sh
```

Réexécutable : il reconstruit l'image (Cloud Build) et remet toute la configuration (compte de service,
droits, planification, alerte) dans l'état décrit par le script et par `alerte.json`. Prérequis : le
composant `beta` de gcloud (`gcloud components install beta`), pour le canal e-mail. Dans un projet neuf, le
premier build peut être refusé le temps que le rôle `run.builder` se propage : relancer deux minutes après.

### Lancer à la main

```bash
gcloud run jobs execute reveil-aura --project=jleroy-labo --region=europe-west9 --wait
```

`--wait` rend la main à la fin de l'exécution ; un échec donne « The execution failed. » et un code non nul.

### Lire les journaux

```bash
# Dernières exécutions et leur état
gcloud run jobs executions list --job=reveil-aura --project=jleroy-labo --region=europe-west9 --limit=5
# Messages du script (une ligne JSON par événement) et erreurs de la plateforme
gcloud logging read 'resource.type="cloud_run_job" AND resource.labels.job_name="reveil-aura"' \
  --project=jleroy-labo --freshness=2d --limit=20 \
  --format='table(timestamp, severity, jsonPayload.message, protoPayload.status.message)'
```

### Réagir à l'e-mail d'alerte

1. Lire l'erreur dans les journaux : commande ci-dessus, ou bouton « VIEW INCIDENT » de l'e-mail. L'e-mail
   ne la cite pas : l'alerte peut naître de l'entrée d'audit de fin d'exécution, qui ne la contient pas.
2. « Aura injoignable » : l'instance est sans doute en pause. Console Aura → menu de l'instance →
   « Resume », puis attendre qu'elle repasse « Running ».
3. « HTTP 401 » ou « identifiants illisibles » : le secret ne correspond plus à l'instance (mot de passe
   changé, instance recréée) ; voir « Recréer l'instance » dans [ACCESS.md](ACCESS.md).
4. Relancer le job à la main (ci-dessus) et vérifier qu'il réussit. L'alerte se ferme seule après 24 h
   sans nouvelle erreur.

### Tester l'alerte

```bash
gcloud run jobs execute reveil-aura --project=jleroy-labo --region=europe-west9 --wait \
  --update-env-vars=FICHIER_IDENTIFIANTS=/secrets/absent
```

Échec attendu (« identifiants illisibles »), pour cette exécution seulement ; l'e-mail arrive en
quelques minutes.

### Couper, puis rétablir

```bash
gcloud scheduler jobs pause reveil-aura --project=jleroy-labo --location=europe-west9
gcloud scheduler jobs resume reveil-aura --project=jleroy-labo --location=europe-west9
```

⚠️ Un job Scheduler en pause compte toujours parmi les 3 gratuits du compte de facturation, et l'alerte
ne voit pas l'absence d'exécution : planification coupée, plus aucun e-mail.

### Tout supprimer

```bash
gcloud scheduler jobs delete reveil-aura --project=jleroy-labo --location=europe-west9
gcloud run jobs delete reveil-aura --project=jleroy-labo --region=europe-west9
gcloud monitoring policies list --project=jleroy-labo --format='value(name,displayName)'  # puis policies delete <nom>
gcloud secrets remove-iam-policy-binding neo4j-aura-poc --project=jleroy-labo \
  --member=serviceAccount:reveil-aura@jleroy-labo.iam.gserviceaccount.com --role=roles/secretmanager.secretAccessor
gcloud iam service-accounts delete reveil-aura@jleroy-labo.iam.gserviceaccount.com --project=jleroy-labo
```

Le canal e-mail, le dépôt d'images `cloud-run-source-deploy` et le bucket `run-sources-jleroy-labo-europe-west9`
peuvent servir à d'autres déploiements : les supprimer seulement s'ils ne servent plus.

## Coupure de Vertex `coupure-vertex` (NEO-26)

Le budget « Plafond jleroy-labo 100 EUR (oct-dec 2026) » publie son état plusieurs fois par jour dans le sujet
Pub/Sub `coupure-vertex` (projet `jleroy-labo`). Eventarc remet chaque message à la fonction Cloud Run
`coupure-vertex` (région `europe-west9`). Quand le coût cumulé depuis le 2026-10-01 atteint 100 €, elle
désactive `aiplatform.googleapis.com` : Gemini s'arrête, et Vertex reste coupé jusqu'à sa réactivation à la
main. Le budget voit les coûts avec jusqu'à un jour de retard, parfois plus : un plafond natif de 30 € par mois
(« Plafond natif Vertex jleroy-labo (mensuel) », Preview) suspend Vertex en quelques minutes, et se lève tout
seul le 1er du mois. Deux e-mails possibles, de `alerting-noreply@google.com` : « Vertex est coupé, le plafond
de dépense est atteint » et « la coupure automatique de Vertex a échoué ». Code et configuration :
[`infra/coupure-vertex/`](../../infra/coupure-vertex/) ; décisions : [ADR-0010](adr/0010-infra-plafond-de-depense.md)
et [ADR-0013](adr/0013-infra-plafond-natif-de-vertex.md).

⚠️ Le budget de 100 € expire le 2026-12-31 : il n'envoie plus rien ensuite, et la fonction ne coupe plus rien.
Le prolonger (console : Facturation → Budgets et alertes), ou en créer un autre et relancer `deploy.sh`
(`BUDGET_NOM=…` s'il change de nom).

### Redéployer

```bash
infra/coupure-vertex/deploy.sh
```

Réexécutable : il reconstruit la fonction (buildpack Python de Cloud Run) et remet le rôle, les comptes, le
sujet, le déclencheur, les alertes et le lien du budget dans l'état décrit par le script. Le plafond natif
n'est créé qu'une fois. Au tout premier déploiement, deux refus passent seuls après un nouvel essai :
le compte tout juste créé, « does not exist », et le déclencheur, « Eventarc service agent is not ready ».

### Vérifier la chaîne sans rien couper

```bash
budget=$(gcloud billing budgets list --billing-account=019774-B0D77F-72CED7 --billing-project=jleroy-outils \
  --filter='displayName="Plafond jleroy-labo 100 EUR (oct-dec 2026)"' --format='value(name.basename())')
gcloud pubsub topics publish coupure-vertex --project=jleroy-labo \
  --attribute="budgetId=$budget,schemaVersion=1.0,billingAccountId=019774-B0D77F-72CED7" \
  --message='{"budgetDisplayName":"essai","costAmount":1.5,"budgetAmount":100,"currencyCode":"EUR"}'
```

Dans les journaux (ci-dessous), moins d'une minute après : « sous le plafond : 1.5 EUR dépensés sur 100 EUR ».

### Lire les journaux

```bash
gcloud logging read 'resource.type="cloud_run_revision" AND resource.labels.service_name="coupure-vertex"
  AND jsonPayload.message:*' --project=jleroy-labo --freshness=1d --limit=20 \
  --format='table(timestamp, severity, jsonPayload.message)'
```

Chaque message du budget laisse une ligne : « sous le plafond », « Vertex déjà coupé » ou « Vertex coupé »
(WARNING, qui déclenche l'e-mail).

### Tester la coupure

Même message que ci-dessus, avec `"costAmount":100` : Vertex est désactivé en moins d'une minute, et l'e-mail
« Vertex est coupé » arrive dans la minute qui suit. Une alerte tout juste créée ne voit rien pendant quelques
minutes : attendre avant de tester après un premier déploiement. Puis réactiver (ci-dessous). Fait le 2026-10-10.

### Réagir à l'e-mail « Vertex est coupé »

1. Relire la facture : `/google-facture`, ou la console de facturation.
2. Décider : relever le budget de 100 €, ou laisser Vertex coupé. Tant que le coût reste au-dessus du budget, le
   message suivant recoupe Vertex : relever le budget avant de réactiver.
3. Réactiver, et vérifier :

```bash
gcloud services enable aiplatform.googleapis.com --project=jleroy-labo
gcloud services list --enabled --project=jleroy-labo --filter='config.name=aiplatform.googleapis.com'
```

### Réagir à l'e-mail « la coupure automatique de Vertex a échoué »

1. Lire l'erreur dans les journaux (ci-dessus) ou par le bouton « VIEW INCIDENT ».
2. « refusée (400) : FAILED_PRECONDITION » et Vertex toujours actif : un service activé dépend de Vertex. Si le
   plafond est atteint, couper Vertex à la main : `gcloud services disable aiplatform.googleapis.com
--project=jleroy-labo`, puis chercher le service dépendant avant de redéployer.
3. « notification illisible » : le format des messages du budget a changé ; comparer avec la doc des
   notifications programmatiques, puis corriger `main.py`.
4. Eventarc renvoie un message en échec pendant 24 h : l'erreur doit cesser une fois la cause corrigée.

### Lever le plafond natif

Pour le mois en cours seulement : console → Facturation → Budgets et alertes → le budget « Plafond natif Vertex
jleroy-labo (mensuel) » → « Lift spend cap ». Le retour à la normale peut prendre jusqu'à une heure. Tant que le
plafond agit, Google refuse de modifier ou de supprimer ce budget.

### Tout supprimer

```bash
gcloud eventarc triggers delete coupure-vertex --project=jleroy-labo --location=europe-west9
gcloud run services delete coupure-vertex --project=jleroy-labo --region=europe-west9
gcloud pubsub topics delete coupure-vertex --project=jleroy-labo
gcloud monitoring policies list --project=jleroy-labo --format='value(name,displayName)'  # puis policies delete <nom>
gcloud iam service-accounts delete coupure-vertex@jleroy-labo.iam.gserviceaccount.com --project=jleroy-labo
gcloud iam service-accounts delete coupure-vertex-declencheur@jleroy-labo.iam.gserviceaccount.com --project=jleroy-labo
gcloud iam roles delete coupureVertex --project=jleroy-labo
```

Avant de supprimer le sujet, le détacher du budget de 100 € : gcloud n'a pas d'option pour cela (587.0.0),
c'est la console, Budgets et alertes → le budget → « Manage notifications ». Le plafond natif se supprime
aussi dans la console, hors des périodes où il agit.
