"""Revue humaine à l'aveugle (T3.2 ; plan 002, D4) : cas à revoir, décisions datées dans
revues.toml, note réutilisée par réponse courte normalisée après le gel, présentation sans rien qui
trahisse la cellule, saisie au clavier, `banc revoir`. Ni base ni LLM : des lignes de mesure et des
tours écrits à la main.
"""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import pytest

from banc import revue
from banc.__main__ import main
from banc.mesures import COLONNES, Entete, Journal, TourMesure, commit_pokeapi, ecrire
from banc.revue import (
    SANS_REUTILISATION,
    Console,
    Decision,
    Finale,
    RevueError,
    Revues,
    ajouter,
    charger,
    cle,
    en_attente,
    finale,
    melanger,
    presenter,
    reference,
    regles,
    retenues,
    revoir,
    traces,
    verifier,
)
from banc.trace import Appel

GEL = datetime(2026, 10, 20, 10, 0)
AVANT = datetime(2026, 10, 19, 18, 0)
APRES = datetime(2026, 10, 21, 9, 30)
EMPREINTE = "0123456789abcdef"
REPONSE = "Je suis Gemini, et voici.\n\nRéponse : Aquali, Voltali\n\nSources : `MATCH (e)`"
REQUETE = "MATCH (e:Pokemon)\nRETURN e.nom AS nom"
LECTURE = Appel("read-cypher", REQUETE, {}, '[{"nom": "Aquali"}]', False)


def ligne_csv(question: str = "Q5", **champs: object) -> dict[str, str]:
    """Une ligne du CSV d'une campagne (banc.mesures), avec ce qui trahirait la cellule ; champs :
    les colonnes à changer."""
    valeurs = dict.fromkeys(COLONNES, "")
    valeurs |= {
        "campagne": "c1",
        "cellule": "adk-gemini",
        "passe": "1",
        "question": question,
        "essai": "1",
        "issue": "reponse",
        "note": "à revoir",
        "source": "oui",
        "motifs": "distracteur",
        "empreinte": EMPREINTE,
        "modele": "gemini-3.8-flash",
        "duree_s": "12.34",
        "cout_usd": "0.004321",
        "effort": "HIGH",
    }
    return valeurs | {colonne: str(valeur) for colonne, valeur in champs.items()}


def decision(question: str = "Q5", **champs: Any) -> Decision:
    """La décision du cas de ligne_csv(question) : note juste, après le gel ; champs : à changer."""
    valeurs: dict[str, Any] = {"campagne": "c1", "cellule": "adk-gemini", "passe": 1}
    valeurs |= {"question": question, "essai": 1, "empreinte": EMPREINTE, "date": APRES}
    return Decision(**valeurs | {"note": "juste"} | champs)


def tour(question: str = "Q5", reponse: str = REPONSE) -> TourMesure:
    message = f"Question {question} telle que posée ?"
    return TourMesure(question, message, (LECTURE,), reponse=reponse, issue="reponse", duree_s=1.0)


# --- Cas à revoir --------------------------------------------------------------------------------


def test_cas_a_revoir() -> None:
    # Une note ou une source « à revoir » ; le reste est déjà tranché par la pré-notation.
    lignes = [
        ligne_csv("Q5"),
        ligne_csv("Q6", note="juste", source="à revoir"),
        ligne_csv("Q19", note="juste"),
        ligne_csv("Q21", note="faux", source="non"),
    ]
    assert [ligne["question"] for ligne in en_attente(lignes, Revues())] == ["Q5", "Q6"]


def test_dernier_essai_seul_compte() -> None:
    # Une paire relancée après une panne : seul le dernier essai de chaque question compte.
    lignes = [
        ligne_csv("Q2", essai=1),
        ligne_csv("Q18", essai=1, issue="panne", note="", source=""),
        ligne_csv("Q2", essai=2, note="juste"),
        ligne_csv("Q18", essai=2),
    ]
    assert [(ligne["question"], ligne["essai"]) for ligne in retenues(lignes)] == [
        ("Q2", "2"),
        ("Q18", "2"),
    ]
    assert en_attente(lignes, Revues()) == [lignes[3]]


