"""Cellule Claude Code (plan 002, T4.1 ; D2, D3, D13) : Claude Code par l'Agent SDK, isolé.

`python -m banc.cellule_sdk` lit sa commande (banc.cellule) sur stdin, mène la conversation dans une
seule session de Claude Code et en écrit la trace (banc.mesures). L'orchestration la lance dans un
processus dont l'environnement est la liste blanche de banc.isolement : le SDK fusionne os.environ
avec le sien, Claude Code ne reçoit donc rien d'autre (l'équivalent d'env -i).

Relevé sur le vrai Claude Code 2.1.292, contre une fausse API et un faux serveur (T4.1,
tests/test_cellule_sdk_reel.py) :
- disallowed_tools ôte get-schema de la liste des outils, dontAsk refuse tout autre outil sans
  classifieur ; l'effort part dans chaque requête (output_config), mais init annonce effort=null ;
- --max-budget-usd montrerait son budget à l'agent après chaque appel : le budget se compte ici, sur
  le flux de l'API, qui ne change rien aux requêtes (include_partial_messages) ;
- model_usage cumule la session et oublie l'appel coupé par interrupt() ; le flux donne l'usage de
  chaque appel du modèle de la cellule, dont l'entrée et le cache de l'appel coupé (sa sortie reste
  inconnue : le coût d'un délai dépassé est une borne basse). Les tokens du modèle de la cellule
  viennent donc du flux, appel par appel ; ceux des autres modèles, de model_usage.
"""

import asyncio
import os
import sys
from collections.abc import AsyncGenerator, Mapping, Sequence
from contextlib import aclosing
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Final, cast

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ClaudeSDKError,
    McpServerStatus,
    McpStatusResponse,
    Message,
    ResultMessage,
    StreamEvent,
    SystemMessage,
    ToolResultBlock,
    ToolUseBlock,
    UserMessage,
)
from claude_agent_sdk import __version__ as VERSION_SDK
from claude_agent_sdk._cli_version import __cli_version__ as VERSION_CLI

from banc import prix
from banc.cellule import (
    CelluleError,
    Commande,
    IsolementError,
    Plafonds,
    consigne_et_fiche,
    lire_commande,
)
from banc.isolement import EFFORT, PETIT_MODELE, CleNonUtilisee, verifier_cle
from banc.mesures import (
    Entete,
    Journal,
    MesureError,
    commit_pokeapi,
    couts,
    fichier_trace,
    reflexion_anthropic,
    usage_anthropic,
    usage_claude_code,
    usage_du_tour,
)
from banc.notation import LECTURE, OUTILS_D_INTROSPECTION
from banc.prix import PrixError, Tarif, Usage

CLIENT = "claude-code"
MODELE = "claude-sonnet-5-5"
ACCES = "api"
SERVEUR = "neo4j"
PREFIXE = f"mcp__{SERVEUR}__"
# Seul outil de l'agent (D1) ; get-schema, que le serveur enregistre quoi qu'on fasse, est masqué.
OUTIL = PREFIXE + LECTURE
MASQUES = tuple(sorted(PREFIXE + nom for nom in OUTILS_D_INTROSPECTION))
PERMISSION: Final = "dontAsk"
VERSIONS = {"claude-agent-sdk": VERSION_SDK, "claude-code": VERSION_CLI}
# Entre deux relevés du statut MCP ; attente du résultat après interrupt().
RELEVE_S = 0.1
FIN_COUPURE_S = 10.0
# Erreurs de l'API que Claude Code rapporte (AssistantMessage.error) : une panne se relance, des
# crédits épuisés arrêtent la campagne (D13).
ERREURS_DE_PANNE = frozenset({"rate_limit", "server_error"})
CREDITS_EPUISES = "billing_error"


def options(commande: Commande, prompt: str) -> ClaudeAgentOptions:
    """Options de D3 : préréglage claude_code et prompt commun, aucun réglage lu, aucun outil
    intégré, read-cypher seul, serveur MCP passé en mémoire, budget compté par la cellule."""
    lanceur, *arguments = commande.serveur
    return ClaudeAgentOptions(
        model=MODELE,
        system_prompt={"type": "preset", "preset": "claude_code", "append": prompt},
        setting_sources=[],
        tools=[],
        allowed_tools=[OUTIL],
        disallowed_tools=list(MASQUES),
        mcp_servers={SERVEUR: {"type": "stdio", "command": lanceur, "args": arguments}},
        strict_mcp_config=True,
        permission_mode=PERMISSION,
        max_turns=commande.plafonds.tours,
        effort=EFFORT,
        include_partial_messages=True,
        cwd=Path.cwd(),
        cli_path=commande.cli,
        stderr=_relayer,
    )


