"""Faux neo4j-mcp v1.6.0 pour tests/test_cellule_sdk_reel.py : un serveur MCP en stdio, lancé par le
vrai lanceur (scripts/mcp-neo4j.sh), qui lui passe sa configuration par l'environnement.

Mêmes outils et mêmes instructions que la v1.6.0 (mcp-go v0.56.0) ; read-cypher renvoie
l'identifiant de l'instance (comme CALL db.info()), que le lanceur doit masquer. Note dans
../journal/neo4j-mcp.jsonl l'environnement reçu (ses noms), son groupe de processus et ses ancêtres
(tests/test_orchestration.py : le groupe que l'orchestration arrête), puis les requêtes.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any

JOURNAL = Path(__file__).resolve().parent.parent / "journal" / "neo4j-mcp.jsonl"
INSTRUCTIONS = (
    "This is the Neo4j official MCP server and can provide tool calling to interact with your "
    "Neo4j database,by inferring the schema with tools like get-schema and executing arbitrary "
    "Cypher queries with read-cypher."
)
OUTILS = [
    {
        "name": "get-schema",
        "description": "Retrieve the schema information from the Neo4j database.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read-cypher",
        "description": "read-cypher can run only read-only Cypher statements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The Cypher query to execute"},
                "params": {"type": "object", "description": "Parameters to pass to the query"},
            },
            "required": ["query"],
        },
    },
]


def noter(note: dict[str, Any]) -> None:
    with JOURNAL.open("a", encoding="utf-8") as flux:
        flux.write(json.dumps(note) + "\n")


def repondre(ident: Any, resultat: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": ident, "result": resultat}) + "\n")
    sys.stdout.flush()


def ancetres() -> list[dict[str, Any]]:
    """Les processus dont il descend, du parent à la racine : pid, groupe, ligne de commande."""
    lignee = []
    pid = os.getppid()
    while pid > 1:
        try:
            champs = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
            commande = Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode()
        except OSError:
            break
        lignee.append({"pid": pid, "pgid": int(champs[2]), "commande": commande.strip()})
        pid = int(champs[1])
    return lignee


def principal() -> None:
    noter(
        {
            "env": sorted(os.environ),
            "pid": os.getpid(),
            "pgid": os.getpgid(0),
            "ancetres": ancetres(),
        }
    )
    instance = os.environ.get("NEO4J_MCP_USERNAME", "")
    for ligne in sys.stdin:
        message = json.loads(ligne)
        noter({"recu": message})
        methode, ident = message.get("method"), message.get("id")
        if ident is None:
            continue
        if methode == "initialize":
            version = message["params"].get("protocolVersion", "2025-06-18")
            repondre(
                ident,
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": True}},
                    "serverInfo": {"name": "neo4j-mcp", "version": "v1.6.0"},
                    "instructions": INSTRUCTIONS,
                },
            )
        elif methode == "tools/list":
            repondre(ident, {"tools": OUTILS})
        elif methode == "tools/call":
            texte = json.dumps([{"name": instance, "n": 42}], indent=2)
            repondre(ident, {"content": [{"type": "text", "text": texte}], "isError": False})
        elif methode == "ping":
            repondre(ident, {})
        else:
            erreur = {"code": -32601, "message": "Method not found"}
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": ident, "error": erreur}) + "\n")
            sys.stdout.flush()


principal()