@pytest.mark.parametrize(
    "premier",
    [
        pytest.param({"issue": "echec", "note": "faux", "source": "non"}, id="apres-un-echec"),
        pytest.param({"note": "juste"}, id="apres-une-reponse"),
    ],
)
def test_essai_remplace_sans_panne(premier: dict[str, str]) -> None:
    # D13 : un échec compte faux et ne se relance jamais ; seule une panne ou un arrêt de la
    # conversation (la paire pour Q18 et Q28) justifie un essai suivant.
    with pytest.raises(RevueError, match="sans panne"):
        retenues([ligne_csv("Q5", essai=1, **premier), ligne_csv("Q5", essai=2, note="juste")])


def test_doublon_d_un_essai_ancien() -> None:
    panne = ligne_csv("Q5", essai=1, issue="panne", note="", source="")
    with pytest.raises(RevueError, match="double"):
        retenues([panne, ligne_csv("Q5", essai=2), panne])


def test_ligne_en_double() -> None:
    with pytest.raises(RevueError, match="double"):
        retenues([ligne_csv("Q5"), ligne_csv("Q5", note="juste")])


def test_echec_et_panne_hors_revue() -> None:
    # Un échec compte faux d'office (D13) ; une panne se relance.
    lignes = [
        ligne_csv("Q5", issue="echec", note="faux", source="non"),
        ligne_csv("Q6", issue="panne", note="", source=""),
    ]
    assert en_attente(lignes, Revues()) == []


def test_decision_du_cas() -> None:
    revues = Revues(decisions=(decision(note="partiel", motif="forme-signalee"),))
    assert finale(ligne_csv(), revues) == Finale("partiel", "oui", "revue", "forme-signalee")
    assert en_attente([ligne_csv()], revues) == []


def test_note_reutilisee_apres_le_gel() -> None:
    # Même question, même réponse courte normalisée, décision prise après le gel : note reprise.
    revues = Revues(GEL, (decision(cellule="claude-code", motif="valeur-exacte"),))
    assert finale(ligne_csv(), revues) == Finale("juste", "oui", "reutilisee", "valeur-exacte")
    assert en_attente([ligne_csv()], revues) == []


def test_decision_datee_du_gel() -> None:
    # « À partir du gel » : une décision prise à l'heure même du gel se réutilise.
    revues = Revues(GEL, (decision(cellule="claude-code", date=GEL),))
    assert en_attente([ligne_csv()], revues) == []


def test_decision_sans_note_jamais_reutilisee() -> None:
    # Une décision qui n'a tranché que la source d'un autre cas ne dit rien de cette note.
    revues = Revues(GEL, (decision(cellule="claude-code", note=None, source="oui"),))
    assert finale(ligne_csv(), revues) == Finale("à revoir", "oui", "pre-note", "")


@pytest.mark.parametrize(("gel", "quand"), [(None, APRES), (GEL, AVANT)], ids=["sans-gel", "avant"])
def test_rien_d_herite_d_avant_le_gel(gel: datetime | None, quand: datetime) -> None:
    # Le pilote précède le gel : aucune de ses décisions ne passe aux passes comptées.
    revues = Revues(gel, (decision(cellule="claude-code", date=quand),))
    assert en_attente([ligne_csv()], revues) == [ligne_csv()]


def test_questions_sans_reutilisation() -> None:
    # Plan, D4 ; Q10, Q14, Q15 et Q30 ajoutées par Julien le 2026-10-08 : culture générale, formes
    # ou critère signalés, hors de la réponse courte.
    # Puis Q4 et Q19, après la revue adverse (talent ou type d'une méga-forme, accepté s'il est
    # signalé), choix de Julien du 2026-10-08.
    attendues = {"Q4", "Q7", "Q10", "Q11", "Q12", "Q13", "Q14", "Q15", "Q19"}
    attendues |= {"Q27", "Q28", "Q29", "Q30"}
    assert attendues == SANS_REUTILISATION


@pytest.mark.parametrize("question", sorted(SANS_REUTILISATION))
def test_jamais_reutilisee_quand_la_regle_depasse_la_reponse_courte(question: str) -> None:
    revues = Revues(GEL, (decision(question, cellule="claude-code"),))
    assert en_attente([ligne_csv(question)], revues) == [ligne_csv(question)]


