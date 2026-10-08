"""Pré-notation des réponses (T2.2) : modes de banc.toml, distracteurs, longues listes, tables de
l'ADR-0008, contrôle de Q2, source citée vérifiée sur la trace du tour, introspections comptées.

Aucun appel réel : des tours fabriqués (banc.trace) et un faux contrôle de Q2.
"""

import json
import sys
from pathlib import Path

import pytest

from banc import attendu
from banc.lecture import liste_cypher
from banc.notation import (
    Controle,
    NotationError,
    Referentiel,
    controle_par_script,
    introspections,
    noter,
)
from banc.questions import Question, charger
from banc.trace import Appel, Tour

BANC = charger()
REF = Referentiel.charger(BANC)
Q = BANC.questions


def ecrire(court: str, sources: str = "") -> str:
    """Une réponse au format de la consigne : un raisonnement, puis « Réponse » et « Sources »."""
    fin = f"\n\n**Sources :**\n{sources}" if sources else ""
    return f"J'interroge le graphe.\n\n**Réponse :** {court}{fin}"


def noter_texte(ident: str, court: str, *appels: Appel, sources: str = "") -> str:
    return noter(Q[ident], Tour(ident, ecrire(court, sources), appels), REF).note


def lecture(requete: str, lignes: object, *, erreur: bool = False) -> Appel:
    """Un appel à read-cypher et son résultat, tel que neo4j-mcp le renvoie (JSON indenté)."""
    resultat = lignes if isinstance(lignes, str) else json.dumps(lignes, indent=2)
    return Appel("read-cypher", requete, {}, resultat, erreur)


# --- Réponse idéale : chaque question notée juste -----------------------------------------------


def ideale(question: Question) -> str:
    """Réponse courte idéale, tirée de banc.toml et de attendu/ (les espèces par leur nom exact)."""
    if question.notation in {"valeur", "ensemble", "liste-ordonnee"}:
        return ", ".join(str(v) for v in (*question.attendus, *question.un_parmi[:1]))
    if question.notation == "longue-liste":
        return ", ".join(sorted(REF.listes[question.id]))
    table = REF.tables[question.id]
    if not question.pluriel:
        return min(table.obligatoires)
    if question.avec_types:
        return ", ".join(f"{n} ({', '.join(table.types[n])})" for n in sorted(table.obligatoires))
    return ", ".join(sorted(table.obligatoires))


AUTOMATIQUES = [q for q in Q.values() if q.notation not in {"revue", "controle"}]


@pytest.mark.parametrize("question", AUTOMATIQUES, ids=lambda q: q.id)
def test_reponse_ideale_juste(question: Question) -> None:
    notation = noter(question, Tour(question.id, ecrire(ideale(question))), REF)
    assert notation.note == "juste", notation


def test_referentiel_tire_de_attendu() -> None:
    assert len(REF.listes["Q7"]) == 71
    assert len(REF.listes["Q14"]) == 55
    assert set(REF.tables) == {"Q3", "Q9", "Q16", "Q17", "Q26"}
    assert REF.tables["Q16"].obligatoires == {"Dracolosse"}
    assert REF.tables["Q9"].types["Lugia"] == ("Psy", "Vol")
    assert "Arcanin" in REF.tables["Q16"].ecartes


# --- Valeur et ensemble --------------------------------------------------------------------------


def test_valeur_absente_fausse() -> None:
    assert noter_texte("Q12", "Leveinard") == "faux"


def test_nombre_compare_comme_un_nombre() -> None:
    # Q24 attend 100 : « 1000 » ne le contient pas, « 100,0 » si.
    assert noter_texte("Q24", "Sol, 1000, physique") == "partiel"
    assert noter_texte("Q24", "Sol, 100,0, physique") == "juste"


def test_ensemble_partiel_et_faux() -> None:
    assert noter_texte("Q4", "Combat et Acier ; Impassible") == "partiel"
    assert noter_texte("Q4", "Normal") == "faux"


