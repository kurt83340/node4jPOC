"""Liste blanche de D3 : seul environnement d'un agent, rien hérité de la session du banc."""

from pathlib import Path

import pytest

from banc.isolement import environnement_agent

ATTENDUES = {
    "HOME",
    "PATH",
    "CLOUDSDK_CONFIG",
    "GOOGLE_APPLICATION_CREDENTIALS",
    "GOOGLE_CLOUD_QUOTA_PROJECT",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "GOOGLE_GENAI_USE_ENTERPRISE",
    "CLAUDE_CODE_USE_VERTEX",
    "CLOUD_ML_REGION",
    "ANTHROPIC_VERTEX_PROJECT_ID",
    "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "CLAUDE_CODE_EFFORT_LEVEL",
    "CLAUDE_CONFIG_DIR",
    "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
}


def test_rien_d_herite(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # La session de Claude Code qui lance le banc exporte ses propres réglages.
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "max")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("CLAUDECODE", "1")
    env = environnement_agent(tmp_path / "home", tmp_path / "claude")
    assert set(env) == ATTENDUES
    assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "high"
    assert (env["HOME"], env["CLAUDE_CONFIG_DIR"]) == (
        str(tmp_path / "home"),
        str(tmp_path / "claude"),
    )


def test_vertex_eu_sur_le_projet_du_labo(tmp_path: Path) -> None:
    # Projet de quota compris : sans lui, l'ADC compterait les appels sur jleroy-outils.
    env = environnement_agent(tmp_path / "home", tmp_path / "claude")
    assert {env["CLOUD_ML_REGION"], env["GOOGLE_CLOUD_LOCATION"]} == {"eu"}
    projets = ("ANTHROPIC_VERTEX_PROJECT_ID", "GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_QUOTA_PROJECT")
    assert {env[nom] for nom in projets} == {"jleroy-labo"}


def test_chemins_avant_ceux_du_systeme(tmp_path: Path) -> None:
    outils = [Path("/outils/gcloud"), Path("/outils/neo4j-mcp")]
    env = environnement_agent(tmp_path / "home", tmp_path / "claude", outils)
    assert env["PATH"] == "/outils/gcloud:/outils/neo4j-mcp:/usr/bin:/bin"


def test_configuration_gcloud_du_poste(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Sous un HOME temporaire, Claude Code (Node) ne trouve l'ADC que par son chemin explicite.
    monkeypatch.setenv("CLOUDSDK_CONFIG", "/ailleurs/gcloud")
    env = environnement_agent(tmp_path, tmp_path)
    assert env["CLOUDSDK_CONFIG"] == "/ailleurs/gcloud"
    adc = "/ailleurs/gcloud/application_default_credentials.json"
    assert env["GOOGLE_APPLICATION_CREDENTIALS"] == adc
    monkeypatch.delenv("CLOUDSDK_CONFIG")
    monkeypatch.setenv("HOME", str(tmp_path / "julien"))
    attendu = str(tmp_path / "julien" / ".config" / "gcloud")
    assert environnement_agent(tmp_path, tmp_path)["CLOUDSDK_CONFIG"] == attendu
