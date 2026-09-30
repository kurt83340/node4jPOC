#!/usr/bin/env bash
# Déploie le job reveil-aura (NEO-13) dans le projet Google Cloud du POC : compte de service qui ne
# lit que le secret d'Aura, job Cloud Run construit depuis ce dossier par Cloud Build, lancement
# quotidien par Cloud Scheduler, alerte par e-mail sur toute erreur du job ou de son déclencheur.
#
# Le premier déploiement crée aussi, par gcloud, le dépôt d'images cloud-run-source-deploy et le
# bucket des sources run-sources-<projet>-<région> ; le script garde les 2 dernières images.
#
# Réexécutable : chaque étape vérifie l'existant. Relancer le script redéploie le code et remet la
# configuration dans l'état décrit ici. Aucun secret ne passe par ce script : Cloud Run lit
# neo4j-aura-poc lui-même, au démarrage de chaque exécution (ADR-0007).
#
# Codes retour, comme les autres scripts : 0 = succès · 2 = erreur technique.

set -euo pipefail
# Toute commande qui échoue arrête le script avec le code 2, comme une erreur technique.
trap 'erreur "échec à la ligne $LINENO : relancer le script une fois la cause corrigée"; exit 2' ERR

readonly PROJET="${GCP_PROJET:-jleroy-labo}"
readonly REGION="${GCP_REGION:-europe-west9}"
readonly SECRET="${NEO4J_SECRET:-neo4j-aura-poc}"
readonly EMAIL="${ALERTE_EMAIL:-fr.julienleroy@gmail.com}"
# Chaque jour à 9 h, heure de Paris : trois tentatives avant la pause des 72 h.
readonly HORAIRE="0 9 * * *"
readonly FUSEAU="Europe/Paris"
readonly JOB="reveil-aura"
readonly COMPTE="$JOB@$PROJET.iam.gserviceaccount.com"
readonly MONTAGE="/secrets/$SECRET"
DOSSIER="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly DOSSIER

usage() {
  cat <<'EOF'
Usage : infra/reveil-aura/deploy.sh

Crée ou met à jour, dans le projet Google Cloud du POC : les API nécessaires, le compte de service
reveil-aura, son droit de lecture sur le secret d'Aura, le job Cloud Run, sa planification et
l'alerte par e-mail. Réexécutable.

Variables : GCP_PROJET (défaut jleroy-labo), GCP_REGION (défaut europe-west9),
NEO4J_SECRET (défaut neo4j-aura-poc), ALERTE_EMAIL (défaut fr.julienleroy@gmail.com).
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
  if ! command -v gcloud >/dev/null 2>&1; then
    erreur "gcloud introuvable"
    exit 2
  fi
  # Tester par la liste des composants : appeler « gcloud beta » proposerait de l'installer.
  local beta
  beta="$(gcloud components list --filter=id=beta --format='value(state.name)' 2>/dev/null)"
  if [[ "$beta" != "Installed" ]]; then
    erreur "composant beta de gcloud absent (canal e-mail) : gcloud components install beta"
    exit 2
  fi
}

activer_api() {
  etape "API : Cloud Run, Cloud Build, Artifact Registry, Cloud Scheduler, IAM"
  gcloud services enable run.googleapis.com cloudbuild.googleapis.com \
    artifactregistry.googleapis.com cloudscheduler.googleapis.com iam.googleapis.com \
    --project="$PROJET"
}

# Un compte tout juste créé met quelques secondes à être visible de l'IAM : on réessaie.
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

# Cloud Build construit l'image avec le compte Compute Engine par défaut, que l'activation de Cloud
# Run crée : il lui faut le rôle Cloud Run Builder. Un job ne permet pas de choisir un autre compte.
# Le rôle met quelques minutes à se propager : au tout premier déploiement, le build peut échouer sur
# « IAM permission denied for service account …-compute@… » ; relancer le script deux minutes après.
autoriser_build() {
  local numero
  numero="$(gcloud projects describe "$PROJET" --format='value(projectNumber)')"
  etape "Rôle Cloud Run Builder pour le compte de build $numero-compute@developer.gserviceaccount.com"
  avec_patience gcloud projects add-iam-policy-binding "$PROJET" \
    --member="serviceAccount:$numero-compute@developer.gserviceaccount.com" \
    --role=roles/run.builder --condition=None
}

