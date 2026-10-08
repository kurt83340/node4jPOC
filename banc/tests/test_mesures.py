"""Traces et mesures (T3.1 ; plan 002, D10 et D13) : une trace JSONL par conversation, relue en
tours pour la notation (banc.trace, inchangé) ; une ligne CSV sans prose par tour ; le coût par
modèle, cache, réflexion et petit modèle de Claude Code compris. Ni base ni LLM : des conversations
écrites à la main, une horloge monotone factice.
"""

import csv
import json
from collections.abc import Callable
from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from google.genai import types

from banc.mesures import (
    COLONNES,
    Entete,
    Journal,
    MesureError,
    commit_pokeapi,
    couts,
    ecrire,
    empreinte,
    fichier_trace,
    ligne,
    lire,
    reflexion_anthropic,
    usage_adk,
    usage_anthropic,
    usage_claude_code,
)
from banc.notation import Notation
from banc.prix import PrixError, Usage, charger
from banc.trace import Appel, Tour

TARIFS = charger()
COMMIT = "168b1e89467054cda2e7df43ccebbb69b459497a"
SONNET = "claude-sonnet-5-5"
HAIKU = "claude-haiku-4-5-20251001"
ENTETE = Entete(
    campagne="essai",
    cellule="claude-code",
    passe=1,
    essai=1,
    questions=("Q2", "Q18"),
    modele=SONNET,
    acces="api",
    jour=date(2026, 10, 8),
    effort="high",
    versions={"neo4j-mcp": "1.6.0", "claude-agent-sdk": "0.2.164", "claude-code": "2.1.292"},
    commit_pokeapi=COMMIT,
)
MESSAGE_Q2 = "Mon équipe : Lokhlass, …\n\nQuelle équipe proposes-tu ?"
REQUETE = "MATCH (p:Pokemon) RETURN p.nom AS nom"
RESULTAT = '[\n  {\n    "nom": "Dracaufeu"\n  }\n]'
REPONSE_Q2 = f"Voici l'équipe.\n\nRéponse : Dracaufeu, Lokhlass\n\nSources : `{REQUETE}`"
# Texte écrit avant l'abandon du tour : un échec n'a pas de réponse courte à comparer.
PARTIELLE = "Je vérifie encore.\n\nRéponse : Lokhlass"
BRUT = {"input_tokens": 10, "output_tokens": 200, "cache_creation_input_tokens": 9_000}


class Horloge:
    """Horloge monotone factice : chaque test règle l'heure."""

    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def conversation(fichier: Path) -> None:
    """Q2 répondue, puis Q18 abandonnée à 180 s pendant une lecture (agent tué)."""
    horloge = Horloge()
    with Journal(fichier, ENTETE, horloge) as journal:
        horloge.t = 1002.0
        journal.question("Q2", MESSAGE_Q2)
        horloge.t = 1003.5
        usage = Usage(entree=10, sortie=200, cache_ecriture_1h=9_000)
        journal.llm(SONNET, usage, reflexion=150, brut=BRUT)
        journal.appel("toolu_1", "read-cypher", REQUETE, {"limite": 5})
        horloge.t = 1004.0
        journal.resultat("toolu_1", RESULTAT)
        journal.llm(HAIKU, Usage(entree=50, sortie=5), reflexion=3)
        journal.reprise(429)
        journal.llm(SONNET, Usage(entree=20, sortie=300, cache_lecture=9_000), reflexion=50)
        horloge.t = 1012.25
        journal.fin("reponse", reponse=REPONSE_Q2)
        horloge.t = 1013.0
        journal.question("Q18", "Et sans Lokhlass ?")
        journal.appel("toolu_2", "read-cypher", "CALL db.labels()")
        horloge.t = 1193.0
        journal.fin("echec", "delai", PARTIELLE)


@pytest.fixture
def trace(tmp_path: Path) -> Path:
    fichier = tmp_path / "trace.jsonl"
    conversation(fichier)
    return fichier


# --- Trace JSONL ---------------------------------------------------------------------------------


