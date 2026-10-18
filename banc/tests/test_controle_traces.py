"""Contrôle des traces d'une campagne (spec 003, T15.1 ; US1 et US4) : banc controle-traces.

Campagne fabriquée dans un dossier temporaire, traces écrites par le vrai Journal (banc.mesures) :
une conversation GraphRAG (la vraie requête de recherche, l'empreinte du vecteur, le résultat fixe
du faux serveur), une paire de la technique 2, campagne.json et encodages.json, dont les vecteurs
restent permis. Chaque test d'écart ajoute une seule chose à cette campagne conforme. Les textes
cherchés (jeton Google, vecteur) ne s'affichent jamais. Aucun service appelé.
"""

import json
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest

from banc import controle_traces
from banc.__main__ import main
from banc.cellule import RECHERCHE
from banc.faux_serveur import RECHERCHE_FIXE
from banc.mesures import Entete, Journal, commit_pokeapi, empreinte_vecteur, fichier_trace
from banc.prix import Usage

SONNET = "claude-sonnet-5-5"
# Un vecteur de la dimension de l'index (3 072) : décimales, exposants et zéro, comme neo4j-mcp
# v1.6.0 écrit les composantes d'un vecteur stocké (relevé en lecture sur Aura le 2026-10-18).
VECTEUR = [0.017206049, -0.005001527, 1.2e-05, -3.4e-06, 0.0] * 614 + [0.1, -0.2]
# Un vecteur stocké tel que read-cypher le renvoie : JSON indenté, un nombre par ligne, sous
# « Elems » (forme relevée sur la vraie base ; texte de description inventé, ADR-0001).
NEO4J_MCP = json.dumps(
    [
        {
            "d": {
                "Id": 12485,
                "Labels": ["Description"],
                "Props": {
                    "embedding": {"Elems": VECTEUR},
                    "jeux": ["rouge", "bleu"],
                    "texte": "Un texte inventé pour le test.",
                },
            }
        }
    ],
    indent=2,
)
# Jeton d'accès Google factice, assemblé ici : le motif entier n'est jamais écrit dans le dépôt, où
# gitleaks le prendrait pour un vrai (plan, D17).
JETON_GOOGLE = "ya29" + "." + "factice-du-banc-" + "x" * 40
REPONSE = "Réponse : Kecleon\n\nSources : aucune"

type AppelEcrit = tuple[str, str, dict[str, object], str, bool]

RECHERCHE_DU_TOUR: AppelEcrit = (
    "read-cypher",
    RECHERCHE.read_text(encoding="utf-8"),
    {"vecteur": empreinte_vecteur(VECTEUR)},
    RECHERCHE_FIXE,
    False,
)
LECTURE: AppelEcrit = (
    "read-cypher",
    "MATCH (p:Pokemon {nom: $nom}) RETURN p.nom AS nom",
    {"nom": "Pikachu"},
    '[\n  {\n    "nom": "Pikachu"\n  }\n]',
    False,
)
CONFORME = [
    "campagne c1 : 2 traces, 4 fichiers",
    "✓ outils : 3 appels, tous à read-cypher",
    "✓ écritures : aucune clause d'écriture dans les 3 requêtes",
    "✓ jetons Google : aucun « ya29. » dans les 4 fichiers",
    "✓ vecteurs : aucune suite de 100 nombres ou plus dans les 2 traces",
    "CONFORME : 4 contrôles.",
]


def tracer(
    traces: Path,
    cellule: str,
    tours: dict[str, list[AppelEcrit]],
    *,
    reponse: str = REPONSE,
) -> Path:
    """Une conversation de la campagne c1 par le vrai Journal : par question, ses appels (outil,
    requête, paramètres, résultat, erreur), puis sa réponse."""
    entete = Entete(
        campagne="c1",
        cellule=cellule,
        passe=1,
        essai=1,
        questions=tuple(tours),
        modele=SONNET,
        acces="api",
        jour=date(2026, 10, 18),
        effort="high",
        versions={"neo4j-mcp": "1.6.0"},
        commit_pokeapi=commit_pokeapi(),
    )
    fichier = fichier_trace(traces, entete)
    with Journal(fichier, entete) as journal:
        for question, appels in tours.items():
            journal.question(question, f"Question {question} telle que posée ?")
            journal.llm(SONNET, Usage(entree=10, sortie=20))
            for rang, (outil, requete, parametres, resultat, erreur) in enumerate(appels, start=1):
                journal.appel(f"{question}-{rang}", outil, requete, parametres)
                journal.resultat(f"{question}-{rang}", resultat, erreur)
            journal.fin("reponse", reponse=reponse)
    return fichier


def lecture(requete: str, *, resultat: str = "[]", erreur: bool = False) -> AppelEcrit:
    return ("read-cypher", requete, {}, resultat, erreur)


