"""Recherche seule (spec 003, US2 ; plan D13) : banc recherche-seule --campagne <id>.

Un dépôt git temporaire porte revues.toml et les tables des cinq questions sémantiques
(questions/attendu/qNN.txt, et le classement de questions/qNN.cypher pour ses marques horsFilet), en
quatre commits : le gel du jalon 2 (en-tête de revues.toml) ; un réglage du pilote du jalon 3
(Viskuse acceptable pour Q17) ; le gel du jalon 3 (table [[jalon]]) ; puis ce que T16.2 pourrait
changer après lui (Magby obligatoire pour Q3, Lovdisc marqué hors filet pour Q9), avec un
commentaire de revues.toml qui cite la ligne du gel. La mesure lit les tables au commit qui a écrit
le gel du jalon de la campagne (choix de Julien du 2026-10-19), jamais celles d'après. Les traces
d'une campagne GraphRAG (deux cellules, une passe) sont écrites par le vrai Journal (banc.mesures).
Aucun service appelé : git seul, en local, hors de la configuration de l'utilisateur. Valeurs de la
spec en clair : 20 espèces au plus, Q9 plafonnée à 20 sur 26 (77 %).
"""

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pytest

from banc import orchestration, recherche_seule
from banc.__main__ import main
from banc.cellule import RECHERCHE, empreinte_recherche
from banc.mesures import Entete, Journal, commit_pokeapi, empreinte_vecteur, fichier_trace
from banc.prix import Usage

SONNET = "claude-sonnet-5-5"
GEL_2 = "2026-10-10T21:22:40"
GEL_3 = "2026-10-20T10:00:00"
JOUR = date(2026, 10, 21)
CELLULES = ("graphrag-claude", "graphrag-gemini")
OBLIGATOIRE, ACCEPTABLE, ECARTE = "obligatoire", "acceptable", "écarté"

# Q9 : les 26 espèces obligatoires et acceptables de sa vraie table au 2026-10-19 (D13 : « Q9 compte
# 26 espèces obligatoires et acceptables : 77 % au plus »), et ses écartées, Poissirène hors filet.
OBLIGATOIRES_Q9 = (
    "Aquali",
    "Crustabri",
    "Hyporoi",
    "Kokiyas",
    "Kyogre",
    "Lanturn",
    "Loupio",
    "Lugia",
    "Luminéon",
    "Mamanbo",
    "Prédastérie",
    "Relicanth",
    "Rosabyss",
    "Sarmuraï",
    "Serpang",
    "Sovkipou",
    "Stari",
    "Vacilys",
    "Venalgue",
    "Vorastérie",
)
ACCEPTABLES_Q9 = ("Amonita", "Kabutops", "Lilia", "Moyade", "Viskuse", "Écayon")
ECARTES_Q9 = ("Concombaffe", "Lovdisc", "Poissirène", "Sinistrail", "Tadmorv")

# Tables du gel du jalon 2 (premier commit) : par question, chaque espèce et son ensemble.
TABLES: dict[str, dict[str, str]] = {
    "Q3": {
        "Magmar": OBLIGATOIRE,
        "Camérupt": OBLIGATOIRE,
        "Heatran": OBLIGATOIRE,
        "Chartor": ACCEPTABLE,
        "Laggron": ECARTE,
    },
    "Q9": {
        **dict.fromkeys(OBLIGATOIRES_Q9, OBLIGATOIRE),
        **dict.fromkeys(ACCEPTABLES_Q9, ACCEPTABLE),
        **dict.fromkeys(ECARTES_Q9, ECARTE),
    },
    "Q16": {"Dracolosse": OBLIGATOIRE, "Arcanin": ECARTE, "Scorvol": ECARTE},
    "Q17": {"Léviator": OBLIGATOIRE, "Tentacruel": OBLIGATOIRE, "Lokhlass": ECARTE},
    "Q26": {
        "Ronflex": OBLIGATOIRE,
        "Abra": OBLIGATOIRE,
        "Parecool": OBLIGATOIRE,
        "Goinfrex": OBLIGATOIRE,
        "Grodoudou": OBLIGATOIRE,
        "Dodoala": ACCEPTABLE,
        "Feuillajou": ACCEPTABLE,
        "Kaorine": ACCEPTABLE,
        "Spododo": ECARTE,
    },
}
HORS_FILET = {"Q9": ("Poissirène",)}

