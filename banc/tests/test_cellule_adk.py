"""Cellules ADK (T4.2) : le vrai ADK 2.11.0, contre une fausse API (l'API Anthropic en flux, Vertex
en flux, et le jeton d'une ADC factice : tests/fixtures/fausse_api_adk.py) et un faux serveur MCP
(tests/fixtures/faux_serveur_mcp.py). Aucun appel réel, aucun coût : le client mesuré tourne tel
quel, seule l'adresse de l'API change (leçon du 2026-10-09).

DoD : faux serveur MCP, faux LLM. Puis : ce que le modèle reçoit, le chrono après la connexion, la
mesure (tokens par appel, coût, budget), les issues d'un tour (D13), la paire Q2 puis Q18,
l'isolement jusqu'au serveur, le vrai lanceur, l'arrêt du serveur par son propre groupe.
"""

import asyncio
import io
import json
import os
import signal
import socket
import subprocess
import sys
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import google.auth.exceptions
import httpx2
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.adk.runners import Runner
from google.genai import types

from banc import cellule_adk, prix
from banc.cellule import (
    LANCEUR,
    CelluleError,
    Commande,
    IsolementError,
    Plafonds,
    commande_json,
    consigne_et_fiche,
)
from banc.cellule_adk import ACCES, MODELES, converser
from banc.isolement import CleAbsente, environnement_agent
from banc.mesures import Conversation, MesureError, lire
from banc.prix import Usage

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLE = "sk-ant-api03-cle-factice-du-banc"
CLAUDE, GEMINI = "adk-claude", "adk-gemini"
CLIENTS = (CLAUDE, GEMINI)
REQUETE = "MATCH (n) RETURN count(n) AS n"
RESULTAT = '[\n  {\n    "n": 42\n  }\n]'
REPONSE = f"Réponse : 42\n\nSources : {REQUETE}"
Q1 = ("Q1", "Combien de nœuds ?")
Q2 = ("Q2", "Mon équipe : Pikachu.\n\nQui remplacer ?")
Q18 = ("Q18", "Et si je garde Pikachu ?")
# Un tour type : une lecture du graphe (cache écrit), puis la réponse (cache lu). La sortie
# comprend la réflexion.
APPEL_1 = {"entree": 900, "sortie": 40, "ecrit": 3000, "reflexion": 12}
APPEL_2 = {"entree": 100, "sortie": 30, "lu": 3000, "reflexion": 5}
INSTANCE = "f4c7e9a2"
SECRET = (
    f"NEO4J_URI=neo4j+s://{INSTANCE}.databases.neo4j.io\nNEO4J_USERNAME={INSTANCE}\n"
    f"NEO4J_PASSWORD=mdp-factice-du-banc\nNEO4J_DATABASE={INSTANCE}\n"
)


# --- Scénarios de la fausse API -------------------------------------------------------------------


def lecture(requete: str = REQUETE, params: Any = None, **usage: Any) -> dict[str, Any]:
    """Un appel du modèle qui lit le graphe."""
    arguments = {"query": requete} | ({} if params is None else {"params": params})
    blocs = [["reflexion", "Je cherche."], ["texte", "Je lis le graphe."], ["outil", arguments]]
    return {"blocs": blocs, "usage": usage or APPEL_1}


def reponse(texte: str = REPONSE, **usage: Any) -> dict[str, Any]:
    """Un appel du modèle qui répond."""
    return {"blocs": [["reflexion", "Je conclus."], ["texte", texte]], "usage": usage or APPEL_2}


def erreur(statut: int, genre: str = "api_error", message: str = "?") -> dict[str, Any]:
    return {"statut": statut, "type": genre, "message": message}


TOUR_TYPE = [lecture(), reponse()]


def usage_attendu(client: str, *appels: dict[str, int]) -> Usage:
    """Tokens d'appels du modèle, tels que la cellule les compte : Vertex n'écrit pas en cache."""
    total = Usage()
    for appel in appels:
        ecrit = appel.get("ecrit", 0) if client == CLAUDE else 0
        total += Usage(
            entree=appel.get("entree", 0),
            sortie=appel.get("sortie", 0),
            cache_ecriture_5m=ecrit,
            cache_lecture=appel.get("lu", 0),
        )
    return total


# --- Bac à sable ---------------------------------------------------------------------------------


@pytest.fixture(scope="module")
def cle_adc() -> str:
    """Clé privée d'un compte de service factice : l'ADC de Vertex, signée puis échangée contre un
    jeton auprès de la fausse API (token_uri)."""
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = cle.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pem.decode()


