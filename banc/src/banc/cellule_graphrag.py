"""Cellules GraphRAG (spec 003 ; plan D7, D8, D9 ; ADR-0017, ADR-0018) : graphrag-claude et
graphrag-gemini, la technique 3 du banc. Des cellules ADK sans outil (D7) : elles reprennent de
banc.cellule_adk la connexion au serveur MCP, le modèle et ses réglages, les comptes, la lecture du
flux du modèle et les issues d'un tour.

`python -m banc.cellule_graphrag graphrag-claude|graphrag-gemini` lit sa commande (banc.cellule)
sur stdin et mène la conversation dans une session d'ADK. Pour chaque question, dans le temps
mesuré : la recherche, puis un seul appel au modèle, qui reçoit son résultat, le contexte. La
recherche lance questions/recherche.cypher telle quelle, commentaires compris, par read-cypher, le
vecteur du message en paramètre : la voie que banc essai-recherche a prouvée sur la vraie base
(T8.2). L'orchestration encode les messages à la création de la campagne (banc.encodage, D5) et
passe leurs vecteurs dans la commande.

Le serveur MCP se connecte avant le chrono, avec l'environnement de la cellule, comme pour les
cellules ADK ; la cellule appelle read-cypher elle-même, sur la session ouverte alors, et ne relance
jamais le serveur : une recherche sans réponse (serveur perdu, read-cypher en erreur) est une
panne. La trace note la recherche comme un appel read-cypher (D9) : la requête, l'empreinte du
vecteur à sa place dans les paramètres (banc.mesures.empreinte_vecteur), le résultat tel que le
modèle le reçoit. Garde-fou de l'ADR-0017 : un contexte dont le coût estimé ferait dépasser le
budget de la conversation arrête le tour avant l'appel au modèle (échec « budget »).

L'appel au modèle (T10.1) : la consigne de contexte et la fiche (ADR-0018) ; le message, le contexte
puis la question, entre balises (D8) ; le modèle, ses réglages et son cache, ceux de la cellule ADK
jumelle ; son flux lu comme dans banc.cellule_adk (usage, reprises, coupures, erreurs), sous
l'échéance du tour, qui court depuis l'envoi du message, recherche comprise. Un seul appel par
question : le plafond d'appels du modèle n'y joue pas.
"""

import asyncio
import signal
import sys
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from typing import Final

import google.auth.exceptions
from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset
from mcp import ClientSession
from mcp.shared.exceptions import MCPError

from banc import cellule_adk, prix
from banc.cellule import (
    CelluleError,
    Commande,
    consigne_et_fiche,
    lire_commande,
    requete_de_recherche,
)
from banc.cellule_adk import (
    AGENT,
    APPLI,
    INTERROMPUE,
    UTILISATEUR,
    _arreter_les_restes,
    _Comptes,
    _connecter,
    _identifiants,
    _issue,
    _journal_des_reprises,
    _panne,
    _Tour,
    boite_a_outils,
    instruction,
    modele,
    verifier_acces,
)
from banc.encodage import DIMENSIONS
from banc.essai_serveur import EssaiError, lire
from banc.isolement import CleAbsente
from banc.mesures import Entete, Journal, MesureError, empreinte_vecteur, fichier_trace
from banc.notation import LECTURE
from banc.prix import PrixError, Tarif

CLIENTS = ("graphrag-claude", "graphrag-gemini")
# Même client et même modèle que les cellules ADK du jalon 2 (D7) : l'écart tient à la technique.
JUMELLES: Final = {"graphrag-claude": "adk-claude", "graphrag-gemini": "adk-gemini"}
# Le message d'un tour (D8, choix de Julien du 2026-10-18) : le contexte d'abord, la question à la
# fin, entre balises, comme le conseillent les docs de Claude et de Gemini.
MESSAGE = "<contexte>\n{contexte}\n</contexte>\n\n<question>\n{question}\n</question>"

# L'appel au modèle d'un tour, le contexte en main : il note sur le tour sa réponse, ou ce qui l'a
# coupé ; la cellule tient l'échéance du tour.
type Redaction = Callable[[_Tour, str, str], Awaitable[None]]
# La rédaction d'une conversation, faite avec ses comptes (usage, coût, budget) : ADK, ou un
# rédacteur factice dans les tests de la recherche.
type Redacteur = Callable[[_Comptes], Redaction]