# Les espèces que la recherche retrouve, dans son ordre : 20 pour Q9, le plafond.
RESULTATS: dict[str, list[str]] = {
    "Q3": ["Magmar", "Camérupt", "Magby", "Laggron", "Ignifiore"],
    "Q9": [
        "Lugia",
        "Lanturn",
        "Relicanth",
        "Luminéon",
        "Kyogre",
        "Hyporoi",
        "Serpang",
        "Stari",
        "Kabutops",
        "Lovdisc",
        "Poissirène",
        "Barpau",
        "Wailord",
        "Léviator",
        "Tentacool",
        "Qwilfish",
        "Kraknoix",
        "Octillery",
        "Mantine",
        "Corayon",
    ],
    "Q16": ["Arcanin", "Scorvol", "Latios"],
    "Q17": ["Léviator", "Viskuse", "Lokhlass"],
    "Q26": ["Ronflex", "Spododo", "Lamantine"],
}


class Depot(NamedTuple):
    """Le dépôt temporaire, et les commits qui ont écrit les gels des jalons 2 et 3."""

    racine: Path
    gel_2: str
    gel_3: str


def git(racine: Path, *arguments: str) -> str:
    """git dans le dépôt temporaire, hors de toute configuration de l'utilisateur."""
    environnement = os.environ | {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": "Banc",
        "GIT_AUTHOR_EMAIL": "banc@example.invalid",
        "GIT_COMMITTER_NAME": "Banc",
        "GIT_COMMITTER_EMAIL": "banc@example.invalid",
    }
    fini = subprocess.run(
        ["git", "-C", str(racine), *arguments],
        capture_output=True,
        encoding="utf-8",
        env=environnement,
        check=True,
    )
    return fini.stdout


def fichiers(
    tables: Mapping[str, Mapping[str, str]], hors_filet: Mapping[str, Sequence[str]]
) -> dict[str, str]:
    """La réponse de référence (attendu/qNN.txt, format de scripts/questions.sh) et le classement
    (qNN.cypher, avec ses marques horsFilet sur une ligne de suite, comme Poissirène) de chaque
    question."""
    contenus: dict[str, str] = {}
    for question, table in tables.items():
        nom = f"q{int(question[1:]):02d}"
        lignes = [f'"{espece}", "{ensemble}", "une raison"' for espece, ensemble in table.items()]
        contenus[f"questions/attendu/{nom}.txt"] = "\n".join(
            [
                f"// PokéAPI {commit_pokeapi()} · {nom}.cypher",
                "pokemon, ensemble, raison",
                *lignes,
                "",
            ]
        )
        entrees = [
            f"    {{pokemon: '{espece}', ensemble: '{ensemble}', raison: 'une raison'"
            + (",\n      horsFilet: true}" if espece in hors_filet.get(question, ()) else "}")
            for espece, ensemble in table.items()
        ]
        contenus[f"questions/{nom}.cypher"] = "\n".join(
            [
                f"// {question} : un classement",
                "WITH [",
                ",\n".join(entrees),
                "  ] AS classement",
                "RETURN classement;",
                "",
            ]
        )
    return contenus


def committer(racine: Path, message: str, contenus: Mapping[str, str]) -> str:
    """Écrit les fichiers, les commite, et rend le commit."""
    for chemin, texte in contenus.items():
        (racine / chemin).parent.mkdir(parents=True, exist_ok=True)
        (racine / chemin).write_text(texte, encoding="utf-8")
    git(racine, "add", "--all")
    git(racine, "commit", "--quiet", "--message", message)
    return git(racine, "rev-parse", "HEAD").strip()


def revues(*gels: tuple[str, str]) -> str:
    """revues.toml : le gel du jalon 2 en tête, puis une table [[jalon]] par jalon suivant."""
    (gel, pilote), *suivants = gels
    texte = f'gel = {gel}\npilote = "{pilote}"\n'
    for gel_suivant, pilote_suivant in suivants:
        texte += f'\n[[jalon]]\ngel = {gel_suivant}\npilote = "{pilote_suivant}"\n'
    return texte