@dataclass
class Bac:
    """Dossiers de l'agent, faux serveur MCP, fausse API ; de quoi lire ce qui s'est passé."""

    racine: Path
    monkeypatch: pytest.MonkeyPatch
    cle_adc: str

    @property
    def journal(self) -> Path:
        return self.racine / "journal"

    def commande(
        self, *questions: tuple[str, str], mcp: dict[str, Any] | None = None, **reglages: Any
    ) -> Commande:
        """La commande d'une conversation, servie par le faux serveur MCP et son scénario."""
        (self.journal / "mcp.json").write_text(json.dumps(mcp or {}))
        faux = (
            sys.executable,
            "-I",
            str(FIXTURES / "faux_serveur_mcp.py"),
            str(self.journal / "mcp.json"),
            str(self.journal / "mcp.jsonl"),
        )
        serveur = reglages.pop("serveur", faux)
        cache_1h = reglages.pop("cache_1h", False)
        return Commande(
            campagne="essai",
            passe=1,
            essai=1,
            questions=questions or (Q1,),
            traces=self.racine / "traces",
            plafonds=Plafonds(**reglages),
            cache_1h=cache_1h,
            serveur=serveur,
        )

    @contextmanager
    def api(self, client: str, etapes: list[dict[str, Any]], **reglages: Any) -> Iterator[str]:
        """Lance la fausse API et l'annonce au client par son adresse ; rend cette adresse.
        reglages : clés du scénario (jeton_s, jeton_refuse)."""
        scenario = self.journal / "api.json"
        scenario.write_text(json.dumps({"etapes": etapes} | reglages))
        processus = subprocess.Popen(
            [
                sys.executable,
                "-I",
                str(FIXTURES / "fausse_api_adk.py"),
                str(scenario),
                str(self.journal / "api.jsonl"),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert processus.stdout is not None
            adresse = f"http://127.0.0.1:{processus.stdout.readline().strip()}"
            adc = {
                "type": "service_account",
                "project_id": "jleroy-labo",
                "private_key_id": "cle-factice",
                "private_key": self.cle_adc,
                "client_email": "banc@jleroy-labo.iam.gserviceaccount.com",
                "client_id": "1",
                "token_uri": f"{adresse}/token",
            }
            fichier_adc = self.racine / "gcloud" / "application_default_credentials.json"
            fichier_adc.write_text(json.dumps(adc))
            self.monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(fichier_adc))
            self.monkeypatch.setenv("ANTHROPIC_BASE_URL", adresse)
            self.monkeypatch.setenv("GOOGLE_VERTEX_BASE_URL", adresse)
            if client == CLAUDE:
                self.monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)
            else:
                self.monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
            yield adresse
        finally:
            processus.terminate()
            processus.wait()

    def converser(
        self,
        client: str,
        etapes: list[dict[str, Any]],
        commande: Commande | None = None,
        **reglages: Any,
    ) -> Conversation:
        """Mène la conversation dans ce processus (couverture), et relit sa trace."""
        commande = commande or self.commande()
        with self.api(client, etapes, **reglages):
            asyncio.run(converser(client, commande, prix.charger()))
        return self.trace()

    def trace(self) -> Conversation:
        (fichier,) = (self.racine / "traces").rglob("*.jsonl")
        return lire(fichier)

    def events(self, genre: str) -> list[dict[str, Any]]:
        """Les événements bruts d'un type, dans la trace de la conversation."""
        (fichier,) = (self.racine / "traces").rglob("*.jsonl")
        evenements = [json.loads(ligne) for ligne in fichier.read_text().splitlines()]
        return [evenement for evenement in evenements if evenement["type"] == genre]

    def requetes(self) -> list[dict[str, Any]]:
        """Les requêtes du modèle reçues par la fausse API (le jeton de l'ADC à part)."""
        fichier = self.journal / "api.jsonl"
        lignes = fichier.read_text().splitlines() if fichier.exists() else []
        notes = [json.loads(ligne) for ligne in lignes]
        return [note for note in notes if not note["chemin"].startswith("/token")]

    def notes_mcp(self, genre: str | None = None) -> list[dict[str, Any]]:
        """Ce que le faux serveur MCP a noté, tous lancements confondus."""
        fichier = self.journal / "mcp.jsonl"
        lignes = fichier.read_text().splitlines() if fichier.exists() else []
        notes = [json.loads(ligne) for ligne in lignes]
        return [note for note in notes if genre is None or genre in note]

    def methodes_mcp(self) -> list[str]:
        return [note["recu"].get("method") for note in self.notes_mcp("recu")]


@pytest.fixture
def bac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cle_adc: str) -> Bac:
    for dossier in ("home", "claude", "gcloud", "outils", "journal", "travail", "traces"):
        (tmp_path / dossier).mkdir()
    # Rien du poste ne doit choisir l'accès des clients à la place de la cellule.
    for nom in ("ANTHROPIC_AUTH_TOKEN", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path / "gcloud"))
    # Reprises de Gemini sans attente : seul leur nombre compte ici (celui de la cellule).
    rapides = {"initial_delay": 0.01, "max_delay": 0.02}
    reprises = cellule_adk.REPRISES_GEMINI.model_copy(update=rapides)
    monkeypatch.setattr(cellule_adk, "REPRISES_GEMINI", reprises)
    monkeypatch.chdir(tmp_path / "travail")
    return Bac(tmp_path, monkeypatch, cle_adc)


def vivant(pid: int) -> bool:
    """Le processus existe et n'est pas un zombie."""
    try:
        etat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except FileNotFoundError:
        return False
    return etat != "Z"


def attendre(condition: Any, delai_s: float = 10.0) -> None:
    fin = time.monotonic() + delai_s
    while not condition():
        assert time.monotonic() < fin, "condition jamais remplie"
        time.sleep(0.05)


# --- DoD : isolement, chrono ---------------------------------------------------------------------


