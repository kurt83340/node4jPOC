"""Contre-épreuve de la revue assistée (ADR-0014 ; plan 003, D15, T1.1) : `banc contre-epreuve`.

Avant de voir la pré-analyse de Claude, Julien revoit seul, à l'aveugle, 8 cas tirés au sort parmi
les cas à revoir d'une campagne finie (tous s'il y en a moins) ; le taux d'accord (même note) et
chaque désaccord vont au relevé de la campagne, au plan. Trois temps, une commande :

- tirage (`--campagne <id>`) : les cas à revoir de `banc revoir` (banc.revue.en_attente), dans son
  ordre (banc.revue.melanger), avant toute décision de la campagne ; la graine, les 16 premiers
  caractères hexadécimaux du SHA-256 du CSV de la campagne finie : personne ne la choisit, et le
  tirage se refait à l'identique (ceux de en-1 et de fr-controle l'ont été à la promotion des
  scripts du jalon 2) ;
- accord (`--accord "<réponses copiées de la page>"`) : les réponses de Julien contre la
  pré-analyse, dont le SHA-256 se relit (le sceau, annoncé avant ses réponses) ; « je ne sais pas »
  sort le cas de la comparaison ;
- enregistrement (`--enregistrer [<fichier>]`) : les décisions validées, par banc.revue.revoir, cas
  après cas comme au clavier, avec en tête de leurs tables la note qui dit d'où elles viennent.

Pièces, dans logs/revues/<campagne>/ (hors git : elles citent les réponses des agents) :
contre-epreuve.html, la page de Julien (cas numérotés de 1 à 8 : ni cellule, ni passe, ni modèle) ;
tous.txt, tous les cas à revoir (R1…Rn), pour la pré-analyse ; cles.json, à part : les numéros R
des cas de la page, et le cas de chaque R ; preanalyse.json, écrite par Claude sur tous.txt, un
objet par cas : {"cas": "R1", "note": …, "source": …, "motif": …, "raison": …}, ce qui reste à
trancher seulement. Des décisions validées qui s'en écartent vont dans un autre fichier, pour que
la pré-analyse garde son sceau.
"""

import hashlib
import html
import json
import random
import re
import sys
import textwrap
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from banc import mesures, rapport, revue
from banc.mesures import CODE, MesureError
from banc.orchestration import OrchestrationError, lire_campagne
from banc.revue import A_REVOIR, MOTIF_MINIMAL, NOTES, SOURCES, Finale, RevueError, Saisie

MESURES = mesures.MESURES
TRACES = mesures.TRACES
RACINE = Path(__file__).resolve().parents[3]
REVUES = RACINE / "logs" / "revues"
GABARIT = Path(__file__).resolve().parent / "contre-epreuve.html"
NOMBRE = 8
JE_NE_SAIS_PAS = "je ne sais pas"
GENRES = ("note", "source")
# Les lettres de la page : celles de banc revoir, plus x, « je ne sais pas ».
LETTRES = {"note": {**NOTES, "x": JE_NE_SAIS_PAS}, "source": {**SOURCES, "x": JE_NE_SAIS_PAS}}
LIBELLES = {
    "note": {"j": "Juste", "p": "Partiel", "f": "Faux", "x": "Je ne sais pas"},
    "source": {"o": "Oui", "n": "Non", "e": "Exempte", "x": "Je ne sais pas"},
}
CHAMPS = frozenset({"cas", "note", "source", "motif", "raison"})
MARGE_DES_NOTES = 118


class ContreEpreuveError(Exception):
    """Contre-épreuve impossible : campagne pas finie ou déjà revue, tirage absent ou déjà fait,
    réponses ou pré-analyse illisibles, décision qui ne colle pas au cas."""


@dataclass(frozen=True)
class CasTire:
    """Un cas à revoir, dans les clés : de quoi le retrouver, sa réponse courte normalisée, et ce
    qui en reste à trancher."""

    cellule: str
    passe: int
    question: str
    essai: int
    empreinte: str
    besoins: tuple[str, ...]