@pytest.fixture
def traces(tmp_path: Path) -> Path:
    """Une campagne conforme : 2 traces, 3 appels, 4 fichiers. Le contrôle ne dépend pas de la
    technique : une conversation GraphRAG et une paire de la technique 2 y voisinent."""
    tracer(tmp_path, "graphrag-claude", {"Q19": [RECHERCHE_DU_TOUR]})
    tracer(tmp_path, "adk-claude", {"Q2": [LECTURE], "Q18": [LECTURE]})
    dossier = tmp_path / "c1"
    (dossier / "campagne.json").write_text(json.dumps({"format": 4, "campagne": "c1"}))
    # Les vecteurs des messages, gardés par construction (plan, D5) : permis.
    encodages = {"dimension": 3072, "questions": {"Q19": {"vecteur": VECTEUR}}}
    (dossier / "encodages.json").write_text(json.dumps(encodages))
    return tmp_path


def controler(traces: Path, campagne: str = "c1") -> tuple[int, list[str]]:
    sortie: list[str] = []
    code = controle_traces.commande(campagne, traces=traces, ecrire=sortie.append)
    return code, sortie


def test_campagne_conforme(traces: Path) -> None:
    # Lectures read-cypher seules, sans clause d'écriture, sans jeton Google, sans vecteur hors
    # d'encodages.json : code 0, chaque contrôle compté.
    assert controler(traces) == (0, CONFORME)


# --- Outils (US1 : un seul chemin vers la base) ---------------------------------------------------


@pytest.mark.parametrize("outil", ["get-schema", "write-cypher"])
def test_outil_hors_de_read_cypher(traces: Path, outil: str) -> None:
    # get-schema, que le Journal accepte (introspection), et write-cypher, qu'il refuse, sont
    # d'autres outils : l'appel s'écrit avec read-cypher, puis la trace change de nom d'outil.
    fichier = tracer(traces, "adk-gemini", {"Q1": [lecture("MATCH (n) RETURN n.nom LIMIT 1")]})
    texte = fichier.read_text(encoding="utf-8")
    fichier.write_text(texte.replace('"outil": "read-cypher"', f'"outil": "{outil}"'))
    code, sortie = controler(traces)
    assert code == 1
    assert "✗ outils : 1 appel(s) hors de read-cypher sur 4" in sortie
    assert f"  · adk-gemini-p1-Q1-e1.jsonl, Q1 : {outil}" in sortie
    assert sortie[-1] == "ÉCART : 1 contrôle(s) sur 4."


# --- Écritures (US1 : aucune écriture dans la base) -----------------------------------------------


@pytest.mark.parametrize(
    ("requete", "clauses"),
    [
        pytest.param("CREATE (n:Temoin) RETURN n", "CREATE", id="create"),
        pytest.param("INSERT (n:Temoin)", "INSERT", id="insert"),
        pytest.param("MERGE (n:Temoin {nom: 'x'}) RETURN n", "MERGE", id="merge"),
        pytest.param("MATCH (n:Pokemon) SET n.vu = true", "SET", id="set"),
        pytest.param("MATCH (n:Temoin) DETACH DELETE n", "DELETE", id="detach-delete"),
        pytest.param("MATCH (n:Pokemon) REMOVE n.vu", "REMOVE", id="remove"),
        pytest.param("FOREACH (x IN [1] | CREATE (:Temoin))", "FOREACH, CREATE", id="foreach"),
        pytest.param("DROP INDEX descriptions_texte", "DROP", id="drop"),
        pytest.param("match (n:Temoin) delete n", "DELETE", id="minuscules"),
        pytest.param("CALL () { CREATE (:Temoin) } IN TRANSACTIONS", "CREATE", id="sous-requete"),
    ],
)
def test_clause_d_ecriture(traces: Path, requete: str, clauses: str) -> None:
    # Les clauses d'écriture du Cypher Manual (CREATE et son synonyme INSERT, MERGE, SET, DELETE,
    # REMOVE, FOREACH) et DROP : une seule suffit, en capitales ou non.
    tracer(traces, "adk-gemini", {"Q1": [lecture(requete)]})
    code, sortie = controler(traces)
    assert code == 1
    assert "✗ écritures : 1 requête(s) avec une clause d'écriture sur 4" in sortie
    assert f"  · adk-gemini-p1-Q1-e1.jsonl, Q1 : {clauses}" in sortie
    assert sortie[-1] == "ÉCART : 1 contrôle(s) sur 4."


