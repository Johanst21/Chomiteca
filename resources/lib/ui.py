# -*- coding: utf-8 -*-
"""Construcción de elementos de lista (carpetas y archivos) con metadatos y menús contextuales."""
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

from resources.lib.common import AUDIO_EXTS, MODE_DELETE_COOKIES, MODE_MANAGE_ACCOUNTS, MODE_SETTINGS, MODE_STRM_GEN_DIALOG, VIDEO_EXTS_UI, traducao, wtpath


def set_video_tag(liz, title, mediatype=None, kind="video"):
    """InfoTag* en lugar de ListItem.setInfo (obsoleto desde Kodi 20)."""
    try:
        if kind == "audio":
            tag = liz.getMusicInfoTag()
            tag.setTitle(title)
            tag.setMediaType("song")
        else:
            tag = liz.getVideoInfoTag()
            tag.setTitle(title)
            if mediatype: tag.setMediaType(mediatype)
    except Exception as e:
        k.log(f"InfoTag no disponible: {e}", xbmc.LOGWARNING)


def end_directory():
    """endOfDirectory una sola vez, y nunca si el handle ya se resolvió o no hay handle."""
    pass
    if st.plugin_handle != -1 and not st._eod_done and not st._resolved:
        st._eod_done = True
        xbmcplugin.endOfDirectory(st.plugin_handle)


def addLink(name_param, url_param, iconimage_param):
    try:
        display_name = str(name_param); liz = xbmcgui.ListItem(label=display_name)
        liz.setArt({'icon': iconimage_param, 'thumb': iconimage_param})
        set_video_tag(liz, display_name)
        addon_fanart = os.path.join(wtpath, 'fanart.jpg')
        if xbmcvfs.exists(addon_fanart): liz.setArt({'fanart': addon_fanart})
        xbmcplugin.addDirectoryItem(handle=st.plugin_handle, url=url_param, listitem=liz, isFolder=False)
    except Exception as e: k.log(f"Error in addLink for '{name_param}': {e}", xbmc.LOGERROR)


def addDir(name_param, url_param, mode_param, iconimage_param, total_param=0, pasta_param=True, atalhos_param=False):
    try:
        display_name_for_listitem = str(name_param)
        name_for_query = name_param
        query_params = {'url': url_param, 'mode': str(mode_param)}
        if name_for_query is not None:
            query_params['name'] = name_for_query

        if mode_param in [MODE_MANAGE_ACCOUNTS, MODE_SETTINGS, MODE_DELETE_COOKIES, 18]:
            query_params.pop('url', None)
            if mode_param != 18:
                 if mode_param != 21:
                      query_params.pop('name', None)


        plugin_url_val = f"{sys.argv[0]}?"
        encoded_query_parts = []
        for key, value in query_params.items():
            if value is not None:
                encoded_query_parts.append(f"{key}={urllib.parse.quote_plus(str(value))}")
        plugin_url_val += "&".join(encoded_query_parts)

        liz = xbmcgui.ListItem(label=display_name_for_listitem)
        liz.setArt({'icon': iconimage_param, 'thumb': iconimage_param})
        set_video_tag(liz, display_name_for_listitem)

        addon_fanart = os.path.join(wtpath, 'fanart.jpg')
        if xbmcvfs.exists(addon_fanart): liz.setArt({'fanart': addon_fanart})
        if mode_param == 3 and pasta_param: decorate_folder_item(liz, display_name_for_listitem)

        contexto = []
        url_quoted_ctx = urllib.parse.quote_plus(url_param)
        name_quoted_ctx = urllib.parse.quote_plus(name_param)

        if pasta_param:
            contexto.append((traducao(40056), f'RunPlugin({sys.argv[0]}?mode=17&url={url_quoted_ctx}&name={name_quoted_ctx})'))
            if not atalhos_param:
                contexto.append((traducao(40055), f'RunPlugin({sys.argv[0]}?mode=20&url={url_quoted_ctx}&name={name_quoted_ctx})'))
            else:
                contexto.append((traducao(40065), f'RunPlugin({sys.argv[0]}?mode=21&name={str(atalhos_param)})'))
            contexto.append((traducao(40160), f'RunPlugin({sys.argv[0]}?mode={MODE_STRM_GEN_DIALOG}&url={url_quoted_ctx}&name={name_quoted_ctx})'))
            if mode_param == 3:
                contexto.append((strings.t(40316), f'RunPlugin({sys.argv[0]}?mode=52&url={url_quoted_ctx}&name={name_quoted_ctx})'))
                contexto.append((strings.t(40319), f'RunPlugin({sys.argv[0]}?mode=53&url={url_quoted_ctx})'))

        if contexto: liz.addContextMenuItems(contexto)
        xbmcplugin.addDirectoryItem(handle=st.plugin_handle, url=plugin_url_val, listitem=liz, isFolder=pasta_param, totalItems=total_param if total_param > 0 else 0)
    except Exception as e: k.log(f"Error in addDir for '{name_param}': {e}\n{traceback.format_exc()}", xbmc.LOGERROR)


