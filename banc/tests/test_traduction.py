"""Traduction du Cypher vers le schéma anglais, et retour (spec 002, T6.2 ; plan D8), sans base.

Règles, une par test : labels, types de relation, clés (après un point, dans la map d'un motif,
raccourci {rang} de la fiche compris), noms des contraintes et des index se traduisent ; alias,
variables, clés d'une map hors motif, paramètres, commentaires et littéraux restent tels quels, sauf
un littéral qui est en entier un identifiant du schéma.
"""

import pytest

from banc import correspondance
from banc.traduction import TraductionError, traduire

TABLE = correspondance.charger()


def en(cypher: str) -> str:
    return traduire(cypher, TABLE, "en")


@pytest.mark.parametrize(
    ("francais", "anglais"),
    [
        pytest.param("MATCH (a:Attaque) RETURN a", "MATCH (a:Move) RETURN a", id="label"),
        pytest.param("(:Forme)", "(:Form)", id="label-anonyme"),
        pytest.param("(:Pokemon)", "(:Pokemon)", id="label-commun"),
        pytest.param("()-[:A_LE_TYPE]->()", "()-[:HAS_TYPE]->()", id="type"),
        pytest.param("()-[r:APPREND]->()", "()-[r:LEARNS]->()", id="type-variable"),
        pytest.param(
            "(a)-[:EVOLUE_EN*1..]->(b)", "(a)-[:EVOLVES_INTO*1..]->(b)", id="type-longueur"
        ),
        pytest.param(
            "(:Type)<-[:SANS_EFFET_CONTRE]-(e)",
            "(:Type)<-[:NO_EFFECT_AGAINST]-(e)",
            id="type-entrant",
        ),
        pytest.param(
            "[e:SUPER_EFFICACE_CONTRE|PEU_EFFICACE_CONTRE|SANS_EFFET_CONTRE]",
            "[e:SUPER_EFFECTIVE_AGAINST|NOT_VERY_EFFECTIVE_AGAINST|NO_EFFECT_AGAINST]",
            id="types-alternatifs",
        ),
        pytest.param(
            "(n:Type|Pokemon|Forme|Talent|Attaque)",
            "(n:Type|Pokemon|Form|Ability|Move)",
            id="labels-alternatifs",
        ),
        pytest.param("WHERE n:Forme AND m:Talent", "WHERE n:Form AND m:Ability", id="predicat"),
        pytest.param("(n:`Forme`)", "(n:`Form`)", id="label-echappe"),
    ],
)
def test_labels_et_types(francais: str, anglais: str) -> None:
    assert en(francais) == anglais


@pytest.mark.parametrize(
    ("francais", "anglais"),
    [
        pytest.param("RETURN p.nom", "RETURN p.name", id="point"),
        pytest.param("RETURN p.nom AS nom", "RETURN p.name AS nom", id="point-alias"),
        pytest.param("e.facteur, r.rang, f.statPv", "e.factor, r.slot, f.statHp", id="points"),
        pytest.param("RETURN n {.nom, .id}", "RETURN n {.name, .id}", id="projection"),
        pytest.param("(:Pokemon {nom: 'Dracaufeu'})", "(:Pokemon {name: 'Dracaufeu'})", id="motif"),
        pytest.param("(:Pokemon {nom: nom})", "(:Pokemon {name: nom})", id="motif-variable"),
        pytest.param("(:Pokemon {nom: $nom})", "(:Pokemon {name: $nom})", id="motif-parametre"),
        pytest.param("(f {parDefaut: true})", "(f {isDefault: true})", id="motif-sans-label"),
        pytest.param("[r:A_LE_TYPE {rang: 1}]", "[r:HAS_TYPE {slot: 1}]", id="motif-relation"),
        pytest.param("[:A_LE_TYPE {rang}]", "[:HAS_TYPE {slot}]", id="raccourci-fiche"),
        pytest.param(
            "[:APPREND {methodes, niveau}]", "[:LEARNS {methods, level}]", id="raccourci-deux"
        ),
    ],
)
def test_cles(francais: str, anglais: str) -> None:
    assert en(francais) == anglais


@pytest.mark.parametrize(
    "inchange",
    [
        pytest.param("RETURN x AS nom, y AS categorie, z AS precision", id="alias"),
        pytest.param("UNWIND trouves AS nom WITH nom, nom IN trouves AS trouve", id="variable"),
        pytest.param("RETURN {type: t, facteurFeu: x}", id="map"),
        pytest.param("collect({pokemon: p, n: 1})", id="map-argument"),
        pytest.param("WITH [{pokemon: 'Aquali', ensemble: 'écarté'}] AS c", id="liste-de-maps"),
        pytest.param("WHERE 'Montée de niveau' IN r", id="litteral"),
        pytest.param("WHERE d =~ '(?iU).*\\\\b(nom|texte|niveau)\\\\b.*'", id="regex"),
        pytest.param("// A_LE_TYPE, nom, Forme\nRETURN 1", id="commentaire"),
        pytest.param("RETURN labels(n), keys(n), type(r)", id="fonctions"),
        pytest.param("WHERE x :: INTEGER", id="predicat-de-type"),
        pytest.param("MATCH (n:$($label))", id="label-dynamique"),
        pytest.param("RETURN $nom, $proposee", id="parametres"),
        pytest.param("RETURN 'Forme : nœuds|' + x", id="litteral-partiel"),
    ],
)
def test_inchange(inchange: str) -> None:
    assert en(inchange) == inchange