@pytest.fixture
def depot(tmp_path: Path) -> Depot:
    racine = tmp_path / "depot"
    racine.mkdir()
    git(racine, "init", "--quiet", "--initial-branch", "main")
    gel_2 = committer(
        racine,
        "gel du jalon 2",
        {"banc/mesures/revues.toml": revues((GEL_2, "pilote"))} | fichiers(TABLES, HORS_FILET),
    )
    q17 = {"Q17": TABLES["Q17"] | {"Viskuse": ACCEPTABLE}}
    committer(racine, "réglage du pilote du jalon 3", fichiers(q17, {}))
    gel_3 = committer(
        racine,
        "gel du jalon 3",
        {"banc/mesures/revues.toml": revues((GEL_2, "pilote"), (GEL_3, "pilote-3"))},
    )
    apres = fichiers({"Q3": TABLES["Q3"] | {"Magby": OBLIGATOIRE}}, {}) | fichiers(
        {"Q9": TABLES["Q9"]}, {"Q9": ("Poissirène", "Lovdisc")}
    )
    # Un commentaire qui cite la ligne du gel : ce commit la touche aussi, sans l'avoir écrite.
    rappel = f"\n# Rappel du gel du jalon 3 : gel = {GEL_3}\n"
    apres["banc/mesures/revues.toml"] = revues((GEL_2, "pilote"), (GEL_3, "pilote-3")) + rappel
    committer(racine, "tables changées après le gel (T16.2)", apres)
    return Depot(racine, gel_2, gel_3)


def depot_au_gel(
    racine: Path, tables: Mapping[str, Mapping[str, str]], hors_filet: Mapping[str, Sequence[str]]
) -> Depot:
    """Un dépôt d'un seul commit, celui du gel du jalon 2 : d'autres tables que celles du dépôt."""
    racine.mkdir()
    git(racine, "init", "--quiet", "--initial-branch", "main")
    contenus = {"banc/mesures/revues.toml": revues((GEL_2, "pilote"))} | fichiers(
        tables, hors_filet
    )
    gel = committer(racine, "gel", contenus)
    return Depot(racine, gel, gel)


def texte(especes: Sequence[str]) -> str:
    """Le résultat de la recherche tel que read-cypher le rend : un enregistrement par espèce, en
    JSON indenté (questions/recherche.cypher ; textes inventés, ADR-0001)."""
    enregistrements = [
        {
            "espece": espece,
            "types": ["Eau"],
            "descriptions": [{"texte": "Un texte inventé.", "jeux": ["rouge"], "score": 0.8}],
        }
        for espece in especes
    ]
    return json.dumps(enregistrements, ensure_ascii=False, indent=2)


def tracer(
    traces: Path,
    entete: Entete,
    resultat: str,
    *,
    erreur: bool = False,
) -> Path:
    """Une conversation GraphRAG par le vrai Journal : la recherche (la vraie requête, l'empreinte
    d'un vecteur), son résultat, puis l'appel au modèle et la réponse."""
    [question] = entete.questions
    fichier = fichier_trace(traces, entete)
    with Journal(fichier, entete) as journal:
        journal.question(question, f"Question {question} telle que posée ?")
        requete = RECHERCHE.read_text(encoding="utf-8")
        vecteur = {"vecteur": empreinte_vecteur([0.1, 0.2, 0.3])}
        journal.appel(f"recherche-{question}", "read-cypher", requete, vecteur)
        journal.resultat(f"recherche-{question}", resultat, erreur)
        journal.llm(SONNET, Usage(entree=10, sortie=20))
        journal.fin("reponse", reponse="Réponse : une espèce\n\nSources : aucune")
    return fichier


def entete(cellule: str, question: str, *, passe: int = 1, jour: date = JOUR) -> Entete:
    return Entete(
        campagne="g-1",
        cellule=cellule,
        passe=passe,
        essai=1,
        questions=(question,),
        modele=SONNET,
        acces="api",
        jour=jour,
        effort="high",
        versions={"neo4j-mcp": "1.6.0"},
        commit_pokeapi=commit_pokeapi(),
    )


