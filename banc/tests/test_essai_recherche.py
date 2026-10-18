"""Essai de la recherche (banc essai-recherche, spec 003 T8.2) sans base, sans Vertex ni réseau.

Un faux neo4j-mcp (tests/fixtures/faux_serveur_mcp.py) répond aux trois recherches dans l'ordre (le
vecteur factice, puis les deux phrases), à la lecture de la description et à la symétrie par motif ;
un faux encodeur note ses appels. L'essai doit juger chaque contrôle, ne rien encoder si la requête
échoue, et relever la taille du contexte et la latence.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
from test_contamination import INTERDITES, contient, mots

from banc import __main__, essai_recherche
from banc.encodage import DOCUMENT, QUESTION, Encodage, EncodageError
from banc.essai_recherche import COLONNES, PHRASES, Moyens, symetrie
from banc.essai_serveur import EssaiError
from banc.questions import charger

FIXTURES = Path(__file__).parent / "fixtures"
RECHERCHE = (Path(__file__).resolve().parents[2] / "questions" / "recherche.cypher").read_text(
    encoding="utf-8"
)
DESCRIPTION = "Un texte factice, lu comme une description."
IDENTIFIANT = "4:factice:1"


def espece(rang: int, descriptions: int = 2, **changees: Any) -> dict[str, Any]:
    """Un enregistrement de recherche.cypher : une espèce, ses colonnes, ses descriptions."""
    enregistrement: dict[str, Any] = {
        "espece": f"Espèce {rang}",
        "categorie": "Pokémon Factice",
        "types": ["Normal"],
        "talents": [{"nom": "Talent", "cache": False}],
        "statistiques": {"statPv": 50},
        "evolueDe": [],
        "evolueEn": [],
        "descriptions": [
            {"texte": f"Texte {rang}.{n}", "jeux": ["Jeu"], "score": 0.8}
            for n in range(descriptions)
        ],
    }
    return enregistrement | changees


def contexte(*enregistrements: dict[str, Any]) -> dict[str, Any]:
    return {"texte": json.dumps(list(enregistrements), ensure_ascii=False)}


CONFORME = contexte(espece(1), espece(2, descriptions=1), espece(3))


@dataclass
class FauxEncodeur:
    """Encode sans Vertex : un vecteur de 3 072 dimensions, et chaque appel noté."""

    erreur: Exception | None = None
    appels: list[tuple[str, str]] = field(default_factory=list)

    def __call__(self, texte: str, tache: str) -> Encodage:
        self.appels.append((texte, tache))
        if self.erreur is not None:
            raise self.erreur
        return Encodage(vecteur=(0.25,) * 3072, jetons=12, latence_s=0.05)


@dataclass
class Essai:
    code: int
    lignes: list[str]
    erreurs: str
    encodeur: FauxEncodeur
    journal: list[dict[str, Any]]

    def ligne(self, debut: str) -> str:
        trouvees = [ligne for ligne in self.lignes if ligne.startswith(debut)]
        assert len(trouvees) == 1, (debut, self.lignes)
        return trouvees[0]

    def appels(self) -> list[dict[str, Any]]:
        """Les arguments de chaque appel de read-cypher, dans l'ordre."""
        return [
            note["recu"]["params"]["arguments"]
            for note in self.journal
            if note.get("recu", {}).get("method") == "tools/call"
        ]


@pytest.fixture
def lancer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Any:
    def lancer(
        recherches: list[dict[str, Any]] | None = None,
        description: dict[str, Any] | None = None,
        similarite: dict[str, Any] | None = None,
        encodeur: FauxEncodeur | None = None,
        serveur: tuple[str, ...] | None = None,
    ) -> Essai:
        lu = {"texte": json.dumps([{"id": IDENTIFIANT, "texte": DESCRIPTION}])}
        scenario = {
            "appels": recherches if recherches is not None else [CONFORME] * 3,
            "par_requete": [
                ["ORDER BY p.id, d.texte LIMIT 1", description or lu],
                ["vector.similarity.cosine", similarite or {"texte": '[{"similarite": 0.99997}]'}],
            ],
        }
        fichier = tmp_path / "scenario.json"
        fichier.write_text(json.dumps(scenario))
        journal = tmp_path / "journal.jsonl"
        encodeur = encodeur or FauxEncodeur()
        lignes: list[str] = []
        faux = (sys.executable, "-I", str(FIXTURES / "faux_serveur_mcp.py"), str(fichier))
        moyens = Moyens(
            serveur=serveur or (*faux, str(journal)),
            chemins=lambda: (),
            connexion_s=10.0,
            encoder=encodeur,
            ecrire=lignes.append,
        )
        code = essai_recherche.commande(moyens)
        notes = journal.read_text().splitlines() if journal.exists() else []
        return Essai(
            code, lignes, capsys.readouterr().err, encodeur, [json.loads(n) for n in notes]
        )

    return lancer


