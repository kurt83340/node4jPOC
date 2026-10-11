"""Table de correspondance du schéma anglais (plan 002, D8) : cypher/anglais/correspondance.toml,
lue et validée, et la carte de paramètres de cypher/anglais/renommer.cypher qu'on en tire.

Une seule table : labels, types de relation, clés, noms des contraintes et des index ; les valeurs
ne changent pas. La carte donne les deux sens ; scripts/charger.sh --schema la passe telle quelle à
cypher-shell (-P) : ni Python au chargement (ADR-0003), ni secret ici.
"""

import re
import tomllib
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DOSSIER = Path(__file__).resolve().parents[3] / "cypher" / "anglais"
TABLE = DOSSIER / "correspondance.toml"
CARTE = DOSSIER / "correspondance.cypher"
# Genres d'identifiants et forme de chacun (ADR-0005) ; une faute de frappe ne passe pas.
FORMES: dict[str, re.Pattern[str]] = {
    "labels": re.compile(r"[A-Z][A-Za-z0-9]*"),
    "relations": re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*"),
    "proprietes": re.compile(r"[a-z][A-Za-z0-9]*"),
    "index": re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*"),
}
GENRES = tuple(FORMES)
LANGUES = ("en", "fr")
# Ce que renommer.cypher renomme dans les données, sous le nom qu'il lui donne ; les contraintes et
# les index se recréent depuis leur fichier (00-contraintes.cypher, contraintes.cypher).
RENOMMES = {"labels": "labels", "relations": "types", "proprietes": "cles"}


class CorrespondanceError(Exception):
    """Table illisible, ou incohérente : nom mal formé, en double, ou qui en masque un autre."""


@dataclass(frozen=True)
class Correspondance:
    """Les noms anglais des identifiants français, par genre, et les identifiants communs aux deux
    langues, qui ne changent pas."""

    vers_anglais: Mapping[str, Mapping[str, str]]
    communs: Mapping[str, frozenset[str]]

    def sens(self, langue: str) -> Mapping[str, Mapping[str, str]]:
        """Les correspondances, par genre, vers cette langue : la table, ou son inverse."""
        if langue == "en":
            return self.vers_anglais
        if langue == "fr":
            return {g: {en: fr for fr, en in noms.items()} for g, noms in self.vers_anglais.items()}
        raise CorrespondanceError(f"langue {langue!r} inconnue (attendu : {LANGUES})")

    def nom(self, genre: str, identifiant: str, langue: str) -> str | None:
        """Le nom de l'identifiant dans cette langue ; lui-même s'il est commun ; None s'il n'est
        pas du schéma dans l'autre langue."""
        if identifiant in self.communs[genre]:
            return identifiant
        return self.sens(langue)[genre].get(identifiant)


def charger(fichier: Path = TABLE) -> Correspondance:
    """Lit la table et la valide : formes, noms en double, noms qui en masquent d'autres."""
    try:
        brut = tomllib.loads(fichier.read_text())
    except (OSError, tomllib.TOMLDecodeError) as erreur:
        raise CorrespondanceError(f"{fichier} illisible : {erreur!r}") from erreur
    vers_anglais = {genre: _section(brut, genre) for genre in GENRES}
    communs = _communs(brut)
    for genre in GENRES:
        _valider(genre, vers_anglais[genre], communs[genre])
    _un_seul_genre(vers_anglais, communs)
    return Correspondance(vers_anglais, communs)


def carte(table: Correspondance) -> str:
    """La carte de paramètres de renommer.cypher : une map Cypher, {cartes: {en: …, fr: …}}."""
    lignes = [
        "// Carte de paramètres de cypher/anglais/renommer.cypher (spec 002, plan D8), produite",
        "// depuis correspondance.toml par `uv run --directory banc python -m banc anglais` :",
        "// ne pas l'éditer. scripts/charger.sh --schema la passe à cypher-shell (-P), sans ses",
        "// lignes « // » ; $langue choisit le sens.",
        "{cartes: {",
    ]
    for i, langue in enumerate(LANGUES):
        sens = table.sens(langue)
        lignes.append(f"  {langue}: {{")
        for j, (genre, nom) in enumerate(RENOMMES.items()):
            lignes.append(f"    {nom}: {{")
            noms = list(sens[genre].items())
            lignes += [
                f"      {a}: '{b}'{',' if k < len(noms) - 1 else ''}"
                for k, (a, b) in enumerate(noms)
            ]
            lignes.append("    }" + ("," if j < len(RENOMMES) - 1 else ""))
        lignes.append("  }" + ("," if i < len(LANGUES) - 1 else ""))
    lignes.append("}}")
    return "\n".join(lignes) + "\n"


def _section(brut: Mapping[str, Any], genre: str) -> dict[str, str]:
    """Une section de traductions : des textes, en entier."""
    if not isinstance(section := brut.get(genre), dict):
        raise CorrespondanceError(f"section {genre} absente")
    if not all(isinstance(v, str) for v in section.values()):
        raise CorrespondanceError(f"{genre} : des noms en texte attendus")
    return dict(section)


def _communs(brut: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """Les identifiants communs, une liste par genre."""
    if not isinstance(section := brut.get("communs"), dict) or set(section) != set(GENRES):
        raise CorrespondanceError(f"section communs absente, ou sans une liste par genre {GENRES}")
    if not all(isinstance(n, str) for noms in section.values() for n in noms):
        raise CorrespondanceError("communs : des noms en texte attendus")
    return {genre: frozenset(section[genre]) for genre in GENRES}


def _valider(genre: str, noms: Mapping[str, str], communs: frozenset[str]) -> None:
    """Un genre : formes, puis noms anglais en double, puis noms qui en masquent d'autres (un nom à
    la fois français et anglais renommerait deux fois), puis communs aussi traduits."""
    forme = FORMES[genre]
    for nom in (*noms, *noms.values(), *communs):
        if not forme.fullmatch(nom):
            raise CorrespondanceError(f"{genre} : {nom!r} mal formé")
    anglais = list(noms.values())
    for nom in anglais:
        if anglais.count(nom) > 1:
            raise CorrespondanceError(f"{genre} : {nom!r} en double")
    for nom in anglais:
        if nom in noms:
            raise CorrespondanceError(f"{genre} : {nom!r} à la fois français et anglais")
    for nom in communs:
        if nom in noms or nom in anglais:
            raise CorrespondanceError(f"{genre} : {nom!r} à la fois commun et traduit")


def _un_seul_genre(
    vers_anglais: Mapping[str, Mapping[str, str]], communs: Mapping[str, frozenset[str]]
) -> None:
    """Un nom n'appartient qu'à un genre, dans chaque langue : un littéral qui le porte se traduit
    sans ambiguïté."""
    vus: dict[str, str] = {}
    for genre, nom in _tous(vers_anglais, communs):
        if vus.setdefault(nom, genre) != genre:
            raise CorrespondanceError(f"{nom!r} dans deux genres ({vus[nom]}, {genre})")


def _tous(
    vers_anglais: Mapping[str, Mapping[str, str]], communs: Mapping[str, frozenset[str]]
) -> Iterator[tuple[str, str]]:
    for genre in GENRES:
        noms = vers_anglais[genre]
        for nom in (*noms, *noms.values(), *communs[genre]):
            yield genre, nom