@dataclass(frozen=True)
class Cles:
    """Les clés d'un tirage (cles.json) : tous les cas à revoir, R1…Rn dans l'ordre de banc revoir,
    et les numéros R des cas de la page, dans son ordre (le cas k est tires[k - 1])."""

    campagne: str
    graine: str
    tires: tuple[str, ...]
    cas: Mapping[str, CasTire]


@dataclass(frozen=True)
class Reponse:
    """Ce que Julien a tranché d'un cas de la page ; None pour ce qui n'était pas à trancher."""

    note: str | None
    source: str | None
    motif: str | None = None


@dataclass(frozen=True)
class Proposition:
    """Ce qu'une pré-analyse (ou une décision validée) tranche d'un cas, avec un motif facultatif
    et une raison d'une ligne."""

    note: str | None = None
    source: str | None = None
    motif: str | None = None
    raison: str = ""

    def __post_init__(self) -> None:
        motif = self.motif
        problemes = {
            "note": self.note is not None and self.note not in NOTES.values(),
            "source": self.source is not None and self.source not in SOURCES.values(),
            "motif": motif is not None
            and not (
                isinstance(motif, str) and CODE.fullmatch(motif) and len(motif) >= MOTIF_MINIMAL
            ),
            "raison": not isinstance(self.raison, str),
        }
        if fautifs := [champ for champ, probleme in problemes.items() if probleme]:
            raise ContreEpreuveError(f"proposition invalide ({', '.join(fautifs)}) : {self}")


@dataclass(frozen=True)
class Desaccord:
    """Un cas de la page que Julien et la pré-analyse ne tranchent pas pareil."""

    numero: int
    question: str
    genre: str
    julien: str
    preanalyse: str
    motif: str
    raison: str


@dataclass(frozen=True)
class Accord:
    """Notes, puis sources : (d'accord, comparées) ; réponses « je ne sais pas », hors de la
    comparaison ; désaccords, dans l'ordre de la page."""

    notes: tuple[int, int]
    sources: tuple[int, int]
    sans_avis: int
    desaccords: tuple[Desaccord, ...]


# --- Tirage --------------------------------------------------------------------------------------


def graine(fichier: Path) -> str:
    """Les 16 premiers caractères hexadécimaux du SHA-256 du CSV de la campagne finie."""
    return hashlib.sha256(fichier.read_bytes()).hexdigest()[:16]


def population(
    lignes: Sequence[Mapping[str, str]], revues: revue.Revues
) -> list[Mapping[str, str]]:
    """Les cas à revoir, dans l'ordre de banc revoir."""
    return revue.melanger(revue.en_attente(lignes, revues))


def tirer[T](cas: Sequence[T], semence: str, nombre: int = NOMBRE) -> list[T]:
    """nombre cas tirés au sort (tous s'il y en a moins), dans l'ordre du tirage."""
    return random.Random(semence).sample(list(cas), min(nombre, len(cas)))


def besoins(ligne: Mapping[str, str], revues: revue.Revues) -> tuple[str, ...]:
    """Ce qui reste à trancher d'un cas : la note, la source, ou les deux ; une note tranchée par
    une décision réutilisée ne se redemande pas (banc revoir fait de même)."""
    etat = revue.finale(ligne, revues)
    valeurs = {"note": etat.note, "source": etat.source}
    return tuple(genre for genre in GENRES if valeurs[genre] == A_REVOIR)


