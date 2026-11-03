# -*- coding: utf-8 -*-
"""Resolución y reproducción (vídeo, audio, imágenes), tráilers y reproducción desde STRM."""
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
from resources.lib.textutils import real_title

from resources.lib.common import DIALOG_MESSAGE, KODI_PLAYER, abrir_url, clean_title, login, nameURL, notify, pastaperfil, selfAddon, traducao


def trailer(name):
    api_key = selfAddon.getSetting("youtube_api_key")
    if not api_key:
         k.log("YouTube API Key not set in addon settings.", xbmc.LOGWARNING)
         ok = DIALOG_MESSAGE.yesno(traducao(40120), traducao(40121), yeslabel=traducao(40122), nolabel=traducao(40123))
         if ok: selfAddon.openSettings()
         return

    youtube_search_base_url = 'https://www.googleapis.com/youtube/v3/search'
    clean_search_term = clean_title(name)
    if not clean_search_term:
         k.log("Could not extract a clean name for trailer search.", xbmc.LOGWARNING)
         notify(traducao(40222), error=True)
         return

    search_query = f"{clean_search_term} {traducao(30002).lower()}"
    params_youtube = { 'part': 'id,snippet', 'q': search_query, 'maxResults': '1', 'type': 'video', 'key': api_key }
    search_url = f"{youtube_search_base_url}?{urllib.parse.urlencode(params_youtube)}"
    k.log(f"Searching YouTube trailer: {search_url}", xbmc.LOGDEBUG)
    ytpage_bytes = None
    try:
        ytpage_bytes = abrir_url(search_url)
        if not ytpage_bytes: raise ValueError("No response from YouTube API")
        yt_data = json.loads(ytpage_bytes.decode('utf-8'))
        if 'items' in yt_data and len(yt_data['items']) > 0:
            video_id = yt_data['items'][0]['id']['videoId']
            video_title = yt_data['items'][0]['snippet']['title']
            k.log(f"Found YouTube trailer: '{video_title}' (ID: {video_id})", xbmc.LOGINFO)
            youtube_addon_id_val = 'plugin.video.youtube'
            play_url = f"plugin://{youtube_addon_id_val}/play/?video_id={video_id}"
            notify(traducao(40124).format(video_title))
            xbmc.executebuiltin(f'PlayMedia("{play_url}")')
        else:
            k.log(f"No YouTube trailer found for query: '{search_query}'", xbmc.LOGINFO)
            notify(traducao(40125).format(clean_search_term))
    except ValueError as json_e:
         k.log(f"Error decoding YouTube API response or no response: {json_e}", xbmc.LOGERROR)
         if ytpage_bytes:
             try: response_text = ytpage_bytes.decode('utf-8')
             except: response_text = str(ytpage_bytes)
             k.log(f"YouTube API Response Text: {response_text[:500]}", xbmc.LOGERROR)
         else:
             k.log("YouTube API request returned no data (ytpage_bytes is None).", xbmc.LOGERROR)
         notify(traducao(40126), error=True)
    except Exception as e:
        k.log(f"Error fetching/playing YouTube trailer: {e}", xbmc.LOGERROR)
        traceback.print_exc()
        notify(traducao(40129).format(f"{traducao(30002)}: {e}"), error=True)


def _get_link(url_param):
    """Resuelve la URL temporal. Si la sesión caducó, reloguea UNA vez y reintenta."""
    for attempt in (0, 1):
        session = make_session()
        try:
            return resolver.resolve(session, url_param)
        except resolver.ResolveError as e:
            if attempt == 0 and getattr(e, "relogin", False):
                k.log("Sesión caducada: relogueando y reintentando.", xbmc.LOGINFO)
                session.clear()
                if login(True):
                    continue
            raise


def _close_handle():
    """Todo plugin invocado con handle debe cerrarlo: setResolvedUrl(False) si no se reprodujo nada."""
    pass
    if st.plugin_handle != -1 and not st._resolved:
        st._resolved = True
        player.fail(st.plugin_handle)


def _play(link, title, kind, subtitle_path=None):
    pass
    if st.plugin_handle == -1:
        # Invocado con RunPlugin (sin handle): reproducir por el reproductor directamente.
        li = xbmcgui.ListItem(label=title, path=link.url + "|" + urllib.parse.urlencode(link.headers))
        li.setContentLookup(False)
        KODI_PLAYER.play(li.getPath(), li)
    else:
        st._resolved = True
        player.play(st.plugin_handle, link, title, kind, subtitle_path, key=st._play_key, offset=st._play_offset)