def test_source_jamais_reutilisee() -> None:
    # La source dépend de la trace du tour, pas de la réponse courte.
    revues = Revues(GEL, (decision(cellule="claude-code", source="oui"),))
    autre = ligne_csv(source="à revoir")
    assert finale(autre, revues) == Finale("juste", "à revoir", "reutilisee", "")
    assert en_attente([autre], revues) == [autre]


def test_sans_reponse_courte_rien_a_reutiliser() -> None:
    revues = Revues(GEL, (decision(cellule="claude-code", empreinte=""),))
    sans = ligne_csv(empreinte="")
    assert en_attente([sans], revues) == [sans]


def test_source_pre_notee_gardee() -> None:
    # Après une renotation, une source décidée sur le cas ne remplace pas une source pré-notée.
    revues = Revues(decisions=(decision(note=None, source="oui"),))
    assert finale(ligne_csv(note="juste", source="non"), revues) == Finale(
        "juste", "non", "pre-note", ""
    )


def test_rien_d_herite_du_pilote() -> None:
    # Une décision du pilote ne se réutilise jamais, même datée après le gel (plan, D4).
    du_pilote = Decision("pilote", "claude-code", 1, "Q5", 1, EMPREINTE, APRES, "juste")
    revues = Revues(GEL, (du_pilote,), pilote="pilote")
    assert en_attente([ligne_csv()], revues) == [ligne_csv()]


def test_pre_note_gardee() -> None:
    # La revue ne tranche que ce qui est « à revoir » : une note pré-notée ne change pas.
    revues = Revues(GEL, (decision(cellule="claude-code", note="faux"),))
    assert finale(ligne_csv(note="juste"), revues) == Finale("juste", "oui", "pre-note", "")


def test_decisions_contradictoires() -> None:
    contraires = (decision(cellule="claude-code"), decision(cellule="adk-claude", note="faux"))
    with pytest.raises(RevueError, match="contradictoires"):
        Revues(GEL, contraires)


def test_une_decision_par_cas() -> None:
    with pytest.raises(RevueError, match="deux décisions"):
        Revues(None, (decision(), decision(note="faux")))


# --- revues.toml ---------------------------------------------------------------------------------


def test_decisions_ajoutees_puis_relues(tmp_path: Path) -> None:
    fichier = tmp_path / "revues.toml"
    premiere = decision(note="partiel", motif="forme-signalee")
    seconde = decision("Q30", note=None, source="exempte")
    ajouter(fichier, premiere)
    ajouter(fichier, seconde)
    assert charger(fichier) == Revues(None, (premiere, seconde))
    # En-tête commenté à la création, une seule fois : le gel s'inscrit en haut, avant toute table.
    assert fichier.read_text().startswith("# ")
    assert fichier.read_text().count("# Décisions de la revue") == 1


def test_gel_relu(tmp_path: Path) -> None:
    fichier = tmp_path / "revues.toml"
    fichier.write_text('gel = 2026-10-20T10:00:00\npilote = "pilote"\n')
    ajouter(fichier, decision())
    assert charger(fichier) == Revues(GEL, (decision(),), "pilote")


def test_aucune_revue(tmp_path: Path) -> None:
    assert charger(tmp_path / "absent.toml") == Revues()


@pytest.mark.parametrize(
    "contenu",
    [
        pytest.param("[[revue]]\nnote = \n", id="toml-invalide"),
        pytest.param('gel = "demain"\npilote = "pilote"\n', id="gel-en-texte"),
        pytest.param('gel = 2026-10-20\npilote = "pilote"\n', id="gel-sans-heure"),
        pytest.param('[[revue]]\ncampagne = "c1"\n', id="decision-incomplete"),
        pytest.param('autre = "x"\n', id="cle-inconnue"),
        pytest.param('gel = 2026-10-20T10:00:00+02:00\npilote = "pilote"\n', id="gel-avec-fuseau"),
        pytest.param("gel = 2026-10-20T10:00:00\n", id="gel-sans-pilote"),
        pytest.param('pilote = "Pilote 1"\n', id="pilote-en-prose"),
    ],
)
def test_fichier_refuse(tmp_path: Path, contenu: str) -> None:
    fichier = tmp_path / "revues.toml"
    fichier.write_text(contenu)
    with pytest.raises(RevueError):
        charger(fichier)


