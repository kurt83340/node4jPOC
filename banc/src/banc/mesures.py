"""Traces et mesures d'une conversation (plan 002, T3.1 ; D10 et D13).

Trace : un fichier JSONL par conversation, sous logs/banc/ (ignoré par git), un événement par ligne,
vidé dès son écriture : une conversation tuée garde tout ce qui précède. Temps à l'horloge
monotone, en secondes depuis l'ouverture de la trace. Relue, elle redonne les tours que lit la
notation (banc.trace, inchangé) et leurs mesures. L'identifiant de l'instance n'y entre pas :
scripts/mcp-neo4j.sh le masque à la sortie de neo4j-mcp, avant même l'agent (choix de Julien).

Mesures : une ligne CSV par tour et par essai, pannes comprises, sans prose (nombres et codes,
vérifiés). Coût = tokens × banc/prix.toml, modèle par modèle : les colonnes de tokens portent sur
le modèle de la cellule, cout_usd sur tous les modèles appelés, cout_annexe_usd sur les autres (le
petit modèle de Claude Code ; choix de Julien) ; leur détail reste dans la trace.
"""

import csv
import hashlib
import json
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol, Self, get_args

from banc import attendu
from banc.lecture import mots, prose, sections
from banc.notation import Notation, Note, Source, introspections
from banc.prix import ACCES, Tarif, Usage, tarif
from banc.trace import Appel, Tour

TRACES = Path(__file__).resolve().parents[3] / "logs" / "banc"
MESURES = Path(__file__).resolve().parents[2] / "mesures"
FORMAT = 1
TYPES = frozenset({"conversation", "question", "llm", "appel", "resultat", "reprise", "fin"})
# Issue d'un tour et causes permises (D13) : un échec de l'agent compte faux ; une panne se relance
# (la paire pour Q18 et Q28) ; un plafond de dépense arrête la campagne, ni panne ni échec.
CAUSES: dict[str, frozenset[str | None]] = {
    "reponse": frozenset({None}),
    "echec": frozenset({"delai", "tours", "budget"}),
    "panne": frozenset({"serveur", "api", "reprises"}),
    "arret": frozenset({"plafond"}),
}
NOTES: tuple[str, ...] = get_args(Note.__value__)
SOURCES: tuple[str, ...] = get_args(Source.__value__)
# Codes : campagne, cellule et motifs (minuscules, chiffres, tirets) ; jetons : modèles, effort,
# versions ; puis tout champ du CSV hors ensembles fermés (aucune espace : pas de prose).
CODE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
JETON = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")
CHAMP = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:;=+-]*")
QUESTION = re.compile(r"Q[1-9]\d*")
COMMIT = re.compile(r"[0-9a-f]{40}")
EN_TETE_ATTENDU = re.compile(r"// PokéAPI ([0-9a-f]{40}) · ")
# La notation compare le nom MCP nu (banc.trace) : le client préfixe les siens (mcp__neo4j__…).
PREFIXE_CLIENT = "mcp__"
MICRO = Decimal("0.000001")
COLONNES = (
    "campagne", "cellule", "passe", "question", "essai", "issue", "cause",
    "note", "motifs", "source", "introspections", "rappel", "precision",
    "duree_s", "appels", "reprises",
    "modele", "entree", "sortie", "reflexion", "cache_lecture", "cache_ecriture_5m",
    "cache_ecriture_1h", "cout_usd", "cout_annexe_usd",
    "effort", "versions", "commit_pokeapi", "empreinte",
)  # fmt: skip


class MesureError(Exception):
    """Trace ou mesure impossible : événement hors d'un tour, trace illisible, champ en prose."""