def test_distracteur_a_revoir() -> None:
    # Une réponse comparative cite l'autre Pokémon (plan, D4).
    notation = noter(Q["Q21"], Tour("Q21", ecrire("Dracaufeu, plus rapide que Tortank.")), REF)
    assert notation.note == "à revoir"
    assert notation.motifs == ("distracteur",)


def test_distracteur_dans_un_nom_de_forme() -> None:
    assert noter_texte("Q15", "Pichu, Pikachu, Raichu (et Raichu d'Alola)") == "à revoir"


def test_un_parmi() -> None:
    # Q27 : une attaque Électrik du groupe suffit, avec la raison (Tortank est de type Eau).
    assert noter_texte("Q27", "Tonnerre : Tortank est de type Eau.") == "juste"
    assert noter_texte("Q27", "Fatal-Foudre, puis Électacle ; type Eau.") == "juste"


@pytest.mark.parametrize(
    "court",
    [
        pytest.param("Nœud Herbe : Tortank est de type Eau.", id="autre-attaque"),
        pytest.param("Tonnerre, l'attaque la plus sûre.", id="sans-raison"),
        pytest.param("Charge.", id="rien"),
    ],
)
def test_revoir_si_incomplete(court: str) -> None:
    # Q27 : une autre attaque, expliquée, peut être juste : à revoir plutôt que partielle ou fausse.
    notation = noter(Q["Q27"], Tour("Q27", ecrire(court)), REF)
    assert notation.note == "à revoir"
    assert "incomplete" in notation.motifs


def test_piege_de_q28() -> None:
    assert noter_texte("Q28", "Surf : l'Électrik est sans effet sur Onix.") == "juste"
    assert noter_texte("Q28", "Surf, ou Tonnerre malgré l'Électrik sans effet.") == "à revoir"


# --- Liste ordonnée (Q8) -------------------------------------------------------------------------

Q8 = ("Drattak", "Dracolosse", "Reshiram", "Libégon", "Groudon")


@pytest.mark.parametrize(
    "ordre",
    [
        pytest.param(Q8, id="exact"),
        pytest.param(
            ("Drattak", "Dracolosse", "Libégon", "Reshiram", "Groudon"), id="echange-proche"
        ),
        pytest.param(
            ("Drattak", "Dracolosse", "Reshiram", "Libégon", "Braségali"), id="brasegali-5e"
        ),
        pytest.param((*Q8[:4], "Typhlosion"), id="typhlosion-5e"),
        pytest.param((*Q8, "Braségali", "Typhlosion"), id="au-dela-du-5e"),
    ],
)
def test_liste_ordonnee_juste(ordre: tuple[str, ...]) -> None:
    # Tolérance de 0,01 sur l'ordre (README) ; Dracaufeu, sujet de la question, ne compte pas.
    assert noter_texte("Q8", "Pour Dracaufeu : " + ", ".join(ordre)) == "juste"


def test_liste_ordonnee_hors_tolerance() -> None:
    # Reshiram (0,490) contre Dracolosse (0,517) : 0,027 d'écart, au-delà de la tolérance.
    assert noter_texte("Q8", "Drattak, Reshiram, Dracolosse, Libégon, Groudon") == "partiel"
    assert noter_texte("Q8", "Drattak, Dracolosse, Reshiram") == "partiel"
    # « À moins de 0,01 » (README) : Braségali (0,480) à la place de Reshiram (0,490), pile 0,01.
    assert noter_texte("Q8", "Drattak, Dracolosse, Braségali, Libégon, Groudon") == "partiel"
    assert noter_texte("Q8", "Drattak, Dracolosse, Reshiram, Libégon, Ptéra") == "partiel"
    assert noter_texte("Q8", "Ptéra, Steelix") == "faux"


def test_liste_ordonnee_famille_non_exclue() -> None:
    assert noter_texte("Q8", "Salamèche, Reptincel, Drattak, Dracolosse, Reshiram") == "à revoir"


# --- Longues listes (Q7, Q14) --------------------------------------------------------------------


def test_longue_liste_compte_et_extrait() -> None:
    assert noter_texte("Q7", "71 espèces, dont Onix, Steelix et Groudon.") == "juste"


