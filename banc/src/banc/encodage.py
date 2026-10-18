"""Encodage des messages d'une campagne GraphRAG (spec 003, plan D5 ; ADR-0018) : google-genai,
gemini-embedding-001 sur Vertex europe-west1, 3 072 dimensions, un texte par requête.

Le harnais encode chaque message posé à la création d'une campagne (T12.1) : la cellule Claude ne
reçoit aucune variable Vertex (règle d'isolement, plan 002 D3), et le temps mesuré exclut
l'encodage, rapporté à côté par sa latence (ADR-0018). Les identifiants sont l'ADC du poste, comme
pour la cellule Gemini, avec jleroy-labo pour projet de quota (celui de l'ADC du poste est
jleroy-outils) ; des identifiants explicites passent avant une clé d'API de l'environnement.

encodages.json, près des traces de la campagne, garde chaque encodage (plan, « Flux de données ») :
par question, l'empreinte du message posé, le vecteur, les jetons et la latence ; écrit à la
création, jamais réécrit, il se relit à la reprise sans réencoder.

Relevé sur le vrai google-genai 2.28.0 contre une fausse API (T8.1) : gemini-embedding-001 passe par
:predict (instances[].content, instances[].task_type, parameters.outputDimensionality) ; le projet
de quota part dans l'en-tête x-goog-user-project ; un 429 est repris ; token_count arrive en float.
"""

import hashlib
import json
import math
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import google.auth
import google.auth.credentials
import google.auth.exceptions
from google import genai
from google.genai import errors as erreurs_genai
from google.genai import types

from banc.isolement import PROJET, REPRISES

MODELE = "gemini-embedding-001"
# La région de l'instance Aura et de l'encodage des descriptions au chargement (plan D3) : le point
# multirégion eu ne sert pas ce modèle (404 au test payant du 2026-10-12).
REGION = "europe-west1"
# Voie de prix de l'encodage (banc/prix.toml).
ACCES = "vertex-europe-west1"
DIMENSIONS = 3072
# Le type de tâche d'une question ; celui d'une description, pour la preuve de symétrie (T8.2).
QUESTION = "RETRIEVAL_QUERY"
DOCUMENT = "RETRIEVAL_DOCUMENT"
# Portée de l'ADC de Vertex, celle que google-genai demande lui-même.
PORTEE = "https://www.googleapis.com/auth/cloud-platform"
# Autant de reprises que les cellules (plan 002, D13) ; délais de google-genai.
REPRISES_VERTEX = types.HttpRetryOptions(attempts=REPRISES + 1)


class EncodageError(Exception):
    """Encodage impossible ou inutilisable (ADC, Vertex, vecteur) : la campagne ne démarre pas."""


@dataclass(frozen=True)
class Encodage:
    """Le vecteur d'un texte, les jetons que Vertex a comptés (le coût, D11) et la latence de
    l'appel, à l'horloge monotone."""

    vecteur: tuple[float, ...]
    jetons: int
    latence_s: float


def connexion() -> genai.Client:
    """Le client de Vertex : l'ADC du poste, jleroy-labo pour projet et pour projet de quota, la
    région de l'encodage ; une connexion sert toute une campagne.

    Raises:
        EncodageError: ADC introuvable, ou qui ne peut pas porter de projet de quota : les appels
            seraient comptés à un autre projet sans rien dire.
    """
    try:
        identifiants, _projet = google.auth.default(scopes=[PORTEE])
    except google.auth.exceptions.GoogleAuthError as erreur:
        raise EncodageError(f"ADC introuvable : {erreur}") from erreur
    if not isinstance(identifiants, google.auth.credentials.CredentialsWithQuotaProject):
        genre = type(identifiants).__name__
        raise EncodageError(f"ADC sans projet de quota possible ({genre}) : {PROJET} non imposé")
    return genai.Client(
        enterprise=True,
        project=PROJET,
        location=REGION,
        credentials=identifiants.with_quota_project(PROJET),  # type: ignore[no-untyped-call]
        http_options=types.HttpOptions(retry_options=REPRISES_VERTEX),
    )


def encoder(texte: str, tache: str = QUESTION, client: genai.Client | None = None) -> Encodage:
    """Encode un texte : un appel à Vertex, un vecteur de 3 072 dimensions, ses jetons, sa latence.

    Raises:
        EncodageError: ADC refusée, erreur de Vertex, vecteur d'une autre dimension, texte tronqué,
            jetons absents.
    """
    client = client or connexion()
    config = types.EmbedContentConfig(task_type=tache, output_dimensionality=DIMENSIONS)
    debut = time.monotonic()
    try:
        reponse = client.models.embed_content(model=MODELE, contents=texte, config=config)
    except google.auth.exceptions.GoogleAuthError as erreur:
        raise EncodageError(f"ADC refusée : {erreur}") from erreur
    except erreurs_genai.APIError as erreur:
        raise EncodageError(
            f"Vertex refuse l'encodage ({erreur.code}) : {erreur.message}"
        ) from erreur
    latence = time.monotonic() - debut
    plongements = reponse.embeddings or []
    if len(plongements) != 1 or plongements[0].values is None:
        raise EncodageError(f"un vecteur attendu, {len(plongements)} rendu(s)")
    vecteur = tuple(float(valeur) for valeur in plongements[0].values)
    if len(vecteur) != DIMENSIONS:
        raise EncodageError(f"vecteur de {len(vecteur)} dimensions, {DIMENSIONS} attendues")
    statistiques = plongements[0].statistics
    if statistiques is not None and statistiques.truncated:
        raise EncodageError("texte tronqué par Vertex (au-delà de 2 048 jetons)")
    if statistiques is None or statistiques.token_count is None:
        raise EncodageError("jetons absents de la réponse : coût non mesurable")
    return Encodage(vecteur, int(statistiques.token_count), latence)


