#!/usr/bin/env bash
# Charge le graphe Pokémon dans AuraDB Free (spec 001) : --tout exécute les fichiers de cypher/ dans
# l'ordre (depuis T4.1). Autour : --ping (T2.1), --go-no-go (T2.2) et --purge (T3.1).
#
# Identifiants, garde-fou de sortie et codes retour communs (0 = succès · 1 = écart constaté ·
# 2 = erreur technique) : voir commun.sh (ADR-0007).

set -euo pipefail
set +x

# Fonctions partagées avec verifier.sh : identifiants, garde-fou de sortie, appels à cypher-shell.
# shellcheck source=scripts/commun.sh
source "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

# CSV PokéAPI au commit figé (ADR-0001). POKEAPI_BASE sert au repli prévu par le plan (URL signée Cloud Storage).
readonly BASE="${POKEAPI_BASE:-https://raw.githubusercontent.com/PokeAPI/pokeapi/168b1e89467054cda2e7df43ccebbb69b459497a/data/v2/csv}"
# Fichiers de chargement : cypher/00 à 89, exécutés dans l'ordre de leur numéro ; 90 et au-delà vérifient.
DOSSIER_CYPHER="$(dirname "${BASH_SOURCE[0]}")/../cypher"
readonly DOSSIER_CYPHER
ECARTS=0
NOMS=()

usage() {
  cat <<'EOF'
Usage : scripts/charger.sh --tout | --ping | --go-no-go | --purge

  --tout       exécute dans l'ordre les fichiers de chargement de cypher/ (00 à 89) ; une relance ne crée rien
  --ping       vérifie qu'Aura répond, avec les identifiants lus dans Secret Manager
  --go-no-go   contrôles en lecture seule avant tout chargement (T2.2)
  --purge      efface tout le graphe, ses contraintes et ses index, pour repartir d'une base vide

Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo),
POKEAPI_BASE (défaut : CSV PokéAPI au commit 168b1e8).
Codes retour : 0 = succès · 1 = écart constaté · 2 = erreur technique.
EOF
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

# NOMS reçoit les valeurs de SORTIE (une entre guillemets par ligne, après l'en-tête). La boucle tourne
# dans le shell principal : un nom inattendu arrête vraiment tout, au lieu d'entrer dans un DROP.
lire_noms() {
  local nom
  NOMS=()
  while IFS= read -r nom; do
    if [[ ! "$nom" =~ ^[A-Za-z0-9_]+$ ]]; then
      erreur "nom de contrainte ou d'index inattendu : $nom"
      exit 2
    fi
    NOMS+=("$nom")
  done < <(printf '%s\n' "$SORTIE" | sed -n 's/^"\(.*\)"$/\1/p')
}

# Écrire : seul mode de charger.sh qui détruit (plan, étape 0). Relations d'abord, par lots, pour ménager
# la mémoire d'Aura Free, puis nœuds ; enfin contraintes (leurs index partent avec elles) et index
# restants, sauf les deux index LOOKUP qu'Aura crée d'office.
purger() {
  local nom avant contraintes=0 index=0
  cypher "CALL () { MATCH (n) RETURN count(n) AS n } CALL () { MATCH ()-[r]->() RETURN count(r) AS r }
    RETURN toString(n) + ' nœuds et ' + toString(r) + ' relations' AS avant" || {
    erreur "comptage impossible : ${SORTIE%%$'\n'*}"
    exit 2
  }
  avant="$(valeur)"
  local requete
  for requete in "MATCH ()-[r]->() CALL (r) { DELETE r } IN TRANSACTIONS OF 10000 ROWS" \
    "MATCH (n) CALL (n) { DELETE n } IN TRANSACTIONS OF 10000 ROWS"; do
    if ! cypher "$requete"; then
      erreur "purge interrompue : ${SORTIE%%$'\n'*}"
      exit 2
    fi
  done
  cypher "SHOW CONSTRAINTS YIELD name RETURN name" || {
    erreur "liste des contraintes illisible : ${SORTIE%%$'\n'*}"
    exit 2
  }
  lire_noms
  for nom in "${NOMS[@]}"; do
    cypher "DROP CONSTRAINT \`$nom\` IF EXISTS" || {
      erreur "contrainte $nom non supprimée : ${SORTIE%%$'\n'*}"
      exit 2
    }
    contraintes=$((contraintes + 1))
  done
  cypher "SHOW INDEXES YIELD name, type, owningConstraint WHERE type <> 'LOOKUP' AND owningConstraint IS NULL
    RETURN name" || {
    erreur "liste des index illisible : ${SORTIE%%$'\n'*}"
    exit 2
  }
  lire_noms
  for nom in "${NOMS[@]}"; do
    cypher "DROP INDEX \`$nom\` IF EXISTS" || {
      erreur "index $nom non supprimé : ${SORTIE%%$'\n'*}"
      exit 2
    }
    index=$((index + 1))
  done
  printf '✓ Purge : %s supprimés, puis %d contrainte(s) et %d index.\n' "$avant" "$contraintes" "$index"
}

# Écrit : exécute dans l'ordre les fichiers de chargement, avec $base en paramètre. Chacun est idempotent
# (MERGE sur une clé contrainte, IF NOT EXISTS) : une relance ne crée rien, et après une coupure on relance
# tout. Au premier fichier en erreur, arrêt : les suivants dépendent de lui.
charger() {
  local fichier debut dixiemes
  local fichiers=("$DOSSIER_CYPHER"/[0-8][0-9]-*.cypher)
  if [[ ! -f "${fichiers[0]}" ]]; then
    erreur "aucun fichier de chargement dans cypher/"
    exit 2
  fi
  for fichier in "${fichiers[@]}"; do
    debut="$(centiemes)"
    if ! cypher_fichier "$fichier" -P "{base: '$BASE'}"; then
      erreur "chargement arrêté à ${fichier##*/}"
      printf '%s\n' "$SORTIE" >&2
      exit 2
    fi
    dixiemes=$((($(centiemes) - debut) / 10))
    printf '✓ %s (%d,%d s)\n' "${fichier##*/}" $((dixiemes / 10)) $((dixiemes % 10))
  done
}

main() {
  case "${1:-}" in
    --tout)
      trouver_outils
      lire_identifiants
      ping_aura
      charger
      ;;
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
    --purge)
      trouver_outils
      lire_identifiants
      ping_aura
      purger
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
