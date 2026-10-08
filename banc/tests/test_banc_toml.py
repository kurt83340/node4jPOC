"""Les 30 questions du banc d'essai (T1.1) : questions/banc.toml, lu et validé par banc.questions.

Le README des questions et questions/attendu/ font foi ; banc.toml en est la version lisible par le
harnais. Ces tests vérifient qu'il les suit : texte posé, catégorie, tour précédent, équipe de Q2,
valeurs attendues, comptes des longues listes, scores de Q8, tables sémantiques.
"""

import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import pytest

from banc import attendu
from banc.questions import BancError, Question, charger

RACINE = Path(__file__).resolve().parents[2]
README = (RACINE / "questions" / "README.md").read_text()
BANC = charger()


@dataclass(frozen=True)
class LigneReadme:
    """Une ligne des tableaux du README : section, question annotée, premier calcul."""

    section: str
    question: str
    premier_calcul: str


def lignes_readme() -> dict[str, LigneReadme]:
    lignes: dict[str, LigneReadme] = {}
    section = ""
    for ligne in README.splitlines():
        if titre := re.fullmatch(r"## \d\. (.+)", ligne):
            section = titre[1]
        elif cellules := re.fullmatch(r"\| (Q\d+) +\| (.+?) +\| .+? +\| (.+?) +\|", ligne):
            lignes[cellules[1]] = LigneReadme(section, cellules[2], cellules[3])
    return lignes


LIGNES = lignes_readme()


def texte_pose(cellule: str) -> str:
    """La question telle qu'on la pose : sans les annotations en italique du README."""
    return " ".join(re.sub(r"_\([^)]*\)_", " ", cellule).split())


def mots(texte: str) -> tuple[str, ...]:
    """Mots d'un nom, pour les comparer : casse, accents, apostrophes et tirets ignorés."""
    decompose = unicodedata.normalize("NFKD", texte.casefold())
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return tuple(re.findall(r"\w+", sans_accents))


def contient(longue: tuple[str, ...], courte: tuple[str, ...]) -> bool:
    return any(longue[i : i + len(courte)] == courte for i in range(len(longue) - len(courte) + 1))


def numero(ident: str) -> int:
    return int(ident[1:])


def questions(*modes: str) -> list[Question]:
    return [q for q in BANC.questions.values() if q.notation in modes]


def fichier(question: Question) -> str:
    """Nom des fichiers de la question dans questions/ : q01 pour Q1."""
    return f"q{numero(question.id):02d}"


# --- Cohérence avec le README --------------------------------------------------------------------


def test_trente_questions() -> None:
    attendues = {f"Q{n}" for n in range(1, 31)}
    assert set(LIGNES) == attendues
    assert set(BANC.questions) == attendues


# Hors du décorateur : son type attendu forcerait sorted() à trier des object.
IDENTIFIANTS = sorted(LIGNES, key=numero)


@pytest.mark.parametrize("ident", IDENTIFIANTS)
def test_texte_pose_tel_quel(ident: str) -> None:
    assert BANC.questions[ident].texte == texte_pose(LIGNES[ident].question)


def test_categories_du_readme() -> None:
    sections = list(dict.fromkeys(ligne.section for ligne in LIGNES.values()))
    assert list(BANC.categories.values()) == sections
    for ident, ligne in LIGNES.items():
        assert BANC.categories[BANC.questions[ident].categorie] == ligne.section, ident


def test_seconds_tours() -> None:
    # Q18 après Q2, Q28 après Q27 : posées dans la même conversation (README, règles de réponse).
    for ident, ligne in LIGNES.items():
        annonce = re.search(r"_\(2e tour, juste après (Q\d+)\)_", ligne.question)
        assert BANC.questions[ident].tour_precedent == (annonce[1] if annonce else None), ident
    assert {q.id: q.tour_precedent for q in BANC.questions.values() if q.tour_precedent} == {
        "Q18": "Q2",
        "Q28": "Q27",
    }


def test_equipe_de_q2() -> None:
    # L'équipe de référence vient du README ; q02.cypher contrôle par rapport à la même (plan, D6).
    annonce = re.search(r"^\*\*Équipe de référence[^*]*\*\* : (.+)\.$", README, re.MULTILINE)
    assert annonce is not None
    equipe = annonce[1].split(", ")
    assert len(equipe) == 6
    assert BANC.questions["Q2"].preambule == f"Mon équipe : {', '.join(equipe)}."
    requete = (RACINE / "questions" / "q02.cypher").read_text()
    reference = re.search(r"\[([^\]]*)\] AS reference", requete)
    assert reference is not None
    assert re.findall(r"'([^']*)'", reference[1]) == equipe


def annoncees(nature: str) -> set[str]:
    """Questions qu'une règle du README annonce : « **Q10, Q29, Q30** (questions …) »."""
    annonce = re.search(rf"\*\*((?:Q\d+, )*Q\d+)\*\* \({nature}\)", README)
    assert annonce is not None, nature
    return set(annonce[1].split(", "))


