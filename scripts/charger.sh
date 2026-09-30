#!/usr/bin/env bash
# Charge le graphe Pokémon dans AuraDB Free (spec 001). Pour l'instant : --ping (T2.1) et
# --go-no-go (T2.2).
#
# Identifiants lus au lancement dans GCP Secret Manager (ADR-0007) : jamais écrits sur le disque ni
# affichés. Seules les 4 variables NEO4J_* passent à cypher-shell, par l'environnement : un argument
# de commande serait visible de tous les processus (ps).
#
# Codes retour, comme verifier.sh : 0 = succès · 1 = écart constaté · 2 = erreur technique
# (Aura injoignable, configuration, garde-fou).

set -euo pipefail
set +x

readonly SECRET="${NEO4J_SECRET:-neo4j-aura-poc}"
readonly PROJET="${GCP_PROJET:-jleroy-labo}"
# CSV PokéAPI au commit figé (ADR-0001). POKEAPI_BASE sert au repli prévu par le plan (URL signée Cloud Storage).
readonly BASE="${POKEAPI_BASE:-https://raw.githubusercontent.com/PokeAPI/pokeapi/168b1e89467054cda2e7df43ccebbb69b459497a/data/v2/csv}"
SORTIE=""
ECARTS=0

usage() {
  cat <<'EOF'
Usage : scripts/charger.sh --ping | --go-no-go

  --ping       vérifie qu'Aura répond, avec les identifiants lus dans Secret Manager
  --go-no-go   contrôles en lecture seule avant tout chargement (T2.2)

Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo),
POKEAPI_BASE (défaut : CSV PokéAPI au commit 168b1e8).
Codes retour : 0 = succès · 1 = écart constaté · 2 = erreur technique.
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

# Exécute une requête Cypher (options de cypher-shell en plus après la requête) : SORTIE reçoit
# sa sortie filtrée, le code retour est celui de cypher-shell.
cypher() {
  local requete="$1" brut code=0
  shift
  brut="$(cypher-shell --non-interactive --format plain "$@" "$requete" 2>&1)" || code=$?
  filtrer "$brut"
  return "$code"
}

# Première ligne de résultat (la ligne 1 de SORTIE est l'en-tête), sans guillemets.
valeur() {
  local v="${SORTIE#*$'\n'}"
  v="${v%%$'\n'*}"
  printf '%s' "${v//\"/}"
}

ping_aura() {
  if ! cypher "CALL dbms.components() YIELD versions, edition RETURN 'Neo4j ' + versions[0] + ' (' + edition + ')' AS aura"; then
    erreur "Aura injoignable : instance en pause (console Aura → Resume) ou réseau coupé"
    printf '%s\n' "$SORTIE" >&2
    exit 2
  fi
  printf '✓ Aura répond : %s\n' "$(valeur)"
}

# Centièmes de seconde depuis le démarrage : l'horloge murale de WSL2 recule par à-coups
# (EPOCHREALTIME et SECONDS avec elle), /proc/uptime jamais.
centiemes() {
  local depuis_demarrage _
  read -r depuis_demarrage _ </proc/uptime
  printf '%s' "${depuis_demarrage/./}"
}

# Un contrôle du go/no-go, en lecture seule (--access-mode read) : cypher-shell refuse toute écriture.
# Attendu « accepté » : seule compte l'absence d'erreur.
controler() {
  local libelle="$1" attendu="$2" requete="$3" debut dixiemes obtenu code=0
  debut="$(centiemes)"
  cypher "$requete" --access-mode read -P "{base: '$BASE'}" || code=$?
  dixiemes=$((($(centiemes) - debut) / 10))
  if ((code != 0)); then
    obtenu="erreur : ${SORTIE%%$'\n'*}"
  elif [[ "$attendu" == "accepté" ]]; then
    obtenu="accepté"
  else
    obtenu="$(valeur)"
  fi
  if [[ "$obtenu" == "$attendu" ]]; then
    printf '✓ %s : %s (%d,%d s)\n' "$libelle" "$obtenu" $((dixiemes / 10)) $((dixiemes % 10))
  else
    printf '✗ %s : %s, attendu %s\n' "$libelle" "$obtenu" "$attendu"
    ECARTS=$((ECARTS + 1))
  fi
}

# Une mesure pour information, sans verdict.
informer() {
  local libelle="$1" requete="$2"
  if cypher "$requete" --access-mode read -P "{base: '$BASE'}"; then
    printf '  · %s : %s\n' "$libelle" "$(valeur)"
  else
    printf '  · %s : erreur : %s\n' "$libelle" "${SORTIE%%$'\n'*}"
  fi
}

go_no_go() {
  ping_aura
  controler "Aura lit GitHub, languages.csv" "14" \
    "LOAD CSV WITH HEADERS FROM \$base + '/languages.csv' AS ligne RETURN count(ligne) AS lignes"
  controler "Champs multilignes, descriptions FR (total, multilignes)" "7116, 7115" \
    "LOAD CSV WITH HEADERS FROM \$base + '/pokemon_species_flavor_text.csv' AS ligne
     WITH ligne WHERE ligne.language_id = '5'
     RETURN count(*) AS fr, count(CASE WHEN ligne.flavor_text CONTAINS '\n' THEN 1 END) AS multilignes"
  controler "Gros fichier, pokemon_moves.csv" "638321" \
    "LOAD CSV WITH HEADERS FROM \$base + '/pokemon_moves.csv' AS ligne RETURN count(ligne) AS lignes"
  controler "Fins de ligne Windows, pokemon_abilities.csv avec trim" "2943" \
    "LOAD CSV WITH HEADERS FROM \$base + '/pokemon_abilities.csv' AS ligne RETURN count(toInteger(trim(ligne.slot))) AS slots"
  informer "même compte sans trim" \
    "LOAD CSV WITH HEADERS FROM \$base + '/pokemon_abilities.csv' AS ligne RETURN count(toInteger(ligne.slot)) AS slots"
  controler "Label Type sans backticks" "accepté" \
    "EXPLAIN MATCH (t:Type) RETURN count(t) AS types"
  controler "Langue par défaut de la base" "CYPHER 25" \
    "SHOW DATABASES YIELD name, defaultLanguage WHERE name <> 'system' RETURN defaultLanguage"
  if ((ECARTS > 0)); then
    printf 'NO-GO : %d écart(s).\n' "$ECARTS"
    if [[ "$(valeur)" != "CYPHER 25" ]]; then
      printf '%s\n' "  Langue : ALTER DATABASE \`<base>\` SET DEFAULT LANGUAGE CYPHER 25, sur la base system (<base> = NEO4J_DATABASE du secret)."
    fi
    exit 1
  fi
  printf 'GO : tous les contrôles passent.\n'
}

main() {
  case "${1:-}" in
    --ping)
      trouver_outils
      lire_identifiants
      ping_aura
      ;;
    --go-no-go)
      trouver_outils
      lire_identifiants
      go_no_go
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
