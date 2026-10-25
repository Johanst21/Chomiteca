# -*- coding: utf-8 -*-
"""Utilidades de Kodi: logging con redacción de secretos, notificaciones, rutas."""
import re

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs



class _AddonProxy:
    """Cada acceso crea un xbmcaddon.Addon() nuevo: con reuselanguageinvoker un Addon cacheado puede devolver ajustes viejos."""

    def __getattr__(self, name):
        return getattr(xbmcaddon.Addon(), name)


ADDON = _AddonProxy()
ADDON_ID = ADDON.getAddonInfo("id")
ADDON_NAME = ADDON.getAddonInfo("name")
ADDON_PATH = xbmcvfs.translatePath(ADDON.getAddonInfo("path"))
PROFILE = xbmcvfs.translatePath(ADDON.getAddonInfo("profile"))

# Evita que cookies, tokens y contraseñas acaben en kodi.log (la gente lo comparte en foros).
_SECRET = re.compile(
    r"(?i)(__RequestVerificationToken|token|cookie|password|passwd|key|\.ASPXAUTH|sid)"
    r"(\s*[=:]\s*)([^&;\s\"']+)"
)


_URL_QUERY = re.compile(r"(https?://[^\s?\"']+)\?[^\s\"']*")


def redact(text):
    text = _URL_QUERY.sub(r"\1?***", str(text))  # los enlaces temporales de descarga llevan tokens en la query
    return _SECRET.sub(r"\1\2***", text)


def log(msg, level=xbmc.LOGINFO):
    xbmc.log("[%s] %s" % (ADDON_ID, redact(msg)), level)


def tr(string_id, default=""):
    """Cadena localizada; si falta en el .po devuelve `default` en vez de ''."""
    text = ADDON.getLocalizedString(int(string_id))
    return text or default or str(string_id)


def notify(message, error=False, ms=5000):
    # Dialog().notification evita construir una cadena de executebuiltin
    # (las comillas en `message` rompían/inyectaban en Notification(...)).
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    xbmcgui.Dialog().notification(ADDON_NAME, str(message), icon, ms)
    log(message, xbmc.LOGERROR if error else xbmc.LOGINFO)


def get_bool(setting_id, default=False):
    try:
        return ADDON.getSettingBool(setting_id)
    except Exception:  # ajuste legacy (type="bool" en settings v1) o ausente
        value = ADDON.getSetting(setting_id)
        return (value == "true") if value else default


_MONITOR = xbmc.Monitor()


def wait(seconds):
    """Espera interrumpible: True si Kodi pidió cerrar (hay que abandonar)."""
    return _MONITOR.waitForAbort(seconds)