def test_relue_en_tours_pour_la_notation(trace: Path) -> None:
    # Le contrat de banc.trace, inchangé : réponse finale et appels du tour, dans l'ordre.
    q2, q18 = lire(trace).tours
    assert q2.tour() == Tour(
        "Q2", REPONSE_Q2, (Appel("read-cypher", REQUETE, {"limite": 5}, RESULTAT, False),)
    )
    # Un appel resté sans résultat (agent tué pendant la lecture) : en échec, requête gardée.
    appel = Appel("read-cypher", "CALL db.labels()", {}, "", True)
    assert q18.tour() == Tour("Q18", PARTIELLE, (appel,))


def test_entete_relu(trace: Path) -> None:
    assert lire(trace).entete == ENTETE


def test_une_ligne_par_evenement_ecrite_aussitot(tmp_path: Path) -> None:
    # Une conversation tuée garde tout ce qui précède : chaque ligne est vidée dès son écriture.
    fichier = tmp_path / "trace.jsonl"
    horloge = Horloge()
    with Journal(fichier, ENTETE, horloge) as journal:
        horloge.t = 1001.5
        journal.question("Q2", MESSAGE_Q2)
        horloge.t = 1002.25
        journal.appel("toolu_1", "read-cypher", REQUETE)
        lues = [json.loads(texte) for texte in fichier.read_text().splitlines()]
        assert [(e["type"], e["t"]) for e in lues] == [
            ("conversation", 0.0),
            ("question", 1.5),
            ("appel", 2.25),
        ]
        assert lues[2]["requete"] == REQUETE


def test_details_gardes_pour_l_audit(trace: Path) -> None:
    # Usage tel que reçu du client, statut d'une reprise : pour relire une mesure, pas pour noter.
    evenements = [json.loads(texte) for texte in trace.read_text().splitlines()]
    assert (evenements[2]["brut"], evenements[6]["statut"]) == (BRUT, 429)


def test_durees_a_l_horloge_monotone(trace: Path) -> None:
    # De l'envoi de la question à la fin du tour : le second tour ne compte pas le premier.
    q2, q18 = lire(trace).tours
    assert (q2.duree_s, q18.duree_s) == (10.25, 180.0)


def test_mesures_du_tour(trace: Path) -> None:
    q2, q18 = lire(trace).tours
    assert q2.usages == {
        SONNET: Usage(entree=30, sortie=500, cache_ecriture_1h=9_000, cache_lecture=9_000),
        HAIKU: Usage(entree=50, sortie=5),
    }
    reflexion = {SONNET: 200, HAIKU: 3}
    assert (q2.reflexion, q2.reprises, q2.issue, q2.cause) == (reflexion, 1, "reponse", None)
    assert (q18.usages, q18.reflexion, q18.issue, q18.cause) == ({}, {}, "echec", "delai")


def test_tour_inacheve(tmp_path: Path) -> None:
    # Le harnais lui-même interrompu : le tour n'a ni fin ni durée, et ne se mesure pas.
    fichier = tmp_path / "trace.jsonl"
    with Journal(fichier, ENTETE, Horloge()) as journal:
        journal.question("Q2", MESSAGE_Q2)
    [tour] = lire(fichier).tours
    assert (tour.issue, tour.duree_s) == (None, None)
    with pytest.raises(MesureError, match="inachevé"):
        ligne(ENTETE, tour, None, TARIFS)


def test_trace_jamais_ecrasee(trace: Path) -> None:
    with pytest.raises(MesureError, match="existe déjà"):
        Journal(trace, ENTETE, Horloge())


def test_evenement_hors_d_un_tour(tmp_path: Path) -> None:
    with (
        Journal(tmp_path / "trace.jsonl", ENTETE, Horloge()) as journal,
        pytest.raises(MesureError, match="hors d'un tour"),
    ):
        journal.llm(SONNET, Usage(entree=1))


@pytest.mark.parametrize(
    "questions",
    [
        pytest.param(("Q7",), id="hors-de-la-conversation"),
        pytest.param(("Q18", "Q2"), id="hors-d-ordre"),
        pytest.param(("Q2", "Q2"), id="deux-fois"),
        pytest.param(("Q2", "Q18", "Q2"), id="apres-la-derniere"),
    ],
)
def test_questions_dans_l_ordre_de_l_entete(tmp_path: Path, questions: tuple[str, ...]) -> None:
    with (
        Journal(tmp_path / "trace.jsonl", ENTETE, Horloge()) as journal,
        pytest.raises(MesureError, match="question"),
    ):
        for question in questions:
            journal.question(question, "?")
            journal.fin("panne", "api")