async def converser(
    client: str,
    commande: Commande,
    tarifs: Sequence[Tarif],
    redacteur: Redacteur | None = None,
) -> None:
    """Mène la conversation de la commande et en écrit la trace : pour chaque question, la
    recherche, le garde-fou, puis l'appel au modèle (redacteur : ADK sans outil si None).

    Le serveur se connecte avant le chrono ; une panne avant la première question la note en
    panne. Une question qui n'a pas de réponse arrête la conversation, comme dans les cellules ADK
    (ADR-0012).

    Raises:
        CelluleError: client inconnu ; commande sans un vecteur par question de la dimension de
            l'index ; consigne, fiche ou requête de recherche changées depuis la création de la
            campagne ; ADC de Vertex refusée.
        CleAbsente: cellule Claude sans clé Anthropic.
        IsolementError: cellule Gemini qui reçoit la clé Anthropic, ou serveur sans read-cypher.
    """
    if client not in JUMELLES:
        raise CelluleError(f"client inconnu : {client} (attendu : {', '.join(CLIENTS)})")
    jumelle = JUMELLES[client]
    verifier_acces(jumelle)
    vecteurs = _vecteurs(commande)
    # Avant toute trace : un prompt ou une requête de recherche modifiés depuis la création de la
    # campagne arrêtent tout (D7).
    prompt = consigne_et_fiche(
        schema=commande.schema, empreinte=commande.empreinte_prompt, consigne="contexte"
    )
    requete = requete_de_recherche(commande.empreinte_recherche)
    avant = asyncio.all_tasks()
    boite = boite_a_outils(commande)
    try:
        initiale = await _connecter(boite, commande.plafonds.connexion_s)
        info = None if initiale is None else initiale.server_info
        en_tete = entete(client, commande, "absent" if info is None else info.version)
        with Journal(fichier_trace(commande.traces, en_tete), en_tete) as journal:
            if initiale is None:
                _panne_avant(journal, commande, "serveur")
                return
            comptes = _Comptes(journal, en_tete, commande, tarifs)
            rediger: Redaction | None
            if redacteur is None:
                rediger = await _redaction_adk(client, comptes, prompt, boite, initiale)
            else:
                rediger = redacteur(comptes)
            if rediger is None:
                return
            conversation = _Conversation(
                journal, en_tete, commande, comptes, initiale, requete, rediger
            )
            with _journal_des_reprises(jumelle, comptes):
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


def _panne_avant(journal: Journal, commande: Commande, cause: str) -> None:
    """Une panne avant la première question (serveur, jeton de Vertex) : notée sur elle."""
    ident, message = commande.questions[0]
    journal.question(ident, message)
    journal.fin("panne", cause)


async def _redaction_adk(
    client: str, comptes: _Comptes, prompt: str, boite: McpToolset, initiale: ClientSession
) -> Redaction | None:
    """L'appel au modèle par ADK, sans outil (D7) : le modèle, ses réglages et son cache, ceux de
    la cellule ADK jumelle, et sa lecture du flux, dans une seule session d'ADK. L'ADC de Vertex se
    prend ici, avant le chrono. None : jeton de Vertex indisponible, panne notée sur la première
    question.

    Raises:
        CelluleError: ADC de Vertex refusée.
    """
    jumelle, commande = JUMELLES[client], comptes.commande
    try:
        identifiants = await _identifiants(jumelle)
    except google.auth.exceptions.GoogleAuthError as erreur:
        if not _panne(erreur):
            raise CelluleError(f"ADC de Vertex refusée : {erreur}") from erreur
        print(f"cellule {client} : jeton de Vertex indisponible ({erreur})", file=sys.stderr)
        _panne_avant(comptes.journal, commande, "api")
        return None
    llm, config, cache = modele(jumelle, commande, comptes.anthropic, identifiants)
    agent = LlmAgent(
        name=AGENT,
        model=llm,
        instruction=instruction(prompt),
        tools=[],
        generate_content_config=config,
        after_model_callback=comptes.apres_le_modele,
    )
    sessions = InMemorySessionService()
    runner = Runner(
        app=App(name=APPLI, root_agent=agent, context_cache_config=cache),
        session_service=sessions,
    )
    session = await sessions.create_session(app_name=APPLI, user_id=UTILISATEUR)
    # La lecture du flux des cellules ADK ; sans outil, la boîte et la session MCP n'y servent pas.
    lecture = cellule_adk._Conversation(
        runner, session.id, comptes.journal, comptes.entete, commande, comptes, boite, initiale
    )

    async def rediger(tour: _Tour, message: str, contexte: str) -> None:
        await lecture._lire(tour, MESSAGE.format(contexte=contexte, question=message))

    return rediger


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
        """Pose une question et en note le tour ; renvoie son issue. L'échéance du tour couvre la
        recherche et l'appel au modèle."""
        self.journal.question(ident, message)
        tour = _Tour()
        self.comptes.tour = tour
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
        finally:
            self.comptes.tour = None
        if tour.usage_partiel is not None:
            # Un appel coupé avant sa réponse finale : son dernier morceau donne ce qu'on sait de
            # son usage, comme dans les cellules ADK.
            self.comptes.compter(*tour.usage_partiel, tour, partiel=True)
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


async def _lancer(client: str, commande: Commande, tarifs: Sequence[Tarif]) -> None:
    """La conversation, qu'un SIGTERM annule : le serveur MCP, dans sa propre session, est alors
    arrêté avant la sortie."""
    tache = asyncio.current_task()
    assert tache is not None
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, tache.cancel)
    await converser(client, commande, tarifs)


def main(arguments: Sequence[str] | None = None) -> int:
    """Lit la commande sur stdin et mène la conversation : 0, 2 sur une erreur technique, 143 sur
    un SIGTERM."""
    lus = list(sys.argv[1:] if arguments is None else arguments)
    if len(lus) != 1 or lus[0] not in CLIENTS:
        print(f"usage : python -m banc.cellule_graphrag {'|'.join(CLIENTS)}", file=sys.stderr)
        return 2
    client = lus[0]
    try:
        commande = lire_commande(sys.stdin.read())
        asyncio.run(_lancer(client, commande, prix.charger()))
    except asyncio.CancelledError:
        print(f"cellule {client} : arrêtée par SIGTERM", file=sys.stderr)
        return INTERROMPUE
    except (CelluleError, CleAbsente, MesureError, PrixError, OSError) as erreur:
        print(f"cellule {client} : {erreur}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
