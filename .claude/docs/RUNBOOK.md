# Runbook — node4jPOC

> Procédures d'exploitation des services déployés : redéployer, lancer, lire les journaux, réagir à une
> alerte, couper. Accès et identifiants : [ACCESS.md](ACCESS.md). Aucun secret ici.

**Dernière MAJ :** 2026-10-13

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

## Lancer une campagne du banc (spec 002)

Une campagne pose les 30 questions aux cellules, passe après passe ; elle est payante. Avant : le feu vert de Julien et
un plafond (`--plafond-usd`, réserve de 1 $ comprise), qui arrête la campagne en code 3 s'il allait être dépassé.

```bash
uv run --directory banc python -m banc traduire --vers logs/anglais   # schéma anglais seulement : traduction à jour
scripts/banc.sh lancer --campagne <id> --passes 3 --plafond-usd <$> [--cellules adk-gemini] [--schema en]
scripts/banc.sh lancer --campagne <id> --plafond-usd <$> --reprendre  # après un arrêt : rejoue pannes et coupures
uv run --directory banc python -m banc rapport --campagne <id> --complet   # 0 : complète
uv run --directory banc python -m banc revoir --campagne <id> --verifier   # 0 : aucun cas à revoir
```

- Avant de créer ou de reprendre une campagne, `banc lancer` vérifie que la base est dans la langue de la campagne
  (`scripts/charger.sh --langue` : noms, contraintes et index) et, en anglais, que `logs/anglais` est à jour.
- Une seule campagne à la fois sur le poste (verrou). Pendant qu'elle tourne, ne pas modifier `banc/` : chaque
  cellule l'importe à son lancement.
- Codes retour : 0 finie, 1 finie avec une passe invalide, 2 erreur technique, 3 plafond de dépense atteint (crédits
  ou plafond de la campagne : décision de Julien, puis `--reprendre`), 130 interrompue.
- Revue : assistée ([ADR-0014](adr/0014-mvp-revue-assistee.md)), avec une contre-épreuve de 8 cas tirés au sort.

Précision du 2026-10-13 (spec 003, T1.1) : la revue assistée passe par `banc contre-epreuve`, une fois la campagne
complète. Ordre : tirage ; page montrée à Julien ; pré-analyse de Claude écrite sur `tous.txt` dans
`logs/revues/<id>/preanalyse.json`, son SHA-256 annoncé avant les réponses de Julien ; accord ; chaque désaccord
présenté, puis tranché par Julien ; enregistrement.

```bash
uv run --directory banc python -m banc contre-epreuve --campagne <id>                      # page, tous.txt, cles.json
uv run --directory banc python -m banc contre-epreuve --campagne <id> --accord "1 j | 2 p o"  # 0 : aucun désaccord
uv run --directory banc python -m banc contre-epreuve --campagne <id> --enregistrer [<fichier>]  # 0 : plus rien à revoir
```

## Basculer le schéma en anglais, puis revenir (spec 002, D8)

```bash
scripts/charger.sh --schema en --explain   # à blanc : EXPLAIN de chaque requête, rien d'écrit
scripts/charger.sh --schema en             # bascule (44 s le 2026-10-11) ; --tout est refusé tant qu'elle dure
scripts/charger.sh --langue                # en ; contraintes et index de la langue en ligne ; db.propertyKeys()
scripts/questions.sh --verifier --dossier logs/anglais   # les 27 requêtes traduites rendent attendu/
scripts/questions.sh --exemples --dossier logs/anglais   # fiche anglaise, dracofeu~, balayage : aucun
scripts/charger.sh --schema fr             # retour (40 s)
scripts/verifier.sh && scripts/questions.sh --verifier && scripts/questions.sh --exemples   # base de référence intacte
```

- Une bascule coupée (réseau, Aura) se relance telle quelle : rien ne se fait deux fois. `--langue` dit alors
  « mixte » (noms des deux langues) ou « incomplète » (contraintes ou index absents), et `banc lancer` refuse de
  partir.
- `db.propertyKeys()` garde les noms de clés de l'autre langue, orphelins : sans effet sur les données, à revoir avant
  qu'Aura Agent lise le schéma (jalon 4). Repli complet : `--purge`, puis `--tout`.