def test_longue_liste_extrait_seul() -> None:
    assert noter_texte("Q7", "Onix, Steelix, Groudon…") == "partiel"
    assert noter_texte("Q7", "70 espèces, dont Onix.") == "partiel"


def test_longue_liste_compte_seul() -> None:
    notation = noter(Q["Q7"], Tour("Q7", ecrire("71 espèces.")), REF)
    assert (notation.note, notation.motifs) == ("à revoir", ("compte-seul",))


def test_longue_liste_intrus() -> None:
    # Pikachu apprend Séisme ? non, et il craint le Sol : intrus, à revoir.
    notation = noter(Q["Q7"], Tour("Q7", ecrire("71 espèces, dont Onix et Pikachu.")), REF)
    assert (notation.note, notation.motifs) == ("à revoir", ("hors-ensemble",))


def test_longue_liste_distracteur() -> None:
    notation = noter(Q["Q7"], Tour("Q7", ecrire("Onix, Steelix et Élekable (Motorisé).")), REF)
    assert (notation.note, notation.motifs) == ("à revoir", ("distracteur",))


def test_longue_liste_vide() -> None:
    assert noter_texte("Q14", "Aucun Pokémon de type Feu.") == "faux"


def test_longue_liste_complete_sans_compte() -> None:
    # Q14 : la liste complète suffit, même avec un compte faux.
    assert noter_texte("Q14", "56 espèces : " + ", ".join(sorted(REF.listes["Q14"]))) == "juste"


# --- Questions sémantiques (ADR-0008) ------------------------------------------------------------


@pytest.mark.parametrize(
    ("court", "note"),
    [
        pytest.param("Magmar.", "juste", id="obligatoire"),
        pytest.param("Entei.", "juste", id="acceptable"),
        pytest.param("Magmar et Chamallot.", "partiel", id="obligatoire-et-ecarte"),
        pytest.param("Chamallot.", "faux", id="ecarte"),
        pytest.param("Aucun.", "faux", id="aucune-espece"),
    ],
)
def test_semantique_au_singulier(court: str, note: str) -> None:
    assert noter_texte("Q3", court) == note


def test_espece_hors_table_a_revoir() -> None:
    # Correction sur preuve (ADR-0008) : une espèce hors table peut être juste ; la revue en juge.
    notation = noter(Q["Q3"], Tour("Q3", ecrire("Magmar et Dracaufeu.")), REF)
    assert (notation.note, notation.motifs) == ("à revoir", ("hors-table",))


def test_singulier_q16() -> None:
    assert noter_texte("Q16", "Dracolosse") == "juste"
    assert noter_texte("Q16", "Arcanin") == "faux"
    assert noter_texte("Q16", "Dracolosse, ou Scorvol") == "partiel"


@pytest.mark.parametrize(
    ("court", "note", "rappel", "precision"),
    [
        pytest.param("Abra, Bulbizarre, Dodoala, Jirachi.", "juste", 0.5, 1.0, id="moitie"),
        pytest.param(
            "Abra, Bulbizarre, Dodoala, Luxray.", "partiel", 0.375, 1.0, id="rappel-court"
        ),
        pytest.param(
            "Abra, Bulbizarre, Dodoala, Jirachi, Rondoudou.", "partiel", 0.5, 0.8, id="imprecis"
        ),
        pytest.param("Rondoudou et Girafarig.", "faux", 0.0, 0.0, id="ecartes-seuls"),
    ],
)
def test_semantique_au_pluriel(court: str, note: str, rappel: float, precision: float) -> None:
    # Juste : précision 100 %, rappel 50 % ou plus ; sinon partiel avec une espèce juste, faux sans
    # (choix de Julien du 2026-10-08).
    notation = noter(Q["Q26"], Tour("Q26", ecrire(court)), REF)
    assert (notation.note, notation.rappel, notation.precision) == (note, rappel, precision)