def preparer(campagne: str) -> Cles:
    """Tire les cas de la contre-épreuve d'une campagne finie et écrit ses pièces ; sans cas à
    revoir, n'écrit rien.

    Raises:
        ContreEpreuveError: campagne incomplète, déjà revue en partie, tirage déjà fait, trace
            absente.
    """
    csv = mesures.fichier_mesures(campagne, MESURES)
    lignes = mesures.lire_lignes(csv)
    traces = TRACES / campagne
    if manques := rapport.manques(lire_campagne(traces / "campagne.json"), lignes, traces):
        raise ContreEpreuveError(
            f"campagne {campagne} incomplète ({len(manques)} manque{_s(len(manques))}, voir banc "
            "rapport --complet) : la graine se prend sur le CSV de la campagne finie"
        )
    revues = revue.charger(MESURES / "revues.toml")
    if any(decision.campagne == campagne for decision in revues.decisions):
        raise ContreEpreuveError(
            f"campagne {campagne} déjà revue en partie : la contre-épreuve se tire avant toute "
            "décision (ADR-0014)"
        )
    dossier = REVUES / campagne
    if (dossier / "cles.json").exists():
        raise ContreEpreuveError(
            f"tirage déjà fait ({dossier / 'cles.json'}) : ses numéros lient les réponses de "
            "Julien aux cas"
        )
    cas = population(lignes, revues)
    semence = graine(csv)
    numeros = {revue.cle(ligne): f"R{rang}" for rang, ligne in enumerate(cas, start=1)}
    cles = Cles(
        campagne,
        semence,
        tuple(numeros[revue.cle(ligne)] for ligne in tirer(cas, semence)),
        {numeros[revue.cle(ligne)]: _cas_tire(ligne, revues) for ligne in cas},
    )
    if cas:
        index = revue.traces(traces)
        textes = {numeros[revue.cle(ligne)]: _texte(ligne, index) for ligne in cas}
        _ecrire_pieces(dossier, cles, textes)
    return cles


def lire_cles(dossier: Path) -> Cles:
    """Relit les clés du tirage d'une campagne (dossier : ses pièces)."""
    fichier = dossier / "cles.json"
    try:
        brut = json.loads(fichier.read_text(encoding="utf-8"))
        cas = {
            numero: CasTire(**{**valeurs, "besoins": tuple(valeurs["besoins"])})
            for numero, valeurs in brut["cas"].items()
        }
        return Cles(brut["campagne"], brut["graine"], tuple(brut["tires"]), cas)
    except FileNotFoundError as erreur:
        raise ContreEpreuveError(
            f"aucun tirage ({fichier}) : banc contre-epreuve --campagne <id> d'abord"
        ) from erreur
    except (OSError, ValueError, KeyError, TypeError) as erreur:
        raise ContreEpreuveError(f"{fichier} illisible : {erreur}") from erreur


def _cas_tire(ligne: Mapping[str, str], revues: revue.Revues) -> CasTire:
    _, cellule, passe, question, essai = revue.cle(ligne)
    return CasTire(cellule, passe, question, essai, ligne["empreinte"], besoins(ligne, revues))


def _texte(
    ligne: Mapping[str, str],
    index: Mapping[revue.Cle, tuple[mesures.TourMesure, mesures.TourMesure | None]],
) -> str:
    """Le cas tel que banc revoir le montre : rien de ce qui trahit la cellule."""
    if (cas := revue.cle(ligne)) not in index:
        raise ContreEpreuveError(f"aucune trace pour le cas {cas} (logs/banc/ de ce poste ?)")
    tour, precedent = index[cas]
    return revue.presenter(ligne, tour, precedent, revue.reference(ligne["question"]))