# --- Conforme ------------------------------------------------------------------------------------


def test_tout_conforme(lancer: Any) -> None:
    essai = lancer()
    assert essai.code == 0, essai.lignes
    assert essai.lignes[-1] == "CONFORME : 4 contrôles."
    # Deux phrases encodées en question, puis la description de contrôle en document.
    assert essai.encodeur.appels == [
        (PHRASES[0], QUESTION),
        (PHRASES[1], QUESTION),
        (DESCRIPTION, DOCUMENT),
    ]


def test_appels_de_read_cypher(lancer: Any) -> None:
    # La requête telle que la lancera la cellule, d'abord sur le vecteur factice, puis sur chaque
    # phrase encodée ; la description lue ; sa similarité avec le vecteur réencodé, sur la base.
    essai = lancer()
    factice, premiere, seconde, lecture, symetrie = essai.appels()
    for appel in (factice, premiere, seconde):
        assert appel["query"] == RECHERCHE
        assert len(appel["params"]["vecteur"]) == 3072
    assert set(factice["params"]["vecteur"]) == {0.001}
    assert premiere["params"]["vecteur"] == [0.25] * 3072
    assert "params" not in lecture
    assert symetrie["params"] == {"id": IDENTIFIANT, "vecteur": [0.25] * 3072}


def test_taille_et_latence_relevees(lancer: Any) -> None:
    # D6 : la taille du contexte (caractères, jetons estimés par excès) et la latence de
    # read-cypher, pour refaire l'estimation du coût sur la taille mesurée.
    essai = lancer()
    taille = len(CONFORME["texte"])
    for rang in (1, 2):
        ligne = essai.ligne(f"  · phrase {rang} : ")
        assert f"{taille} caractères" in ligne
        assert f"≈ {-(-taille // 3)} jetons" in ligne
        assert "read-cypher" in ligne


def test_description_jamais_ecrite(lancer: Any) -> None:
    # ADR-0001 : aucun texte de description dans le compte rendu, seulement sa longueur.
    essai = lancer()
    assert not [ligne for ligne in essai.lignes if DESCRIPTION in ligne]
    assert f"{len(DESCRIPTION)} caractères" in essai.ligne("  · description de contrôle : ")


# --- Écarts --------------------------------------------------------------------------------------


def test_requete_en_erreur_rien_n_est_encode(lancer: Any) -> None:
    # Le premier contrôle passe avant tout encodage : une requête cassée ne dépense rien.
    refus = {"erreur": True, "texte": "Neo.ClientError.Statement.SyntaxError: requête invalide"}
    essai = lancer(recherches=[refus])
    assert essai.code == 1
    assert essai.ligne("✗ requête").endswith(
        "Neo.ClientError.Statement.SyntaxError: requête invalide"
    )
    assert essai.encodeur.appels == []


@pytest.mark.parametrize(
    ("resultat", "motif"),
    [
        pytest.param(contexte(*(espece(n) for n in range(21))), "21 espèce(s)", id="21-especes"),
        pytest.param(contexte(), "0 espèce(s)", id="aucune-espece"),
        pytest.param(contexte(espece(1, descriptions=3)), "3 description(s)", id="3-descriptions"),
        pytest.param(
            contexte(espece(1, descriptions=0)), "0 description(s)", id="sans-description"
        ),
        pytest.param(
            contexte(espece(1, descriptions=1) | {"descriptions": [{"embedding": [0.1]}]}),
            "embedding",
            id="vecteur",
        ),
        pytest.param(contexte(espece(1, autre=1)), "colonnes", id="colonne-en-trop"),
        pytest.param({"texte": "pas du JSON"}, "illisible", id="illisible"),
    ],
)
def test_contexte_en_ecart(lancer: Any, resultat: dict[str, Any], motif: str) -> None:
    essai = lancer(recherches=[CONFORME, resultat, CONFORME])
    assert essai.code == 1
    assert motif in essai.ligne("✗ phrase 1")
    assert essai.ligne("✓ phrase 2")


def test_borne_de_vingt_especes(lancer: Any) -> None:
    essai = lancer(recherches=[CONFORME, contexte(*(espece(n) for n in range(20))), CONFORME])
    assert essai.code == 0, essai.lignes


@pytest.mark.parametrize(("similarite", "code"), [(0.9999, 0), (0.99989, 1)])
def test_symetrie_pile_a_la_borne(lancer: Any, similarite: float, code: int) -> None:
    # D5 : 0,9999 au moins, sinon le modèle aurait dérivé et la campagne ne démarre pas.
    essai = lancer(similarite={"texte": json.dumps([{"similarite": similarite}])})
    assert essai.code == code, essai.lignes
    assert str(similarite) in essai.ligne(f"{'✓' if code == 0 else '✗'} symétrie")


