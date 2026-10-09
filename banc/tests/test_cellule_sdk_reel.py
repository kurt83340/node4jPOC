"""Cellule Claude Code contre le vrai Claude Code 2.1.292 : le relevé de T4.1, gardé en test (choix
de Julien).

Toute la chaîne de production tourne : la cellule, le SDK, le binaire qu'il embarque, le vrai
lanceur (scripts/mcp-neo4j.sh) ; seuls gcloud, neo4j-mcp et l'API Anthropic sont faux, cette
dernière sur 127.0.0.1 (ANTHROPIC_BASE_URL, seul ajout à la liste blanche). Aucun appel réel, aucun
coût : le CLI mesuré n'ouvre qu'une connexion, vers la fausse API (relevé le 2026-10-09).

Ce qu'un faux cli_path ne peut pas voir : les outils que le vrai client présente au modèle,
l'effort et la durée du cache qu'il envoie, les instructions du serveur retirées par le lanceur,
l'identifiant masqué de bout en bout, un message init conforme (sinon la cellule sort en 2), les
reprises et l'interruption réelles.
"""

import json
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from banc.cellule import Commande, Plafonds, commande_json
from banc.cellule_sdk import MODELE, OUTIL
from banc.isolement import environnement_agent
from banc.mesures import Conversation, lire
from banc.prix import Usage

FIXTURES = Path(__file__).resolve().parent / "fixtures"
CLE = "sk-ant-api03-cle-factice-du-banc"
INSTANCE = "f4c7e9a2"
SECRET = (
    f"NEO4J_URI=neo4j+s://{INSTANCE}.databases.neo4j.io\nNEO4J_USERNAME={INSTANCE}\n"
    f"NEO4J_PASSWORD=mdp-factice-du-banc\nNEO4J_DATABASE={INSTANCE}\n"
)
REQUETE = "CALL db.info() YIELD name RETURN name"
REPONSE = f"Réponse : 42\n\nSources : {REQUETE}"
# Un tour de la fausse API : une lecture (cache écrit), puis la réponse (cache lu) ; 7 tokens de
# réflexion par appel.
TOUR_5M = Usage(entree=1000, sortie=70, cache_ecriture_5m=3000, cache_lecture=3000)
TOUR_1H = Usage(entree=1000, sortie=70, cache_ecriture_1h=3000, cache_lecture=3000)


@dataclass
class Essai:
    """Un lancement : code retour, stderr, trace, et les requêtes reçues par la fausse API."""

    code: int
    erreurs: str
    trace: Conversation | None
    requetes: list[dict[str, Any]]

    def principales(self) -> list[dict[str, Any]]:
        """Requêtes du modèle de la cellule (celles qui portent des outils)."""
        return [r["corps"] for r in self.requetes if r["corps"] and r["corps"].get("tools")]