@dataclass(frozen=True)
class Entete:
    """Ce qui identifie une conversation et ce qui la mesure : la première ligne de sa trace."""

    campagne: str
    cellule: str
    passe: int
    essai: int
    # Questions de la conversation, dans l'ordre : une seule, ou une paire (Q2 puis Q18).
    questions: tuple[str, ...]
    # Modèle de la cellule ; tout autre modèle appelé (petit modèle de Claude Code) est annexe.
    modele: str
    # Voie d'accès (banc.prix) et jour : de quoi trouver le tarif.
    acces: str
    jour: date
    # Effort effectif (D2), tel que le client l'annonce.
    effort: str
    versions: Mapping[str, str]
    commit_pokeapi: str

    def __post_init__(self) -> None:
        textes = [*self.versions, *self.versions.values(), self.modele, self.effort]
        problemes = {
            "campagne": not CODE.fullmatch(self.campagne),
            "cellule": not CODE.fullmatch(self.cellule),
            "passe": self.passe < 1,
            "essai": self.essai < 1,
            "questions": not self.questions
            or len(set(self.questions)) != len(self.questions)
            or not all(QUESTION.fullmatch(q) for q in self.questions),
            "acces": self.acces not in ACCES,
            "modele, effort ou versions": not all(JETON.fullmatch(texte) for texte in textes),
            "commit_pokeapi": not COMMIT.fullmatch(self.commit_pokeapi),
        }
        if fautifs := [champ for champ, probleme in problemes.items() if probleme]:
            raise MesureError(f"en-tête de conversation invalide : {', '.join(fautifs)}")


@dataclass(frozen=True)
class TourMesure:
    """Un tour relu dans sa trace : ce que lit la notation, et ses mesures."""

    question: str
    message: str
    appels: tuple[Appel, ...] = ()
    usages: Mapping[str, Usage] = field(default_factory=dict)
    # Tokens de réflexion par modèle, quand le client les donne ; déjà comptés dans la sortie.
    reflexion: Mapping[str, int] = field(default_factory=dict)
    reprises: int = 0
    # Fin du tour ; None tant qu'il n'a pas fini (harnais interrompu).
    issue: str | None = None
    cause: str | None = None
    reponse: str = ""
    duree_s: float | None = None

    def tour(self) -> Tour:
        """Le tour tel que la notation le lit (banc.trace)."""
        return Tour(self.question, self.reponse, self.appels)


@dataclass(frozen=True)
class Conversation:
    """Une trace relue : son en-tête, puis ses tours dans l'ordre."""

    entete: Entete
    tours: tuple[TourMesure, ...]


