"""Requête de recherche de la technique 3 (spec 003, plan D6) : questions/recherche.cypher, que la
cellule GraphRAG lance par read-cypher avec le vecteur de la question ; son résultat est le contexte
du seul appel au LLM (ADR-0018).

Sans base, sur son texte : préfixe CYPHER 25 ; SEARCH dans l'index des descriptions que crée
cypher/00-contraintes.cypher, 60 descriptions ; regroupement par espèce, 20 au plus, 2 descriptions
chacune ; parcours de chaque espèce ; jamais de vecteur ni de nœud entier dans le résultat ; aucun
texte en dur ni valeur du banc. EXPLAIN et forme du résultat sur la base : banc essai-recherche
(T8.2).
"""

import re
from dataclasses import dataclass
from pathlib import Path

import pytest
from test_contamination import INTERDITES, contient, mots

from banc.traduction import Jeton, jetons

RACINE = Path(__file__).resolve().parents[2]
RECHERCHE = (RACINE / "questions" / "recherche.cypher").read_text(encoding="utf-8")
CONTRAINTES = (RACINE / "cypher" / "00-contraintes.cypher").read_text(encoding="utf-8")
# Ce qui clôt un RETURN, hors de ses parenthèses, crochets et accolades.
FIN_DE_RETURN = frozenset({"ORDER", "SKIP", "LIMIT", "UNION"})


@dataclass(frozen=True)
class Element:
    """Un élément d'un RETURN : son expression, jetons séparés d'une espace, et son alias."""

    expression: str
    alias: str | None


def significatifs(cypher: str = RECHERCHE) -> list[Jeton]:
    """Les jetons qui portent la requête : ni espaces ni commentaires."""
    return [j for j in jetons(cypher) if j.genre not in {"espace", "commentaire"}]


def code(cypher: str = RECHERCHE) -> str:
    """La requête sans ses commentaires, chaque jeton séparé du suivant d'une espace."""
    return " ".join(j.texte for j in significatifs(cypher))


def variables_de_noeud(cypher: str = RECHERCHE) -> set[str]:
    """Les variables liées à un nœud : celles d'un motif « (x:Label) »."""
    return set(re.findall(r"\( (\w+) : [A-Z]\w*", code(cypher)))


def retours(cypher: str = RECHERCHE) -> list[tuple[int, list[Element]]]:
    """Chaque RETURN, avec sa profondeur (0 : la requête ; plus : une sous-requête entre
    accolades, COLLECT { … }) et ses éléments."""
    resultat: list[tuple[int, list[Element]]] = []
    tous = significatifs(cypher)
    profondeur = 0
    for rang, jeton in enumerate(tous):
        if jeton.texte in "([{":
            profondeur += 1
        elif jeton.texte in ")]}":
            profondeur -= 1
        elif (jeton.nom or "").upper() == "RETURN":
            resultat.append((profondeur, _elements(tous[rang + 1 :])))
    return resultat


def _elements(suite: list[Jeton]) -> list[Element]:
    """Les éléments d'un RETURN, jusqu'à ce qui le clôt."""
    elements: list[list[Jeton]] = [[]]
    profondeur = 0
    for jeton in suite:
        if profondeur == 0 and (
            (jeton.nom or "").upper() in FIN_DE_RETURN or jeton.texte in {"}", ";"}
        ):
            break
        if jeton.texte in "([{":
            profondeur += 1
        elif jeton.texte in ")]}":
            profondeur -= 1
        if profondeur == 0 and jeton.texte == ",":
            elements.append([])
        else:
            elements[-1].append(jeton)
    resultat = []
    for element in elements:
        alias, expression = None, element
        if len(element) > 2 and (element[-2].nom or "").upper() == "AS":
            alias, expression = element[-1].texte, element[:-2]
        resultat.append(Element(" ".join(j.texte for j in expression), alias))
    return resultat


def fautes(cypher: str = RECHERCHE) -> list[str]:
    """Ce qui mettrait un nœud entier ou un vecteur dans le résultat : un RETURN (sous-requêtes
    comprises) qui rend une variable de nœud seule, collect() d'une variable de nœud,
    properties(), keys(), une projection .*, la propriété embedding."""
    noeuds = variables_de_noeud(cypher)
    trouvees = [e.expression for _, elements in retours(cypher) for e in elements]
    resultat = [expression for expression in trouvees if expression in noeuds]
    texte = code(cypher)
    resultat += re.findall(rf"(?i)\bcollect \( (?:{'|'.join(noeuds)}) \)", texte)
    resultat += re.findall(r"(?i)\b(?:properties|keys) \(", texte)
    resultat += re.findall(r"\{ \. \*", texte)
    resultat += [j.texte for j in significatifs(cypher) if j.nom == "embedding"]
    return resultat


def principal() -> list[Element]:
    """Les éléments du RETURN de la requête (profondeur 0) : un enregistrement par espèce."""
    (elements,) = [elements for profondeur, elements in retours() if profondeur == 0]
    return elements


# --- Tests -------------------------------------------------------------------------------------


def test_cypher_25_en_tete() -> None:
    # SEARCH n'existe qu'en Cypher 25 (Cypher Manual, « Cypher 25 only », Neo4j 2026.01).
    assert code().startswith("CYPHER 25 MATCH ")


def test_recherche_dans_l_index_des_descriptions() -> None:
    # D6 : les 60 descriptions les plus proches du vecteur de la question, dans l'index que crée
    # 00-contraintes.cypher ; le vecteur en paramètre, seul paramètre de la requête.
    index = re.search(r"CREATE VECTOR INDEX (\w+)", CONTRAINTES)
    trouve = re.search(
        r"^CYPHER 25 MATCH \( (\w+) : Description \) SEARCH \1 IN \( VECTOR INDEX (\w+) "
        r"FOR \$vecteur LIMIT (\d+) \) SCORE AS (\w+) ",
        code(),
    )
    assert index is not None
    assert trouve is not None
    assert trouve.group(2) == index.group(1) == "descriptions_texte"
    assert int(trouve.group(3)) == 60
    assert {j.texte for j in significatifs() if j.genre == "parametre"} == {"$vecteur"}


