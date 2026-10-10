"""Rapport d'une campagne (T9.1) : complétude des séries (`--complet`), issues, coût et durées ;
scores seulement une fois la revue finie (revue à l'aveugle, plan D4)."""

from pathlib import Path

import pytest

from banc import rapport
from banc.mesures import COLONNES, ecrire, fichier_mesures, nom_de_trace
from banc.orchestration import Campagne, ecrire_campagne

CELLULES = ("claude-code", "adk-gemini")
CONVERSATIONS = (("Q1",), ("Q2", "Q18"))
CAMPAGNE = Campagne("c1", passes=2, conversations=CONVERSATIONS, cellules=CELLULES)


def ligne(
    cellule: str, passe: int, question: str, essai: int = 1, **champs: object
) -> dict[str, str]:
    """Une ligne du CSV de la campagne (banc.mesures) ; champs : les colonnes à changer."""
    valeurs = dict.fromkeys(COLONNES, "")
    valeurs |= {
        "campagne": "c1",
        "cellule": cellule,
        "passe": str(passe),
        "question": question,
        "essai": str(essai),
        "issue": "reponse",
        "note": "juste",
        "source": "oui",
        "empreinte": "0123456789abcdef",
        "modele": "claude-sonnet-5-5",
        "duree_s": "10.00",
        "cout_usd": "0.010000",
        "cout_annexe_usd": "0.000000",
        "effort": "high",
    }
    return valeurs | {colonne: str(valeur) for colonne, valeur in champs.items()}


def completes() -> list[dict[str, str]]:
    """Toutes les lignes d'une campagne menée sans incident, notes finales."""
    return [
        ligne(cellule, passe, question)
        for passe in (1, 2)
        for conversation in CONVERSATIONS
        for cellule in CELLULES
        for question in conversation
    ]


def tracer(dossier: Path, lignes: list[dict[str, str]]) -> None:
    """Une trace par conversation menée, comme l'orchestration en laisse."""
    for valeurs in lignes:
        conversation = next(c for c in CONVERSATIONS if valeurs["question"] in c)
        nom = nom_de_trace(
            valeurs["cellule"], int(valeurs["passe"]), conversation, int(valeurs["essai"])
        )
        (dossier / nom).touch()


@pytest.fixture
def dossier(tmp_path: Path) -> Path:
    return tmp_path


def test_campagne_complete(dossier: Path) -> None:
    lignes = completes()
    tracer(dossier, lignes)
    assert rapport.manques(CAMPAGNE, lignes, dossier) == []


def test_conversation_jamais_menee(dossier: Path) -> None:
    lignes = [
        v
        for v in completes()
        if (v["cellule"], v["passe"], v["question"]) != ("adk-gemini", "2", "Q1")
    ]
    tracer(dossier, lignes)
    assert rapport.manques(CAMPAGNE, lignes, dossier) == [
        "passe 2 · Q1 · adk-gemini : jamais menée"
    ]


@pytest.mark.parametrize("issue", ["panne", "arret"])
def test_dernier_essai_a_rejouer(dossier: Path, issue: str) -> None:
    lignes = completes()
    lignes[0] = ligne("claude-code", 1, "Q1", issue=issue, note="")
    tracer(dossier, lignes)
    [manque] = rapport.manques(CAMPAGNE, lignes, dossier)
    assert manque == f"passe 1 · Q1 · claude-code : essai 1 en {issue}, --reprendre"


def test_panne_rejouee(dossier: Path) -> None:
    lignes = [*completes(), ligne("claude-code", 1, "Q1", essai=2)]
    lignes[0] = ligne("claude-code", 1, "Q1", issue="panne", note="")
    tracer(dossier, lignes)
    assert rapport.manques(CAMPAGNE, lignes, dossier) == []


def test_trace_sans_ligne(dossier: Path) -> None:
    # Harnais arrêté après la sortie de sa cellule : la trace attend sa ligne (--reprendre la note).
    lignes = completes()
    tracer(dossier, lignes)
    (dossier / nom_de_trace("adk-gemini", 2, ("Q2", "Q18"), 2)).touch()
    [manque] = rapport.manques(CAMPAGNE, lignes, dossier)
    assert manque == "passe 2 · Q2+Q18 · adk-gemini : essai 2 sans ligne, --reprendre"


def test_deux_pannes_par_serie_tolerees(dossier: Path) -> None:
    pannes = [ligne("claude-code", 1, "Q1", essai=e, issue="panne", note="") for e in (1, 2)]
    lignes = [*pannes, *completes()[1:], ligne("claude-code", 1, "Q1", essai=3)]
    tracer(dossier, lignes)
    assert rapport.manques(CAMPAGNE, lignes, dossier) == []


