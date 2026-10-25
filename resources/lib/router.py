# -*- coding: utf-8 -*-
"""Enrutado. Los modos de reproducción (4 y 25) se resuelven aquí sin cargar el módulo pesado de navegación;
el resto va a browse.main(). endOfDirectory lo gestiona browse.end_directory() (una sola vez)."""
import urllib.parse

import xbmc

from . import auth, kodiutils as k, player, playstate, resolver
from .session import make_session


def _parse(argv):
    query = argv[2][1:] if len(argv) > 2 and argv[2].startswith("?") else (argv[2] if len(argv) > 2 else "")
    return dict(urllib.parse.parse_qsl(query, keep_blank_values=True))  # ya decodificado una vez


def _get_link(page_url):
    from . import accounts
    for attempt in (0, 1):
        session = make_session()
        if not session.has_cookies():
            account = accounts.active()
            if not account:
                raise resolver.ResolveError(k.tr(40109, "No hay cuenta activa"))
            auth.login(session, account)
        try:
            return resolver.resolve(session, page_url)
        except resolver.ResolveError as exc:
            if attempt == 0 and exc.relogin:
                session.clear()  # sesión caducada: relogin y un único reintento
                continue
            raise


def play_mode(handle, params):
    page_url, title = params.get("url", ""), params.get("name", "")
    if not page_url:
        return player.fail(handle)
    try:
        page_url = resolver.normalize_url(page_url)
        kind = player.kind_of(player.ext_of(page_url))
        wants_subs = k.get_bool("subtitles") and not k.get_bool("legendas-disable")
        if kind == "audio" or (kind == "video" and not wants_subs):
            key = playstate.key_for(page_url)
            label = title or page_url.rsplit("/", 1)[-1]
            offset = playstate.choose_resume(key, label)  # se pregunta ANTES de resolver: el enlace caduca
            return player.play(handle, _get_link(page_url), label, kind, key=key, offset=offset)
        # imágenes, vídeo con subtítulos y tipos desconocidos: lógica completa en browse
        from . import browse
        browse.play_entry(page_url, title)
        return None
    except (resolver.ResolveError, auth.LoginError) as exc:
        k.notify(str(exc), error=True)
    except Exception as exc:  # último recurso: nunca dejar el handle abierto
        k.log("Fallo inesperado: %r" % exc, xbmc.LOGERROR)
        k.notify(k.tr(40130, "Error inesperado").replace("{}", ""), error=True)
    player.fail(handle)
    return None


def run(argv):
    handle = int(argv[1]) if len(argv) > 1 else -1
    params = _parse(argv)
    if params.get("mode") in ("4", "25") and handle != -1:
        return play_mode(handle, params)
    from . import browse
    return browse.main(handle, params)
