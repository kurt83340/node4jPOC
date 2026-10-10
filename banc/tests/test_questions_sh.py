"""Rejeu des questions (scripts/questions.sh, spec 002 T1.3) : $proposee toujours passé,
--dossier et --exemples ; liste des espèces rejouée avec les questions, et contrôle de Q2 sur
l'équipe d'un agent (T2.1, plan D4 et D6). Contrôle sur la vraie base en T7.2 et T7.3.

Aucun outil réel : le PATH ne contient que bash, quelques commandes de base et de faux gcloud et
cypher-shell. Le faux cypher-shell note chaque appel ; il répond comme la base de référence (les
corps de questions/attendu/), sauf règle posée par le test.
"""

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from banc import attendu
from banc.lecture import liste_cypher

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "questions.sh"
QUESTIONS = RACINE / "questions"
PROPOSEE = "{proposee: ['Magnéton', 'Dracolosse', 'Flagadoss', 'Noadkoko', 'Staross', 'Parasect']}"
# Une équipe d'agent : des noms à espace, tiret, point, deux-points, chiffre et symbole.
EQUIPE = "['M. Mime', 'Porygon-Z', 'Type:0', 'Nidoran♀', 'Ho-Oh', 'Kaimorse']"
SECRET = (
    "NEO4J_URI=neo4j+s://instance.databases.neo4j.io\nNEO4J_USERNAME=instance\n"
    "NEO4J_PASSWORD=mot-de-passe-factice\nNEO4J_DATABASE=instance\n"
)
COMMANDES = ("bash", "cat", "dirname", "basename", "diff", "sed", "mkdir")

FAUX_GCLOUD = f"""
import sys
sys.stdout.write({SECRET!r})
"""
# Règles du test (journal/regles.json) : la première dont le motif est dans la requête répond ;
# sinon, la base de référence. Un fichier .cypher répond par le corps de sa réponse attendue.
FAUX_CYPHER_SHELL = f"""
import json, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
argv = sys.argv[1:]
fichier = argv[argv.index("--file") + 1] if "--file" in argv else None
requete = Path(fichier).read_text() if fichier else argv[-1]
with (journal / "cypher-shell.jsonl").open("a") as note:
    note.write(json.dumps({{"argv": argv, "requete": requete}}) + "\\n")
regles = json.loads((journal / "regles.json").read_text())
for regle in regles:
    if regle["motif"] in requete:
        print(regle["sortie"])
        sys.exit(regle["code"])
if "dbms.components" in requete:
    print('aura\\n"Neo4j 2026.01 (enterprise)"')
elif fichier and Path(fichier).name == "fiche.cypher":
    print(FICHE_CONFORME, end="")
elif fichier:
    attendu = Path({str(QUESTIONS / "attendu")!r}) / (Path(fichier).stem + ".txt")
    print(attendu.read_text().split("\\n", 1)[1], end="")
elif "dracofeu~" in requete:
    print('nom\\n"Dracaufeu"\\n"Dracolosse"')
elif "'ELECTRIK'" in requete:
    print('nom\\n"Électrik"')
else:
    print('nom\\n"Exemple"')
"""
# Ce que questions/fiche.cypher rend sur une base conforme : deux vérifications et une information.
FICHE_CONFORME = (
    'ligne\n"labels des nœuds|Attaque, Type|Attaque, Type"\n'
    'ligne\n"méthodes rares (relations)||Boîte (3)"\n'
    'ligne\n"Type.nom|Eau, Feu|Eau, Feu"\n'
)
FAUX_CYPHER_SHELL = f"FICHE_CONFORME = {FICHE_CONFORME!r}\n" + FAUX_CYPHER_SHELL


@dataclass
class Lancement:
    """Ce qu'un lancement a produit : code retour, flux, et les appels au faux cypher-shell."""

    code: int
    sortie: str
    erreurs: str
    appels: list[dict[str, Any]]

    def requetes(self) -> list[dict[str, Any]]:
        """Les appels hors du test de connexion (ping_aura)."""
        return [a for a in self.appels if "dbms.components" not in a["requete"]]