@pytest.mark.parametrize(
    "champs",
    [
        pytest.param({"note": "excellent"}, id="note"),
        pytest.param({"source": "peut-être"}, id="source"),
        pytest.param({"note": None, "source": None}, id="rien-de-tranche"),
        pytest.param({"motif": "forme signalée"}, id="motif-en-prose"),
        pytest.param({"motif": "o"}, id="motif-d-une-lettre"),
        pytest.param({"question": "q5"}, id="question"),
        pytest.param({"cellule": "Claude Code"}, id="cellule"),
        pytest.param({"campagne": "../c1"}, id="campagne"),
        pytest.param({"passe": 0}, id="passe"),
        pytest.param({"essai": 0}, id="essai"),
        pytest.param({"empreinte": "zz"}, id="empreinte"),
        pytest.param({"date": datetime(2026, 10, 21, 9, 30, tzinfo=UTC)}, id="date-avec-fuseau"),
        pytest.param({"date": date(2026, 10, 21)}, id="date-sans-heure"),
    ],
)
def test_decision_refusee(champs: dict[str, Any]) -> None:
    with pytest.raises(RevueError):
        Decision(**{**decision().__dict__, **champs})


# --- Présentation à l'aveugle --------------------------------------------------------------------


def test_presentation_a_l_aveugle() -> None:
    # Ni cellule, ni modèle, ni passe, ni essai, ni durée, ni coût ; les noms de modèles que
    # l'agent écrit lui-même sont masqués.
    texte = presenter(ligne_csv(passe=2, essai=3), tour(), None, "REF")
    for indice in ("adk-gemini", "gemini-3.8-flash", "HIGH", "12.34", "0.004321", "passe", "essai"):
        assert indice not in texte, indice
    assert "Gemini" not in texte
    assert "Je suis ‹modèle›, et voici." in texte


def test_presentation_complete() -> None:
    texte = presenter(ligne_csv(motifs="distracteur+forme"), tour(), None, "RÉFÉRENCE")
    for attendu in ("Question Q5 telle que posée ?", "RÉFÉRENCE", "Réponse : Aquali, Voltali"):
        assert attendu in texte
    assert "note à revoir" in texte
    assert "distracteur, forme" in texte


def test_second_tour_avec_le_precedent() -> None:
    # Q18 se juge sur l'équipe proposée à Q2, dans la même conversation.
    q2 = tour("Q2", "Réponse : Lokhlass, Florizarre (proposée par Gemini)")
    texte = presenter(ligne_csv("Q18"), tour("Q18"), q2, "REF")
    assert "Question Q2 telle que posée ?" in texte
    assert "Réponse : Lokhlass, Florizarre (proposée par ‹modèle›)" in texte


@pytest.mark.parametrize(("source", "montrees"), [("à revoir", True), ("oui", False)])
def test_lectures_du_tour_precedent(source: str, montrees: bool) -> None:
    # ADR-0015 : la source d'un second tour peut venir du tour précédent, ses lectures se montrent.
    q27 = TourMesure("Q27", "?", (LECTURE,), reponse="Électacle", issue="reponse", duree_s=1.0)
    texte = presenter(ligne_csv("Q28", source=source), tour("Q28"), q27, "REF")
    assert ("Lectures du tour précédent :" in texte) is montrees
    assert texte.count("RETURN e.nom AS nom") == (2 if montrees else 0)


@pytest.mark.parametrize(("source", "montrees"), [("à revoir", True), ("oui", False)])
def test_lectures_si_la_source_est_a_revoir(source: str, montrees: bool) -> None:
    texte = presenter(ligne_csv(source=source), tour(), None, "REF")
    assert ("RETURN e.nom AS nom" in texte) is montrees
    assert ('[{"nom": "Aquali"}]' in texte) is montrees


