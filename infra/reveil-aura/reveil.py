"""Réveil quotidien de l'instance AuraDB Free (NEO-13).

Sans activité pendant 72 h, Aura met l'instance Free en pause. Lancé chaque jour par un job Cloud
Run, ce script envoie `RETURN 1` à la Query API d'Aura, en lecture seule. S'il échoue, il le dit
dans une entrée de sévérité ERROR, et une alerte Cloud Monitoring envoie un e-mail.

Les identifiants arrivent dans un fichier que Cloud Run monte depuis Secret Manager (ADR-0007), au
chemin FICHIER_IDENTIFIANTS. Rien n'est journalisé sans passer par `masquer` : un message qui
contiendrait le mot de passe est remplacé, et l'identifiant de l'instance devient ‹instance›.

Bibliothèque standard seule : l'image n'installe rien. Codes retour, comme les scripts du dépôt :
0 = succès · 1 = écart constaté · 2 = erreur technique.
"""

import base64
import http.client
import json
import logging
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REQUETE = "RETURN 1 AS reveil"
FICHIER_PAR_DEFAUT = "/secrets/neo4j-aura-poc"
DELAI_S = 30.0
# Clés du fichier d'identifiants d'Aura → champs d'Identifiants ; les autres lignes sont ignorées.
CLES = {
    "NEO4J_URI": "uri",
    "NEO4J_USERNAME": "utilisateur",
    "NEO4J_PASSWORD": "mot_de_passe",
    "NEO4J_DATABASE": "base",
}

journal = logging.getLogger("reveil-aura")


class ErreurReveil(Exception):
    """Aura n'a pas pu être interrogée : configuration, réseau, refus ou erreur Cypher."""

    code = 2


class EcartReveil(ErreurReveil):
    """Aura a répondu, mais pas la valeur attendue."""

    code = 1


@dataclass(frozen=True)
class Identifiants:
    """Les 4 clés utiles du fichier d'identifiants d'Aura ; le mot de passe reste hors du repr."""

    uri: str
    utilisateur: str
    mot_de_passe: str = field(repr=False)
    base: str


class FormatCloudLogging(logging.Formatter):
    """Une ligne JSON par entrée : Cloud Logging en tire la sévérité et le message."""

    def format(self, record: logging.LogRecord) -> str:
        entree: dict[str, Any] = {"severity": record.levelname, "message": record.getMessage()}
        entree.update(getattr(record, "champs", {}))
        return json.dumps(entree, ensure_ascii=False)


def lire_fichier(chemin: Path) -> str:
    """Contenu du fichier d'identifiants monté par Cloud Run."""
    try:
        return chemin.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as erreur:
        cause = getattr(erreur, "strerror", None) or type(erreur).__name__
        raise ErreurReveil(f"identifiants illisibles : {chemin} ({cause})") from None


def lire_identifiants(texte: str) -> Identifiants:
    """Extrait les 4 clés NEO4J_* du fichier d'identifiants d'Aura (lignes CLE=valeur)."""
    valeurs: dict[str, str] = {}
    for ligne in texte.splitlines():
        cle, egal, valeur = ligne.partition("=")
        if egal and cle in CLES:
            valeurs[CLES[cle]] = valeur
    if manquantes := [cle for cle, champ in CLES.items() if not valeurs.get(champ)]:
        raise ErreurReveil(f"clé(s) absente(s) des identifiants : {', '.join(manquantes)}")
    return Identifiants(**valeurs)


def url_query_api(identifiants: Identifiants) -> str:
    """Adresse de la Query API v2 : l'hôte de l'URI Bolt d'Aura, en HTTPS."""
    uri = urllib.parse.urlsplit(identifiants.uri)
    if uri.scheme not in {"neo4j+s", "bolt+s"} or not uri.hostname:
        raise ErreurReveil("NEO4J_URI inattendue : une adresse neo4j+s:// d'Aura est attendue")
    return f"https://{uri.hostname}/db/{urllib.parse.quote(identifiants.base, safe='')}/query/v2"


