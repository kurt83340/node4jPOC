"""Isolement des agents (plan 002, D3) : la liste blanche, seul environnement qu'ils reçoivent.

L'Agent SDK fusionne l'environnement du processus qui l'appelle avec le sien : un agent se lance
donc dans un processus dont l'environnement est cette liste, et rien d'autre (l'équivalent
d'env -i). La session de Claude Code qui lance le banc exporte ses propres réglages (effort max,
modèle…) : aucun ne doit atteindre l'agent mesuré.

La liste dépend du client (ADR-0011) : les cellules Claude reçoivent la clé Anthropic que
scripts/banc.sh passe au harnais, et aucune variable Vertex (CLAUDE_CODE_USE_VERTEX passerait avant
la clé) ; la cellule Gemini reçoit Vertex `eu` par l'ADC, et jamais la clé.
"""

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Final

PROJET = "jleroy-labo"
REGION = "eu"
EFFORT: Final = "high"
PETIT_MODELE = "claude-haiku-4-5-20251001"
CHEMINS_SYSTEME = ("/usr/bin", "/bin")


class CleAbsente(Exception):
    """Une cellule Claude sans clé Anthropic : le banc n'a pas été lancé par scripts/banc.sh."""


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
    client: str, home: Path, config_claude: Path, chemins: Sequence[Path] = ()
) -> dict[str, str]:
    """Liste blanche de D3 pour ce client.

    Args:
        client: claude-code, adk-claude ou adk-gemini.
        home: HOME temporaire de l'agent.
        config_claude: CLAUDE_CONFIG_DIR temporaire (aucun réglage ni historique du poste).
        chemins: dossiers d'outils placés devant ceux du système (gcloud, neo4j-mcp).

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
    }
    if client == "claude-code":
        env |= {
            "ANTHROPIC_API_KEY": cle_anthropic(),
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": PETIT_MODELE,
            "CLAUDE_CODE_EFFORT_LEVEL": EFFORT,
            "CLAUDE_CONFIG_DIR": str(config_claude),
            # Ni mise à jour du binaire figé, ni télémétrie, ni rapport d'erreur pendant une mesure.
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
    elif client == "adk-claude":
        env["ANTHROPIC_API_KEY"] = cle_anthropic()
    elif client == "adk-gemini":
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
