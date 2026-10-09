"""Fausse API Anthropic pour tests/test_cellule_sdk_reel.py : le vrai Claude Code y envoie ses
requêtes (ANTHROPIC_BASE_URL), en flux SSE comme vers l'API.

Usage : fausse_api.py <journal.jsonl> <mode>. Écrit son port sur stdout, puis note chaque
requête (chemin, en-têtes sans la clé, corps). Le modèle de la cellule lit d'abord le graphe
(read-cypher), puis répond après le résultat de l'outil ; une requête sans outils (petit modèle)
reçoit un texte court. Modes : « normal » ; « lent » (le flux s'ouvre, puis rien : l'échéance
tombe) ; « 429 » (limite de débit, sans fin). Le cache s'écrit à la durée que la requête demande.
"""

import json
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

JOURNAL = Path(sys.argv[1])
MODE = sys.argv[2]
REQUETE = "CALL db.info() YIELD name RETURN name"
REPONSE = f"Réponse : 42\n\nSources : {REQUETE}"
compteur = {"appels": 0}


def usage(corps: dict[str, Any], apres_outil: bool) -> dict[str, Any]:
    """Tokens d'un appel : écriture en cache au premier, lecture ensuite, à la durée demandée."""
    une_heure = '"ttl": "1h"' in json.dumps(corps)
    ecrit = 0 if apres_outil else 3000
    return {
        "input_tokens": 100 if apres_outil else 900,
        "output_tokens": 30 if apres_outil else 40,
        "cache_creation_input_tokens": ecrit,
        "cache_read_input_tokens": 3000 if apres_outil else 0,
        "cache_creation": {
            "ephemeral_5m_input_tokens": 0 if une_heure else ecrit,
            "ephemeral_1h_input_tokens": ecrit if une_heure else 0,
        },
    }


class Gestion(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        """Silence : le journal suffit."""

    def do_GET(self) -> None:
        self._noter(None)
        self._json(404, {"type": "error", "error": {"type": "not_found_error", "message": "?"}})

    def do_POST(self) -> None:
        corps = json.loads(self.rfile.read(int(self.headers.get("content-length", 0))) or b"{}")
        self._noter(corps)
        if not self.path.startswith("/v1/messages") or "count_tokens" in self.path:
            self._json(404, {"type": "error", "error": {"type": "not_found_error", "message": "?"}})
            return
        compteur["appels"] += 1
        outils = corps.get("tools") or []
        if outils and MODE == "429":
            erreur = {"type": "rate_limit_error", "message": "Rate limited"}
            self._json(429, {"type": "error", "error": erreur}, {"retry-after": "0"})
            return
        utiles = [m for m in corps.get("messages", []) if m.get("role") != "system"]
        dernier = utiles[-1].get("content") if utiles else None
        apres_outil = isinstance(dernier, list) and any(
            bloc.get("type") == "tool_result" for bloc in dernier
        )
        if not outils:
            blocs: list[tuple[str, Any]] = [("text", "Titre")]
        elif apres_outil:
            blocs = [("text", REPONSE)]
        else:
            blocs = [("text", "Je lis le graphe."), ("tool_use", {"query": REQUETE})]
        self._flux(corps.get("model", "?"), blocs, usage(corps, apres_outil), bool(outils))

    def _noter(self, corps: Any) -> None:
        entetes = {
            cle: valeur for cle, valeur in self.headers.items() if cle.lower() != "x-api-key"
        }
        note = {"t": time.monotonic(), "chemin": self.path, "entetes": entetes, "corps": corps}
        with JOURNAL.open("a", encoding="utf-8") as flux:
            flux.write(json.dumps(note, ensure_ascii=False) + "\n")

    def _json(self, code: int, objet: Any, entetes: dict[str, str] | None = None) -> None:
        donnees = json.dumps(objet).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        for cle, valeur in (entetes or {}).items():
            self.send_header(cle, valeur)
        self.send_header("content-length", str(len(donnees)))
        self.end_headers()
        self.wfile.write(donnees)

    def _evenement(self, nom: str, donnees: dict[str, Any]) -> None:
        self.wfile.write(f"event: {nom}\ndata: {json.dumps(donnees)}\n\n".encode())
        self.wfile.flush()

    def _flux(
        self, modele: str, blocs: list[tuple[str, Any]], tokens: dict[str, Any], principal: bool
    ) -> None:
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("connection", "close")
        self.end_headers()
        ident = f"msg_{compteur['appels']}"
        message: dict[str, Any] = {"id": ident, "type": "message", "role": "assistant"}
        debut = message | {
            "model": modele,
            "content": [],
            "stop_reason": None,
            "usage": tokens | {"output_tokens": 1},
        }
        self._evenement("message_start", {"type": "message_start", "message": debut})
        if MODE == "lent" and principal:
            try:
                for _ in range(1200):
                    time.sleep(0.05)
                    self._evenement("ping", {"type": "ping"})
            except BrokenPipeError, ConnectionResetError:
                return
        for i, (genre, valeur) in enumerate(blocs):
            bloc: dict[str, Any]
            if genre == "text":
                bloc = {"type": "text", "text": ""}
                delta = {"type": "text_delta", "text": valeur}
            else:
                bloc = {
                    "type": "tool_use",
                    "id": f"toolu_{ident}",
                    "name": "mcp__neo4j__read-cypher",
                    "input": {},
                }
                delta = {"type": "input_json_delta", "partial_json": json.dumps(valeur)}
            self._evenement(
                "content_block_start",
                {"type": "content_block_start", "index": i, "content_block": bloc},
            )
            self._evenement(
                "content_block_delta", {"type": "content_block_delta", "index": i, "delta": delta}
            )
            self._evenement("content_block_stop", {"type": "content_block_stop", "index": i})
        fin = "tool_use" if any(genre == "tool_use" for genre, _ in blocs) else "end_turn"
        sortie = {k: v for k, v in tokens.items() if k != "cache_creation"}
        sortie["output_tokens_details"] = {"thinking_tokens": 7}
        self._evenement(
            "message_delta",
            {"type": "message_delta", "delta": {"stop_reason": fin}, "usage": sortie},
        )
        self._evenement("message_stop", {"type": "message_stop"})


serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestion)
print(serveur.server_address[1], flush=True)
serveur.serve_forever()