def test_les_acceptables_ne_comptent_pas_au_rappel() -> None:
    notation = noter(Q["Q17"], Tour("Q17", ecrire("Carvanha, Moyade, Gamblast, Sharpedo")), REF)
    assert (notation.note, notation.rappel, notation.precision) == ("partiel", 2 / 6, 1.0)


def test_types_de_q9() -> None:
    # Chaque espèce juste porte ses types dans le passage qui la suit (10 obligatoires sur 20).
    reponse = (
        "Lugia (Psy, Vol), Kyogre (Eau), Lanturn (Eau et Électrik), Relicanth : Eau, Roche ; "
        "Hyporoi (Eau, Dragon), Vacilys (Roche, Plante), Stari (Eau), Serpang (Eau), "
        "Luminéon (Eau), Aquali (Eau)"
    )
    assert noter_texte("Q9", reponse) == "juste"
    # Types écrits une fois pour deux espèces : l'association est incertaine, à revoir.
    groupee = reponse.replace("Stari (Eau), Serpang (Eau)", "Stari, Serpang (Eau)")
    notation = noter(Q["Q9"], Tour("Q9", ecrire(groupee)), REF)
    assert (notation.note, notation.motifs) == ("à revoir", ("types",))


def test_types_de_q9_manquants() -> None:
    reponse = ", ".join(f"{n} (Eau)" for n in sorted(REF.tables["Q9"].obligatoires))
    notation = noter(Q["Q9"], Tour("Q9", ecrire(reponse)), REF)
    # Lugia est Psy et Vol, Vacilys Roche et Plante : leurs types manquent.
    assert (notation.note, notation.motifs) == ("à revoir", ("types",))


# --- Q2 : contrôle de l'équipe -------------------------------------------------------------------

EQUIPE = ("Magnéton", "Dracolosse", "Flagadoss", "Noadkoko", "Staross", "Parasect")


class FauxControle:
    """Contrôle de Q2 simulé : note la liste reçue, renvoie le résultat prévu."""

    def __init__(self, resultat: Controle) -> None:
        self.resultat = resultat
        self.listes: list[str] = []

    def __call__(self, liste: str) -> Controle:
        self.listes.append(liste)
        return self.resultat


def noter_q2(court: str, resultat: Controle | None) -> tuple[str, tuple[str, ...], list[str]]:
    controle = FauxControle(resultat) if resultat else None
    notation = noter(Q["Q2"], Tour("Q2", ecrire(court)), REF, controle)
    return notation.note, notation.motifs, controle.listes if controle else []


def test_q2_equipe_valide() -> None:
    note, motifs, listes = noter_q2(", ".join(EQUIPE), Controle(6, (), equipe_valide=True))
    assert (note, motifs) == ("juste", ())
    assert listes == [liste_cypher(EQUIPE)]


def test_q2_equipe_qui_ne_couvre_pas_tout() -> None:
    note, motifs, _ = noter_q2(", ".join(EQUIPE), Controle(6, ("Roche",), equipe_valide=False))
    assert (note, motifs) == ("faux", ("types-non-couverts",))


def test_q2_especes_non_reconnues() -> None:
    note, motifs, _ = noter_q2(", ".join(EQUIPE), Controle(5, (), equipe_valide=False))
    assert (note, motifs) == ("à revoir", ("non-reconnus",))


def test_q2_noms_introuvables() -> None:
    # Moins de 6 espèces : rien n'est envoyé au contrôle.
    note, motifs, listes = noter_q2("Magnéton et Dracolosse.", Controle(6, (), equipe_valide=True))
    assert (note, motifs, listes) == ("à revoir", ("noms-q2",), [])


def test_q2_sans_controle() -> None:
    note, motifs, _ = noter_q2(", ".join(EQUIPE), None)
    assert (note, motifs) == ("à revoir", ("sans-controle",))


# --- Revue, réponse absente ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ident", "source"), [("Q10", "exempte"), ("Q29", "à revoir"), ("Q30", "à revoir")]
)
def test_questions_a_regle(ident: str, source: str) -> None:
    # Q10 : pas de source exigée (« pas dans les données ») ; Q29 et Q30 : jugées en revue (D4).
    notation = noter(Q[ident], Tour(ident, ecrire("Pikachu est de type Électrik.")), REF)
    assert (notation.note, notation.motifs, notation.source) == ("à revoir", ("regle",), source)