def _ecrire_pieces(dossier: Path, cles: Cles, textes: Mapping[str, str]) -> None:
    """La page et tous.txt, puis les clés : un tirage interrompu avant elles se refait."""
    tous = [
        f"===== {numero} : à trancher, {' et '.join(cas.besoins)} =====\n{textes[numero]}"
        for numero, cas in cles.cas.items()
    ]
    cartes = [
        carte(rang, cles.cas[numero].question, textes[numero], cles.cas[numero].besoins)
        for rang, numero in enumerate(cles.tires, start=1)
    ]
    dossier.mkdir(parents=True, exist_ok=True)
    (dossier / "contre-epreuve.html").write_text(
        page(cles.campagne, cles.graine, cartes), encoding="utf-8"
    )
    (dossier / "tous.txt").write_text("\n\n".join(tous) + "\n", encoding="utf-8")
    (dossier / "cles.json").write_text(
        json.dumps(asdict(cles), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# --- Page à l'aveugle ----------------------------------------------------------------------------


def page(campagne: str, semence: str, cartes: Sequence[str]) -> str:
    """La page de la contre-épreuve : le gabarit du paquet, rempli en une passe (rien de ce qui y
    entre, réponses des agents comprises, ne s'y relit)."""
    valeurs = {
        "CAMPAGNE": campagne,
        "NOMBRE": str(len(cartes)),
        "GRAINE": semence,
        "CARTES": "\n".join(cartes),
    }
    modele = GABARIT.read_text(encoding="utf-8")
    return re.sub(r"\{\{([A-Z]+)\}\}", lambda trouve: valeurs[trouve[1]], modele)


def carte(numero: int, question: str, texte: str, besoins: Sequence[str]) -> str:
    """Un cas de la page : le texte de banc revoir mis en blocs, et de quoi trancher ce qui en
    reste, avec un motif facultatif."""
    corps = "".join(_bloc(titre, contenu) for titre, contenu in _blocs(texte))
    controles = "".join(_choix(numero, genre) for genre in besoins) + _motif(numero)
    return (
        f'<article class="cas" id="cas-{numero}" data-numero="{numero}" '
        f'data-besoins="{",".join(besoins)}">'
        f'<header class="cas-tete"><h2>Cas {numero}<span class="question">'
        f"{html.escape(question)}</span></h2>"
        f'<span class="statut" id="statut-{numero}">à trancher : {" et ".join(besoins)}</span>'
        f"</header>{corps}"
        f'<form class="decision" onsubmit="return false">{controles}</form></article>'
    )


def _blocs(texte: str) -> list[tuple[str, str]]:
    """Les blocs d'un cas de banc revoir : un titre non indenté, puis son contenu indenté (lignes
    vides comprises)."""
    blocs: list[tuple[str, list[str]]] = []
    for ligne in texte.splitlines():
        if ligne and not ligne.startswith(" "):
            blocs.append((ligne, []))
        elif blocs:
            blocs[-1][1].append(ligne)
    return [(titre, "\n".join(contenu).strip("\n")) for titre, contenu in blocs]


def _desindente(contenu: str) -> str:
    lignes = contenu.splitlines()
    marge = min(
        (len(ligne) - len(ligne.lstrip(" ")) for ligne in lignes if ligne.strip()), default=0
    )
    return "\n".join(ligne[marge:] for ligne in lignes)


def _bloc(titre: str, contenu: str) -> str:
    if titre.startswith("Pré-notation :"):
        details = html.escape(titre.removeprefix("Pré-notation :").strip())
        return f'<p class="prenote"><span class="etiquette">Pré-notation</span> {details}</p>'
    nom, _, valeur = titre.partition(" :")
    entete = html.escape(nom.strip())
    if valeur.strip():
        entete += f' <span class="valeur">{html.escape(valeur.strip())}</span>'
    genre = "texte"
    if nom.startswith("Lectures"):
        genre = "lectures"
    elif nom.startswith("Référence"):
        genre = "reference"
    corps = ""
    if contenu.strip():
        corps = f'<pre class="{genre}">{html.escape(_desindente(contenu))}</pre>'
    return f'<section class="bloc"><h3>{entete}</h3>{corps}</section>'


def _choix(numero: int, genre: str) -> str:
    boutons = "".join(
        f'<input type="radio" id="{genre}-{numero}-{code}" name="{genre}-{numero}" '
        f'value="{code}"><label for="{genre}-{numero}-{code}" class="{genre}-{code}">'
        f"{html.escape(libelle)}</label>"
        for code, libelle in LIBELLES[genre].items()
    )
    return (
        f'<fieldset class="choix"><legend>{genre.capitalize()}</legend>'
        f'<div class="segments">{boutons}</div></fieldset>'
    )


def _motif(numero: int) -> str:
    return (
        f'<div class="motif"><label for="motif-{numero}">Motif <span class="aide">(facultatif : '
        f'minuscules, chiffres, tirets)</span></label><input id="motif-{numero}" type="text" '
        f'inputmode="latin" autocomplete="off" spellcheck="false" '
        f'pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="ex. explication-partielle"></div>'
    )


# --- Réponses de Julien, pré-analyse, accord -----------------------------------------------------


def lire_reponses(texte: str, cles: Cles) -> dict[int, Reponse]:
    """Les réponses que la page fait copier, « 1 j | 2 p o motif | 3 x » : numéro du cas, une lettre
    par chose à trancher (note, puis source ; x pour « je ne sais pas »), un motif facultatif ;
    chaque cas de la page une fois."""
    reponses: dict[int, Reponse] = {}
    for segment in filter(None, (morceau.strip() for morceau in texte.split("|"))):
        numero_lu, *mots = segment.split()
        if not numero_lu.isdigit() or not 1 <= int(numero_lu) <= len(cles.tires):
            raise ContreEpreuveError(
                f"cas {numero_lu} inconnu : la page en compte {len(cles.tires)}"
            )
        numero = int(numero_lu)
        if numero in reponses:
            raise ContreEpreuveError(f"cas {numero} : répondu deux fois")
        genres = cles.cas[cles.tires[numero - 1]].besoins
        lettres, reste = mots[: len(genres)], mots[len(genres) :]
        valeurs = [
            LETTRES[genre].get(lettre) for genre, lettre in zip(genres, lettres, strict=False)
        ]
        if (
            len(lettres) < len(genres)
            or None in valeurs
            or len(reste) > 1
            or (reste and not CODE.fullmatch(reste[0]))
        ):
            aide = " puis ".join(f"{genre} {'/'.join(LETTRES[genre])}" for genre in genres)
            raise ContreEpreuveError(
                f"cas {numero} : réponse illisible « {segment} » ({aide}, puis un motif facultatif)"
            )
        tranche = dict(zip(genres, valeurs, strict=True))
        reponses[numero] = Reponse(tranche.get("note"), tranche.get("source"), *reste)
    if manquants := [n for n in range(1, len(cles.tires) + 1) if n not in reponses]:
        raise ContreEpreuveError(
            f"cas sans réponse : {', '.join(map(str, manquants))} (« je ne sais pas » s'écrit x)"
        )
    return reponses


def lire_preanalyse(fichier: Path, cles: Cles) -> dict[str, Proposition]:
    """La pré-analyse (ou des décisions validées) : un objet par cas à revoir, R1…Rn de tous.txt,
    qui tranche tout ce qui en reste à trancher."""
    try:
        brut = json.loads(fichier.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erreur:
        raise ContreEpreuveError(f"{fichier} illisible : {erreur}") from erreur
    if not isinstance(brut, list) or not all(isinstance(objet, dict) for objet in brut):
        raise ContreEpreuveError(f"{fichier} : une liste d'objets attendue, un par cas")
    propositions: dict[str, Proposition] = {}
    for objet in brut:
        if inconnus := sorted(set(objet) - CHAMPS):
            raise ContreEpreuveError(f"{fichier} : champs inconnus {inconnus}")
        numero = objet.get("cas")
        if not isinstance(numero, str) or numero not in cles.cas:
            raise ContreEpreuveError(
                f"{fichier} : cas {numero} inconnu (R1 à R{len(cles.cas)} de tous.txt)"
            )
        if numero in propositions:
            raise ContreEpreuveError(f"{fichier} : cas {numero} deux fois")
        propositions[numero] = Proposition(
            objet.get("note"), objet.get("source"), objet.get("motif"), objet.get("raison", "")
        )
    incomplets = [
        numero
        for numero, cas in cles.cas.items()
        if numero not in propositions
        or any(_valeur(propositions[numero], genre) is None for genre in cas.besoins)
    ]
    if incomplets:
        raise ContreEpreuveError(f"{fichier} : cas non tranchés : {', '.join(incomplets)}")
    return propositions


def accord(
    cles: Cles, reponses: Mapping[int, Reponse], propositions: Mapping[str, Proposition]
) -> Accord:
    """Les réponses de Julien contre la pré-analyse, cas de la page après cas : même note, même
    source ; « je ne sais pas » hors de la comparaison."""
    comptes = {genre: [0, 0] for genre in GENRES}
    sans_avis = 0
    desaccords = []
    for rang, numero in enumerate(cles.tires, start=1):
        cas, proposition = cles.cas[numero], propositions[numero]
        for genre in cas.besoins:
            avis, propose = _valeur(reponses[rang], genre), _valeur(proposition, genre)
            if avis == JE_NE_SAIS_PAS:
                sans_avis += 1
                continue
            comptes[genre][1] += 1
            if avis == propose:
                comptes[genre][0] += 1
            else:
                desaccords.append(
                    Desaccord(
                        rang,
                        cas.question,
                        genre,
                        str(avis),
                        str(propose),
                        proposition.motif or "",
                        proposition.raison,
                    )
                )
    (notes_ok, notes), (sources_ok, sources) = comptes["note"], comptes["source"]
    return Accord((notes_ok, notes), (sources_ok, sources), sans_avis, tuple(desaccords))


def _valeur(tranche: Reponse | Proposition | Finale, genre: str) -> str | None:
    return tranche.note if genre == "note" else tranche.source


# --- Enregistrement des décisions validées -------------------------------------------------------


def _decideur(
    numeros: Mapping[revue.Cle, str],
    propositions: Mapping[str, Proposition],
    avant_la_premiere: Callable[[], None],
) -> revue.Decideur:
    """Les décisions validées, pour banc.revue.revoir : ce qui reste à trancher du cas, rien de
    plus ; ce qu'une décision réutilisée a tranché entre-temps doit être ce qu'elle proposait.
    avant_la_premiere : appelé une fois, juste avant que revoir écrive la première décision."""
    premiere = [True]

    def decider(ligne: Mapping[str, str], etat: Finale) -> Saisie:
        if (numero := numeros.get(revue.cle(ligne))) is None:
            raise ContreEpreuveError(
                f"cas {revue.cle(ligne)} absent du tirage : renoté depuis la contre-épreuve ?"
            )
        proposition, saisie = propositions[numero], dict[str, str | None]()
        for genre in GENRES:
            propose, actuel = _valeur(proposition, genre), _valeur(etat, genre)
            if actuel == A_REVOIR and propose is None:
                raise ContreEpreuveError(
                    f"{numero} ({ligne['question']}) : {genre} à trancher, la décision ne la "
                    "tranche pas"
                )
            if actuel != A_REVOIR and propose not in {None, actuel}:
                raise ContreEpreuveError(
                    f"{numero} ({ligne['question']}) : {genre} {propose} proposée, déjà {actuel}"
                )
            saisie[genre] = propose if actuel == A_REVOIR else None
        if premiere:
            premiere.clear()
            avant_la_premiere()
        tranche = [f"{genre} {valeur}" for genre, valeur in saisie.items() if valeur]
        if proposition.motif:
            tranche.append(f"motif {proposition.motif}")
        print(f"{numero} ({ligne['question']}) : {', '.join(tranche)}")
        return saisie["note"], saisie["source"], proposition.motif

    return decider


def _noter(fichier: Path, cles: Cles, source: Path) -> None:
    """La note en tête des tables de la campagne (ADR-0014) : d'où viennent ses décisions ; le
    fichier se crée avec son en-tête s'il manque."""
    texte = (
        f"Campagne {cles.campagne} ({date.today().isoformat()}) : décisions de Julien, sur la "
        f"pré-analyse de Claude (revue assistée de l'ADR-0014), enregistrées depuis {source.name}. "
        f"Contre-épreuve : {len(cles.tires)} cas sur {len(cles.cas)} tirés au sort (graine "
        f"{cles.graine}) ; relevé au plan (sceau de la pré-analyse, accord, désaccords)."
    )
    note = textwrap.fill(
        texte, MARGE_DES_NOTES, initial_indent="# ", subsequent_indent="# ", break_on_hyphens=False
    )
    fichier.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not fichier.exists()
    with fichier.open("a", encoding="utf-8") as flux:
        if nouveau:
            flux.write(revue.EN_TETE)
        flux.write(f"\n{note}\n")


def _jamais(invite: str) -> str:
    raise ContreEpreuveError(f"saisie au clavier demandée pendant l'enregistrement : {invite}")


# --- Commande ------------------------------------------------------------------------------------


def commande(campagne: str, *, reponses: str | None = None, decisions: str | None = None) -> int:
    """`banc contre-epreuve` : tirage (0, ou 2 en erreur) ; avec reponses, l'accord (0 sans
    désaccord, 1 avec) ; avec decisions (chemin, ou vide pour preanalyse.json), l'enregistrement
    (0 s'il ne reste aucun cas à revoir, 1 sinon)."""
    try:
        if not CODE.fullmatch(campagne):
            raise ContreEpreuveError(
                f"campagne {campagne!r} : un code attendu (minuscules, chiffres, tirets)"
            )
        if reponses is not None:
            return _accord(campagne, reponses)
        if decisions is not None:
            return _enregistrer(campagne, decisions)
        return _tirage(campagne)
    except (ContreEpreuveError, MesureError, OrchestrationError, RevueError) as erreur:
        print(f"banc contre-epreuve : {erreur}", file=sys.stderr)
        return 2


def _tirage(campagne: str) -> int:
    cles = preparer(campagne)
    if not cles.cas:
        print(f"campagne {campagne} : aucun cas à revoir, pas de contre-épreuve")
        return 0
    dossier = REVUES / campagne
    print(
        f"contre-épreuve de {campagne} : {len(cles.tires)} cas tirés sur {len(cles.cas)} à "
        f"revoir ; graine {cles.graine}"
    )
    print(f"  page à l'aveugle, pour Julien : {dossier / 'contre-epreuve.html'}")
    print(
        f"  cas de la pré-analyse (R1 à R{len(cles.cas)}) : {dossier / 'tous.txt'} ; elle va dans "
        f"{dossier / 'preanalyse.json'}, scellée avant les réponses de Julien"
    )
    print(f"  clés, à part : {dossier / 'cles.json'}")
    return 0


def _accord(campagne: str, texte: str) -> int:
    dossier = REVUES / campagne
    cles = lire_cles(dossier)
    fichier = dossier / "preanalyse.json"
    resultat = accord(cles, lire_reponses(texte, cles), lire_preanalyse(fichier, cles))
    sceau = hashlib.sha256(fichier.read_bytes()).hexdigest()
    print(f"pré-analyse : {fichier}, SHA-256 {sceau} (le sceau annoncé avant les réponses)")
    (notes_ok, notes), (sources_ok, sources) = resultat.notes, resultat.sources
    print(
        f"notes : {notes_ok}/{notes} d'accord ; sources : {sources_ok}/{sources} d'accord ; "
        f"« je ne sais pas » : {resultat.sans_avis}"
    )
    for ecart in resultat.desaccords:
        motif = f" ({ecart.motif})" if ecart.motif else ""
        raison = f" : {ecart.raison}" if ecart.raison else ""
        print(
            f"désaccord, cas {ecart.numero} ({ecart.question}) : {ecart.genre} {ecart.julien} pour "
            f"Julien, {ecart.preanalyse} pour la pré-analyse{motif}{raison}"
        )
    return 1 if resultat.desaccords else 0


def _enregistrer(campagne: str, chemin: str) -> int:
    dossier = REVUES / campagne
    cles = lire_cles(dossier)
    # uv lance le banc depuis banc/ : un chemin relatif part de la racine du dépôt ; un chemin
    # absolu reste tel quel.
    fichier = RACINE / chemin if chemin else dossier / "preanalyse.json"
    propositions = lire_preanalyse(fichier, cles)
    lignes = mesures.lire_lignes(mesures.fichier_mesures(campagne, MESURES))
    fichier_revues = MESURES / "revues.toml"
    deja = any(
        decision.campagne == campagne for decision in revue.charger(fichier_revues).decisions
    )

    def noter() -> None:
        # Une seule note par campagne, juste avant sa première décision : un enregistrement repris
        # n'en ajoute pas une seconde, un échec avant toute décision n'en laisse pas d'orpheline.
        if not deja:
            _noter(fichier_revues, cles, fichier)

    numeros = {
        (campagne, cas.cellule, cas.passe, cas.question, cas.essai): numero
        for numero, cas in cles.cas.items()
    }
    sorties: list[str] = []
    decideur = _decideur(numeros, propositions, noter)
    console = revue.Console(_jamais, sorties.append, decideur=decideur)
    revue.revoir(lignes, revue.traces(TRACES / campagne), fichier_revues, console)
    for sortie in [*(s for s in sorties[:-1] if "à compléter à la main" in s), sorties[-1]]:
        print(sortie)
    return revue.verifier(lignes, revue.charger(fichier_revues))


def _s(nombre: int) -> str:
    return "s" if nombre > 1 else ""
