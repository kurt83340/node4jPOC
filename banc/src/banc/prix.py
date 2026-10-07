"""Prix des modèles (plan 002, D10) : tarifs datés de banc/prix.toml et coût d'un usage."""

import tomllib
from dataclasses import dataclass, fields
from datetime import date
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Any

FICHIER = Path(__file__).resolve().parents[2] / "prix.toml"
MILLION = Decimal(1_000_000)


class PrixError(Exception):
    """Fichier de prix invalide, ou aucun tarif pour ce modèle ce jour-là."""


@dataclass(frozen=True)
class Usage:
    """Tokens consommés, par ligne de facturation ; la réflexion compte dans la sortie."""

    entree: int = 0
    sortie: int = 0
    cache_ecriture_5m: int = 0
    cache_ecriture_1h: int = 0
    cache_lecture: int = 0

    def __add__(self, autre: Usage) -> Usage:
        somme = {f.name: getattr(self, f.name) + getattr(autre, f.name) for f in fields(Usage)}
        return Usage(**somme)


@dataclass(frozen=True)
class Tarif:
    """Prix d'un modèle en dollars par million de tokens, du `du` au `au` compris."""

    modele: str
    du: date
    au: date | None
    entree: Decimal
    sortie: Decimal
    cache_ecriture_5m: Decimal
    cache_ecriture_1h: Decimal
    cache_lecture: Decimal
    source: str

    def couvre(self, jour: date) -> bool:
        """Vrai si le tarif vaut ce jour-là."""
        return self.du <= jour and (self.au is None or jour <= self.au)

    def cout(self, usage: Usage) -> Decimal:
        """Coût de l'usage, en dollars."""
        lignes = (getattr(usage, f.name) * getattr(self, f.name) for f in fields(Usage))
        return sum(lignes, Decimal(0)) / MILLION


def charger(fichier: Path = FICHIER) -> list[Tarif]:
    """Lit les tarifs ; refuse deux périodes qui se chevauchent pour un même modèle."""
    try:
        tarifs = [_lire(brut) for brut in tomllib.loads(fichier.read_text())["tarif"]]
    except (OSError, tomllib.TOMLDecodeError, KeyError, TypeError, ValueError) as erreur:
        raise PrixError(f"{fichier} illisible : {erreur!r}") from erreur
    for modele in {t.modele for t in tarifs}:
        periodes = sorted((t for t in tarifs if t.modele == modele), key=lambda t: t.du)
        for avant, apres in pairwise(periodes):
            if avant.au is None or avant.au >= apres.du:
                raise PrixError(f"{modele} : périodes qui se chevauchent ({avant.du}, {apres.du})")
    return tarifs


def tarif(tarifs: list[Tarif], modele: str, jour: date) -> Tarif:
    """Tarif du modèle ce jour-là."""
    for candidat in tarifs:
        if candidat.modele == modele and candidat.couvre(jour):
            return candidat
    raise PrixError(f"aucun tarif pour {modele} le {jour}")


def _lire(brut: dict[str, Any]) -> Tarif:
    """Un tarif du fichier ; les prix passent par leur texte pour rester exacts en Decimal."""
    if not isinstance(brut["du"], date) or not isinstance(brut.get("au", date.max), date):
        raise TypeError(f"{brut['modele']} : dates attendues au format AAAA-MM-JJ")
    prix = {f.name: Decimal(str(brut[f.name])) for f in fields(Usage)}
    return Tarif(brut["modele"], brut["du"], brut.get("au"), source=brut["source"], **prix)