def test_question_avant_la_fin_du_tour(tmp_path: Path) -> None:
    with Journal(tmp_path / "trace.jsonl", ENTETE, Horloge()) as journal:
        journal.question("Q2", MESSAGE_Q2)
        with pytest.raises(MesureError, match="pas fini"):
            journal.question("Q18", "?")


def test_nom_d_outil_nu(tmp_path: Path) -> None:
    # La notation compare le nom MCP nu (banc.trace) : la cellule retire le préfixe du client.
    with Journal(tmp_path / "trace.jsonl", ENTETE, Horloge()) as journal:
        journal.question("Q2", MESSAGE_Q2)
        with pytest.raises(MesureError, match="nom MCP nu"):
            journal.appel("toolu_1", "mcp__neo4j__read-cypher", REQUETE)


@pytest.mark.parametrize(
    ("evenements", "message"),
    [
        pytest.param([("resultat", "toolu_9")], "sans appel", id="resultat-sans-appel"),
        pytest.param([("appel", "toolu_1"), ("appel", "toolu_1")], "déjà", id="appel-en-double"),
        pytest.param(
            [("appel", "toolu_1"), ("resultat", "toolu_1"), ("resultat", "toolu_1")],
            "déjà",
            id="resultat-en-double",
        ),
    ],
)
def test_appels_apparies(tmp_path: Path, evenements: list[tuple[str, str]], message: str) -> None:
    with Journal(tmp_path / "trace.jsonl", ENTETE, Horloge()) as journal:
        journal.question("Q2", MESSAGE_Q2)
        with pytest.raises(MesureError, match=message):
            for genre, ident in evenements:
                if genre == "appel":
                    journal.appel(ident, "read-cypher", REQUETE)
                else:
                    journal.resultat(ident, RESULTAT)


@pytest.mark.parametrize(
    ("issue", "cause"),
    [("reponse", None), ("echec", "delai"), ("echec", "tours"), ("echec", "budget"),
     ("panne", "serveur"), ("panne", "api"), ("panne", "reprises"), ("arret", "plafond")],
)  # fmt: skip
def test_issues_et_causes(tmp_path: Path, issue: str, cause: str | None) -> None:
    # D13 : l'échec de l'agent compte faux ; la panne se relance ; un plafond de dépense arrête la
    # campagne, ni panne ni échec.
    fichier = tmp_path / "trace.jsonl"
    with Journal(fichier, ENTETE, Horloge()) as journal:
        journal.question("Q2", MESSAGE_Q2)
        journal.fin(issue, cause)
    [tour] = lire(fichier).tours
    assert (tour.issue, tour.cause) == (issue, cause)


@pytest.mark.parametrize(
    ("issue", "cause"),
    [("reponse", "delai"), ("echec", None), ("echec", "api"), ("panne", "delai"),
     ("arret", None), ("abandon", None), ("panne", "Délai dépassé après 3 reprises")],
)  # fmt: skip
def test_issue_ou_cause_refusee(tmp_path: Path, issue: str, cause: str | None) -> None:
    with Journal(tmp_path / "trace.jsonl", ENTETE, Horloge()) as journal:
        journal.question("Q2", MESSAGE_Q2)
        with pytest.raises(MesureError, match="issue"):
            journal.fin(issue, cause)


def test_evenement_inconnu_refuse(trace: Path) -> None:
    with trace.open("a") as flux:
        flux.write('{"type": "autre", "t": 1.0}\n')
    with pytest.raises(MesureError, match="'autre' inconnu"):
        lire(trace)


def test_ligne_illisible_refusee(trace: Path) -> None:
    with trace.open("a") as flux:
        flux.write('{"type": "fin", "t":\n')
    with pytest.raises(MesureError, match="ligne 13"):
        lire(trace)


def test_trace_absente(tmp_path: Path) -> None:
    with pytest.raises(MesureError, match="illisible"):
        lire(tmp_path / "absente.jsonl")


type Evenements = list[dict[str, Any]]


