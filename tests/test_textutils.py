# -*- coding: utf-8 -*-
import pytest
from resources.lib.textutils import strip_size_label, real_title


def test_strip_size_label():
    assert strip_size_label("Nombre.mkv [COLOR white](1.2 GB)[/COLOR]") == "Nombre.mkv"


def test_strip_size_label_sin_sufijo():
    assert strip_size_label("Nombre.mkv") == "Nombre.mkv"


def test_strip_size_label_vacio():
    assert strip_size_label("") == ""
    assert strip_size_label(None) == ""


def test_real_title_cirilico():
    assert real_title("Фильм.mkv") == "Фильм.mkv"


def test_real_title_polaco():
    assert real_title("Wałęsa [COLOR white](800 MB)[/COLOR]") == "Wałęsa"


def test_real_title_default_title():
    assert real_title("") == ""
