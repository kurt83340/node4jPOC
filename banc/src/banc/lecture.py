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
from itertools import pairwise

from banc import attendu

# Une ligne d'en-tête : marque de liste, titre ou gras facultatifs, le mot de la section,
# deux-points ; ou bien le seul mot de la section, en titre ou en gras, sur sa ligne.
# « Réponse rapide : » n'en est pas un. Les sources prennent un mot de plus (« Sources utilisées »,
# « Requêtes exécutées », « Source(s) ») : les variantes des agents, relevées en revue adverse.
_SECTION = (
    r"(?P<nom>r[ée]ponses?(?:\s+(?:courte|finale))?"
    r"|sources?(?:\s*\(s\))?(?:\s+[^\W\d_]+)?|requ[êe]tes?(?:\s+[^\W\d_]+)?)"
)
REPONSE = re.compile(r"r[ée]ponse", re.IGNORECASE)
_EMPHASE = r"(?:\*\*|__|\*|_)?"
EN_TETE = re.compile(
    rf"^\s*(?:[-*+]\s+|\d+[.)]\s+)?(?:#{{1,6}}\s+)?{_EMPHASE}\s*{_SECTION}\s*{_EMPHASE}\s*:"
    rf"\s*{_EMPHASE}(?P<reste>.*)$",
    re.IGNORECASE,
)
EN_TETE_SEUL = re.compile(
    rf"^\s*(?=#|\*\*|__)(?:#{{1,6}}\s+)?{_EMPHASE}{_SECTION}{_EMPHASE}\s*:?\s*$", re.IGNORECASE
)
# Une clôture de bloc seule sur sa ligne (```cypher) : « ```RETURN 1``` » n'ouvre aucun bloc.
CLOTURE = re.compile(r"^\s*```\s*[\w+-]*\s*$")
# Un mot : lettres et chiffres ; ♀ et ♂ y restent, sinon Nidoran♀ et Nidoran♂ se confondraient.
MOT = re.compile(r"(?:[^\W_]|[♀♂])+")
# Ce qui peut séparer les mots d'un même nom d'espèce : M. Mime, Ho-Oh, Type:0, Mime Jr.
LIAISON = re.compile(r"[ .:'’-]{1,3}")
TIRETS = "-‐‑"
# Un nombre isolé, avec ses milliers séparés par une espace (1 025) et sa décimale (0,541 ou 0.541).
NOMBRE = re.compile(
    r"(?<![\w.,])(?P<entier>\d{1,3}(?:[ \u00a0\u202f]\d{3})+|\d+)(?:[.,](?P<decimale>\d+))?(?!\w)"
)
BLOC = re.compile(
    r"^[ \t]*```[ \t]*[\w+-]*[ \t]*\n(?P<code>.*?)^[ \t]*```[ \t]*$", re.MULTILINE | re.DOTALL
)
CODE_EN_LIGNE = re.compile(r"`([^`\n]+)`")
_CLAUSES = r"(?:OPTIONAL\s+MATCH|MATCH|CALL|WITH|UNWIND|RETURN)\b"
CLAUSE = re.compile(rf"^\s*{_CLAUSES}", re.IGNORECASE)
# Du code en ligne qui ressemble à du Cypher (une clause, ou ses signes) : retiré de la réponse.
# Un nom mis en forme de code (`Dracaufeu`) reste un nom.
CYPHERESQUE = re.compile(rf"^\s*{_CLAUSES}|[(){{}}\[\]=$]", re.IGNORECASE)
MARQUE_DE_LISTE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
ETIQUETTE = re.compile(
    r"^\s*(?:\*\*)?requ[êe]tes?(?:\s+[^\W\d_]+)?\s*(?:\*\*)?\s*:\s*(?:\*\*)?\s*", re.IGNORECASE
)
FIN_D_INSTRUCTION = re.compile(r";\s*(?:\n|$)")
# Deux requêtes d'un même bloc séparées par une ligne vide, sans « ; ».
LIGNE_VIDE_PUIS_CLAUSE = re.compile(rf"\n\s*\n(?=\s*{_CLAUSES})", re.IGNORECASE)
# Morceaux d'une requête, pour la comparer aux espaces près : commentaire, chaîne, blancs, le reste.
MORCEAU_CYPHER = re.compile(
    r"//[^\n]*|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|\s+|[^\s'\"/]+|[\s\S]"
)
# Une citation : entre guillemets, en bloc de citation (« > ») ou en italique.
CITATION = re.compile(
    r"«([^»]*)»|“([^”]*)”|\"([^\"\n]*)\"|^[ \t]*>[ \t]?(.+)$"
    r"|(?<![*\w])\*(?!\*)([^*\n]+)\*(?!\*)|(?<![_\w])_([^_\n]+)_(?!\w)",
    re.MULTILINE,
)
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
class Jeton:
    """Un mot normalisé, et sa place dans le texte (NFC), en caractères, fin exclue."""

    mot: str
    debut: int
    fin: int


