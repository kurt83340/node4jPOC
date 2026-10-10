"""Cellules ADK (plan 002, T4.2 ; D2, D3, D13) : ADK + Claude par l'API Anthropic, ADK + Gemini par
Vertex `eu`.

`python -m banc.cellule_adk adk-claude|adk-gemini` lit sa commande (banc.cellule) sur stdin, mène la
conversation dans une session d'ADK et en écrit la trace (banc.mesures). L'orchestration la lance
dans un processus dont l'environnement est la liste blanche de banc.isolement ; le serveur MCP
reçoit cette liste telle quelle (sans env explicite, mcp 2.3.0 ne lui passerait que HOME, PATH et
quatre variables du poste).

Relevé sur ADK 2.11.0 (google-genai 2.28.0, anthropic 1.11.0, mcp 2.3.0), contre une fausse API et
un faux serveur (tests/test_cellule_adk.py) :
- le délai de StdioConnectionParams borne la connexion, mais aussi chaque appel d'outil (5 s par
  défaut), quand Claude Code attend un outil sans limite utile : il dépasse ici le plafond d'un
  tour, et la cellule borne elle-même la connexion (30 s, comme MCP_TIMEOUT de Claude Code) ;
- ADK lit une consigne en texte comme un gabarit : {rang} de la fiche y serait une variable de
  session (KeyError) ; elle lui est passée par une fonction, telle quelle ;
- ADK relit la liste des outils à chaque appel du modèle : gardée pour la conversation, elle n'est
  lue qu'une fois, avant le chrono ; ADK relance seul un serveur perdu au prochain appel d'outil :
  la cellule compare la session MCP à celle d'avant le chrono ;
- l'usage se compte dans le rappel qu'ADK appelle après chaque réponse du modèle : il les voit
  toutes, même une réponse vide de Gemini, qu'ADK ne rend pas en événement ; en flux, Gemini joint
  aussi l'usage aux morceaux partiels, dont le dernier ne sert que si l'appel est coupé ; un appel
  de Claude coupé par le délai ne rend aucun usage, le coût d'un délai dépassé est une borne basse
  (choix de Julien) ; un résultat d'outil qui ferait dépasser le budget arrête le tour avant
  l'appel suivant (garde-fou, choix de Julien : ADK ne coupe pas un résultat comme Claude Code) ;
- reprises internes : le middleware du client Anthropic voit chaque tentative en échec ;
  google-genai passe par aiohttp, sans crochet : ses reprises se lisent dans son journal ;
- une erreur que l'API annonce dans un flux ouvert (surcharge) fait lever à ADK
  httpx2.ResponseNotRead, en lisant le corps de l'erreur pour l'envelopper (workflow/_errors.py),
  sans chaîne vers l'erreur d'origine : une panne, comme une coupure du flux.
"""

import asyncio
import json
import logging
import os
import re
import signal
import sys
from collections.abc import Awaitable, Callable, Iterator, Mapping, Sequence
from contextlib import aclosing, contextmanager
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from importlib.metadata import version
from typing import Any, Final

import aiohttp
import anthropic
import google.auth
import google.auth.exceptions
import google.auth.transport.requests
import httpx2
from google.adk.agents import LlmAgent
from google.adk.agents._streaming_mode import StreamingMode
from google.adk.agents.callback_context import CallbackContext
from google.adk.agents.context_cache_config import ContextCacheConfig
from google.adk.agents.invocation_context import LlmCallsLimitExceededError
from google.adk.agents.readonly_context import ReadonlyContext
from google.adk.agents.run_config import RunConfig
from google.adk.apps import App
from google.adk.events import Event
from google.adk.models import BaseLlm, Gemini
from google.adk.models.anthropic_llm import AnthropicGenerateContentConfig, AnthropicLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from google.auth.credentials import Credentials
from google.genai import errors as erreurs_genai
from google.genai import types
from mcp import ClientSession, StdioServerParameters

from banc import prix
from banc.cellule import (
    CelluleError,
    Commande,
    IsolementError,
    Plafonds,
    consigne_et_fiche,
    lire_commande,
)
from banc.isolement import EFFORT, PROJET, REGION, REPRISES, CleAbsente, cle_anthropic
from banc.mesures import (
    OUTILS,
    Entete,
    Journal,
    MesureError,
    commit_pokeapi,
    couts,
    fichier_trace,
    usage_adk,
)
from banc.notation import LECTURE
from banc.prix import PrixError, Tarif, Usage, tarif

