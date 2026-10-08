"""Revue humaine à l'aveugle (plan 002, T3.2 ; D4) : `banc revoir --campagne <id> [--verifier]`.

Les cas : dans le CSV d'une campagne (banc.mesures), la ligne retenue de chaque question, celle de
son dernier essai ; une réponse dont la note ou la source est « à revoir », sans décision. Un échec
compte faux d'office, une panne se relance : ni l'un ni l'autre n'est revu.

À l'aveugle : rien de ce qui trahit la cellule (cellule, modèle, passe, essai, durée, coût), les
noms de modèles masqués dans le texte, un ordre mélangé qui ne suit pas l'alternance des cellules.
On voit le message posé, le tour précédent d'un second tour, la référence (réponse attendue et
règles du README), la pré-notation, la réponse de l'agent et, si la source est à revoir, les
lectures du tour.

Les décisions : banc/mesures/revues.toml (versionné), une table [[revue]] par cas, ajoutée dès la
saisie, jamais réécrite ; des codes seulement, et la date-heure. Une note se réutilise pour une
même question et une même réponse courte normalisée (empreinte), à partir des décisions datées du
gel (gel = <date-heure>, en tête du fichier, posé en T8.1) : rien n'est hérité du pilote. Jamais
la source, qui dépend de la trace ; jamais pour une question dont la règle dépasse la réponse
courte. Une espèce acceptée sur preuve (ADR-0008) entre dans sa table à la main : la revue ne
touche pas aux tables.
"""

import hashlib
import json
import re
import sys
import tomllib
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import asdict, astuple, dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

from banc import attendu, mesures
from banc.mesures import CODE, QUESTION, TourMesure

MESURES = mesures.MESURES
TRACES = mesures.TRACES
README = Path(__file__).resolve().parents[3] / "questions" / "README.md"
A_REVOIR = "à revoir"
NOTES = {"j": "juste", "p": "partiel", "f": "faux"}
SOURCES = {"o": "oui", "n": "non", "e": "exempte"}
# Jamais de réutilisation quand la règle dépasse la réponse courte : explication (Q11, Q27),
# signalement (Q7, Q12, Q13, Q28), prémisse (Q29) ; plan, D4. Puis culture générale signalée
# (Q10), formes acceptées si signalées (Q14, Q15), critère demandé ou annoncé (Q30) : choix de
# Julien du 2026-10-08 (T3.2).
SANS_REUTILISATION = frozenset(
    {"Q7", "Q10", "Q11", "Q12", "Q13", "Q14", "Q15", "Q27", "Q28", "Q29", "Q30"}
)
EMPREINTE = re.compile(r"[0-9a-f]{16}")
# Un motif de décision : un code d'au moins 3 caractères (une lettre seule est une faute de frappe).
MOTIF_MINIMAL = 3
MODELES = re.compile(r"\b(?:Claude|Anthropic|Gemini|Google|Sonnet|Haiku|Opus)\b", re.IGNORECASE)
LIMITE_RESULTAT = 1_500
EN_TETE = """\
# Décisions de la revue humaine à l'aveugle (plan 002, T3.2) : une table [[revue]] par cas, ajoutée
# par `banc revoir`, jamais réécrite ; une correction se fait ici, à la main (diff versionné).
# Le gel du protocole (T8.1) s'inscrit tout en haut, avant toute table : gel = AAAA-MM-JJTHH:MM:SS.
# Seules les décisions datées du gel ou après se réutilisent, par réponse courte normalisée.
"""

# Un cas : campagne, cellule, passe, question, essai.
type Cle = tuple[str, str, int, str, int]
type Saisie = tuple[str | None, str | None, str | None] | Literal["sauter", "quitter"]


class RevueError(Exception):
    """Revue impossible : revues.toml illisible, décisions en double ou contradictoires, trace
    absente."""