def handle_resolved(link, url_param, display_name, playterm=False):
    """Despacha según el tipo de fichero ya resuelto."""
    ext = player.ext_of(url_param)
    kind = player.kind_of(ext)
    clean_display_name = clean_title(display_name)
    shown_title = real_title(display_name)
    if kind == "image":
        if playterm == "download":
            fazerdownload(display_name, url_param)
        else:
            temp_img_path = os.path.join(pastaperfil, f"temp_view{ext}")
            try:
                if xbmcvfs.exists(temp_img_path): xbmcvfs.delete(temp_img_path)
            except Exception as del_e: k.log(f"Could not delete previous temp image: {del_e}", xbmc.LOGWARNING)
            try:
                # Descarga síncrona y acotada (30 MB): la antigua descarga por RunScript era asíncrona y
                # devuelve al instante, así que la imagen aún no existiría al llamar a ShowPicture.
                req = urllib.request.Request(link.url, headers=link.headers)
                with urllib.request.urlopen(req, timeout=30) as resp_img:
                    data_img = resp_img.read(30 * 1024 * 1024)
                fh_img = xbmcvfs.File(temp_img_path, 'wb')
                try: fh_img.write(data_img)
                finally: fh_img.close()
                xbmc.executebuiltin('ShowPicture("%s")' % temp_img_path.replace('"', ''))
            except Exception as img_e:
                k.log(f"Image download failed: {img_e}", xbmc.LOGERROR)
                notify(traducao(40103), error=True)
        _close_handle()
    elif kind in ("video", "audio"):
        if playterm == "download":
            fazerdownload(display_name, url_param)
            _close_handle()
            return
        sub_path = None
        if kind == "video" and k.get_bool('subtitles') and not k.get_bool('legendas-disable'):
            try:
                from resources.lib import subtitles as SubtitlesMod
                sub_path = SubtitlesMod.getsubtitles(clean_display_name, selfAddon.getSetting('sublang1'), selfAddon.getSetting('sublang2'))
            except Exception as sub_e:
                k.log(f"Subtitles unavailable: {sub_e}", xbmc.LOGWARNING)
        _play(link, shown_title or traducao(40067), kind, sub_path)
    else:
        if playterm == "download":
            fazerdownload(display_name, url_param)
        elif selfAddon.getSetting('aviso-extensao') != 'false':
            notify(f"{traducao(40028)} ({ext}). {traducao(40029)} {traducao(40030)}", error=True)
        _close_handle()


def analyzer(url_param, subtitles='', playterm=False, playlistTitle='', returning=False):
    """Compatibilidad con el código heredado: resuelve y reproduce/descarga.
    returning=True devuelve la URL (con cabeceras `|...`) en vez de reproducir."""
    pass
    if playterm == 'download':  # la cola resuelve el enlace al empezar (es temporal): no gastar una resolución aquí
        fazerdownload(playlistTitle or st.name, url_param)
        _close_handle()
        return True
    if not returning and subtitles != 'sim':
        _ext_pre = player.ext_of(url_param)
        if player.kind_of(_ext_pre) in ('video', 'audio'):
            st._play_key = playstate.key_for(url_param)
            st._play_offset = playstate.choose_resume(st._play_key, playlistTitle or st.name or '')  # antes de resolver: el enlace caduca
    if not login(True):
        if not returning: notify(traducao(40128), error=True)
        if not returning and subtitles != 'sim': _close_handle()
        return None if returning else False
    dialogWait = None
    if not playlistTitle and not returning and not subtitles:
        try:
            dialogWait = xbmcgui.DialogProgressBG()
            dialogWait.create(nameURL, traducao(40025))
        except Exception as bg_e:
            k.log(f"Failed to create background progress dialog: {bg_e}", xbmc.LOGWARNING)
            dialogWait = None
    try:
        link = _get_link(url_param)
        if subtitles == 'sim': return link.url
        if returning:
            return link.url + "|" + urllib.parse.urlencode(link.headers)
        handle_resolved(link, url_param, playlistTitle if playlistTitle else st.name, playterm)
    except (resolver.ResolveError, auth.LoginError) as e:
        k.log(f"Analyzer error for URL {url_param}: {e}", xbmc.LOGERROR)
        if not returning and subtitles != 'sim':
            notify(traducao(40129).format(e), error=True)
            _close_handle()
        return None if returning else False
    except Exception as e:
        k.log(f"Unexpected error in analyzer: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
        if not returning and subtitles != 'sim':
            notify(traducao(40130).format(e), error=True)
            _close_handle()
        return None if returning else False
    finally:
        if dialogWait: dialogWait.close()
    return True


def play_from_outside(name_param, url_param):
    """
    Manejador de reproducción para items iniciados desde fuera del addon (ej. biblioteca de Jellyfin).
    Esta función ahora delega directamente a `analyzer`, pero primero se asegura
    de que la URL de entrada esté correctamente codificada para evitar errores de 'InvalidURL'.
    """
    st.addon.log_info(f"Playback from outside: Name='{name_param}', Raw URL='{url_param}'")
    if not url_param:
        st.addon.log_error("Play from outside called without URL.")
        notify(traducao(40223), error=True)
        xbmcplugin.setResolvedUrl(handle=int(sys.argv[1]), succeeded=False, listitem=xbmcgui.ListItem(offscreen=True))
        return

    try:
        # Decodificamos primero para manejar casos donde la URL ya venga parcialmente codificada (ej. %2B)
        # y luego la codificamos de forma segura, permitiendo solo los caracteres que una ruta URL puede tener.
        encoded_url = resolver.normalize_url(url_param)
        st.addon.log_info(f"Playback from outside: Encoded URL for processing: {encoded_url}")
    except Exception as e:
        st.addon.log_error(f"Failed to parse/encode incoming URL '{url_param}': {e}")
        notify(traducao(40224), error=True)
        xbmcplugin.setResolvedUrl(handle=int(sys.argv[1]), succeeded=False, listitem=xbmcgui.ListItem(offscreen=True))
        return

    # Llamamos a analyzer con la URL saneada y el título.
    analyzer(encoded_url, playlistTitle=name_param)


# Importaciones entre módulos de funciones al final: así las referencias circulares son seguras
from resources.lib.downloads import fazerdownload
