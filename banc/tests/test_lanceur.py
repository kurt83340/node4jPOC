"""Lanceur scripts/mcp-neo4j.sh (T0.4), lancé comme un client MCP le lance.

Chemin absolu, dossier de travail vide hors du dépôt, environnement réduit à la liste blanche de D3
(env= de subprocess : l'équivalent d'env -i). Aucun outil réel : le PATH ne contient que bash et de
faux gcloud et neo4j-mcp, qui notent dans un journal ce qu'ils reçoivent.
"""

import json
import select
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

LANCEUR = Path(__file__).resolve().parents[2] / "scripts" / "mcp-neo4j.sh"

# Secret factice, au format du fichier d'identifiants d'Aura : l'utilisateur et la base valent
# l'identifiant de l'instance.
INSTANCE = "f4c7e9a2"
MOT_DE_PASSE = "mdp-factice-du-banc"
URI = f"neo4j+s://{INSTANCE}.databases.neo4j.io"
SECRET = (
    f"NEO4J_URI={URI}\nNEO4J_USERNAME={INSTANCE}\nNEO4J_PASSWORD={MOT_DE_PASSE}\n"
    f"NEO4J_DATABASE={INSTANCE}\nAURA_INSTANCEID={INSTANCE}\nAURA_INSTANCENAME=Instance01\n"
)
# Canal MCP : ce que le client écrit sur stdin, ce que le serveur répond sur stdout.
REQUETE_MCP = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}\n'
REPONSE_MCP = '{"jsonrpc":"2.0","id":1,"result":{}}\n'

# Configuration attendue du serveur, noms du tag v1.6.0 (plan, D1).
CONFIGURATION = {
    "NEO4J_MCP_URI": URI,
    "NEO4J_MCP_USERNAME": INSTANCE,
    "NEO4J_MCP_PASSWORD": MOT_DE_PASSE,
    "NEO4J_MCP_DATABASE": INSTANCE,
    "NEO4J_MCP_READ_ONLY": "true",
    "NEO4J_MCP_TELEMETRY": "false",
    "NEO4J_MCP_TRANSPORT_MODE": "stdio",
}
# Les 14 anciens noms encore lus par la v1.6.0 (internal/config/config.go), avec des valeurs
# hostiles, et des NEO4J_MCP_* hérités qui contrediraient la configuration.
HERITAGE_HOSTILE = {
    "NEO4J_URI": "neo4j://ailleurs:7687",
    "NEO4J_USERNAME": "intrus",
    "NEO4J_PASSWORD": "un-autre",
    "NEO4J_DATABASE": "autre",
    "NEO4J_READ_ONLY": "false",
    "NEO4J_TELEMETRY": "true",
    "NEO4J_LOG_LEVEL": "debug",
    "NEO4J_LOG_FORMAT": "json",
    "NEO4J_TRANSPORT_MODE": "http",
    "NEO4J_MCP_TRANSPORT": "http",
    "NEO4J_SCHEMA_SAMPLE_SIZE": "1",
    "NEO4J_HTTP_AUTH_HEADER_NAME": "X-Intrus",
    "NEO4J_HTTP_ALLOW_UNAUTHENTICATED_PING": "true",
    "NEO4J_HTTP_ALLOW_UNAUTHENTICATED_TOOLS_LIST": "true",
    "NEO4J_MCP_READ_ONLY": "false",
    "NEO4J_MCP_TELEMETRY": "true",
    "NEO4J_MCP_LOG_LEVEL": "debug",
}
# Variables que bash ajoute de lui-même à l'environnement d'un programme qu'il lance.
AJOUTS_DE_BASH = {"PWD", "SHLVL"}
# Clé factice de la cellule Claude Code (ADR-0011), et autres accès à Claude qu'un agent pourrait
# hériter : aucun ne doit atteindre neo4j-mcp, un binaire tiers qui n'en a pas l'usage.
CLE_ANTHROPIC = "sk-ant-api03-cle-factice-du-banc"
ACCES_CLAUDE_HOSTILES = {
    "ANTHROPIC_AUTH_TOKEN": "jeton-factice",
    "CLAUDE_CODE_OAUTH_TOKEN": "oauth-factice",
}


def acces_claude(nom: str) -> bool:
    """Vrai pour une variable qui donne accès à Claude, que le lanceur retire."""
    return nom.startswith("ANTHROPIC_") or nom == "CLAUDE_CODE_OAUTH_TOKEN"