@dataclass
class Bac:
    """Bac à sable : faux outils, HOME et dossier de travail vides."""

    racine: Path
    env: dict[str, str]

    def regles(self, *regles: tuple[str, str, int]) -> None:
        """Réponses du faux cypher-shell : (motif dans la requête, sortie, code retour)."""
        texte = json.dumps([{"motif": m, "sortie": s, "code": c} for m, s, c in regles])
        (self.racine / "journal" / "regles.json").write_text(texte)

    def lancer(self, *arguments: str) -> Lancement:
        resultat = subprocess.run(
            [str(SCRIPT), *arguments],
            cwd=self.racine / "travail",
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        journal = self.racine / "journal" / "cypher-shell.jsonl"
        lignes = journal.read_text().splitlines() if journal.exists() else []
        appels = [json.loads(ligne) for ligne in lignes]
        return Lancement(resultat.returncode, resultat.stdout, resultat.stderr, appels)


def installer(outils: Path, nom: str, code: str) -> None:
    script = outils / nom
    script.write_text(f"#!{sys.executable} -I\n{code}")
    script.chmod(0o755)


@pytest.fixture
def bac(tmp_path: Path) -> Bac:
    for dossier in ("home", "outils", "journal", "travail"):
        (tmp_path / dossier).mkdir()
    for commande in COMMANDES:
        chemin = shutil.which(commande)
        assert chemin is not None, commande
        (tmp_path / "outils" / commande).symlink_to(chemin)
    installer(tmp_path / "outils", "gcloud", FAUX_GCLOUD)
    installer(tmp_path / "outils", "cypher-shell", FAUX_CYPHER_SHELL)
    nouveau = Bac(tmp_path, {"HOME": str(tmp_path / "home"), "PATH": str(tmp_path / "outils")})
    nouveau.regles()
    return nouveau


def exemples_de_la_fiche() -> list[str]:
    fiche = (QUESTIONS / "fiche-schema.md").read_text()
    return re.findall(r"```cypher\n(.*?)```", fiche, re.DOTALL)


def test_proposee_passee_a_chaque_requete(bac: Bac) -> None:
    lancement = bac.lancer("--verifier")
    assert lancement.code == 0, lancement.erreurs
    assert "CONFORME : 28 requêtes." in lancement.sortie
    requetes = lancement.requetes()
    assert len(requetes) == 28
    for appel in requetes:
        argv = appel["argv"]
        assert argv[argv.index("-P") + 1] == PROPOSEE
        assert argv[argv.index("--access-mode") + 1] == "read"


def test_q02_lit_proposee() -> None:
    # Le contrôle de Q2 ne garde aucune équipe en dur : la proposition vient du paramètre.
    requetes = re.sub(r"//[^\n]*", "", (QUESTIONS / "q02.cypher").read_text())
    controle = requetes.split(";")[1]
    assert "$proposee AS proposee" in controle
    assert "Magnéton" not in controle


def test_dossier(bac: Bac, tmp_path: Path) -> None:
    dossier = tmp_path / "traduites"
    dossier.mkdir()
    for nom in ("q01.cypher", "q02.cypher"):
        shutil.copy(QUESTIONS / nom, dossier / nom)
    lancement = bac.lancer("--dossier", str(dossier), "--verifier")
    assert lancement.code == 0, lancement.erreurs
    assert "CONFORME : 2 requêtes." in lancement.sortie
    fichiers = [a["argv"][a["argv"].index("--file") + 1] for a in lancement.requetes()]
    assert [Path(f).parent for f in fichiers] == [dossier, dossier]


def test_dossier_refuse_avec_enregistrer(bac: Bac, tmp_path: Path) -> None:
    # Les réponses de référence ne viennent jamais de requêtes traduites : refus avant tout appel.
    lancement = bac.lancer("--dossier", str(tmp_path), "--enregistrer")
    assert lancement.code == 2
    assert "--dossier" in lancement.erreurs
    assert lancement.appels == []


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param([], id="sans-mode"),
        pytest.param(["--verifier", "--exemples"], id="deux-modes"),
        pytest.param(["--verifier", "q01"], id="question-hors-enregistrer"),
        pytest.param(["--dossier"], id="dossier-sans-chemin"),
        pytest.param(["--inconnue"], id="option-inconnue"),
    ],
)
def test_arguments_invalides(bac: Bac, arguments: list[str]) -> None:
    lancement = bac.lancer(*arguments)
    assert lancement.code == 2
    assert lancement.appels == []


