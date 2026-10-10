#!/usr/bin/env bash
# Déploie la coupure automatique de Vertex (ADR-0010, NEO-26) dans le projet Google Cloud du POC :
# - fonction Cloud Run coupure-vertex, construite depuis ce dossier, sous un compte de service qui ne
#   peut que lire l'état d'un service et le désactiver (rôle personnalisé) ;
# - sujet Pub/Sub coupure-vertex et déclencheur Eventarc, sous un compte qui ne peut qu'appeler la
#   fonction ;
# - alertes par e-mail : fonction en échec, Vertex coupé ;
# - le budget de 100 € relié au sujet : il y publie son état plusieurs fois par jour ;
# - plafond natif mensuel sur Vertex (budget « spend cap », Preview), créé une fois par l'API Budget.
#
# Réexécutable : chaque étape vérifie l'existant. Relancer le script redéploie le code et remet la
# configuration dans l'état décrit ici, sauf le plafond natif : tant qu'il agit, Google refuse de le
# modifier (RUNBOOK). Aucun secret ne passe par ce script ; le jeton d'accès de l'API Budget passe
# par un fichier temporaire lisible du seul utilisateur, jamais en argument (ps).
#
# Codes retour, comme les autres scripts : 0 = succès · 2 = erreur technique.
set -euo pipefail
# Toute commande qui échoue arrête le script avec le code 2, comme une erreur technique.
trap 'erreur "échec à la ligne $LINENO : relancer le script une fois la cause corrigée"; exit 2' ERR

readonly PROJET="${GCP_PROJET:-jleroy-labo}"
readonly REGION="${GCP_REGION:-europe-west9}"
readonly FACTURATION="${COMPTE_FACTURATION:-019774-B0D77F-72CED7}"
# Projet de quota des appels à l'API Budget : billingbudgets.googleapis.com y est activée.
readonly PROJET_QUOTA="${PROJET_QUOTA:-jleroy-outils}"
readonly BUDGET="${BUDGET_NOM:-Plafond jleroy-labo 100 EUR (oct-dec 2026)}"
readonly EMAIL="${ALERTE_EMAIL:-fr.julienleroy@gmail.com}"
readonly PLAFOND_MENSUEL="${PLAFOND_MENSUEL_EUR:-30}"
readonly NOM="coupure-vertex"
readonly COMPTE="$NOM@$PROJET.iam.gserviceaccount.com"
readonly COMPTE_DECLENCHEUR="$NOM-declencheur@$PROJET.iam.gserviceaccount.com"
readonly ROLE="coupureVertex"
# Vertex AI dans le catalogue de facturation (export BigQuery, relevé le 2026-10-10).
readonly SERVICE_FACTURATION="services/C7E2-9256-1C43"
readonly PLAFOND_NOM="Plafond natif Vertex $PROJET (mensuel)"
DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DOSSIER

usage() {
  cat <<'EOF'
Usage : infra/coupure-vertex/deploy.sh

Crée ou met à jour, dans le projet Google Cloud du POC : les API nécessaires, le rôle personnalisé
coupureVertex, les comptes de service de la fonction et de son déclencheur, le sujet Pub/Sub, la
fonction Cloud Run, le déclencheur Eventarc, les alertes par e-mail, le lien du budget vers le sujet
et, une fois, le plafond natif mensuel sur Vertex. Réexécutable.

Variables : GCP_PROJET (défaut jleroy-labo), GCP_REGION (défaut europe-west9),
COMPTE_FACTURATION (défaut 019774-B0D77F-72CED7), PROJET_QUOTA (défaut jleroy-outils),
BUDGET_NOM (défaut « Plafond jleroy-labo 100 EUR (oct-dec 2026) »),
ALERTE_EMAIL (défaut fr.julienleroy@gmail.com), PLAFOND_MENSUEL_EUR (défaut 30).
Codes retour : 0 = succès · 2 = erreur technique.
EOF
}

erreur() {
  printf 'deploy.sh : %s\n' "$*" >&2
}

etape() {
  printf '→ %s\n' "$*"
}

