#!/usr/bin/env bash
# Banc d'essai (spec 001, T7.1 ; spec 002, T1.3 et T2.1) : rejoue les requêtes de référence (questions/qNN.cypher
# et la liste des espèces) et compare leurs réponses à celles enregistrées dans questions/attendu/ (plan D11) ;
# exécute les exemples de la fiche de schéma ; contrôle l'équipe de Q2 proposée par un agent. Tout en lecture
# seule (--access-mode read), comme chaque technique du banc d'essai (code-map).
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
# paramètre optionnel. Par défaut, une équipe valide (6 espèces reconnues, aucun type non couvert) ; --controle
# la remplace par celle d'un agent.
PROPOSEE="['Magnéton', 'Dracolosse', 'Flagadoss', 'Noadkoko', 'Staross', 'Parasect']"
# Forme exigée de l'équipe de --controle : 6 noms entre apostrophes droites, séparés par « , », sans apostrophe,
# antislash ni caractère de contrôle. Rien ne peut alors sortir d'une chaîne Cypher : jamais un texte libre
# dans -P (D6). Le harnais n'envoie que des noms de la liste des espèces, validés puis échappés (banc.lecture).
readonly FORME_EQUIPE="^\\['[^'\\\\[:cntrl:]]+'(, '[^'\\\\[:cntrl:]]+'){5}]$"
# Recherche approchée de Q19 (spec 002, D9) : ici, pour qu'une base sans index rende un écart (1) et non une
# erreur (2). Sur le schéma anglais, sa traduction vient du dossier (exemples/dracofeu.cypher).
readonly DRACOFEU="CALL db.index.fulltext.queryNodes('noms_plein_texte', 'dracofeu~') YIELD node
RETURN node.nom AS nom"
# Recherche sans casse ni accents, que la fiche promet (analyseur standard-folding, T7.3) : ELECTRIK trouve Électrik.
# Sur le schéma anglais : exemples/electrik.cypher.
readonly ELECTRIK="CALL db.index.fulltext.queryNodes('noms_plein_texte', 'ELECTRIK') YIELD node
RETURN node.nom AS nom"

