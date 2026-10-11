#!/usr/bin/env bash
# Charge le graphe Pokémon dans AuraDB Free (spec 001) : --tout exécute les fichiers de cypher/ dans
# l'ordre (depuis T4.1), --idempotence prouve que le chargement est rejouable (T6.1). Autour : --ping
# (T2.1), --go-no-go (T2.2) et --purge (T3.1). Spec 002 : --schema bascule le schéma en anglais ou le
# ramène en français (D8), --sonde-renommage a choisi son mécanisme (T7.5).
#
# Identifiants, garde-fou de sortie et codes retour communs (0 = succès · 1 = écart constaté ·
# 2 = erreur technique) : voir commun.sh (ADR-0007).

set -euo pipefail
set +x

# Fonctions partagées avec verifier.sh : identifiants, garde-fou de sortie, appels à cypher-shell.
# shellcheck source=scripts/commun.sh
source "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

# CSV PokéAPI au commit figé (ADR-0001). POKEAPI_BASE sert au repli prévu par le plan (URL signée Cloud Storage).
readonly BASE="${POKEAPI_BASE:-https://raw.githubusercontent.com/PokeAPI/pokeapi/$COMMIT_POKEAPI/data/v2/csv}"
# Fichiers de chargement : cypher/00 à 89, exécutés dans l'ordre de leur numéro ; 90 et au-delà vérifient.
DOSSIER_CYPHER="$(dirname "${BASH_SOURCE[0]}")/../cypher"
readonly DOSSIER_CYPHER
# Journaux de chargement : logs/ (ignoré par git), un fichier par lancement de --tout.
DOSSIER_JOURNAUX="$(dirname "${BASH_SOURCE[0]}")/../logs"
readonly DOSSIER_JOURNAUX
JOURNAL=""
# Statistiques d'écriture du dernier --tout, une ligne par requête (voir idempotence).
STATISTIQUES=""
# Vérification en lecture seule, appelée par --idempotence pour prendre l'empreinte du graphe.
VERIFIER="$(dirname "${BASH_SOURCE[0]}")/verifier.sh"
readonly VERIFIER
# Schéma anglais (spec 002, D8) : la carte de paramètres produite par banc depuis correspondance.toml,
# le renommage, et les contraintes et index de chaque langue. Aucun Python au chargement (ADR-0003).
readonly CARTE="$DOSSIER_CYPHER/anglais/correspondance.cypher"
readonly RENOMMER="$DOSSIER_CYPHER/anglais/renommer.cypher"
readonly CONTRAINTES_FR="$DOSSIER_CYPHER/00-contraintes.cypher"
readonly CONTRAINTES_EN="$DOSSIER_CYPHER/anglais/contraintes.cypher"
# La carte, en une ligne, sans ses commentaires : passée à cypher-shell par -P (voir lire_carte).
CARTES=""
# Requêtes d'un fichier .cypher, une par case (voir lire_requetes).
REQUETES=()
ECARTS=0
NOMS=()

