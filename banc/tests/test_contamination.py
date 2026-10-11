"""Consigne et fiche de schéma (T1.2, plan D5) : ajoutées telles quelles au prompt système de chaque
technique, elles ne doivent rien souffler des 30 questions ni de leurs réponses.

Trois contrôles, sur les deux fichiers entiers, puis sur la consigne et la fiche anglaise (D8 ;
T10.0), qui ne change que les identifiants du schéma et va dans le prompt des passes anglaises :
- aucun nom propre hors d'une liste blanche (types, catégories d'attaque, méthodes, schéma, outils,
  entités des exemples) ;
- aucune valeur de questions/attendu/, aucun nom des questions, du README ni de banc.toml, hors des
  valeurs de schéma permises ; aucune entité des exemples parmi eux ;
- aucun exemple dont la structure, littéraux et variables masqués, recoupe l'une des 27 requêtes
  (traduites, pour la fiche anglaise).
"""

import difflib
import re
import unicodedata
from pathlib import Path

import pytest

from banc import anglais, attendu, correspondance
from banc.questions import charger

RACINE = Path(__file__).resolve().parents[2]
QUESTIONS = RACINE / "questions"
FICHIERS = (QUESTIONS / "consigne.md", QUESTIONS / "fiche-schema.md")
TEXTE = "\n".join(fichier.read_text() for fichier in FICHIERS)
# Le prompt des passes anglaises : la même consigne, la fiche anglaise (T6.3).
FICHIERS_EN = (QUESTIONS / "consigne.md", QUESTIONS / "fiche-schema.en.md")
TEXTE_EN = "\n".join(fichier.read_text() for fichier in FICHIERS_EN)
TABLE = correspondance.charger()
# Les labels anglais (D8) : les seuls noms propres que la fiche anglaise ajoute ; les types de
# relation sont en capitales, les clés en minuscules.
SCHEMA_EN = tuple(TABLE.sens("en")["labels"].values())
README = (QUESTIONS / "README.md").read_text()
BANC = charger()

# Valeurs de schéma que la fiche cite, même si des réponses les contiennent (plan, D5) ; vérifiées
# dans la base en T7.3.
TYPES = (
    "Acier", "Combat", "Dragon", "Eau", "Électrik", "Fée", "Feu", "Glace", "Insecte",
    "Normal", "Plante", "Poison", "Psy", "Roche", "Sol", "Spectre", "Ténèbres", "Vol",
)  # fmt: skip
CATEGORIES = ("physique", "spéciale", "statut")
METHODES = ("Montée de niveau", "Œuf", "Enseigné", "Capsule", "Changement de Forme", "train")
SCHEMA = ("Pokemon", "Forme", "Type", "Attaque", "Talent", "Description", "Pokémon")
OUTILS = ("Neo4j", "Cypher", "PokéAPI", "Lucene")
# Termes de jeu que la fiche doit employer : les 18 attaques Z, noms en double (ROADMAP).
TERMES = ("Z",)
# Entités des exemples : choisies hors des questions, de leurs réponses et de leurs distracteurs.
EXEMPLES = (
    "Ectoplasma", "Deoxys", "Tartard", "Noarfang", "Tropius", "Ball’", "Écras’Face",
    "Osmose Équine", "Pokémon Ombre", "Chat Plante",
)  # fmt: skip
# Mots courants qui n'apparaissent qu'en tête de titre ou de phrase : les autres se reconnaissent
# à leur forme en minuscules, ailleurs dans les textes. Une nouvelle majuscule s'ajoute ici, relue.
FRANCAIS = (
    "Consigne", "Efficacité", "Exemples", "Interroge", "Quelques", "Recherche", "Termine",
)  # fmt: skip
PERMIS = {*TYPES, *CATEGORIES, *METHODES, *SCHEMA, *OUTILS, *TERMES}
ELISION = re.compile(r"\b(?:[cdjlmnst]|qu|jusqu|lorsqu|puisqu)['’]", re.IGNORECASE)


def mots(texte: str) -> tuple[str, ...]:
    """Mots d'un texte, pour les comparer : casse, accents, apostrophes et tirets ignorés."""
    decompose = unicodedata.normalize("NFKD", texte.casefold())
    sans_accents = "".join(c for c in decompose if not unicodedata.combining(c))
    return tuple(re.findall(r"\w+", sans_accents))


def contient(longue: tuple[str, ...], courte: tuple[str, ...]) -> bool:
    return any(longue[i : i + len(courte)] == courte for i in range(len(longue) - len(courte) + 1))


def jetons(texte: str) -> list[str]:
    """Mots d'un texte ; une élision (d', l', qu'…) se détache du mot qu'elle précède, l'apostrophe
    d'un nom (Écras’Face) reste dedans."""
    trouves = re.findall(r"[^\W\d_][\w’'-]*", ELISION.sub(" ", texte))
    return [jeton.rstrip("'-") for jeton in trouves]


