"""Orchestration d'une campagne (T4.3) : le plan (conversations, paires, rotation des cellules), une
conversation par processus isolé, les issues (D13 : panne rejouée, échec compté faux, ADR-0012 pour
le second tour, arrêt sur un plafond), --reprendre, et l'arrêt de tout l'arbre d'une cellule.

Une fausse cellule (tests/fixtures/fausse_cellule.py) joue chaque conduite et écrit sa trace par
banc.mesures, comme une vraie ; puis deux essais de bout en bout : le vrai Claude Code contre une
fausse API (tests/fixtures/fausse_api.py) avec le vrai lanceur, et la cellule ADK contre la sienne.
Aucun appel réel, aucun coût. Le nettoyage d'Aura (scripts/transactions.sh) et le contrôle de Q2
sont remplacés par des faux : on compte leurs appels.
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from banc import orchestration, revue
from banc import questions as banc_questions
from banc.__main__ import main
from banc.cellule import RACINE, Plafonds
from banc.isolement import environnement_agent
from banc.mesures import lire, lire_lignes, nom_de_trace
from banc.notation import Controle, NotationError
from banc.orchestration import (
    CELLULES,
    PROGRAMMES,
    ArretPlafond,
    Campagne,
    Demande,
    Etape,
    Moyens,
    Orchestration,
    OrchestrationError,
    arreter,
    commande,
    conversations,
    dernier_essai,
    descendants,
    ecrire_campagne,
    lire_campagne,
    message,
    outils_des_agents,
    pannes_de_suite,
    transactions,
    verrou,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
FAUSSE_CELLULE = FIXTURES / "fausse_cellule.py"
CLE = "sk-ant-api03-cle-factice-du-banc"
BANC = banc_questions.charger()
EQUIPE_VALIDE = Controle(6, (), True)
CC, AC, AG = CELLULES
INSTANCE = "f4c7e9a2"
SECRET = (
    f"NEO4J_URI=neo4j+s://{INSTANCE}.databases.neo4j.io\nNEO4J_USERNAME={INSTANCE}\n"
    f"NEO4J_PASSWORD=mdp-factice-du-banc\nNEO4J_DATABASE={INSTANCE}\n"
)
# Une réponse coûte 0,20 $ à une cellule Claude : 100 000 tokens d'entrée à 2 $ le million.
CHERE = {"tours": [{"issue": "reponse", "entree": 100_000, "sortie": 0}]}


# --- Bac à sable ----------------------------------------------------------------------------------


@dataclass
class Bac:
    """Dossiers de la campagne, fausse cellule et son scénario ; nettoyages comptés."""

    racine: Path
    sortie: list[str] = field(default_factory=list)
    # Conversations lancées au moment de chaque nettoyage d'Aura.
    moments: list[int] = field(default_factory=list)

    @property
    def nettoyages(self) -> int:
        return len(self.moments)

    @property
    def fichier_scenario(self) -> Path:
        return self.racine / "journal" / "scenario.json"

    @property
    def journal(self) -> Path:
        return self.racine / "journal" / "cellules.jsonl"

    def scenario(self, conduites: dict[str, dict[str, Any]]) -> None:
        """Conduite de la fausse cellule par conversation : « <cellule> p<passe> <Q…> e<essai> »."""
        self.fichier_scenario.write_text(json.dumps(conduites))

    def nettoyer(self) -> str:
        self.moments.append(len(self.lancees()))
        return "transactions : aucune lecture active"

    def moyens(self, **reglages: Any) -> Moyens:
        programmes = {
            cellule: (
                sys.executable,
                str(FAUSSE_CELLULE),
                str(self.fichier_scenario),
                str(self.journal),
                cellule,
            )
            for cellule in CELLULES
        }
        valeurs: dict[str, Any] = {
            "mesures": self.racine / "mesures",
            "traces": self.racine / "traces",
            "programmes": programmes,
            "chemins": (self.racine / "outils",),
            "controle": lambda _liste: EQUIPE_VALIDE,
            "nettoyer": self.nettoyer,
            "marge_s": 30.0,
            "ecrire": self.sortie.append,
        }
        return Moyens(**(valeurs | reglages))

    def orchestrer(self, campagne: Campagne, plafond: str = "100", **reglages: Any) -> int:
        moyens = self.moyens(**reglages)
        return Orchestration(campagne, Decimal(plafond), moyens, BANC).lancer()

    def commande(self, plafond: str = "100", **demande: Any) -> int:
        return commande(Demande("essai", Decimal(plafond), **demande), self.moyens())

    def lignes(self) -> list[dict[str, str]]:
        fichier = self.racine / "mesures" / "essai.csv"
        return lire_lignes(fichier) if fichier.exists() else []

    def notes(self) -> list[dict[str, Any]]:
        if not self.journal.exists():
            return []
        return [json.loads(texte) for texte in self.journal.read_text().splitlines()]

    def lancees(self) -> list[str]:
        """Les conversations lancées, dans l'ordre : « <cellule> p<passe> <Q…> e<essai> »."""
        return [note["cle"] for note in self.notes()]

    def resume(self) -> list[tuple[str, str, str, str, str]]:
        """Les lignes du CSV, réduites à cellule, question, essai, issue et cause."""
        return [
            (v["cellule"], v["question"], v["essai"], v["issue"], v["cause"]) for v in self.lignes()
        ]


@pytest.fixture
def bac(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Bac:
    for dossier in ("journal", "outils", "gcloud", "mesures", "traces"):
        (tmp_path / dossier).mkdir()
    # Clé factice : la fausse cellule note son environnement, la liste blanche, clé comprise.
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path / "gcloud"))
    monkeypatch.setattr(orchestration, "GRACE_S", 2.0)
    nouveau = Bac(tmp_path)
    nouveau.scenario({})
    return nouveau


def campagne(
    *conversations_: tuple[str, ...],
    passes: int = 1,
    cellules: tuple[str, ...] = CELLULES,
    cache_1h: bool = False,
    **plafonds: Any,
) -> Campagne:
    return Campagne(
        "essai",
        passes,
        conversations_ or (("Q1",),),
        cellules,
        cache_1h,
        Plafonds(**plafonds),
    )


def vivant(pid: int) -> bool:
    """Le processus existe et n'est pas un zombie."""
    try:
        etat = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except FileNotFoundError, ProcessLookupError:
        # Disparu, ou en train de disparaître : lire son stat donne alors ESRCH.
        return False
    return etat != "Z"


def attendre(condition: Callable[[], bool], delai_s: float = 10.0) -> None:
    fin = time.monotonic() + delai_s
    while not condition():
        assert time.monotonic() < fin, "condition jamais remplie"
        time.sleep(0.05)


def tour(issue: str, cause: str | None = None) -> dict[str, Any]:
    return {"issue": issue, "cause": cause}


# --- Le plan --------------------------------------------------------------------------------------


def test_conversations_du_banc() -> None:
    # Les 30 questions, par numéro, en 28 conversations : Q18 et Q28 au second tour de Q2 et Q27.
    plan = conversations(BANC)
    assert len(plan) == 28
    assert plan[:3] == (("Q1",), ("Q2", "Q18"), ("Q3",))
    assert ("Q27", "Q28") in plan
    assert sorted(q for c in plan for q in c) == sorted(BANC.questions)
    assert [c for c in plan if c[0] in {"Q18", "Q28"}] == []


def test_conversations_demandees() -> None:
    # L'ordre demandé est gardé ; un second tour rejoint la conversation de son tour précédent.
    assert conversations(BANC, ["Q19", "Q2", "Q18"]) == (("Q19",), ("Q2", "Q18"))
    assert conversations(BANC, ["Q18", "Q2"]) == (("Q2", "Q18"),)
    assert conversations(BANC, ["Q2"]) == (("Q2",),)


def test_second_tour_sans_le_premier() -> None:
    with pytest.raises(OrchestrationError, match="demander aussi Q27"):
        conversations(BANC, ["Q1", "Q28"])


def test_question_inconnue() -> None:
    with pytest.raises(OrchestrationError, match="questions inconnues : Q31"):
        conversations(BANC, ["Q1", "Q31"])


def test_question_en_double() -> None:
    with pytest.raises(OrchestrationError, match="en double"):
        conversations(BANC, ["Q1", "Q3", "Q1"])


