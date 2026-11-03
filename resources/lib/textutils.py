# -*- coding: utf-8 -*-
"""Utilidades de texto ligeras: sin dependencias de Kodi ni de common."""
import re

# Sufijo de tamaño inyectado por ui.decorate_file_item: " [COLOR white](1.2 GB)[/COLOR]"
_SIZE_RE = re.compile(r"\s*\[COLOR[^\]]*\][^\[\]]*\[/COLOR\]\s*$", re.IGNORECASE)


def strip_size_label(text):
    if not text:
        return ""
    return _SIZE_RE.sub("", text).strip()


def real_title(text):
    """Devuelve el nombre real sin BBCode ni sufijos de tamaño. Conserva unicode."""
    if not text:
        return ""
    return strip_size_label(text)