@pytest.mark.parametrize(
    ("francais", "anglais"),
    [
        pytest.param("['Pokemon', 'Forme', 'Attaque']", "['Pokemon', 'Form', 'Move']", id="labels"),
        pytest.param("['id', 'nom']", "['id', 'name']", id="cles"),
        pytest.param('"A_LE_TYPE"', '"HAS_TYPE"', id="type-guillemets"),
        pytest.param(
            "CALL db.index.fulltext.queryNodes('noms_plein_texte', 'dracofeu~')",
            "CALL db.index.fulltext.queryNodes('names_fulltext', 'dracofeu~')",
            id="index",
        ),
    ],
)
def test_litteral_qui_est_un_identifiant(francais: str, anglais: str) -> None:
    assert en(francais) == anglais


def test_appel_de_procedure_inchange() -> None:
    # Les segments d'un nom de procédure ne sont pas des clés, même au retour vers le français.
    anglais = "CALL apoc.text.join(x) RETURN n.text"
    assert traduire(anglais, TABLE, "fr") == "CALL apoc.text.join(x) RETURN n.texte"


@pytest.mark.parametrize(
    ("francais", "anglais"),
    [
        pytest.param(
            "CREATE CONSTRAINT forme_id IF NOT EXISTS FOR (n:Forme) REQUIRE n.id IS UNIQUE",
            "CREATE CONSTRAINT form_id IF NOT EXISTS FOR (n:Form) REQUIRE n.id IS UNIQUE",
            id="contrainte",
        ),
        pytest.param(
            "CREATE INDEX attaque_nom IF NOT EXISTS FOR (n:Attaque) ON (n.nom)",
            "CREATE INDEX move_name IF NOT EXISTS FOR (n:Move) ON (n.name)",
            id="index",
        ),
        pytest.param(
            "CREATE FULLTEXT INDEX noms_plein_texte IF NOT EXISTS\nFOR (n:Forme) ON EACH [n.nom]\n"
            "OPTIONS {indexConfig: {`fulltext.analyzer`: 'standard-folding'}}",
            "CREATE FULLTEXT INDEX names_fulltext IF NOT EXISTS\nFOR (n:Form) ON EACH [n.name]\n"
            "OPTIONS {indexConfig: {`fulltext.analyzer`: 'standard-folding'}}",
            id="plein-texte",
        ),
        pytest.param("DROP INDEX type_nom IF EXISTS", "DROP INDEX type_name IF EXISTS", id="drop"),
        pytest.param(
            "CREATE INDEX IF NOT EXISTS FOR (n:Talent) ON (n.nom)",
            "CREATE INDEX IF NOT EXISTS FOR (n:Ability) ON (n.name)",
            id="sans-nom",
        ),
    ],
)
def test_contraintes_et_index(francais: str, anglais: str) -> None:
    assert en(francais) == anglais


def test_sous_requetes() -> None:
    francais = (
        "CALL () { MATCH (p:Pokemon) RETURN collect(p.nom) AS trouves }\n"
        "RETURN COLLECT { MATCH (f)-[r:A_LE_TYPE]->(t:Type) RETURN t.nom ORDER BY r.rang } AS t,\n"
        "  COUNT { (f)-[:APPREND]->(:Attaque) } AS n,\n"
        "  EXISTS { (p)-[:A_POUR_DESCRIPTION]->(d) } AS e"
    )
    anglais = (
        "CALL () { MATCH (p:Pokemon) RETURN collect(p.name) AS trouves }\n"
        "RETURN COLLECT { MATCH (f)-[r:HAS_TYPE]->(t:Type) RETURN t.name ORDER BY r.slot } AS t,\n"
        "  COUNT { (f)-[:LEARNS]->(:Move) } AS n,\n"
        "  EXISTS { (p)-[:HAS_DESCRIPTION]->(d) } AS e"
    )
    assert en(francais) == anglais


@pytest.mark.parametrize(
    "ouverture",
    ["CALL () {", "CALL (n) {", "COLLECT {", "COUNT {", "EXISTS {", "CALL {"],
)
def test_virgule_dans_une_sous_requete(ouverture: str) -> None:
    # Une sous-requête n'est pas une map : après une virgule, « n:Forme » reste un prédicat.
    francais = f"{ouverture} MATCH (n) WITH n, n:Forme AS f RETURN f }}"
    assert en(francais) == f"{ouverture} MATCH (n) WITH n, n:Form AS f RETURN f }}"


def test_retour_vers_le_francais() -> None:
    francais = (
        "MATCH (p:Pokemon {nom: 'Pikachu'})-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)\n"
        "RETURN f.statPv AS pv"
    )
    assert traduire(en(francais), TABLE, "fr") == francais


@pytest.mark.parametrize(
    ("cypher", "message"),
    [
        pytest.param("MATCH (n:Inconnu)", "label ou type inconnu : 'Inconnu'", id="label"),
        pytest.param("MATCH ()-[:INCONNU]->()", "label ou type inconnu : 'INCONNU'", id="type"),
        pytest.param(
            "CREATE INDEX inconnu FOR (n:Type) ON (n.nom)", "index inconnu : 'inconnu'", id="index"
        ),
    ],
)
def test_identifiant_inconnu(cypher: str, message: str) -> None:
    with pytest.raises(TraductionError, match=message):
        en(cypher)


def test_deja_anglais_refuse() -> None:
    # Un label anglais n'est pas un label du schéma français : la traduction vers l'anglais refuse.
    with pytest.raises(TraductionError, match="label ou type inconnu : 'Move'"):
        en("MATCH (a:Move)")