@dataclass(frozen=True)
class Decision:
    """Ce que la revue a tranché pour un cas : la note, la source, ou les deux ; un motif
    facultatif (code) ; la date-heure de la décision."""

    campagne: str
    cellule: str
    passe: int
    question: str
    essai: int
    # Réponse courte normalisée du cas (banc.mesures.empreinte) ; vide s'il n'en a pas.
    empreinte: str
    date: datetime
    note: str | None = None
    source: str | None = None
    motif: str | None = None

    def __post_init__(self) -> None:
        motif = self.motif
        problemes = {
            "campagne": not CODE.fullmatch(self.campagne),
            "cellule": not CODE.fullmatch(self.cellule),
            "passe": self.passe < 1,
            "essai": self.essai < 1,
            "question": not QUESTION.fullmatch(self.question),
            "empreinte": bool(self.empreinte) and not EMPREINTE.fullmatch(self.empreinte),
            "date": not isinstance(self.date, datetime),
            "note": self.note is not None and self.note not in NOTES.values(),
            "source": self.source is not None and self.source not in SOURCES.values(),
            "rien de tranché": self.note is None and self.source is None,
            "motif": motif is not None
            and not (CODE.fullmatch(motif) and len(motif) >= MOTIF_MINIMAL),
        }
        if fautifs := [champ for champ, probleme in problemes.items() if probleme]:
            raise RevueError(f"décision invalide ({', '.join(fautifs)}) : {self}")

    @property
    def cle(self) -> Cle:
        """Le cas tranché."""
        return (self.campagne, self.cellule, self.passe, self.question, self.essai)


@dataclass(frozen=True)
class Revues:
    """revues.toml relu : le gel du protocole (None tant qu'il n'est pas posé), puis les décisions
    dans l'ordre de leur saisie. Une décision par cas ; deux notes réutilisables contraires pour
    une même réponse courte sont refusées."""

    gel: datetime | None = None
    decisions: tuple[Decision, ...] = ()

    def __post_init__(self) -> None:
        vus: set[Cle] = set()
        for decision in self.decisions:
            if decision.cle in vus:
                raise RevueError(f"deux décisions pour le cas {decision.cle}")
            vus.add(decision.cle)
        notes: dict[tuple[str, str], str | None] = {}
        for decision in self._reutilisables():
            vue = notes.setdefault((decision.question, decision.empreinte), decision.note)
            if vue != decision.note:
                raise RevueError(
                    f"décisions contradictoires pour {decision.question} ({decision.empreinte}) : "
                    f"{vue} et {decision.note}"
                )

    def du_cas(self, cle: Cle) -> Decision | None:
        """La décision de ce cas, s'il en a une."""
        return next((d for d in self.decisions if d.cle == cle), None)

    def reutilisable(self, question: str, empreinte: str) -> Decision | None:
        """Une décision dont la note vaut pour cette réponse courte normalisée, s'il en est."""
        return next(
            (
                d
                for d in self._reutilisables()
                if (d.question, d.empreinte) == (question, empreinte)
            ),
            None,
        )

    def _reutilisables(self) -> Iterator[Decision]:
        if self.gel is None:
            return
        for decision in self.decisions:
            if (
                decision.note is not None
                and decision.empreinte
                and decision.question not in SANS_REUTILISATION
                and decision.date >= self.gel
            ):
                yield decision


@dataclass(frozen=True)
class Finale:
    """Note et source d'une ligne après la revue ; l'origine de la note (pre-note, revue ou
    reutilisee) et le motif de la décision qui l'a tranchée."""

    note: str
    source: str
    origine: str
    motif: str = ""


def cle(ligne: Mapping[str, str]) -> Cle:
    """Le cas d'une ligne du CSV."""
    passe, essai = int(ligne["passe"]), int(ligne["essai"])
    return (ligne["campagne"], ligne["cellule"], passe, ligne["question"], essai)


