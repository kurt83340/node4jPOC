"""Traduction du Cypher vers le schéma anglais, et retour (plan 002, D8).

Le texte est découpé en jetons (espaces, commentaires, littéraux, noms, symboles), puis chaque nom
est jugé par sa place : label ou type après les deux-points d'un motif ou d'un prédicat (et après |
ou & dans une expression de labels), clé après un point ou dans la map d'un motif, nom de contrainte
ou d'index après CONSTRAINT ou INDEX. Tout le reste ne change pas : alias, variables, clés d'une map
hors motif, paramètres, commentaires, littéraux et expressions régulières, sauf un littéral qui est
en entier un identifiant du schéma (`'noms_plein_texte'` dans un appel de l'index plein texte, une
liste de labels).

Écrit pour le corpus du banc (27 requêtes, liste des espèces, fiche et ses vérifications,
contraintes) : une clé de map hors motif lue par un point se traduirait, sans que sa map change ; le
corpus n'en a aucune qui porte le nom d'une clé du schéma (tests/test_traduction.py le vérifie).
"""

import re
from dataclasses import dataclass

from banc.correspondance import GENRES, Correspondance

JETON = re.compile(
    r"""(?P<espace>\s+)
    |(?P<commentaire>//[^\n]*|/\*.*?\*/)
    |(?P<chaine>'(?:[^'\\]|\\.)*'|"(?:[^"\\]|\\.)*")
    |(?P<echappe>`(?:[^`]|``)*`)
    |(?P<parametre>\$(?:[^\W\d]\w*|\d+))
    |(?P<nombre>\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)
    |(?P<nom>[^\W\d]\w*)
    |(?P<symbole>::|\.\.|->|<-|=~|<>|<=|>=|\+=|.)""",
    re.VERBOSE | re.DOTALL,
)
# Mots qui ouvrent une sous-requête entre accolades, et non une map.
BLOCS = frozenset({"CALL", "COLLECT", "COUNT", "EXISTS"})
# Le nom d'une contrainte ou d'un index suit CONSTRAINT ou INDEX, eux-mêmes après CREATE, DROP ou le
# genre de l'index ; une commande sans nom enchaîne sur IF, FOR ou ON.
NOMMANTS = frozenset({"CONSTRAINT", "INDEX"})
AVANT_NOMMANT = frozenset(
    {"CREATE", "DROP", "FULLTEXT", "RANGE", "TEXT", "POINT", "VECTOR", "LOOKUP"}
)
SANS_NOM = frozenset({"IF", "FOR", "ON"})


class TraductionError(Exception):
    """Un nom à une place du schéma (label, type, index) que la table ne connaît pas."""


@dataclass(frozen=True)
class Jeton:
    """Un morceau du texte : son genre (espace, commentaire, chaine, echappe, parametre, nombre,
    nom, symbole) et son texte exact."""

    genre: str
    texte: str

    @property
    def nom(self) -> str | None:
        """Le nom porté : celui d'un nom, ou celui d'un nom entre accents graves."""
        if self.genre == "nom":
            return self.texte
        if self.genre == "echappe":
            return self.texte[1:-1].replace("``", "`")
        return None


def jetons(cypher: str) -> list[Jeton]:
    """Le texte en jetons, sans perte : leurs textes mis bout à bout le redonnent."""
    return [Jeton(str(m.lastgroup), m.group()) for m in JETON.finditer(cypher)]


def traduire(cypher: str, table: Correspondance, langue: str) -> str:
    """Le texte Cypher avec les identifiants du schéma dans cette langue (en ou fr)."""
    return _Traducteur(table, langue).traduire(jetons(cypher))


def sans_commentaires(cypher: str) -> str:
    """Le texte sans ses commentaires, ni les lignes qu'ils laissent vides ; au plus une ligne vide
    entre deux blocs."""
    texte = "".join(j.texte for j in jetons(cypher) if j.genre != "commentaire")
    sortie: list[str] = []
    for ligne in (ligne.rstrip() for ligne in texte.splitlines()):
        if ligne or (sortie and sortie[-1]):
            sortie.append(ligne)
    return "\n".join(sortie).strip("\n") + "\n"