# gcloud est installé dans ~/google-cloud-sdk, absent du PATH des shells non interactifs.
trouver_outils() {
  if ! command -v gcloud >/dev/null 2>&1 && [[ -x "$HOME/google-cloud-sdk/bin/gcloud" ]]; then
    PATH="$HOME/google-cloud-sdk/bin:$PATH"
  fi
  local outil
  for outil in gcloud curl python3; do
    if ! command -v "$outil" >/dev/null 2>&1; then
      erreur "$outil introuvable"
      exit 2
    fi
  done
  # Tester par la liste des composants : appeler « gcloud beta » proposerait de l'installer.
  local beta
  beta="$(gcloud components list --filter=id=beta --format='value(state.name)' 2>/dev/null)"
  # « Update Available » dès qu'une version plus récente de gcloud sort : le composant est là.
  case "$beta" in
    Installed | "Update Available") ;;
    *)
      erreur "composant beta de gcloud absent (canal e-mail) : gcloud components install beta"
      exit 2
      ;;
  esac
}

# Un compte ou un rôle tout juste créé met quelques secondes à être visible de l'IAM : on réessaie.
avec_patience() {
  local essai
  for essai in 1 2 3 4 5 6; do
    if "$@" >/dev/null; then
      return 0
    fi
    erreur "essai $essai refusé, nouvel essai dans 10 s"
    sleep 10
  done
  return 1
}

activer_api() {
  etape "API : Cloud Run, Cloud Build, Artifact Registry, Eventarc, Pub/Sub, IAM"
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com eventarc.googleapis.com pubsub.googleapis.com \
    iam.googleapis.com --project="$PROJET"
}

# Cloud Build construit l'image avec le compte Compute Engine par défaut : il lui faut le rôle Cloud
# Run Builder (déjà posé par infra/reveil-aura/deploy.sh ; sans effet s'il est là).
autoriser_build() {
  local numero
  numero="$(gcloud projects describe "$PROJET" --format='value(projectNumber)')"
  etape "Rôle Cloud Run Builder pour le compte de build $numero-compute@developer.gserviceaccount.com"
  avec_patience gcloud projects add-iam-policy-binding "$PROJET" \
    --member="serviceAccount:$numero-compute@developer.gserviceaccount.com" \
    --role=roles/run.builder --condition=None
}

# Aucun rôle prédéfini ne se limite à désactiver un service : roles/serviceusage.serviceUsageAdmin
# permet aussi de les activer. serviceusage.operations.get, en test pour les rôles personnalisés,
# n'est pas utile : la fonction relit l'état du service.
creer_role() {
  local action=create
  etape "Rôle personnalisé $ROLE : lire l'état d'un service et le désactiver"
  if gcloud iam roles describe "$ROLE" --project="$PROJET" >/dev/null 2>&1; then
    action=update
  fi
  gcloud iam roles "$action" "$ROLE" --project="$PROJET" --title="Coupure de Vertex" \
    --description="Lire l'état d'un service et le désactiver, rien d'autre (NEO-26)" \
    --permissions=serviceusage.services.get,serviceusage.services.disable --stage=GA \
    --quiet >/dev/null
}

creer_comptes() {
  local compte description
  for compte in "$COMPTE" "$COMPTE_DECLENCHEUR"; do
    if [[ "$compte" == "$COMPTE" ]]; then
      description="coupure-vertex : désactive Vertex au plafond de dépense"
    else
      description="coupure-vertex : remet les messages du budget à la fonction"
    fi
    etape "Compte de service $compte"
    if ! gcloud iam service-accounts describe "$compte" --project="$PROJET" >/dev/null 2>&1; then
      gcloud iam service-accounts create "${compte%%@*}" --project="$PROJET" \
        --display-name="$description"
    fi
  done
  etape "Rôle $ROLE pour $COMPTE"
  avec_patience gcloud projects add-iam-policy-binding "$PROJET" \
    --member="serviceAccount:$COMPTE" --role="projects/$PROJET/roles/$ROLE" --condition=None
  etape "Réception des événements Eventarc pour $COMPTE_DECLENCHEUR"
  avec_patience gcloud projects add-iam-policy-binding "$PROJET" \
    --member="serviceAccount:$COMPTE_DECLENCHEUR" --role=roles/eventarc.eventReceiver \
    --condition=None
}

