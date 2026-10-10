"""Essai du lanceur sur la vraie base (spec 002, T7.4 ; plan D1, D3 et D13) : banc essai-serveur.

Le harnais lance scripts/mcp-neo4j.sh comme une cellule le lance (liste blanche de D3, dossier vide
hors du dépôt) et lui parle en MCP, sans aucun modèle (0 $) :

1. le serveur : neo4j-mcp v1.6.0, sans les instructions que le lanceur retire (T4.1) ;
2. ses outils : read-cypher et get-schema, jamais write-cypher (NEO4J_MCP_READ_ONLY ignoré : circuit
   breaker du plan, aucune mesure) ; vus d'une cellule ADK, read-cypher seul. Claude Code masque
   les mêmes noms, vérifié sur le vrai binaire (tests/test_cellule_sdk_reel.py), et sa cellule
   contrôle la liste de ses outils au début de chaque requête ;
3. une lecture répond, et l'identifiant de l'instance reste masqué (T3.1) ;
4. des écritures sont refusées par read-cypher, et aucun nœud témoin n'est écrit ;
5. une lecture lente est arrêtée côté Aura par scripts/transactions.sh (D13) : serveur vivant,
   d'abord, et read-cypher reçoit alors l'erreur d'arrêt ; puis serveur tué, comme le harnais tue
   une cellule abandonnée, après quoi aucune lecture d'agent ne reste. La lecture lente est un
   produit cartésien étalonné sur la base : si rien ne l'arrêtait, elle finirait seule en quelques
   minutes.

Environnement : celui de la cellule adk-gemini (aucune clé Anthropic : l'essai n'appelle aucun
modèle) ; le lanceur retire lui-même les variables Vertex. Rien n'est écrit dans la base : les
écritures tentées sont refusées avant d'être exécutées (EXPLAIN de read-cypher), et arrêter une
transaction ne touche pas au graphe.

Codes retour : 0 conforme · 1 écart · 2 erreur technique.
"""

import asyncio
import contextlib
import json
import math
import os
import re
import signal
import sys
import tempfile
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TextIO

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
from mcp.shared.exceptions import MCPError

from banc import orchestration
from banc.cellule import LANCEUR
from banc.isolement import environnement_agent
from banc.notation import LECTURE
from banc.orchestration import OrchestrationError

VERSION = "v1.6.0"
OUTILS_DU_SERVEUR = ("get-schema", "read-cypher")
LECTURE_SIMPLE = "MATCH (t:Type) RETURN count(t) AS types"
TYPES = 18
# Le nom de la base est l'identifiant de l'instance : le lanceur le remplace par MASQUE.
IDENTITE = "CALL db.info() YIELD name RETURN name"
MASQUE = "‹instance›"
TEMOIN = "EssaiEcriture"
ECRITURES = (
    ("CREATE", f"CREATE (:{TEMOIN}) RETURN 1 AS cree"),
    ("CREATE dans un CALL", f"CALL () {{ CREATE (:{TEMOIN}) }} RETURN 1 AS cree"),
    (
        "procédure APOC d'écriture",
        f"CALL apoc.create.node(['{TEMOIN}'], {{}}) YIELD node RETURN 1 AS cree",
    ),
)
REFUS = "read-cypher can only run read-only Cypher statements"
TEMOINS = f"MATCH (n:{TEMOIN}) RETURN count(n) AS temoins"
# Six ensembles de types : 18^6 lignes, qu'aucun index ne raccourcit (le filtre porte sur les six
# nœuds à la fois et n'est jamais vrai). La lecture lente répète ce produit autant de fois qu'il
# faut pour durer Moyens.cible_s d'après l'étalon.
PRODUIT = "MATCH (a:Type), (b:Type), (c:Type), (d:Type), (e:Type), (f:Type)"
SOMME = "a.id + b.id + c.id + d.id + e.id + f.id"
LIGNES_ETALON = TYPES**6
ETALON = f"{PRODUIT} WHERE {SOMME} < 0 RETURN count(*) AS lignes"
LENTE = (
    f"UNWIND range(1, $repetitions) AS tour {PRODUIT} WHERE {SOMME} + tour < 0 "
    "RETURN count(*) AS lignes"
)
REPETITIONS_MAX = 2000
# Neo4j : « The transaction has been terminated… ».
ARRET = "terminated"
ARRETEES = re.compile(r"(\d+) lecture\(s\) d'agent arrêtée\(s\)")


class EssaiError(Exception):
    """L'essai ne peut pas conclure : serveur injoignable, réponse illisible, étalon en échec."""


