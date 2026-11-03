# -*- coding: utf-8 -*-
"""Servicio de Kodi: calentamiento de sesión, cola de descargas y seguimiento de reproducción."""
import threading
import xbmc

from . import accounts, auth, downloadqueue, kodiutils as k, playstate
from .session import make_session

_warm_up_started = False


def _warm_up():
    account = accounts.active()
    if not account:
        return
    session = make_session()
    if session.has_cookies():
        return
    try:
        auth.login(session, account)
        k.log("Sesión inicial creada")
    except auth.LoginError as exc:
        k.log("Login inicial fallido: %s" % exc, xbmc.LOGWARNING)


def _warm_up_safe():
    try:
        _warm_up()
    except Exception as exc:
        k.log("_warm_up: %r" % exc, xbmc.LOGERROR)


def run():
    global _warm_up_started
    monitor = xbmc.Monitor()
    player = playstate.PlayerMonitor()
    manager = None
    ticks = 0
    while not monitor.waitForAbort(1):
        try:
            ticks += 1
            player.tick()
            if ticks >= 15 and not _warm_up_started:
                _warm_up_started = True
                threading.Thread(target=_warm_up_safe, daemon=True, name="ChomitecaWarmUp").start()
                manager = downloadqueue.Manager(monitor)
            if manager is not None and ticks % 2 == 0:
                manager.tick()
        except Exception as exc:
            k.log("service tick: %r" % exc, xbmc.LOGERROR)
