# -*- coding: utf-8 -*-
"""Estado de UNA invocación del plugin (argumentos, parámetros, banderas de reproducción/listado).
init() lo recalcula entero: así el addon puede funcionar con reuselanguageinvoker sin arrastrar estado entre llamadas."""
import sys
from urllib.parse import urlparse

import xbmc
import xbmcvfs

from resources.lib import kodiutils as k

plugin_url = ""
plugin_handle = -1
plugin_query = ""
addon_id_dynamic = "plugin.video.chomiteca"
addon = None
addon_handle = -1
downloadPath = ""
moviesFolder = tvshowFolder = musicvideoFolder = ""
foldertype = 0
params = {}
url = None
name = None
mode_str = None
mode = None
_play_key = None
_play_offset = 0
_eod_done = False
_resolved = False
season_var = ""
season_requested = False
username_setting_global_ref = ""
usernameURL_global_ref = ""


def init():
    """Recalcula el estado a partir de sys.argv y de los ajustes actuales."""
    g = globals()
    argv = sys.argv
    try:
        g["plugin_url"], g["plugin_handle"], g["plugin_query"] = argv[0], int(argv[1]), argv[2]
    except (IndexError, ValueError):
        g["plugin_url"], g["plugin_handle"], g["plugin_query"] = "", -1, ""
        k.log("Chomiteca: no se pudo leer argv.", xbmc.LOGWARNING)
    try:
        parsed = urlparse(argv[0])
        g["addon_id_dynamic"] = parsed.netloc if parsed.scheme == "plugin" else "plugin.video.chomiteca"
    except (IndexError, AttributeError):
        g["addon_id_dynamic"] = "plugin.video.chomiteca"
    from resources.lib.t0mm0 import Addon
    from resources.lib.common import get_params
    g["addon"] = Addon(g["addon_id_dynamic"], argv)
    g["addon_handle"] = g["plugin_handle"]
    g["downloadPath"] = k.ADDON.getSetting("download-folder")
    g["moviesFolder"] = xbmcvfs.translatePath(k.ADDON.getSetting("libraryfolder"))
    g["tvshowFolder"] = xbmcvfs.translatePath(k.ADDON.getSetting("tvshowlibraryfolder"))
    g["musicvideoFolder"] = xbmcvfs.translatePath(k.ADDON.getSetting("musicvideolibraryfolder"))
    try:
        g["foldertype"] = int(k.ADDON.getSetting("folder-type"))
    except ValueError:
        g["foldertype"] = 0
    g["params"] = get_params()
    g["url"] = g["params"].get("url")
    g["name"] = g["params"].get("name")
    g["mode_str"] = g["params"].get("mode")
    g["mode"] = None
    if g["mode_str"] is not None:
        try:
            g["mode"] = int(g["mode_str"])
        except ValueError:
            k.log("Modo inválido: %s" % g["mode_str"], xbmc.LOGERROR)
    g["_play_key"], g["_play_offset"], g["_eod_done"], g["_resolved"] = None, 0, False, False
    g["season_var"], g["season_requested"] = "", False
    g["username_setting_global_ref"], g["usernameURL_global_ref"] = "", ""