def verifier_init(init: Mapping[str, Any]) -> None:
    """D3 sur ce que Claude Code annonce au début de chaque requête : la clé de l'API, read-cypher
    seul, dontAsk, le modèle et la version figés, notre seul serveur, ni socket entre sessions ni
    mémoire.

    Raises:
        CleNonUtilisee: Claude Code ne paie pas par la clé (circuit breaker).
        IsolementError: tout autre écart.
    """
    verifier_cle(init)
    serveurs = [serveur.get("name") for serveur in init.get("mcp_servers") or []]
    ecarts = {
        "tools": init.get("tools") != [OUTIL],
        "permissionMode": init.get("permissionMode") != PERMISSION,
        "model": init.get("model") != MODELE,
        "claude_code_version": init.get("claude_code_version") != VERSIONS["claude-code"],
        "mcp_servers": serveurs != [SERVEUR],
        # 2.1.292 annonce effort=null ; la requête porte bien l'effort (test réel).
        "effort": init.get("effort") not in {None, EFFORT},
        "messaging_socket_path": init.get("messaging_socket_path") is not None,
        "memory_paths": init.get("memory_paths") is not None,
    }
    if fautifs := [cle for cle, ecart in ecarts.items() if ecart]:
        valeurs = {cle: init.get(cle) for cle in fautifs}
        raise IsolementError(f"message init hors de D3 : {valeurs}")


def verifier_cache(commande: Commande) -> None:
    """La durée du cache de la commande est celle de l'environnement (banc.isolement)."""
    variable = "ENABLE_PROMPT_CACHING_1H" if commande.cache_1h else "FORCE_PROMPT_CACHING_5M"
    if os.environ.get(variable) != "1":
        raise IsolementError(f"cache de la commande sans {variable}=1 dans l'environnement")


async def attendre_serveur(client: ClaudeSDKClient, delai_s: float) -> McpServerStatus | None:
    """Relève le statut MCP jusqu'à « connected », avant le chrono (D3) : le démarrage du serveur
    ne compte pas dans le temps de la première question. None : panne (échec, ou délai dépassé).

    Raises:
        IsolementError: un autre serveur que le nôtre, ou le nôtre sans read-cypher.
    """
    boucle = asyncio.get_running_loop()
    echeance = boucle.time() + delai_s
    while True:
        statut = _statut(await client.get_mcp_status())
        if statut is not None and statut["status"] == "connected":
            outils = {outil["name"] for outil in statut.get("tools", [])}
            if LECTURE not in outils:
                raise IsolementError(f"serveur {SERVEUR} connecté sans {LECTURE} : {outils}")
            return statut
        if (statut is not None and statut["status"] != "pending") or boucle.time() >= echeance:
            return None
        await asyncio.sleep(RELEVE_S)


def entete(commande: Commande, version_serveur: str) -> Entete:
    """En-tête de la trace : la cellule, son modèle, son petit modèle (annexe) et leurs versions."""
    return Entete(
        campagne=commande.campagne,
        cellule=CLIENT,
        passe=commande.passe,
        essai=commande.essai,
        questions=tuple(ident for ident, _ in commande.questions),
        modele=MODELE,
        acces=ACCES,
        jour=date.today(),
        effort=EFFORT,
        versions=VERSIONS | {"neo4j-mcp": version_serveur},
        commit_pokeapi=commit_pokeapi(),
        annexes=(PETIT_MODELE,),
    )


