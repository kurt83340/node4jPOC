"""Faux serveur MCP pour tests/test_cellule_adk.py : neo4j-mcp v1.6.0 vu du client (mêmes outils),
lancé directement par la cellule (commande « serveur »), sans le lanceur.

Usage : faux_serveur_mcp.py <scenario.json> <journal.jsonl>. Note l'environnement reçu, chaque
message reçu et l'instant de chaque réponse (horloge monotone). L'environnement ne s'écrit en entier
qu'avec « noter_env » (sinon ses seuls noms) : lancé dans le processus des tests, le serveur
recevrait celui du poste, secrets compris. Scénario : {"attente_s": délai
avant de répondre à initialize, "relance_s": délai de plus quand le serveur est relancé (le journal
note déjà un lancement), "version": version annoncée, "outils": noms des outils annoncés (défaut :
ceux de la v1.6.0), "appels": [une entrée par tools/call, dans l'ordre : {"texte", "erreur",
"lent_s", "mort", "quitter", "quitter_apres_s"}], "par_requete": [[motif, réponse], …],
"instructions": texte}. « mort » : le serveur sort au lieu de répondre ; « quitter » : il sort juste
après avoir répondu (serveur perdu entre deux appels) ; « quitter_apres_s » : il sort ce délai après
avoir répondu. « par_requete » (tests/test_essai_serveur.py) : la première réponse dont le motif
figure dans la requête de read-cypher passe avant les appels prévus. « instructions » : ajoutées à
la réponse à initialize, comme les annonce le vrai serveur. « outils » peut nommer write-cypher
(lecture seule ignorée). Au-delà des appels prévus : un résultat type.
"""

import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

SCENARIO = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
JOURNAL = Path(sys.argv[2])
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
    {
        "name": "write-cypher",
        "description": "write-cypher executes any arbitrary Cypher query.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
]
# Les outils de la v1.6.0 en lecture seule : write-cypher n'est annoncé que si le scénario le nomme.
LECTURE_SEULE = ["get-schema", "read-cypher"]
RESULTAT_TYPE = '[\n  {\n    "n": 42\n  }\n]'


def noter(note: dict[str, Any]) -> None:
    with JOURNAL.open("a", encoding="utf-8") as flux:
        flux.write(json.dumps(note | {"t": time.monotonic()}, ensure_ascii=False) + "\n")


def repondre(ident: Any, resultat: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": ident, "result": resultat}) + "\n")
    sys.stdout.flush()


def principal() -> None:
    relance = JOURNAL.exists() and '"pid"' in JOURNAL.read_text(encoding="utf-8")
    env = dict(os.environ) if SCENARIO.get("noter_env") else sorted(os.environ)
    noter({"env": env, "pid": os.getpid(), "pgid": os.getpgid(0)})
    appels = list(SCENARIO.get("appels", []))
    for ligne in sys.stdin:
        message = json.loads(ligne)
        noter({"recu": message})
        methode, ident = message.get("method"), message.get("id")
        if ident is None:
            continue
        if methode == "initialize":
            time.sleep(
                SCENARIO.get("attente_s", 0) + (SCENARIO.get("relance_s", 0) if relance else 0)
            )
            version = message["params"].get("protocolVersion", "2025-06-18")
            info = {"name": "neo4j-mcp", "version": SCENARIO.get("version", "v1.6.0")}
            capacites = {"tools": {"listChanged": True}}
            initiale = {"protocolVersion": version, "capabilities": capacites, "serverInfo": info}
            if "instructions" in SCENARIO:
                initiale["instructions"] = SCENARIO["instructions"]
            repondre(ident, initiale)
        elif methode == "tools/list":
            noms = SCENARIO.get("outils", LECTURE_SEULE)
            annonces = [outil for outil in OUTILS if outil["name"] in noms]
            repondre(ident, {"tools": annonces})
        elif methode == "tools/call":
            requete = message["params"].get("arguments", {}).get("query", "")
            choisies = [r for motif, r in SCENARIO.get("par_requete", []) if motif in requete]
            appel = choisies[0] if choisies else (appels.pop(0) if appels else {})
            if appel.get("mort"):
                noter({"mort": True})
                sys.exit(3)
            time.sleep(appel.get("lent_s", 0))
            contenu = [{"type": "text", "text": appel.get("texte", RESULTAT_TYPE)}]
            repondre(ident, {"content": contenu, "isError": appel.get("erreur", False)})
            if appel.get("quitter"):
                noter({"quitte": True})
                sys.exit(0)
            if "quitter_apres_s" in appel:
                threading.Timer(appel["quitter_apres_s"], os._exit, (0,)).start()
        elif methode == "ping":
            repondre(ident, {})
        else:
            erreur = {"code": -32601, "message": "Method not found"}
            sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": ident, "error": erreur}) + "\n")
            sys.stdout.flush()
        noter({"repondu": methode})


principal()
