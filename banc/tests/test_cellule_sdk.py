"""Cellule Claude Code (T4.1), avec un faux Claude Code pour cli_path
(tests/fixtures/faux_claude.py), qui parle le protocole du SDK et note ce qu'il reçoit.

DoD : aucune variable hors liste blanche, aucun fichier de réglages lu, chrono lancé après la
connexion. Ensuite, les issues d'un tour (D13) et la mesure : tokens appel par appel tirés du flux,
part à 1 h, petit modèle, Q18 sans les tokens de Q2, interruption à l'échéance et au budget.
"""

import asyncio
import io
import json
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import pytest

from banc import cellule_sdk, prix
from banc.cellule import (
    LANCEUR,
    RACINE,
    CelluleError,
    Commande,
    IsolementError,
    Plafonds,
    consigne_et_fiche,
    empreinte_prompt,
)
from banc.cellule import commande_json as en_json
from banc.cellule_sdk import MODELE, OUTIL, VERSIONS, converser
from banc.isolement import PETIT_MODELE, CleNonUtilisee, environnement_agent
from banc.mesures import Conversation, MesureError, lire
from banc.prix import Usage

FAUX_CLAUDE = Path(__file__).resolve().parent / "fixtures" / "faux_claude.py"
CLE = "sk-ant-api03-cle-factice-du-banc"
SESSION = "session-factice"
# Ce que le SDK 0.2.164 ajoute de lui-même à l'environnement de Claude Code (subprocess_cli.py).
AJOUTS_DU_SDK = {
    "CLAUDE_CODE_ENTRYPOINT",
    "CLAUDE_AGENT_SDK_VERSION",
    "CLAUDE_CODE_SDK_READS_SESSION_STATE",
    "PWD",
}
Q2 = ("Q2", "Mon équipe : Pikachu.\n\nQui remplacer ?")
Q18 = ("Q18", "Et si je garde Pikachu ?")


# --- Messages du protocole, tels que Claude Code 2.1.292 les écrit (relevé T4.1) -----------------


def emettre(message: dict[str, Any]) -> dict[str, Any]:
    return {"emettre": message}


def flux(evenement: dict[str, Any]) -> dict[str, Any]:
    return emettre(
        {
            "type": "stream_event",
            "uuid": "u",
            "session_id": SESSION,
            "event": evenement,
            "parent_tool_use_id": None,
        }
    )


@dataclass(frozen=True)
class Tokens:
    """Un appel du modèle : ce que message_start, puis message_delta, en disent."""

    entree: int = 0
    sortie: int = 0
    ecrit_5m: int = 0
    ecrit_1h: int = 0
    lu: int = 0
    reflexion: int | None = None

    @property
    def ecrit(self) -> int:
        """Tokens écrits en cache, toutes durées confondues."""
        return self.ecrit_5m + self.ecrit_1h

    def debut(self) -> dict[str, Any]:
        return {
            "input_tokens": self.entree,
            "output_tokens": 1,
            "cache_creation_input_tokens": self.ecrit,
            "cache_read_input_tokens": self.lu,
            "cache_creation": {
                "ephemeral_5m_input_tokens": self.ecrit_5m,
                "ephemeral_1h_input_tokens": self.ecrit_1h,
            },
        }

    def fin(self) -> dict[str, Any]:
        usage: dict[str, Any] = {
            "output_tokens": self.sortie,
            "input_tokens": self.entree,
            "cache_creation_input_tokens": self.ecrit,
            "cache_read_input_tokens": self.lu,
        }
        if self.reflexion is not None:
            usage["output_tokens_details"] = {"thinking_tokens": self.reflexion}
        return usage

    def usage(self) -> Usage:
        return Usage(self.entree, self.sortie, self.ecrit_5m, self.ecrit_1h, self.lu)


def debut(ident: str, tokens: Tokens, modele: str = MODELE) -> dict[str, Any]:
    message = {"id": ident, "type": "message", "role": "assistant", "model": modele}
    return flux({"type": "message_start", "message": message | {"usage": tokens.debut()}})


def fin(tokens: Tokens) -> list[dict[str, Any]]:
    delta = {"type": "message_delta", "delta": {"stop_reason": "end_turn"}}
    return [flux(delta | {"usage": tokens.fin()}), flux({"type": "message_stop"})]


def assistant(ident: str, *blocs: dict[str, Any], erreur: str | None = None) -> dict[str, Any]:
    message = {"id": ident, "model": MODELE, "content": list(blocs), "usage": {}}
    corps = {"type": "assistant", "message": message, "parent_tool_use_id": None}
    return emettre(corps | {"session_id": SESSION} | ({"error": erreur} if erreur else {}))


def lecture(ident: str, requete: str, params: Any = None) -> dict[str, Any]:
    entree = {"query": requete} | ({} if params is None else {"params": params})
    return {"type": "tool_use", "id": ident, "name": OUTIL, "input": entree}


