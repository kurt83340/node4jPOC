"""Réponses de référence (questions/attendu/qNN.txt, plan 001 D11), relues par le harnais :
tables de l'ADR-0008, longues listes et scores de Q8 pour la notation, cohérence de
questions/banc.toml.

Format (scripts/questions.sh) : une ligne « // PokéAPI <commit> · qNN.cypher », puis la sortie
de cypher-shell en format plain. Chaque requête du fichier donne un tableau : une ligne d'en-tête
(les noms des colonnes), puis ses lignes de valeurs Cypher (chaînes, nombres, booléens, NULL,
listes, dictionnaires).
"""

import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

DOSSIER = Path(__file__).resolve().parents[3] / "questions" / "attendu"
IDENTIFIANT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
NOMBRE = re.compile(r"-?\d+(\.\d+)?([eE][-+]?\d+)?")
MOTS = {"TRUE": True, "FALSE": False, "NULL": None}

type Valeur = str | int | float | bool | list[Valeur] | dict[str, Valeur] | None


class AttenduError(Exception):
    """Réponse de référence absente ou illisible."""


@dataclass(frozen=True)
class Tableau:
    """Résultat d'une requête : ses colonnes, puis ses lignes, chacune indexée par colonne."""

    colonnes: tuple[str, ...]
    lignes: tuple[dict[str, Valeur], ...]


def lire(question: str) -> list[Tableau]:
    """Tableaux de la réponse de référence d'une question, nommée comme son fichier (« q07 »)."""
    try:
        texte = (DOSSIER / f"{question}.txt").read_text()
    except OSError as erreur:
        message = f"{question} : aucune réponse de référence ({erreur.strerror})"
        raise AttenduError(message) from erreur
    return analyser(texte)


def analyser(texte: str) -> list[Tableau]:
    """Tableaux d'une réponse de référence, dans l'ordre de ses requêtes."""
    lignes = texte.splitlines()
    if not lignes or not lignes[0].startswith("// PokéAPI "):
        raise AttenduError("première ligne attendue : « // PokéAPI <commit> · qNN.cypher »")
    tableaux: list[tuple[tuple[str, ...], list[dict[str, Valeur]]]] = []
    for numero, ligne in enumerate(lignes[1:], start=2):
        if not ligne.strip():
            continue
        colonnes = _entete(ligne)
        if colonnes is not None:
            tableaux.append((colonnes, []))
            continue
        if not tableaux:
            raise AttenduError(f"ligne {numero} : des valeurs avant tout en-tête")
        colonnes, rangees = tableaux[-1]
        valeurs = _Lecteur(ligne, numero).rangee()
        if len(valeurs) != len(colonnes):
            attendu = f"{len(colonnes)} valeurs attendues ({', '.join(colonnes)})"
            raise AttenduError(f"ligne {numero} : {len(valeurs)} valeurs, {attendu}")
        rangees.append(dict(zip(colonnes, valeurs, strict=True)))
    for colonnes, rangees in tableaux:
        if not rangees:
            raise AttenduError(f"tableau sans ligne ({', '.join(colonnes)})")
    return [Tableau(colonnes, tuple(rangees)) for colonnes, rangees in tableaux]


def feuilles(tableaux: Iterable[Tableau]) -> Iterator[str | int | float | bool | None]:
    """Toutes les valeurs simples des tableaux, listes et dictionnaires dépliés, ligne par ligne."""
    for tableau in tableaux:
        for ligne in tableau.lignes:
            for colonne in tableau.colonnes:
                yield from _deplier(ligne[colonne])


def _deplier(valeur: Valeur) -> Iterator[str | int | float | bool | None]:
    if isinstance(valeur, list):
        for element in valeur:
            yield from _deplier(element)
    elif isinstance(valeur, dict):
        for element in valeur.values():
            yield from _deplier(element)
    else:
        yield valeur


def _entete(ligne: str) -> tuple[str, ...] | None:
    """Colonnes si la ligne est un en-tête : des identifiants nus (ni TRUE, ni FALSE, ni NULL)."""
    noms = tuple(ligne.split(", "))
    if all(IDENTIFIANT.fullmatch(nom) and nom not in MOTS for nom in noms):
        return noms
    return None


class _Lecteur:
    """Une ligne de valeurs Cypher, lue caractère par caractère (descente récursive)."""

    def __init__(self, texte: str, numero: int) -> None:
        self.texte = texte
        self.numero = numero
        self.position = 0

    def rangee(self) -> list[Valeur]:
        valeurs = [self.valeur()]
        while self._suivant(","):
            valeurs.append(self.valeur())
        self._espaces()
        if self.position != len(self.texte):
            raise self._erreur("fin de ligne attendue")
        return valeurs

    def valeur(self) -> Valeur:
        if self._suivant('"'):
            return self._chaine()
        if self._suivant("["):
            return self._liste()
        if self._suivant("{"):
            return self._dictionnaire()
        return self._atome()

    def _chaine(self) -> str:
        morceaux: list[str] = []
        while self.position < len(self.texte):
            caractere = self.texte[self.position]
            self.position += 1
            if caractere == '"':
                return "".join(morceaux)
            if caractere == "\\" and self.position < len(self.texte):
                caractere = self.texte[self.position]
                self.position += 1
            morceaux.append(caractere)
        raise self._erreur("chaîne non fermée")

    def _liste(self) -> list[Valeur]:
        if self._suivant("]"):
            return []
        elements = [self.valeur()]
        while self._suivant(","):
            elements.append(self.valeur())
        if not self._suivant("]"):
            raise self._erreur("« ] » attendu")
        return elements

    def _dictionnaire(self) -> dict[str, Valeur]:
        paires: dict[str, Valeur] = {}
        if self._suivant("}"):
            return paires
        while True:
            self._espaces()
            cle = IDENTIFIANT.match(self.texte, self.position)
            if cle is None:
                raise self._erreur("clé de dictionnaire attendue")
            self.position = cle.end()
            if not self._suivant(":"):
                raise self._erreur("« : » attendu")
            paires[cle.group()] = self.valeur()
            if self._suivant("}"):
                return paires
            if not self._suivant(","):
                raise self._erreur("« , » ou « } » attendu")

    def _atome(self) -> Valeur:
        self._espaces()
        nombre = NOMBRE.match(self.texte, self.position)
        if nombre is not None:
            self.position = nombre.end()
            texte = nombre.group()
            return float(texte) if nombre.group(1) or nombre.group(2) else int(texte)
        mot = IDENTIFIANT.match(self.texte, self.position)
        if mot is not None and mot.group() in MOTS:
            self.position = mot.end()
            return MOTS[mot.group()]
        raise self._erreur("valeur attendue")

    def _suivant(self, caractere: str) -> bool:
        """Consomme le caractère, espaces sautés, s'il vient ensuite."""
        self._espaces()
        if self.texte.startswith(caractere, self.position):
            self.position += len(caractere)
            return True
        return False

    def _espaces(self) -> None:
        while self.texte.startswith(" ", self.position):
            self.position += 1

    def _erreur(self, message: str) -> AttenduError:
        return AttenduError(f"ligne {self.numero}, colonne {self.position + 1} : {message}")