@dataclass(frozen=True)
class Moyens:
    """Ce que l'essai lance : le vrai lanceur et le vrai transactions.sh, ou des faux (tests)."""

    serveur: tuple[str, ...] = (str(LANCEUR),)
    # scripts/transactions.sh, lancé sans clé Anthropic ; rend son compte rendu, lève
    # OrchestrationError s'il échoue.
    nettoyer: Callable[[], str] = orchestration.transactions
    # Dossiers de gcloud et de neo4j-mcp, placés dans le PATH des agents.
    chemins: Callable[[], tuple[Path, ...]] = orchestration.outils_des_agents
    connexion_s: float = 30.0
    # Attente après l'envoi de la lecture lente : elle tourne alors sur Aura.
    demarrage_s: float = 5.0
    # Durée visée de la lecture lente si rien ne l'arrêtait.
    cible_s: float = 180.0
    # Attente de la réponse de read-cypher après l'arrêt de sa lecture.
    reponse_s: float = 60.0
    ecrire: Callable[[str], None] = print


@dataclass
class Bilan:
    """Les contrôles de l'essai et leurs écarts, écrits au fil de l'eau."""

    ecrire: Callable[[str], None]
    controles: int = 0
    ecarts: int = 0

    def juger(self, libelle: str, conforme: bool, obtenu: str) -> bool:
        self.controles += 1
        if not conforme:
            self.ecarts += 1
        self.ecrire(f"{'✓' if conforme else '✗'} {libelle} : {obtenu}")
        return conforme

    def informer(self, libelle: str, texte: str) -> None:
        self.ecrire(f"  · {libelle} : {texte}")


ERREURS_TECHNIQUES = (EssaiError, OrchestrationError, MCPError, OSError, TimeoutError)


def commande(moyens: Moyens | None = None) -> int:
    """banc essai-serveur : 0 conforme, 1 écart, 2 erreur technique."""
    try:
        return asyncio.run(essai(moyens or Moyens()))
    except ERREURS_TECHNIQUES as erreur:
        print(f"banc essai-serveur : {erreur}", file=sys.stderr)
        return 2
    except BaseExceptionGroup as groupe:
        # Le client MCP (anyio) regroupe les erreurs de ses tâches : seules les erreurs techniques
        # attendues donnent le code 2, toute autre remonte telle quelle.
        reste = groupe.split(ERREURS_TECHNIQUES)[1]
        if reste is not None:
            raise
        for feuille in _feuilles(groupe):
            print(f"banc essai-serveur : {feuille}", file=sys.stderr)
        return 2


def _feuilles(groupe: BaseExceptionGroup[BaseException]) -> list[BaseException]:
    return [
        feuille
        for erreur in groupe.exceptions
        for feuille in (_feuilles(erreur) if isinstance(erreur, BaseExceptionGroup) else [erreur])
    ]


async def essai(moyens: Moyens) -> int:
    """Mène l'essai dans un dossier temporaire hors du dépôt, détruit ensuite."""
    bilan = Bilan(moyens.ecrire)
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
            try:
                await _essai(bilan, moyens, parametres, journal)
            finally:
                journal.flush()
                _signaler_le_journal(racine / "serveur.log", bilan)
    if bilan.ecarts:
        moyens.ecrire(f"ÉCART : {bilan.ecarts} contrôle(s) sur {bilan.controles}.")
        return 1
    moyens.ecrire(f"CONFORME : {bilan.controles} contrôles.")
    return 0


async def _essai(
    bilan: Bilan, moyens: Moyens, parametres: StdioServerParameters, journal: TextIO
) -> None:
    bilan.informer("départ", await asyncio.to_thread(moyens.nettoyer) or "rien à arrêter")
    async with serveur(parametres, journal, moyens.connexion_s) as (session, initiale):
        verifier_serveur(bilan, initiale)
        await verifier_outils(bilan, session)
        await verifier_lecture(bilan, session)
        await verifier_ecritures(bilan, session)
        repetitions = await etalonner(bilan, session, moyens.cible_s)
        await lecture_arretee(bilan, session, moyens, repetitions)
    await vue_adk(bilan, parametres, moyens.connexion_s)
    await cellule_tuee(bilan, parametres, journal, moyens, repetitions)


@contextlib.asynccontextmanager
async def serveur(
    parametres: StdioServerParameters, journal: TextIO, delai_s: float
) -> AsyncIterator[tuple[ClientSession, types.InitializeResult]]:
    """Le serveur lancé comme par une cellule, connecté ; sa sortie d'erreur va dans le journal."""
    async with (
        stdio_client(parametres, errlog=journal) as (lecture, ecriture),
        ClientSession(lecture, ecriture) as session,
    ):
        async with asyncio.timeout(delai_s):
            initiale = await session.initialize()
        yield session, initiale