def test_rotation_des_cellules() -> None:
    # Un cran à chaque conversation et à chaque passe (choix de Julien).
    plan = campagne(("Q1",), ("Q2", "Q18"), ("Q3",), passes=2).etapes()
    ordre = [(e.passe, e.questions[0], e.cellule) for e in plan]
    assert ordre == [
        (1, "Q1", CC), (1, "Q1", AC), (1, "Q1", AG),
        (1, "Q2", AC), (1, "Q2", AG), (1, "Q2", CC),
        (1, "Q3", AG), (1, "Q3", CC), (1, "Q3", AC),
        (2, "Q1", AC), (2, "Q1", AG), (2, "Q1", CC),
        (2, "Q2", AG), (2, "Q2", CC), (2, "Q2", AC),
        (2, "Q3", CC), (2, "Q3", AC), (2, "Q3", AG),
    ]  # fmt: skip
    assert plan[3] == Etape(1, AC, ("Q2", "Q18"))


def test_message_pose() -> None:
    # Q2 : l'équipe en tête du message (D6) ; les autres : le texte seul.
    q2 = BANC.questions["Q2"]
    assert q2.preambule is not None
    assert message(q2) == f"{q2.preambule}\n\n{q2.texte}"
    assert message(BANC.questions["Q1"]) == BANC.questions["Q1"].texte


@pytest.mark.parametrize(
    "reglages",
    [
        {"nom": "Essai"},
        {"passes": 0},
        {"conversations": ()},
        {"conversations": (("Q1",), ())},
        {"conversations": (("Q1",), ("Q1",))},
        {"cellules": ()},
        {"cellules": (CC, CC)},
        {"cellules": (CC, "claude-autre")},
    ],
)
def test_campagne_invalide(reglages: dict[str, Any]) -> None:
    valide = campagne(("Q1",), ("Q2", "Q18"))
    with pytest.raises(OrchestrationError, match="campagne invalide"):
        replace(valide, **reglages)


def test_parametres_relus(tmp_path: Path) -> None:
    fixee = campagne(("Q19",), ("Q2", "Q18"), passes=3, cellules=(AG, CC), cache_1h=True, tours=5)
    fichier = tmp_path / "campagne.json"
    ecrire_campagne(fichier, fixee)
    assert lire_campagne(fichier) == fixee
    # Jamais réécrits.
    with pytest.raises(FileExistsError):
        ecrire_campagne(fichier, fixee)


@pytest.mark.parametrize(
    ("cle", "valeur"),
    [("format", 2), ("passes", 2.0), ("cache_1h", 1), ("inconnue", True)],
)
def test_parametres_illisibles(tmp_path: Path, cle: str, valeur: Any) -> None:
    fichier = tmp_path / "campagne.json"
    ecrire_campagne(fichier, campagne())
    contenu = json.loads(fichier.read_text()) | {cle: valeur}
    fichier.write_text(json.dumps(contenu))
    with pytest.raises(OrchestrationError, match="illisible"):
        lire_campagne(fichier)


# --- Essai à mener --------------------------------------------------------------------------------


def lignes_de(*cas: tuple[str, str, str]) -> list[dict[str, str]]:
    """Des lignes du CSV d'une étape de claude-code en passe 1 : (question, essai, issue)."""
    return [{"cellule": CC, "passe": "1", "question": q, "essai": e, "issue": i} for q, e, i in cas]


def test_dernier_essai(tmp_path: Path) -> None:
    paire = Etape(1, CC, ("Q2", "Q18"))
    assert dernier_essai(paire, [], tmp_path) == (0, None)
    finie = lignes_de(("Q2", "1", "reponse"), ("Q18", "1", "echec"))
    assert dernier_essai(paire, finie, tmp_path) == (1, frozenset({"reponse", "echec"}))
    rejouee = [*finie, *lignes_de(("Q2", "2", "panne"))]
    assert dernier_essai(paire, rejouee, tmp_path) == (2, frozenset({"panne"}))
    # Ni une autre cellule, ni une autre passe, ni une autre question ne comptent.
    autres = [
        {"cellule": AC, "passe": "1", "question": "Q2", "essai": "3", "issue": "panne"},
        {"cellule": CC, "passe": "2", "question": "Q2", "essai": "3", "issue": "panne"},
        {"cellule": CC, "passe": "1", "question": "Q3", "essai": "3", "issue": "panne"},
    ]
    assert dernier_essai(paire, finie + autres, tmp_path) == (1, frozenset({"reponse", "echec"}))


def test_pannes_de_suite() -> None:
    # Seules comptent les pannes des derniers essais, à la suite.
    paire = Etape(1, CC, ("Q2", "Q18"))
    assert pannes_de_suite(paire, []) == 0
    deux = lignes_de(("Q2", "1", "panne"), ("Q2", "2", "reponse"), ("Q18", "2", "panne"))
    assert pannes_de_suite(paire, deux) == 2
    coupee = lignes_de(("Q2", "1", "panne"), ("Q2", "2", "arret"), ("Q2", "3", "panne"))
    assert pannes_de_suite(paire, coupee) == 1


def test_dernier_essai_d_une_trace_sans_ligne(tmp_path: Path) -> None:
    # Cellule ou harnais arrêtés en route : la trace de l'essai 2 existe, sans ligne. Les traces
    # d'une autre conversation ou au numéro illisible ne comptent pas.
    paire = Etape(1, CC, ("Q2", "Q18"))
    (tmp_path / nom_de_trace(CC, 1, ("Q2", "Q18"), 2)).touch()
    (tmp_path / nom_de_trace(CC, 1, ("Q2",), 7)).touch()
    (tmp_path / nom_de_trace(CC, 1, ("Q2", "Q18"), 9)).with_suffix(".txt").touch()
    (tmp_path / nom_de_trace(CC, 1, ("Q2", "Q18"), 8).replace("-e8", "-e8b")).touch()
    panne = lignes_de(("Q2", "1", "panne"))
    assert dernier_essai(paire, panne, tmp_path) == (2, None)
    assert dernier_essai(paire, [], tmp_path) == (2, None)
    # Une trace écartée (cellule fautive) garde son numéro : la conversation se rejoue au suivant.
    ecartee = tmp_path / (nom_de_trace(CC, 1, ("Q2", "Q18"), 3) + ".ecartee")
    ecartee.touch()
    assert dernier_essai(paire, panne, tmp_path) == (3, None)


# --- Une campagne, avec la fausse cellule ---------------------------------------------------------


def test_campagne_finie(bac: Bac) -> None:
    assert bac.orchestrer(campagne(("Q1",), ("Q2", "Q18"))) == 0
    # Les cellules tournent ; chaque conversation est lancée une fois, à l'essai 1.
    assert bac.lancees() == [
        f"{CC} p1 Q1 e1", f"{AC} p1 Q1 e1", f"{AG} p1 Q1 e1",
        f"{AC} p1 Q2+Q18 e1", f"{AG} p1 Q2+Q18 e1", f"{CC} p1 Q2+Q18 e1",
    ]  # fmt: skip
    lignes = bac.lignes()
    assert len(lignes) == 9
    assert {(v["issue"], v["essai"]) for v in lignes} == {("reponse", "1")}
    assert all(v["note"] and v["source"] for v in lignes)
    # Q2 au premier tour, Q18 au second, dans la même conversation (une trace par cellule).
    traces = sorted((bac.racine / "traces" / "essai").glob("*Q2+Q18*.jsonl"))
    assert [[t.question for t in lire(f).tours] for f in traces] == [["Q2", "Q18"]] * 3
    # Un seul nettoyage d'Aura, au départ, avant toute conversation.
    assert bac.moments == [0]
    # Une ligne par conversation, sans note : la revue reste à l'aveugle (D4).
    assert len(bac.sortie) == 8
    assert not any(mot in " ".join(bac.sortie) for mot in ("juste", "partiel", "faux", "revoir"))


