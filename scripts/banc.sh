#!/usr/bin/env bash
# Lance le harnais du banc d'essai (banc/) avec la clé Anthropic des cellules Claude (ADR-0011) :
# la lit dans GCP Secret Manager, la passe par l'environnement, puis se remplace par le harnais (exec).
#
# La clé n'est jamais écrite sur le disque, ni passée en argument, ni affichée, même en erreur ; le
# harnais ne lit jamais Secret Manager. Une commande du banc qui n'appelle pas Claude se lance sans ce
# script : uv run --directory banc python -m banc <commande>.
#
# Usage : scripts/banc.sh <commande du banc> [options] (par exemple : scripts/banc.sh acces).
# Variables : ANTHROPIC_SECRET (défaut anthropic-api-banc), GCP_PROJET (défaut jleroy-labo).
# Codes retour : 2 = erreur technique avant l'exec ; ensuite, ceux du harnais.

set -euo pipefail
set +x

# shellcheck source=scripts/commun.sh
source "${BASH_SOURCE[0]%/*}/commun.sh"

readonly SECRET_ANTHROPIC="${ANTHROPIC_SECRET:-anthropic-api-banc}"
# Le harnais reçoit le PATH de l'appelant, tel quel : gcloud, qu'on va chercher dans
# ~/google-cloud-sdk/bin s'il manque, ne sert ici qu'à lire la clé. Sans lui dans son PATH, le
# harnais ne peut joindre ni Secret Manager ni la base (répétition générale, T5.1).
readonly PATH_APPELANT="$PATH"
RACINE="$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)"
readonly RACINE

trouver_outils gcloud uv

# gcloud sans stdin ; la clé reste en mémoire, jamais dans un fichier temporaire.
if ! cle="$(gcloud secrets versions access latest --secret="$SECRET_ANTHROPIC" \
  --project="$PROJET" </dev/null)"; then
  erreur "secret $SECRET_ANTHROPIC illisible dans le projet $PROJET (gcloud auth login ?)"
  exit 2
fi
cle="${cle%$'\r'}"
# Une seule clé de l'API, sur une ligne : tout autre contenu est refusé sans être affiché.
if [[ ! "$cle" =~ ^sk-ant-[A-Za-z0-9_-]+$ ]]; then
  unset cle
  erreur "le secret $SECRET_ANTHROPIC ne contient pas une clé de l'API Anthropic (sk-ant-…)"
  exit 2
fi
export ANTHROPIC_API_KEY="$cle"
unset cle

uv_chemin="$(command -v uv)"
PATH="$PATH_APPELANT" exec "$uv_chemin" run --directory "$RACINE/banc" python -m banc "$@"