async def lire(
    session: ClientSession, requete: str, parametres: dict[str, Any] | None = None
) -> tuple[str, bool]:
    """Un appel de read-cypher : le texte de sa réponse, et vrai si c'est une erreur."""
    arguments: dict[str, Any] = {"query": requete}
    if parametres:
        arguments["params"] = parametres
    resultat = await session.call_tool(LECTURE, arguments)
    if not isinstance(resultat, types.CallToolResult):
        raise EssaiError(f"réponse inattendue de read-cypher : {type(resultat).__name__}")
    texte = "".join(bloc.text for bloc in resultat.content if isinstance(bloc, types.TextContent))
    return texte, bool(resultat.is_error)


def valeur(texte: str, colonne: str) -> Any:
    """La colonne du seul enregistrement d'une réponse de read-cypher (un tableau JSON), sinon
    None."""
    try:
        enregistrements = json.loads(texte)
    except json.JSONDecodeError:
        return None
    if not (isinstance(enregistrements, list) and len(enregistrements) == 1):
        return None
    enregistrement = enregistrements[0]
    return enregistrement.get(colonne) if isinstance(enregistrement, dict) else None


def extrait(texte: str) -> str:
    """Le début d'une réponse, sur une ligne, pour un compte rendu."""
    ligne = " ".join(texte.split())
    return ligne if len(ligne) <= 160 else ligne[:159] + "…"


def verifier_serveur(bilan: Bilan, initiale: types.InitializeResult) -> None:
    info = initiale.server_info
    bilan.juger(
        "serveur",
        info.name == "neo4j-mcp" and info.version == VERSION,
        f"{info.name} {info.version}",
    )
    bilan.juger(
        "instructions du serveur retirées par le lanceur",
        initiale.instructions is None,
        "aucune" if initiale.instructions is None else "présentes",
    )


async def verifier_outils(bilan: Bilan, session: ClientSession) -> None:
    noms = sorted(outil.name for outil in (await session.list_tools()).tools)
    detail = ", ".join(noms)
    if "write-cypher" in noms:
        detail += (
            " : écriture ouverte, NEO4J_MCP_READ_ONLY ignoré (circuit breaker : aucune mesure)"
        )
    bilan.juger("outils du serveur, en lecture seule", noms == sorted(OUTILS_DU_SERVEUR), detail)


async def verifier_lecture(bilan: Bilan, session: ClientSession) -> None:
    texte, en_erreur = await lire(session, LECTURE_SIMPLE)
    types_lus = None if en_erreur else valeur(texte, "types")
    bilan.juger(
        "read-cypher répond",
        types_lus == TYPES,
        f"{types_lus} types" if types_lus is not None else extrait(texte),
    )
    texte, en_erreur = await lire(session, IDENTITE)
    nom = None if en_erreur else valeur(texte, "name")
    # Jamais l'identifiant lui-même dans le compte rendu.
    bilan.juger(
        "identifiant de l'instance masqué",
        nom == MASQUE,
        MASQUE if nom == MASQUE else ("non masqué" if nom is not None else extrait(texte)),
    )


async def verifier_ecritures(bilan: Bilan, session: ClientSession) -> None:
    for libelle, requete in ECRITURES:
        texte, en_erreur = await lire(session, requete)
        if en_erreur and REFUS in texte:
            obtenu = "refusée par read-cypher"
        elif en_erreur:
            obtenu = f"autre erreur : {extrait(texte)}"
        else:
            obtenu = "ACCEPTÉE : écriture ouverte (circuit breaker : aucune mesure)"
        bilan.juger(f"écriture refusée, {libelle}", en_erreur and REFUS in texte, obtenu)
    texte, en_erreur = await lire(session, TEMOINS)
    temoins = None if en_erreur else valeur(texte, "temoins")
    bilan.juger(
        f"nœuds {TEMOIN} dans la base",
        temoins == 0,
        str(temoins) if temoins is not None else extrait(texte),
    )


async def etalonner(bilan: Bilan, session: ClientSession, cible_s: float) -> int:
    """Durée du produit sur la base, et le nombre de répétitions pour que la lecture lente dure
    cible_s : assez pour être arrêtée, bornée si l'arrêt échoue."""
    debut = time.monotonic()
    texte, en_erreur = await lire(session, ETALON)
    duree = time.monotonic() - debut
    if en_erreur or valeur(texte, "lignes") != 0:
        raise EssaiError(f"étalon de la lecture lente en échec : {extrait(texte)}")
    repetitions = min(REPETITIONS_MAX, max(1, math.ceil(cible_s / max(duree, 1e-3))))
    lignes = f"{LIGNES_ETALON:,}".replace(",", " ")
    bilan.informer(
        "étalon", f"{lignes} lignes en {duree:.1f} s ; lecture lente : {repetitions} fois plus"
    )
    return repetitions


def lectures_arretees(compte_rendu: str) -> int:
    """Le nombre de lectures que transactions.sh dit avoir arrêtées (0 s'il n'y en avait aucune)."""
    trouve = ARRETEES.search(compte_rendu)
    return int(trouve.group(1)) if trouve else 0