def test_exemples_de_la_fiche(bac: Bac) -> None:
    lancement = bac.lancer("--exemples")
    assert lancement.code == 0, lancement.sortie + lancement.erreurs
    requetes = [a["requete"] for a in lancement.requetes()]
    # D'abord ce que la fiche affirme (T7.3), puis ses exemples et les deux recherches dans l'index.
    assert requetes[0] == (QUESTIONS / "fiche.cypher").read_text()
    assert requetes[1:-2] == exemples_de_la_fiche()
    assert "'noms_plein_texte', 'dracofeu~'" in requetes[-2]
    assert "'noms_plein_texte', 'ELECTRIK'" in requetes[-1]
    assert all(
        a["argv"][a["argv"].index("--access-mode") + 1] == "read" for a in lancement.requetes()
    )
    assert f"CONFORME : 2 valeurs de la fiche, {len(requetes) - 1} exemples." in lancement.sortie


def test_valeurs_de_la_fiche_jugees(bac: Bac) -> None:
    ecart = 'ligne\n"Type.nom|Eau, Feu|Eau"\nligne\n"labels des nœuds|Type|Type"'
    bac.regles(("valeurFiche", ecart, 0))
    lancement = bac.lancer("--exemples")
    assert lancement.code == 1
    assert "✗ Type.nom : Eau, attendu Eau, Feu" in lancement.sortie
    assert "✓ labels des nœuds : Type" in lancement.sortie
    # Les exemples passent quand même : l'écart vient des seules valeurs.
    assert "✓ dracofeu~" in lancement.sortie
    assert "ÉCART : valeurs de la fiche, 1 écart(s) ; exemples, 0 sur 10." in lancement.sortie


def test_information_sans_verdict(bac: Bac) -> None:
    lancement = bac.lancer("--exemples")
    assert lancement.code == 0
    assert "  · méthodes rares (relations) : Boîte (3)" in lancement.sortie
    assert "2 valeurs de la fiche" in lancement.sortie


def test_valeurs_de_la_fiche_en_echec_est_un_ecart(bac: Bac) -> None:
    # Comme un exemple : Aura a répondu à ping_aura, la fiche ne se vérifie pas.
    bac.regles(("valeurFiche", "Invalid input 'MATCH'", 1))
    lancement = bac.lancer("--exemples")
    assert lancement.code == 1
    assert "✗ fiche.cypher : Invalid input 'MATCH'" in lancement.sortie
    assert "✓ exemple 1 de la fiche" in lancement.sortie


def test_aucune_valeur_lue_est_une_erreur(bac: Bac) -> None:
    bac.regles(("valeurFiche", "ligne", 0))
    lancement = bac.lancer("--exemples")
    assert lancement.code == 2
    assert "aucune valeur de la fiche lue" in lancement.erreurs


def test_electrik_doit_trouver_electrik(bac: Bac) -> None:
    # La fiche promet une recherche sans casse ni accents (analyseur standard-folding).
    bac.regles(("'ELECTRIK'", 'nom\n"Électrode"', 0))
    lancement = bac.lancer("--exemples")
    assert lancement.code == 1
    assert "✗ ELECTRIK : Électrik absent du résultat" in lancement.sortie
    assert "✓ dracofeu~" in lancement.sortie


def test_exemple_sans_ligne(bac: Bac) -> None:
    bac.regles(("Tropius", "description, jeux", 0))
    lancement = bac.lancer("--exemples")
    assert lancement.code == 1
    assert "✗ exemple 7 de la fiche : aucune ligne" in lancement.sortie


def test_index_absent_est_un_ecart(bac: Bac) -> None:
    # D9 : une base sans index plein texte rend un écart (1), pas une erreur technique (2).
    absent = "There is no such fulltext schema index: noms_plein_texte"
    bac.regles(("queryNodes", absent, 1))
    lancement = bac.lancer("--exemples")
    assert lancement.code == 1
    assert f"✗ exemple 6 de la fiche : {absent}" in lancement.sortie
    assert f"✗ dracofeu~ : {absent}" in lancement.sortie
    assert f"✗ ELECTRIK : {absent}" in lancement.sortie


