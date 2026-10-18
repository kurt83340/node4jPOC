"""Cellules GraphRAG (spec 003 ; plan D7, D9 ; ADR-0017, ADR-0018), contre un faux serveur MCP qui
répond à la recherche (tests/fixtures/faux_serveur_mcp.py) et une fausse API (l'API Anthropic et
Vertex en flux, le jeton d'une ADC factice : tests/fixtures/fausse_api_adk.py). Aucun appel réel,
aucun coût.

T9.1, la recherche et sa trace : un rédacteur factice remplace l'appel au modèle et note ce qu'il
reçoit. DoD : la commande avec les vecteurs, la connexion avant le chrono, la requête telle quelle
et le vecteur en paramètre, l'empreinte du vecteur à sa place dans la trace, le garde-fou de
l'ADR-0017 avant l'appel ; puis les issues d'une recherche (D13), l'isolement, l'arrêt du serveur.

T10.1, l'appel au modèle : le vrai ADK 2.11.0, sans outil. DoD : la consigne de contexte et la
fiche, le message (le contexte, puis la question), les réglages et les comptes des cellules ADK du
jalon 2 (D7), les plafonds et les issues comme banc.cellule_adk ; puis le point d'entrée.

T11.1, les seconds tours (D10) et l'isolement : Q18 dans la session d'ADK de Q2, sa recherche
partie de son propre vecteur, son appel au modèle qui reçoit le message de Q2, son contexte et sa
réponse ; Q18 non posée après un échec de Q2 (ADR-0012) ; la cellule lancée avec sa propre liste
blanche (banc.isolement).
"""

import asyncio
import io
import json
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_cellule_adk import Bac, attendre, erreur, reponse, vivant
from test_essai_recherche import espece

from banc import cellule_adk, cellule_graphrag, prix
from banc.cellule import (
    CelluleError,
    Commande,
    IsolementError,
    commande_json,
    consigne_et_fiche,
    empreinte_prompt,
)
from banc.cellule_adk import _Comptes, _Tour
from banc.cellule_graphrag import Redaction, converser
from banc.isolement import CleAbsente, environnement_agent
from banc.mesures import Conversation
from banc.prix import Usage

RECHERCHE = (Path(__file__).resolve().parents[2] / "questions" / "recherche.cypher").read_text(
    encoding="utf-8"
)
CLE = "sk-ant-api03-cle-factice-du-banc"
CLAUDE, GEMINI = "graphrag-claude", "graphrag-gemini"
CLIENTS = (CLAUDE, GEMINI)
# Modèle et voie de prix des cellules ADK du jalon 2, que les cellules GraphRAG reprennent (D7) ; la
# fausse API se lance sous le nom de la jumelle.
MODELES = {CLAUDE: "claude-sonnet-5-5", GEMINI: "gemini-3.8-flash"}
ACCES = {CLAUDE: "api", GEMINI: "vertex-eu"}
JUMELLES = {CLAUDE: "adk-claude", GEMINI: "adk-gemini"}
Q1 = ("Q1", "Combien de nœuds ?")
Q2 = ("Q2", "Mon équipe : Pikachu.\n\nQui remplacer ?")
Q18 = ("Q18", "Et si je garde Pikachu ?")
# Les vecteurs des messages, de la dimension de l'index (3 072), et leurs empreintes, calculées à
# part (SHA-256 des composantes en flottants de 64 bits petit-boutistes).
VECTEUR = (0.0123456789,) * 3072
EMPREINTE = "sha256:a32c37e9fcbe45fc3ccc97244ac67f48b10dc739c88a8e66dded152415802162"
VECTEUR_Q18 = (-0.0987654321,) * 3072
EMPREINTE_Q18 = "sha256:d71b7a020749564b887342e25d117b3f6bfd75f948b830cd29668f4cd4fd2dcd"
# Le contexte que rend le faux serveur : des enregistrements de recherche.cypher, une espèce chacun.
CONTEXTE = json.dumps([espece(1), espece(2, descriptions=1)], ensure_ascii=False, indent=2)
REPONSE = "Réponse : Espèce 1\n\nSources : Texte 1.0 (Jeu)"
# Le contexte de la recherche de Q18, et sa réponse : ceux d'un second tour.
CONTEXTE_Q18 = json.dumps([espece(3)], ensure_ascii=False, indent=2)
REPONSE_Q18 = "Réponse : Espèce 3\n\nSources : Texte 3.0 (Jeu)"
# Le contexte d'une recherche qui renverrait les vecteurs (US4) : 20 espèces, chacune avec le sien.
AVEC_VECTEURS = json.dumps([espece(n) | {"embedding": [0.1] * 3072} for n in range(20)])


@dataclass
class RedacteurFactice:
    """Remplace l'appel au modèle dans les tests de la recherche : note ce qu'il reçoit et
    l'instant, répond, et ajoute son coût à celui de la conversation."""

    reponse: str = REPONSE
    cout: Decimal = Decimal(0)
    recus: list[tuple[str, str]] = field(default_factory=list)
    instants: list[float] = field(default_factory=list)

    def __call__(self, comptes: _Comptes) -> Redaction:
        async def rediger(tour: _Tour, message: str, contexte: str) -> None:
            self.recus.append((message, contexte))
            self.instants.append(time.monotonic())
            comptes.cout += self.cout
            tour.reponse = self.reponse

        return rediger