async def lecture_arretee(
    bilan: Bilan, session: ClientSession, moyens: Moyens, repetitions: int
) -> None:
    """Serveur vivant : transactions.sh arrête la lecture sur Aura, read-cypher reçoit l'erreur."""
    libelle = "lecture lente arrêtée par transactions.sh, serveur vivant"
    appel = asyncio.create_task(lire(session, LENTE, {"repetitions": repetitions}))
    await asyncio.sleep(moyens.demarrage_s)
    if appel.done():
        texte, _ = appel.result()
        bilan.juger(libelle, False, f"finie avant l'arrêt, à rendre plus lente : {extrait(texte)}")
        return
    debut = time.monotonic()
    try:
        compte_rendu = await asyncio.to_thread(moyens.nettoyer)
    except OrchestrationError as erreur:
        appel.cancel()
        with contextlib.suppress(asyncio.CancelledError, MCPError):
            await appel
        bilan.juger(libelle, False, f"transactions.sh en échec : {erreur}")
        return
    arretees = lectures_arretees(compte_rendu)
    try:
        texte, en_erreur = await asyncio.wait_for(appel, moyens.reponse_s)
    except TimeoutError:
        bilan.juger(libelle, False, f"{arretees} arrêtée(s), read-cypher sans réponse")
        return
    delai = time.monotonic() - debut
    conforme = arretees == 1 and en_erreur and ARRET in texte.lower()
    bilan.juger(
        libelle,
        conforme,
        f"{arretees} arrêtée(s) ; read-cypher, {delai:.1f} s après : {extrait(texte)}",
    )


async def vue_adk(bilan: Bilan, parametres: StdioServerParameters, delai_s: float) -> None:
    """Les outils qu'une cellule ADK voit : le filtre de la cellule (read-cypher seul, D1)."""
    boite = McpToolset(
        connection_params=StdioConnectionParams(server_params=parametres, timeout=delai_s),
        tool_filter=[LECTURE],
    )
    try:
        async with asyncio.timeout(delai_s):
            outils = await boite.get_tools()
    finally:
        await boite.close()
    noms = [outil.name for outil in outils]
    bilan.juger("outils vus d'une cellule ADK", noms == [LECTURE], ", ".join(noms) or "aucun")


def groupes_serveurs() -> set[int]:
    """Les groupes des processus issus de l'essai : le serveur vit dans sa propre session."""
    return {groupe for _pid, groupe in orchestration.descendants(os.getpid())} - {os.getpgid(0)}


async def cellule_tuee(
    bilan: Bilan,
    parametres: StdioServerParameters,
    journal: TextIO,
    moyens: Moyens,
    repetitions: int,
) -> None:
    """Le cas du harnais : la cellule abandonnée est tuée, son serveur avec elle, puis
    transactions.sh passe ; aucune lecture d'agent ne doit rester sur Aura."""
    libelle = "serveur tué pendant une lecture lente, puis transactions.sh"
    avant = groupes_serveurs()
    async with serveur(parametres, journal, moyens.connexion_s) as (session, _initiale):
        groupes = groupes_serveurs() - avant
        if len(groupes) != 1:
            raise EssaiError(f"groupe du serveur introuvable : {sorted(groupes)}")
        appel = asyncio.create_task(lire(session, LENTE, {"repetitions": repetitions}))
        await asyncio.sleep(moyens.demarrage_s)
        en_cours = not appel.done()
        for groupe in groupes:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(groupe, signal.SIGKILL)
        appel.cancel()
        with contextlib.suppress(asyncio.CancelledError, MCPError):
            await appel
    if not en_cours:
        bilan.juger(
            libelle, False, "lecture finie avant que le serveur soit tué, à rendre plus lente"
        )
        return
    try:
        compte_rendu = await asyncio.to_thread(moyens.nettoyer)
    except OrchestrationError as erreur:
        bilan.juger(libelle, False, f"transactions.sh en échec : {erreur}")
        return
    arretees = lectures_arretees(compte_rendu)
    qui = "transactions.sh l'a arrêtée, Aura la gardait" if arretees else "Aura l'avait arrêtée"
    bilan.juger(libelle, True, f"plus aucune lecture d'agent ({qui})")


def _signaler_le_journal(chemin: Path, bilan: Bilan) -> None:
    """Après un écart, la fin du journal des serveurs (stderr de neo4j-mcp, déjà filtré par le
    lanceur), pour comprendre sans relancer."""
    if not bilan.ecarts:
        return
    lignes = chemin.read_text(encoding="utf-8", errors="replace").splitlines()
    for ligne in lignes[-15:]:
        print(f"  serveur : {ligne}", file=sys.stderr)