def resultat_outil(ident: str, texte: str, erreur: bool = False) -> dict[str, Any]:
    bloc = {
        "type": "tool_result",
        "tool_use_id": ident,
        "content": [{"type": "text", "text": texte}],
    }
    contenu = [bloc | ({"is_error": True} if erreur else {})]
    message = {"role": "user", "content": contenu}
    return emettre({"type": "user", "message": message, "parent_tool_use_id": None})


def cumul(entree: int, sortie: int, ecrit: int, lu: int) -> dict[str, Any]:
    """Une entrée de model_usage : le cumul de la session pour un modèle."""
    return {
        "inputTokens": entree,
        "outputTokens": sortie,
        "cacheReadInputTokens": lu,
        "cacheCreationInputTokens": ecrit,
        "webSearchRequests": 0,
        "costUSD": 0,
        "contextWindow": 1_000_000,
        "maxOutputTokens": 128_000,
    }


def resultat(
    texte: str = "Réponse : 42\n\nSources : MATCH (n) RETURN count(n)",
    *,
    sous_type: str = "success",
    erreur: bool = False,
    statut: int | None = None,
    modeles: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return emettre(
        {
            "type": "result",
            "subtype": sous_type,
            "duration_ms": 1,
            "duration_api_ms": 1,
            "is_error": erreur,
            "num_turns": 2,
            "session_id": SESSION,
            "result": texte,
            "total_cost_usd": 0,
            "usage": {},
            "modelUsage": modeles or {},
            "api_error_status": statut,
        }
    )


def reprise(statut: int = 429) -> dict[str, Any]:
    retry = {"attempt": 1, "max_retries": 2, "retry_delay_ms": 500, "error_status": statut}
    return emettre({"type": "system", "subtype": "api_retry", "error": "rate_limit"} | retry)


# Un tour type : une lecture du graphe, puis la réponse ; part 1 h écrite au premier appel.
APPEL_1 = Tokens(entree=900, sortie=40, ecrit_1h=3000, reflexion=12)
APPEL_2 = Tokens(entree=100, sortie=30, lu=3000, reflexion=5)
REQUETE = "MATCH (n) RETURN count(n) AS n"


def tour_type(prefixe: str = "") -> list[dict[str, Any]]:
    outil = f"toolu_{prefixe}1"
    return [
        debut(f"msg_{prefixe}1", APPEL_1),
        assistant(f"msg_{prefixe}1", lecture(outil, REQUETE, {"limite": 3})),
        *fin(APPEL_1),
        resultat_outil(outil, '[\n  {\n    "n": 42\n  }\n]'),
        debut(f"msg_{prefixe}2", APPEL_2),
        assistant(f"msg_{prefixe}2", {"type": "text", "text": "Réponse : 42"}),
        *fin(APPEL_2),
    ]


CUMUL_1 = {MODELE: cumul(1000, 70, 3000, 3000)}
SCENARIO = {"tours": [[*tour_type(), resultat(modeles=CUMUL_1)]]}


# --- Bac à sable ---------------------------------------------------------------------------------


@dataclass
class Bac:
    """Faux Claude Code installé, dossiers de l'agent, et de quoi lire ce qui s'est passé."""

    racine: Path

    @property
    def cli(self) -> Path:
        return self.racine / "outils" / "claude"

    def scenario(self, **scenario: Any) -> None:
        """Scénario du faux Claude Code : un tour type, sauf ce que le test change."""
        (self.racine / "journal" / "scenario.json").write_text(json.dumps(SCENARIO | scenario))

    def commande(self, *questions: tuple[str, str], **plafonds: Any) -> Commande:
        return Commande(
            campagne="essai",
            passe=1,
            essai=1,
            questions=questions or (("Q1", "Combien de nœuds ?"),),
            traces=self.racine / "traces",
            plafonds=Plafonds(**plafonds),
            cli=self.cli,
        )

    def converser(self, commande: Commande) -> Conversation:
        asyncio.run(converser(commande, prix.charger()))
        return self.trace(commande)

    def trace(self, commande: Commande) -> Conversation:
        (fichier,) = (self.racine / "traces" / commande.campagne).glob("*.jsonl")
        return lire(fichier)

    def evenements(self, genre: str) -> list[dict[str, Any]]:
        """Les événements bruts d'un type, dans la trace de la conversation."""
        (fichier,) = (self.racine / "traces").rglob("*.jsonl")
        evenements = [json.loads(ligne) for ligne in fichier.read_text().splitlines()]
        return [evenement for evenement in evenements if evenement["type"] == genre]

    def notes(self, genre: str | None = None) -> list[dict[str, Any]]:
        lignes = (self.racine / "journal" / "claude.jsonl").read_text().splitlines()
        notes = [json.loads(ligne) for ligne in lignes]
        return [note for note in notes if genre is None or note["genre"] == genre]

    def demarrage(self) -> dict[str, Any]:
        (note,) = self.notes("demarrage")
        return note


@pytest.fixture
def bac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Bac:
    for dossier in ("home", "claude", "outils", "journal", "travail", "traces"):
        (tmp_path / dossier).mkdir()
    faux = tmp_path / "outils" / "claude"
    faux.write_text(f"#!{sys.executable} -I\n{FAUX_CLAUDE.read_text()}")
    faux.chmod(0o755)
    # Ce que l'orchestration fixe : la clé (scripts/banc.sh), la durée du cache, le dossier vide.
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)
    monkeypatch.setenv("FORCE_PROMPT_CACHING_5M", "1")
    monkeypatch.chdir(tmp_path / "travail")
    nouveau = Bac(tmp_path)
    nouveau.scenario()
    return nouveau