async def converser(commande: Commande, tarifs: Sequence[Tarif]) -> None:
    """Mène la conversation de la commande, dans une seule session, et en écrit la trace.

    Le serveur se connecte avant le chrono ; une panne avant la première question la note en
    panne. Une question qui n'a pas de réponse arrête la conversation : le second tour d'une paire
    après un échec est l'affaire de l'orchestration (ADR-0012, T4.3).
    """
    verifier_cache(commande)
    client = ClaudeSDKClient(options(commande, consigne_et_fiche()))
    await client.connect()
    try:
        statut = await attendre_serveur(client, commande.plafonds.connexion_s)
        info = statut.get("serverInfo") if statut is not None else None
        en_tete = entete(commande, "absent" if info is None else info["version"])
        with Journal(fichier_trace(commande.traces, en_tete), en_tete) as journal:
            if statut is None:
                ident, message = commande.questions[0]
                journal.question(ident, message)
                journal.fin("panne", "serveur")
                return
            conversation = _Conversation(client, journal, commande.plafonds, tarifs, en_tete.jour)
            for ident, message in commande.questions:
                if await conversation.tour(ident, message) != "reponse":
                    break
    finally:
        await client.disconnect()


@dataclass
class _Appel:
    """Un appel du modèle, vu dans le flux : message_start, complété par message_delta."""

    modele: str
    brut: dict[str, Any]


@dataclass
class _Tour:
    """Ce qu'un tour accumule en cours de lecture."""

    # Appels d'outils notés (identifiants de Claude Code), pour apparier leurs résultats.
    outils: set[str] = field(default_factory=set)
    # Appels du modèle vus dans le flux, par identifiant de message ; ceux déjà comptés.
    appels: dict[str, _Appel] = field(default_factory=dict)
    comptes: set[str] = field(default_factory=set)
    courant: str | None = None
    reprises: int = 0
    erreur_api: str | None = None
    # Raison de l'interruption : « delai » ou « budget ».
    coupure: str | None = None