def campagne(
    traces: Path,
    resultats: Mapping[str, str],
    *,
    jour: date = JOUR,
    cellules: tuple[str, ...] = CELLULES,
    faux_serveur: bool = False,
) -> Path:
    """La campagne g-1 : campagne.json (orchestration.ecrire_campagne), puis une trace par cellule
    et par question, chacune avec le résultat de recherche de sa question."""
    graphrag = all(cellule.startswith("graphrag-") for cellule in cellules)
    parametres = orchestration.Campagne(
        nom="g-1",
        passes=1,
        conversations=tuple((question,) for question in resultats),
        cellules=cellules,
        faux_serveur=faux_serveur,
        empreinte_prompt=hashlib.sha256(b"prompt").hexdigest(),
        empreinte_recherche=empreinte_recherche() if graphrag else None,
    )
    orchestration.ecrire_campagne(traces / "g-1" / "campagne.json", parametres)
    for cellule in cellules:
        for question, resultat in resultats.items():
            tracer(traces, entete(cellule, question, jour=jour), resultat)
    return traces


@pytest.fixture
def traces(tmp_path: Path) -> Path:
    resultats = {question: texte(especes) for question, especes in RESULTATS.items()}
    return campagne(tmp_path / "traces", resultats)


def mesurer(traces: Path, depot: Depot, nom: str = "g-1") -> tuple[int, list[str]]:
    sortie: list[str] = []
    code = recherche_seule.commande(nom, traces=traces, depot=depot.racine, ecrire=sortie.append)
    return code, sortie


def conforme(depot: Depot) -> list[str]:
    return [
        f"campagne g-1 : 10 traces ; tables du gel du {GEL_3} (commit {depot.gel_3[:12]})",
        "✓ Q3 : 5 espèces retrouvées, même résultat dans 2 traces",
        "  · grille : 2 sur 4 obligatoires et acceptables (50 %), plafond 4 sur 4 (100 %)",
        "  · dans la grille : Magmar, Camérupt",
        "  · hors filet : Magby (à classer), Ignifiore (à classer)",
        "✓ Q9 : 20 espèces retrouvées, même résultat dans 2 traces",
        "  · grille : 9 sur 26 obligatoires et acceptables (35 %), plafond 20 sur 26 (77 %)",
        "  · dans la grille : Lugia, Lanturn, Relicanth, Luminéon, Kyogre, Hyporoi, Serpang, "
        "Stari, Kabutops",
        "  · hors filet : Poissirène (écarté), Barpau (à classer), Wailord (à classer), "
        "Léviator (à classer), Tentacool (à classer), Qwilfish (à classer), Kraknoix (à classer), "
        "Octillery (à classer), Mantine (à classer), Corayon (à classer)",
        "✓ Q16 : 3 espèces retrouvées, même résultat dans 2 traces",
        "  · grille : 0 sur 1 obligatoires et acceptables (0 %), plafond 1 sur 1 (100 %)",
        "  · dans la grille : aucune",
        "  · hors filet : Latios (à classer)",
        "✓ Q17 : 3 espèces retrouvées, même résultat dans 2 traces",
        "  · grille : 2 sur 3 obligatoires et acceptables (67 %), plafond 3 sur 3 (100 %)",
        "  · dans la grille : Léviator, Viskuse",
        "  · hors filet : aucune",
        "✓ Q26 : 3 espèces retrouvées, même résultat dans 2 traces",
        "  · grille : 1 sur 8 obligatoires et acceptables (13 %), plafond 8 sur 8 (100 %)",
        "  · dans la grille : Ronflex",
        "  · hors filet : Lamantine (à classer)",
        "CONFORME : 5 questions mesurées, même résultat de recherche d'une trace à l'autre.",
    ]


def lignes_de(sortie: list[str], question: str) -> list[str]:
    """Les lignes d'une question : sa tête, puis ses détails."""
    debut = next(rang for rang, ligne in enumerate(sortie) if ligne[2:].startswith(f"{question} :"))
    fin = next(
        (rang for rang in range(debut + 1, len(sortie)) if not sortie[rang].startswith("  · ")),
        len(sortie),
    )
    return sortie[debut:fin]


# --- La mesure -----------------------------------------------------------------------------------