class Journal:
    """Trace d'une conversation en cours : une ligne JSON par événement, vidée aussitôt écrite.

    Dans chaque tour : la question, les tokens facturés par modèle, les appels d'outils puis leurs
    résultats (appariés par l'identifiant que leur donne le client), les reprises internes du
    client (429, 5xx), et la fin (issue, cause, réponse finale). Une trace n'est jamais écrasée.
    """

    def __init__(
        self, fichier: Path, entete: Entete, horloge: Callable[[], float] = time.monotonic
    ) -> None:
        fichier.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._flux = fichier.open("x", encoding="utf-8", newline="\n")
        except FileExistsError as erreur:
            raise MesureError(f"{fichier} existe déjà : une trace n'est jamais écrasée") from erreur
        self._entete = entete
        self._horloge = horloge
        self._debut = horloge()
        self._posees = 0
        self._en_cours: str | None = None
        self._appels: set[str] = set()
        self._resultats: set[str] = set()
        self._ecrire("conversation", format=FORMAT, **_entete_json(entete))

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exception: object) -> None:
        self._flux.close()

    def question(self, question: str, message: str) -> None:
        """Ouvre un tour : la question, et le message envoyé (préambule de Q2 compris). Les
        questions viennent dans l'ordre de l'en-tête, chacune une fois."""
        attendues = self._entete.questions
        if self._en_cours is not None:
            raise MesureError(f"question {question} : le tour de {self._en_cours} n'a pas fini")
        suivante = attendues[self._posees] if self._posees < len(attendues) else None
        if question != suivante:
            raise MesureError(
                f"question {question} : attendue {suivante} (conversation {attendues})"
            )
        self._posees += 1
        self._en_cours = question
        self._ecrire("question", message=message)

    def llm(
        self,
        modele: str,
        usage: Usage,
        reflexion: int | None = None,
        brut: Mapping[str, Any] | None = None,
    ) -> None:
        """Tokens facturés pour un modèle : un appel, ou le compte du tour quand le client le donne
        d'un bloc. La réflexion, déjà dans la sortie, se note à part quand le client la donne ;
        brut garde l'usage tel que reçu."""
        self._tour("llm")
        champs: dict[str, object] = {"modele": modele, "usage": asdict(usage)}
        if reflexion is not None:
            champs["reflexion"] = reflexion
        if brut is not None:
            champs["brut"] = dict(brut)
        self._ecrire("llm", **champs)

    def appel(
        self,
        ident: str,
        outil: str,
        requete: str = "",
        parametres: Mapping[str, object] | None = None,
    ) -> None:
        """Un appel d'outil, noté dès son envoi : s'il ne revient pas, sa requête reste lisible."""
        self._tour("appel")
        if outil.startswith(PREFIXE_CLIENT):
            raise MesureError(f"outil {outil} : le nom MCP nu est attendu, sans préfixe du client")
        if ident in self._appels:
            raise MesureError(f"appel {ident} déjà noté")
        self._appels.add(ident)
        self._ecrire("appel", id=ident, outil=outil, requete=requete, parametres=parametres or {})

    def resultat(self, ident: str, resultat: str, erreur: bool = False) -> None:
        """Le résultat d'un appel, tel que l'agent l'a reçu ; erreur : isError de MCP."""
        self._tour("resultat")
        if ident not in self._appels:
            raise MesureError(f"résultat sans appel ({ident})")
        if ident in self._resultats:
            raise MesureError(f"résultat de {ident} déjà noté")
        self._resultats.add(ident)
        self._ecrire("resultat", id=ident, resultat=resultat, erreur=erreur)

    def reprise(self, statut: int | None = None) -> None:
        """Une reprise interne du client (429, 5xx…) : D13 la distingue d'un échec de l'agent."""
        self._tour("reprise")
        self._ecrire("reprise", statut=statut)

    def fin(self, issue: str, cause: str | None = None, reponse: str = "") -> None:
        """Ferme le tour : son issue, la cause d'un échec, d'une panne ou d'un arrêt, et la
        réponse finale de l'agent."""
        self._tour("fin")
        _verifier_issue(issue, cause)
        self._ecrire("fin", issue=issue, cause=cause, reponse=reponse)
        self._en_cours = None

    def _tour(self, genre: str) -> None:
        if self._en_cours is None:
            raise MesureError(f"{genre} hors d'un tour : aucune question en cours")

    def _ecrire(self, genre: str, **champs: object) -> None:
        evenement: dict[str, object] = {"type": genre, "t": round(self._horloge() - self._debut, 3)}
        if self._en_cours is not None:
            evenement["question"] = self._en_cours
        try:
            ligne_json = json.dumps(evenement | champs, ensure_ascii=False)
        except (TypeError, ValueError) as erreur:
            raise MesureError(f"{genre} : événement non sérialisable ({erreur})") from erreur
        self._flux.write(ligne_json + "\n")
        self._flux.flush()


def fichier_trace(racine: Path, entete: Entete) -> Path:
    """Trace d'une conversation : <racine>/<campagne>/<cellule>-p<passe>-<questions>-e<essai>.jsonl
    (racine : TRACES pour une campagne)."""
    questions = "+".join(entete.questions)
    nom = f"{entete.cellule}-p{entete.passe}-{questions}-e{entete.essai}.jsonl"
    return racine / entete.campagne / nom


def lire(fichier: Path) -> Conversation:
    """Relit une trace : son en-tête, puis ses tours, chacun avec ses appels et ses mesures."""
    try:
        with fichier.open(encoding="utf-8") as flux:
            lignes = list(flux)
    except OSError as erreur:
        raise MesureError(f"{fichier} illisible : {erreur.strerror}") from erreur
    relecture = _Relecture()
    for numero, texte in enumerate(lignes, start=1):
        try:
            relecture.lire(json.loads(texte))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError, MesureError) as erreur:
            raise MesureError(f"{fichier.name}, ligne {numero} : {erreur}") from erreur
    if relecture.entete is None:
        raise MesureError(f"{fichier.name} : trace vide")
    return Conversation(relecture.entete, tuple(tour.mesure() for tour in relecture.tours))


# --- Tokens par modèle, cache et réflexion -------------------------------------------------------


