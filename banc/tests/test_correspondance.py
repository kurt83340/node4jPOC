"""Table de correspondance du schéma anglais (spec 002, T6.1 ; plan D8), sans base.

La table couvre tout le schéma, d'après des listes qui ne viennent pas d'elle (schema_francais) :
les labels, types et clés d'ARCHITECTURE § 5, les noms de cypher/00-contraintes.cypher. Les
fichiers qu'on en tire (carte de paramètres, contraintes en anglais) sont à jour. Chaque règle de
validation refuse seule une table qui ne viole qu'elle.
"""

import re
from pathlib import Path

import pytest
from schema_francais import schema_francais

from banc import anglais, correspondance
from banc.correspondance import Correspondance, CorrespondanceError

TABLE = correspondance.charger()


def test_table_couvre_le_schema() -> None:
    attendu = schema_francais()
    assert attendu["labels"] == {"Pokemon", "Forme", "Type", "Attaque", "Talent", "Description"}
    assert len(attendu["relations"]) == 10
    assert len(attendu["proprietes"]) == 22
    assert len(attendu["index"]) == 12
    for genre, noms in attendu.items():
        traduits = set(TABLE.vers_anglais[genre])
        assert traduits | TABLE.communs[genre] == noms, genre


def test_embedding_commun_aux_deux_langues() -> None:
    # Le vecteur d'une Description (spec 003, T5.2) : même nom dans les deux schémas, permis par le
    # balayage d'une base anglaise qui porte des vecteurs.
    assert "embedding" in TABLE.communs["proprietes"]
    assert "'embedding'" in anglais.balayage(TABLE)


def test_carte_a_jour() -> None:
    assert correspondance.CARTE.read_text() == correspondance.carte(TABLE)


def test_produits_a_jour() -> None:
    for chemin, texte in anglais.produits(TABLE).items():
        assert chemin.read_text() == texte, f"{chemin} : relancer python -m banc anglais"


def test_vers_le_francais_inverse_l_anglais() -> None:
    for genre in correspondance.GENRES:
        en, fr = TABLE.sens("en")[genre], TABLE.sens("fr")[genre]
        assert {anglais: francais for francais, anglais in en.items()} == fr


def test_carte_porte_les_deux_sens() -> None:
    carte = correspondance.carte(TABLE)
    assert "{cartes: {\n  en: {\n" in carte
    assert "\n  fr: {\n" in carte
    assert "      Forme: 'Form',\n" in carte
    assert "      Form: 'Forme',\n" in carte
    # Les noms des index ne servent pas au renommage : contraintes.cypher les porte.
    assert "noms_plein_texte" not in carte


def test_traduction_d_un_nom() -> None:
    assert TABLE.nom("labels", "Attaque", "en") == "Move"
    assert TABLE.nom("labels", "Move", "fr") == "Attaque"
    assert TABLE.nom("labels", "Pokemon", "en") == "Pokemon"
    assert TABLE.nom("labels", "Inconnu", "en") is None


# --- Une règle de validation, une table qui ne viole qu'elle -----------------------------------

VALIDE = """
[labels]
Forme = "Form"
[relations]
APPREND = "LEARNS"
[proprietes]
nom = "name"
[index]
forme_id = "form_id"
[communs]
labels = ["Pokemon"]
relations = []
proprietes = ["id"]
index = ["pokemon_id"]
"""


def lire(tmp_path: Path, texte: str) -> Correspondance:
    fichier = tmp_path / "correspondance.toml"
    fichier.write_text(texte)
    return correspondance.charger(fichier)


def test_table_minimale_valide(tmp_path: Path) -> None:
    table = lire(tmp_path, VALIDE)
    assert table.nom("proprietes", "nom", "en") == "name"


@pytest.mark.parametrize(
    ("avant", "apres", "message"),
    [
        pytest.param('Forme = "Form"', 'Forme = "form"', "labels : 'form' mal formé", id="forme"),
        pytest.param(
            'nom = "name"',
            'nom = "name"\ntexte = "name"',
            "proprietes : 'name' en double",
            id="double",
        ),
        pytest.param(
            'Forme = "Form"',
            'Forme = "Talent"\nTalent = "Ability"',
            "labels : 'Talent' à la fois français et anglais",
            id="masque",
        ),
        pytest.param(
            'labels = ["Pokemon"]',
            'labels = ["Pokemon", "Forme"]',
            "labels : 'Forme' à la fois commun et traduit",
            id="commun-traduit",
        ),
        pytest.param(
            'forme_id = "form_id"',
            'forme_id = "form_id"\nnom = "nom_index"',
            "'nom' dans deux genres",
            id="deux-genres",
        ),
        pytest.param("[index]", "[indexes]", "section index absente", id="section"),
    ],
)
def test_table_refusee(tmp_path: Path, avant: str, apres: str, message: str) -> None:
    assert VALIDE.count(avant) == 1
    with pytest.raises(CorrespondanceError, match=re.escape(message)):
        lire(tmp_path, VALIDE.replace(avant, apres))