def test_questions_en_revue() -> None:
    # Q10, Q29 et Q30 n'ont ni requête ni réponse de référence ; Q27 et Q28 en ont, mais leur
    # explication se juge à la main (2026-10-08) : toutes en revue humaine, toujours.
    comportementales = annoncees("questions comportementales")
    assert {q.id for q in questions("revue")} == comportementales | annoncees(
        "questions à explication"
    )
    for question in BANC.questions.values():
        requete = RACINE / "questions" / f"{fichier(question)}.cypher"
        assert requete.exists() == (question.id not in comportementales), question.id


def test_semantiques_au_singulier_et_au_pluriel() -> None:
    # ADR-0008 : au singulier, une espèce juste suffit ; au pluriel, rappel et précision.
    singulier = re.search(r"au singulier \(([^)]*)\)", README)
    pluriel = re.search(r"[Aa]u pluriel \(([^)]*)\)", README)
    assert singulier is not None
    assert pluriel is not None
    semantiques = {q.id: q.pluriel for q in questions("semantique")}
    assert semantiques == {
        **dict.fromkeys(singulier[1].split(", "), False),
        **dict.fromkeys(pluriel[1].split(", "), True),
    }
    categorie = {q.id for q in BANC.questions.values() if q.categorie == "semantique"}
    assert categorie == set(semantiques)


# --- Cohérence avec questions/attendu/ -----------------------------------------------------------


@pytest.mark.parametrize("question", questions("semantique"), ids=lambda q: q.id)
def test_tables_semantiques(question: Question) -> None:
    [table] = attendu.lire(fichier(question))
    assert {"pokemon", "ensemble"} <= set(table.colonnes)
    ensembles = {ligne["ensemble"] for ligne in table.lignes}
    assert "obligatoire" in ensembles
    assert ensembles <= {"obligatoire", "acceptable", "écarté"}
    # Q9 demande aussi les types : la table les donne (forme par défaut).
    assert question.avec_types == ("types" in table.colonnes)


@pytest.mark.parametrize(
    "question", questions("valeur", "ensemble", "liste-ordonnee"), ids=lambda q: q.id
)
def test_valeurs_attendues_dans_la_reponse_de_reference(question: Question) -> None:
    # Chaque valeur attendue figure dans attendu/ ; sinon dans le premier calcul du README (le type
    # de Tortank, raison attendue de Q27, n'est pas une colonne de q27.cypher).
    feuilles = list(attendu.feuilles(attendu.lire(fichier(question))))
    readme = mots(LIGNES[question.id].premier_calcul)
    for valeur in (*question.attendus, *question.un_parmi):
        if isinstance(valeur, str):
            assert valeur in feuilles or contient(readme, mots(valeur)), valeur
        else:
            nombres = [f for f in feuilles if isinstance(f, int | float)]
            assert any(math.isclose(valeur, n) for n in nombres), valeur


@pytest.mark.parametrize("question", questions("longue-liste"), ids=lambda q: q.id)
def test_longues_listes(question: Question) -> None:
    [table] = attendu.lire(fichier(question))
    assert table.colonnes == ("pokemon",)
    assert question.compte == len(table.lignes)
    assert re.search(rf"\b{question.compte} espèces\b", LIGNES[question.id].premier_calcul)
    ensemble = {mots(str(ligne["pokemon"])) for ligne in table.lignes}
    assert not {mots(str(d)) for d in question.distracteurs} & ensemble


def test_scores_de_q8() -> None:
    q8 = BANC.questions["Q8"]
    [table] = attendu.lire("q08")
    reference: dict[str, float] = {}
    for ligne in table.lignes:
        score = ligne["jaccard"]
        assert isinstance(score, float)
        reference[str(ligne["pokemon"])] = score
    assert list(reference) == list(q8.attendus)
    assert {p: q8.scores[p] for p in reference} == reference
    tolerance = re.search(r"à moins de (\d+,\d+)", README)
    assert tolerance is not None
    assert q8.tolerance == float(tolerance[1].replace(",", "."))
    # Les autres espèces notées sont celles qui peuvent prendre la 5e place : sous le 5e score, à
    # moins de la tolérance, et citées par le README avec leur score.
    cinquieme = min(reference.values())
    autres = {p: s for p, s in q8.scores.items() if p not in reference}
    assert autres
    for espece, score in autres.items():
        assert q8.tolerance is not None
        assert score < cinquieme
        assert round(cinquieme - score, 3) < q8.tolerance, espece
        assert f"{espece} {score:.3f}".replace(".", ",") in README, espece


@pytest.mark.parametrize(
    "question", [q for q in BANC.questions.values() if q.distracteurs], ids=lambda q: q.id
)
def test_distracteurs_distincts_des_valeurs_attendues(question: Question) -> None:
    # Un distracteur ne recoupe aucune valeur attendue : sinon, toute bonne réponse irait en revue.
    for distracteur in question.distracteurs:
        for valeur in (*question.attendus, *question.un_parmi):
            d, v = mots(str(distracteur)), mots(str(valeur))
            assert not contient(d, v), (distracteur, valeur)
            assert not contient(v, d), (distracteur, valeur)


