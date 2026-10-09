"""Arrêt des lectures des agents restées actives sur Aura (scripts/transactions.sh, spec 002 T4.3,
D13). Contrôle sur la vraie base en T7.4 (droit d'arrêter et mode lecture sur Aura Free).

Aucun outil réel : le PATH ne contient que bash, sleep et de faux gcloud et cypher-shell. Le faux
cypher-shell note chaque appel et répond selon le scénario du test : les transactions que TERMINATE
arrête, puis le nombre de lectures d'agents encore listées à chaque relecture.
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
SCRIPT = RACINE / "scripts" / "transactions.sh"
INSTANCE = "f4c7e9a2"
MOT_DE_PASSE = "mdp-factice-du-banc"
SECRET = (
    f"NEO4J_URI=neo4j+s://{INSTANCE}.databases.neo4j.io\nNEO4J_USERNAME={INSTANCE}\n"
    f"NEO4J_PASSWORD={MOT_DE_PASSE}\nNEO4J_DATABASE={INSTANCE}\n"
)
COMMANDES = ("bash", "sleep")
FAUX_GCLOUD = f"import sys\nsys.stdout.write({SECRET!r})\n"
# Scénario (journal/scenario.json) : « arretees », identifiants rendus par TERMINATE ;
# « restantes », lectures encore listées à chaque relecture (la dernière valeur se répète) ;
# « erreur_arret » et « erreur_releve », [sortie, code] de l'appel qui échoue ; « entete_vide » :
# un résultat vide écrit son en-tête (sinon rien, comme cypher-shell 2026.09 selon la revue).
FAUX_CYPHER_SHELL = """
import json, os, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
argv = sys.argv[1:]
requete = argv[-1]
noms = sorted(nom for nom in os.environ if nom.startswith("NEO4J"))
with (journal / "cypher-shell.jsonl").open("a") as note:
    note.write(json.dumps({"argv": argv, "requete": requete, "env": noms}) + "\\n")
scenario = json.loads((journal / "scenario.json").read_text())
if "dbms.components" in requete:
    print('aura\\n"Neo4j 2026.09 (enterprise)"')
elif "TERMINATE TRANSACTIONS" in requete:
    if "erreur_arret" in scenario:
        print(scenario["erreur_arret"][0])
        sys.exit(scenario["erreur_arret"][1])
    lignes = [f'"{ident}", "Transaction terminated."' for ident in scenario.get("arretees", [])]
    if lignes or scenario.get("entete_vide"):
        print("\\n".join(["id, message", *lignes]))
else:
    if "erreur_releve" in scenario:
        print(scenario["erreur_releve"][0])
        sys.exit(scenario["erreur_releve"][1])
    compteur = journal / "releves"
    rang = int(compteur.read_text()) if compteur.exists() else 0
    compteur.write_text(str(rang + 1))
    restantes = scenario.get("restantes", [0])
    nombre = restantes[min(rang, len(restantes) - 1)]
    if nombre or scenario.get("entete_vide"):
        print("\\n".join(["id", *(f'"base-transaction-{rang}{i}"' for i in range(nombre))]))
"""


@dataclass
class Lancement:
    """Ce qu'un lancement a produit : code retour, flux, et les appels au faux cypher-shell."""

    code: int
    sortie: str
    erreurs: str
    appels: list[dict[str, Any]]

    def requetes(self) -> list[str]:
        """Les requêtes, hors du test de connexion (ping_aura)."""
        return [a["requete"] for a in self.appels if "dbms.components" not in a["requete"]]


@dataclass
class Bac:
    """Bac à sable : faux outils, HOME et dossier de travail vides."""

    racine: Path
    env: dict[str, str]

    def scenario(self, **scenario: Any) -> None:
        (self.racine / "journal" / "scenario.json").write_text(json.dumps(scenario))

    def lancer(self, *arguments: str, **env: str) -> Lancement:
        resultat = subprocess.run(
            [str(SCRIPT), *arguments],
            cwd=self.racine / "travail",
            env=self.env | env,
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
    nouveau.scenario()
    return nouveau


def test_syntaxe() -> None:
    # DoD de T4.3 : bash -n.
    fini = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True, text=True, check=False)
    assert fini.returncode == 0, fini.stderr


