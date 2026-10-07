"""`banc acces` (T0.2) : un appel minimal à Vertex par client, chacun isolé selon D3.

Chaque sonde tourne dans son processus, depuis un dossier vide, avec un HOME et une configuration de
Claude Code neufs, et la liste blanche pour seul environnement. Le coût vient de banc/prix.toml.
Codes retour : 0 = tous les clients répondent · 1 = au moins un échec · 2 = prix illisibles.
"""

import json
import subprocess
import sys
import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from banc.isolement import environnement_agent
from banc.prix import PrixError, Tarif, Usage, charger, tarif

# (client, modèle) : les 3 clients sur le modèle de leur cellule, plus le petit modèle de Claude
# Code et le repli des cellules Claude (plan, D2).
SONDES = (
    ("claude-code", "claude-sonnet-5-5"),
    ("claude-code", "claude-haiku-4-5@20251001"),
    ("adk-claude", "claude-sonnet-5-5"),
    ("adk-claude", "claude-sonnet-5"),
    ("adk-gemini", "gemini-3.8-flash"),
)
DELAI_S = 180


def lancer(client: str, modele: str, racine: Path) -> dict[str, Any]:
    """Lance une sonde isolée ; renvoie son relevé, ou l'erreur et la fin de son stderr."""
    dossier = racine / f"{client}--{modele}"
    for sous_dossier in ("home", "claude", "travail"):
        (dossier / sous_dossier).mkdir(parents=True)
    env = environnement_agent(dossier / "home", dossier / "claude")
    commande = [sys.executable, "-m", "banc.sondes", client, modele]
    try:
        fini = subprocess.run(
            commande,
            cwd=dossier / "travail",
            env=env,
            capture_output=True,
            text=True,
            timeout=DELAI_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"erreur": f"aucune réponse en {DELAI_S} s"}
    lignes = fini.stdout.strip().splitlines()
    if fini.returncode != 0 or not lignes:
        fin = "\n".join(fini.stderr.strip().splitlines()[-6:])
        return {"erreur": f"code {fini.returncode}\n{fin}"}
    releve: dict[str, Any] = json.loads(lignes[-1])
    return releve


def cout(usages: dict[str, dict[str, int]], tarifs: list[Tarif], jour: date) -> Decimal | None:
    """Coût total des modèles appelés, ou None si l'un d'eux n'a pas de tarif."""
    try:
        return sum(
            (tarif(tarifs, modele, jour).cout(Usage(**u)) for modele, u in usages.items()),
            Decimal(0),
        )
    except PrixError:
        return None


def acces() -> int:
    """Lance toutes les sondes et affiche, pour chacune, réponse, durée, tokens et coût."""
    try:
        tarifs = charger()
    except PrixError as erreur:
        print(f"banc acces : {erreur}", file=sys.stderr)
        return 2
    echecs = 0
    with tempfile.TemporaryDirectory(prefix="banc-acces-") as dossier:
        for client, modele in SONDES:
            releve = lancer(client, modele, Path(dossier))
            if "erreur" in releve or not releve.get("reponse"):
                echecs += 1
                print(f"✗ {client:<12} {modele:<26} {releve.get('erreur', 'réponse vide')}")
                continue
            usages = releve["usages"]
            prix = cout(usages, tarifs, date.today())
            montant = "tarif absent" if prix is None else f"{prix:.6f} $"
            print(f"✓ {client:<12} {modele:<26} {releve['duree_s']:>6} s  {montant}")
            for nom, u in usages.items():
                print(f"    {nom:<28} {u}")
            print(f"    observations : {json.dumps(releve['observations'], ensure_ascii=False)}")
    return 1 if echecs else 0
