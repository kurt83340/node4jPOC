"""Faux serveur MCP de la répétition générale (T5.1) : le protocole vu du client, le résultat
neutre, la lenteur qui fait dépasser le délai d'une question."""

import io
import json
import subprocess
import sys
import time
from typing import Any

import pytest

from banc import faux_serveur
from banc.faux_serveur import RESULTAT, VERSION, reponse, servir

INITIALISER = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}},
}
APPEL = {
    "jsonrpc": "2.0",
    "id": 3,
    "method": "tools/call",
    "params": {"name": "read-cypher", "arguments": {"query": "MATCH (n) RETURN count(n)"}},
}


def echanger(*messages: Any, lent_s: float = 0.0) -> list[dict[str, Any]]:
    """Les réponses du serveur aux messages, une ligne JSON chacun (texte brut pour une ligne
    illisible)."""
    lignes = [m if isinstance(m, str) else json.dumps(m) for m in messages]
    sortie = io.StringIO()
    servir(io.StringIO("\n".join(lignes) + "\n"), sortie, lent_s)
    return [json.loads(ligne) for ligne in sortie.getvalue().splitlines()]


def test_initialize_annonce_le_faux_serveur() -> None:
    (envoi,) = echanger(INITIALISER)
    assert envoi["id"] == 1
    assert envoi["result"]["serverInfo"] == {"name": "neo4j-mcp", "version": VERSION}
    assert envoi["result"]["protocolVersion"] == "2025-06-18"
    # Comme le lanceur, qui les ôte (T4.1) : aucune instruction au client.
    assert "instructions" not in envoi["result"]


def test_outils_de_neo4j_mcp() -> None:
    (envoi,) = echanger({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert [outil["name"] for outil in envoi["result"]["tools"]] == ["get-schema", "read-cypher"]


def test_resultat_neutre_a_chaque_appel() -> None:
    envois = echanger(APPEL, APPEL | {"id": 4})
    assert [envoi["id"] for envoi in envois] == [3, 4]
    for envoi in envois:
        assert envoi["result"] == {"content": [{"type": "text", "text": "[]"}], "isError": False}
    assert RESULTAT == "[]"


def test_notifications_sans_reponse_et_methode_inconnue() -> None:
    envois = echanger(
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 5, "method": "resources/list"},
        {"jsonrpc": "2.0", "id": 6, "method": "ping"},
    )
    assert envois == [
        {"jsonrpc": "2.0", "id": 5, "error": {"code": -32601, "message": "Method not found"}},
        {"jsonrpc": "2.0", "id": 6, "result": {}},
    ]


def test_ligne_illisible_puis_la_suite() -> None:
    envois = echanger("{pas du json", "", APPEL)
    assert envois[0]["error"]["code"] == -32700
    assert envois[1]["id"] == 3


def test_lenteur_avant_chaque_resultat() -> None:
    debut = time.monotonic()
    echanger(APPEL, lent_s=0.3)
    assert time.monotonic() - debut >= 0.3
    # Seuls les appels d'outil attendent.
    debut = time.monotonic()
    assert reponse(INITIALISER, lent_s=5.0) is not None
    assert time.monotonic() - debut < 1.0


def test_lance_comme_un_client_le_lance() -> None:
    # Par le module, en mode isolé, comme FAUX_SERVEUR dans banc.orchestration.
    entree = "\n".join(json.dumps(m) for m in (INITIALISER, APPEL)) + "\n"
    fini = subprocess.run(
        [sys.executable, "-I", "-m", "banc.faux_serveur", "--lent-s", "0.1"],
        input=entree,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    envois = [json.loads(ligne) for ligne in fini.stdout.splitlines()]
    assert [envoi["id"] for envoi in envois] == [1, 3]
    assert fini.stderr == ""


def test_main_sans_option(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(INITIALISER) + "\n"))
    assert faux_serveur.main([]) == 0
    assert json.loads(capsys.readouterr().out)["id"] == 1
