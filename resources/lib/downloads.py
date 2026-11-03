# -*- coding: utf-8 -*-
"""Cola de descargas: encolar archivos/carpetas y pantalla de gestión."""
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

from resources.lib.common import DIALOG_MESSAGE, art, notify, selfAddon, traducao, wtpath


def _download_filename(name_param, url_param):
    base = re.sub(r'\[/?(?:COLOR|B|I)[^\]]*\]', '', str(name_param or ''))
    base = re.sub(r'\s*\([\d,.]+\s*[KMGT]?B\)\s*$', '', base).strip()
    ext = player.ext_of(url_param)
    if not base:
        base = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url_param).path)) or "download"
    if ext and not base.lower().endswith(ext):
        base += ext
    elif not os.path.splitext(base)[1]:
        base += ".download"
    return dq.safe_name(base)


def _ensure_download_dir():
    path = selfAddon.getSetting('download-folder')
    if path and xbmcvfs.exists(path):
        return xbmcvfs.translatePath(path)
    selected = DIALOG_MESSAGE.browse(3, traducao(40041), 'files', defaultt=path or '')  # 3 = carpeta con permiso de escritura
    if isinstance(selected, list): selected = selected[0] if selected else ''
    if not selected:
        notify(traducao(40213))
        return None
    selfAddon.setSetting('download-folder', selected)
    return xbmcvfs.translatePath(selected)


def fazerdownload(name_param, url_param, tipo="outros", headers=None):
    """Encola la descarga (la cola la procesa el servicio, con reanudación y varias a la vez)."""
    try:
        filename = _download_filename(name_param, url_param)
        dest_root = _ensure_download_dir()
        if not dest_root:
            return False
        dq.enqueue(url_param, filename, dest_root)
        notify(strings.t(40315).format(filename))
        return True
    except Exception as e:
        k.log(f"Exception enqueueing download: {e}", xbmc.LOGERROR); traceback.print_exc()
        notify(traducao(40216).format(e), error=True)
        return False


def download_folder(url_param, name_param):
    """Encola todos los archivos de una carpeta (y sus subcarpetas) conservando la estructura."""
    dest_root = _ensure_download_dir()
    if not dest_root: return
    root_name = dq.safe_name(name_param, "Chomikuj")
    count = {'n': 0}
    dialog = None
    try:
        dialog = xbmcgui.DialogProgressBG()
        dialog.create(strings.t(40316), strings.t(40317))
    except Exception: dialog = None
    def progress(rel, page):
        if dialog:
            try: dialog.update(50, strings.t(40317), f"{rel or '/'} | {count['n']}")
            except Exception: pass
    incomplete = False
    try:
        try:
            for entry in walk_folder_files(url_param, progress):
                fname = _download_filename(entry['title'] + entry['ext'], entry['url'])
                dq.enqueue(entry['url'], fname, dest_root, os.path.join(root_name, entry['rel_dir']))
                count['n'] += 1
        except WalkIncomplete as exc:
            incomplete = True
            k.log("Downloads: carpeta escaneada parcialmente; se encolan %d archivos" % count['n'], xbmc.LOGWARNING)
    finally:
        if dialog:
            try: dialog.close()
            except Exception: pass
    if incomplete:
        notify(strings.t(40318).format(count['n']) + " (parcial)")
    else:
        notify(strings.t(40318).format(count['n']))


def _fmt_mb(n): return f"{n / 1048576:.1f}"


def downloads_ui():
    rows = dq.list_all()
    colors = {'queued': 'white', 'downloading': 'lime', 'paused': 'yellow', 'done': 'gray', 'error': 'red', 'canceled': 'gray'}
    labels = {'queued': 40308, 'downloading': 40309, 'paused': 40310, 'done': 40311, 'error': 40312, 'canceled': 40313}
    def add(label, query, ctx=None):
        liz = xbmcgui.ListItem(label=label)
        liz.setArt({'icon': os.path.join(wtpath, art[1:], 'attach.png')})
        if ctx: liz.addContextMenuItems(ctx)
        xbmcplugin.addDirectoryItem(handle=st.plugin_handle, url=f"{sys.argv[0]}?{urllib.parse.urlencode(query)}", listitem=liz, isFolder=False)
    if not rows:
        add(strings.t(40314), {'mode': 51, 'act': 'noop'})
        return
    add(strings.t(40344), {'mode': 51, 'act': 'pause_all'})
    add(strings.t(40345), {'mode': 51, 'act': 'resume_all'})
    add(strings.t(40302), {'mode': 51, 'act': 'clear'})
    for did, title, dest, status, done, total, error in rows:
        pct = f" {int(done * 100 / total)}% ({_fmt_mb(done)}/{_fmt_mb(total)} MB)" if total else ""
        label = f"[COLOR {colors.get(status, 'white')}][{strings.t(labels.get(status, 40308))}][/COLOR] {title}{pct}"
        if status == 'error' and error: label += f" [COLOR red]- {error}[/COLOR]"
        ctx = []
        for act_name, sid in (('pause', 40303), ('resume', 40304), ('cancel', 40305), ('retry', 40306), ('remove', 40307)):
            ctx.append((strings.t(sid), f"RunPlugin({sys.argv[0]}?mode=51&act={act_name}&id={did})"))
        toggle = 'pause' if status in ('queued', 'downloading') else 'resume' if status in ('paused', 'error', 'canceled') else 'noop'
        add(label, {'mode': 51, 'act': toggle, 'id': did}, ctx)


def downloads_action(p):
    action = p.get('act', 'noop')
    if action != 'noop':
        try: dq.act(int(p.get('id', 0) or 0), action)
        except Exception as e: k.log(f"Download action failed: {e}", xbmc.LOGERROR)
    xbmc.executebuiltin("Container.Refresh")


# Importaciones entre módulos de funciones al final: así las referencias circulares son seguras
from resources.lib.library import walk_folder_files, WalkIncomplete
