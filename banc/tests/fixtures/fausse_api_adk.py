"""Fausse API pour tests/test_cellule_adk.py : l'API Anthropic (flux SSE de /v1/messages) et Vertex
(streamGenerateContent), plus le point de jeton OAuth d'une ADC factice, sur 127.0.0.1.

Usage : fausse_api_adk.py <scenario.json> <journal.jsonl>. Écrit son port sur stdout, puis répond à
chaque appel du modèle par l'étape suivante du scénario (une liste, prise dans l'ordre, quel que
soit le protocole) et note chaque requête (chemin, en-têtes sans la clé ni le jeton, corps).

Étape réussie : {"blocs": [["reflexion", texte] | ["texte", texte] | ["outil", arguments, nom?],
...], "usage": {"entree", "sortie", "ecrit", "lu", "reflexion", "outil"}, "lent_s": secondes}. La
sortie comprend la réflexion, comme output_tokens d'Anthropic (Vertex la sépare :
candidatesTokenCount n'en a que le reste) ; Vertex n'écrit pas en cache (cache implicite). L'outil
appelé est read-cypher, sauf nom donné. Avec lent_s, le flux s'ouvre (message_start, ou un premier
morceau sans contenu), puis plus rien pendant lent_s : l'échéance de la cellule tombe.

Variantes d'une étape : « sans_usage » (Vertex répond sans usageMetadata), « sans_contenu » (par un
candidat sans « content »), « illisible » (par un morceau qui n'est pas du JSON), « fin » (sa raison
de fin, STOP par défaut) ; « erreur_flux » (l'API Anthropic annonce cette erreur dans le flux
ouvert), « coupure » (la connexion se ferme après message_start). Étape en erreur : {"statut": code
HTTP, "type": type d'erreur, "message": texte, "retry_after_s": en-tête retry-after}. Scénario
épuisé : 400, que la cellule traite en erreur technique.

Au niveau du scénario : « jeton_s » (délai du point de jeton), « jeton_refuse » (il refuse l'ADC,
invalid_grant), « jeton_statut » (il répond ce statut d'erreur ; à 503, google-auth reprend, puis
lève une erreur passagère).
"""

import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCENARIO = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
JOURNAL = Path(sys.argv[2])
VERROU = threading.Lock()
etat = {"etape": 0}
# Statut Vertex de chaque code d'erreur, tel que l'API le nomme.
STATUTS_VERTEX = {400: "INVALID_ARGUMENT", 403: "PERMISSION_DENIED", 429: "RESOURCE_EXHAUSTED"}


def etape_suivante() -> dict[str, Any] | None:
    with VERROU:
        etapes = SCENARIO["etapes"]
        if etat["etape"] >= len(etapes):
            return None
        etat["etape"] += 1
        etape: dict[str, Any] = etapes[etat["etape"] - 1]
        return etape


