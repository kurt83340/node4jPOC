"""Tests de la coupure de Vertex : sans réseau, un faux serveur local tient le rôle du serveur de
métadonnées de Cloud Run et de l'API Service Usage."""

import base64
import io
import json
import logging
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

import pytest
from cloudevents.http import CloudEvent

import main
from main import AUTRE_BUDGET, COUPE, DEJA_COUPE, SOUS_LE_PLAFOND, ErreurCoupure, traiter

PROJET = "projet-essai"
BUDGET = "de72f49d-779b-4945-a127-4d6ce8def0bb"
SERVICE = f"/su/projects/{PROJET}/services/aiplatform.googleapis.com"
JETON = "/md/instance/service-accounts/default/token"


@dataclass
class Google:
    """Ce que le faux serveur répondra, et les requêtes qu'il a reçues."""

    etat: str = "ENABLED"
    # Réponse à :disable ; None : 200, et l'état passe à DISABLED.
    refus: tuple[int, dict[str, Any]] | None = None
    # État après un refus de :disable (un autre message a coupé Vertex entre-temps).
    etat_apres_refus: str | None = None
    jeton: int = 200
    lecture: int = 200
    recues: list[tuple[str, str, Any]] = field(default_factory=list)


@pytest.fixture
def google(monkeypatch: pytest.MonkeyPatch) -> Iterator[Google]:
    reglage = Google()

    class Gestionnaire(BaseHTTPRequestHandler):
        def log_message(self, *_: Any) -> None:
            pass

        def _repondre(self, statut: int, corps: dict[str, Any]) -> None:
            brut = json.dumps(corps).encode()
            self.send_response(statut)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(brut)))
            self.end_headers()
            self.wfile.write(brut)

        def _noter(self) -> None:
            longueur = int(self.headers.get("Content-Length") or 0)
            corps = json.loads(self.rfile.read(longueur)) if longueur else None
            reglage.recues.append((self.command, self.path, corps))

        def _autorise(self) -> bool:
            if self.headers.get("Authorization") == "Bearer jeton-factice":
                return True
            self._repondre(401, {"error": {"status": "UNAUTHENTICATED"}})
            return False

        def do_GET(self) -> None:
            self._noter()
            if self.path == JETON:
                if self.headers.get("Metadata-Flavor") != "Google":
                    self._repondre(403, {})
                elif reglage.jeton != 200:
                    self._repondre(reglage.jeton, {})
                else:
                    self._repondre(200, {"access_token": "jeton-factice", "expires_in": 3599})
            elif self.path == SERVICE:
                if not self._autorise():
                    return
                if reglage.lecture != 200:
                    erreur = {"status": "PERMISSION_DENIED", "message": "refusé"}
                    self._repondre(reglage.lecture, {"error": erreur})
                else:
                    self._repondre(200, {"name": SERVICE, "state": reglage.etat})
            else:
                self._repondre(404, {})

        def do_POST(self) -> None:
            self._noter()
            if self.path != f"{SERVICE}:disable":
                self._repondre(404, {})
            elif not self._autorise():
                return
            elif reglage.refus is not None:
                if reglage.etat_apres_refus:
                    reglage.etat = reglage.etat_apres_refus
                self._repondre(*reglage.refus)
            else:
                reglage.etat = "DISABLED"
                self._repondre(200, {"name": "operations/acat.p2-1", "done": False})

    serveur = ThreadingHTTPServer(("127.0.0.1", 0), Gestionnaire)
    fil = threading.Thread(
        target=serveur.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True
    )
    fil.start()
    base = f"http://127.0.0.1:{serveur.server_address[1]}"
    monkeypatch.setattr(main, "METADONNEES", f"{base}/md")
    monkeypatch.setattr(main, "SERVICE_USAGE", f"{base}/su")
    try:
        yield reglage
    finally:
        serveur.shutdown()
        serveur.server_close()


@pytest.fixture
def sortie(monkeypatch: pytest.MonkeyPatch) -> io.StringIO:
    """Ce que le journal de la fonction écrit sur stdout, une ligne JSON par entrée."""
    flux = io.StringIO()
    # pytest 9 ajoute ses propres collecteurs aux journaux qui ne remontent pas à la racine.
    (gestionnaire,) = (
        g for g in main.journal.handlers if isinstance(g.formatter, main.FormatCloudLogging)
    )
    monkeypatch.setattr(gestionnaire, "stream", flux)
    return flux


