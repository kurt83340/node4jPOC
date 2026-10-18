"""Faux serveur MCP de la répétition générale (T5.1) : le protocole vu du client, le résultat
neutre, la lenteur qui fait dépasser le délai d'une question ; le résultat fixe de la recherche
des cellules GraphRAG (spec 003, T13.1)."""

import io
import json
import subprocess
import sys
import time
from typing import Any

import pytest
from test_contamination import INTERDITES, contient, mots

from banc import faux_serveur
from banc.essai_recherche import ecarts_du_contexte
from banc.faux_serveur import RECHERCHE_FIXE, RESULTAT, VERSION, reponse, servir
from banc.questions import charger

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
# La recherche d'une cellule GraphRAG : la requête de recherche, le vecteur du message en paramètre.
RECHERCHER = APPEL | {
    "id": 7,
    "params": {
        "name": "read-cypher",
        "arguments": {
            "query": "CYPHER 25 MATCH (d) RETURN d.texte",
            "params": {"vecteur": [0.1] * 3},
        },
    },
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


# --- Recherche des cellules GraphRAG (spec 003, T13.1) --------------------------------------------


def test_recherche_fixe_des_cellules_graphrag() -> None:
    # La lecture qui porte un vecteur, la recherche d'une cellule GraphRAG, reçoit un résultat fixe
    # dans la forme de questions/recherche.cypher (contrôle de banc essai-recherche, T8.2) ; toute
    # autre lecture, le résultat neutre.
    recherche, autre = echanger(RECHERCHER, APPEL)
    assert recherche["result"] == {
        "content": [{"type": "text", "text": RECHERCHE_FIXE}],
        "isError": False,
    }
    assert ecarts_du_contexte(RECHERCHE_FIXE) == []
    assert autre["result"]["content"] == [{"type": "text", "text": "[]"}]


def test_recherche_fixe_neutre() -> None:
    # Comme les phrases maison de T8.2 : ni espèce ni valeur du banc dans ses espèces et ses
    # descriptions (inventées : aucun texte de la base dans le dépôt), aucun thème des questions
    # sémantiques ; la répétition éprouve la chaîne, pas les réponses.
    enregistrements = json.loads(RECHERCHE_FIXE)
    especes = [enregistrement["espece"] for enregistrement in enregistrements]
    textes = [d["texte"] for e in enregistrements for d in e["descriptions"]]
    questions = {question.texte for question in charger().questions.values()}
    for valeur in (*especes, *textes):
        assert valeur not in questions
        assert not [v for v in INTERDITES if contient(mots(valeur), mots(v))], valeur
    for theme in ("volcan", "ocean", "planete", "humain", "dort", "dormir", "sommeil"):
        assert not [t for t in textes if theme in " ".join(mots(t))], theme