def lancer_isolee(bac: Bac, commande: Commande) -> subprocess.CompletedProcess[str]:
    """La cellule comme l'orchestration la lance : liste blanche pour seul environnement."""
    env = environnement_agent("claude-code", bac.racine / "home", bac.racine / "claude")
    return subprocess.run(
        [sys.executable, "-m", "banc.cellule_sdk"],
        input=en_json(commande),
        cwd=bac.racine / "travail",
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def argument(argv: list[str], option: str) -> str:
    """Valeur d'une option, en deux mots ou en --option=valeur."""
    for i, mot in enumerate(argv):
        if mot == option:
            return argv[i + 1]
        if mot.startswith(f"{option}="):
            return mot.split("=", 1)[1]
    raise AssertionError(f"{option} absente de {argv}")


# --- DoD : isolement et chrono -------------------------------------------------------------------


@pytest.fixture
def isolee(bac: Bac, monkeypatch: pytest.MonkeyPatch) -> Iterator[subprocess.CompletedProcess[str]]:
    # La session de Claude Code qui lance le banc exporte ses réglages : rien ne doit passer.
    for nom, valeur in {
        "CLAUDECODE": "1",
        "CLAUDE_CODE_EFFORT_LEVEL": "max",
        "ANTHROPIC_MODEL": "claude-opus-5-5",
        "CLAUDE_CODE_USE_VERTEX": "1",
    }.items():
        monkeypatch.setenv(nom, valeur)
    yield lancer_isolee(bac, bac.commande())


def test_aucune_variable_hors_liste_blanche(
    bac: Bac, isolee: subprocess.CompletedProcess[str]
) -> None:
    assert isolee.returncode == 0, isolee.stderr
    recu = bac.demarrage()["env"]
    liste = environnement_agent("claude-code", bac.racine / "home", bac.racine / "claude")
    assert set(recu) - set(liste) == AJOUTS_DU_SDK
    assert {nom: recu[nom] for nom in liste} == liste
    assert recu["PWD"] == str(bac.racine / "travail")


def test_aucun_fichier_de_reglages(bac: Bac, isolee: subprocess.CompletedProcess[str]) -> None:
    assert isolee.returncode == 0, isolee.stderr
    note = bac.demarrage()
    argv = note["argv"]
    # Aucune source de réglages, aucun fichier de réglages ni de configuration MCP sur le disque.
    assert argument(argv, "--setting-sources") == ""
    assert "--settings" not in argv
    assert "--strict-mcp-config" in argv
    config = json.loads(argument(argv, "--mcp-config"))
    assert config == {
        "mcpServers": {"neo4j": {"type": "stdio", "command": str(LANCEUR), "args": []}}
    }
    # HOME et CLAUDE_CONFIG_DIR neufs et vides, dossier de travail vide hors du dépôt.
    assert (note["home"], note["config"], note["travail"]) == ([], [], [])
    assert not Path(note["cwd"]).is_relative_to(RACINE)


def test_options_de_d3(bac: Bac, isolee: subprocess.CompletedProcess[str]) -> None:
    assert isolee.returncode == 0, isolee.stderr
    argv = bac.demarrage()["argv"]
    assert argument(argv, "--tools") == ""
    assert argument(argv, "--allowedTools") == OUTIL
    assert argument(argv, "--disallowedTools") == "mcp__neo4j__get-schema"
    assert argument(argv, "--permission-mode") == "dontAsk"
    assert argument(argv, "--max-turns") == "10"
    assert argument(argv, "--model") == MODELE
    assert argument(argv, "--effort") == "high"
    assert "--include-partial-messages" in argv
    # Préréglage claude_code, prolongé par la consigne et la fiche, telles quelles (D5).
    assert argument(argv, "--append-system-prompt") == consigne_et_fiche()
    assert "--system-prompt" not in argv
    # Le budget, compté par la cellule, ne s'affiche pas à l'agent (relevé T4.1).
    assert "--max-budget-usd" not in argv


def test_prompt_de_la_campagne_anglaise(bac: Bac) -> None:
    # Schéma anglais (D8, T10.0) : la fiche anglaise, sous l'empreinte fixée à la création.
    commande = replace(bac.commande(), schema="en", empreinte_prompt=empreinte_prompt("en"))
    fini = lancer_isolee(bac, commande)
    assert fini.returncode == 0, fini.stderr
    argv = bac.demarrage()["argv"]
    assert argument(argv, "--append-system-prompt") == consigne_et_fiche(schema="en")


def test_prompt_change_depuis_la_creation(bac: Bac) -> None:
    # L'empreinte d'un autre prompt : erreur technique, avant Claude Code et avant toute trace.
    commande = replace(bac.commande(), schema="en", empreinte_prompt=empreinte_prompt("fr"))
    fini = lancer_isolee(bac, commande)
    assert fini.returncode == 2
    assert "changées depuis la création de la campagne" in fini.stderr
    assert not bac.racine.joinpath("journal", "claude.jsonl").exists()
    assert list((bac.racine / "traces").rglob("*.jsonl")) == []


def test_chrono_apres_la_connexion(bac: Bac) -> None:
    # Le serveur met 0,6 s à se connecter : la question part après, et son temps ne le compte pas.
    bac.scenario(mcp={"attente_s": 0.6})
    trace = bac.converser(bac.commande())
    controles = [note for note in bac.notes("controle") if note["sous_type"] == "mcp_status"]
    connecte = next(note["t"] for note in controles if note["etat"] == "connected")
    (question,) = bac.notes("utilisateur")
    assert {note["etat"] for note in controles} >= {"pending", "connected"}
    assert question["t"] > connecte
    (tour,) = trace.tours
    assert tour.issue == "reponse"
    assert tour.duree_s is not None and tour.duree_s < 0.6


# --- Un tour mesuré ------------------------------------------------------------------------------


def test_tour_note(bac: Bac) -> None:
    trace = bac.converser(bac.commande())
    (tour,) = trace.tours
    assert (tour.issue, tour.cause, tour.reponse) == (
        "reponse",
        None,
        "Réponse : 42\n\nSources : MATCH (n) RETURN count(n)",
    )
    (appel,) = tour.appels
    assert (appel.outil, appel.requete, appel.parametres) == ("read-cypher", REQUETE, {"limite": 3})
    assert (appel.resultat, appel.erreur) == ('[\n  {\n    "n": 42\n  }\n]', False)
    # Tokens du flux, appel par appel : la part à 1 h que model_usage ne sépare pas.
    assert tour.usages == {MODELE: APPEL_1.usage() + APPEL_2.usage()}
    assert tour.reflexion == {MODELE: 17}
    assert trace.entete.versions == VERSIONS | {"neo4j-mcp": "v1.6.0"}
    assert (trace.entete.cellule, trace.entete.annexes) == ("claude-code", (PETIT_MODELE,))


def test_resultat_d_outil_en_erreur(bac: Bac) -> None:
    # Une écriture refusée par read-cypher (D1) reste visible dans la trace.
    outil = "toolu_1"
    tour = [
        debut("msg_1", APPEL_1),
        assistant("msg_1", lecture(outil, "CREATE (n)")),
        *fin(APPEL_1),
        resultat_outil(outil, "read-cypher can only run read-only Cypher statements", True),
        debut("msg_2", APPEL_2),
        *fin(APPEL_2),
        resultat(modeles=CUMUL_1),
    ]
    bac.scenario(tours=[tour])
    (appel,) = bac.converser(bac.commande()).tours[0].appels
    assert (appel.requete, appel.erreur) == ("CREATE (n)", True)


def test_paire_dans_la_meme_session(bac: Bac) -> None:
    # Q18 suit Q2 dans la même session (D13) ; ses tokens ne comptent pas ceux de Q2, et le petit
    # modèle, que le flux ne montre pas, vient de model_usage, cumulé.
    cumul_2 = {MODELE: cumul(2000, 140, 6000, 6000), PETIT_MODELE: cumul(50, 5, 0, 0)}
    second = [*tour_type("b"), resultat(modeles=cumul_2)]
    bac.scenario(tours=[[*tour_type(), resultat(modeles=CUMUL_1)], second])
    trace = bac.converser(bac.commande(Q2, Q18))
    assert [tour.question for tour in trace.tours] == ["Q2", "Q18"]
    assert len(bac.notes("demarrage")) == 1
    assert [note["message"] for note in bac.notes("utilisateur")] == [Q2[1], Q18[1]]
    q2, q18 = trace.tours
    assert q2.usages == {MODELE: APPEL_1.usage() + APPEL_2.usage()}
    assert q18.usages == {
        MODELE: APPEL_1.usage() + APPEL_2.usage(),
        PETIT_MODELE: Usage(entree=50, sortie=5),
    }


def test_recoupement_du_flux(bac: Bac) -> None:
    # Sur un tour net, model_usage et le flux comptent les mêmes tokens : sinon, un appel échappe
    # à la mesure, qui s'arrête.
    bac.scenario(tours=[[*tour_type(), resultat(modeles={MODELE: cumul(1000, 71, 3000, 3000)})]])
    with pytest.raises(MesureError, match="divergent"):
        bac.converser(bac.commande())


# --- Plafonds : délai, budget, tours -------------------------------------------------------------


# Appel coupé à l'échéance : Claude Code l'interrompt, clôt son flux et oublie ses tokens.
COUPE = Tokens(entree=500, ecrit_5m=200)
COUPE_RELEVE = replace(COUPE.usage(), sortie=1)
APRES_COUPURE = [
    flux(
        {
            "type": "message_delta",
            "delta": {"stop_reason": None},
            "usage": COUPE.fin() | {"output_tokens": 1},
        }
    )["emettre"],
    flux({"type": "message_stop"})["emettre"],
    {
        "type": "user",
        "message": {"role": "user", "content": [{"type": "text", "text": "[Request interrupted"}]},
        "parent_tool_use_id": None,
    },
    resultat(sous_type="error_during_execution", erreur=True, texte="", modeles=CUMUL_1)["emettre"],
]


def tour_coupe(*avant_coupure: dict[str, Any]) -> list[dict[str, Any]]:
    return [*tour_type(), *avant_coupure, debut("msg_3", COUPE), {"bloquer": True}]


def test_delai(bac: Bac) -> None:
    bac.scenario(tours=[tour_coupe()], apres_coupure=APRES_COUPURE)
    trace = bac.converser(bac.commande(delai_s=0.5))
    (tour,) = trace.tours
    assert (tour.issue, tour.cause, tour.reponse) == ("echec", "delai", "")
    assert tour.duree_s is not None and 0.5 <= tour.duree_s < 1.5
    assert [note["sous_type"] for note in bac.notes("controle")][-2:] == ["interrupt", "mcp_status"]
    # L'appel coupé compte son entrée et son cache (D13 : un échec ne coûte pas 0 $) ; sa sortie
    # reste celle que message_start annonce, 1 token ; la trace le marque.
    assert tour.usages == {MODELE: APPEL_1.usage() + APPEL_2.usage() + COUPE_RELEVE}
    marques = {e["brut"]["id"]: e["brut"].get("interrompu") for e in bac.evenements("llm")}
    assert marques == {"msg_1": None, "msg_2": None, "msg_3": True}


def test_delai_sans_message_delta(bac: Bac) -> None:
    # Si Claude Code ne clôt pas le flux de l'appel coupé, son message_start suffit.
    bac.scenario(tours=[tour_coupe()], apres_coupure=APRES_COUPURE[2:])
    (tour,) = bac.converser(bac.commande(delai_s=0.5)).tours
    assert tour.usages == {MODELE: APPEL_1.usage() + APPEL_2.usage() + COUPE_RELEVE}


def test_delai_apres_une_reprise(bac: Bac) -> None:
    # Délai dépassé dans un tour qui a dû reprendre un appel : panne, relancée (D13).
    bac.scenario(tours=[tour_coupe(reprise())], apres_coupure=APRES_COUPURE)
    (tour,) = bac.converser(bac.commande(delai_s=0.5)).tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "reprises", 1)