@pytest.mark.parametrize("client", CLIENTS)
def test_aucune_variable_hors_liste_blanche(bac: Bac, client: str) -> None:
    # La cellule lancée comme l'orchestration la lance : la liste blanche pour seul environnement.
    # Le serveur MCP la reçoit telle quelle (ni plus, ni moins), sans rien du processus des tests.
    commande = bac.commande(mcp={"noter_env": True})
    with bac.api(client, TOUR_TYPE) as adresse:
        env = environnement_agent(client, bac.racine / "home", bac.racine / "claude")
        env |= {"ANTHROPIC_BASE_URL" if client == CLAUDE else "GOOGLE_VERTEX_BASE_URL": adresse}
        fini = subprocess.run(
            [sys.executable, "-m", "banc.cellule_adk", client],
            input=commande_json(commande),
            cwd=bac.racine / "travail",
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    assert fini.returncode == 0, fini.stderr
    (demarrage,) = bac.notes_mcp("env")
    assert demarrage["env"] == env
    assert ("ANTHROPIC_API_KEY" in env) == (client == CLAUDE)
    (tour,) = bac.trace().tours
    assert tour.issue == "reponse"


@pytest.mark.parametrize("client", CLIENTS)
def test_chrono_apres_la_connexion(bac: Bac, client: str) -> None:
    # Le serveur met 2 s à se connecter : la question part après, et son temps ne le compte pas.
    commande = bac.commande(mcp={"attente_s": 2.0})
    (tour,) = bac.converser(client, TOUR_TYPE, commande).tours
    listes = [note["t"] for note in bac.notes_mcp("repondu") if note["repondu"] == "tools/list"]
    assert tour.issue == "reponse"
    assert tour.duree_s is not None and tour.duree_s < 2.0
    # Horloge monotone du système : comparable d'un processus à l'autre.
    assert min(r["t"] for r in bac.requetes()) > listes[0]


@pytest.mark.parametrize("client", CLIENTS)
def test_une_seule_lecture_des_outils(bac: Bac, client: str) -> None:
    # ADK relirait la liste à chaque appel du modèle, dans le chrono : lue une fois, avant.
    bac.converser(client, [lecture(), lecture(), reponse(), reponse()], bac.commande(Q2, Q18))
    assert bac.methodes_mcp().count("tools/list") == 1
    assert bac.methodes_mcp().count("tools/call") == 2


# --- Ce que le modèle reçoit ---------------------------------------------------------------------


def test_requete_de_claude(bac: Bac) -> None:
    bac.converser(CLAUDE, TOUR_TYPE)
    requetes = bac.requetes()
    assert len(requetes) == 2
    for requete in requetes:
        corps = requete["corps"]
        assert requete["chemin"].startswith("/v1/messages")
        assert corps["model"] == MODELES[CLAUDE]
        # Plafond de Claude Code (relevé), effort high, réflexion adaptative, en flux (D2).
        assert corps["max_tokens"] == 128_000
        assert corps["output_config"] == {"effort": "high"}
        assert corps["thinking"] == {"type": "adaptive", "display": "summarized"}
        assert corps["stream"] is True
        assert [outil["name"] for outil in corps["tools"]] == ["read-cypher"]
        (systeme,) = corps["system"]
        # Consigne et fiche telles quelles, accolades comprises ({rang}), cache à 5 min (D10).
        assert systeme["text"].startswith(consigne_et_fiche())
        assert "{rang}" in systeme["text"]
        assert systeme["cache_control"] == {"type": "ephemeral"}
        assert "get-schema" not in json.dumps(corps)


def test_requete_de_gemini(bac: Bac) -> None:
    bac.converser(GEMINI, TOUR_TYPE)
    requetes = bac.requetes()
    assert len(requetes) == 2
    modele = "/projects/jleroy-labo/locations/eu/publishers/google/models/gemini-3.8-flash"
    for requete in requetes:
        corps = requete["corps"]
        assert f"{modele}:streamGenerateContent" in requete["chemin"]
        assert corps["generationConfig"] == {"thinkingConfig": {"thinking_level": "HIGH"}}
        (declarations,) = corps["tools"]
        noms = [outil["name"] for outil in declarations["functionDeclarations"]]
        assert noms == ["read-cypher"]
        (partie,) = corps["systemInstruction"]["parts"]
        assert partie["text"].startswith(consigne_et_fiche())
        assert "get-schema" not in json.dumps(corps)
        # Rien de stocké en cache (cache implicite de Vertex) : aucun cachedContent.
        assert "cachedContent" not in json.dumps(corps)
    assert all("cachedContents" not in requete["chemin"] for requete in requetes)


def test_cache_d_une_heure(bac: Bac) -> None:
    trace = bac.converser(CLAUDE, TOUR_TYPE, bac.commande(cache_1h=True))
    for requete in bac.requetes():
        (systeme,) = requete["corps"]["system"]
        assert systeme["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    (tour,) = trace.tours
    usage = tour.usages[MODELES[CLAUDE]]
    assert (usage.cache_ecriture_1h, usage.cache_ecriture_5m) == (3000, 0)


# --- Un tour mesuré ------------------------------------------------------------------------------


@pytest.mark.parametrize("client", CLIENTS)
def test_tour_note(bac: Bac, client: str) -> None:
    trace = bac.converser(client, [lecture(params={"limite": 3}), reponse()])
    (tour,) = trace.tours
    assert (tour.issue, tour.cause, tour.reponse) == ("reponse", None, REPONSE)
    (appel,) = tour.appels
    assert (appel.outil, appel.requete, appel.parametres) == ("read-cypher", REQUETE, {"limite": 3})
    assert (appel.resultat, appel.erreur) == (RESULTAT, False)
    # Un appel du modèle, un compte : les morceaux partiels de Gemini portent aussi l'usage.
    assert tour.usages == {MODELES[client]: usage_attendu(client, APPEL_1, APPEL_2)}
    assert tour.reflexion == {MODELES[client]: 17}
    appels = bac.events("llm")
    assert [appel["brut"]["model_version"] for appel in appels] == [MODELES[client]] * 2
    entete = trace.entete
    assert (entete.cellule, entete.modele, entete.acces) == (client, MODELES[client], ACCES[client])
    assert (entete.effort, entete.annexes) == ("high", ())
    bibliotheque = "anthropic" if client == CLAUDE else "google-genai"
    assert set(entete.versions) == {"google-adk", "mcp", bibliotheque, "neo4j-mcp"}
    assert entete.versions["neo4j-mcp"] == "v1.6.0"


@pytest.mark.parametrize("client", CLIENTS)
def test_resultat_d_outil_en_erreur(bac: Bac, client: str) -> None:
    # Une écriture refusée par read-cypher (D1) reste visible dans la trace.
    refus = "read-cypher can only run read-only Cypher statements"
    commande = bac.commande(mcp={"appels": [{"texte": refus, "erreur": True}]})
    (tour,) = bac.converser(client, [lecture("CREATE (n)"), reponse()], commande).tours
    (appel,) = tour.appels
    assert (appel.requete, appel.resultat, appel.erreur) == ("CREATE (n)", refus, True)
    assert tour.issue == "reponse"


def test_invite_d_outil_de_gemini(bac: Bac) -> None:
    # Des tokens d'invite d'outil (tool_use_prompt_token_count) : tarif non relevé, la mesure
    # s'arrête plutôt que de les oublier.
    with pytest.raises(MesureError, match="invite d'outil"):
        bac.converser(GEMINI, [reponse(entree=100, sortie=30, outil=7)])


def test_reponse_sans_usage(bac: Bac) -> None:
    # Un appel du modèle sans usage coûterait 0 en silence : la mesure s'arrête.
    with pytest.raises(MesureError, match="sans usage"):
        bac.converser(GEMINI, [reponse() | {"sans_usage": True}])


@pytest.mark.parametrize("fin", ["MALFORMED_FUNCTION_CALL", "STOP"])
def test_appel_de_gemini_sans_contenu(bac: Bac, fin: str) -> None:
    # Gemini rend un appel sans aucune part (appel de fonction mal formé, ou réponse vide) : ses
    # tokens se comptent quand même ; l'agent n'a rien répondu.
    vide = {"blocs": [], "fin": fin, "usage": {"entree": 5000, "sortie": 20, "reflexion": 20}}
    (tour,) = bac.converser(GEMINI, [lecture(), vide]).tours
    assert (tour.issue, tour.reponse) == ("reponse", "")
    sans_contenu = Usage(entree=5000, sortie=20)
    assert tour.usages == {MODELES[GEMINI]: usage_attendu(GEMINI, APPEL_1) + sans_contenu}
    # MALFORMED_FUNCTION_CALL : ADK rend l'événement final (sans contenu, avec son erreur) ; STOP
    # vide : il le tait ; le rappel d'ADK voit la réponse finale dans les deux cas.
    assert not [appel for appel in bac.events("llm") if appel["brut"].get("partiel")]


def test_reponse_vide_sans_contenu(bac: Bac) -> None:
    # Un candidat sans « content » du tout : ni morceau ni événement final ne sortent d'ADK, mais
    # son rappel voit la réponse finale et son usage.
    vide = {"blocs": [], "sans_contenu": True, "usage": {"entree": 5000, "sortie": 20}}
    (tour,) = bac.converser(GEMINI, [lecture(), vide]).tours
    assert (tour.issue, tour.reponse) == ("reponse", "")
    sans_contenu = Usage(entree=5000, sortie=20)
    assert tour.usages == {MODELES[GEMINI]: usage_attendu(GEMINI, APPEL_1) + sans_contenu}


@pytest.mark.parametrize("client", CLIENTS)
def test_outil_inconnu(bac: Bac, client: str) -> None:
    # Un outil que le serveur n'offre pas : ADK le refuse à l'agent, qui continue ; la trace ne note
    # que les outils de neo4j-mcp.
    inconnu = {"blocs": [["outil", {"query": "CREATE (n)"}, "write-cypher"]], "usage": APPEL_1}
    (tour,) = bac.converser(client, [inconnu, reponse()]).tours
    assert (tour.issue, tour.appels) == ("reponse", ())
    assert "tools/call" not in bac.methodes_mcp()


@pytest.mark.parametrize("client", CLIENTS)
def test_parametres_hors_dictionnaire(bac: Bac, client: str) -> None:
    (tour,) = bac.converser(client, [lecture(params=[1, 2]), reponse()]).tours
    (appel,) = tour.appels
    assert appel.parametres == {"params": [1, 2]}


def test_appel_d_outil() -> None:
    lecture_ = types.FunctionCall(id="appel-1", name="read-cypher", args={"query": REQUETE})
    assert cellule_adk.appel_d_outil(lecture_) == ("appel-1", "read-cypher", REQUETE, None)
    autre = types.FunctionCall(id="appel-2", name="write-cypher", args={"query": REQUETE})
    assert cellule_adk.appel_d_outil(autre) is None
    # Sans identifiant, son résultat ne pourrait pas lui être apparié.
    sans_identifiant = types.FunctionCall(name="read-cypher", args={"query": REQUETE})
    with pytest.raises(MesureError, match="sans identifiant"):
        cellule_adk.appel_d_outil(sans_identifiant)


@pytest.mark.parametrize("client", CLIENTS)
def test_paire_dans_la_meme_session(bac: Bac, client: str) -> None:
    etapes = [*TOUR_TYPE, reponse("Réponse : 41")]
    trace = bac.converser(client, etapes, bac.commande(Q2, Q18))
    assert [tour.issue for tour in trace.tours] == ["reponse", "reponse"]
    assert [tour.reponse for tour in trace.tours] == [REPONSE, "Réponse : 41"]
    # Q18 ne compte pas les tokens de Q2.
    assert trace.tours[1].usages == {MODELES[client]: usage_attendu(client, APPEL_2)}
    # Le second tour voit le premier : même session.
    derniere = json.dumps(bac.requetes()[-1]["corps"], ensure_ascii=False)
    assert Q2[1].split("\n")[0] in derniere
    assert "Réponse : 42" in derniere


def test_reponse_en_plusieurs_blocs(bac: Bac) -> None:
    # Deux blocs de texte dans la réponse finale : une ligne chacun, que la notation sépare.
    finale = {"blocs": [["texte", "Réponse : 42"], ["texte", "Sources : aucune"]], "usage": APPEL_2}
    (tour,) = bac.converser(CLAUDE, [finale]).tours
    assert tour.reponse == "Réponse : 42\nSources : aucune"


@pytest.mark.parametrize("client", CLIENTS)
def test_paire_arretee_apres_un_echec(bac: Bac, client: str) -> None:
    # Q2 échoue : Q18 n'est pas posée ; sa ligne relève de l'orchestration (ADR-0012, T4.3).
    commande = bac.commande(Q2, Q18, tours=1)
    trace = bac.converser(client, [lecture(), reponse()], commande)
    (tour,) = trace.tours
    assert (tour.question, tour.issue, tour.cause) == ("Q2", "echec", "tours")


def test_gemini_sans_cache_stocke(bac: Bac) -> None:
    # Gemini : le cache implicite de Vertex, aucun ContextCacheConfig (qui stockerait un cache
    # facturé à l'heure) ; Claude : un cache de prompt à la durée de la commande (D10).
    with bac.api(GEMINI, []):
        assert cellule_adk.modele(GEMINI, bac.commande())[2] is None
    with bac.api(CLAUDE, []):
        cache = cellule_adk.modele(CLAUDE, bac.commande(cache_1h=True))[2]
    assert cache is not None and cache.ttl_seconds == 3600


# --- Issues d'un tour (D13) ----------------------------------------------------------------------


@pytest.mark.parametrize("client", CLIENTS)
def test_delai_depasse(bac: Bac, client: str) -> None:
    # Le flux s'ouvre puis se tait : à l'échéance, le tour est coupé. Un appel de Claude coupé ne
    # rend aucun usage (borne basse, choix de Julien) ; de Gemini, son premier morceau donne
    # l'entrée (la fausse API n'y met que promptTokenCount).
    lent = reponse() | {"lent_s": 30}
    (tour,) = bac.converser(client, [lecture(), lent], bac.commande(delai_s=2.0)).tours
    assert (tour.issue, tour.cause) == ("echec", "delai")
    assert tour.duree_s is not None and 2.0 <= tour.duree_s < 4.0
    coupe = Usage(entree=APPEL_2["entree"] + APPEL_2["lu"]) if client == GEMINI else Usage()
    assert tour.usages == {MODELES[client]: usage_attendu(client, APPEL_1) + coupe}
    partiels = [appel for appel in bac.events("llm") if appel["brut"].get("partiel")]
    assert len(partiels) == (client == GEMINI)


@pytest.mark.parametrize("client", CLIENTS)
def test_delai_pendant_une_lecture(bac: Bac, client: str) -> None:
    # L'échéance tombe pendant une lecture du graphe : échec de l'agent (D13), la lecture en cours
    # est abandonnée côté client ; le serveur, occupé mais vivant, n'est pas une panne.
    commande = bac.commande(mcp={"appels": [{"lent_s": 30}]}, delai_s=2.0)
    (tour,) = bac.converser(client, TOUR_TYPE, commande).tours
    assert (tour.issue, tour.cause) == ("echec", "delai")
    assert tour.duree_s is not None and 2.0 <= tour.duree_s < 4.0
    (appel,) = tour.appels
    # Lecture sans résultat : notée en erreur à la relecture (banc.mesures).
    assert (appel.requete, appel.resultat, appel.erreur) == (REQUETE, "", True)
    assert len(bac.notes_mcp("pid")) == 1


@pytest.mark.parametrize("client", CLIENTS)
def test_delai_d_une_lecture_lente(bac: Bac, client: str) -> None:
    # Une lecture plus longue que le délai de connexion n'est pas coupée par le client MCP (son
    # délai borne aussi chaque appel d'outil) : seule l'échéance du tour la coupe.
    commande = bac.commande(mcp={"appels": [{"lent_s": 3}]}, delai_s=10.0, connexion_s=1.0)
    (tour,) = bac.converser(client, TOUR_TYPE, commande).tours
    assert (tour.issue, tour.reponse) == ("reponse", REPONSE)
    (appel,) = tour.appels
    assert (appel.resultat, appel.erreur) == (RESULTAT, False)


@pytest.mark.parametrize("client", CLIENTS)
def test_delai_apres_une_reprise(bac: Bac, client: str) -> None:
    # Un délai dépassé dans un tour qui a dû reprendre un appel : panne, relancée (D13).
    etapes = [erreur(429, "rate_limit_error"), reponse() | {"lent_s": 30}]
    (tour,) = bac.converser(client, etapes, bac.commande(delai_s=2.0)).tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "reprises", 1)


@pytest.mark.parametrize("client", CLIENTS)
def test_echeance_pendant_l_attente_d_une_reprise(
    bac: Bac, monkeypatch: pytest.MonkeyPatch, client: str
) -> None:
    # Le client attend 5 s avant de reprendre (retry-after d'Anthropic, attente de google-genai) ;
    # l'échéance tombe pendant cette attente : la reprise se voit déjà, c'est une panne (D13).
    lentes = cellule_adk.REPRISES_GEMINI.model_copy(update={"initial_delay": 5, "max_delay": 5})
    monkeypatch.setattr(cellule_adk, "REPRISES_GEMINI", lentes)
    etapes = [erreur(429, "rate_limit_error") | {"retry_after_s": 5}, reponse()]
    (tour,) = bac.converser(client, etapes, bac.commande(delai_s=2.0)).tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "reprises", 1)
    assert len(bac.requetes()) == 1