def test_isolement_de_chaque_conversation(bac: Bac) -> None:
    assert bac.orchestrer(campagne(("Q2", "Q18"), cellules=(CC, AG))) == 0
    notes = bac.notes()
    for note, cellule in zip(notes, (CC, AG), strict=True):
        home, travail = Path(note["env"]["HOME"]), Path(note["cwd"])
        claude = home.parent / "claude"
        # La liste blanche de la cellule, pour seul environnement (D3).
        attendu = environnement_agent(cellule, home, claude, (bac.racine / "outils",))
        assert note["env"] == attendu
        # Dossiers neufs, hors du dépôt, détruits après la conversation.
        assert home.parent == travail.parent
        assert note["env"].get("CLAUDE_CONFIG_DIR", str(claude)) == str(claude)
        assert home.parent.name.startswith("banc-agent-")
        assert not travail.is_relative_to(RACINE)
        assert note["contenu"] == []
        assert not home.parent.exists()
        # Sa propre session, donc son propre groupe : l'orchestration peut l'arrêter en entier.
        assert note["pgid"] == note["sid"] == note["pid"] != os.getpgid(0)
    # Chacune ses dossiers.
    assert notes[0]["env"]["HOME"] != notes[1]["env"]["HOME"]
    # Le message posé : l'équipe de Q2 en tête, puis Q18.
    q2, q18 = BANC.questions["Q2"], BANC.questions["Q18"]
    assert notes[0]["messages"] == [message(q2), message(q18)]


def test_cache_et_plafonds_transmis(bac: Bac) -> None:
    assert bac.orchestrer(campagne(cellules=(CC,), cache_1h=True, tours=4)) == 0
    (note,) = bac.notes()
    assert note["cache_1h"] is True
    assert note["env"]["ENABLE_PROMPT_CACHING_1H"] == "1"
    assert note["plafonds"]["tours"] == 4


def test_panne_rejouee(bac: Bac) -> None:
    bac.scenario({f"{CC} p1 Q1 e1": {"tours": [tour("panne", "api")]}})
    assert bac.orchestrer(campagne()) == 0
    assert bac.lancees() == [f"{CC} p1 Q1 e1", f"{CC} p1 Q1 e2", f"{AC} p1 Q1 e1", f"{AG} p1 Q1 e1"]
    assert bac.resume()[:2] == [(CC, "Q1", "1", "panne", "api"), (CC, "Q1", "2", "reponse", "")]
    # Une panne n'a pas de note ; Aura est nettoyé au départ, puis après elle seulement.
    assert bac.lignes()[0]["note"] == ""
    assert bac.moments == [0, 1]
    # La revue retient l'essai 2, sans contester le remplacement (une panne le justifie).
    assert [(v["cellule"], v["essai"]) for v in revue.retenues(bac.lignes())] == [
        (CC, "2"),
        (AC, "1"),
        (AG, "1"),
    ]


def test_panne_du_second_tour_rejoue_la_paire(bac: Bac) -> None:
    bac.scenario({f"{AG} p1 Q2+Q18 e1": {"tours": [tour("reponse"), tour("panne", "serveur")]}})
    assert bac.orchestrer(campagne(("Q2", "Q18"), cellules=(AG,))) == 0
    assert bac.resume() == [
        (AG, "Q2", "1", "reponse", ""),
        (AG, "Q18", "1", "panne", "serveur"),
        (AG, "Q2", "2", "reponse", ""),
        (AG, "Q18", "2", "reponse", ""),
    ]
    assert [v["essai"] for v in revue.retenues(bac.lignes())] == ["2", "2"]


def test_panne_du_premier_tour(bac: Bac) -> None:
    # Q18 n'a pas été posée : aucune ligne pour elle avant la reprise de la paire.
    bac.scenario({f"{CC} p1 Q2+Q18 e1": {"tours": [tour("panne", "api")]}})
    assert bac.orchestrer(campagne(("Q2", "Q18"), cellules=(CC,))) == 0
    assert bac.resume() == [
        (CC, "Q2", "1", "panne", "api"),
        (CC, "Q2", "2", "reponse", ""),
        (CC, "Q18", "2", "reponse", ""),
    ]


def test_deux_pannes_de_suite_puis_une_reponse(bac: Bac) -> None:
    panne = {"tours": [tour("panne", "reprises")]}
    bac.scenario({f"{CC} p1 Q1 e1": panne, f"{CC} p1 Q1 e2": panne})
    assert bac.orchestrer(campagne(cellules=(CC,))) == 0
    assert [v["issue"] for v in bac.lignes()] == ["panne", "panne", "reponse"]


def test_trois_pannes_de_suite(bac: Bac) -> None:
    # Circuit breaker du plan : la campagne s'arrête, rien n'est tenté au-delà.
    panne = {"tours": [tour("panne", "api")]}
    bac.scenario({f"{CC} p1 Q1 e{essai}": panne for essai in (1, 2, 3)})
    with pytest.raises(OrchestrationError, match="3 pannes de suite"):
        bac.orchestrer(campagne(("Q1",), ("Q3",), cellules=(CC,)))
    assert bac.lancees() == [f"{CC} p1 Q1 e1", f"{CC} p1 Q1 e2", f"{CC} p1 Q1 e3"]
    assert bac.nettoyages == 4


def pannes_dans_une_serie(bac: Bac, nombre: int) -> int:
    """Une panne, rejouée avec succès, dans autant de conversations de la série claude-code, p1."""
    questions = ("Q1", "Q3", "Q4")
    panne = {"tours": [tour("panne", "api")]}
    bac.scenario({f"{CC} p1 {q} e1": panne for q in questions[:nombre]})
    return bac.orchestrer(campagne(*((q,) for q in questions), cellules=(CC, AG)))


def test_passe_invalide_signalee(bac: Bac) -> None:
    # Plus de 2 pannes dans une série : signalé, la campagne va au bout, puis sort en 1.
    assert pannes_dans_une_serie(bac, 3) == 1
    assert len(bac.lignes()) == 9
    assert sum("passe invalide" in texte for texte in bac.sortie) == 2


def test_deux_pannes_dans_une_serie(bac: Bac) -> None:
    assert pannes_dans_une_serie(bac, 2) == 0
    assert not any("passe invalide" in texte for texte in bac.sortie)


def test_premier_tour_en_echec(bac: Bac) -> None:
    # ADR-0012 : Q18 compte faux sans être posée, une ligne « echec » à 0 s, sans tokens ni coût.
    bac.scenario({f"{CC} p1 Q2+Q18 e1": {"tours": [tour("echec", "delai") | {"entree": 500}]}})
    assert bac.orchestrer(campagne(("Q2", "Q18"), cellules=(CC,))) == 0
    q2, q18 = bac.lignes()
    assert (q2["issue"], q2["cause"], q2["note"], q2["source"]) == ("echec", "delai", "faux", "non")
    assert Decimal(q2["cout_usd"]) > 0
    attendu = {
        "question": "Q18", "essai": "1", "issue": "echec", "cause": "precedent", "note": "faux",
        "source": "non", "duree_s": "0.00", "appels": "0", "entree": "0", "sortie": "0",
        "cout_usd": "0.000000", "empreinte": "",
    }  # fmt: skip
    assert {cle: q18[cle] for cle in attendu} == attendu
    # Un échec ne se relance pas (ADR-0009) ; Aura est nettoyé.
    assert bac.lancees() == [f"{CC} p1 Q2+Q18 e1"]
    assert bac.nettoyages == 2


def test_second_tour_en_echec(bac: Bac) -> None:
    bac.scenario({f"{CC} p1 Q2+Q18 e1": {"tours": [tour("reponse"), tour("echec", "tours")]}})
    assert bac.orchestrer(campagne(("Q2", "Q18"), cellules=(CC,))) == 0
    assert [(v["question"], v["cause"]) for v in bac.lignes()] == [("Q2", ""), ("Q18", "tours")]


def test_question_seule_en_echec(bac: Bac) -> None:
    # Sans second tour, aucune ligne de plus.
    bac.scenario({f"{CC} p1 Q1 e1": {"tours": [tour("echec", "budget")]}})
    assert bac.orchestrer(campagne(cellules=(CC,))) == 0
    assert bac.resume() == [(CC, "Q1", "1", "echec", "budget")]


