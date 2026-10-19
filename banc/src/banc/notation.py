"""Pré-notation des réponses d'un agent (plan 002, T2.2 ; ADR-0008 et ADR-0009).

Le mode de chaque question (banc.toml) note la réponse courte, la section « Réponse » : juste,
partiel ou faux. Un distracteur cité, une espèce hors ensemble ou hors table, une équipe de Q2
introuvable la font passer « à revoir », comme Q10, Q29 et Q30, toujours revues (plan, D4).
La source citée se vérifie sur la trace du tour (banc.trace) : une requête de « Sources » exécutée
pendant le tour, aux espaces près, dont le résultat contient les valeurs justes de la réponse ; ou
des descriptions renvoyées par les lectures du tour, dont les enregistrements, réunis, les
contiennent toutes (ADR-0018). Les introspections du schéma sont comptées. Aucun juge LLM : tout est
rejouable (ADR-0008).
"""

import json
import math
import os
import re
import subprocess
import unicodedata
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from banc import attendu
from banc.lecture import (
    Citation,
    Especes,
    Sections,
    contient,
    descriptions_citees,
    equipe,
    liste_cypher,
    meme_requete,
    mots,
    nombres,
    prose,
    requetes_citees,
    sections,
)
from banc.questions import Banc, Question, Valeur
from banc.trace import Tour

type Note = Literal["juste", "partiel", "faux", "à revoir"]
type Source = Literal["oui", "non", "exempte", "à revoir"]
type Controleur = Callable[[str], Controle]

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "questions.sh"
LECTURE = "read-cypher"
# Introspection du schéma (plan, D4), comptée, pas pénalisée : l'outil get-schema, s'il passait le
# filtre du client, et les requêtes qui interrogent le schéma plutôt que les données.
OUTILS_D_INTROSPECTION = frozenset({"get-schema"})
INTROSPECTION = re.compile(
    r"apoc\.meta\.|db\.(?:labels|relationshipTypes|propertyKeys)\s*\(|db\.schema\.|db\.indexes|"
    r"db\.constraints|dbms\.components|db\.index\.fulltext\.listAvailableAnalyzers|"
    r"\bSHOW\s+(?:\w+\s+){0,2}(?:INDEX(?:ES)?|CONSTRAINTS?|PROCEDURES|FUNCTIONS|DATABASES?)\b",
    re.IGNORECASE,
)
# Pas de source exigée pour Q10 : « pas dans les données » se fonde sur un résultat vide (D4).
SANS_SOURCE = frozenset({"Q10"})
# ADR-0008, au pluriel : juste si la précision vaut 100 % et le rappel au moins 50 %.
SEUIL_RAPPEL = 0.5
TAILLE_EQUIPE = 6
# Les 18 types (fiche de schéma, Type.nom), pour lire ceux que Q9 demande (README : « exacts »).
TYPES = (
    "Acier", "Combat", "Dragon", "Eau", "Électrik", "Fée", "Feu", "Glace", "Insecte",
    "Normal", "Plante", "Poison", "Psy", "Roche", "Sol", "Spectre", "Ténèbres", "Vol",
)  # fmt: skip
COLONNES_DU_CONTROLE = ("especesReconnues", "typesNonCouverts", "equipeValide")
ENSEMBLES = ("obligatoire", "acceptable", "écarté")


class NotationError(Exception):
    """Notation impossible : tour d'une autre question, contrôle de Q2 en échec ou illisible."""


@dataclass(frozen=True)
class Notation:
    """Pré-note d'une réponse : note, motifs (codes courts, sans prose), source citée,
    introspections ; rappel et précision d'une question sémantique au pluriel."""

    note: Note
    motifs: tuple[str, ...] = ()
    source: Source = "non"
    introspections: int = 0
    rappel: float | None = None
    precision: float | None = None


@dataclass(frozen=True)
class Controle:
    """Résultat du contrôle de Q2 (q02.cypher) sur l'équipe proposée."""

    especes_reconnues: int
    types_non_couverts: tuple[str, ...]
    equipe_valide: bool


@dataclass(frozen=True)
class Table:
    """Table d'une question sémantique (ADR-0008) ; types de la forme par défaut, pour Q9."""

    obligatoires: frozenset[str]
    acceptables: frozenset[str]
    ecartes: frozenset[str]
    types: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