def test_mesure_conforme(traces: Path, depot: Depot) -> None:
    # Les cinq questions sémantiques, au gel du jalon 3 : part de la grille et plafond (20 espèces
    # au plus, Q9 à 77 %), espèces de la grille retrouvées, espèces hors filet ; code 0.
    assert mesurer(traces, depot) == (0, conforme(depot))


def test_les_cinq_questions_semantiques(traces: Path, depot: Depot) -> None:
    # Q3, Q9, Q16, Q17 et Q26 (D13), dans l'ordre de leurs numéros, et elles seules.
    _, sortie = mesurer(traces, depot)
    tetes = [ligne.split(" : ")[0] for ligne in sortie if ligne.startswith(("✓", "✗"))]
    assert tetes == ["✓ Q3", "✓ Q9", "✓ Q16", "✓ Q17", "✓ Q26"]


def test_plafond_de_vingt_especes(traces: Path, depot: Depot) -> None:
    # La recherche rend 20 espèces au plus : Q9, 26 espèces obligatoires et acceptables, plafonne à
    # 20 sur 26 (77 %) ; Q16, une seule, à 1 sur 1.
    _, sortie = mesurer(traces, depot)
    assert lignes_de(sortie, "Q9")[1].endswith("plafond 20 sur 26 (77 %)")
    assert lignes_de(sortie, "Q16")[1].endswith("plafond 1 sur 1 (100 %)")


def test_pourcentage_arrondi_au_plus_proche(traces: Path, depot: Depot) -> None:
    # 1 sur 8 fait 12,5 % : arrondi à 13 %, comme on l'écrit à la main.
    _, sortie = mesurer(traces, depot)
    assert "(13 %)" in lignes_de(sortie, "Q26")[1]


# --- Tables au commit du gel ---------------------------------------------------------------------


def test_tables_lues_au_commit_du_gel(traces: Path, depot: Depot) -> None:
    # Magby, obligatoire pour Q3 dans une table changée après le gel (T16.2), n'est pas dans la
    # grille du gel : hors filet, à classer, et la part reste de 2 sur 4.
    _, sortie = mesurer(traces, depot)
    assert lignes_de(sortie, "Q3")[1:] == [
        "  · grille : 2 sur 4 obligatoires et acceptables (50 %), plafond 4 sur 4 (100 %)",
        "  · dans la grille : Magmar, Camérupt",
        "  · hors filet : Magby (à classer), Ignifiore (à classer)",
    ]


def test_marque_hors_filet_lue_au_commit_du_gel(traces: Path, depot: Depot) -> None:
    # Lovdisc, marqué hors filet pour Q9 après le gel seulement, reste au gel une espèce du filet,
    # écartée : ni dans la grille, ni hors filet.
    _, sortie = mesurer(traces, depot)
    assert not [ligne for ligne in lignes_de(sortie, "Q9") if "Lovdisc" in ligne]


def test_gel_du_jalon_de_la_campagne(traces: Path, depot: Depot) -> None:
    # Une campagne d'après le gel du jalon 3 lit les tables de son commit : Viskuse, acceptable pour
    # Q17 depuis le réglage de son pilote, est dans sa grille.
    _, sortie = mesurer(traces, depot)
    assert sortie[0].endswith(f"tables du gel du {GEL_3} (commit {depot.gel_3[:12]})")
    assert lignes_de(sortie, "Q17")[2] == "  · dans la grille : Léviator, Viskuse"


def test_campagne_du_jalon_2(tmp_path: Path, depot: Depot) -> None:
    # Une campagne d'avant le gel du jalon 3 relève du gel du jalon 2 : le dernier posé à son jour.
    # La grille de Q17 n'a pas encore Viskuse : hors filet, à classer.
    resultats = {question: texte(especes) for question, especes in RESULTATS.items()}
    traces = campagne(tmp_path / "traces", resultats, jour=date(2026, 10, 15))
    code, sortie = mesurer(traces, depot)
    assert code == 0
    assert sortie[0].endswith(f"tables du gel du {GEL_2} (commit {depot.gel_2[:12]})")
    assert lignes_de(sortie, "Q17")[1:] == [
        "  · grille : 1 sur 2 obligatoires et acceptables (50 %), plafond 2 sur 2 (100 %)",
        "  · dans la grille : Léviator",
        "  · hors filet : Viskuse (à classer)",
    ]


