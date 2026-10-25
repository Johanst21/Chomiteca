# -*- coding: utf-8 -*-
"""Posición de reproducción y estado de visto, guardados en nuestra BD (no dependemos de la de Kodi)."""
import hashlib
import re
import time
import urllib.parse

import xbmc
import xbmcgui

from . import kodiutils as k, store, strings

WATCHED_AT = 0.90
MIN_SAVE_SECONDS = 30
_PROP_KEY = "chomiteca.nowplaying"
_PROP_OFFSET = "chomiteca.startoffset"


def enabled():
    return (k.ADDON.getSetting("remember_progress") or "true") == "true"


def key_for(url):
    path = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    path = re.sub(r"\s*\([^)]*\)\s*$", "", path).lower()
    return hashlib.sha1(path.encode("utf-8")).hexdigest()[:20]


def get(key):
    try:
        with store.db() as c:
            row = c.execute("SELECT position, total, watched FROM progress WHERE key=?", (key,)).fetchone()
        return {"position": row[0], "total": row[1], "watched": bool(row[2])} if row else None
    except Exception:
        return None


def save(key, position, total, title=""):
    if not key or total <= 0:
        return
    watched = position / total >= WATCHED_AT
    if not watched and position < MIN_SAVE_SECONDS:
        position = 0
    try:
        with store.db() as c:
            c.execute("INSERT OR REPLACE INTO progress(key, position, total, watched, ts, title) VALUES (?,?,?,?,?,?)",
                      (key, 0 if watched else position, total, 1 if watched else 0, time.time(), title))
    except Exception as exc:
        k.log("playstate.save: %s" % exc, xbmc.LOGWARNING)


def _fmt(seconds):
    s = int(seconds)
    return "%d:%02d:%02d" % (s // 3600, s % 3600 // 60, s % 60) if s >= 3600 else "%d:%02d" % (s // 60, s % 60)


def choose_resume(key, title=""):
    """Devuelve los segundos desde los que reproducir (0 = desde el principio). Pregunta si está configurado."""
    if not enabled():
        return 0
    state = get(key)
    if not state or state["watched"] or state["position"] < MIN_SAVE_SECONDS:
        return 0
    if (k.ADDON.getSetting("resume_ask") or "true") != "true":
        return int(state["position"])
    ask = xbmcgui.Dialog().yesno(strings.t(40332), title or "", nolabel=strings.t(40334),
                                 yeslabel=strings.t(40333).format(_fmt(state["position"])))
    return int(state["position"]) if ask else 0


def mark_playing(key, offset=0):
    """Avisa al servicio de qué estamos reproduciendo (la URL resuelta no identifica el fichero)."""
    if not enabled() or not key:
        return
    win = xbmcgui.Window(10000)
    win.setProperty(_PROP_KEY, key)
    win.setProperty(_PROP_OFFSET, str(int(offset or 0)))


def apply_to_item(item, tag, key):
    """Marca visto y expone ResumeTime/TotalTime (las skins dibujan la barra de progreso)."""
    if not enabled():
        return
    state = get(key)
    if not state:
        return
    try:
        if state["watched"]:
            tag.setPlaycount(1)
        elif state["position"] >= MIN_SAVE_SECONDS and state["total"] > 0:
            item.setProperty("ResumeTime", str(int(state["position"])))
            item.setProperty("TotalTime", str(int(state["total"])))
    except Exception as exc:
        k.log("playstate.apply: %s" % exc, xbmc.LOGDEBUG)


class PlayerMonitor(xbmc.Player):
    """Corre en el servicio: guarda la posición al parar/terminar y aplica el desplazamiento de reanudación."""

    def __init__(self):
        super().__init__()
        self.key, self.total, self.last, self.title, self._offset = None, 0.0, 0.0, "", 0

    def onAVStarted(self):
        win = xbmcgui.Window(10000)
        key = win.getProperty(_PROP_KEY)
        if not key:
            self.key = None
            return
        self._offset = int(float(win.getProperty(_PROP_OFFSET) or 0))
        win.clearProperty(_PROP_KEY)
        win.clearProperty(_PROP_OFFSET)
        self.key, self.last = key, 0.0
        try:
            self.total = float(self.getTotalTime())
            self.title = self.getPlayingFile() and xbmc.getInfoLabel("Player.Title")
            if self._offset > 0 and self.getTime() < self._offset - 5:
                self.seekTime(self._offset)  # por si Kodi ignoró StartOffset
        except Exception as exc:
            k.log("PlayerMonitor.onAVStarted: %s" % exc, xbmc.LOGDEBUG)

    def tick(self):
        if self.key and self.isPlaying():
            try:
                self.last = float(self.getTime())
            except Exception:
                pass

    def _finish(self, ended):
        if self.key:
            save(self.key, self.total if ended else self.last, self.total, self.title or "")
        self.key = None

    def onPlayBackStopped(self):
        self._finish(False)

    def onPlayBackEnded(self):
        self._finish(True)