def charger(fichier: Path) -> Revues:
    """Relit revues.toml ; absent, aucune décision et pas de gel."""
    try:
        brut = tomllib.loads(fichier.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return Revues()
    except (OSError, tomllib.TOMLDecodeError) as erreur:
        raise RevueError(f"{fichier} illisible : {erreur}") from erreur
    if inconnues := sorted(set(brut) - {"gel", "revue"}):
        raise RevueError(f"{fichier} : clés inconnues {inconnues}")
    gel = brut.get("gel")
    if gel is not None and not isinstance(gel, datetime):
        raise RevueError(f"{fichier} : gel = AAAA-MM-JJTHH:MM:SS attendu, pas {gel!r}")
    try:
        decisions = tuple(Decision(**table) for table in brut.get("revue", []))
    except TypeError as erreur:
        raise RevueError(f"{fichier} : décision incomplète ou inconnue ({erreur})") from erreur
    return Revues(gel, decisions)


def ajouter(fichier: Path, decision: Decision) -> None:
    """Ajoute une décision en fin de fichier, créé avec son en-tête s'il manque."""
    champs = {nom: valeur for nom, valeur in asdict(decision).items() if valeur is not None}
    lignes = ["", "[[revue]]"]
    for nom, valeur in champs.items():
        texte = valeur.isoformat() if isinstance(valeur, datetime) else json.dumps(valeur)
        lignes.append(f"{nom} = {texte}")
    fichier.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not fichier.exists()
    with fichier.open("a", encoding="utf-8") as flux:
        if nouveau:
            flux.write(EN_TETE)
        flux.write("\n".join(lignes) + "\n")


# --- Cas à revoir et notes finales ---------------------------------------------------------------


def retenues(lignes: Iterable[Mapping[str, str]]) -> list[Mapping[str, str]]:
    """Les lignes qui comptent : pour chaque question d'une passe d'une cellule, celle du dernier
    essai (une paire relancée après une panne se rejoue en entier)."""
    lignes = list(lignes)
    dernieres: dict[tuple[str, str, int, str], int] = {}
    for rang, ligne in enumerate(lignes):
        campagne, cellule, passe, question, essai = cle(ligne)
        groupe = (campagne, cellule, passe, question)
        if groupe in dernieres and int(lignes[dernieres[groupe]]["essai"]) == essai:
            raise RevueError(f"ligne en double dans les mesures : {cle(ligne)}")
        if groupe not in dernieres or essai > int(lignes[dernieres[groupe]]["essai"]):
            dernieres[groupe] = rang
    return [lignes[rang] for rang in sorted(dernieres.values())]


def finale(ligne: Mapping[str, str], revues: Revues) -> Finale:
    """Note et source d'une ligne : la pré-notation, sauf ce que la revue a tranché, sur ce cas ou,
    pour la note, sur une même réponse courte."""
    note, source, origine = ligne["note"], ligne["source"], "pre-note"
    propre = revues.du_cas(cle(ligne))
    reprise = None
    if note == A_REVOIR:
        if propre is not None and propre.note is not None:
            note, origine = propre.note, "revue"
        elif (reprise := revues.reutilisable(ligne["question"], ligne["empreinte"])) is not None:
            note, origine = reprise.note or note, "reutilisee"
    if source == A_REVOIR and propre is not None and propre.source is not None:
        source = propre.source
    motif = (propre.motif if propre else None) or (reprise.motif if reprise else None) or ""
    return Finale(note, source, origine, motif)


def en_attente(lignes: Iterable[Mapping[str, str]], revues: Revues) -> list[Mapping[str, str]]:
    """Les lignes retenues dont la note ou la source reste « à revoir » ; seule une réponse peut
    l'être (banc.mesures.ligne : un échec est faux, une panne sans note)."""
    return [ligne for ligne in retenues(lignes) if A_REVOIR in astuple(finale(ligne, revues))[:2]]


def melanger(cas: Sequence[Mapping[str, str]]) -> list[Mapping[str, str]]:
    """L'ordre de la revue : celui d'une empreinte de chaque cas. Rien n'y suit l'alternance des
    cellules du CSV, et une revue reprise garde l'ordre des cas restants."""
    return sorted(cas, key=lambda ligne: hashlib.sha256(repr(cle(ligne)).encode()).hexdigest())


# --- Présentation à l'aveugle --------------------------------------------------------------------


def presenter(
    ligne: Mapping[str, str], tour: TourMesure, precedent: TourMesure | None, reference: str
) -> str:
    """Le cas tel que la revue le montre : rien de ce qui trahit la cellule."""
    blocs = []
    if precedent is not None:
        blocs.append(f"Tour précédent : {precedent.question}\n{_retrait(precedent.message)}")
        blocs.append(
            f"Réponse de l'agent au tour précédent :\n{_retrait(_masquer(precedent.reponse))}"
        )
    blocs.append(f"Question {ligne['question']} :\n{_retrait(tour.message)}")
    blocs.append(f"Référence :\n{_retrait(reference)}")
    note = "note à revoir" if ligne["note"] == A_REVOIR else f"note pré-notée : {ligne['note']}"
    source = A_REVOIR if ligne["source"] == A_REVOIR else f"pré-notée : {ligne['source']}"
    motifs = ligne["motifs"].replace("+", ", ") or "aucun"
    blocs.append(f"Pré-notation : {note} ; source {source} ; motifs : {motifs}")
    blocs.append(f"Réponse de l'agent :\n{_retrait(_masquer(tour.reponse))}")
    if ligne["source"] == A_REVOIR:
        blocs.append(_lectures(tour))
    return "\n\n".join(blocs)


def regles(question: str, readme: Path = README) -> tuple[str, ...]:
    """Les puces des « Règles de réponse » du README qui citent la question, avec leurs
    sous-puces."""
    _, _, section = readme.read_text(encoding="utf-8").partition("## Règles de réponse")
    puces: list[list[str]] = []
    for ligne in section.split("\n## ", 1)[0].splitlines():
        if ligne.startswith("- "):
            puces.append([ligne])
        elif puces and (not ligne.strip() or ligne.startswith(" ")):
            puces[-1].append(ligne)
    citee = re.compile(rf"\b{re.escape(question)}\b")
    textes = ("\n".join(puce).strip() for puce in puces)
    return tuple(texte for texte in textes if citee.search(texte))


def reference(question: str, dossier: Path = attendu.DOSSIER, readme: Path = README) -> str:
    """La référence d'une question : sa réponse attendue (questions/attendu/), puis ses règles."""
    fichier = dossier / f"q{int(question[1:]):02d}.txt"
    if fichier.exists():
        attendue = "\n".join(fichier.read_text(encoding="utf-8").splitlines()[1:])
        tete = f"questions/attendu/{fichier.name} :\n{attendue}"
    else:
        tete = "aucune requête de référence : la règle du README fait foi"
    return "\n\n".join([tete, *regles(question, readme)])


def traces(dossier: Path) -> dict[Cle, tuple[TourMesure, TourMesure | None]]:
    """Les tours des traces d'une campagne, par cas, chacun avec le tour qui le précède dans sa
    conversation (Q2 pour Q18, Q27 pour Q28)."""
    index: dict[Cle, tuple[TourMesure, TourMesure | None]] = {}
    for fichier in sorted(dossier.glob("*.jsonl")):
        conversation = mesures.lire(fichier)
        e = conversation.entete
        precedent = None
        for tour in conversation.tours:
            index[e.campagne, e.cellule, e.passe, tour.question, e.essai] = (tour, precedent)
            precedent = tour
    return index


# --- Saisie, vérification, commande --------------------------------------------------------------


def _maintenant() -> datetime:
    return datetime.now().replace(microsecond=0)


@dataclass(frozen=True)
class Console:
    """Ce que la revue lit et écrit, et l'heure de ses décisions (l'horloge murale : une
    décision se date, elle ne se chronomètre pas)."""

    lire: Callable[[str], str] = input
    ecrire: Callable[[str], None] = print
    maintenant: Callable[[], datetime] = _maintenant


TERMINAL = Console()


def revoir(
    lignes: Sequence[Mapping[str, str]],
    index: Mapping[Cle, tuple[TourMesure, TourMesure | None]],
    fichier: Path,
    console: Console = TERMINAL,
    ordre: Callable[[Sequence[Mapping[str, str]]], list[Mapping[str, str]]] = melanger,
) -> int:
    """Revue au clavier des cas en attente, un par un ; chaque décision est écrite aussitôt.
    « s » saute un cas, « q » ou Ctrl-D arrête la revue."""
    ecrire = console.ecrire
    revues = charger(fichier)
    cas = ordre(en_attente(lignes, revues))
    decidees = 0
    for rang, ligne in enumerate(cas, start=1):
        # Une décision prise entre-temps a pu trancher ce cas (même réponse courte, après le gel).
        etat = finale(ligne, revues)
        besoins = [genre for genre, valeur in (("note", etat.note), ("source", etat.source))
                   if valeur == A_REVOIR]  # fmt: skip
        if not besoins:
            continue
        if cle(ligne) not in index:
            raise RevueError(f"aucune trace pour le cas {cle(ligne)} (logs/banc/ de ce poste ?)")
        tour, precedent = index[cle(ligne)]
        ecrire(f"\n── Cas {rang}/{len(cas)} " + "─" * 60)
        ecrire(presenter(ligne, tour, precedent, reference(ligne["question"])))
        saisie = _demander(besoins, console)
        if saisie == "quitter":
            break
        if saisie == "sauter":
            continue
        note, source, motif = saisie
        quand = console.maintenant()
        decision = Decision(*cle(ligne), ligne["empreinte"], quand, note, source, motif)
        ajouter(fichier, decision)
        revues = Revues(revues.gel, (*revues.decisions, decision))
        decidees += 1
    restants = len(en_attente(lignes, revues))
    ecrire(
        f"{decidees} décision{_s(decidees)} enregistrée{_s(decidees)} ; "
        f"{restants} cas restant{_s(restants)}"
    )
    return 0


def verifier(
    lignes: Iterable[Mapping[str, str]], revues: Revues, ecrire: Callable[[str], None] = print
) -> int:
    """0 s'il ne reste aucun cas à revoir, 1 sinon (DoD de T9.2)."""
    restants = en_attente(lignes, revues)
    questions = ", ".join(ligne["question"] for ligne in restants)
    ecrire(f"{len(restants)} cas à revoir" + (f" ({questions})" if restants else ""))
    return 1 if restants else 0


def commande(campagne: str, *, seulement_verifier: bool) -> int:
    """`banc revoir` : codes retour 0 (fini), 1 (cas restants, --verifier), 2 (erreur)."""
    try:
        lignes = mesures.lire_lignes(mesures.fichier_mesures(campagne, MESURES))
        fichier = MESURES / "revues.toml"
        if seulement_verifier:
            return verifier(lignes, charger(fichier))
        return revoir(lignes, traces(TRACES / campagne), fichier)
    except (mesures.MesureError, RevueError) as erreur:
        print(f"banc revoir : {erreur}", file=sys.stderr)
        return 2


def _demander(besoins: Sequence[str], console: Console) -> Saisie:
    """Lit une décision : les lettres demandées, dans l'ordre (note, puis source), puis un motif
    facultatif ; redemande tant que la saisie est invalide."""
    choix = {"note": NOTES, "source": SOURCES}
    aide = " puis ".join(f"{genre} {'/'.join(choix[genre])}" for genre in besoins)
    invite = f"Décision ({aide}) [motif] ; s : sauter, q : quitter > "
    while True:
        try:
            mots = console.lire(invite).split()
        except EOFError:
            return "quitter"
        if mots in (["q"], ["s"]):
            return "quitter" if mots == ["q"] else "sauter"
        lettres, reste = mots[: len(besoins)], mots[len(besoins) :]
        valeurs = {
            genre: choix[genre].get(lettre) for genre, lettre in zip(besoins, lettres, strict=False)
        }
        motif = reste[0] if len(reste) == 1 else None
        if (
            len(lettres) == len(besoins)
            and None not in valeurs.values()
            and len(reste) <= 1
            and (motif is None or (CODE.fullmatch(motif) and len(motif) >= MOTIF_MINIMAL))
        ):
            return valeurs.get("note"), valeurs.get("source"), motif
        console.ecrire(
            f"Saisie invalide : {aide}, puis un motif facultatif (code d'au moins 3 caractères)."
        )


def _lectures(tour: TourMesure) -> str:
    lignes = ["Lectures du tour :"]
    for rang, appel in enumerate(tour.appels, start=1):
        etat = " (en erreur)" if appel.erreur else ""
        lignes += [f"  [{rang}] {appel.outil}{etat}", _retrait(appel.requete, 6)]
        lignes += ["      →", _retrait(_tronquer(appel.resultat), 6)]
    return "\n".join(lignes) if tour.appels else "Lectures du tour : aucune"


def _tronquer(texte: str) -> str:
    if len(texte) <= LIMITE_RESULTAT:
        return texte
    return f"{texte[:LIMITE_RESULTAT]} … (+{len(texte) - LIMITE_RESULTAT} caractères)"


def _masquer(texte: str) -> str:
    return MODELES.sub("‹modèle›", texte)


def _retrait(texte: str, espaces: int = 2) -> str:
    return "\n".join(" " * espaces + ligne if ligne else "" for ligne in texte.splitlines())


def _s(nombre: int) -> str:
    return "s" if nombre > 1 else ""
