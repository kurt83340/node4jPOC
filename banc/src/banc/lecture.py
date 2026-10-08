"""Lecture des réponses d'un agent (plan 002, T2.1) : ce que la notation y cherche.

La consigne demande de finir par deux sections, « Réponse » et « Sources » (plan, D4). On les
retrouve ici, puis on lit leur texte en mots normalisés (casse, accents et apostrophes ignorés,
élisions détachées), en nombres, en espèces citées (liste tirée de la base,
questions/attendu/especes.txt), en requêtes et en descriptions citées. Pour Q2, les 6 noms de
l'équipe proposée deviennent une liste littérale de Cypher, validée puis échappée, que
scripts/questions.sh --controle revérifie : jamais un texte libre dans -P (plan, D6).
"""

import re
import unicodedata
from collections.abc import Collection, Iterable, Sequence
from dataclasses import dataclass

from banc import attendu

# Une ligne d'en-tête : marque de liste, titre ou gras facultatifs, le mot de la section,
# deux-points ; ou bien le seul mot de la section, en titre ou en gras, sur sa ligne.
# « Réponse rapide : » n'en est pas un.
_SECTION = r"(?P<nom>r[ée]ponse(?:\s+courte)?|sources?)"
_EMPHASE = r"(?:\*\*|__|\*|_)?"
EN_TETE = re.compile(
    rf"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:#{{1,6}}\s+)?{_EMPHASE}\s*{_SECTION}\s*{_EMPHASE}\s*:"
    rf"\s*{_EMPHASE}(?P<reste>.*)$",
    re.IGNORECASE,
)
EN_TETE_SEUL = re.compile(
    rf"^\s*(?=#|\*\*|__)(?:#{{1,6}}\s+)?{_EMPHASE}{_SECTION}{_EMPHASE}\s*:?\s*$", re.IGNORECASE
)
CLOTURE = re.compile(r"^\s*```")
# Un mot : lettres et chiffres ; ♀ et ♂ y restent, sinon Nidoran♀ et Nidoran♂ se confondraient.
MOT = re.compile(r"(?:[^\W_]|[♀♂])+")
# Un nombre isolé, avec ses milliers séparés par une espace (1 025) et sa décimale (0,541 ou 0.541).
NOMBRE = re.compile(
    r"(?<![\w.,])(?P<entier>\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,](?P<decimale>\d+))?(?!\w)"
)
BLOC = re.compile(r"^[ \t]*```[^\n]*\n(?P<code>.*?)^[ \t]*```[ \t]*$", re.MULTILINE | re.DOTALL)
CODE_EN_LIGNE = re.compile(r"`([^`\n]+)`")
CLAUSE = re.compile(r"^\s*(?:OPTIONAL\s+MATCH|MATCH|CALL|WITH|UNWIND|RETURN)\b", re.IGNORECASE)
MARQUE_DE_LISTE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
FIN_D_INSTRUCTION = re.compile(r";\s*(?:\n|$)")
CHAINE = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
CITATION = re.compile(r"«([^»]*)»|“([^”]*)”|\"([^\"\n]*)\"")
ELLIPSE = re.compile(r"\[\s*(?:…|\.\.\.)\s*\]|…|\.\.\.")
# Une description citée : au moins 4 mots. « Pokémon Flamme » ou « Feu » citent une valeur, pas un
# texte.
MOTS_D_UNE_DESCRIPTION = 4
TAILLE_EQUIPE = 6
# Caractères permis dans un nom passé à Cypher : ceux des 1 025 noms réels (lettres, chiffres,
# espace, point, deux-points, tiret, ♀ et ♂ ; relevé du 2026-10-08) ; ni apostrophe, ni
# antislash, ni caractère de contrôle.
NOM_PERMIS = re.compile(r"[^\W_](?:[^\W_]|[ .:♀♂-])*")
LONGUEUR_MAX = 30


class LectureError(Exception):
    """Liste d'espèces incohérente, ou noms impropres à une liste littérale de Cypher."""


@dataclass(frozen=True)
class Sections:
    """Les deux sections de fin d'une réponse ; None si l'agent ne l'a pas écrite (ou vide)."""

    reponse: str | None
    sources: str | None