@pytest.mark.parametrize("client", CLIENTS)
def test_budget_depasse(bac: Bac, client: str) -> None:
    # Le premier appel coûte plus que le budget : le tour s'arrête là, sa lecture ne part pas.
    commande = bac.commande(budget_usd=Decimal("0.0001"))
    (tour,) = bac.converser(client, TOUR_TYPE, commande).tours
    assert (tour.issue, tour.cause) == ("echec", "budget")
    assert "tools/call" not in bac.methodes_mcp()
    assert len(bac.requetes()) == 1


@pytest.mark.parametrize("client", CLIENTS)
def test_budget_a_la_borne(bac: Bac, client: str) -> None:
    # Pile au budget après l'appel : pas de dépassement (strict), la réponse compte.
    tarif = prix.tarif(prix.charger(), MODELES[client], date.today(), ACCES[client])
    commande = bac.commande(budget_usd=tarif.cout(usage_attendu(client, APPEL_2)))
    (tour,) = bac.converser(client, [reponse()], commande).tours
    assert tour.issue == "reponse"


@pytest.mark.parametrize("client", CLIENTS)
def test_gros_resultat(bac: Bac, client: str) -> None:
    # Garde-fou de budget (choix de Julien) : ADK enverrait un résultat énorme en entier (Claude
    # Code le couperait à 25 000 tokens) ; le tour s'arrête avant l'appel suivant, qui coûterait
    # plus que le budget.
    enorme = json.dumps([{"description": "x" * 1000}] * 300)
    commande = bac.commande(mcp={"appels": [{"texte": enorme}]}, budget_usd=Decimal("0.05"))
    (tour,) = bac.converser(client, TOUR_TYPE, commande).tours
    assert (tour.issue, tour.cause) == ("echec", "budget")
    (appel,) = tour.appels
    assert appel.resultat == enorme
    assert len(bac.requetes()) == 1


