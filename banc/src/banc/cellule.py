"""Ce que toute cellule reçoit (plan 002, D3 et D13) : la commande d'une conversation, ses
plafonds, la consigne et la fiche communes.

L'orchestration (T4.3) lance une cellule par conversation, dans un processus dont l'environnement
est la liste blanche de banc.isolement, depuis un dossier vide hors du dépôt, et lui passe sa
commande en JSON sur stdin. La cellule écrit la trace (banc.mesures.Journal), puis sort : 0 quand
chaque question posée a son issue, 2 sur une erreur technique (commande, isolement, mesure), qui
arrête la campagne.
"""

import json
from dataclasses import asdict, dataclass, field, fields
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from banc.mesures import QUESTION

RACINE = Path(__file__).resolve().parents[3]
QUESTIONS = RACINE / "questions"
LANCEUR = RACINE / "scripts" / "mcp-neo4j.sh"


class CelluleError(Exception):
    """Erreur technique : la conversation ne se mesure pas (commande, isolement, client, API)."""


class IsolementError(CelluleError):
    """Le client ne tourne pas comme D3 l'exige (outils, permissions, clé, version…)."""


@dataclass(frozen=True)
class Plafonds:
    """Plafonds d'un agent (ADR-0009, plan D13) : un dépassement compte faux, avec sa cause."""

    # Par question, de l'envoi du message à la réponse finale.
    delai_s: float = 180.0
    # Appels du modèle par question.
    tours: int = 10
    # Par conversation, toutes ses questions comprises (choix de Julien, T4.1).
    budget_usd: Decimal = Decimal("0.50")
    # Attente du serveur MCP avant le chrono ; au-delà, panne.
    connexion_s: float = 30.0

    def __post_init__(self) -> None:
        if not (self.delai_s > 0 and self.tours >= 1 and self.connexion_s > 0):
            raise ValueError(f"plafonds invalides : {self}")
        if not self.budget_usd > 0:
            raise ValueError(f"budget invalide : {self.budget_usd}")


@dataclass(frozen=True)
class Commande:
    """Une conversation à mener : de quoi écrire l'en-tête de sa trace, puis ses questions."""

    campagne: str
    passe: int
    essai: int
    # (identifiant, message posé), dans l'ordre : une question, ou une paire (Q2 puis Q18).
    questions: tuple[tuple[str, str], ...]
    # Racine des traces (banc.mesures.TRACES pour une campagne).
    traces: Path
    plafonds: Plafonds = field(default_factory=Plafonds)
    # Cache d'une heure des cellules Claude, au lieu de 5 min (plan, D10 : tranché au pilote).
    cache_1h: bool = False
    # Serveur MCP lancé par le client : le lanceur, ou un faux serveur (répétition générale, tests).
    serveur: tuple[str, ...] = (str(LANCEUR),)
    # Binaire de Claude Code : None pour celui du SDK, sinon un faux (tests).
    cli: Path | None = None


def lire_commande(texte: str) -> Commande:
    """Lit et valide la commande que l'orchestration envoie en JSON ; une clé inconnue est refusée :
    une faute de frappe ne doit pas retirer un plafond en silence."""
    try:
        brut = json.loads(texte)
        if not isinstance(brut, dict):
            raise TypeError("un objet JSON attendu")
        if inconnues := sorted(set(brut) - {f.name for f in fields(Commande)}):
            raise ValueError(f"clés inconnues {inconnues}")
        commande = _commande(brut)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError, InvalidOperation) as erreur:
        raise CelluleError(f"commande illisible : {erreur}") from erreur
    return commande


def commande_json(commande: Commande) -> str:
    """La commande en JSON, telle que lire_commande la relit (budget en texte, exact)."""
    champs: dict[str, Any] = asdict(commande)
    champs["questions"] = [list(question) for question in commande.questions]
    champs["traces"] = str(commande.traces)
    champs["serveur"] = list(commande.serveur)
    champs["cli"] = None if commande.cli is None else str(commande.cli)
    champs["plafonds"]["budget_usd"] = str(commande.plafonds.budget_usd)
    return json.dumps(champs, ensure_ascii=False)


def consigne_et_fiche(dossier: Path = QUESTIONS) -> str:
    """La consigne puis la fiche de schéma, telles quelles (D5) : le même texte pour toutes les
    cellules."""
    consigne = (dossier / "consigne.md").read_text(encoding="utf-8")
    fiche = (dossier / "fiche-schema.md").read_text(encoding="utf-8")
    return f"{consigne}\n\n{fiche}"


def _commande(brut: dict[str, Any]) -> Commande:
    questions = tuple((ident, message) for ident, message in brut["questions"])
    if not questions or not all(
        isinstance(ident, str)
        and QUESTION.fullmatch(ident)
        and isinstance(message, str)
        and message.strip()
        for ident, message in questions
    ):
        raise ValueError(f"questions : une liste de [Qn, message] attendue, pas {questions!r}")
    serveur = tuple(brut.get("serveur") or (str(LANCEUR),))
    if not all(isinstance(partie, str) and partie for partie in serveur):
        raise ValueError(f"serveur : une commande attendue, pas {serveur!r}")
    if not Path(serveur[0]).is_absolute():
        raise ValueError(f"serveur : chemin absolu attendu (plan, D1), pas {serveur[0]!r}")
    for nombre in ("passe", "essai"):
        if not isinstance(brut[nombre], int) or isinstance(brut[nombre], bool):
            raise TypeError(f"{nombre} : un entier attendu")
    if not isinstance(brut["campagne"], str) or not isinstance(brut["traces"], str):
        raise TypeError("campagne et traces : du texte attendu")
    if not isinstance(brut.get("cache_1h", False), bool):
        raise TypeError("cache_1h : vrai ou faux attendu")
    cli = brut.get("cli")
    return Commande(
        campagne=brut["campagne"],
        passe=brut["passe"],
        essai=brut["essai"],
        questions=questions,
        traces=Path(brut["traces"]),
        plafonds=_plafonds(brut.get("plafonds")),
        cache_1h=brut.get("cache_1h", False),
        serveur=serveur,
        cli=None if cli is None else Path(cli),
    )


def _plafonds(brut: Any) -> Plafonds:
    valeurs = dict(brut or {})
    if "budget_usd" in valeurs:
        valeurs["budget_usd"] = Decimal(str(valeurs["budget_usd"]))
    return Plafonds(**valeurs)
