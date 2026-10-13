"""Section embeddings de scripts/verifier.sh (spec 003, T3.1 ; plan D3), sans base ni réseau.

Le PATH ne contient que bash, cat, dirname, sed et de faux gcloud et cypher-shell. Pour
cypher/90-verification.cypher, le faux cypher-shell rend une ligne
« section|contrôle|attendu|obtenu » par contrôle de la section embeddings, contrôle et attendu
lus dans le fichier, l'obtenu donné par le test (par défaut l'attendu : section conforme), plus
une ligne de la section types. Seule la base calcule l'obtenu : verifier.sh --section embeddings
se lance aussi sur la vraie base, rouge tant que les vecteurs manquent (T3.1), vert après leur
chargement (T6.2).
"""

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[2]
SCRIPT = RACINE / "scripts" / "verifier.sh"
VERIFICATION = RACINE / "cypher" / "90-verification.cypher"
SECRET = (
    "NEO4J_URI=neo4j+s://instance.databases.neo4j.io\nNEO4J_USERNAME=instance\n"
    "NEO4J_PASSWORD=mot-de-passe-factice\nNEO4J_DATABASE=instance\n"
)
COMMANDES = ("bash", "cat", "dirname", "sed")
# Un contrôle de la section dans 90-verification.cypher : le littéral
# « embeddings|contrôle|attendu| », entre apostrophes, ou entre guillemets quand le contrôle
# porte une apostrophe.
MOTIF = r"""(['"])embeddings\|([^|]*)\|([^|]*)\|\1"""
FAUX_GCLOUD = f"import sys\nsys.stdout.write({SECRET!r})\n"
FAUX_CYPHER_SHELL = f"""
import json, re, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
argv = sys.argv[1:]
with (journal / "cypher-shell.jsonl").open("a") as note:
    note.write(json.dumps(argv) + "\\n")
if "--file" not in argv:
    print('aura\\n"Neo4j 2026.09 (enterprise)"')
    sys.exit(0)
texte = Path(argv[argv.index("--file") + 1]).read_text()
obtenus = json.loads((journal / "obtenus.json").read_text())
print("ligne")
print('"types|(:Type)|18|18"')
for _, controle, attendu in re.findall({MOTIF!r}, texte):
    print(f'"embeddings|{{controle}}|{{attendu}}|{{obtenus.get(controle, attendu)}}"')
"""

VECTEURS = "(:Description) à embedding"
AUTRES = "embedding hors VECTOR de 3 072 dimensions"
INDEX = "index descriptions_texte (type, schéma, dimensions, similarité, quantification, état)"
# Ce que la spec demande (plan, D2 et D3) : 5 233 vecteurs, tous VECTOR de 3 072 dimensions, et
# l'index vectoriel des descriptions en ligne, cosine, sans quantification.
CONTROLES = {
    VECTEURS: "5233",
    AUTRES: "0",
    INDEX: "VECTOR, Description.embedding, 3072, cosine, none, ONLINE",
}
DEFINITION = CONTROLES[INDEX]


@dataclass
class Lancement:
    """Ce qu'un lancement a produit : code retour, flux, arguments des appels à cypher-shell."""

    code: int
    sortie: str
    erreurs: str
    appels: list[list[str]]


