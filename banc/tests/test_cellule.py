"""Commande d'une conversation (banc.cellule) : ce que l'orchestration envoie à une cellule, en JSON
sur stdin, et que la cellule refuse au moindre doute (T4.1)."""

import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from banc.cellule import (
    LANCEUR,
    QUESTIONS,
    CelluleError,
    Commande,
    Plafonds,
    commande_json,
    consigne_et_fiche,
    lire_commande,
)

COMMANDE = Commande(
    campagne="pilote",
    passe=2,
    essai=3,
    questions=(("Q2", "Mon équipe : Pikachu.\n\nQui remplacer ?"), ("Q18", "Et ensuite ?")),
    traces=Path("/tmp/traces"),
    plafonds=Plafonds(delai_s=90.0, tours=5, budget_usd=Decimal("0.35"), connexion_s=10.0),
    cache_1h=True,
    serveur=("/opt/faux/serveur", "--option"),
    cli=Path("/opt/faux/claude"),
)


def brut(**changes: Any) -> str:
    """La commande type en JSON, avec quelques champs changés (None : retiré)."""
    champs = json.loads(commande_json(COMMANDE)) | changes
    return json.dumps({cle: valeur for cle, valeur in champs.items() if valeur is not None})


def test_aller_retour() -> None:
    assert lire_commande(commande_json(COMMANDE)) == COMMANDE


def test_budget_exact() -> None:
    # Le budget passe en texte : aucun arrondi de flottant entre l'orchestration et la cellule.
    assert json.loads(commande_json(COMMANDE))["plafonds"]["budget_usd"] == "0.35"
    plafonds = {"budget_usd": "0.1", "delai_s": 1, "tours": 1, "connexion_s": 1}
    assert lire_commande(brut(plafonds=plafonds)).plafonds.budget_usd == Decimal("0.1")


def test_valeurs_par_defaut() -> None:
    commande = lire_commande(brut(plafonds=None, cache_1h=None, serveur=None, cli=None))
    assert (commande.plafonds, commande.cache_1h) == (Plafonds(), False)
    assert (commande.serveur, commande.cli) == ((str(LANCEUR),), None)
    # ADR-0009 et choix de Julien (T4.1) : 180 s et 10 tours par question, 0,50 $ par conversation.
    assert Plafonds() == Plafonds(180.0, 10, Decimal("0.50"), 30.0)


@pytest.mark.parametrize(
    ("changes", "motif"),
    [
        ({"campagne": None}, "'campagne'"),
        ({"plafond": {"delai_s": 1}}, r"clés inconnues \['plafond'\]"),
        ({"questions": []}, "questions : une liste"),
        ({"questions": [["question-2", "texte"]]}, "questions : une liste"),
        ({"questions": [["Q2", "   "]]}, "questions : une liste"),
        ({"serveur": ["scripts/mcp-neo4j.sh"]}, "chemin absolu attendu"),
        ({"serveur": ["/opt/serveur", ""]}, "serveur : une commande attendue"),
        ({"passe": "1"}, "passe : un entier attendu"),
        ({"essai": True}, "essai : un entier attendu"),
        ({"traces": 3}, "campagne et traces : du texte attendu"),
        ({"cache_1h": "oui"}, "cache_1h : vrai ou faux attendu"),
        ({"plafonds": {"tours": 0}}, "plafonds invalides"),
        ({"plafonds": {"delai_s": 0}}, "plafonds invalides"),
        ({"plafonds": {"connexion_s": -1}}, "plafonds invalides"),
        ({"plafonds": {"budget_usd": "0"}}, "budget invalide"),
        ({"plafonds": {"budget": "1"}}, "unexpected keyword argument 'budget'"),
    ],
    ids=lambda valeur: valeur if isinstance(valeur, str) else None,
)
def test_commande_refusee(changes: dict[str, Any], motif: str) -> None:
    with pytest.raises(CelluleError, match=motif):
        lire_commande(brut(**changes))


@pytest.mark.parametrize("texte", ["", "{"])
def test_json_illisible(texte: str) -> None:
    with pytest.raises(CelluleError, match="commande illisible"):
        lire_commande(texte)


@pytest.mark.parametrize("texte", ["[]", '"commande"', "3"])
def test_pas_un_objet(texte: str) -> None:
    with pytest.raises(CelluleError, match="un objet JSON attendu"):
        lire_commande(texte)


def test_plafonds_aux_bornes() -> None:
    # Les plus petites valeurs permises : une borne se teste pile dessus.
    Plafonds(delai_s=0.001, tours=1, budget_usd=Decimal("0.000001"), connexion_s=0.001)


def test_consigne_puis_fiche() -> None:
    # Telles quelles (D5), dans cet ordre, séparées par une ligne vide.
    consigne = (QUESTIONS / "consigne.md").read_text(encoding="utf-8")
    fiche = (QUESTIONS / "fiche-schema.md").read_text(encoding="utf-8")
    assert consigne_et_fiche() == f"{consigne}\n\n{fiche}"
    assert consigne_et_fiche().startswith("# Consigne")
