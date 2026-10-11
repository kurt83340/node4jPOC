"""Sonde du renommage (scripts/charger.sh --sonde-renommage, spec 002 T7.5) et bascule du schéma
(--schema en|fr, --explain, T6.1), sans base ni réseau.

Le PATH ne contient que bash, cat, dirname, sed, tr et de faux gcloud et cypher-shell. Le faux
cypher-shell note chaque appel et répond à toute requête (code 0, sans ligne), sauf règle posée par
le test. La sonde passe tout par EXPLAIN en lecture seule, puis choisit le mécanisme ; la bascule
supprime contraintes et index, renomme avec la carte, recrée ceux de la langue visée ; --explain
n'écrit rien ; --tout refuse une base anglaise.
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
COMMANDES = ("bash", "cat", "dirname", "sed", "tr")
FAUX_GCLOUD = f"""
import sys
sys.stdout.write({SECRET!r})
"""
# Règles du test (journal/regles.json) : la première dont le motif est dans la requête répond ; une
# règle à « fois » comptées s'efface après sa dernière réponse.
FAUX_CYPHER_SHELL = """
import json, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
argv = sys.argv[1:]
requete = argv[-1]
with (journal / "cypher-shell.jsonl").open("a") as note:
    note.write(json.dumps({"argv": argv, "requete": requete}) + "\\n")
regles = json.loads((journal / "regles.json").read_text())
for regle in regles:
    if regle["motif"] in requete:
        if regle["fois"] is not None:
            regle["fois"] -= 1
            if regle["fois"] == 0:
                regles.remove(regle)
            (journal / "regles.json").write_text(json.dumps(regles))
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

    def regles(self, *regles: tuple[str, str, int] | tuple[str, str, int, int]) -> None:
        texte = json.dumps(
            [
                {"motif": r[0], "sortie": r[1], "code": r[2], "fois": (r[3:] or (None,))[0]}
                for r in regles
            ]
        )
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
        lignes = journal.read_text().splitlines() if journal.exists() else []
        appels = [json.loads(ligne) for ligne in lignes]
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


# --- Bascule du schéma (--schema en|fr, T6.1) --------------------------------------------------

AVANT = 'compte\n"8859 nœuds et 113700 relations"'
SANS_RESTE = 'restes\n"0 nœuds, 0 relations"'
CONTRAINTES = 'name\n"type_id"\n"forme_id"'
INDEX = 'name\n"noms_plein_texte"'
REGLES_BASCULE = (
    ("AS compte", AVANT, 0),
    ("AS restes", SANS_RESTE, 0),
    ("SHOW CONSTRAINTS", CONTRAINTES, 0),
    ("SHOW INDEXES", INDEX, 0),
)


def parametres(appel: dict[str, Any]) -> list[str]:
    argv = appel["argv"]
    return [argv[i + 1] for i, a in enumerate(argv) if a == "-P"]


def fichier(appel: dict[str, Any]) -> str | None:
    argv = appel["argv"]
    return argv[argv.index("--file") + 1] if "--file" in argv else None


def test_bascule_vers_l_anglais(bac: Bac) -> None:
    bac.regles(*REGLES_BASCULE)
    lancement = bac.lancer("--schema", "en")
    assert lancement.code == 0, lancement.sortie
    assert "SCHÉMA en : 8859 nœuds et 113700 relations, plus aucun nom de l'autre langue" in (
        lancement.sortie
    )
    ordre = [fichier(a) or a["requete"] for a in lancement.requetes]
    supprimees = [r for r in ordre if r.startswith("DROP ")]
    assert supprimees == [
        "DROP CONSTRAINT `type_id` IF EXISTS",
        "DROP CONSTRAINT `forme_id` IF EXISTS",
        "DROP INDEX `noms_plein_texte` IF EXISTS",
    ]
    renommer = next(i for i, r in enumerate(ordre) if r.endswith("anglais/renommer.cypher"))
    recreer = next(i for i, r in enumerate(ordre) if r.endswith("anglais/contraintes.cypher"))
    attendre = ordre.index("CALL db.awaitIndexes(300)")
    assert (
        max(i for i, r in enumerate(ordre) if r.startswith("DROP ")) < renommer < recreer < attendre
    )
    assert not any(r.endswith("00-contraintes.cypher") for r in ordre)


def test_carte_et_sens_passes_au_renommage(bac: Bac) -> None:
    bac.regles(*REGLES_BASCULE)
    lancement = bac.lancer("--schema", "en")
    [appel] = [a for a in lancement.requetes if (fichier(a) or "").endswith("renommer.cypher")]
    carte, sens = parametres(appel)
    assert sens == "{langue: 'en'}"
    assert carte.startswith("{cartes: {   en: {     labels: {")
    assert "Forme: 'Form'" in carte
    assert "//" not in carte
    assert "\n" not in carte


