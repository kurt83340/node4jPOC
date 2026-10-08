"""Les 30 questions du banc d'essai (plan 002, T1.1) : questions/banc.toml, lu et validé.

Chaque question porte de quoi la poser (texte, préambule de Q2, tour précédent) et la pré-noter
(mode de notation, valeurs attendues, distracteurs) ; le README des questions et questions/attendu/
font foi (tests/test_banc_toml.py). La notation elle-même vient en phase 2 (T2.1, T2.2).
"""

import re
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

FICHIER = Path(__file__).resolve().parents[3] / "questions" / "banc.toml"
IDENTIFIANT = re.compile(r"Q[1-9]\d*")
COMMUNS = frozenset({"texte", "categorie", "notation", "tour_precedent", "distracteurs"})
# Champs propres à chaque mode de notation : obligatoires, puis facultatifs. Un champ hors de son
# mode est refusé : une faute de frappe ne doit pas retirer un garde-fou en silence.
MODES: dict[str, tuple[frozenset[str], frozenset[str]]] = {
    "valeur": (frozenset(), frozenset({"attendus", "un_parmi", "revoir_si_incomplete"})),
    "ensemble": (frozenset(), frozenset({"attendus", "un_parmi", "revoir_si_incomplete"})),
    "liste-ordonnee": (frozenset({"attendus"}), frozenset({"scores", "tolerance"})),
    "longue-liste": (frozenset({"compte"}), frozenset()),
    "semantique": (frozenset({"pluriel"}), frozenset({"avec_types"})),
    "controle": (frozenset({"preambule"}), frozenset()),
    "revue": (frozenset(), frozenset()),
}

type Valeur = str | int | float


class BancError(Exception):
    """banc.toml illisible, ou une question mal décrite."""


@dataclass(frozen=True)
class Question:
    """Une question du banc : de quoi la poser et la pré-noter (champs selon le mode)."""

    id: str
    texte: str
    categorie: str
    notation: str
    tour_precedent: str | None = None
    attendus: tuple[Valeur, ...] = ()
    un_parmi: tuple[str, ...] = ()
    distracteurs: tuple[Valeur, ...] = ()
    revoir_si_incomplete: bool = False
    compte: int | None = None
    pluriel: bool | None = None
    avec_types: bool = False
    scores: Mapping[str, float] = field(default_factory=dict)
    tolerance: float | None = None
    preambule: str | None = None


@dataclass(frozen=True)
class Banc:
    """Catégories (identifiant → titre de section du README), puis questions par identifiant."""

    categories: dict[str, str]
    questions: dict[str, Question]


def charger(fichier: Path = FICHIER) -> Banc:
    """Lit et valide banc.toml."""
    try:
        brut = tomllib.loads(fichier.read_text())
    except (OSError, tomllib.TOMLDecodeError) as erreur:
        raise BancError(f"{fichier} illisible : {erreur!r}") from erreur
    categories = brut.pop("categories", None)
    if not isinstance(categories, dict) or not all(isinstance(t, str) for t in categories.values()):
        raise BancError("table [categories] attendue : identifiant = titre de section du README")
    lues = {ident: _question(ident, champs, categories) for ident, champs in brut.items()}
    for question in lues.values():
        precedent = question.tour_precedent
        if precedent is not None and (
            precedent not in lues or lues[precedent].tour_precedent is not None
        ):
            raise BancError(f"{question.id} : tour précédent {precedent} absent, ou second tour")
    return Banc(categories, lues)


