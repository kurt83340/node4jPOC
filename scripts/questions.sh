#!/usr/bin/env bash
# Banc d'essai (spec 001, T7.1 ; spec 002, T1.3) : rejoue les requêtes de référence (questions/qNN.cypher) et
# compare leurs réponses à celles enregistrées dans questions/attendu/ (plan D11) ; exécute les exemples de la
# fiche de schéma. Tout en lecture seule (--access-mode read), comme chaque technique du banc d'essai
# (code-map).
#
# Identifiants, garde-fou de sortie et codes retour communs (0 = conforme · 1 = écart constaté ·
# 2 = erreur technique) : voir commun.sh (ADR-0007).

set -euo pipefail
set +x

# shellcheck source=scripts/commun.sh
source "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

DOSSIER_QUESTIONS="$(dirname "${BASH_SOURCE[0]}")/../questions"
readonly DOSSIER_QUESTIONS
# Requêtes rejouées : celles de questions/, ou celles d'un autre dossier (--dossier : requêtes traduites du
# schéma anglais, spec 002 D8). Les réponses attendues restent celles de questions/attendu/.
DOSSIER_REQUETES="$DOSSIER_QUESTIONS"
PAR_DOSSIER=0
# Équipe proposée, passée à chaque requête comme $proposee (q02.cypher, spec 002 D6) : Cypher n'a pas de
# paramètre optionnel. Par défaut, une équipe valide (6 espèces reconnues, aucun type non couvert).
readonly PROPOSEE="['Magnéton', 'Dracolosse', 'Flagadoss', 'Noadkoko', 'Staross', 'Parasect']"
# Recherche approchée de Q19 (spec 002, D9) : ici, pour qu'une base sans index rende un écart (1) et non une
# erreur (2). Sur le schéma anglais, sa traduction vient du dossier (exemples/dracofeu.cypher).
readonly DRACOFEU="CALL db.index.fulltext.queryNodes('noms_plein_texte', 'dracofeu~') YIELD node
RETURN node.nom AS nom"

