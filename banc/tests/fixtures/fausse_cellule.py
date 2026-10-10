"""Fausse cellule pour tests/test_orchestration.py : l'orchestration la lance comme une vraie (liste
blanche, dossier vide, sa propre session, commande sur stdin). Elle note ce qu'elle reçoit, puis
joue sa conduite et écrit sa trace par banc.mesures, comme une vraie cellule.

Usage : fausse_cellule.py <scenario.json> <journal.jsonl> <cellule>. Le scénario associe une
conduite à une conversation, « <cellule> p<passe> <questions> e<essai> » (questions jointes par
« + ») ; sans conduite, chaque question reçoit une réponse. Conduite : {"tours": [un tour par
question posée, {"issue", "cause", "reponse", "entree", "sortie"}], "code": code de sortie (0),
"sans_trace": rien d'écrit, "bloquer": rang du tour (0 : le premier) laissé sans fin, la cellule
attendant sans fin, "sourde": SIGTERM ignoré, "enfant": un enfant lancé dans sa propre session
(comme le serveur MCP d'ADK), qui attend sans fin, "orphelin": un enfant laissé dans son groupe à
sa sortie, "quitter": rang du tour laissé sans fin, la cellule sortant aussitôt, "seulement":
nombre de questions posées, "autre_entete": une trace au nom attendu, mais d'un autre essai,
"continuer": elle pose la question suivante après un tour sans réponse, ce que les vraies ne font
jamais, "attendre_a_la_fin": la trace complète, elle attend sans fin au lieu de sortir,
"signal_au_harnais": numéro d'un signal envoyé à son parent, l'orchestration, dès le départ,
"zero_sur_sigterm": un SIGTERM la fait sortir en 0}. Un tour laissé sans fin (« bloquer »,
« quitter ») a déjà payé ses tokens.

L'environnement reçu est noté en entier : c'est la liste blanche, et la clé Anthropic des tests est
factice.
"""

import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any

from banc.cellule import lire_commande
from banc.mesures import Entete, Journal, commit_pokeapi, fichier_trace
from banc.prix import Usage

SCENARIO = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
JOURNAL = Path(sys.argv[2])
CELLULE = sys.argv[3]
MODELES = {
    "claude-code": ("claude-sonnet-5-5", "api"),
    "adk-claude": ("claude-sonnet-5-5", "api"),
    "adk-gemini": ("gemini-3.8-flash", "vertex-eu"),
}
REPONSE = "Réponse : 42\n\nSources : MATCH (n) RETURN count(n) AS n"


def noter(note: dict[str, Any]) -> None:
    with JOURNAL.open("a", encoding="utf-8") as flux:
        flux.write(json.dumps(note | {"t": time.monotonic()}, ensure_ascii=False) + "\n")


def regler_sigterm(conduite: dict[str, Any]) -> None:
    """SIGTERM ignoré (« sourde »), ou qui la fait sortir en 0 (« zero_sur_sigterm »)."""
    if conduite.get("sourde"):
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if conduite.get("zero_sur_sigterm"):
        signal.signal(signal.SIGTERM, lambda _numero, _cadre: sys.exit(0))


def principal() -> int:
    commande = lire_commande(sys.stdin.read())
    questions = tuple(ident for ident, _ in commande.questions)
    cle = f"{CELLULE} p{commande.passe} {'+'.join(questions)} e{commande.essai}"
    conduite: dict[str, Any] = SCENARIO.get(cle, {})
    regler_sigterm(conduite)
    note: dict[str, Any] = {
        "cle": cle,
        "pid": os.getpid(),
        "pgid": os.getpgid(0),
        "sid": os.getsid(0),
        "env": dict(os.environ),
        "cwd": str(Path.cwd()),
        "contenu": sorted(chemin.name for chemin in Path.cwd().iterdir()),
        "messages": [message for _, message in commande.questions],
        "cache_1h": commande.cache_1h,
        "plafonds": {"delai_s": commande.plafonds.delai_s, "tours": commande.plafonds.tours},
        "serveur": list(commande.serveur),
    }
    attente = [sys.executable, "-c", "import time; time.sleep(600)"]
    if conduite.get("enfant"):
        note["enfant"] = subprocess.Popen(attente, start_new_session=True).pid
    if conduite.get("orphelin"):
        note["orphelin"] = subprocess.Popen(attente).pid
    noter(note)
    if "signal_au_harnais" in conduite:
        os.kill(os.getppid(), conduite["signal_au_harnais"])
    code: int = conduite.get("code", 0)
    if conduite.get("sans_trace"):
        return code
    modele, acces = MODELES[CELLULE]
    entete = Entete(
        campagne=commande.campagne,
        cellule=CELLULE,
        passe=commande.passe,
        essai=commande.essai,
        questions=questions,
        modele=modele,
        acces=acces,
        jour=date.today(),
        effort="high",
        versions={"fausse-cellule": "1"},
        commit_pokeapi=commit_pokeapi(),
    )
    fichier = fichier_trace(commande.traces, entete)
    if conduite.get("autre_entete"):
        entete = replace(entete, essai=entete.essai + 1)
    tours: list[dict[str, Any]] = conduite.get("tours", [])
    with Journal(fichier, entete) as journal:
        posees = commande.questions[: conduite.get("seulement", len(commande.questions))]
        for rang, (ident, message) in enumerate(posees):
            journal.question(ident, message)
            tour = tours[rang] if rang < len(tours) else {}
            issue = tour.get("issue", "reponse")
            entree = tour.get("entree", 1000 if issue == "reponse" else 0)
            sortie = tour.get("sortie", 100 if issue == "reponse" else 0)
            if entree or sortie:
                journal.llm(modele, Usage(entree=entree, sortie=sortie))
            if conduite.get("bloquer") == rang:
                time.sleep(600)
            if conduite.get("quitter") == rang:
                return code
            reponse = tour.get("reponse", REPONSE) if issue == "reponse" else ""
            journal.fin(issue, tour.get("cause"), reponse)
            if issue != "reponse" and not conduite.get("continuer"):
                break
    if conduite.get("attendre_a_la_fin"):
        time.sleep(600)
    return code


sys.exit(principal())