def test_gel_pose_le_jour_meme(tmp_path: Path, depot: Depot) -> None:
    # Gel le matin, campagne l'après-midi : la campagne relève du gel posé le jour même.
    resultats = {question: texte(especes) for question, especes in RESULTATS.items()}
    traces = campagne(tmp_path / "traces", resultats, jour=date(2026, 10, 20))
    _, sortie = mesurer(traces, depot)
    assert sortie[0].endswith(f"tables du gel du {GEL_3} (commit {depot.gel_3[:12]})")


def test_jour_le_plus_ancien_des_traces(traces: Path, depot: Depot) -> None:
    # Le jour de la campagne est celui de sa première trace : une trace du 2026-10-15 la place au
    # jalon 2, même si les autres datent d'après le gel du jalon 3.
    premiere = entete("graphrag-claude", "Q3", passe=2, jour=date(2026, 10, 15))
    tracer(traces, premiere, texte(RESULTATS["Q3"]))
    _, sortie = mesurer(traces, depot)
    assert sortie[0].endswith(f"tables du gel du {GEL_2} (commit {depot.gel_2[:12]})")


def test_campagne_d_avant_tout_gel(
    tmp_path: Path, depot: Depot, capsys: pytest.CaptureFixture[str]
) -> None:
    resultats = {question: texte(especes) for question, especes in RESULTATS.items()}
    traces = campagne(tmp_path / "traces", resultats, jour=date(2026, 10, 9))
    assert mesurer(traces, depot) == (2, [])
    assert "aucun gel posé le 2026-10-09 ou avant" in capsys.readouterr().err


def test_gel_absent_de_l_historique(
    traces: Path, depot: Depot, capsys: pytest.CaptureFixture[str]
) -> None:
    # Un gel écrit dans revues.toml mais jamais commité n'a pas de commit : ses tables sont
    # introuvables, la mesure ne se fait pas.
    texte_revues = revues((GEL_2, "pilote"), (GEL_3, "pilote-3"), ("2026-10-21T09:00:00", "p4"))
    (depot.racine / "banc" / "mesures" / "revues.toml").write_text(texte_revues, encoding="utf-8")
    assert mesurer(traces, depot) == (2, [])
    erreur = capsys.readouterr().err
    assert (
        "gel du 2026-10-21T09:00:00 introuvable dans l'historique de banc/mesures/revues.toml"
        in (erreur)
    )