class _Conversation:
    """Une session de Claude Code, question après question : trace, usage, budget, issue."""

    def __init__(
        self,
        client: ClaudeSDKClient,
        journal: Journal,
        plafonds: Plafonds,
        tarifs: Sequence[Tarif],
        jour: date,
    ) -> None:
        self._client = client
        self._journal = journal
        self._plafonds = plafonds
        self._tarifs = tarifs
        self._jour = jour
        # model_usage cumulé de la session (D13 : usage_du_tour à chaque résultat).
        self._cumul: dict[str, Usage] = {}
        self.cout = Decimal(0)

    async def tour(self, ident: str, message: str) -> str:
        """Pose une question et en note le tour ; renvoie son issue."""
        self._journal.question(ident, message)
        echeance = asyncio.get_running_loop().time() + self._plafonds.delai_s
        tour = _Tour()
        await self._client.query(message)
        resultat = await self._lire(tour, echeance)
        self._compter_les_restes(tour)
        if resultat is not None:
            self._annexes(resultat, tour)
        issue, cause, reponse = await self._issue(resultat, tour)
        self._journal.fin(issue, cause, reponse)
        return issue

    async def _lire(self, tour: _Tour, echeance: float) -> ResultMessage | None:
        """Lit les messages jusqu'au résultat ; à l'échéance ou au budget dépassé, interrupt(),
        puis le résultat qui s'ensuit. None : Claude Code muet après interrupt()."""
        try:
            async with asyncio.timeout_at(echeance), aclosing(_messages(self._client)) as flux:
                async for message in flux:
                    if (resultat := self._noter(message, tour)) is not None:
                        return resultat
                    if tour.coupure is not None:
                        break
                else:
                    raise CelluleError("Claude Code s'est arrêté sans résultat")
        except TimeoutError:
            tour.coupure = "delai"
        await self._client.interrupt()
        try:
            async with asyncio.timeout(FIN_COUPURE_S), aclosing(_messages(self._client)) as flux:
                async for message in flux:
                    if (resultat := self._noter(message, tour)) is not None:
                        return resultat
        except TimeoutError:
            print(f"cellule {CLIENT} : aucun résultat après interrupt()", file=sys.stderr)
        return None

    def _noter(self, message: Message, tour: _Tour) -> ResultMessage | None:
        """Note un message dans la trace ; renvoie le résultat qui clôt le tour."""
        match message:
            case StreamEvent(parent_tool_use_id=None):
                self._flux(message.event, tour)
            case AssistantMessage(parent_tool_use_id=None):
                tour.erreur_api = message.error or tour.erreur_api
                for bloc in message.content:
                    if isinstance(bloc, ToolUseBlock) and bloc.name in {OUTIL, *MASQUES}:
                        self._appel_d_outil(bloc, tour)
            case UserMessage(content=list() as blocs):
                for bloc in blocs:
                    if isinstance(bloc, ToolResultBlock) and bloc.tool_use_id in tour.outils:
                        texte = _texte(bloc.content)
                        self._journal.resultat(bloc.tool_use_id, texte, bool(bloc.is_error))
            case SystemMessage(subtype="init"):
                verifier_init(message.data)
            case SystemMessage(subtype="api_retry"):
                tour.reprises += 1
                self._journal.reprise(message.data.get("error_status"))
            case ResultMessage():
                return message
        return None

    def _appel_d_outil(self, bloc: ToolUseBlock, tour: _Tour) -> None:
        requete = bloc.input.get("query", "")
        parametres = bloc.input.get("params")
        if parametres is not None and not isinstance(parametres, Mapping):
            parametres = {"params": parametres}
        tour.outils.add(bloc.id)
        outil = bloc.name.removeprefix(PREFIXE)
        self._journal.appel(bloc.id, outil, str(requete), parametres)

    def _flux(self, evenement: Mapping[str, Any], tour: _Tour) -> None:
        """Usage d'un appel du modèle : message_start donne l'entrée et le cache, message_delta la
        sortie ; l'appel se compte (trace, coût, budget) à son message_delta."""
        genre = evenement.get("type")
        if genre == "message_start":
            debut = evenement["message"]
            tour.courant = debut["id"]
            tour.appels[debut["id"]] = _Appel(debut["model"], dict(debut.get("usage") or {}))
        elif genre == "message_delta" and tour.courant is not None:
            appel = tour.appels[tour.courant]
            delta = evenement.get("usage") or {}
            appel.brut |= {cle: valeur for cle, valeur in delta.items() if valeur is not None}
            self._compter(tour.courant, appel, tour)
            tour.courant = None

    def _compter(self, ident: str, appel: _Appel, tour: _Tour) -> None:
        usage = usage_anthropic(appel.brut)
        brut = {"id": ident, **appel.brut} | ({"interrompu": True} if tour.coupure else {})
        self._journal.llm(appel.modele, usage, reflexion_anthropic(appel.brut), brut)
        tour.comptes.add(ident)
        self._payer(appel.modele, usage, tour)

    def _payer(self, modele: str, usage: Usage, tour: _Tour) -> None:
        """Ajoute le coût d'un usage à celui de la conversation ; au-delà du budget, le tour se
        coupe (D13)."""
        self.cout += couts({modele: usage}, self._tarifs, self._jour, ACCES)[modele]
        if tour.coupure is None and self.cout > self._plafonds.budget_usd:
            tour.coupure = "budget"

    def _compter_les_restes(self, tour: _Tour) -> None:
        """Un appel coupé sans message_delta compte pour son entrée et son cache."""
        for ident, appel in tour.appels.items():
            if ident not in tour.comptes:
                self._compter(ident, appel, tour)

    def _annexes(self, resultat: ResultMessage, tour: _Tour) -> None:
        """Tokens des autres modèles (petit modèle de Claude Code), tirés de model_usage : leur
        coût, connu en fin de tour, peut encore dépasser le budget. Puis recoupement du modèle de
        la cellule sur un tour net (ni coupure ni reprise)."""
        brut = resultat.model_usage or {}
        cumul = usage_claude_code(brut)
        par_modele = usage_du_tour(self._cumul, cumul)
        self._cumul = cumul
        for modele, usage in sorted(par_modele.items()):
            if modele != MODELE:
                self._journal.llm(modele, usage, brut={"modelUsage": dict(brut[modele])})
                self._payer(modele, usage, tour)
        if tour.coupure is None and tour.reprises == 0:
            flux = sum(
                (
                    usage_anthropic(appel.brut)
                    for appel in tour.appels.values()
                    if appel.modele == MODELE
                ),
                Usage(),
            )
            _recouper(flux, par_modele.get(MODELE, Usage()))

    async def _issue(
        self, resultat: ResultMessage | None, tour: _Tour
    ) -> tuple[str, str | None, str]:
        """Issue et cause du tour (D13), puis la réponse finale. Des crédits épuisés arrêtent la
        campagne ; un serveur perdu en cours de tour en fait une panne, quoi qu'ait fait l'agent."""
        if tour.erreur_api == CREDITS_EPUISES:
            return "arret", "plafond", ""
        if resultat is not None and not await self._serveur_connecte():
            return "panne", "serveur", ""
        if tour.coupure is not None:
            # Délai dépassé dans un tour qui a dû reprendre un appel : panne, relancée (D13).
            if tour.coupure == "delai" and tour.reprises:
                return "panne", "reprises", ""
            return "echec", tour.coupure, ""
        # _lire ne rend None qu'après une coupure.
        assert resultat is not None
        return _selon_le_resultat(resultat, tour)

    async def _serveur_connecte(self) -> bool:
        statut = _statut(await self._client.get_mcp_status())
        return statut is not None and statut["status"] == "connected"