@dataclass(frozen=True)
class Referentiel:
    """Ce que la notation lit hors de banc.toml, dans questions/attendu/ : les espèces, les
    ensembles des longues listes, les tables des questions sémantiques."""

    especes: Especes
    listes: Mapping[str, frozenset[str]]
    tables: Mapping[str, Table]

    @classmethod
    def charger(cls, banc: Banc) -> Referentiel:
        """Lit les réponses de référence des questions qui en ont besoin."""
        listes: dict[str, frozenset[str]] = {}
        tables: dict[str, Table] = {}
        for question in banc.questions.values():
            if question.notation == "longue-liste":
                [tableau] = attendu.lire(_fichier(question))
                listes[question.id] = frozenset(str(ligne["pokemon"]) for ligne in tableau.lignes)
            elif question.notation == "semantique":
                tables[question.id] = _table(question, attendu.lire(_fichier(question)))
        return cls(Especes.charger(), listes, tables)


@dataclass(frozen=True)
class _Jugement:
    """Ce que dit un mode : note, motifs, et les valeurs justes citées (pour la source citée) ;
    sans elles, la source se vérifie sur les espèces que la réponse avance."""

    note: Note
    motifs: tuple[str, ...] = ()
    valeurs: tuple[Valeur, ...] = ()
    rappel: float | None = None
    precision: float | None = None


def noter(
    question: Question,
    tour: Tour,
    referentiel: Referentiel,
    controle: Controleur | None = None,
    precedent: Tour | None = None,
) -> Notation:
    """Pré-note la réponse d'un tour ; controle fait le contrôle de Q2 (controle_par_script sur la
    base, ou sa simulation en mode faux serveur) : sans lui, Q2 passe « à revoir ». precedent : le
    tour précédent d'un second tour (Q2 pour Q18) ; ses lectures comptent aussi pour la source
    citée (ADR-0015)."""
    if tour.question != question.id:
        raise NotationError(f"tour de {tour.question}, noté comme {question.id}")
    if precedent is not None and precedent.question != question.tour_precedent:
        raise NotationError(
            f"tour précédent de {precedent.question}, attendu {question.tour_precedent} pour "
            f"{question.id}"
        )
    tours = (tour,) if precedent is None else (precedent, tour)
    lues = sections(tour.reponse)
    compte = introspections(tour)
    if question.notation == "revue":
        source: Source = "exempte" if question.id in SANS_SOURCE else "à revoir"
        return Notation("à revoir", ("regle",), source, compte)
    if lues.reponse is None:
        return Notation("à revoir", ("sans-reponse",), _source(lues, tours, ()), compte)
    # Le code recopié dans la réponse ne compte pas comme dit (revue adverse du 2026-10-08).
    texte = prose(lues.reponse)
    jugement = _juger(question, texte, referentiel, controle)
    note, motifs = jugement.note, jugement.motifs
    if _distracteur_cite(question, texte):
        note, motifs = "à revoir", (*motifs, "distracteur")
    if question.revoir_si_incomplete and note in {"partiel", "faux"}:
        note, motifs = "à revoir", (*motifs, "incomplete")
    # Sans valeur juste, la réponse se juge sur ce qu'elle affirme : toutes les espèces avancées.
    avancees = tuple(referentiel.especes.citees(texte))
    source = _source(lues, tours, jugement.valeurs or avancees)
    return Notation(note, motifs, source, compte, jugement.rappel, jugement.precision)


def introspections(tour: Tour) -> int:
    """Appels d'introspection du schéma pendant le tour, en échec compris."""
    return sum(
        1
        for appel in tour.appels
        if appel.outil in OUTILS_D_INTROSPECTION
        or (appel.outil == LECTURE and INTROSPECTION.search(appel.requete))
    )


