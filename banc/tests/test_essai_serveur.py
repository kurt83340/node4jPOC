"""Essai du lanceur (banc essai-serveur, spec 002 T7.4) sans base ni réseau.

Un faux neo4j-mcp (tests/fixtures/faux_serveur_mcp.py) répond selon un scénario, choisi par
requête ; un faux transactions.sh rend des comptes rendus prévus. L'essai doit juger chaque
contrôle, ne jamais écrire l'identifiant de l'instance, et ne tuer que le groupe du serveur qu'il a
lancé.
"""

import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from banc import essai_serveur, orchestration
from banc.essai_serveur import Moyens
from banc.orchestration import OrchestrationError

FIXTURES = Path(__file__).parent / "fixtures"
UNE_ARRETEE = "transactions : 1 lecture(s) d'agent arrêtée(s) sur Aura"
AUCUNE = "transactions : aucune lecture d'agent active sur Aura"
TERMINEE = (
    "The transaction has been terminated. Retry your operation in a new transaction, and you "
    "should see a successful result. Explicitly terminated by the user."
)
REFUS = (
    essai_serveur.REFUS
    + ". For write operations (CREATE, MERGE, DELETE, SET, etc...), use write-cypher."
)


def reponses(**changees: dict[str, Any]) -> list[list[Any]]:
    """Réponses du faux serveur par motif de requête ; la première qui correspond l'emporte."""
    base: dict[str, dict[str, Any]] = {
        "UNWIND range": {"lent_s": 1.0, "erreur": True, "texte": TERMINEE},
        "count(t) AS types": {"texte": '[{"types": 18}]'},
        "db.info()": {"texte": '[{"name": "‹instance›"}]'},
        "CREATE (:EssaiEcriture)": {"erreur": True, "texte": REFUS},
        "apoc.create.node": {"erreur": True, "texte": REFUS},
        "count(n) AS temoins": {"texte": '[{"temoins": 0}]'},
        "< 0 RETURN count(*)": {"lent_s": 0.05, "texte": '[{"lignes": 0}]'},
    }
    return [[motif, changees.get(motif, reponse)] for motif, reponse in base.items()]


@dataclass
class FauxNettoyage:
    """transactions.sh : un compte rendu ou une erreur par appel (départ, serveur vivant, serveur
    tué), puis « aucune »."""

    prevus: list[str | Exception] = field(default_factory=lambda: [AUCUNE, UNE_ARRETEE, AUCUNE])
    appels: int = 0

    def __call__(self) -> str:
        self.appels += 1
        prevu = self.prevus.pop(0) if self.prevus else AUCUNE
        if isinstance(prevu, Exception):
            raise prevu
        return prevu


@dataclass
class Essai:
    code: int
    lignes: list[str]
    erreurs: str
    nettoyage: FauxNettoyage
    journal: list[dict[str, Any]]

    def ligne(self, debut: str) -> str:
        trouvees = [ligne for ligne in self.lignes if ligne.startswith(debut)]
        assert len(trouvees) == 1, (debut, self.lignes)
        return trouvees[0]