def test_depot_sans_git(traces: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    racine = tmp_path / "copie"
    (racine / "banc" / "mesures").mkdir(parents=True)
    (racine / "banc" / "mesures" / "revues.toml").write_text(
        revues((GEL_2, "pilote")), encoding="utf-8"
    )
    assert mesurer(traces, Depot(racine, "", "")) == (2, [])
    assert "git log : " in capsys.readouterr().err


# --- Hors du filet de mots-clés ------------------------------------------------------------------


def test_hors_filet_marquee(traces: Path, depot: Depot) -> None:
    # Poissirène, que le filet ne trouve pas, est marquée horsFilet dans le classement de Q9 :
    # hors filet, avec son ensemble au gel.
    _, sortie = mesurer(traces, depot)
    assert lignes_de(sortie, "Q9")[3].startswith("  · hors filet : Poissirène (écarté), Barpau")


def test_hors_filet_dans_la_grille(traces: Path, tmp_path: Path) -> None:
    # Une espèce acceptée sur preuve (ADR-0008), marquée horsFilet : dans la grille, et hors filet
    # aussi, car le filet ne la trouve pas.
    marques = {"Q9": ("Poissirène", "Kabutops")}
    _, sortie = mesurer(traces, depot_au_gel(tmp_path / "preuve", TABLES, marques))
    q9 = lignes_de(sortie, "Q9")
    assert q9[2].endswith(", Stari, Kabutops")
    assert q9[3].startswith("  · hors filet : Kabutops (acceptable), Poissirène (écarté), Barpau")


def test_espece_du_filet_ni_grille_ni_hors_filet(traces: Path, depot: Depot) -> None:
    # Laggron, écarté de la table de Q3 et trouvé par le filet : ni dans la grille, ni hors filet.
    _, sortie = mesurer(traces, depot)
    assert not [ligne for ligne in lignes_de(sortie, "Q3") if "Laggron" in ligne]


def test_hors_filet_du_vrai_q09() -> None:
    # Le vrai classement de Q9 marque Poissirène hors filet, sur une ligne de suite (README).
    classement = (RECHERCHE.parent / "q09.cypher").read_text(encoding="utf-8")
    assert recherche_seule.hors_filet_marques(classement) == {"Poissirène"}


# --- Même recherche d'une trace à l'autre --------------------------------------------------------


def test_resultats_differents(traces: Path, depot: Depot) -> None:
    # Une passe dont la recherche de Q9 rend un autre résultat : écart, chaque trace avec
    # l'empreinte de son résultat ; la question n'est pas mesurée.
    autre = texte(RESULTATS["Q9"][:19])
    tracer(traces, entete("graphrag-claude", "Q9", passe=2), autre)
    code, sortie = mesurer(traces, depot)
    premier = hashlib.sha256(texte(RESULTATS["Q9"]).encode("utf-8")).hexdigest()[:12]
    second = hashlib.sha256(autre.encode("utf-8")).hexdigest()[:12]
    assert code == 1
    assert lignes_de(sortie, "Q9") == [
        "✗ Q9 : 2 résultats différents dans 3 traces",
        f"  · graphrag-claude-p1-Q9-e1.jsonl : résultat {premier}",
        f"  · graphrag-claude-p2-Q9-e1.jsonl : résultat {second}",
        f"  · graphrag-gemini-p1-Q9-e1.jsonl : résultat {premier}",
    ]
    assert sortie[-1] == "ÉCART : 1 question(s) sur 5."


def test_question_sans_recherche(traces: Path, depot: Depot) -> None:
    # Une question sémantique sans recherche dans les traces n'a pas de mesure : écart.
    for fichier in (traces / "g-1").glob("*-Q16-*.jsonl"):
        fichier.unlink()
    code, sortie = mesurer(traces, depot)
    assert code == 1
    assert lignes_de(sortie, "Q16") == ["✗ Q16 : aucune recherche réussie dans les traces"]
    assert sortie[-1] == "ÉCART : 1 question(s) sur 5."


def test_recherche_en_erreur_ignoree(traces: Path, depot: Depot) -> None:
    # Une recherche en erreur (serveur perdu) n'a pas de résultat : elle ne compte pas.
    refus = "Neo4jError: connexion perdue"
    tracer(traces, entete("graphrag-claude", "Q3", passe=2), refus, erreur=True)
    code, sortie = mesurer(traces, depot)
    assert code == 0
    assert lignes_de(sortie, "Q3")[0] == "✓ Q3 : 5 espèces retrouvées, même résultat dans 2 traces"


def test_trace_ecartee_ignoree(traces: Path, depot: Depot) -> None:
    # Une trace écartée (.jsonl.ecartee, cellule fautive) ne compte pas, même avec un autre
    # résultat.
    fichier = tracer(traces, entete("graphrag-claude", "Q9", passe=2), texte(["Barpau"]))
    fichier.rename(fichier.with_name(f"{fichier.name}.ecartee"))
    assert mesurer(traces, depot) == (0, conforme(depot))


# --- Erreurs techniques ---------------------------------------------------------------------------


def test_plus_de_vingt_especes(
    tmp_path: Path, depot: Depot, capsys: pytest.CaptureFixture[str]
) -> None:
    # 21 espèces : plus que la recherche n'en rend, ce n'est pas sa requête.
    resultats = {question: texte(especes) for question, especes in RESULTATS.items()}
    resultats["Q9"] = texte([*RESULTATS["Q9"], "Lokhlass"])
    traces = campagne(tmp_path / "traces", resultats)
    assert mesurer(traces, depot) == (2, [])
    assert "Q9 : 21 espèces, plus que les 20 de la recherche" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("resultat", "message"),
    [
        pytest.param("pas du JSON", "Q3 : résultat de recherche illisible", id="texte"),
        pytest.param('{"espece": "Magmar"}', "Q3 : résultat de recherche inattendu", id="objet"),
        pytest.param(
            '[{"nom": "Magmar"}]', "Q3 : résultat de recherche inattendu", id="sans-espece"
        ),
    ],
)
def test_resultat_illisible(
    tmp_path: Path,
    depot: Depot,
    capsys: pytest.CaptureFixture[str],
    resultat: str,
    message: str,
) -> None:
    resultats = {question: texte(especes) for question, especes in RESULTATS.items()}
    resultats["Q3"] = resultat
    traces = campagne(tmp_path / "traces", resultats)
    assert mesurer(traces, depot) == (2, [])
    assert message in capsys.readouterr().err