CLIENTS = ("adk-claude", "adk-gemini")
MODELES: Final = {"adk-claude": "claude-sonnet-5-5", "adk-gemini": "gemini-3.8-flash"}
ACCES: Final = {"adk-claude": "api", "adk-gemini": "vertex-eu"}
# Plafond de sortie de Claude Code 2.1.292 (relevé T4.2), au lieu des 8 192 d'ADK (choix de
# Julien) : au-delà de ~21 000 tokens, le SDK Anthropic exige le flux, que la cellule demande.
SORTIE_MAX_CLAUDE = 128_000
# Réflexion adaptative de Claude, la seule où l'effort joue (D2).
REFLEXION_ADAPTATIVE = -1
NIVEAU_GEMINI: Final = types.ThinkingLevel.HIGH
# Autant de reprises que les cellules Claude (choix de Julien) ; délais de google-genai.
REPRISES_GEMINI = types.HttpRetryOptions(attempts=REPRISES + 1)
# Durée du cache de prompt d'ADK + Claude (D10) : 1 h dès 3 600 s, sinon 5 min.
CACHE_S: Final = {True: 3600, False: 300}
# La liste des outils, lue avant le chrono, sert toute la conversation.
LISTE_OUTILS_S = 24 * 3600.0
# ADK le cite dans le prompt (« Your internal name is … ») : un nom neutre.
AGENT = "agent"
APPLI = "banc"
UTILISATEUR = "banc"
# Journal de google-genai, où tenacity écrit chaque reprise (« Retrying … as it raised
# ClientError: 429 … »), comme la reprise d'une erreur de connexion d'aiohttp.
JOURNAL_GENAI = "google_genai._api_client"
# Journaux d'ADK 2.11.0 qui écrivent sur stderr, trace comprise, l'épuisement des appels du modèle
# (« Node execution failed with exception », « Root node agent failed. ») : la cellule le traite
# elle-même, issue « tours » (bruit relevé en T5.1).
JOURNAUX_DES_TOURS = (
    "google_adk.google.adk.workflow._node_runner",
    "google_adk.google.adk.runners",
)
STATUT_REPRISE = re.compile(r"Error: (\d{3}) ")
# Plafond de dépense atteint (D13) : type d'erreur de l'API, ou message relevé par Claude Code.
CREDITS_EPUISES = "billing_error"
SOLDE_EPUISE = "credit balance is too low"
# Portée de l'ADC de Vertex, celle que google-genai demande lui-même (_api_client.load_auth).
PORTEE_VERTEX = "https://www.googleapis.com/auth/cloud-platform"
# Garde-fou de budget : un résultat d'outil compte un token pour 3 caractères (par excès).
CARACTERES_PAR_TOKEN = 3
INTERROMPUE = 128 + signal.SIGTERM


@dataclass
class _Tour:
    """Ce qu'un tour accumule en cours de lecture."""

    # Appels d'outils notés, pour apparier leurs résultats.
    appels: set[str] = field(default_factory=set)
    reprises: int = 0
    # « delai », « budget » ou « tours ».
    coupure: str | None = None
    # Erreur de l'API (ou de son transport) qui a fini le tour.
    erreur: Exception | None = None
    serveur_perdu: bool = False
    reponse: str = ""
    # Usage du dernier morceau partiel de l'appel en cours, et sa version de modèle : il ne sert que
    # si l'appel finit sans événement final (réponse vide de Gemini, appel coupé).
    usage_partiel: tuple[types.GenerateContentResponseUsageMetadata, str | None] | None = None


