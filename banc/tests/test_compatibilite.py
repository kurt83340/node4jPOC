"""Python 3.14 et les clients mesurés (T0.1) : ce qu'emploieront les cellules existe et s'importe.

Les classifiers de claude-agent-sdk s'arrêtent à 3.13 et sa CI ne teste que 3.12 ; ses roues
sont du Python pur (plus le binaire de Claude Code) : ces imports sous 3.14, sans réseau, en
tiennent lieu de preuve.
"""

import dataclasses
import importlib
import sys

import pytest
from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

# Points d'entrée des cellules (plan, D2 et D3 ; Claude par l'API depuis l'ADR-0011), sous la forme
# (module, nom).
POINTS_D_ENTREE = [
    ("anthropic", "AsyncAnthropic"),
    ("claude_agent_sdk", "ClaudeSDKClient"),
    ("google.adk.agents", "LlmAgent"),
    ("google.adk.models.anthropic_llm", "AnthropicGenerateContentConfig"),
    ("google.adk.models.anthropic_llm", "AnthropicLlm"),
    ("google.adk.runners", "Runner"),
    ("google.adk.sessions", "InMemorySessionService"),
    # Extra « mcp » d'ADK : sans lui, ces deux noms manquent, et ADK ne le dit que dans son journal.
    ("google.adk.tools.mcp_tool", "McpToolset"),
    ("google.adk.tools.mcp_tool", "StdioConnectionParams"),
]
OPTIONS_D3 = {"setting_sources", "tools", "cli_path", "env", "mcp_servers", "max_budget_usd"}


def test_interpreteur() -> None:
    assert sys.version_info[:2] == (3, 14)


@pytest.mark.parametrize(("module", "nom"), POINTS_D_ENTREE)
def test_point_d_entree(module: str, nom: str) -> None:
    assert hasattr(importlib.import_module(module), nom)


def test_options_de_l_isolement() -> None:
    # D3 : réglages ignorés, aucun outil intégré ; binaire, environnement et budget fixés par le
    # harnais ; connexion au serveur MCP vérifiée avant le chrono.
    champs = {champ.name for champ in dataclasses.fields(ClaudeAgentOptions)}
    assert champs >= OPTIONS_D3
    assert callable(ClaudeSDKClient.get_mcp_status)
