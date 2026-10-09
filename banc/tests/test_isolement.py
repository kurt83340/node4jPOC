"""Liste blanche de D3, par client (ADR-0011) : seul environnement d'un agent, rien d'hérité."""

from pathlib import Path

import pytest

from banc.isolement import CleAbsente, environnement_agent

CLE = "sk-ant-api03-cle-factice-du-banc"
COMMUNES = {"HOME", "PATH", "CLOUDSDK_CONFIG", "LC_CTYPE"}
ATTENDUES = {
    "claude-code": COMMUNES
    | {
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "CLAUDE_CODE_EFFORT_LEVEL",
        "CLAUDE_CONFIG_DIR",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC",
        "CLAUDE_CODE_HARBOR_KITE",
        "CLAUDE_CODE_DISABLE_AUTO_MEMORY",
        "CLAUDE_CODE_MAX_RETRIES",
        "FORCE_PROMPT_CACHING_5M",
    },
    "adk-claude": COMMUNES | {"ANTHROPIC_API_KEY"},
    "adk-gemini": COMMUNES
    | {
        "GOOGLE_APPLICATION_CREDENTIALS",
        "GOOGLE_CLOUD_QUOTA_PROJECT",
        "GOOGLE_CLOUD_PROJECT",
        "GOOGLE_CLOUD_LOCATION",
        "GOOGLE_GENAI_USE_ENTERPRISE",
    },
}
CLAUDE = ["claude-code", "adk-claude"]