def controle_par_script(
    liste: str, *, script: Path = SCRIPT, dossier: Path | None = None, delai_s: float = 120.0
) -> Controle:
    """Contrôle de Q2 par scripts/questions.sh --controle : sur la base, ou avec --dossier sur la
    traduction de q02.cypher (schéma anglais, D8). Lancé sans la clé Anthropic de l'environnement :
    elle ne sert qu'aux cellules Claude (code-map). Sans réponse dans le délai : NotationError,
    comme tout échec du contrôle."""
    arguments = [
        str(script),
        *(["--dossier", str(dossier)] if dossier else []),
        "--controle",
        liste,
    ]
    environnement = {cle: v for cle, v in os.environ.items() if not cle.startswith("ANTHROPIC_")}
    try:
        fini = subprocess.run(
            arguments,
            capture_output=True,
            text=True,
            timeout=delai_s,
            env=environnement,
            check=False,
        )
    except subprocess.TimeoutExpired as erreur:
        raise NotationError(
            f"questions.sh --controle : aucune réponse en {delai_s:g} s"
        ) from erreur
    if fini.returncode != 0:
        message = (fini.stderr.strip().splitlines() or [""])[-1]
        raise NotationError(f"questions.sh --controle : code {fini.returncode} {message}".strip())
    try:
        tableau = attendu.analyser(fini.stdout)[-1]
    except attendu.AttenduError as erreur:
        raise NotationError(f"questions.sh --controle : réponse illisible ({erreur})") from erreur
    if tableau.colonnes != COLONNES_DU_CONTROLE or len(tableau.lignes) != 1:
        raise NotationError(f"questions.sh --controle : colonnes {tableau.colonnes} inattendues")
    reconnues, non_couverts, valide = (tableau.lignes[0][c] for c in COLONNES_DU_CONTROLE)
    if (
        not isinstance(reconnues, int)
        or isinstance(reconnues, bool)
        or not isinstance(non_couverts, list)
        or not isinstance(valide, bool)
    ):
        raise NotationError(f"questions.sh --controle : valeurs inattendues {tableau.lignes[0]}")
    return Controle(reconnues, tuple(str(t) for t in non_couverts), valide)


def controle_simule(liste: str) -> Controle:
    """Contrôle de Q2 en répétition générale (mode faux serveur, T5.1) : la liste des noms a passé
    leur validation (banc.lecture.liste_cypher), mais aucune base n'est lue. Comme sur une base
    vide, aucune espèce n'est reconnue : Q2 passe « à revoir »."""
    del liste
    return Controle(0, (), False)


# --- Modes de notation ---------------------------------------------------------------------------


def _juger(
    question: Question, reponse: str, referentiel: Referentiel, controle: Controleur | None
) -> _Jugement:
    match question.notation:
        case "valeur" | "ensemble":
            return _ensemble(question, reponse)
        case "liste-ordonnee":
            return _liste_ordonnee(question, reponse, referentiel.especes)
        case "longue-liste":
            return _longue_liste(question, reponse, referentiel)
        case "semantique":
            return _semantique(question, reponse, referentiel)
        case "controle":
            return _controle(question, reponse, referentiel.especes, controle)
        case _:
            raise NotationError(f"{question.id} : mode {question.notation} sans règle")


def _ensemble(question: Question, reponse: str) -> _Jugement:
    """Toutes les valeurs citées, juste ; une partie, partiel ; aucune, faux. Un groupe un_parmi
    compte pour une valeur. Le mode valeur n'en a qu'une : juste ou faux."""
    texte, nombres_du_texte = mots(reponse), nombres(reponse)
    trouvees = [v for v in question.attendus if _cite(v, texte, nombres_du_texte)]
    groupe = [v for v in question.un_parmi if _cite(v, texte, nombres_du_texte)]
    attendues = len(question.attendus) + bool(question.un_parmi)
    obtenues = len(trouvees) + bool(groupe)
    note: Note = "juste" if obtenues == attendues else "partiel" if obtenues else "faux"
    return _Jugement(note, valeurs=(*trouvees, *groupe))


def _liste_ordonnee(question: Question, texte: str, especes: Especes) -> _Jugement:
    """Les espèces attendues en tête, dans l'ordre, à des échanges près (Q8 : Braségali ou
    Typhlosion en 5e). Une espèce de tête sans score, ou nommée comme une forme, passe
    « à revoir » : un faux positif de la liste des espèces ne doit pas finir en note."""
    citations = _citations(especes, question, texte)
    citees = _noms(citations)
    attendues = [str(a) for a in question.attendus]
    distracteurs = {str(d) for d in question.distracteurs}
    tete = citees[: len(attendues)]
    trouvees = tuple(nom for nom in citees if nom in attendues)
    if any(citation.forme for citation in citations):
        return _Jugement("à revoir", ("forme",), trouvees)
    connues = {*attendues, *question.scores, *distracteurs}
    if any(nom not in connues for nom in tete):
        return _Jugement("à revoir", ("hors-classement",), trouvees)
    if len(tete) == len(attendues) and _ordre_tolere(question, tete, attendues):
        return _Jugement("juste", valeurs=tuple(tete))
    return _Jugement("partiel" if trouvees else "faux", valeurs=trouvees)


