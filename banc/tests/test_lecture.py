"""Lecture des réponses d'un agent (T2.1) : sections « Réponse » et « Sources », normalisation des
mots, nombres, espèces, requêtes et descriptions citées, et les 6 noms de Q2, validés puis échappés
en liste littérale pour scripts/questions.sh --controle (plan, D4 et D6).
"""

import pytest

from banc import attendu
from banc.lecture import (
    Especes,
    LectureError,
    chaine_cypher,
    contient,
    descriptions_citees,
    equipe,
    liste_cypher,
    meme_requete,
    mots,
    nom_permis,
    nombres,
    requetes_citees,
    sections,
)
from banc.questions import charger

BANC = charger()
ESPECES = Especes.charger()
REFERENCE = ("Florizarre", "Dracaufeu", "Tortank", "Pikachu", "Ronflex", "Lokhlass")

REQUETE = (
    "MATCH (p:Pokemon)-[:A_POUR_FORME_PAR_DEFAUT]->(f:Forme)\n"
    "WHERE p.nom IN ['Dracaufeu', 'Tortank']\n"
    "RETURN p.nom AS pokemon, f.statVitesse AS vitesse"
)
REPONSE_TYPE = f"""Je compare les vitesses des deux Pokémon.

**Réponse :** Dracaufeu est le plus rapide (Vitesse 100 contre 78).

**Sources :**
```cypher
{REQUETE}
```
"""


# --- Sections ------------------------------------------------------------------------------------


def test_sections_de_la_consigne() -> None:
    lues = sections(REPONSE_TYPE)
    assert lues.reponse == "Dracaufeu est le plus rapide (Vitesse 100 contre 78)."
    assert lues.sources is not None
    assert REQUETE in lues.sources


@pytest.mark.parametrize(
    ("entete_reponse", "entete_sources"),
    [
        pytest.param("**Réponse :**", "**Sources :**", id="gras-deux-points-dedans"),
        pytest.param("**Réponse** :", "**Sources** :", id="gras-deux-points-dehors"),
        pytest.param("Réponse :", "Sources :", id="simple"),
        pytest.param("- **Réponse :**", "- **Sources :**", id="liste-comme-la-consigne"),
        pytest.param("RÉPONSE :", "SOURCES :", id="capitales"),
        pytest.param("Reponse :", "Source :", id="sans-accent-singulier"),
        pytest.param("**Réponse courte :**", "**Sources :**", id="reponse-courte"),
    ],
)
def test_entetes_sur_la_ligne(entete_reponse: str, entete_sources: str) -> None:
    lues = sections(f"Analyse.\n\n{entete_reponse} Dracaufeu.\n\n{entete_sources} la requête.")
    assert lues.reponse == "Dracaufeu."
    assert lues.sources == "la requête."


@pytest.mark.parametrize(
    "entete", ["## Réponse", "### Réponse :", "**Réponse**", "# **Réponse**"], ids=str
)
def test_entete_seul_sur_sa_ligne(entete: str) -> None:
    lues = sections(f"{entete}\nDracaufeu,\nplus rapide.\n\n## Sources\n`RETURN 1`")
    assert lues.reponse == "Dracaufeu,\nplus rapide."
    assert lues.sources == "`RETURN 1`"


def test_ordre_inverse() -> None:
    lues = sections("**Sources :** la requête.\n**Réponse :** Dracaufeu.")
    assert lues.reponse == "Dracaufeu."
    assert lues.sources == "la requête."


def test_la_derniere_section_l_emporte() -> None:
    # La consigne demande de terminer par ces sections : un brouillon plus haut ne compte pas.
    texte = "Réponse : peut-être Tortank ?\nVérifions.\n\n" + REPONSE_TYPE
    assert sections(texte).reponse == "Dracaufeu est le plus rapide (Vitesse 100 contre 78)."


def test_entete_dans_un_bloc_de_code_ignore() -> None:
    # Hors d'un bloc, « Réponse : Tortank » serait un en-tête (extrait de sortie recopié…).
    bloc = "```text\nRéponse : Tortank\n```"
    lues = sections(f"**Réponse :** Dracaufeu.\n**Sources :**\n{bloc}")
    assert lues.reponse == "Dracaufeu."
    assert lues.sources == bloc


