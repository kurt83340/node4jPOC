"""Sondes de T0.2 : clé de l'API exigée (ADR-0011). Les tokens par ligne de facturation (D10) se
testent avec banc.mesures (tests/test_mesures.py)."""

from typing import Any

import pytest

from banc.isolement import CleNonUtilisee, verifier_cle


def test_cle_de_l_api_acceptee() -> None:
    # Valeur du message init quand la clé vient de l'environnement (Claude Code 2.1.292, hors mode
    # interactif).
    verifier_cle({"apiKeySource": "ANTHROPIC_API_KEY", "model": "claude-sonnet-5-5"})


@pytest.mark.parametrize("source", ["oauth", "none", "apiKeyHelper", "/login managed key", None])
def test_autre_source_refusee(source: str | None) -> None:
    # Par l'abonnement de Julien, le coût ne serait pas mesurable (circuit breaker du plan 002).
    init: dict[str, Any] = {} if source is None else {"apiKeySource": source}
    with pytest.raises(CleNonUtilisee, match="apiKeySource"):
        verifier_cle(init)