def test_budget(bac: Bac) -> None:
    # 0,50 $ par conversation : 0,40 $ au premier appel, 0,80 $ au second.
    gros = Tokens(entree=100_000, sortie=20_000)
    tour = [debut("msg_1", gros), *fin(gros), debut("msg_2", gros), *fin(gros), {"bloquer": True}]
    apres = resultat(
        sous_type="error_during_execution",
        erreur=True,
        texte="",
        modeles={MODELE: cumul(200_000, 40_000, 0, 0)},
    )
    bac.scenario(tours=[tour], apres_coupure=[apres["emettre"]])
    (tour_note,) = bac.converser(bac.commande(delai_s=5)).tours
    assert (tour_note.issue, tour_note.cause) == ("echec", "budget")
    assert "interrupt" in [note["sous_type"] for note in bac.notes("controle")]
    assert tour_note.usages == {MODELE: gros.usage() + gros.usage()}


def test_budget_pile_atteint(bac: Bac) -> None:
    # Le budget est dépassé au-delà de 0,50 $, pas à 0,50 $ pile (0,10 $ + 0,40 $).
    petit, gros = Tokens(entree=50_000), Tokens(entree=100_000, sortie=20_000)
    tour = [debut("msg_1", petit), *fin(petit), debut("msg_2", gros), *fin(gros)]
    tour.append(resultat(modeles={MODELE: cumul(150_000, 20_000, 0, 0)}))
    bac.scenario(tours=[tour])
    (tour_note,) = bac.converser(bac.commande()).tours
    assert tour_note.issue == "reponse"