def test_resultat_long_tronque() -> None:
    longue = Appel("read-cypher", REQUETE, {}, "x" * 5_000, True)
    avec = TourMesure("Q5", "?", (longue,), reponse=REPONSE, issue="reponse", duree_s=1.0)
    texte = presenter(ligne_csv(source="à revoir"), avec, None, "REF")
    assert "x" * 5_000 not in texte
    assert "(+3500 caractères)" in texte
    assert "en erreur" in texte


# --- Référence : réponse attendue et règles du README --------------------------------------------


def test_regles_du_readme() -> None:
    q12 = regles("Q12")
    assert any(regle.startswith("- **Q12** : Leuphorie") for regle in q12)
    # La règle générale qui cite Q12 entre parenthèses compte aussi.
    assert any(regle.startswith("- **« Pokémon » = espèce**") for regle in q12)
    # Une puce entière, sous-puces comprises ; Q1 ne désigne pas Q12.
    assert any("**Correction sur preuve**" in regle for regle in regles("Q3"))
    assert not any("**Q12**" in regle for regle in regles("Q1"))
    assert regles("Q21") == ()


def test_reference_d_une_question() -> None:
    texte = reference("Q12")
    assert "questions/attendu/q12.txt" in texte
    assert '"Leuphorie", "Leuphorie", TRUE, 255' in texte
    assert "- **Q12** : Leuphorie" in texte
    assert "// PokéAPI" not in texte


def test_regles_de_leur_seule_section(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Banc\n\n- Q5 hors des règles\n\n## Règles de réponse\n\n- **Q5** : la règle\n"
        "  - sa sous-puce\n\n- **Q50** : une autre\n\n## Critères\n\n- Q5 ailleurs\n"
    )
    assert regles("Q5", readme) == ("- **Q5** : la règle\n  - sa sous-puce",)


def test_reference_sans_requete() -> None:
    # Q10, Q29 et Q30 : pas de requête de référence, la règle du README fait foi.
    texte = reference("Q10")
    assert "aucune requête de référence" in texte
    assert "- **Q10, Q29, Q30**" in texte


# --- Traces d'une campagne -----------------------------------------------------------------------


def test_traces_d_une_campagne(tmp_path: Path) -> None:
    entete = Entete(
        campagne="c1",
        cellule="claude-code",
        passe=1,
        essai=2,
        questions=("Q2", "Q18"),
        modele="claude-sonnet-5-5",
        acces="api",
        jour=date(2026, 10, 21),
        effort="high",
        versions={},
        commit_pokeapi=commit_pokeapi(),
    )
    with Journal(tmp_path / "c1" / "conversation.jsonl", entete) as journal:
        for question in entete.questions:
            journal.question(question, f"{question} ?")
            journal.fin("reponse", reponse=f"Réponse : {question}")
    index = traces(tmp_path / "c1")
    q18, precedent = index["c1", "claude-code", 1, "Q18", 2]
    assert (q18.reponse, precedent.question if precedent else None) == ("Réponse : Q18", "Q2")
    assert index["c1", "claude-code", 1, "Q2", 2][1] is None


# --- Saisie au clavier ---------------------------------------------------------------------------


class Clavier:
    """Saisies successives ; EOFError une fois épuisées (Ctrl-D)."""

    def __init__(self, *saisies: str) -> None:
        self.saisies = list(saisies)
        self.invites: list[str] = []

    def __call__(self, invite: str) -> str:
        self.invites.append(invite)
        if not self.saisies:
            raise EOFError
        return self.saisies.pop(0)


def lancer(
    tmp_path: Path, lignes: list[dict[str, str]], *saisies: str, gel: datetime | None = None
) -> tuple[int, list[str], Revues, Clavier]:
    """Revue de ces lignes, dans leur ordre, avec ces saisies ; renvoie le code, les sorties, les
    décisions enregistrées et le clavier."""
    fichier = tmp_path / "revues.toml"
    if gel is not None:
        fichier.write_text(f'gel = {gel.isoformat()}\npilote = "pilote"\n')
    index: Mapping[revue.Cle, tuple[TourMesure, TourMesure | None]] = {
        cle(ligne): (tour(ligne["question"]), None) for ligne in lignes
    }
    clavier, sorties = Clavier(*saisies), list[str]()
    console = Console(clavier, sorties.append, lambda: APRES)
    code = revoir(lignes, index, fichier, console, list)
    return code, sorties, charger(fichier), clavier