def test_credits_epuises_puis_reprise(bac: Bac) -> None:
    bac.scenario({f"{AC} p1 Q2+Q18 e1": {"tours": [tour("reponse"), tour("arret", "plafond")]}})
    code = bac.commande(questions=("Q2", "Q18", "Q3"), cellules=(CC, AC))
    assert code == orchestration.PLAFOND
    # Arrêt aussitôt : ni Q3, ni l'autre cellule après l'arrêt.
    assert bac.lancees() == [f"{CC} p1 Q2+Q18 e1", f"{AC} p1 Q2+Q18 e1"]
    assert bac.nettoyages == 2
    # Après recharge : la paire est rejouée, puis la campagne continue.
    assert bac.commande(reprendre=True) == 0
    assert bac.lancees()[2:] == [f"{AC} p1 Q2+Q18 e2", f"{AC} p1 Q3 e1", f"{CC} p1 Q3 e1"]
    assert len(revue.retenues(bac.lignes())) == 6


def test_plafond_de_la_campagne(bac: Bac) -> None:
    # Chaque conversation coûte 0,20 $ ; avant chacune, la dépense plus le budget d'une
    # conversation (0,50 $) ne doit pas dépasser 1,10 $ : la 4e passe pile, la 5e non.
    questions = ("Q1", "Q3", "Q4", "Q5", "Q6")
    bac.scenario({f"{CC} p1 {q} e1": CHERE for q in questions})
    with pytest.raises(ArretPlafond, match=r"0\.800000 \$ dépensés sur 1\.10 \$"):
        bac.orchestrer(campagne(*((q,) for q in questions), cellules=(CC,)), plafond="1.10")
    assert len(bac.lignes()) == 4


def test_plafond_compte_les_traces_ecartees(bac: Bac) -> None:
    # Une trace écartée (cellule fautive) a payé ses tokens : le plafond les compte.
    fautive = {"tours": [CHERE["tours"][0] | {"issue": "echec", "cause": "delai"}, tour("reponse")]}
    bac.scenario({f"{CC} p1 Q2+Q18 e1": fautive | {"continuer": True}})
    fixee = campagne(("Q2", "Q18"), cellules=(CC,))
    with pytest.raises(OrchestrationError, match="écarter cette trace"):
        bac.orchestrer(fixee)
    (fichier,) = (bac.racine / "traces" / "essai").glob("*.jsonl")
    fichier.rename(fichier.with_name(fichier.name + ".ecartee"))
    # 0,20 $ de Q2 et 0,003 $ de Q18, puis la réserve de 0,50 $.
    with pytest.raises(ArretPlafond, match="plafond de la campagne"):
        bac.orchestrer(fixee, plafond="0.70")
    assert bac.orchestrer(fixee, plafond="0.703") == 0


def test_plafond_et_les_paires(bac: Bac) -> None:
    # Une paire coûte 0,40 $ et laisse deux lignes ; avant Q1, 0,40 + 0,50 passe pile sous
    # 0,90 $ : la paire n'est comptée qu'une fois, ses lignes reconnues à sa trace.
    paire = {"tours": [CHERE["tours"][0], CHERE["tours"][0]]}
    bac.scenario({f"{CC} p1 Q2+Q18 e1": paire})
    assert bac.orchestrer(campagne(("Q2", "Q18"), ("Q1",), cellules=(CC,)), plafond="0.90") == 0
    assert len(bac.lignes()) == 3


def test_plafond_releve_a_la_reprise(bac: Bac) -> None:
    bac.scenario({f"{CC} p1 {q} e1": CHERE for q in ("Q1", "Q3")})
    assert bac.commande(plafond="0.60", questions=("Q1", "Q3"), cellules=(CC,)) == 3
    assert len(bac.lignes()) == 1
    assert bac.commande(plafond="0.90", reprendre=True) == 0
    assert len(bac.lignes()) == 2


def test_erreur_technique_apres_la_trace(bac: Bac) -> None:
    # Sortie en 2 après une trace complète : la campagne s'arrête, sans ligne ; la reprise note la
    # trace (une erreur après le dernier tour ne fausse pas la mesure) au lieu de la rejouer.
    bac.scenario({f"{CC} p1 Q1 e1": {"code": 2}})
    with pytest.raises(OrchestrationError, match="sortie en 2"):
        bac.orchestrer(campagne(("Q1",), ("Q3",)))
    assert bac.lignes() == []
    assert bac.nettoyages == 2
    assert bac.commande(reprendre=False, questions=("Q1", "Q3")) == 2  # campagne déjà là
    ecrire_campagne(bac.racine / "traces" / "essai" / "campagne.json", campagne(("Q1",), ("Q3",)))
    assert bac.commande(reprendre=True) == 0
    assert f"{CC} p1 Q1 e2" not in bac.lancees()
    assert bac.resume()[0] == (CC, "Q1", "1", "reponse", "")
    assert len(bac.lignes()) == 6


def test_erreur_technique_en_plein_tour(bac: Bac) -> None:
    # Sortie en 2 en plein tour : la trace est inachevée ; la reprise rejoue la conversation à
    # l'essai suivant, sans écraser la trace.
    bac.scenario({f"{CC} p1 Q1 e1": {"quitter": 0, "code": 2}})
    with pytest.raises(OrchestrationError, match="sortie en 2"):
        bac.orchestrer(campagne(cellules=(CC,)))
    assert bac.orchestrer(campagne(cellules=(CC,))) == 0
    assert bac.lancees() == [f"{CC} p1 Q1 e1", f"{CC} p1 Q1 e2"]
    assert bac.resume() == [(CC, "Q1", "2", "reponse", "")]


def test_cellule_sans_trace(bac: Bac) -> None:
    bac.scenario({f"{CC} p1 Q1 e1": {"sans_trace": True}})
    with pytest.raises(OrchestrationError, match="trace absente ou inachevée"):
        bac.orchestrer(campagne(cellules=(CC,)))
    assert bac.nettoyages == 2


def test_trace_d_une_autre_conversation(bac: Bac) -> None:
    bac.scenario({f"{CC} p1 Q1 e1": {"autre_entete": True}})
    with pytest.raises(OrchestrationError, match="en-tête d'une autre conversation"):
        bac.orchestrer(campagne(cellules=(CC,)))
    assert bac.lignes() == []


def test_cellule_bloquee_tuee(bac: Bac) -> None:
    # Au-delà de ses plafonds et de la marge, la cellule est tuée : erreur technique (choix de
    # Julien), sans ligne ; Aura est nettoyé ; la trace garde le tour inachevé.
    bac.scenario({f"{CC} p1 Q1 e1": {"bloquer": 0}})
    debut = time.monotonic()
    with pytest.raises(OrchestrationError, match="cellule tuée"):
        bac.orchestrer(campagne(cellules=(CC,), delai_s=0.5, connexion_s=0.2), marge_s=0.5)
    # Échéance : 0,2 + (0,5 + 0,2) + 0,5 s.
    assert 1.4 <= time.monotonic() - debut < 6
    (note,) = bac.notes()
    assert not vivant(note["pid"])
    assert bac.lignes() == []
    assert bac.nettoyages == 2
    (fichier,) = (bac.racine / "traces" / "essai").glob("*.jsonl")
    (inacheve,) = lire(fichier).tours
    assert inacheve.issue is None
    # La reprise rejoue la conversation à l'essai suivant.
    assert bac.orchestrer(campagne(cellules=(CC,)), marge_s=0.5) == 0
    assert bac.resume() == [(CC, "Q1", "2", "reponse", "")]


def test_cellule_tuee_apres_sa_trace(bac: Bac) -> None:
    # Bloquée après son dernier tour (arrêt du client), la cellule est tuée ; sa trace est
    # complète : la reprise la note, sans rejouer l'échec qu'elle porte (ADR-0009).
    conduite = {"tours": [tour("echec", "delai")], "attendre_a_la_fin": True}
    bac.scenario({f"{CC} p1 Q1 e1": conduite})
    fixee = campagne(cellules=(CC,), delai_s=0.5, connexion_s=0.2)
    with pytest.raises(OrchestrationError, match="cellule tuée"):
        bac.orchestrer(fixee, marge_s=0.5)
    assert bac.orchestrer(fixee, marge_s=0.5) == 0
    assert bac.lancees() == [f"{CC} p1 Q1 e1"]
    assert bac.resume() == [(CC, "Q1", "1", "echec", "delai")]