@dataclass(frozen=True)
class Sections:
    """Les deux sections de fin d'une réponse ; None si l'agent ne l'a pas écrite (ou vide)."""

    reponse: str | None
    sources: str | None


def sections(texte: str) -> Sections:
    """Sections « Réponse » et « Sources », chacune jusqu'à l'en-tête suivant.

    La consigne demande de terminer par elles : la dernière « Réponse » compte, un brouillon plus
    haut non. « Sources » réunit les sections de sources qui la suivent (« Sources : », puis
    « Requête : »…), ou, à défaut, celles qui la précèdent depuis la « Réponse » d'avant. Un
    en-tête dans un bloc de code est ignoré.
    """
    lignes = texte.splitlines()
    en_tetes: list[tuple[int, bool, str]] = []
    dans_un_bloc = False
    for numero, ligne in enumerate(lignes):
        if CLOTURE.match(ligne):
            dans_un_bloc = not dans_un_bloc
            continue
        if dans_un_bloc:
            continue
        trouve = EN_TETE.match(ligne) or EN_TETE_SEUL.match(ligne)
        if trouve is not None:
            reste = trouve.groupdict().get("reste") or ""
            en_tetes.append((numero, REPONSE.match(trouve["nom"]) is not None, reste))
    textes = []
    for rang, (numero, _, reste) in enumerate(en_tetes):
        fin = en_tetes[rang + 1][0] if rang + 1 < len(en_tetes) else len(lignes)
        textes.append("\n".join([reste, *lignes[numero + 1 : fin]]).strip())
    reponses = [rang for rang, (_, est_reponse, _) in enumerate(en_tetes) if est_reponse]
    if not reponses:
        return Sections(None, _joindre(textes))
    derniere = reponses[-1]
    apres = textes[derniere + 1 :]
    avant = textes[reponses[-2] + 1 if len(reponses) > 1 else 0 : derniere]
    return Sections(textes[derniere] or None, _joindre(apres) or _joindre(avant))


def _joindre(textes: Sequence[str]) -> str | None:
    return "\n\n".join(texte for texte in textes if texte) or None


def prose(texte: str) -> str:
    """Le texte sans son code, en NFC : blocs retirés, code en ligne retiré s'il ressemble à du
    Cypher. Une valeur tirée d'une requête recopiée dans la réponse ne compte pas comme dite."""
    sans_blocs = BLOC.sub("\n", texte)
    sans_code = CODE_EN_LIGNE.sub(lambda m: " " if CYPHERESQUE.search(m[1]) else m[1], sans_blocs)
    return unicodedata.normalize("NFC", sans_code)


def jetons(texte: str) -> list[Jeton]:
    """Mots d'un texte (mis en NFC), chacun normalisé et situé : casse et accents ignorés, œ lu oe.

    Apostrophes, tirets et ponctuation séparent les mots : une élision se détache du nom qu'elle
    précède (« d'Évoli » : d, evoli) et un nom à apostrophe se lit pareil des deux côtés
    (« Fracass’Tête » comme « Fracass'Tête » : fracass, tete).
    """
    brut = unicodedata.normalize("NFC", texte)
    return [Jeton(_normaliser(m.group()), m.start(), m.end()) for m in MOT.finditer(brut)]


def _normaliser(mot: str) -> str:
    plie = mot.casefold().replace("œ", "oe").replace("æ", "ae")
    return "".join(c for c in unicodedata.normalize("NFKD", plie) if not unicodedata.combining(c))


def mots(texte: str) -> tuple[str, ...]:
    """Mots normalisés d'un texte (voir jetons), pour comparer des noms."""
    return tuple(jeton.mot for jeton in jetons(texte))


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
    """Une espèce citée : son nom exact, sa place dans le texte (NFC, en caractères, fin exclue),
    et si elle est nommée comme une forme (Méga-Dracaufeu, Raichu d'Alola, Motisma Lavage)."""

    nom: str
    debut: int
    fin: int
    forme: bool = False


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

    def citations(self, texte: str) -> list[Citation]:
        """Espèces citées dans un texte, de gauche à droite, par la plus longue correspondance :
        Porygon-Z avant Porygon. Un nom collé par un tiret au mot suivant n'est pas une citation
        (Draco-Météore est une attaque)."""
        brut = unicodedata.normalize("NFC", texte)
        liste = jetons(brut)
        trouvees = []
        position = 0
        while position < len(liste):
            taille, nom = self._plus_longue(brut, liste, position)
            if nom is None:
                position += 1
                continue
            debut, fin = liste[position].debut, liste[position + taille - 1].fin
            if not _collee(brut, fin):
                trouvees.append(Citation(nom, debut, fin, _en_forme(brut, debut, fin)))
            position += taille
        return trouvees

    def _plus_longue(
        self, brut: str, liste: Sequence[Jeton], position: int
    ) -> tuple[int, str | None]:
        for taille in range(min(self._plus_long, len(liste) - position), 0, -1):
            morceau = liste[position : position + taille]
            nom = self._formes.get(tuple(jeton.mot for jeton in morceau))
            liee = all(
                LIAISON.fullmatch(brut[gauche.fin : droite.debut])
                for gauche, droite in pairwise(morceau)
            )
            if nom is not None and liee:
                return taille, nom
        return 1, None

    def citees(self, texte: str) -> list[str]:
        """Noms exacts des espèces citées, une fois chacune, dans l'ordre de première mention."""
        return list(dict.fromkeys(citation.nom for citation in self.citations(texte)))


