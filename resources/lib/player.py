# -*- coding: utf-8 -*-
"""Entrega a Kodi del enlace resuelto. Todos los caminos cierran el handle con setResolvedUrl."""
import os
import re
import urllib.parse

import xbmc
import xbmcgui
import xbmcplugin

from . import kodiutils as k, playstate

VIDEO_EXT = {".mkv", ".avi", ".mp4", ".wmv", ".mov", ".flv", ".ts", ".m2ts", ".mpg", ".mpeg", ".ogm", ".webm", ".vob", ".3gp"}
AUDIO_EXT = {".mp3", ".aac", ".m4a", ".ac3", ".wma", ".wav", ".ogg", ".flac", ".alac", ".aiff", ".ape", ".mid", ".midi"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp"}


def ext_of(url):
    """Extensión del recurso; las URLs de Chomikuj pueden llevar sufijos tipo '.mkv(1.2' -> '.mkv'."""
    path = re.sub(r"\s*\([^)]*\)\s*$", "", urllib.parse.urlparse(url).path)  # quita sufijos tipo "(video)" o "(1.2 GB)"
    ext = os.path.splitext(path)[1].lower()
    match = re.match(r"(\.[^.(\s]+)", ext)
    return match.group(1) if match else ext


def kind_of(ext):
    ext = ext.lower()
    return "video" if ext in VIDEO_EXT else "audio" if ext in AUDIO_EXT else "image" if ext in IMAGE_EXT else "other"


def fail(handle):
    xbmcplugin.setResolvedUrl(handle, False, xbmcgui.ListItem(offscreen=True))


def play(handle, link, title, kind, subtitle_path=None, key=None, offset=0):
    url = link.url + "|" + urllib.parse.urlencode(link.headers)
    item = xbmcgui.ListItem(label=title, path=url, offscreen=True)
    item.setContentLookup(False)  # evita que Kodi consuma el enlace temporal con un HEAD/GET previo
    if kind == "audio":
        tag = item.getMusicInfoTag()
        tag.setTitle(title)
        tag.setMediaType("song")
    else:
        tag = item.getVideoInfoTag()  # sustituye a ListItem.setInfo (obsoleto desde Kodi 20)
        tag.setTitle(title)
        tag.setMediaType("video")
    if subtitle_path:
        item.setSubtitles([subtitle_path])
    if key:
        playstate.mark_playing(key, offset)  # el servicio guarda la posición al parar
        if offset:
            item.setProperty("StartOffset", str(int(offset)))
    xbmcplugin.setResolvedUrl(handle, True, item)
    k.log("setResolvedUrl OK (%s)" % kind)


def show_image(handle, local_path):
    fail(handle)  # una imagen no es reproducible: se cierra el handle y se muestra aparte
    xbmc.executebuiltin('ShowPicture("%s")' % local_path.replace('"', ""))
