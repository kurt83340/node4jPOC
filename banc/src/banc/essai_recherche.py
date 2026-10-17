"""Essai de la recherche sur la vraie base, sans LLM (spec 003, T8.2 ; plan D5 et D6) :
banc essai-recherche.

Le harnais lance scripts/mcp-neo4j.sh comme une cellule (banc.essai_serveur) et lance
questions/recherche.cypher par read-cypher, comme le fera la cellule GraphRAG :

1. la requête sur un vecteur factice, avant tout encodage : read-cypher la planifie (il préfixe
   lui-même EXPLAIN pour la classer en lecture, neo4j-mcp v1.6.0), puis l'exécute ; une requête
   cassée ne dépense rien ;
2. deux phrases maison, hors du banc, encodées (RETRIEVAL_QUERY) et cherchées : de 1 à 20 espèces,
   1 ou 2 descriptions chacune, les colonnes de la requête, aucun vecteur ; taille du contexte et
   latence de read-cypher relevées ;
3. preuve de symétrie : une description lue par read-cypher, encodée en RETRIEVAL_DOCUMENT et
   comparée sur la base à son vecteur stocké (vector.similarity.cosine, comme au test payant du
   2026-10-12) : 0,9999 au moins, sinon le modèle aurait dérivé.

Trois encodages (moins de 0,001 $), sur le feu vert de Julien ; aucune écriture ; aucun texte de
description dans le compte rendu (ADR-0001). Codes retour : 0 conforme · 1 écart · 2 erreur
technique.
"""

import asyncio
import json
import math
import sys
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters

from banc import orchestration
from banc.cellule import LANCEUR, QUESTIONS
from banc.encodage import DIMENSIONS, DOCUMENT, QUESTION, Encodage, EncodageError, connexion
from banc.encodage import encoder as encoder_vertex
from banc.essai_serveur import (
    ERREURS_TECHNIQUES,
    Bilan,
    EssaiError,
    _feuilles,
    extrait,
    lire,
    serveur,
    valeur,
)
from banc.isolement import environnement_agent

RECHERCHE = QUESTIONS / "recherche.cypher"
# Deux phrases maison, hors du banc : leurs thèmes évitent ceux des questions sémantiques.
PHRASES = (
    "Une créature qui collectionne des objets brillants et les cache dans son nid.",
    "Un être qui change de couleur au fil des saisons.",
)
# Les colonnes de questions/recherche.cypher, une espèce par enregistrement (D9).
COLONNES = (
    "espece", "categorie", "types", "talents", "statistiques", "evolueDe", "evolueEn",
    "descriptions",
)  # fmt: skip
ESPECES_MAX = 20
DESCRIPTIONS_MAX = 2
SEUIL_SYMETRIE = 0.9999
# Vecteur du premier contrôle : de la dimension de l'index, et non nul pour une similarité cosinus.
FACTICE = [0.001] * DIMENSIONS
# Jetons estimés par excès, comme le garde-fou des cellules sur un résultat d'outil.
CARACTERES_PAR_JETON = 3
# La description de contrôle : la première de la première espèce, toujours la même.
DESCRIPTION = (
    "CYPHER 25 MATCH (p:Pokemon)-[:A_POUR_DESCRIPTION]->(d:Description) "
    "WITH p, d ORDER BY p.id, d.texte LIMIT 1 RETURN elementId(d) AS id, d.texte AS texte"
)
SYMETRIE = (
    "CYPHER 25 MATCH (d:Description) WHERE elementId(d) = $id "
    "RETURN vector.similarity.cosine(d.embedding, $vecteur) AS similarite"
)
TECHNIQUES = (*ERREURS_TECHNIQUES, EncodageError)


@dataclass(frozen=True)
class Moyens:
    """Ce que l'essai lance : le vrai lanceur et Vertex, ou des faux (tests)."""

    serveur: tuple[str, ...] = (str(LANCEUR),)
    # Dossiers de gcloud et de neo4j-mcp, placés dans le PATH des agents.
    chemins: Callable[[], tuple[Path, ...]] = orchestration.outils_des_agents
    connexion_s: float = 30.0
    # Encode un texte pour une tâche : None, banc.encodage par une connexion à Vertex.
    encoder: Callable[[str, str], Encodage] | None = None
    ecrire: Callable[[str], None] = print


def commande(moyens: Moyens | None = None) -> int:
    """banc essai-recherche : 0 conforme, 1 écart, 2 erreur technique."""
    try:
        return asyncio.run(essai(moyens or Moyens()))
    except TECHNIQUES as erreur:
        print(f"banc essai-recherche : {erreur}", file=sys.stderr)
        return 2
    except BaseExceptionGroup as groupe:
        # Le client MCP (anyio) regroupe les erreurs de ses tâches (banc.essai_serveur).
        if groupe.split(TECHNIQUES)[1] is not None:
            raise
        for feuille in _feuilles(groupe):
            print(f"banc essai-recherche : {feuille}", file=sys.stderr)
        return 2


