"""Contre-épreuve de la revue assistée (ADR-0014 ; plan 003, D15 ; T1.1) : tirage de 8 cas sur la
graine du CSV fini, page à l'aveugle et clés à part, cas de la pré-analyse, taux d'accord et
désaccords, puis décisions validées enregistrées par la revue elle-même. Ni base ni LLM : des
campagnes écrites à la main, et les CSV versionnés du jalon 2 pour refaire ses tirages.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime
from pathlib import Path

import pytest

from banc import contre_epreuve, mesures, revue
from banc.__main__ import main
from banc.contre_epreuve import (
    JE_NE_SAIS_PAS,
    NOMBRE,
    Accord,
    CasTire,
    Cles,
    ContreEpreuveError,
    Desaccord,
    Proposition,
    Reponse,
    accord,
    besoins,
    graine,
    lire_cles,
    lire_preanalyse,
    lire_reponses,
    population,
    preparer,
    tirer,
)
from banc.mesures import (
    COLONNES,
    Entete,
    Journal,
    commit_pokeapi,
    ecrire,
    fichier_mesures,
    fichier_trace,
)
from banc.orchestration import Campagne, ecrire_campagne
from banc.revue import A_REVOIR, Decision, Revues

CELLULES = ("adk-claude", "adk-gemini")
MODELES = {"adk-claude": "claude-sonnet-5-5", "adk-gemini": "gemini-3.8-flash"}
ACCES = {"adk-claude": "api", "adk-gemini": "vertex-eu"}
# Des questions d'une conversation à un seul tour (ni Q2 et Q18, ni Q27 et Q28).
QUESTIONS = ("Q1", "Q3", "Q5", "Q6", "Q8", "Q9")
REPONSE = "Je suis Gemini 3.8 Flash.\n\nRéponse : Aquali\n\nSources : `MATCH (e)`"
REQUETE = "MATCH (e:Espece)\nRETURN e.nom AS nom"
EMPREINTE = "0123456789abcdef"


def ligne_csv(
    cellule: str = "adk-gemini", passe: int = 1, question: str = "Q5", **champs: object
) -> dict[str, str]:
    """Une ligne du CSV de la campagne c1, tranchée par la pré-notation, avec ce qui trahirait la
    cellule ; champs : les colonnes à changer."""
    valeurs = dict.fromkeys(COLONNES, "")
    valeurs |= {
        "campagne": "c1",
        "cellule": cellule,
        "passe": str(passe),
        "question": question,
        "essai": "1",
        "issue": "reponse",
        "note": "juste",
        "source": "oui",
        "empreinte": hashlib.sha256(f"{cellule}-{passe}-{question}".encode()).hexdigest()[:16],
        "modele": MODELES[cellule],
        "duree_s": "12.34",
        "cout_usd": "0.004321",
        "effort": "high",
    }
    return valeurs | {colonne: str(valeur) for colonne, valeur in champs.items()}


def grille(a_revoir: int) -> list[dict[str, str]]:
    """Les 12 lignes d'une passe des deux cellules, menée sans incident ; la note des a_revoir
    premières est à revoir."""
    lignes = [ligne_csv(cellule, 1, question) for question in QUESTIONS for cellule in CELLULES]
    for valeurs in lignes[:a_revoir]:
        valeurs["note"] = A_REVOIR
    return lignes


def installer(monkeypatch: pytest.MonkeyPatch, racine: Path) -> Path:
    """Mesures, traces et pièces des revues d'un poste sous racine ; rend le dossier des pièces de
    la campagne c1."""
    for nom in ("MESURES", "TRACES", "REVUES"):
        monkeypatch.setattr(contre_epreuve, nom, racine / nom.lower())
    return racine / "revues" / "c1"


@pytest.fixture
def poste(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    return installer(monkeypatch, tmp_path)


def poser(poste: Path, lignes: Sequence[Mapping[str, str]], reponse: str = REPONSE) -> None:
    """La campagne c1 finie sur le poste : campagne.json, une trace par conversation, le CSV."""
    racine = poste.parents[1]
    traces = racine / "traces"
    (traces / "c1").mkdir(parents=True)
    questions = tuple(dict.fromkeys(valeurs["question"] for valeurs in lignes))
    parametres = Campagne(
        "c1",
        passes=max(int(valeurs["passe"]) for valeurs in lignes),
        conversations=tuple((question,) for question in questions),
        cellules=tuple(dict.fromkeys(valeurs["cellule"] for valeurs in lignes)),
        empreinte_prompt="c" * 64,
    )
    ecrire_campagne(traces / "c1" / "campagne.json", parametres)
    for valeurs in lignes:
        entete = Entete(
            campagne="c1",
            cellule=valeurs["cellule"],
            passe=int(valeurs["passe"]),
            essai=int(valeurs["essai"]),
            questions=(valeurs["question"],),
            modele=valeurs["modele"],
            acces=ACCES[valeurs["cellule"]],
            jour=date(2026, 10, 21),
            effort="high",
            versions={},
            commit_pokeapi=commit_pokeapi(),
        )
        with Journal(fichier_trace(traces, entete), entete) as journal:
            journal.question(
                valeurs["question"], f"Question {valeurs['question']} telle que posée ?"
            )
            journal.appel("a1", "read-cypher", REQUETE)
            journal.resultat("a1", '[{"nom": "Aquali"}]')
            journal.fin("reponse", reponse=reponse)
    ecrire(fichier_mesures("c1", racine / "mesures"), lignes)


def revues_du_poste(poste: Path) -> Path:
    return poste.parents[1] / "mesures" / "revues.toml"


# --- Tirage --------------------------------------------------------------------------------------


def test_graine_du_csv_fini(tmp_path: Path) -> None:
    # Les 16 premiers caractères hexadécimaux du SHA-256 du CSV : personne ne la choisit.
    fichier = tmp_path / "c1.csv"
    ecrire(fichier, grille(3))
    assert graine(fichier) == hashlib.sha256(fichier.read_bytes()).hexdigest()[:16]


def test_huit_cas_au_plus() -> None:
    cas = population(grille(12), Revues())
    tires = tirer(cas, EMPREINTE)
    assert len(tires) == NOMBRE == 8
    assert len({revue.cle(ligne) for ligne in tires}) == 8
    assert all(ligne in cas for ligne in tires)


def test_moins_de_huit_cas_tous() -> None:
    cas = population(grille(5), Revues())
    assert sorted(map(revue.cle, tirer(cas, EMPREINTE))) == sorted(map(revue.cle, cas))


def test_meme_csv_memes_cas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Le tirage se refait à l'identique : deux postes, le même CSV, les mêmes cas sous les mêmes
    # numéros.
    cles = []
    for nom in ("premier", "second"):
        dossier = installer(monkeypatch, tmp_path / nom)
        poser(dossier, grille(12))
        preparer("c1")
        cles.append((dossier / "cles.json").read_text(encoding="utf-8"))
    assert cles[0] == cles[1]


# Tirages faits au jalon 2 par les scripts de logs/outils/ (pièces dans logs/revues/<campagne>/,
# non versionnées) : la graine, le nombre de cas à revoir, puis la passe et la question des 8 cas
# tirés, dans l'ordre de la page (cellule adk-gemini et essai 1 pour tous).
JALON_2 = {
    "en-1": (
        "98dcbd7d875aff90",
        16,
        [
            (3, "Q12"),
            (1, "Q27"),
            (1, "Q13"),
            (3, "Q1"),
            (1, "Q12"),
            (2, "Q12"),
            (3, "Q29"),
            (1, "Q14"),
        ],
    ),
    "fr-controle": (
        "94cf111db62ab236",
        9,
        [
            (1, "Q13"),
            (1, "Q19"),
            (1, "Q1"),
            (1, "Q12"),
            (1, "Q8"),
            (1, "Q29"),
            (1, "Q27"),
            (1, "Q28"),
        ],
    ),
}


@pytest.mark.parametrize("campagne", sorted(JALON_2))
def test_tirages_du_jalon_2_refaits(campagne: str) -> None:
    # Les CSV versionnés, et revues.toml tel qu'au tirage : sans les décisions prises depuis la
    # première de la campagne (les siennes, puis celles des campagnes suivantes).
    attendue, nombre, tires = JALON_2[campagne]
    csv = fichier_mesures(campagne, mesures.MESURES)
    actuelles = revue.charger(mesures.MESURES / "revues.toml")
    premiere = min(d.date for d in actuelles.decisions if d.campagne == campagne)
    avant = tuple(d for d in actuelles.decisions if d.date < premiere)
    cas = population(mesures.lire_lignes(csv), Revues(actuelles.gel, avant, actuelles.pilote))
    assert (graine(csv), len(cas)) == (attendue, nombre)
    tirage = tirer(cas, attendue)
    assert {(ligne["cellule"], ligne["essai"]) for ligne in tirage} == {("adk-gemini", "1")}
    assert [(int(ligne["passe"]), ligne["question"]) for ligne in tirage] == tires


# --- Garde-fous ----------------------------------------------------------------------------------


def test_campagne_incomplete_refusee(poste: Path) -> None:
    # La graine se prend sur le CSV fini : une conversation qui attend sa ligne le changera.
    lignes = grille(3)
    poser(poste, lignes)
    csv = fichier_mesures("c1", poste.parents[1] / "mesures")
    csv.unlink()
    ecrire(csv, lignes[:-1])
    with pytest.raises(ContreEpreuveError, match="incomplète"):
        preparer("c1")
    assert not poste.exists()


def test_campagne_deja_revue_refusee(poste: Path) -> None:
    # La contre-épreuve se tire avant toute décision de la campagne : après, les cas déjà tranchés
    # manqueraient au tirage (ADR-0014).
    lignes = grille(3)
    poser(poste, lignes)
    deja = Decision(*revue.cle(lignes[0]), lignes[0]["empreinte"], datetime(2026, 10, 21), "juste")
    revue.ajouter(revues_du_poste(poste), deja)
    with pytest.raises(ContreEpreuveError, match="déjà revue"):
        preparer("c1")
    assert not poste.exists()


def test_decisions_d_une_autre_campagne_sans_effet(poste: Path) -> None:
    lignes = grille(3)
    poser(poste, lignes)
    ailleurs = Decision("c0", "adk-claude", 1, "Q1", 1, EMPREINTE, datetime(2026, 10, 21), "juste")
    revue.ajouter(revues_du_poste(poste), ailleurs)
    assert len(preparer("c1").tires) == 3


def test_tirage_deja_fait_refuse(poste: Path) -> None:
    # Ses numéros lient les réponses de Julien aux cas : un second tirage les changerait.
    poser(poste, grille(3))
    preparer("c1")
    avant = {fichier.name: fichier.read_bytes() for fichier in poste.iterdir()}
    with pytest.raises(ContreEpreuveError, match="déjà fait"):
        preparer("c1")
    assert {fichier.name: fichier.read_bytes() for fichier in poste.iterdir()} == avant


def test_aucun_cas_a_revoir(poste: Path) -> None:
    poser(poste, grille(0))
    cles = preparer("c1")
    assert (cles.tires, dict(cles.cas)) == ((), {})
    assert not poste.exists()


def test_tirage_interrompu_se_refait(poste: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Les clés s'écrivent en dernier : un tirage arrêté avant elles (ici, sans gabarit) se refait.
    poser(poste, grille(3))
    gabarit = contre_epreuve.GABARIT
    monkeypatch.setattr(contre_epreuve, "GABARIT", poste.parents[1] / "absent.html")
    with pytest.raises(FileNotFoundError):
        preparer("c1")
    assert not (poste / "cles.json").exists()
    monkeypatch.setattr(contre_epreuve, "GABARIT", gabarit)
    assert len(preparer("c1").tires) == 3


# --- Pièces : page, clés, cas de la pré-analyse --------------------------------------------------


def test_pieces_du_tirage(poste: Path) -> None:
    # La page pour Julien, tous les cas pour la pré-analyse, les clés à part.
    lignes = grille(10)
    poser(poste, lignes)
    cles = preparer("c1")
    assert sorted(f.name for f in poste.iterdir()) == [
        "cles.json",
        "contre-epreuve.html",
        "tous.txt",
    ]
    assert lire_cles(poste) == cles
    assert cles.graine == graine(fichier_mesures("c1", poste.parents[1] / "mesures"))
    # R1…R10 : les cas à revoir dans l'ordre de banc revoir ; le cas k de la page est tires[k - 1].
    ordre = population(lignes, Revues())
    assert [(c.cellule, c.passe, c.question, c.essai, c.empreinte) for c in cles.cas.values()] == [
        (v["cellule"], int(v["passe"]), v["question"], int(v["essai"]), v["empreinte"])
        for v in ordre
    ]
    assert list(cles.cas) == [f"R{numero}" for numero in range(1, 11)]
    assert cles.tires == tuple(f"R{ordre.index(v) + 1}" for v in tirer(ordre, cles.graine))


def test_page_a_l_aveugle(poste: Path) -> None:
    # Ni cellule, ni modèle, ni passe, ni coût, ni durée : le numéro du cas et sa question.
    poser(poste, grille(10))
    preparer("c1")
    page = (poste / "contre-epreuve.html").read_text(encoding="utf-8")
    for indice in (*CELLULES, *MODELES.values(), "Gemini 3.8", "0.004321", "12.34", "vertex-eu"):
        assert indice not in page, indice
    for indice in ("data-passe", '"passe"', "data-cellule"):
        assert indice not in page, indice
    assert "Je suis ‹modèle›." in page
    assert page.count('<article class="cas"') == 8


def test_cas_de_la_pre_analyse_a_l_aveugle(poste: Path) -> None:
    # Tous les cas à revoir, R1…Rn dans l'ordre de banc revoir, pour la pré-analyse de Claude.
    lignes = grille(10)
    poser(poste, lignes)
    preparer("c1")
    texte = (poste / "tous.txt").read_text(encoding="utf-8")
    for indice in (*CELLULES, *MODELES.values(), "Gemini 3.8", "0.004321", "12.34", "vertex-eu"):
        assert indice not in texte, indice
    entetes = [ligne for ligne in texte.splitlines() if ligne.startswith("=====")]
    assert entetes == [f"===== R{numero} : à trancher, note =====" for numero in range(1, 11)]
    questions = [ligne.split()[1] for ligne in texte.splitlines() if ligne.startswith("Question ")]
    assert questions == [v["question"] for v in population(lignes, Revues())]


def test_texte_des_agents_echappe(poste: Path) -> None:
    # Une réponse d'agent est du texte : rien de ce qu'elle contient ne s'exécute dans la page.
    poser(poste, grille(1), reponse="Réponse : <script>alert(1)</script> & <b>gras</b>")
    preparer("c1")
    page = (poste / "contre-epreuve.html").read_text(encoding="utf-8")
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; &lt;b&gt;gras&lt;/b&gt;" in page
    assert "<script>alert" not in page


def test_page_remplie_en_une_passe(poste: Path) -> None:
    # Ce qui entre dans le gabarit ne s'y relit pas : une réponse qui cite « {{GRAINE}} » le garde.
    poser(poste, grille(1), reponse="Réponse : {{GRAINE}} et {{CAMPAGNE}}")
    preparer("c1")
    page = (poste / "contre-epreuve.html").read_text(encoding="utf-8")
    assert "Réponse : {{GRAINE}} et {{CAMPAGNE}}" in page


def test_stockage_local_propre_a_la_campagne(poste: Path) -> None:
    # La page garde les choix de Julien dans le navigateur sous une clé de sa campagne : deux
    # contre-épreuves ne se mélangent pas (le script du jalon 2 avait celle de fr-controle en dur).
    poser(poste, grille(2))
    preparer("c1")
    page = (poste / "contre-epreuve.html").read_text(encoding="utf-8")
    assert 'const CLE = "contre-epreuve-c1";' in page
    assert "{{" not in page


def test_besoins_de_chaque_cas(poste: Path) -> None:
    # La page ne demande que ce qui reste à trancher : la note, la source, ou les deux.
    lignes = grille(0)
    lignes[0]["note"] = A_REVOIR
    lignes[1]["source"] = A_REVOIR
    lignes[2] |= {"note": A_REVOIR, "source": A_REVOIR}
    poser(poste, lignes)
    cles = preparer("c1")
    assert {(c.cellule, c.question): c.besoins for c in cles.cas.values()} == {
        ("adk-claude", "Q1"): ("note",),
        ("adk-gemini", "Q1"): ("source",),
        ("adk-claude", "Q3"): ("note", "source"),
    }
    page = (poste / "contre-epreuve.html").read_text(encoding="utf-8")
    assert (page.count("<legend>Note</legend>"), page.count("<legend>Source</legend>")) == (2, 2)


def test_besoins_apres_une_note_reprise() -> None:
    # Une note déjà tranchée par une décision réutilisée (même réponse courte, après le gel) ne se
    # redemande pas : seule la source reste, comme dans banc revoir.
    ligne = ligne_csv(note=A_REVOIR, source=A_REVOIR, empreinte=EMPREINTE)
    autre = Decision("c0", "adk-claude", 1, "Q5", 1, EMPREINTE, datetime(2026, 10, 2), "juste")
    assert besoins(ligne, Revues(datetime(2026, 10, 1), (autre,), "pilote")) == ("source",)
    assert besoins(ligne, Revues()) == ("note", "source")


# --- Réponses de Julien --------------------------------------------------------------------------


def cles_de(*besoins_des_cas: tuple[str, ...]) -> Cles:
    """Les clés d'un tirage : le cas k de la page a les besoins besoins_des_cas[k - 1] et la
    question QUESTIONS[k - 1] ; les numéros R vont à rebours de la page."""
    nombre = len(besoins_des_cas)
    cas = {
        f"R{nombre - rang}": CasTire("adk-gemini", 1, QUESTIONS[rang], 1, EMPREINTE, besoins)
        for rang, besoins in reversed(list(enumerate(besoins_des_cas)))
    }
    return Cles("c1", EMPREINTE, tuple(f"R{nombre - rang}" for rang in range(nombre)), cas)


# Cas 1 de la page : R3, Q1, la note ; cas 2 : R2, Q3, note et source ; cas 3 : R1, Q5, la source.
CLES = cles_de(("note",), ("note", "source"), ("source",))


def test_cles_de_test() -> None:
    assert CLES.tires == ("R3", "R2", "R1")
    assert [CLES.cas[r].question for r in CLES.tires] == ["Q1", "Q3", "Q5"]


def test_reponses_de_la_page() -> None:
    # La ligne que la page fait copier : numéro, lettres de ce qui est à trancher, motif facultatif.
    assert lire_reponses("1 j | 2 p n forme-signalee | 3 x", CLES) == {
        1: Reponse("juste", None),
        2: Reponse("partiel", "non", "forme-signalee"),
        3: Reponse(None, JE_NE_SAIS_PAS),
    }


@pytest.mark.parametrize(
    ("texte", "attendu"),
    [
        pytest.param("1 j | 2 p n | 3 e | 4 j", "cas 4 inconnu", id="cas-inconnu"),
        pytest.param("1 j | 2 p n | 1 f | 3 e", "deux fois", id="cas-en-double"),
        pytest.param("1 j | 3 e", "sans réponse", id="cas-sans-reponse"),
        pytest.param("1 o | 2 p n | 3 e", "illisible", id="lettre-d-un-autre-genre"),
        pytest.param("1 j | 2 p | 3 e", "illisible", id="source-manquante"),
        pytest.param("1 j | 2 p n un-motif autre | 3 e", "illisible", id="deux-motifs"),
        pytest.param("1 j | 2 p n Motif | 3 e", "illisible", id="motif-en-majuscules"),
    ],
)
def test_reponses_refusees(texte: str, attendu: str) -> None:
    with pytest.raises(ContreEpreuveError, match=attendu):
        lire_reponses(texte, CLES)


# --- Pré-analyse ---------------------------------------------------------------------------------


def ecrire_json(fichier: Path, contenu: object) -> Path:
    fichier.write_text(json.dumps(contenu, ensure_ascii=False), encoding="utf-8")
    return fichier


PREANALYSE = [
    {"cas": "R1", "source": "oui", "raison": "la requête porte la valeur"},
    {"cas": "R2", "note": "juste", "source": "non"},
    {"cas": "R3", "note": "partiel", "motif": "forme-signalee", "raison": "une forme de trop"},
]
PROPOSITIONS = {
    "R1": Proposition(None, "oui", None, "la requête porte la valeur"),
    "R2": Proposition("juste", "non"),
    "R3": Proposition("partiel", None, "forme-signalee", "une forme de trop"),
}


def test_preanalyse_relue(tmp_path: Path) -> None:
    # Un objet par cas R1…Rn de tous.txt : ce qu'il tranche, un motif, une raison d'une ligne.
    assert lire_preanalyse(ecrire_json(tmp_path / "p.json", PREANALYSE), CLES) == PROPOSITIONS


@pytest.mark.parametrize(
    ("contenu", "attendu"),
    [
        pytest.param(PREANALYSE[1:], "non tranchés : R1", id="cas-absent"),
        pytest.param(
            [PREANALYSE[0], {"cas": "R2", "note": "juste"}, PREANALYSE[2]],
            "non tranchés : R2",
            id="besoin-non-tranche",
        ),
        pytest.param([*PREANALYSE, {"cas": "R4", "note": "juste"}], "R4 inconnu", id="cas-inconnu"),
        pytest.param([*PREANALYSE, {"cas": ["R1"], "note": "juste"}], "inconnu", id="cas-en-liste"),
        pytest.param([*PREANALYSE, PREANALYSE[0]], "R1 deux fois", id="cas-en-double"),
        pytest.param([{**PREANALYSE[2], "note": "excellent"}], r"invalide \(note\)", id="note"),
        pytest.param(
            [{**PREANALYSE[0], "source": "peut-être"}], r"invalide \(source\)", id="source"
        ),
        pytest.param([{**PREANALYSE[2], "motif": "f"}], r"invalide \(motif\)", id="motif"),
        pytest.param([{**PREANALYSE[0], "nate": "juste"}], "champs inconnus", id="champ-inconnu"),
        pytest.param({"R1": "oui"}, "une liste", id="pas-une-liste"),
    ],
)
def test_preanalyse_refusee(tmp_path: Path, contenu: object, attendu: str) -> None:
    with pytest.raises(ContreEpreuveError, match=attendu):
        lire_preanalyse(ecrire_json(tmp_path / "p.json", contenu), CLES)


# --- Accord --------------------------------------------------------------------------------------


def test_accord_complet() -> None:
    reponses = lire_reponses("1 p | 2 j n | 3 o", CLES)
    assert accord(CLES, reponses, PROPOSITIONS) == Accord((2, 2), (2, 2), 0, ())


def test_desaccord_sur_une_note() -> None:
    # Accord = même note (ADR-0014) ; chaque désaccord se liste avec la proposition et sa raison.
    resultat = accord(CLES, lire_reponses("1 j | 2 j n | 3 o", CLES), PROPOSITIONS)
    assert resultat.notes == (1, 2)
    assert resultat.desaccords == (
        Desaccord(1, "Q1", "note", "juste", "partiel", "forme-signalee", "une forme de trop"),
    )


def test_sources_comptees_a_part() -> None:
    resultat = accord(CLES, lire_reponses("1 p | 2 j o | 3 n", CLES), PROPOSITIONS)
    assert (resultat.notes, resultat.sources) == ((2, 2), (0, 2))
    assert [(d.numero, d.genre) for d in resultat.desaccords] == [(2, "source"), (3, "source")]


def test_je_ne_sais_pas_hors_comparaison() -> None:
    # « Je ne sais pas » (x) : le cas sort de la comparaison pour ce qu'il ne tranche pas.
    resultat = accord(CLES, lire_reponses("1 x | 2 j x | 3 o", CLES), PROPOSITIONS)
    assert resultat == Accord((1, 1), (1, 1), 2, ())


def test_commande_accord(poste: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Le sceau (SHA-256 de la pré-analyse, annoncé avant les réponses de Julien) se relit au calcul.
    poser(poste, grille(2))
    cles = preparer("c1")
    fichier = ecrire_json(
        poste / "preanalyse.json", [{"cas": r, "note": "juste"} for r in cles.cas]
    )
    sceau = hashlib.sha256(fichier.read_bytes()).hexdigest()
    assert main(["contre-epreuve", "--campagne", "c1", "--accord", "1 j | 2 j"]) == 0
    sortie = capsys.readouterr().out
    assert sceau in sortie
    assert "notes : 2/2 d'accord" in sortie
    assert main(["contre-epreuve", "--campagne", "c1", "--accord", "1 j | 2 f"]) == 1
    assert "désaccord, cas 2" in capsys.readouterr().out


# --- Enregistrement des décisions validées -------------------------------------------------------


def numeros(cles: Cles) -> dict[tuple[str, str], str]:
    """(cellule, question) → numéro R du cas."""
    return {(c.cellule, c.question): r for r, c in cles.cas.items()}


def test_decisions_validees_enregistrees(poste: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Par banc.revue.revoir, cas après cas, comme au clavier ; avec la note en tête de leurs tables
    # qui dit d'où elles viennent (ADR-0014).
    lignes = grille(0)
    lignes[0]["note"] = A_REVOIR
    lignes[1]["source"] = A_REVOIR
    lignes[2] |= {"note": A_REVOIR, "source": A_REVOIR}
    poser(poste, lignes)
    r = numeros(preparer("c1"))
    propositions = [
        {"cas": r["adk-claude", "Q1"], "note": "partiel", "motif": "forme-signalee"},
        {"cas": r["adk-gemini", "Q1"], "source": "non"},
        {"cas": r["adk-claude", "Q3"], "note": "juste", "source": "oui"},
    ]
    ecrire_json(poste / "preanalyse.json", propositions)
    assert main(["contre-epreuve", "--campagne", "c1", "--enregistrer"]) == 0
    decisions = revue.charger(revues_du_poste(poste)).decisions
    assert {(d.cellule, d.question, d.note, d.source, d.motif) for d in decisions} == {
        ("adk-claude", "Q1", "partiel", None, "forme-signalee"),
        ("adk-gemini", "Q1", None, "non", None),
        ("adk-claude", "Q3", "juste", "oui", None),
    }
    texte = revues_du_poste(poste).read_text(encoding="utf-8")
    assert texte.startswith(revue.EN_TETE)
    assert texte.index("# Campagne c1") < texte.index("\n[[revue]]\n")
    assert "0 cas à revoir" in capsys.readouterr().out


def test_decisions_d_un_autre_fichier(poste: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Des décisions validées qui s'écartent de la pré-analyse scellée vont dans un autre fichier,
    # au chemin relatif à la racine du dépôt (uv lance le banc depuis banc/) : la pré-analyse garde
    # son sceau.
    monkeypatch.setattr(contre_epreuve, "RACINE", poste.parents[1])
    poser(poste, grille(1))
    preparer("c1")
    ecrire_json(poste / "preanalyse.json", [{"cas": "R1", "note": "juste"}])
    ecrire_json(poste / "decisions.json", [{"cas": "R1", "note": "partiel"}])
    options = ["--campagne", "c1", "--enregistrer", "revues/c1/decisions.json"]
    assert main(["contre-epreuve", *options]) == 0
    assert [d.note for d in revue.charger(revues_du_poste(poste)).decisions] == ["partiel"]


def test_preanalyse_incomplete_rien_d_enregistre(poste: Path) -> None:
    # Un cas non tranché arrête tout avant la première décision.
    poser(poste, grille(2))
    preparer("c1")
    ecrire_json(poste / "preanalyse.json", [{"cas": "R1", "note": "juste"}])
    assert main(["contre-epreuve", "--campagne", "c1", "--enregistrer"]) == 2
    assert not revues_du_poste(poste).exists()


def reprise(poste: Path, note_du_second: str) -> int:
    """Deux cas de même réponse courte, après le gel : le premier dans l'ordre de la revue n'a que
    sa note à revoir, le second sa note et sa source ; renvoie le code de l'enregistrement."""
    revues_du_poste(poste).parent.mkdir(parents=True)
    revues_du_poste(poste).write_text('gel = 2026-01-01T00:00:00\npilote = "pilote"\n')
    lignes = grille(0)
    for valeurs in lignes[:2]:
        valeurs["empreinte"] = EMPREINTE
    rangs = {revue.cle(valeurs): rang for rang, valeurs in enumerate(revue.melanger(lignes[:2]))}
    premier, second = sorted(lignes[:2], key=lambda valeurs: rangs[revue.cle(valeurs)])
    premier["note"] = A_REVOIR
    second |= {"note": A_REVOIR, "source": A_REVOIR}
    poser(poste, lignes)
    r = numeros(preparer("c1"))
    propositions = [
        {"cas": r[premier["cellule"], "Q1"], "note": "juste"},
        {"cas": r[second["cellule"], "Q1"], "note": note_du_second, "source": "oui"},
    ]
    ecrire_json(poste / "preanalyse.json", propositions)
    return main(["contre-epreuve", "--campagne", "c1", "--enregistrer"])