# Faux outils : rien que la bibliothèque standard, journal dans ../journal.
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
# L'environnement se lit tel que reçu à l'exec (/proc/self/environ) : Python ajoute LC_CTYPE au sien
# quand aucune locale n'est fixée (PEP 538), ce que le vrai neo4j-mcp, en Go, ne fait pas.
FAUX_SERVEUR = """
import json, os, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
recu = Path("/proc/self/environ").read_bytes().decode().split("\\0")
env = dict(variable.split("=", 1) for variable in recu if variable)
note = {"argv": sys.argv[1:], "env": env, "stdin": sys.stdin.read(), "pid": os.getpid()}
(journal / "neo4j-mcp.json").write_text(json.dumps(note))
sys.stdout.write((journal / "neo4j-mcp-reponse.txt").read_text())
sys.stderr.write("connexion à " + env["NEO4J_MCP_URI"] + "\\n")
sys.stderr.write("mot de passe : " + env["NEO4J_MCP_PASSWORD"] + "\\n")
"""
# Le vrai perl masque le canal MCP ; ce relais note d'abord ses arguments, visibles de ps.
RELAIS_PERL = """
import json, os, shutil, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
(journal / "perl.json").write_text(json.dumps({"argv": sys.argv[1:]}))
os.execv(PERL, ["perl", *sys.argv[1:]])
"""
# Serveur qui répond à chaque requête dès réception, comme neo4j-mcp face à un client.
FAUX_DIALOGUE = """
import sys
while ligne := sys.stdin.readline():
    sys.stdout.write(ligne.replace("requete", "reponse"))
    sys.stdout.flush()
"""
# Résultat de read-cypher qui porte l'identifiant (CALL db.info()) : une ligne, un message MCP.
RESULTAT_MCP = (
    '{"jsonrpc":"2.0","id":2,"result":{"content":[{"type":"text","text":'
    f'"[{{\\"name\\": \\"{INSTANCE}\\", \\"adresse\\": \\"{INSTANCE}.databases.neo4j.io\\"}}]"'
    "}]}}\n"
)
# Réponse de neo4j-mcp v1.6.0 (mcp-go v0.56.0) à initialize. Ses instructions citent get-schema, que
# le client retire (plan, D1) : Claude Code les injecterait dans la conversation (relevé T4.1).
INSTRUCTIONS = (
    "This is the Neo4j official MCP server and can provide tool calling to interact with your "
    "Neo4j database,by inferring the schema with tools like get-schema and executing arbitrary "
    "Cypher queries with read-cypher."
)
DEBUT_INITIALISATION = '{"jsonrpc":"2.0","id":0,"result":{'
RESTE_INITIALISATION = (
    '"protocolVersion":"2025-06-18","capabilities":{"tools":{"listChanged":true}},'
    '"serverInfo":{"name":"neo4j-mcp","version":"v1.6.0"}'
)
INITIALISATION_SANS_INSTRUCTIONS = DEBUT_INITIALISATION + RESTE_INITIALISATION + "}}\n"


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

    def serveur(self) -> dict[str, Any]:
        """Ce que le faux neo4j-mcp a reçu (il doit avoir été lancé)."""
        note = self.note("neo4j-mcp")
        assert note is not None, f"neo4j-mcp pas lancé ; stderr : {self.erreurs}"
        return note


@dataclass
class Bac:
    """Bac à sable d'un lancement : liste blanche de D3, faux outils, dossier de travail vide."""

    racine: Path
    env: dict[str, str]

    def repondre(self, secret: str = SECRET, code: int = 0) -> None:
        """Règle la réponse du faux gcloud."""
        reponse = {"secret": secret, "code": code}
        (self.racine / "journal" / "gcloud-reponse.json").write_text(json.dumps(reponse))

    def lancer(self, *arguments: str, entree: str = REQUETE_MCP) -> Lancement:
        """Lance le lanceur par son chemin absolu, comme un client MCP, et attend sa fin."""
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


def liste_blanche(racine: Path) -> dict[str, str]:
    """Environnement de la cellule Claude Code selon D3 (ADR-0011) : rien d'autre ne passe."""
    return {
        "HOME": str(racine / "home"),
        "CLOUDSDK_CONFIG": str(racine / "gcloud"),
        "CLAUDE_CONFIG_DIR": str(racine / "claude"),
        "PATH": str(racine / "outils"),
        "ANTHROPIC_API_KEY": CLE_ANTHROPIC,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": "claude-haiku-4-5-20251001",
        "CLAUDE_CODE_EFFORT_LEVEL": "high",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        "CLAUDE_CODE_HARBOR_KITE": "0",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
        "CLAUDE_CODE_MAX_RETRIES": "2",
        "FORCE_PROMPT_CACHING_5M": "1",
    }


def installer(outils: Path, nom: str, code: str) -> None:
    """Écrit un faux outil exécutable, lancé par l'interpréteur des tests en mode isolé."""
    script = outils / nom
    script.write_text(f"#!{sys.executable} -I\n{code}")
    script.chmod(0o755)


