"""Isolement des agents (plan 002, D3) : la liste blanche, seul environnement qu'ils reçoivent.

L'Agent SDK fusionne l'environnement du processus qui l'appelle avec le sien : un agent se lance
donc dans un processus dont l'environnement est cette liste, et rien d'autre (l'équivalent
d'env -i). La session de Claude Code qui lance le banc exporte ses propres réglages (effort max,
modèle…) : aucun ne doit atteindre l'agent mesuré.

La liste dépend du client (ADR-0011) : les cellules Claude reçoivent la clé Anthropic que
scripts/banc.sh passe au harnais, et aucune variable Vertex (CLAUDE_CODE_USE_VERTEX passerait avant
la clé) ; les cellules Gemini reçoivent Vertex `eu` par l'ADC, et jamais la clé. Une cellule
GraphRAG reçoit la liste de sa jumelle ADK, dont elle reprend le client et le modèle (plan 003, D7).

Claude Code 2.1.292 (relevé T4.1, sur le vrai binaire et une fausse API) ouvre par défaut une socket
de messagerie entre sessions dans /tmp/cc-socks/, décrit à l'agent une mémoire persistante, reprend
jusqu'à 10 fois un appel en échec et choisit seul la durée du cache : tout est fixé ici.
"""

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Final

PROJET = "jleroy-labo"
REGION = "eu"
EFFORT: Final = "high"
PETIT_MODELE = "claude-haiku-4-5-20251001"
# Reprises internes de Claude Code : autant que le client Anthropic d'ADK (plan, D13).
REPRISES = 2
CHEMINS_SYSTEME = ("/usr/bin", "/bin")
# Source d'authentification que le message init de Claude Code annonce quand la clé vient de
# l'environnement.
SOURCE_CLE = "ANTHROPIC_API_KEY"


class CleAbsente(Exception):
    """Une cellule Claude sans clé Anthropic : le banc n'a pas été lancé par scripts/banc.sh."""


class CleNonUtilisee(Exception):
    """Claude Code ne paie pas par la clé de l'API : coût non mesurable (circuit breaker)."""


def verifier_cle(init: Mapping[str, Any]) -> None:
    """Exige que Claude Code s'authentifie par la clé de l'API, jamais par un abonnement."""
    source = init.get("apiKeySource")
    if source != SOURCE_CLE:
        raise CleNonUtilisee(
            f"Claude Code ne paie pas par la clé de l'API : apiKeySource={source!r}"
        )


def config_gcloud() -> Path:
    """Dossier de configuration de gcloud du poste, qui contient les identifiants ADC."""
    return Path(os.environ.get("CLOUDSDK_CONFIG") or Path.home() / ".config" / "gcloud")


def cle_anthropic() -> str:
    """Clé que scripts/banc.sh a lue dans Secret Manager et passée par l'environnement."""
    cle = os.environ.get("ANTHROPIC_API_KEY")
    if not cle:
        raise CleAbsente("ANTHROPIC_API_KEY absente : lancer le banc par scripts/banc.sh")
    return cle


def environnement_agent(
    client: str,
    home: Path,
    config_claude: Path,
    chemins: Sequence[Path] = (),
    *,
    cache_1h: bool = False,
) -> dict[str, str]:
    """Liste blanche de D3 pour ce client.

    Args:
        client: claude-code, adk-claude, adk-gemini, graphrag-claude ou graphrag-gemini.
        home: HOME temporaire de l'agent.
        config_claude: CLAUDE_CONFIG_DIR temporaire (aucun réglage ni historique du poste).
        chemins: dossiers d'outils placés devant ceux du système (gcloud, neo4j-mcp).
        cache_1h: cache d'une heure pour Claude Code, au lieu de 5 min (durée tranchée au pilote,
            plan, D10) ; ADK règle le sien par ContextCacheConfig.

    Raises:
        ValueError: client inconnu.
        CleAbsente: cellule Claude sans clé Anthropic.
    """
    gcloud = config_gcloud()
    env = {
        "HOME": str(home),
        "PATH": os.pathsep.join([*map(str, chemins), *CHEMINS_SYSTEME]),
        # Le lanceur de neo4j-mcp y lit le secret de la base, quelle que soit la cellule.
        "CLOUDSDK_CONFIG": str(gcloud),
        # Sans locale, Python la fixerait de lui-même (PEP 538) et l'ajouterait à l'environnement du
        # client : déclarée ici, la liste reste exacte.
        "LC_CTYPE": "C.UTF-8",
    }
    if client == "claude-code":
        env |= {
            "ANTHROPIC_API_KEY": cle_anthropic(),
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": PETIT_MODELE,
            "CLAUDE_CODE_EFFORT_LEVEL": EFFORT,
            "CLAUDE_CONFIG_DIR": str(config_claude),
            # Ni mise à jour du binaire figé, ni télémétrie, ni rapport d'erreur pendant une mesure.
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            # Ni socket de messagerie entre sessions (une autre session du poste pourrait écrire à
            # l'agent), ni mémoire persistante décrite dans le prompt système.
            "CLAUDE_CODE_HARBOR_KITE": "0",
            "CLAUDE_CODE_DISABLE_AUTO_MEMORY": "1",
            "CLAUDE_CODE_MAX_RETRIES": str(REPRISES),
        }
        # Durée explicite, pour toutes les requêtes : sans variable, Claude Code choisit seul.
        env |= {"ENABLE_PROMPT_CACHING_1H": "1"} if cache_1h else {"FORCE_PROMPT_CACHING_5M": "1"}
    elif client in ("adk-claude", "graphrag-claude"):
        env["ANTHROPIC_API_KEY"] = cle_anthropic()
    elif client in ("adk-gemini", "graphrag-gemini"):
        env |= {
            # Chemin explicite : sous un HOME temporaire, l'ADC ne se trouve pas d'elle-même.
            "GOOGLE_APPLICATION_CREDENTIALS": str(gcloud / "application_default_credentials.json"),
            # L'ADC du poste a jleroy-outils pour projet de quota : les appels y seraient comptés.
            "GOOGLE_CLOUD_QUOTA_PROJECT": PROJET,
            "GOOGLE_CLOUD_PROJECT": PROJET,
            "GOOGLE_CLOUD_LOCATION": REGION,
            "GOOGLE_GENAI_USE_ENTERPRISE": "true",
        }
    else:
        raise ValueError(f"client inconnu : {client}")
    return env