class UsageGenai(Protocol):
    """Usage d'une réponse d'ADK (GenerateContentResponseUsageMetadata de google-genai), pour
    Claude comme pour Gemini."""

    @property
    def prompt_token_count(self) -> int | None: ...
    @property
    def cached_content_token_count(self) -> int | None: ...
    @property
    def candidates_token_count(self) -> int | None: ...
    @property
    def thoughts_token_count(self) -> int | None: ...


def usage_anthropic(brut: Mapping[str, Any]) -> Usage:
    """Tokens d'un usage de l'API Anthropic (anthropic 1.11.0, types/usage.py), tel que Claude Code
    le joint aux messages de l'assistant : écriture en cache par durée quand cache_creation la
    détaille, sinon à 5 min ; output_tokens comprend la réflexion et fait foi pour la facture."""
    detail = brut.get("cache_creation") or {}
    une_heure: int = detail.get("ephemeral_1h_input_tokens") or 0
    ecrit: int = brut.get("cache_creation_input_tokens") or 0
    if une_heure > ecrit:
        raise MesureError(f"écriture en cache : {une_heure} tokens à 1 h sur {ecrit} écrits")
    return Usage(
        entree=brut.get("input_tokens") or 0,
        sortie=brut.get("output_tokens") or 0,
        cache_ecriture_5m=ecrit - une_heure,
        cache_ecriture_1h=une_heure,
        cache_lecture=brut.get("cache_read_input_tokens") or 0,
    )


def reflexion_anthropic(brut: Mapping[str, Any]) -> int | None:
    """Tokens de réflexion d'un usage de l'API Anthropic (output_tokens_details), s'il les donne."""
    detail = brut.get("output_tokens_details") or {}
    reflexion: int | None = detail.get("thinking_tokens")
    return reflexion


def usage_claude_code(
    model_usage: Mapping[str, Mapping[str, Any]], ecritures_1h: Mapping[str, int] | None = None
) -> dict[str, Usage]:
    """Tokens par modèle d'un ResultMessage de Claude Code (SDK 0.2.164, ModelUsage), petit modèle
    compris. ModelUsage ne sépare pas l'écriture à 1 h : sa part, tirée des messages de
    l'assistant (usage_anthropic), vient d'ecritures_1h ; le reste compte à 5 min."""
    parts = dict(ecritures_1h or {})
    if inconnus := sorted(set(parts) - set(model_usage)):
        raise MesureError(f"écriture à 1 h pour un modèle sans usage : {inconnus}")
    usages = {}
    for modele, compte in model_usage.items():
        ecrit = compte.get("cacheCreationInputTokens", 0)
        une_heure = parts.get(modele, 0)
        if une_heure > ecrit:
            raise MesureError(f"{modele} : {une_heure} tokens écrits à 1 h sur {ecrit}")
        usages[modele] = Usage(
            entree=compte.get("inputTokens", 0),
            sortie=compte.get("outputTokens", 0),
            cache_ecriture_5m=ecrit - une_heure,
            cache_ecriture_1h=une_heure,
            cache_lecture=compte.get("cacheReadInputTokens", 0),
        )
    return usages


def usage_adk(meta: UsageGenai, *, cache_1h: bool = False) -> Usage:
    """Tokens d'une réponse d'ADK (2.11.0, models/anthropic_llm.py) : l'entrée comprend le cache
    lu et écrit, la sortie exclut la réflexion. ADK ne détaille pas la durée de l'écriture : la
    cellule la connaît (ContextCacheConfig, 1 h dès 3 600 s)."""
    lu = meta.cached_content_token_count or 0
    ecrit: int = getattr(meta, "cache_creation_input_tokens", None) or 0
    return Usage(
        entree=(meta.prompt_token_count or 0) - lu - ecrit,
        sortie=(meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0),
        cache_ecriture_5m=0 if cache_1h else ecrit,
        cache_ecriture_1h=ecrit if cache_1h else 0,
        cache_lecture=lu,
    )


def couts(
    usages: Mapping[str, Usage], tarifs: Sequence[Tarif], jour: date, acces: str
) -> dict[str, Decimal]:
    """Coût de chaque modèle, à son tarif du jour par cette voie ; un modèle sans tarif lève
    PrixError : une mesure n'a pas de trou."""
    return {
        modele: tarif(list(tarifs), modele, jour, acces).cout(usage)
        for modele, usage in usages.items()
    }