@pytest.fixture
def bac(tmp_path: Path) -> Bac:
    for dossier in ("home", "gcloud", "claude", "outils", "journal", "travail"):
        (tmp_path / dossier).mkdir()
    bash = shutil.which("bash")
    assert bash is not None
    (tmp_path / "outils" / "bash").symlink_to(bash)
    installer(tmp_path / "outils", "gcloud", FAUX_GCLOUD)
    installer(tmp_path / "outils", "neo4j-mcp", FAUX_SERVEUR)
    perl = shutil.which("perl")
    assert perl is not None
    installer(tmp_path / "outils", "perl", f"PERL = {perl!r}\n{RELAIS_PERL}")
    (tmp_path / "journal" / "neo4j-mcp-reponse.txt").write_text(REPONSE_MCP)
    nouveau = Bac(tmp_path, liste_blanche(tmp_path))
    nouveau.repondre()
    return nouveau


def test_variables_du_tag(bac: Bac) -> None:
    env = bac.lancer().serveur()["env"]
    assert {nom: env.get(nom) for nom in CONFIGURATION} == CONFIGURATION


def test_rien_d_autre_dans_l_environnement(bac: Bac) -> None:
    env = bac.lancer().serveur()["env"]
    assert set(env) - set(bac.env) - set(CONFIGURATION) <= AJOUTS_DE_BASH
    gardees = {nom: valeur for nom, valeur in bac.env.items() if not acces_claude(nom)}
    assert {nom: env.get(nom) for nom in gardees} == gardees


def test_aucun_acces_a_claude(bac: Bac) -> None:
    # La clé de la cellule Claude Code, et tout autre accès à Claude hérité, s'arrêtent au lanceur.
    bac.env |= ACCES_CLAUDE_HOSTILES
    env = bac.lancer().serveur()["env"]
    assert not [nom for nom in env if acces_claude(nom)]
    assert all(CLE_ANTHROPIC not in valeur for valeur in env.values())


def test_heritage_ecarte(bac: Bac) -> None:
    # Anciens noms et NEO4J_MCP_* hérités : retirés, la configuration ne vient que du lanceur.
    bac.env |= HERITAGE_HOSTILE
    env = bac.lancer().serveur()["env"]
    assert {nom: valeur for nom, valeur in env.items() if nom.startswith("NEO4J_")} == CONFIGURATION


def test_stdout_ne_porte_que_le_serveur(bac: Bac) -> None:
    lancement = bac.lancer()
    assert lancement.code == 0
    assert lancement.sortie == REPONSE_MCP


def test_stdin_intact(bac: Bac) -> None:
    lancement = bac.lancer()
    assert lancement.serveur()["stdin"] == REQUETE_MCP
    assert lancement.note("gcloud") == {
        "argv": [
            "secrets",
            "versions",
            "access",
            "latest",
            "--secret=neo4j-aura-poc",
            "--project=jleroy-labo",
        ],
        "stdin": "",
    }


def test_mot_de_passe_jamais_en_argument(bac: Bac) -> None:
    lancement = bac.lancer()
    gcloud = lancement.note("gcloud")
    assert gcloud is not None
    assert lancement.serveur()["argv"] == []
    assert all(MOT_DE_PASSE not in argument for argument in gcloud["argv"])


def test_stderr_filtre(bac: Bac) -> None:
    erreurs = bac.lancer().erreurs
    assert MOT_DE_PASSE not in erreurs
    assert INSTANCE not in erreurs
    assert "connexion à neo4j+s://‹instance›.databases.neo4j.io" in erreurs
    assert "ligne masquée : elle contenait le mot de passe" in erreurs


def test_stdout_masque_l_instance(bac: Bac) -> None:
    # L'identifiant n'atteint ni l'agent, ni le fournisseur du LLM, ni la trace (T3.1, choix de
    # Julien) ; le reste du canal passe octet pour octet, ligne par ligne.
    (bac.racine / "journal" / "neo4j-mcp-reponse.txt").write_text(REPONSE_MCP + RESULTAT_MCP)
    lancement = bac.lancer()
    assert lancement.sortie == REPONSE_MCP + RESULTAT_MCP.replace(INSTANCE, "‹instance›")
    perl = lancement.note("perl")
    assert perl is not None
    assert all(INSTANCE not in argument for argument in perl["argv"])