def test_vingt_especes_deux_descriptions_chacune() -> None:
    # D6 : regroupées par espèce (A_POUR_DESCRIPTION), classées par meilleur score, 20 au plus,
    # chacune avec ses 2 meilleures descriptions (texte, jeux, score).
    texte = code()
    regroupement = re.search(
        r"MATCH \( (\w+) : Pokemon \) - \[ : A_POUR_DESCRIPTION \] -> \( (\w+) \) "
        r"WITH \1 , \2 , (\w+) ORDER BY \3 DESC "
        r"WITH \1 , collect \( \{ texte : \2 \. texte , jeux : \2 \. jeux , "
        r"score : [^}]*\3[^}]*\} \) \[ \.\. (\d+) \] AS descriptions , max \( \3 \) AS (\w+) "
        r"ORDER BY \5 DESC LIMIT (\d+) ",
        texte,
    )
    assert regroupement is not None
    assert (int(regroupement.group(4)), int(regroupement.group(6))) == (2, 20)
    # L'ordre des espèces, défait par le parcours qui suit, se refait sur le meilleur score.
    assert texte.endswith(f"ORDER BY {regroupement.group(5)} DESC")


def test_parcours_de_chaque_espece() -> None:
    # D6 : nom, catégorie, types de la forme par défaut (par rang), talents (caché ou non), les 6
    # statistiques, espèce d'origine et évolutions directes ; puis les descriptions.
    noms = {j.nom for j in significatifs() if j.genre == "nom"}
    assert {
        "A_POUR_FORME_PAR_DEFAUT", "A_LE_TYPE", "rang", "A_LE_TALENT", "cache", "EVOLUE_EN",
        "statPv", "statAttaque", "statDefense", "statAttaqueSpeciale", "statDefenseSpeciale",
        "statVitesse",
    } <= noms  # fmt: skip
    texte = code()
    trouve = re.search(r"MATCH \( (\w+) : Pokemon \) - \[ : A_POUR_DESCRIPTION \]", texte)
    assert trouve is not None
    espece = trouve.group(1)
    # Chaque sous-requête, bornée à ses accolades : types par rang, talents avec « caché ».
    assert re.search(
        r"COLLECT \{ MATCH [^{}]* : A_LE_TYPE \] [^{}]* RETURN \w+ \. nom ORDER BY \w+ \. rang \}",
        texte,
    )
    assert re.search(
        r"COLLECT \{ MATCH [^{}]* : A_LE_TALENT \] [^{}]* RETURN \{ nom : \w+ \. nom , "
        r"cache : \w+ \. cache \}",
        texte,
    )
    # Les deux sens d'EVOLUE_EN : l'espèce d'origine, puis les évolutions directes.
    assert re.search(rf"\( \w+ : Pokemon \) - \[ : EVOLUE_EN \] -> \( {espece} \)", texte)
    assert re.search(rf"\( {espece} \) - \[ : EVOLUE_EN \] -> \( \w+ : Pokemon \)", texte)
    assert [e.alias or e.expression for e in principal()] == [
        "espece", "categorie", "types", "talents", "statistiques", "evolueDe", "evolueEn",
        "descriptions",
    ]  # fmt: skip


def test_jamais_de_vecteur_ni_de_noeud_entier() -> None:
    # D6 : ni embedding ni un nœud entier dans le résultat : 3 072 nombres par description
    # rempliraient le contexte. La fiche le dit aussi aux techniques qui écrivent du Cypher (D8).
    assert fautes() == []
    assert len(retours()) == 5  # le contrôle voit la requête et ses quatre sous-requêtes


@pytest.mark.parametrize(
    ("avant", "apres"),
    [
        pytest.param("RETURN p.nom AS espece", "RETURN p AS espece", id="espece-entiere"),
        pytest.param("RETURN t.nom ORDER BY r.rang", "RETURN t ORDER BY r.rang", id="type-entier"),
        pytest.param("jeux: d.jeux,", "jeux: d.jeux, vecteur: d.embedding,", id="vecteur"),
        pytest.param(
            "collect({texte: d.texte, jeux: d.jeux, score: round(score, 4)})",
            "collect(d)",
            id="descriptions-entieres",
        ),
        pytest.param(
            "RETURN avant.nom ORDER BY avant.nom",
            "RETURN properties(avant) ORDER BY avant.nom",
            id="proprietes",
        ),
    ],
)
def test_le_controle_voit_un_noeud_ou_un_vecteur(avant: str, apres: str) -> None:
    assert RECHERCHE.count(avant) == 1
    assert fautes(RECHERCHE.replace(avant, apres))


def test_le_controle_voit_une_projection_entiere() -> None:
    statistiques = re.search(r"f \{[^}]*\} AS statistiques", RECHERCHE)
    assert statistiques is not None
    assert fautes(RECHERCHE.replace(statistiques.group(), "f {.*} AS statistiques"))


def test_aucune_valeur_du_banc() -> None:
    # D6 : les seuils (60, 20, 2) viennent des données, pas des questions du banc ; la requête ne
    # porte aucun texte en dur, ni entité ni valeur du banc, commentaires compris (ADR-0009).
    assert [j.texte for j in significatifs() if j.genre == "chaine"] == []
    assert sorted(v for v in INTERDITES if contient(mots(RECHERCHE), mots(v))) == []
