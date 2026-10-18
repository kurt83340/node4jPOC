"""Ce que toute cellule reçoit (plan 002, D3 et D13) : la commande d'une conversation, ses
plafonds, la consigne de sa technique (avec ou sans outil, ADR-0018) et la fiche commune ; une
cellule GraphRAG, en plus, les vecteurs de ses messages et la requête de recherche (spec 003).

L'orchestration (T4.3) lance une cellule par conversation, dans un processus dont l'environnement
est la liste blanche de banc.isolement, depuis un dossier vide hors du dépôt, et lui passe sa
commande en JSON sur stdin. La cellule écrit la trace (banc.mesures.Journal), puis sort : 0 quand
chaque question posée a son issue, 2 sur une erreur technique (commande, isolement, mesure), qui
arrête la campagne. Toute vérification qui invalide la mesure d'un tour passe avant son `fin` : une
trace complète se note même après une sortie en 2 (reprise de banc.orchestration) ; après le
dernier `fin`, seul l'arrêt du client peut encore échouer.
"""

import hashlib
import json
import math
import re
from dataclasses import asdict, dataclass, field, fields
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from banc.mesures import QUESTION

RACINE = Path(__file__).resolve().parents[3]
QUESTIONS = RACINE / "questions"
LANCEUR = RACINE / "scripts" / "mcp-neo4j.sh"
# La fiche de schéma de chaque langue de la base (plan, D8) : la française, ou sa traduction par la
# table (T6.3), qui ne change que les identifiants du schéma.
FICHES = {"fr": "fiche-schema.md", "en": "fiche-schema.en.md"}
# La consigne de chaque genre de technique (ADR-0018) : un agent qui interroge la base par l'outil
# read-cypher (technique 2), ou un LLM sans outil qui reçoit le résultat d'une recherche, le
# contexte (technique 3, GraphRAG) ; la fiche reste commune.
CONSIGNES = {"outil": "consigne.md", "contexte": "consigne-contexte.md"}
# La recherche des cellules GraphRAG (spec 003, D6), lancée telle quelle par read-cypher.
RECHERCHE = QUESTIONS / "recherche.cypher"
EMPREINTE = re.compile(r"[0-9a-f]{64}")


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
    # Langue du schéma (D8) : la fiche du prompt.
    schema: str = "fr"
    # SHA-256 du prompt (consigne et fiche), fixé à la création de la campagne : un prompt modifié
    # depuis arrête la conversation (protocole gelé, D7). None : non vérifié (essais hors campagne).
    empreinte_prompt: str | None = None
    # Vecteurs des messages, un par question et dans leur ordre, encodés à la création de la
    # campagne (spec 003, D5) : la recherche des cellules GraphRAG ; aucun pour les autres.
    vecteurs: tuple[tuple[float, ...], ...] = ()
    # SHA-256 de la requête de recherche, fixé à la création de la campagne (spec 003, T12.1) : une
    # requête modifiée depuis arrête la conversation, comme le prompt (D7). None : non vérifiée.
    empreinte_recherche: str | None = None


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
    champs["vecteurs"] = [list(vecteur) for vecteur in commande.vecteurs]
    return json.dumps(champs, ensure_ascii=False)


def empreinte_prompt(schema: str, dossier: Path = QUESTIONS, consigne: str = "outil") -> str:
    """SHA-256 du prompt de cette langue et de cette consigne (CONSIGNES) : la consigne et la
    fiche, telles que les cellules les reçoivent (D7 les gèle toutes deux)."""
    return hashlib.sha256(_prompt(dossier, schema, consigne).encode("utf-8")).hexdigest()


