"""Ce que la fiche de schéma affirme, vérifié sur la base par questions/fiche.cypher (spec 002,
T7.3).

Sans base : chaque requête cite une phrase exacte de la fiche (« // fiche : « … » »), les valeurs
qu'elle recopie (valeurFiche, nombreFiche) sont celles de cette phrase, dans son ordre, et chaque
ligne des sections Nœuds et Valeurs possibles, comme chaque motif de la section Relations, a sa
vérification. Une fiche corrigée sans sa vérification, ou l'inverse, fait échouer ces tests ;
scripts/questions.sh --exemples rejoue ensuite tout sur la base.
"""

import ast
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
FICHE = (RACINE / "questions" / "fiche-schema.md").read_text(encoding="utf-8")
CYPHER = (RACINE / "questions" / "fiche.cypher").read_text(encoding="utf-8")

type Valeur = str | int | float | bool | list[str | float]


@dataclass(frozen=True)
class Verification:
    """Une requête de fiche.cypher : la phrase de la fiche qu'elle prouve, les valeurs qu'elle en
    recopie."""

    texte: str
    phrase: str | None
    valeurs: tuple[Valeur, ...] | None
    nombre: int | None


def verifications(cypher: str = CYPHER) -> list[Verification]:
    """Découpe fiche.cypher en requêtes (« ; » en fin de ligne) et lit, dans chacune, sa phrase et
    ses valeurs."""
    resultat: list[Verification] = []
    for texte in re.split(r";[ \t]*\n", cypher):
        if "RETURN" not in texte:
            continue
        phrases = re.findall(r"^// fiche : « (.*) »$", texte, re.MULTILINE)
        assert len(phrases) <= 1, f"une phrase par requête : {phrases}"
        liste = re.search(r"UNWIND (\[.*?\]) AS valeurFiche", texte, re.DOTALL)
        nombre = re.search(r"(\d+) AS nombreFiche", texte)
        resultat.append(
            Verification(
                texte=texte,
                phrase=phrases[0] if phrases else None,
                valeurs=lire_liste(liste.group(1)) if liste else None,
                nombre=int(nombre.group(1)) if nombre else None,
            )
        )
    return resultat


def lire_liste(litteral: str) -> tuple[Valeur, ...]:
    """Une liste littérale de Cypher (textes entre apostrophes droites, entiers, booléens)."""
    python = re.sub(r"\btrue\b", "True", re.sub(r"\bfalse\b", "False", litteral))
    valeurs = ast.literal_eval(python)
    assert isinstance(valeurs, list)
    return tuple(valeurs)


def section(titre: str, fiche: str = FICHE) -> str:
    """Le texte d'une section « ## titre » de la fiche, jusqu'à la suivante."""
    trouve = re.search(
        rf"^## {re.escape(titre)}\n(.*?)(?=^## |\Z)", fiche, re.MULTILINE | re.DOTALL
    )
    assert trouve is not None, titre
    return trouve.group(1)


def lignes(titre: str, fiche: str = FICHE) -> list[str]:
    """Les lignes d'une section, puces ôtées."""
    return [
        ligne.removeprefix("- ") for ligne in section(titre, fiche).splitlines() if ligne.strip()
    ]


# --- Ce que chaque phrase de la fiche affirme -------------------------------------------------

type Attendu = tuple[tuple[Valeur, ...], int | None]


def noeud(phrase: str, fiche: str) -> Attendu | None:
    """« `Label` : … (1 025) ; propriétés `a`, `b`… » : les propriétés et le nombre de nœuds."""
    trouve = re.match(r"`\w+` : .*?\((\d[\d ]*)\).*?[pP]ropriétés (.*)$", phrase)
    if trouve is None:
        return None
    return tuple(re.findall(r"`(\w+)`", trouve.group(2))), int(trouve.group(1).replace(" ", ""))