# --- Erreurs techniques --------------------------------------------------------------------------


def test_encodage_impossible(lancer: Any) -> None:
    essai = lancer(encodeur=FauxEncodeur(erreur=EncodageError("Vertex refuse l'encodage (403)")))
    assert essai.code == 2
    assert "banc essai-recherche : Vertex refuse l'encodage (403)" in essai.erreurs


def test_description_illisible(lancer: Any) -> None:
    essai = lancer(description={"texte": "[]"})
    assert essai.code == 2
    assert "description de contrôle illisible" in essai.erreurs


def test_serveur_injoignable(lancer: Any) -> None:
    essai = lancer(serveur=(sys.executable, "-I", "-c", "pass"))
    assert essai.code == 2
    assert essai.erreurs.startswith("banc essai-recherche : ")


# --- Preuve de symétrie seule, à la création d'une campagne GraphRAG (T13.1) --------------------


def moyens_de_symetrie(
    tmp_path: Path,
    description: dict[str, Any] | None = None,
    similarite: dict[str, Any] | None = None,
    serveur: tuple[str, ...] | None = None,
) -> Moyens:
    """Le faux serveur MCP qui rend la description de contrôle et sa similarité."""
    lu = {"texte": json.dumps([{"id": IDENTIFIANT, "texte": DESCRIPTION}])}
    scenario = {
        "par_requete": [
            ["ORDER BY p.id, d.texte LIMIT 1", description or lu],
            ["vector.similarity.cosine", similarite or {"texte": '[{"similarite": 0.99997}]'}],
        ]
    }
    fichier = tmp_path / "scenario.json"
    fichier.write_text(json.dumps(scenario))
    faux = (sys.executable, "-I", str(FIXTURES / "faux_serveur_mcp.py"), str(fichier))
    return Moyens(
        serveur=serveur or (*faux, str(tmp_path / "journal.jsonl")),
        chemins=lambda: (),
        connexion_s=10.0,
    )


def test_symetrie_seule(tmp_path: Path) -> None:
    # La preuve de T8.2 sans le reste de l'essai : la description de contrôle, réencodée en
    # RETRIEVAL_DOCUMENT par l'encodeur de la campagne, comparée sur la base à son vecteur stocké ;
    # la similarité est rendue, la campagne en juge.
    encodeur = FauxEncodeur()
    assert symetrie(encodeur, moyens_de_symetrie(tmp_path)) == 0.99997
    assert encodeur.appels == [(DESCRIPTION, DOCUMENT)]


@pytest.mark.parametrize(
    ("description", "similarite", "motif"),
    [
        ({"texte": "[]"}, None, "description de contrôle illisible"),
        (None, {"texte": "[]"}, "similarité illisible"),
        (None, {"texte": "Neo.ClientError: refus", "erreur": True}, "similarité illisible"),
    ],
    ids=["description", "similarite", "erreur"],
)
def test_symetrie_seule_illisible(
    tmp_path: Path,
    description: dict[str, Any] | None,
    similarite: dict[str, Any] | None,
    motif: str,
) -> None:
    moyens = moyens_de_symetrie(tmp_path, description, similarite)
    with pytest.raises(EssaiError, match=motif):
        symetrie(FauxEncodeur(), moyens)


def test_symetrie_seule_serveur_injoignable(tmp_path: Path) -> None:
    # Une erreur du client MCP (regroupée par anyio) devient une erreur de l'essai.
    moyens = moyens_de_symetrie(tmp_path, serveur=(sys.executable, "-I", "-c", "pass"))
    with pytest.raises(EssaiError):
        symetrie(FauxEncodeur(), moyens)


# --- Phrases et commande -------------------------------------------------------------------------


def test_phrases_hors_du_banc() -> None:
    # T8.2 : des phrases maison, ni questions du banc ni valeurs de ses réponses (ADR-0009) ; leurs
    # thèmes évitent ceux des cinq questions sémantiques (volcans, océan, tour de la planète, danger
    # pour les humains, sommeil).
    assert len(PHRASES) == 2
    textes = {question.texte for question in charger().questions.values()}
    for phrase in PHRASES:
        assert phrase not in textes
        assert not [v for v in INTERDITES if contient(mots(phrase), mots(v))], phrase
    for theme in ("volcan", "ocean", "planete", "humain", "dort", "dormir", "sommeil"):
        assert not [p for p in PHRASES if theme in " ".join(mots(p))], theme


def test_colonnes_de_la_requete() -> None:
    # Le contrôle attend les colonnes que rend questions/recherche.cypher (T7.2).
    assert COLONNES == (
        "espece", "categorie", "types", "talents", "statistiques", "evolueDe", "evolueEn",
        "descriptions",
    )  # fmt: skip


def test_commande_branchee(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(essai_recherche, "commande", lambda: 7)
    assert __main__.main(["essai-recherche"]) == 7
