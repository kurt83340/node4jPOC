"""Sondes d'accès (T0.2) : un appel minimal par client, chacune dans son processus.

Claude passe par l'API Anthropic (ADR-0011), Gemini par Vertex `eu`.

`banc acces` lance `python -m banc.sondes <client> <modèle>` depuis un dossier vide, avec la liste
blanche de D3 pour seul environnement ; la sonde écrit son relevé en une ligne JSON sur stdout.
"""

import asyncio
import json
import sys
import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, SystemMessage, query
from google.adk.agents import LlmAgent
from google.adk.models import Gemini
from google.adk.models.anthropic_llm import AnthropicGenerateContentConfig, AnthropicLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from banc.isolement import EFFORT, PROJET, REGION
from banc.mesures import usage_adk, usage_claude_code
from banc.prix import Usage

QUESTION = "Réponds seulement : OK"
CONSIGNE = "Tu réponds en un seul mot."
# Source d'authentification annoncée par le message init quand la clé vient de l'environnement.
SOURCE_CLE = "ANTHROPIC_API_KEY"


class CleNonUtilisee(Exception):
    """Claude Code ne paie pas par la clé de l'API : coût non mesurable (circuit breaker)."""


@dataclass
class Releve:
    """Ce qu'une sonde rapporte : réponse, tokens par modèle, durée de l'appel, observations."""

    client: str
    modele: str
    reponse: str = ""
    usages: dict[str, Usage] = field(default_factory=dict)
    duree_s: float = 0.0
    observations: dict[str, Any] = field(default_factory=dict)


def verifier_cle(init: Mapping[str, Any]) -> None:
    """Exige que Claude Code s'authentifie par la clé de l'API, jamais par un abonnement."""
    source = init.get("apiKeySource")
    if source != SOURCE_CLE:
        raise CleNonUtilisee(
            f"Claude Code ne paie pas par la clé de l'API : apiKeySource={source!r}"
        )


async def claude_code(modele: str) -> Releve:
    """Claude Code par l'Agent SDK : aucun réglage lu, aucun outil, un seul tour."""
    releve = Releve("claude-code", modele)
    options = ClaudeAgentOptions(
        model=modele,
        system_prompt=CONSIGNE,
        setting_sources=[],
        tools=[],
        max_turns=1,
        cwd=Path.cwd(),
    )
    async for message in query(prompt=QUESTION, options=options):
        if isinstance(message, SystemMessage) and message.subtype == "init":
            verifier_cle(message.data)
            scalaires = {k: v for k, v in message.data.items() if isinstance(v, str | int | bool)}
            releve.observations["init"] = scalaires
        elif isinstance(message, ResultMessage):
            releve.reponse = message.result or ""
            releve.usages = usage_claude_code(message.model_usage or {})
            releve.observations["cout_annonce_usd"] = message.total_cost_usd
            releve.observations["erreur_api"] = message.api_error_status
    return releve


async def adk(client: str, modele: str) -> Releve:
    """ADK avec Claude (effort, réflexion adaptative) ou Gemini (niveau de réflexion)."""
    llm: AnthropicLlm | Gemini
    config: types.GenerateContentConfig
    if client == "adk-claude":
        llm = AnthropicLlm(model=modele)  # clé lue dans ANTHROPIC_API_KEY par le client Anthropic
        adaptative = types.ThinkingConfig(thinking_budget=-1)
        config = AnthropicGenerateContentConfig(effort=EFFORT, thinking_config=adaptative)
    else:
        options = {"enterprise": True, "project": PROJET, "location": REGION}
        llm = Gemini(model=modele, client_kwargs=options)
        niveau = types.ThinkingConfig(thinking_level=types.ThinkingLevel.HIGH)
        config = types.GenerateContentConfig(thinking_config=niveau)
    agent = LlmAgent(name="sonde", model=llm, instruction=CONSIGNE, generate_content_config=config)
    sessions = InMemorySessionService()
    runner = Runner(app_name="banc", agent=agent, session_service=sessions)
    session = await sessions.create_session(app_name="banc", user_id="banc")
    message = types.Content(role="user", parts=[types.Part(text=QUESTION)])
    releve = Releve(client, modele)
    usage, reflexion = Usage(), 0
    async for evenement in runner.run_async(
        user_id="banc", session_id=session.id, new_message=message
    ):
        if evenement.usage_metadata:
            usage += usage_adk(evenement.usage_metadata)
            reflexion += evenement.usage_metadata.thoughts_token_count or 0
        if evenement.content and evenement.content.parts:
            textes = (p.text for p in evenement.content.parts if p.text and not p.thought)
            releve.reponse += "".join(textes)
    releve.usages = {modele: usage}
    releve.observations["reflexion_tokens"] = reflexion
    return releve


def main() -> int:
    """Lance la sonde demandée et écrit son relevé ; une erreur remonte telle quelle (stderr)."""
    client, modele = sys.argv[1:3]
    debut = time.monotonic()
    appel = claude_code(modele) if client == "claude-code" else adk(client, modele)
    releve = asyncio.run(appel)
    releve.duree_s = round(time.monotonic() - debut, 2)
    print(json.dumps(asdict(releve)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
