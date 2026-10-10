"""Sonde du renommage (scripts/charger.sh --sonde-renommage, spec 002 T7.5) sans base ni réseau.

Le PATH ne contient que bash, dirname et de faux gcloud et cypher-shell. Le faux cypher-shell note
chaque appel et planifie toute requête (code 0), sauf règle posée par le test ; la sonde doit tout
passer par EXPLAIN en lecture seule, puis choisir le mécanisme.
"""

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "charger.sh"
SECRET = (
    "NEO4J_URI=neo4j+s://instance.databases.neo4j.io\nNEO4J_USERNAME=instance\n"
    "NEO4J_PASSWORD=mot-de-passe-factice\nNEO4J_DATABASE=instance\n"
)
COMMANDES = ("bash", "dirname")
FAUX_GCLOUD = f"""
import sys
sys.stdout.write({SECRET!r})
"""
# Règles du test (journal/regles.json) : la première dont le motif est dans la requête répond.
FAUX_CYPHER_SHELL = """
import json, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
argv = sys.argv[1:]
requete = argv[-1]
with (journal / "cypher-shell.jsonl").open("a") as note:
    note.write(json.dumps({"argv": argv, "requete": requete}) + "\\n")
for regle in json.loads((journal / "regles.json").read_text()):
    if regle["motif"] in requete:
        print(regle["sortie"])
        sys.exit(regle["code"])
if "dbms.components" in requete:
    print('aura\\n"Neo4j 2026.09 (enterprise)"')
"""
ABSENTE = "There is no procedure with the name `apoc.refactor.rename.label` registered."


@dataclass
class Lancement:
    code: int
    sortie: str
    requetes: list[dict[str, Any]]


@dataclass
class Bac:
    racine: Path
    env: dict[str, str]

    def regles(self, *regles: tuple[str, str, int]) -> None:
        texte = json.dumps([{"motif": m, "sortie": s, "code": c} for m, s, c in regles])
        (self.racine / "journal" / "regles.json").write_text(texte)

    def lancer(self, *arguments: str) -> Lancement:
        fini = subprocess.run(
            [str(SCRIPT), *arguments],
            cwd=self.racine,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        journal = self.racine / "journal" / "cypher-shell.jsonl"
        appels = [json.loads(ligne) for ligne in journal.read_text().splitlines()]
        requetes = [a for a in appels if "dbms.components" not in a["requete"]]
        return Lancement(fini.returncode, fini.stdout + fini.stderr, requetes)


@pytest.fixture
def bac(tmp_path: Path) -> Bac:
    for dossier in ("home", "outils", "journal"):
        (tmp_path / dossier).mkdir()
    for commande in COMMANDES:
        chemin = shutil.which(commande)
        assert chemin is not None, commande
        (tmp_path / "outils" / commande).symlink_to(chemin)
    for nom, code in (("gcloud", FAUX_GCLOUD), ("cypher-shell", FAUX_CYPHER_SHELL)):
        outil = tmp_path / "outils" / nom
        outil.write_text(f"#!{sys.executable} -I\n{code}")
        outil.chmod(0o755)
    nouveau = Bac(tmp_path, {"HOME": str(tmp_path / "home"), "PATH": str(tmp_path / "outils")})
    nouveau.regles()
    return nouveau


def test_cypher_25_retenu(bac: Bac) -> None:
    lancement = bac.lancer("--sonde-renommage")
    assert lancement.code == 0, lancement.sortie
    retenu = "MÉCANISME : Cypher 25 (labels, types et clés dynamiques, par lots)"
    assert f"{retenu} ; repli APOC disponible." in lancement.sortie
    # Les deux mécanismes, quatre gestes chacun : renommer un label, recréer un type, deux clés.
    assert len(lancement.requetes) == 8


def test_rien_n_est_execute(bac: Bac) -> None:
    # EXPLAIN planifie sans exécuter, en lecture seule ; les paramètres viennent d'un vrai couple de
    # la future table, jamais d'un texte libre.
    lancement = bac.lancer("--sonde-renommage")
    assert lancement.requetes
    for appel in lancement.requetes:
        assert appel["requete"].startswith("EXPLAIN "), appel["requete"]
        argv = appel["argv"]
        assert argv[argv.index("--access-mode") + 1] == "read"
        assert "label: 'Attaque', nouveauLabel: 'Move'" in argv[argv.index("-P") + 1]


def test_repli_apoc_indisponible(bac: Bac) -> None:
    bac.regles(("apoc.refactor.rename.label", ABSENTE, 1))
    lancement = bac.lancer("--sonde-renommage")
    assert lancement.code == 0
    assert f"✗ label : {ABSENTE}" in lancement.sortie
    assert "; repli APOC indisponible." in lancement.sortie


def test_apoc_si_cypher_25_echoue(bac: Bac) -> None:
    bac.regles(("REMOVE n[$cle]", "Invalid input 'REMOVE n['", 1))
    lancement = bac.lancer("--sonde-renommage")
    assert lancement.code == 0
    assert "✗ propriété de nœud : Invalid input 'REMOVE n['" in lancement.sortie
    assert "MÉCANISME : APOC (apoc.refactor.rename.*)." in lancement.sortie


def test_aucun_mecanisme(bac: Bac) -> None:
    bac.regles(("$($type)", "Invalid input '$('", 1), ("apoc.refactor.rename.type", ABSENTE, 1))
    lancement = bac.lancer("--sonde-renommage")
    assert lancement.code == 1
    assert (
        "AUCUN MÉCANISME : ni Cypher 25 ni APOC ne planifient les quatre gestes."
        in lancement.sortie
    )
