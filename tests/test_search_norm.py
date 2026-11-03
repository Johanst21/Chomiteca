import pytest
from resources.lib.search import _norm


def test_norm_lodz():
    assert _norm("Łódź") == "lodz"


def test_norm_walesa():
    assert _norm("Wałęsa") == "walesa"


def test_norm_zolc():
    assert _norm("Żółć") == "zolc"


def test_norm_dzien_dobry():
    assert _norm("Dzień dobry") == "dzien dobry"


def test_norm_lodz_busca():
    assert "lodz" in _norm("Łódź")


def test_norm_vacio():
    assert _norm("") == ""
    assert _norm(None) == ""
