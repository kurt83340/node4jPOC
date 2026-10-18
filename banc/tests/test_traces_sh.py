"""Identifiant de l'instance dans les traces d'une campagne (scripts/traces.sh, spec 003, T15.1).

Aucun outil réel hors bash et grep : un faux gcloud rend un secret factice ; grep passe par une
enveloppe qui note ses arguments et les variables NEO4J_* qu'il reçoit, puis lance le vrai. Les
traces d'une campagne factice vivent dans un dossier temporaire (BANC_TRACES). Le script ne rend que
des comptes : ni l'identifiant, ni les fichiers où il paraît.
"""

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "traces.sh"
INSTANCE = "f4c7e9a2"
MOT_DE_PASSE = "mdp-factice-du-banc"
SECRET = (
    f"NEO4J_URI=neo4j+s://{INSTANCE}.databases.neo4j.io\nNEO4J_USERNAME={INSTANCE}\n"
    f"NEO4J_PASSWORD={MOT_DE_PASSE}\nNEO4J_DATABASE={INSTANCE}\n"
)
GREP = shutil.which("grep")
# Le faux gcloud note chaque appel ; s'il trouve journal/refus, il échoue comme un secret illisible.
FAUX_GCLOUD = f"""
import json, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
with (journal / "gcloud.jsonl").open("a") as note:
    note.write(json.dumps(sys.argv[1:]) + "\\n")
if (journal / "refus").exists():
    sys.exit(1)
sys.stdout.write({SECRET!r})
"""
ENVELOPPE_GREP = f"""
import json, os, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
noms = sorted(nom for nom in os.environ if nom.startswith("NEO4J"))
with (journal / "grep.jsonl").open("a") as note:
    note.write(json.dumps({{"argv": sys.argv[1:], "env": noms}}) + "\\n")
os.execv({GREP!r}, ["grep", *sys.argv[1:]])
"""
# Une trace où l'identifiant est masqué, comme scripts/mcp-neo4j.sh le laisse.
MASQUEE = '{"type": "resultat", "t": 1.0, "resultat": "[{\\"name\\": \\"‹instance›\\"}]"}\n'


@dataclass
class Lancement:
    """Ce qu'un lancement a produit : code retour, flux, appels à gcloud et à grep."""

    code: int
    sortie: str
    erreurs: str
    gcloud: list[list[str]]
    grep: list[dict[str, Any]]