@pytest.fixture
def lancer(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> Any:
    def lancer(
        scenario: dict[str, Any] | None = None,
        nettoyage: FauxNettoyage | None = None,
        serveur: tuple[str, ...] | None = None,
    ) -> Essai:
        fichier = tmp_path / "scenario.json"
        fichier.write_text(json.dumps({"par_requete": reponses()} | (scenario or {})))
        journal = tmp_path / "journal.jsonl"
        nettoyage = nettoyage or FauxNettoyage()
        lignes: list[str] = []
        moyens = Moyens(
            serveur=serveur
            or (
                sys.executable,
                "-I",
                str(FIXTURES / "faux_serveur_mcp.py"),
                str(fichier),
                str(journal),
            ),
            nettoyer=nettoyage,
            chemins=lambda: (),
            connexion_s=10.0,
            demarrage_s=0.2,
            cible_s=1.0,
            reponse_s=5.0,
            ecrire=lignes.append,
        )
        code = essai_serveur.commande(moyens)
        notes = journal.read_text().splitlines() if journal.exists() else []
        return Essai(
            code, lignes, capsys.readouterr().err, nettoyage, [json.loads(n) for n in notes]
        )

    return lancer


def test_tout_conforme(lancer: Any) -> None:
    essai = lancer()
    assert essai.code == 0, essai.lignes
    assert essai.lignes[-1] == "CONFORME : 12 contrôles."
    assert essai.ligne("✓ serveur :") == "✓ serveur : neo4j-mcp v1.6.0"
    assert (
        essai.ligne("✓ outils du serveur")
        == "✓ outils du serveur, en lecture seule : get-schema, read-cypher"
    )
    assert (
        essai.ligne("✓ outils vus d'une cellule ADK")
        == "✓ outils vus d'une cellule ADK : read-cypher"
    )
    assert essai.ligne("✓ identifiant") == ("✓ identifiant de l'instance masqué : ‹instance›")
    assert essai.ligne("✓ lecture lente arrêtée").startswith(
        "✓ lecture lente arrêtée par transactions.sh, serveur vivant : 1 arrêtée(s) ; read-cypher"
    )
    assert essai.ligne("✓ serveur tué") == (
        "✓ serveur tué pendant une lecture lente, puis transactions.sh : "
        "plus aucune lecture d'agent (Aura l'avait arrêtée)"
    )
    # Départ, serveur vivant, serveur tué.
    assert essai.nettoyage.appels == 3
    assert essai.lignes[0] == f"  · départ : {AUCUNE}"


def test_trois_serveurs_lances_le_dernier_tue(lancer: Any) -> None:
    # Le serveur des contrôles, celui de la vue ADK, puis celui qu'on tue pendant sa lecture lente :
    # il a reçu la lecture et n'y a jamais répondu.
    essai = lancer()
    assert essai.code == 0, essai.lignes
    lancements = [note for note in essai.journal if "pid" in note]
    assert len(lancements) == 3
    dernier = lancements[-1]["pid"]
    notes = essai.journal[essai.journal.index(lancements[-1]) :]
    recues = [n["recu"] for n in notes if "recu" in n and n["recu"].get("method") == "tools/call"]
    assert ["UNWIND range" in r["params"]["arguments"]["query"] for r in recues] == [True]
    assert not any(n.get("repondu") == "tools/call" for n in notes)
    with pytest.raises(ProcessLookupError):
        os.kill(dernier, 0)


def test_seul_le_groupe_du_serveur_est_tue(lancer: Any) -> None:
    # Un autre processus du poste, dans sa propre session (une cellule, un autre serveur) : l'essai
    # ne vise que le groupe qu'il a lancé.
    voisin = subprocess.Popen(["sleep", "30"], start_new_session=True)
    try:
        essai = lancer()
        assert essai.code == 0, essai.lignes
        assert voisin.poll() is None
    finally:
        voisin.kill()
        voisin.wait()


def test_lecture_lente_parametree_par_l_etalon(lancer: Any) -> None:
    essai = lancer()
    lentes = [
        n["recu"]["params"]["arguments"]
        for n in essai.journal
        if "recu" in n
        and n["recu"].get("method") == "tools/call"
        and "UNWIND range" in n["recu"]["params"]["arguments"]["query"]
    ]
    assert len(lentes) == 2
    # Étalon d'au moins 0,05 s pour une cible de 1 s : au plus 20 répétitions, les mêmes deux fois.
    assert 3 <= lentes[0]["params"]["repetitions"] <= 20
    assert lentes[0]["params"] == lentes[1]["params"]
    assert essai.ligne("  · étalon").startswith("  · étalon : 34 012 224 lignes en ")


def test_ecriture_ouverte(lancer: Any) -> None:
    essai = lancer({"outils": ["get-schema", "read-cypher", "write-cypher"]})
    assert essai.code == 1
    assert "write-cypher : écriture ouverte, NEO4J_MCP_READ_ONLY ignoré" in essai.ligne(
        "✗ outils du serveur"
    )
    assert essai.lignes[-1] == "ÉCART : 1 contrôle(s) sur 12."


def test_instructions_presentes(lancer: Any) -> None:
    essai = lancer({"instructions": "Infer the schema with tools like get-schema."})
    assert essai.code == 1
    assert (
        essai.ligne("✗ instructions")
        == "✗ instructions du serveur retirées par le lanceur : présentes"
    )


def test_autre_version(lancer: Any) -> None:
    essai = lancer({"version": "v1.7.0"})
    assert essai.code == 1
    assert essai.ligne("✗ serveur :") == "✗ serveur : neo4j-mcp v1.7.0"


def test_lecture_fausse(lancer: Any) -> None:
    essai = lancer({"par_requete": reponses(**{"count(t) AS types": {"texte": '[{"types": 17}]'}})})
    assert essai.code == 1
    assert essai.ligne("✗ read-cypher répond") == "✗ read-cypher répond : 17 types"


def test_identifiant_non_masque_jamais_ecrit(lancer: Any) -> None:
    identifiant = "a1b2c3d4"
    essai = lancer(
        {"par_requete": reponses(**{"db.info()": {"texte": f'[{{"name": "{identifiant}"}}]'}})}
    )
    assert essai.code == 1
    assert essai.ligne("✗ identifiant") == "✗ identifiant de l'instance masqué : non masqué"
    assert identifiant not in "\n".join(essai.lignes) + essai.erreurs


def test_ecriture_acceptee(lancer: Any) -> None:
    essai = lancer(
        {"par_requete": reponses(**{"CREATE (:EssaiEcriture)": {"texte": '[{"cree": 1}]'}})}
    )
    assert essai.code == 1
    # CREATE seul et CREATE dans un CALL portent le même motif : les deux passent.
    ouverte = "ACCEPTÉE : écriture ouverte (circuit breaker : aucune mesure)"
    acceptees = [ligne for ligne in essai.lignes if "ACCEPTÉE" in ligne]
    assert acceptees == [
        f"✗ écriture refusée, CREATE : {ouverte}",
        f"✗ écriture refusée, CREATE dans un CALL : {ouverte}",
    ]


def test_ecriture_refusee_pour_une_autre_raison(lancer: Any) -> None:
    # Une procédure absente est refusée, mais pas parce qu'elle écrit : le contrôle ne prouve rien.
    absente = (
        "There is no procedure with the name `apoc.create.node` registered for this database "
        "instance."
    )
    essai = lancer(
        {"par_requete": reponses(**{"apoc.create.node": {"erreur": True, "texte": absente}})}
    )
    assert essai.code == 1
    assert essai.ligne("✗ écriture refusée, procédure APOC").startswith(
        "✗ écriture refusée, procédure APOC d'écriture : autre erreur : There is no procedure"
    )


def test_temoin_ecrit(lancer: Any) -> None:
    essai = lancer(
        {"par_requete": reponses(**{"count(n) AS temoins": {"texte": '[{"temoins": 1}]'}})}
    )
    assert essai.code == 1
    assert essai.ligne("✗ nœuds EssaiEcriture") == "✗ nœuds EssaiEcriture dans la base : 1"


def test_lecture_lente_trop_courte(lancer: Any) -> None:
    essai = lancer({"par_requete": reponses(**{"UNWIND range": {"texte": '[{"lignes": 0}]'}})})
    assert essai.code == 1
    assert "finie avant l'arrêt, à rendre plus lente" in essai.ligne("✗ lecture lente arrêtée")
    assert "lecture finie avant que le serveur soit tué" in essai.ligne("✗ serveur tué")


def test_transactions_n_arrete_rien(lancer: Any) -> None:
    essai = lancer(nettoyage=FauxNettoyage([AUCUNE, AUCUNE, AUCUNE]))
    assert essai.code == 1
    assert essai.ligne("✗ lecture lente arrêtée").startswith(
        "✗ lecture lente arrêtée par transactions.sh, serveur vivant : 0 arrêtée(s)"
    )


def test_read_cypher_sans_erreur_apres_l_arret(lancer: Any) -> None:
    lente = {"lent_s": 1.0, "texte": '[{"lignes": 0}]'}
    essai = lancer({"par_requete": reponses(**{"UNWIND range": lente})})
    assert essai.code == 1
    assert "1 arrêtée(s)" in essai.ligne("✗ lecture lente arrêtée")


def test_transactions_en_echec(lancer: Any) -> None:
    refus = OrchestrationError(
        "transactions.sh : code 2 transactions.sh : arrêt des lectures refusé"
    )
    essai = lancer(nettoyage=FauxNettoyage([AUCUNE, refus, refus]))
    assert essai.code == 1
    assert essai.ligne("✗ lecture lente arrêtée").endswith(
        "transactions.sh en échec : " + str(refus)
    )
    assert essai.ligne("✗ serveur tué").endswith("transactions.sh en échec : " + str(refus))


def test_serveur_tue_et_lecture_que_transactions_arrete(lancer: Any) -> None:
    essai = lancer(nettoyage=FauxNettoyage([AUCUNE, UNE_ARRETEE, UNE_ARRETEE]))
    assert essai.code == 0
    assert essai.ligne("✓ serveur tué").endswith(
        "plus aucune lecture d'agent (transactions.sh l'a arrêtée, Aura la gardait)"
    )


def test_sans_read_cypher(lancer: Any) -> None:
    essai = lancer({"outils": ["get-schema"]})
    assert essai.code != 0
    assert essai.ligne("✗ outils vus d'une cellule ADK") == "✗ outils vus d'une cellule ADK : aucun"


def test_serveur_introuvable(lancer: Any, tmp_path: Path) -> None:
    essai = lancer(serveur=(str(tmp_path / "absent"),))
    assert essai.code == 2
    assert "banc essai-serveur :" in essai.erreurs


def test_etalon_en_echec(lancer: Any) -> None:
    echec = {"erreur": True, "texte": "Neo.TransientError.General.MemoryPoolOutOfMemoryError"}
    essai = lancer({"par_requete": reponses(**{"< 0 RETURN count(*)": echec})})
    assert essai.code == 2
    assert "étalon de la lecture lente en échec" in essai.erreurs


def test_rien_ne_survit(lancer: Any) -> None:
    lancer()
    restes = orchestration.descendants(os.getpid())
    assert not [pid for pid, _groupe in restes if "faux_serveur_mcp" in _cmdline(pid)]


def _cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_text().replace("\0", " ")
    except OSError:
        return ""