def consigne_et_fiche(
    dossier: Path = QUESTIONS,
    schema: str = "fr",
    empreinte: str | None = None,
    consigne: str = "outil",
) -> str:
    """La consigne de la technique (CONSIGNES : avec ou sans outil, ADR-0018) puis la fiche de
    schéma de la langue de la base, telles quelles (D5, D8) : le même texte pour toutes les
    cellules d'une technique.

    Raises:
        CelluleError: le prompt n'a plus l'empreinte fixée à la création de la campagne.
    """
    prompt = _prompt(dossier, schema, consigne)
    if empreinte is not None and hashlib.sha256(prompt.encode("utf-8")).hexdigest() != empreinte:
        raise CelluleError(
            f"{CONSIGNES[consigne]} ou {FICHES[schema]} changées depuis la création de la "
            "campagne (protocole gelé, D7)"
        )
    return prompt


def empreinte_recherche(fichier: Path = RECHERCHE) -> str:
    """SHA-256 de la requête de recherche des cellules GraphRAG, telle qu'elles l'envoient (D6) :
    D7 la gèle comme le prompt."""
    return hashlib.sha256(fichier.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def requete_de_recherche(empreinte: str | None = None, fichier: Path = RECHERCHE) -> str:
    """La requête de recherche, telle quelle, commentaires compris (D6).

    Raises:
        CelluleError: la requête n'a plus l'empreinte fixée à la création de la campagne.
    """
    requete = fichier.read_text(encoding="utf-8")
    if empreinte is not None and hashlib.sha256(requete.encode("utf-8")).hexdigest() != empreinte:
        raise CelluleError(
            f"{fichier.name} changée depuis la création de la campagne (protocole gelé, D7)"
        )
    return requete


def _prompt(dossier: Path, schema: str, consigne: str) -> str:
    texte = (dossier / CONSIGNES[consigne]).read_text(encoding="utf-8")
    fiche = (dossier / FICHES[schema]).read_text(encoding="utf-8")
    return f"{texte}\n\n{fiche}"


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
    if brut.get("schema", "fr") not in FICHES:
        raise ValueError(f"schema : {' ou '.join(FICHES)} attendu, pas {brut['schema']!r}")
    empreinte = _empreinte(brut, "empreinte_prompt")
    vecteurs = _vecteurs(brut.get("vecteurs", []))
    if vecteurs and len(vecteurs) != len(questions):
        raise ValueError(
            f"vecteurs : un par question attendu, {len(vecteurs)} pour {len(questions)} questions"
        )
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
        schema=brut.get("schema", "fr"),
        empreinte_prompt=empreinte,
        vecteurs=vecteurs,
        empreinte_recherche=_empreinte(brut, "empreinte_recherche"),
    )


def _empreinte(brut: dict[str, Any], cle: str) -> str | None:
    """Une empreinte de la commande : un SHA-256 en hexadécimal, ou rien."""
    empreinte = brut.get(cle)
    if empreinte is not None and not (
        isinstance(empreinte, str) and EMPREINTE.fullmatch(empreinte)
    ):
        raise ValueError(f"{cle} : un SHA-256 en hexadécimal attendu, pas {empreinte!r}")
    return empreinte


def _vecteurs(brut: Any) -> tuple[tuple[float, ...], ...]:
    """Les vecteurs d'une commande : une liste de listes de nombres finis, en flottants (JSON écrit
    1 pour 1.0)."""
    if not isinstance(brut, list):
        raise TypeError(f"vecteurs : une liste attendue, pas {type(brut).__name__}")
    vecteurs = []
    for vecteur in brut:
        if not isinstance(vecteur, list):
            raise TypeError(f"vecteur : une liste attendue, pas {type(vecteur).__name__}")
        if not vecteur:
            raise ValueError("vecteur vide")
        if not all(isinstance(x, int | float) and not isinstance(x, bool) for x in vecteur):
            raise TypeError("vecteur : des nombres attendus")
        if not all(math.isfinite(x) for x in vecteur):
            raise ValueError("vecteur : des nombres finis attendus")
        vecteurs.append(tuple(float(x) for x in vecteur))
    return tuple(vecteurs)


def _plafonds(brut: Any) -> Plafonds:
    valeurs = dict(brut or {})
    if "budget_usd" in valeurs:
        valeurs["budget_usd"] = Decimal(str(valeurs["budget_usd"]))
    return Plafonds(**valeurs)