def modifier(evenements: Evenements, rang: int, **champs: object) -> Evenements:
    return [*evenements[:rang], evenements[rang] | champs, *evenements[rang + 1 :]]


# Événements de la trace de référence, par rang : 0 en-tête, 1 question Q2, 2 llm, 3 appel,
# 4 résultat, 5 llm, 6 reprise, 7 llm, 8 fin de Q2, 9 question Q18, 10 appel, 11 fin de Q18.
@pytest.mark.parametrize(
    ("retouche", "message"),
    [
        pytest.param(lambda e: e[1:], "en-tête", id="sans-en-tete"),
        pytest.param(lambda e: [*e[:8], *e[9:]], "pas fini", id="fin-retiree"),
        pytest.param(lambda e: [*e[:9], e[6], *e[9:]], "hors d'un tour", id="apres-la-fin"),
        pytest.param(lambda e: [*e[:4], e[3], *e[4:]], "déjà", id="appel-en-double"),
        pytest.param(lambda e: modifier(e, 4, id="toolu_9"), "sans appel", id="resultat-inconnu"),
        pytest.param(lambda e: modifier(e, 2, question="Q18"), "dans le tour", id="autre-tour"),
        pytest.param(lambda e: modifier(e, 8, cause="fatigue"), "issue", id="cause-inventee"),
        pytest.param(lambda e: modifier(e, 0, format=2), "format", id="format-inconnu"),
        pytest.param(lambda e: [], "vide", id="vide"),
    ],
)
def test_trace_retouchee_refusee(
    trace: Path, retouche: Callable[[Evenements], Evenements], message: str
) -> None:
    # La relecture applique les règles de l'écriture : une trace retouchée à la main ne passe pas.
    evenements = [json.loads(texte) for texte in trace.read_text().splitlines()]
    trace.write_text("".join(json.dumps(e) + "\n" for e in retouche(evenements)))
    with pytest.raises(MesureError, match=message):
        lire(trace)


def test_evenement_non_serialisable(tmp_path: Path) -> None:
    with Journal(tmp_path / "trace.jsonl", ENTETE, Horloge()) as journal:
        journal.question("Q2", MESSAGE_Q2)
        with pytest.raises(MesureError, match="sérialisable"):
            journal.appel("toolu_1", "read-cypher", REQUETE, {"limite": object()})


def test_fichier_de_la_trace(tmp_path: Path) -> None:
    attendu = tmp_path / "essai" / "claude-code-p1-Q2+Q18-e1.jsonl"
    assert fichier_trace(tmp_path, ENTETE) == attendu


@pytest.mark.parametrize(
    "champs",
    [
        pytest.param({"campagne": "../hors"}, id="campagne-hors-du-dossier"),
        pytest.param({"cellule": "Claude Code"}, id="cellule-en-prose"),
        pytest.param({"passe": 0}, id="passe"),
        pytest.param({"essai": 0}, id="essai"),
        pytest.param({"questions": ()}, id="sans-question"),
        pytest.param({"questions": ("q2",)}, id="question"),
        pytest.param({"questions": ("Q2", "Q2")}, id="question-en-double"),
        pytest.param({"acces": "vertex"}, id="acces"),
        pytest.param({"commit_pokeapi": "168b1e8"}, id="commit"),
        pytest.param({"versions": {"claude code": "2.1.292"}}, id="version-en-prose"),
    ],
)
def test_entete_refuse(champs: dict[str, Any]) -> None:
    valeurs = {**ENTETE.__dict__, **champs}
    with pytest.raises(MesureError):
        Entete(**valeurs)


# --- Tokens par modèle, cache et réflexion -------------------------------------------------------


def test_usage_anthropic_par_duree_de_cache() -> None:
    # Usage de l'API (anthropic 1.11.0, types/usage.py) : écriture détaillée par durée, réflexion
    # comprise dans output_tokens, qui fait foi pour la facture.
    brut = {
        "input_tokens": 12,
        "output_tokens": 340,
        "cache_creation_input_tokens": 9_500,
        "cache_creation": {"ephemeral_5m_input_tokens": 500, "ephemeral_1h_input_tokens": 9_000},
        "cache_read_input_tokens": 3_000,
        "output_tokens_details": {"thinking_tokens": 120},
    }
    attendu = Usage(
        entree=12, sortie=340, cache_ecriture_5m=500, cache_ecriture_1h=9_000, cache_lecture=3_000
    )
    assert usage_anthropic(brut) == attendu
    assert reflexion_anthropic(brut) == 120


