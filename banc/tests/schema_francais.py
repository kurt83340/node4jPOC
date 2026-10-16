"""Le schéma français, tiré de la doc et non de la table de correspondance (spec 002, D8) : une
liste indépendante, pour juger les traductions sans passer par la table qu'elles appliquent.

ARCHITECTURE § 5 donne les labels, les types de relation et les clés ; cypher/00-contraintes.cypher,
les noms des contraintes et des index. Les identifiants communs aux deux langues, relus ici et non
lus dans la table, sont écartés des contrôles « aucun identifiant français ».

places_du_schema lit, par des expressions régulières et non par le traducteur, les noms qu'un
texte Cypher met à une place du schéma ; il suit la mise en forme du corpus : `:Label` sans espace,
une clé de map suivie de ses deux-points, aucun « // » dans un littéral.
"""

import re
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
ARCHITECTURE = RACINE / ".claude" / "docs" / "conception" / "ARCHITECTURE.md"
CONTRAINTES = RACINE / "cypher" / "00-contraintes.cypher"
# Identiques dans les deux langues (relus le 2026-10-11).
COMMUNS = frozenset(
    {"Pokemon", "Type", "Description", "id", "pp", "statDefense", "type_id", "pokemon_id"}
)
LITTERAL = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
NOM = r"[^\W\d]\w*"


def _section(titre: str) -> str:
    """Le texte d'une sous-section « ### titre » de la section 5 d'ARCHITECTURE."""
    cinq = ARCHITECTURE.read_text().split("\n## 5.", 1)[1].split("\n## 6.", 1)[0]
    return cinq.split(f"\n### {titre}\n", 1)[1].split("\n### ", 1)[0]


def _colonne(texte: str, rang: int) -> list[str]:
    """Une colonne des lignes d'un tableau Markdown (« \\| » échappé gardé dans la cellule)."""
    lignes = [ligne for ligne in texte.splitlines() if ligne.startswith("| ")]
    cellules = [re.split(r"(?<!\\)\|", ligne)[rang + 1] for ligne in lignes[2:]]
    return [cellule.replace("\\|", "|").strip() for cellule in cellules]


def schema_francais() -> dict[str, set[str]]:
    """Les identifiants français, par genre : ARCHITECTURE § 5 et 00-contraintes.cypher."""
    noeuds, relations = _section("Nœuds"), _section("Relations")
    labels = set(re.findall(r"^`(\w+)`", "\n".join(_colonne(noeuds, 0)), re.MULTILINE))
    groupes = re.findall(r"\[:([\w |]+)\]", " ".join(_colonne(relations, 0)))
    types = {t.strip() for groupe in groupes for t in groupe.split("|")}
    cles = set(re.findall(r"`(\w+)`", " ".join(_colonne(noeuds, 1) + _colonne(relations, 1))))
    contraintes = CONTRAINTES.read_text()
    index = set(
        re.findall(r"CREATE (?:(?:FULLTEXT|VECTOR) )?(?:CONSTRAINT|INDEX) (\w+)", contraintes)
    )
    return {"labels": labels, "relations": types, "proprietes": cles, "index": index}


def francais() -> frozenset[str]:
    """Les identifiants proprement français : tous, moins les communs."""
    return frozenset().union(*schema_francais().values()) - COMMUNS


def places_du_schema(cypher: str) -> set[str]:
    """Les noms qu'un texte Cypher met à une place du schéma : après « : » ou « | » collés (labels,
    types), après un point (clés), en clé de map, en littéral entier, après CONSTRAINT ou INDEX."""
    sans_commentaires = re.sub(r"//[^\n]*", "", cypher)
    litteraux = {m.group()[1:-1] for m in LITTERAL.finditer(sans_commentaires)}
    code = LITTERAL.sub("''", sans_commentaires)
    noms = set(re.findall(rf"[:|]`?({NOM})", code))
    noms |= set(re.findall(rf"\.({NOM})", code))
    noms |= set(re.findall(rf"[{{,]\s*({NOM})\s*:(?!:)", code))
    noms |= set(re.findall(rf"\b(?:CONSTRAINT|INDEX)\s+({NOM})", code)) - {"IF", "FOR", "ON"}
    return noms | litteraux