@pytest.mark.parametrize("entete_vide", [False, True])
def test_aucune_lecture_active(bac: Bac, entete_vide: bool) -> None:
    # Un résultat vide : rien du tout, ou son seul en-tête ; aucune lecture dans les deux cas.
    bac.scenario(entete_vide=entete_vide)
    lancement = bac.lancer()
    assert lancement.code == 0, lancement.erreurs
    # stdout ne porte que le compte rendu, que le harnais affiche.
    assert lancement.sortie == "transactions : aucune lecture d'agent active sur Aura\n"
    arreter, lister = lancement.requetes()
    for requete in (arreter, lister):
        assert requete.startswith("SHOW TRANSACTIONS\nYIELD transactionId AS id, metaData\n")
        assert "WHERE metaData.app STARTS WITH 'MCP4NEO4J/'" in requete
    assert "TERMINATE TRANSACTIONS id\nYIELD message\nRETURN id, message" in arreter
    assert lister.endswith("RETURN id")
    assert "TERMINATE" not in lister
    # En lecture, comme toutes les lectures du banc (code-map) ; mot de passe jamais en argument.
    # (Le test de connexion de commun.sh, ping_aura, garde le mode par défaut, comme partout.)
    for appel in lancement.appels:
        argv = appel["argv"]
        assert MOT_DE_PASSE not in " ".join(argv)
        if "dbms.components" not in appel["requete"]:
            assert argv[argv.index("--access-mode") + 1] == "read"
        assert appel["env"] == [
            "NEO4J_DATABASE",
            "NEO4J_PASSWORD",
            "NEO4J_URI",
            "NEO4J_USERNAME",
        ]


def test_lectures_arretees_puis_relues(bac: Bac) -> None:
    # TERMINATE est asynchrone : une lecture arrêtée reste listée un moment, le script relit.
    bac.scenario(arretees=["base-transaction-7", "base-transaction-9"], restantes=[1, 0])
    lancement = bac.lancer()
    assert lancement.code == 0, lancement.erreurs
    assert lancement.sortie == "transactions : 2 lecture(s) d'agent arrêtée(s) sur Aura\n"
    assert len(lancement.requetes()) == 3


def test_lecture_qui_reste(bac: Bac) -> None:
    # Toujours listée après les relectures : écart (1), la campagne s'arrête.
    bac.scenario(arretees=["base-transaction-7"], restantes=[1])
    lancement = bac.lancer(TRANSACTIONS_RELECTURES="2")
    assert lancement.code == 1
    assert "1 lecture(s) d'agent encore listée(s) après 2 relecture(s)" in lancement.erreurs
    assert len(lancement.requetes()) == 4
    assert lancement.sortie == ""


def test_relectures_sans_attente(bac: Bac) -> None:
    # Aucune relecture demandée : un seul relevé, juste après l'arrêt (la borne).
    bac.scenario(arretees=["base-transaction-7"], restantes=[1])
    lancement = bac.lancer(TRANSACTIONS_RELECTURES="0")
    assert lancement.code == 1
    assert len(lancement.requetes()) == 2


@pytest.mark.parametrize(
    ("cle", "message"),
    [
        ("erreur_arret", "arrêt des lectures refusé"),
        ("erreur_releve", "relecture des transactions refusée"),
    ],
)
def test_commande_refusee(bac: Bac, cle: str, message: str) -> None:
    # Arrêt ou relecture refusés (droit, mode lecture, Aura injoignable) : erreur technique, sortie
    # filtrée (identifiant masqué).
    bac.scenario(**{cle: [f"Permission denied for user {INSTANCE}", 1]})
    lancement = bac.lancer()
    assert lancement.code == 2
    assert f"{message} : Permission denied for user ‹instance›" in lancement.erreurs
    assert INSTANCE not in lancement.erreurs + lancement.sortie


def test_mot_de_passe_jamais_affiche(bac: Bac) -> None:
    bac.scenario(erreur_arret=[f"échec, mot de passe {MOT_DE_PASSE}", 1])
    lancement = bac.lancer()
    assert lancement.code == 2
    assert "sortie masquée" in lancement.erreurs
    assert MOT_DE_PASSE not in lancement.erreurs + lancement.sortie


def test_argument_refuse(bac: Bac) -> None:
    lancement = bac.lancer("--tout")
    assert lancement.code == 2
    assert "aucun argument" in lancement.erreurs
    assert lancement.appels == []


def test_relectures_invalides(bac: Bac) -> None:
    lancement = bac.lancer(TRANSACTIONS_RELECTURES="dix")
    assert lancement.code == 2
    assert "TRANSACTIONS_RELECTURES" in lancement.erreurs
    assert lancement.appels == []
