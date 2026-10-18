"""Cellules GraphRAG, recherche et trace (spec 003, T9.1 ; plan D7, D9 ; ADR-0017) : la recherche de
questions/recherche.cypher par read-cypher, avant l'appel au modèle, contre un faux serveur MCP qui
lui répond (tests/fixtures/faux_serveur_mcp.py). Aucun appel réel, aucun coût.

L'appel au modèle se branche en T10.1 (ADK sans outil) : ici, un rédacteur factice le remplace et
note ce qu'il reçoit. DoD : la commande avec les vecteurs, la connexion avant le chrono, la requête
telle quelle et le vecteur en paramètre, l'empreinte du vecteur à sa place dans la trace, le
garde-fou de l'ADR-0017 avant l'appel. Puis : les issues d'un tour (D13), l'isolement, l'arrêt du
serveur.
"""

import asyncio
import json
import time
from dataclasses import dataclass, field, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from test_cellule_adk import Bac, vivant
from test_essai_recherche import espece

from banc import prix
from banc.cellule import CelluleError, Commande, IsolementError
from banc.cellule_adk import _Comptes, _Tour
from banc.cellule_graphrag import Redaction, converser
from banc.isolement import CleAbsente
from banc.mesures import Conversation
from banc.prix import Usage

RECHERCHE = (Path(__file__).resolve().parents[2] / "questions" / "recherche.cypher").read_text(
    encoding="utf-8"
)
CLE = "sk-ant-api03-cle-factice-du-banc"
CLAUDE, GEMINI = "graphrag-claude", "graphrag-gemini"
CLIENTS = (CLAUDE, GEMINI)
# Modèle et voie de prix des cellules ADK du jalon 2, que les cellules GraphRAG reprennent (D7).
MODELES = {CLAUDE: "claude-sonnet-5-5", GEMINI: "gemini-3.8-flash"}
ACCES = {CLAUDE: "api", GEMINI: "vertex-eu"}
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
# Le contexte d'une recherche qui renverrait les vecteurs (US4) : 20 espèces, chacune avec le sien.
AVEC_VECTEURS = json.dumps([espece(n) | {"embedding": [0.1] * 3072} for n in range(20)])


@dataclass
class RedacteurFactice:
    """Remplace l'appel au modèle (T10.1) : note ce qu'il reçoit et l'instant, répond, et ajoute
    son coût à celui de la conversation."""

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
        """Mène la conversation dans ce processus, avec l'accès de la cellule, et relit sa trace."""
        self.acces(client)
        commande = commande or self.commande()
        asyncio.run(converser(client, commande, prix.charger(), redacteur or RedacteurFactice()))
        return self.trace()

    def appels(self) -> list[dict[str, Any]]:
        """Les appels d'outils reçus par le faux serveur (nom, arguments), dans l'ordre."""
        return [
            note["recu"]["params"]
            for note in self.notes_mcp("recu")
            if note["recu"].get("method") == "tools/call"
        ]


@pytest.fixture
def bac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BacGraphrag:
    for dossier in ("home", "claude", "gcloud", "journal", "travail", "traces"):
        (tmp_path / dossier).mkdir()
    for nom in ("ANTHROPIC_AUTH_TOKEN", "GOOGLE_API_KEY", "GEMINI_API_KEY"):
        monkeypatch.delenv(nom, raising=False)
    monkeypatch.chdir(tmp_path / "travail")
    # Aucune ADC : rien n'appelle le modèle avant T10.1.
    return BacGraphrag(tmp_path, monkeypatch, cle_adc="")


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
