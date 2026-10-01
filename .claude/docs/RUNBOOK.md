# Runbook — node4jPOC

> Procédures d'exploitation des services déployés : redéployer, lancer, lire les journaux, réagir à une
> alerte, couper. Accès et identifiants : [ACCESS.md](ACCESS.md). Aucun secret ici.

**Dernière MAJ :** 2026-09-30

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