@dataclass
class Bac:
    """Bac à sable : faux outils, HOME vide, journal des appels."""

    racine: Path
    env: dict[str, str]

    def lancer(self, *arguments: str, obtenus: dict[str, str] | None = None) -> Lancement:
        journal = self.racine / "journal"
        (journal / "obtenus.json").write_text(json.dumps(obtenus or {}))
        fini = subprocess.run(
            [str(SCRIPT), *arguments],
            cwd=self.racine,
            env=self.env,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        notes = journal / "cypher-shell.jsonl"
        lignes = notes.read_text().splitlines() if notes.exists() else []
        appels = [json.loads(ligne) for ligne in lignes]
        return Lancement(fini.returncode, fini.stdout, fini.stderr, appels)


def installer(outils: Path, nom: str, code: str) -> None:
    script = outils / nom
    script.write_text(f"#!{sys.executable} -I\n{code}")
    script.chmod(0o755)


@pytest.fixture
def bac(tmp_path: Path) -> Bac:
    for dossier in ("home", "outils", "journal"):
        (tmp_path / dossier).mkdir()
    for commande in COMMANDES:
        chemin = shutil.which(commande)
        assert chemin is not None, commande
        (tmp_path / "outils" / commande).symlink_to(chemin)
    installer(tmp_path / "outils", "gcloud", FAUX_GCLOUD)
    installer(tmp_path / "outils", "cypher-shell", FAUX_CYPHER_SHELL)
    return Bac(tmp_path, {"HOME": str(tmp_path / "home"), "PATH": str(tmp_path / "outils")})


def test_controles_de_la_section() -> None:
    # Contrôles et attendus tels que 90-verification.cypher les écrit : ceux de la spec, une fois.
    trouves = re.findall(MOTIF, VERIFICATION.read_text())
    assert [(controle, attendu) for _, controle, attendu in trouves] == list(CONTROLES.items())


@pytest.mark.parametrize(
    "fragment",
    [
        # L'index se cherche par son nom : réglé autrement, il montre ses options, pas « aucun ».
        pytest.param("WHERE name = 'descriptions_texte'", id="index-par-son-nom"),
        # SHOW INDEXES écrit similarité et quantification en capitales (« COSINE », Cypher 25).
        pytest.param("toLower(config.`vector.similarity_function`)", id="similarite-minuscules"),
        pytest.param("toLower(config.`vector.quantization.type`)", id="quantification-minuscules"),
        # Type et dimension jugés sans erreur : vector_dimension_count() lève 22N27 sur une
        # liste, ce qui arrêterait toute la vérification (sondé sur Aura le 2026-10-13).
        pytest.param("IS NOT :: VECTOR(3072)", id="dimension-sans-erreur"),
    ],
)
def test_requetes_de_la_section(fragment: str) -> None:
    assert fragment in VERIFICATION.read_text()


def test_section_annoncee(bac: Bac) -> None:
    lancement = bac.lancer("--help")
    assert lancement.code == 0
    assert "global ou embeddings" in lancement.sortie


def test_section_conforme(bac: Bac) -> None:
    lancement = bac.lancer("--section", "embeddings")
    assert lancement.code == 0, lancement.erreurs
    assert "── embeddings\n" in lancement.sortie
    for controle, attendu in CONTROLES.items():
        assert f"✓ {controle} : {attendu}\n" in lancement.sortie
    assert "CONFORME : 3 contrôles" in lancement.sortie
    # Les lignes des autres sections ne sont ni montrées ni comptées.
    assert "(:Type)" not in lancement.sortie


def test_verification_en_lecture_seule(bac: Bac) -> None:
    lancement = bac.lancer("--section", "embeddings")
    [appel] = [a for a in lancement.appels if "--file" in a]
    assert Path(appel[appel.index("--file") + 1]).resolve() == VERIFICATION
    assert appel[appel.index("--access-mode") + 1] == "read"


@pytest.mark.parametrize(
    ("controle", "obtenu"),
    [
        pytest.param(VECTEURS, "5232", id="description-sans-vecteur"),
        pytest.param(AUTRES, "1", id="vecteur-d-une-autre-dimension"),
        pytest.param(INDEX, "aucun", id="index-absent"),
        pytest.param(INDEX, DEFINITION.replace("ONLINE", "POPULATING"), id="index-en-remplissage"),
        # IF NOT EXISTS garderait sans rien dire un index réglé par défaut (binary depuis 2026.08).
        pytest.param(INDEX, DEFINITION.replace("none", "binary"), id="quantification-par-defaut"),
        pytest.param(INDEX, DEFINITION.replace("3072", "768"), id="index-d-une-autre-dimension"),
    ],
)
def test_ecart_juge(bac: Bac, controle: str, obtenu: str) -> None:
    # Un seul contrôle s'écarte : lui seul est jugé en écart, et le code dit « écart constaté ».
    lancement = bac.lancer("--section", "embeddings", obtenus={controle: obtenu})
    assert lancement.code == 1, lancement.erreurs
    assert f"✗ {controle} : {obtenu}, attendu {CONTROLES[controle]}\n" in lancement.sortie
    assert "ÉCART : 1 contrôle(s) sur 3" in lancement.sortie
    for autre, attendu in CONTROLES.items():
        if autre != controle:
            assert f"✓ {autre} : {attendu}\n" in lancement.sortie


def test_toutes_les_sections(bac: Bac) -> None:
    # Sans option, la section embeddings est jugée avec les autres (T6.2 : base entière conforme).
    lancement = bac.lancer()
    assert lancement.code == 0, lancement.erreurs
    assert "✓ (:Type) : 18\n" in lancement.sortie
    assert "CONFORME : 4 contrôles" in lancement.sortie
