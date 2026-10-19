"""Recherche seule (spec 003, US2 ; plan D13) : banc recherche-seule --campagne <id>.

Ce que la recherche vectorielle de la technique 3 retrouve, sans LLM, pour les questions sémantiques
(notation « semantique » de questions/banc.toml : Q3, Q9, Q16, Q17, Q26), lu dans les traces d'une
campagne GraphRAG, sans aucun appel de plus, ni à la base ni à un modèle :

- la recherche est la même d'une trace à l'autre : un seul résultat (son empreinte) par question,
  pour les deux cellules et toutes les passes ; une recherche en erreur n'a pas de résultat, une
  trace écartée (.jsonl.ecartee, cellule fautive) ne compte pas ;
- la part des espèces obligatoires et acceptables de la grille (ADR-0008) parmi les espèces
  retrouvées, avec le plafond de la question : la recherche rend PLAFOND espèces au plus, d'où
  min(PLAFOND, taille de la grille) ;
- les espèces retrouvées hors du filet de mots-clés de la requête de référence : absentes de la
  table, ou marquées horsFilet dans son classement (questions/qNN.cypher, README des questions),
  chacune avec son ensemble, ou « à classer ». Leur classement (pré-classement de Claude, accord
  de Julien) s'écrit dans le résultat d'US2 du rapport, sans toucher aux tables.

Les tables se lisent telles qu'au commit du gel du jalon de la campagne, même si T16.2 les a
changées depuis (D13) : le jalon est celui du dernier gel posé au premier jour de ses traces ou
avant (banc.revue), le commit celui qui a écrit ce gel dans banc/mesures/revues.toml (git log -S).
Choix de Julien du 2026-10-19 : commit lu dans git, hors filet par la table et ses marques
horsFilet, classement consigné dans le rapport.

Codes retour : 0 conforme · 1 écart (recherche différente d'une trace à l'autre, question sans
recherche) · 2 erreur technique (campagne introuvable, hors GraphRAG ou en faux serveur, trace ou
résultat illisible, gel introuvable, git en échec).
"""

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

from banc import questions as banc_questions
from banc import revue
from banc.attendu import AttenduError
from banc.mesures import CODE, TRACES, Conversation, MesureError, lire
from banc.notation import ENSEMBLES, NotationError, Table, table_semantique
from banc.orchestration import OrchestrationError, lire_campagne
from banc.questions import BancError, Question

DEPOT = Path(__file__).resolve().parents[3]
# revues.toml, relatif au dépôt : git en lit l'historique.
REVUES = "banc/mesures/revues.toml"
# La recherche rend 20 espèces au plus (questions/recherche.cypher, LIMIT 20 ; plan D6).
PLAFOND = 20
A_CLASSER = "à classer"
# Une entrée du classement marquée hors filet : son nom, puis la marque, sur une ou plusieurs
# lignes, sans sortir de ses accolades (questions/q09.cypher, Poissirène).
MARQUE = re.compile(r"\{\s*pokemon:\s*'([^']+)'[^{}]*\bhorsFilet:\s*true\b[^{}]*\}")
DELAI_GIT_S = 60


class RechercheSeuleError(Exception):
    """Mesure impossible : campagne invalide, hors GraphRAG ou sans trace, gel introuvable,
    résultat ou table illisibles, git en échec."""


@dataclass(frozen=True)
class Gel:
    """Le gel du jalon d'une campagne : sa date-heure dans revues.toml, et le commit qui l'a
    écrit."""

    moment: datetime
    commit: str


@dataclass(frozen=True)
class Bilan:
    """Ce qu'une question donne : sa ligne, ses détails, et si elle est en écart."""

    tete: str
    details: tuple[str, ...] = ()
    ecart: bool = False