def test_ecriture_refusee_par_le_serveur(traces: Path) -> None:
    # Une écriture tentée compte, même refusée par read-cypher (erreur MCP) : la trace le dit.
    refus = "Neo4jError: write queries are not allowed in read-only mode"
    tracer(traces, "adk-gemini", {"Q1": [lecture("CREATE (:Temoin)", resultat=refus, erreur=True)]})
    code, sortie = controler(traces)
    assert code == 1
    assert "  · adk-gemini-p1-Q1-e1.jsonl, Q1 : CREATE (refusée par le serveur)" in sortie


@pytest.mark.parametrize(
    "requete",
    [
        pytest.param(
            "MATCH (d:Description) WHERE d.texte CONTAINS 'CREATE' RETURN d.texte AS texte",
            id="chaine",
        ),
        pytest.param("// SET n.vu = true\nMATCH (n:Pokemon) RETURN n.nom AS nom", id="commentaire"),
        pytest.param("MATCH (n:Pokemon) /* DELETE n */ RETURN n.nom AS nom", id="bloc"),
        pytest.param("MATCH (n:Pokemon) RETURN n.set AS valeur", id="propriete"),
        pytest.param("RETURN {merge: 1} AS m", id="cle"),
        pytest.param("RETURN {merge /* clé */ : 1} AS m", id="cle-et-commentaire"),
        pytest.param("MATCH (n:Remove) RETURN count(n) AS nombre", id="label"),
        pytest.param("MATCH (n:Pokemon) RETURN n.nom AS `delete`", id="accents-graves"),
    ],
)
def test_mot_d_ecriture_hors_clause(traces: Path, requete: str) -> None:
    # Un mot d'écriture dans une chaîne, un commentaire, une propriété, une clé de map, un label ou
    # un nom entre accents graves n'est pas une clause : requêtes lues jeton par jeton.
    tracer(traces, "adk-gemini", {"Q1": [lecture(requete)]})
    code, sortie = controler(traces)
    assert code == 0, sortie
    assert "✓ écritures : aucune clause d'écriture dans les 4 requêtes" in sortie


# --- Jetons Google --------------------------------------------------------------------------------


def _dans_le_resultat(traces: Path) -> str:
    tracer(traces, "adk-gemini", {"Q1": [lecture("RETURN 1", resultat=f'["{JETON_GOOGLE}"]')]})
    return "adk-gemini-p1-Q1-e1.jsonl"


def _dans_la_reponse(traces: Path) -> str:
    tracer(traces, "adk-gemini", {"Q1": [lecture("RETURN 1")]}, reponse=f"Jeton {JETON_GOOGLE}")
    return "adk-gemini-p1-Q1-e1.jsonl"


def _dans_campagne_json(traces: Path) -> str:
    (traces / "c1" / "campagne.json").write_text(json.dumps({"jeton": JETON_GOOGLE}))
    return "campagne.json"


def _dans_encodages_json(traces: Path) -> str:
    (traces / "c1" / "encodages.json").write_text(json.dumps({"jeton": JETON_GOOGLE}))
    return "encodages.json"


def _dans_une_ligne_coupee(traces: Path) -> str:
    # Harnais interrompu en pleine écriture : la dernière ligne, sans fin de ligne, ne se relit pas
    # (banc.mesures.lire), mais son texte est contrôlé.
    fichier = traces / "c1" / "adk-claude-p1-Q2+Q18-e1.jsonl"
    with fichier.open("a", encoding="utf-8") as flux:
        flux.write(f'{{"type": "question", "t": 9.0, "message": "{JETON_GOOGLE}')
    return fichier.name


@pytest.mark.parametrize(
    "placer",
    [
        pytest.param(_dans_le_resultat, id="resultat"),
        pytest.param(_dans_la_reponse, id="reponse"),
        pytest.param(_dans_campagne_json, id="campagne-json"),
        pytest.param(_dans_encodages_json, id="encodages-json"),
        pytest.param(_dans_une_ligne_coupee, id="ligne-coupee"),
    ],
)
def test_jeton_google(traces: Path, placer: Callable[[Path], str]) -> None:
    # Un jeton d'accès Google, où qu'il soit dans les fichiers de la campagne : écart, avec le
    # fichier et le nombre, jamais le jeton.
    nom = placer(traces)
    code, sortie = controler(traces)
    assert code == 1
    fichiers = 5 if nom.startswith("adk-gemini") else 4
    assert f"✗ jetons Google : « ya29. » dans 1 fichier(s) sur {fichiers}" in sortie
    assert f"  · {nom} : 1 occurrence(s)" in sortie
    assert "factice-du-banc" not in "\n".join(sortie)


