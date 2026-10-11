"""Traduction du Cypher vers le schéma anglais, et retour (spec 002, T6.2 ; plan D8), sans base.

Corpus (fin du fichier) : les 27 requêtes, la liste des espèces, les vérifications et les exemples
de la fiche, les deux recherches de questions.sh. Traduits, ils ne portent plus aucun identifiant
français à une place du schéma, d'après une liste tirée d'ARCHITECTURE § 5 et un lecteur qui ne
doit rien au traducteur (schema_francais) ; seuls des identifiants changent, jamais un alias ni
une valeur, et l'aller-retour rend le texte.

Règles, une par test : labels, types de relation, clés (après un point, dans la map d'un motif,
raccourci {rang} de la fiche compris), noms des contraintes et des index se traduisent ; alias,
variables, clés d'une map hors motif, paramètres, commentaires et littéraux restent tels quels, sauf
un littéral qui est en entier un identifiant du schéma.
"""

import re
import shutil
from pathlib import Path

import pytest
from schema_francais import COMMUNS, LITTERAL, francais, places_du_schema, schema_francais

from banc import anglais, correspondance
from banc.correspondance import GENRES
from banc.traduction import TraductionError, traduire

TABLE = correspondance.charger()
FRANCAIS = francais()
CORPUS = anglais.corpus()
TRADUCTIONS = anglais.traductions(TABLE)


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
        pytest.param("RETURN {nom: p.nom}", "RETURN {nom: p.name}", id="cle-de-map-gardee"),
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


# --- Le corpus (T6.2) --------------------------------------------------------------------------


def test_corpus_complet() -> None:
    assert len([c for c in CORPUS if re.fullmatch(r"q\d\d\.cypher", c)]) == 27
    assert len([c for c in CORPUS if c.startswith("exemples/exemple-")]) == 8
    attendus = {
        "especes.cypher",
        "fiche.cypher",
        "exemples/dracofeu.cypher",
        "exemples/electrik.cypher",
    }
    assert attendus <= set(CORPUS)
    assert len(CORPUS) == 39


def test_le_lecteur_voit_le_schema_francais() -> None:
    # Le contrôle ne passe pas à vide : sur le corpus français, il voit tous les labels et types.
    vus = set().union(*(places_du_schema(texte) for texte in CORPUS.values()))
    schema = schema_francais()
    assert schema["labels"] | schema["relations"] <= vus
    assert {"nom", "rang", "facteur", "noms_plein_texte"} <= vus


@pytest.mark.parametrize("chemin", sorted(CORPUS))
def test_aucun_identifiant_francais(chemin: str) -> None:
    restes = places_du_schema(TRADUCTIONS[chemin]) & FRANCAIS
    assert not restes, f"{chemin} : {sorted(restes)}"


@pytest.mark.parametrize("chemin", sorted(CORPUS))
def test_aller_retour(chemin: str) -> None:
    texte = CORPUS[chemin]
    assert traduire(traduire(texte, TABLE, "en"), TABLE, "fr") == texte


@pytest.mark.parametrize("chemin", sorted(CORPUS))
def test_seuls_des_identifiants_changent(chemin: str) -> None:
    avant = re.findall(r"\w+|\W", CORPUS[chemin])
    apres = re.findall(r"\w+|\W", traduire(CORPUS[chemin], TABLE, "en"))
    assert len(avant) == len(apres)
    for francais_, anglais_ in {(a, b) for a, b in zip(avant, apres, strict=True) if a != b}:
        assert any(TABLE.nom(g, francais_, "en") == anglais_ for g in GENRES), francais_
        assert francais_ in FRANCAIS, francais_


@pytest.mark.parametrize("chemin", sorted(CORPUS))
def test_alias_inchanges(chemin: str) -> None:
    alias = re.compile(r"\bAS\s+(\w+)")
    assert alias.findall(traduire(CORPUS[chemin], TABLE, "en")) == alias.findall(CORPUS[chemin])


def test_seuls_les_litteraux_qui_sont_des_identifiants_changent() -> None:
    changes: set[tuple[str, str]] = set()
    for texte in CORPUS.values():
        avant = LITTERAL.findall(re.sub(r"//[^\n]*", "", texte))
        apres = LITTERAL.findall(re.sub(r"//[^\n]*", "", traduire(texte, TABLE, "en")))
        changes |= {(a, b) for a, b in zip(avant, apres, strict=True) if a != b}
    assert {a[1:-1] for a, _ in changes} <= FRANCAIS
    assert ("'noms_plein_texte'", "'names_fulltext'") in changes
    assert ("'Forme'", "'Form'") in changes