def noms_propres(texte: str) -> list[str]:
    """Mots à majuscule initiale, hors sigles et mots-clés tout en capitales (MATCH, APPREND)."""
    return [j for j in jetons(texte) if j[0].isupper() and not (len(j) > 1 and j.isupper())]


def courants(texte: str) -> set[str]:
    """Mots écrits en minuscules quelque part : en tête de phrase, ils ne sont pas des noms."""
    return {jeton for jeton in jetons(texte) if jeton[0].islower()}


def noms_du_readme() -> set[str]:
    """Noms propres des tableaux du README (questions, premier calcul) et de ses règles."""
    cellules = re.findall(r"^\| Q\d+ +\| (.+?) +\| .+? +\| (.+?) +\|$", README, re.MULTILINE)
    regles = README.split("## Règles de réponse", 1)[1]
    # Le premier mot d'une cellule est un mot courant (Quels…) ou un nom déjà dans attendu/.
    noms = [nom for paire in cellules for cellule in paire for nom in noms_propres(cellule)[1:]]
    mots_courants = courants(README)
    return {nom for nom in [*noms, *noms_propres(regles)] if nom.lower() not in mots_courants}


def valeurs_interdites() -> set[str]:
    """Ce que la consigne et la fiche ne doivent pas citer : réponses, questions, distracteurs."""
    interdites: set[str] = set()
    for fichier in sorted((QUESTIONS / "attendu").glob("q*.txt")):
        feuilles = attendu.feuilles(attendu.lire(fichier.stem))
        interdites |= {f for f in feuilles if isinstance(f, str)}
    for question in BANC.questions.values():
        # Le premier mot d'une question est un mot courant (Quels, Pourquoi, Mon…).
        interdites |= set(noms_propres(question.texte)[1:])
        valeurs = (*question.attendus, *question.distracteurs)
        interdites |= {v for v in valeurs if isinstance(v, str)}
        interdites |= {*question.un_parmi, *question.scores}
        interdites |= set(noms_propres(question.preambule or "")[1:])
    interdites |= noms_du_readme()
    permis = {mots(p) for p in PERMIS}
    return {v for v in interdites if mots(v) and mots(v) not in permis}


INTERDITES = valeurs_interdites()


def exemples(texte: str = TEXTE) -> list[str]:
    return re.findall(r"```cypher\n(.*?)```", texte, re.DOTALL)


# --- Noms propres et valeurs ---------------------------------------------------------------------


def test_fichiers_entiers() -> None:
    # Les fichiers vont entiers dans le prompt : le contrôle porte sur tout leur texte.
    for fichier in (*FICHIERS, *FICHIERS_EN):
        assert fichier.read_text().strip()


@pytest.mark.parametrize(
    ("texte", "schema"), [(TEXTE, ()), (TEXTE_EN, SCHEMA_EN)], ids=["fr", "en"]
)
def test_noms_propres_en_liste_blanche(texte: str, schema: tuple[str, ...]) -> None:
    permis = {
        jeton for nom in (*PERMIS, *EXEMPLES, *FRANCAIS, *schema) for jeton in noms_propres(nom)
    }
    mots_courants = courants(texte) | courants(README)
    inconnus = {
        nom for nom in noms_propres(texte) if nom not in permis and nom.lower() not in mots_courants
    }
    assert not inconnus


@pytest.mark.parametrize("texte", [TEXTE, TEXTE_EN], ids=["fr", "en"])
def test_aucune_valeur_du_banc(texte: str) -> None:
    cites = sorted(v for v in INTERDITES if contient(mots(texte), mots(v)))
    assert not cites


@pytest.mark.parametrize("entite", EXEMPLES)
def test_entites_des_exemples_hors_du_banc(entite: str) -> None:
    for valeur in INTERDITES:
        assert not contient(mots(entite), mots(valeur)), valeur
        assert not contient(mots(valeur), mots(entite)), valeur


def test_le_controle_voit_le_banc() -> None:
    # Garde-fou du test lui-même : les noms du banc, des réponses et du README sont bien interdits.
    for nom in ("Dracofeu", "Sacha", "Évoli", "Pokémon Flamme", "Fracass’Tête", "Typhlosion"):
        assert mots(nom) in {mots(v) for v in INTERDITES}, nom
    for nom in ("Eau", "physique", "Montée de niveau"):
        assert mots(nom) not in {mots(v) for v in INTERDITES}, nom


# --- Exemples ------------------------------------------------------------------------------------

MOTS_CLES = {
    "match", "optional", "where", "with", "return", "order", "by", "limit", "skip", "as", "and",
    "or", "not", "in", "is", "null", "distinct", "desc", "asc", "call", "yield", "unwind",
    "exists", "count", "collect", "case", "when", "then", "else", "end", "contains", "starts",
    "ends", "true", "false",
}  # fmt: skip
JETON = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|\d+(?:\.\d+)?|\$?\w+|->|<-|\S")