# --- Vecteurs (US4) -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("appel", "reponse", "ligne"),
    [
        pytest.param(
            ("read-cypher", "RETURN $v AS v", {"vecteur": VECTEUR}, "[]", False),
            REPONSE,
            4,
            id="parametres",
        ),
        pytest.param(lecture("MATCH (d) RETURN d", resultat=NEO4J_MCP), REPONSE, 5, id="resultat"),
        pytest.param(lecture("RETURN 1"), ", ".join(map(str, VECTEUR)), 6, id="reponse"),
    ],
)
def test_vecteur(traces: Path, appel: AppelEcrit, reponse: str, ligne: int) -> None:
    # Un vecteur dans les paramètres, dans un résultat (le contexte d'une technique sans outil) ou
    # dans une réponse : écart, avec le fichier, la ligne et la taille, jamais les nombres.
    tracer(traces, "adk-gemini", {"Q1": [appel]}, reponse=reponse)
    code, sortie = controler(traces)
    assert code == 1
    assert "✗ vecteurs : 1 suite(s) de 100 nombres ou plus dans 1 trace(s) sur 3" in sortie
    assert f"  · adk-gemini-p1-Q1-e1.jsonl, ligne {ligne} (Q1) : 3072 nombres" in sortie
    assert "0.017206049" not in "\n".join(sortie)


def test_vecteur_dans_une_ligne_coupee(traces: Path) -> None:
    # La dernière ligne d'un harnais interrompu, illisible en JSON, est contrôlée sur son texte.
    fichier = traces / "c1" / "adk-claude-p1-Q2+Q18-e1.jsonl"
    with fichier.open("a", encoding="utf-8") as flux:
        flux.write('{"type": "resultat", "t": 9.0, "resultat": "' + json.dumps(VECTEUR)[:-1])
    code, sortie = controler(traces)
    assert code == 1
    assert f"  · {fichier.name}, ligne 12 (coupée) : 3072 nombres" in sortie


@pytest.mark.parametrize(("nombres", "code"), [(99, 0), (100, 1)])
def test_suite_de_nombres_a_la_borne(traces: Path, nombres: int, code: int) -> None:
    # Le seuil : une suite de 100 nombres ou plus (US4, « plusieurs centaines » ; un vecteur de
    # l'index en compte 3 072), entiers compris ; 99 passent.
    resultat = json.dumps(list(range(nombres)))
    tracer(traces, "adk-gemini", {"Q1": [lecture("RETURN range(0, 99) AS r", resultat=resultat)]})
    assert controler(traces)[0] == code


# --- Traces écartées, erreurs, ligne de commande --------------------------------------------------


def test_trace_ecartee_controlee(traces: Path) -> None:
    # Une trace écartée (.jsonl.ecartee) vient d'une vraie conversation : contrôlée aussi.
    fichier = tracer(traces, "adk-gemini", {"Q1": [lecture("CREATE (:Temoin)")]})
    ecartee = fichier.rename(fichier.with_name(fichier.name + ".ecartee"))
    code, sortie = controler(traces)
    assert code == 1
    assert f"  · {ecartee.name}, Q1 : CREATE" in sortie


@pytest.mark.parametrize("vide", [False, True])
def test_campagne_sans_trace(
    tmp_path: Path, vide: bool, capsys: pytest.CaptureFixture[str]
) -> None:
    # Dossier absent, ou sans trace (campagne.json seul) : rien à contrôler, erreur technique.
    if vide:
        (tmp_path / "c1").mkdir()
        (tmp_path / "c1" / "campagne.json").write_text("{}")
    assert controler(tmp_path) == (2, [])
    assert f"campagne c1 : aucune trace dans {tmp_path / 'c1'}" in capsys.readouterr().err


def test_entree_qui_n_est_pas_un_fichier(traces: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Un dossier dans celui de la campagne sort de ce qu'elle écrit : rien ne le montrerait sûr.
    (traces / "c1" / "notes").mkdir()
    assert controler(traces) == (2, [])
    assert "campagne c1 : notes n'est pas un fichier" in capsys.readouterr().err


def test_trace_illisible(traces: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fichier = traces / "c1" / "graphrag-claude-p1-Q19-e1.jsonl"
    lignes = fichier.read_text(encoding="utf-8").splitlines(keepends=True)
    fichier.write_text("".join([lignes[0], "{pas du JSON\n", *lignes[1:]]), encoding="utf-8")
    assert controler(traces) == (2, [])
    assert "graphrag-claude-p1-Q19-e1.jsonl, ligne 2" in capsys.readouterr().err


def test_nom_de_campagne_refuse(traces: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Un code de campagne (minuscules, chiffres, tirets), jamais un chemin.
    assert controler(traces / "c1", "../c1") == (2, [])
    assert "un code attendu" in capsys.readouterr().err


def test_ligne_de_commande(capsys: pytest.CaptureFixture[str]) -> None:
    # banc controle-traces --campagne <id>, sur logs/banc/ : une campagne qui n'existe pas.
    assert main(["controle-traces", "--campagne", "t151-inexistante"]) == 2
    assert "campagne t151-inexistante : aucune trace" in capsys.readouterr().err