@pytest.mark.parametrize(
    "texte",
    [
        pytest.param("Dracaufeu est le plus rapide.", id="aucune-section"),
        pytest.param("Réponse rapide : Dracaufeu.", id="phrase-qui-commence-par-reponse"),
        pytest.param("**Réponse :**\n\n**Sources :** la requête.", id="reponse-vide"),
    ],
)
def test_sans_reponse(texte: str) -> None:
    assert sections(texte).reponse is None


def test_sans_sources() -> None:
    lues = sections("**Réponse :** Dracaufeu.")
    assert lues.reponse == "Dracaufeu."
    assert lues.sources is None


# --- Normalisation -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("texte", "attendus"),
    [
        pytest.param("Évoli", ("evoli",), id="accent-et-casse"),
        pytest.param("Cœur Noble", ("coeur", "noble"), id="ligature"),
        pytest.param("Fracass’Tête", ("fracass", "tete"), id="apostrophe-typographique"),
        pytest.param("Fracass'Tête", ("fracass", "tete"), id="apostrophe-droite"),
        pytest.param("les évolutions d'Évoli", ("les", "evolutions", "d", "evoli"), id="elision"),
        pytest.param("l’Électrik", ("l", "electrik"), id="elision-typographique"),
        pytest.param("Roue-de-Fer", ("roue", "de", "fer"), id="tirets"),
        pytest.param("M. Mime", ("m", "mime"), id="point"),
        pytest.param("Type:0", ("type", "0"), id="deux-points"),
        pytest.param("Nidoran♀", ("nidoran♀",), id="symbole-garde"),
    ],
)
def test_mots(texte: str, attendus: tuple[str, ...]) -> None:
    assert mots(texte) == attendus


def test_elision_detachee_du_nom() -> None:
    # Piège de la phase 1 (code-map-gotchas) : « d'Évoli » doit laisser voir Évoli.
    assert contient(mots("Toutes les évolutions d'Évoli sont connues."), mots("Évoli"))
    assert contient(mots("Il craint l'Électrik."), mots("Électrik"))


def test_contient_en_mots_entiers() -> None:
    assert contient(mots("Type Sol et Roche"), mots("Sol"))
    assert not contient(mots("Solaroc"), mots("Sol"))
    assert contient(mots("Il apprend Fracass'Tête."), mots("Fracass’Tête"))
    assert not contient(mots("Fracass"), mots("Fracass’Tête"))
    assert not contient(mots("Dracaufeu"), ())


@pytest.mark.parametrize(
    ("texte", "attendus"),
    [
        pytest.param("Vitesse 100 contre 78", [100, 78], id="entiers"),
        pytest.param("1 025 espèces, 10 000 km", [1025, 10000], id="milliers"),
        pytest.param("Roche ×4, Eau ×0,5", [4, 0.5], id="multiplicateurs"),
        pytest.param("Jaccard 0,541 puis 0.517", [0.541, 0.517], id="decimales"),
        pytest.param("puissance 100.", [100], id="fin-de-phrase"),
        pytest.param("précision 100 %", [100], id="pourcentage"),
        pytest.param("Q7, Porygon2 et le 2e tour", [], id="dans-un-mot"),
    ],
)
def test_nombres(texte: str, attendus: list[float]) -> None:
    assert nombres(texte) == attendus


def test_milliers_a_espace_insecable() -> None:
    # Construites par chr() : écrites telles quelles, elles seraient invisibles (code-map-gotchas).
    insecable, fine = chr(0xA0), chr(0x202F)
    assert nombres(f"1{insecable}025 espèces et 10{fine}000 km") == [1025, 10000]


def test_un_nombre_n_en_contient_pas_un_autre() -> None:
    assert 100 not in nombres("1000 espèces")
    assert 100 in nombres("100,0")


# --- Espèces citées ------------------------------------------------------------------------------


def test_liste_des_especes() -> None:
    # Tirée de la base (questions/attendu/especes.txt) : 1 025 noms, aucun ne se confond avec un
    # autre une fois normalisé.
    assert len(ESPECES.noms) == 1025
    assert {"Dracaufeu", "Porygon-Z", "Nidoran♀", "Nidoran♂", "M. Mime", "Type:0"} <= ESPECES.noms


def test_la_liste_couvre_les_especes_du_banc() -> None:
    # Toute espèce des réponses de référence (longues listes, tables, Q8) et de banc.toml y figure.
    cites: set[str] = set(REFERENCE)
    for fichier in ("q03", "q07", "q09", "q14", "q16", "q17", "q26", "q08", "q20"):
        [tableau, *_] = attendu.lire(fichier)
        cites |= {str(ligne["pokemon"]) for ligne in tableau.lignes}
    cites |= set(BANC.questions["Q8"].scores)
    assert cites <= ESPECES.noms
    for question in ("Q7", "Q14"):
        assert {str(d) for d in BANC.questions[question].distracteurs} <= ESPECES.noms