@pytest.mark.parametrize(
    "cellule",
    [(CLAUDE, False), (CLAUDE, True), (GEMINI, False)],
    ids=["claude-5m", "claude-1h", "gemini"],
)
@pytest.mark.parametrize(
    "borne", [(Decimal(0), "reponse"), (Decimal("-1E-7"), "echec")], ids=["pile", "en-dessous"]
)
def test_garde_fou_a_la_borne(
    bac: Bac,
    monkeypatch: pytest.MonkeyPatch,
    cellule: tuple[str, bool],
    borne: tuple[Decimal, str],
) -> None:
    # Un résultat estimé à un token, au prix de l'entrée ou de l'écriture en cache à la durée de
    # la commande s'il est plus haut : budget pile égal au premier appel plus ce token, le tour
    # continue (dépassement strict) ; un dix-millionième de dollar de moins, il s'arrête.
    (client, cache_1h), (marge, issue) = cellule, borne
    monkeypatch.setattr(cellule_adk, "CARACTERES_PAR_TOKEN", 10**9)
    tarif = prix.tarif(prix.charger(), MODELES[client], date.today(), ACCES[client])
    ecriture = Usage(cache_ecriture_1h=1) if cache_1h else Usage(cache_ecriture_5m=1)
    un_token = max(tarif.cout(Usage(entree=1)), tarif.cout(ecriture))
    premier = usage_attendu(client, APPEL_1)
    if cache_1h:
        # La cellule compte l'écriture du premier appel à la durée de la commande.
        ecrit = premier.cache_ecriture_5m
        premier = Usage(premier.entree, premier.sortie, 0, ecrit, premier.cache_lecture)
    budget = tarif.cout(premier) + un_token + marge
    commande = bac.commande(budget_usd=budget, cache_1h=cache_1h)
    (tour,) = bac.converser(client, [lecture(), reponse(entree=0, sortie=0)], commande).tours
    assert tour.issue == issue
    assert len(bac.requetes()) == (2 if issue == "reponse" else 1)


def test_garde_fou_au_texte_envoye(bac: Bac) -> None:
    # ADK donne à Claude le texte du résultat, pas sa forme sérialisée : l'estimation suit ce texte
    # (30 000 caractères, 10 000 tokens écrits en cache à 5 min). Budget pile à cette borne : le
    # tour continue.
    texte = "x" * 30_000
    tarif = prix.tarif(prix.charger(), MODELES[CLAUDE], date.today(), ACCES[CLAUDE])
    premier = tarif.cout(usage_attendu(CLAUDE, APPEL_1))
    budget = premier + tarif.cout(Usage(cache_ecriture_5m=10_000))
    commande = bac.commande(mcp={"appels": [{"texte": texte}]}, budget_usd=budget)
    (tour,) = bac.converser(CLAUDE, [lecture(), reponse(entree=0, sortie=0)], commande).tours
    assert tour.issue == "reponse"