usage() {
  cat <<'EOF'
Usage : scripts/charger.sh --tout | --idempotence | --ping | --go-no-go | --purge | --sonde-renommage
       scripts/charger.sh --schema en|fr [--explain] | --langue

  --tout         exécute dans l'ordre les fichiers de chargement de cypher/ (00 à 89) ; une relance ne crée
                 rien ; journal dans logs/, à suivre avec tail -f quand le chargement tourne en arrière-plan
  --idempotence  prouve le chargement rejouable (T6.1) : purge, chargement, vérification, second chargement
                 qui ne doit rien créer, même vérification ; efface et recharge toute la base
  --ping         vérifie qu'Aura répond, avec les identifiants lus dans Secret Manager
  --go-no-go     contrôles en lecture seule avant tout chargement (T2.2)
  --purge        efface tout le graphe, ses contraintes et ses index, pour repartir d'une base vide
  --sonde-renommage
                 choisit le mécanisme de renommage du schéma anglais (spec 002, T7.5) : EXPLAIN de chaque
                 candidat, Cypher 25 dynamique puis APOC, en lecture seule ; rien n'est exécuté ni écrit
  --schema en|fr bascule le schéma en anglais, ou le ramène en français (spec 002, D8) : contraintes et
                 index supprimés, labels, types et clés renommés (cypher/anglais/renommer.cypher, d'après
                 la carte correspondance.cypher), contraintes et index de la langue visée recréés ; les
                 valeurs ne changent pas. --tout est refusé tant que la base est en anglais
  --explain      avec --schema : EXPLAIN de chaque requête du renommage et des contraintes, en lecture
                 seule, et liste de ce qui serait supprimé ; rien n'est exécuté ni écrit
  --langue       langue du schéma de la base, en lecture seule : fr ou en (noms, contraintes et index de la
                 langue en place), vide, mixte ou incomplète (bascule interrompue, code 1) ; banc lancer la
                 vérifie avant une campagne (spec 002, T10.0) ; relève aussi db.propertyKeys() par langue

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
  # Analyseur de l'index plein texte noms_plein_texte (cypher/00-contraintes.cypher, spec 002 D9) : sans lui,
  # le chargement s'arrêterait sur la création de l'index.
  controler "Analyseur standard-folding (index plein texte)" "1" \
    "CALL db.index.fulltext.listAvailableAnalyzers() YIELD analyzer WHERE analyzer = 'standard-folding'
     RETURN count(*) AS analyseurs"
  informer "ce qu'il fait" \
    "CALL db.index.fulltext.listAvailableAnalyzers() YIELD analyzer, description
     WHERE analyzer = 'standard-folding' RETURN description"
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

# Sonde des mécanismes de renommage (spec 002, T7.5 ; plan D8), avant d'écrire cypher/anglais/renommer.cypher (T6.1) :
# EXPLAIN planifie chaque requête sans l'exécuter, en lecture seule ; rien n'est écrit. Un mécanisme convient si ses
# quatre gestes passent : renommer un label, recréer les relations d'un type sous un autre nom (un type ne se renomme
# pas en place), renommer une propriété de nœud et une de relation, par lots pour ménager la mémoire d'Aura Free.
# Paramètres : un vrai couple de la future table (Attaque → Move, APPREND → LEARNS, nom → name, niveau → level).
readonly PARAMETRES_SONDE="{label: 'Attaque', nouveauLabel: 'Move', type: 'APPREND', nouveauType: 'LEARNS',
  cle: 'nom', nouvelleCle: 'name', cleRelation: 'niveau', nouvelleCleRelation: 'level'}"
readonly SONDE_CYPHER_25=(
  "label|MATCH (n:\$(\$label)) CALL (n) { SET n:\$(\$nouveauLabel) REMOVE n:\$(\$label) } IN TRANSACTIONS OF 10000 ROWS"
  "type de relation|MATCH (a)-[r:\$(\$type)]->(b) CALL (a, r, b) { CREATE (a)-[s:\$(\$nouveauType)]->(b) SET s = properties(r) DELETE r } IN TRANSACTIONS OF 10000 ROWS"
  "propriété de nœud|MATCH (n:\$(\$label)) WHERE n[\$cle] IS NOT NULL CALL (n) { SET n[\$nouvelleCle] = n[\$cle] REMOVE n[\$cle] } IN TRANSACTIONS OF 10000 ROWS"
  "propriété de relation|MATCH ()-[r:\$(\$type)]->() WHERE r[\$cleRelation] IS NOT NULL CALL (r) { SET r[\$nouvelleCleRelation] = r[\$cleRelation] REMOVE r[\$cleRelation] } IN TRANSACTIONS OF 10000 ROWS"
)
readonly SONDE_APOC=(
  "label|CALL apoc.refactor.rename.label(\$label, \$nouveauLabel)"
  "type de relation|CALL apoc.refactor.rename.type(\$type, \$nouveauType)"
  "propriété de nœud|CALL apoc.refactor.rename.nodeProperty(\$cle, \$nouvelleCle)"
  "propriété de relation|CALL apoc.refactor.rename.typeProperty(\$cleRelation, \$nouvelleCleRelation)"
)