@dataclass
class _Comptes:
    """Ce que la conversation reprend et coûte, appel par appel (D13) : les reprises internes du
    client, l'usage de chaque appel du modèle, le budget."""

    journal: Journal
    entete: Entete
    commande: Commande
    tarifs: Sequence[Tarif]
    # Tour en cours ; None entre deux questions.
    tour: _Tour | None = None
    cout: Decimal = Decimal(0)

    def noter_reprise(self, statut: int | None) -> None:
        if self.tour is not None:
            self.tour.reprises += 1
            self.journal.reprise(statut)

    async def anthropic(self, requete: anthropic.APIRequest, suite: Callable[..., Any]) -> Any:
        """Middleware du client Anthropic, appelé à chaque tentative : une tentative en échec que
        le SDK va reprendre se note aussitôt, avant l'attente de la reprise, où l'échéance du tour
        peut tomber (D13)."""
        reprise_possible = requete.retries_taken < REPRISES
        try:
            reponse = await suite(requete)
        except anthropic.APIConnectionError:
            if reprise_possible:
                self.noter_reprise(None)
            raise
        if reprise_possible and _reprise_anthropic(reponse.http_response):
            self.noter_reprise(reponse.status_code)
        return reponse

    def apres_le_modele(
        self, callback_context: CallbackContext, llm_response: LlmResponse
    ) -> LlmResponse | None:
        """Rappel d'ADK après chaque réponse du modèle, morceaux compris, avant qu'il décide d'en
        faire un événement : une réponse finale se compte toujours, même celle qu'il tait ; d'un
        morceau, seul l'usage se garde, pour un appel coupé avant sa réponse finale.

        Raises:
            MesureError: réponse finale sans usage.
        """
        tour, meta = self.tour, llm_response.usage_metadata
        # ADK n'appelle ce rappel que pendant run_async, donc dans un tour.
        assert tour is not None
        if llm_response.partial:
            if meta is not None:
                tour.usage_partiel = (meta, llm_response.model_version)
            return None
        if meta is None:
            raise MesureError(f"{self.entete.modele} : réponse du modèle sans usage")
        tour.usage_partiel = None
        self.compter(meta, llm_response.model_version, tour)
        return None

    def compter(
        self,
        meta: types.GenerateContentResponseUsageMetadata,
        version: str | None,
        tour: _Tour,
        *,
        partiel: bool = False,
    ) -> None:
        """Usage d'un appel du modèle : trace, coût, budget (D13). partiel : tiré du dernier
        morceau d'un appel coupé avant sa réponse finale."""
        usage = usage_adk(meta, cache_1h=self.commande.cache_1h)
        brut: dict[str, Any] = meta.model_dump(mode="json", exclude_none=True)
        ecrit = getattr(meta, "cache_creation_input_tokens", None)
        if ecrit is not None:
            brut["cache_creation_input_tokens"] = ecrit
        brut["model_version"] = version
        if partiel:
            brut["partiel"] = True
        modele_ = self.entete.modele
        self.journal.llm(modele_, usage, meta.thoughts_token_count, brut)
        jour, acces = self.entete.jour, self.entete.acces
        self.cout += couts({modele_: usage}, self.tarifs, jour, acces)[modele_]
        if tour.coupure is None and self.cout > self.commande.plafonds.budget_usd:
            tour.coupure = "budget"

    def estimation(self, caracteres: int) -> Decimal:
        """Coût, par excès, de caractères ajoutés à l'entrée de l'appel suivant : un token pour 3
        caractères, au prix de l'entrée, ou de l'écriture en cache à la durée de la commande s'il
        est plus haut (ADK + Claude écrit en cache la fin de chaque requête)."""
        tokens = -(-caracteres // CARACTERES_PAR_TOKEN)
        prix_ = tarif(list(self.tarifs), self.entete.modele, self.entete.jour, self.entete.acces)
        if self.commande.cache_1h:
            ecriture = Usage(cache_ecriture_1h=tokens)
        else:
            ecriture = Usage(cache_ecriture_5m=tokens)
        return max(prix_.cout(Usage(entree=tokens)), prix_.cout(ecriture))


class _JournalGenai(logging.Handler):
    """Reprises de google-genai, lues dans son journal (tenacity, aiohttp) : aucun crochet HTTP."""

    def __init__(self, comptes: _Comptes) -> None:
        super().__init__(logging.INFO)
        self.comptes = comptes

    def emit(self, record: logging.LogRecord) -> None:
        message = record.getMessage()
        if message.startswith("Retrying"):
            statut = STATUT_REPRISE.search(message)
            self.comptes.noter_reprise(None if statut is None else int(statut[1]))


def verifier_acces(client: str) -> None:
    """L'accès de la cellule à son modèle, vérifié avant de lancer quoi que ce soit (D3).

    Raises:
        CleAbsente: cellule Claude sans clé Anthropic.
        IsolementError: cellule Gemini qui reçoit la clé Anthropic.
        CelluleError: client inconnu.
    """
    if client == "adk-claude":
        cle_anthropic()
    elif client == "adk-gemini":
        if "ANTHROPIC_API_KEY" in os.environ:
            raise IsolementError("la cellule Gemini ne reçoit jamais la clé Anthropic (D3)")
    else:
        raise CelluleError(f"client inconnu : {client} (attendu : {', '.join(CLIENTS)})")


def identifiants_vertex() -> Credentials:
    """L'ADC de la cellule Gemini, comme google-genai la charge, rafraîchie avant le chrono : sinon
    il irait chercher son jeton pendant la première question (un aller-retour vers Google dans le
    temps mesuré).

    Raises:
        google.auth.exceptions.GoogleAuthError: ADC introuvable, refusée ou injoignable.
    """
    identifiants, _projet = google.auth.default(scopes=[PORTEE_VERTEX])
    identifiants.refresh(google.auth.transport.requests.Request())  # type: ignore[no-untyped-call]
    return identifiants


def modele(
    client: str,
    commande: Commande,
    middleware: Callable[..., Awaitable[Any]] | None = None,
    identifiants: Credentials | None = None,
) -> tuple[BaseLlm, types.GenerateContentConfig, ContextCacheConfig | None]:
    """Modèle de la cellule, sa configuration (effort ou niveau de réflexion, D2) et son cache ;
    middleware : celui du client Anthropic (reprises), identifiants : l'ADC de Vertex.

    Raises:
        CleAbsente: cellule Claude sans clé Anthropic.
        IsolementError: cellule Gemini qui reçoit la clé Anthropic (D3).
        CelluleError: client inconnu.
    """
    verifier_acces(client)
    if client == "adk-claude":
        connexion = anthropic.AsyncAnthropic(
            api_key=cle_anthropic(),
            max_retries=REPRISES,
            middleware=[] if middleware is None else [middleware],
        )
        claude = AnthropicLlm(model=MODELES[client], max_tokens=SORTIE_MAX_CLAUDE, client=connexion)
        reflexion = types.ThinkingConfig(thinking_budget=REFLEXION_ADAPTATIVE)
        config = AnthropicGenerateContentConfig(effort=EFFORT, thinking_config=reflexion)
        return claude, config, ContextCacheConfig(ttl_seconds=CACHE_S[commande.cache_1h])
    options: dict[str, Any] = {"enterprise": True, "project": PROJET, "location": REGION}
    if identifiants is not None:
        options["credentials"] = identifiants
    gemini = Gemini(model=MODELES[client], retry_options=REPRISES_GEMINI, client_kwargs=options)
    niveau = types.ThinkingConfig(thinking_level=NIVEAU_GEMINI)
    # Ni ContextCacheConfig ni cache stocké : le cache implicite de Vertex (banc/prix.toml).
    return gemini, types.GenerateContentConfig(thinking_config=niveau), None


def boite_a_outils(commande: Commande) -> McpToolset:
    """Le serveur MCP de la commande en stdio, read-cypher seul (D1), avec l'environnement de la
    cellule ; son délai, qui borne aussi chaque appel d'outil, dépasse le plafond d'un tour."""
    lanceur, *arguments = commande.serveur
    plafonds = commande.plafonds
    parametres = StdioServerParameters(command=lanceur, args=arguments, env=dict(os.environ))
    connexion = StdioConnectionParams(
        server_params=parametres, timeout=plafonds.delai_s + plafonds.connexion_s
    )
    return McpToolset(
        connection_params=connexion,
        tool_filter=[LECTURE],
        tool_list_cache_ttl_seconds=LISTE_OUTILS_S,
    )


def instruction(texte: str) -> Callable[[ReadonlyContext], str]:
    """La consigne et la fiche, telles quelles : par une fonction, ADK ne les lit pas comme un
    gabarit."""

    def fournir(_contexte: ReadonlyContext) -> str:
        return texte

    return fournir


def entete(client: str, commande: Commande, version_serveur: str) -> Entete:
    """En-tête de la trace : la cellule, son modèle et les versions qui la mesurent."""
    bibliotheque = "anthropic" if client == "adk-claude" else "google-genai"
    versions = {nom: version(nom) for nom in ("google-adk", "mcp", bibliotheque)}
    return Entete(
        campagne=commande.campagne,
        cellule=client,
        passe=commande.passe,
        essai=commande.essai,
        questions=tuple(ident for ident, _ in commande.questions),
        modele=MODELES[client],
        acces=ACCES[client],
        jour=date.today(),
        effort=EFFORT,
        versions=versions | {"neo4j-mcp": version_serveur},
        commit_pokeapi=commit_pokeapi(),
    )


async def session_mcp(boite: McpToolset) -> ClientSession:
    """La session MCP qu'ADK donnerait au prochain appel d'outil, après avoir relancé le serveur
    s'il est perdu. Seul accès à un attribut privé d'ADK 2.11.0 : aucun accesseur public."""
    return await boite._mcp_session_manager.create_session()


async def converser(client: str, commande: Commande, tarifs: Sequence[Tarif]) -> None:
    """Mène la conversation de la commande, dans une seule session d'ADK, et en écrit la trace.

    Le serveur se connecte avant le chrono ; une panne avant la première question la note en
    panne. Une question qui n'a pas de réponse arrête la conversation : le second tour d'une paire
    après un échec est l'affaire de l'orchestration (ADR-0012, T4.3).
    """
    verifier_acces(client)
    avant = asyncio.all_tasks()
    boite = boite_a_outils(commande)
    try:
        initiale = await _connecter(boite, commande.plafonds.connexion_s)
        info = None if initiale is None else initiale.server_info
        en_tete = entete(client, commande, "absent" if info is None else info.version)
        with Journal(fichier_trace(commande.traces, en_tete), en_tete) as journal:
            ident, message = commande.questions[0]
            if initiale is None:
                journal.question(ident, message)
                journal.fin("panne", "serveur")
                return
            try:
                identifiants = await _identifiants(client)
            except google.auth.exceptions.GoogleAuthError as erreur:
                if not _panne(erreur):
                    raise CelluleError(f"ADC de Vertex refusée : {erreur}") from erreur
                print(
                    f"cellule {client} : jeton de Vertex indisponible ({erreur})", file=sys.stderr
                )
                journal.question(ident, message)
                journal.fin("panne", "api")
                return
            comptes = _Comptes(journal, en_tete, commande, tarifs)
            llm, config, cache = modele(client, commande, comptes.anthropic, identifiants)
            agent = LlmAgent(
                name=AGENT,
                model=llm,
                instruction=instruction(consigne_et_fiche()),
                tools=[boite],
                generate_content_config=config,
                after_model_callback=comptes.apres_le_modele,
            )
            sessions = InMemorySessionService()
            runner = Runner(
                app=App(name=APPLI, root_agent=agent, context_cache_config=cache),
                session_service=sessions,
            )
            session = await sessions.create_session(app_name=APPLI, user_id=UTILISATEUR)
            conversation = _Conversation(
                runner, session.id, journal, en_tete, commande, comptes, boite, initiale
            )
            with _journal_des_reprises(client, comptes):
                for ident, message in commande.questions:
                    if await conversation.tour(ident, message) != "reponse":
                        break
    finally:
        await boite.close()
        await _arreter_les_restes(avant)


async def _identifiants(client: str) -> Credentials | None:
    """Les identifiants de Vertex de la cellule Gemini, rafraîchis hors du chrono ; aucun pour
    Claude (sa clé suffit).

    Raises:
        google.auth.exceptions.GoogleAuthError: ADC introuvable, refusée ou injoignable.
    """
    if client != "adk-gemini":
        return None
    return await asyncio.to_thread(identifiants_vertex)


async def _arreter_les_restes(avant: set[asyncio.Task[Any]]) -> None:
    """Annule et attend les tâches nées pendant la conversation qu'ADK laisse derrière lui : la
    session MCP dont un délai a coupé la connexion (ou la relance) n'entre pas dans son pool, et
    `McpToolset.close()` ne la voit pas. Son serveur s'arrête ainsi avant que la cellule rende la
    main, pas à la fin de la boucle ; les tâches d'avant la conversation ne sont pas touchées."""
    courante = asyncio.current_task()
    restes = [
        tache for tache in asyncio.all_tasks() if tache is not courante and tache not in avant
    ]
    for tache in restes:
        tache.cancel()
    await asyncio.gather(*restes, return_exceptions=True)


async def _connecter(boite: McpToolset, delai_s: float) -> ClientSession | None:
    """Lance le serveur et lit ses outils avant le chrono (D3). None : panne (échec, ou délai
    dépassé).

    Raises:
        IsolementError: le serveur connecté sans read-cypher, ou avec un autre outil visible.
    """
    try:
        async with asyncio.timeout(delai_s):
            outils = await boite.get_tools()
            session = await session_mcp(boite)
    except (TimeoutError, ConnectionError) as erreur:
        print(f"cellule ADK : serveur MCP injoignable ({erreur!r})", file=sys.stderr)
        return None
    noms = [outil.name for outil in outils]
    if noms != [LECTURE]:
        raise IsolementError(f"outils visibles de l'agent : {noms}, attendu [{LECTURE}]")
    return session


@contextmanager
def _journal_des_reprises(client: str, comptes: _Comptes) -> Iterator[None]:
    """Branche le relevé des reprises de google-genai sur son journal, le temps de la
    conversation."""
    if client != "adk-gemini":
        yield
        return
    journal = logging.getLogger(JOURNAL_GENAI)
    niveau = journal.level
    releve = _JournalGenai(comptes)
    journal.addHandler(releve)
    journal.setLevel(logging.INFO)
    try:
        yield
    finally:
        journal.removeHandler(releve)
        journal.setLevel(niveau)


@dataclass
class _Conversation:
    """Une session d'ADK, question après question : trace, usage, budget, issue."""

    runner: Runner
    session: str
    journal: Journal
    entete: Entete
    commande: Commande
    comptes: _Comptes
    boite: McpToolset
    # Session MCP d'avant le chrono : une autre en fin de tour, c'est le serveur perdu.
    initiale: ClientSession

    @property
    def plafonds(self) -> Plafonds:
        return self.commande.plafonds

    async def tour(self, ident: str, message: str) -> str:
        """Pose une question et en note le tour ; renvoie son issue."""
        self.journal.question(ident, message)
        tour = _Tour()
        self.comptes.tour = tour
        try:
            await self._lire(tour, message)
        finally:
            self.comptes.tour = None
        if tour.usage_partiel is not None:
            # Un appel coupé avant sa réponse finale : son dernier morceau donne ce qu'on sait de
            # son usage.
            self.comptes.compter(*tour.usage_partiel, tour, partiel=True)
        if not tour.serveur_perdu:
            tour.serveur_perdu = not await self._serveur_intact()
        issue, cause = _issue(tour)
        self.journal.fin(issue, cause, tour.reponse if issue == "reponse" else "")
        return issue

    async def _lire(self, tour: _Tour, message: str) -> None:
        """Lit les événements du tour jusqu'à sa fin ; au délai, au budget ou au serveur perdu, le
        coupe (ADK annule alors l'appel en cours)."""
        echeance = asyncio.get_running_loop().time() + self.plafonds.delai_s
        question = types.Content(role="user", parts=[types.Part(text=message)])
        evenements = self.runner.run_async(
            user_id=UTILISATEUR,
            session_id=self.session,
            new_message=question,
            run_config=RunConfig(
                streaming_mode=StreamingMode.SSE, max_llm_calls=self.plafonds.tours
            ),
        )
        delai = asyncio.timeout_at(echeance)
        try:
            async with delai, aclosing(evenements) as flux:
                async for evenement in flux:
                    await self._noter(evenement, tour)
                    if tour.coupure is not None or tour.serveur_perdu:
                        break
        except TimeoutError as erreur:
            if delai.expired():
                tour.coupure = "delai"
            else:
                tour.erreur = erreur
        except LlmCallsLimitExceededError:
            tour.coupure = "tours"
        except (
            anthropic.APIError,
            erreurs_genai.APIError,
            erreurs_genai.UnknownApiResponseError,
            aiohttp.ClientError,
            httpx2.HTTPError,
            httpx2.StreamError,
            google.auth.exceptions.GoogleAuthError,
        ) as erreur:
            tour.erreur = erreur

    async def _noter(self, evenement: Event, tour: _Tour) -> None:
        """Note un événement final d'ADK : les appels d'outils d'une réponse du modèle, leurs
        résultats, et la réponse finale (l'usage, lui, se compte dans le rappel d'ADK)."""
        if evenement.partial:
            return
        # L'épuisement des appels du modèle s'écrit dans la trace (issue « tours »), pas sur stderr.
        if evenement.error_code and evenement.error_code != LlmCallsLimitExceededError.__name__:
            print(
                f"cellule {self.entete.cellule} : {evenement.error_code} "
                f"{evenement.error_message or ''}",
                file=sys.stderr,
            )
        contenu = evenement.content
        if contenu is None:
            return
        if contenu.role == "model":
            self._reponse_du_modele(contenu.parts or [], tour)
        else:
            await self._resultats(contenu.parts or [], tour)

    def _reponse_du_modele(self, parties: Sequence[types.Part], tour: _Tour) -> None:
        """Les appels d'outils d'une réponse du modèle ; sans appel, c'est sa réponse finale."""
        for partie in parties:
            if partie.function_call is not None and (lu := appel_d_outil(partie.function_call)):
                ident, outil, requete, parametres = lu
                tour.appels.add(ident)
                self.journal.appel(ident, outil, requete, parametres)
        if not any(partie.function_call for partie in parties):
            textes = [partie.text for partie in parties if partie.text and not partie.thought]
            tour.reponse = "\n".join(textes)

    async def _resultats(self, parties: Sequence[types.Part], tour: _Tour) -> None:
        """Les résultats des outils : trace, garde-fou de budget, puis le serveur toujours là."""
        resultats = [p.function_response for p in parties if p.function_response is not None]
        for reponse in resultats:
            if reponse.id in tour.appels:
                texte, erreur = _resultat(reponse.response or {})
                self.journal.resultat(reponse.id, texte, erreur)
        # Garde-fou de budget (choix de Julien) : ce que les résultats ajoutent à l'entrée de
        # l'appel suivant ne doit pas faire dépasser le budget.
        taille = sum(_taille_envoyee(self.entete.cellule, r.response or {}) for r in resultats)
        estimation = self.comptes.estimation(taille)
        if tour.coupure is None and self.comptes.cout + estimation > self.plafonds.budget_usd:
            tour.coupure = "budget"
        if resultats and not await self._serveur_intact():
            tour.serveur_perdu = True

    async def _serveur_intact(self) -> bool:
        """Le serveur d'avant le chrono sert encore : ADK n'a pas eu à le relancer."""
        try:
            async with asyncio.timeout(self.plafonds.connexion_s):
                courante = await session_mcp(self.boite)
        except TimeoutError, ConnectionError:
            return False
        return courante is self.initiale


def appel_d_outil(
    appel: types.FunctionCall,
) -> tuple[str, str, str, Mapping[str, object] | None] | None:
    """Un appel d'outil de neo4j-mcp, tel que la trace le note (identifiant, outil, requête,
    paramètres) ; None pour un autre outil, que la trace ignore (comme la cellule Claude Code).

    Raises:
        MesureError: appel sans identifiant (ADK en donne un à chaque appel) : son résultat ne
            pourrait pas lui être apparié.
    """
    nom, ident = appel.name, appel.id
    if nom is None or nom not in OUTILS:
        return None
    if not ident:
        raise MesureError(f"appel de {nom} sans identifiant")
    arguments = dict(appel.args or {})
    parametres = arguments.get("params")
    if parametres is not None and not isinstance(parametres, Mapping):
        parametres = {"params": parametres}
    return ident, nom, str(arguments.get("query", "")), parametres


def _issue(tour: _Tour) -> tuple[str, str | None]:
    """Issue et cause d'un tour (D13), dans l'ordre de la cellule Claude Code : crédits épuisés,
    arrêt ; serveur perdu, panne ; budget dépassé, échec ; délai dépassé, échec, ou panne si le
    tour a dû reprendre un appel ; tours épuisés, échec ; 429, 5xx ou transport, panne.

    Raises:
        CelluleError: tout autre refus de l'API (400, 401, 403…), qui arrête la campagne.
    """
    if _credits_epuises(tour.erreur):
        return "arret", "plafond"
    if tour.serveur_perdu:
        return "panne", "serveur"
    if tour.coupure == "delai" and tour.reprises:
        return "panne", "reprises"
    if tour.coupure is not None:
        return "echec", tour.coupure
    if tour.erreur is not None:
        if _panne(tour.erreur):
            return "panne", "api"
        raise CelluleError(f"refus de l'API : {tour.erreur!r}")
    return "reponse", None


def _credits_epuises(erreur: Exception | None) -> bool:
    """Crédits épuisés : le type d'erreur de l'API, ou le message que relève Claude Code."""
    if not isinstance(erreur, anthropic.APIStatusError):
        return False
    corps = erreur.body if isinstance(erreur.body, Mapping) else {}
    detail = corps.get("error")
    genre = detail.get("type") if isinstance(detail, Mapping) else None
    return genre == CREDITS_EPUISES or SOLDE_EPUISE in str(erreur).lower()


def _panne(erreur: Exception) -> bool:
    """Limite de débit ou erreur du fournisseur (429, 5xx), réponse illisible, flux coupé ou
    interrompu par une erreur (httpx2.ResponseNotRead d'ADK), transport coupé, point de jeton
    injoignable ou indisponible : une panne, relancée (D13). Des identifiants refusés n'en sont
    pas une."""
    match erreur:
        case anthropic.APIStatusError():
            return _statut_de_panne(erreur.status_code)
        case erreurs_genai.APIError():
            return _statut_de_panne(erreur.code)
        case google.auth.exceptions.TransportError():
            return True
        case google.auth.exceptions.GoogleAuthError():
            # google-auth marque retryable un échec passager du point de jeton (5xx, 429).
            return bool(erreur.retryable)
        case _:
            return True


def _reprise_anthropic(reponse: httpx2.Response) -> bool:
    """Le SDK Anthropic 1.11.0 reprendra cette réponse (_base_client.py, _should_retry) : l'en-tête
    x-should-retry d'abord, sinon 408, 409, 429 et 5xx."""
    if reponse.is_success:
        return False
    consigne = reponse.headers.get("x-should-retry")
    if consigne in {"true", "false"}:
        return bool(consigne == "true")
    return reponse.status_code in {408, 409, 429} or reponse.status_code >= 500


def _taille_envoyee(client: str, reponse: Mapping[str, Any]) -> int:
    """Taille de ce que le modèle reçoit d'un résultat d'outil : ADK donne à Claude le texte du
    résultat (models/anthropic_llm.py), à Gemini le résultat entier, sérialisé."""
    if client == "adk-claude" and "content" in reponse:
        blocs = reponse.get("content") or []
        textes = [bloc.get("text", "") for bloc in blocs if bloc.get("type") == "text"]
        return len("\n".join(textes))
    return len(json.dumps(reponse, ensure_ascii=False))


def _statut_de_panne(statut: int) -> bool:
    return statut == 429 or statut >= 500


def _resultat(reponse: Mapping[str, Any]) -> tuple[str, bool]:
    """Le texte d'un résultat d'outil et son erreur : le CallToolResult de MCP, ou l'erreur qu'ADK
    rend à l'agent quand l'appel n'aboutit pas."""
    if "content" in reponse:
        blocs = reponse.get("content") or []
        texte = "".join(bloc.get("text", "") for bloc in blocs if bloc.get("type") == "text")
        return texte, bool(reponse.get("isError"))
    return str(reponse.get("error", reponse)), True


class SansLesToursEpuises(logging.Filter):
    """Retire d'un journal d'ADK les enregistrements dont l'erreur est l'épuisement des appels du
    modèle (ADK 2.11.0 journalise LlmCallsLimitExceededError elle-même, deux fois) ; tout autre
    enregistrement passe, vraies erreurs comprises."""

    def filter(self, record: logging.LogRecord) -> bool:
        erreur = record.exc_info[1] if record.exc_info else None
        return not isinstance(erreur, LlmCallsLimitExceededError)


async def _lancer(client: str, commande: Commande, tarifs: Sequence[Tarif]) -> None:
    """La conversation, qu'un SIGTERM annule : le serveur MCP, dans sa propre session, est alors
    arrêté par son groupe avant la sortie."""
    tache = asyncio.current_task()
    assert tache is not None
    asyncio.get_running_loop().add_signal_handler(signal.SIGTERM, tache.cancel)
    await converser(client, commande, tarifs)


def main(arguments: Sequence[str] | None = None) -> int:
    """Lit la commande sur stdin et mène la conversation : 0, 2 sur une erreur technique, 143 sur
    un SIGTERM."""
    lus = list(sys.argv[1:] if arguments is None else arguments)
    if len(lus) != 1 or lus[0] not in CLIENTS:
        print(f"usage : python -m banc.cellule_adk {'|'.join(CLIENTS)}", file=sys.stderr)
        return 2
    client = lus[0]
    for nom in JOURNAUX_DES_TOURS:
        logging.getLogger(nom).addFilter(SansLesToursEpuises())
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