def addCont(name_param, url_param, mode_param, tamanho_param, iconimage_param, total_param=0, pasta_param=False, atalhos_param=False):
    try:
        display_name_for_listitem = str(name_param)
        size_bytes = 0
        try:
             size_match = re.search(r'\(([\d,.]+)\s*(K|M|G)?B\)', tamanho_param, re.IGNORECASE)
             if size_match:
                  num_str = size_match.group(1).replace(',', '.')
                  num = float(num_str); unit = size_match.group(2).upper() if size_match.group(2) else 'B'
                  if unit == 'G': size_bytes = int(num * 1024*1024*1024)
                  elif unit == 'M': size_bytes = int(num * 1024*1024)
                  elif unit == 'K': size_bytes = int(num * 1024)
                  else: size_bytes = int(num)
        except: pass

        name_for_query = name_param
        plugin_url_val = f"{sys.argv[0]}?url={urllib.parse.quote_plus(url_param)}&mode=4&name={urllib.parse.quote_plus(name_for_query)}"

        liz = xbmcgui.ListItem(label=display_name_for_listitem)
        liz.setArt({'icon': iconimage_param, 'thumb': iconimage_param})
        ext = player.ext_of(url_param)
        kind_ui = 'audio' if ext in AUDIO_EXTS else ('video' if ext in VIDEO_EXTS_UI else 'other')
        decorate_file_item(liz, display_name_for_listitem, url_param, kind_ui)

        addon_fanart = os.path.join(wtpath, 'fanart.jpg')
        if xbmcvfs.exists(addon_fanart): liz.setArt({'fanart': addon_fanart})
        liz.setProperty('IsPlayable', 'true')

        contexto = []
        url_quoted_ctx = urllib.parse.quote_plus(url_param)
        name_quoted_ctx = urllib.parse.quote_plus(name_param)

        contexto.append((traducao(40038), 'QueueItem'))
        contexto.append((traducao(40040), f'RunPlugin({sys.argv[0]}?mode=11&url={url_quoted_ctx}&name={name_quoted_ctx}&tamanhof={urllib.parse.quote_plus(tamanho_param)})'))
        contexto.append((traducao(40051), f'RunPlugin({sys.argv[0]}?mode=26&url={url_quoted_ctx}&name={name_quoted_ctx})'))
        contexto.append((traducao(40056), f'RunPlugin({sys.argv[0]}?mode=17&url={url_quoted_ctx}&name={name_quoted_ctx})'))
        if not atalhos_param:
            contexto.append((traducao(40055), f'RunPlugin({sys.argv[0]}?mode=19&url={url_quoted_ctx}&name={name_quoted_ctx})'))
        else:
            contexto.append((traducao(40065), f'RunPlugin({sys.argv[0]}?mode=21&name={str(atalhos_param)})'))
        contexto.append((traducao(10105).split('?')[0].strip() + '...', 'PlayerControl(ShowPlayerProcessInfo)'))

        liz.addContextMenuItems(contexto)
        xbmcplugin.addDirectoryItem(handle=st.plugin_handle, url=plugin_url_val, listitem=liz, isFolder=pasta_param, totalItems=total_param if total_param > 0 else 0)
    except Exception as e: k.log(f"Error in addCont for '{name_param}': {e}\n{traceback.format_exc()}", xbmc.LOGERROR)


