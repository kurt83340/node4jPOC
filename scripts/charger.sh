#!/usr/bin/env bash
# Charge le graphe Pokémon dans AuraDB Free (spec 001). Pour l'instant : --ping (T2.1).
#
# Identifiants lus au lancement dans GCP Secret Manager (ADR-0007) : jamais écrits sur le disque ni
# affichés. Seules les 4 variables NEO4J_* passent à cypher-shell, par l'environnement : un argument
# de commande serait visible de tous les processus (ps).
#
# Codes retour : 0 = succès · 1 = Aura injoignable · 2 = configuration ou garde-fou.

set -euo pipefail
set +x

readonly SECRET="${NEO4J_SECRET:-neo4j-aura-poc}"
readonly PROJET="${GCP_PROJET:-jleroy-labo}"
SORTIE=""

usage() {
  cat <<'EOF'
Usage : scripts/charger.sh --ping

  --ping    vérifie qu'Aura répond, avec les identifiants lus dans Secret Manager

Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo).
Codes retour : 0 = succès · 1 = Aura injoignable · 2 = configuration ou garde-fou.
EOF
}

erreur() {
  printf 'charger.sh : %s\n' "$*" >&2
}

# gcloud est installé dans ~/google-cloud-sdk, absent du PATH des shells non interactifs.
trouver_outils() {
  if ! command -v gcloud >/dev/null 2>&1 && [[ -x "$HOME/google-cloud-sdk/bin/gcloud" ]]; then
    PATH="$HOME/google-cloud-sdk/bin:$PATH"
  fi
  local outil
  for outil in gcloud cypher-shell; do
    if ! command -v "$outil" >/dev/null 2>&1; then
      erreur "$outil introuvable"
      exit 2
    fi
  done
}

# Le secret reste en mémoire : son contenu n'est jamais exécuté (ni source ni eval) et passe par
# un tube, pas par un fichier temporaire. Seules les 4 clés NEO4J_* sont exportées.
lire_identifiants() {
  local contenu ligne cle
  if ! contenu="$(gcloud secrets versions access latest --secret="$SECRET" --project="$PROJET")"; then
    erreur "secret $SECRET illisible dans le projet $PROJET (gcloud auth login ?)"
    exit 2
  fi
  while IFS= read -r ligne; do
    ligne="${ligne%$'\r'}"
    cle="${ligne%%=*}"
    case "$cle" in
      NEO4J_URI | NEO4J_USERNAME | NEO4J_PASSWORD | NEO4J_DATABASE)
        printf -v "$cle" '%s' "${ligne#*=}"
        export "${cle?}"
        ;;
    esac
  done < <(printf '%s\n' "$contenu")
  unset contenu ligne
  for cle in NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD NEO4J_DATABASE; do
    if [[ -z "${!cle:-}" ]]; then
      erreur "clé $cle absente du secret $SECRET"
      exit 2
    fi
  done
}

# Garde-fou de sortie : SORTIE reçoit le texte sûr. Le mot de passe arrête tout ; l'identifiant de
# l'instance, qui est aussi l'utilisateur et le nom de la base, devient ‹instance›.
filtrer() {
  if [[ "$1" == *"$NEO4J_PASSWORD"* ]]; then
    erreur "sortie masquée : elle contenait le mot de passe"
    exit 2
  fi
  SORTIE="${1//"$NEO4J_USERNAME"/‹instance›}"
}

# Exécute une requête Cypher : SORTIE reçoit sa sortie filtrée, le code retour est celui de cypher-shell.
cypher() {
  local brut code=0
  brut="$(cypher-shell --non-interactive --format plain "$1" 2>&1)" || code=$?
  filtrer "$brut"
  return "$code"
}

ping_aura() {
  if ! cypher "CALL dbms.components() YIELD versions, edition RETURN 'Neo4j ' + versions[0] + ' (' + edition + ')' AS aura"; then
    erreur "Aura injoignable : instance en pause (console Aura → Resume) ou réseau coupé"
    printf '%s\n' "$SORTIE" >&2
    exit 1
  fi
  local valeur="${SORTIE#*$'\n'}"
  valeur="${valeur%%$'\n'*}"
  printf '✓ Aura répond : %s\n' "${valeur//\"/}"
}

main() {
  case "${1:-}" in
    --ping)
      trouver_outils
      lire_identifiants
      ping_aura
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