def sections(texte: str) -> Sections:
    """Sections « Réponse » et « Sources » : la dernière de chaque sorte, jusqu'à l'en-tête suivant.

    La consigne demande de terminer par elles : un brouillon plus haut ne compte pas. Un en-tête
    dans un bloc de code (commentaire Cypher) est ignoré ; l'ordre des deux sections est libre.
    """
    lignes = texte.splitlines()
    en_tetes: list[tuple[int, str, str]] = []
    dans_un_bloc = False
    for numero, ligne in enumerate(lignes):
        if CLOTURE.match(ligne):
            dans_un_bloc = not dans_un_bloc
            continue
        if dans_un_bloc:
            continue
        trouve = EN_TETE.match(ligne) or EN_TETE_SEUL.match(ligne)
        if trouve is not None:
            nom = "reponse" if trouve["nom"].lower().startswith("r") else "sources"
            reste = trouve.groupdict().get("reste") or ""
            en_tetes.append((numero, nom, reste))
    textes: dict[str, str | None] = {"reponse": None, "sources": None}
    for rang, (numero, nom, reste) in enumerate(en_tetes):
        fin = en_tetes[rang + 1][0] if rang + 1 < len(en_tetes) else len(lignes)
        texte_section = "\n".join([reste, *lignes[numero + 1 : fin]]).strip()
        textes[nom] = texte_section or None
    return Sections(textes["reponse"], textes["sources"])


def mots(texte: str) -> tuple[str, ...]:
    """Mots d'un texte, pour comparer des noms : casse et accents ignorés, œ lu oe.

    Apostrophes, tirets et ponctuation séparent les mots : une élision se détache du nom qu'elle
    précède (« d'Évoli » : d, evoli) et un nom à apostrophe se lit pareil des deux côtés
    (« Fracass’Tête » comme « Fracass'Tête » : fracass, tete).
    """
    plie = texte.casefold().replace("œ", "oe").replace("æ", "ae")
    decompose = unicodedata.normalize("NFKD", plie)
    return tuple(MOT.findall("".join(c for c in decompose if not unicodedata.combining(c))))


def contient(texte: Sequence[str], nom: Sequence[str]) -> bool:
    """Le nom figure-t-il dans le texte (leurs mots), en mots entiers et d'un seul tenant ?"""
    taille = len(nom)
    if not taille:
        return False
    cible = tuple(nom)
    return any(tuple(texte[i : i + taille]) == cible for i in range(len(texte) - taille + 1))


def nombres(texte: str) -> list[float]:
    """Nombres isolés : 100 et 1000 sont deux nombres, Q7 et Porygon2 n'en contiennent pas."""
    trouves = []
    for nombre in NOMBRE.finditer(texte):
        entier = re.sub(r"\D", "", nombre["entier"])
        decimale = nombre["decimale"]
        trouves.append(float(f"{entier}.{decimale}" if decimale else entier))
    return trouves


@dataclass(frozen=True)
class Citation:
    """Une espèce citée : son nom exact, et sa place dans le texte (indices de mots, fin exclue)."""

    nom: str
    debut: int
    fin: int


class Especes:
    """Noms d'espèces, reconnus dans un texte par la plus longue correspondance en mots entiers."""

    def __init__(self, noms: Iterable[str]) -> None:
        formes: dict[tuple[str, ...], str] = {}
        for nom in noms:
            forme = mots(nom)
            if not forme:
                raise LectureError(f"{nom!r} : nom vide une fois normalisé")
            if formes.setdefault(forme, nom) != nom:
                raise LectureError(f"{formes[forme]} et {nom} se confondent une fois normalisés")
        self._formes = formes
        self._plus_long = max((len(forme) for forme in formes), default=0)
        self.noms = frozenset(formes.values())

    @classmethod
    def charger(cls) -> Especes:
        """La liste tirée de la base : questions/attendu/especes.txt, rejouée par
        scripts/questions.sh --verifier."""
        [tableau] = attendu.lire("especes")
        return cls(str(ligne["pokemon"]) for ligne in tableau.lignes)

    def citations(self, texte: Sequence[str]) -> list[Citation]:
        """Espèces citées dans un texte (ses mots), de gauche à droite : Porygon-Z avant Porygon."""
        trouvees = []
        position = 0
        while position < len(texte):
            for taille in range(min(self._plus_long, len(texte) - position), 0, -1):
                nom = self._formes.get(tuple(texte[position : position + taille]))
                if nom is not None:
                    trouvees.append(Citation(nom, position, position + taille))
                    position += taille
                    break
            else:
                position += 1
        return trouvees

    def citees(self, texte: str) -> list[str]:
        """Noms exacts des espèces citées, une fois chacune, dans l'ordre de première mention."""
        return list(dict.fromkeys(citation.nom for citation in self.citations(mots(texte))))


