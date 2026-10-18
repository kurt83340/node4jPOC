"""Rapport d'une campagne (T9.1) : `banc rapport --campagne <id> [--complet]`.

Une campagne est complète quand chaque conversation de chaque série (une cellule, une passe) a sa
dernière ligne, sans panne ni arrêt à rejouer, qu'aucune trace n'attend plus sa ligne et qu'aucune
série ne dépasse 2 pannes (passe invalide, plan D13) ; `--complet` sort alors en 0, sinon en 1.
Le rapport donne, série par série, les questions menées, les issues, le coût (essais rejoués
compris) et la durée médiane d'une réponse. Les scores (réponses justes, plus la moitié des
partielles) n'apparaissent qu'une fois la revue finie : avant, une note trahirait la cellule d'un
cas encore à revoir (revue à l'aveugle, plan D4).
"""

import statistics
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from banc import revue
from banc.cellule import CONSIGNES, FICHES
from banc.mesures import TRACES, MesureError, fichier_mesures, lire_lignes
from banc.orchestration import (
    PANNES_PAR_SERIE,
    Campagne,
    OrchestrationError,
    dernier_essai,
    lire_campagne,
)

# Issues d'un dernier essai que --reprendre rejoue : la conversation n'a pas encore compté.
A_REJOUER = frozenset({"panne", "arret"})

type Serie = tuple[str, int]


@dataclass(frozen=True)
class Bilan:
    """Une série : ses questions retenues, leurs issues, son coût, sa durée médiane de réponse."""

    cellule: str
    passe: int
    questions: int
    issues: dict[str, int]
    cout_usd: Decimal
    duree_mediane_s: float | None


def manques(campagne: Campagne, lignes: Sequence[Mapping[str, str]], dossier: Path) -> list[str]:
    """Ce qui empêche de compter la campagne, dans l'ordre du plan ; vide si elle est complète.

    Args:
        campagne: les paramètres de la campagne (campagne.json).
        lignes: son CSV.
        dossier: ses traces.
    """
    problemes = []
    for etape in campagne.etapes():
        essai, issues = dernier_essai(etape, lignes, dossier)
        if essai == 0:
            problemes.append(f"{etape} : jamais menée")
        elif issues is None:
            problemes.append(f"{etape} : essai {essai} sans ligne, --reprendre")
        elif rejouer := sorted(issues & A_REJOUER):
            problemes.append(f"{etape} : essai {essai} en {', '.join(rejouer)}, --reprendre")
    pannes = Counter((v["cellule"], int(v["passe"])) for v in lignes if v["issue"] == "panne")
    for (cellule, passe), nombre in sorted(pannes.items()):
        if nombre > PANNES_PAR_SERIE:
            problemes.append(
                f"{cellule}, passe {passe} : {nombre} pannes, série invalide (plan, D13)"
            )
    return problemes


def series(campagne: Campagne, lignes: Sequence[Mapping[str, str]]) -> list[Bilan]:
    """Le bilan de chaque série, cellule par cellule, passe par passe."""
    retenues = revue.retenues(lignes)
    bilans = []
    for cellule in campagne.cellules:
        for passe in range(1, campagne.passes + 1):

            def de_la_serie(valeurs: Mapping[str, str]) -> bool:
                return (valeurs["cellule"], int(valeurs["passe"])) == (cellule, passe)  # noqa: B023

            gardees = [valeurs for valeurs in retenues if de_la_serie(valeurs)]
            reponses = [float(v["duree_s"]) for v in gardees if v["issue"] == "reponse"]
            bilans.append(
                Bilan(
                    cellule,
                    passe,
                    len(gardees),
                    dict(Counter(_issue(valeurs) for valeurs in gardees)),
                    sum((Decimal(v["cout_usd"]) for v in lignes if de_la_serie(v)), Decimal(0)),
                    statistics.median(reponses) if reponses else None,
                )
            )
    return bilans


