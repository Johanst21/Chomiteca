# -*- coding: utf-8 -*-
"""Resolución de la URL directa y temporal de un fichero de Chomikuj."""
import html
import re
import urllib.parse
from dataclasses import dataclass

import xbmc

from . import kodiutils as k
from .auth import MAIN_URL
from .session import USER_AGENT, HttpError, text

ALLOWED_SUFFIX = "chomikuj.pl"
_FILE_ID = (
    re.compile(r'(?:name|id)=["\']FileId["\'].*?value=["\'](\d+)["\']', re.I),
    re.compile(r'fileId["\']?\s*[:=]\s*["\']?(\d+)'),
    re.compile(r'data-file-id=["\'](\d+)["\']'),
)
_TOKEN = (
    re.compile(r'name=["\']__RequestVerificationToken["\'].*?value=["\']([^"\']+)["\']', re.I),
    re.compile(r'antiForgeryToken["\']?\s*[:=]\s*["\']([^"\']+)["\']'),
)
_URL_PATTERNS = (
    re.compile(r'"redirectUrl"\s*:\s*"([^"]+)"'),
    re.compile(r'<a[^>]+(?:id="downloadLink"|class="[^"]*?downloadButton[^"]*?")[^>]*?href="([^"]+)"', re.I),
    re.compile(r'location\.href\s*=\s*["\']([^"\']+)["\']'),
    re.compile(r'href=["\'](https?://[^"\']*?chomikuj\.pl/action/(?:Download|Preview)[^"\']+)["\']', re.I),
)
# Mensajes de error conocidos -> id de cadena existente en strings.po
_ERRORS = (
    (re.compile(r"Please try to download this file later"), 40026),
    (re.compile(r"limit transferu", re.I), 40114),
    (re.compile(r"plik zosta\w* usuni\w*", re.I), 40065),  # el original comparaba con `in` y nunca coincidía
    (re.compile(r"has[łl]o|password", re.I), 40061),
)


class ResolveError(Exception):
    def __init__(self, message, relogin=False):
        super().__init__(message)
        self.relogin = relogin  # True si probablemente la sesión caducó: conviene reloguear y reintentar


def normalize_url(url):
    """Codifica solo la ruta (STRM de Jellyfin/Emby traen espacios sin escapar). unquote -> quote es
    idempotente y, a diferencia del unquote_plus original, no convierte un '+' real del nombre en espacio."""
    parsed = urllib.parse.urlparse(url.strip())
    path = urllib.parse.quote(urllib.parse.unquote(parsed.path), safe="/:*()")
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, path, parsed.params, parsed.query, parsed.fragment))


@dataclass
class ResolvedLink:
    url: str
    headers: dict


def host_allowed(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host == ALLOWED_SUFFIX or host.endswith("." + ALLOWED_SUFFIX)


def _first(patterns, source):
    for pattern in patterns:
        match = pattern.search(source)
        if match:
            return match.group(1)
    return None


def _json_unescape(s):
    return (s.replace("\\u0026", "&").replace("\\u003c", "<").replace("\\u003e", ">")
             .replace("\\/", "/").replace("\\\\", "\\"))


def _post_with_retry(session, url, data, referer, monitor, tries=3):
    last = None
    for attempt in range(tries):
        try:
            body = session.request(
                url, data=data,
                headers={"Referer": referer, "Origin": MAIN_URL.rstrip("/"),
                         "X-Requested-With": "XMLHttpRequest", "Accept": "*/*"},
            )
            if body:
                return _json_unescape(text(body))
        except HttpError as exc:
            last = exc
            if exc.code in (401, 403, 404):  # no se arregla reintentando
                break
        except OSError as exc:
            last = exc
        if attempt < tries - 1 and monitor.waitForAbort(1 + attempt):  # backoff y respeta cierre de Kodi
            raise ResolveError("abort")
    raise ResolveError(k.tr(40027, "No se pudo obtener el enlace") + (" (%s)" % last if last else ""))


def resolve(session, page_url, monitor=None):
    monitor = monitor or xbmc.Monitor()
    if not host_allowed(page_url):
        raise ResolveError("URL fuera de chomikuj.pl: %s" % urllib.parse.urlparse(page_url).hostname)
    try:
        page = text(session.request(page_url, headers={"Referer": MAIN_URL}, retries=2))
    except HttpError as exc:
        raise ResolveError(k.tr(40032, "Error de red") + " (HTTP %s)" % exc.code,
                           relogin=exc.code in (401, 403)) from exc
    except OSError as exc:
        raise ResolveError(k.tr(40032, "Error de red") + " (%s)" % exc) from exc

    file_id, token = _first(_FILE_ID, page), _first(_TOKEN, page)
    if not (file_id and token):
        raise ResolveError(k.tr(40036, "No se pudo analizar la página") + " (FileId/Token)", relogin=True)

    reply = _post_with_retry(session, MAIN_URL + "action/License/Download",
                             {"fileId": file_id, "__RequestVerificationToken": token}, page_url, monitor)

    if "/action/License/acceptLargeTransfer" in reply:
        form = {name: _first([re.compile(r'name="%s".*?value="([^"]+)"' % name)], reply)
                for name in ("fileId", "orgFile", "userSelection", "__RequestVerificationToken")}
        if not (form["fileId"] and form["orgFile"] and form["__RequestVerificationToken"]):
            raise ResolveError(k.tr(40036, "No se pudo analizar la página") + " (LargeTransfer)")
        form["userSelection"] = form["userSelection"] or "True"
        reply = _post_with_retry(session, MAIN_URL + "action/License/acceptLargeTransfer", form, page_url, monitor)

    found = _first(_URL_PATTERNS, reply)
    if not found:
        for pattern, string_id in _ERRORS:
            if pattern.search(reply):
                raise ResolveError(k.tr(string_id))
        k.log("Sin URL final; respuesta de %d bytes" % len(reply), xbmc.LOGWARNING)  # no volcar el cuerpo
        raise ResolveError(k.tr(40027, "No se pudo obtener el enlace"))

    final = urllib.parse.urljoin(page_url, html.unescape(found.replace("\\/", "/")).strip())
    if urllib.parse.urlparse(final).scheme not in ("http", "https") or not host_allowed(final):
        # Nunca mandar cookies de sesión a un host que no sea de Chomikuj.
        raise ResolveError("Host de descarga no permitido: %s" % urllib.parse.urlparse(final).hostname)

    headers = {"User-Agent": USER_AGENT}
    cookie = session.cookie_header_for(final)
    if cookie:
        headers["Cookie"] = cookie
    k.log("Enlace resuelto en %s" % urllib.parse.urlparse(final).hostname)  # sin ruta ni query
    return ResolvedLink(final, headers)

