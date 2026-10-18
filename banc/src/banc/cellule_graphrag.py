"""Cellules GraphRAG (spec 003 ; plan D7, D9 ; ADR-0017, ADR-0018) : graphrag-claude et
graphrag-gemini, la technique 3 du banc. Des cellules ADK sans outil (D7) : elles reprennent de
banc.cellule_adk la connexion au serveur MCP, les comptes, le garde-fou et les issues d'un tour.

Pour chaque question, dans le temps mesuré : la recherche, puis un seul appel au modèle, qui reçoit
son résultat, le contexte. La recherche lance questions/recherche.cypher telle quelle, commentaires
compris, par read-cypher, le vecteur du message en paramètre : la voie que banc essai-recherche a
prouvée sur la vraie base (T8.2). L'orchestration encode les messages à la création de la campagne
(banc.encodage, D5) et passe leurs vecteurs dans la commande (banc.cellule).

Le serveur MCP se connecte avant le chrono, avec l'environnement de la cellule, comme pour les
cellules ADK ; la cellule appelle read-cypher elle-même, sur la session ouverte alors, et ne relance
jamais le serveur : une recherche sans réponse (serveur perdu, read-cypher en erreur) est une
panne. La trace note la recherche comme un appel read-cypher (D9) : la requête, l'empreinte du
vecteur à sa place dans les paramètres (banc.mesures.empreinte_vecteur), le résultat tel que le
modèle le reçoit. Garde-fou de l'ADR-0017 : un contexte dont le coût estimé ferait dépasser le
budget de la conversation arrête le tour avant l'appel au modèle (échec « budget »).

L'appel au modèle passe par un rédacteur, que la conversation reçoit (T10.1 : ADK sans outil, la
consigne de contexte et la fiche).
"""

import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from typing import Final

from mcp import ClientSession
from mcp.shared.exceptions import MCPError

from banc import cellule_adk
from banc.cellule import RECHERCHE, CelluleError, Commande
from banc.cellule_adk import (
    _arreter_les_restes,
    _Comptes,
    _connecter,
    _issue,
    _Tour,
    boite_a_outils,
    verifier_acces,
)
from banc.encodage import DIMENSIONS
from banc.essai_serveur import EssaiError, lire
from banc.mesures import Entete, Journal, empreinte_vecteur, fichier_trace
from banc.notation import LECTURE
from banc.prix import Tarif

CLIENTS = ("graphrag-claude", "graphrag-gemini")
# Même client et même modèle que les cellules ADK du jalon 2 (D7) : l'écart tient à la technique.
JUMELLES: Final = {"graphrag-claude": "adk-claude", "graphrag-gemini": "adk-gemini"}

# L'appel au modèle d'un tour, le contexte en main : il note sur le tour sa réponse, ou ce qui l'a
# coupé ; la cellule tient l'échéance du tour.
type Redaction = Callable[[_Tour, str, str], Awaitable[None]]
# La rédaction d'une conversation, faite avec ses comptes (usage, coût, budget).
type Redacteur = Callable[[_Comptes], Redaction]


async def converser(
    client: str, commande: Commande, tarifs: Sequence[Tarif], redacteur: Redacteur
) -> None:
    """Mène la conversation de la commande et en écrit la trace : pour chaque question, la
    recherche, le garde-fou, puis la rédaction.

    Le serveur se connecte avant le chrono ; une panne avant la première question la note en
    panne. Une question qui n'a pas de réponse arrête la conversation, comme dans les cellules ADK
    (ADR-0012).

    Raises:
        CelluleError: client inconnu, ou commande sans un vecteur par question de la dimension de
            l'index.
        CleAbsente: cellule Claude sans clé Anthropic.
        IsolementError: cellule Gemini qui reçoit la clé Anthropic, ou serveur sans read-cypher.
    """
    if client not in JUMELLES:
        raise CelluleError(f"client inconnu : {client} (attendu : {', '.join(CLIENTS)})")
    verifier_acces(JUMELLES[client])
    vecteurs = _vecteurs(commande)
    requete = RECHERCHE.read_text(encoding="utf-8")
    avant = asyncio.all_tasks()
    boite = boite_a_outils(commande)
    try:
        initiale = await _connecter(boite, commande.plafonds.connexion_s)
        info = None if initiale is None else initiale.server_info
        en_tete = entete(client, commande, "absent" if info is None else info.version)
        with Journal(fichier_trace(commande.traces, en_tete), en_tete) as journal:
            if initiale is None:
                ident, message = commande.questions[0]
                journal.question(ident, message)
                journal.fin("panne", "serveur")
                return
            comptes = _Comptes(journal, en_tete, commande, tarifs)
            conversation = _Conversation(
                journal, en_tete, commande, comptes, initiale, requete, redacteur(comptes)
            )
            for (ident, message), vecteur in zip(commande.questions, vecteurs, strict=True):
                if await conversation.tour(ident, message, vecteur) != "reponse":
                    break
    finally:
        await boite.close()
        await _arreter_les_restes(avant)