def derniere(sortie: io.StringIO) -> dict[str, Any]:
    entree: dict[str, Any] = json.loads(sortie.getvalue().strip().splitlines()[-1])
    return entree


def contenu(cout: Any = 100.0, montant: Any = 100.0) -> dict[str, Any]:
    return {
        "budgetDisplayName": "Plafond jleroy-labo 100 EUR (oct-dec 2026)",
        "costAmount": cout,
        "costIntervalStart": "2026-10-01T07:00:00Z",
        "budgetAmount": montant,
        "budgetAmountType": "SPECIFIED_AMOUNT",
        "currencyCode": "EUR",
    }


def message(
    cout: Any = 100.0, montant: Any = 100.0, budget: str = BUDGET, brut: bytes | None = None
) -> dict[str, Any]:
    """Les données d'un événement Pub/Sub d'Eventarc, au format 1.0 des notifications de budget."""
    donnees = brut if brut is not None else json.dumps(contenu(cout, montant)).encode()
    attributs = {"billingAccountId": "019774-B0D77F-72CED7", "budgetId": budget}
    return {
        "message": {
            "data": base64.b64encode(donnees).decode(),
            "attributes": attributs | {"schemaVersion": "1.0"},
        }
    }


def appels(google: Google) -> list[tuple[str, str]]:
    return [(methode, chemin) for methode, chemin, _ in google.recues]


def test_sous_le_plafond_aucun_appel(google: Google) -> None:
    assert traiter(message(cout=99.99), PROJET, BUDGET) == SOUS_LE_PLAFOND
    assert google.recues == []


def test_autre_budget_ignore(google: Google) -> None:
    # Au-delà de son plafond, mais d'un autre budget : rien.
    assert traiter(message(cout=500, budget="autre"), PROJET, BUDGET) == AUTRE_BUDGET
    assert google.recues == []


def test_plafond_atteint_pile_coupe(google: Google) -> None:
    assert traiter(message(cout=100.0, montant=100.0), PROJET, BUDGET) == COUPE
    assert appels(google) == [("GET", JETON), ("GET", SERVICE), ("POST", f"{SERVICE}:disable")]
    corps = google.recues[-1][2]
    assert corps == {"disableDependentServices": False, "checkIfServiceHasUsage": "SKIP"}
    assert google.etat == "DISABLED"


def test_montants_en_texte(google: Google) -> None:
    # Les exemples de la doc mettent parfois les montants entre guillemets.
    assert traiter(message(cout="99.99", montant="100"), PROJET, BUDGET) == SOUS_LE_PLAFOND
    assert traiter(message(cout="100.01", montant="100"), PROJET, BUDGET) == COUPE


def test_deja_coupe_sans_desactiver(google: Google) -> None:
    google.etat = "DISABLED"
    assert traiter(message(cout=120), PROJET, BUDGET) == DEJA_COUPE
    assert appels(google) == [("GET", JETON), ("GET", SERVICE)]


def test_messages_repetes_une_seule_desactivation(google: Google) -> None:
    issues = [traiter(message(cout=cout), PROJET, BUDGET) for cout in (50, 100, 150, 150)]
    assert issues == [SOUS_LE_PLAFOND, COUPE, DEJA_COUPE, DEJA_COUPE]
    assert appels(google).count(("POST", f"{SERVICE}:disable")) == 1
    # Jamais de réactivation, ni d'autre service.
    assert all(chemin in {JETON, SERVICE, f"{SERVICE}:disable"} for _, chemin in appels(google))


def test_coupe_entre_lecture_et_appel(google: Google) -> None:
    # Refus « déjà désactivé », que l'état relu confirme : succès.
    refus = {"error": {"status": "FAILED_PRECONDITION", "message": "déjà désactivé"}}
    google.refus, google.etat_apres_refus = (400, refus), "DISABLED"
    assert traiter(message(), PROJET, BUDGET) == COUPE
    assert appels(google)[-1] == ("GET", SERVICE)


def test_services_dependants_refus_en_erreur(google: Google) -> None:
    # Refus, et Vertex toujours actif (un service activé en dépend) : erreur, rien n'est coupé.
    refus = {"error": {"status": "FAILED_PRECONDITION", "message": "dépendants activés"}}
    google.refus = (400, refus)
    with pytest.raises(ErreurCoupure, match="FAILED_PRECONDITION dépendants activés"):
        traiter(message(), PROJET, BUDGET)
    assert google.etat == "ENABLED"