def test_note_reprise_pendant_l_enregistrement(poste: Path) -> None:
    # La décision du premier tranche la note du second (même réponse courte, après le gel) : seule
    # la source du second s'enregistre.
    assert reprise(poste, "juste") == 0
    decisions = revue.charger(revues_du_poste(poste)).decisions
    assert [(d.note, d.source) for d in decisions] == [("juste", None), (None, "oui")]


def test_note_contraire_a_la_reprise_refusee(
    poste: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # La pré-analyse proposait pour le second une autre note que celle qui le tranche déjà.
    assert reprise(poste, "partiel") == 2
    assert "déjà juste" in capsys.readouterr().err


def test_note_ecrite_une_fois(poste: Path) -> None:
    # Un enregistrement arrêté en route (le premier cas écrit, le second refusé), puis repris une
    # fois la décision corrigée, n'ajoute pas une seconde note.
    assert reprise(poste, "partiel") == 2
    propositions = json.loads((poste / "preanalyse.json").read_text(encoding="utf-8"))
    ecrire_json(poste / "preanalyse.json", [{**p, "note": "juste"} for p in propositions])
    assert main(["contre-epreuve", "--campagne", "c1", "--enregistrer"]) == 0
    lignes = revues_du_poste(poste).read_text(encoding="utf-8").splitlines()
    assert sum(ligne.startswith("# Campagne c1") for ligne in lignes) == 1
    assert lignes.count("[[revue]]") == 2


def renoter(poste: Path, lignes: Sequence[Mapping[str, str]]) -> None:
    """Le CSV de c1 réécrit, comme après une renotation."""
    csv = fichier_mesures("c1", poste.parents[1] / "mesures")
    csv.unlink()
    ecrire(csv, lignes)


def test_note_renotee_apres_le_tirage(poste: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Sa note, pré-notée au tirage, est à revoir depuis : la décision validée ne la tranche pas.
    # Rien ne s'écrit, pas même la note en tête des tables.
    lignes = grille(0)
    lignes[0]["source"] = A_REVOIR
    poser(poste, lignes)
    preparer("c1")
    ecrire_json(poste / "preanalyse.json", [{"cas": "R1", "source": "oui"}])
    lignes[0]["note"] = A_REVOIR
    renoter(poste, lignes)
    assert main(["contre-epreuve", "--campagne", "c1", "--enregistrer"]) == 2
    assert "note à trancher, la décision ne la tranche pas" in capsys.readouterr().err
    assert not revues_du_poste(poste).exists()


def test_cas_renote_apres_le_tirage(poste: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # Un cas devenu à revoir depuis le tirage n'a ni numéro ni décision validée.
    lignes = grille(0)
    lignes[0]["source"] = A_REVOIR
    poser(poste, lignes)
    preparer("c1")
    ecrire_json(poste / "preanalyse.json", [{"cas": "R1", "source": "oui"}])
    lignes[1]["note"] = A_REVOIR
    renoter(poste, lignes)
    assert main(["contre-epreuve", "--campagne", "c1", "--enregistrer"]) == 2
    assert "absent du tirage" in capsys.readouterr().err


# --- Commande ------------------------------------------------------------------------------------


def test_campagne_hors_du_dossier_des_revues(
    poste: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Un identifiant de campagne est un code : « ../revues/c1 » ne mène jamais aux pièces d'un
    # autre dossier, même quand elles s'y trouvent.
    poser(poste, grille(2))
    cles = preparer("c1")
    ecrire_json(poste / "preanalyse.json", [{"cas": r, "note": "juste"} for r in cles.cas])
    options = ["--campagne", "../revues/c1", "--accord", "1 j | 2 j"]
    assert main(["contre-epreuve", *options]) == 2
    assert "un code attendu" in capsys.readouterr().err


def test_commande_tirage(poste: Path, capsys: pytest.CaptureFixture[str]) -> None:
    poser(poste, grille(10))
    assert main(["contre-epreuve", "--campagne", "c1"]) == 0
    sortie = capsys.readouterr().out
    assert "8 cas tirés sur 10 à revoir" in sortie
    assert graine(fichier_mesures("c1", poste.parents[1] / "mesures")) in sortie


@pytest.mark.parametrize(
    "options",
    [
        pytest.param(["--campagne", "absente"], id="campagne-absente"),
        pytest.param(["--campagne", "../c1"], id="campagne-hors-du-dossier"),
        pytest.param(["--campagne", "../c1", "--accord", "1 j"], id="accord-hors-du-dossier"),
        pytest.param(["--campagne", "c1", "--accord", "1 j"], id="accord-sans-tirage"),
        pytest.param(["--campagne", "c1", "--enregistrer"], id="enregistrement-sans-tirage"),
    ],
)
def test_commande_en_erreur(
    poste: Path, capsys: pytest.CaptureFixture[str], options: list[str]
) -> None:
    assert main(["contre-epreuve", *options]) == 2
    assert "banc contre-epreuve :" in capsys.readouterr().err
