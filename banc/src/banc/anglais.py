"""Le schéma anglais (plan 002, D8) : les fichiers versionnés tirés de la table de correspondance
(python -m banc anglais). banc ne joint jamais la base : scripts/charger.sh --schema joue ces
fichiers.
"""

import sys
from pathlib import Path

from banc import correspondance, traduction
from banc.correspondance import Correspondance

RACINE = Path(__file__).resolve().parents[3]
CONTRAINTES_FR = RACINE / "cypher" / "00-contraintes.cypher"
CONTRAINTES_EN = correspondance.DOSSIER / "contraintes.cypher"
PRODUIT = "uv run --directory banc python -m banc anglais"


def contraintes(table: Correspondance) -> str:
    """Contraintes et index en anglais : 00-contraintes.cypher traduit, sans ses commentaires."""
    entete = (
        "// Contraintes et index du schéma anglais (spec 002, plan D8) : 00-contraintes.cypher\n"
        "// traduit par correspondance.toml, produit par\n"
        f"// `{PRODUIT}` : ne pas l'éditer.\n"
        "// scripts/charger.sh --schema en le joue après le renommage des données ; --schema fr\n"
        "// rejoue cypher/00-contraintes.cypher.\n"
    )
    francais = traduction.sans_commentaires(CONTRAINTES_FR.read_text())
    return entete + "\n" + traduction.traduire(francais, table, "en")


def produits(table: Correspondance) -> dict[Path, str]:
    """Les fichiers tirés de la table, avec leur contenu attendu."""
    return {
        correspondance.CARTE: correspondance.carte(table),
        CONTRAINTES_EN: contraintes(table),
    }


def commande() -> int:
    """Écrit les fichiers tirés de la table ; dit lesquels ont changé."""
    table = correspondance.charger()
    for chemin, texte in produits(table).items():
        avant = chemin.read_text() if chemin.exists() else None
        if avant != texte:
            chemin.write_text(texte)
        etat = "inchangé" if avant == texte else "écrit"
        sys.stdout.write(f"✓ {chemin.relative_to(RACINE)} : {etat}\n")
    return 0