def test_cellule_tuee_meme_sortie_en_zero(bac: Bac) -> None:
    # Arrêtée par la surveillance, la cellule sort en 0 sur SIGTERM, sa trace complète : elle
    # reste tuée (erreur technique, choix de Julien) ; la reprise note sa trace.
    conduite = {"attendre_a_la_fin": True, "zero_sur_sigterm": True}
    bac.scenario({f"{CC} p1 Q1 e1": conduite})
    fixee = campagne(cellules=(CC,), delai_s=0.5, connexion_s=0.2)
    with pytest.raises(OrchestrationError, match=r"cellule tuée \(code 0\)"):
        bac.orchestrer(fixee, marge_s=0.5)
    assert bac.lignes() == []
    assert bac.orchestrer(fixee, marge_s=0.5) == 0
    assert bac.resume() == [(CC, "Q1", "1", "reponse", "")]


def test_plafond_compte_les_traces_sans_ligne(bac: Bac) -> None:
    # Tuée en plein tour, la cellule a payé 0,20 $ sans laisser de ligne : à la reprise, le
    # plafond les compte, avec la réserve d'une conversation (0,50 $) ; 0,70 $ passe pile.
    conduite = {"tours": CHERE["tours"], "bloquer": 0}
    bac.scenario({f"{CC} p1 Q1 e1": conduite})
    fixee = campagne(cellules=(CC,), delai_s=0.5, connexion_s=0.2)
    with pytest.raises(OrchestrationError, match="cellule tuée"):
        bac.orchestrer(fixee, marge_s=0.5)
    with pytest.raises(ArretPlafond, match="plafond de la campagne"):
        bac.orchestrer(fixee, plafond="0.69", marge_s=0.5)
    assert bac.orchestrer(fixee, plafond="0.70", marge_s=0.5) == 0
    assert bac.lancees() == [f"{CC} p1 Q1 e1", f"{CC} p1 Q1 e2"]


def test_cellule_sourde_et_son_enfant(bac: Bac) -> None:
    # SIGTERM ignoré : SIGKILL après la grâce ; l'enfant lancé dans sa propre session (comme le
    # serveur MCP d'ADK) ne survit pas non plus.
    bac.scenario({f"{CC} p1 Q1 e1": {"bloquer": 0, "sourde": True, "enfant": True}})
    with pytest.raises(OrchestrationError, match="cellule tuée"):
        bac.orchestrer(campagne(cellules=(CC,), delai_s=0.5, connexion_s=0.2), marge_s=0.5)
    (note,) = bac.notes()
    assert note["enfant"] != note["pgid"]
    assert not vivant(note["pid"])
    attendre(lambda: not vivant(note["enfant"]), 5.0)


@pytest.mark.parametrize("numero", [signal.SIGTERM, signal.SIGHUP])
def test_signal_au_harnais(bac: Bac, numero: signal.Signals) -> None:
    # Un SIGTERM, ou un SIGHUP (terminal fermé), interrompt le harnais comme un Ctrl-C : la
    # cellule en cours est arrêtée, Aura nettoyé, et `banc lancer` sort en 130 ; --reprendre
    # rejouera la conversation. Le refuge fait échouer le test, au lieu de tuer pytest, si la
    # commande ne pose pas son gestionnaire.
    def refuge(_numero: int, _cadre: object) -> None:
        raise AssertionError(f"{numero!r} reçu hors du gestionnaire de banc lancer")

    bac.scenario({f"{CC} p1 Q1 e1": {"bloquer": 0}})
    precedent = signal.signal(numero, refuge)
    attente = threading.Timer(1.0, os.kill, (os.getpid(), numero))
    attente.start()
    try:
        assert bac.commande(questions=("Q1",), cellules=(CC,)) == orchestration.INTERROMPUE
        # Le gestionnaire d'avant la commande est rendu.
        assert signal.getsignal(numero) is refuge
    finally:
        attente.cancel()
        signal.signal(numero, precedent)
    (note,) = bac.notes()
    attendre(lambda: not vivant(note["pid"]), 5.0)
    assert bac.nettoyages == 2


def test_sighup_sous_nohup(bac: Bac) -> None:
    # Sous nohup, SIGHUP est ignoré : fermer le terminal n'interrompt pas la campagne.
    bac.scenario({f"{CC} p1 Q1 e1": {"signal_au_harnais": signal.SIGHUP}})
    precedent = signal.signal(signal.SIGHUP, signal.SIG_IGN)
    try:
        assert bac.commande(questions=("Q1",), cellules=(CC,)) == 0
        assert signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
    finally:
        signal.signal(signal.SIGHUP, precedent)
    assert len(bac.lignes()) == 1


def test_restes_du_groupe_balayes(bac: Bac) -> None:
    # Une cellule sortie normalement ne laisse rien derrière elle dans son groupe.
    bac.scenario({f"{CC} p1 Q1 e1": {"orphelin": True}})
    assert bac.orchestrer(campagne(cellules=(CC,))) == 0
    (note,) = bac.notes()
    attendre(lambda: not vivant(note["orphelin"]), 5.0)


@pytest.mark.parametrize(
    ("conduite", "message_"),
    [
        ({"quitter": 0}, "trace absente ou inachevée, cellule sortie en 0"),
        ({"seulement": 1}, "trace absente ou inachevée, cellule sortie en 0"),
        (
            {"tours": [tour("panne", "api"), tour("reponse")], "continuer": True},
            "un tour suit un tour sans réponse, hors de D13",
        ),
    ],
)
def test_trace_incoherente(bac: Bac, conduite: dict[str, Any], message_: str) -> None:
    # Sortie en 0, mais une trace qu'une vraie cellule n'écrit jamais : erreur technique.
    bac.scenario({f"{CC} p1 Q2+Q18 e1": conduite})
    with pytest.raises(OrchestrationError, match=message_):
        bac.orchestrer(campagne(("Q2", "Q18"), cellules=(CC,)))
    assert bac.lignes() == []
    assert bac.nettoyages == 2


def test_nettoyage_avant_le_controle_de_q2(bac: Bac) -> None:
    # Une lecture restée active ne doit pas ralentir le contrôle de Q2 sur Aura : le nettoyage
    # passe avant la notation.
    nettoyages_au_controle: list[int] = []

    def controle(_liste: str) -> Controle:
        nettoyages_au_controle.append(bac.nettoyages)
        return EQUIPE_VALIDE

    equipe = "Réponse : Magnéton, Dracolosse, Flagadoss, Noadkoko, Staross, Parasect"
    tours = [tour("reponse") | {"reponse": equipe}, tour("echec", "delai")]
    bac.scenario({f"{CC} p1 Q2+Q18 e1": {"tours": tours}})
    assert bac.orchestrer(campagne(("Q2", "Q18"), cellules=(CC,)), controle=controle) == 0
    assert nettoyages_au_controle == [2]


def nettoyage_rate(message: str) -> Callable[[], str]:
    """Un nettoyage d'Aura réussi au départ, puis en échec."""
    appels: list[None] = []

    def nettoyer() -> str:
        appels.append(None)
        if len(appels) > 1:
            raise OrchestrationError(message)
        return ""

    return nettoyer


def test_nettoyage_en_echec_puis_reprise(bac: Bac) -> None:
    # Une lecture qui reste active sur Aura arrête la campagne, sans ligne ; la reprise, Aura
    # nettoyé au départ, note la trace complète : l'échec n'est jamais rejoué (ADR-0009).
    bac.scenario({f"{CC} p1 Q1 e1": {"tours": [tour("echec", "delai")]}})
    fixee = campagne(("Q1",), ("Q3",), cellules=(CC,))
    rate = nettoyage_rate("transactions.sh : code 1 une lecture reste active")
    with pytest.raises(OrchestrationError, match="une lecture reste active"):
        bac.orchestrer(fixee, nettoyer=rate)
    assert bac.lignes() == []
    assert bac.orchestrer(fixee) == 0
    assert bac.resume() == [(CC, "Q1", "1", "echec", "delai"), (CC, "Q3", "1", "reponse", "")]
    assert bac.lancees() == [f"{CC} p1 Q1 e1", f"{CC} p1 Q3 e1"]