class _Traducteur:
    """Un passage sur les jetons, avec la pile des parenthèses, crochets et accolades ouverts."""

    def __init__(self, table: Correspondance, langue: str) -> None:
        self.table = table
        self.langue = langue
        self.sens = table.sens(langue)
        self.pile: list[str] = []
        self.etiquette = False  # le prochain nom est un label ou un type
        self.apres_etiquette = False  # le dernier jeton significatif était un label ou un type
        self.ferme_call = False  # la dernière parenthèse fermée était celle d'un CALL (…)

    def traduire(self, tous: list[Jeton]) -> str:
        significatifs = [j for j in tous if j.genre not in {"espace", "commentaire"}]
        sortie: list[str] = []
        rang = 0
        for jeton in tous:
            if jeton.genre in {"espace", "commentaire"}:
                sortie.append(jeton.texte)
                continue
            sortie.append(self._jeton(significatifs, rang))
            rang += 1
        return "".join(sortie)

    def _jeton(self, significatifs: list[Jeton], rang: int) -> str:
        jeton = significatifs[rang]
        avant = significatifs[rang - 1] if rang >= 1 else None
        avant2 = significatifs[rang - 2] if rang >= 2 else None
        etiquette, self.etiquette = self.etiquette, False
        apres_etiquette, self.apres_etiquette = self.apres_etiquette, False
        if jeton.genre == "chaine":
            return self._litteral(jeton.texte)
        if (nom := jeton.nom) is not None:
            return self._nom(jeton, nom, significatifs, rang, etiquette=etiquette)
        if jeton.genre == "symbole":
            self._symbole(jeton.texte, avant, avant2, etiquette=etiquette, apres=apres_etiquette)
        return jeton.texte

    def _nom(
        self, jeton: Jeton, nom: str, significatifs: list[Jeton], rang: int, *, etiquette: bool
    ) -> str:
        avant = significatifs[rang - 1] if rang >= 1 else None
        avant2 = significatifs[rang - 2] if rang >= 2 else None
        if etiquette:
            self.apres_etiquette = True
            return self._ecrire(jeton, self._schema(nom))
        if _symbole(avant, ".") and not _appel(significatifs, rang):
            return self._ecrire(jeton, self._cle(nom))
        if self.pile[-1:] == ["{motif"] and (_symbole(avant, "{") or _symbole(avant, ",")):
            return self._ecrire(jeton, self._cle(nom))
        if (
            _mot(avant) in NOMMANTS
            and _mot(avant2) in AVANT_NOMMANT
            and nom.upper() not in SANS_NOM
        ):
            return self._ecrire(jeton, self._index(nom))
        return jeton.texte

    def _symbole(
        self, texte: str, avant: Jeton | None, avant2: Jeton | None, *, etiquette: bool, apres: bool
    ) -> None:
        match texte:
            case ":":
                self.etiquette = self._deux_points_d_etiquette(avant, avant2, apres=apres)
            case "|" | "&":
                self.etiquette = apres
            case "!":
                self.etiquette = etiquette
            case "(":
                self.pile.append("(call" if _mot(avant) == "CALL" else "(")
            case "[":
                self.pile.append("[")
            case "{":
                self.pile.append(self._accolade(avant, avant2, apres=apres))
            case ")" | "]" | "}":
                ferme = self.pile.pop() if self.pile else ""
                self.ferme_call = ferme == "(call"

    def _deux_points_d_etiquette(
        self, avant: Jeton | None, avant2: Jeton | None, *, apres: bool
    ) -> bool:
        """Les deux-points d'un label ou d'un type, et non ceux d'une clé de map."""
        if apres or _symbole(avant, "(") or _symbole(avant, "["):
            return True
        if avant is None or avant.nom is None:
            return False
        dans_une_map = self.pile[-1:] in (["{motif"], ["{map"])
        return not (dans_une_map and (_symbole(avant2, "{") or _symbole(avant2, ",")))

    def _accolade(self, avant: Jeton | None, avant2: Jeton | None, *, apres: bool) -> str:
        """Une sous-requête, la map d'un motif (ses clés sont des clés du schéma), ou une map."""
        if _mot(avant) in BLOCS:
            return "{bloc"
        if _symbole(avant, ")") and self.ferme_call:
            return "{bloc"
        if apres or (
            avant is not None
            and avant.nom is not None
            and (_symbole(avant2, "(") or _symbole(avant2, "["))
        ):
            return "{motif"
        return "{map"

    def _litteral(self, texte: str) -> str:
        """Un littéral reste tel quel, sauf s'il est en entier un identifiant du schéma."""
        contenu = texte[1:-1]
        for genre in GENRES:
            if (nom := self.table.nom(genre, contenu, self.langue)) is not None:
                return texte[0] + nom + texte[-1]
        return texte

    def _schema(self, nom: str) -> str:
        for genre in ("labels", "relations"):
            if (traduit := self.table.nom(genre, nom, self.langue)) is not None:
                return traduit
        raise TraductionError(f"label ou type inconnu : {nom!r}")

    def _cle(self, nom: str) -> str:
        return self.table.nom("proprietes", nom, self.langue) or nom

    def _index(self, nom: str) -> str:
        if (traduit := self.table.nom("index", nom, self.langue)) is None:
            raise TraductionError(f"index inconnu : {nom!r}")
        return traduit

    @staticmethod
    def _ecrire(jeton: Jeton, nom: str) -> str:
        if jeton.genre == "echappe":
            return "`" + nom.replace("`", "``") + "`"
        return nom


def _symbole(jeton: Jeton | None, texte: str) -> bool:
    return jeton is not None and jeton.genre == "symbole" and jeton.texte == texte


def _mot(jeton: Jeton | None) -> str:
    """Le nom d'un jeton en majuscules (mot-clé), ou rien."""
    return (jeton.nom or "").upper() if jeton is not None and jeton.genre == "nom" else ""


def _appel(significatifs: list[Jeton], rang: int) -> bool:
    """Vrai si le nom fait partie d'un nom pointé de fonction ou de procédure (db.index.…( ) : la
    suite de « .nom » finit par une parenthèse ouvrante."""
    suivant = rang + 1
    while (
        suivant + 1 < len(significatifs)
        and _symbole(significatifs[suivant], ".")
        and significatifs[suivant + 1].nom is not None
    ):
        suivant += 2
    return suivant < len(significatifs) and _symbole(significatifs[suivant], "(")
