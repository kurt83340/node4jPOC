"""Tests du réveil d'Aura : sans réseau, une fausse Query API locale tient le rôle d'Aura."""

import base64
import json
import logging
import re
import socket
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

import reveil
from reveil import EcartReveil, ErreurReveil, Identifiants

# Même forme que le fichier téléchargé depuis la console Aura (valeurs factices).
FICHIER_AURA = (
    "# Wait 60 seconds before connecting using these details, or login to https://console.neo4j.io\r\n"
    "NEO4J_URI=neo4j+s://abcd1234.databases.neo4j.io\r\n"
    "NEO4J_USERNAME=abcd1234\r\n"
    "NEO4J_PASSWORD=faux-mot-de-passe\r\n"
    "NEO4J_DATABASE=abcd1234\r\n"
    "AURA_INSTANCEID=abcd1234\r\n"
    "AURA_INSTANCENAME=Free instance\r\n"
)
IDENTIFIANTS = Identifiants(
    uri="neo4j+s://abcd1234.databases.neo4j.io",
    utilisateur="abcd1234",
    mot_de_passe="faux-mot-de-passe",
    base="abcd1234",
)
REPONSE_OK = b'{"data": {"fields": ["reveil"], "values": [[1]]}, "bookmarks": ["FB:x"]}'


@dataclass
class Echange:
    """Ce que la fausse Aura renverra, et ce qu'elle a reçu."""

    statut: int = 202
    corps: bytes = REPONSE_OK
    attente_s: float = 0.0
    recu: dict[str, Any] = field(default_factory=dict)


class ServeurSilencieux(ThreadingHTTPServer):
    """Serveur de test qui ne trace pas les clients partis avant la réponse (test du délai)."""

    def handle_error(self, request: Any, client_address: Any) -> None:
        pass