@pytest.fixture(autouse=True)
def cle(monkeypatch: pytest.MonkeyPatch) -> None:
    """La clé que scripts/banc.sh passe au harnais par son environnement."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)


@pytest.mark.parametrize("client", list(ATTENDUES))
def test_rien_d_herite(client: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # La session de Claude Code qui lance le banc exporte ses propres réglages.
    monkeypatch.setenv("CLAUDE_CODE_EFFORT_LEVEL", "max")
    monkeypatch.setenv("ANTHROPIC_MODEL", "claude-opus-5-5")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
    env = environnement_agent(client, tmp_path / "home", tmp_path / "claude")
    assert set(env) == ATTENDUES[client]


def test_claude_code_par_la_cle(tmp_path: Path) -> None:
    env = environnement_agent("claude-code", tmp_path / "home", tmp_path / "claude")
    assert env["ANTHROPIC_API_KEY"] == CLE
    assert env["CLAUDE_CODE_EFFORT_LEVEL"] == "high"
    # Identifiant de l'API ; « @20251001 » est la forme de Google.
    assert env["ANTHROPIC_DEFAULT_HAIKU_MODEL"] == "claude-haiku-4-5-20251001"
    assert (env["HOME"], env["CLAUDE_CONFIG_DIR"]) == (
        str(tmp_path / "home"),
        str(tmp_path / "claude"),
    )


def test_claude_code_hors_du_poste(tmp_path: Path) -> None:
    # Relevé T4.1 sur le vrai Claude Code 2.1.292 : sans ces réglages, la session ouvre une socket
    # de messagerie dans /tmp/cc-socks/ (joignable par les autres sessions du poste), décrit une
    # mémoire persistante à l'agent, et reprend jusqu'à 10 fois un appel en échec.
    env = environnement_agent("claude-code", tmp_path / "home", tmp_path / "claude")
    assert env["CLAUDE_CODE_HARBOR_KITE"] == "0"
    assert env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
    # Autant de reprises que le client Anthropic d'ADK (plan, D13).
    assert env["CLAUDE_CODE_MAX_RETRIES"] == "2"


def test_cache_a_5_minutes_par_defaut(tmp_path: Path) -> None:
    # Durée tranchée au pilote (plan, D10) : 5 min forcées tant qu'elle ne l'est pas.
    env = environnement_agent("claude-code", tmp_path / "home", tmp_path / "claude")
    assert env["FORCE_PROMPT_CACHING_5M"] == "1"
    assert "ENABLE_PROMPT_CACHING_1H" not in env


def test_cache_a_1_heure(tmp_path: Path) -> None:
    env = environnement_agent("claude-code", tmp_path / "home", tmp_path / "claude", cache_1h=True)
    cinq_minutes, une_heure = "FORCE_PROMPT_CACHING_5M", "ENABLE_PROMPT_CACHING_1H"
    assert set(env) == ATTENDUES["claude-code"] - {cinq_minutes} | {une_heure}
    assert env["ENABLE_PROMPT_CACHING_1H"] == "1"


@pytest.mark.parametrize("client", ["adk-claude", "adk-gemini"])
def test_cache_d_adk_hors_environnement(client: str, tmp_path: Path) -> None:
    # ADK règle son cache par ContextCacheConfig (T4.2), pas par une variable.
    env = environnement_agent(client, tmp_path, tmp_path, cache_1h=True)
    assert set(env) == ATTENDUES[client]


@pytest.mark.parametrize("client", CLAUDE)
def test_claude_sans_vertex(client: str, tmp_path: Path) -> None:
    # CLAUDE_CODE_USE_VERTEX passerait avant la clé dans l'ordre d'authentification de Claude Code.
    env = environnement_agent(client, tmp_path, tmp_path)
    assert not [nom for nom in env if "VERTEX" in nom or nom.startswith(("GOOGLE_", "CLOUD_ML"))]
    assert env["ANTHROPIC_API_KEY"] == CLE


def test_gemini_sur_vertex_eu_sans_la_cle(tmp_path: Path) -> None:
    # Projet de quota compris : sans lui, l'ADC compterait les appels sur jleroy-outils.
    env = environnement_agent("adk-gemini", tmp_path, tmp_path)
    assert all(CLE not in valeur for valeur in env.values())
    assert env["GOOGLE_CLOUD_LOCATION"] == "eu"
    projets = ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_QUOTA_PROJECT")
    assert {env[nom] for nom in projets} == {"jleroy-labo"}


@pytest.mark.parametrize("client", CLAUDE)
@pytest.mark.parametrize("valeur", [None, ""], ids=["absente", "vide"])
def test_cle_absente(
    client: str, valeur: str | None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    if valeur is None:
        monkeypatch.delenv("ANTHROPIC_API_KEY")
    else:
        monkeypatch.setenv("ANTHROPIC_API_KEY", valeur)
    with pytest.raises(CleAbsente, match=r"scripts/banc\.sh"):
        environnement_agent(client, tmp_path, tmp_path)


def test_gemini_n_exige_pas_la_cle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY")
    assert set(environnement_agent("adk-gemini", tmp_path, tmp_path)) == ATTENDUES["adk-gemini"]


def test_client_inconnu(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="client inconnu"):
        environnement_agent("claude-vertex", tmp_path, tmp_path)


def test_chemins_avant_ceux_du_systeme(tmp_path: Path) -> None:
    outils = [Path("/outils/gcloud"), Path("/outils/neo4j-mcp")]
    env = environnement_agent("adk-gemini", tmp_path / "home", tmp_path / "claude", outils)
    assert env["PATH"] == "/outils/gcloud:/outils/neo4j-mcp:/usr/bin:/bin"


def test_configuration_gcloud_du_poste(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # Le lanceur de neo4j-mcp y lit le secret de la base dans toutes les cellules ; Gemini y prend
    # aussi l'ADC, par son chemin explicite (le HOME de l'agent est temporaire).
    monkeypatch.setenv("CLOUDSDK_CONFIG", "/ailleurs/gcloud")
    for client in ATTENDUES:
        assert (
            environnement_agent(client, tmp_path, tmp_path)["CLOUDSDK_CONFIG"] == "/ailleurs/gcloud"
        )
    adc = "/ailleurs/gcloud/application_default_credentials.json"
    assert (
        environnement_agent("adk-gemini", tmp_path, tmp_path)["GOOGLE_APPLICATION_CREDENTIALS"]
        == adc
    )
    monkeypatch.delenv("CLOUDSDK_CONFIG")
    monkeypatch.setenv("HOME", str(tmp_path / "julien"))
    attendu = str(tmp_path / "julien" / ".config" / "gcloud")
    assert environnement_agent("adk-gemini", tmp_path, tmp_path)["CLOUDSDK_CONFIG"] == attendu