def test_sans_section_reponse() -> None:
    notation = noter(Q["Q21"], Tour("Q21", "Dracaufeu est le plus rapide."), REF)
    assert (notation.note, notation.motifs, notation.source) == (
        "à revoir",
        ("sans-reponse",),
        "non",
    )


def test_mode_sans_regle() -> None:
    # Un mode ajouté à banc.questions sans sa règle ici ne doit pas passer en silence.
    question = Question("Q1", "Qui ?", "faits", "vote")
    with pytest.raises(NotationError, match="vote"):
        noter(question, Tour("Q1", ecrire("Dracaufeu")), REF)


def test_tour_d_une_autre_question() -> None:
    with pytest.raises(NotationError, match="Q21"):
        noter(Q["Q22"], Tour("Q21", ecrire("Spectre")), REF)


# --- Source citée (plan, D4) ---------------------------------------------------------------------

VITESSES = (
    "MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)\n"
    "WHERE p.nom IN ['Dracaufeu', 'Tortank']\n"
    "RETURN p.nom AS pokemon, f.statVitesse AS vitesse"
)
LIGNES = [{"pokemon": "Dracaufeu", "vitesse": 100}, {"pokemon": "Tortank", "vitesse": 78}]


def source(ident: str, court: str, sources: str, *appels: Appel) -> str:
    return noter(Q[ident], Tour(ident, ecrire(court, sources), appels), REF).source


def bloc(requete: str) -> str:
    return f"```cypher\n{requete}\n```"


def test_source_executee_et_porteuse() -> None:
    assert source("Q21", "Dracaufeu", bloc(VITESSES), lecture(VITESSES, LIGNES)) == "oui"


def test_source_aux_espaces_pres() -> None:
    citee = bloc(" ".join(VITESSES.split()) + ";")
    assert source("Q21", "Dracaufeu", citee, lecture(VITESSES, LIGNES)) == "oui"


def test_source_non_executee() -> None:
    autre = VITESSES.replace("Tortank", "Carapuce")
    assert source("Q21", "Dracaufeu", bloc(autre), lecture(VITESSES, LIGNES)) == "non"


def test_source_executee_sans_la_reponse() -> None:
    # Un RETURN count(*) validait n'importe quoi (revue adverse) : le résultat porte la réponse.
    compte = "MATCH (p:Pokemon) RETURN count(*) AS total"
    assert source("Q21", "Dracaufeu", bloc(compte), lecture(compte, [{"total": 1025}])) == "non"


def test_source_en_erreur() -> None:
    # Le message d'erreur recopie la requête, noms compris : il ne porte pas pour autant la réponse.
    message = f"Neo.ClientError.Statement.SyntaxError: Invalid input in {VITESSES!r}"
    appel = lecture(VITESSES, message, erreur=True)
    assert source("Q21", "Dracaufeu", bloc(VITESSES), appel) == "non"


def test_source_executee_mais_pas_citee() -> None:
    assert source("Q21", "Dracaufeu", "le graphe", lecture(VITESSES, LIGNES)) == "non"


def test_source_absente() -> None:
    assert source("Q21", "Dracaufeu", "", lecture(VITESSES, LIGNES)) == "non"


def test_source_d_un_autre_outil() -> None:
    appel = Appel("write-cypher", VITESSES, {}, json.dumps(LIGNES), erreur=False)
    assert source("Q21", "Dracaufeu", bloc(VITESSES), appel) == "non"


def test_source_nombre() -> None:
    seisme = (
        "MATCH (a:Attaque {nom: 'Séisme'})-[:A_LE_TYPE]->(t) RETURN t.nom, a.puissance, a.categorie"
    )
    lignes = [{"t.nom": "Sol", "a.puissance": 100, "a.categorie": "physique"}]
    assert source("Q24", "Sol, 100, physique", bloc(seisme), lecture(seisme, lignes)) == "oui"
    autres = [{"t.nom": "Sol", "a.puissance": 90, "a.categorie": "physique"}]
    assert source("Q24", "Sol, 100, physique", bloc(seisme), lecture(seisme, autres)) == "non"