@dataclass
class BacGraphrag(Bac):
    """Le bac des cellules ADK (dossiers, faux serveur MCP, trace), et une commande qui porte un
    vecteur par question."""

    def commande(
        self, *questions: tuple[str, str], mcp: dict[str, Any] | None = None, **reglages: Any
    ) -> Commande:
        """La commande d'une conversation ; vecteurs : ceux des questions, sinon VECTEUR, puis
        VECTEUR_Q18."""
        vecteurs = reglages.pop("vecteurs", None)
        commande = super().commande(*questions, mcp=mcp, **reglages)
        if vecteurs is None:
            vecteurs = (VECTEUR, VECTEUR_Q18)[: len(commande.questions)]
        return replace(commande, vecteurs=vecteurs)

    @contextmanager
    def api(self, client: str, etapes: list[dict[str, Any]], **reglages: Any) -> Iterator[str]:
        """La fausse API, lancée sous le nom de la cellule ADK jumelle : la clé Anthropic pour la
        cellule Claude seule (D3)."""
        with super().api(JUMELLES[client], etapes, **reglages) as adresse:
            yield adresse

    def acces(self, client: str) -> None:
        """La clé Anthropic pour la cellule Claude seule (D3)."""
        if client == CLAUDE:
            self.monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)
        else:
            self.monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    def mener(
        self,
        client: str,
        commande: Commande | None = None,
        redacteur: RedacteurFactice | None = None,
    ) -> Conversation:
        """Mène la conversation dans ce processus, le modèle remplacé par un rédacteur factice, et
        relit sa trace."""
        self.acces(client)
        commande = commande or self.commande()
        asyncio.run(converser(client, commande, prix.charger(), redacteur or RedacteurFactice()))
        return self.trace()

    def converser(
        self,
        client: str,
        etapes: list[dict[str, Any]],
        commande: Commande | None = None,
        **reglages: Any,
    ) -> Conversation:
        """Mène la conversation dans ce processus, avec le vrai ADK contre la fausse API et son
        scénario, et relit sa trace."""
        commande = commande or self.commande()
        with self.api(client, etapes, **reglages):
            asyncio.run(converser(client, commande, prix.charger()))
        return self.trace()

    def lancer(
        self, client: str, etapes: list[dict[str, Any]], commande: Commande
    ) -> subprocess.CompletedProcess[str]:
        """La cellule dans son propre processus, comme l'orchestration la lancera : sa liste
        blanche pour seul environnement (banc.isolement)."""
        with self.api(client, etapes) as adresse:
            env = environnement_agent(client, self.racine / "home", self.racine / "claude")
            env |= {"ANTHROPIC_BASE_URL" if client == CLAUDE else "GOOGLE_VERTEX_BASE_URL": adresse}
            return subprocess.run(
                [sys.executable, "-m", "banc.cellule_graphrag", client],
                input=commande_json(commande),
                cwd=self.racine / "travail",
                env=env,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

    def appels(self) -> list[dict[str, Any]]:
        """Les appels d'outils reçus par le faux serveur (nom, arguments), dans l'ordre."""
        return [
            note["recu"]["params"]
            for note in self.notes_mcp("recu")
            if note["recu"].get("method") == "tools/call"
        ]


@pytest.fixture
def bac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cle_adc: str) -> BacGraphrag:
    for dossier in ("home", "claude", "gcloud", "journal", "travail", "traces"):
        (tmp_path / dossier).mkdir()
    # Rien du poste ne doit choisir l'accès des clients à la place de la cellule.
    for nom in ("ANTHROPIC_AUTH_TOKEN", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path / "gcloud"))
    # Reprises de Gemini sans attente : seul leur nombre compte ici.
    rapides = {"initial_delay": 0.01, "max_delay": 0.02}
    reprises = cellule_adk.REPRISES_GEMINI.model_copy(update=rapides)
    monkeypatch.setattr(cellule_adk, "REPRISES_GEMINI", reprises)
    monkeypatch.chdir(tmp_path / "travail")
    return BacGraphrag(tmp_path, monkeypatch, cle_adc)


def mener_puis_regarder(bac: BacGraphrag, client: str, commande: Commande) -> list[int]:
    """Mène la conversation, puis rend les serveurs encore vivants avant la fin de la boucle (qui
    annulerait de toute façon les tâches restantes) : c'est la cellule qui doit les arrêter."""

    async def regarder() -> list[int]:
        await converser(client, commande, prix.charger(), RedacteurFactice())
        return [note["pid"] for note in bac.notes_mcp("pid") if vivant(note["pid"])]

    bac.acces(client)
    return asyncio.run(regarder())


