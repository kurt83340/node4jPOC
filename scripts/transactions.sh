#!/usr/bin/env bash
# Arrête sur Aura les lectures des agents du banc d'essai restées actives (spec 002, D13). Un agent
# abandonné (délai dépassé, cellule tuée) peut laisser sa requête tourner : neo4j-mcp v1.6.0 ne pose
# aucun délai de transaction (#293) et, son stdin fermé, attend la fin des appels en cours (mcp-go
# v0.56.0). Le harnais (banc.orchestration) l'appelle après une conversation qui n'a pas fini
# proprement, une fois la cellule sortie : la durée mesurée n'en compte rien.
#
# Ne vise que les transactions de neo4j-mcp, qui pose sur chacune la métadonnée app =
# « MCP4NEO4J/<version> » (internal/database/service.go du tag v1.6.0) : ni le chargement, ni le
# réveil quotidien, ni ce script ne la portent. Chacun peut voir et arrêter ses propres transactions
# sans privilège (Operations Manual 2026.09, « Show and terminate transactions ») : neo4j-mcp et ce
# script se connectent avec le même utilisateur. TERMINATE est asynchrone, une transaction arrêtée
# peut rester listée un moment : le script relit jusqu'à ce qu'il n'en reste aucune.
#
# Aucune donnée écrite : arrêter une transaction ne touche pas au graphe. Tout passe en
# --access-mode read, comme les autres lectures du banc (code-map) ; ce mode et le droit d'arrêter
# sur Aura Free, que la doc ne précise pas, se vérifient sur la vraie base en T7.4.
#
# Usage : scripts/transactions.sh, sans argument.
# Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo),
# TRANSACTIONS_RELECTURES (relectures après l'arrêt, une par seconde, défaut 10).
# Codes retour : 0 = aucune lecture d'agent active (rien à arrêter, ou toutes arrêtées) · 1 = une
# lecture d'agent encore listée après les relectures · 2 = erreur technique (Aura injoignable,
# commande refusée).

set -euo pipefail
set +x

# Sans dirname, comme mcp-neo4j.sh : le harnais lance ce script par son chemin absolu.
# shellcheck source=scripts/commun.sh
source "${BASH_SOURCE[0]%/*}/commun.sh"

readonly RELECTURES="${TRANSACTIONS_RELECTURES:-10}"
# Les transactions de neo4j-mcp, quelle que soit sa version. Composer SHOW et TERMINATE dans une
# requête exige YIELD et RETURN, et un YIELD qui nomme ses colonnes (Cypher Manual 25).
readonly AGENTS="SHOW TRANSACTIONS
YIELD transactionId AS id, metaData
WHERE metaData.app STARTS WITH 'MCP4NEO4J/'"
readonly ARRETER="$AGENTS
TERMINATE TRANSACTIONS id
YIELD message
RETURN id, message"
readonly LISTER="$AGENTS
RETURN id"

# Lignes de résultat dans SORTIE : un en-tête, puis une ligne par transaction ; un résultat vide
# n'écrit rien, ou son seul en-tête : 0 dans les deux cas. $(…) a ôté le dernier saut de ligne.
compter() {
  local sauts="${SORTIE//[!$'\n']/}"
  printf '%d' "${#sauts}"
}

main() {
  if (($#)); then
    erreur "aucun argument accepté"
    exit 2
  fi
  if [[ ! "$RELECTURES" =~ ^[0-9]+$ ]]; then
    erreur "TRANSACTIONS_RELECTURES : un entier attendu"
    exit 2
  fi
  trouver_outils
  lire_identifiants
  # stdout ne porte que le compte rendu, que le harnais affiche : le test de connexion passe sur stderr.
  ping_aura >&2
  if ! cypher "$ARRETER" --access-mode read; then
    erreur "arrêt des lectures refusé : ${SORTIE%%$'\n'*}"
    exit 2
  fi
  local arretees restantes=0 releve
  arretees="$(compter)"
  for ((releve = 0; releve <= RELECTURES; releve++)); do
    if ((releve > 0)); then
      sleep 1
    fi
    if ! cypher "$LISTER" --access-mode read; then
      erreur "relecture des transactions refusée : ${SORTIE%%$'\n'*}"
      exit 2
    fi
    restantes="$(compter)"
    if ((restantes == 0)); then
      if ((arretees == 0)); then
        printf "transactions : aucune lecture d'agent active sur Aura\n"
      else
        printf "transactions : %d lecture(s) d'agent arrêtée(s) sur Aura\n" "$arretees"
      fi
      exit 0
    fi
  done
  erreur "$restantes lecture(s) d'agent encore listée(s) après $RELECTURES relecture(s)"
  exit 1
}

main "$@"
