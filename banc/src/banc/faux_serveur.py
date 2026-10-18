"""Faux serveur MCP de la répétition générale (T5.1 ; plan, D13) : neo4j-mcp v1.6.0 vu du client,
mêmes outils, sans base ni réseau.

Chaque appel d'outil reçoit le même résultat neutre, une liste vide (choix de Julien, 2026-10-10) :
les réponses des agents seront fausses ou « à revoir », mais toute la chaîne passe (connexion,
outils, tokens, coût, traces, notation). La recherche d'une cellule GraphRAG, la seule lecture qui
porte un vecteur (spec 003, T13.1), reçoit un résultat fixe, neutre lui aussi, dans la forme de
questions/recherche.cypher : deux espèces hors du banc, des descriptions inventées (aucun texte de
la base dans le dépôt), pour que le contexte, la réponse et ses sources passent toute la chaîne.

Le serveur s'annonce en version « faux-serveur », qui se lit dans l'en-tête des traces et dans le
CSV. Avec --lent-s, chaque appel d'outil attend d'abord ce délai : au-delà du délai d'une question,
la conversation échoue (« un délai dépassé noté faux »).

Usage : python -I -m banc.faux_serveur [--lent-s N]. stdin et stdout sont le canal MCP, une ligne
JSON par message ; rien d'autre n'y passe.
"""

import argparse
import json
import sys
import time
from collections.abc import Sequence
from typing import Any, TextIO

VERSION = "faux-serveur"
RESULTAT = "[]"
# Le résultat fixe de la recherche des cellules GraphRAG : un enregistrement par espèce, les
# colonnes de questions/recherche.cypher, deux descriptions inventées chacune ; ni vecteur ni nœud
# entier.
RECHERCHE_FIXE = json.dumps(
    [
        {
            "espece": "Kecleon",
            "categorie": "Pokémon Caméléon",
            "types": ["Normal"],
            "talents": [{"nom": "Déguisement", "cache": False}, {"nom": "Protéen", "cache": True}],
            "statistiques": {
                "statPv": 60,
                "statAttaque": 90,
                "statDefense": 70,
                "statAttaqueSpeciale": 60,
                "statDefenseSpeciale": 120,
                "statVitesse": 40,
            },
            "evolueDe": [],
            "evolueEn": [],
            "descriptions": [
                {
                    "texte": "Il change de teinte selon l'humeur de ceux qui le regardent.",
                    "jeux": ["Rubis", "Saphir"],
                    "score": 0.8312,
                },
                {
                    "texte": "On raconte qu'il garde les reflets des flaques après la pluie.",
                    "jeux": ["Émeraude"],
                    "score": 0.8127,
                },
            ],
        },
        {
            "espece": "Vivaldaim",
            "categorie": "Pokémon Saison",
            "types": ["Normal", "Plante"],
            "talents": [
                {"nom": "Chlorophylle", "cache": False},
                {"nom": "Herbivore", "cache": False},
                {"nom": "Sérénité", "cache": True},
            ],
            "statistiques": {
                "statPv": 60,
                "statAttaque": 60,
                "statDefense": 50,
                "statAttaqueSpeciale": 40,
                "statDefenseSpeciale": 50,
                "statVitesse": 75,
            },
            "evolueDe": [],
            "evolueEn": ["Haydaim"],
            "descriptions": [
                {
                    "texte": "Il suit la lumière d'une clairière à l'autre au fil de la journée.",
                    "jeux": ["Noir", "Blanc"],
                    "score": 0.8044,
                },
                {
                    "texte": "Les promeneurs le reconnaissent à son pas léger sur la mousse.",
                    "jeux": ["Noir 2", "Blanc 2"],
                    "score": 0.7981,
                },
            ],
        },
    ],
    ensure_ascii=False,
    indent=2,
)
# Les deux outils de neo4j-mcp v1.6.0 en lecture seule ; le client masque get-schema (plan, D1).
OUTILS: list[dict[str, Any]] = [
    {
        "name": "get-schema",
        "description": "Retrieve the schema information from the Neo4j database.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "read-cypher",
        "description": "read-cypher can run only read-only Cypher statements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The Cypher query to execute"},
                "params": {"type": "object", "description": "Parameters to pass to the query"},
            },
            "required": ["query"],
        },
    },
]


def reponse(message: dict[str, Any], lent_s: float = 0.0) -> dict[str, Any] | None:
    """La réponse JSON-RPC à un message du client ; None pour une notification, qui n'en attend
    pas."""
    ident, methode = message.get("id"), message.get("method")
    if ident is None:
        return None
    match methode:
        case "initialize":
            parametres = message.get("params") or {}
            resultat: dict[str, Any] = {
                "protocolVersion": parametres.get("protocolVersion", "2025-06-18"),
                "capabilities": {"tools": {"listChanged": True}},
                "serverInfo": {"name": "neo4j-mcp", "version": VERSION},
            }
        case "tools/list":
            resultat = {"tools": OUTILS}
        case "tools/call":
            time.sleep(lent_s)
            arguments = (message.get("params") or {}).get("arguments") or {}
            # La recherche d'une cellule GraphRAG : read-cypher avec le vecteur du message.
            texte = RECHERCHE_FIXE if "vecteur" in (arguments.get("params") or {}) else RESULTAT
            resultat = {"content": [{"type": "text", "text": texte}], "isError": False}
        case "ping":
            resultat = {}
        case _:
            erreur = {"code": -32601, "message": "Method not found"}
            return {"jsonrpc": "2.0", "id": ident, "error": erreur}
    return {"jsonrpc": "2.0", "id": ident, "result": resultat}


def servir(entree: TextIO, sortie: TextIO, lent_s: float = 0.0) -> None:
    """Répond à chaque message, ligne après ligne, jusqu'à la fin de l'entrée."""
    for ligne in entree:
        if not ligne.strip():
            continue
        try:
            message = json.loads(ligne)
        except ValueError:
            erreur = {"code": -32700, "message": "Parse error"}
            sortie.write(json.dumps({"jsonrpc": "2.0", "id": None, "error": erreur}) + "\n")
            sortie.flush()
            continue
        if isinstance(message, dict) and (envoi := reponse(message, lent_s)) is not None:
            sortie.write(json.dumps(envoi, ensure_ascii=False) + "\n")
            sortie.flush()


def main(arguments: Sequence[str] | None = None) -> int:
    parseur = argparse.ArgumentParser(prog="banc.faux_serveur", description=__doc__)
    parseur.add_argument("--lent-s", type=float, default=0.0, help="attente avant chaque résultat")
    lus = parseur.parse_args(arguments)
    servir(sys.stdin, sys.stdout, lus.lent_s)
    return 0


if __name__ == "__main__":
    sys.exit(main())