def estimation(client: str, caracteres: int, *, cache_1h: bool = False) -> Decimal:
    """Garde-fou de l'ADR-0017 : un token pour 3 caractères, par excès, au prix de l'entrée ou de
    l'écriture en cache à la durée de la commande s'il est plus haut."""
    jetons = -(-caracteres // 3)
    tarif = prix.tarif(prix.charger(), MODELES[client], date.today(), ACCES[client])
    ecriture = Usage(cache_ecriture_1h=jetons) if cache_1h else Usage(cache_ecriture_5m=jetons)
    return max(tarif.cout(Usage(entree=jetons)), tarif.cout(ecriture))


# --- DoD : la recherche, par la voie de T8.2 -----------------------------------------------------


@pytest.mark.parametrize("client", CLIENTS)
def test_recherche_par_read_cypher(bac: BacGraphrag, client: str) -> None:
    # La requête telle quelle, commentaires compris (la voie prouvée par T8.2 sur la vraie base),
    # le vecteur de la question en paramètre, en entier : un seul appel, à read-cypher.
    commande = bac.commande(mcp={"appels": [{"texte": CONTEXTE}]})
    bac.mener(client, commande)
    (appel,) = bac.appels()
    assert appel["name"] == "read-cypher"
    assert appel["arguments"] == {"query": RECHERCHE, "params": {"vecteur": list(VECTEUR)}}
    assert appel["arguments"]["query"].startswith("// Recherche de la technique 3")


@pytest.mark.parametrize("client", CLIENTS)
def test_contexte_tel_quel_au_modele(bac: BacGraphrag, client: str) -> None:
    # Le résultat de read-cypher, tel quel, est le contexte de l'appel au modèle, avec le message
    # posé ; la réponse rédigée finit le tour.
    redacteur = RedacteurFactice()
    commande = bac.commande(mcp={"appels": [{"texte": CONTEXTE}]})
    (tour,) = bac.mener(client, commande, redacteur).tours
    assert redacteur.recus == [(Q1[1], CONTEXTE)]
    assert (tour.issue, tour.cause, tour.reponse) == ("reponse", None, REPONSE)


@pytest.mark.parametrize("client", CLIENTS)
def test_trace_de_la_recherche(bac: BacGraphrag, client: str) -> None:
    # D9 : la recherche s'écrit comme un appel read-cypher ; à la place du vecteur, son empreinte ;
    # son résultat tel que le modèle le reçoit.
    commande = bac.commande(mcp={"appels": [{"texte": CONTEXTE}]})
    (tour,) = bac.mener(client, commande).tours
    (appel,) = tour.appels
    assert (appel.outil, appel.requete) == ("read-cypher", RECHERCHE)
    assert appel.parametres == {"vecteur": EMPREINTE}
    assert (appel.resultat, appel.erreur) == (CONTEXTE, False)


def test_aucun_vecteur_dans_la_trace(bac: BacGraphrag) -> None:
    # US4 : le vecteur de la question n'entre jamais dans la trace, seule son empreinte.
    bac.mener(CLAUDE)
    (fichier,) = (bac.racine / "traces").rglob("*.jsonl")
    texte = fichier.read_text()
    assert "0.0123456789" not in texte
    assert texte.count(EMPREINTE) == 1


@pytest.mark.parametrize("client", CLIENTS)
def test_paire_un_vecteur_par_question(bac: BacGraphrag, client: str) -> None:
    # Q2 puis Q18 : chaque question cherche avec son vecteur, et le note dans son tour.
    redacteur = RedacteurFactice()
    trace = bac.mener(client, bac.commande(Q2, Q18), redacteur)
    vecteurs = [appel["arguments"]["params"]["vecteur"] for appel in bac.appels()]
    assert vecteurs == [list(VECTEUR), list(VECTEUR_Q18)]
    parametres = [tour.appels[0].parametres for tour in trace.tours]
    assert parametres == [{"vecteur": EMPREINTE}, {"vecteur": EMPREINTE_Q18}]
    assert [message for message, _ in redacteur.recus] == [Q2[1], Q18[1]]
    assert [tour.issue for tour in trace.tours] == ["reponse", "reponse"]


@pytest.mark.parametrize("client", CLIENTS)
def test_connexion_avant_le_chrono(bac: BacGraphrag, client: str) -> None:
    # Le serveur met 2 s à se connecter : la question part après, et son temps ne le compte pas.
    commande = bac.commande(mcp={"attente_s": 2.0})
    (tour,) = bac.mener(client, commande).tours
    assert tour.issue == "reponse"
    assert tour.duree_s is not None and tour.duree_s < 2.0


@pytest.mark.parametrize("client", CLIENTS)
def test_une_seule_lecture_des_outils(bac: BacGraphrag, client: str) -> None:
    # mcp 2.3.0 relit la liste des outils au premier appel d'un outil qu'il n'a pas vu sur la
    # session (validation du résultat) : lue une fois, avant le chrono, sur la même session.
    bac.mener(client, bac.commande(Q2, Q18))
    assert bac.methodes_mcp().count("tools/list") == 1
    assert bac.methodes_mcp().count("tools/call") == 2


# --- DoD : garde-fou de l'ADR-0017, avant l'appel au modèle --------------------------------------


@pytest.mark.parametrize(
    "cellule",
    [(CLAUDE, False), (CLAUDE, True), (GEMINI, False)],
    ids=["claude-5m", "claude-1h", "gemini"],
)
@pytest.mark.parametrize(
    "borne", [(Decimal(0), "reponse"), (Decimal("-1E-7"), "echec")], ids=["pile", "en-dessous"]
)
def test_garde_fou_a_la_borne(
    bac: BacGraphrag, cellule: tuple[str, bool], borne: tuple[Decimal, str]
) -> None:
    # Un contexte de 3 001 caractères, estimé à 1 001 tokens : budget pile à son coût estimé,
    # l'appel au modèle a lieu (dépassement strict) ; un dix-millionième de dollar de moins, le tour
    # s'arrête avant lui, échec « budget ».
    (client, cache_1h), (marge, issue) = cellule, borne
    contexte = "x" * 3001
    budget = estimation(client, 3001, cache_1h=cache_1h) + marge
    redacteur = RedacteurFactice()
    mcp = {"appels": [{"texte": contexte}]}
    commande = bac.commande(mcp=mcp, budget_usd=budget, cache_1h=cache_1h)
    (tour,) = bac.mener(client, commande, redacteur).tours
    assert (tour.issue, tour.cause) == ((issue, None) if issue == "reponse" else (issue, "budget"))
    assert len(redacteur.recus) == (issue == "reponse")


@pytest.mark.parametrize(
    "borne", [(Decimal(0), "reponse"), (Decimal("-1E-7"), "echec")], ids=["pile", "en-dessous"]
)
def test_garde_fou_compte_les_tours_precedents(
    bac: BacGraphrag, borne: tuple[Decimal, str]
) -> None:
    # Le budget est celui de la conversation : au second tour, ce que le premier a coûté s'ajoute
    # à l'estimation du contexte.
    marge, issue = borne
    premier = Decimal("0.01")
    budget = premier + estimation(CLAUDE, 3001) + marge
    mcp = {"appels": [{"texte": "x" * 3001}, {"texte": "x" * 3001}]}
    commande = bac.commande(Q2, Q18, mcp=mcp, budget_usd=budget)
    trace = bac.mener(CLAUDE, commande, RedacteurFactice(cout=premier))
    assert [tour.issue for tour in trace.tours] == ["reponse", issue]


@pytest.mark.parametrize("client", CLIENTS)
def test_contexte_avec_les_vecteurs(bac: BacGraphrag, client: str) -> None:
    # Une recherche qui renverrait les vecteurs (US4) : plus de 300 000 caractères, le tour s'arrête
    # avant l'appel au modèle ; un contexte réel (≈ 19 000 caractères, T8.2) tient dans ce budget.
    assert estimation(client, 19_000) < Decimal("0.05") < estimation(client, len(AVEC_VECTEURS))
    redacteur = RedacteurFactice()
    mcp = {"appels": [{"texte": AVEC_VECTEURS}]}
    commande = bac.commande(mcp=mcp, budget_usd=Decimal("0.05"))
    (tour,) = bac.mener(client, commande, redacteur).tours
    assert (tour.issue, tour.cause) == ("echec", "budget")
    (appel,) = tour.appels
    assert appel.resultat == AVEC_VECTEURS
    assert redacteur.recus == []


def test_paire_arretee_apres_un_echec(bac: BacGraphrag) -> None:
    # Q2 échoue : Q18 n'est pas posée ; sa ligne relève de l'orchestration (ADR-0012).
    mcp = {"appels": [{"texte": AVEC_VECTEURS}]}
    commande = bac.commande(Q2, Q18, mcp=mcp, budget_usd=Decimal("0.05"))
    (tour,) = bac.mener(CLAUDE, commande).tours
    assert (tour.question, tour.issue, tour.cause) == ("Q2", "echec", "budget")
    assert bac.methodes_mcp().count("tools/call") == 1


# --- Issues d'un tour (D13) ----------------------------------------------------------------------


@pytest.mark.parametrize("client", CLIENTS)
def test_read_cypher_en_erreur(bac: BacGraphrag, client: str) -> None:
    # Plan, « Erreurs » : read-cypher en erreur, une panne (la conversation sera rejouée) ; rien ne
    # part au modèle ; la trace garde l'erreur.
    refus = "Neo.TransientError.Transaction.Terminated: transaction arrêtée"
    redacteur = RedacteurFactice()
    commande = bac.commande(mcp={"appels": [{"texte": refus, "erreur": True}]})
    (tour,) = bac.mener(client, commande, redacteur).tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")
    (appel,) = tour.appels
    assert (appel.resultat, appel.erreur) == (refus, True)
    assert redacteur.recus == []


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_perdu_pendant_la_recherche(bac: BacGraphrag, client: str) -> None:
    # Le serveur meurt au lieu de répondre : panne, aussitôt, et non à l'échéance du tour.
    redacteur = RedacteurFactice()
    commande = bac.commande(mcp={"appels": [{"mort": True}]}, delai_s=20.0)
    (tour,) = bac.mener(client, commande, redacteur).tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")
    assert tour.duree_s is not None and tour.duree_s < 10.0
    assert redacteur.recus == []


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_perdu_entre_deux_tours(bac: BacGraphrag, client: str) -> None:
    # Le serveur sort après avoir répondu à Q2 : la recherche de Q18 le trouve perdu, panne. La
    # cellule ne le relance pas (ADK le ferait en silence).
    commande = bac.commande(Q2, Q18, mcp={"appels": [{"quitter": True}]}, delai_s=20.0)
    trace = bac.mener(client, commande)
    issues = [(tour.issue, tour.cause) for tour in trace.tours]
    assert issues == [("reponse", None), ("panne", "serveur")]
    assert len(bac.notes_mcp("pid")) == 1


@pytest.mark.parametrize("client", CLIENTS)
def test_delai_pendant_la_recherche(bac: BacGraphrag, client: str) -> None:
    # L'échéance du tour tombe pendant la recherche : échec « délai » (D13), comme pendant une
    # lecture d'agent ; rien ne part au modèle ; la lecture reste notée, sans résultat.
    redacteur = RedacteurFactice()
    commande = bac.commande(mcp={"appels": [{"lent_s": 30}]}, delai_s=2.0)
    (tour,) = bac.mener(client, commande, redacteur).tours
    assert (tour.issue, tour.cause) == ("echec", "delai")
    assert tour.duree_s is not None and 2.0 <= tour.duree_s < 4.0
    (appel,) = tour.appels
    assert (appel.parametres, appel.resultat, appel.erreur) == ({"vecteur": EMPREINTE}, "", True)
    assert redacteur.recus == []


# --- Serveur MCP ---------------------------------------------------------------------------------


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_absent(bac: BacGraphrag, client: str) -> None:
    # Le serveur ne démarre pas : panne avant la première question ; ni recherche ni modèle.
    redacteur = RedacteurFactice()
    trace = bac.mener(client, bac.commande(serveur=("/bin/false",)), redacteur)
    (tour,) = trace.tours
    assert (tour.issue, tour.cause, tour.appels) == ("panne", "serveur", ())
    assert trace.entete.versions["neo4j-mcp"] == "absent"
    assert redacteur.recus == []


def test_serveur_trop_lent(bac: BacGraphrag) -> None:
    # La connexion dépasse son délai : panne, sans attendre le serveur, qui ne reste pas vivant.
    commande = bac.commande(mcp={"attente_s": 30}, connexion_s=0.5)
    debut = time.monotonic()
    assert mener_puis_regarder(bac, CLAUDE, commande) == []
    assert time.monotonic() - debut < 10
    (tour,) = bac.trace().tours
    assert (tour.issue, tour.cause) == ("panne", "serveur")


def test_serveur_sans_lecture(bac: BacGraphrag) -> None:
    with pytest.raises(IsolementError, match="read-cypher"):
        bac.mener(CLAUDE, bac.commande(mcp={"outils": ["get-schema"]}))


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_arrete_avant_la_fin(bac: BacGraphrag, client: str) -> None:
    # La cellule arrête son serveur avant de rendre la main, comme les cellules ADK.
    assert mener_puis_regarder(bac, client, bac.commande()) == []
    assert len(bac.notes_mcp("pid")) == 1


@pytest.mark.parametrize("client", CLIENTS)
def test_serveur_avec_l_environnement_de_la_cellule(bac: BacGraphrag, client: str) -> None:
    # Le serveur reçoit l'environnement de la cellule, la liste blanche que l'orchestration lui
    # donne (D3) : sans env explicite, mcp ne lui passerait que HOME, PATH et quelques variables du
    # poste. Ses seuls noms sont notés : lancé par les tests, il reçoit celui du poste.
    bac.monkeypatch.setenv("BANC_TEMOIN", "1")
    bac.mener(client)
    (demarrage,) = bac.notes_mcp("env")
    assert "BANC_TEMOIN" in demarrage["env"]


# --- Commande, accès, en-tête --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("questions", "vecteurs", "motif"),
    [
        pytest.param((Q1,), (), "commande sans vecteurs", id="sans-vecteurs"),
        pytest.param((Q2, Q18), (VECTEUR,), "un par question", id="un-de-moins"),
        pytest.param((Q1,), ((0.5,) * 3071,), "3071 dimensions", id="dimension"),
    ],
)
def test_vecteurs_refuses(
    bac: BacGraphrag,
    questions: tuple[tuple[str, str], ...],
    vecteurs: tuple[tuple[float, ...], ...],
    motif: str,
) -> None:
    # D5 : un vecteur par question, de la dimension de l'index ; refusé avant de lancer quoi que ce
    # soit : ni serveur, ni trace.
    commande = bac.commande(*questions, vecteurs=vecteurs)
    with pytest.raises(CelluleError, match=motif):
        bac.mener(CLAUDE, commande)
    assert bac.notes_mcp("pid") == []
    assert not list((bac.racine / "traces").rglob("*.jsonl"))