def _collee(brut: str, fin: int) -> bool:
    """Le nom est-il collé par un tiret au mot qui le suit (Draco-Météore) ?"""
    return brut[fin : fin + 1] in TIRETS and brut[fin + 1 : fin + 2].isalpha()


def _en_forme(brut: str, debut: int, fin: int) -> bool:
    """Le nom est-il celui d'une forme : précédé d'un mot collé par un tiret (Méga-Dracaufeu,
    Primo-Groudon), ou suivi d'un mot à majuscule (Motisma Lavage), au besoin après d', de ou du
    (Raichu d'Alola) ?"""
    if debut >= 2 and brut[debut - 1] in TIRETS and brut[debut - 2].isalpha():
        return True
    suite = re.match(r"[ \t]+(?:(?:d['’]|de[ \t]|du[ \t])[ \t]*)?(\w)", brut[fin:])
    return suite is not None and suite[1].isupper()


def requetes_citees(sources: str) -> list[str]:
    """Requêtes de la section « Sources » : blocs de code (une requête par instruction ; des
    morceaux séparés par une ligne vide comptent aussi), code en ligne qui commence par une clause,
    et paragraphes qui commencent par une clause, au besoin après « Requête : »."""
    requetes = []
    for bloc in BLOC.finditer(sources):
        for instruction in FIN_D_INSTRUCTION.split(bloc["code"]):
            morceaux = [m.strip() for m in LIGNE_VIDE_PUIS_CLAUSE.split(instruction) if m.strip()]
            requetes += [instruction.strip()] * bool(instruction.strip())
            requetes += morceaux if len(morceaux) > 1 else []
    hors_blocs = BLOC.sub("\n", sources)
    requetes += [code.strip() for code in CODE_EN_LIGNE.findall(hors_blocs) if CLAUSE.match(code)]
    for paragraphe in re.split(r"\n\s*\n", CODE_EN_LIGNE.sub(" ", hors_blocs)):
        texte = ETIQUETTE.sub("", MARQUE_DE_LISTE.sub("", paragraphe.strip(), count=1), count=1)
        if CLAUSE.match(texte):
            requetes.append(texte.strip().removesuffix(";").strip())
    return requetes


def meme_requete(citee: str, executee: str) -> bool:
    """Même requête aux espaces près : hors des chaînes, ni les blancs, ni les commentaires //, ni
    un « ; » final ne comptent."""
    return _sans_blancs(citee) == _sans_blancs(executee)


def _sans_blancs(requete: str) -> str:
    morceaux = (m.group() for m in MORCEAU_CYPHER.finditer(requete))
    gardes = (m for m in morceaux if not m.startswith("//") and not m.isspace())
    return "".join(gardes).removesuffix(";")


def descriptions_citees(sources: str) -> list[str]:
    """Passages cités entre guillemets (« », “ ”, " "), en bloc de citation (« > ») ou en
    italique, hors code, coupés à leurs points de suspension : chaque morceau d'au moins 4 mots
    doit avoir été renvoyé par une requête du tour (plan, D4)."""
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
    """Les 6 espèces proposées à Q2, à leur orthographe exacte ; None si on ne peut les isoler sans
    doute : la réponse passe alors « à revoir », et rien n'est envoyé à la base (plan, D6).

    Les espèces de l'équipe de référence, citées dans une explication, sont écartées quand il y en a
    plus de 6. Doutes : pas exactement 6 espèces, un membre de la référence parmi elles (cité
    dans l'explication à la place d'un nom non reconnu ?), ou l'une nommée comme une forme
    (le contrôle lirait sa forme par défaut).
    """
    citations = especes.citations(reponse)
    noms = list(dict.fromkeys(citation.nom for citation in citations))
    if len(noms) != TAILLE_EQUIPE:
        noms = [nom for nom in noms if nom not in reference]
    if len(noms) != TAILLE_EQUIPE or any(nom in reference for nom in noms):
        return None
    if any(citation.forme for citation in citations if citation.nom in noms):
        return None
    return tuple(noms)


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
