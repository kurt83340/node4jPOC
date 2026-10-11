"""Point d'entrée du banc d'essai : python -m banc <commande>."""

import argparse
import sys
from collections.abc import Callable, Sequence
from decimal import Decimal, InvalidOperation
from pathlib import Path

from banc import anglais, essai_serveur, orchestration, rapport, revue
from banc.acces import acces


def main(arguments: Sequence[str] | None = None) -> int:
    """Analyse la ligne de commande et lance la commande demandée."""
    parseur = argparse.ArgumentParser(
        prog="banc", description="Banc d'essai des techniques text-to-Cypher (spec 002)."
    )
    commandes = parseur.add_subparsers(dest="commande", required=True)
    commandes.add_parser("acces", help="un appel minimal par client (T0.2), par scripts/banc.sh")
    lancer = commandes.add_parser(
        "lancer",
        help="mène une campagne : passes, conversations, cellules alternées (T4.3) ; par "
        "scripts/banc.sh, qui passe la clé Anthropic",
    )
    lancer.add_argument("--campagne", required=True, help="identifiant (minuscules, chiffres, -)")
    lancer.add_argument(
        "--plafond-usd",
        required=True,
        type=_dollars,
        help="dépense totale de la campagne à ne pas dépasser, reprises comprises (exigé)",
    )
    lancer.add_argument("--passes", type=int, help="nombre de passes (défaut : 1)")
    lancer.add_argument(
        "--questions", type=_liste, default=(), help="Q19,Q2,Q18… (défaut : les 30, par numéro)"
    )
    lancer.add_argument(
        "--cellules", type=_liste, default=(), help="claude-code,adk-claude,adk-gemini (défaut)"
    )
    lancer.add_argument(
        "--cache-1h",
        action="store_const",
        const=True,
        help="cache d'une heure pour les cellules Claude, au lieu de 5 min (plan, D10)",
    )
    lancer.add_argument(
        "--faux-serveur",
        action="store_true",
        help="répétition générale (T5.1) : vrais LLM, faux serveur MCP, rien ne touche Aura",
    )
    lancer.add_argument(
        "--reprendre",
        action="store_true",
        help="continue la campagne : rejoue pannes, arrêts et conversations coupées",
    )
    commandes.add_parser(
        "essai-serveur",
        help="le lanceur sur la vraie base (T7.4) : outils, lecture, écritures refusées, lecture "
        "lente arrêtée par transactions.sh ; sans modèle (0 $), sans la clé Anthropic",
    )
    revoir = commandes.add_parser(
        "revoir", help="revue humaine à l'aveugle des cas « à revoir » d'une campagne (T3.2)"
    )
    revoir.add_argument("--campagne", required=True, help="identifiant de la campagne")
    revoir.add_argument(
        "--verifier", action="store_true", help="code 0 s'il ne reste aucun cas à revoir, 1 sinon"
    )
    rapport_ = commandes.add_parser(
        "rapport",
        help="bilan d'une campagne, série par série (T9.1) ; scores une fois la revue finie",
    )
    rapport_.add_argument("--campagne", required=True, help="identifiant de la campagne")
    rapport_.add_argument(
        "--complet",
        action="store_true",
        help="code 0 si chaque série est complète, sans panne à rejouer ni passe invalide, 1 sinon",
    )
    commandes.add_parser(
        "anglais",
        help="écrit les fichiers du schéma anglais tirés de cypher/anglais/correspondance.toml "
        "(T6.1) : carte de paramètres, contraintes et index ; sans la base",
    )
    traduire = commandes.add_parser(
        "traduire",
        help="traduit vers le schéma anglais les 27 requêtes, la liste des espèces, les "
        "vérifications et les exemples de la fiche (T6.2), pour scripts/questions.sh --dossier ; "
        "sans la base",
    )
    traduire.add_argument("--vers", required=True, type=Path, help="dossier (logs/anglais)")
    lus = parseur.parse_args(arguments)
    if lus.commande == "lancer":
        demande = orchestration.Demande(
            nom=lus.campagne,
            plafond_usd=lus.plafond_usd,
            reprendre=lus.reprendre,
            passes=lus.passes,
            questions=lus.questions,
            cellules=lus.cellules,
            cache_1h=lus.cache_1h,
            faux_serveur=lus.faux_serveur,
        )
        return orchestration.commande(demande)
    actions: dict[str, Callable[[], int]] = {
        "revoir": lambda: revue.commande(lus.campagne, seulement_verifier=lus.verifier),
        "rapport": lambda: rapport.commande(lus.campagne, complet=lus.complet),
        "essai-serveur": essai_serveur.commande,
        "anglais": anglais.commande,
        "traduire": lambda: anglais.commande_traduire(lus.vers),
        "acces": acces,
    }
    return actions[lus.commande]()


def _dollars(texte: str) -> Decimal:
    """Un montant en dollars, fini et positif."""
    try:
        montant = Decimal(texte)
    except InvalidOperation as erreur:
        raise argparse.ArgumentTypeError(f"montant illisible : {texte!r}") from erreur
    if not (montant.is_finite() and montant > 0):
        raise argparse.ArgumentTypeError(f"montant positif attendu, pas {texte!r}")
    return montant


def _liste(texte: str) -> tuple[str, ...]:
    """Une liste séparée par des virgules : « Q19, Q2,Q18 »."""
    return tuple(element.strip() for element in texte.split(",") if element.strip())


if __name__ == "__main__":
    sys.exit(main())
