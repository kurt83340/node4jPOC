#!/usr/bin/env bash
# Banc d'essai (spec 001, T7.1) : rejoue les requêtes de référence (questions/qNN.cypher) et compare leurs
# réponses à celles enregistrées dans questions/attendu/ (plan D11). Tout en lecture seule
# (--access-mode read), comme chaque technique du banc d'essai (code-map).
#
# Identifiants, garde-fou de sortie et codes retour communs (0 = conforme · 1 = écart constaté ·
# 2 = erreur technique) : voir commun.sh (ADR-0007).

set -euo pipefail
set +x

# shellcheck source=scripts/commun.sh
source "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

DOSSIER_QUESTIONS="$(dirname "${BASH_SOURCE[0]}")/../questions"
readonly DOSSIER_QUESTIONS

usage() {
  cat <<'EOF'
Usage : scripts/questions.sh --verifier | --enregistrer [qNN…]

Rejoue les requêtes de référence de questions/ (qNN.cypher), en lecture seule.

  --verifier     compare chaque réponse à celle enregistrée dans questions/attendu/qNN.txt
  --enregistrer  écrit les réponses de la base actuelle dans questions/attendu/, toutes ou celles des
                 qNN nommées ; à relire avant de commiter : ce sont les réponses de référence

Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo).
Codes retour : 0 = conforme · 1 = écart constaté · 2 = erreur technique.
EOF
}

# Réponse d'une question : un en-tête (le commit PokéAPI dont viennent les données), puis la sortie de
# cypher-shell en format plain, déjà filtrée. Les requêtes trient tout (ORDER BY total, listes triées) :
# la même base donne toujours le même texte (plan D11).
repondre() {
  local fichier="$1"
  if ! cypher_fichier "$fichier" --access-mode read; then
    erreur "${fichier##*/} : ${SORTIE%%$'\n'*}"
    exit 2
  fi
  printf '// PokéAPI %s · %s\n%s\n' "$COMMIT_POKEAPI" "${fichier##*/}" "$SORTIE"
}

# FICHIERS reçoit les questions à traiter : celles nommées (q01 ou q01.cypher), sinon toutes. Pas de
# sous-shell : une question inconnue arrête vraiment tout (voir lire_noms dans charger.sh).
FICHIERS=()
choisir() {
  local nom
  FICHIERS=()
  if (($# == 0)); then
    FICHIERS=("$DOSSIER_QUESTIONS"/q[0-9][0-9].cypher)
    if [[ ! -f "${FICHIERS[0]}" ]]; then
      erreur "aucune question dans questions/"
      exit 2
    fi
    return
  fi
  for nom in "$@"; do
    nom="${nom%.cypher}"
    if [[ ! "$nom" =~ ^q[0-9][0-9]$ || ! -f "$DOSSIER_QUESTIONS/$nom.cypher" ]]; then
      erreur "question inconnue : $nom"
      exit 2
    fi
    FICHIERS+=("$DOSSIER_QUESTIONS/$nom.cypher")
  done
}

# La réponse est lue en entier avant d'être écrite : une erreur ne laisse aucun fichier à moitié écrit.
enregistrer() {
  local fichier cible reponse
  choisir "$@"
  mkdir -p "$DOSSIER_QUESTIONS/attendu"
  for fichier in "${FICHIERS[@]}"; do
    cible="$DOSSIER_QUESTIONS/attendu/$(basename "$fichier" .cypher).txt"
    reponse="$(repondre "$fichier")"
    printf '%s\n' "$reponse" >"$cible"
    printf '✓ %s enregistrée\n' "$(basename "$cible")"
  done
}

verifier() {
  local fichier nom attendu obtenu ecarts=0
  choisir
  for fichier in "${FICHIERS[@]}"; do
    nom="$(basename "$fichier" .cypher)"
    attendu="$DOSSIER_QUESTIONS/attendu/$nom.txt"
    if [[ ! -f "$attendu" ]]; then
      printf '✗ %s : aucune réponse enregistrée\n' "$nom"
      ecarts=$((ecarts + 1))
      continue
    fi
    obtenu="$(repondre "$fichier")"
    if [[ "$obtenu" == "$(<"$attendu")" ]]; then
      printf '✓ %s\n' "$nom"
    else
      printf '✗ %s : réponse différente de attendu/%s.txt\n' "$nom" "$nom"
      diff <(printf '%s\n' "$(<"$attendu")") <(printf '%s\n' "$obtenu") | sed 's/^/    /' || true
      ecarts=$((ecarts + 1))
    fi
  done
  if ((ecarts > 0)); then
    printf 'ÉCART : %d question(s) sur %d.\n' "$ecarts" "${#FICHIERS[@]}"
    exit 1
  fi
  printf 'CONFORME : %d questions.\n' "${#FICHIERS[@]}"
}

main() {
  case "${1:-}" in
    --verifier)
      trouver_outils
      lire_identifiants
      ping_aura
      verifier
      ;;
    --enregistrer)
      shift
      trouver_outils
      lire_identifiants
      ping_aura
      enregistrer "$@"
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
