#!/usr/bin/env bash
# Lanceur stdio de neo4j-mcp v1.6.0 pour les agents du banc d'essai (spec 002, D1) : lit le secret
# d'Aura, règle le serveur en lecture seule et sans télémétrie, puis se remplace par lui (exec).
#
# Un client MCP (Claude Code, ADK) le lance par son chemin absolu, depuis un dossier vide hors du
# dépôt, dans l'environnement réduit de D3 : il n'emploie que bash, gcloud et neo4j-mcp, pris dans
# le PATH. stdin et stdout sont le canal MCP : rien n'y est lu ni écrit avant l'exec. Le stderr du
# serveur passe par filtrer_flux (ADR-0007).
#
# Usage : /chemin/absolu/scripts/mcp-neo4j.sh, sans argument.
# Variables : NEO4J_SECRET (défaut neo4j-aura-poc), GCP_PROJET (défaut jleroy-labo).
# Codes retour : 2 = erreur technique avant l'exec ; ensuite, ceux du serveur.

set -euo pipefail
set +x

# Sans dirname : le PATH des agents ne contient que les outils voulus.
# shellcheck source=scripts/commun.sh
source "${BASH_SOURCE[0]%/*}/commun.sh"

# neo4j-mcp fait passer ses options avant l'environnement : --read-only false rouvrirait l'écriture.
if (($#)); then
  erreur "aucun argument accepté : la configuration du serveur est fixée par ce lanceur"
  exit 2
fi

# La configuration du serveur ne vient que d'ici : toute variable NEO4J_* héritée est retirée, dont
# les 14 anciens noms que la v1.6.0 lit encore quand le nom canonique est vide.
unset "${!NEO4J_@}"
# La clé Anthropic de la cellule Claude Code (ADR-0011), comme tout accès à Claude hérité, s'arrête
# ici : neo4j-mcp, binaire tiers, n'en a pas l'usage.
unset "${!ANTHROPIC_@}" CLAUDE_CODE_OAUTH_TOKEN

# Rien sur stdout, et gcloud sans stdin : il lirait les premiers messages du client.
trouver_outils gcloud neo4j-mcp >&2
lire_identifiants </dev/null >&2

# Noms du tag v1.6.0 (plan, D1). Booléens en toutes lettres : une valeur invalide prendrait le défaut
# du serveur, soit l'écriture permise et la télémétrie active.
export NEO4J_MCP_URI="$NEO4J_URI" NEO4J_MCP_USERNAME="$NEO4J_USERNAME" \
  NEO4J_MCP_PASSWORD="$NEO4J_PASSWORD" NEO4J_MCP_DATABASE="$NEO4J_DATABASE" \
  NEO4J_MCP_READ_ONLY=true NEO4J_MCP_TELEMETRY=false NEO4J_MCP_TRANSPORT_MODE=stdio
# Anciens noms hors de l'environnement du serveur, gardés par le shell pour filtrer_flux.
export -n NEO4J_URI NEO4J_USERNAME NEO4J_PASSWORD NEO4J_DATABASE

# Le filtre écrit sur le stderr d'origine et ne garde aucune copie du canal MCP.
exec neo4j-mcp 2> >(
  exec >&2
  filtrer_flux
)