def commande(
    campagne: str,
    *,
    traces: Path = TRACES,
    depot: Path = DEPOT,
    ecrire: Callable[[str], None] = print,
) -> int:
    """`banc recherche-seule` : 0 conforme, 1 écart, 2 erreur technique."""
    try:
        conversations = conversations_de(campagne, traces)
        gel = gel_de(min(conversation.entete.jour for _, conversation in conversations), depot)
        bilans = [bilan(question, conversations, gel, depot) for question in semantiques()]
    except (
        RechercheSeuleError,
        OrchestrationError,
        MesureError,
        revue.RevueError,
        BancError,
        OSError,
        UnicodeDecodeError,
    ) as erreur:
        print(f"banc recherche-seule : {erreur}", file=sys.stderr)
        return 2
    ecrire(
        f"campagne {campagne} : {len(conversations)} traces ; tables du gel du "
        f"{gel.moment.isoformat()} (commit {gel.commit[:12]})"
    )
    for resultat in bilans:
        ecrire(f"{'✗' if resultat.ecart else '✓'} {resultat.tete}")
        for detail in resultat.details:
            ecrire(f"  · {detail}")
    if ecarts := sum(1 for resultat in bilans if resultat.ecart):
        ecrire(f"ÉCART : {ecarts} question(s) sur {len(bilans)}.")
        return 1
    ecrire(
        f"CONFORME : {len(bilans)} questions mesurées, même résultat de recherche d'une trace à "
        "l'autre."
    )
    return 0


def conversations_de(campagne: str, traces: Path) -> list[tuple[str, Conversation]]:
    """Les traces d'une campagne GraphRAG qui a lu la base, chacune avec son nom ; une trace
    écartée n'en est pas une."""
    if not CODE.fullmatch(campagne):
        raise RechercheSeuleError(
            f"campagne {campagne!r} : un code attendu (minuscules, chiffres, -)"
        )
    dossier = traces / campagne
    parametres = lire_campagne(dossier / "campagne.json")
    if parametres.consigne != "contexte":
        raise RechercheSeuleError(
            f"campagne {campagne} : cellules {', '.join(parametres.cellules)}, sans recherche "
            "vectorielle (technique 2)"
        )
    if parametres.faux_serveur:
        raise RechercheSeuleError(
            f"campagne {campagne} en faux serveur : sa recherche n'a pas lu la base"
        )
    fichiers = sorted(dossier.glob("*.jsonl"))
    if not fichiers:
        raise RechercheSeuleError(f"campagne {campagne} : aucune trace dans {dossier}")
    return [(fichier.name, lire(fichier)) for fichier in fichiers]


def gel_de(jour: date, depot: Path) -> Gel:
    """Le gel du jalon d'une campagne commencée ce jour : le dernier posé ce jour ou avant
    (revues.toml du dépôt), avec le plus ancien commit qui l'a écrit dans revues.toml."""
    revues = revue.charger(depot / REVUES)
    gels = [gel for gel in (revues.gel, *(jalon.gel for jalon in revues.jalons)) if gel]
    if not (poses := [gel for gel in gels if gel.date() <= jour]):
        raise RechercheSeuleError(f"aucun gel posé le {jour.isoformat()} ou avant ({REVUES})")
    moment = max(poses)
    ligne = f"gel = {moment.isoformat()}"
    commits = _git(depot, "log", "--format=%H", "--reverse", f"-S{ligne}", "--", REVUES).split()
    if not commits:
        raise RechercheSeuleError(
            f"gel du {moment.isoformat()} introuvable dans l'historique de {REVUES}"
        )
    return Gel(moment, commits[0])


def semantiques() -> list[Question]:
    """Les questions sémantiques du banc (ADR-0008), par numéro."""
    banc = banc_questions.charger()
    choisies = (
        question for question in banc.questions.values() if question.notation == "semantique"
    )
    return sorted(choisies, key=lambda question: int(question.id[1:]))


