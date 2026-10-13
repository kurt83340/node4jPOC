# shellcheck shell=bash
# Fonctions communes aux scripts qui interrogent Aura (charger.sh, mcp-neo4j.sh…) : à sourcer, pas à lancer.
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
# Compte de service du plugin GenAI d'Aura (spec 003, D4 ; ADR-0019) : rôle predictionVertex seul, emprunté
# par Julien seul, pour un jeton de 15 minutes, le temps d'un chargement qui encode.
readonly COMPTE_GENAI="aura-genai@$PROJET.iam.gserviceaccount.com"
readonly DUREE_JETON=900
# Texte filtré de la dernière commande cypher-shell (voir filtrer).
SORTIE=""
# Jeton emprunté par cypher_fichier_avec_jeton : jamais exporté ni écrit ; filtrer le masque jusqu'à la fin
# du script.
JETON=""

erreur() {
  printf '%s : %s\n' "${0##*/}" "$*" >&2
}

# gcloud est installé dans ~/google-cloud-sdk, absent du PATH des shells non interactifs.
trouver_outils() {
  (($#)) || set -- gcloud cypher-shell # outils vérifiés : ceux passés en arguments, sinon ceux-ci
  if ! command -v gcloud >/dev/null 2>&1 && [[ -x "$HOME/google-cloud-sdk/bin/gcloud" ]]; then
    PATH="$HOME/google-cloud-sdk/bin:$PATH"
  fi
  local outil
  for outil in "$@"; do
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
# l'instance, qui est aussi l'utilisateur et le nom de la base, devient ‹instance› ; le jeton Vertex
# emprunté, ‹jeton›.
filtrer() {
  if [[ "$1" == *"$NEO4J_PASSWORD"* ]]; then
    erreur "sortie masquée : elle contenait le mot de passe"
    exit 2
  fi
  SORTIE="${1//"$NEO4J_USERNAME"/‹instance›}"
  if [[ -n "$JETON" ]]; then
    SORTIE="${SORTIE//"$JETON"/‹jeton›}"
  fi
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

# Exécute un fichier .cypher avec le jeton du compte aura-genai en $jeton (spec 003, D4 ; ADR-0019), comme
# cypher_fichier. Le jeton, emprunté pour DUREE_JETON secondes, passe par une ligne :param sur le stdin de
# cypher-shell, suivie du fichier : jamais en argument (ps le montrerait), ni dans l'environnement, ni sur le
# disque. cypher-shell évalue :param côté serveur : le jeton arrive chez Aura en littéral, d'où un rôle limité
# à la prédiction et 15 minutes.
cypher_fichier_avec_jeton() {
  local fichier="$1" brut code=0
  # Syntaxe d'un jeton Bearer (RFC 6750) : rien qui puisse sortir de la chaîne Cypher qui le porte.
  local -r syntaxe='^[A-Za-z0-9._~+/-]+=*$'
  shift
  if ! JETON="$(gcloud auth print-access-token --impersonate-service-account="$COMPTE_GENAI" \
    --lifetime="$DUREE_JETON")"; then
    JETON=""
    erreur "jeton du compte $COMPTE_GENAI non obtenu (gcloud auth login ? emprunt autorisé ?)"
    exit 2
  fi
  if [[ ! "$JETON" =~ $syntaxe ]]; then
    JETON=""
    erreur "jeton du compte $COMPTE_GENAI illisible : rien n'est envoyé à Aura"
    exit 2
  fi
  brut="$({ printf ':param {jeton: "%s"}\n' "$JETON"; cat "$fichier"; } |
    cypher-shell --non-interactive --format plain "$@" 2>&1)" || code=$?
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

# Garde-fou d'un flux continu (stderr d'un serveur lancé par exec), ligne à ligne, selon les règles
# de filtrer. Un flux ne peut pas tout arrêter : une ligne qui contiendrait le mot de passe n'est pas
# écrite, un avertissement la remplace.
filtrer_flux() {
  local ligne
  while IFS= read -r ligne || [[ -n "$ligne" ]]; do
    if [[ "$ligne" == *"$NEO4J_PASSWORD"* ]]; then
      erreur "ligne masquée : elle contenait le mot de passe"
    else
      printf '%s\n' "${ligne//"$NEO4J_USERNAME"/‹instance›}"
    fi
  done
}