def test_dracofeu_doit_trouver_dracaufeu(bac: Bac) -> None:
    bac.regles(("dracofeu~", 'nom\n"Dracolosse"', 0))
    lancement = bac.lancer("--exemples")
    assert lancement.code == 1
    assert "✗ dracofeu~ : Dracaufeu absent du résultat" in lancement.sortie


def test_exemples_du_dossier(bac: Bac, tmp_path: Path) -> None:
    exemples = tmp_path / "traduites" / "exemples"
    exemples.mkdir(parents=True)
    (exemples / "01.cypher").write_text("MATCH (n:Species) RETURN n.name AS name LIMIT 1")
    dracofeu = "CALL db.index.fulltext.queryNodes('names', 'dracofeu~') YIELD node RETURN node.name"
    (exemples / "dracofeu.cypher").write_text(dracofeu)
    lancement = bac.lancer("--dossier", str(exemples.parent), "--exemples")
    assert lancement.code == 0, lancement.sortie + lancement.erreurs
    assert [a["requete"] for a in lancement.requetes()] == [
        "MATCH (n:Species) RETURN n.name AS name LIMIT 1",
        dracofeu,
    ]
    assert (
        f"  · valeurs de la fiche : pas de fiche.cypher dans {exemples.parent}" in lancement.sortie
    )


def test_valeurs_de_la_fiche_du_dossier(bac: Bac, tmp_path: Path) -> None:
    # Schéma anglais (T10.1) : la traduction de fiche.cypher se lit dans le dossier, comme les
    # exemples.
    traduites = tmp_path / "traduites"
    (traduites / "exemples").mkdir(parents=True)
    (traduites / "fiche.cypher").write_text("MATCH (t:Type) RETURN 'Type.name|18|18' AS ligne")
    electrik = "CALL db.index.fulltext.queryNodes('names', 'ELECTRIK') YIELD node RETURN node.name"
    (traduites / "exemples" / "electrik.cypher").write_text(electrik)
    bac.regles(("'names', 'ELECTRIK'", 'name\n"Électrik"', 0))
    lancement = bac.lancer("--dossier", str(traduites), "--exemples")
    assert lancement.code == 0, lancement.sortie + lancement.erreurs
    fichiers = [
        a["argv"][a["argv"].index("--file") + 1] for a in lancement.appels if "--file" in a["argv"]
    ]
    assert fichiers == [str(traduites / "fiche.cypher")]
    assert "✓ electrik.cypher" in lancement.sortie


# --- Liste des espèces et contrôle de Q2 (T2.1, plan D4 et D6) --------------------------------


def fichiers_lus(lancement: Lancement) -> list[str]:
    return [Path(a["argv"][a["argv"].index("--file") + 1]).name for a in lancement.requetes()]


def test_verifier_rejoue_la_liste_des_especes(bac: Bac) -> None:
    # La liste qui sert à reconnaître les espèces se rejoue avec les 27 requêtes : un changement des
    # données ne la laisse pas se périmer en silence.
    lancement = bac.lancer("--verifier")
    assert lancement.code == 0, lancement.erreurs
    assert fichiers_lus(lancement)[-1] == "especes.cypher"
    assert "✓ especes" in lancement.sortie


def test_liste_des_especes_differente_est_un_ecart(bac: Bac) -> None:
    bac.regles(("RETURN p.nom AS pokemon", 'pokemon\n"Bulbizarre"', 0))
    lancement = bac.lancer("--verifier")
    assert lancement.code == 1
    assert "✗ especes : réponse différente de attendu/especes.txt" in lancement.sortie


def test_controle_passe_l_equipe_a_q02(bac: Bac) -> None:
    lancement = bac.lancer("--controle", EQUIPE)
    assert lancement.code == 0, lancement.erreurs
    [appel] = lancement.requetes()
    argv = appel["argv"]
    assert fichiers_lus(lancement) == ["q02.cypher"]
    assert argv[argv.index("-P") + 1] == f"{{proposee: {EQUIPE}}}"
    assert argv[argv.index("--access-mode") + 1] == "read"
    # stdout ne porte que la réponse, relisible comme les réponses de référence.
    controle = attendu.analyser(lancement.sortie)[-1]
    assert controle.colonnes == ("especesReconnues", "typesNonCouverts", "equipeValide")


