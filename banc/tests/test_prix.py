"""Prix des modèles (D10) : tarifs datés de banc/prix.toml, par voie d'accès, et coût d'un usage."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from banc.prix import PrixError, Usage, charger, tarif

TARIFS = charger()
RELEVE = date(2026, 10, 7)
MILLION = 1_000_000


def test_cout_par_ligne_de_facturation() -> None:
    sonnet = tarif(TARIFS, "claude-sonnet-5-5", RELEVE, "vertex-eu")
    assert sonnet.cout(Usage(entree=MILLION)) == Decimal("2.20")
    assert sonnet.cout(Usage(sortie=MILLION)) == Decimal(11)
    assert sonnet.cout(Usage(cache_ecriture_5m=MILLION)) == Decimal("2.75")
    assert sonnet.cout(Usage(cache_ecriture_1h=MILLION)) == Decimal("4.40")
    assert sonnet.cout(Usage(cache_lecture=MILLION)) == Decimal("0.22")


def test_api_anthropic() -> None:
    # ADR-0011 : prix de l'API ; lecture du cache de Sonnet 5.5 comptée à 0,20 $ par prudence.
    sonnet = tarif(TARIFS, "claude-sonnet-5-5", RELEVE, "api")
    assert (sonnet.entree, sonnet.sortie) == (Decimal(2), Decimal(10))
    assert (sonnet.cache_ecriture_5m, sonnet.cache_ecriture_1h) == (Decimal("2.5"), Decimal(4))
    assert sonnet.cache_lecture == Decimal("0.2")
    haiku = tarif(TARIFS, "claude-haiku-4-5-20251001", RELEVE, "api")
    assert (haiku.entree, haiku.sortie) == (Decimal(1), Decimal(5))


@pytest.mark.parametrize("modele", ["claude-sonnet-5-5", "claude-sonnet-5"])
def test_prime_de_vertex_eu(modele: str) -> None:
    # Contrôle de saisie : les points multirégionaux de Google Cloud coûtent 10 % de plus que
    # l'API, sur toutes les lignes (page de prix d'Anthropic).
    api = tarif(TARIFS, modele, RELEVE, "api")
    vertex = tarif(TARIFS, modele, RELEVE, "vertex-eu")
    for ligne in ("entree", "sortie", "cache_ecriture_5m", "cache_ecriture_1h", "cache_lecture"):
        assert getattr(vertex, ligne) == getattr(api, ligne) * Decimal("1.1"), ligne


def test_cout_d_un_tour() -> None:
    # Consigne et fiche écrites puis relues en cache, question en entrée, réflexion dans la sortie.
    usage = Usage(entree=1_500, sortie=2_000, cache_ecriture_5m=12_000, cache_lecture=36_000)
    prix = (
        1_500 * Decimal("2.20")
        + 2_000 * Decimal(11)
        + 12_000 * Decimal("2.75")
        + 36_000 * Decimal("0.22")
    )
    assert tarif(TARIFS, "claude-sonnet-5-5", RELEVE, "vertex-eu").cout(usage) == prix / MILLION


def test_usages_additionnes() -> None:
    total = Usage(entree=1, sortie=2, cache_lecture=3) + Usage(entree=10, cache_ecriture_1h=20)
    assert total == Usage(entree=11, sortie=2, cache_ecriture_1h=20, cache_lecture=3)


def test_gemini_change_de_prix_au_1er_janvier() -> None:
    fin = tarif(TARIFS, "gemini-3.8-flash", date(2026, 12, 31), "vertex-eu")
    assert fin.entree == Decimal("0.825")
    assert tarif(TARIFS, "gemini-3.8-flash", date(2027, 1, 1), "vertex-eu").entree == Decimal(
        "1.65"
    )


def test_multiplicateurs_du_cache() -> None:
    # Contrôle de saisie : lecture au dixième de l'entrée ; écriture à 1,25 (5 min) et 2 fois (1 h)
    # pour Claude, sans objet pour Gemini (cache implicite).
    for t in TARIFS:
        assert t.cache_lecture * 10 == t.entree, t.modele
        if t.modele.startswith("claude-"):
            assert t.cache_ecriture_5m == t.entree * Decimal("1.25"), t.modele
            assert t.cache_ecriture_1h == t.entree * 2, t.modele


@pytest.mark.parametrize(
    ("modele", "jour", "acces"),
    [
        pytest.param("claude-opus-5-5", RELEVE, "api", id="modele-absent"),
        pytest.param("claude-sonnet-5-5", date(2026, 10, 6), "api", id="avant-le-releve"),
        pytest.param("gemini-3.8-flash", RELEVE, "api", id="gemini-hors-api"),
        pytest.param("claude-haiku-4-5-20251001", RELEVE, "vertex-eu", id="identifiant-de-l-api"),
    ],
)
def test_tarif_introuvable(modele: str, jour: date, acces: str) -> None:
    with pytest.raises(PrixError):
        tarif(TARIFS, modele, jour, acces)


PERIODE = (
    '[[tarif]]\nmodele = "m"\nacces = "{acces}"\ndu = {du}\nau = 2026-12-31\nentree = 1\n'
    'sortie = 1\ncache_ecriture_5m = 1\ncache_ecriture_1h = 1\ncache_lecture = 1\nsource = "s"\n'
)


def test_periodes_qui_se_chevauchent(tmp_path: Path) -> None:
    fichier = tmp_path / "prix.toml"
    fichier.write_text(
        PERIODE.format(acces="api", du="2026-10-01") + PERIODE.format(acces="api", du="2026-12-01")
    )
    with pytest.raises(PrixError):
        charger(fichier)


def test_meme_periode_sur_deux_acces(tmp_path: Path) -> None:
    fichier = tmp_path / "prix.toml"
    fichier.write_text(
        PERIODE.format(acces="api", du="2026-10-01")
        + PERIODE.format(acces="vertex-eu", du="2026-10-01")
    )
    assert len(charger(fichier)) == 2


@pytest.mark.parametrize("acces", ["bedrock", ""])
def test_acces_inconnu(tmp_path: Path, acces: str) -> None:
    fichier = tmp_path / "prix.toml"
    fichier.write_text(PERIODE.format(acces=acces, du="2026-10-01"))
    with pytest.raises(PrixError):
        charger(fichier)


def test_acces_obligatoire(tmp_path: Path) -> None:
    fichier = tmp_path / "prix.toml"
    fichier.write_text(PERIODE.format(acces="api", du="2026-10-01").replace('acces = "api"\n', ""))
    with pytest.raises(PrixError):
        charger(fichier)
