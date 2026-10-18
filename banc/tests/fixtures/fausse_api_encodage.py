"""Fausse API Vertex pour tests/test_encodage.py : le point :predict de gemini-embedding-001 et le
point de jeton OAuth d'une ADC factice, sur 127.0.0.1.

Usage : fausse_api_encodage.py <scenario.json> <journal.jsonl>. Écrit son port sur stdout, puis
répond à chaque :predict par l'étape suivante du scénario, prise dans l'ordre, et note chaque
requête (chemin, en-têtes sans le jeton, corps).

Étape réussie : {"dimensions": 3072, "jetons": 13, "tronque": false, "lent_s": secondes} ;
« sans_statistiques » retire les statistiques de la prédiction. Le vecteur vaut partout un nombre
tiré du texte : un même texte, un même vecteur. Étape en erreur : {"statut": code HTTP, "message":
texte}. Scénario épuisé : 400. Au niveau du scénario, « jeton_refuse » : le point de jeton refuse
l'ADC (invalid_grant).
"""

import json
import sys
import threading
import time
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

SCENARIO = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
JOURNAL = Path(sys.argv[2])
VERROU = threading.Lock()
etat = {"etape": 0}
STATUTS = {400: "INVALID_ARGUMENT", 403: "PERMISSION_DENIED", 429: "RESOURCE_EXHAUSTED"}


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
        longueur = int(self.headers.get("content-length", 0))
        brut = self.rfile.read(longueur)
        if self.path.startswith("/token"):
            if SCENARIO.get("jeton_refuse"):
                self._json(400, {"error": "invalid_grant", "error_description": "refusée"})
            else:
                jeton = {"access_token": "jeton-factice", "expires_in": 3600}
                self._json(200, jeton | {"token_type": "Bearer"})
            return
        corps = json.loads(brut)
        entetes = {cle.lower(): valeur for cle, valeur in self.headers.items()}
        if "authorization" in entetes:
            entetes["authorization"] = entetes["authorization"].split(" ")[0] + " ‹jeton›"
        with VERROU, JOURNAL.open("a", encoding="utf-8") as journal:
            note = {"t": time.monotonic(), "chemin": self.path, "entetes": entetes, "corps": corps}
            journal.write(json.dumps(note, ensure_ascii=False) + "\n")
        etape = etape_suivante()
        if etape is None:
            self._erreur(400, "scénario épuisé")
            return
        if "statut" in etape:
            self._erreur(etape["statut"], etape.get("message", "erreur"))
            return
        time.sleep(etape.get("lent_s", 0))
        texte = corps["instances"][0]["content"]
        valeur = zlib.crc32(texte.encode("utf-8")) / 2**32
        prediction: dict[str, Any] = {"values": [valeur] * etape.get("dimensions", 3072)}
        if not etape.get("sans_statistiques"):
            statistiques = {"token_count": etape.get("jetons", 13), "truncated": False}
            prediction["statistics"] = statistiques | {"truncated": etape.get("tronque", False)}
        self._json(200, {"predictions": [{"embeddings": prediction}]})

    def _erreur(self, statut: int, message: str) -> None:
        etat_vertex = STATUTS.get(statut, "INTERNAL")
        self._json(statut, {"error": {"code": statut, "message": message, "status": etat_vertex}})

    def _json(self, code: int, objet: Any) -> None:
        corps = json.dumps(objet).encode("utf-8")
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(corps)))
        self.end_headers()
        self.wfile.write(corps)


serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestion)
print(serveur.server_address[1], flush=True)
serveur.serve_forever()
