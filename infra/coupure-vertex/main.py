"""Coupure de Vertex au plafond de dépense (ADR-0010, NEO-26).

Le budget « Plafond jleroy-labo 100 EUR (oct-dec 2026) » publie son état plusieurs fois par jour
dans le sujet Pub/Sub coupure-vertex, et Eventarc remet chaque message à cette fonction. Quand le
coût cumulé atteint le montant du budget, elle désactive aiplatform.googleapis.com sur le projet :
Gemini s'arrête (Claude passe par l'API Anthropic depuis l'ADR-0011). Vertex reste coupé ; le
réactiver est un geste volontaire, après relecture de la facture (RUNBOOK). La fonction ne réactive
jamais rien et ne touche à aucun autre service.

Les messages arrivent au moins une fois, parfois en double ou dans le désordre : chaque appel relit
l'état de Vertex avant d'agir. Un message d'un autre budget est ignoré. Toute erreur est journalisée
en ERROR (alerte par e-mail), puis relevée : Eventarc renvoie alors le message.

Bibliothèque standard seule, hors Functions Framework : le jeton du compte de service vient du
serveur de métadonnées de Cloud Run.
"""

import base64
import binascii
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

import functions_framework
from cloudevents.http import CloudEvent

SERVICE = "aiplatform.googleapis.com"
METADONNEES = "http://metadata.google.internal/computeMetadata/v1"
SERVICE_USAGE = "https://serviceusage.googleapis.com/v1"
DELAI_S = 30.0
# Issues d'un message, renvoyées par traiter() et journalisées.
AUTRE_BUDGET, SOUS_LE_PLAFOND, DEJA_COUPE, COUPE = (
    "autre-budget",
    "sous-le-plafond",
    "deja-coupe",
    "coupe",
)

journal = logging.getLogger("coupure-vertex")


class ErreurCoupure(Exception):
    """Message illisible, jeton refusé, ou Service Usage en échec : Eventarc renverra le message."""


@dataclass(frozen=True)
class Notification:
    """Ce qu'un message du budget dit de la dépense (format 1.0 des notifications de budget)."""

    budget_id: str
    nom: str
    cout: Decimal
    montant: Decimal
    devise: str


class FormatCloudLogging(logging.Formatter):
    """Une ligne JSON par entrée : Cloud Logging en tire la sévérité et le message."""

    def format(self, record: logging.LogRecord) -> str:
        entree: dict[str, Any] = {"severity": record.levelname, "message": record.getMessage()}
        entree.update(getattr(record, "champs", {}))
        return json.dumps(entree, ensure_ascii=False)


def lire(donnees: Mapping[str, Any]) -> Notification:
    """La notification portée par l'événement Pub/Sub d'Eventarc.

    Raises:
        ErreurCoupure: message illisible ou incomplet.
    """
    try:
        message = donnees["message"]
        attributs = message.get("attributes") or {}
        contenu = json.loads(base64.b64decode(message["data"], validate=True))
        # Montants en nombres dans la doc, parfois en texte dans ses exemples : Decimal les lit
        # tous deux, sans arrondi binaire.
        return Notification(
            budget_id=str(attributs["budgetId"]),
            nom=str(contenu["budgetDisplayName"]),
            cout=Decimal(str(contenu["costAmount"])),
            montant=Decimal(str(contenu["budgetAmount"])),
            devise=str(contenu["currencyCode"]),
        )
    except (KeyError, TypeError, AttributeError, ValueError, binascii.Error, InvalidOperation) as e:
        raise ErreurCoupure(f"notification illisible : {type(e).__name__} {e}") from e


def appeler(
    methode: str, url: str, entetes: Mapping[str, str], corps: Mapping[str, Any] | None = None
) -> tuple[int, dict[str, Any]]:
    """Un appel HTTP qui rend le statut et la réponse JSON, erreurs HTTP comprises.

    Raises:
        ErreurCoupure: point d'accès injoignable, ou réponse qui n'est pas du JSON.
    """
    donnees = json.dumps(corps).encode() if corps is not None else None
    requete = urllib.request.Request(url, data=donnees, method=methode, headers=dict(entetes))
    if donnees is not None:
        requete.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(requete, timeout=DELAI_S) as reponse:
            statut, brut = reponse.status, reponse.read()
    except urllib.error.HTTPError as erreur:
        statut, brut = erreur.code, erreur.read()
    except (urllib.error.URLError, TimeoutError) as erreur:
        raise ErreurCoupure(f"{methode} {url} injoignable : {erreur}") from erreur
    try:
        lu = json.loads(brut) if brut else {}
    except ValueError as erreur:
        raise ErreurCoupure(f"{methode} {url} : réponse {statut} illisible") from erreur
    return statut, lu if isinstance(lu, dict) else {}