def test_serie_invalide(dossier: Path) -> None:
    # Plus de 2 pannes dans une série (une cellule, une passe) : passe invalide (plan, D13).
    pannes = [ligne("claude-code", 1, "Q1", essai=e, issue="panne", note="") for e in (1, 2, 3)]
    lignes = [*pannes, *completes()[1:], ligne("claude-code", 1, "Q1", essai=4)]
    tracer(dossier, lignes)
    assert rapport.manques(CAMPAGNE, lignes, dossier) == [
        "claude-code, passe 1 : 3 pannes, série invalide (plan, D13)"
    ]


def test_series() -> None:
    # Durée médiane des seules réponses : 10 et 20 s, pas l'échec à 180 s.
    lignes = completes()
    lignes[0] = ligne(
        "claude-code", 1, "Q1", issue="echec", cause="tours", note="faux", cout_usd="0.5",
        duree_s="180.00",
    )  # fmt: skip
    lignes[3] = ligne("claude-code", 1, "Q18", duree_s="20.00")
    [premiere, *_] = rapport.series(CAMPAGNE, lignes)
    assert (premiere.cellule, premiere.passe, premiere.questions) == ("claude-code", 1, 3)
    assert premiere.issues == {"echec (tours)": 1, "reponse": 2}
    assert str(premiere.cout_usd) == "0.520000"
    assert premiere.duree_mediane_s == 15.0


def test_cout_compte_les_essais_rejoues() -> None:
    # Une panne rejouée a été payée : elle compte au coût de sa série, pas à ses questions.
    lignes = [ligne("claude-code", 1, "Q1", issue="panne", note="", cout_usd="0.2")]
    lignes += [*completes()[1:], ligne("claude-code", 1, "Q1", essai=2)]
    [premiere, *_] = rapport.series(CAMPAGNE, lignes)
    assert (premiere.questions, premiere.issues) == (3, {"reponse": 3})
    assert str(premiere.cout_usd) == "0.230000"


def test_scores_masques_tant_que_la_revue_n_est_pas_finie(tmp_path: Path) -> None:
    lignes = completes()
    lignes[0] = ligne("claude-code", 1, "Q1", note="à revoir")
    assert rapport.scores(CAMPAGNE, lignes, tmp_path / "revues.toml") is None


def test_scores_apres_la_revue(tmp_path: Path) -> None:
    lignes = completes()
    lignes[0] = ligne("claude-code", 1, "Q1", note="partiel")
    lignes[1] = ligne("adk-gemini", 1, "Q1", issue="echec", cause="delai", note="faux")
    scores = rapport.scores(CAMPAGNE, lignes, tmp_path / "revues.toml")
    assert scores == {
        ("claude-code", 1): 2.5,
        ("adk-gemini", 1): 2.0,
        ("claude-code", 2): 3.0,
        ("adk-gemini", 2): 3.0,
    }


def test_ecart_entre_passes() -> None:
    scores = {("claude-code", 1): 2.5, ("claude-code", 2): 3.0, ("adk-gemini", 1): 2.0}
    assert rapport.ecarts(scores) == {"claude-code": 0.5, "adk-gemini": 0.0}


def campagne_sur_disque(tmp_path: Path, lignes: list[dict[str, str]]) -> tuple[Path, Path]:
    traces, mesures = tmp_path / "logs", tmp_path / "mesures"
    (traces / "c1").mkdir(parents=True)
    ecrire_campagne(traces / "c1" / "campagne.json", CAMPAGNE)
    tracer(traces / "c1", lignes)
    ecrire(fichier_mesures("c1", mesures), lignes)
    return traces, mesures


def test_commande_complete(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    traces, mesures = campagne_sur_disque(tmp_path, completes())
    assert rapport.commande("c1", complet=True, traces=traces, mesures=mesures) == 0
    sortie = capsys.readouterr().out
    assert "campagne c1 : complète" in sortie
    assert "claude-code, passe 1 : 3/3 questions" in sortie


def test_commande_incomplete(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    traces, mesures = campagne_sur_disque(tmp_path, completes()[1:])
    assert rapport.commande("c1", complet=True, traces=traces, mesures=mesures) == 1
    assert "passe 1 · Q1 · claude-code : jamais menée" in capsys.readouterr().out


def test_sans_complet_le_rapport_ne_tranche_pas(tmp_path: Path) -> None:
    traces, mesures = campagne_sur_disque(tmp_path, completes()[1:])
    assert rapport.commande("c1", complet=False, traces=traces, mesures=mesures) == 0


def test_campagne_inconnue(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert rapport.commande("absente", complet=True, traces=tmp_path, mesures=tmp_path) == 2
    assert "banc rapport :" in capsys.readouterr().err
