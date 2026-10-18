#!/usr/bin/env bash
# Cherche l'identifiant de l'instance Aura dans les traces d'une campagne du banc d'essai (spec 003, T15.1 ;
# US1). Le harnais ne le voit jamais : scripts/mcp-neo4j.sh le masque à la sortie de neo4j-mcp (code-map) ;
# ce script le vérifie après coup, ce que banc controle-traces ne peut pas faire sans le connaître. Il lit
# chaque fichier de logs/banc/<campagne>/, puis logs/banc/<campagne>.log s'il existe : la sortie de banc
# lancer, quand elle y est redirigée, porte le stderr de neo4j-mcp.
#
# Il ne rend que des comptes (fichiers lus, fichiers et lignes où l'identifiant paraît) : jamais l'identifiant,
# ni les fichiers qui le portent. Lu dans le secret d'Aura (commun.sh), l'identifiant passe à grep par un tube,
# jamais en argument (ps le montrerait), et grep ne reçoit aucune variable NEO4J_*.
#
# Usage : scripts/traces.sh --campagne <id>
# Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo), BANC_TRACES (dossier des
# traces des campagnes, défaut logs/banc du dépôt).
# Codes retour : 0 = identifiant absent · 1 = identifiant présent · 2 = erreur technique (arguments, campagne
# sans fichier, secret ou fichier illisible).

set -euo pipefail
set +x

# shellcheck source=scripts/commun.sh
source "${BASH_SOURCE[0]%/*}/commun.sh"

RACINE="$(cd "${BASH_SOURCE[0]%/*}/.." && pwd)"
readonly RACINE
readonly TRACES="${BANC_TRACES:-$RACINE/logs/banc}"

main() {
  if (($# != 2)) || [[ "$1" != --campagne ]]; then
    erreur "usage : ${0##*/} --campagne <id>"
    exit 2
  fi
  local -r campagne="$2"
  # Un code de campagne (banc.mesures.CODE), jamais un chemin.
  if [[ ! "$campagne" =~ ^[a-z0-9]+(-[a-z0-9]+)*$ ]]; then
    erreur "campagne « $campagne » : un code attendu (minuscules, chiffres, -)"
    exit 2
  fi
  local -r dossier="$TRACES/$campagne"
  local -a fichiers=()
  local fichier
  # Fichiers cachés compris, comme banc controle-traces ; une autre entrée (un dossier) sort de ce
  # qu'une campagne écrit : rien ne la montrerait sûre.
  shopt -s dotglob
  for fichier in "$dossier"/*; do
    if [[ -f "$fichier" ]]; then
      fichiers+=("$fichier")
    elif [[ -e "$fichier" ]]; then
      erreur "campagne $campagne : ${fichier##*/} n'est pas un fichier"
      exit 2
    fi
  done
  if ((${#fichiers[@]} == 0)); then
    erreur "campagne $campagne : aucun fichier dans $dossier"
    exit 2
  fi
  if [[ -f "$TRACES/$campagne.log" ]]; then
    fichiers+=("$TRACES/$campagne.log")
  fi
  trouver_outils gcloud grep
  lire_identifiants
  export -n NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD NEO4J_DATABASE
  # Lignes où paraît l'identifiant, par fichier (« chemin:nombre ») ; printf est interne au shell : le motif
  # n'entre dans aucun argument. grep sort en 1 s'il ne trouve rien, en 2 sur un fichier illisible.
  local comptes code=0
  comptes="$(grep --count --with-filename --fixed-strings \
    --file=<(printf '%s\n' "$NEO4J_USERNAME") -- "${fichiers[@]}")" || code=$?
  if ((code > 1)); then
    erreur "lecture des fichiers de la campagne $campagne impossible"
    exit 2
  fi
  local ligne nombre presents=0 lignes=0
  while IFS= read -r ligne; do
    nombre="${ligne##*:}"
    if ((nombre > 0)); then
      presents=$((presents + 1))
      lignes=$((lignes + nombre))
    fi
  done <<<"$comptes"
  if ((presents == 0)); then
    printf "traces %s : identifiant de l'instance absent des %d fichiers\n" "$campagne" "${#fichiers[@]}"
    exit 0
  fi
  printf "traces %s : identifiant de l'instance dans %d fichier(s) sur %d (%d ligne(s))\n" \
    "$campagne" "$presents" "${#fichiers[@]}" "$lignes"
  exit 1
}

main "$@"