@pytest.mark.parametrize("client", CLIENTS)
def test_tours_epuises(bac: Bac, client: str) -> None:
    # Plafond d'appels du modèle par question : le 3e appel n'a pas lieu.
    commande = bac.commande(tours=2)
    (tour,) = bac.converser(client, [lecture(), lecture(), reponse()], commande).tours
    assert (tour.issue, tour.cause) == ("echec", "tours")
    assert len(bac.requetes()) == 2


@pytest.mark.parametrize("client", CLIENTS)
def test_reprise_puis_reponse(bac: Bac, client: str) -> None:
    (tour,) = bac.converser(client, [erreur(429, "rate_limit_error"), reponse()]).tours
    assert (tour.issue, tour.reprises) == ("reponse", 1)
    (reprise,) = bac.events("reprise")
    assert reprise["statut"] == 429


@pytest.mark.parametrize(
    ("client", "statuts"),
    [
        (CLAUDE, [429, 529, 503]),
        (CLAUDE, [529, 503, 429]),
        (GEMINI, [429, 503, 500]),
        (GEMINI, [503, 500, 429]),
    ],
)
def test_panne_de_l_api(bac: Bac, client: str, statuts: list[int]) -> None:
    # 429 puis 5xx sans fin : 2 reprises (comme Claude Code), puis une panne, relancée (D13).
    (tour,) = bac.converser(client, [erreur(statut) for statut in statuts]).tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "api", 2)
    assert [r["statut"] for r in bac.events("reprise")] == statuts[:2]
    assert len(bac.requetes()) == 3


def test_api_injoignable(bac: Bac) -> None:
    # Connexion refusée à chaque tentative : 2 reprises sans statut, puis une panne (D13).
    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        port = libre.getsockname()[1]
    commande = bac.commande()
    with bac.api(CLAUDE, TOUR_TYPE):
        bac.monkeypatch.setenv("ANTHROPIC_BASE_URL", f"http://127.0.0.1:{port}")
        asyncio.run(converser(CLAUDE, commande, prix.charger()))
    (tour,) = bac.trace().tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "api", 2)
    assert [r["statut"] for r in bac.events("reprise")] == [None, None]


def test_delai_d_un_autre_que_le_tour(bac: Bac, monkeypatch: pytest.MonkeyPatch) -> None:
    # Un TimeoutError qui ne vient pas de l'échéance du tour (transport) : une panne, pas un échec
    # de l'agent.
    async def expire(*_: Any, **__: Any) -> AsyncIterator[Any]:
        raise TimeoutError("lecture du transport")
        yield

    monkeypatch.setattr(Runner, "run_async", expire)
    (tour,) = bac.converser(CLAUDE, TOUR_TYPE).tours
    assert (tour.issue, tour.cause) == ("panne", "api")


def test_reponse_illisible(bac: Bac) -> None:
    # Vertex répond par un morceau qui n'est pas du JSON : une panne du fournisseur, relancée.
    (tour,) = bac.converser(GEMINI, [{"illisible": True}]).tours
    assert (tour.issue, tour.cause) == ("panne", "api")


def test_vertex_injoignable(bac: Bac, monkeypatch: pytest.MonkeyPatch) -> None:
    # Connexion refusée : google-genai la reprend une fois de lui-même (aiohttp, attente tirée au
    # hasard, ici fixée), puis une panne (D13).
    monkeypatch.setattr("google.genai._api_client.random.randint", lambda _a, _b: 0)
    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        port = libre.getsockname()[1]
    commande = bac.commande()
    with bac.api(GEMINI, TOUR_TYPE):
        bac.monkeypatch.setenv("GOOGLE_VERTEX_BASE_URL", f"http://127.0.0.1:{port}")
        asyncio.run(converser(GEMINI, commande, prix.charger()))
    (tour,) = bac.trace().tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "api", 1)


def test_erreur_dans_le_flux(bac: Bac) -> None:
    # L'API annonce une surcharge dans le flux déjà ouvert (statut 200) ; ADK n'en garde pas
    # l'origine (httpx2.ResponseNotRead) : une panne (D13).
    (tour,) = bac.converser(CLAUDE, [reponse() | {"erreur_flux": "overloaded_error"}]).tours
    assert (tour.issue, tour.cause) == ("panne", "api")


def test_flux_coupe(bac: Bac) -> None:
    # La connexion se ferme au milieu du flux : une panne (D13).
    (tour,) = bac.converser(CLAUDE, [reponse() | {"coupure": True}]).tours
    assert (tour.issue, tour.cause) == ("panne", "api")


def test_jeton_injoignable(bac: Bac) -> None:
    # Le point de jeton de l'ADC ne répond pas : une panne, avant tout appel du modèle.
    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        port = libre.getsockname()[1]
    commande = bac.commande()
    with bac.api(GEMINI, TOUR_TYPE):
        fichier = bac.racine / "gcloud" / "application_default_credentials.json"
        adc = json.loads(fichier.read_text())
        fichier.write_text(json.dumps(adc | {"token_uri": f"http://127.0.0.1:{port}/token"}))
        asyncio.run(converser(GEMINI, commande, prix.charger()))
    (tour,) = bac.trace().tours
    assert (tour.issue, tour.cause) == ("panne", "api")
    assert not bac.requetes()


def test_jeton_refuse(bac: Bac) -> None:
    # L'ADC refusée (invalid_grant) : erreur technique, qui arrête la campagne.
    with pytest.raises(CelluleError, match="ADC de Vertex refusée"):
        bac.converser(GEMINI, TOUR_TYPE, jeton_refuse=True)


def test_jeton_indisponible(bac: Bac) -> None:
    # Le point de jeton répond 503 : google-auth reprend, puis lève une erreur passagère
    # (retryable) : une panne, pas une ADC refusée.
    (tour,) = bac.converser(GEMINI, TOUR_TYPE, jeton_statut=503).tours
    assert (tour.issue, tour.cause) == ("panne", "api")
    assert not bac.requetes()


def test_jeton_hors_du_chrono(bac: Bac) -> None:
    # Le jeton de Vertex se prend avant la première question : son délai ne compte pas.
    (tour,) = bac.converser(GEMINI, TOUR_TYPE, jeton_s=1.5).tours
    assert tour.issue == "reponse"
    assert tour.duree_s is not None and tour.duree_s < 1.0