def test_source_nombre_ecrit_dans_un_texte() -> None:
    # Un nombre peut arriver dans une chaîne du résultat (q02 renvoie « Dracaufeu ×4.0 »).
    requete = "MATCH (p:Pokemon {nom: 'Dracaufeu'}) RETURN p.nom + ' : ' + f.statVitesse AS ligne"
    lignes = [{"ligne": "Dracaufeu : Vitesse 100"}]
    assert source("Q24", "Sol, 100, physique", bloc(requete), lecture(requete, lignes)) == "non"
    lignes = [{"ligne": "Séisme : Sol, puissance 100, physique"}]
    assert source("Q24", "Sol, 100, physique", bloc(requete), lecture(requete, lignes)) == "oui"


def test_source_valeurs_reparties_sur_deux_requetes() -> None:
    types = "MATCH (p:Pokemon {nom: 'Lucario'}) RETURN p"
    talents = "MATCH (t:Talent) RETURN t.nom"
    citees = bloc(types) + "\n" + bloc(talents)
    appels = (
        lecture(types, [{"types": ["Combat", "Acier"]}]),
        lecture(
            talents, [{"t.nom": "Attention"}, {"t.nom": "Impassible"}, {"t.nom": "Cœur Noble"}]
        ),
    )
    court = "Combat, Acier ; Attention, Impassible, Cœur Noble"
    assert source("Q4", court, citees, *appels) == "oui"
    assert source("Q4", court, bloc(types), *appels) == "non"


def test_source_resultat_non_json() -> None:
    appel = lecture(VITESSES, "pokemon: Dracaufeu, vitesse: 100")
    assert source("Q21", "Dracaufeu", bloc(VITESSES), appel) == "oui"


def test_source_noeud_serialise() -> None:
    # neo4j-mcp sérialise un nœud avec ses propriétés sous « Props ».
    noeud = [{"p": {"Id": 6, "Labels": ["Pokemon"], "Props": {"nom": "Dracaufeu"}}}]
    requete = "MATCH (p:Pokemon {nom: 'Dracaufeu'}) RETURN p"
    assert source("Q21", "Dracaufeu", bloc(requete), lecture(requete, noeud)) == "oui"


DESCRIPTIONS = "MATCH (p:Pokemon)-[:A_POUR_DESCRIPTION]->(d) RETURN p.nom, d.texte"
DECRIT = [{"p.nom": "Magmar", "d.texte": "Il se trouve près des bouches de volcans, en éruption."}]


def test_description_renvoyee() -> None:
    citee = "« Il se trouve près des bouches de volcans » (Pokémon Rouge)"
    assert source("Q3", "Magmar", citee, lecture(DESCRIPTIONS, DECRIT)) == "oui"


def test_description_inventee() -> None:
    citee = bloc(DESCRIPTIONS) + "\n« Il adore se baigner dans la lave chaude » (Pokémon Rouge)"
    assert source("Q3", "Magmar", citee, lecture(DESCRIPTIONS, DECRIT)) == "non"


def test_reponse_fausse_avec_sa_requete() -> None:
    # Sans valeur juste à retrouver, il suffit d'une requête citée réellement exécutée.
    assert source("Q21", "Tortank", bloc(VITESSES), lecture(VITESSES, LIGNES)) == "oui"


def test_source_de_q10_exemptee() -> None:
    assert source("Q10", "Ce n'est pas dans les données.", "") == "exempte"


# --- Introspections ------------------------------------------------------------------------------