@dataclass
class Banc:
    """Bac à sable : dossiers de l'agent, faux gcloud et faux neo4j-mcp dans le PATH."""

    racine: Path

    def lancer(self, *questions: tuple[str, str], mode: str = "normal", **reglages: Any) -> Essai:
        journal = self.racine / "journal" / "api.jsonl"
        api = subprocess.Popen(
            [sys.executable, "-I", str(FIXTURES / "fausse_api.py"), str(journal), mode],
            stdout=subprocess.PIPE,
            text=True,
        )
        try:
            assert api.stdout is not None
            port = api.stdout.readline().strip()
            cache_1h = reglages.pop("cache_1h", False)
            commande = Commande(
                campagne="reel",
                passe=1,
                essai=1,
                questions=questions or (("Q1", "Combien de nœuds compte le graphe ?"),),
                traces=self.racine / "traces",
                plafonds=Plafonds(**reglages),
                cache_1h=cache_1h,
            )
            outils = [self.racine / "outils"]
            dossiers = (self.racine / "home", self.racine / "claude")
            env = environnement_agent("claude-code", *dossiers, outils, cache_1h=cache_1h)
            fini = subprocess.run(
                [sys.executable, "-m", "banc.cellule_sdk"],
                input=commande_json(commande),
                cwd=self.racine / "travail",
                env=env | {"ANTHROPIC_BASE_URL": f"http://127.0.0.1:{port}"},
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
        finally:
            api.terminate()
            api.wait()
        traces = list((self.racine / "traces").rglob("*.jsonl"))
        trace = lire(traces[0]) if traces else None
        requetes = [json.loads(ligne) for ligne in journal.read_text().splitlines()]
        return Essai(fini.returncode, fini.stderr, trace, requetes)


def installer(dossier: Path, nom: str, code: str) -> None:
    script = dossier / nom
    script.write_text(f"#!{sys.executable} -I\n{code}")
    script.chmod(0o755)


@pytest.fixture
def banc(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Banc]:
    for dossier in ("home", "claude", "gcloud", "outils", "journal", "travail", "traces"):
        (tmp_path / dossier).mkdir()
    installer(tmp_path / "outils", "gcloud", f"import sys\nsys.stdout.write({SECRET!r})\n")
    installer(tmp_path / "outils", "neo4j-mcp", (FIXTURES / "faux_neo4j_mcp.py").read_text())
    monkeypatch.setenv("ANTHROPIC_API_KEY", CLE)
    monkeypatch.setenv("CLOUDSDK_CONFIG", str(tmp_path / "gcloud"))
    yield Banc(tmp_path)


def test_reponse_du_vrai_client(banc: Banc) -> None:
    essai = banc.lancer()
    # Code 0 : le message init du vrai client est conforme à D3 (clé, read-cypher seul, dontAsk,
    # modèle et version, ni socket entre sessions ni mémoire).
    assert essai.code == 0, essai.erreurs
    assert essai.trace is not None
    (tour,) = essai.trace.tours
    assert (tour.issue, tour.reponse) == ("reponse", REPONSE)
    (appel,) = tour.appels
    assert (appel.outil, appel.requete, appel.erreur) == ("read-cypher", REQUETE, False)
    # L'identifiant de l'instance, renvoyé par le serveur, est masqué avant le client (T3.1).
    assert "‹instance›" in appel.resultat
    assert INSTANCE not in json.dumps(essai.requetes) + appel.resultat
    # Tokens appel par appel, tirés du flux et recoupés par la cellule avec model_usage.
    assert tour.usages == {MODELE: TOUR_5M}
    assert tour.reflexion == {MODELE: 14}


def test_ce_que_le_modele_recoit(banc: Banc) -> None:
    essai = banc.lancer()
    assert essai.code == 0, essai.erreurs
    principales = essai.principales()
    assert len(principales) == 2
    for corps in principales:
        assert [outil["name"] for outil in corps["tools"]] == [OUTIL]
        assert corps["model"] == MODELE
        assert corps["output_config"]["effort"] == "high"
        texte = json.dumps(corps, ensure_ascii=False)
        # Ni get-schema (outil masqué, instructions du serveur retirées par le lanceur), ni budget
        # affiché, ni mémoire persistante décrite.
        for absent in ("get-schema", "official MCP server", "USD budget", "# Memory"):
            assert absent not in texte
        assert "# Consigne" in texte
        assert "# Fiche de schéma" in texte
        # Cache à 5 min forcé tant que le pilote n'a pas tranché (plan, D10).
        assert '"ttl": "1h"' not in texte
    assert all(r["chemin"].startswith("/v1/messages") for r in essai.requetes)


def test_paire_et_cache_d_une_heure(banc: Banc) -> None:
    q2 = ("Q2", "Mon équipe : Pikachu.\n\nQui remplacer ?")
    essai = banc.lancer(q2, ("Q18", "Et si je garde Pikachu ?"), cache_1h=True)
    assert essai.code == 0, essai.erreurs
    assert essai.trace is not None
    assert [tour.issue for tour in essai.trace.tours] == ["reponse", "reponse"]
    # Q18 ne compte pas les tokens de Q2 ; l'écriture à 1 h vient du flux.
    assert [tour.usages for tour in essai.trace.tours] == [{MODELE: TOUR_1H}] * 2
    assert all('"ttl": "1h"' in json.dumps(corps) for corps in essai.principales())


def test_delai_du_vrai_client(banc: Banc) -> None:
    # Le flux s'ouvre, puis plus rien : à l'échéance, interrupt(), et l'appel coupé compte son
    # entrée et son cache (message_start).
    essai = banc.lancer(mode="lent", delai_s=3.0)
    assert essai.code == 0, essai.erreurs
    assert essai.trace is not None
    (tour,) = essai.trace.tours
    assert (tour.issue, tour.cause) == ("echec", "delai")
    assert tour.duree_s is not None and 3.0 <= tour.duree_s < 6.0
    usage = tour.usages[MODELE]
    assert (usage.entree, usage.cache_ecriture_5m) == (900, 3000)


def test_panne_du_vrai_client(banc: Banc) -> None:
    # 429 sans fin : 2 reprises (CLAUDE_CODE_MAX_RETRIES), puis une panne, relancée (D13).
    essai = banc.lancer(mode="429")
    assert essai.code == 0, essai.erreurs
    assert essai.trace is not None
    (tour,) = essai.trace.tours
    assert (tour.issue, tour.cause, tour.reprises) == ("panne", "api", 2)
    assert len(essai.principales()) == 3
