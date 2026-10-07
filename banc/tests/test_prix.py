"""Prix des modèles (D10) : tarifs datés de banc/prix.toml et coût d'un usage."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from banc.prix import PrixError, Usage, charger, tarif

TARIFS = charger()
RELEVE = date(2026, 10, 7)
MILLION = 1_000_000


def test_cout_par_ligne_de_facturation() -> None:
    sonnet = tarif(TARIFS, "claude-sonnet-5-5", RELEVE)
    assert sonnet.cout(Usage(entree=MILLION)) == Decimal("2.20")
    assert sonnet.cout(Usage(sortie=MILLION)) == Decimal(11)
    assert sonnet.cout(Usage(cache_ecriture_5m=MILLION)) == Decimal("2.75")
    assert sonnet.cout(Usage(cache_ecriture_1h=MILLION)) == Decimal("4.40")
    assert sonnet.cout(Usage(cache_lecture=MILLION)) == Decimal("0.22")


def test_cout_d_un_tour() -> None:
    # Consigne et fiche écrites puis relues en cache, question en entrée, réflexion dans la sortie.
    usage = Usage(entree=1_500, sortie=2_000, cache_ecriture_5m=12_000, cache_lecture=36_000)
    prix = (
        1_500 * Decimal("2.20")
        + 2_000 * Decimal(11)
        + 12_000 * Decimal("2.75")
        + 36_000 * Decimal("0.22")
    )
    assert tarif(TARIFS, "claude-sonnet-5-5", RELEVE).cout(usage) == prix / MILLION


def test_usages_additionnes() -> None:
    total = Usage(entree=1, sortie=2, cache_lecture=3) + Usage(entree=10, cache_ecriture_1h=20)
    assert total == Usage(entree=11, sortie=2, cache_ecriture_1h=20, cache_lecture=3)


def test_gemini_change_de_prix_au_1er_janvier() -> None:
    assert tarif(TARIFS, "gemini-3.8-flash", date(2026, 12, 31)).entree == Decimal("0.825")
    assert tarif(TARIFS, "gemini-3.8-flash", date(2027, 1, 1)).entree == Decimal("1.65")


def test_multiplicateurs_du_cache() -> None:
    # Contrôle de saisie : lecture au dixième de l'entrée ; écriture à 1,25 (5 min) et 2 fois (1 h)
    # pour Claude, sans objet pour Gemini (cache implicite).
    for t in TARIFS:
        assert t.cache_lecture * 10 == t.entree, t.modele
        if t.modele.startswith("claude-"):
            assert t.cache_ecriture_5m == t.entree * Decimal("1.25"), t.modele
            assert t.cache_ecriture_1h == t.entree * 2, t.modele


@pytest.mark.parametrize(
    ("modele", "jour"),
    [
        pytest.param("claude-opus-5-5", RELEVE, id="modele-absent"),
        pytest.param("claude-sonnet-5-5", date(2026, 10, 6), id="avant-le-releve"),
    ],
)
def test_tarif_introuvable(modele: str, jour: date) -> None:
    with pytest.raises(PrixError):
        tarif(TARIFS, modele, jour)


def test_periodes_qui_se_chevauchent(tmp_path: Path) -> None:
    periode = (
        '[[tarif]]\nmodele = "m"\ndu = {du}\nau = 2026-12-31\nentree = 1\nsortie = 1\n'
        'cache_ecriture_5m = 1\ncache_ecriture_1h = 1\ncache_lecture = 1\nsource = "s"\n'
    )
    fichier = tmp_path / "prix.toml"
    fichier.write_text(periode.format(du="2026-10-01") + periode.format(du="2026-12-01"))
    with pytest.raises(PrixError):
        charger(fichier)