def _ordre_tolere(question: Question, tete: Sequence[str], attendues: Sequence[str]) -> bool:
    """Deux espèces dont les scores diffèrent de moins de la tolérance peuvent échanger leur place
    (README) : chaque espèce attendue absente doit l'être au profit d'une espèce proche d'elle, et
    chaque inversion d'ordre se faire entre espèces proches ; jamais par glissements cumulés."""
    scores, tolerance = question.scores, question.tolerance or 0.0
    rang = {nom: i for i, nom in enumerate(attendues)}

    def proches(a: str, b: str) -> bool:
        return a in scores and b in scores and round(abs(scores[a] - scores[b]), 3) < tolerance

    def place(nom: str) -> float:
        return -scores[nom] if nom in scores else rang.get(nom, len(rang))

    absentes = [nom for nom in attendues if nom not in tete]
    remplacantes = [nom for nom in tete if nom not in attendues]
    if not all(proches(a, r) for a in absentes for r in remplacantes):
        return False
    return all(
        proches(a, b) for i, a in enumerate(tete) for b in tete[i + 1 :] if place(b) < place(a)
    )


def _longue_liste(question: Question, texte: str, referentiel: Referentiel) -> _Jugement:
    """Règle des longues listes (Q7, Q14 ; README) : liste complète, ou compte exact et extrait.
    Une espèce nommée comme une forme passe « à revoir » : Ossatueur d'Alola n'est pas Sol."""
    ensemble = referentiel.listes[question.id]
    distracteurs = {str(d) for d in question.distracteurs}
    citations = _citations(referentiel.especes, question, texte)
    citees = _noms(citations)
    dans = tuple(nom for nom in citees if nom in ensemble)
    if any(citation.forme for citation in citations):
        return _Jugement("à revoir", ("forme",), dans)
    if any(nom not in ensemble and nom not in distracteurs for nom in citees):
        return _Jugement("à revoir", ("hors-ensemble",), dans)
    compte = question.compte
    if compte is not None and any(math.isclose(n, compte) for n in nombres(texte)):
        if dans:
            return _Jugement("juste", valeurs=dans)
        # Le compte seul : la source citée doit au moins le porter.
        return _Jugement("à revoir", ("compte-seul",), (compte,))
    if set(dans) == ensemble:
        return _Jugement("juste", valeurs=dans)
    return _Jugement("partiel" if dans else "faux", valeurs=dans)


def _semantique(question: Question, texte: str, referentiel: Referentiel) -> _Jugement:
    """Tables de l'ADR-0008. Au singulier : au moins une espèce juste et aucune écartée, juste ;
    les deux, partiel. Au pluriel : précision 100 % et rappel ≥ 50 %, juste ; sinon partiel avec une
    espèce juste (choix de Julien du 2026-10-08). Faux sans espèce juste. Une espèce hors table
    passe « à revoir » (correction sur preuve), comme une espèce nommée comme une forme ; Q9 veut
    aussi les types de chaque espèce."""
    table = referentiel.tables[question.id]
    citations = _citations(referentiel.especes, question, texte)
    citees = _noms(citations)
    justes = table.obligatoires | table.acceptables
    bonnes = tuple(nom for nom in citees if nom in justes)
    rappel = precision = None
    if question.pluriel:
        rappel = len(table.obligatoires.intersection(bonnes)) / len(table.obligatoires)
        precision = len(bonnes) / len(citees) if citees else 0.0
    if any(citation.forme for citation in citations):
        return _Jugement("à revoir", ("forme",), bonnes, rappel, precision)
    if any(nom not in justes and nom not in table.ecartes for nom in citees):
        return _Jugement("à revoir", ("hors-table",), bonnes, rappel, precision)
    note: Note
    if rappel is not None:
        note = (
            "juste"
            if precision == 1 and rappel >= SEUIL_RAPPEL
            else "partiel"
            if bonnes
            else "faux"
        )
    else:
        ecartee = any(nom in table.ecartes for nom in citees)
        note = "partiel" if bonnes and ecartee else "juste" if bonnes else "faux"
    if (
        question.avec_types
        and note != "faux"
        and not _types_exacts(table, citations, texte, bonnes)
    ):
        return _Jugement("à revoir", ("types",), bonnes, rappel, precision)
    return _Jugement(note, (), bonnes, rappel, precision)


