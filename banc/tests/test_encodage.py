"""Encodage des messages (spec 003, plan D5) : banc.encodage, le vrai google-genai 2.28.0 contre une
fausse API Vertex (tests/fixtures/fausse_api_encodage.py) et une ADC factice, sans réseau.

Relevé sur le vrai client (T8.1) : gemini-embedding-001 passe par :predict, pas :embedContent ;
corps {"instances": [{"content", "task_type"}], "parameters": {"outputDimensionality"}} ; le projet
de quota part dans l'en-tête x-goog-user-project ; un 429 est repris ; token_count arrive en float.
"""

import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path
from typing import Any

import google.auth
import google.auth.credentials
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from banc.encodage import DOCUMENT, Encodage, EncodageError, encoder

FIXTURES = Path(__file__).parent / "fixtures"
# Les valeurs de D5, écrites en clair : un réglage changé dans le module ne change pas l'attendu.
CHEMIN = (
    "/v1beta1/projects/jleroy-labo/locations/europe-west1/publishers/google/models/"
    "gemini-embedding-001:predict"
)
ETAPE: dict[str, Any] = {"dimensions": 3072, "jetons": 13}
PHRASE = "Une phrase maison, hors du banc."

type Vertex = Callable[..., AbstractContextManager[Path]]


@pytest.fixture(scope="module")
def cle_adc() -> str:
    """Clé privée d'un compte de service factice : l'ADC, signée puis échangée contre un jeton
    auprès de la fausse API (token_uri) ; une ADC d'utilisateur irait au vrai point de Google."""
    cle = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = cle.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pem.decode()


@pytest.fixture
def vertex(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cle_adc: str) -> Vertex:
    """Lance la fausse API sur un scénario et y pointe google-genai et l'ADC ; rend le journal."""

    @contextmanager
    def lancer(etapes: list[dict[str, Any]], **reglages: Any) -> Iterator[Path]:
        scenario = tmp_path / "scenario.json"
        scenario.write_text(json.dumps({"etapes": etapes} | reglages))
        journal = tmp_path / "api.jsonl"
        journal.touch()
        api = FIXTURES / "fausse_api_encodage.py"
        processus = subprocess.Popen(
            [sys.executable, "-I", str(api), str(scenario), str(journal)],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert processus.stdout is not None
            adresse = f"http://127.0.0.1:{processus.stdout.readline().strip()}"
            adc = {
                "type": "service_account",
                "project_id": "jleroy-outils",
                "quota_project_id": "jleroy-outils",
                "private_key_id": "cle-factice",
                "private_key": cle_adc,
                "client_email": "banc@jleroy-outils.iam.gserviceaccount.com",
                "client_id": "1",
                "token_uri": f"{adresse}/token",
            }
            fichier = tmp_path / "application_default_credentials.json"
            fichier.write_text(json.dumps(adc))
            monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(fichier))
            monkeypatch.setenv("GOOGLE_VERTEX_BASE_URL", adresse)
            for nom in ("GOOGLE_API_KEY", "GEMINI_API_KEY", "GOOGLE_CLOUD_QUOTA_PROJECT"):
                monkeypatch.delenv(nom, raising=False)
            yield journal
        finally:
            processus.terminate()
            processus.wait(timeout=10)

    return lancer


def requetes(journal: Path) -> list[dict[str, Any]]:
    return [json.loads(ligne) for ligne in journal.read_text(encoding="utf-8").splitlines()]


# --- Requête -------------------------------------------------------------------------------------


def test_requete_de_vertex(vertex: Vertex) -> None:
    # D5 : gemini-embedding-001 sur Vertex europe-west1, projet jleroy-labo, projet de quota
    # jleroy-labo (celui de l'ADC du poste est jleroy-outils), RETRIEVAL_QUERY, 3 072 dimensions,
    # un texte par requête ; l'ADC, jamais une clé d'API.
    with vertex([ETAPE]) as journal:
        encoder(PHRASE)
    (requete,) = requetes(journal)
    assert requete["chemin"] == CHEMIN
    assert requete["entetes"]["x-goog-user-project"] == "jleroy-labo"
    assert requete["entetes"]["authorization"] == "Bearer ‹jeton›"
    assert requete["corps"] == {
        "instances": [{"content": PHRASE, "task_type": "RETRIEVAL_QUERY"}],
        "parameters": {"outputDimensionality": 3072},
    }