@pytest.fixture
def fausse_aura() -> Iterator[tuple[str, Echange]]:
    """Une Query API locale : renvoie l'URL à interroger et l'échange à régler ou lire."""
    echange = Echange()

    class Gestionnaire(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            longueur = int(self.headers["Content-Length"])
            echange.recu = {
                "chemin": self.path,
                "entetes": dict(self.headers),
                "corps": json.loads(self.rfile.read(longueur)),
            }
            time.sleep(echange.attente_s)
            self.send_response(echange.statut)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(echange.corps)

        def log_message(self, format: str, *args: Any) -> None:
            pass

    serveur = ServeurSilencieux(("127.0.0.1", 0), Gestionnaire)
    threading.Thread(target=serveur.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{serveur.server_port}/db/abcd1234/query/v2", echange
    serveur.shutdown()
    serveur.server_close()


def test_lire_identifiants_garde_les_4_cles_du_fichier_aura() -> None:
    assert reveil.lire_identifiants(FICHIER_AURA) == IDENTIFIANTS


def test_lire_identifiants_nomme_la_cle_absente() -> None:
    sans_mot_de_passe = FICHIER_AURA.replace("NEO4J_PASSWORD=faux-mot-de-passe\r\n", "")
    with pytest.raises(ErreurReveil, match="NEO4J_PASSWORD"):
        reveil.lire_identifiants(sans_mot_de_passe)


def test_repr_des_identifiants_sans_mot_de_passe() -> None:
    assert "faux-mot-de-passe" not in repr(IDENTIFIANTS)


def test_url_query_api_depuis_l_uri_bolt() -> None:
    attendue = "https://abcd1234.databases.neo4j.io/db/abcd1234/query/v2"
    assert reveil.url_query_api(IDENTIFIANTS) == attendue


def test_url_query_api_refuse_une_uri_sans_tls() -> None:
    locale = Identifiants("neo4j://localhost:7687", "neo4j", "x", "neo4j")
    with pytest.raises(ErreurReveil, match="neo4j\\+s"):
        reveil.url_query_api(locale)


def test_envoyer_poste_return_1_en_lecture_seule(fausse_aura: tuple[str, Echange]) -> None:
    url, echange = fausse_aura
    assert reveil.envoyer(url, IDENTIFIANTS, delai_s=5) == REPONSE_OK
    jeton = base64.b64encode(b"abcd1234:faux-mot-de-passe").decode()
    assert echange.recu["chemin"] == "/db/abcd1234/query/v2"
    assert echange.recu["entetes"]["Authorization"] == f"Basic {jeton}"
    assert echange.recu["corps"] == {"statement": "RETURN 1 AS reveil", "accessMode": "Read"}


def test_envoyer_rapporte_un_refus_d_authentification(fausse_aura: tuple[str, Echange]) -> None:
    url, echange = fausse_aura
    echange.statut = 401
    echange.corps = b'{"errors": [{"code": "Neo.ClientError.Security.Unauthorized"}]}'
    attendu = re.escape("HTTP 401 Neo.ClientError.Security.Unauthorized")
    with pytest.raises(ErreurReveil, match=attendu) as exc:
        reveil.envoyer(url, IDENTIFIANTS, delai_s=5)
    assert exc.value.code == 2


def test_envoyer_rapporte_une_aura_injoignable() -> None:
    with socket.socket() as libre:
        libre.bind(("127.0.0.1", 0))
        port = libre.getsockname()[1]
    with pytest.raises(ErreurReveil, match="Aura injoignable"):
        reveil.envoyer(f"http://127.0.0.1:{port}/db/x/query/v2", IDENTIFIANTS, delai_s=5)


def test_envoyer_abandonne_apres_le_delai(fausse_aura: tuple[str, Echange]) -> None:
    url, echange = fausse_aura
    echange.attente_s = 1.0
    with pytest.raises(ErreurReveil, match="Aura injoignable"):
        reveil.envoyer(url, IDENTIFIANTS, delai_s=0.2)


def test_analyser_accepte_la_valeur_1() -> None:
    reveil.analyser(REPONSE_OK)


def test_analyser_rapporte_une_erreur_cypher_recue_en_202() -> None:
    corps = b'{"errors": [{"code": "Neo.ClientError.Statement.SyntaxError", "message": "x"}]}'
    with pytest.raises(ErreurReveil, match=re.escape("Statement.SyntaxError")) as exc:
        reveil.analyser(corps)
    assert exc.value.code == 2


def test_analyser_signale_un_ecart_sur_une_autre_valeur() -> None:
    with pytest.raises(EcartReveil, match=r"\[\[2\]\]") as exc:
        reveil.analyser(b'{"data": {"fields": ["reveil"], "values": [[2]]}}')
    assert exc.value.code == 1


def test_analyser_refuse_une_reponse_qui_n_est_pas_du_json() -> None:
    with pytest.raises(ErreurReveil, match="illisible"):
        reveil.analyser(b"<html>502 Bad Gateway</html>")


def test_masquer_remplace_tout_message_qui_contient_le_mot_de_passe() -> None:
    message = reveil.masquer("échec pour abcd1234:faux-mot-de-passe", IDENTIFIANTS)
    assert message == "message masqué : il contenait le mot de passe"


def test_masquer_remplace_l_identifiant_de_l_instance() -> None:
    message = reveil.masquer("hôte abcd1234.databases.neo4j.io injoignable", IDENTIFIANTS)
    assert message == "hôte ‹instance›.databases.neo4j.io injoignable"


def test_format_cloud_logging_ecrit_une_ligne_json() -> None:
    entree = logging.LogRecord("reveil-aura", logging.ERROR, __file__, 1, "échec", None, None)
    entree.champs = {"code_retour": 2}
    ligne = reveil.FormatCloudLogging().format(entree)
    assert "\n" not in ligne
    assert json.loads(ligne) == {"severity": "ERROR", "message": "échec", "code_retour": 2}


def test_main_journalise_le_succes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    fichier = tmp_path / "identifiants"
    fichier.write_text(FICHIER_AURA, encoding="utf-8")
    monkeypatch.setenv("FICHIER_IDENTIFIANTS", str(fichier))
    monkeypatch.setattr(reveil, "envoyer", lambda url, identifiants, delai_s: REPONSE_OK)
    with caplog.at_level(logging.INFO, logger="reveil-aura"):
        assert reveil.main() == 0
    assert [e.levelname for e in caplog.records] == ["INFO"]
    assert caplog.records[0].getMessage().startswith("Aura répond à RETURN 1 AS reveil en ")


def test_main_sort_en_2_sans_fichier_d_identifiants(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("FICHIER_IDENTIFIANTS", str(tmp_path / "absent"))
    assert reveil.main() == 2
    assert [e.levelname for e in caplog.records] == ["ERROR"]
    assert "identifiants illisibles" in caplog.records[0].getMessage()


def test_main_masque_l_instance_dans_le_journal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    fichier = tmp_path / "identifiants"
    fichier.write_text(FICHIER_AURA, encoding="utf-8")
    monkeypatch.setenv("FICHIER_IDENTIFIANTS", str(fichier))

    def injoignable(url: str, identifiants: Identifiants, delai_s: float) -> bytes:
        raise ErreurReveil(f"Aura injoignable ({url})")

    monkeypatch.setattr(reveil, "envoyer", injoignable)
    assert reveil.main() == 2
    message = caplog.records[0].getMessage()
    assert "abcd1234" not in message
    assert "‹instance›.databases.neo4j.io" in message
