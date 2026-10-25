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