def test_budget_de_la_conversation(bac: Bac) -> None:
    # Le budget vaut pour la conversation entière : Q18 le dépasse avec ce que Q2 a coûté.
    gros = Tokens(entree=100_000, sortie=20_000)
    q2 = [
        debut("msg_1", gros),
        *fin(gros),
        resultat(modeles={MODELE: cumul(100_000, 20_000, 0, 0)}),
    ]
    q18 = [debut("msg_2", gros), *fin(gros), {"bloquer": True}]
    apres = resultat(
        sous_type="error_during_execution",
        erreur=True,
        texte="",
        modeles={MODELE: cumul(200_000, 40_000, 0, 0)},
    )
    bac.scenario(tours=[q2, q18], apres_coupure=[apres["emettre"]])
    q2_note, q18_note = bac.converser(bac.commande(Q2, Q18, delai_s=5)).tours
    assert (q2_note.issue, q18_note.issue, q18_note.cause) == ("reponse", "echec", "budget")


def test_tours(bac: Bac) -> None:
    fini = resultat(sous_type="error_max_turns", erreur=True, texte="", modeles=CUMUL_1)
    bac.scenario(tours=[[*tour_type(), fini]])
    (tour,) = bac.converser(bac.commande()).tours
    assert (tour.issue, tour.cause) == ("echec", "tours")