def scores(
    campagne: Campagne, lignes: Sequence[Mapping[str, str]], revues: Path
) -> dict[Serie, float] | None:
    """Le score de chaque série (justes, plus la moitié des partielles), une fois la revue finie ;
    None tant qu'un cas reste à revoir (revue à l'aveugle)."""
    decisions = revue.charger(revues)
    if revue.en_attente(lignes, decisions):
        return None
    points = {"juste": 1.0, "partiel": 0.5}
    resultat: dict[Serie, float] = {}
    for valeurs in revue.retenues(lignes):
        serie = (valeurs["cellule"], int(valeurs["passe"]))
        note = revue.finale(valeurs, decisions).note
        resultat[serie] = resultat.get(serie, 0.0) + points.get(note or "", 0.0)
    return {
        (cellule, passe): resultat.get((cellule, passe), 0.0)
        for passe in range(1, campagne.passes + 1)
        for cellule in campagne.cellules
    }


def ecarts(par_serie: Mapping[Serie, float]) -> dict[str, float]:
    """Par cellule, l'écart entre sa meilleure et sa moins bonne passe (le bruit, plan D8)."""
    par_cellule: dict[str, list[float]] = {}
    for (cellule, _passe), score in par_serie.items():
        par_cellule.setdefault(cellule, []).append(score)
    return {cellule: max(valeurs) - min(valeurs) for cellule, valeurs in par_cellule.items()}


def commande(
    campagne: str,
    *,
    complet: bool,
    traces: Path = TRACES,
    mesures: Path = revue.MESURES,
) -> int:
    """`banc rapport` : codes retour 0 (rapport, ou campagne complète avec --complet), 1 (campagne
    incomplète, --complet), 2 (erreur)."""
    try:
        dossier = traces / campagne
        parametres = lire_campagne(dossier / "campagne.json")
        lignes = lire_lignes(fichier_mesures(campagne, mesures))
        manquants = manques(parametres, lignes, dossier)
        bilans = series(parametres, lignes)
        notes = scores(parametres, lignes, mesures / "revues.toml")
    except (OrchestrationError, MesureError, revue.RevueError) as erreur:
        print(f"banc rapport : {erreur}", file=sys.stderr)
        return 2
    attendues = sum(len(conversation) for conversation in parametres.conversations)
    etat = "complète" if not manquants else f"incomplète ({len(manquants)} manques)"
    total = sum((bilan.cout_usd for bilan in bilans), Decimal(0))
    print(f"campagne {campagne} : {etat} ; {len(lignes)} lignes ; {total} $")
    if parametres.empreinte_prompt is not None:
        # La consigne de la technique (ADR-0018) ; une campagne GraphRAG gèle aussi sa requête.
        recherche = parametres.empreinte_recherche
        print(
            f"schéma {parametres.schema} : {CONSIGNES[parametres.consigne]} et "
            f"{FICHES[parametres.schema]}, empreinte du prompt {parametres.empreinte_prompt[:12]}"
            + ("" if recherche is None else f" ; requête de recherche {recherche[:12]}")
        )
    for manque in manquants:
        print(f"  manque : {manque}")
    for bilan in bilans:
        issues = ", ".join(f"{nombre} {issue}" for issue, nombre in sorted(bilan.issues.items()))
        mediane = "-" if bilan.duree_mediane_s is None else f"{bilan.duree_mediane_s:.1f} s"
        print(
            f"{bilan.cellule}, passe {bilan.passe} : {bilan.questions}/{attendues} questions ; "
            f"{issues} ; {bilan.cout_usd} $ ; réponse médiane {mediane}"
        )
    if notes is None:
        print("scores : masqués tant que la revue n'est pas finie (revue à l'aveugle, plan D4)")
    else:
        for (cellule, passe), score in notes.items():
            print(f"score {cellule}, passe {passe} : {score:g} / {attendues}")
        for cellule, ecart in ecarts(notes).items():
            print(f"écart entre passes, {cellule} : {ecart:g}")
    return 1 if complet and manquants else 0


def _issue(valeurs: Mapping[str, str]) -> str:
    return valeurs["issue"] + (f" ({valeurs['cause']})" if valeurs["cause"] else "")
