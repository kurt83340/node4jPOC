"""Rejeu des questions (scripts/questions.sh, spec 002 T1.3) : $proposee toujours passé,
--dossier et --exemples. Contrôle sur la vraie base en T7.2 et T7.3.

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

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "questions.sh"
QUESTIONS = RACINE / "questions"
PROPOSEE = "{proposee: ['Magnéton', 'Dracolosse', 'Flagadoss', 'Noadkoko', 'Staross', 'Parasect']}"
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
elif fichier:
    attendu = Path({str(QUESTIONS / "attendu")!r}) / (Path(fichier).stem + ".txt")
    print(attendu.read_text().split("\\n", 1)[1], end="")
elif "dracofeu~" in requete:
    print('nom\\n"Dracaufeu"\\n"Dracolosse"')
else:
    print('nom\\n"Exemple"')
"""


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
    assert "CONFORME : 27 questions." in lancement.sortie
    requetes = lancement.requetes()
    assert len(requetes) == 27
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
    assert "CONFORME : 2 questions." in lancement.sortie
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
    assert requetes[:-1] == exemples_de_la_fiche()
    assert "'noms_plein_texte', 'dracofeu~'" in requetes[-1]
    assert all("--access-mode" in a["argv"] for a in lancement.requetes())
    assert f"CONFORME : {len(requetes)} exemples." in lancement.sortie


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