def test_pas_de_second_tour_apres_un_echec(bac: Bac) -> None:
    # Q18 n'est jamais posée après l'échec de Q2 (ADR-0012 : sa ligne revient à T4.3).
    fini = resultat(sous_type="error_max_turns", erreur=True, texte="", modeles=CUMUL_1)
    bac.scenario(tours=[[*tour_type(), fini], [*tour_type("b"), resultat(modeles=CUMUL_1)]])
    trace = bac.converser(bac.commande(Q2, Q18))
    assert [(tour.question, tour.issue) for tour in trace.tours] == [("Q2", "echec")]
    assert len(bac.notes("utilisateur")) == 1


# --- Pannes, plafond de dépense, erreurs techniques ----------------------------------------------


def erreur_d_api(genre: str, statut: int) -> list[dict[str, Any]]:
    texte = f"API Error: {statut}"
    return [
        reprise(statut),
        assistant("msg_err", {"type": "text", "text": texte}, erreur=genre),
        resultat(texte, erreur=True, statut=statut),
    ]


@pytest.mark.parametrize(("genre", "statut"), [("rate_limit", 429), ("server_error", 529)])
def test_panne_de_l_api(bac: Bac, genre: str, statut: int) -> None:
    bac.scenario(tours=[erreur_d_api(genre, statut)])
    (tour,) = bac.converser(bac.commande()).tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "api", 1)


def test_credits_epuises(bac: Bac) -> None:
    # Ni panne ni échec : la campagne s'arrête (D13, question à Julien avant toute recharge).
    bac.scenario(tours=[erreur_d_api("billing_error", 400)[1:]])
    (tour,) = bac.converser(bac.commande()).tours
    assert (tour.issue, tour.cause) == ("arret", "plafond")


@pytest.mark.parametrize(
    ("genre", "statut"),
    [("invalid_request", 400), ("authentication_failed", 401)],
    ids=["requete-refusee", "cle-invalide"],
)
def test_erreur_technique(bac: Bac, genre: str, statut: int) -> None:
    # Une relance n'y changerait rien (limite du workspace comprise, HTTP 400 selon la doc) : la
    # mesure s'arrête, le tour reste sans issue.
    bac.scenario(tours=[erreur_d_api(genre, statut)[1:]])
    with pytest.raises(CelluleError, match=f"HTTP {statut}"):
        bac.converser(bac.commande())
    (tour,) = bac.trace(bac.commande()).tours
    assert tour.issue is None


@pytest.mark.parametrize(
    ("mcp", "connexion_s"),
    [({"suite": ["failed"]}, 30.0), ({"attente_s": 60}, 0.3)],
    ids=["en-echec", "jamais-connecte"],
)
def test_serveur_absent(bac: Bac, mcp: dict[str, Any], connexion_s: float) -> None:
    # Panne avant le chrono : la question n'est jamais posée, l'agent ne répond pas de mémoire. Un
    # serveur en échec se note tout de suite, sans attendre la fin du délai de connexion.
    bac.scenario(mcp=mcp)
    debut_s = time.monotonic()
    trace = bac.converser(bac.commande(connexion_s=connexion_s))
    assert time.monotonic() - debut_s < 5
    (tour,) = trace.tours
    assert (tour.issue, tour.cause, tour.duree_s is not None and tour.duree_s < 0.1) == (
        "panne",
        "serveur",
        True,
    )
    assert bac.notes("utilisateur") == []
    assert trace.entete.versions["neo4j-mcp"] == "absent"


def test_serveur_perdu_pendant_le_tour(bac: Bac) -> None:
    bac.scenario(mcp={"suite": ["connected", "failed"]})
    (tour,) = bac.converser(bac.commande()).tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")


# --- Isolement vérifié sur ce que Claude Code annonce --------------------------------------------