def test_usage_anthropic_sans_detail() -> None:
    # Sans détail par durée, l'écriture compte à 5 min (durée par défaut).
    brut = {"input_tokens": 3, "output_tokens": 4, "cache_creation_input_tokens": 50}
    assert usage_anthropic(brut) == Usage(entree=3, sortie=4, cache_ecriture_5m=50)
    assert reflexion_anthropic(brut) is None


def test_usage_anthropic_incoherent() -> None:
    brut = {
        "input_tokens": 1,
        "output_tokens": 1,
        "cache_creation_input_tokens": 10,
        "cache_creation": {"ephemeral_5m_input_tokens": 0, "ephemeral_1h_input_tokens": 20},
    }
    with pytest.raises(MesureError, match="1 h"):
        usage_anthropic(brut)


def test_claude_code_par_modele() -> None:
    # ResultMessage.model_usage (SDK 0.2.164, ModelUsage) : un compte par modèle, petit modèle
    # compris ; il ne sépare pas l'écriture à 1 h, que la cellule tire des messages de l'assistant.
    model_usage: dict[str, dict[str, Any]] = {
        SONNET: {
            "inputTokens": 10,
            "outputTokens": 20,
            "cacheReadInputTokens": 30,
            "cacheCreationInputTokens": 40,
            "costUSD": 0.001,
        },
        HAIKU: {"inputTokens": 5, "outputTokens": 1},
    }
    assert usage_claude_code(model_usage) == {
        SONNET: Usage(entree=10, sortie=20, cache_ecriture_5m=40, cache_lecture=30),
        HAIKU: Usage(entree=5, sortie=1),
    }
    assert usage_claude_code(model_usage, {SONNET: 25})[SONNET] == Usage(
        entree=10, sortie=20, cache_ecriture_5m=15, cache_ecriture_1h=25, cache_lecture=30
    )


def test_claude_code_part_1h_impossible() -> None:
    model_usage = {SONNET: {"inputTokens": 1, "cacheCreationInputTokens": 40}}
    with pytest.raises(MesureError, match="1 h"):
        usage_claude_code(model_usage, {SONNET: 41})
    with pytest.raises(MesureError, match="1 h"):
        usage_claude_code(model_usage, {HAIKU: 1})


def test_adk_claude() -> None:
    # ADK 2.11.0 (models/anthropic_llm.py) replie entrée, lecture et écriture du cache dans
    # prompt_token_count, et sépare la réflexion de la sortie ; il ne détaille pas la durée du
    # cache, que la cellule connaît (ContextCacheConfig).
    meta = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=100,
        cached_content_token_count=30,
        candidates_token_count=5,
        thoughts_token_count=7,
    )
    object.__setattr__(meta, "cache_creation_input_tokens", 60)
    assert usage_adk(meta) == Usage(entree=10, sortie=12, cache_ecriture_5m=60, cache_lecture=30)
    assert usage_adk(meta, cache_1h=True) == Usage(
        entree=10, sortie=12, cache_ecriture_1h=60, cache_lecture=30
    )


def test_adk_gemini() -> None:
    meta = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=100,
        cached_content_token_count=40,
        candidates_token_count=3,
        thoughts_token_count=9,
    )
    assert usage_adk(meta) == Usage(entree=60, sortie=12, cache_lecture=40)


# --- Coût par modèle ------------------------------------------------------------------------------


def test_cout_par_modele() -> None:
    # Prix de l'API (banc/prix.toml), en dollars par million : chaque modèle à son tarif.
    usages = {
        SONNET: Usage(entree=30, sortie=500, cache_ecriture_1h=9_000, cache_lecture=9_000),
        HAIKU: Usage(entree=50, sortie=5),
    }
    sonnet = (30 * 2 + 500 * 10 + 9_000 * 4 + 9_000 * Decimal("0.2")) / 1_000_000
    haiku = Decimal(50 * 1 + 5 * 5) / 1_000_000
    assert couts(usages, TARIFS, date(2026, 10, 8), "api") == {SONNET: sonnet, HAIKU: haiku}