def requetes_citees(sources: str) -> list[str]:
    """Requêtes de la section « Sources » : blocs de code (une requête par instruction) et code en
    ligne qui commence par une clause ; à défaut, les paragraphes qui commencent par une clause."""
    requetes = []
    for bloc in BLOC.finditer(sources):
        requetes += [r.strip() for r in FIN_D_INSTRUCTION.split(bloc["code"]) if r.strip()]
    hors_blocs = BLOC.sub("", sources)
    requetes += [code.strip() for code in CODE_EN_LIGNE.findall(hors_blocs) if CLAUSE.match(code)]
    if requetes:
        return requetes
    for paragraphe in re.split(r"\n\s*\n", hors_blocs):
        texte = MARQUE_DE_LISTE.sub("", paragraphe.strip(), count=1)
        if CLAUSE.match(texte):
            requetes.append(texte.strip().removesuffix(";").strip())
    return requetes


def meme_requete(citee: str, executee: str) -> bool:
    """Même requête aux espaces près : hors des chaînes, ni les blancs ni un « ; » final ne
    comptent."""
    return _sans_blancs(citee) == _sans_blancs(executee)


def _sans_blancs(requete: str) -> str:
    morceaux = []
    position = 0
    for chaine in CHAINE.finditer(requete):
        morceaux += [re.sub(r"\s+", "", requete[position : chaine.start()]), chaine.group()]
        position = chaine.end()
    morceaux.append(re.sub(r"\s+", "", requete[position:]))
    return "".join(morceaux).removesuffix(";")


def descriptions_citees(sources: str) -> list[str]:
    """Passages cités entre guillemets (« », “ ”, " "), hors code, coupés à leurs points de
    suspension : chaque morceau d'au moins 4 mots doit avoir été renvoyé par une requête du tour
    (plan, D4)."""
    texte = CODE_EN_LIGNE.sub("", BLOC.sub("", sources))
    morceaux: list[str] = []
    for citation in CITATION.finditer(texte):
        passage = next(groupe for groupe in citation.groups() if groupe is not None)
        morceaux.extend(
            morceau.strip()
            for morceau in ELLIPSE.split(passage)
            if len(mots(morceau)) >= MOTS_D_UNE_DESCRIPTION
        )
    return morceaux


def equipe(reponse: str, especes: Especes, reference: Collection[str]) -> tuple[str, ...] | None:
    """Les 6 espèces proposées à Q2, à leur orthographe exacte ; None si on ne peut les isoler.

    Les espèces de l'équipe de référence, citées dans une explication, sont écartées quand il y en a
    plus de 6 ; sans exactement 6 espèces, la réponse passe « à revoir » (plan, D6).
    """
    citees = especes.citees(reponse)
    if len(citees) != TAILLE_EQUIPE:
        citees = [nom for nom in citees if nom not in reference]
    return tuple(citees) if len(citees) == TAILLE_EQUIPE else None


def nom_permis(nom: str) -> bool:
    """Un nom peut-il entrer dans une liste littérale de Cypher ? Caractères des noms réels
    seulement."""
    return len(nom) <= LONGUEUR_MAX and NOM_PERMIS.fullmatch(nom) is not None


def chaine_cypher(texte: str) -> str:
    """Chaîne littérale de Cypher entre apostrophes, antislash et apostrophe échappés."""
    return "'" + texte.replace("\\", "\\\\").replace("'", "\\'") + "'"


def liste_cypher(noms: Sequence[str]) -> str:
    """Liste littérale de Cypher des 6 noms de Q2 ($proposee de q02.cypher), validés puis échappés.

    Sa forme est celle que scripts/questions.sh --controle exige : ['Nom', 'Nom', …].
    """
    if len(noms) != TAILLE_EQUIPE or len(set(noms)) != TAILLE_EQUIPE:
        raise LectureError(f"{TAILLE_EQUIPE} noms distincts attendus : {list(noms)}")
    for nom in noms:
        if not nom_permis(nom):
            raise LectureError(f"{nom!r} : caractère non permis dans un nom, ou nom trop long")
    return "[" + ", ".join(chaine_cypher(nom) for nom in noms) + "]"