## Index vectoriel des descriptions (spec 003, D2 à D4)

L'index `descriptions_texte` (`Description.embedding`, 3 072 dimensions, `cosine`, sans quantification) se déclare
dans `cypher/00-contraintes.cypher` ; `cypher/07-embeddings.cypher` encode les descriptions qui n'ont pas de vecteur
([ADR-0020](adr/0020-mvp-index-vectoriel-des-descriptions.md)). Contrôle, en lecture seule :

```bash
scripts/verifier.sh --section embeddings   # 5 233 vecteurs de 3 072 dimensions, index en ligne avec ses options
```

Une écriture à la main, avec l'accord de Julien, passe par les fonctions des scripts : identifiants lus dans Secret
Manager, jamais affichés, et sortie filtrée.

```bash
bash -c 'set -euo pipefail; source scripts/commun.sh; trouver_outils; lire_identifiants; code=0
  cypher "$1" --format verbose || code=$?; printf "%s\n" "$SORTIE"; exit "$code"' _ "<requête>"
```

- **Réindexer** (index absent, en échec ou réglé autrement) : `DROP INDEX descriptions_texte IF EXISTS`, puis
  `scripts/charger.sh --tout` : `00-contraintes.cypher` recrée l'index, qui se remplit des vecteurs déjà stockés, et
  `07` n'encode rien quand tout est encodé (ni jeton, ni dépense). Puis `scripts/verifier.sh --section embeddings`.
- **Retirer les vecteurs**, par lots :
  `MATCH (d:Description) WHERE d.embedding IS NOT NULL CALL (d) { REMOVE d.embedding } IN TRANSACTIONS OF 1000 ROWS`.
  Le chargement suivant réencode les 5 233 descriptions : c'est une reconstruction complète (ci-dessous).
- **Changer la quantification ou la dimension** : un nouvel ADR d'abord (ADR-0020), sauf le repli `scalar` prévu par le
  plan 003 (circuit breaker, noté daté au plan). Puis `00-contraintes.cypher`, l'attendu de
  `cypher/90-verification.cypher` et `banc anglais` ; `DROP INDEX descriptions_texte` (`IF NOT EXISTS` garderait
  l'ancien sans rien dire) ; pour une autre dimension, retirer aussi les vecteurs et régler `07` ; enfin `--tout` et
  la vérification.
- **Reconstruction complète** (purge puis `--tout`, `--idempotence`, ou vecteurs retirés) : les 5 233 descriptions se
  réencodent, environ 0,03 $, avec le feu vert de Julien. Elle exige Vertex actif (coupure à 100 €, budget jusqu'au
  2026-12-31) et l'emprunt du compte `aura-genai` par Julien (`gcloud auth login`, rôle `predictionVertex`,
  [ADR-0019](adr/0019-infra-jeton-vertex-du-plugin-genai.md)) : jeton de 15 minutes, passé au seul `07` sur stdin.
- `scripts/charger.sh --explain` planifie `CREATE VECTOR INDEX` sans en valider les options : une option inconnue y
  passe (sondé le 2026-10-13). Seule `verifier.sh --section embeddings` les contrôle, une fois l'index créé.

## Recouper le coût d'une campagne (spec 002, D10)

- Gemini : export de facturation BigQuery (`/google-facture`), une ligne par heure d'usage et par SKU (`usage_start_time`) ; une requête `bq` par heure isole la campagne, dont les jetons (entrée hors cache, lecture du cache, sortie) égalent ceux du CSV du banc. Google compte au prix standard et retire la promotion de 50 % en crédit `DISCOUNT` ; taux : `currency_conversion_rate`. Délai observé : 4 h 35 à 6 h 43 après le début de l'heure d'usage (2026-10-11).
- Claude : usage de la Console Anthropic, jours en UTC, rafraîchi environ toutes les 4 h ; capture au moins 4 à 5 h après la fin de la campagne.
- Fuseaux : l'export compte les jours à l'heure du Pacifique, la Console en UTC ; une campagne de nuit (heure de Paris) tombe sur deux jours UTC.
- L'écart se note au relevé de la campagne (plan 002, D7) ; pour `en-1` et `fr-controle`, D8.