def test_description_en_retrieval_document(vertex: Vertex) -> None:
    # La preuve de symétrie (T8.2) encode une description comme le plugin au chargement (D3).
    with vertex([ETAPE]) as journal:
        encoder(PHRASE, tache=DOCUMENT)
    (requete,) = requetes(journal)
    assert requete["corps"]["instances"] == [{"content": PHRASE, "task_type": "RETRIEVAL_DOCUMENT"}]


def test_cle_d_api_de_l_environnement_ignoree(
    vertex: Vertex, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Une clé d'API Gemini dans l'environnement du harnais ne remplace pas l'ADC : les identifiants
    # explicites passent avant elle (google-genai 2.28.0, _api_client).
    with vertex([ETAPE]) as journal:
        monkeypatch.setenv("GOOGLE_API_KEY", "cle-factice")
        encoder(PHRASE)
    (requete,) = requetes(journal)
    assert requete["entetes"]["authorization"] == "Bearer ‹jeton›"
    assert "x-goog-api-key" not in requete["entetes"]


# --- Résultat ------------------------------------------------------------------------------------


def test_vecteur_jetons_et_latence(vertex: Vertex) -> None:
    # D5 : vecteur, jetons rendus par Vertex (le coût de la campagne) et latence, à l'horloge
    # monotone, de l'envoi à la réponse.
    with vertex([ETAPE | {"jetons": 17, "lent_s": 0.3}]):
        encodage = encoder(PHRASE)
    assert isinstance(encodage, Encodage)
    assert len(encodage.vecteur) == 3072
    assert all(isinstance(valeur, float) for valeur in encodage.vecteur)
    assert encodage.jetons == 17
    assert isinstance(encodage.jetons, int)
    assert 0.3 <= encodage.latence_s < 10


def test_un_meme_texte_un_meme_vecteur(vertex: Vertex) -> None:
    with vertex([ETAPE, ETAPE, ETAPE]):
        premier, second, autre = encoder(PHRASE), encoder(PHRASE), encoder(PHRASE + " Autre.")
    assert premier.vecteur == second.vecteur
    assert premier.vecteur != autre.vecteur


def test_reprise_apres_429(vertex: Vertex) -> None:
    # Vertex ne facture que les réponses 200 (page de prix, lue le 2026-10-17) : la reprise ne coûte
    # rien de plus.
    with vertex([{"statut": 429, "message": "quota"}, ETAPE]) as journal:
        encodage = encoder(PHRASE)
    assert len(requetes(journal)) == 2
    assert encodage.jetons == 13


# --- Refus ---------------------------------------------------------------------------------------


def test_autre_dimension_refusee(vertex: Vertex) -> None:
    # Un vecteur d'une autre dimension que l'index (3 072) ne se chercherait pas (D2, D5).
    with (
        vertex([ETAPE | {"dimensions": 768}]),
        pytest.raises(EncodageError, match="768 dimensions"),
    ):
        encoder(PHRASE)


def test_texte_tronque_refuse(vertex: Vertex) -> None:
    # Au-delà de 2 048 jetons, Vertex tronque sans erreur : le vecteur ne serait pas celui du texte.
    with vertex([ETAPE | {"tronque": True}]), pytest.raises(EncodageError, match="tronqué"):
        encoder(PHRASE)


def test_jetons_absents_refuses(vertex: Vertex) -> None:
    # Sans jetons, le coût de l'encodage ne se compte pas (D11).
    with (
        vertex([ETAPE | {"sans_statistiques": True}]),
        pytest.raises(EncodageError, match="jetons"),
    ):
        encoder(PHRASE)


def test_erreur_de_vertex(vertex: Vertex) -> None:
    with vertex([{"statut": 403, "message": "refus"}]), pytest.raises(EncodageError, match="403"):
        encoder(PHRASE)


def test_adc_refusee(vertex: Vertex) -> None:
    with vertex([ETAPE], jeton_refuse=True), pytest.raises(EncodageError, match="ADC refusée"):
        encoder(PHRASE)


def test_adc_sans_projet_de_quota_refusee(monkeypatch: pytest.MonkeyPatch) -> None:
    # Des identifiants qui ne portent pas de projet de quota : les appels seraient comptés à un
    # autre projet que jleroy-labo, sans rien dire (D5).
    identifiants = google.auth.credentials.AnonymousCredentials()  # type: ignore[no-untyped-call]
    monkeypatch.setattr(google.auth, "default", lambda scopes: (identifiants, None))
    with pytest.raises(EncodageError, match="sans projet de quota"):
        encoder(PHRASE)