# --- Ligne et fichier CSV ------------------------------------------------------------------------


def ligne(
    entete: Entete, tour: TourMesure, notation: Notation | None, tarifs: Sequence[Tarif]
) -> dict[str, str]:
    """Ligne CSV d'un tour (COLONNES, dans l'ordre), sans prose.

    Une réponse se note : notation exigée, sur ce tour (mêmes introspections que la trace). Un
    échec de l'agent compte faux, avec sa cause (D13). Une panne ou un arrêt n'ont pas de note :
    le tour sera relancé ou rejoué.
    """
    if tour.issue is None or tour.duree_s is None:
        raise MesureError(f"{tour.question} : tour inachevé, rien à mesurer")
    compte = introspections(tour.tour())
    note, source = "", ""
    motifs: tuple[str, ...] = ()
    rappel = precision = None
    if tour.issue == "reponse":
        if notation is None:
            raise MesureError(f"{tour.question} : réponse sans notation")
        if notation.introspections != compte:
            raise MesureError(
                f"{tour.question} : {notation.introspections} introspections notées, {compte} "
                "dans la trace (notation d'un autre tour ?)"
            )
        note, motifs, source = notation.note, notation.motifs, notation.source
        rappel, precision = notation.rappel, notation.precision
    elif notation is not None:
        raise MesureError(f"{tour.question} ({tour.issue}) : pas de notation sans réponse")
    elif tour.issue == "echec":
        note, source = "faux", "non"
    principal = tour.usages.get(entete.modele, Usage())
    par_modele = couts(tour.usages, tarifs, entete.jour, entete.acces)
    annexe = (cout for modele, cout in par_modele.items() if modele != entete.modele)
    reflexion = tour.reflexion.get(entete.modele)
    for motif in motifs:
        if not CODE.fullmatch(motif):
            raise MesureError(f"motif {motif!r} : un code attendu (CSV sans prose)")
    valeurs = {
        "campagne": entete.campagne,
        "cellule": entete.cellule,
        "passe": str(entete.passe),
        "question": tour.question,
        "essai": str(entete.essai),
        "issue": tour.issue,
        "cause": tour.cause or "",
        "note": note,
        "motifs": "+".join(motifs),
        "source": source,
        "introspections": str(compte),
        "rappel": _decimales(rappel, 3),
        "precision": _decimales(precision, 3),
        "duree_s": _decimales(tour.duree_s, 2),
        "appels": str(len(tour.appels)),
        "reprises": str(tour.reprises),
        "modele": entete.modele,
        "entree": str(principal.entree),
        "sortie": str(principal.sortie),
        "reflexion": "" if reflexion is None else str(reflexion),
        "cache_lecture": str(principal.cache_lecture),
        "cache_ecriture_5m": str(principal.cache_ecriture_5m),
        "cache_ecriture_1h": str(principal.cache_ecriture_1h),
        "cout_usd": _dollars(sum(par_modele.values(), Decimal(0))),
        "cout_annexe_usd": _dollars(sum(annexe, Decimal(0))),
        "effort": entete.effort,
        "versions": ";".join(f"{nom}={v}" for nom, v in sorted(entete.versions.items())),
        "commit_pokeapi": entete.commit_pokeapi,
        "empreinte": empreinte(tour.reponse) if tour.issue == "reponse" else "",
    }
    _sans_prose(valeurs)
    return valeurs


def empreinte(reponse: str) -> str:
    """Empreinte de la réponse courte normalisée : section « Réponse », code retiré, casse,
    accents et ponctuation ignorés. Vide sans réponse courte. La revue (T3.2) réutilise une
    décision par réponse courte normalisée."""
    courte = sections(reponse).reponse
    normale = " ".join(mots(prose(courte))) if courte else ""
    return hashlib.sha256(normale.encode()).hexdigest()[:16] if normale else ""