class Gestion(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:
        """Silence : le journal suffit."""

    def do_POST(self) -> None:
        brut = self.rfile.read(int(self.headers.get("content-length", 0)))
        if self.path.startswith("/token"):
            self._noter(brut.decode())
            time.sleep(SCENARIO.get("jeton_s", 0))
            if "jeton_statut" in SCENARIO:
                self._json(SCENARIO["jeton_statut"], {"error": "temporarily_unavailable"})
                return
            if SCENARIO.get("jeton_refuse"):
                self._json(400, {"error": "invalid_grant", "error_description": "refusé"})
                return
            jeton = {"access_token": "jeton-factice", "expires_in": 3600, "token_type": "Bearer"}
            self._json(200, jeton)
            return
        corps = json.loads(brut or b"{}")
        self._noter(corps)
        etape = etape_suivante()
        anthropic = self.path.startswith("/v1/messages")
        if etape is None:
            etape = {"statut": 400, "type": "invalid_request_error", "message": "scénario épuisé"}
        if "statut" in etape:
            self._erreur(etape, anthropic)
        elif anthropic:
            self._anthropic(corps, etape)
        else:
            self._vertex(etape)

    def _noter(self, corps: Any) -> None:
        caches = {"x-api-key", "authorization"}
        entetes = {cle: valeur for cle, valeur in self.headers.items() if cle.lower() not in caches}
        note = {"t": time.monotonic(), "chemin": self.path, "entetes": entetes, "corps": corps}
        with VERROU, JOURNAL.open("a", encoding="utf-8") as flux:
            flux.write(json.dumps(note, ensure_ascii=False) + "\n")

    def _json(self, code: int, objet: Any, attente_s: float | None = None) -> None:
        donnees = json.dumps(objet).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(donnees)))
        if attente_s is not None:
            self.send_header("retry-after", str(attente_s))
        elif code == 429 or code >= 500:
            # Le SDK Anthropic reprend après ce délai : des tests rapides.
            self.send_header("retry-after-ms", "10")
        self.end_headers()
        self.wfile.write(donnees)

    def _erreur(self, etape: dict[str, Any], anthropic: bool) -> None:
        code, attente_s = etape["statut"], etape.get("retry_after_s")
        if anthropic:
            erreur = {"type": etape.get("type", "api_error"), "message": etape.get("message", "?")}
            self._json(code, {"type": "error", "error": erreur}, attente_s)
        else:
            statut = STATUTS_VERTEX.get(
                code, "UNAVAILABLE" if code >= 500 else "FAILED_PRECONDITION"
            )
            erreur = {"code": code, "message": etape.get("message", "?"), "status": statut}
            self._json(code, {"error": erreur}, attente_s)

    def _ouvrir_flux(self) -> None:
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("connection", "close")
        self.end_headers()

    def _attendre(self, etape: dict[str, Any], ping: bytes | None) -> bool:
        """Flux ouvert, plus rien pendant lent_s ; False si le client a coupé. Vertex n'a pas de
        ping (google-genai ne lit pas un commentaire SSE) : le flux se tait."""
        fin = time.monotonic() + etape.get("lent_s", 0)
        try:
            while time.monotonic() < fin:
                time.sleep(0.05)
                if ping is not None:
                    self.wfile.write(ping)
                    self.wfile.flush()
        except BrokenPipeError, ConnectionResetError:
            return False
        return True

    # --- API Anthropic -------------------------------------------------------------------------

    def _evenement(self, nom: str, donnees: dict[str, Any]) -> None:
        self.wfile.write(f"event: {nom}\ndata: {json.dumps(donnees)}\n\n".encode())
        self.wfile.flush()

    def _anthropic(self, corps: dict[str, Any], etape: dict[str, Any]) -> None:
        usage = etape.get("usage", {})
        une_heure = '"ttl": "1h"' in json.dumps(corps)
        ecrit = usage.get("ecrit", 0)
        debut = {
            "input_tokens": usage.get("entree", 0),
            "output_tokens": 1,
            "cache_creation_input_tokens": ecrit,
            "cache_read_input_tokens": usage.get("lu", 0),
            "cache_creation": {
                "ephemeral_5m_input_tokens": 0 if une_heure else ecrit,
                "ephemeral_1h_input_tokens": ecrit if une_heure else 0,
            },
        }
        with VERROU:
            ident = f"msg_{etat['etape']}"
        message = {"id": ident, "type": "message", "role": "assistant", "model": corps["model"]}
        message |= {"content": [], "stop_reason": None, "usage": debut}
        if etape.get("coupure"):
            self._couper({"type": "message_start", "message": message})
            return
        self._ouvrir_flux()
        self._evenement("message_start", {"type": "message_start", "message": message})
        if etape.get("erreur_flux"):
            erreur = {"type": etape["erreur_flux"], "message": "Overloaded"}
            self._evenement("error", {"type": "error", "error": erreur})
            return
        if not self._attendre(etape, b'event: ping\ndata: {"type": "ping"}\n\n'):
            return
        outil = False
        for i, (genre, valeur, *nom) in enumerate(etape.get("blocs", [])):
            bloc: dict[str, Any]
            if genre == "reflexion":
                bloc = {"type": "thinking", "thinking": "", "signature": ""}
                deltas = [
                    {"type": "thinking_delta", "thinking": valeur},
                    {"type": "signature_delta", "signature": f"signature-{ident}-{i}"},
                ]
            elif genre == "texte":
                bloc = {"type": "text", "text": ""}
                deltas = [{"type": "text_delta", "text": valeur}]
            else:
                outil = True
                bloc = {
                    "type": "tool_use",
                    "id": f"toolu_{ident}_{i}",
                    "name": nom[0] if nom else "read-cypher",
                    "input": {},
                }
                deltas = [{"type": "input_json_delta", "partial_json": json.dumps(valeur)}]
            debut_bloc = {"type": "content_block_start", "index": i, "content_block": bloc}
            self._evenement("content_block_start", debut_bloc)
            for delta in deltas:
                corps_delta = {"type": "content_block_delta", "index": i, "delta": delta}
                self._evenement("content_block_delta", corps_delta)
            self._evenement("content_block_stop", {"type": "content_block_stop", "index": i})
        sortie = {
            "output_tokens": usage.get("sortie", 0),
            "output_tokens_details": {"thinking_tokens": usage.get("reflexion", 0)},
        }
        fin = {"stop_reason": "tool_use" if outil else "end_turn", "stop_sequence": None}
        self._evenement("message_delta", {"type": "message_delta", "delta": fin, "usage": sortie})
        self._evenement("message_stop", {"type": "message_stop"})

    def _couper(self, debut: dict[str, Any]) -> None:
        """Un flux en morceaux (chunked, comme l'API) coupé après message_start : la connexion se
        ferme avant le morceau final, une erreur de protocole pour le client."""
        self.send_response(200)
        self.send_header("content-type", "text/event-stream")
        self.send_header("transfer-encoding", "chunked")
        self.end_headers()
        donnees = f"event: message_start\ndata: {json.dumps(debut)}\n\n".encode()
        self.wfile.write(f"{len(donnees):x}\r\n".encode() + donnees + b"\r\n")
        self.wfile.flush()
        time.sleep(0.1)
        self.connection.shutdown(socket.SHUT_RDWR)
        self.close_connection = True

    # --- Vertex ----------------------------------------------------------------------------------

    def _morceau(self, donnees: dict[str, Any]) -> None:
        self.wfile.write(f"data: {json.dumps(donnees)}\r\n\r\n".encode())
        self.wfile.flush()

    def _vertex(self, etape: dict[str, Any]) -> None:
        usage = etape.get("usage", {})
        meta = {
            "promptTokenCount": usage.get("entree", 0) + usage.get("lu", 0),
            "candidatesTokenCount": usage.get("sortie", 0) - usage.get("reflexion", 0),
            "thoughtsTokenCount": usage.get("reflexion", 0),
            "totalTokenCount": usage.get("entree", 0) + usage.get("lu", 0) + usage.get("sortie", 0),
        }
        if usage.get("lu"):
            meta["cachedContentTokenCount"] = usage["lu"]
        if usage.get("outil"):
            meta["toolUsePromptTokenCount"] = usage["outil"]
        self._ouvrir_flux()
        if etape.get("illisible"):
            self.wfile.write(b"data: pas du JSON\r\n\r\n")
            self.wfile.flush()
            return
        if etape.get("lent_s"):
            premier = {"candidates": [{"content": {"role": "model", "parts": [{"text": ""}]}}]}
            self._morceau(
                premier | {"usageMetadata": {"promptTokenCount": meta["promptTokenCount"]}}
            )
            if not self._attendre(etape, None):
                return
        parties: list[dict[str, Any]] = []
        for genre, valeur, *nom in etape.get("blocs", []):
            if genre == "reflexion":
                parties.append({"text": valeur, "thought": True})
            elif genre == "texte":
                parties.append({"text": valeur})
            else:
                appel = {"name": nom[0] if nom else "read-cypher", "args": valeur}
                parties.append({"functionCall": appel})
        contenu = {"role": "model", "parts": parties}
        candidat = {"content": contenu, "finishReason": etape.get("fin", "STOP"), "index": 0}
        if etape.get("sans_contenu"):
            del candidat["content"]
        morceau = {"candidates": [candidat], "modelVersion": "gemini-3.8-flash"}
        self._morceau(morceau if etape.get("sans_usage") else morceau | {"usageMetadata": meta})


serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestion)
print(serveur.server_address[1], flush=True)
serveur.serve_forever()