def masquer(requete: str) -> list[str]:
    """Jetons d'une requête, littéraux et variables masqués ; restent les mots-clés, labels, types
    de relation, propriétés, fonctions et la ponctuation : la structure."""
    jetons = JETON.findall(re.sub(r"//[^\n]*", "", requete))
    masques = []
    for i, jeton in enumerate(jetons):
        precedent = jetons[i - 1] if i else ""
        suivant = jetons[i + 1] if i + 1 < len(jetons) else ""
        if jeton[0] in "'\"":
            masques.append("‹texte›")
        elif jeton[0].isdigit():
            masques.append("‹nombre›")
        elif not re.fullmatch(r"\$?\w+", jeton) or jeton.lower() in MOTS_CLES:
            masques.append(jeton.lower())
        elif precedent in {":", "."} or suivant == "(" or (suivant == ":" and precedent in "{,"):
            # Label, type de relation, propriété, fonction ou clé de dictionnaire : le schéma.
            masques.append(jeton)
        else:
            masques.append("‹variable›")
    return masques


def requetes_de_reference(langue: str = "fr") -> dict[str, list[str]]:
    """Les requêtes des 27 fichiers qNN.cypher, une par instruction ; en anglais, leur traduction
    (banc traduire)."""
    if langue == "fr":
        textes = {f.stem: f.read_text() for f in sorted(QUESTIONS.glob("q[0-9][0-9].cypher"))}
    else:
        traduits = anglais.traductions(TABLE)
        textes = {Path(c).stem: v for c, v in traduits.items() if re.fullmatch(r"q\d\d\.cypher", c)}
    requetes = {}
    for nom, brut in textes.items():
        texte = re.sub(r"//[^\n]*", "", brut)
        for rang, instruction in enumerate(i for i in texte.split(";") if i.strip()):
            requetes[f"{nom}.{rang + 1}"] = masquer(instruction)
    return requetes


REFERENCES = requetes_de_reference()
REFERENCES_EN = requetes_de_reference("en")
# Seuils mesurés sur les 31 instructions de référence (2026-10-08) : deux requêtes de même
# gabarit se ressemblent à 0,88 et plus (q01 et q27, les sémantiques entre elles) ; deux requêtes
# courtes sans rapport, jusqu'à 0,80 (q05 et q22, par la seule syntaxe). À 0,85, l'exemple reprend
# un gabarit ; ou bien il contient d'un bloc 80 % d'une requête de référence.
SEUIL_RESSEMBLANCE = 0.85
SEUIL_INCLUSION = 0.8


def test_six_a_huit_exemples() -> None:
    assert 6 <= len(exemples()) <= 8
    assert len(exemples(TEXTE_EN)) == len(exemples())
    assert len(REFERENCES) >= 27
    assert REFERENCES_EN.keys() == REFERENCES.keys()


def test_plein_texte_enseigne_avec_une_autre_faute() -> None:
    # D9 : la fiche montre la recherche approchée sur un autre nom que celui de Q19.
    recherches = [e for e in exemples() if "db.index.fulltext.queryNodes" in e]
    assert recherches
    assert all("dracofeu" not in e.lower() for e in recherches)
    assert any(re.search(r"'\w+~'", e) for e in recherches)


@pytest.mark.parametrize(
    ("exemple", "references"),
    [*((e, REFERENCES) for e in exemples()), *((e, REFERENCES_EN) for e in exemples(TEXTE_EN))],
    ids=[
        *(f"fr {' '.join(e.split())[:36]}" for e in exemples()),
        *(f"en {' '.join(e.split())[:36]}" for e in exemples(TEXTE_EN)),
    ],
)
def test_exemple_hors_des_requetes_de_reference(
    exemple: str, references: dict[str, list[str]]
) -> None:
    masque = masquer(exemple)
    for nom, reference in references.items():
        comparaison = difflib.SequenceMatcher(None, masque, reference, autojunk=False)
        bloc = comparaison.find_longest_match(0, len(masque), 0, len(reference)).size
        assert comparaison.ratio() < SEUIL_RESSEMBLANCE, nom
        assert bloc < SEUIL_INCLUSION * len(reference), nom


def test_masquage() -> None:
    # Même structure, autres littéraux et autres variables : même masque.
    modele = (
        "MATCH ({0}:Pokemon {{nom: '{1}'}})-[:A_POUR_FORME_PAR_DEFAUT]->({2}:Forme) "
        "RETURN {2}.statPv"
    )
    a = masquer(modele.format("p", "Abra", "f"))
    b = masquer(modele.format("x", "Kadabra", "y"))
    assert a == b
    assert "Pokemon" in a
    assert "A_POUR_FORME_PAR_DEFAUT" in a
    assert "statPv" in a
    assert "‹texte›" in a