@pytest.mark.parametrize(
    ("init", "motif"),
    [
        ({"tools": [OUTIL, "mcp__neo4j__get-schema"]}, "tools"),
        ({"permissionMode": "auto"}, "permissionMode"),
        ({"model": "claude-opus-5-5"}, "model"),
        ({"claude_code_version": "2.1.300"}, "claude_code_version"),
        ({"mcp_servers": [{"name": "neo4j"}, {"name": "autre"}]}, "mcp_servers"),
        ({"effort": "max"}, "effort"),
        ({"messaging_socket_path": "/tmp/cc-socks/1.sock"}, "messaging_socket_path"),
        ({"memory_paths": {"auto": "/tmp/memoire"}}, "memory_paths"),
    ],
    ids=lambda valeur: valeur if isinstance(valeur, str) else None,
)
def test_init_hors_de_d3(bac: Bac, init: dict[str, Any], motif: str) -> None:
    bac.scenario(init=init)
    with pytest.raises(IsolementError, match=f"'{motif}'"):
        bac.converser(bac.commande())


@pytest.mark.parametrize("source", ["oauth", "none", None])
def test_init_sans_la_cle(bac: Bac, source: str | None) -> None:
    # Par l'abonnement de Julien, le coût ne serait pas mesurable (circuit breaker du plan 002).
    bac.scenario(init={"apiKeySource": source})
    with pytest.raises(CleNonUtilisee, match="apiKeySource"):
        bac.converser(bac.commande())


def test_init_conforme_accepte(bac: Bac) -> None:
    # L'entrée des tests d'exclusion ci-dessus, sans son écart : acceptée.
    bac.scenario(init={"effort": "high"})
    assert bac.converser(bac.commande()).tours[0].issue == "reponse"


@pytest.mark.parametrize(
    ("scenario", "motif"),
    [
        ({"autres_serveurs": ["autre"]}, "hors de la commande"),
        ({"outils": ["get-schema"]}, "sans read-cypher"),
    ],
    ids=["serveur-en-trop", "sans-read-cypher"],
)
def test_serveur_hors_de_d3(bac: Bac, scenario: dict[str, Any], motif: str) -> None:
    bac.scenario(**scenario)
    with pytest.raises(IsolementError, match=motif):
        bac.converser(bac.commande())


def test_cache_de_la_commande(bac: Bac, monkeypatch: pytest.MonkeyPatch) -> None:
    # Une commande à 1 h dans un environnement à 5 min : la durée mesurée ne serait pas celle dite.
    commande = replace(bac.commande(), cache_1h=True)
    with pytest.raises(IsolementError, match="ENABLE_PROMPT_CACHING_1H"):
        asyncio.run(converser(commande, prix.charger()))
    monkeypatch.setenv("ENABLE_PROMPT_CACHING_1H", "1")
    assert bac.converser(commande).tours[0].issue == "reponse"


# --- Point d'entrée ------------------------------------------------------------------------------


def test_erreur_technique_code_2(bac: Bac) -> None:
    bac.scenario(init={"apiKeySource": "oauth"})
    fini = lancer_isolee(bac, bac.commande())
    assert fini.returncode == 2
    assert "apiKeySource='oauth'" in fini.stderr


