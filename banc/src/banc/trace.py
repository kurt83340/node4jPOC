"""Trace d'un tour de conversation, telle que la notation la lit (plan 002, D4).

Contrat minimal, choisi par Julien le 2026-10-08 : la réponse finale du tour et ses appels d'outils,
dans l'ordre, chacun avec sa requête, ses paramètres et son résultat tel que l'agent l'a reçu
(neo4j-mcp v1.6.0 : le JSON indenté des enregistrements, ou un message d'erreur). Une description
« renvoyée » se lit dans ces résultats. T3.1 l'entoure (trace JSONL par conversation, masquage,
mesures) sans le changer : la notation ne dépend pas de la façon dont la trace est rangée.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Appel:
    """Un appel d'outil MCP pendant le tour."""

    # Nom MCP nu, sans le préfixe du client (mcp__…) : « read-cypher ».
    outil: str
    # Cypher envoyé, tel quel ; vide pour un outil sans requête (get-schema).
    requete: str = ""
    parametres: Mapping[str, object] = field(default_factory=dict)
    # Texte reçu par l'agent, verbatim.
    resultat: str = ""
    # isError de MCP : requête refusée (écriture) ou en échec (syntaxe, délai).
    erreur: bool = False


@dataclass(frozen=True)
class Tour:
    """Un tour : la question posée, la réponse finale de l'agent, les appels de ce tour seul.

    Q18 et Q28 sont des seconds tours : les appels du tour de Q2 ou de Q27 n'y figurent pas.
    """

    question: str
    reponse: str
    appels: tuple[Appel, ...] = ()