def jeton() -> str:
    """Jeton d'accès du compte de service de la fonction, par le serveur de métadonnées."""
    url = f"{METADONNEES}/instance/service-accounts/default/token"
    statut, reponse = appeler("GET", url, {"Metadata-Flavor": "Google"})
    if statut != 200 or not reponse.get("access_token"):
        raise ErreurCoupure(f"jeton refusé par le serveur de métadonnées ({statut})")
    return str(reponse["access_token"])


def _url(projet: str) -> str:
    return f"{SERVICE_USAGE}/projects/{projet}/services/{SERVICE}"


def _detail(reponse: Mapping[str, Any]) -> str:
    erreur = reponse.get("error")
    if isinstance(erreur, dict):
        return f"{erreur.get('status', '')} {erreur.get('message', '')}".strip()
    return ""


def etat(projet: str, cle: str) -> str:
    """État de Vertex sur le projet : ENABLED ou DISABLED."""
    statut, reponse = appeler("GET", _url(projet), {"Authorization": f"Bearer {cle}"})
    if statut != 200 or "state" not in reponse:
        raise ErreurCoupure(f"état de {SERVICE} illisible ({statut}) : {_detail(reponse)}")
    return str(reponse["state"])


def desactiver(projet: str, cle: str) -> None:
    """Désactive Vertex, sans les services qui en dépendraient : s'il y en a, Service Usage refuse,
    et l'erreur part en alerte plutôt que de couper autre chose en silence."""
    corps = {"disableDependentServices": False, "checkIfServiceHasUsage": "SKIP"}
    entetes = {"Authorization": f"Bearer {cle}"}
    statut, reponse = appeler("POST", f"{_url(projet)}:disable", entetes, corps)
    if statut == 200:
        return
    # Un autre message a pu couper Vertex entre la lecture et l'appel : refus attendu.
    if _detail(reponse).startswith("FAILED_PRECONDITION") and etat(projet, cle) == "DISABLED":
        return
    raise ErreurCoupure(f"désactivation de {SERVICE} refusée ({statut}) : {_detail(reponse)}")


def traiter(donnees: Mapping[str, Any], projet: str, budget_id: str) -> str:
    """Lit la notification, coupe Vertex si le budget est atteint ; rend l'issue du message."""
    note = lire(donnees)
    montants = {"cout": str(note.cout), "montant": str(note.montant), "devise": note.devise}
    if note.budget_id != budget_id:
        journal.info(f"budget « {note.nom} » ignoré : ce n'est pas celui de la coupure")
        return AUTRE_BUDGET
    depense = f"{note.cout} {note.devise} dépensés sur {note.montant} {note.devise}"
    if note.cout < note.montant:
        journal.info(f"sous le plafond : {depense}", extra={"champs": montants})
        return SOUS_LE_PLAFOND
    cle = jeton()
    if etat(projet, cle) == "DISABLED":
        journal.info(f"Vertex déjà coupé : {depense}", extra={"champs": montants})
        return DEJA_COUPE
    desactiver(projet, cle)
    # Cette entrée déclenche l'alerte « Vertex coupé » (alerte-coupure.json).
    champs = montants | {"evenement": "vertex-coupe"}
    journal.warning(f"Vertex coupé sur {projet} : {depense}", extra={"champs": champs})
    return COUPE


@functions_framework.cloud_event
def coupure(evenement: CloudEvent) -> None:
    """Point d'entrée de la fonction : un message Pub/Sub du budget, remis par Eventarc."""
    try:
        traiter(evenement.data, os.environ["PROJET"], os.environ["BUDGET_ID"])
    except (ErreurCoupure, KeyError) as erreur:
        journal.error(f"coupure de Vertex en échec : {erreur}")
        raise


if not journal.handlers:
    _sortie = logging.StreamHandler(sys.stdout)
    _sortie.setFormatter(FormatCloudLogging())
    journal.addHandler(_sortie)
    journal.setLevel(logging.INFO)
    journal.propagate = False