def entete(client: str, commande: Commande, version_serveur: str) -> Entete:
    """En-tête de la trace : celui de la cellule ADK jumelle (même modèle, même voie, mêmes
    versions, D7), sous le nom de la cellule GraphRAG."""
    jumelle = cellule_adk.entete(JUMELLES[client], commande, version_serveur)
    return replace(jumelle, cellule=client)


def _vecteurs(commande: Commande) -> tuple[tuple[float, ...], ...]:
    """Les vecteurs des messages : un par question, de la dimension de l'index (D5).

    Raises:
        CelluleError: aucun vecteur, pas un par question, ou d'une autre dimension.
    """
    vecteurs, questions = commande.vecteurs, commande.questions
    if not vecteurs:
        raise CelluleError("commande sans vecteurs : la recherche en exige un par question (D5)")
    if len(vecteurs) != len(questions):
        raise CelluleError(
            f"vecteurs : un par question attendu, {len(vecteurs)} pour {len(questions)}"
        )
    if autres := sorted({len(vecteur) for vecteur in vecteurs} - {DIMENSIONS}):
        raise CelluleError(
            f"vecteurs de {', '.join(map(str, autres))} dimensions, {DIMENSIONS} attendues "
            "(index descriptions_texte)"
        )
    return vecteurs


@dataclass
class _Conversation:
    """Les questions d'une conversation, l'une après l'autre : recherche, garde-fou, rédaction,
    issue."""

    journal: Journal
    entete: Entete
    commande: Commande
    comptes: _Comptes
    # Session MCP d'avant le chrono, jamais relancée : perdue, la recherche est en panne.
    session: ClientSession
    requete: str
    rediger: Redaction

    async def tour(self, ident: str, message: str, vecteur: Sequence[float]) -> str:
        """Pose une question et en note le tour ; renvoie son issue."""
        self.journal.question(ident, message)
        tour = _Tour()
        echeance = asyncio.get_running_loop().time() + self.commande.plafonds.delai_s
        delai = asyncio.timeout_at(echeance)
        try:
            async with delai:
                if (contexte := await self._rechercher(tour, ident, vecteur)) is not None:
                    await self.rediger(tour, message, contexte)
        except TimeoutError as erreur:
            if delai.expired():
                tour.coupure = "delai"
            else:
                tour.erreur = erreur
        issue, cause = _issue(tour)
        self.journal.fin(issue, cause, tour.reponse if issue == "reponse" else "")
        return issue

    async def _rechercher(self, tour: _Tour, ident: str, vecteur: Sequence[float]) -> str | None:
        """La recherche du tour, notée comme un appel read-cypher, l'empreinte du vecteur à sa place
        (D9) ; rend le contexte, ou None quand le tour s'arrête là : panne (serveur perdu,
        read-cypher en erreur) ou contexte trop gros pour le budget."""
        appel = f"recherche-{ident}"
        self.journal.appel(appel, LECTURE, self.requete, {"vecteur": empreinte_vecteur(vecteur)})
        try:
            contexte, erreur = await lire(self.session, self.requete, {"vecteur": list(vecteur)})
        except (MCPError, EssaiError) as panne:
            cellule = self.entete.cellule
            print(f"cellule {cellule} : recherche sans réponse ({panne})", file=sys.stderr)
            tour.serveur_perdu = True
            return None
        self.journal.resultat(appel, contexte, erreur)
        if erreur:
            # Plan, « Erreurs » : read-cypher en erreur, une panne, comme un serveur perdu.
            tour.serveur_perdu = True
            return None
        # Garde-fou de l'ADR-0017 : ce que le contexte ajoute à l'entrée de l'appel au modèle ne
        # doit pas faire dépasser le budget de la conversation.
        estimation = self.comptes.estimation(len(contexte))
        if self.comptes.cout + estimation > self.commande.plafonds.budget_usd:
            tour.coupure = "budget"
            return None
        return contexte