def test_panne_notee_a_la_reprise(bac: Bac) -> None:
    # Le nettoyage qui suit une panne échoue : arrêt, sans ligne. La reprise note la panne,
    # puis rejoue la conversation à l'essai suivant.
    bac.scenario({f"{CC} p1 Q1 e1": {"tours": [tour("panne", "api")]}})
    fixee = campagne(cellules=(CC,))
    rate = nettoyage_rate("transactions.sh : code 1 une lecture reste active")
    with pytest.raises(OrchestrationError, match="une lecture reste active"):
        bac.orchestrer(fixee, nettoyer=rate)
    assert bac.orchestrer(fixee) == 0
    assert bac.resume() == [(CC, "Q1", "1", "panne", "api"), (CC, "Q1", "2", "reponse", "")]


def test_coupee_entre_deux_tours_rejouee(bac: Bac) -> None:
    # Q2 a sa réponse, Q18 n'a jamais été posée : la conversation est inachevée (une cellule tuée
    # entre deux tours) ; erreur sur le moment, puis la reprise la rejoue en entier.
    bac.scenario({f"{CC} p1 Q2+Q18 e1": {"seulement": 1}})
    fixee = campagne(("Q2", "Q18"), cellules=(CC,))
    with pytest.raises(OrchestrationError, match="trace absente ou inachevée"):
        bac.orchestrer(fixee)
    assert bac.orchestrer(fixee) == 0
    assert [(v["question"], v["essai"]) for v in bac.lignes()] == [("Q2", "2"), ("Q18", "2")]


def test_echec_puis_tour_commence_jamais_rejoue(bac: Bac) -> None:
    # Q2 en échec, puis Q18 commencée (cellule fautive) : erreur, à la reprise aussi, jamais un
    # rejeu qui effacerait l'échec. Une fois la trace écartée, la conversation se rejoue au
    # numéro suivant.
    conduite = {"tours": [tour("echec", "delai")], "continuer": True, "quitter": 1}
    bac.scenario({f"{CC} p1 Q2+Q18 e1": conduite})
    fixee = campagne(("Q2", "Q18"), cellules=(CC,))
    for _ in range(2):
        with pytest.raises(OrchestrationError, match="écarter cette trace"):
            bac.orchestrer(fixee)
    assert bac.lancees() == [f"{CC} p1 Q2+Q18 e1"]
    (fichier,) = (bac.racine / "traces" / "essai").glob("*.jsonl")
    fichier.rename(fichier.with_name(fichier.name + ".ecartee"))
    assert bac.orchestrer(fixee) == 0
    assert bac.lancees()[-1] == f"{CC} p1 Q2+Q18 e2"


def test_arret_note_a_la_reprise(bac: Bac) -> None:
    # Crédits épuisés, puis un nettoyage raté : arrêt sur le nettoyage, sans ligne. La reprise
    # note l'arrêt et s'arrête aussitôt sur lui (question à Julien avant toute recharge) ; la
    # suivante rejoue la conversation.
    bac.scenario({f"{CC} p1 Q1 e1": {"tours": [tour("arret", "plafond")]}})
    fixee = campagne(cellules=(CC,))
    rate = nettoyage_rate("transactions.sh : code 1 une lecture reste active")
    with pytest.raises(OrchestrationError, match="une lecture reste active"):
        bac.orchestrer(fixee, nettoyer=rate)
    with pytest.raises(ArretPlafond, match="crédits Anthropic épuisés"):
        bac.orchestrer(fixee)
    assert bac.lancees() == [f"{CC} p1 Q1 e1"]
    assert bac.resume() == [(CC, "Q1", "1", "arret", "plafond")]
    assert bac.orchestrer(fixee) == 0
    assert bac.lancees() == [f"{CC} p1 Q1 e1", f"{CC} p1 Q1 e2"]


def test_panne_notee_comptee_dans_les_trois(bac: Bac) -> None:
    # La panne notée à la reprise compte dans les 3 de suite : arrêt après e3, pas e4.
    panne = {"tours": [tour("panne", "api")]}
    bac.scenario({f"{CC} p1 Q1 e{essai}": panne for essai in (1, 2, 3, 4)})
    fixee = campagne(cellules=(CC,))
    rate = nettoyage_rate("transactions.sh : code 1 une lecture reste active")
    with pytest.raises(OrchestrationError, match="une lecture reste active"):
        bac.orchestrer(fixee, nettoyer=rate)
    with pytest.raises(OrchestrationError, match="3 pannes de suite"):
        bac.orchestrer(fixee)
    assert bac.lancees() == [f"{CC} p1 Q1 e1", f"{CC} p1 Q1 e2", f"{CC} p1 Q1 e3"]


def test_pannes_de_suite_d_un_lancement_a_l_autre(bac: Bac) -> None:
    # Deux pannes, puis le plafond arrête la campagne ; relancée, une troisième panne déclenche
    # le circuit breaker ; relancée encore, un seul essai de plus.
    panne = {"tours": [tour("panne", "api") | {"entree": 100_000}]}
    bac.scenario({f"{CC} p1 Q1 e{essai}": panne for essai in (1, 2, 3, 4)})
    fixee = campagne(cellules=(CC,))
    with pytest.raises(ArretPlafond):
        bac.orchestrer(fixee, plafond="0.85")
    assert len(bac.lancees()) == 2
    with pytest.raises(OrchestrationError, match="3 pannes de suite"):
        bac.orchestrer(fixee)
    assert len(bac.lancees()) == 3
    with pytest.raises(OrchestrationError, match="4 pannes de suite"):
        bac.orchestrer(fixee)
    assert len(bac.lancees()) == 4


def test_controle_de_q2_en_echec_puis_reprise(bac: Bac) -> None:
    # Le contrôle de Q2 en échec arrête la campagne, sans ligne ; la reprise note la trace.
    def en_panne(_liste: str) -> Controle:
        raise NotationError("questions.sh --controle : code 2 Aura injoignable")

    equipe = "Réponse : Magnéton, Dracolosse, Flagadoss, Noadkoko, Staross, Parasect"
    bac.scenario({f"{CC} p1 Q2+Q18 e1": {"tours": [tour("reponse") | {"reponse": equipe}]}})
    fixee = campagne(("Q2", "Q18"), cellules=(CC,))
    with pytest.raises(NotationError, match="Aura injoignable"):
        bac.orchestrer(fixee, controle=en_panne)
    assert bac.lignes() == []
    assert bac.orchestrer(fixee) == 0
    assert bac.lancees() == [f"{CC} p1 Q2+Q18 e1"]
    assert [(v["question"], v["essai"]) for v in bac.lignes()] == [("Q2", "1"), ("Q18", "1")]


def test_nettoyage_en_echec_ne_masque_pas_l_erreur(
    bac: Bac, capsys: pytest.CaptureFixture[str]
) -> None:
    bac.scenario({f"{CC} p1 Q1 e1": {"code": 2}})
    rate = nettoyage_rate("transactions.sh : code 2 Aura injoignable")
    with pytest.raises(OrchestrationError, match="sortie en 2"):
        bac.orchestrer(campagne(cellules=(CC,)), nettoyer=rate)
    assert "Aura injoignable" in capsys.readouterr().err


# --- La commande ----------------------------------------------------------------------------------


def test_campagne_creee_puis_finie(bac: Bac) -> None:
    assert bac.commande(questions=("Q19", "Q2", "Q18"), cellules=(AG,), passes=2) == 0
    fixee = lire_campagne(bac.racine / "traces" / "essai" / "campagne.json")
    assert fixee == Campagne("essai", 2, (("Q19",), ("Q2", "Q18")), (AG,))
    # Reprendre une campagne finie ne relance rien.
    assert bac.commande(reprendre=True) == 0
    assert len(bac.lancees()) == 4


def test_campagne_existante(bac: Bac) -> None:
    assert bac.commande(questions=("Q1",), cellules=(AG,)) == 0
    assert bac.commande(questions=("Q1",), cellules=(AG,)) == 2
    assert len(bac.lancees()) == 1


def test_une_campagne_a_la_fois(bac: Bac) -> None:
    # Le verrou est pris avant de créer quoi que ce soit : refusée, la campagne n'existe pas.
    with verrou(bac.racine / "traces"):
        assert bac.commande(questions=("Q1",), cellules=(AG,)) == 2
    assert not (bac.racine / "traces" / "essai").exists()
    assert bac.commande(questions=("Q1",), cellules=(AG,)) == 0


def test_reprendre_sans_campagne(bac: Bac) -> None:
    assert bac.commande(reprendre=True) == 2
    assert bac.lancees() == []