def _question(ident: str, champs: Any, categories: Mapping[str, str]) -> Question:
    if not IDENTIFIANT.fullmatch(ident) or not isinstance(champs, dict):
        raise BancError(f"[{ident}] : une question se nomme Q1, Q2…")
    notation = champs.get("notation")
    if notation not in MODES:
        raise BancError(f"{ident} : notation {notation!r} inconnue (permises : {', '.join(MODES)})")
    obligatoires, facultatifs = MODES[notation]
    if inconnus := set(champs) - COMMUNS - obligatoires - facultatifs:
        raise BancError(f"{ident} : {', '.join(sorted(inconnus))} hors du mode {notation}")
    if manquants := ({"texte", "categorie"} | obligatoires) - set(champs):
        raise BancError(f"{ident} : {', '.join(sorted(manquants))} manquant (mode {notation})")
    if champs["categorie"] not in categories:
        raise BancError(f"{ident} : catégorie {champs['categorie']!r} absente de [categories]")
    if "un_parmi" in champs and not champs["un_parmi"]:
        raise BancError(f"{ident} : un_parmi vide")
    question = Question(
        id=ident,
        texte=_texte(ident, champs, "texte") or "",
        categorie=champs["categorie"],
        notation=notation,
        tour_precedent=_texte(ident, champs, "tour_precedent"),
        attendus=_valeurs(ident, champs, "attendus"),
        un_parmi=tuple(str(v) for v in _valeurs(ident, champs, "un_parmi", noms=True)),
        distracteurs=_valeurs(ident, champs, "distracteurs"),
        revoir_si_incomplete=_booleen(ident, champs, "revoir_si_incomplete") or False,
        compte=_compte(ident, champs),
        pluriel=_booleen(ident, champs, "pluriel"),
        avec_types=_booleen(ident, champs, "avec_types") or False,
        scores=_scores(ident, champs),
        tolerance=_tolerance(ident, champs),
        preambule=_texte(ident, champs, "preambule"),
    )
    _verifier_mode(question)
    return question


def _verifier_mode(question: Question) -> None:
    """Nombre de valeurs attendues selon le mode ; un groupe un_parmi compte pour une valeur."""
    ident, notation = question.id, question.notation
    valeurs = len(question.attendus) + (1 if question.un_parmi else 0)
    if notation == "valeur" and valeurs != 1:
        raise BancError(f"{ident} : le mode valeur attend une seule valeur ({valeurs} données)")
    if notation in {"ensemble", "liste-ordonnee"} and valeurs < 2:
        raise BancError(f"{ident} : le mode {notation} attend au moins deux valeurs")
    if (question.tolerance is None) != (not question.scores):
        raise BancError(f"{ident} : scores et tolerance vont ensemble")
    if question.scores and (absents := set(question.attendus) - set(question.scores)):
        raise BancError(f"{ident} : score manquant pour {', '.join(map(str, sorted(absents)))}")
    if question.tour_precedent == ident:
        raise BancError(f"{ident} : une question ne suit pas elle-même")


def _texte(ident: str, champs: dict[str, Any], cle: str) -> str | None:
    valeur = champs.get(cle)
    if valeur is None or isinstance(valeur, str):
        return valeur
    raise BancError(f"{ident} : {cle} doit être un texte")


def _valeurs(
    ident: str, champs: dict[str, Any], cle: str, *, noms: bool = False
) -> tuple[Valeur, ...]:
    """Liste de textes ou de nombres (de textes seuls si noms) ; un booléen n'est pas un nombre."""
    valeurs = champs.get(cle, [])
    permis = (str,) if noms else (str, int, float)
    if not isinstance(valeurs, list) or not all(
        isinstance(v, permis) and not isinstance(v, bool) for v in valeurs
    ):
        raise BancError(f"{ident} : {cle} doit être une liste de {'noms' if noms else 'valeurs'}")
    return tuple(valeurs)


def _booleen(ident: str, champs: dict[str, Any], cle: str) -> bool | None:
    valeur = champs.get(cle)
    if valeur is None or isinstance(valeur, bool):
        return valeur
    raise BancError(f"{ident} : {cle} doit valoir true ou false")


def _compte(ident: str, champs: dict[str, Any]) -> int | None:
    compte = champs.get("compte")
    if compte is None:
        return None
    if isinstance(compte, int) and not isinstance(compte, bool) and compte > 0:
        return compte
    raise BancError(f"{ident} : compte doit être un entier positif")


def _scores(ident: str, champs: dict[str, Any]) -> dict[str, float]:
    scores = champs.get("scores", {})
    if not isinstance(scores, dict) or not all(
        isinstance(s, int | float) and not isinstance(s, bool) for s in scores.values()
    ):
        raise BancError(f"{ident} : scores doit associer chaque espèce à un nombre")
    return {espece: float(score) for espece, score in scores.items()}


def _tolerance(ident: str, champs: dict[str, Any]) -> float | None:
    tolerance = champs.get("tolerance")
    if tolerance is None:
        return None
    if isinstance(tolerance, int | float) and not isinstance(tolerance, bool) and tolerance > 0:
        return float(tolerance)
    raise BancError(f"{ident} : tolerance doit être un nombre positif")