creer_sujet() {
  etape "Sujet Pub/Sub $NOM"
  if ! gcloud pubsub topics describe "$NOM" --project="$PROJET" >/dev/null 2>&1; then
    gcloud pubsub topics create "$NOM" --project="$PROJET" >/dev/null
  fi
}

# Identifiant du budget de la coupure, retrouvé par son nom.
id_budget() {
  local nom
  nom="$(gcloud billing budgets list --billing-account="$FACTURATION" \
    --billing-project="$PROJET_QUOTA" --format=json |
    python3 -c 'import json, sys
noms = [b["name"] for b in json.load(sys.stdin) if b.get("displayName") == sys.argv[1]]
print(noms[0] if len(noms) == 1 else "")' "$BUDGET")"
  if [[ -z "$nom" ]]; then
    erreur "budget « $BUDGET » introuvable, ou en double, sur le compte $FACTURATION"
    exit 2
  fi
  printf '%s' "${nom##*/}"
}

deployer_fonction() {
  local budget_id
  budget_id="$(id_budget)"
  etape "Fonction Cloud Run $NOM ($REGION), construite par Cloud Build depuis $DOSSIER"
  # Une requête à la fois, une instance au plus : deux messages ne se croisent pas.
  gcloud run deploy "$NOM" --project="$PROJET" --region="$REGION" --source="$DOSSIER" \
    --function=coupure --base-image=python314 \
    --service-account="$COMPTE" --no-allow-unauthenticated \
    --set-env-vars="PROJET=$PROJET,BUDGET_ID=$budget_id" \
    --concurrency=1 --max-instances=1 --cpu=1 --memory=512Mi --timeout=120s \
    --quiet
  etape "Droit d'appeler la fonction, pour le seul compte du déclencheur"
  avec_patience gcloud run services add-iam-policy-binding "$NOM" --project="$PROJET" \
    --region="$REGION" --member="serviceAccount:$COMPTE_DECLENCHEUR" --role=roles/run.invoker
}

creer_declencheur() {
  etape "Déclencheur Eventarc $NOM : sujet $NOM → fonction $NOM"
  if ! gcloud eventarc triggers describe "$NOM" --project="$PROJET" --location="$REGION" \
    >/dev/null 2>&1; then
    avec_patience gcloud eventarc triggers create "$NOM" --project="$PROJET" \
      --location="$REGION" --destination-run-service="$NOM" --destination-run-region="$REGION" \
      --event-filters="type=google.cloud.pubsub.topic.v1.messagePublished" \
      --transport-topic="projects/$PROJET/topics/$NOM" \
      --service-account="$COMPTE_DECLENCHEUR"
  fi
}

# Le canal e-mail n'existe qu'en beta dans gcloud ; la politique d'alerte, elle, est en GA.
alerter() {
  local canal politique fichier titre
  etape "Canal de notification : $EMAIL"
  canal="$(gcloud beta monitoring channels list --project="$PROJET" \
    --filter="type=\"email\" AND labels.email_address=\"$EMAIL\"" --format='value(name)' --limit=1)"
  if [[ -z "$canal" ]]; then
    canal="$(gcloud beta monitoring channels create --project="$PROJET" --type=email \
      --display-name="E-mail $EMAIL" --channel-labels="email_address=$EMAIL" --format='value(name)')"
  fi
  for fichier in "$DOSSIER/alerte-echec.json" "$DOSSIER/alerte-coupure.json"; do
    titre="$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["displayName"])' \
      "$fichier")"
    etape "Alerte « $titre »"
    politique="$(gcloud monitoring policies list --project="$PROJET" \
      --filter="displayName=\"$titre\"" --format='value(name)' --limit=1)"
    if [[ -z "$politique" ]]; then
      gcloud monitoring policies create --project="$PROJET" \
        --policy-from-file="$fichier" --notification-channels="$canal" >/dev/null
    else
      gcloud monitoring policies update "$politique" --project="$PROJET" \
        --policy-from-file="$fichier" --set-notification-channels="$canal" >/dev/null
    fi
  done
}

