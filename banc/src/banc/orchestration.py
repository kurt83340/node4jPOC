"""Orchestration d'une campagne (plan 002, T4.3 ; D7, D13 ; ADR-0009, ADR-0012) : `banc lancer`.

Une campagne : ses passes, et dans chaque passe chaque conversation (une question, ou la paire Q2
puis Q18, Q27 puis Q28) posée à chaque cellule. Les cellules alternent question par question, dans
un ordre qui tourne d'un cran à chaque conversation et à chaque passe (choix de Julien) : aucune
n'est toujours la première sur un cache d'Aura froid. Les paramètres d'une campagne sont fixés à sa
création (campagne.json, près de ses traces) ; --reprendre les relit.

Une campagne mesure une seule technique : la technique 2, des agents qui interrogent la base par
l'outil read-cypher (claude-code, adk-claude, adk-gemini, les cellules par défaut), ou la
technique 3, des cellules GraphRAG sans outil (graphrag-claude, graphrag-gemini ; spec 003). Une
campagne GraphRAG encode ses messages à sa création (banc.encodage, encodages.json près de ses
traces), avant toute écriture, et chaque cellule reçoit les vecteurs de ses questions ; la reprise
les relit sans réencoder. L'empreinte de sa requête de recherche est gelée avec celle du prompt.

Une conversation : un processus de cellule (banc.cellule_sdk, banc.cellule_adk,
banc.cellule_graphrag) dans sa propre session, la liste blanche pour seul environnement
(banc.isolement), un HOME, une configuration de Claude Code et un dossier de travail neufs, hors
du dépôt, détruits ensuite. La cellule tient elle-même ses plafonds et écrit sa trace ;
l'orchestration la relit, note ses réponses (banc.notation) et en ajoute toutes les lignes d'un
coup au CSV de la campagne (banc.mesures).
Puis, selon les issues (D13) :
- panne : la conversation (la paire) est rejouée aussitôt, à l'essai suivant ; 3 de suite arrêtent
  la campagne (circuit breaker du plan) ; plus de 2 dans une série (une cellule, une passe) la
  rendent invalide : signalé, sans arrêt (choix de Julien : le rapport tranche) ;
- échec du premier tour d'une paire : le second compte faux sans être posé, une ligne « echec » de
  cause « precedent », à 0 s, sans tokens (ADR-0012) ;
- crédits épuisés, ou plafond de dépense de la campagne : arrêt, puis --reprendre après décision.
Une erreur technique d'une cellule, ou une cellule qui dépasse ses plafonds d'une marge (tuée :
SIGTERM à son groupe, puis SIGKILL), arrête la campagne (choix de Julien).

Reprise : une trace complète restée sans ligne (harnais arrêté après la sortie de sa cellule :
nettoyage ou contrôle de Q2 en échec, Ctrl-C, cellule en erreur après son dernier tour) est notée,
jamais rejouée, car un échec ne se rejoue pas (ADR-0009), puis suit les règles d'un essai qu'on
vient de mener (arrêt sur crédits épuisés, panne comptée). Seule une trace inachevée (coupée en
plein tour ou entre deux tours) se rejoue, à l'essai suivant : une trace n'est jamais écrasée. Une
trace où un tour suit un tour sans réponse vient d'une cellule fautive : erreur, jusqu'à ce que la
trace soit écartée (renommée en .jsonl.ecartee), après correction de la cellule.

Une conversation qui ne finit pas proprement (un tour sans réponse, une cellule tuée ou en erreur)
fait arrêter sur Aura les lectures des agents restées actives (scripts/transactions.sh), après la
sortie de la cellule et avant toute autre lecture : la durée, fixée par la cellule à l'échéance,
n'en compte rien. Chaque lancement commence aussi par là : une campagne interrompue a pu en
laisser. Une seule campagne à la fois sur le poste (verrou) : elles partagent l'instance Aura.

Répétition générale (--faux-serveur, T5.1) : les vrais LLM, mais un faux serveur MCP
(banc.faux_serveur) qui rend un résultat neutre à chaque appel ; contrôle de Q2 simulé, aucun
nettoyage, ni gcloud ni neo4j-mcp dans le PATH des agents : rien ne touche Aura. La paire Q2 → Q18
de la cellule adk-gemini a un serveur lent, au-delà du délai d'une question : Q2 échoue (délai),
Q18 compte faux d'office (ADR-0012).

Codes retour : 0 campagne finie · 1 finie, avec une passe invalide · 2 erreur technique · 3 arrêt
sur un plafond de dépense, à reprendre après décision · 130 interrompue (Ctrl-C, SIGTERM, SIGHUP ;
SIGHUP reste ignoré sous nohup).

Limites connues (revue adverse) : un harnais tué par SIGKILL laisse sa cellule, dans sa propre
session, finir seule sa conversation, et le verrou tombe avec lui ; un descendant lancé dans sa
propre session qui survivrait à la sortie normale de sa cellule n'est pas balayé (le serveur MCP
d'ADK est arrêté par sa cellule ; neo4j-mcp sort à la fin de son appel, stdin fermé).
"""

import contextlib
import fcntl
import functools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from decimal import Decimal, InvalidOperation
from glob import escape
from pathlib import Path
from types import FrameType

from banc import anglais, prix
from banc import questions as banc_questions
from banc.attendu import AttenduError
from banc.cellule import (
    EMPREINTE,
    FICHES,
    LANCEUR,
    RACINE,
    RECHERCHE,
    Commande,
    Plafonds,
    commande_json,
    empreinte_prompt,
    empreinte_recherche,
)
from banc.correspondance import CorrespondanceError
from banc.encodage import (
    Encodage,
    EncodageError,
    ecrire_les_encodages,
    encoder_les_messages,
    encodeur_vertex,
    relire_les_encodages,
)
from banc.isolement import CleAbsente, cle_anthropic, environnement_agent
from banc.lecture import LectureError
from banc.mesures import (
    CODE,
    MESURES,
    TRACES,
    Conversation,
    MesureError,
    TourMesure,
    couts,
    ecrire,
    fichier_mesures,
    ligne,
    lire,
    lire_lignes,
    nom_de_trace,
)
from banc.notation import (
    Controleur,
    NotationError,
    Referentiel,
    controle_par_script,
    controle_simule,
    noter,
)
from banc.prix import PrixError
from banc.questions import Banc, BancError, Question
from banc.traduction import TraductionError