def test_controle_accepte_la_liste_du_harnais(bac: Bac) -> None:
    # Les deux barrières s'accordent : ce que banc.lecture produit, questions.sh l'accepte tel quel.
    liste = liste_cypher(("M. Mime", "Porygon-Z", "Type:0", "Nidoran♀", "Ho-Oh", "Épine-de-Fer"))
    lancement = bac.lancer("--controle", liste)
    assert lancement.code == 0, lancement.erreurs
    [appel] = lancement.requetes()
    assert appel["argv"][appel["argv"].index("-P") + 1] == f"{{proposee: {liste}}}"


def test_controle_avec_dossier(bac: Bac, tmp_path: Path) -> None:
    # Sur la base anglaise, la traduction de q02.cypher fait le contrôle (plan, D6).
    dossier = tmp_path / "traduites"
    dossier.mkdir()
    shutil.copy(QUESTIONS / "q02.cypher", dossier / "q02.cypher")
    lancement = bac.lancer("--dossier", str(dossier), "--controle", EQUIPE)
    assert lancement.code == 0, lancement.erreurs
    [appel] = lancement.requetes()
    assert Path(appel["argv"][appel["argv"].index("--file") + 1]).parent == dossier


@pytest.mark.parametrize(
    "equipe",
    [
        pytest.param("['A', 'B', 'C', 'D', 'E']", id="cinq-noms"),
        pytest.param("['A', 'B', 'C', 'D', 'E', 'F', 'G']", id="sept-noms"),
        pytest.param("['A', 'B', 'C', 'D', 'E', 'F'] + ['G']", id="expression"),
        pytest.param("['A', 'B', 'C', 'D', 'E', 'F'}, x: {y: 'z']", id="sortie-de-liste"),
        pytest.param("['A', 'B', 'C', 'D', 'E', 'O'Brien']", id="apostrophe"),
        pytest.param("['A', 'B', 'C', 'D', 'E', 'F\\']", id="antislash"),
        pytest.param("['A', 'B', 'C', 'D', 'E', '']", id="nom-vide"),
        pytest.param('["A", "B", "C", "D", "E", "F"]', id="guillemets"),
        pytest.param("['A', 'B', 'C', 'D', 'E', 'F\nG']", id="saut-de-ligne"),
        pytest.param("['A','B','C','D','E','F']", id="separateur"),
        pytest.param("", id="vide"),
    ],
)
def test_controle_refuse_une_equipe_mal_formee(bac: Bac, equipe: str) -> None:
    # Jamais un texte libre dans -P (plan, D6) : refus avant tout appel, test de connexion compris.
    lancement = bac.lancer("--controle", equipe)
    assert lancement.code == 2
    assert "--controle" in lancement.erreurs
    assert lancement.appels == []


@pytest.mark.parametrize(
    "equipe",
    [
        pytest.param("['A', 'B', 'C', 'D', 'E', 'O'Brien']", id="apostrophe"),
        pytest.param("['A', 'B', 'C', 'D', 'E', 'F\\']", id="antislash"),
        pytest.param("['A', 'B', 'C', 'D', 'E', 'F\nG']", id="saut-de-ligne"),
    ],
)
def test_controle_refuse_aussi_en_utf8(bac: Bac, equipe: str) -> None:
    # Les classes de caractères de la regex dépendent de la locale : même refus en UTF-8.
    bac.env["LC_ALL"] = "C.UTF-8"
    lancement = bac.lancer("--controle", equipe)
    assert lancement.code == 2
    assert lancement.appels == []
    # Et la même locale accepte une équipe bien formée (noms accentués, ♀).
    valide = bac.lancer("--controle", EQUIPE)
    assert valide.code == 0, valide.erreurs


@pytest.mark.parametrize(
    "arguments",
    [
        pytest.param(["--controle"], id="sans-equipe"),
        pytest.param(["--verifier", "--controle", EQUIPE], id="deux-modes"),
        pytest.param(["--controle", EQUIPE, "q02"], id="question-en-plus"),
    ],
)
def test_controle_arguments_invalides(bac: Bac, arguments: list[str]) -> None:
    lancement = bac.lancer(*arguments)
    assert lancement.code == 2
    assert lancement.appels == []