@pytest.mark.parametrize(
    "ecart",
    [{"passes": 2}, {"questions": ("Q3",)}, {"cellules": (CC,)}, {"cache_1h": True}],
)
def test_reprendre_garde_les_parametres(bac: Bac, ecart: dict[str, Any]) -> None:
    fixes: dict[str, Any] = {
        "passes": 1,
        "questions": ("Q1",),
        "cellules": (AG,),
        "cache_1h": False,
    }
    assert bac.commande(**fixes) == 0
    # Les mêmes paramètres, redits, passent ; un seul qui change est refusé.
    assert bac.commande(reprendre=True, **fixes) == 0
    assert bac.commande(reprendre=True, **(fixes | ecart)) == 2


def test_cle_absente(bac: Bac, monkeypatch: pytest.MonkeyPatch) -> None:
    # Vérifiée avant d'écrire quoi que ce soit ; une campagne Gemini seule s'en passe.
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert bac.commande(questions=("Q1",), cellules=(AG, AC)) == 2
    assert not (bac.racine / "traces" / "essai").exists()
    assert bac.commande(questions=("Q1",), cellules=(AG,)) == 0


def test_nom_de_campagne_invalide(bac: Bac) -> None:
    assert commande(Demande("Pilote 1", Decimal(1)), bac.moyens()) == 2
    assert bac.lancees() == []


def test_point_d_entree(monkeypatch: pytest.MonkeyPatch) -> None:
    recues: list[Demande] = []

    def noter(demande: Demande) -> int:
        recues.append(demande)
        return 0

    monkeypatch.setattr(orchestration, "commande", noter)
    complete = [
        "lancer", "--campagne", "pilote", "--plafond-usd", "4.5", "--questions", "Q19, Q2,Q18",
        "--cellules", "adk-gemini", "--passes", "3", "--cache-1h", "--reprendre",
    ]  # fmt: skip
    assert main(complete) == 0
    assert main(["lancer", "--campagne", "pilote", "--plafond-usd", "2"]) == 0
    assert recues == [
        Demande("pilote", Decimal("4.5"), True, 3, ("Q19", "Q2", "Q18"), (AG,), True),
        Demande("pilote", Decimal(2)),
    ]


@pytest.mark.parametrize("plafond", ["0", "-1", "abc", "NaN", "Infinity"])
def test_plafond_refuse(plafond: str) -> None:
    with pytest.raises(SystemExit) as sortie:
        main(["lancer", "--campagne", "pilote", "--plafond-usd", plafond])
    assert sortie.value.code == 2


def test_plafond_exige() -> None:
    with pytest.raises(SystemExit):
        main(["lancer", "--campagne", "pilote"])


# --- Outils : processus, transactions, PATH des agents --------------------------------------------


def test_descendants_et_arret() -> None:
    # Un enfant et un petit-enfant lancés chacun dans sa propre session restent des descendants ;
    # arreter les tue avec leur ancêtre.
    script = (
        "import subprocess, sys, time\n"
        "attente = [sys.executable, '-c', 'import time; time.sleep(60)']\n"
        "if sys.argv[1] == 'enfant':\n"
        "    petit = subprocess.Popen(attente, start_new_session=True)\n"
        "    print(petit.pid, flush=True)\n"
        "else:\n"
        "    moi = [sys.executable, '-c', sys.argv[-1], 'enfant', sys.argv[-1]]\n"
        "    enfant = subprocess.Popen(moi, start_new_session=True)\n"
        "    print(enfant.pid, flush=True)\n"
        "time.sleep(60)\n"
    )
    ancetre = subprocess.Popen(
        [sys.executable, "-c", script, script],
        stdout=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    assert ancetre.stdout is not None
    enfant, petit_enfant = int(ancetre.stdout.readline()), int(ancetre.stdout.readline())
    try:
        assert {(enfant, enfant), (petit_enfant, petit_enfant)} <= descendants(ancetre.pid)
        assert descendants(petit_enfant) == set()
        arreter(ancetre, 1.0)
        assert ancetre.returncode == -signal.SIGTERM
        attendre(lambda: not vivant(enfant) and not vivant(petit_enfant), 5.0)
    finally:
        for pid in (ancetre.pid, enfant, petit_enfant):
            if vivant(pid):
                os.kill(pid, signal.SIGKILL)
        ancetre.stdout.close()


def test_arret_d_une_cellule_sourde() -> None:
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print(flush=True)\n"
        "time.sleep(60)\n"
    )
    sourde = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, start_new_session=True
    )
    assert sourde.stdout is not None
    sourde.stdout.readline()
    debut = time.monotonic()
    arreter(sourde, 0.5)
    assert sourde.returncode == -signal.SIGKILL
    assert 0.5 <= time.monotonic() - debut < 5
    sourde.stdout.close()


def test_arret_interrompu_pendant_la_grace() -> None:
    # Un second Ctrl-C (ici SIGUSR1) interrompt l'attente de la grâce : la cellule sourde est
    # tuée quand même, avant que l'interruption remonte.
    class Interruption(Exception):
        pass

    def interrompre(_numero: int, _cadre: object) -> None:
        raise Interruption

    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print(flush=True)\n"
        "time.sleep(60)\n"
    )
    sourde = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, start_new_session=True
    )
    assert sourde.stdout is not None
    sourde.stdout.readline()
    precedent = signal.signal(signal.SIGUSR1, interrompre)
    minuterie = threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGUSR1))
    minuterie.start()
    try:
        with pytest.raises(Interruption):
            arreter(sourde, 30.0)
        assert sourde.returncode == -signal.SIGKILL
    finally:
        minuterie.cancel()
        signal.signal(signal.SIGUSR1, precedent)
        sourde.stdout.close()


class Interruption(Exception):
    """Un signal reçu au mauvais moment, simulé."""


def sourde() -> subprocess.Popen[str]:
    """Une cellule qui ignore SIGTERM, dans sa propre session, prête."""
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "print(flush=True)\n"
        "time.sleep(60)\n"
    )
    cellule = subprocess.Popen(
        [sys.executable, "-c", code], stdout=subprocess.PIPE, text=True, start_new_session=True
    )
    assert cellule.stdout is not None
    cellule.stdout.readline()
    cellule.stdout.close()
    return cellule


def test_arret_interrompu_pendant_le_releve(monkeypatch: pytest.MonkeyPatch) -> None:
    # Le relevé des descendants interrompu avant tout signal : la cellule est tuée quand même.
    def interrompu(_racine: int) -> set[tuple[int, int]]:
        raise Interruption

    monkeypatch.setattr(orchestration, "descendants", interrompu)
    cellule = sourde()
    with pytest.raises(Interruption):
        arreter(cellule, 30.0)
    assert cellule.returncode == -signal.SIGKILL


def test_executer_balaie_meme_si_l_arret_echoue(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # L'arrêt lui-même interrompu : executer tue encore le groupe de la cellule.
    def interrompu(_cellule: object, _grace_s: float | None = None) -> None:
        raise Interruption

    monkeypatch.setattr(orchestration, "arreter", interrompu)
    fichier = tmp_path / "pid"
    code = f"import os, time\nopen({str(fichier)!r}, 'w').write(str(os.getpid()))\ntime.sleep(60)\n"
    with pytest.raises(Interruption):
        orchestration.executer([sys.executable, "-c", code], "", dict(os.environ), tmp_path, 1.0)
    pid = int(fichier.read_text())
    attendre(lambda: not vivant(pid), 5.0)


def installer(dossier: Path, nom: str, code: str) -> Path:
    script = dossier / nom
    script.write_text(f"#!{sys.executable} -I\n{code}")
    script.chmod(0o755)
    return script


def test_transactions_sans_la_cle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Le script reçoit l'environnement du harnais (gcloud…), sans la clé Anthropic.
    script = installer(
        tmp_path, "transactions.sh", "import json, os\nprint(json.dumps(sorted(os.environ)))\n"
    )
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:1")
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path))
    noms = json.loads(transactions(script))
    assert [nom for nom in noms if nom.startswith("ANTHROPIC_")] == []
    assert "CLOUDSDK_CONFIG" in noms