usage() {
  cat <<'EOF'
Usage : scripts/questions.sh [--dossier D] --verifier | --enregistrer [qNN…] | --exemples

Rejoue les requêtes de référence de questions/ (qNN.cypher), en lecture seule.

  --verifier     compare chaque réponse à celle enregistrée dans questions/attendu/qNN.txt
  --enregistrer  écrit les réponses de la base actuelle dans questions/attendu/, toutes ou celles des
                 qNN nommées ; à relire avant de commiter : ce sont les réponses de référence
  --exemples     exécute les exemples de questions/fiche-schema.md et la recherche approchée dracofeu~ :
                 chacun doit rendre au moins une ligne, et dracofeu~ trouver Dracaufeu
  --dossier D    lit les requêtes dans D plutôt que dans questions/ : D/qNN.cypher, et pour --exemples
                 D/exemples/*.cypher, dont D/exemples/dracofeu.cypher ; les réponses attendues restent
                 celles de questions/attendu/ ; refusé avec --enregistrer

Chaque requête reçoit $proposee, l'équipe que contrôle q02.cypher : une équipe valide par défaut.
Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo).
Codes retour : 0 = conforme · 1 = écart constaté · 2 = erreur technique.
EOF
}

# Réponse d'une question : un en-tête (le commit PokéAPI dont viennent les données), puis la sortie de
# cypher-shell en format plain, déjà filtrée. Les requêtes trient tout (ORDER BY total, listes triées) :
# la même base donne toujours le même texte (plan D11).
repondre() {
  local fichier="$1"
  if ! cypher_fichier "$fichier" --access-mode read -P "{proposee: $PROPOSEE}"; then
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
    FICHIERS=("$DOSSIER_REQUETES"/q[0-9][0-9].cypher)
    if [[ ! -f "${FICHIERS[0]}" ]]; then
      erreur "aucune question dans $DOSSIER_REQUETES"
      exit 2
    fi
    return
  fi
  for nom in "$@"; do
    nom="${nom%.cypher}"
    if [[ ! "$nom" =~ ^q[0-9][0-9]$ || ! -f "$DOSSIER_REQUETES/$nom.cypher" ]]; then
      erreur "question inconnue : $nom"
      exit 2
    fi
    FICHIERS+=("$DOSSIER_REQUETES/$nom.cypher")
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

# EXEMPLES reçoit les requêtes d'exemple et NOMS_EXEMPLES leurs noms : les blocs ```cypher de la fiche, puis
# dracofeu~ ; ou, avec --dossier, les fichiers de D/exemples/. Pas de sous-shell, comme pour choisir.
EXEMPLES=()
NOMS_EXEMPLES=()
lire_exemples() {
  local ligne fichier requete="" dedans=0
  EXEMPLES=()
  NOMS_EXEMPLES=()
  if ((PAR_DOSSIER)); then
    for fichier in "$DOSSIER_REQUETES"/exemples/*.cypher; do
      if [[ ! -f "$fichier" ]]; then
        erreur "aucun exemple dans $DOSSIER_REQUETES/exemples/"
        exit 2
      fi
      EXEMPLES+=("$(<"$fichier")")
      NOMS_EXEMPLES+=("${fichier##*/}")
    done
    return
  fi
  while IFS= read -r ligne || [[ -n "$ligne" ]]; do
    if ((dedans)) && [[ "$ligne" == '```' ]]; then
      EXEMPLES+=("$requete")
      NOMS_EXEMPLES+=("exemple ${#EXEMPLES[@]} de la fiche")
      requete=""
      dedans=0
    elif ((dedans)); then
      requete+="$ligne"$'\n'
    elif [[ "$ligne" == '```cypher' ]]; then
      dedans=1
    fi
  done <"$DOSSIER_QUESTIONS/fiche-schema.md"
  if ((${#EXEMPLES[@]} == 0)); then
    erreur "aucun exemple dans questions/fiche-schema.md"
    exit 2
  fi
  EXEMPLES+=("$DRACOFEU")
  NOMS_EXEMPLES+=("dracofeu~")
}

# Un exemple qui échoue (index absent compris) ou ne rend aucune ligne est un écart de la fiche, pas une
# erreur technique : Aura a déjà répondu à ping_aura.
exemples() {
  local i nom ecarts=0
  lire_exemples
  for i in "${!EXEMPLES[@]}"; do
    nom="${NOMS_EXEMPLES[i]}"
    if ! cypher "${EXEMPLES[i]}" --access-mode read; then
      printf '✗ %s : %s\n' "$nom" "${SORTIE%%$'\n'*}"
      ecarts=$((ecarts + 1))
    elif [[ "$SORTIE" != *$'\n'* ]]; then
      printf '✗ %s : aucune ligne\n' "$nom"
      ecarts=$((ecarts + 1))
    elif [[ "$nom" == dracofeu* && $'\n'"$SORTIE"$'\n' != *$'\n"Dracaufeu"\n'* ]]; then
      printf '✗ %s : Dracaufeu absent du résultat\n' "$nom"
      ecarts=$((ecarts + 1))
    else
      printf '✓ %s\n' "$nom"
    fi
  done
  if ((ecarts > 0)); then
    printf 'ÉCART : %d exemple(s) sur %d.\n' "$ecarts" "${#EXEMPLES[@]}"
    exit 1
  fi
  printf 'CONFORME : %d exemples.\n' "${#EXEMPLES[@]}"
}

main() {
  local mode="" noms=()
  while (($# > 0)); do
    case "$1" in
      --verifier | --enregistrer | --exemples)
        if [[ -n "$mode" ]]; then
          usage >&2
          exit 2
        fi
        mode="$1"
        ;;
      --dossier)
        if (($# < 2)) || [[ ! -d "$2" ]]; then
          erreur "--dossier : dossier introuvable (${2:-aucun})"
          exit 2
        fi
        DOSSIER_REQUETES="$2"
        PAR_DOSSIER=1
        shift
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      -*)
        usage >&2
        exit 2
        ;;
      *)
        noms+=("$1")
        ;;
    esac
    shift
  done
  if [[ -z "$mode" ]] || { [[ "$mode" != --enregistrer ]] && ((${#noms[@]} > 0)); }; then
    usage >&2
    exit 2
  fi
  # Les réponses de référence ne viennent que des requêtes de questions/ : jamais de requêtes traduites.
  if [[ "$mode" == --enregistrer ]] && ((PAR_DOSSIER)); then
    erreur "--dossier : refusé avec --enregistrer"
    exit 2
  fi
  trouver_outils
  lire_identifiants
  ping_aura
  case "$mode" in
    --verifier) verifier ;;
    --enregistrer) enregistrer "${noms[@]}" ;;
    --exemples) exemples ;;
  esac
}

main "$@"