def _types_exacts(
    table: Table, citations: Sequence[Citation], texte: str, bonnes: Sequence[str]
) -> bool:
    """Q9 (README : types « exacts », forme par défaut) : les types écrits dans les passages qui
    suivent les mentions d'une espèce juste, jusqu'à l'espèce suivante, sont exactement les siens.
    Un type s'écrit avec sa majuscule : « l'eau » d'une raison n'est pas le type Eau."""
    for nom in bonnes:
        ecrits: set[str] = set()
        for rang, citation in enumerate(citations):
            if citation.nom == nom:
                fin = citations[rang + 1].debut if rang + 1 < len(citations) else len(texte)
                ecrits |= _types_nommes(texte[citation.fin : fin])
        if ecrits != set(table.types.get(nom, ())):
            return False
    return True


def _types_nommes(passage: str) -> set[str]:
    """Types nommés dans un passage, accents ignorés, majuscule exigée."""
    lu = _sans_accents(passage)
    return {
        type_
        for type_ in TYPES
        if re.search(rf"(?<![^\W_]){re.escape(_sans_accents(type_))}(?![^\W_])", lu)
    }


def _sans_accents(texte: str) -> str:
    decompose = unicodedata.normalize("NFKD", texte)
    return "".join(c for c in decompose if not unicodedata.combining(c))


def _controle(
    question: Question, texte: str, especes: Especes, controle: Controleur | None
) -> _Jugement:
    """Q2 : les 6 espèces proposées, contrôlées par q02.cypher (plan, D6). Une équipe qui laisse un
    type sans résistance est fausse : la règle du README est binaire. Un doute sur les 6 noms
    (banc.lecture.equipe) la fait passer « à revoir »."""
    noms = equipe(texte, especes, especes.citees(question.preambule or ""))
    if noms is None:
        return _Jugement("à revoir", ("noms-q2",))
    if controle is None:
        return _Jugement("à revoir", ("sans-controle",), noms)
    resultat = controle(liste_cypher(noms))
    if resultat.especes_reconnues != TAILLE_EQUIPE:
        return _Jugement("à revoir", ("non-reconnus",), noms)
    if resultat.equipe_valide:
        return _Jugement("juste", valeurs=noms)
    return _Jugement("faux", ("types-non-couverts",), noms)


# --- Réponse, distracteurs et source citée -------------------------------------------------------


def _cite(valeur: Valeur, texte: Sequence[str], nombres_du_texte: Sequence[float]) -> bool:
    """Une valeur citée : un nom en mots entiers, un nombre comme un nombre (100 n'est pas 1000)."""
    if isinstance(valeur, str):
        return contient(texte, mots(valeur))
    return any(math.isclose(nombre, valeur) for nombre in nombres_du_texte)


def _distracteur_cite(question: Question, texte: str) -> bool:
    lus, nombres_du_texte = mots(texte), nombres(texte)
    return any(_cite(d, lus, nombres_du_texte) for d in question.distracteurs)


def _citations(especes: Especes, question: Question, texte: str) -> list[Citation]:
    """Espèces citées par la réponse, hors celles que la question nomme (Dracaufeu à Q8, l'équipe
    de référence du préambule de Q2)."""
    sujet = set(especes.citees(f"{question.texte}\n{question.preambule or ''}"))
    return [citation for citation in especes.citations(texte) if citation.nom not in sujet]


def _noms(citations: Sequence[Citation]) -> list[str]:
    return list(dict.fromkeys(citation.nom for citation in citations))