@pytest.mark.parametrize(
    ("statut", "consigne", "reprise"),
    [
        (200, None, False),
        (400, None, False),
        (404, None, False),
        (408, None, True),
        (409, None, True),
        (429, None, True),
        (500, None, True),
        (529, None, True),
        (400, "true", True),
        (503, "false", False),
        # Un succès n'est jamais repris, quoi que dise l'en-tête.
        (200, "true", False),
    ],
)
def test_reprise_anthropic(statut: int, consigne: str | None, reprise: bool) -> None:
    # La règle du SDK Anthropic 1.11.0 (_should_retry), que le middleware applique pour noter une
    # reprise dès l'échec : x-should-retry d'abord, sinon 408, 409, 429 et 5xx.
    entetes = {} if consigne is None else {"x-should-retry": consigne}
    assert cellule_adk._reprise_anthropic(httpx2.Response(statut, headers=entetes)) is reprise


def test_panne_des_identifiants() -> None:
    # En cours de tour, un point de jeton injoignable est une panne ; une ADC refusée, non.
    injoignable = google.auth.exceptions.TransportError("injoignable")  # type: ignore[no-untyped-call]
    refusee = google.auth.exceptions.RefreshError("invalid_grant")  # type: ignore[no-untyped-call]
    assert cellule_adk._panne(injoignable)
    assert not cellule_adk._panne(refusee)


@pytest.mark.parametrize(
    ("statut", "genre", "message"),
    [
        (400, "invalid_request_error", "Your credit balance is too low to access the API."),
        (402, "billing_error", "Billing issue"),
    ],
)
def test_credits_epuises(bac: Bac, statut: int, genre: str, message: str) -> None:
    # Plafond de dépense atteint : ni panne ni échec, la campagne s'arrête (D13).
    (tour,) = bac.converser(CLAUDE, [erreur(statut, genre, message)]).tours
    assert (tour.issue, tour.cause) == ("arret", "plafond")


@pytest.mark.parametrize(
    ("client", "statut", "genre"),
    [
        (CLAUDE, 400, "invalid_request_error"),
        (CLAUDE, 401, "authentication_error"),
        (GEMINI, 400, "invalid_argument"),
        (GEMINI, 403, "permission_denied"),
    ],
)
def test_refus_de_l_api(bac: Bac, client: str, statut: int, genre: str) -> None:
    # Tout autre refus : erreur technique, qui arrête la campagne.
    with pytest.raises(CelluleError, match="refus de l'API"):
        bac.converser(client, [erreur(statut, genre, "refusé")])


# --- Serveur MCP ---------------------------------------------------------------------------------


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_absent(bac: Bac, client: str) -> None:
    # Le serveur ne démarre pas : panne avant la première question, aucun appel du modèle.
    commande = bac.commande(serveur=("/bin/false",))
    trace = bac.converser(client, TOUR_TYPE, commande)
    (tour,) = trace.tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")
    assert trace.entete.versions["neo4j-mcp"] == "absent"
    assert not bac.requetes()


def converser_puis_regarder(bac: Bac, client: str, commande: Commande) -> list[int]:
    """Mène la conversation, puis rend les serveurs encore vivants avant la fin de la boucle (qui
    annulerait de toute façon les tâches restantes) : c'est la cellule qui doit les arrêter."""

    async def regarder() -> list[int]:
        await converser(client, commande, prix.charger())
        return [note["pid"] for note in bac.notes_mcp("pid") if vivant(note["pid"])]

    with bac.api(client, TOUR_TYPE):
        return asyncio.run(regarder())


def test_serveur_trop_lent(bac: Bac) -> None:
    # Connexion coupée par le délai : ADK laisse la session hors de son pool, la cellule arrête
    # quand même son serveur.
    commande = bac.commande(mcp={"attente_s": 30}, connexion_s=0.5)
    debut = time.monotonic()
    assert converser_puis_regarder(bac, CLAUDE, commande) == []
    assert time.monotonic() - debut < 10
    (tour,) = bac.trace().tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")


def test_serveur_sans_lecture(bac: Bac) -> None:
    commande = bac.commande(mcp={"outils": ["get-schema"]})
    with pytest.raises(IsolementError, match="read-cypher"):
        bac.converser(CLAUDE, TOUR_TYPE, commande)


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_perdu_pendant_une_lecture(bac: Bac, client: str) -> None:
    # Le serveur meurt en pleine lecture : ADK le relancerait au prochain appel ; panne aussitôt.
    commande = bac.commande(mcp={"appels": [{"mort": True}]})
    (tour,) = bac.converser(client, [lecture(), lecture(), reponse()], commande).tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")
    assert len(bac.requetes()) == 1


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_perdu_apres_une_lecture(bac: Bac, client: str) -> None:
    # Le serveur sort après avoir répondu ; la lecture suivante, 0,5 s plus tard, le trouve mort :
    # ADK le relance en silence et la sert, la cellule voit la session changée.
    commande = bac.commande(mcp={"appels": [{"quitter": True}]})
    etapes = [lecture(), lecture() | {"lent_s": 0.5}, reponse()]
    (tour,) = bac.converser(client, etapes, commande).tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")
    # Au moins la relance d'ADK ; le serveur relancé sort aussi, d'où parfois une autre.
    assert len(bac.notes_mcp("pid")) >= 2
    assert len(bac.requetes()) == 2


def test_taches_d_avant_epargnees(bac: Bac) -> None:
    # La cellule n'arrête que les tâches nées pendant la conversation.
    commande = bac.commande(mcp={"attente_s": 30}, connexion_s=0.5)

    async def avec_une_tache() -> bool:
        tache = asyncio.create_task(asyncio.sleep(30))
        await converser(CLAUDE, commande, prix.charger())
        annulee = tache.cancelled() or tache.cancelling() > 0
        tache.cancel()
        return annulee

    with bac.api(CLAUDE, TOUR_TYPE):
        assert asyncio.run(avec_une_tache()) is False


def test_relance_trop_lente(bac: Bac) -> None:
    # Le serveur meurt, et sa relance par ADK traîne : la vérification ne l'attend pas au-delà du
    # délai de connexion ; rien ne reste vivant après la conversation.
    mcp = {"appels": [{"mort": True}], "relance_s": 30}
    debut = time.monotonic()
    commande = bac.commande(mcp=mcp, connexion_s=1.0)
    assert converser_puis_regarder(bac, CLAUDE, commande) == []
    assert time.monotonic() - debut < 10
    (tour,) = bac.trace().tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")
    assert len(bac.notes_mcp("pid")) == 2


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_perdu_en_fin_de_tour(bac: Bac, client: str) -> None:
    # Le serveur sort 1 s après sa réponse, quand la cellule l'a déjà vu vivant ; la réponse
    # arrive après 2 s : seul le contrôle de fin de tour le voit perdu.
    commande = bac.commande(mcp={"appels": [{"quitter_apres_s": 1.0}]})
    etapes = [lecture(), reponse() | {"lent_s": 2.0}]
    (tour,) = bac.converser(client, etapes, commande).tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")
    assert len(bac.requetes()) == 2


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_arrete_par_son_groupe(bac: Bac, client: str) -> None:
    # ADK lance le serveur dans sa propre session, hors du groupe de la cellule : la cellule
    # l'arrête elle-même avant de rendre la main, sans attendre la fin de la boucle (qui
    # annulerait la tâche de la session MCP).
    assert converser_puis_regarder(bac, client, bac.commande()) == []
    (demarrage,) = bac.notes_mcp("pid")
    assert demarrage["pgid"] == demarrage["pid"] != os.getpgid(0)