def test_transactions_en_echec(tmp_path: Path) -> None:
    code = (
        "import sys\n"
        "print('détail', file=sys.stderr)\n"
        "print('1 lecture encore active', file=sys.stderr)\n"
        "sys.exit(1)\n"
    )
    script = installer(tmp_path, "transactions.sh", code)
    with pytest.raises(OrchestrationError, match=r"code 1 1 lecture encore active$"):
        transactions(script)


def test_outils_des_agents(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sdk, serveur = tmp_path / "sdk", tmp_path / "neo4j-mcp"
    sdk.mkdir()
    serveur.mkdir()
    gcloud = installer(sdk, "gcloud", "")
    monkeypatch.setattr(orchestration, "GCLOUD", gcloud)
    monkeypatch.setattr(orchestration, "NEO4J_MCP", serveur)
    # gcloud hors du PATH (shell non interactif) : celui du SDK ; neo4j-mcp manquant : refusé.
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    with pytest.raises(OrchestrationError, match="neo4j-mcp introuvable"):
        outils_des_agents()
    installer(serveur, "neo4j-mcp", "")
    assert outils_des_agents() == (sdk, serveur)
    # gcloud dans le PATH : celui-là.
    autre = tmp_path / "autre"
    autre.mkdir()
    installer(autre, "gcloud", "")
    monkeypatch.setenv("PATH", f"{autre}:/usr/bin:/bin")
    assert outils_des_agents() == (autre, serveur)


def test_programmes_des_cellules() -> None:
    assert {cellule: programme[1:] for cellule, programme in PROGRAMMES.items()} == {
        CC: ("-m", "banc.cellule_sdk"),
        AC: ("-m", "banc.cellule_adk", AC),
        AG: ("-m", "banc.cellule_adk", AG),
    }
    assert {programme[0] for programme in PROGRAMMES.values()} == {sys.executable}


# --- Bout en bout : les vraies cellules -----------------------------------------------------------


@pytest.fixture
def vrais_outils(bac: Bac) -> Path:
    """Faux gcloud et faux neo4j-mcp pour le vrai lanceur, comme tests/test_cellule_sdk_reel.py."""
    outils = bac.racine / "outils"
    installer(outils, "gcloud", f"import sys\nsys.stdout.write({SECRET!r})\n")
    installer(outils, "neo4j-mcp", (FIXTURES / "faux_neo4j_mcp.py").read_text())
    return outils


@contextmanager
def fausse_api(bac: Bac, monkeypatch: pytest.MonkeyPatch, mode: str) -> Iterator[None]:
    """La fausse API Anthropic de tests/test_cellule_sdk_reel.py, annoncée aux cellules par
    ANTHROPIC_BASE_URL, seul ajout à leur liste blanche."""
    journal = bac.racine / "journal" / "api.jsonl"
    commande_api = [sys.executable, "-I", str(FIXTURES / "fausse_api.py"), str(journal), mode]
    api = subprocess.Popen(commande_api, stdout=subprocess.PIPE, text=True)
    assert api.stdout is not None
    try:
        adresse = f"http://127.0.0.1:{api.stdout.readline().strip()}"

        def avec_l_api(*arguments: Any, **options: Any) -> dict[str, str]:
            return environnement_agent(*arguments, **options) | {"ANTHROPIC_BASE_URL": adresse}

        monkeypatch.setattr(orchestration, "environnement_agent", avec_l_api)
        yield
    finally:
        api.terminate()
        api.wait()
        api.stdout.close()


def notes_de(fichier: Path) -> list[dict[str, Any]]:
    return [json.loads(texte) for texte in fichier.read_text().splitlines()]


def test_vrai_claude_code(bac: Bac, vrais_outils: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # La vraie cellule, le vrai Claude Code 2.1.292 et le vrai lanceur : seuls gcloud, neo4j-mcp
    # et l'API sont faux. La ligne porte les tokens tirés du flux.
    with fausse_api(bac, monkeypatch, "normal"):
        code = bac.orchestrer(campagne(cellules=(CC,)), programmes=dict(PROGRAMMES))
    assert code == 0, bac.sortie
    (valeurs,) = bac.lignes()
    tokens = ("issue", "entree", "sortie", "cache_lecture", "cache_ecriture_5m")
    assert [valeurs[cle] for cle in tokens] == ["reponse", "1000", "70", "3000", "3000"]
    assert valeurs["note"]
    assert Decimal(valeurs["cout_usd"]) > 0
    assert bac.nettoyages == 1


def test_vrai_claude_code_arrete_avec_son_serveur(
    bac: Bac, vrais_outils: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Relevé (T4.3) : Claude Code 2.1.292 lance son serveur MCP dans son propre groupe, qui est
    # celui de la cellule ; arrêter ce groupe arrête la cellule, Claude Code, le lanceur et le
    # serveur. La fausse API tient le flux ouvert ; la surveillance tombe avant le délai.
    monkeypatch.setattr(Orchestration, "_echeance", lambda _moi, _commande: 8.0)
    with (
        fausse_api(bac, monkeypatch, "lent"),
        pytest.raises(OrchestrationError, match=r"cellule tuée \(code -15\)"),
    ):
        bac.orchestrer(campagne(cellules=(CC,), delai_s=60.0), programmes=dict(PROGRAMMES))
    (serveur,) = [n for n in notes_de(bac.racine / "journal" / "neo4j-mcp.jsonl") if "pid" in n]
    lignee = serveur["ancetres"]
    rang = next(i for i, a in enumerate(lignee) if "banc.cellule_sdk" in a["commande"])
    cellule, claude_code = lignee[rang], lignee[:rang]
    assert claude_code
    assert {a["pgid"] for a in claude_code} == {serveur["pgid"]} == {cellule["pid"]}
    assert cellule["pgid"] == cellule["pid"] != os.getpgid(0)
    pids: list[int] = [serveur["pid"], cellule["pid"], *(a["pid"] for a in claude_code)]
    attendre(lambda: not any(vivant(pid) for pid in pids), 5.0)
    assert bac.nettoyages == 2


def test_vraie_cellule_adk_arretee_avec_son_serveur(
    bac: Bac, monkeypatch: pytest.MonkeyPatch
) -> None:
    # ADK lance le serveur dans sa propre session : au SIGTERM, la cellule l'arrête elle-même,
    # puis sort en 143 (T4.2), dans la grâce qui précède le SIGKILL.
    monkeypatch.setattr(orchestration, "GRACE_S", 15.0)
    monkeypatch.setattr(Orchestration, "_echeance", lambda _moi, _commande: 12.0)
    journal = bac.racine / "journal"
    etape = {"blocs": [["texte", "..."]], "usage": {"entree": 10, "sortie": 1}, "lent_s": 60}
    (journal / "api-adk.json").write_text(json.dumps({"etapes": [etape]}))
    (journal / "mcp.json").write_text("{}")
    lancement = [
        sys.executable,
        "-I",
        str(FIXTURES / "fausse_api_adk.py"),
        str(journal / "api-adk.json"),
        str(journal / "api-adk.jsonl"),
    ]
    serveur = (
        sys.executable,
        "-I",
        str(FIXTURES / "faux_serveur_mcp.py"),
        str(journal / "mcp.json"),
        str(journal / "mcp.jsonl"),
    )
    api = subprocess.Popen(lancement, stdout=subprocess.PIPE, text=True)
    assert api.stdout is not None
    try:
        adresse = f"http://127.0.0.1:{api.stdout.readline().strip()}"

        def avec_l_api(*arguments: Any, **options: Any) -> dict[str, str]:
            return environnement_agent(*arguments, **options) | {"ANTHROPIC_BASE_URL": adresse}

        monkeypatch.setattr(orchestration, "environnement_agent", avec_l_api)
        with pytest.raises(OrchestrationError, match=r"cellule tuée \(code 143\)"):
            bac.orchestrer(
                campagne(cellules=(AC,), delai_s=60.0),
                programmes=dict(PROGRAMMES),
                serveur=serveur,
            )
    finally:
        api.terminate()
        api.wait()
        api.stdout.close()
    (demarrage,) = [n for n in notes_de(journal / "mcp.jsonl") if "pid" in n]
    assert demarrage["pgid"] == demarrage["pid"] != os.getpgid(0)
    attendre(lambda: not vivant(demarrage["pid"]), 5.0)
    assert bac.nettoyages == 2