def test_refus_de_desactiver(google: Google) -> None:
    google.refus = (403, {"error": {"status": "PERMISSION_DENIED", "message": "non"}})
    with pytest.raises(ErreurCoupure, match=r"refusée \(403\) : PERMISSION_DENIED non"):
        traiter(message(), PROJET, BUDGET)


def test_etat_illisible(google: Google) -> None:
    google.lecture = 403
    with pytest.raises(ErreurCoupure, match=r"état de aiplatform.googleapis.com illisible \(403\)"):
        traiter(message(), PROJET, BUDGET)


def test_jeton_refuse(google: Google) -> None:
    google.jeton = 500
    with pytest.raises(ErreurCoupure, match=r"jeton refusé par le serveur de métadonnées \(500\)"):
        traiter(message(), PROJET, BUDGET)
    assert appels(google) == [("GET", JETON)]


def test_metadonnees_injoignables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "METADONNEES", "http://127.0.0.1:9/md")
    with pytest.raises(ErreurCoupure, match=r"GET http://127\.0\.0\.1:9/md/.* injoignable"):
        traiter(message(), PROJET, BUDGET)


@pytest.mark.parametrize(
    ("donnees", "cause"),
    [
        ({}, "KeyError"),
        ({"message": {"attributes": {"budgetId": BUDGET}}}, "KeyError"),
        ({"message": {"data": "pas du base64 !", "attributes": {"budgetId": BUDGET}}}, "Error"),
        (message(brut=b"{pas du json"), "JSONDecodeError"),
        (message(brut=b"{}"), "KeyError"),
        ({"message": {"data": message()["message"]["data"]}}, "KeyError"),
        (message(cout="beaucoup"), "InvalidOperation"),
    ],
    ids=["vide", "sans-data", "pas-base64", "pas-json", "sans-champs", "sans-budget", "cout"],
)
def test_message_illisible(google: Google, donnees: dict[str, Any], cause: str) -> None:
    with pytest.raises(ErreurCoupure, match=f"notification illisible : {cause}"):
        traiter(donnees, PROJET, BUDGET)
    assert google.recues == []


def evenement(donnees: dict[str, Any]) -> CloudEvent:
    attributs = {
        "type": "google.cloud.pubsub.topic.v1.messagePublished",
        "source": "//pubsub.googleapis.com/projects/projet-essai/topics/coupure-vertex",
    }
    return CloudEvent(attributs, donnees)


@pytest.fixture
def configuree(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJET", PROJET)
    monkeypatch.setenv("BUDGET_ID", BUDGET)


@pytest.mark.usefixtures("configuree")
def test_point_d_entree_coupe_et_journalise(google: Google, sortie: io.StringIO) -> None:
    main.coupure(evenement(message(cout=104.5)))
    entree = derniere(sortie)
    # L'entrée qui déclenche l'alerte « Vertex coupé » (alerte-coupure.json).
    assert entree["severity"] == "WARNING"
    assert entree["evenement"] == "vertex-coupe"
    assert entree["message"] == "Vertex coupé sur projet-essai : 104.5 EUR dépensés sur 100.0 EUR"


@pytest.mark.usefixtures("configuree")
def test_point_d_entree_sous_le_plafond(google: Google, sortie: io.StringIO) -> None:
    main.coupure(evenement(message(cout=12.34)))
    entree = derniere(sortie)
    assert entree["severity"] == "INFO"
    assert entree["message"] == "sous le plafond : 12.34 EUR dépensés sur 100.0 EUR"
    assert "evenement" not in entree


@pytest.mark.usefixtures("configuree")
def test_point_d_entree_erreur_journalisee_puis_relevee(
    google: Google, sortie: io.StringIO
) -> None:
    google.lecture = 500
    with pytest.raises(ErreurCoupure):
        main.coupure(evenement(message()))
    entree = derniere(sortie)
    assert entree["severity"] == "ERROR"
    assert entree["message"].startswith("coupure de Vertex en échec : état de")


def test_point_d_entree_sans_configuration(
    monkeypatch: pytest.MonkeyPatch, sortie: io.StringIO
) -> None:
    monkeypatch.delenv("PROJET", raising=False)
    monkeypatch.setenv("BUDGET_ID", BUDGET)
    with pytest.raises(KeyError):
        main.coupure(evenement(message()))
    assert derniere(sortie)["severity"] == "ERROR"


def test_journal_isole() -> None:
    # Une seule ligne JSON par entrée : le journal ne remonte pas à la racine.
    assert main.journal.propagate is False
    assert main.journal.level == logging.INFO