def encodeur_vertex() -> Callable[[str, str], Encodage]:
    """Encode un texte pour une tâche, par une seule connexion à Vertex (D5 : une par campagne,
    ou par essai de la recherche).

    Raises:
        EncodageError: ADC introuvable ou sans projet de quota possible.
    """
    client = connexion()
    return lambda texte, tache: encoder(texte, tache, client)


def encoder_les_messages(
    messages: Mapping[str, str], encodeur: Callable[[str, str], Encodage]
) -> dict[str, Encodage]:
    """Les messages posés d'une campagne (par question, préambule de Q2 compris), encodés un par
    un, en RETRIEVAL_QUERY.

    Raises:
        EncodageError: un encodage en échec : la campagne ne démarre pas.
    """
    return {ident: encodeur(message, QUESTION) for ident, message in messages.items()}


def ecrire_les_encodages(
    fichier: Path, messages: Mapping[str, str], encodages: Mapping[str, Encodage]
) -> None:
    """Écrit encodages.json à la création de la campagne ; jamais réécrit (FileExistsError)."""
    contenu = {
        "modele": MODELE,
        "acces": ACCES,
        "tache": QUESTION,
        "dimensions": DIMENSIONS,
        "messages": {
            ident: {
                "empreinte": _empreinte(messages[ident]),
                "jetons": encodage.jetons,
                "latence_s": encodage.latence_s,
                "vecteur": list(encodage.vecteur),
            }
            for ident, encodage in encodages.items()
        },
    }
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with fichier.open("x", encoding="utf-8") as flux:
        flux.write(json.dumps(contenu, ensure_ascii=False) + "\n")


def relire_les_encodages(fichier: Path, messages: Mapping[str, str]) -> dict[str, Encodage]:
    """Relit encodages.json à la reprise, sans réencoder : chaque question de la campagne, avec
    l'empreinte de son message actuel et un vecteur de la dimension de l'index.

    Raises:
        EncodageError: fichier illisible ; modèle, tâche ou dimension d'un autre encodage ;
            questions différentes ; message changé depuis la création ; vecteur d'une autre
            dimension.
    """
    try:
        contenu = json.loads(fichier.read_text(encoding="utf-8"))
        reglages = (contenu["modele"], contenu["tache"], contenu["dimensions"])
        lus: dict[str, Any] = contenu["messages"]
        if not isinstance(lus, dict):
            raise TypeError("messages : un objet attendu")
    except (OSError, ValueError, KeyError, TypeError) as erreur:
        raise EncodageError(f"{fichier} illisible : {erreur}") from erreur
    if reglages != (MODELE, QUESTION, DIMENSIONS):
        raise EncodageError(
            f"{fichier} : modèle, tâche ou dimension d'un autre encodage ({reglages})"
        )
    if set(lus) != set(messages):
        raise EncodageError(
            f"{fichier} : questions encodées {sorted(lus)}, attendues {sorted(messages)}"
        )
    encodages = {}
    for ident, message in messages.items():
        lu = lus[ident]
        if not isinstance(lu, dict) or lu.get("empreinte") != _empreinte(message):
            raise EncodageError(f"{ident} : message changé depuis la création de la campagne")
        encodages[ident] = _encodage(fichier, ident, lu)
    return encodages


def _empreinte(message: str) -> str:
    return hashlib.sha256(message.encode("utf-8")).hexdigest()


def _encodage(fichier: Path, ident: str, lu: Mapping[str, Any]) -> Encodage:
    """Un encodage relu : un vecteur de nombres finis, de la dimension de l'index ; des jetons
    entiers ; une latence en secondes.

    Raises:
        EncodageError: valeur illisible, ou vecteur d'une autre dimension.
    """
    vecteur, jetons, latence = lu.get("vecteur"), lu.get("jetons"), lu.get("latence_s")
    if (
        not isinstance(vecteur, list)
        or not all(isinstance(x, int | float) and not isinstance(x, bool) for x in vecteur)
        or not all(math.isfinite(x) for x in vecteur)
        or not isinstance(jetons, int)
        or isinstance(jetons, bool)
        or not isinstance(latence, int | float)
    ):
        raise EncodageError(f"{fichier} illisible : encodage de {ident}")
    if len(vecteur) != DIMENSIONS:
        raise EncodageError(
            f"{ident} : vecteur de {len(vecteur)} dimensions, {DIMENSIONS} attendues"
        )
    return Encodage(tuple(float(x) for x in vecteur), jetons, float(latence))