def test_aucune_cle_de_map_hors_motif_n_est_une_cle_du_schema() -> None:
    # Limite du traducteur : une clé de map hors motif se lit par un point, qui se traduirait sans
    # que la map change. Le corpus n'en a aucune qui porte le nom d'une clé du schéma.
    motif = re.compile(r"[(\[]\s*\w*\s*:\s*\w+\s*\{[^}]*\}")
    cles_du_schema = schema_francais()["proprietes"]
    for chemin, texte in CORPUS.items():
        code = motif.sub("()", LITTERAL.sub("''", re.sub(r"//[^\n]*", "", texte)))
        cles = set(re.findall(r"[{,]\s*([^\W\d]\w*)\s*:(?!:)", code))
        assert not cles & cles_du_schema, f"{chemin} : {sorted(cles & cles_du_schema)}"


def test_communs_relus_egaux_a_la_table() -> None:
    assert frozenset().union(*TABLE.communs.values()) == COMMUNS


def test_fiche_suivie_du_balayage() -> None:
    fiche = TRADUCTIONS["fiche.cypher"]
    assert fiche.count("balayage : labels, types et clés hors du schéma anglais|aucun|") == 1
    assert "'NOT_VERY_EFFECTIVE_AGAINST'" in fiche.split("// Balayage", 1)[1]
    for chemin, texte in TRADUCTIONS.items():
        assert texte.startswith("// Traduit vers le schéma anglais par banc traduire (D8) : "), (
            chemin
        )


def test_recherches_lues_dans_questions_sh() -> None:
    assert anglais.recherche("DRACOFEU").startswith("CALL db.index.fulltext.queryNodes(")
    assert "'dracofeu~'" in CORPUS["exemples/dracofeu.cypher"]
    assert "'ELECTRIK'" in CORPUS["exemples/electrik.cypher"]
    with pytest.raises(ValueError, match=r"ABSENTE introuvable dans scripts/questions\.sh"):
        anglais.recherche("ABSENTE", 'readonly DRACOFEU="x"\n')


def test_commande_traduire(tmp_path: Path) -> None:
    assert anglais.commande_traduire(tmp_path / "anglais") == 0
    ecrits = sorted(
        str(f.relative_to(tmp_path / "anglais")) for f in (tmp_path / "anglais").rglob("*.cypher")
    )
    assert ecrits == sorted(TRADUCTIONS)
    assert (tmp_path / "anglais" / "q09.cypher").read_text() == TRADUCTIONS["q09.cypher"]


# --- banc traduire --vers (revue adverse de la phase 6, T10.0) --------------------------------


def test_vers_relatif_a_la_racine(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # uv run --directory banc change de dossier : logs/anglais part quand même de la racine.
    monkeypatch.setattr(anglais, "RACINE", tmp_path / "depot")
    (tmp_path / "ailleurs").mkdir()
    monkeypatch.chdir(tmp_path / "ailleurs")
    assert anglais.commande_traduire(Path("logs/anglais")) == 0
    assert (tmp_path / "depot" / "logs" / "anglais" / "q02.cypher").is_file()
    assert not (tmp_path / "ailleurs" / "logs").exists()


def test_traduction_perimee_effacee(tmp_path: Path) -> None:
    dossier = tmp_path / "anglais"
    assert anglais.commande_traduire(dossier) == 0
    perimee = dossier / "exemples" / "q99.cypher"
    perimee.write_text(f"{anglais.ENTETE}questions/q99.cypher.\nRETURN 1;\n")
    assert anglais.commande_traduire(dossier) == 0
    assert not perimee.exists()
    assert anglais.ecarts_de_traduction(dossier) == []


@pytest.mark.parametrize("etranger", ["notes.txt", "exemples/a-garder.cypher"])
def test_dossier_etranger_rien_n_est_efface(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], etranger: str
) -> None:
    dossier = tmp_path / "anglais"
    assert anglais.commande_traduire(dossier) == 0
    fichier = dossier / etranger
    fichier.write_text("RETURN 1;\n")
    q02 = dossier / "q02.cypher"
    q02.write_text(q02.read_text() + "// retouche\n")
    assert anglais.commande_traduire(dossier) == 2
    assert f"contient {etranger}, qui n'est pas une traduction" in capsys.readouterr().err
    assert fichier.read_text() == "RETURN 1;\n"
    # Rien d'effacé, rien de réécrit.
    assert q02.read_text().endswith("// retouche\n")


