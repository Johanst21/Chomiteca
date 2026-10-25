# -*- coding: utf-8 -*-
"""Despacho de modos (punto de entrada de navegación)."""
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs
import os, re, sys, time, traceback, unicodedata, sqlite3, stat
import urllib.request, urllib.parse, urllib.error
import random, threading, time as _time, json
from xml.sax.saxutils import escape as _xml_escape
from html.parser import HTMLParser
import html
from urllib.parse import urlparse
from http.cookiejar import MozillaCookieJar

from resources.lib.t0mm0 import Net, Addon
from resources.lib.dictionary import dictionary
from resources.lib import kodiutils as k
from resources.lib import auth, player, resolver, strings
from resources.lib import cache as cache_mod, metadata, playstate, store
from resources.lib import downloadqueue as dq
from resources.lib.session import make_session, describe_error, backoff
from resources.lib import state as st

from resources.lib.common import MODE_DELETE_COOKIES, MODE_MANAGE_ACCOUNTS, MODE_SETTINGS, MODE_STRM_GEN_DIALOG, MainURL, caixadetexto, cookies, delete_cookies, init_user_refs, notify, selfAddon, traducao
from resources.lib.ui import end_directory


def main(handle=None, router_params=None):
    """Despacho de los modos de navegación/gestión. Reproducción (4, 25) la resuelve router.py."""
    st.init()
    pass
    st._play_key, st._play_offset, st._resolved, st._eod_done = None, 0, False, False
    init_user_refs()
    k.log(f"--- Chomiteca Start --- Mode: {st.mode}", xbmc.LOGINFO)
    if st.plugin_handle != -1:
        xbmcplugin.setContent(st.plugin_handle, 'videos' if (metadata.enabled() and metadata.tmdb_key()) else 'files')  # 'videos': los paneles de información de las skins muestran póster/sinopsis
        xbmcplugin.addSortMethod(st.plugin_handle, xbmcplugin.SORT_METHOD_UNSORTED)
        xbmcplugin.addSortMethod(st.plugin_handle, xbmcplugin.SORT_METHOD_LABEL)

    if st.mode is None:
        menu_principal(None)
    elif st.mode == 1:
        topcolecionadores()
    elif st.mode == 3:
        pastas(st.url, st.name)
    elif st.mode == 4:
        analyzer(st.url, playlistTitle=st.name)
    elif st.mode == 6:
        manage_accounts_ui()
    elif st.mode == 7:
        pesquisa()
    elif st.mode == MODE_SETTINGS:
        selfAddon.openSettings()
    elif st.mode == 9:
        favoritos()
    elif st.mode == 11:
        fazerdownload(st.name, st.url)
    elif st.mode == 15:
        play_playlist_from_db()
    elif st.mode == 17:
        trailer(st.name)
    elif st.mode == 18:
        atalhos()
    elif st.mode == 19:
        atalhos(action='addfile')
    elif st.mode == 20:
        atalhos(action='addfolder')
    elif st.mode == 21:
        atalhos(action='remove')
    elif st.mode == 23:
        pastas_de_fora(st.url, st.name)
    elif st.mode == 24:
        proxpesquisa_ck_page()
    elif st.mode == 25:
        play_from_outside(st.name, st.url)
    elif st.mode == 26:
        add_to_library_opt(st.name, st.url)
    elif st.mode == 30:
        add_to_library_batch()
    elif st.mode == 50:
        downloads_ui()
    elif st.mode == 51:
        downloads_action(st.params)
    elif st.mode == 52:
        download_folder(st.url, st.name)
    elif st.mode == 53:
        refresh_folder_cache(st.url)
    elif st.mode == 54:
        diagnostics()
    elif st.mode == 55:
        export_log()
    elif st.mode == 56:
        cache_mod.invalidate(); notify(strings.t(40320))
    elif st.mode == 57:
        set_tmdb_key()
    elif st.mode == MODE_DELETE_COOKIES:
        delete_cookies(cookies)
    elif st.mode == MODE_MANAGE_ACCOUNTS:
        manage_accounts_ui()
    elif st.mode == MODE_STRM_GEN_DIALOG:
        if st.url and st.name:
            generate_strm_files_dialog(st.url, st.name)
        else:
            k.log("STRM Gen (mode 35) called without URL or Name.", xbmc.LOGWARNING)
            notify(traducao(40181), error=True)
    else:
        notify(traducao(40227).format(st.mode), error=True)
        menu_principal(None)

    end_directory()
    k.log("--- Chomiteca End ---", xbmc.LOGINFO)


# Importaciones entre módulos de funciones al final: así las referencias circulares son seguras
from resources.lib.accounts_ui import manage_accounts_ui
from resources.lib.downloads import download_folder, downloads_action, downloads_ui, fazerdownload
from resources.lib.favorites import atalhos, favoritos
from resources.lib.library import add_to_library_batch, add_to_library_opt, generate_strm_files_dialog
from resources.lib.listing import menu_principal, pastas, refresh_folder_cache, topcolecionadores
from resources.lib.playback import analyzer, play_from_outside, trailer
from resources.lib.playlist import play_playlist_from_db
from resources.lib.search import pastas_de_fora, pesquisa, proxpesquisa_ck_page
from resources.lib.tools import diagnostics, export_log, set_tmdb_key


def play_entry(page_url, title):
    """Reproducción con la lógica completa (imágenes, subtítulos, tipos desconocidos); llamado por router.py."""
    st.init()
    return analyzer(page_url, playlistTitle=title)