def bilan(
    question: Question, conversations: Sequence[tuple[str, Conversation]], gel: Gel, depot: Path
) -> Bilan:
    """Une question : un seul résultat de recherche dans ses traces, puis la part de sa grille au
    gel, son plafond et ses espèces hors filet."""
    recherches = [
        (nom, appel.resultat)
        for nom, conversation in conversations
        for tour in conversation.tours
        if tour.question == question.id
        for appel in tour.appels
        if not appel.erreur
    ]
    if not recherches:
        return Bilan(f"{question.id} : aucune recherche réussie dans les traces", ecart=True)
    empreintes = {nom: _empreinte(resultat) for nom, resultat in recherches}
    if (differents := len(set(empreintes.values()))) > 1:
        return Bilan(
            f"{question.id} : {differents} résultats différents dans {len(recherches)} traces",
            tuple(f"{nom} : résultat {empreinte}" for nom, empreinte in sorted(empreintes.items())),
            ecart=True,
        )
    especes = especes_de(question.id, recherches[0][1])
    table = table_au_gel(question, gel, depot)
    grille = table.obligatoires | table.acceptables
    if not grille:
        raise RechercheSeuleError(
            f"{question.id} : aucune espèce obligatoire ni acceptable dans la table du gel"
        )
    ensembles = {
        espece: ensemble
        for ensemble, membres in zip(
            ENSEMBLES, (table.obligatoires, table.acceptables, table.ecartes), strict=True
        )
        for espece in membres
    }
    marques = hors_filet_marques(
        _git(depot, "show", f"{gel.commit}:questions/{_nom(question)}.cypher")
    )
    trouvees = [espece for espece in especes if espece in grille]
    hors_filet = [
        f"{espece} ({ensembles.get(espece, A_CLASSER)})"
        for espece in especes
        if espece not in ensembles or espece in marques
    ]
    plafond = min(PLAFOND, len(grille))
    return Bilan(
        f"{question.id} : {len(especes)} espèces retrouvées, même résultat dans "
        f"{len(recherches)} traces",
        (
            f"grille : {len(trouvees)} sur {len(grille)} obligatoires et acceptables "
            f"({_pourcentage(len(trouvees), len(grille))}), plafond {plafond} sur {len(grille)} "
            f"({_pourcentage(plafond, len(grille))})",
            f"dans la grille : {', '.join(trouvees) or 'aucune'}",
            f"hors filet : {', '.join(hors_filet) or 'aucune'}",
        ),
    )


def especes_de(question: str, resultat: str) -> tuple[str, ...]:
    """Les espèces d'un résultat de recherche, dans son ordre (questions/recherche.cypher : un
    enregistrement par espèce, PLAFOND au plus)."""
    try:
        enregistrements = json.loads(resultat)
    except json.JSONDecodeError as erreur:
        raise RechercheSeuleError(
            f"{question} : résultat de recherche illisible ({erreur})"
        ) from erreur
    if not isinstance(enregistrements, list) or not all(
        isinstance(enregistrement, dict) and isinstance(enregistrement.get("espece"), str)
        for enregistrement in enregistrements
    ):
        raise RechercheSeuleError(
            f"{question} : résultat de recherche inattendu, une liste d'enregistrements avec "
            "« espece » attendue"
        )
    if len(enregistrements) > PLAFOND:
        raise RechercheSeuleError(
            f"{question} : {len(enregistrements)} espèces, plus que les {PLAFOND} de la recherche"
        )
    return tuple(enregistrement["espece"] for enregistrement in enregistrements)


def table_au_gel(question: Question, gel: Gel, depot: Path) -> Table:
    """La table d'une question sémantique telle qu'au commit du gel (attendu/qNN.txt)."""
    texte = _git(depot, "show", f"{gel.commit}:questions/attendu/{_nom(question)}.txt")
    try:
        return table_semantique(question, texte)
    except (AttenduError, NotationError, ValueError) as erreur:
        raise RechercheSeuleError(f"{question.id} : table du gel illisible ({erreur})") from erreur


def hors_filet_marques(classement: str) -> frozenset[str]:
    """Les espèces marquées horsFilet dans le classement d'une question sémantique (qNN.cypher) :
    classées sur preuve, sans que le filet de mots-clés les trouve (README des questions)."""
    return frozenset(MARQUE.findall(classement))


def _git(depot: Path, *arguments: str) -> str:
    """La sortie d'une commande git en lecture dans le dépôt."""
    try:
        fini = subprocess.run(
            ["git", "-C", str(depot), *arguments],
            capture_output=True,
            encoding="utf-8",
            timeout=DELAI_GIT_S,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        raise RechercheSeuleError(f"git {arguments[0]} : {erreur}") from erreur
    if fini.returncode != 0:
        raise RechercheSeuleError(f"git {arguments[0]} : {fini.stderr.strip()}")
    return fini.stdout


def _nom(question: Question) -> str:
    return f"q{int(question.id[1:]):02d}"


def _empreinte(resultat: str) -> str:
    return hashlib.sha256(resultat.encode("utf-8")).hexdigest()[:12]


def _pourcentage(partie: int, tout: int) -> str:
    """Un pourcentage arrondi à l'unité la plus proche, une demie vers le haut (12,5 : 13 %)."""
    return f"{(Decimal(100 * partie) / tout).quantize(Decimal(1), rounding=ROUND_HALF_UP)} %"
