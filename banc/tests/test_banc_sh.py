"""Lanceur du harnais scripts/banc.sh (ADR-0011) : lit la clé Anthropic, puis lance banc avec elle.

Aucun outil réel : le PATH ne contient que bash et de faux gcloud et uv, qui notent dans un journal
ce qu'ils reçoivent. La clé ne passe que par l'environnement : jamais en argument, jamais affichée.
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
LANCEUR = RACINE / "scripts" / "banc.sh"
CLE = "sk-ant-api03-cle-factice-du-banc_0123456789"

FAUX_GCLOUD = """
import json, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
reponse = json.loads((journal / "gcloud-reponse.json").read_text())
lu = sys.stdin.read() if sys.stdin else ""
(journal / "gcloud.json").write_text(json.dumps({"argv": sys.argv[1:], "stdin": lu}))
sys.stdout.write(reponse["secret"])
sys.exit(reponse["code"])
"""
# Environnement lu tel que reçu à l'exec, comme dans test_lanceur.py (PEP 538).
FAUX_UV = """
import json, os, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
recu = Path("/proc/self/environ").read_bytes().decode().split("\\0")
env = dict(variable.split("=", 1) for variable in recu if variable)
note = {"argv": sys.argv[1:], "env": env, "pid": os.getpid()}
(journal / "uv.json").write_text(json.dumps(note))
"""


@dataclass
class Lancement:
    """Ce qu'un lancement a produit : code retour, flux, et journal des faux outils."""

    pid: int
    code: int
    sortie: str
    erreurs: str
    journal: Path

    def note(self, outil: str) -> dict[str, Any] | None:
        """Ce que l'outil a reçu, ou None s'il n'a pas été lancé."""
        fichier = self.journal / f"{outil}.json"
        if not fichier.exists():
            return None
        note: dict[str, Any] = json.loads(fichier.read_text())
        return note

    def harnais(self) -> dict[str, Any]:
        """Ce que le faux uv a reçu (il doit avoir été lancé)."""
        note = self.note("uv")
        assert note is not None, f"uv pas lancé ; stderr : {self.erreurs}"
        return note


@dataclass
class Bac:
    """Bac à sable d'un lancement : faux outils, HOME et dossier de travail vides."""

    racine: Path
    env: dict[str, str]

    def repondre(self, secret: str = CLE, code: int = 0) -> None:
        """Règle la réponse du faux gcloud."""
        reponse = {"secret": secret, "code": code}
        (self.racine / "journal" / "gcloud-reponse.json").write_text(json.dumps(reponse))

    def lancer(self, *arguments: str, entree: str = "") -> Lancement:
        """Lance scripts/banc.sh, avec ce texte sur stdin, et attend sa fin."""
        processus = subprocess.Popen(
            [str(LANCEUR), *arguments],
            cwd=self.racine / "travail",
            env=self.env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        sortie, erreurs = processus.communicate(entree, timeout=30)
        journal = self.racine / "journal"
        return Lancement(processus.pid, processus.returncode, sortie, erreurs, journal)


def installer(outils: Path, nom: str, code: str) -> None:
    """Écrit un faux outil exécutable, lancé par l'interpréteur des tests en mode isolé."""
    script = outils / nom
    script.write_text(f"#!{sys.executable} -I\n{code}")
    script.chmod(0o755)


@pytest.fixture
def bac(tmp_path: Path) -> Bac:
    for dossier in ("home", "outils", "journal", "travail"):
        (tmp_path / dossier).mkdir()
    bash = shutil.which("bash")
    assert bash is not None
    (tmp_path / "outils" / "bash").symlink_to(bash)
    installer(tmp_path / "outils", "gcloud", FAUX_GCLOUD)
    installer(tmp_path / "outils", "uv", FAUX_UV)
    nouveau = Bac(tmp_path, {"HOME": str(tmp_path / "home"), "PATH": str(tmp_path / "outils")})
    nouveau.repondre()
    return nouveau


def test_cle_passee_au_harnais(bac: Bac) -> None:
    harnais = bac.lancer("acces").harnais()
    assert harnais["env"]["ANTHROPIC_API_KEY"] == CLE
    banc = str(RACINE / "banc")
    assert harnais["argv"] == ["run", "--directory", banc, "python", "-m", "banc", "acces"]


def test_fin_de_ligne_retiree(bac: Bac) -> None:
    # Une clé déposée avec une fin de ligne (CRLF compris) arrive nue.
    bac.repondre(CLE + "\r\n")
    assert bac.lancer("acces").harnais()["env"]["ANTHROPIC_API_KEY"] == CLE


def test_cle_jamais_affichee_ni_en_argument(bac: Bac) -> None:
    lancement = bac.lancer("acces", "--un-argument")
    assert CLE not in lancement.sortie + lancement.erreurs
    assert all(CLE not in argument for argument in lancement.harnais()["argv"])


def test_gcloud_sans_stdin(bac: Bac) -> None:
    # gcloud ne lit rien : une invite ne bloquerait pas le lancement, ni ne mangerait l'entrée.
    assert bac.lancer("acces", entree="à ne pas lire\n").note("gcloud") == {
        "argv": [
            "secrets",
            "versions",
            "access",
            "latest",
            "--secret=anthropic-api-banc",
            "--project=jleroy-labo",
        ],
        "stdin": "",
    }


def test_exec_remplace_le_lanceur(bac: Bac) -> None:
    # Même processus : un Ctrl-C ou l'arrêt du groupe de processus atteint le harnais.
    lancement = bac.lancer("acces")
    assert lancement.harnais()["pid"] == lancement.pid


@pytest.mark.parametrize(
    ("secret", "code"),
    [
        pytest.param(CLE, 1, id="secret-illisible"),
        pytest.param("", 0, id="secret-vide"),
        pytest.param("NEO4J_URI=neo4j+s://x\nNEO4J_PASSWORD=mdp\n", 0, id="pas-une-cle"),
        pytest.param(CLE + "\nautre-ligne", 0, id="plusieurs-lignes"),
    ],
)
def test_secret_inutilisable(bac: Bac, secret: str, code: int) -> None:
    bac.repondre(secret, code)
    lancement = bac.lancer("acces")
    assert (lancement.code, lancement.sortie, lancement.note("uv")) == (2, "", None)
    assert CLE not in lancement.erreurs
    assert "mdp" not in lancement.erreurs


def test_uv_introuvable(bac: Bac) -> None:
    (bac.racine / "outils" / "uv").unlink()
    lancement = bac.lancer("acces")
    assert (lancement.code, lancement.sortie) == (2, "")
    assert "uv introuvable" in lancement.erreurs
