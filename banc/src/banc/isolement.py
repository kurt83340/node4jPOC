"""Isolement des agents (plan 002, D3) : la liste blanche, seul environnement qu'ils reçoivent.

L'Agent SDK fusionne l'environnement du processus qui l'appelle avec le sien : un agent se lance
donc dans un processus dont l'environnement est cette liste, et rien d'autre (l'équivalent
d'env -i). La session de Claude Code qui lance le banc exporte ses propres réglages (effort max,
modèle…) : aucun ne doit atteindre l'agent mesuré.
"""

import os
from collections.abc import Sequence
from pathlib import Path
from typing import Final

PROJET = "jleroy-labo"
REGION = "eu"
EFFORT: Final = "high"
PETIT_MODELE = "claude-haiku-4-5@20251001"
CHEMINS_SYSTEME = ("/usr/bin", "/bin")


def config_gcloud() -> Path:
    """Dossier de configuration de gcloud du poste, qui contient les identifiants ADC."""
    return Path(os.environ.get("CLOUDSDK_CONFIG") or Path.home() / ".config" / "gcloud")


def environnement_agent(
    home: Path, config_claude: Path, chemins: Sequence[Path] = ()
) -> dict[str, str]:
    """Liste blanche de D3 : HOME et réglages de Claude Code temporaires, Vertex `eu` par l'ADC.

    Args:
        home: HOME temporaire de l'agent.
        config_claude: CLAUDE_CONFIG_DIR temporaire (aucun réglage ni historique du poste).
        chemins: dossiers d'outils placés devant ceux du système (gcloud, neo4j-mcp).
    """
    gcloud = config_gcloud()
    return {
        "HOME": str(home),
        "PATH": os.pathsep.join([*map(str, chemins), *CHEMINS_SYSTEME]),
        "CLOUDSDK_CONFIG": str(gcloud),
        # Claude Code (Node) ne cherche l'ADC que sous HOME, temporaire ici : chemin explicite.
        "GOOGLE_APPLICATION_CREDENTIALS": str(gcloud / "application_default_credentials.json"),
        # L'ADC du poste a jleroy-outils pour projet de quota : les appels y seraient comptés.
        "GOOGLE_CLOUD_QUOTA_PROJECT": PROJET,
        "GOOGLE_CLOUD_PROJECT": PROJET,
        "GOOGLE_CLOUD_LOCATION": REGION,
        "GOOGLE_GENAI_USE_ENTERPRISE": "true",
        "CLAUDE_CODE_USE_VERTEX": "1",
        "CLOUD_ML_REGION": REGION,
        "ANTHROPIC_VERTEX_PROJECT_ID": PROJET,
        "ANTHROPIC_DEFAULT_HAIKU_MODEL": PETIT_MODELE,
        "CLAUDE_CODE_EFFORT_LEVEL": EFFORT,
        "CLAUDE_CONFIG_DIR": str(config_claude),
        # Ni mise à jour du binaire figé, ni télémétrie, ni rapport d'erreur pendant une mesure.
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