creer_compte() {
  etape "Compte de service $COMPTE"
  if ! gcloud iam service-accounts describe "$COMPTE" --project="$PROJET" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$JOB" --project="$PROJET" \
      --display-name="reveil-aura : lit le secret d'Aura, lance le job"
  fi
  etape "Lecture du seul secret $SECRET par ce compte"
  avec_patience gcloud secrets add-iam-policy-binding "$SECRET" --project="$PROJET" \
    --member="serviceAccount:$COMPTE" --role=roles/secretmanager.secretAccessor --condition=None
}

deployer_job() {
  etape "Job Cloud Run $JOB ($REGION), construit par Cloud Build depuis $DOSSIER"
  gcloud run jobs deploy "$JOB" --project="$PROJET" --region="$REGION" --source="$DOSSIER" \
    --service-account="$COMPTE" \
    --set-secrets="$MONTAGE=$SECRET:latest" \
    --set-env-vars="FICHIER_IDENTIFIANTS=$MONTAGE" \
    --tasks=1 --max-retries=1 --task-timeout=2m --cpu=1 --memory=512Mi \
    --quiet
  etape "Droit de lancer le job, pour Cloud Scheduler"
  avec_patience gcloud run jobs add-iam-policy-binding "$JOB" --project="$PROJET" \
    --region="$REGION" --member="serviceAccount:$COMPTE" --role=roles/run.invoker
  # Chaque déploiement pousse une image d'environ 45 Mo ; l'offre gratuite s'arrête à 0,5 Gio.
  etape "Nettoyage du dépôt d'images : les 2 dernières versions restent"
  gcloud artifacts repositories set-cleanup-policies cloud-run-source-deploy --project="$PROJET" \
    --location="$REGION" --policy="$DOSSIER/nettoyage-images.json" --quiet >/dev/null
}

planifier() {
  local action=create
  etape "Planification : « $HORAIRE » ($FUSEAU)"
  if gcloud scheduler jobs describe "$JOB" --project="$PROJET" --location="$REGION" >/dev/null 2>&1; then
    action=update
  fi
  gcloud scheduler jobs "$action" http "$JOB" --project="$PROJET" --location="$REGION" \
    --description="Lance le job Cloud Run reveil-aura (NEO-13)" \
    --schedule="$HORAIRE" --time-zone="$FUSEAU" --http-method=POST --max-retry-attempts=2 \
    --uri="https://run.googleapis.com/v2/projects/$PROJET/locations/$REGION/jobs/$JOB:run" \
    --oauth-service-account-email="$COMPTE" >/dev/null
}

# Le canal e-mail n'existe qu'en beta dans gcloud ; la politique d'alerte, elle, est en GA.
alerter() {
  local canal politique
  etape "Canal de notification : $EMAIL"
  canal="$(gcloud beta monitoring channels list --project="$PROJET" \
    --filter="type=\"email\" AND labels.email_address=\"$EMAIL\"" --format='value(name)' --limit=1)"
  if [[ -z "$canal" ]]; then
    canal="$(gcloud beta monitoring channels create --project="$PROJET" --type=email \
      --display-name="E-mail $EMAIL" --channel-labels="email_address=$EMAIL" --format='value(name)')"
  fi
  etape "Alerte sur les erreurs du job et de son déclencheur ($DOSSIER/alerte.json)"
  politique="$(gcloud monitoring policies list --project="$PROJET" \
    --filter="displayName=\"reveil-aura : réveil d'Aura en échec\"" --format='value(name)' --limit=1)"
  if [[ -z "$politique" ]]; then
    gcloud monitoring policies create --project="$PROJET" \
      --policy-from-file="$DOSSIER/alerte.json" --notification-channels="$canal" >/dev/null
  else
    gcloud monitoring policies update "$politique" --project="$PROJET" \
      --policy-from-file="$DOSSIER/alerte.json" --set-notification-channels="$canal" >/dev/null
  fi
}

main() {
  case "${1:-}" in
    "")
      trouver_outils
      activer_api
      autoriser_build
      creer_compte
      deployer_job
      planifier
      alerter
      printf '✓ %s déployé : %s, chaque jour à 9 h (%s), alerte vers %s\n' \
        "$JOB" "$REGION" "$FUSEAU" "$EMAIL"
      printf 'Essai : gcloud run jobs execute %s --project=%s --region=%s --wait\n' \
        "$JOB" "$PROJET" "$REGION"
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