def test_client_inconnu(bac: BacGraphrag) -> None:
    with pytest.raises(CelluleError, match="client inconnu"):
        bac.mener("graphrag-autre")


def test_gemini_sans_cle_anthropic(bac: BacGraphrag) -> None:
    # Refusée avant de lancer quoi que ce soit (D3).
    commande = bac.commande()
    bac.monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)
    with pytest.raises(IsolementError, match="jamais la clé"):
        asyncio.run(converser(GEMINI, commande, prix.charger(), RedacteurFactice()))
    assert bac.notes_mcp("pid") == []


def test_claude_sans_cle(bac: BacGraphrag) -> None:
    commande = bac.commande()
    bac.monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(CleAbsente):
        asyncio.run(converser(CLAUDE, commande, prix.charger(), RedacteurFactice()))
    assert bac.notes_mcp("pid") == []


@pytest.mark.parametrize("client", CLIENTS)
def test_entete(bac: BacGraphrag, client: str) -> None:
    # D7 : le modèle, la voie et l'effort de la cellule ADK jumelle, sous le nom de la cellule.
    trace = bac.mener(client)
    entete = trace.entete
    assert (entete.cellule, entete.modele, entete.acces) == (client, MODELES[client], ACCES[client])
    assert (entete.effort, entete.annexes) == ("high", ())
    bibliotheque = "anthropic" if client == CLAUDE else "google-genai"
    assert set(entete.versions) == {"google-adk", "mcp", bibliotheque, "neo4j-mcp"}
    assert entete.versions["neo4j-mcp"] == "v1.6.0"
    (fichier,) = (bac.racine / "traces").rglob("*.jsonl")
    assert fichier.name == f"{client}-p1-Q1-e1.jsonl"


