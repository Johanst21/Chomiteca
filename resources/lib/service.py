# -*- coding: utf-8 -*-
"""Servicio de Kodi: calentamiento de sesión, cola de descargas y seguimiento de reproducción."""
import xbmc

from . import accounts, auth, downloadqueue, kodiutils as k, playstate
from .session import make_session


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


def run():
    monitor = xbmc.Monitor()
    player = playstate.PlayerMonitor()
    manager = None
    ticks = 0
    while not monitor.waitForAbort(1):
        ticks += 1
        player.tick()
        if ticks == 15:  # no competir con el arranque de Kodi
            _warm_up()
            manager = downloadqueue.Manager(monitor)
        if manager is not None and ticks % 2 == 0:
            manager.tick()