def test_vers_un_fichier(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fichier = tmp_path / "anglais"
    fichier.write_text("RETURN 1;\n")
    assert anglais.commande_traduire(fichier) == 2
    assert "n'est pas un dossier" in capsys.readouterr().err
    assert fichier.read_text() == "RETURN 1;\n"


def test_ecarts_de_traduction(tmp_path: Path) -> None:
    dossier = tmp_path / "anglais"
    assert anglais.ecarts_de_traduction(dossier) == ["dossier absent"]
    dossier.mkdir()
    assert len(anglais.ecarts_de_traduction(dossier)) == len(TRADUCTIONS)
    assert "q02.cypher absent" in anglais.ecarts_de_traduction(dossier)
    assert anglais.commande_traduire(dossier) == 0
    assert anglais.ecarts_de_traduction(dossier) == []
    (dossier / "q02.cypher").write_text(TRADUCTIONS["q02.cypher"].replace("HAS_TYPE", "A_LE_TYPE"))
    (dossier / "q31.cypher").write_text("RETURN 1;\n")
    assert anglais.ecarts_de_traduction(dossier) == ["q02.cypher périmé", "q31.cypher en trop"]


# --- Maps dont une clé porte le nom d'une clé du schéma (T10.0) --------------------------------


@pytest.mark.parametrize(
    ("francais", "anglais_"),
    [
        pytest.param("RETURN {nom: 'Abra'} AS m", "RETURN {nom: 'Abra'} AS m", id="map-seule"),
        pytest.param(
            "WITH {nom: p.nom, rang: r.rang} AS m RETURN m",
            "WITH {nom: p.name, rang: r.slot} AS m RETURN m",
            id="valeurs-traduites",
        ),
        pytest.param(
            "RETURN [x IN liste | {nom: x}] AS noms",
            "RETURN [x IN liste | {nom: x}] AS noms",
            id="map-de-liste",
        ),
        # Limite connue (plan, D8) : la lecture par un point se traduit, la clé de la map non ; la
        # requête traduite ne lit plus rien. Le corpus n'en a aucune
        # (test_aucune_cle_de_map_hors_motif_n_est_une_cle_du_schema).
        pytest.param(
            "WITH {nom: 'Abra'} AS m RETURN m.nom",
            "WITH {nom: 'Abra'} AS m RETURN m.name",
            id="limite-lecture-par-un-point",
        ),
    ],
)
def test_map_a_cle_du_schema(francais: str, anglais_: str) -> None:
    assert en(francais) == anglais_


def test_lien_vers_un_dossier_refuse(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Revue adverse de T10.0 : exemples/ en lien vers un autre dossier faisait écrire dedans.
    precieux = tmp_path / "precieux"
    precieux.mkdir()
    (precieux / "dracofeu.cypher").write_text("MON FICHIER\n")
    (precieux / "notes.md").write_text("notes\n")
    dossier = tmp_path / "anglais"
    assert anglais.commande_traduire(dossier) == 0
    shutil.rmtree(dossier / "exemples")
    (dossier / "exemples").symlink_to(precieux, target_is_directory=True)
    assert anglais.commande_traduire(dossier) == 2
    assert "contient exemples, qui n'est pas une traduction" in capsys.readouterr().err
    assert sorted(f.name for f in precieux.iterdir()) == ["dracofeu.cypher", "notes.md"]
    assert (precieux / "dracofeu.cypher").read_text() == "MON FICHIER\n"
    # Rien d'effacé dans le dossier non plus.
    assert (dossier / "q02.cypher").read_text() == TRADUCTIONS["q02.cypher"]


def test_lien_vers_une_traduction_refuse(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Même vers un fichier sous l'en-tête, un lien n'est pas une traduction : effacer le lien
    # laisserait la cible, écrire suivrait le lien.
    ailleurs = tmp_path / "ailleurs.cypher"
    ailleurs.write_text(TRADUCTIONS["q02.cypher"])
    dossier = tmp_path / "anglais"
    assert anglais.commande_traduire(dossier) == 0
    (dossier / "q02.cypher").unlink()
    (dossier / "q02.cypher").symlink_to(ailleurs)
    assert anglais.commande_traduire(dossier) == 2
    assert "contient q02.cypher, qui n'est pas une traduction" in capsys.readouterr().err
    assert ailleurs.read_text() == TRADUCTIONS["q02.cypher"]


def test_dossier_en_lien_refuse(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    vrai = tmp_path / "vrai"
    vrai.mkdir()
    (tmp_path / "anglais").symlink_to(vrai, target_is_directory=True)
    assert anglais.commande_traduire(tmp_path / "anglais") == 2
    assert "n'est pas un dossier (ou c'est un lien)" in capsys.readouterr().err
    assert list(vrai.iterdir()) == []


def test_traduction_impossible_rien_n_est_efface(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    dossier = tmp_path / "anglais"
    assert anglais.commande_traduire(dossier) == 0

    def en_echec(_table: object) -> dict[str, str]:
        raise TraductionError("identifiant inconnu")

    monkeypatch.setattr(anglais, "traductions", en_echec)
    assert anglais.commande_traduire(dossier) == 2
    assert "traduction impossible, rien n'est effacé : identifiant inconnu" in (
        capsys.readouterr().err
    )
    assert (dossier / "q02.cypher").read_text() == TRADUCTIONS["q02.cypher"]
