"""Sonde du renommage (scripts/charger.sh --sonde-renommage, spec 002 T7.5) et bascule du schéma
(--schema en|fr, --explain, T6.1), sans base ni réseau.

Le PATH ne contient que bash, cat, dirname, sed, tr et de faux gcloud et cypher-shell. Le faux
cypher-shell note chaque appel et répond à toute requête (code 0, sans ligne), sauf règle posée par
le test. La sonde passe tout par EXPLAIN en lecture seule, puis choisit le mécanisme ; la bascule
supprime contraintes et index, renomme avec la carte, recrée ceux de la langue visée ; --explain
n'écrit rien ; --tout refuse une base anglaise.

Jeton du chargement (spec 003, T3.2) : la fonction de commun.sh, appelée par un script qui la
source. Le faux gcloud rend un jeton factice, hors du motif ya29. des jetons Google ; le faux
cypher-shell note aussi son stdin et son environnement : le jeton n'y passe que par la ligne :param
de stdin.
"""

import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
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
# Emprunt du compte (journal/emprunt.json) : le jeton rendu, l'erreur et le code de gcloud.
FAUX_GCLOUD = f"""
import json, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
argv = sys.argv[1:]
with (journal / "gcloud.jsonl").open("a") as note:
    note.write(json.dumps(argv) + "\\n")
if argv[:2] == ["auth", "print-access-token"]:
    emprunt = json.loads((journal / "emprunt.json").read_text())
    sys.stdout.write(emprunt["jeton"] + "\\n")
    sys.stderr.write(emprunt["erreur"])
    sys.exit(emprunt["code"])
sys.stdout.write({SECRET!r})
"""
# Règles du test (journal/regles.json) : la première dont le motif est dans la requête répond ; une
# règle à « fois » comptées s'efface après sa dernière réponse ; « {entree} » y cite la requête
# reçue. Sans requête en argument ni --file, les requêtes arrivent sur stdin.
FAUX_CYPHER_SHELL = """
import json, os, sys
from pathlib import Path
journal = Path(__file__).resolve().parent.parent / "journal"
argv = sys.argv[1:]
entree = None
a_valeur = {"--format", "--access-mode", "-P"}
if "--file" not in argv and (argv[-1].startswith("-") or argv[-2] in a_valeur):
    entree = sys.stdin.read()
requete = argv[-1] if entree is None else entree
with (journal / "cypher-shell.jsonl").open("a") as note:
    appel = {"argv": argv, "requete": requete, "entree": entree, "env": dict(os.environ)}
    note.write(json.dumps(appel) + "\\n")
regles = json.loads((journal / "regles.json").read_text())
for regle in regles:
    if regle["motif"] in requete:
        if regle["fois"] is not None:
            regle["fois"] -= 1
            if regle["fois"] == 0:
                regles.remove(regle)
            (journal / "regles.json").write_text(json.dumps(regles))
        print(regle["sortie"].replace("{entree}", requete))
        sys.exit(regle["code"])
if "dbms.components" in requete:
    print('aura\\n"Neo4j 2026.09 (enterprise)"')
"""
ABSENTE = "There is no procedure with the name `apoc.refactor.rename.label` registered."
COMMUN = RACINE / "scripts" / "commun.sh"
# Hors du motif ya29. des jetons Google, que gitleaks prendrait pour un vrai (plan, D17).
JETON = "jeton-factice-du-chargement"
COMPTE = "aura-genai@jleroy-labo.iam.gserviceaccount.com"
# Un script qui source commun.sh comme charger.sh, lit les identifiants, exécute un fichier avec le
# jeton, puis écrit SORTIE, le texte que charger.sh affiche et journalise.
HARNAIS = """set -euo pipefail
source "$1"
shift
trouver_outils
lire_identifiants
code=0
cypher_fichier_avec_jeton "$@" || code=$?
printf '%s\\n' "$SORTIE"
exit "$code"
"""


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

    def emprunt(self, jeton: str = "", erreur: str = "", code: int = 0) -> None:
        texte = json.dumps({"jeton": jeton or JETON, "erreur": erreur, "code": code})
        (self.racine / "journal" / "emprunt.json").write_text(texte)

    def lancer(self, *arguments: str) -> Lancement:
        return self.executer([str(SCRIPT), *arguments])

    def avec_jeton(self, fichier: Path, *options: str) -> Lancement:
        """cypher_fichier_avec_jeton de commun.sh, dans un script qui la source comme charger.sh."""
        harnais = ["bash", "-c", HARNAIS, "harnais", str(COMMUN), str(fichier)]
        return self.executer([*harnais, *options])

    def gcloud(self) -> list[list[str]]:
        journal = self.racine / "journal" / "gcloud.jsonl"
        lignes = journal.read_text().splitlines() if journal.exists() else []
        return [json.loads(ligne) for ligne in lignes]

    def executer(self, commande: list[str]) -> Lancement:
        fini = subprocess.run(
            commande,
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
    nouveau.emprunt()
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
SANS_RESTE = 'restes\n"0 nœuds, 0 relations, 0 clés"'
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
    bac.regles(("AS restes", 'restes\n"3 nœuds, 0 relations, 0 clés"', 0), *REGLES_BASCULE)
    lancement = bac.lancer("--schema", "en")
    assert lancement.code == 1
    assert "✗ noms de l'autre langue restants : 3 nœuds, 0 relations, 0 clés" in lancement.sortie


def test_cles_restantes(bac: Bac) -> None:
    # Labels et types renommés, des clés non : la bascule n'est pas finie (revue adverse, phase 6).
    bac.regles(("AS restes", 'restes\n"0 nœuds, 0 relations, 12 clés"', 0), *REGLES_BASCULE)
    lancement = bac.lancer("--schema", "en")
    assert lancement.code == 1
    assert "✗ noms de l'autre langue restants : 0 nœuds, 0 relations, 12 clés" in lancement.sortie
    [requete] = {a["requete"] for a in lancement.requetes if "AS restes" in a["requete"]}
    # Les clés à renommer, comptées sur les nœuds et sur les relations.
    assert requete.count("WHERE cle IN keys(carte.cles)") == 2
    assert "MATCH (n)\n" in requete
    assert "MATCH ()-[r]->()\n" in requete


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
    # 4 requêtes du renommage, 12 contraintes et index (le vectoriel compris), l'attente des index.
    assert "PLANIFIÉ : 17 requêtes, rien d'exécuté." in lancement.sortie
    assert "  · contraintes à supprimer : type_id forme_id" in lancement.sortie
    for appel in lancement.requetes:
        argv = appel["argv"]
        assert argv[argv.index("--access-mode") + 1] == "read", appel["requete"]
        assert "--file" not in argv
        assert not appel["requete"].startswith(("DROP ", "CALL db.awaitIndexes"))
    expliquees = [a["requete"] for a in lancement.requetes if a["requete"].startswith("EXPLAIN ")]
    assert len(expliquees) == 17
    assert any("CREATE FULLTEXT INDEX names_fulltext" in r for r in expliquees)
    assert any("CREATE VECTOR INDEX descriptions_text IF NOT EXISTS" in r for r in expliquees)
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
    assert "NON PLANIFIÉ : 1 requête(s) sur 17." in lancement.sortie


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
    bac.regles(("AS restes", 'restes\n"2583 nœuds, 113700 relations, 0 clés"', 0))
    lancement = bac.lancer("--tout")
    assert lancement.code == 2
    assert (
        "base en anglais (2583 nœuds, 113700 relations, 0 clés) : scripts/charger.sh --schema fr "
        "d'abord" in lancement.sortie
    )
    [appel] = lancement.requetes
    assert "{langue: 'fr'}" in parametres(appel)


# --- Fichiers de la bascule vérifiés avant toute suppression (T10.0) --------------------------


def absent(chemin: Path) -> None:
    chemin.unlink()


def vide(chemin: Path) -> None:
    chemin.write_text("")


def dossier(chemin: Path) -> None:
    chemin.unlink()
    chemin.mkdir()


@pytest.mark.parametrize(
    ("langue", "fichier", "defaut"),
    [
        ("en", "anglais/renommer.cypher", absent),
        ("en", "anglais/contraintes.cypher", absent),
        ("en", "anglais/renommer.cypher", vide),
        ("en", "anglais/contraintes.cypher", dossier),
        ("fr", "00-contraintes.cypher", absent),
    ],
    ids=["renommer-absent", "contraintes-en-absent", "renommer-vide", "dossier", "retour-fr"],
)
def test_fichier_absent_rien_n_est_supprime(
    bac: Bac, langue: str, fichier: str, defaut: Callable[[Path], None]
) -> None:
    # Une copie du dépôt, fichier gâté : la base garderait sinon ses données sans contraintes.
    depot = bac.racine / "depot"
    shutil.copytree(RACINE / "scripts", depot / "scripts")
    shutil.copytree(RACINE / "cypher", depot / "cypher")
    defaut(depot / "cypher" / fichier)
    bac.regles(*REGLES_BASCULE)
    fini = subprocess.run(
        [str(depot / "scripts" / "charger.sh"), "--schema", langue],
        cwd=bac.racine,
        env=bac.env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert fini.returncode == 2
    assert f"fichier de la bascule absent ou vide, rien n'est supprimé : {fichier}" in fini.stderr
    journal = bac.racine / "journal" / "cypher-shell.jsonl"
    requetes = [json.loads(ligne)["requete"] for ligne in journal.read_text().splitlines()]
    assert not any(r.startswith(("SHOW CONSTRAINTS", "DROP ")) for r in requetes)


# --- Langue de la base (--langue, T10.0) ---------------------------------------------------


FRANCAIS = 'restes\n"2583 nœuds, 113700 relations, 30245 clés"'
# Contraintes et index de la langue trouvée : 5 contraintes, 7 index (5 sur nom, plein texte,
# vectoriel) et les 5 des contraintes.
EN_PLACE = (("AS presentes", "presentes\n5", 0), ("AS etat", 'etat\n"12 index, 12 en ligne"', 0))


@pytest.mark.parametrize(
    ("vers_en", "vers_fr", "langue", "code"),
    [
        (FRANCAIS, SANS_RESTE, "fr", 0),
        (SANS_RESTE, FRANCAIS.replace("30245", "30244"), "en", 0),
        (SANS_RESTE, SANS_RESTE, "vide", 0),
        (FRANCAIS, 'restes\n"0 nœuds, 0 relations, 3 clés"', "mixte", 1),
    ],
)
def test_langue(bac: Bac, vers_en: str, vers_fr: str, langue: str, code: int) -> None:
    # Les noms français se comptent vers l'anglais, puis les noms anglais vers le français.
    bac.regles(("AS restes", vers_en, 0, 1), ("AS restes", vers_fr, 0, 1), *EN_PLACE)
    lancement = bac.lancer("--langue")
    assert lancement.code == code, lancement.sortie
    assert lancement.sortie.splitlines()[-1] == f"LANGUE : {langue}"
    restes = [a for a in lancement.requetes if "AS restes" in a["requete"]]
    assert [parametres(a)[-1] for a in restes] == ["{langue: 'en'}", "{langue: 'fr'}"]
    for appel in lancement.requetes:
        argv = appel["argv"]
        assert argv[argv.index("--access-mode") + 1] == "read", appel["requete"]
    # Contraintes et index lus pour une langue franche, et pour elle seule.
    lus = [a for a in lancement.requetes if a["requete"].startswith("SHOW ")]
    assert len(lus) == (2 if langue in {"fr", "en"} else 0)


@pytest.mark.parametrize(
    ("langue", "noms", "autres"),
    [
        (
            "fr",
            ("'forme_id'", "'attaque_nom'", "'noms_plein_texte'", "'descriptions_texte'"),
            ("'form_id'", "'names_fulltext'", "'descriptions_text'"),
        ),
        (
            "en",
            ("'form_id'", "'move_name'", "'names_fulltext'", "'descriptions_text'"),
            ("'forme_id'", "'noms_plein_texte'", "'descriptions_texte'"),
        ),
    ],
)
def test_langue_lit_les_contraintes_de_sa_langue(
    bac: Bac, langue: str, noms: tuple[str, ...], autres: tuple[str, ...]
) -> None:
    vers_en, vers_fr = (FRANCAIS, SANS_RESTE) if langue == "fr" else (SANS_RESTE, FRANCAIS)
    bac.regles(("AS restes", vers_en, 0, 1), ("AS restes", vers_fr, 0, 1), *EN_PLACE)
    lancement = bac.lancer("--langue")
    assert lancement.code == 0, lancement.sortie
    lues = [a["requete"] for a in lancement.requetes if a["requete"].startswith("SHOW ")]
    [contraintes, index] = lues
    assert contraintes.startswith("SHOW CONSTRAINTS")
    assert index.startswith("SHOW INDEXES")
    crochets = re.findall(r"IN \[([^\]]*)\]", contraintes + index)
    listes = [re.findall(r"'(\w+)'", liste) for liste in crochets]
    # SHOW CONSTRAINTS : les 5 contraintes ; SHOW INDEXES : les 7 index, puis les 5 contraintes
    # (l'index de chacune).
    assert [len(liste) for liste in listes] == [5, 7, 5]
    assert listes[0] == listes[2]
    lus = {nom for liste in listes for nom in liste}
    assert {nom.strip("'") for nom in noms} <= lus
    assert not {nom.strip("'") for nom in autres} & lus
    assert "contraintes et index : 5/5 contraintes, 12 index, 12 en ligne (attendus : 12)" in (
        lancement.sortie
    )


@pytest.mark.parametrize(
    "en_place",
    [
        (("AS presentes", "presentes\n3", 0), EN_PLACE[1]),
        (EN_PLACE[0], ("AS etat", 'etat\n"11 index, 10 en ligne"', 0)),
        (EN_PLACE[0], ("AS etat", 'etat\n"10 index, 10 en ligne"', 0)),
    ],
    ids=["contraintes-manquantes", "index-pas-en-ligne", "index-manquant"],
)
def test_langue_incomplete(bac: Bac, en_place: tuple[tuple[str, str, int], ...]) -> None:
    # Des noms d'une seule langue, sans ses contraintes ou ses index en ligne : bascule coupée.
    bac.regles(("AS restes", FRANCAIS, 0, 1), ("AS restes", SANS_RESTE, 0, 1), *en_place)
    lancement = bac.lancer("--langue")
    assert lancement.code == 1
    assert lancement.sortie.splitlines()[-1] == "LANGUE : incomplète"


def test_langue_sans_contraintes_lues(bac: Bac) -> None:
    # Un fichier de contraintes sans contrainte ne doit pas passer pour un schéma complet (0 sur 0).
    depot = bac.racine / "depot"
    shutil.copytree(RACINE / "scripts", depot / "scripts")
    shutil.copytree(RACINE / "cypher", depot / "cypher")
    contraintes = depot / "cypher" / "00-contraintes.cypher"
    lignes = contraintes.read_text().splitlines()
    contraintes.write_text("\n".join(ligne for ligne in lignes if "CONSTRAINT" not in ligne))
    bac.regles(("AS restes", FRANCAIS, 0, 1), ("AS restes", SANS_RESTE, 0, 1), *EN_PLACE)
    fini = subprocess.run(
        [str(depot / "scripts" / "charger.sh"), "--langue"],
        cwd=bac.racine,
        env=bac.env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert fini.returncode == 2
    assert "aucune contrainte ou aucun index lu dans 00-contraintes.cypher" in fini.stderr


def test_langue_releve_les_cles_connues(bac: Bac) -> None:
    # db.propertyKeys() garde les clés orphelines (D8) : relevé par langue, en lecture seule.
    connues = ("AS connues", 'connues\n"58 clés, dont 29 françaises et 29 anglaises"', 0)
    bac.regles(("AS restes", SANS_RESTE, 0, 1), ("AS restes", FRANCAIS, 0, 1), *EN_PLACE, connues)
    lancement = bac.lancer("--langue")
    assert lancement.code == 0, lancement.sortie
    assert "db.propertyKeys() : 58 clés, dont 29 françaises et 29 anglaises" in lancement.sortie
    [appel] = [a for a in lancement.requetes if "AS connues" in a["requete"]]
    assert "CALL db.propertyKeys()" in appel["requete"]
    assert appel["argv"][appel["argv"].index("--access-mode") + 1] == "read"
    assert parametres(appel)[0].startswith("{cartes: ")


# --- Jeton du chargement (spec 003, T3.2 ; plan D4) ----------------------------------------------

FICHIER_07 = "// Encodage (factice)\nRETURN $jeton IS NOT NULL AS jeton;\n"


@pytest.fixture
def encodage(bac: Bac) -> Path:
    fichier = bac.racine / "07-embeddings.cypher"
    fichier.write_text(FICHIER_07)
    return fichier


def test_jeton_emprunte_pour_15_minutes(bac: Bac, encodage: Path) -> None:
    lancement = bac.avec_jeton(encodage)
    assert lancement.code == 0, lancement.sortie
    emprunts = [a for a in bac.gcloud() if a[:2] == ["auth", "print-access-token"]]
    assert emprunts == [
        ["auth", "print-access-token", f"--impersonate-service-account={COMPTE}", "--lifetime=900"]
    ]


def test_jeton_sur_l_entree_standard(bac: Bac, encodage: Path) -> None:
    # Une ligne :param, puis le fichier : cypher-shell lit le tout sur stdin, sans --file.
    lancement = bac.avec_jeton(encodage, "--format", "verbose")
    assert lancement.code == 0, lancement.sortie
    [appel] = lancement.requetes
    assert appel["entree"] == f':param {{jeton: "{JETON}"}}\n' + FICHIER_07
    assert "--file" not in appel["argv"]
    assert appel["argv"][-2:] == ["--format", "verbose"]


def test_jeton_ni_en_argument_ni_dans_l_environnement(bac: Bac, encodage: Path) -> None:
    # Un argument se lit dans ps ; une variable exportée passerait à tout processus lancé.
    lancement = bac.avec_jeton(encodage, "-P", "{base: 'x'}")
    assert lancement.code == 0, lancement.sortie
    [appel] = lancement.requetes
    assert not [argument for argument in appel["argv"] if JETON in argument]
    assert not [nom for nom, valeur in appel["env"].items() if JETON in valeur]


def test_jeton_masque_dans_la_sortie(bac: Bac, encodage: Path) -> None:
    # Une erreur de syntaxe cite la requête reçue, :param compris : SORTIE, que charger.sh affiche
    # et journalise, n'en garde que ‹jeton›.
    bac.regles((":param", "Invalid input, near: {entree}", 1))
    lancement = bac.avec_jeton(encodage)
    assert lancement.code == 1
    assert JETON not in lancement.sortie
    assert ':param {jeton: "‹jeton›"}' in lancement.sortie


def test_emprunt_refuse(bac: Bac, encodage: Path) -> None:
    # gcloud échoue (emprunt non autorisé) : rien ne part vers Aura, même si sa sortie a la forme
    # d'un jeton.
    bac.emprunt(erreur="ERROR: (gcloud.auth.print-access-token) PERMISSION_DENIED\n", code=1)
    lancement = bac.avec_jeton(encodage)
    assert lancement.code == 2
    assert f"jeton du compte {COMPTE} non obtenu" in lancement.sortie
    assert lancement.requetes == []


def test_jeton_illisible(bac: Bac, encodage: Path) -> None:
    # Un jeton qui sortirait de sa chaîne Cypher n'est jamais envoyé, ni affiché.
    bac.emprunt(jeton='jeton"} RETURN 1 //')
    lancement = bac.avec_jeton(encodage)
    assert lancement.code == 2
    assert f"jeton du compte {COMPTE} illisible" in lancement.sortie
    assert lancement.requetes == []
    assert "RETURN 1" not in lancement.sortie


# --- Index vectoriel vu par --langue et --explain (spec 003, T3.3 ; plan D2) ---------------------

# Depuis T4.1, l'index est dans 00-contraintes.cypher : --langue le compte avec les autres
# (test_langue_lit_les_contraintes_de_sa_langue), --explain le planifie, sur le vrai fichier.


def test_explain_planifie_l_index_vectoriel(bac: Bac) -> None:
    # EXPLAIN en lecture seule, comme les autres index : il ne valide pas les options (sondé le
    # 2026-10-13), que seul verifier.sh --section embeddings contrôle, l'index créé. Son libellé est
    # le début de sa ligne : aucun commentaire n'est collé au-dessus (lire_requetes de charger.sh).
    bac.regles(*REGLES_BASCULE)
    lancement = bac.lancer("--schema", "fr", "--explain")
    assert lancement.code == 0, lancement.sortie
    assert "PLANIFIÉ : 17 requêtes, rien d'exécuté." in lancement.sortie
    assert "✓ CREATE VECTOR INDEX descriptions_texte IF NOT EXISTS : planifiée" in lancement.sortie
    [vectoriel] = [a for a in lancement.requetes if "CREATE VECTOR INDEX" in a["requete"]]
    assert vectoriel["requete"].startswith("EXPLAIN CREATE VECTOR INDEX descriptions_texte")
    assert vectoriel["argv"][vectoriel["argv"].index("--access-mode") + 1] == "read"