def test_retour_au_francais(bac: Bac) -> None:
    bac.regles(*REGLES_BASCULE)
    lancement = bac.lancer("--schema", "fr")
    assert lancement.code == 0, lancement.sortie
    fichiers = [fichier(a) for a in lancement.requetes if fichier(a)]
    assert [f.rsplit("/", 2)[-2:] for f in fichiers if f] == [
        ["anglais", "renommer.cypher"],
        ["cypher", "00-contraintes.cypher"],
    ]
    assert all(
        "{langue: 'fr'}" in parametres(a) for a in lancement.requetes if "AS restes" in a["requete"]
    )


def test_bascule_inachevee(bac: Bac) -> None:
    bac.regles(("AS restes", 'restes\n"3 nœuds, 0 relations"', 0), *REGLES_BASCULE)
    lancement = bac.lancer("--schema", "en")
    assert lancement.code == 1
    assert "✗ noms de l'autre langue restants : 3 nœuds, 0 relations" in lancement.sortie


def test_graphe_change(bac: Bac) -> None:
    # Le second comptage diffère du premier : le renommage a perdu ou doublé des éléments.
    apres = 'compte\n"8859 nœuds et 113699 relations"'
    bac.regles(("AS compte", AVANT, 0, 1), ("AS compte", apres, 0), *REGLES_BASCULE[1:])
    lancement = bac.lancer("--schema", "en")
    assert lancement.code == 1
    assert "✗ graphe changé : 8859 nœuds et 113699 relations, avant 8859 nœuds et 113700" in (
        lancement.sortie
    )


def test_renommage_en_echec(bac: Bac) -> None:
    bac.regles(
        ("renommer.cypher", "Neo.TransientError.General.MemoryPoolOutOfMemoryError", 1),
        *REGLES_BASCULE,
    )
    lancement = bac.lancer("--schema", "en")
    assert lancement.code == 2
    assert "renommage interrompu, à relancer : Neo.TransientError" in lancement.sortie
    assert not any((fichier(a) or "").endswith("contraintes.cypher") for a in lancement.requetes)


def test_explain_n_ecrit_rien(bac: Bac) -> None:
    bac.regles(*REGLES_BASCULE)
    lancement = bac.lancer("--schema", "en", "--explain")
    assert lancement.code == 0, lancement.sortie
    # 4 requêtes du renommage, 11 contraintes et index, l'attente des index.
    assert "PLANIFIÉ : 16 requêtes, rien d'exécuté." in lancement.sortie
    assert "  · contraintes à supprimer : type_id forme_id" in lancement.sortie
    for appel in lancement.requetes:
        argv = appel["argv"]
        assert argv[argv.index("--access-mode") + 1] == "read", appel["requete"]
        assert "--file" not in argv
        assert not appel["requete"].startswith(("DROP ", "CALL db.awaitIndexes"))
    expliquees = [a["requete"] for a in lancement.requetes if a["requete"].startswith("EXPLAIN ")]
    assert len(expliquees) == 16
    assert any("CREATE FULLTEXT INDEX names_fulltext" in r for r in expliquees)
    assert all(
        "{langue: 'en'}" in parametres(a) for a in lancement.requetes if "EXPLAIN" in a["requete"]
    )


def test_explain_libelles(bac: Bac) -> None:
    # Une requête porte le commentaire qui la précède sans ligne vide, sinon le début de son code :
    # l'en-tête d'un fichier, suivi d'une ligne vide, ne nomme pas sa première requête.
    bac.regles(*REGLES_BASCULE)
    lancement = bac.lancer("--schema", "fr", "--explain")
    assert "✓ Labels des nœuds. : planifiée" in lancement.sortie
    premiere = "CREATE CONSTRAINT type_id IF NOT EXISTS FOR (n:Type) REQUIRE n.id IS U"
    assert f"✓ {premiere} : planifiée" in lancement.sortie
    assert "✓ attente des index en ligne : planifiée" in lancement.sortie


def test_explain_non_planifie(bac: Bac) -> None:
    bac.regles(("EXPLAIN CREATE FULLTEXT", "Invalid input 'FULLTEXT'", 1), *REGLES_BASCULE)
    lancement = bac.lancer("--schema", "en", "--explain")
    assert lancement.code == 1
    assert "NON PLANIFIÉ : 1 requête(s) sur 16." in lancement.sortie


@pytest.mark.parametrize(
    "arguments",
    [
        ("--schema",),
        ("--schema", "de"),
        ("--schema", "en", "--tout"),
        ("--schema", "en", "--explain", "x"),
    ],
)
def test_schema_mal_demande(bac: Bac, arguments: tuple[str, ...]) -> None:
    lancement = bac.lancer(*arguments)
    assert lancement.code == 2
    assert "Usage : scripts/charger.sh" in lancement.sortie
    assert lancement.requetes == []


def test_tout_refuse_sur_une_base_anglaise(bac: Bac) -> None:
    bac.regles(("AS restes", 'restes\n"8859 nœuds, 113700 relations"', 0))
    lancement = bac.lancer("--tout")
    assert lancement.code == 2
    assert (
        "base en anglais (8859 nœuds, 113700 relations) : scripts/charger.sh --schema fr d'abord"
        in (lancement.sortie)
    )
    [appel] = lancement.requetes
    assert "{langue: 'fr'}" in parametres(appel)