def _selon_le_resultat(resultat: ResultMessage, tour: _Tour) -> tuple[str, str | None, str]:
    """Issue d'un tour mené à son terme par Claude Code : réponse, tours épuisés, panne de l'API,
    ou erreur technique (requête refusée, clé invalide, limite de dépense du workspace : HTTP 400
    selon la doc de l'API)."""
    if resultat.subtype == "error_max_turns":
        return "echec", "tours", ""
    if not resultat.is_error:
        return "reponse", None, resultat.result or ""
    statut = resultat.api_error_status
    if tour.erreur_api in ERREURS_DE_PANNE or (statut is not None and _panne_http(statut)):
        return "panne", "api", ""
    raise CelluleError(
        f"Claude Code en erreur ({resultat.subtype}, HTTP {statut}, {tour.erreur_api}) : "
        f"{resultat.result or resultat.errors}"
    )


def _messages(client: ClaudeSDKClient) -> AsyncGenerator[Message]:
    """Les messages d'une requête, jusqu'à son résultat ; receive_response() est un générateur,
    déclaré AsyncIterator, que aclosing referme."""
    return cast(AsyncGenerator[Message], client.receive_response())


def _statut(reponse: McpStatusResponse) -> McpServerStatus | None:
    serveurs = reponse.get("mcpServers", [])
    if autres := sorted({serveur["name"] for serveur in serveurs} - {SERVEUR}):
        raise IsolementError(f"serveurs MCP hors de la commande : {autres}")
    return next((serveur for serveur in serveurs if serveur["name"] == SERVEUR), None)


def _recouper(flux: Usage, cli: Usage) -> None:
    """Sur un tour net, le flux et model_usage comptent les mêmes tokens du modèle de la cellule
    (model_usage ne sépare pas le cache à 5 min et à 1 h)."""

    def totaux(usage: Usage) -> tuple[int, int, int, int]:
        ecrit = usage.cache_ecriture_5m + usage.cache_ecriture_1h
        return usage.entree, usage.sortie, usage.cache_lecture, ecrit

    if totaux(flux) != totaux(cli):
        raise MesureError(f"{MODELE} : le flux ({flux}) et model_usage ({cli}) divergent")


def _panne_http(statut: int) -> bool:
    """Limite de débit ou erreur du fournisseur (429, 5xx) : une panne, relancée (D13)."""
    return statut == 429 or statut >= 500


def _texte(contenu: str | list[dict[str, Any]] | None) -> str:
    """Le texte d'un résultat d'outil, tel que l'agent l'a reçu."""
    if contenu is None or isinstance(contenu, str):
        return contenu or ""
    return "".join(bloc.get("text", "") for bloc in contenu if bloc.get("type") == "text")


def _relayer(ligne: str) -> None:
    print(f"{CLIENT} : {ligne}", file=sys.stderr)


def main() -> int:
    """Lit la commande sur stdin et mène la conversation : 0, ou 2 sur une erreur technique."""
    try:
        commande = lire_commande(sys.stdin.read())
        asyncio.run(converser(commande, prix.charger()))
    except (
        CelluleError,
        CleNonUtilisee,
        MesureError,
        PrixError,
        ClaudeSDKError,
        OSError,
    ) as erreur:
        print(f"cellule {CLIENT} : {erreur}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