def test_especes_citees_dans_l_ordre() -> None:
    texte = "Drattak, puis dracolosse, puis RESHIRAM ; Drattak encore."
    assert ESPECES.citees(texte) == ["Drattak", "Dracolosse", "Reshiram"]


def test_plus_longue_correspondance() -> None:
    assert ESPECES.citees("Porygon-Z et Porygon") == ["Porygon-Z", "Porygon"]
    assert ESPECES.citees("Nidoran♀ et Nidoran♂") == ["Nidoran♀", "Nidoran♂"]


def test_espece_apres_une_elision() -> None:
    assert ESPECES.citees("les évolutions d'Évoli et l'Onix") == ["Évoli", "Onix"]


def test_orthographe_approchee() -> None:
    # Casse, accents et apostrophes ignorés : l'agent qui écrit « magneton » cite Magnéton.
    assert ESPECES.citees("magneton, ho oh, m mime") == ["Magnéton", "Ho-Oh", "M. Mime"]


def test_faux_positifs_connus() -> None:
    # Relevés le 2026-10-08 : Draco dans les attaques Draco-…, Ronflex dans « Gare au Ronflex ».
    # Ils font passer une réponse « à revoir », jamais « juste » à tort.
    assert ESPECES.citees("Il connaît Draco-Météore.") == ["Draco"]


def test_citations_situees() -> None:
    [citation] = ESPECES.citations(mots("Le Pokémon Porygon-Z"))
    assert (citation.nom, citation.debut, citation.fin) == ("Porygon-Z", 2, 4)


def test_noms_qui_se_confondent() -> None:
    with pytest.raises(LectureError, match="se confondent"):
        Especes(["Magnéton", "Magneton"])
    with pytest.raises(LectureError, match="vide"):
        Especes(["Magnéton", "♥"])


# --- Requêtes et descriptions citées -------------------------------------------------------------


def test_requetes_en_blocs_de_code() -> None:
    sources = f"```cypher\n{REQUETE}\n```\nPuis :\n```\nRETURN 1;\nRETURN 2;\n```"
    assert requetes_citees(sources) == [REQUETE, "RETURN 1", "RETURN 2"]


def test_requete_en_ligne() -> None:
    sources = "La requête `MATCH (t:Type) RETURN t.nom` ; le type `Feu` n'en est pas une."
    assert requetes_citees(sources) == ["MATCH (t:Type) RETURN t.nom"]


def test_requete_sans_bloc() -> None:
    sources = "1. MATCH (t:Type)\nRETURN t.nom\n\nC'est tout."
    assert requetes_citees(sources) == ["MATCH (t:Type)\nRETURN t.nom"]


def test_aucune_requete() -> None:
    assert requetes_citees("la fiche de schéma") == []


@pytest.mark.parametrize(
    "citee",
    [
        pytest.param(REQUETE.replace("\n", " "), id="une-ligne"),
        pytest.param(REQUETE + ";", id="point-virgule"),
        pytest.param(REQUETE.replace("IN [", "IN[").replace("', '", "','"), id="espaces-retires"),
        pytest.param("  " + REQUETE.replace("\n", "\n    "), id="indentation"),
    ],
)
def test_meme_requete_aux_espaces_pres(citee: str) -> None:
    assert meme_requete(citee, REQUETE)


@pytest.mark.parametrize(
    "citee",
    [
        pytest.param(REQUETE.replace("Tortank", "Tortan"), id="autre-litteral"),
        pytest.param(REQUETE.replace("RETURN", "RETURN DISTINCT"), id="autre-requete"),
        pytest.param(REQUETE.replace("'Dracaufeu'", "'Dracau feu'"), id="espace-dans-une-chaine"),
    ],
)
def test_requetes_differentes(citee: str) -> None:
    assert not meme_requete(citee, REQUETE)


def test_descriptions_citees() -> None:
    sources = (
        "« Il vit près des volcans, dit-on. » (Pokémon Rubis)\n"
        "“Ses flammes brûlent tout… et rien ne l'arrête.” (Pokémon Or)\n"
        '"Pokémon Flamme" et « Feu » : trop courts pour être des descriptions.\n'
        '```cypher\nMATCH (p {nom: "un nom entre guillemets doubles"}) RETURN p\n```'
    )
    assert descriptions_citees(sources) == [
        "Il vit près des volcans, dit-on.",
        "Ses flammes brûlent tout",
        "et rien ne l'arrête.",
    ]


