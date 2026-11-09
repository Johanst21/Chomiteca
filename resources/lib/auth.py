# -*- coding: utf-8 -*-
"""Login web de Chomikuj (formulario + __RequestVerificationToken).
NOTA: los marcadores de éxito/fracaso se han portado tal cual del addon original;
no se han podido verificar contra el sitio real desde esta revisión."""
import re

import xbmc

from . import kodiutils as k
from .session import HttpError, text

MAIN_URL = "https://chomikuj.pl/"
_TOKEN = re.compile(r'name="__RequestVerificationToken"[^>]*?value="([^"]+)"')
_OK_MARKERS = ('"LoggedIn":true', '"IsSuccess":true', "ChomikToolbar.IsLogged = true")


class LoginError(Exception):
    pass


def login(session, account):
    """Hace login completo y guarda cookies. Lanza LoginError con mensaje legible."""
    session.jar.clear()  # login fresco: no arrastrar cookies caducadas
    try:
        home = text(session.request(MAIN_URL))
        match = _TOKEN.search(home)
        if not match:
            raise LoginError(k.tr(40036, "No se pudo analizar la página"))
        reply = text(
            session.request(
                MAIN_URL + "action/Login/Login",
                data={
                    "Login": account["username"],
                    "Password": account["password"],
                    "RememberMe": "true",
                    "__RequestVerificationToken": match.group(1),
                },
                headers={"Referer": MAIN_URL},
            )
        )
    except HttpError as exc:
        raise LoginError("HTTP %s" % exc.code) from exc
    except OSError as exc:  # URLError/timeout heredan de OSError
        raise LoginError(str(exc)) from exc

    if "Niepoprawne dane logowania" in reply:
        raise LoginError(k.tr(40002, "Credenciales incorrectas"))
    ok = any(m in reply for m in _OK_MARKERS) or re.search(
        r"<title>.*Pliki użytkownika\s+" + re.escape(account["username"]), reply, re.I
    )
    if not ok:
        k.log("Respuesta de login no reconocida (%d bytes)" % len(reply), xbmc.LOGWARNING)
        raise LoginError(k.tr(40110, "Respuesta de login desconocida").replace("{}", account.get("label", "")))
    session.save()


def verify_session(session, username=None, timeout=15):
    """Check if the given session has valid Chomikuj cookies.

    Returns True if logged in (markers present, username matches if given),
    False otherwise. Never raises.
    """
    try:
        resp = session.request("https://chomikuj.pl/", timeout=timeout)
    except Exception as exc:
        k.log("verify_session: request failed: %r" % exc, xbmc.LOGWARNING)
        return False

    if not resp:
        return False
    try:
        body = resp if isinstance(resp, str) else resp.decode("utf-8", "ignore")
    except Exception:
        return False

    for marker in _OK_MARKERS:
        if marker in body:
            break
    else:
        # None of the markers matched; also try the title regex for robustness
        if not re.search(r"<title>.*Pliki użytkownika", body, re.I):
            return False

    if username:
        # If we got a positive marker, but the page clearly shows a different user,
        # treat as not logged in for THIS account.
        # Only check if we can find "Pliki użytkownika <username>" with a different name.
        title_match = re.search(r"<title>.*Pliki użytkownika\s+(\S+)", body, re.I)
        if title_match and title_match.group(1).lower() != username.lower():
            k.log(
                "verify_session: cookies belong to %s, not %s"
                % (title_match.group(1), username),
                xbmc.LOGWARNING,
            )
            return False

    return True
