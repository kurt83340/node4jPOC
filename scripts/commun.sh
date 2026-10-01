# shellcheck shell=bash
# Fonctions communes aux scripts qui interrogent Aura (charger.sh, verifier.sh) : à sourcer, pas à lancer.
#
# Identifiants lus au lancement dans GCP Secret Manager (ADR-0007) : jamais écrits sur le disque ni
# affichés. Seules les 4 variables NEO4J_* passent à cypher-shell, par l'environnement : un argument
# de commande serait visible de tous les processus (ps).
#
# Codes retour communs : 0 = succès · 1 = écart constaté · 2 = erreur technique (Aura injoignable,
# configuration, garde-fou).

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  printf 'commun.sh : à sourcer depuis un script, pas à lancer\n' >&2
  exit 2
fi

readonly SECRET="${NEO4J_SECRET:-neo4j-aura-poc}"
readonly PROJET="${GCP_PROJET:-jleroy-labo}"
# Commit PokéAPI figé (ADR-0001) : les CSV chargés et les réponses de référence en viennent. En changer
# change les réponses de questions/attendu/.
# gitleaks y voit une clé d'API (« API » dans le nom, valeur hexadécimale) : c'est un SHA de commit public.
# shellcheck disable=SC2034 # lu par charger.sh (URL des CSV) et questions.sh (en-tête des réponses)
readonly COMMIT_POKEAPI="168b1e89467054cda2e7df43ccebbb69b459497a" # gitleaks:allow
# Texte filtré de la dernière commande cypher-shell (voir filtrer).
SORTIE=""

erreur() {
  printf '%s : %s\n' "${0##*/}" "$*" >&2
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

# Exécute un fichier .cypher (une ou plusieurs requêtes), comme cypher.
cypher_fichier() {
  local fichier="$1" brut code=0
  shift
  brut="$(cypher-shell --non-interactive --format plain "$@" --file "$fichier" 2>&1)" || code=$?
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