# --- Isolement et entrée -------------------------------------------------------------------------


def test_gemini_sans_cle_anthropic(bac: Bac) -> None:
    # Refusée avant de lancer quoi que ce soit : ni serveur, ni trace.
    with bac.api(GEMINI, TOUR_TYPE):
        bac.monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)
        with pytest.raises(IsolementError, match="jamais la clé"):
            asyncio.run(converser(GEMINI, bac.commande(), prix.charger()))
    assert bac.notes_mcp("pid") == []
    assert not list((bac.racine / "traces").rglob("*.jsonl"))


def test_claude_sans_cle(bac: Bac) -> None:
    with bac.api(CLAUDE, TOUR_TYPE):
        bac.monkeypatch.delenv("ANTHROPIC_API_KEY")
        with pytest.raises(CleAbsente):
            asyncio.run(converser(CLAUDE, bac.commande(), prix.charger()))
    assert bac.notes_mcp("pid") == []


@pytest.mark.parametrize("arguments", [[], ["claude-code"], [CLAUDE, GEMINI]])
def test_client_refuse(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert cellule_adk.main(arguments) == 2
    assert "usage" in capsys.readouterr().err


def test_commande_illisible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"campagne": "essai"}'))
    assert cellule_adk.main([CLAUDE]) == 2


def test_point_d_entree(bac: Bac, monkeypatch: pytest.MonkeyPatch) -> None:
    # main lit la commande sur stdin et la passe à la conversation.
    recues: list[tuple[str, Commande]] = []

    async def noter(client: str, commande: Commande, _tarifs: Any) -> None:
        recues.append((client, commande))

    commande = bac.commande()
    monkeypatch.setattr(cellule_adk, "converser", noter)
    monkeypatch.setattr(sys, "stdin", io.StringIO(commande_json(commande)))
    assert cellule_adk.main([GEMINI]) == 0
    assert recues == [(GEMINI, commande)]


def test_sigterm_annule_la_conversation(bac: Bac, monkeypatch: pytest.MonkeyPatch) -> None:
    # Un SIGTERM pendant la conversation l'annule (le serveur s'arrête alors avec la boîte à
    # outils) ; main sort en 143.
    async def interrompue(*_: Any) -> None:
        os.kill(os.getpid(), signal.SIGTERM)
        await asyncio.sleep(60)

    monkeypatch.setattr(cellule_adk, "converser", interrompue)
    monkeypatch.setattr(sys, "stdin", io.StringIO(commande_json(bac.commande())))
    assert cellule_adk.main([CLAUDE]) == 128 + signal.SIGTERM


def test_client_inconnu_de_la_conversation(bac: Bac) -> None:
    with pytest.raises(CelluleError, match="client inconnu"):
        asyncio.run(converser("adk-autre", bac.commande(), prix.charger()))


# --- Processus : vrai lanceur, SIGTERM -----------------------------------------------------------


def installer(dossier: Path, nom: str, code: str) -> None:
    script = dossier / nom
    script.write_text(f"#!{sys.executable} -I\n{code}")
    script.chmod(0o755)


@pytest.mark.parametrize("client", CLIENTS)
def test_vrai_lanceur(bac: Bac, client: str) -> None:
    # Toute la chaîne : la cellule, ADK, le vrai lanceur (scripts/mcp-neo4j.sh) ; seuls gcloud,
    # neo4j-mcp et l'API sont faux. L'identifiant de l'instance, renvoyé par le serveur, est masqué
    # avant le client ; ni la clé Anthropic ni les variables Vertex n'atteignent neo4j-mcp.
    outils = bac.racine / "outils"
    installer(outils, "gcloud", f"import sys\nsys.stdout.write({SECRET!r})\n")
    installer(outils, "neo4j-mcp", (FIXTURES / "faux_neo4j_mcp.py").read_text())
    commande = bac.commande(serveur=(str(LANCEUR),))
    with bac.api(client, TOUR_TYPE) as adresse:
        env = environnement_agent(client, bac.racine / "home", bac.racine / "claude", [outils])
        env |= {"ANTHROPIC_BASE_URL" if client == CLAUDE else "GOOGLE_VERTEX_BASE_URL": adresse}
        fini = subprocess.run(
            [sys.executable, "-m", "banc.cellule_adk", client],
            input=commande_json(commande),
            cwd=bac.racine / "travail",
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    assert fini.returncode == 0, fini.stderr
    (tour,) = bac.trace().tours
    assert tour.issue == "reponse"
    (appel,) = tour.appels
    assert "‹instance›" in appel.resultat
    assert INSTANCE not in json.dumps(bac.requetes()) + appel.resultat
    lignes = (bac.journal / "neo4j-mcp.jsonl").read_text().splitlines()
    notes = [json.loads(ligne) for ligne in lignes]
    (demarrage,) = [note for note in notes if "env" in note]
    assert not [nom for nom in demarrage["env"] if nom.startswith(("ANTHROPIC_", "GOOGLE_"))]


def test_sigterm_arrete_le_serveur(bac: Bac) -> None:
    # Arrêtée par l'orchestration en pleine lecture, la cellule arrête son serveur avant de sortir.
    commande = bac.commande(mcp={"appels": [{"lent_s": 60}]})
    with bac.api(CLAUDE, TOUR_TYPE) as adresse:
        env = environnement_agent(CLAUDE, bac.racine / "home", bac.racine / "claude")
        cellule = subprocess.Popen(
            [sys.executable, "-m", "banc.cellule_adk", CLAUDE],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=bac.racine / "travail",
            env=env | {"ANTHROPIC_BASE_URL": adresse},
            text=True,
        )
        assert cellule.stdin is not None
        cellule.stdin.write(commande_json(commande))
        cellule.stdin.close()
        attendre(lambda: "tools/call" in bac.methodes_mcp())
        cellule.send_signal(signal.SIGTERM)
        code = cellule.wait(timeout=20)
    assert code == 128 + signal.SIGTERM
    (demarrage,) = bac.notes_mcp("pid")
    attendre(lambda: not vivant(demarrage["pid"]), 5.0)