def test_grille_vide(traces: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Une table sans espèce obligatoire ni acceptable n'a pas de part : erreur, pas une division
    # par zéro.
    vide = depot_au_gel(tmp_path / "vide", TABLES | {"Q16": {"Arcanin": ECARTE}}, HORS_FILET)
    assert mesurer(traces, vide) == (2, [])
    assert "Q16 : aucune espèce obligatoire ni acceptable" in capsys.readouterr().err


def test_table_du_gel_illisible(
    traces: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Un ensemble hors de l'ADR-0008 dans la table du gel : la table ne se lit pas, erreur.
    tables = TABLES | {"Q3": {"Magmar": "peut-être"}}
    assert mesurer(traces, depot_au_gel(tmp_path / "faute", tables, HORS_FILET)) == (2, [])
    assert "Q3 : table du gel illisible" in capsys.readouterr().err


def test_campagne_de_la_technique_2(
    tmp_path: Path, depot: Depot, capsys: pytest.CaptureFixture[str]
) -> None:
    resultats = {question: texte(especes) for question, especes in RESULTATS.items()}
    traces = campagne(tmp_path / "traces", resultats, cellules=("adk-claude", "adk-gemini"))
    assert mesurer(traces, depot) == (2, [])
    assert "sans recherche vectorielle (technique 2)" in capsys.readouterr().err


def test_campagne_en_faux_serveur(
    tmp_path: Path, depot: Depot, capsys: pytest.CaptureFixture[str]
) -> None:
    # Une répétition générale : la recherche a rendu le résultat fixe du faux serveur.
    resultats = {question: texte(especes) for question, especes in RESULTATS.items()}
    traces = campagne(tmp_path / "traces", resultats, faux_serveur=True)
    assert mesurer(traces, depot) == (2, [])
    assert "faux serveur : sa recherche n'a pas lu la base" in capsys.readouterr().err


def test_campagne_introuvable(
    tmp_path: Path, depot: Depot, capsys: pytest.CaptureFixture[str]
) -> None:
    assert mesurer(tmp_path, depot, "absente") == (2, [])
    assert "campagne.json illisible" in capsys.readouterr().err


def test_nom_de_campagne_invalide(
    tmp_path: Path, depot: Depot, capsys: pytest.CaptureFixture[str]
) -> None:
    assert mesurer(tmp_path, depot, "../g-1") == (2, [])
    assert "un code attendu" in capsys.readouterr().err


def test_campagne_sans_trace(
    tmp_path: Path, depot: Depot, capsys: pytest.CaptureFixture[str]
) -> None:
    traces = tmp_path
    parametres = orchestration.Campagne(
        nom="g-1",
        passes=1,
        conversations=(("Q3",),),
        cellules=CELLULES,
        empreinte_prompt=hashlib.sha256(b"prompt").hexdigest(),
        empreinte_recherche=empreinte_recherche(),
    )
    orchestration.ecrire_campagne(traces / "g-1" / "campagne.json", parametres)
    assert mesurer(traces, depot) == (2, [])
    assert "aucune trace" in capsys.readouterr().err


# --- Ligne de commande ---------------------------------------------------------------------------


def test_point_d_entree(monkeypatch: pytest.MonkeyPatch) -> None:
    appels: list[str] = []

    def commande(campagne: str) -> int:
        appels.append(campagne)
        return 7

    monkeypatch.setattr(recherche_seule, "commande", commande)
    assert main(["recherche-seule", "--campagne", "g-1"]) == 7
    assert appels == ["g-1"]