def test_modele_sans_tarif() -> None:
    # Une mesure n'a pas de trou : un modèle inconnu arrête tout plutôt que de coûter 0.
    with pytest.raises(PrixError, match="claude-inconnu"):
        couts({"claude-inconnu": Usage(entree=1)}, TARIFS, date(2026, 10, 8), "api")


# --- Ligne CSV -----------------------------------------------------------------------------------


def test_ligne_d_une_reponse(trace: Path) -> None:
    q2, _ = lire(trace).tours
    notation = Notation("partiel", ("distracteur", "incomplete"), "oui", 0, 0.5, 1.0)
    assert ligne(ENTETE, q2, notation, TARIFS) == {
        "campagne": "essai",
        "cellule": "claude-code",
        "passe": "1",
        "question": "Q2",
        "essai": "1",
        "issue": "reponse",
        "cause": "",
        "note": "partiel",
        "motifs": "distracteur+incomplete",
        "source": "oui",
        "introspections": "0",
        "rappel": "0.500",
        "precision": "1.000",
        "duree_s": "10.25",
        "appels": "1",
        "reprises": "1",
        "modele": SONNET,
        "entree": "30",
        "sortie": "500",
        "reflexion": "200",
        "cache_lecture": "9000",
        "cache_ecriture_5m": "0",
        "cache_ecriture_1h": "9000",
        "cout_usd": "0.042935",
        "cout_annexe_usd": "0.000075",
        "effort": "high",
        "versions": "claude-agent-sdk=0.2.164;claude-code=2.1.292;neo4j-mcp=1.6.0",
        "commit_pokeapi": COMMIT,
        "empreinte": empreinte(REPONSE_Q2),
    }
    assert list(ligne(ENTETE, q2, notation, TARIFS)) == list(COLONNES)


def test_echec_compte_faux_avec_sa_cause(trace: Path) -> None:
    # D13 : 180 s dépassées, la réponse est fausse ; l'introspection du tour reste comptée.
    _, q18 = lire(trace).tours
    resultat = ligne(ENTETE, q18, None, TARIFS)
    attendu = {
        "issue": "echec", "cause": "delai", "note": "faux", "motifs": "", "source": "non",
        "introspections": "1", "duree_s": "180.00", "appels": "1", "empreinte": "",
        "entree": "0", "reflexion": "", "cout_usd": "0.000000", "cout_annexe_usd": "0.000000",
    }  # fmt: skip
    assert {colonne: resultat[colonne] for colonne in attendu} == attendu


@pytest.mark.parametrize(("issue", "cause"), [("panne", "api"), ("arret", "plafond")])
def test_tour_relance_sans_note(tmp_path: Path, issue: str, cause: str) -> None:
    # Une panne se relance, un arrêt se rejoue : la ligne reste (passe invalide au-delà de 2
    # pannes), sans note.
    fichier = tmp_path / "trace.jsonl"
    with Journal(fichier, ENTETE, Horloge()) as journal:
        journal.question("Q2", MESSAGE_Q2)
        journal.fin(issue, cause)
    [tour] = lire(fichier).tours
    resultat = ligne(ENTETE, tour, None, TARIFS)
    assert (resultat["issue"], resultat["cause"]) == (issue, cause)
    assert (resultat["note"], resultat["motifs"], resultat["source"]) == ("", "", "")


def test_notation_exigee_pour_une_reponse_seulement(trace: Path) -> None:
    q2, q18 = lire(trace).tours
    with pytest.raises(MesureError, match="sans notation"):
        ligne(ENTETE, q2, None, TARIFS)
    with pytest.raises(MesureError, match="pas de notation"):
        ligne(ENTETE, q18, Notation("juste"), TARIFS)


def test_notation_d_un_autre_tour(trace: Path) -> None:
    # Les introspections de la notation sont celles de la trace : sinon, notation d'un autre tour.
    q2, _ = lire(trace).tours
    with pytest.raises(MesureError, match="introspections"):
        ligne(ENTETE, q2, Notation("juste", introspections=3), TARIFS)


