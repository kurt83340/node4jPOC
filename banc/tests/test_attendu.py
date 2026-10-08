"""Réponses de référence (questions/attendu/) relues par le harnais : la sortie de cypher-shell en
format plain, un ou plusieurs tableaux par fichier."""

from pathlib import Path

import pytest

from banc.attendu import DOSSIER, AttenduError, analyser, feuilles, lire

ENTETE = "// PokéAPI 168b1e89467054cda2e7df43ccebbb69b459497a · q99.cypher\n"


def test_valeurs_typees() -> None:
    texte = ENTETE + (
        "attaque, puissance, precision, multiplicateur, valide, types, detail\n"
        '"Fracass’Tête", 150, NULL, 4.0, TRUE, ["Feu", "Vol"], '
        '[{type: "Plante", facteurFeu: 2.0}]\n'
    )
    [tableau] = analyser(texte)
    assert tableau.colonnes == (
        "attaque",
        "puissance",
        "precision",
        "multiplicateur",
        "valide",
        "types",
        "detail",
    )
    assert tableau.lignes == (
        {
            "attaque": "Fracass’Tête",
            "puissance": 150,
            "precision": None,
            "multiplicateur": 4.0,
            "valide": True,
            "types": ["Feu", "Vol"],
            "detail": [{"type": "Plante", "facteurFeu": 2.0}],
        },
    )


def test_plusieurs_tableaux() -> None:
    # Comme q13 : une seconde requête ouvre un second tableau, avec son propre en-tête.
    texte = ENTETE + (
        'attaque, pokemon\n"Zénith", 677\n"Lance-Flammes", 203\n'
        'attaqueOffensive, pokemon\n"Lance-Flammes", 203\n'
    )
    premier, second = analyser(texte)
    assert [ligne["attaque"] for ligne in premier.lignes] == ["Zénith", "Lance-Flammes"]
    assert second.colonnes == ("attaqueOffensive", "pokemon")


def test_ligne_de_donnees_et_non_d_en_tete() -> None:
    # Une ligne faite de booléens seuls n'est pas un en-tête : TRUE et FALSE sont des valeurs.
    [tableau] = analyser(ENTETE + "a, b\nTRUE, FALSE\n")
    assert tableau.lignes == ({"a": True, "b": False},)


def test_virgule_et_guillemet_dans_une_chaine() -> None:
    [tableau] = analyser(ENTETE + 'raison\n"coule des navires ; les marins, eux, fuient"\n')
    assert tableau.lignes[0]["raison"] == "coule des navires ; les marins, eux, fuient"
    [tableau] = analyser(ENTETE + 'raison\n"dit \\"oui\\""\n')
    assert tableau.lignes[0]["raison"] == 'dit "oui"'


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param('a, b\n"x"\n', id="champ-manquant"),
        pytest.param('a\n"x", "y"\n', id="champ-en-trop"),
        pytest.param('"x"\n', id="donnees-sans-en-tete"),
        pytest.param('a\n"x\n', id="chaine-non-fermee"),
        pytest.param("a\n[1, 2\n", id="liste-non-fermee"),
        pytest.param('a, b\n"x", quoi\n', id="valeur-inconnue"),
        # Une réponse de référence a toujours au moins une ligne : un tableau vide trahit une
        # requête qui ne rend rien, ou une ligne de valeurs lue comme un en-tête.
        pytest.param('a\nb\n"x"\n', id="tableau-sans-ligne"),
    ],
)
def test_reponse_mal_formee(texte: str) -> None:
    with pytest.raises(AttenduError):
        analyser(ENTETE + texte)


def test_entete_pokeapi_exige() -> None:
    with pytest.raises(AttenduError, match="PokéAPI"):
        analyser('a\n"x"\n')


def test_feuilles() -> None:
    # Toutes les valeurs simples, listes et dictionnaires dépliés : les tests de cohérence y
    # cherchent les valeurs attendues de banc.toml.
    ligne = '"Bulbizarre", [{type: "Plante", f: 2.0}, {type: "Poison"}]'
    [tableau] = analyser(ENTETE + f"p, t\n{ligne}\n")
    assert list(feuilles([tableau])) == ["Bulbizarre", "Plante", 2.0, "Poison"]


@pytest.mark.parametrize("fichier", sorted(DOSSIER.glob("q*.txt")), ids=lambda f: f.stem)
def test_reponses_du_depot(fichier: Path) -> None:
    # Les 27 réponses enregistrées par scripts/questions.sh se relisent sans erreur.
    tableaux = lire(fichier.stem)
    assert tableaux
    assert all(tableau.lignes for tableau in tableaux)


def test_question_sans_reponse() -> None:
    with pytest.raises(AttenduError, match="q10"):
        lire("q10")