def resumer_erreurs(corps: Any) -> str:
    """Les erreurs Neo4j d'une réponse (« code : message », séparées par « ; »), vide sinon."""
    erreurs = corps.get("errors") if isinstance(corps, dict) else None
    if not isinstance(erreurs, list):
        return ""
    resume = " ; ".join(
        f"{e.get('code', '?')} : {e.get('message', '')}" for e in erreurs if isinstance(e, dict)
    )
    return resume[:500]


def envoyer(url: str, identifiants: Identifiants, delai_s: float) -> bytes:
    """Envoie REQUETE en lecture seule et renvoie le corps brut de la réponse."""
    jeton = base64.b64encode(f"{identifiants.utilisateur}:{identifiants.mot_de_passe}".encode())
    requete = urllib.request.Request(
        url,
        data=json.dumps({"statement": REQUETE, "accessMode": "Read"}).encode(),
        headers={
            "Authorization": f"Basic {jeton.decode()}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=delai_s) as reponse:
            corps: bytes = reponse.read()
    except urllib.error.HTTPError as erreur:
        # La Query API répond 202 même quand la requête échoue ; un code d'erreur HTTP vient
        # d'un refus d'authentification (401) ou d'en amont de la base.
        try:
            detail = resumer_erreurs(json.loads(erreur.read()))
        except OSError, http.client.HTTPException, ValueError:
            detail = ""
        message = f"Aura refuse la requête : HTTP {erreur.code} {detail}"
        raise ErreurReveil(message.rstrip()) from None
    except (OSError, http.client.HTTPException) as erreur:
        raise ErreurReveil(
            f"Aura injoignable ({erreur}) : "
            "instance en pause (console Aura → Resume) ou réseau coupé"
        ) from None
    return corps


def analyser(brut: bytes) -> None:
    """Vérifie la réponse : aucune erreur Neo4j, et la seule valeur 1."""
    try:
        corps = json.loads(brut)
    except ValueError:
        raise ErreurReveil("réponse d'Aura illisible : JSON attendu") from None
    if erreurs := resumer_erreurs(corps):
        raise ErreurReveil(f"Aura signale une erreur : {erreurs}")
    donnees = corps.get("data") if isinstance(corps, dict) else None
    valeurs = donnees.get("values") if isinstance(donnees, dict) else None
    if valeurs != [[1]]:
        raise EcartReveil(f"réponse inattendue à {REQUETE} : {str(valeurs)[:200]}, attendu [[1]]")


def masquer(message: str, identifiants: Identifiants | None) -> str:
    """Rend un message sûr à journaliser : jamais le mot de passe, l'instance devient ‹instance›."""
    if identifiants is None:
        return message
    if identifiants.mot_de_passe in message:
        return "message masqué : il contenait le mot de passe"
    if identifiants.utilisateur:
        message = message.replace(identifiants.utilisateur, "‹instance›")
    return message


def main() -> int:
    """Réveille Aura et journalise le résultat ; renvoie le code retour."""
    chemin = Path(os.environ.get("FICHIER_IDENTIFIANTS", FICHIER_PAR_DEFAUT))
    identifiants: Identifiants | None = None
    debut = time.monotonic()
    try:
        identifiants = lire_identifiants(lire_fichier(chemin))
        analyser(envoyer(url_query_api(identifiants), identifiants, DELAI_S))
    except ErreurReveil as erreur:
        champs = {"code_retour": erreur.code}
        journal.error(masquer(str(erreur), identifiants), extra={"champs": champs})
        return erreur.code
    duree_s = round(time.monotonic() - debut, 2)
    duree = f"{duree_s:.1f}".replace(".", ",")
    journal.info(f"Aura répond à {REQUETE} en {duree} s", extra={"champs": {"duree_s": duree_s}})
    return 0


if __name__ == "__main__":
    sortie = logging.StreamHandler(sys.stdout)
    sortie.setFormatter(FormatCloudLogging())
    journal.addHandler(sortie)
    journal.setLevel(logging.INFO)
    sys.exit(main())