def liste_simple(phrase: str, fiche: str) -> Attendu | None:
    """« `Type.nom` : Acier, Combat… » : les valeurs, séparées par des virgules."""
    trouve = re.match(r"`(?:Type\.nom|Attaque\.categorie)` : (.*)\.$", phrase)
    return (tuple(trouve.group(1).split(", ")), None) if trouve else None


def methodes(phrase: str, fiche: str) -> Attendu | None:
    """Les méthodes nommées, et leur nombre total avec les rares."""
    if not phrase.startswith("`APPREND.methodes`"):
        return None
    nommees = tuple(re.findall(r"« ([^»]+) »", phrase))
    rares = re.search(r"et (\d+) méthodes rares", phrase)
    assert rares is not None
    return nommees, len(nommees) + int(rares.group(1))


def facteurs(phrase: str, fiche: str) -> Attendu | None:
    """« `facteur` : 2.0 (`SUPER_EFFICACE_CONTRE`)… » : chaque type de relation et son facteur."""
    if not phrase.startswith("`facteur`"):
        return None
    return tuple([t, float(f)] for f, t in re.findall(r"(\d\.\d) \(`(\w+)`\)", phrase)), None


def rangs(phrase: str, fiche: str) -> Attendu | None:
    """« `A_LE_TYPE.rang` : 1 ou 2. »"""
    if not phrase.startswith("`A_LE_TYPE.rang` : "):
        return None
    return tuple(int(x) for x in re.findall(r"\d+", phrase.split(" : ", 1)[1])), None


def booleens(phrase: str, fiche: str) -> Attendu | None:
    """« … : vrai ou faux. »"""
    if not phrase.endswith(" : vrai ou faux."):
        return None
    return (True, False), None


def labels(phrase: str, fiche: str) -> Attendu | None:
    """La section Nœuds : un label par puce."""
    if phrase != "## Nœuds":
        return None
    return tuple(re.findall(r"^- `(\w+)` :", section("Nœuds", fiche), re.MULTILINE)), None


def motifs(phrase: str, fiche: str) -> Attendu | None:
    """La section Relations : chaque motif en liste (label de départ, type, label d'arrivée, puis
    les clés), une par type quand la fiche en réunit plusieurs (A|B|C)."""
    if phrase != "## Relations":
        return None
    resultat: list[Valeur] = []
    for motif in re.findall(r"`(\(:\w+\)-\[:[^`]+\]->\(:\w+\))`", section("Relations", fiche)):
        decoupe = re.fullmatch(r"\(:(\w+)\)-\[:([\w|]+)(?: \{([^}]*)\})?\]->\(:(\w+)\)", motif)
        assert decoupe is not None, motif
        de, types, proprietes, vers = decoupe.groups()
        cles: list[str | float] = list(re.findall(r"\w+", proprietes or ""))
        resultat += [[de, t, vers, *cles] for t in types.split("|")]
    return tuple(resultat), None


LECTEURS: tuple[Callable[[str, str], Attendu | None], ...] = (
    noeud,
    liste_simple,
    methodes,
    facteurs,
    rangs,
    booleens,
    labels,
    motifs,
)


def attendu(phrase: str, fiche: str = FICHE) -> Attendu | None:
    """Ce que la phrase affirme, lu par le seul lecteur qui la reconnaît ; None si elle n'a pas de
    valeurs."""
    lus = [lu for lecteur in LECTEURS if (lu := lecteur(phrase, fiche)) is not None]
    assert len(lus) <= 1, f"plusieurs lecteurs pour : {phrase}"
    return lus[0] if lus else None


# --- Tests -------------------------------------------------------------------------------------


def test_chaque_requete_cite_une_phrase_ou_informe() -> None:
    # Une requête sans phrase de la fiche n'est qu'une information (attendu vide, sans verdict).
    for verification in verifications():
        if verification.phrase is None:
            assert re.search(r"RETURN '[^'|]*\|\|", verification.texte), verification.texte