def ecrire(fichier: Path, lignes: Iterable[Mapping[str, str]]) -> None:
    """Ajoute des lignes au CSV d'une campagne ; l'en-tête s'écrit à la création. Un fichier ou une
    ligne aux colonnes différentes sont refusés, avant toute écriture : jamais deux formats dans
    un même fichier."""
    lignes = list(lignes)
    for valeurs in lignes:
        if set(valeurs) != set(COLONNES):
            raise MesureError(f"ligne aux colonnes {list(valeurs)}, attendu {list(COLONNES)}")
    nouveau = not fichier.exists()
    if not nouveau:
        with fichier.open(encoding="utf-8", newline="") as flux:
            colonnes = next(csv.reader(flux), [])
        if tuple(colonnes) != COLONNES:
            raise MesureError(f"{fichier} : colonnes {colonnes}, attendu {list(COLONNES)}")
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with fichier.open("a", encoding="utf-8", newline="") as flux:
        redacteur = csv.DictWriter(flux, fieldnames=COLONNES, lineterminator="\n")
        if nouveau:
            redacteur.writeheader()
        redacteur.writerows(lignes)


def fichier_mesures(campagne: str, dossier: Path = MESURES) -> Path:
    """CSV d'une campagne : <dossier>/<campagne>.csv (dossier : MESURES, versionné)."""
    if not CODE.fullmatch(campagne):
        raise MesureError(f"campagne {campagne!r} : un code attendu (minuscules, chiffres, tirets)")
    return dossier / f"{campagne}.csv"


def lire_lignes(fichier: Path) -> list[dict[str, str]]:
    """Relit le CSV d'une campagne ; un fichier d'un autre format est refusé."""
    try:
        with fichier.open(encoding="utf-8", newline="") as flux:
            lecteur = csv.DictReader(flux)
            if tuple(lecteur.fieldnames or ()) != COLONNES:
                colonnes = list(lecteur.fieldnames or ())
                raise MesureError(f"{fichier} : colonnes {colonnes}, attendu {list(COLONNES)}")
            return [dict(valeurs) for valeurs in lecteur]
    except OSError as erreur:
        raise MesureError(f"{fichier} illisible : {erreur.strerror}") from erreur


def commit_pokeapi(dossier: Path = attendu.DOSSIER) -> str:
    """Commit PokéAPI des réponses de référence (ADR-0001), lu dans leur en-tête : un seul, sinon
    elles ne viennent pas des mêmes données."""
    commits = set()
    for fichier in sorted(dossier.glob("*.txt")):
        premiere = fichier.read_text(encoding="utf-8").partition("\n")[0]
        if (trouve := EN_TETE_ATTENDU.match(premiere)) is None:
            raise MesureError(f"{fichier.name} : en-tête « // PokéAPI <commit> · … » attendu")
        commits.add(trouve[1])
    if len(commits) != 1:
        raise MesureError(f"réponses de référence : {len(commits)} commits PokéAPI {commits}")
    return commits.pop()


# --- Relecture -----------------------------------------------------------------------------------


@dataclass
class _Tour:
    """Un tour en cours de relecture."""

    question: str
    message: str
    debut: float
    appels: dict[str, tuple[str, str, dict[str, object]]] = field(default_factory=dict)
    resultats: dict[str, tuple[str, bool]] = field(default_factory=dict)
    usages: dict[str, Usage] = field(default_factory=dict)
    reflexion: dict[str, int] = field(default_factory=dict)
    reprises: int = 0
    fin: tuple[float, str, str | None, str] | None = None

    def mesure(self) -> TourMesure:
        # Un appel resté sans résultat (agent tué pendant la lecture) compte en échec.
        appels = tuple(
            Appel(outil, requete, parametres, *self.resultats.get(ident, ("", True)))
            for ident, (outil, requete, parametres) in self.appels.items()
        )
        mesure = TourMesure(
            self.question, self.message, appels, self.usages, self.reflexion, self.reprises
        )
        if self.fin is None:
            return mesure
        t, issue, cause, reponse = self.fin
        duree = round(t - self.debut, 3)
        return replace(mesure, issue=issue, cause=cause, reponse=reponse, duree_s=duree)