# Les cellules du banc : la technique 2 (jalon 2), puis la technique 3, GraphRAG (spec 003, D7).
CELLULES = ("claude-code", "adk-claude", "adk-gemini", "graphrag-claude", "graphrag-gemini")
# Une campagne sans --cellules : la technique 2, comme au jalon 2 (choix de Claude, T12.1).
PAR_DEFAUT = ("claude-code", "adk-claude", "adk-gemini")
# Chaque cellule lit sa commande sur stdin (banc.cellule).
PROGRAMMES: Mapping[str, tuple[str, ...]] = {
    "claude-code": (sys.executable, "-m", "banc.cellule_sdk"),
    "adk-claude": (sys.executable, "-m", "banc.cellule_adk", "adk-claude"),
    "adk-gemini": (sys.executable, "-m", "banc.cellule_adk", "adk-gemini"),
    "graphrag-claude": (sys.executable, "-m", "banc.cellule_graphrag", "graphrag-claude"),
    "graphrag-gemini": (sys.executable, "-m", "banc.cellule_graphrag", "graphrag-gemini"),
}
# La consigne de chaque cellule (ADR-0018, banc.cellule.CONSIGNES) : un agent qui interroge la base
# par l'outil read-cypher, ou un LLM sans outil qui reçoit le contexte d'une recherche. Une campagne
# mesure une seule technique, donc une seule consigne.
CONSIGNE_DE: Mapping[str, str] = {
    "claude-code": "outil",
    "adk-claude": "outil",
    "adk-gemini": "outil",
    "graphrag-claude": "contexte",
    "graphrag-gemini": "contexte",
}
# Cellules qui paient par la clé Anthropic (ADR-0011).
CLAUDE = frozenset({"claude-code", "adk-claude", "graphrag-claude"})
# neo4j-mcp v1.6.0, seul dans son dossier (T0.3) ; gcloud, absent du PATH des shells non
# interactifs (scripts/commun.sh).
NEO4J_MCP = Path.home() / ".local" / "share" / "neo4j-mcp" / "v1.6.0"
GCLOUD = Path.home() / "google-cloud-sdk" / "bin" / "gcloud"
TRANSACTIONS = RACINE / "scripts" / "transactions.sh"
# Langue du schéma de la base, en lecture seule (--langue, T10.0).
CHARGER = RACINE / "scripts" / "charger.sh"
PARAMETRES = "campagne.json"
# Les messages d'une campagne GraphRAG, encodés à sa création (banc.encodage, D5).
ENCODAGES = "encodages.json"
# 2 : le mode faux serveur (T5.1) entre dans les paramètres d'une campagne ; 3 : la langue du schéma
# et l'empreinte du prompt (T10.0) ; 4 : l'empreinte de la requête de recherche (spec 003, T12.1).
# Les formats 2 et 3 se relisent encore : la technique 2, en français pour le format 2.
FORMAT = 4
FORMATS_LUS = (2, 3, 4)
# Répétition générale (T5.1) : faux serveur MCP, lancé par chaque client comme le lanceur.
FAUX_SERVEUR = (sys.executable, "-I", "-m", "banc.faux_serveur")
# La conversation au faux serveur lent : sa cellule et son premier tour. adk-gemini, la moins
# chère ; chaque appel d'outil y attend le délai d'une question et LENTEUR_S de plus.
LENTE = ("adk-gemini", "Q2")
LENTEUR_S = 60.0
# Cause du second tour d'une paire dont le premier a échoué (ADR-0012, banc.mesures.CAUSES).
PRECEDENT = "precedent"
# Circuit breaker du plan : 3 pannes de suite sur une même conversation arrêtent la campagne.
PANNES_DE_SUITE = 3
# Plus de 2 pannes dans une série (une cellule, une passe) : passe invalide (plan, D13).
PANNES_PAR_SERIE = 2
# Réserve du plafond avant chaque conversation, en budgets d'une conversation : le sien, et autant
# de marge, car une cellule ne voit le coût d'un appel du modèle qu'à sa fin, et un appel peut
# franchir le budget de tout son coût (plan, D13).
RESERVE_EN_BUDGETS = 2
# Au-delà des plafonds de la cellule : démarrage, jeton de Vertex, arrêt.
MARGE_S = 60.0
# Entre SIGTERM et SIGKILL : la cellule ADK arrête son serveur MCP, puis sort en 143.
GRACE_S = 10.0
NETTOYAGE_S = 120.0
FINIE, INVALIDE, ERREUR, PLAFOND = 0, 1, 2, 3
INTERROMPUE = 128 + signal.SIGINT
# Fin du nom d'une trace : son essai, puis .jsonl, ou .jsonl.ecartee pour une trace écartée.
FIN_DE_TRACE = re.compile(r"([0-9]+)\.jsonl(?:\.ecartee)?")


class OrchestrationError(Exception):
    """Erreur technique : la campagne s'arrête (cellule en erreur ou tuée, trace incohérente…)."""


class ArretPlafond(Exception):
    """Plafond de dépense atteint (crédits Anthropic épuisés, plafond de la campagne) : arrêt, puis
    --reprendre après décision (D13)."""


@dataclass(frozen=True)
class Etape:
    """Une conversation d'une cellule dans une passe."""

    passe: int
    cellule: str
    questions: tuple[str, ...]

    def __str__(self) -> str:
        return f"passe {self.passe} · {'+'.join(self.questions)} · {self.cellule}"


@dataclass(frozen=True)
class Campagne:
    """Paramètres d'une campagne, fixés à sa création (campagne.json) : --reprendre les relit."""

    nom: str
    passes: int
    # Conversations dans l'ordre : une question, ou une paire (Q2 puis Q18).
    conversations: tuple[tuple[str, ...], ...]
    cellules: tuple[str, ...] = PAR_DEFAUT
    # Cache d'une heure des cellules Claude, au lieu de 5 min (D10 : tranché au pilote).
    cache_1h: bool = False
    plafonds: Plafonds = field(default_factory=Plafonds)
    # Répétition générale (T5.1) : faux serveur MCP, rien ne touche Aura.
    faux_serveur: bool = False
    # Langue du schéma de la base (D8) : la fiche du prompt, et la requête du contrôle de Q2.
    schema: str = "fr"
    # SHA-256 du prompt (consigne de la technique et fiche) à la création (T10.0) : un prompt
    # modifié depuis arrête la campagne (protocole gelé, D7). None : campagne d'avant T10.0
    # (format 2), non vérifiée.
    empreinte_prompt: str | None = None
    # SHA-256 de la requête de recherche d'une campagne GraphRAG à sa création (spec 003, T12.1),
    # gelée comme le prompt ; aucun pour la technique 2.
    empreinte_recherche: str | None = None

    def __post_init__(self) -> None:
        questions = [question for conversation in self.conversations for question in conversation]
        consignes = {CONSIGNE_DE.get(cellule) for cellule in self.cellules}
        problemes = {
            "nom": not CODE.fullmatch(self.nom),
            "passes": self.passes < 1,
            "conversations": not all(self.conversations)
            or not questions
            or len(set(questions)) != len(questions),
            "cellules": not self.cellules
            or len(set(self.cellules)) != len(self.cellules)
            or not set(self.cellules) <= set(CELLULES),
            "schema": self.schema not in FICHES,
            "empreinte_prompt": self.empreinte_prompt is not None
            and not EMPREINTE.fullmatch(self.empreinte_prompt),
            "empreinte_recherche": self.empreinte_recherche is not None
            and (not EMPREINTE.fullmatch(self.empreinte_recherche) or "contexte" not in consignes),
        }
        if fautifs := [champ for champ, probleme in problemes.items() if probleme]:
            raise OrchestrationError(f"campagne invalide ({', '.join(fautifs)}) : {self}")
        if len(consignes) > 1:
            raise OrchestrationError(
                f"cellules {', '.join(self.cellules)} : une campagne mesure une seule technique, "
                "avec l'outil read-cypher ou sans outil (ADR-0018)"
            )

    @property
    def consigne(self) -> str:
        """La consigne de ses cellules : « outil » (technique 2) ou « contexte » (GraphRAG)."""
        return CONSIGNE_DE[self.cellules[0]]

    def etapes(self) -> list[Etape]:
        """Le plan : passe après passe, conversation après conversation, chaque cellule une fois,
        dans un ordre qui tourne d'un cran à chaque conversation et à chaque passe."""
        return [
            Etape(passe, cellule, questions)
            for passe in range(1, self.passes + 1)
            for rang, questions in enumerate(self.conversations)
            for cellule in _tourner(self.cellules, rang + passe - 1)
        ]