# --- T10.1 : l'appel au modèle, ADK sans outil, contre une fausse API ---------------------------


def message(question: str, contexte: str = CONTEXTE) -> str:
    """Le message d'un tour dans la forme choisie par Julien le 2026-10-18 (plan, D8) : le
    contexte d'abord, puis la question, entre balises."""
    return f"<contexte>\n{contexte}\n</contexte>\n\n<question>\n{question}\n</question>"


def systeme(client: str, corps: dict[str, Any]) -> str:
    """Le prompt système d'une requête du modèle, chez Anthropic ou chez Vertex."""
    if client == CLAUDE:
        (bloc,) = corps["system"]
        return str(bloc["text"])
    (partie,) = corps["systemInstruction"]["parts"]
    return str(partie["text"])


def envoye(client: str, corps: dict[str, Any]) -> list[str]:
    """Les textes des messages de l'utilisateur d'une requête du modèle, dans l'ordre."""
    if client == CLAUDE:
        messages = [m for m in corps["messages"] if m["role"] == "user"]
        return [bloc["text"] for m in messages for bloc in m["content"] if bloc["type"] == "text"]
    contenus = [c for c in corps["contents"] if c["role"] == "user"]
    return [partie["text"] for c in contenus for partie in c["parts"] if "text" in partie]