def test_phrases_citees_dans_la_fiche() -> None:
    for verification in verifications():
        if verification.phrase is not None:
            assert verification.phrase in FICHE, verification.phrase


@pytest.mark.parametrize(
    "verification",
    [v for v in verifications() if v.valeurs is not None or v.nombre is not None],
    ids=lambda v: (v.phrase or "")[:40],
)
def test_valeurs_recopiees_de_la_phrase(verification: Verification) -> None:
    assert verification.phrase is not None
    lu = attendu(verification.phrase)
    assert lu is not None, f"aucun lecteur pour : {verification.phrase}"
    valeurs, nombre = lu
    assert verification.valeurs == valeurs
    assert verification.nombre == nombre


@pytest.mark.parametrize("titre", ["Nœuds", "Valeurs possibles"])
def test_chaque_ligne_verifiee(titre: str) -> None:
    phrases = [v.phrase for v in verifications() if v.phrase is not None]
    for ligne in lignes(titre):
        reste = ligne
        for phrase in phrases:
            reste = reste.replace(phrase, "")
        assert reste.strip(" .;") == "", f"{titre} : non vérifié : {reste!r}"


def test_chaque_motif_verifie() -> None:
    relations = [v for v in verifications() if v.phrase == "## Relations"]
    assert len(relations) == 1
    lu = attendu("## Relations")
    assert lu is not None
    assert len(lu[0]) == 11
    assert relations[0].valeurs == lu[0]


# --- Les tests voient-ils une fiche corrigée sans sa vérification ? ----------------------------


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        pytest.param("Ténèbres, Vol.", "Ténèbres, Vol, Lumière.", id="type-ajoute"),
        pytest.param("et 4 méthodes rares", "et 5 méthodes rares", id="methodes-rares"),
        pytest.param("(1 351)", "(1 352)", id="nombre-de-formes"),
        pytest.param("`statVitesse`.", "`statVitesse`, `generation`.", id="propriete-ajoutee"),
        pytest.param("1 ou 2.", "1, 2 ou 3.", id="rang"),
        # Spec 003, D8 : la fiche revenue à sa ligne d'avant les vecteurs.
        pytest.param(
            " ; `embedding`, le vecteur de son texte (voir les règles)", "", id="vecteur-retire"
        ),
    ],
)
def test_fiche_changee_sans_sa_verification(avant: str, apres: str) -> None:
    assert FICHE.count(avant) == 1
    fiche = FICHE.replace(avant, apres)
    ecarts = []
    for verification in verifications():
        if verification.phrase is None or verification.phrase in fiche:
            continue
        ecarts.append(verification.phrase)
    assert ecarts, "la phrase changée devrait ne plus figurer dans la fiche"


def test_motif_ajoute_sans_sa_verification() -> None:
    assert FICHE.count("\n## Règles") == 1
    fiche = FICHE.replace(
        "\n## Règles", "- `(:Pokemon)-[:A_POUR_ICONE]->(:Icone)` : une image.\n\n## Règles"
    )
    lu = attendu("## Relations", fiche)
    relations = [v for v in verifications() if v.phrase == "## Relations"]
    assert lu is not None
    assert len(lu[0]) == 12
    assert relations[0].valeurs != lu[0]


def test_valeur_recopiee_differente() -> None:
    # Une valeur mal recopiée dans fiche.cypher : sa requête, et elle seule, s'écarte de sa phrase.
    cypher = CYPHER.replace(
        "'Ténèbres', 'Vol'] AS valeurFiche", "'Ténèbres', 'Vole'] AS valeurFiche"
    )
    assert cypher != CYPHER
    fautives = []
    for verification in verifications(cypher):
        lu = attendu(verification.phrase) if verification.phrase else None
        if lu is not None and lu != (verification.valeurs, verification.nombre):
            fautives.append(verification.phrase)
    assert len(fautives) == 1
    assert (fautives[0] or "").startswith("`Type.nom` : ")
