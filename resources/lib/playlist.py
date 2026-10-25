# -*- coding: utf-8 -*-
"""Lista de reproducción temporal en BD."""
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

from resources.lib.common import KODI_PLAYER, _get_db_connection, notify, traducao
from resources.lib.ui import set_video_tag


def _create_playlist_table():
     conn, cursor = _get_db_connection()
     if not conn: return False
     try:
          cursor.execute("""
               CREATE TABLE IF NOT EXISTS playlist (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    title TEXT NOT NULL,
                    UNIQUE(url, title)
               )
          """)
          conn.commit()
          return True
     except sqlite3.Error as e:
          k.log(f"Database error creating playlist table: {e}", xbmc.LOGERROR)
          notify(traducao(40178).format(e), error=True)
          return False
     finally:
          if conn: conn.close()


def add_items_to_playlist_db(items_list):
     if not items_list: return 0
     if not _create_playlist_table(): return 0
     conn, cursor = _get_db_connection()
     if not conn: return 0
     added_count = 0
     try:
          data_to_insert = [(item[0], item[1]) for item in items_list if len(item) == 2]
          cursor.executemany("INSERT OR IGNORE INTO playlist (title, url) VALUES (?, ?)", data_to_insert)
          conn.commit()
          added_count = cursor.rowcount
          k.log(f"Added {added_count} new items to playlist DB.", xbmc.LOGINFO)
     except sqlite3.Error as e:
          k.log(f"Database error adding to playlist: {e}", xbmc.LOGERROR)
          notify(traducao(40179).format(e), error=True)
     except Exception as e:
          k.log(f"General error adding to playlist DB: {e}", xbmc.LOGERROR)
          traceback.print_exc()
     finally:
          if conn: conn.close()
     return added_count


def clear_playlist_db():
     if not _create_playlist_table():
          k.log("Failed to ensure playlist table exists before clearing.", xbmc.LOGERROR)
          return False
     k.log("Playlist table structure verified/created.", xbmc.LOGDEBUG)
     conn, cursor = _get_db_connection()
     if not conn: return False
     try:
          cursor.execute("DELETE FROM playlist")
          conn.commit()
          k.log("Playlist database table cleared.", xbmc.LOGINFO)
          return True
     except sqlite3.Error as e:
          k.log(f"Database error during DELETE FROM playlist: {e}", xbmc.LOGERROR)
          notify(traducao(40180).format(e), error=True)
          return False
     except Exception as e:
         k.log(f"General error clearing playlist DB entries: {e}", xbmc.LOGERROR)
         traceback.print_exc()
         return False
     finally:
          if conn: conn.close()


def play_playlist_from_db():
     conn, cursor = _get_db_connection()
     if not conn: return
     try:
          cursor.execute("SELECT title, url FROM playlist ORDER BY id")
          playlist_entries = cursor.fetchall()
          if not playlist_entries:
               notify(traducao(40116))
               return
          kodi_playlist = xbmc.PlayList(xbmc.PLAYLIST_VIDEO)
          kodi_playlist.clear()
          # Cada entrada apunta a este mismo plugin (modo 4): Kodi resuelve el enlace temporal
          # justo cuando le toca, así no caduca mientras suenan los elementos anteriores.
          for title, item_url in playlist_entries:
               entry_url = f"{sys.argv[0]}?url={urllib.parse.quote_plus(item_url)}&mode=4&name={urllib.parse.quote_plus(title)}"
               list_item = xbmcgui.ListItem(title, path=entry_url)
               set_video_tag(list_item, title)
               list_item.setProperty('IsPlayable', 'true')
               kodi_playlist.add(entry_url, list_item)
          k.log(f"Playing playlist from DB with {len(playlist_entries)} lazily-resolved items.", xbmc.LOGINFO)
          KODI_PLAYER.play(kodi_playlist)
          notify(traducao(40117).format(len(playlist_entries)))
     except sqlite3.Error as e:
          k.log(f"Database error loading playlist for playback: {e}", xbmc.LOGERROR)
          notify(traducao(40178).format(f"{traducao(40046)}: {e}"), error=True)
     except Exception as e:
          k.log(f"General error playing playlist from DB: {e}\n{traceback.format_exc()}", xbmc.LOGERROR)
          notify(traducao(40129).format(f"{traducao(40046)}: {e}"), error=True)
     finally:
          if conn: conn.close()