def _tourner(cellules: tuple[str, ...], crans: int) -> tuple[str, ...]:
    debut = crans % len(cellules)
    return cellules[debut:] + cellules[:debut]


@dataclass(frozen=True)
class Demande:
    """Ce que `banc lancer` reçoit de la ligne de commande ; None ou vide : non précisé."""

    nom: str
    plafond_usd: Decimal
    reprendre: bool = False
    passes: int | None = None
    questions: tuple[str, ...] = ()
    cellules: tuple[str, ...] = ()
    cache_1h: bool | None = None
    # Répétition générale (T5.1) : à redonner à la reprise, qui le vérifie.
    faux_serveur: bool = False
    # Langue du schéma (D8 ; défaut : fr).
    schema: str | None = None


def conversations(banc: Banc, demandees: Sequence[str] = ()) -> tuple[tuple[str, ...], ...]:
    """Les conversations à mener, dans l'ordre : les questions demandées (à défaut, toutes, par
    numéro), chaque second tour dans la conversation de son tour précédent (Q18 après Q2).

    Raises:
        OrchestrationError: question inconnue ou en double, second tour sans son tour précédent.
    """
    ids = list(demandees) or sorted(banc.questions, key=lambda ident: int(ident[1:]))
    if inconnues := [ident for ident in ids if ident not in banc.questions]:
        raise OrchestrationError(f"questions inconnues : {', '.join(inconnues)}")
    if len(set(ids)) != len(ids):
        raise OrchestrationError(f"question en double : {', '.join(ids)}")
    seconds = {q.tour_precedent: q.id for q in banc.questions.values() if q.tour_precedent}
    resultat: list[tuple[str, ...]] = []
    for ident in ids:
        precedent = banc.questions[ident].tour_precedent
        if precedent is not None:
            if precedent not in ids:
                raise OrchestrationError(
                    f"{ident} se pose au second tour, après {precedent} : demander aussi "
                    f"{precedent}"
                )
            continue
        second = seconds.get(ident)
        resultat.append((ident, second) if second is not None and second in ids else (ident,))
    return tuple(resultat)


def message(question: Question) -> str:
    """Le message posé : la question, précédée de son préambule (l'équipe de Q2, D6)."""
    if question.preambule is None:
        return question.texte
    return f"{question.preambule}\n\n{question.texte}"


def ecrire_campagne(fichier: Path, campagne: Campagne) -> None:
    """Écrit les paramètres d'une campagne à sa création ; jamais réécrits. Une campagne créée
    porte l'empreinte de son prompt (format 3), et une campagne GraphRAG celle de sa requête de
    recherche (format 4) : sans elles, rien ne vérifierait le gel (D7)."""
    if campagne.empreinte_prompt is None:
        raise OrchestrationError(f"campagne {campagne.nom} sans empreinte du prompt : non écrite")
    if campagne.consigne == "contexte" and campagne.empreinte_recherche is None:
        raise OrchestrationError(
            f"campagne {campagne.nom} sans empreinte de la requête de recherche : non écrite"
        )
    plafonds = asdict(campagne.plafonds) | {"budget_usd": str(campagne.plafonds.budget_usd)}
    contenu = {
        "format": FORMAT,
        "campagne": campagne.nom,
        "passes": campagne.passes,
        "conversations": [list(conversation) for conversation in campagne.conversations],
        "cellules": list(campagne.cellules),
        "cache_1h": campagne.cache_1h,
        "plafonds": plafonds,
        "faux_serveur": campagne.faux_serveur,
        "schema": campagne.schema,
        "empreinte_prompt": campagne.empreinte_prompt,
        "empreinte_recherche": campagne.empreinte_recherche,
    }
    fichier.parent.mkdir(parents=True, exist_ok=True)
    with fichier.open("x", encoding="utf-8") as flux:
        flux.write(json.dumps(contenu, ensure_ascii=False, indent=2) + "\n")


def lire_campagne(fichier: Path) -> Campagne:
    """Relit les paramètres d'une campagne ; une clé inconnue ou manquante est refusée. Une campagne
    au format 2 (d'avant T10.0) est en français, sans empreinte de sa fiche ; aux formats 2 et 3
    (d'avant T12.1), elle mesure la technique 2, sans requête de recherche."""
    cles = {
        "format",
        "campagne",
        "passes",
        "conversations",
        "cellules",
        "cache_1h",
        "plafonds",
        "faux_serveur",
    }
    try:
        brut = json.loads(fichier.read_text(encoding="utf-8"))
        if not isinstance(brut, dict) or brut.get("format") not in FORMATS_LUS:
            raise ValueError(f"format {brut.get('format') if isinstance(brut, dict) else brut!r}")
        if brut["format"] >= 3:
            cles |= {"schema", "empreinte_prompt"}
        if brut["format"] >= 4:
            cles |= {"empreinte_recherche"}
        if set(brut) != cles:
            raise ValueError(f"clés {sorted(brut)} inattendues")
        if not isinstance(brut.get("schema", "fr"), str):
            raise TypeError("schema : du texte attendu")
        if brut["format"] >= 3 and not isinstance(brut["empreinte_prompt"], str):
            raise TypeError("empreinte_prompt : du texte attendu")
        recherche = brut.get("empreinte_recherche")
        if recherche is not None and not isinstance(recherche, str):
            raise TypeError("empreinte_recherche : du texte ou null attendu")
        plafonds = dict(brut["plafonds"])
        plafonds["budget_usd"] = Decimal(plafonds["budget_usd"])
        if not isinstance(brut["passes"], int) or not all(
            isinstance(brut[cle], bool) for cle in ("cache_1h", "faux_serveur")
        ):
            raise TypeError("passes : un entier ; cache_1h, faux_serveur : vrai ou faux")
        campagne = Campagne(
            nom=brut["campagne"],
            passes=brut["passes"],
            conversations=tuple(tuple(conversation) for conversation in brut["conversations"]),
            cellules=tuple(brut["cellules"]),
            cache_1h=brut["cache_1h"],
            plafonds=Plafonds(**plafonds),
            faux_serveur=brut["faux_serveur"],
            schema=brut.get("schema", "fr"),
            empreinte_prompt=brut.get("empreinte_prompt"),
            empreinte_recherche=recherche,
        )
    except (OSError, ValueError, KeyError, TypeError, InvalidOperation) as erreur:
        raise OrchestrationError(f"{fichier} illisible : {erreur}") from erreur
    # Une empreinte nulle couperait la vérification du gel de la requête (D7).
    if campagne.consigne == "contexte" and campagne.empreinte_recherche is None:
        raise OrchestrationError(
            f"{fichier} : campagne GraphRAG sans empreinte de la requête de recherche"
        )
    return campagne