async def essai(moyens: Moyens) -> int:
    """Mène l'essai dans un dossier temporaire hors du dépôt, détruit ensuite."""
    bilan = Bilan(moyens.ecrire)
    requete = RECHERCHE.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="banc-essai-") as dossier:
        racine = Path(dossier)
        for sous_dossier in ("home", "claude", "travail"):
            (racine / sous_dossier).mkdir()
        env = environnement_agent(
            "adk-gemini", racine / "home", racine / "claude", moyens.chemins()
        )
        parametres = StdioServerParameters(
            command=moyens.serveur[0],
            args=list(moyens.serveur[1:]),
            env=env,
            cwd=racine / "travail",
        )
        with (racine / "serveur.log").open("w", encoding="utf-8") as journal:
            async with serveur(parametres, journal, moyens.connexion_s) as (session, _initiale):
                await _essai(bilan, moyens, session, requete)
    if bilan.ecarts:
        moyens.ecrire(f"ÉCART : {bilan.ecarts} contrôle(s) sur {bilan.controles}.")
        return 1
    moyens.ecrire(f"CONFORME : {bilan.controles} contrôles.")
    return 0


async def _essai(bilan: Bilan, moyens: Moyens, session: ClientSession, requete: str) -> None:
    texte, erreur = await lire(session, requete, {"vecteur": FACTICE})
    ecarts = [extrait(texte)] if erreur else ecarts_du_contexte(texte)
    obtenu = "; ".join(ecarts) or f"{len(json.loads(texte))} espèce(s)"
    if not bilan.juger("requête lue par read-cypher, vecteur factice", not ecarts, obtenu):
        return
    encoder = moyens.encoder or _encodeur()
    for rang, phrase in enumerate(PHRASES, start=1):
        encodage = await asyncio.to_thread(encoder, phrase, QUESTION)
        debut = time.monotonic()
        texte, erreur = await lire(session, requete, {"vecteur": list(encodage.vecteur)})
        latence = time.monotonic() - debut
        ecarts = [extrait(texte)] if erreur else ecarts_du_contexte(texte)
        obtenu = "; ".join(ecarts) or f"{len(json.loads(texte))} espèce(s)"
        bilan.juger(f"phrase {rang} : contexte de la recherche", not ecarts, obtenu)
        jetons = math.ceil(len(texte) / CARACTERES_PAR_JETON)
        bilan.informer(
            f"phrase {rang}",
            f"{len(texte)} caractères, ≈ {jetons} jetons (÷ {CARACTERES_PAR_JETON}, par excès), "
            f"read-cypher {latence:.2f} s ; encodage {encodage.jetons} jetons en "
            f"{encodage.latence_s:.2f} s",
        )
    await _symetrie(bilan, session, encoder)


async def _symetrie(
    bilan: Bilan, session: ClientSession, encoder: Callable[[str, str], Encodage]
) -> None:
    texte, erreur = await lire(session, DESCRIPTION)
    identifiant, description = valeur(texte, "id"), valeur(texte, "texte")
    if erreur or not isinstance(identifiant, str) or not isinstance(description, str):
        raise EssaiError(f"description de contrôle illisible : {extrait(texte)}")
    encodage = await asyncio.to_thread(encoder, description, DOCUMENT)
    bilan.informer(
        "description de contrôle",
        f"{len(description)} caractères, encodée en {encodage.jetons} jetons",
    )
    parametres = {"id": identifiant, "vecteur": list(encodage.vecteur)}
    texte, erreur = await lire(session, SYMETRIE, parametres)
    similarite = None if erreur else valeur(texte, "similarite")
    libelle = (
        f"symétrie : description réencodée contre son vecteur stocké ({SEUIL_SYMETRIE} au moins)"
    )
    if isinstance(similarite, (int, float)) and not isinstance(similarite, bool):
        bilan.juger(libelle, similarite >= SEUIL_SYMETRIE, str(similarite))
    else:
        bilan.juger(libelle, False, extrait(texte))


def ecarts_du_contexte(texte: str) -> list[str]:
    """Ce qui s'écarte de D6 dans un résultat de recherche.cypher : le nombre d'espèces, leurs
    colonnes, le nombre de leurs descriptions, un vecteur."""
    try:
        enregistrements = json.loads(texte)
    except json.JSONDecodeError:
        return [f"réponse illisible : {extrait(texte)}"]
    if not isinstance(enregistrements, list) or not all(
        isinstance(enregistrement, dict) for enregistrement in enregistrements
    ):
        return [f"pas une liste d'enregistrements : {extrait(texte)}"]
    ecarts = []
    if not 1 <= len(enregistrements) <= ESPECES_MAX:
        ecarts.append(f"{len(enregistrements)} espèce(s), de 1 à {ESPECES_MAX} attendues")
    for enregistrement in enregistrements:
        # Des colonnes, sans ordre : neo4j-mcp (Go) écrit chaque enregistrement comme une map.
        if set(enregistrement) != set(COLONNES):
            ecarts.append(f"colonnes {sorted(enregistrement)}, {sorted(COLONNES)} attendues")
            break
        descriptions = enregistrement["descriptions"]
        nombre = len(descriptions) if isinstance(descriptions, list) else 0
        if not 1 <= nombre <= DESCRIPTIONS_MAX:
            ecarts.append(f"{nombre} description(s) pour une espèce, 1 ou {DESCRIPTIONS_MAX}")
            break
    if "embedding" in cles(enregistrements):
        ecarts.append("propriété embedding dans le contexte")
    return ecarts


def cles(objet: Any) -> set[str]:
    """Toutes les clés des maps d'un objet JSON, à toute profondeur."""
    if isinstance(objet, dict):
        return set(objet).union(*(cles(element) for element in objet.values()))
    if isinstance(objet, list):
        return set().union(*(cles(element) for element in objet))
    return set()


def _encodeur() -> Callable[[str, str], Encodage]:
    """L'encodage de banc.encodage, par une seule connexion à Vertex pour tout l'essai."""
    client = connexion()
    return lambda texte, tache: encoder_vertex(texte, tache, client)