def test_commande_illisible_code_2(bac: Bac) -> None:
    env = environnement_agent("claude-code", bac.racine / "home", bac.racine / "claude")
    fini = subprocess.run(
        [sys.executable, "-m", "banc.cellule_sdk"],
        input='{"campagne": "essai"}',
        cwd=bac.racine / "travail",
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert (fini.returncode, bac.racine.joinpath("journal", "claude.jsonl").exists()) == (2, False)
    assert "commande illisible" in fini.stderr


# --- Cas rares : client arrêté, muet, entrées inattendues ----------------------------------------


def test_claude_code_arrete_en_plein_tour(bac: Bac) -> None:
    bac.scenario(tours=[[debut("msg_1", APPEL_1), {"quitter": True}]])
    with pytest.raises(CelluleError, match="sans résultat"):
        bac.converser(bac.commande())


def test_muet_apres_l_interruption(
    bac: Bac, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Sans résultat après interrupt(), le tour garde son issue ; l'orchestration arrêtera le groupe.
    monkeypatch.setattr(cellule_sdk, "FIN_COUPURE_S", 0.3)
    bac.scenario(tours=[tour_coupe()])
    (tour,) = bac.converser(bac.commande(delai_s=0.5)).tours
    assert (tour.issue, tour.cause) == ("echec", "delai")
    assert tour.usages == {MODELE: APPEL_1.usage() + APPEL_2.usage() + COUPE_RELEVE}
    assert "aucun résultat après interrupt()" in capsys.readouterr().err


def test_entrees_inattendues(bac: Bac) -> None:
    # Des paramètres qui ne sont pas un objet, un résultat d'outil en texte brut : notés tels quels.
    outil = "toolu_1"
    texte = {"type": "tool_result", "tool_use_id": outil, "content": "texte brut"}
    tour = [
        debut("msg_1", APPEL_1),
        assistant("msg_1", lecture(outil, REQUETE, "pas un objet")),
        *fin(APPEL_1),
        emettre({"type": "user", "message": {"role": "user", "content": [texte]}}),
        debut("msg_2", APPEL_2),
        *fin(APPEL_2),
        resultat(modeles=CUMUL_1),
    ]
    bac.scenario(tours=[tour])
    (appel,) = bac.converser(bac.commande()).tours[0].appels
    assert (appel.parametres, appel.resultat) == ({"params": "pas un objet"}, "texte brut")


def test_stderr_relaye(bac: Bac, capsys: pytest.CaptureFixture[str]) -> None:
    bac.scenario(stderr="avertissement du faux")
    bac.converser(bac.commande())
    assert "claude-code : avertissement du faux" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("init", "code"), [({}, 0), ({"apiKeySource": "oauth"}, 2)], ids=["reponse", "cle"]
)
def test_point_d_entree(
    bac: Bac, monkeypatch: pytest.MonkeyPatch, init: dict[str, Any], code: int
) -> None:
    bac.scenario(init=init)
    monkeypatch.setattr(sys, "stdin", io.StringIO(en_json(bac.commande())))
    assert cellule_sdk.main() == code


def test_budget_compte_le_petit_modele(bac: Bac) -> None:
    # Le petit modèle, que model_usage seul montre, compte dans le budget dès la fin du tour : Q2
    # coûte 0,20 $ au modèle de la cellule et 0,40 $ au petit modèle (400 000 tokens à 1 $ le
    # million), au-delà des 0,50 $ ; Q18 n'est pas posée.
    moyen = Tokens(entree=100_000)
    cumul_q2 = {MODELE: cumul(100_000, 0, 0, 0), PETIT_MODELE: cumul(400_000, 0, 0, 0)}
    q2 = [debut("msg_1", moyen), *fin(moyen), resultat(modeles=cumul_q2)]
    bac.scenario(tours=[q2])
    trace = bac.converser(bac.commande(Q2, Q18, delai_s=5))
    assert [(tour.question, tour.issue, tour.cause) for tour in trace.tours] == [
        ("Q2", "echec", "budget")
    ]
    assert trace.tours[0].usages[PETIT_MODELE] == Usage(entree=400_000)


@pytest.mark.parametrize(
    ("genre", "statut", "issue"),
    [
        ("unknown", 500, "panne"),
        ("unknown", 429, "panne"),
        ("server_error", None, "panne"),
        ("unknown", 499, None),
        ("unknown", 428, None),
    ],
)
def test_statuts_de_panne(bac: Bac, genre: str, statut: int | None, issue: str | None) -> None:
    # Une limite de débit (429) ou une erreur du fournisseur (5xx, ou annoncée comme telle) se
    # relance ; tout autre refus est une erreur technique (aux bornes : 499 et 428).
    texte = "API Error"
    erreur = assistant("msg_err", {"type": "text", "text": texte}, erreur=genre)
    bac.scenario(tours=[[erreur, resultat(texte, erreur=True, statut=statut)]])
    if issue is None:
        with pytest.raises(CelluleError, match=f"HTTP {statut}"):
            bac.converser(bac.commande())
        return
    (tour,) = bac.converser(bac.commande()).tours
    assert (tour.issue, tour.cause) == ("panne", "api")


def test_reprise_sans_recoupement(bac: Bac) -> None:
    # Un appel coupé par une erreur de l'API, puis repris : le flux le compte, model_usage non. Sur
    # un tour qui a eu une reprise, les deux ne se recoupent pas.
    tour = [debut("msg_0", COUPE), reprise(529), *tour_type(), resultat(modeles=CUMUL_1)]
    bac.scenario(tours=[tour])
    (tour_note,) = bac.converser(bac.commande()).tours
    assert (tour_note.issue, tour_note.reprises) == ("reponse", 1)
    assert tour_note.usages == {MODELE: COUPE_RELEVE + APPEL_1.usage() + APPEL_2.usage()}


def test_outil_inconnu_ignore(bac: Bac) -> None:
    # Un outil que l'agent n'a pas (nom inventé) : Claude Code le refuse ; la trace ne garde que
    # read-cypher et get-schema (banc.trace).
    tour = [
        debut("msg_1", APPEL_1),
        assistant("msg_1", {"type": "tool_use", "id": "toolu_x", "name": "Bash", "input": {}}),
        *fin(APPEL_1),
        resultat_outil("toolu_x", "No such tool available: Bash", erreur=True),
        debut("msg_2", APPEL_2),
        *fin(APPEL_2),
        resultat(modeles=CUMUL_1),
    ]
    bac.scenario(tours=[tour])
    (tour_note,) = bac.converser(bac.commande()).tours
    assert (tour_note.issue, tour_note.appels) == ("reponse", ())