@dataclass
class Bac:
    """Bac à sable : faux outils, HOME vide, dossier des traces d'une campagne c1 conforme."""

    racine: Path
    env: dict[str, str]

    @property
    def traces(self) -> Path:
        return self.racine / "traces"

    def lancer(self, *arguments: str) -> Lancement:
        resultat = subprocess.run(
            [str(SCRIPT), *arguments],
            cwd=self.racine / "travail",
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        journal = self.racine / "journal"
        gcloud = journal / "gcloud.jsonl"
        grep = journal / "grep.jsonl"
        return Lancement(
            resultat.returncode,
            resultat.stdout,
            resultat.stderr,
            [json.loads(ligne) for ligne in gcloud.read_text().splitlines()]
            if gcloud.exists()
            else [],
            [json.loads(ligne) for ligne in grep.read_text().splitlines()] if grep.exists() else [],
        )


def installer(outils: Path, nom: str, code: str) -> None:
    script = outils / nom
    script.write_text(f"#!{sys.executable} -I\n{code}")
    script.chmod(0o755)


@pytest.fixture
def bac(tmp_path: Path) -> Bac:
    for dossier in ("home", "outils", "journal", "travail", "traces/c1"):
        (tmp_path / dossier).mkdir(parents=True)
    bash = shutil.which("bash")
    assert bash is not None and GREP is not None
    (tmp_path / "outils" / "bash").symlink_to(bash)
    installer(tmp_path / "outils", "gcloud", FAUX_GCLOUD)
    installer(tmp_path / "outils", "grep", ENVELOPPE_GREP)
    campagne = tmp_path / "traces" / "c1"
    (campagne / "adk-claude-p1-Q1-e1.jsonl").write_text(MASQUEE, encoding="utf-8")
    (campagne / "campagne.json").write_text('{"format": 4, "campagne": "c1"}\n', encoding="utf-8")
    (campagne / "encodages.json").write_text('{"dimension": 3072}\n', encoding="utf-8")
    env = {
        "HOME": str(tmp_path / "home"),
        "PATH": str(tmp_path / "outils"),
        "BANC_TRACES": str(tmp_path / "traces"),
    }
    return Bac(tmp_path, env)


def test_syntaxe() -> None:
    fini = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert fini.returncode == 0, fini.stderr


def test_identifiant_absent(bac: Bac) -> None:
    # Identifiant masqué partout (‹instance›) : code 0, le nombre de fichiers lus.
    lancement = bac.lancer("--campagne", "c1")
    assert lancement.code == 0, lancement.erreurs
    assert lancement.sortie == "traces c1 : identifiant de l'instance absent des 3 fichiers\n"
    # Le secret est lu une fois, celui d'Aura (commun.sh).
    assert len(lancement.gcloud) == 1
    assert "--secret=neo4j-aura-poc" in lancement.gcloud[0]


def test_identifiant_present_compte_par_ligne(bac: Bac) -> None:
    # L'identifiant, nu ou dans l'URI de l'instance, dans deux fichiers : comptes seuls, par ligne
    # (une ligne de trace qui le porte deux fois compte une fois), ni valeur ni nom de fichier.
    campagne = bac.traces / "c1"
    trace = campagne / "adk-claude-p1-Q1-e1.jsonl"
    deux_fois = f'{{"resultat": "neo4j+s://{INSTANCE}.databases.neo4j.io, {INSTANCE}"}}\n'
    trace.write_text(MASQUEE + deux_fois + f'{{"resultat": "{INSTANCE}"}}\n', encoding="utf-8")
    (campagne / "campagne.json").write_text(f'{{"base": "{INSTANCE}"}}\n', encoding="utf-8")
    lancement = bac.lancer("--campagne", "c1")
    assert lancement.code == 1
    assert lancement.sortie == (
        "traces c1 : identifiant de l'instance dans 2 fichier(s) sur 3 (3 ligne(s))\n"
    )
    flux = lancement.sortie + lancement.erreurs
    assert INSTANCE not in flux
    assert "campagne.json" not in flux
    assert trace.name not in flux


@pytest.mark.parametrize(("porte", "code"), [(False, 0), (True, 1)])
def test_journal_de_la_campagne(bac: Bac, porte: bool, code: int) -> None:
    # logs/banc/<campagne>.log, s'il existe (la sortie de banc lancer, stderr de neo4j-mcp compris),
    # est lu aussi ; celui d'une autre campagne, jamais.
    (bac.traces / "c1.log").write_text(
        f"time=… level=ERROR {INSTANCE if porte else '‹instance›'}\n", encoding="utf-8"
    )
    (bac.traces / "c10.log").write_text(f"time=… level=ERROR {INSTANCE}\n", encoding="utf-8")
    lancement = bac.lancer("--campagne", "c1")
    assert lancement.code == code, lancement.erreurs
    attendu = "dans 1 fichier(s) sur 4 (1 ligne(s))" if porte else "absent des 4 fichiers"
    assert lancement.sortie == f"traces c1 : identifiant de l'instance {attendu}\n"


def test_identifiant_jamais_en_argument(bac: Bac) -> None:
    # L'identifiant passe à grep par un tube (ps ne le montre pas), et grep ne reçoit aucune
    # variable NEO4J_*, mot de passe compris.
    (bac.traces / "c1" / "campagne.json").write_text(
        f'{{"base": "{INSTANCE}"}}\n', encoding="utf-8"
    )
    lancement = bac.lancer("--campagne", "c1")
    assert lancement.code == 1
    assert lancement.grep, "grep jamais appelé"
    for appel in lancement.grep:
        arguments = " ".join(appel["argv"])
        assert INSTANCE not in arguments
        assert MOT_DE_PASSE not in arguments
        assert appel["env"] == []


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        pytest.param((), "usage : traces.sh --campagne <id>", id="sans-argument"),
        pytest.param(("--campagne",), "usage : traces.sh --campagne <id>", id="sans-identifiant"),
        pytest.param(("--tout", "c1"), "usage : traces.sh --campagne <id>", id="option-inconnue"),
        pytest.param(
            ("--campagne", "c1", "--plus"),
            "usage : traces.sh --campagne <id>",
            id="argument-de-trop",
        ),
        pytest.param(("--campagne", "../c1"), "un code attendu", id="chemin"),
        pytest.param(("--campagne", "C1"), "un code attendu", id="capitales"),
    ],
)
def test_arguments_refuses(bac: Bac, arguments: tuple[str, ...], message: str) -> None:
    # Refusés avant toute lecture du secret : un code de campagne, jamais un chemin.
    lancement = bac.lancer(*arguments)
    assert lancement.code == 2
    assert message in lancement.erreurs
    assert lancement.gcloud == []
    assert lancement.grep == []


@pytest.mark.parametrize("dossier", ["c2", "c3"])
def test_campagne_sans_fichier(bac: Bac, dossier: str) -> None:
    # Dossier absent (c2), ou vide (c3) : rien à lire, erreur technique, secret jamais lu.
    (bac.traces / "c3").mkdir()
    lancement = bac.lancer("--campagne", dossier)
    assert lancement.code == 2
    assert f"campagne {dossier} : aucun fichier dans {bac.traces / dossier}" in lancement.erreurs
    assert lancement.gcloud == []


def test_entree_qui_n_est_pas_un_fichier(bac: Bac) -> None:
    # Un dossier dans celui de la campagne sort de ce qu'elle écrit : erreur, secret jamais lu.
    (bac.traces / "c1" / "notes").mkdir()
    lancement = bac.lancer("--campagne", "c1")
    assert lancement.code == 2
    assert "campagne c1 : notes n'est pas un fichier" in lancement.erreurs
    assert lancement.gcloud == []


def test_fichier_cache_lu(bac: Bac) -> None:
    # Un fichier caché du dossier est lu comme les autres (banc controle-traces aussi).
    (bac.traces / "c1" / ".brouillon").write_text(f"{INSTANCE}\n", encoding="utf-8")
    lancement = bac.lancer("--campagne", "c1")
    assert lancement.code == 1
    assert lancement.sortie == (
        "traces c1 : identifiant de l'instance dans 1 fichier(s) sur 4 (1 ligne(s))\n"
    )


def test_secret_illisible(bac: Bac) -> None:
    (bac.racine / "journal" / "refus").touch()
    lancement = bac.lancer("--campagne", "c1")
    assert lancement.code == 2
    assert "secret neo4j-aura-poc illisible" in lancement.erreurs
    assert lancement.grep == []


@pytest.mark.skipif(os.geteuid() == 0, reason="root lit un fichier sans droit de lecture")
def test_fichier_illisible(bac: Bac) -> None:
    # Un fichier que grep ne peut pas lire : rien ne prouve son absence, erreur technique.
    (bac.traces / "c1" / "campagne.json").chmod(0)
    lancement = bac.lancer("--campagne", "c1")
    assert lancement.code == 2
    assert "lecture des fichiers de la campagne c1 impossible" in lancement.erreurs
    assert lancement.sortie == ""
