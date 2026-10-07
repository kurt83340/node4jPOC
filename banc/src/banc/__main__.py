"""Point d'entrée du banc d'essai : python -m banc <commande>."""

import argparse
import sys

from banc.acces import acces


def main() -> int:
    """Analyse la ligne de commande et lance la commande demandée."""
    parseur = argparse.ArgumentParser(
        prog="banc", description="Banc d'essai des techniques text-to-Cypher (spec 002)."
    )
    commandes = parseur.add_subparsers(dest="commande", required=True)
    commandes.add_parser("acces", help="un appel minimal à Vertex par client (T0.2)")
    parseur.parse_args()
    return acces()


if __name__ == "__main__":
    sys.exit(main())