def test_requete_de_claude(bac: BacGraphrag) -> None:
    # D7 : les réglages d'adk-claude (Claude Sonnet 5.5, effort high, 128 000 tokens de sortie,
    # réflexion adaptative, en flux, cache de 5 min) ; aucun outil ; la consigne de contexte et la
    # fiche ; un seul message, le contexte puis la question.
    commande = bac.commande(mcp={"appels": [{"texte": CONTEXTE}]})
    bac.converser(CLAUDE, [reponse(REPONSE)], commande)
    (requete,) = bac.requetes()
    corps = requete["corps"]
    assert requete["chemin"].startswith("/v1/messages")
    assert corps["model"] == "claude-sonnet-5-5"
    assert corps["max_tokens"] == 128_000
    assert corps["output_config"] == {"effort": "high"}
    assert corps["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert corps["stream"] is True
    assert "tools" not in corps
    assert systeme(CLAUDE, corps).startswith(consigne_et_fiche(consigne="contexte"))
    assert corps["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert envoye(CLAUDE, corps) == [message(Q1[1])]


def test_requete_de_gemini(bac: BacGraphrag) -> None:
    # D7 : les réglages d'adk-gemini (Gemini 3.8 Flash sur Vertex eu, réflexion HIGH, aucun cache
    # stocké) ; aucun outil ; la consigne de contexte et la fiche ; le contexte puis la question.
    commande = bac.commande(mcp={"appels": [{"texte": CONTEXTE}]})
    bac.converser(GEMINI, [reponse(REPONSE)], commande)
    (requete,) = bac.requetes()
    corps = requete["corps"]
    modele = "/projects/jleroy-labo/locations/eu/publishers/google/models/gemini-3.8-flash"
    assert f"{modele}:streamGenerateContent" in requete["chemin"]
    assert corps["generationConfig"] == {"thinkingConfig": {"thinking_level": "HIGH"}}
    assert "tools" not in corps
    assert "cachedContent" not in json.dumps(corps)
    assert systeme(GEMINI, corps).startswith(consigne_et_fiche(consigne="contexte"))
    assert envoye(GEMINI, corps) == [message(Q1[1])]


@pytest.mark.parametrize("client", CLIENTS)
def test_tour_mesure(bac: BacGraphrag, client: str) -> None:
    # Un tour : la recherche, puis un seul appel au modèle ; ses tokens, sa réflexion, sa réponse.
    commande = bac.commande(mcp={"appels": [{"texte": CONTEXTE}]})
    trace = bac.converser(client, [reponse(REPONSE)], commande)
    (tour,) = trace.tours
    assert (tour.issue, tour.cause, tour.reponse) == ("reponse", None, REPONSE)
    (appel,) = tour.appels
    assert (appel.outil, appel.parametres, appel.resultat) == (
        "read-cypher",
        {"vecteur": EMPREINTE},
        CONTEXTE,
    )
    # La réponse type de la fausse API : 100 tokens d'entrée, 3 000 lus en cache, 30 de sortie
    # dont 5 de réflexion.
    assert tour.usages == {MODELES[client]: Usage(entree=100, sortie=30, cache_lecture=3000)}
    assert tour.reflexion == {MODELES[client]: 5}
    (llm,) = bac.events("llm")
    assert llm["brut"]["model_version"] == MODELES[client]


@pytest.mark.parametrize("client", CLIENTS)
def test_prompt_change_depuis_la_creation(bac: BacGraphrag, client: str) -> None:
    # L'empreinte du prompt d'une autre technique (la consigne de l'outil) : erreur technique avant
    # tout serveur, toute trace et tout appel (protocole gelé, D7).
    commande = replace(bac.commande(), empreinte_prompt=empreinte_prompt("fr"))
    with pytest.raises(CelluleError, match="changées depuis la création de la campagne"):
        bac.converser(client, [reponse()], commande)
    assert bac.notes_mcp("pid") == []
    assert not list((bac.racine / "traces").rglob("*.jsonl"))
    assert bac.requetes() == []


@pytest.mark.parametrize("client", CLIENTS)
def test_prompt_de_la_campagne_anglaise(bac: BacGraphrag, client: str) -> None:
    # Schéma anglais : la fiche anglaise, sous l'empreinte de la consigne de contexte fixée à la
    # création de la campagne.
    empreinte = empreinte_prompt("en", consigne="contexte")
    commande = replace(bac.commande(), schema="en", empreinte_prompt=empreinte)
    bac.converser(client, [reponse()], commande)
    (requete,) = bac.requetes()
    attendu = consigne_et_fiche(schema="en", consigne="contexte")
    assert systeme(client, requete["corps"]).startswith(attendu)


def test_cache_d_une_heure(bac: BacGraphrag) -> None:
    # D10 du jalon 2 : le cache d'une heure des cellules Claude, quand la campagne le fixe.
    commande = bac.commande(cache_1h=True)
    (tour,) = bac.converser(CLAUDE, [reponse(entree=100, sortie=30, ecrit=3000)], commande).tours
    (requete,) = bac.requetes()
    assert requete["corps"]["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}
    usage = tour.usages[MODELES[CLAUDE]]
    assert (usage.cache_ecriture_1h, usage.cache_ecriture_5m) == (3000, 0)


@pytest.mark.parametrize("client", CLIENTS)
def test_delai_pendant_l_appel(bac: BacGraphrag, client: str) -> None:
    # Le flux du modèle s'ouvre puis se tait : à l'échéance, échec « délai ». Un appel de Claude
    # coupé ne rend aucun usage (borne basse, choix de Julien) ; celui de Gemini, son premier
    # morceau (l'entrée, 100 tokens et 3 000 en cache, sans détail).
    commande = bac.commande(delai_s=2.0)
    (tour,) = bac.converser(client, [reponse() | {"lent_s": 30}], commande).tours
    assert (tour.issue, tour.cause) == ("echec", "delai")
    assert tour.duree_s is not None and 2.0 <= tour.duree_s < 4.0
    attendu = {MODELES[GEMINI]: Usage(entree=3100)} if client == GEMINI else {}
    assert tour.usages == attendu
    partiels = [appel for appel in bac.events("llm") if appel["brut"].get("partiel")]
    assert len(partiels) == (client == GEMINI)


@pytest.mark.parametrize("client", CLIENTS)
def test_le_delai_couvre_la_recherche(bac: BacGraphrag, client: str) -> None:
    # Le temps d'une question court de l'envoi du message à la réponse finale, recherche comprise
    # (plan, « Performance ») : 1,5 s de recherche, puis 1 s d'appel, dépassent un délai de 2 s.
    commande = bac.commande(mcp={"appels": [{"texte": CONTEXTE, "lent_s": 1.5}]}, delai_s=2.0)
    (tour,) = bac.converser(client, [reponse() | {"lent_s": 1.0}], commande).tours
    assert (tour.issue, tour.cause) == ("echec", "delai")
    assert tour.duree_s is not None and 2.0 <= tour.duree_s < 3.0


@pytest.mark.parametrize("client", CLIENTS)
def test_budget_depasse_par_l_appel(bac: BacGraphrag, client: str) -> None:
    # Le garde-fou laisse passer le contexte ; l'appel coûte plus que le budget qui reste : échec
    # « budget », comme dans les cellules ADK (un appel se compte à sa fin).
    budget = estimation(client, len(CONTEXTE)) + Decimal("0.001")
    commande = bac.commande(mcp={"appels": [{"texte": CONTEXTE}]}, budget_usd=budget)
    (tour,) = bac.converser(client, [reponse(entree=100_000, sortie=30)], commande).tours
    assert (tour.issue, tour.cause) == ("echec", "budget")
    assert len(bac.requetes()) == 1


@pytest.mark.parametrize("client", CLIENTS)
def test_reprise_puis_reponse(bac: BacGraphrag, client: str) -> None:
    (tour,) = bac.converser(client, [erreur(429, "rate_limit_error"), reponse()]).tours
    assert (tour.issue, tour.reprises) == ("reponse", 1)
    (reprise,) = bac.events("reprise")
    assert reprise["statut"] == 429


@pytest.mark.parametrize("client", CLIENTS)
def test_panne_de_l_api(bac: BacGraphrag, client: str) -> None:
    # 429 puis 5xx sans fin : 2 reprises, puis une panne, relancée (D13).
    etapes = [erreur(429), erreur(503), erreur(500)]
    (tour,) = bac.converser(client, etapes).tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "api", 2)
    assert len(bac.requetes()) == 3


def test_credits_epuises(bac: BacGraphrag) -> None:
    # Plafond de dépense atteint : ni panne ni échec, la campagne s'arrête (D13).
    solde = "Your credit balance is too low to access the API."
    (tour,) = bac.converser(CLAUDE, [erreur(400, "invalid_request_error", solde)]).tours
    assert (tour.issue, tour.cause) == ("arret", "plafond")


@pytest.mark.parametrize(
    ("client", "genre"), [(CLAUDE, "invalid_request_error"), (GEMINI, "invalid_argument")]
)
def test_refus_de_l_api(bac: BacGraphrag, client: str, genre: str) -> None:
    # Tout autre refus : erreur technique, qui arrête la campagne.
    with pytest.raises(CelluleError, match="refus de l'API"):
        bac.converser(client, [erreur(400, genre, "refusé")])


def test_jeton_refuse(bac: BacGraphrag) -> None:
    # L'ADC refusée (invalid_grant) : erreur technique, avant la première question.
    with pytest.raises(CelluleError, match="ADC de Vertex refusée"):
        bac.converser(GEMINI, [reponse()], jeton_refuse=True)
    assert bac.methodes_mcp().count("tools/call") == 0


def test_jeton_indisponible(bac: BacGraphrag) -> None:
    # Le point de jeton répond 503 : une panne avant la première question, ni recherche ni appel.
    (tour,) = bac.converser(GEMINI, [reponse()], jeton_statut=503).tours
    assert (tour.issue, tour.cause, tour.appels) == ("panne", "api", ())
    assert not bac.requetes()


def test_jeton_hors_du_chrono(bac: BacGraphrag) -> None:
    # Le jeton de Vertex se prend avant la première question : son délai ne compte pas.
    (tour,) = bac.converser(GEMINI, [reponse()], jeton_s=1.5).tours
    assert tour.issue == "reponse"
    assert tour.duree_s is not None and tour.duree_s < 1.0


# --- T11.1 : seconds tours, dans la même session d'ADK (D10) -------------------------------------


def historique(client: str, corps: dict[str, Any]) -> list[tuple[str, str]]:
    """Les textes d'une requête du modèle, réflexion exclue, dans l'ordre de la conversation, avec
    leur rôle : « user », ou « model » (« assistant » chez Anthropic)."""
    if client == CLAUDE:
        return [
            ("model" if m["role"] == "assistant" else m["role"], bloc["text"])
            for m in corps["messages"]
            for bloc in m["content"]
            if bloc["type"] == "text"
        ]
    return [
        (c["role"], partie["text"])
        for c in corps["contents"]
        for partie in c["parts"]
        if "text" in partie and not partie.get("thought")
    ]


def paire(bac: BacGraphrag, client: str) -> Conversation:
    """Q2 puis Q18 avec le vrai ADK : chaque recherche rend son contexte, chaque appel au modèle sa
    réponse."""
    mcp = {"appels": [{"texte": CONTEXTE}, {"texte": CONTEXTE_Q18}]}
    etapes = [reponse(REPONSE), reponse(REPONSE_Q18)]
    return bac.converser(client, etapes, bac.commande(Q2, Q18, mcp=mcp))


@pytest.mark.parametrize("client", CLIENTS)
def test_second_tour_dans_la_meme_session(bac: BacGraphrag, client: str) -> None:
    # D10 : Q18 se pose dans la session d'ADK de Q2. Son appel au modèle reçoit l'historique (le
    # message de Q2, son contexte compris, puis sa réponse), et enfin son propre message, avec le
    # contexte de sa propre recherche.
    trace = paire(bac, client)
    assert [(tour.question, tour.issue, tour.reponse) for tour in trace.tours] == [
        ("Q2", "reponse", REPONSE),
        ("Q18", "reponse", REPONSE_Q18),
    ]
    premiere, seconde = (requete["corps"] for requete in bac.requetes())
    assert historique(client, premiere) == [("user", message(Q2[1]))]
    assert historique(client, seconde) == [
        ("user", message(Q2[1])),
        ("model", REPONSE),
        ("user", message(Q18[1], CONTEXTE_Q18)),
    ]


@pytest.mark.parametrize("client", CLIENTS)
def test_second_tour_avec_la_reflexion_du_premier(bac: BacGraphrag, client: str) -> None:
    # Relevé sur ADK 2.11.0 : l'historique du second appel garde aussi la réflexion du premier,
    # avant sa réponse (Claude : le bloc thinking, signé ; Gemini : la partie thought).
    paire(bac, client)
    seconde = bac.requetes()[1]["corps"]
    if client == CLAUDE:
        (precedente,) = [m for m in seconde["messages"] if m["role"] == "assistant"]
        reflexion, texte = precedente["content"]
        assert (reflexion["type"], reflexion["thinking"], texte["text"]) == (
            "thinking",
            "Je conclus.",
            REPONSE,
        )
        assert reflexion["signature"]
    else:
        (precedente,) = [c for c in seconde["contents"] if c["role"] == "model"]
        parties = [(partie.get("thought", False), partie["text"]) for partie in precedente["parts"]]
        assert parties == [(True, "Je conclus."), (False, REPONSE)]


@pytest.mark.parametrize("client", CLIENTS)
def test_second_tour_cherche_avec_son_vecteur(bac: BacGraphrag, client: str) -> None:
    # D10 : la recherche de Q18 part de son propre texte, sans réécriture par l'historique : la
    # même requête, avec le vecteur de Q18 (encodé à la création de la campagne, D5), noté par son
    # empreinte dans son tour.
    trace = paire(bac, client)
    assert [appel["arguments"] for appel in bac.appels()] == [
        {"query": RECHERCHE, "params": {"vecteur": list(VECTEUR)}},
        {"query": RECHERCHE, "params": {"vecteur": list(VECTEUR_Q18)}},
    ]
    parametres = [[appel.parametres for appel in tour.appels] for tour in trace.tours]
    assert parametres == [[{"vecteur": EMPREINTE}], [{"vecteur": EMPREINTE_Q18}]]


@pytest.mark.parametrize("client", CLIENTS)
def test_second_tour_mesure_a_part(bac: BacGraphrag, client: str) -> None:
    # Chaque tour compte son seul appel au modèle : Q18 ne reprend pas les tokens de Q2.
    trace = paire(bac, client)
    un_appel = {MODELES[client]: Usage(entree=100, sortie=30, cache_lecture=3000)}
    assert [tour.usages for tour in trace.tours] == [un_appel, un_appel]


@pytest.mark.parametrize("client", CLIENTS)
@pytest.mark.parametrize(
    ("etapes", "issue"),
    [
        pytest.param([reponse(entree=100_000, sortie=30)], ("echec", "budget"), id="echec"),
        pytest.param([erreur(429), erreur(503), erreur(500)], ("panne", "api"), id="panne"),
    ],
)
def test_second_tour_non_pose_sans_reponse_au_premier(
    bac: BacGraphrag, client: str, etapes: list[dict[str, Any]], issue: tuple[str, str]
) -> None:
    # ADR-0012 : Q2 sans réponse (son appel au modèle dépasse le budget ; ou l'API en panne, après
    # 2 reprises), Q18 n'est pas posée : ni recherche ni appel au modèle ; sa ligne relève de
    # l'orchestration (faux d'office après un échec, la paire rejouée après une panne).
    budget = estimation(client, len(CONTEXTE)) + Decimal("0.001")
    mcp = {"appels": [{"texte": CONTEXTE}, {"texte": CONTEXTE_Q18}]}
    commande = bac.commande(Q2, Q18, mcp=mcp, budget_usd=budget)
    trace = bac.converser(client, [*etapes, reponse(REPONSE_Q18)], commande)
    (tour,) = trace.tours
    assert (tour.question, tour.issue, tour.cause) == ("Q2", *issue)
    assert len(bac.requetes()) == len(etapes)
    assert bac.methodes_mcp().count("tools/call") == 1


# --- Point d'entrée (T10.1) ----------------------------------------------------------------------


@pytest.mark.parametrize("client", CLIENTS)
def test_aucune_variable_hors_liste_blanche(bac: BacGraphrag, client: str) -> None:
    # La cellule lancée comme l'orchestration la lancera : le serveur MCP reçoit sa liste blanche
    # telle quelle, rien du processus des tests ; la conversation va au bout, sans trace d'erreur.
    commande = bac.commande(mcp={"noter_env": True, "appels": [{"texte": CONTEXTE}]})
    fini = bac.lancer(client, [reponse(REPONSE)], commande)
    assert fini.returncode == 0, fini.stderr
    (demarrage,) = bac.notes_mcp("env")
    attendu = environnement_agent(client, bac.racine / "home", bac.racine / "claude")
    assert {
        nom: v for nom, v in demarrage["env"].items() if not nom.endswith("BASE_URL")
    } == attendu
    (tour,) = bac.trace().tours
    assert (tour.issue, tour.reponse) == ("reponse", REPONSE)
    assert "Traceback" not in fini.stderr, fini.stderr


@pytest.mark.parametrize("arguments", [[], ["adk-claude"], [CLAUDE, GEMINI]])
def test_client_refuse(arguments: list[str], capsys: pytest.CaptureFixture[str]) -> None:
    assert cellule_graphrag.main(arguments) == 2
    assert "usage" in capsys.readouterr().err


def test_commande_illisible(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"campagne": "essai"}'))
    assert cellule_graphrag.main([CLAUDE]) == 2


def test_point_d_entree(bac: BacGraphrag, monkeypatch: pytest.MonkeyPatch) -> None:
    # main lit la commande sur stdin, vecteurs compris, et la passe à la conversation.
    recues: list[tuple[str, Commande]] = []

    async def noter(client: str, commande: Commande, _tarifs: Any) -> None:
        recues.append((client, commande))

    commande = bac.commande()
    monkeypatch.setattr(cellule_graphrag, "converser", noter)
    monkeypatch.setattr(sys, "stdin", io.StringIO(commande_json(commande)))
    assert cellule_graphrag.main([GEMINI]) == 0
    assert recues == [(GEMINI, commande)]


def test_sigterm_arrete_le_serveur(bac: BacGraphrag) -> None:
    # Arrêtée par l'orchestration en pleine recherche, la cellule arrête son serveur avant de
    # sortir, en 143.
    commande = bac.commande(mcp={"appels": [{"lent_s": 60}]})
    with bac.api(CLAUDE, [reponse()]) as adresse:
        env = environnement_agent(CLAUDE, bac.racine / "home", bac.racine / "claude")
        cellule = subprocess.Popen(
            [sys.executable, "-m", "banc.cellule_graphrag", CLAUDE],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=bac.racine / "travail",
            env=env | {"ANTHROPIC_BASE_URL": adresse},
            text=True,
        )
        assert cellule.stdin is not None
        cellule.stdin.write(commande_json(commande))
        cellule.stdin.close()
        attendre(lambda: "tools/call" in bac.methodes_mcp())
        cellule.send_signal(signal.SIGTERM)
        code = cellule.wait(timeout=20)
    assert code == 128 + signal.SIGTERM
    (demarrage,) = bac.notes_mcp("pid")
    attendre(lambda: not vivant(demarrage["pid"]), 5.0)
    assert bac.requetes() == []