def test_revue_au_clavier(tmp_path: Path) -> None:
    lignes = [
        ligne_csv("Q5"),
        ligne_csv("Q6", note="juste", source="à revoir"),
        ligne_csv("Q27", source="à revoir"),
    ]
    code, sorties, revues, _ = lancer(tmp_path, lignes, "j", "n", "f o premisse-acceptee")
    assert code == 0
    assert revues.decisions == (
        decision("Q5"),
        decision("Q6", note=None, source="non"),
        decision("Q27", note="faux", source="oui", motif="premisse-acceptee"),
    )
    assert "3 décisions enregistrées ; 0 cas restant" in sorties[-1]


@pytest.mark.parametrize(
    "erronee",
    [
        pytest.param("x", id="lettre-inconnue"),
        pytest.param("", id="vide"),
        pytest.param("o", id="source-au-lieu-de-la-note"),
        pytest.param("j forme signalee", id="motif-en-prose"),
        pytest.param("j o", id="motif-d-une-lettre"),
    ],
)
def test_saisie_invalide_redemandee(tmp_path: Path, erronee: str) -> None:
    _, sorties, revues, clavier = lancer(tmp_path, [ligne_csv()], erronee, "j")
    assert revues.decisions == (decision(),)
    assert len(clavier.invites) == 2
    assert any("Saisie invalide" in sortie for sortie in sorties)


def test_sauter_puis_quitter(tmp_path: Path) -> None:
    lignes = [ligne_csv("Q5"), ligne_csv("Q6"), ligne_csv("Q19")]
    code, sorties, revues, _ = lancer(tmp_path, lignes, "s", "p", "q")
    assert code == 0
    assert revues.decisions == (decision("Q6", note="partiel"),)
    assert "1 décision enregistrée ; 2 cas restants" in sorties[-1]


def test_fin_de_saisie(tmp_path: Path) -> None:
    # Ctrl-D arrête la revue comme « q » : les décisions déjà prises restent.
    lignes = [ligne_csv("Q5"), ligne_csv("Q6"), ligne_csv("Q19")]
    code, sorties, revues, clavier = lancer(tmp_path, lignes, "j")
    assert (code, len(revues.decisions), len(clavier.invites)) == (0, 1, 2)
    assert "2 cas restants" in sorties[-1]


def test_reutilisee_pendant_la_revue(tmp_path: Path) -> None:
    # Après le gel, la décision du premier cas tranche aussitôt le second, qui n'est pas montré.
    lignes = [ligne_csv(cellule="claude-code"), ligne_csv(cellule="adk-gemini")]
    _, _, revues, clavier = lancer(tmp_path, lignes, "j", gel=GEL)
    assert (len(revues.decisions), len(clavier.invites)) == (1, 1)
    assert en_attente(lignes, revues) == []


def test_cas_deja_tranche_en_partie(tmp_path: Path) -> None:
    # Sa source tranchée, puis sa note devenue « à revoir » après une renotation : une seconde
    # décision pour le même cas rendrait revues.toml illisible ; la revue renvoie au fichier.
    fichier = tmp_path / "revues.toml"
    ajouter(fichier, decision(note=None, source="oui"))
    avant = fichier.read_text()
    _, sorties, _, clavier = lancer(tmp_path, [ligne_csv()], "j")
    assert (fichier.read_text(), clavier.invites) == (avant, [])
    assert any("à compléter à la main" in sortie for sortie in sorties)
    assert "0 décision enregistrée ; 1 cas restant" in sorties[-1]


def test_trace_manquante(tmp_path: Path) -> None:
    with pytest.raises(RevueError, match="trace"):
        revoir([ligne_csv()], {}, tmp_path / "revues.toml", Console(Clavier("j")))