class _Relecture:
    """Relecture d'une trace, événement par événement, avec les règles de son écriture."""

    def __init__(self) -> None:
        self.entete: Entete | None = None
        self.tours: list[_Tour] = []

    def lire(self, evenement: dict[str, Any]) -> None:
        genre, t = evenement["type"], float(evenement["t"])
        if genre not in TYPES:
            raise MesureError(f"événement {genre!r} inconnu")
        if genre == "conversation":
            if self.entete is not None or evenement["format"] != FORMAT:
                raise MesureError(f"en-tête en double ou format inconnu ({evenement['format']})")
            self.entete = _entete_lu(evenement)
            return
        if self.entete is None:
            raise MesureError("en-tête de conversation attendu en première ligne")
        if genre == "question":
            if self.tours and self.tours[-1].fin is None:
                raise MesureError(f"question {evenement['question']} : tour précédent pas fini")
            self.tours.append(_Tour(evenement["question"], evenement["message"], t))
            return
        if not self.tours or self.tours[-1].fin is not None:
            raise MesureError(f"{genre} hors d'un tour")
        tour = self.tours[-1]
        if evenement["question"] != tour.question:
            raise MesureError(f"{genre} de {evenement['question']} dans le tour de {tour.question}")
        self._dans_le_tour(tour, genre, t, evenement)

    @staticmethod
    def _dans_le_tour(tour: _Tour, genre: str, t: float, evenement: dict[str, Any]) -> None:
        match genre:
            case "llm":
                modele = evenement["modele"]
                tour.usages[modele] = tour.usages.get(modele, Usage()) + Usage(**evenement["usage"])
                if "reflexion" in evenement:
                    tour.reflexion[modele] = tour.reflexion.get(modele, 0) + evenement["reflexion"]
            case "appel":
                if evenement["id"] in tour.appels:
                    raise MesureError(f"appel {evenement['id']} déjà noté")
                appel = (evenement["outil"], evenement["requete"], evenement["parametres"])
                tour.appels[evenement["id"]] = appel
            case "resultat":
                if evenement["id"] not in tour.appels or evenement["id"] in tour.resultats:
                    raise MesureError(f"résultat sans appel, ou en double ({evenement['id']})")
                tour.resultats[evenement["id"]] = (evenement["resultat"], evenement["erreur"])
            case "reprise":
                tour.reprises += 1
            case _:
                _verifier_issue(evenement["issue"], evenement["cause"])
                tour.fin = (t, evenement["issue"], evenement["cause"], evenement["reponse"])


def _verifier_issue(issue: str, cause: str | None) -> None:
    if cause not in CAUSES.get(issue, frozenset()):
        raise MesureError(f"issue {issue!r} et cause {cause!r} : hors de {CAUSES}")


def _entete_json(entete: Entete) -> dict[str, object]:
    champs = asdict(entete)
    return champs | {
        "questions": list(entete.questions),
        "jour": entete.jour.isoformat(),
        "versions": dict(sorted(entete.versions.items())),
    }


def _entete_lu(evenement: Mapping[str, Any]) -> Entete:
    return Entete(
        campagne=evenement["campagne"],
        cellule=evenement["cellule"],
        passe=evenement["passe"],
        essai=evenement["essai"],
        questions=tuple(evenement["questions"]),
        modele=evenement["modele"],
        acces=evenement["acces"],
        jour=date.fromisoformat(evenement["jour"]),
        effort=evenement["effort"],
        versions=dict(evenement["versions"]),
        commit_pokeapi=evenement["commit_pokeapi"],
    )


def _sans_prose(valeurs: Mapping[str, str]) -> None:
    """Chaque champ est vide, une valeur d'un ensemble fermé, ou un jeton sans espace."""
    fermes = {
        "issue": set(CAUSES),
        "cause": {c for causes in CAUSES.values() for c in causes if c},
        "note": set(NOTES),
        "source": set(SOURCES),
    }
    for colonne, valeur in valeurs.items():
        permis = valeur in fermes[colonne] if colonne in fermes else CHAMP.fullmatch(valeur)
        if valeur and not permis:
            raise MesureError(f"{colonne} : {valeur!r} n'est pas un code (CSV sans prose)")


def _decimales(valeur: float | None, decimales: int) -> str:
    return "" if valeur is None else f"{valeur:.{decimales}f}"


def _dollars(montant: Decimal) -> str:
    return f"{montant.quantize(MICRO):f}"
