"""Tokens rapportés par chaque client, ramenés aux lignes de facturation (D10)."""

from typing import Any

from google.genai import types

from banc.prix import Usage
from banc.sondes import usage_adk, usage_claude_code


def test_claude_code_par_modele() -> None:
    # ResultMessage.model_usage : un compte par modèle, petit modèle compris.
    model_usage: dict[str, dict[str, Any]] = {
        "claude-sonnet-5-5": {
            "inputTokens": 10,
            "outputTokens": 20,
            "cacheReadInputTokens": 30,
            "cacheCreationInputTokens": 40,
            "costUSD": 0.001,
        },
        "claude-haiku-4-5@20251001": {"inputTokens": 5, "outputTokens": 1},
    }
    assert usage_claude_code(model_usage) == {
        "claude-sonnet-5-5": Usage(entree=10, sortie=20, cache_ecriture_5m=40, cache_lecture=30),
        "claude-haiku-4-5@20251001": Usage(entree=5, sortie=1),
    }


def test_adk_claude() -> None:
    # ADK replie entrée, lecture et écriture du cache dans prompt_token_count, et sépare la
    # réflexion de la sortie (google/adk/models/anthropic_llm.py).
    meta = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=100,
        cached_content_token_count=30,
        candidates_token_count=5,
        thoughts_token_count=7,
    )
    object.__setattr__(meta, "cache_creation_input_tokens", 60)
    assert usage_adk(meta) == Usage(entree=10, sortie=12, cache_ecriture_5m=60, cache_lecture=30)


def test_adk_gemini() -> None:
    meta = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=100, cached_content_token_count=40, candidates_token_count=3
    )
    assert usage_adk(meta) == Usage(entree=60, sortie=3, cache_lecture=40)
