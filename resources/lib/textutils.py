# -*- coding: utf-8 -*-
"""Utilidades de texto ligeras: sin dependencias de Kodi ni de common."""
import html
import re

# Etiquetas BBCode que puede inyectar Kodi en el label
_BBCODE = re.compile(
    r'\[/?(?:B|I|CR|UPPERCASE|LOWERCASE|CAPITALIZE|LIGHT)\]|\[/?COLOR[^\]]*\]',
    re.IGNORECASE,
)
# Sufijo de tamaño: " [COLOR white](1.2 GB)[/COLOR]" al final
_SIZE_RE = re.compile(r"\s*\[COLOR[^\]]*\][^\[\]]*\[/COLOR\]\s*$", re.IGNORECASE)


def strip_size_label(text):
    if not text:
        return ""
    return _SIZE_RE.sub("", text).strip()


def real_title(text):
    """Nombre tal cual está en Chomikuj: sin BBCode, sin HTML, sin sufijo de tamaño. Conserva unicode."""
    try:
        text = text if isinstance(text, str) else str(text)
        text = strip_size_label(text)
        text = _BBCODE.sub("", text)
        text = re.sub(r"<[^>]+>", "", html.unescape(text))
        return re.sub(r"\s+", " ", text).strip()
    except Exception:
        return text if isinstance(text, str) else ""