def test_introspections_comptees() -> None:
    appels = (
        lecture("CALL apoc.meta.schema() YIELD value RETURN value", "[]"),
        lecture("CALL db.labels()", "[]"),
        lecture("SHOW INDEXES", "erreur", erreur=True),
        Appel("get-schema", "", {}, "{}", erreur=False),
        lecture(VITESSES, LIGNES),
        lecture("MATCH (n) RETURN labels(n) LIMIT 1", "[]"),
    )
    assert introspections(Tour("Q21", ecrire("Dracaufeu"), appels)) == 4
    assert noter(Q["Q21"], Tour("Q21", ecrire("Dracaufeu"), appels), REF).introspections == 4


# --- Contrôle par scripts/questions.sh -----------------------------------------------------------


def faux_script(tmp_path: Path, sortie: str, code: int = 0) -> Path:
    """Un faux questions.sh : note ses arguments et les variables Anthropic reçues, écrit la
    sortie prévue."""
    script = tmp_path / "questions.sh"
    journal = tmp_path / "appel.json"
    script.write_text(
        f"#!{sys.executable} -I\nimport json, os, sys\n"
        "anthropic = sorted(k for k in os.environ if k.startswith('ANTHROPIC'))\n"
        f"appel = {{'argv': sys.argv[1:], 'anthropic': anthropic}}\n"
        f"open({str(journal)!r}, 'w').write(json.dumps(appel))\n"
        f"sys.stdout.write({sortie!r})\nsys.exit({code})\n"
    )
    script.chmod(0o755)
    return script


def reponse_q02(valide: bool) -> str:
    controle = "6, [], TRUE" if valide else '6, ["Roche"], FALSE'
    return (
        "// PokéAPI 168b1e89467054cda2e7df43ccebbb69b459497a · q02.cypher\n"
        'menace, membresMenaces\n"Roche", ["Dracaufeu ×4.0"]\n'
        f"especesReconnues, typesNonCouverts, equipeValide\n{controle}\n"
    )


def test_controle_par_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # La clé Anthropic du harnais ne va qu'aux cellules Claude (code-map) : pas à questions.sh.
    monkeypatch.setenv("ANTHROPIC_API_KEY", "cle-factice")
    liste = liste_cypher(EQUIPE)
    script = faux_script(tmp_path, reponse_q02(valide=False))
    assert controle_par_script(liste, script=script) == Controle(6, ("Roche",), equipe_valide=False)
    appel = json.loads((tmp_path / "appel.json").read_text())
    assert appel == {"argv": ["--controle", liste], "anthropic": []}


def test_controle_par_script_avec_dossier(tmp_path: Path) -> None:
    script = faux_script(tmp_path, reponse_q02(valide=True))
    controle = controle_par_script(liste_cypher(EQUIPE), script=script, dossier=tmp_path)
    assert controle == Controle(6, (), equipe_valide=True)
    appel = json.loads((tmp_path / "appel.json").read_text())
    assert appel["argv"][:2] == ["--dossier", str(tmp_path)]


def test_controle_par_script_en_echec(tmp_path: Path) -> None:
    script = faux_script(tmp_path, "", code=2)
    with pytest.raises(NotationError, match="code 2"):
        controle_par_script(liste_cypher(EQUIPE), script=script)


@pytest.mark.parametrize(
    "sortie",
    [
        pytest.param("pas une réponse", id="illisible"),
        pytest.param(
            '// PokéAPI x · q02.cypher\nmenace, membresMenaces\n"Roche", []\n', id="sans-controle"
        ),
        pytest.param(
            "// PokéAPI x · q02.cypher\nespecesReconnues, typesNonCouverts, equipeValide\n"
            '"six", [], TRUE\n',
            id="mal-type",
        ),
    ],
)
def test_controle_par_script_sortie_inattendue(tmp_path: Path, sortie: str) -> None:
    with pytest.raises(NotationError):
        controle_par_script(liste_cypher(EQUIPE), script=faux_script(tmp_path, sortie))


def test_reponse_de_reference_de_q02_lisible() -> None:
    # Le contrôle de l'équipe par défaut (attendu/q02.txt) se relit comme celui d'un agent.
    controle = attendu.lire("q02")[-1]
    assert controle.colonnes == ("especesReconnues", "typesNonCouverts", "equipeValide")