def test_ordre_melange_mais_stable() -> None:
    # Les cellules alternent question par question dans le CSV : l'ordre de la revue n'en laisse
    # rien deviner, et reste le même pour reprendre une revue interrompue.
    cas = [
        ligne_csv(f"Q{n}", cellule=c) for n in range(1, 7) for c in ("claude-code", "adk-gemini")
    ]
    melange = melanger(cas)
    assert sorted(map(cle, melange)) == sorted(map(cle, cas))
    assert melange != cas
    cellules = [ligne["cellule"] for ligne in melange]
    assert cellules not in (sorted(cellules), sorted(cellules, reverse=True))
    reste = cas[3:]
    assert melanger(reste) == [ligne for ligne in melange if ligne in reste]


# --- Vérification et commande --------------------------------------------------------------------


def test_verifier() -> None:
    sorties: list[str] = []
    assert verifier([ligne_csv("Q5"), ligne_csv("Q6", note="juste")], Revues(), sorties.append) == 1
    assert sorties == ["1 cas à revoir (Q5)"]
    assert verifier([ligne_csv("Q6", note="juste")], Revues(), sorties.append) == 0


def test_verifier_tours_a_relancer() -> None:
    # Une panne pas encore relancée : rien à revoir pour l'instant, mais pas fini non plus.
    sorties: list[str] = []
    panne = ligne_csv("Q6", issue="panne", note="", source="")
    assert verifier([ligne_csv("Q5", note="juste"), panne], Revues(), sorties.append) == 1
    assert sorties == ["0 cas à revoir ; 1 tour à relancer (Q6)"]


def test_commande_verifier(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(revue, "MESURES", tmp_path)
    ecrire(tmp_path / "c1.csv", [ligne_csv("Q5")])
    assert main(["revoir", "--campagne", "c1", "--verifier"]) == 1
    assert "1 cas à revoir" in capsys.readouterr().out
    ajouter(tmp_path / "revues.toml", decision("Q5"))
    assert main(["revoir", "--campagne", "c1", "--verifier"]) == 0


@pytest.mark.parametrize("campagne", ["absente", "../c1"])
def test_commande_en_erreur(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    campagne: str,
) -> None:
    monkeypatch.setattr(revue, "MESURES", tmp_path)
    assert main(["revoir", "--campagne", campagne, "--verifier"]) == 2
    assert "banc revoir" in capsys.readouterr().err


def test_commande_revue_sans_cas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Sans --verifier, la revue au clavier : rien à revoir, rien à demander.
    monkeypatch.setattr(revue, "MESURES", tmp_path)
    ecrire(tmp_path / "c1.csv", [ligne_csv("Q5", note="juste")])
    assert main(["revoir", "--campagne", "c1"]) == 0
    assert "0 décision enregistrée ; 0 cas restant" in capsys.readouterr().out


def test_horloge_des_decisions() -> None:
    # Une décision se date à la seconde (l'horloge murale suffit : on ne chronomètre rien).
    assert Console().maintenant().microsecond == 0


@pytest.mark.parametrize(
    "designation",
    [
        "Claude Code",
        "Claude Sonnet 5.5",
        "Sonnet 5.5",
        "Haiku 4.5",
        "Gemini 3.8 Flash",
        "Google DeepMind",
        "Vertex AI",
        "ADK",
        "Anthropic",
        "Agent SDK",
        "claude-sonnet-5-5",
        "gemini-3.8-flash",
    ],
)
def test_designations_masquees(designation: str) -> None:
    texte = presenter(
        ligne_csv(), tour("Q5", f"Réponse : je suis {designation}, pas toi."), None, "R"
    )
    assert "Réponse : je suis ‹modèle›, pas toi." in texte


def test_attaque_flash_gardee() -> None:
    texte = presenter(ligne_csv(), tour("Q5", "Réponse : l'attaque Flash."), None, "REF")
    assert "Réponse : l'attaque Flash." in texte


def test_lectures_masquees() -> None:
    lecture = Appel("read-cypher", "// requête de Claude\nMATCH (n) RETURN n", {}, "[]", False)
    avec = TourMesure("Q5", "?", (lecture,), reponse=REPONSE, issue="reponse", duree_s=1.0)
    texte = presenter(ligne_csv(source="à revoir"), avec, None, "REF")
    assert "// requête de ‹modèle›" in texte
