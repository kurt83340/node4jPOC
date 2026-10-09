"""Faux Claude Code pour tests/test_cellule_sdk.py : le faux cli_path de T4.1.

Le SDK le lance comme le vrai binaire : d'abord `-v`, puis avec les options de la cellule, stdin
et stdout en stream-json. Il note ce qu'il reçoit dans ../journal/claude.jsonl (arguments,
environnement reçu à l'exec, contenu de HOME, de CLAUDE_CONFIG_DIR et du dossier de travail,
requêtes de contrôle et messages, avec l'instant de chacun à l'horloge monotone, commune aux
processus), et joue le scénario de ../journal/scenario.json :

- "mcp" : {"attente_s": secondes de statut « pending », "suite": statuts rendus ensuite, un par
  relevé, le dernier répété} ; "outils" et "autres_serveurs" changent ce que le statut annonce ;
- "init" : champs qui remplacent ceux du message init ;
- "tours" : une liste d'actions par question, {"emettre": message}, {"attendre": secondes},
  {"bloquer": true}, qui suspend le tour jusqu'à l'interruption, ou {"quitter": true}, qui arrête
  le faux en plein tour ;
- "stderr" : une ligne écrite sur stderr au démarrage ;
- "apres_coupure" : messages émis après la réponse à interrupt().
"""

import json
import sys
import time
from pathlib import Path
from typing import Any

BAC = Path(__file__).resolve().parent.parent
JOURNAL = BAC / "journal"
VERSION = "2.1.292"


def noter(genre: str, **champs: Any) -> None:
    with (JOURNAL / "claude.jsonl").open("a", encoding="utf-8") as flux:
        flux.write(json.dumps({"genre": genre, "t": time.monotonic(), **champs}) + "\n")


def emettre(message: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(message, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def contenu(dossier: str | None) -> list[str] | None:
    """Ce que contient un dossier du bac ; None hors du bac (HOME du poste, en processus)."""
    if not dossier or not Path(dossier).is_relative_to(BAC):
        return None
    return sorted(str(p.relative_to(dossier)) for p in Path(dossier).rglob("*"))


def statut_mcp(scenario: dict[str, Any], debut: float, releves: int) -> tuple[str, dict[str, Any]]:
    mcp = scenario.get("mcp", {})
    if time.monotonic() - debut < mcp.get("attente_s", 0):
        etat = "pending"
    else:
        suite = mcp.get("suite", ["connected"])
        etat = str(suite[min(releves, len(suite) - 1)])
    serveur: dict[str, Any] = {"name": "neo4j", "status": etat, "scope": "dynamic"}
    if etat == "connected":
        serveur["serverInfo"] = {"name": "neo4j-mcp", "version": "v1.6.0"}
        serveur["tools"] = [
            {"name": n} for n in scenario.get("outils", ["get-schema", "read-cypher"])
        ]
    autres = [{"name": n, "status": "connected"} for n in scenario.get("autres_serveurs", [])]
    return etat, {"mcpServers": [serveur, *autres]}


def message_init(scenario: dict[str, Any]) -> dict[str, Any]:
    init = {
        "type": "system",
        "subtype": "init",
        "cwd": str(Path.cwd()),
        "session_id": "session-factice",
        "tools": ["mcp__neo4j__read-cypher"],
        "mcp_servers": [{"name": "neo4j", "status": "connected"}],
        "model": "claude-sonnet-5-5",
        "permissionMode": "dontAsk",
        "apiKeySource": "ANTHROPIC_API_KEY",
        "claude_code_version": VERSION,
        "effort": None,
    }
    remplace: dict[str, Any] = scenario.get("init", {})
    return init | remplace


def repondre(requete: str, reponse: dict[str, Any]) -> None:
    emettre(
        {
            "type": "control_response",
            "response": {"subtype": "success", "request_id": requete, "response": reponse},
        }
    )


def jouer(actions: list[dict[str, Any]]) -> None:
    """Joue un tour ; s'arrête à « bloquer », jusqu'à l'interruption."""
    for action in actions:
        if "emettre" in action:
            emettre(action["emettre"])
        elif "attendre" in action:
            time.sleep(action["attendre"])
        elif action.get("bloquer"):
            return
        elif action.get("quitter"):
            noter("quitte")
            sys.exit(0)


def principal() -> None:
    if sys.argv[1:] == ["-v"]:
        print(f"{VERSION} (Claude Code)")
        return
    debut = time.monotonic()
    recu = Path("/proc/self/environ").read_bytes().decode().split("\0")
    env = dict(variable.split("=", 1) for variable in recu if variable)
    noter(
        "demarrage",
        argv=sys.argv[1:],
        env=env,
        cwd=str(Path.cwd()),
        home=contenu(env.get("HOME")),
        config=contenu(env.get("CLAUDE_CONFIG_DIR")),
        travail=contenu(str(Path.cwd())),
    )
    scenario = json.loads((JOURNAL / "scenario.json").read_text(encoding="utf-8"))
    if "stderr" in scenario:
        sys.stderr.write(scenario["stderr"] + "\n")
        sys.stderr.flush()
    tours = list(scenario.get("tours", []))
    releves = 0
    for ligne in sys.stdin:
        message = json.loads(ligne)
        if message.get("type") == "control_request":
            sous_type = message["request"]["subtype"]
            if sous_type == "mcp_status":
                etat, reponse = statut_mcp(scenario, debut, releves)
                releves += etat != "pending"
                noter("controle", sous_type=sous_type, etat=etat)
                repondre(message["request_id"], reponse)
            else:
                noter("controle", sous_type=sous_type)
                repondre(
                    message["request_id"], {} if sous_type == "interrupt" else {"commands": []}
                )
                if sous_type == "interrupt":
                    jouer([{"emettre": m} for m in scenario.get("apres_coupure", [])])
        elif message.get("type") == "user":
            noter("utilisateur", message=message["message"]["content"])
            emettre(message_init(scenario))
            jouer(tours.pop(0) if tours else [])
    noter("fin")


principal()