def dernier_essai(
    etape: Etape, lignes: Sequence[Mapping[str, str]], dossier: Path
) -> tuple[int, frozenset[str] | None]:
    """Le dernier essai de cette étape (0 s'il n'y en a pas), et les issues de ses lignes ; None
    s'il n'a qu'une trace, sans ligne (cellule ou harnais arrêtés en route).

    Args:
        etape: la conversation d'une cellule dans une passe.
        lignes: le CSV de la campagne.
        dossier: les traces de la campagne.
    """
    issues = issues_par_essai(etape, lignes)
    dernier = max({*issues, *essais_traces(etape, dossier)}, default=0)
    if dernier in issues:
        return dernier, issues[dernier]
    return dernier, None


def issues_par_essai(
    etape: Etape, lignes: Sequence[Mapping[str, str]]
) -> dict[int, frozenset[str]]:
    """Les issues des lignes de cette étape, essai par essai."""
    issues: dict[int, set[str]] = {}
    for valeurs in lignes:
        if (
            (valeurs["cellule"], valeurs["passe"]) == (etape.cellule, str(etape.passe))
            and valeurs["question"] in etape.questions
        ):  # fmt: skip
            issues.setdefault(int(valeurs["essai"]), set()).add(valeurs["issue"])
    return {essai: frozenset(valeurs) for essai, valeurs in issues.items()}


def pannes_de_suite(etape: Etape, lignes: Sequence[Mapping[str, str]]) -> int:
    """Les derniers essais de cette étape en panne, à la suite : le circuit breaker du plan les
    compte d'un lancement à l'autre."""
    compte = 0
    for _essai, issues in sorted(issues_par_essai(etape, lignes).items(), reverse=True):
        if "panne" not in issues:
            break
        compte += 1
    return compte


def essais_traces(etape: Etape, dossier: Path) -> set[int]:
    """Les essais de cette étape qui ont une trace dans le dossier de la campagne, écartée
    comprise : son numéro reste pris."""
    debut = nom_de_trace(etape.cellule, etape.passe, etape.questions, 0).removesuffix("0.jsonl")
    essais = set()
    for fichier in dossier.glob(f"{escape(debut)}*"):
        if trouve := FIN_DE_TRACE.fullmatch(fichier.name[len(debut) :]):
            essais.add(int(trouve[1]))
    return essais


# --- Processus d'une cellule ---------------------------------------------------------------------


def executer(
    programme: Sequence[str], entree: str, env: Mapping[str, str], dossier: Path, echeance_s: float
) -> tuple[int, bool]:
    """Lance une cellule dans sa propre session (son propre groupe), lui passe sa commande sur stdin
    et attend sa sortie ; au-delà de l'échéance, l'arrête (arreter). Rien de son groupe ne lui
    survit, même si l'attente est interrompue (Ctrl-C). Renvoie son code de sortie, et vrai si elle
    a été tuée."""
    cellule = subprocess.Popen(
        list(programme),
        stdin=subprocess.PIPE,
        cwd=dossier,
        env=dict(env),
        start_new_session=True,
        encoding="utf-8",
    )
    tuee = False
    try:
        cellule.communicate(entree, timeout=echeance_s)
    except subprocess.TimeoutExpired:
        # Sortie entre l'échéance et ce relevé : elle n'est pas tuée.
        tuee = cellule.poll() is None
    finally:
        try:
            if cellule.poll() is None:
                arreter(cellule)
        finally:
            # Les restes de son groupe, s'il en est : rien ne survit à une conversation.
            _signaler(cellule.pid, signal.SIGKILL)
    return cellule.returncode, tuee


def arreter(cellule: subprocess.Popen[str], grace_s: float | None = None) -> None:
    """Arrête une cellule et ses descendants : SIGTERM à son groupe (la cellule ADK arrête alors
    son serveur MCP, qui vit dans sa propre session, puis sort en 143) ; après grace_s, SIGKILL à
    son groupe ; enfin SIGKILL aux groupes de ses descendants encore en vie, relevés avant le
    premier signal."""
    grace = GRACE_S if grace_s is None else grace_s
    groupes: set[int] = set()
    try:
        groupes = {groupe for _pid, groupe in descendants(cellule.pid)} - {os.getpgid(0)}
        _signaler(cellule.pid, signal.SIGTERM)
        with contextlib.suppress(subprocess.TimeoutExpired):
            cellule.wait(timeout=grace)
    finally:
        # Même si l'attente est interrompue (un second Ctrl-C pendant la grâce) : rien ne survit.
        for groupe in {cellule.pid, *groupes}:
            _signaler(groupe, signal.SIGKILL)
        cellule.wait()


def descendants(racine: int) -> set[tuple[int, int]]:
    """Les processus issus de racine (enfants, petits-enfants…) et leurs groupes, lus dans /proc :
    un serveur MCP lancé dans sa propre session reste un descendant de la cellule."""
    parents: dict[int, list[tuple[int, int]]] = {}
    for stat in Path("/proc").glob("[0-9]*/stat"):
        try:
            # « pid (nom) état ppid groupe … » : le nom peut porter espaces et parenthèses.
            champs = stat.read_text().rsplit(")", 1)[1].split()
        except OSError, IndexError:
            continue
        parents.setdefault(int(champs[1]), []).append((int(stat.parent.name), int(champs[2])))
    trouves: set[tuple[int, int]] = set()
    a_voir = [racine]
    while a_voir:
        for enfant in parents.get(a_voir.pop(), []):
            if enfant not in trouves:
                trouves.add(enfant)
                a_voir.append(enfant[0])
    return trouves