def _source(lues: Sections, tours: Sequence[Tour], valeurs: Sequence[Valeur]) -> Source:
    """Source citée (plan, D4 ; ADR-0018), vérifiée sur les lectures sans erreur du tour, et du tour
    précédent pour un second tour (ADR-0015).

    Les valeurs à retrouver : les valeurs justes de la réponse ; à défaut, les espèces qu'elle
    avance (une réponse fausse se juge sur ce qu'elle affirme). Des requêtes citées portent la
    réponse si elles ont été exécutées pendant le tour, aux espaces près, et que leurs résultats
    contiennent toutes ces valeurs ; des descriptions citées, si les enregistrements qui les ont
    renvoyées, réunis, les contiennent toutes (ADR-0018 : la rigueur d'une requête citée, pas une
    seule valeur). Requêtes et descriptions se jugent chacune à part. Une citation introuvable à
    côté d'une source valable : « à revoir » (inventée, ou simple citation de la question ?). Rien
    à vérifier : « à revoir » si une requête citée a été exécutée (la revue en juge), « non »
    sinon.
    """
    if lues.sources is None:
        return "non"
    lectures = [a for t in tours for a in t.appels if a.outil == LECTURE and not a.erreur]
    enregistrements = [e for a in lectures for e in _enregistrements(a.resultat)]
    inventee = False
    decrites: list[object] = []
    for description in descriptions_citees(lues.sources):
        cible = mots(description)
        porteurs = [
            e
            for e in enregistrements
            if any(isinstance(f, str) and contient(mots(f), cible) for f in e)
        ]
        inventee = inventee or not porteurs
        decrites += [f for e in porteurs for f in e]
    pertinente = bool(decrites and valeurs) and all(_renvoyee(v, decrites) for v in valeurs)
    requetes = requetes_citees(lues.sources)
    executees = [a for a in lectures if any(meme_requete(r, a.requete) for r in requetes)]
    portees = [f for a in executees for f in _feuilles(a.resultat)]
    porteuse = bool(executees and valeurs) and all(_renvoyee(v, portees) for v in valeurs)
    if porteuse or pertinente:
        return "à revoir" if inventee else "oui"
    if executees and not valeurs:
        return "à revoir"
    return "non"


def _enregistrements(resultat: str) -> list[list[object]]:
    """Valeurs de chaque enregistrement d'un résultat de read-cypher (JSON, nœuds compris) ; un
    résultat qui n'est pas du JSON se lit comme un seul enregistrement, d'un seul texte."""
    try:
        donnees = json.loads(resultat)
    except json.JSONDecodeError:
        return [[resultat]]
    if isinstance(donnees, list):
        return [list(_deplier(element)) for element in donnees]
    return [list(_deplier(donnees))]


def _feuilles(resultat: str) -> list[object]:
    return [feuille for e in _enregistrements(resultat) for feuille in e]


def _deplier(valeur: object) -> Iterator[object]:
    if isinstance(valeur, list):
        for element in valeur:
            yield from _deplier(element)
    elif isinstance(valeur, dict):
        for element in valeur.values():
            yield from _deplier(element)
    else:
        yield valeur


def _renvoyee(valeur: Valeur, feuilles: Sequence[object]) -> bool:
    """Une valeur de la réponse se retrouve-t-elle dans les résultats (un nom dans un texte, un
    nombre comme nombre, ou écrit dans un texte : « Lokhlass ×2.0 ») ?"""
    if isinstance(valeur, str):
        cible = mots(valeur)
        return any(isinstance(f, str) and contient(mots(f), cible) for f in feuilles)
    for feuille in feuilles:
        if isinstance(feuille, int | float) and not isinstance(feuille, bool):
            if math.isclose(feuille, valeur):
                return True
        elif isinstance(feuille, str) and any(math.isclose(n, valeur) for n in nombres(feuille)):
            return True
    return False


# --- Lecture des réponses de référence -----------------------------------------------------------


def table_semantique(question: Question, texte: str) -> Table:
    """La table d'une question sémantique (ADR-0008), lue dans le texte de sa réponse de référence
    (questions/attendu/qNN.txt) : banc.recherche_seule la lit au commit d'un gel (spec 003, D13).

    Raises:
        AttenduError: texte illisible.
        NotationError: ensemble inconnu.
        ValueError: plus d'un tableau, ou aucun.
    """
    return _table(question, attendu.analyser(texte))


def _fichier(question: Question) -> str:
    return f"q{int(question.id[1:]):02d}"


def _table(question: Question, tableaux: list[attendu.Tableau]) -> Table:
    [tableau] = tableaux
    ensembles: dict[str, set[str]] = {ensemble: set() for ensemble in ENSEMBLES}
    types: dict[str, tuple[str, ...]] = {}
    for ligne in tableau.lignes:
        nom, ensemble = str(ligne["pokemon"]), str(ligne["ensemble"])
        if ensemble not in ensembles:
            raise NotationError(f"{question.id} : ensemble {ensemble!r} inconnu pour {nom}")
        ensembles[ensemble].add(nom)
        valeur = ligne.get("types")
        if isinstance(valeur, list):
            types[nom] = tuple(str(t) for t in valeur)
    obligatoires, acceptables, ecartes = (frozenset(ensembles[e]) for e in ENSEMBLES)
    return Table(obligatoires, acceptables, ecartes, types)