# --- Q2 : les 6 noms, validés puis échappés ------------------------------------------------------

EQUIPE = ("Magnéton", "Dracolosse", "Flagadoss", "Noadkoko", "Staross", "Parasect")


def test_equipe_enumeree() -> None:
    reponse = "Magnéton, Dracolosse, Flagadoss, Noadkoko, Staross et Parasect."
    assert equipe(reponse, ESPECES, REFERENCE) == EQUIPE


def test_equipe_expliquee() -> None:
    # Les membres de l'équipe de référence cités dans l'explication sont écartés.
    reponse = (
        "1. **Magnéton** : résiste à l'Électrik qui menace Tortank et Lokhlass.\n"
        "2. **Dracolosse** : immunisé contre le Sol, qui menace Pikachu.\n"
        "3. Flagadoss\n4. Noadkoko\n5. Staross\n6. Parasect (protège Dracaufeu)"
    )
    assert equipe(reponse, ESPECES, REFERENCE) == EQUIPE


def test_equipe_avec_un_membre_de_reference() -> None:
    reponse = "Magnéton, Dracolosse, Flagadoss, Noadkoko, Staross et Ronflex."
    assert equipe(reponse, ESPECES, REFERENCE) == (*EQUIPE[:5], "Ronflex")


def test_equipe_remise_a_son_orthographe() -> None:
    reponse = "magneton, DRACOLOSSE, Flagadoss, Noadkoko, Staross, Parasect"
    assert equipe(reponse, ESPECES, REFERENCE) == EQUIPE


@pytest.mark.parametrize(
    "reponse",
    [
        pytest.param("Magnéton, Dracolosse, Flagadoss, Noadkoko et Staross.", id="cinq"),
        pytest.param(
            "Magnéton, Dracolosse, Flagadoss, Noadkoko, Staross, Parasect, Steelix.", id="sept"
        ),
        pytest.param(
            "Magnéton, Dracolosse, Flagadoss, Noadkoko, Staross et Ronflex, pour Tortank.",
            id="membre-de-reference-et-explication",
        ),
        pytest.param("Magnetonne, Dracolosse, Flagadoss, Noadkoko, Staross, Parasect.", id="faute"),
    ],
)
def test_equipe_introuvable(reponse: str) -> None:
    # Sans exactement 6 espèces, la réponse passe « à revoir » : rien n'est envoyé à la base.
    assert equipe(reponse, ESPECES, REFERENCE) is None


def test_liste_cypher() -> None:
    assert liste_cypher(EQUIPE) == (
        "['Magnéton', 'Dracolosse', 'Flagadoss', 'Noadkoko', 'Staross', 'Parasect']"
    )


def test_tous_les_noms_reels_sont_permis() -> None:
    assert all(nom_permis(nom) for nom in ESPECES.noms)


@pytest.mark.parametrize(
    "nom",
    [
        pytest.param("O'Brien", id="apostrophe"),
        pytest.param("Dracaufeu\\", id="antislash"),
        pytest.param("Dracaufeu\n", id="saut-de-ligne"),
        pytest.param("Dracaufeu']", id="crochet"),
        pytest.param("", id="vide"),
        pytest.param(" Dracaufeu", id="espace-en-tete"),
        pytest.param("D" * 31, id="trop-long"),
        pytest.param("x}, y: {z", id="accolades"),
    ],
)
def test_nom_refuse(nom: str) -> None:
    assert not nom_permis(nom)
    with pytest.raises(LectureError):
        liste_cypher((*EQUIPE[:5], nom))


@pytest.mark.parametrize(
    "noms",
    [
        pytest.param(EQUIPE[:5], id="cinq"),
        pytest.param((*EQUIPE[:5], "Magnéton"), id="doublon"),
    ],
)
def test_liste_de_six_noms_distincts(noms: tuple[str, ...]) -> None:
    with pytest.raises(LectureError):
        liste_cypher(noms)


def test_chaine_cypher_echappe() -> None:
    # Seconde barrière : même un nom qui passerait la validation ne sortirait pas de sa chaîne.
    assert chaine_cypher("O'Brien") == "'O\\'Brien'"
    assert chaine_cypher("a\\b") == "'a\\\\b'"
    assert chaine_cypher("Ho-Oh") == "'Ho-Oh'"