@contextlib.contextmanager
def verrou(racine: Path) -> Iterator[None]:
    """Une campagne à la fois sur ce poste : elles partagent l'instance Aura, et le nettoyage de
    l'une arrêterait les lectures de l'autre. Le verrou tombe avec le processus, même tué.

    Raises:
        OrchestrationError: une campagne tourne déjà.
    """
    racine.mkdir(parents=True, exist_ok=True)
    with (racine / ".verrou").open("a") as fichier:
        try:
            fcntl.flock(fichier, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as erreur:
            raise OrchestrationError(
                f"une campagne tourne déjà sur ce poste ({racine / '.verrou'}) : une à la fois"
            ) from erreur
        yield


def _signaler(groupe: int, numero: signal.Signals) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(groupe, numero)


def transactions(script: Path = TRANSACTIONS) -> str:
    """Arrête sur Aura les lectures des agents restées actives (scripts/transactions.sh), lancé
    sans la clé Anthropic, qui ne sert qu'aux cellules Claude (code-map) ; rend son compte rendu.

    Raises:
        OrchestrationError: le script échoue (1 : une lecture reste active ; 2 : erreur technique).
    """
    env = {cle: valeur for cle, valeur in os.environ.items() if not cle.startswith("ANTHROPIC_")}
    try:
        fini = subprocess.run(
            [str(script)],
            capture_output=True,
            text=True,
            timeout=NETTOYAGE_S,
            env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as erreur:
        raise OrchestrationError(f"transactions.sh : {erreur}") from erreur
    if fini.returncode != 0:
        message_ = (fini.stderr.strip().splitlines() or [""])[-1]
        raise OrchestrationError(f"transactions.sh : code {fini.returncode} {message_}".strip())
    return fini.stdout.strip()


def outils_des_agents() -> tuple[Path, ...]:
    """Dossiers du PATH des agents, devant ceux du système : gcloud (le lanceur y lit le secret
    d'Aura) et neo4j-mcp (seul dans le sien, T0.3).

    Raises:
        OrchestrationError: l'un des deux introuvable.
    """
    trouve = shutil.which("gcloud")
    gcloud = Path(trouve) if trouve else GCLOUD
    serveur = NEO4J_MCP / "neo4j-mcp"
    for outil in (gcloud, serveur):
        if not (outil.is_file() and os.access(outil, os.X_OK)):
            raise OrchestrationError(f"{outil} introuvable ou non exécutable")
    return (gcloud.parent, serveur.parent)


def langue_par_script(script: Path = CHARGER, delai_s: float = 120.0) -> str:
    """La langue du schéma de la base par scripts/charger.sh --langue, en lecture seule : fr, en,
    vide, mixte ou incomplète. Lancé sans la clé Anthropic de l'environnement : elle ne sert
    qu'aux cellules Claude (code-map)."""
    environnement = {cle: v for cle, v in os.environ.items() if not cle.startswith("ANTHROPIC_")}
    try:
        fini = subprocess.run(
            [str(script), "--langue"],
            capture_output=True,
            text=True,
            timeout=delai_s,
            env=environnement,
            check=False,
        )
    except subprocess.TimeoutExpired as erreur:
        raise OrchestrationError(
            f"charger.sh --langue : aucune réponse en {delai_s:g} s"
        ) from erreur
    derniere = (fini.stdout.strip().splitlines() or [""])[-1]
    trouvee = re.fullmatch(r"LANGUE : (fr|en|vide|mixte|incomplète)", derniere)
    if fini.returncode not in {0, 1} or trouvee is None:
        message = (fini.stderr.strip().splitlines() or [""])[-1]
        raise OrchestrationError(f"charger.sh --langue : code {fini.returncode} {message}".strip())
    return trouvee.group(1)


def verifier_la_base(
    schema: str,
    langue: Callable[[], str] = langue_par_script,
    traduction: Path = anglais.TRADUCTION,
) -> None:
    """Avant de créer ou de reprendre une campagne (T10.0) : la base est dans la langue de son
    schéma (D8) ; en anglais, la traduction où le contrôle de Q2 prend q02.cypher est à jour.

    Raises:
        OrchestrationError: base dans l'autre langue, vide, bascule interrompue (noms des deux
            langues, ou d'une seule sans ses contraintes et index) ; traduction absente ou
            périmée.
    """
    trouvee = langue()
    if trouvee in {"mixte", "incomplète"}:
        cause = (
            "noms des deux langues"
            if trouvee == "mixte"
            else "contraintes ou index absents ou pas en ligne"
        )
        raise OrchestrationError(
            f"bascule du schéma interrompue ({cause}) : relancer scripts/charger.sh --schema "
            f"{schema}"
        )
    if trouvee != schema:
        raise OrchestrationError(
            f"base {'vide' if trouvee == 'vide' else f'en {trouvee}'}, campagne en {schema} : "
            f"scripts/charger.sh {'--tout' if trouvee == 'vide' else f'--schema {schema}'} d'abord"
        )
    if schema != "en":
        return
    try:
        ecarts = anglais.ecarts_de_traduction(traduction)
    except (CorrespondanceError, TraductionError, ValueError, OSError) as erreur:
        raise OrchestrationError(f"traduction illisible ({traduction}) : {erreur}") from erreur
    if ecarts:
        raise OrchestrationError(
            f"traduction à refaire dans {traduction} ({', '.join(ecarts[:3])}"
            f"{', …' if len(ecarts) > 3 else ''}) : uv run --directory banc python -m banc "
            "traduire --vers logs/anglais"
        )


# Contrôle de Q2 d'une campagne en anglais : la traduction de q02.cypher (D8).
CONTROLE_EN: Controleur = functools.partial(controle_par_script, dossier=anglais.TRADUCTION)


@dataclass(frozen=True)
class Moyens:
    """Ce qui mène et note les conversations, hors des paramètres de la campagne : les tests le
    remplacent (fausse cellule, faux outils, échéances courtes)."""

    mesures: Path = MESURES
    traces: Path = TRACES
    programmes: Mapping[str, Sequence[str]] = field(default_factory=lambda: dict(PROGRAMMES))
    # Dossiers placés dans le PATH des agents, devant ceux du système (outils_des_agents).
    chemins: tuple[Path, ...] = ()
    # Serveur MCP lancé par chaque client : le lanceur, ou un faux serveur.
    serveur: tuple[str, ...] = (str(LANCEUR),)
    # Répétition générale : le serveur de la conversation LENTE, au-delà du délai d'une question.
    serveur_lent: tuple[str, ...] | None = None
    # Binaire de Claude Code : None pour celui du SDK.
    cli: Path | None = None
    # Contrôle de Q2 (D6), sur la base française ou anglaise ; nettoyage d'Aura après une
    # conversation qui ne finit pas proprement.
    controle: Controleur | None = controle_par_script
    controle_en: Controleur | None = CONTROLE_EN
    nettoyer: Callable[[], str] = transactions
    # Avant de créer ou de reprendre une campagne : la base dans sa langue (T10.0) ; None : rien
    # à vérifier (répétition générale, rien ne touche Aura).
    verifier_la_base: Callable[[str], None] | None = verifier_la_base
    # Encodage des messages d'une campagne GraphRAG à sa création (banc.encodage, D5) : une
    # connexion à Vertex par campagne, qui encode un texte pour une tâche.
    encodeur: Callable[[], Callable[[str, str], Encodage]] = encodeur_vertex
    marge_s: float = MARGE_S
    ecrire: Callable[[str], None] = print


def moyens_faux_serveur() -> Moyens:
    """Répétition générale (T5.1) : faux serveur MCP, contrôle de Q2 simulé, aucun nettoyage, ni
    gcloud ni neo4j-mcp dans le PATH des agents : rien ne touche Aura."""
    lent_s = Plafonds().delai_s + LENTEUR_S
    return Moyens(
        serveur=FAUX_SERVEUR,
        serveur_lent=(*FAUX_SERVEUR, "--lent-s", f"{lent_s:g}"),
        controle=controle_simule,
        controle_en=controle_simule,
        nettoyer=_sans_nettoyage,
        verifier_la_base=None,
    )


def _sans_nettoyage() -> str:
    """Faux serveur : aucune lecture d'agent sur Aura à arrêter."""
    return ""


# --- Campagne ------------------------------------------------------------------------------------


class Orchestration:
    """Mène une campagne, étape après étape (voir le module)."""

    def __init__(
        self,
        campagne: Campagne,
        plafond_usd: Decimal,
        moyens: Moyens,
        banc: Banc,
        vecteurs: Mapping[str, tuple[float, ...]] | None = None,
    ) -> None:
        questions = {
            question for conversation in campagne.conversations for question in conversation
        }
        if inconnues := sorted(questions - set(banc.questions)):
            raise OrchestrationError(f"questions inconnues du banc : {', '.join(inconnues)}")
        # Les vecteurs des messages d'une campagne GraphRAG, par question (encodages.json, D5).
        self.vecteurs = dict(vecteurs or {})
        if set(self.vecteurs) != (questions if campagne.consigne == "contexte" else set()):
            raise OrchestrationError(
                f"vecteurs de {sorted(self.vecteurs)} : une campagne GraphRAG en a un par "
                "question, les autres aucun"
            )
        self.campagne = campagne
        self.plafond_usd = plafond_usd
        self.moyens = moyens
        self.banc = banc
        self.referentiel = Referentiel.charger(banc)
        self.tarifs = prix.charger()
        self.csv = fichier_mesures(campagne.nom, moyens.mesures)
        self.dossier = moyens.traces / campagne.nom
        # Le contrôle de Q2 joue q02.cypher dans la langue de la base (D8).
        self.controle = moyens.controle_en if campagne.schema == "en" else moyens.controle
        # Coût de chaque trace restée sans ligne, lu une fois (plafond de la campagne).
        self._couts_sans_ligne: dict[Path, Decimal] = {}

    def lancer(self) -> int:
        """Mène chaque étape qui n'est pas finie ; rend 0, ou 1 si une passe est invalide.

        Raises:
            ArretPlafond: crédits épuisés, ou plafond de la campagne atteint.
            OrchestrationError: erreur technique, cellule tuée, 3 pannes de suite.
        """
        # Une campagne interrompue a pu laisser des lectures actives sur Aura.
        self._nettoyer()
        for etape in self.campagne.etapes():
            self._etape(etape)
        return self._bilan()

    def _etape(self, etape: Etape) -> None:
        """Mène une étape jusqu'à une issue qui compte (D13). Son dernier essai d'abord : au CSV,
        il dit si l'étape est finie ; resté sans ligne, il est noté s'il est complet, jamais
        rejoué (ADR-0009), puis suit les règles d'un essai qu'on vient de mener ; inachevé, il se
        rejoue. Les pannes de suite se comptent d'un lancement à l'autre."""
        lignes = self._lignes()
        essai, issues = dernier_essai(etape, lignes, self.dossier)
        pannes = pannes_de_suite(etape, lignes)
        a_noter = None
        if essai and issues is None:
            a_noter = self._trace_complete(etape, essai)
        elif issues is not None and not {"panne", "arret"} & issues:
            return
        if a_noter is None:
            essai += 1
        while True:
            if a_noter is not None:
                menees = self._ecrire_les_lignes(etape, essai, a_noter)
                a_noter = None
            else:
                self._verifier_le_plafond()
                menees = self._mener(etape, essai)
            if "arret" in menees:
                raise ArretPlafond(
                    f"{etape} : crédits Anthropic épuisés ou limite du workspace atteinte ; "
                    "recharge après accord, puis --reprendre"
                )
            if "panne" not in menees:
                return
            pannes += 1
            self._signaler_une_passe_invalide(etape)
            if pannes >= PANNES_DE_SUITE:
                raise OrchestrationError(
                    f"{etape} : {pannes} pannes de suite, arrêt (circuit breaker du plan), "
                    "à replanifier"
                )
            essai += 1

    def _mener(self, etape: Etape, essai: int) -> tuple[str, ...]:
        """Une conversation : la cellule dans son processus ; Aura nettoyé si elle ne finit pas
        proprement, avant le contrôle de Q2 ; puis toutes ses lignes au CSV. Une cellule tuée ou
        en erreur arrête la campagne, sans ligne : la reprise note sa trace si elle est complète,
        la rejoue sinon."""
        commande = self._commande(etape, essai)
        try:
            with tempfile.TemporaryDirectory(prefix="banc-agent-") as dossier:
                env, travail = self._isoler(etape, Path(dossier))
                programme = self.moyens.programmes[etape.cellule]
                code, tuee = executer(
                    programme, commande_json(commande), env, travail, self._echeance(commande)
                )
            conversation = self._trace_complete(etape, essai)
        except BaseException:
            self._nettoyer_sans_masquer()
            raise
        if tuee or code != 0 or conversation is None:
            self._nettoyer_sans_masquer()
            if tuee:
                cas = f"cellule tuée (code {code}), au-delà de ses plafonds de plus de "
                cas += f"{self.moyens.marge_s:.0f} s"
            elif code != 0:
                cas = f"cellule sortie en {code} (erreur technique, voir son message)"
            else:
                cas = "trace absente ou inachevée, cellule sortie en 0"
            raise OrchestrationError(f"{etape}, essai {essai} : {cas} ; --reprendre la reprend")
        if any(tour.issue != "reponse" for tour in conversation.tours):
            self._nettoyer()
        return self._ecrire_les_lignes(etape, essai, conversation)

    def _ecrire_les_lignes(
        self, etape: Etape, essai: int, conversation: Conversation
    ) -> tuple[str, ...]:
        """Note la conversation, en ajoute toutes les lignes au CSV d'un coup, les annonce ; rend
        leurs issues."""
        lignes = self._lignes_de(conversation)
        ecrire(self.csv, lignes)
        self._afficher(etape, essai, lignes)
        return tuple(valeurs["issue"] for valeurs in lignes)

    def _commande(self, etape: Etape, essai: int) -> Commande:
        return Commande(
            campagne=self.campagne.nom,
            passe=etape.passe,
            essai=essai,
            questions=tuple(
                (ident, message(self.banc.questions[ident])) for ident in etape.questions
            ),
            traces=self.moyens.traces,
            plafonds=self.campagne.plafonds,
            cache_1h=self.campagne.cache_1h,
            serveur=self._serveur(etape),
            cli=self.moyens.cli,
            schema=self.campagne.schema,
            empreinte_prompt=self.campagne.empreinte_prompt,
            vecteurs=self._vecteurs(etape),
            empreinte_recherche=self.campagne.empreinte_recherche,
        )

    def _vecteurs(self, etape: Etape) -> tuple[tuple[float, ...], ...]:
        """Les vecteurs des questions de l'étape, dans leur ordre ; aucun pour la technique 2."""
        if not self.vecteurs:
            return ()
        return tuple(self.vecteurs[ident] for ident in etape.questions)

    def _serveur(self, etape: Etape) -> tuple[str, ...]:
        if self.moyens.serveur_lent is not None and (etape.cellule, etape.questions[0]) == LENTE:
            return self.moyens.serveur_lent
        return self.moyens.serveur

    def _isoler(self, etape: Etape, dossier: Path) -> tuple[dict[str, str], Path]:
        """La liste blanche de la cellule (D3), avec un HOME, une configuration de Claude Code et
        un dossier de travail neufs, hors du dépôt ; rend l'environnement et le dossier de
        travail."""
        home, claude, travail = dossier / "home", dossier / "claude", dossier / "travail"
        for chemin in (home, claude, travail):
            chemin.mkdir()
        env = environnement_agent(
            etape.cellule, home, claude, self.moyens.chemins, cache_1h=self.campagne.cache_1h
        )
        return env, travail

    def _echeance(self, commande: Commande) -> float:
        """Ce que la cellule peut prendre avant d'être tuée : la connexion avant le chrono ; par
        question, le délai, puis de quoi finir le tour (résultat après l'interruption, serveur
        vérifié) ; la marge."""
        plafonds = commande.plafonds
        par_question = plafonds.delai_s + plafonds.connexion_s
        questions = len(commande.questions)
        return plafonds.connexion_s + questions * par_question + self.moyens.marge_s

    def _trace_complete(self, etape: Etape, essai: int) -> Conversation | None:
        """La trace d'un essai, si la cellule a fini la conversation ; None si elle manque, ou si
        elle a été coupée en plein tour ou entre deux tours (cellule tuée ou en erreur).

        Raises:
            OrchestrationError: trace d'une autre conversation, ou tour qui suit un tour sans
                réponse (hors de D13 : cellule fautive).
            MesureError: trace illisible.
        """
        fichier = self.dossier / nom_de_trace(etape.cellule, etape.passe, etape.questions, essai)
        if not fichier.exists():
            return None
        conversation = lire(fichier)
        e, tours = conversation.entete, conversation.tours
        attendu = (self.campagne.nom, etape.cellule, etape.passe, essai, etape.questions)
        if (e.campagne, e.cellule, e.passe, e.essai, e.questions) != attendu:
            raise OrchestrationError(f"{fichier.name} : en-tête d'une autre conversation")
        # Avant tout : un tour après un tour sans réponse, aucune cellule ne le pose (D13).
        if any(tour.issue != "reponse" for tour in tours[:-1]):
            raise OrchestrationError(
                f"{fichier.name} : un tour suit un tour sans réponse, hors de D13 (cellule "
                "fautive) ; la corriger, puis écarter cette trace (la renommer en "
                ".jsonl.ecartee) pour rejouer la conversation"
            )
        if (
            not tours
            or tours[-1].issue is None
            or (len(tours) < len(etape.questions) and tours[-1].issue == "reponse")
        ):
            return None
        return conversation

    def _lignes_de(self, conversation: Conversation) -> list[dict[str, str]]:
        """Les lignes de la conversation : chaque tour, ses réponses notées ; puis, si son premier
        tour a échoué, le second, faux d'office (ADR-0012)."""
        entete, tours = conversation.entete, conversation.tours
        lignes = []
        for rang, tour in enumerate(tours):
            notation = None
            if tour.issue == "reponse":
                question = self.banc.questions[tour.question]
                # Un second tour lit aussi les lectures de son tour précédent (ADR-0015).
                avant = tours[rang - 1] if rang else None
                precedent = (
                    avant.tour()
                    if avant is not None and avant.question == question.tour_precedent
                    else None
                )
                notation = noter(question, tour.tour(), self.referentiel, self.controle, precedent)
            lignes.append(ligne(entete, tour, notation, self.tarifs))
        if tours[-1].issue == "echec":
            for ident in entete.questions[len(tours) :]:
                posee = message(self.banc.questions[ident])
                sans_tour = TourMesure(ident, posee, issue="echec", cause=PRECEDENT, duree_s=0.0)
                lignes.append(ligne(entete, sans_tour, None, self.tarifs))
        return lignes

    def _lignes(self) -> list[dict[str, str]]:
        return lire_lignes(self.csv) if self.csv.exists() else []

    def _verifier_le_plafond(self) -> None:
        """Avant chaque conversation : ce que la campagne a coûté (son CSV, reprises comprises, et
        ses traces restées sans ligne), plus la réserve d'une conversation (son budget et autant de
        marge), ne doit pas dépasser son plafond (choix de Julien)."""
        lignes = self._lignes()
        depense = sum((Decimal(valeurs["cout_usd"]) for valeurs in lignes), Decimal(0))
        depense += self._depense_sans_ligne(lignes)
        reserve = RESERVE_EN_BUDGETS * self.campagne.plafonds.budget_usd
        if depense + reserve > self.plafond_usd:
            raise ArretPlafond(
                f"plafond de la campagne : {depense} $ dépensés sur {self.plafond_usd} $, il "
                f"reste moins que la réserve d'une conversation ({reserve} $ : son budget et "
                "autant de marge) ; --reprendre avec un plafond relevé, après décision"
            )

    def _depense_sans_ligne(self, lignes: Sequence[Mapping[str, str]]) -> Decimal:
        """Ce qu'ont coûté les traces restées sans ligne (cellule tuée ou en erreur en plein tour,
        trace écartée, rejouées à l'essai suivant) : payé, absent du CSV."""
        conversation_de = {q: c for c in self.campagne.conversations for q in c}
        avec_ligne = {
            nom_de_trace(
                v["cellule"],
                int(v["passe"]),
                conversation_de.get(v["question"], (v["question"],)),
                int(v["essai"]),
            )
            for v in lignes
        }
        total = Decimal(0)
        for fichier in sorted(self.dossier.glob("*.jsonl*")):
            if fichier.name in avec_ligne:
                continue
            if fichier not in self._couts_sans_ligne:
                trace = lire(fichier)
                e = trace.entete
                par_tour = (couts(t.usages, self.tarifs, e.jour, e.acces) for t in trace.tours)
                self._couts_sans_ligne[fichier] = sum(
                    (sum(cout.values(), Decimal(0)) for cout in par_tour), Decimal(0)
                )
            total += self._couts_sans_ligne[fichier]
        return total

    def _nettoyer(self) -> None:
        if compte_rendu := self.moyens.nettoyer():
            self.moyens.ecrire(compte_rendu)

    def _nettoyer_sans_masquer(self) -> None:
        """Nettoie Aura quand une conversation s'arrête sur une erreur, sans masquer celle-ci."""
        try:
            self._nettoyer()
        except OrchestrationError as erreur:
            print(
                f"banc lancer : {erreur} ; lectures des agents à vérifier sur Aura.",
                file=sys.stderr,
            )

    def _afficher(self, etape: Etape, essai: int, lignes: Sequence[Mapping[str, str]]) -> None:
        """Une ligne par conversation : issues, durées et coût, jamais la note, pour garder la
        revue à l'aveugle (D4)."""
        tours = " ; ".join(
            f"{valeurs['question']} {valeurs['issue']}"
            + (f" ({valeurs['cause']})" if valeurs["cause"] else "")
            + f" {float(valeurs['duree_s']):.1f} s"
            for valeurs in lignes
        )
        cout = sum((Decimal(valeurs["cout_usd"]) for valeurs in lignes), Decimal(0))
        self.moyens.ecrire(f"{etape} · essai {essai} : {tours} · {cout:.4f} $")

    def _signaler_une_passe_invalide(self, etape: Etape) -> None:
        pannes = sum(1 for valeurs in self._lignes() if _panne_de(valeurs, etape))
        if pannes == PANNES_PAR_SERIE + 1:
            self.moyens.ecrire(
                f"⚠ {etape.cellule}, passe {etape.passe} : {pannes} pannes, passe invalide "
                "(plan, D13) ; la campagne continue"
            )

    def _bilan(self) -> int:
        lignes = self._lignes()
        pannes = Counter(
            (valeurs["cellule"], int(valeurs["passe"]))
            for valeurs in lignes
            if valeurs["issue"] == "panne"
        )
        invalides = sorted(serie for serie, nombre in pannes.items() if nombre > PANNES_PAR_SERIE)
        depense = sum((Decimal(valeurs["cout_usd"]) for valeurs in lignes), Decimal(0))
        self.moyens.ecrire(
            f"campagne {self.campagne.nom} finie : {len(lignes)} lignes, {depense} $ en tout"
        )
        for cellule, passe in invalides:
            self.moyens.ecrire(
                f"⚠ {cellule}, passe {passe} : {pannes[cellule, passe]} pannes, passe invalide "
                "(plan, D13)"
            )
        return INVALIDE if invalides else FINIE


def _panne_de(valeurs: Mapping[str, str], etape: Etape) -> bool:
    serie = (valeurs["cellule"], valeurs["passe"])
    return serie == (etape.cellule, str(etape.passe)) and valeurs["issue"] == "panne"


# --- Commande ------------------------------------------------------------------------------------


def commande(demande: Demande, moyens: Moyens | None = None) -> int:
    """`banc lancer` : mène ou reprend une campagne ; codes retour du module."""
    # Sous nohup, SIGHUP est ignoré : il le reste.
    ignore = signal.getsignal(signal.SIGHUP) is signal.SIG_IGN
    numeros = (signal.SIGTERM,) if ignore else (signal.SIGTERM, signal.SIGHUP)
    precedents = {numero: signal.signal(numero, _interrompre) for numero in numeros}
    try:
        if moyens is None:
            moyens = (
                moyens_faux_serveur()
                if demande.faux_serveur
                else Moyens(chemins=outils_des_agents())
            )
        # Avant de créer quoi que ce soit : une campagne refusée n'est pas créée.
        with verrou(moyens.traces):
            return _preparer(demande, moyens).lancer()
    except ArretPlafond as arret:
        print(f"banc lancer : arrêt sur un plafond de dépense : {arret}", file=sys.stderr)
        return PLAFOND
    except KeyboardInterrupt:
        print("banc lancer : interrompue ; --reprendre pour continuer", file=sys.stderr)
        return INTERROMPUE
    except (
        OrchestrationError,
        MesureError,
        NotationError,
        LectureError,
        AttenduError,
        BancError,
        PrixError,
        CleAbsente,
        EncodageError,
        OSError,
    ) as erreur:
        print(f"banc lancer : {erreur}", file=sys.stderr)
        return ERREUR
    finally:
        for numero, gestionnaire in precedents.items():
            signal.signal(numero, gestionnaire)


def _interrompre(_numero: int, _cadre: FrameType | None) -> None:
    """Un SIGTERM ou un SIGHUP (terminal fermé) au harnais l'interrompt comme un Ctrl-C : la
    cellule en cours est arrêtée, et Aura nettoyé."""
    raise KeyboardInterrupt


def _preparer(demande: Demande, moyens: Moyens) -> Orchestration:
    """Crée la campagne, ou relit celle à reprendre ; vérifie la clé avant d'écrire quoi que ce
    soit. Une campagne GraphRAG encode ses messages à sa création, avant toute écriture (D5), et
    relit ses encodages à la reprise, sans réencoder."""
    csv = fichier_mesures(demande.nom, moyens.mesures)
    dossier = moyens.traces / demande.nom
    parametres = dossier / PARAMETRES
    banc = banc_questions.charger()
    if demande.reprendre:
        if not parametres.exists():
            raise OrchestrationError(f"aucune campagne {demande.nom} à reprendre ({parametres})")
        campagne = lire_campagne(parametres)
        _verifier_la_reprise(campagne, demande, banc)
        _verifier_le_gel(campagne)
    else:
        if csv.exists() or dossier.exists():
            raise OrchestrationError(
                f"la campagne {demande.nom} existe déjà : --reprendre pour la continuer"
            )
        brouillon = Campagne(
            nom=demande.nom,
            passes=1 if demande.passes is None else demande.passes,
            conversations=conversations(banc, demande.questions),
            cellules=demande.cellules or PAR_DEFAUT,
            cache_1h=bool(demande.cache_1h),
            faux_serveur=demande.faux_serveur,
            schema=demande.schema or "fr",
        )
        campagne = replace(
            brouillon,
            empreinte_prompt=empreinte_prompt(brouillon.schema, consigne=brouillon.consigne),
            empreinte_recherche=empreinte_recherche() if brouillon.consigne == "contexte" else None,
        )
    if CLAUDE & set(campagne.cellules):
        cle_anthropic()
    if moyens.verifier_la_base is not None:
        moyens.verifier_la_base(campagne.schema)
    # Les messages posés d'une campagne GraphRAG, préambule de Q2 compris : sa recherche part du
    # vecteur de chacun (D5, D10).
    messages = {
        ident: message(banc.questions[ident])
        for conversation in campagne.conversations
        for ident in conversation
        if campagne.consigne == "contexte"
    }
    encodages: Mapping[str, Encodage] = {}
    if messages and demande.reprendre:
        encodages = relire_les_encodages(dossier / ENCODAGES, messages)
    elif messages:
        encodages = encoder_les_messages(messages, moyens.encodeur())
    vecteurs = {ident: encodage.vecteur for ident, encodage in encodages.items()}
    orchestration = Orchestration(campagne, demande.plafond_usd, moyens, banc, vecteurs)
    if not demande.reprendre:
        ecrire_campagne(parametres, campagne)
        if encodages:
            ecrire_les_encodages(dossier / ENCODAGES, messages, encodages)
    return orchestration


def _verifier_le_gel(campagne: Campagne) -> None:
    """À la reprise : le prompt et la requête de recherche fixés à la création (protocole gelé,
    D7).

    Raises:
        OrchestrationError: consigne, fiche ou requête de recherche changées depuis.
    """
    if campagne.empreinte_prompt not in {
        None,
        empreinte_prompt(campagne.schema, consigne=campagne.consigne),
    }:
        raise OrchestrationError(
            f"consigne ou {FICHES[campagne.schema]} changées depuis la création de la "
            f"campagne {campagne.nom} (protocole gelé, D7)"
        )
    if campagne.empreinte_recherche not in {None, empreinte_recherche()}:
        raise OrchestrationError(
            f"{RECHERCHE.relative_to(RACINE)} changée depuis la création de la campagne "
            f"{campagne.nom} (protocole gelé, D7)"
        )


def _verifier_la_reprise(campagne: Campagne, demande: Demande, banc: Banc) -> None:
    """--reprendre garde les paramètres de la campagne : une option qui les contredit est
    refusée (seul le plafond de dépense peut changer)."""
    demandes = {
        "passes": (demande.passes, campagne.passes),
        "questions": (
            conversations(banc, demande.questions) if demande.questions else None,
            campagne.conversations,
        ),
        "cellules": (demande.cellules or None, campagne.cellules),
        "cache_1h": (demande.cache_1h, campagne.cache_1h),
        # Sans valeur « non précisé » : une reprise redit le mode de sa campagne.
        "faux_serveur": (demande.faux_serveur, campagne.faux_serveur),
        "schema": (demande.schema, campagne.schema),
    }
    if ecarts := [nom for nom, (voulu, fixe) in demandes.items() if voulu not in {None, fixe}]:
        raise OrchestrationError(
            f"--reprendre garde les paramètres de la campagne {campagne.nom} "
            f"({', '.join(ecarts)} différents)"
        )