# --- Lecture et validation de banc.toml ----------------------------------------------------------

CATEGORIES = '[categories]\nfaits = "Faits simples (étalon)"\n\n'
Q1 = '[Q1]\ntexte = "Qui ?"\ncategorie = "faits"\nnotation = "valeur"\nattendus = ["Dracaufeu"]\n'


def ecrire(tmp_path: Path, texte: str) -> Path:
    banc = tmp_path / "banc.toml"
    banc.write_text(CATEGORIES + texte)
    return banc


def test_question_lue(tmp_path: Path) -> None:
    lu = charger(ecrire(tmp_path, Q1 + 'distracteurs = ["Tortank", 78]\n'))
    assert lu.categories == {"faits": "Faits simples (étalon)"}
    assert lu.questions == {
        "Q1": Question(
            id="Q1",
            texte="Qui ?",
            categorie="faits",
            notation="valeur",
            attendus=("Dracaufeu",),
            distracteurs=("Tortank", 78),
        )
    }


def test_second_tour_lu(tmp_path: Path) -> None:
    q2 = Q1.replace("[Q1]", "[Q2]") + 'tour_precedent = "Q1"\n'
    assert charger(ecrire(tmp_path, Q1 + q2)).questions["Q2"].tour_precedent == "Q1"


ENSEMBLE = '[Q1]\ntexte = "?"\ncategorie = "faits"\nnotation = "ensemble"\n'
LISTE = '[Q1]\ntexte = "?"\ncategorie = "faits"\nnotation = "liste-ordonnee"\n'
SEMANTIQUE = '[Q1]\ntexte = "?"\ncategorie = "faits"\nnotation = "semantique"\n'


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param(Q1 + 'distracteur = ["Tortank"]\n', id="champ-inconnu"),
        pytest.param(Q1.replace('texte = "Qui ?"\n', ""), id="texte-manquant"),
        pytest.param(Q1.replace('"valeur"', '"vote"'), id="notation-inconnue"),
        pytest.param(Q1.replace('"faits"', '"divers"'), id="categorie-inconnue"),
        pytest.param(Q1.replace("[Q1]", "[Question1]"), id="nom-de-question"),
        pytest.param(Q1.replace('"Qui ?"', "3"), id="texte-non-chaine"),
        pytest.param(Q1.replace('["Dracaufeu"]', '["Dracaufeu", "Tortank"]'), id="deux-valeurs"),
        pytest.param(Q1.replace('["Dracaufeu"]', "[]"), id="aucune-valeur"),
        pytest.param(Q1.replace('["Dracaufeu"]', "[true]"), id="booleen-attendu"),
        pytest.param(Q1 + "distracteurs = [[1]]\n", id="liste-distracteur"),
        pytest.param(ENSEMBLE + 'attendus = ["Feu"]\n', id="ensemble-d-une-valeur"),
        pytest.param(ENSEMBLE + 'attendus = ["Eau"]\nun_parmi = []\n', id="un-parmi-vide"),
        pytest.param(LISTE + 'attendus = ["A", "B"]\ntolerance = 0.01\n', id="tolerance-seule"),
        pytest.param(
            LISTE + 'attendus = ["A", "B"]\ntolerance = 0.01\nscores = { A = 0.5 }\n',
            id="score-manquant",
        ),
        pytest.param(SEMANTIQUE, id="semantique-sans-pluriel"),
        pytest.param(SEMANTIQUE + 'pluriel = true\nattendus = ["A"]\n', id="semantique-attendus"),
        pytest.param(Q1.replace('"valeur"', '"longue-liste"'), id="longue-liste-sans-compte"),
        pytest.param(
            '[Q1]\ntexte = "?"\ncategorie = "faits"\nnotation = "longue-liste"\ncompte = 0\n',
            id="compte-nul",
        ),
        pytest.param(
            '[Q1]\ntexte = "?"\ncategorie = "faits"\nnotation = "controle"\n',
            id="controle-sans-preambule",
        ),
        pytest.param(Q1 + 'tour_precedent = "Q9"\n', id="tour-precedent-inconnu"),
        pytest.param(Q1 + 'tour_precedent = "Q1"\n', id="tour-precedent-soi-meme"),
        pytest.param(
            Q1
            + Q1.replace("[Q1]", "[Q2]")
            + 'tour_precedent = "Q1"\n'
            + Q1.replace("[Q1]", "[Q3]")
            + 'tour_precedent = "Q2"\n',
            id="troisieme-tour",
        ),
    ],
)
def test_banc_invalide(tmp_path: Path, texte: str) -> None:
    with pytest.raises(BancError):
        charger(ecrire(tmp_path, texte))


def test_categories_obligatoires(tmp_path: Path) -> None:
    banc = tmp_path / "banc.toml"
    banc.write_text(Q1)
    with pytest.raises(BancError, match="categories"):
        charger(banc)


def test_fichier_illisible(tmp_path: Path) -> None:
    with pytest.raises(BancError, match="illisible"):
        charger(tmp_path / "absent.toml")
