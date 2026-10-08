"""Point d'entrée du banc d'essai : python -m banc <commande>."""

import argparse
import sys
from collections.abc import Sequence

from banc import revue
from banc.acces import acces


def main(arguments: Sequence[str] | None = None) -> int:
    """Analyse la ligne de commande et lance la commande demandée."""
    parseur = argparse.ArgumentParser(
        prog="banc", description="Banc d'essai des techniques text-to-Cypher (spec 002)."
    )
    commandes = parseur.add_subparsers(dest="commande", required=True)
    commandes.add_parser("acces", help="un appel minimal par client (T0.2), par scripts/banc.sh")
    revoir = commandes.add_parser(
        "revoir", help="revue humaine à l'aveugle des cas « à revoir » d'une campagne (T3.2)"
    )
    revoir.add_argument("--campagne", required=True, help="identifiant de la campagne")
    revoir.add_argument(
        "--verifier", action="store_true", help="code 0 s'il ne reste aucun cas à revoir, 1 sinon"
    )
    lus = parseur.parse_args(arguments)
    if lus.commande == "revoir":
        return revue.commande(lus.campagne, seulement_verifier=lus.verifier)
    return acces()


if __name__ == "__main__":
    sys.exit(main())