@pytest.mark.parametrize(
    "motifs",
    [("hors table",), ("distracteur+forme",), ("Délai dépassé : la requête a tourné 3 min",)],
)
def test_motifs_sans_prose(trace: Path, motifs: tuple[str, ...]) -> None:
    # Un motif est un code ; « + » les joint dans la colonne, il n'entre donc pas dans un motif.
    q2, _ = lire(trace).tours
    with pytest.raises(MesureError, match="prose"):
        ligne(ENTETE, q2, Notation("faux", motifs), TARIFS)


def test_champs_sans_prose(trace: Path) -> None:
    # Une notation ou un tour construits à la main ne font pas entrer de texte libre dans le CSV.
    q2, _ = lire(trace).tours
    with pytest.raises(MesureError, match="prose"):
        ligne(ENTETE, q2, Notation("excellent"), TARIFS)  # type: ignore[arg-type]
    with pytest.raises(MesureError, match="prose"):
        ligne(ENTETE, replace(q2, question="Q2 bis"), Notation("juste"), TARIFS)


def test_empreinte_de_la_reponse_courte_normalisee() -> None:
    # Même réponse courte, aux explications, à la casse, aux accents et au code près.
    une = "Le type le plus courant.\n\nRéponse : **Électrik** et Eau\n\nSources : `MATCH (t)`"
    autre = "Autre explication.\nréponse : electrik  et EAU `MATCH (t:Type) RETURN t`\nSources : x"
    assert empreinte(une) == empreinte(autre) != ""
    assert len(empreinte(une)) == 16
    assert empreinte("Réponse : Eau") != empreinte(une)
    assert empreinte("Sans section de réponse") == ""


# --- Fichier CSV ---------------------------------------------------------------------------------


def test_csv_ecrit_puis_complete(trace: Path, tmp_path: Path) -> None:
    q2, q18 = lire(trace).tours
    # « à revoir » : une valeur d'ensemble fermé, pas de la prose, malgré son espace.
    premiere = ligne(ENTETE, q2, Notation("à revoir", ("hors-table",), "à revoir"), TARIFS)
    seconde = ligne(ENTETE, q18, None, TARIFS)
    fichier = tmp_path / "mesures" / "essai.csv"
    ecrire(fichier, [premiere])
    ecrire(fichier, [seconde])
    with fichier.open(newline="") as flux:
        assert list(csv.DictReader(flux)) == [premiere, seconde]
    assert fichier.read_text().count("campagne,") == 1


def test_csv_d_un_autre_format_refuse(trace: Path, tmp_path: Path) -> None:
    # Colonnes changées en cours de campagne : jamais deux formats dans un même fichier.
    fichier = tmp_path / "essai.csv"
    fichier.write_text("campagne,cellule,note\n")
    q2, _ = lire(trace).tours
    with pytest.raises(MesureError, match="colonnes"):
        ecrire(fichier, [ligne(ENTETE, q2, Notation("juste"), TARIFS)])


def test_ligne_incomplete_refusee(trace: Path, tmp_path: Path) -> None:
    # Refusée avant toute écriture : pas même d'en-tête.
    q2, _ = lire(trace).tours
    valeurs = ligne(ENTETE, q2, Notation("juste"), TARIFS)
    del valeurs["empreinte"]
    fichier = tmp_path / "essai.csv"
    with pytest.raises(MesureError, match="colonnes"):
        ecrire(fichier, [valeurs])
    assert not fichier.exists()


def test_commit_pokeapi_des_reponses_de_reference() -> None:
    assert commit_pokeapi() == COMMIT


@pytest.mark.parametrize(
    ("contenus", "message"),
    [
        pytest.param([COMMIT, "0" * 40], "2 commits", id="deux-commits"),
        pytest.param([], "0 commits", id="aucune-reponse"),
        pytest.param([COMMIT, None], "en-tête", id="sans-en-tete"),
    ],
)
def test_commit_pokeapi_douteux(tmp_path: Path, contenus: list[str | None], message: str) -> None:
    for rang, commit in enumerate(contenus, start=1):
        entete = f"// PokéAPI {commit} · q{rang:02d}.cypher\n" if commit else ""
        (tmp_path / f"q{rang:02d}.txt").write_text(f"{entete}x\n1\n")
    with pytest.raises(MesureError, match=message):
        commit_pokeapi(tmp_path)
