#!/usr/bin/env bash
# Vérifie le graphe chargé dans AuraDB Free (spec 001, T3.1) : comptes par motif, empreintes, noms en
# double, volume sous la limite de l'instance ; vecteurs des descriptions et leur index (spec 003, T3.1).
# Tout en lecture seule (--access-mode read).
#
# Écrit avant le chargement (plan, D8) : sur une base vide, il constate des écarts (code 1). Chaque
# fichier de cypher/ fait ensuite passer sa section au vert (--section).
#
# Identifiants, garde-fou de sortie et codes retour communs (0 = conforme · 1 = écart constaté ·
# 2 = erreur technique) : voir commun.sh (ADR-0007).

set -euo pipefail
set +x

# shellcheck source=scripts/commun.sh
source "$(dirname "${BASH_SOURCE[0]}")/commun.sh"

VERIFICATION="$(dirname "${BASH_SOURCE[0]}")/../cypher/90-verification.cypher"
readonly VERIFICATION
# Limite réelle de l'instance AuraDB Free, lue dans la console le 2026-09-30 (ACCESS.md).
readonly LIMITE_NOEUDS="${AURA_LIMITE_NOEUDS:-200000}"
readonly LIMITE_RELATIONS="${AURA_LIMITE_RELATIONS:-400000}"
readonly SECTIONS="contraintes types pokemon formes talents attaques descriptions global embeddings"

usage() {
  cat <<'EOF'
Usage : scripts/verifier.sh [--section NOM]

Compare le graphe aux valeurs attendues, calculées depuis les CSV du commit PokéAPI figé
(cypher/90-verification.cypher). Sans option : toutes les sections.

  --section NOM   une seule section : contraintes, types, pokemon, formes, talents, attaques,
                  descriptions, global ou embeddings (vecteurs des descriptions et leur index)

Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo),
AURA_LIMITE_NOEUDS (défaut 200000), AURA_LIMITE_RELATIONS (défaut 400000).
Codes retour : 0 = conforme · 1 = écart constaté · 2 = erreur technique.
EOF
}

# Lance la vérification et juge chaque ligne « section|contrôle|attendu|obtenu » de la section voulue
# (toutes si elle est vide). Un attendu vide est une information, sans verdict.
verifier() {
  local voulue="$1" section controle attendu obtenu precedente="" controles=0 ecarts=0 debut dixiemes
  debut="$(centiemes)"
  if ! cypher_fichier "$VERIFICATION" --access-mode read \
    -P "{limiteNoeuds: $LIMITE_NOEUDS, limiteRelations: $LIMITE_RELATIONS}"; then
    erreur "vérification impossible : ${SORTIE%%$'\n'*}"
    exit 2
  fi
  dixiemes=$((($(centiemes) - debut) / 10))
  # cypher-shell écrit un en-tête (« ligne ») par requête, puis chaque valeur entre guillemets.
  while IFS='|' read -r section controle attendu obtenu; do
    if [[ -n "$voulue" && "$section" != "$voulue" ]]; then
      continue
    fi
    if [[ "$section" != "$precedente" ]]; then
      printf '── %s\n' "$section"
      precedente="$section"
    fi
    if [[ -z "$attendu" ]]; then
      printf '  · %s : %s\n' "$controle" "$obtenu"
      continue
    fi
    controles=$((controles + 1))
    if [[ "$obtenu" == "$attendu" ]]; then
      printf '✓ %s : %s\n' "$controle" "$obtenu"
    else
      printf '✗ %s : %s, attendu %s\n' "$controle" "$obtenu" "$attendu"
      ecarts=$((ecarts + 1))
    fi
  done < <(printf '%s\n' "$SORTIE" | sed -n 's/^"\(.*\)"$/\1/p')
  if ((controles == 0)); then
    erreur "aucun contrôle lu${voulue:+ pour la section $voulue} : sortie de cypher-shell inattendue"
    exit 2
  fi
  if ((ecarts > 0)); then
    printf 'ÉCART : %d contrôle(s) sur %d (%d,%d s).\n' "$ecarts" "$controles" \
      $((dixiemes / 10)) $((dixiemes % 10))
    exit 1
  fi
  printf 'CONFORME : %d contrôles (%d,%d s).\n' "$controles" $((dixiemes / 10)) $((dixiemes % 10))
}

main() {
  local section=""
  case "${1:-}" in
    "") ;;
    --section)
      section="${2:-}"
      if [[ " $SECTIONS " != *" $section "* || -z "$section" ]]; then
        usage >&2
        exit 2
      fi
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
  trouver_outils
  lire_identifiants
  ping_aura
  verifier "$section"
}

main "$@"