def decorate_folder_item(liz, display_name):
    """Póster, sinopsis y año de TMDb para carpetas de series, temporadas y películas (solo con clave de TMDb y metadatos activados)."""
    if not (metadata.enabled() and metadata.tmdb_key()): return
    try:
        meta = metadata.folder_cached(display_name)
        if not meta:
            logo = metadata.platform_logo(display_name)  # Netflix, HBO Max, Disney+...: el logo hace de carátula
            if logo: liz.setArt({'poster': logo, 'thumb': logo, 'icon': logo})
            return
        tag = liz.getVideoInfoTag()
        kind = meta.get('kind') or 'video'
        tag.setMediaType(kind)
        if kind in ('tvshow', 'season'): tag.setTvShowTitle(meta.get('title') or '')
        if kind == 'season' and meta.get('season'): tag.setSeason(int(meta['season']))
        if meta.get('year'): tag.setYear(int(meta['year']))
        if meta.get('plot'): tag.setPlot(meta['plot'])
        if meta.get('rating'): tag.setRating(float(meta['rating']))
        art_ = {k_: v for k_, v in (('poster', meta.get('poster')), ('thumb', meta.get('poster')), ('icon', meta.get('poster')), ('fanart', meta.get('fanart'))) if v}
        if art_: liz.setArt(art_)
    except Exception as e:
        k.log(f"Folder metadata skipped: {e}", xbmc.LOGDEBUG)


def decorate_file_item(liz, display_name, url_param, kind):
    """Etiquetas del elemento: título/año/temporada/episodio desde el nombre (y TMDb si hay clave) + estado de visto."""
    # Nombre tal cual está en Chomikuj: el de la etiqueta sin el tamaño en color
    real_name = re.sub(r'\s*\[COLOR[^\]]*\].*?\[/COLOR\]\s*$', '', display_name or '').strip() or display_name
    raw = urllib.parse.unquote_plus(os.path.basename(urllib.parse.urlparse(url_param).path))
    raw = re.sub(r'\s*\([\d,.]+\s*[KMGT]?B\)$', '', raw)
    try:
        if kind == 'audio':
            tag = liz.getMusicInfoTag(); tag.setTitle(real_name); tag.setMediaType('song')
        else:
            tag = liz.getVideoInfoTag()
            if kind == 'video' and metadata.enabled():
                info = metadata.parse(real_name or raw)  # se interpreta el nombre real de Chomikuj (la URL puede traer ids y tamaños)
                tmdb = metadata.cached(info) or {}
                tag.setTitle(real_name)  # el título es el nombre de Chomikuj; el parser solo aporta año/temporada/episodio y TMDb póster/sinopsis
                tag.setMediaType(info['kind'])
                year = tmdb.get('year') or info['year']
                if year: tag.setYear(int(year))
                if info['kind'] == 'episode':
                    tag.setSeason(info['season']); tag.setEpisode(info['episode']); tag.setTvShowTitle(info['title'])
                if tmdb.get('plot'): tag.setPlot(tmdb['plot'])
                art = {k_: v for k_, v in (('poster', tmdb.get('poster')), ('thumb', tmdb.get('still') or tmdb.get('poster')), ('fanart', tmdb.get('fanart'))) if v}
                if art: liz.setArt(art)
            else:
                tag.setTitle(real_name)
                if kind == 'video': tag.setMediaType('video')
        playstate.apply_to_item(liz, tag, playstate.key_for(url_param))
    except Exception as e:
        k.log(f"Item metadata skipped: {e}", xbmc.LOGDEBUG)