# Relié en dernier : les premiers messages trouvent la fonction, son déclencheur et ses alertes.
relier_budget() {
  local budget_id
  budget_id="$(id_budget)"
  etape "Budget « $BUDGET » relié au sujet $NOM"
  gcloud billing budgets update "$budget_id" --billing-account="$FACTURATION" \
    --billing-project="$PROJET_QUOTA" \
    --notifications-rule-pubsub-topic="projects/$PROJET/topics/$NOM" >/dev/null
}

# Créé une fois : tant qu'il agit, Google refuse de le modifier ou de le supprimer. Pas de commande
# gcloud pour un plafond natif : l'API Budget, avec le jeton de l'utilisateur.
plafonner() {
  local existant numero code
  existant="$(gcloud billing budgets list --billing-account="$FACTURATION" \
    --billing-project="$PROJET_QUOTA" --format=json |
    python3 -c 'import json, sys
print(sum(b.get("displayName") == sys.argv[1] for b in json.load(sys.stdin)))' "$PLAFOND_NOM")"
  if [[ "$existant" != "0" ]]; then
    etape "Plafond natif « $PLAFOND_NOM » : déjà en place"
    return
  fi
  etape "Plafond natif « $PLAFOND_NOM » : $PLAFOND_MENSUEL € par mois sur Vertex"
  numero="$(gcloud projects describe "$PROJET" --format='value(projectNumber)')"
  # Jeton dans un fichier lisible du seul utilisateur, jamais en argument (ps) : printf est interne.
  (
    umask 077
    printf 'Authorization: Bearer %s\n' "$(gcloud auth print-access-token)" >"$TRAVAIL/entete"
  )
  python3 - "$numero" "$SERVICE_FACTURATION" "$PLAFOND_MENSUEL" "$PLAFOND_NOM" \
    >"$TRAVAIL/plafond.json" <<'EOF'
import json, sys
numero, service, montant, nom = sys.argv[1:]
print(json.dumps({
    "displayName": nom,
    "budgetFilter": {
        "projects": [f"projects/{numero}"],
        "services": [service],
        "creditTypesTreatment": "EXCLUDE_ALL_CREDITS",
        "calendarPeriod": "MONTH",
    },
    "amount": {"specifiedAmount": {"currencyCode": "EUR", "units": montant, "nanos": 0}},
    "thresholdRules": [{"thresholdPercent": seuil} for seuil in (0.5, 0.8, 1.0)],
    "notificationsRule": {"enableProjectLevelRecipients": True},
    "spendCap": {"inputState": "CONFIGURED"},
}))
EOF
  code="$(curl -sS -o "$TRAVAIL/reponse" -w '%{http_code}' -X POST -H "@$TRAVAIL/entete" \
    -H "x-goog-user-project: $PROJET_QUOTA" -H "Content-Type: application/json; charset=utf-8" \
    --data-binary "@$TRAVAIL/plafond.json" \
    "https://billingbudgets.googleapis.com/v1/billingAccounts/$FACTURATION/budgets")"
  if [[ "$code" != "200" ]]; then
    erreur "plafond natif refusé ($code) : $(head -c 600 "$TRAVAIL/reponse")"
    exit 2
  fi
}

main() {
  case "${1:-}" in
    "")
      TRAVAIL="$(mktemp -d)"
      trap 'rm -rf "$TRAVAIL"' EXIT
      trouver_outils
      activer_api
      autoriser_build
      creer_role
      creer_comptes
      creer_sujet
      deployer_fonction
      creer_declencheur
      alerter
      relier_budget
      plafonner
      printf '✓ %s déployée (%s) : Vertex coupé quand « %s » est atteint ; plafond natif de %s € par mois\n' \
        "$NOM" "$REGION" "$BUDGET" "$PLAFOND_MENSUEL"
      printf 'Essai sans coupure, puis coupure réelle : RUNBOOK, section « Coupure de Vertex »\n'
      ;;
    -h | --help)
      usage
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
}

main "$@"