# Un mécanisme : chaque geste passe par EXPLAIN ; rend 0 si tous sont planifiés.
sonder() {
  local mecanisme="$1" geste libelle requete planifies=0
  shift
  printf '── %s\n' "$mecanisme"
  for geste in "$@"; do
    libelle="${geste%%|*}"
    requete="${geste#*|}"
    if cypher "EXPLAIN $requete" --access-mode read -P "$PARAMETRES_SONDE"; then
      printf '✓ %s : planifié\n' "$libelle"
      planifies=$((planifies + 1))
    else
      printf '✗ %s : %s\n' "$libelle" "${SORTIE%%$'\n'*}"
    fi
  done
  ((planifies == $#))
}

# Les deux mécanismes sont sondés, le repli compris ; le retenu : Cypher 25 s'il passe en entier (Cypher pur, sans
# dépendre d'APOC, ADR-0003), sinon APOC.
sonde_renommage() {
  local cypher_25=0 apoc=0
  sonder "Cypher 25 : labels, types et clés dynamiques" "${SONDE_CYPHER_25[@]}" || cypher_25=$?
  sonder "APOC : apoc.refactor.rename.*" "${SONDE_APOC[@]}" || apoc=$?
  if ((cypher_25 == 0)); then
    printf 'MÉCANISME : Cypher 25 (labels, types et clés dynamiques, par lots) ; repli APOC %s.\n' \
      "$( ((apoc == 0)) && printf 'disponible' || printf 'indisponible')"
  elif ((apoc == 0)); then
    printf 'MÉCANISME : APOC (apoc.refactor.rename.*).\n'
  else
    printf 'AUCUN MÉCANISME : ni Cypher 25 ni APOC ne planifient les quatre gestes.\n'
    exit 1
  fi
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

# Supprime les contraintes (leurs index partent avec elles), puis les index restants, sauf les deux index
# LOOKUP qu'Aura crée d'office : avant une purge, ou avant de renommer le schéma (--schema).
SUPPRIMES=""
supprimer_schema() {
  local nom contraintes=0 index=0
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
  SUPPRIMES="$contraintes contrainte(s) et $index index"
}

# Écrire : seul mode de charger.sh qui détruit (plan, étape 0). Relations d'abord, par lots, pour ménager
# la mémoire d'Aura Free, puis nœuds ; enfin contraintes et index (supprimer_schema).
purger() {
  local avant requete
  compter
  avant="$COMPTE"
  for requete in "MATCH ()-[r]->() CALL (r) { DELETE r } IN TRANSACTIONS OF 10000 ROWS" \
    "MATCH (n) CALL (n) { DELETE n } IN TRANSACTIONS OF 10000 ROWS"; do
    if ! cypher "$requete"; then
      erreur "purge interrompue : ${SORTIE%%$'\n'*}"
      exit 2
    fi
  done
  supprimer_schema
  printf '✓ Purge : %s supprimés, puis %s.\n' "$avant" "$SUPPRIMES"
}

# COMPTE reçoit les nœuds et relations du graphe, en un texte : avant une purge, avant et après un renommage.
COMPTE=""
compter() {
  cypher "CALL () { MATCH (n) RETURN count(n) AS n } CALL () { MATCH ()-[r]->() RETURN count(r) AS r }
    RETURN toString(n) + ' nœuds et ' + toString(r) + ' relations' AS compte" --access-mode read || {
    erreur "comptage impossible : ${SORTIE%%$'\n'*}"
    exit 2
  }
  COMPTE="$(valeur)"
}

# CARTES reçoit la carte de paramètres du renommage (spec 002, D8), produite par banc depuis
# correspondance.toml : sans ses lignes « // », en une ligne, pour -P. Une carte sans « {cartes: » arrête tout.
lire_carte() {
  if [[ ! -f "$CARTE" ]]; then
    erreur "carte introuvable : cypher/anglais/correspondance.cypher (uv run --directory banc python -m banc anglais)"
    exit 2
  fi
  CARTES="$(sed '/^[[:space:]]*\/\//d' "$CARTE" | tr '\n' ' ')"
  if [[ "$CARTES" != "{cartes: "* ]]; then
    erreur "carte illisible : cypher/anglais/correspondance.cypher"
    exit 2
  fi
}

# RESTES reçoit ce qui porte encore un nom de l'autre langue, vers la langue visée : les nœuds des labels et
# les relations des types à renommer, et les clés à renommer, sur les nœuds comme sur les relations (revue
# adverse de la phase 6 : une bascule coupée entre les labels et les clés passait sinon pour finie). Vers fr,
# ce sont les noms anglais : SANS_RESTE dit une base en français, ou vide.
RESTES=""
readonly SANS_RESTE="0 nœuds, 0 relations, 0 clés"
restes() {
  local langue="$1"
  cypher "WITH \$cartes[\$langue] AS carte
    CALL (carte) {
      UNWIND keys(carte.labels) AS label
      CALL (label) { MATCH (n:\$(label)) RETURN count(n) AS n }
      RETURN sum(n) AS noeuds
    }
    CALL (carte) {
      UNWIND keys(carte.types) AS nomType
      CALL (nomType) { MATCH ()-[r:\$(nomType)]->() RETURN count(r) AS r }
      RETURN sum(r) AS relations
    }
    CALL (carte) {
      MATCH (n)
      RETURN sum(size([cle IN keys(n) WHERE cle IN keys(carte.cles)])) AS clesNoeuds
    }
    CALL (carte) {
      MATCH ()-[r]->()
      RETURN sum(size([cle IN keys(r) WHERE cle IN keys(carte.cles)])) AS clesRelations
    }
    RETURN toString(noeuds) + ' nœuds, ' + toString(relations) + ' relations, '
      + toString(clesNoeuds + clesRelations) + ' clés' AS restes" \
    --access-mode read -P "$CARTES" -P "{langue: '$langue'}" || {
    erreur "noms de l'autre langue non comptés : ${SORTIE%%$'\n'*}"
    exit 2
  }
  RESTES="$(valeur)"
}

# --tout sur une base anglaise y mêlerait le schéma français (spec 002, D8) : refusé, comme une erreur de garde.
refuser_si_anglais() {
  lire_carte
  restes fr
  if [[ "$RESTES" != "$SANS_RESTE" ]]; then
    erreur "base en anglais ($RESTES) : scripts/charger.sh --schema fr d'abord"
    exit 2
  fi
}

# SCHEMA_EN_PLACE reçoit l'état des contraintes et index d'une langue, en lecture seule : ceux que crée son fichier
# (contraintes_de), les index des contraintes compris, présents et en ligne. Code 0 s'ils y sont tous, 1 sinon (revue
# adverse de T10.0 : une bascule coupée entre la suppression des contraintes et leur recréation laisse des noms d'une
# seule langue, sans contraintes ni index plein texte).
SCHEMA_EN_PLACE=""
schema_en_place() {
  local fichier nom presentes etat total contraintes=() index=()
  fichier="$(contraintes_de "$1")"
  while IFS= read -r nom; do
    contraintes+=("'$nom'")
  done < <(sed -nE 's/^CREATE CONSTRAINT ([A-Za-z0-9_]+) IF NOT EXISTS.*/\1/p' "$fichier")
  while IFS= read -r nom; do
    index+=("'$nom'")
  done < <(sed -nE 's/^CREATE (FULLTEXT )?INDEX ([A-Za-z0-9_]+) IF NOT EXISTS.*/\2/p' "$fichier")
  if ((${#contraintes[@]} == 0 || ${#index[@]} == 0)); then
    erreur "aucune contrainte ou aucun index lu dans ${fichier#"$DOSSIER_CYPHER"/}"
    exit 2
  fi
  local -r liste_contraintes="[$(IFS=,; printf '%s' "${contraintes[*]}")]"
  local -r liste_index="[$(IFS=,; printf '%s' "${index[*]}")]"
  cypher "SHOW CONSTRAINTS YIELD name WHERE name IN $liste_contraintes RETURN count(*) AS presentes" \
    --access-mode read || {
    erreur "contraintes illisibles : ${SORTIE%%$'\n'*}"
    exit 2
  }
  presentes="$(valeur)"
  cypher "SHOW INDEXES YIELD name, state, owningConstraint
    WHERE name IN $liste_index OR owningConstraint IN $liste_contraintes
    RETURN toString(count(*)) + ' index, ' + toString(count(CASE WHEN state = 'ONLINE' THEN 1 END)) + ' en ligne'
      AS etat" --access-mode read || {
    erreur "index illisibles : ${SORTIE%%$'\n'*}"
    exit 2
  }
  etat="$(valeur)"
  total=$((${#index[@]} + ${#contraintes[@]}))
  SCHEMA_EN_PLACE="$presentes/${#contraintes[@]} contraintes, $etat (attendus : $total)"
  [[ "$presentes" == "${#contraintes[@]}" && "$etat" == "$total index, $total en ligne" ]]
}

# CLES_CONNUES reçoit ce que montre db.propertyKeys(), en lecture seule : toutes les clés que la base a connues, par
# langue. Neo4j garde le nom d'une clé que plus rien ne porte (D8) : après une bascule, les deux langues y restent.
# Relevé de T10.1 et T10.3.
CLES_CONNUES=""
cles_connues() {
  cypher "WITH \$cartes AS cartes
    CALL db.propertyKeys() YIELD propertyKey
    WITH cartes, collect(propertyKey) AS cles
    RETURN toString(size(cles)) + ' clés, dont '
      + toString(size([cle IN cles WHERE cle IN keys(cartes.en.cles)])) + ' françaises et '
      + toString(size([cle IN cles WHERE cle IN keys(cartes.fr.cles)])) + ' anglaises' AS connues" \
    --access-mode read -P "$CARTES" || {
    erreur "db.propertyKeys() illisible : ${SORTIE%%$'\n'*}"
    exit 2
  }
  CLES_CONNUES="$(valeur)"
}

# --langue (spec 002, D8 ; T10.0) : la langue du schéma de la base, en lecture seule, que banc lancer vérifie
# avant une campagne. fr ou en : plus aucun nom de l'autre langue, et les contraintes et index de la langue en place
# (schema_en_place) ; vide : aucun nom de l'une ni de l'autre ; mixte : les deux, bascule interrompue ; incomplète :
# une seule langue, mais pas ses contraintes et index. Mixte et incomplète : à relancer, code 1. La dernière ligne
# donne la langue : « LANGUE : fr ».
langue_de_la_base() {
  local francais anglais langue
  lire_carte
  restes en
  francais="$RESTES"
  restes fr
  anglais="$RESTES"
  if [[ "$francais" == "$SANS_RESTE" && "$anglais" == "$SANS_RESTE" ]]; then
    langue=vide
  elif [[ "$anglais" == "$SANS_RESTE" ]]; then
    langue=fr
  elif [[ "$francais" == "$SANS_RESTE" ]]; then
    langue=en
  else
    langue=mixte
  fi
  printf 'noms français : %s\nnoms anglais : %s\n' "$francais" "$anglais"
  cles_connues
  printf 'db.propertyKeys() : %s\n' "$CLES_CONNUES"
  if [[ "$langue" == fr || "$langue" == en ]]; then
    if ! schema_en_place "$langue"; then
      langue=incomplète
    fi
    printf 'contraintes et index : %s\n' "$SCHEMA_EN_PLACE"
  fi
  printf 'LANGUE : %s\n' "$langue"
  if [[ "$langue" == mixte || "$langue" == incomplète ]]; then
    exit 1
  fi
}

# REQUETES reçoit les requêtes d'un fichier .cypher, une par case, et LIBELLES le nom de chacune : le commentaire
# qui la précède sans ligne vide, sinon le début de sa première ligne. Une requête finit à une ligne terminée par « ; »
# (convention de cypher/) ; ses commentaires et son « ; » sont ôtés. Pas de sous-shell, comme lire_noms.
LIBELLES=()
lire_requetes() {
  local ligne requete="" libelle=""
  REQUETES=()
  LIBELLES=()
  while IFS= read -r ligne || [[ -n "$ligne" ]]; do
    if [[ "$ligne" =~ ^[[:space:]]*//[[:space:]]*(.*)$ ]]; then
      [[ -z "$requete" ]] && libelle="${BASH_REMATCH[1]}"
      continue
    fi
    if [[ -z "$requete" && -z "${ligne//[[:space:]]/}" ]]; then
      libelle="" # un commentaire suivi d'une ligne vide ne nomme pas la requête qui vient
      continue
    fi
    [[ -z "$requete" && -z "$libelle" ]] && libelle="${ligne:0:70}"
    requete+="$ligne"$'\n'
    if [[ "$ligne" =~ \;[[:space:]]*$ ]]; then
      REQUETES+=("${requete%;*}")
      LIBELLES+=("$libelle")
      requete=""
      libelle=""
    fi
  done <"$1"
  if [[ -n "${requete//[[:space:]]/}" ]]; then
    REQUETES+=("$requete")
    LIBELLES+=("$libelle")
  fi
}

# Contraintes et index de la langue visée : 00-contraintes.cypher en français, sa traduction par la table
# (cypher/anglais/contraintes.cypher, produite par banc) en anglais.
contraintes_de() {
  if [[ "$1" == en ]]; then
    printf '%s' "$CONTRAINTES_EN"
  else
    printf '%s' "$CONTRAINTES_FR"
  fi
}

# Bascule du schéma (spec 002, D8) : contraintes et index supprimés, labels, types et clés renommés
# (renommer.cypher, d'après la carte), contraintes et index de la langue visée recréés, puis attendus en
# ligne. Écrit, comme le chargement (code-map). Conforme si le graphe garde ses nœuds et ses relations et que
# plus rien ne porte un nom de l'autre langue. Après une coupure, on relance : rien ne se fait deux fois.
changer_schema() {
  local langue="$1" contraintes avant debut dixiemes stats ecarts=0 fichier
  contraintes="$(contraintes_de "$langue")"
  lire_carte
  # Avant de rien supprimer : un fichier absent ici laisserait la base sans contraintes ni index (revue
  # adverse de la phase 6).
  for fichier in "$RENOMMER" "$contraintes"; do
    if [[ ! -f "$fichier" || ! -s "$fichier" ]]; then
      erreur "fichier de la bascule absent ou vide, rien n'est supprimé : ${fichier#"$DOSSIER_CYPHER"/}"
      exit 2
    fi
  done
  compter
  avant="$COMPTE"
  printf '── schéma vers %s : %s\n' "$langue" "$avant"
  debut="$(centiemes)"
  supprimer_schema
  printf '✓ supprimés : %s\n' "$SUPPRIMES"
  if ! cypher_fichier "$RENOMMER" --format verbose -P "$CARTES" -P "{langue: '$langue'}"; then
    erreur "renommage interrompu, à relancer : ${SORTIE%%$'\n'*}"
    exit 2
  fi
  stats="$(printf '%s\n' "$SORTIE" | sed -nE 's/^(Added|Created|Set|Deleted|Removed) .*/    &/p')"
  printf '✓ renommés (anglais/renommer.cypher)\n%s\n' "$stats"
  if ! cypher_fichier "$contraintes" --format verbose; then
    erreur "contraintes et index non recréés : ${SORTIE%%$'\n'*}"
    exit 2
  fi
  if ! cypher "CALL db.awaitIndexes(300)"; then
    erreur "index pas en ligne après 300 s : ${SORTIE%%$'\n'*}"
    exit 2
  fi
  printf '✓ contraintes et index recréés, en ligne (%s)\n' "${contraintes#"$DOSSIER_CYPHER"/}"
  compter
  restes "$langue"
  dixiemes=$((($(centiemes) - debut) / 10))
  if [[ "$COMPTE" != "$avant" ]]; then
    printf '✗ graphe changé : %s, avant %s\n' "$COMPTE" "$avant"
    ecarts=$((ecarts + 1))
  fi
  if [[ "$RESTES" != "$SANS_RESTE" ]]; then
    printf '✗ noms de l'"'"'autre langue restants : %s\n' "$RESTES"
    ecarts=$((ecarts + 1))
  fi
  if ((ecarts > 0)); then
    printf 'ÉCART : %d contrôle(s) sur 2.\n' "$ecarts"
    exit 1
  fi
  printf 'SCHÉMA %s : %s, plus aucun nom de l'"'"'autre langue (%d,%d s).\n' "$langue" "$COMPTE" \
    $((dixiemes / 10)) $((dixiemes % 10))
}

# --explain (spec 002, D8 ; repris de T7.5) : ce que la bascule supprimerait et renommerait, puis EXPLAIN de
# chaque requête du renommage, avec la carte, de chaque commande des contraintes et index de la langue visée,
# et de l'attente des index ; en lecture seule, rien n'est exécuté ni écrit.
expliquer_schema() {
  local langue="$1" contraintes fichier i planifiees=0 total=0
  contraintes="$(contraintes_de "$langue")"
  lire_carte
  compter
  printf '── schéma vers %s, à blanc : %s\n' "$langue" "$COMPTE"
  restes "$langue"
  printf '  · à renommer : %s\n' "$RESTES"
  cypher "SHOW CONSTRAINTS YIELD name RETURN name" --access-mode read || {
    erreur "liste des contraintes illisible : ${SORTIE%%$'\n'*}"
    exit 2
  }
  lire_noms
  printf '  · contraintes à supprimer : %s\n' "${NOMS[*]:-aucune}"
  cypher "SHOW INDEXES YIELD name, type, owningConstraint WHERE type <> 'LOOKUP' AND owningConstraint IS NULL
    RETURN name" --access-mode read || {
    erreur "liste des index illisible : ${SORTIE%%$'\n'*}"
    exit 2
  }
  lire_noms
  printf '  · index à supprimer : %s\n' "${NOMS[*]:-aucun}"
  for fichier in "$RENOMMER" "$contraintes"; do
    printf '── %s\n' "${fichier#"$DOSSIER_CYPHER"/}"
    lire_requetes "$fichier"
    if [[ "$fichier" == "$contraintes" ]]; then
      REQUETES+=("CALL db.awaitIndexes(300)")
      LIBELLES+=("attente des index en ligne")
    fi
    for i in "${!REQUETES[@]}"; do
      total=$((total + 1))
      if cypher "EXPLAIN ${REQUETES[i]}" --access-mode read -P "$CARTES" -P "{langue: '$langue'}"; then
        printf '✓ %s : planifiée\n' "${LIBELLES[i]}"
        planifiees=$((planifiees + 1))
      else
        printf '✗ %s : %s\n' "${LIBELLES[i]}" "${SORTIE%%$'\n'*}"
      fi
    done
  done
  if ((planifiees < total)); then
    printf 'NON PLANIFIÉ : %d requête(s) sur %d.\n' $((total - planifiees)) "$total"
    exit 1
  fi
  printf 'PLANIFIÉ : %d requêtes, rien d'"'"'exécuté.\n' "$total"
}

# Journal (plan, § Observabilité) : chaque ligne s'affiche et s'ajoute au fichier du lancement. L'heure murale
# situe les lignes ; les durées viennent de centiemes, car l'horloge de WSL2 recule par à-coups.
journal() {
  printf '%s\n' "$@" | tee -a "$JOURNAL"
}

# Écrit : exécute dans l'ordre les fichiers de chargement, avec $base en paramètre. Chacun est idempotent
# (MERGE sur une clé contrainte, IF NOT EXISTS) : une relance ne crée rien, et après une coupure on relance
# tout. Au premier fichier en erreur, arrêt : les suivants dépendent de lui. Par fichier, le journal garde
# l'heure de début, la durée et les statistiques d'écriture de cypher-shell (une ligne par requête).
charger() {
  local fichier debut dixiemes stats
  local fichiers=("$DOSSIER_CYPHER"/[0-8][0-9]-*.cypher)
  if [[ ! -f "${fichiers[0]}" ]]; then
    erreur "aucun fichier de chargement dans cypher/"
    exit 2
  fi
  mkdir -p "$DOSSIER_JOURNAUX"
  JOURNAL="$DOSSIER_JOURNAUX/chargement-$(date +%Y%m%d-%H%M%S).log"
  printf 'Journal : logs/%s\n' "${JOURNAL##*/}"
  STATISTIQUES=""
  for fichier in "${fichiers[@]}"; do
    journal "$(date +%T) ▶ ${fichier##*/}"
    debut="$(centiemes)"
    if ! cypher_fichier "$fichier" --format verbose -P "{base: '$BASE'}"; then
      journal "$(date +%T) ✗ ${fichier##*/}" "$SORTIE" >&2
      erreur "chargement arrêté à ${fichier##*/}"
      exit 2
    fi
    dixiemes=$((($(centiemes) - debut) / 10))
    journal "$(date +%T) ✓ ${fichier##*/} ($((dixiemes / 10)),$((dixiemes % 10)) s)"
    stats="$(printf '%s\n' "$SORTIE" | sed -nE 's/^(Added|Created|Set|Deleted|Removed) .*/    &/p')"
    if [[ -n "$stats" ]]; then
      journal "$stats"
      STATISTIQUES+="$stats"$'\n'
    fi
  done
}

# Empreinte du graphe : la sortie de verifier.sh (les valeurs obtenues de chaque contrôle), sans les durées.
# verifier.sh ne fait que lire ; son code retour dit si la base est conforme.
empreinte() {
  local sortie code=0
  sortie="$("$VERIFIER" 2>&1)" || code=$?
  printf '%s\n' "$sortie" | sed -E 's/ \([0-9]+,[0-9] s\)//'
  return "$code"
}

# Preuve d'idempotence (T6.1, plan § Tests) : purge, chargement, empreinte, second chargement, même empreinte.
# Efface et réécrit toute la base : seul charger.sh le peut (code-map) ; verifier.sh, appelé deux fois, ne
# fait que lire. Idempotent si le second chargement ne crée ni ne supprime rien (ses statistiques n'ont que
# des SET) et si les deux empreintes sont conformes et identiques.
idempotence() {
  local avant apres code_avant=0 code_apres=0 ecarts=0
  purger
  charger
  avant="$(empreinte)" || code_avant=$?
  printf 'Vérification après le premier chargement : %s\n' "${avant##*$'\n'}"
  charger
  apres="$(empreinte)" || code_apres=$?
  printf 'Vérification après le second chargement : %s\n' "${apres##*$'\n'}"
  if ((code_avant == 2 || code_apres == 2)); then
    erreur "vérification impossible"
    exit 2
  fi
  printf '── idempotence\n'
  # Un second chargement écrit toujours des SET : sans statistiques, le contrôle passerait à vide.
  if [[ -z "$STATISTIQUES" ]]; then
    erreur "statistiques d'écriture absentes : cypher-shell a-t-il ignoré --format verbose ?"
    exit 2
  fi
  if grep -qiE '(created|added|deleted|removed) ' <<<"$STATISTIQUES"; then
    printf '✗ le second chargement a créé ou supprimé des éléments :\n%s' "$STATISTIQUES"
    ecarts=$((ecarts + 1))
  else
    printf '✓ second chargement : rien de créé ni de supprimé, seulement des SET\n'
  fi
  if ((code_avant == 0 && code_apres == 0)); then
    printf '✓ base conforme après chacun des deux chargements\n'
  else
    printf '✗ base non conforme après un chargement (codes %d et %d)\n' "$code_avant" "$code_apres"
    ecarts=$((ecarts + 1))
  fi
  if [[ "$avant" == "$apres" ]]; then
    printf '✓ empreintes identiques\n'
  else
    printf '✗ empreintes différentes :\n'
    diff <(printf '%s\n' "$avant") <(printf '%s\n' "$apres") || true
    ecarts=$((ecarts + 1))
  fi
  if ((ecarts > 0)); then
    printf 'NON IDEMPOTENT : %d écart(s).\n' "$ecarts"
    exit 1
  fi
  printf 'IDEMPOTENT : 3 contrôles.\n'
}

main() {
  case "${1:-}" in
    --tout)
      trouver_outils
      lire_identifiants
      ping_aura
      refuser_si_anglais
      charger
      ;;
    --idempotence)
      trouver_outils
      lire_identifiants
      ping_aura
      idempotence
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
    --sonde-renommage)
      trouver_outils
      lire_identifiants
      ping_aura
      sonde_renommage
      ;;
    --langue)
      trouver_outils
      lire_identifiants
      ping_aura
      langue_de_la_base
      ;;
    --schema)
      if [[ "${2:-}" != en && "${2:-}" != fr ]] || (($# > 3)) || [[ $# -eq 3 && "$3" != --explain ]]; then
        usage >&2
        exit 2
      fi
      trouver_outils
      lire_identifiants
      ping_aura
      if (($# == 3)); then
        expliquer_schema "$2"
      else
        changer_schema "$2"
      fi
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