usage() {
  cat <<'EOF'
Usage : scripts/questions.sh [--dossier D] --verifier | --enregistrer [qNN|especes…] | --exemples
       scripts/questions.sh [--dossier D] --controle "['Nom', 'Nom', 'Nom', 'Nom', 'Nom', 'Nom']"

Rejoue les requêtes de référence de questions/ (qNN.cypher, puis la liste des espèces especes.cypher),
en lecture seule.

  --verifier     compare chaque réponse à celle enregistrée dans questions/attendu/ (qNN.txt, especes.txt)
  --enregistrer  écrit les réponses de la base actuelle dans questions/attendu/, toutes ou celles nommées
                 (qNN, especes) ; à relire avant de commiter : ce sont les réponses de référence
  --exemples     vérifie la fiche de schéma sur la base : ce qu'elle affirme (questions/fiche.cypher, une
                 requête par liste ou chiffre), puis ses exemples et deux recherches dans l'index plein texte ;
                 chaque exemple doit rendre au moins une ligne, dracofeu~ trouver Dracaufeu et ELECTRIK Électrik
  --controle E   contrôle de Q2 sur l'équipe E proposée par un agent : q02.cypher avec $proposee = E ;
                 E : 6 noms entre apostrophes droites, séparés par « , », sans apostrophe ni antislash ;
                 stdout ne porte que la réponse, au format de questions/attendu/
  --dossier D    lit les requêtes dans D plutôt que dans questions/ : D/qNN.cypher (et D/especes.cypher
                 s'il existe), et pour --exemples D/fiche.cypher s'il existe et D/exemples/*.cypher, dont
                 D/exemples/dracofeu.cypher et D/exemples/electrik.cypher ;
                 les réponses attendues restent celles de questions/attendu/ ; refusé avec --enregistrer

Chaque requête reçoit $proposee, l'équipe que contrôle q02.cypher : une équipe valide par défaut, celle
de --controle sinon.
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

# FICHIERS reçoit les requêtes à traiter : celles nommées (q01 ou q01.cypher, especes), sinon toutes : les
# questions, puis la liste des espèces (spec 002, D4) si le dossier la porte (questions/ la porte toujours).
# Pas de sous-shell : une requête inconnue arrête vraiment tout (voir lire_noms dans charger.sh).
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
    if [[ -f "$DOSSIER_REQUETES/especes.cypher" ]]; then
      FICHIERS+=("$DOSSIER_REQUETES/especes.cypher")
    fi
    return
  fi
  for nom in "$@"; do
    nom="${nom%.cypher}"
    if [[ ! "$nom" =~ ^(q[0-9][0-9]|especes)$ || ! -f "$DOSSIER_REQUETES/$nom.cypher" ]]; then
      erreur "requête inconnue : $nom"
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
    printf 'ÉCART : %d requête(s) sur %d.\n' "$ecarts" "${#FICHIERS[@]}"
    exit 1
  fi
  printf 'CONFORME : %d requêtes.\n' "${#FICHIERS[@]}"
}

# Contrôle de Q2 sur l'équipe d'un agent (PROPOSEE, déjà vérifiée par main) : q02.cypher, ou sa traduction avec
# --dossier (spec 002, D6). La réponse s'écrit comme les réponses de référence ; le harnais la relit et juge.
controler() {
  local fichier="$DOSSIER_REQUETES/q02.cypher"
  if [[ ! -f "$fichier" ]]; then
    erreur "aucune requête q02.cypher dans $DOSSIER_REQUETES"
    exit 2
  fi
  repondre "$fichier"
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
  EXEMPLES+=("$DRACOFEU" "$ELECTRIK")
  NOMS_EXEMPLES+=("dracofeu~" "ELECTRIK")
}

# Nom qu'une recherche dans l'index plein texte doit trouver, d'après le nom de l'exemple : dracofeu~ (faute
# d'orthographe), ELECTRIK (casse et accent) ; rien pour un autre exemple.
nom_attendu() {
  case "$1" in
    dracofeu*) printf 'Dracaufeu' ;;
    ELECTRIK | electrik*) printf 'Électrik' ;;
  esac
}

# Ce que la fiche affirme (questions/fiche.cypher, spec 002 T7.3) : chaque ligne « affirmation|attendu|obtenu » est
# jugée comme celles de verifier.sh ; un attendu vide est une information. Avec --dossier, D/fiche.cypher s'il
# existe. VALEURS et ECARTS_VALEURS comptent les vérifications et leurs écarts. Une requête en échec est un écart de
# la fiche, comme un exemple : Aura a déjà répondu à ping_aura.
VALEURS=0
ECARTS_VALEURS=0
valeurs_de_la_fiche() {
  local fichier="$DOSSIER_REQUETES/fiche.cypher" affirmation attendu obtenu
  if [[ ! -f "$fichier" ]]; then
    if ((PAR_DOSSIER)); then
      printf '  · valeurs de la fiche : pas de fiche.cypher dans %s\n' "$DOSSIER_REQUETES"
      return
    fi
    erreur "questions/fiche.cypher introuvable"
    exit 2
  fi
  printf '── valeurs de la fiche\n'
  if ! cypher_fichier "$fichier" --access-mode read; then
    printf '✗ fiche.cypher : %s\n' "${SORTIE%%$'\n'*}"
    ECARTS_VALEURS=1
    return
  fi
  while IFS='|' read -r affirmation attendu obtenu; do
    if [[ -z "$attendu" ]]; then
      printf '  · %s : %s\n' "$affirmation" "$obtenu"
      continue
    fi
    VALEURS=$((VALEURS + 1))
    if [[ "$obtenu" == "$attendu" ]]; then
      printf '✓ %s : %s\n' "$affirmation" "$obtenu"
    else
      printf '✗ %s : %s, attendu %s\n' "$affirmation" "$obtenu" "$attendu"
      ECARTS_VALEURS=$((ECARTS_VALEURS + 1))
    fi
  done < <(printf '%s\n' "$SORTIE" | sed -n 's/^"\(.*\)"$/\1/p')
  if ((VALEURS == 0)); then
    erreur "aucune valeur de la fiche lue : sortie de cypher-shell inattendue"
    exit 2
  fi
}

# Un exemple qui échoue (index absent compris) ou ne rend aucune ligne est un écart de la fiche, pas une
# erreur technique : Aura a déjà répondu à ping_aura.
exemples() {
  local i nom attendu ecarts=0
  valeurs_de_la_fiche
  lire_exemples
  printf '── exemples\n'
  for i in "${!EXEMPLES[@]}"; do
    nom="${NOMS_EXEMPLES[i]}"
    attendu="$(nom_attendu "$nom")"
    if ! cypher "${EXEMPLES[i]}" --access-mode read; then
      printf '✗ %s : %s\n' "$nom" "${SORTIE%%$'\n'*}"
      ecarts=$((ecarts + 1))
    elif [[ "$SORTIE" != *$'\n'* ]]; then
      printf '✗ %s : aucune ligne\n' "$nom"
      ecarts=$((ecarts + 1))
    elif [[ -n "$attendu" && $'\n'"$SORTIE"$'\n' != *$'\n'\""$attendu"\"$'\n'* ]]; then
      printf '✗ %s : %s absent du résultat\n' "$nom" "$attendu"
      ecarts=$((ecarts + 1))
    else
      printf '✓ %s\n' "$nom"
    fi
  done
  if ((ecarts + ECARTS_VALEURS > 0)); then
    printf 'ÉCART : valeurs de la fiche, %d écart(s) ; exemples, %d sur %d.\n' "$ECARTS_VALEURS" "$ecarts" \
      "${#EXEMPLES[@]}"
    exit 1
  fi
  printf 'CONFORME : %d valeurs de la fiche, %d exemples.\n' "$VALEURS" "${#EXEMPLES[@]}"
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
      --controle)
        if [[ -n "$mode" ]] || (($# < 2)); then
          usage >&2
          exit 2
        fi
        if [[ ! "$2" =~ $FORME_EQUIPE ]]; then
          erreur "--controle : 6 noms attendus, ['Nom', 'Nom', …], sans apostrophe ni antislash dans un nom"
          exit 2
        fi
        mode="$1"
        PROPOSEE="$2"
        shift
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
  readonly PROPOSEE
  trouver_outils
  lire_identifiants
  # Avec --controle, stdout ne porte que la réponse, que le harnais relit : le test de connexion passe sur stderr.
  if [[ "$mode" == --controle ]]; then
    ping_aura >&2
  else
    ping_aura
  fi
  case "$mode" in
    --verifier) verifier ;;
    --enregistrer) enregistrer "${noms[@]}" ;;
    --exemples) exemples ;;
    --controle) controler ;;
  esac
}

main "$@"
