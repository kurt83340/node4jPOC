"""Fiche de schéma anglaise (spec 002, T6.3 ; plan D8), sans base : questions/fiche-schema.en.md,
tirée de la fiche française par la table.

Elle va telle quelle dans le prompt des passes anglaises : seuls les identifiants du schéma y
changent, la prose, les valeurs et les alias restent ceux de la fiche française. Son code ne porte
plus aucun identifiant français, d'après la liste tirée d'ARCHITECTURE § 5 (schema_francais).
"""

import re

from schema_francais import NOM, francais, places_du_schema

from banc import anglais, correspondance
from banc.correspondance import GENRES
from banc.traduction import traduire_fiche

TABLE = correspondance.charger()
FRANCAIS = francais()
FICHE_FR = anglais.FICHE_FR.read_text()
FICHE_EN = anglais.FICHE_EN.read_text()
BLOC = re.compile(r"^```cypher\n(.*?)^```$", re.MULTILINE | re.DOTALL)
EN_LIGNE = re.compile(r"`([^`\n]+)`")


def code(fiche: str) -> tuple[list[str], list[str]]:
    """Les blocs ```cypher d'une fiche, puis son code en ligne hors des blocs."""
    return BLOC.findall(fiche), EN_LIGNE.findall(BLOC.sub("", fiche))


def identifiants(fiche: str) -> set[str]:
    """Les noms du code d'une fiche : chaque mot du code en ligne (un identifiant, Label.clé, un
    motif), et ceux des blocs aux places du schéma (un alias n'en est pas une)."""
    blocs, en_ligne = code(fiche)
    mots = {mot for morceau in en_ligne for mot in re.findall(NOM, morceau)}
    return mots.union(*(places_du_schema(bloc) for bloc in blocs))


def test_a_jour() -> None:
    assert traduire_fiche(FICHE_FR, TABLE, "en") == FICHE_EN, "relancer python -m banc anglais"


def test_aucun_identifiant_francais() -> None:
    restes = identifiants(FICHE_EN) & FRANCAIS
    assert not restes, sorted(restes)


def test_le_controle_voit_la_fiche_francaise() -> None:
    # Le contrôle ne passe pas à vide : sur la fiche française, il voit les identifiants du schéma.
    vus = identifiants(FICHE_FR) & FRANCAIS
    assert {"Forme", "Attaque", "A_LE_TYPE", "nom", "rang", "methodes", "noms_plein_texte"} <= vus


def test_seul_le_code_change() -> None:
    def prose(fiche: str) -> str:
        return EN_LIGNE.sub("‹code›", BLOC.sub("‹bloc›", fiche))

    assert prose(FICHE_EN) == prose(FICHE_FR)
    assert len(code(FICHE_EN)[0]) == len(code(FICHE_FR)[0]) == 8


def test_seuls_des_identifiants_changent() -> None:
    avant = re.findall(r"\w+|\W", FICHE_FR)
    apres = re.findall(r"\w+|\W", FICHE_EN)
    assert len(avant) == len(apres)
    for fr, en in {(a, b) for a, b in zip(avant, apres, strict=True) if a != b}:
        assert fr in FRANCAIS, fr
        assert any(TABLE.nom(genre, fr, "en") == en for genre in GENRES), (fr, en)


def test_formes_du_code_en_ligne() -> None:
    _, en_ligne = code(FICHE_EN)
    for attendu in (
        "Move.category",
        "LEARNS.methods",
        "HAS_TYPE.slot",
        "HAS_ABILITY.isHidden",
        "Form.isDefault",
        "names_fulltext",
        "(:Type)-[:SUPER_EFFECTIVE_AGAINST|NOT_VERY_EFFECTIVE_AGAINST|NO_EFFECT_AGAINST {factor}]->"
        "(:Type)",
        "(:Form)-[:LEARNS {methods, level}]->(:Move)",
        "gengar",
        "read-cypher",
    ):
        assert attendu in en_ligne, attendu


def test_aller_retour() -> None:
    assert traduire_fiche(FICHE_EN, TABLE, "fr") == FICHE_FR
