# -*- coding: utf-8 -*-
"""Sesión HTTP con cookie jar propio (sin install_opener global)."""
import gzip
import http.client
import os
import random
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
import zlib
from http.cookiejar import LWPCookieJar

from . import kodiutils as k, strings

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


RETRY_CODES = (429, 500, 502, 503, 504)


def describe_error(err):
    """Mensaje localizado y accionable para un HttpError / código HTTP / excepción de red."""
    code = err if isinstance(err, int) else getattr(err, "code", None)
    if isinstance(code, int):
        if code in (401, 403):
            return strings.t(40347).format(code)
        if code == 404:
            return strings.t(40348)
        if code == 429:
            return strings.t(40339)
        if code >= 500:
            return strings.t(40338).format(code)
        return "HTTP %s" % code
    reason = getattr(err, "reason", err)
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return strings.t(40340)
    if isinstance(reason, (socket.gaierror, ConnectionError)):
        return strings.t(40341)
    if isinstance(reason, ssl.SSLError):
        return "SSL: %s" % reason
    return str(reason)


def backoff(attempt):
    """Retardo exponencial con jitter: ~0.8s, 1.6s, 3.2s ... (tope 8 s)."""
    return min(8.0, 0.8 * (2 ** attempt)) * (0.5 + random.random())


class HttpError(Exception):
    def __init__(self, code, body=b""):
        super().__init__("HTTP %s" % code)
        self.code = code
        self.body = body


class Session:
    def __init__(self, cookie_path, timeout=20):
        self.cookie_path = cookie_path
        self.timeout = timeout
        self.jar = LWPCookieJar(cookie_path)
        try:
            self.jar.load(ignore_discard=True, ignore_expires=True)
        except (OSError, ValueError):
            pass  # primera ejecución o fichero corrupto -> sesión vacía
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def has_cookies(self):
        return len(self.jar) > 0

    def save(self):
        self.jar.save(ignore_discard=True)
        try:
            os.chmod(self.cookie_path, 0o600)  # no-op en Windows/Android restringido
        except OSError:
            pass

    def clear(self):
        self.jar.clear()
        try:
            os.remove(self.cookie_path)
        except OSError:
            pass

    def request(self, url, data=None, headers=None, retries=0):
        """GET (data=None) o POST (dict). Devuelve bytes; lanza HttpError en >=400.
        retries>0: reintenta (backoff + jitter) ante 429/5xx, timeouts y fallos de conexión."""
        for attempt in range(retries + 1):
            try:
                return self._request_once(url, data, headers)
            except HttpError as exc:
                if exc.code not in RETRY_CODES or attempt == retries:
                    raise
            except OSError:
                if attempt == retries:
                    raise
            if k.wait(backoff(attempt)):  # Kodi se está cerrando
                raise OSError("abort")
        raise OSError("unreachable")

    def _request_once(self, url, data=None, headers=None):
        body = urllib.parse.urlencode(data).encode("utf-8") if data is not None else None
        hdrs = {"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"}
        if body is not None:
            hdrs["Content-Type"] = "application/x-www-form-urlencoded"
        hdrs.update(headers or {})
        req = urllib.request.Request(url, data=body, headers=hdrs)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read()
                enc = (resp.headers.get("Content-Encoding") or "").lower()
        except urllib.error.HTTPError as exc:
            raise HttpError(exc.code, exc.read()[:2000]) from exc
        except (http.client.HTTPException, EOFError, zlib.error) as exc:
            raise OSError("Fallo de lectura/descompresión de red: %r" % exc) from exc
        try:
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                try:
                    raw = zlib.decompress(raw)
                except zlib.error:
                    raw = zlib.decompress(raw, -zlib.MAX_WBITS)
        except (http.client.HTTPException, EOFError, zlib.error) as exc:
            raise OSError("Fallo de lectura/descompresión de red: %r" % exc) from exc
        return raw

    def cookie_header_for(self, url):
        """Cabecera Cookie solo con las cookies cuyo dominio/ruta encajan con `url`."""
        req = urllib.request.Request(url)
        self.jar.add_cookie_header(req)
        return req.get_header("Cookie", "")


def text(raw):
    return raw.decode("utf-8", "ignore")


def make_session():
    os.makedirs(k.PROFILE, exist_ok=True)
    return Session(os.path.join(k.PROFILE, "cookies.lwp"))
