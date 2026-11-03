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


def test_real_title_bbcode_b():
    assert real_title("[B]Nombre[/B]") == "Nombre"


def test_real_title_bbcode_multiple():
    assert real_title("[B][COLOR red]Nombre[/COLOR][/B]") == "Nombre"


def test_real_title_html_entity():
    assert real_title("Dom &amp; Rex") == "Dom & Rex"


def test_real_title_html_tag():
    assert real_title("Nombre <i>italica</i>") == "Nombre italica"


def test_real_title_compuesto():
    assert real_title("[B]Wałęsa[/B] [COLOR white](800 MB)[/COLOR]") == "Wałęsa"


def test_real_title_input_no_string():
    assert real_title(12345) == "12345"