@pytest.mark.parametrize(
    "initialisation",
    [
        pytest.param(
            DEBUT_INITIALISATION + RESTE_INITIALISATION + f',"instructions":"{INSTRUCTIONS}"}}}}\n',
            id="en-dernier",
        ),
        pytest.param(
            f'{DEBUT_INITIALISATION}"instructions":"{INSTRUCTIONS}",{RESTE_INITIALISATION}}}}}\n',
            id="en-premier",
        ),
        pytest.param(
            DEBUT_INITIALISATION
            + RESTE_INITIALISATION
            + ',"instructions":"lire \\"get-schema\\" d\'abord\\nensuite read-cypher \\\\ fin"}}\n',
            id="echappements",
        ),
    ],
)
def test_instructions_retirees(bac: Bac, initialisation: str) -> None:
    # Elles citent get-schema, que le client retire (plan, D1) : aucune cellule ne les reçoit (choix
    # de Julien, T4.1) ; le reste de la réponse à initialize passe tel quel.
    (bac.racine / "journal" / "neo4j-mcp-reponse.txt").write_text(initialisation + RESULTAT_MCP)
    sortie = bac.lancer().sortie
    assert sortie == INITIALISATION_SANS_INSTRUCTIONS + RESULTAT_MCP.replace(INSTANCE, "‹instance›")


@pytest.mark.parametrize(
    "message",
    [
        # Un membre « instructions » ailleurs que dans la réponse à initialize reste.
        pytest.param(
            '{"jsonrpc":"2.0","id":3,"result":{"tools":[],"instructions":"garde-moi"}}\n',
            id="hors-initialize",
        ),
        # Dans un résultat de read-cypher, les guillemets sont échappés : rien d'un membre.
        pytest.param(
            '{"jsonrpc":"2.0","id":4,"result":{"content":[{"type":"text","text":'
            '"[{\\"serverInfo\\": 1, \\"instructions\\": \\"get-schema\\"}]"}]}}\n',
            id="texte-d-un-resultat",
        ),
    ],
)
def test_instructions_ailleurs_intactes(bac: Bac, message: str) -> None:
    (bac.racine / "journal" / "neo4j-mcp-reponse.txt").write_text(message)
    assert bac.lancer().sortie == message


def test_stdout_rendu_ligne_a_ligne(bac: Bac) -> None:
    # Un client MCP attend chaque réponse avant d'envoyer la requête suivante : le masque rend
    # chaque ligne aussitôt, sans attendre que son tampon se remplisse.
    installer(bac.racine / "outils", "neo4j-mcp", FAUX_DIALOGUE)
    processus = subprocess.Popen(
        [str(LANCEUR)],
        cwd=bac.racine / "travail",
        env=bac.env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    assert processus.stdin is not None and processus.stdout is not None
    try:
        processus.stdin.write('{"requete": 1}\n')
        processus.stdin.flush()
        pret, _, _ = select.select([processus.stdout], [], [], 10)
        assert pret, "réponse retenue dans un tampon"
        assert processus.stdout.readline() == '{"reponse": 1}\n'
    finally:
        processus.kill()
        processus.wait()


def test_stdout_sans_fin_de_ligne(bac: Bac) -> None:
    # Le filtre n'ajoute rien : un dernier message sans fin de ligne reste tel quel.
    (bac.racine / "journal" / "neo4j-mcp-reponse.txt").write_text(REPONSE_MCP.rstrip("\n"))
    assert bac.lancer().sortie == REPONSE_MCP.rstrip("\n")


def test_exec_remplace_le_lanceur(bac: Bac) -> None:
    # Même processus : un signal ou l'arrêt du groupe de processus atteint le serveur.
    lancement = bac.lancer()
    assert lancement.serveur()["pid"] == lancement.pid


@pytest.mark.parametrize(
    ("secret", "code"),
    [
        pytest.param(SECRET, 1, id="secret-illisible"),
        pytest.param(SECRET.replace(f"NEO4J_PASSWORD={MOT_DE_PASSE}\n", ""), 0, id="cle-absente"),
    ],
)
def test_secret_inutilisable(bac: Bac, secret: str, code: int) -> None:
    bac.repondre(secret, code)
    lancement = bac.lancer()
    assert (lancement.code, lancement.sortie, lancement.note("neo4j-mcp")) == (2, "", None)


@pytest.mark.parametrize("outil", ["neo4j-mcp", "perl"])
def test_outil_introuvable(bac: Bac, outil: str) -> None:
    # Sans perl, le canal MCP ne serait pas masqué : rien ne se lance.
    (bac.racine / "outils" / outil).unlink()
    lancement = bac.lancer()
    assert (lancement.code, lancement.sortie, lancement.note("neo4j-mcp")) == (2, "", None)
    assert f"{outil} introuvable" in lancement.erreurs


def test_arguments_refuses(bac: Bac) -> None:
    # neo4j-mcp donne priorité à ses options sur l'environnement : --read-only false rouvrirait
    # l'écriture. Le lanceur n'en transmet aucune.
    lancement = bac.lancer("--read-only", "false")
    assert (lancement.code, lancement.sortie, lancement.note("neo4j-mcp")) == (2, "", None)
