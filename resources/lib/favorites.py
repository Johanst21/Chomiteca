# -*- coding: utf-8 -*-
"""Favoritos y atajos."""
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

from resources.lib.common import GetThumbExt, MainURL, _get_db_connection, abrir_url_cookie, art, clean_title, get_active_account_details, login, net, notify, traducao, user_agent, wtpath
from resources.lib.ui import addCont, addDir


def favoritos():
    active_account = get_active_account_details()
    if not active_account or not active_account.get('username'):
         notify(traducao(40199), error=True)
         return

    user_chomik_name = active_account['username']
    site_to_use = MainURL

    if not login(True):
         notify(traducao(40200), error=True)
         return

    profile_url = site_to_use + urllib.parse.quote(user_chomik_name)
    k.log(f"Fetching favorites for {user_chomik_name} from {profile_url}", xbmc.LOGINFO)
    conteudo_bytes = abrir_url_cookie(profile_url)
    if not conteudo_bytes:
        notify(traducao(40201).format(user_chomik_name), error=True)
        return

    conteudo_text = conteudo_bytes.decode('utf-8', 'ignore')
    chomikid_match = re.search(r'id="FriendsTargetChomikName".*?value="([^"]+)"', conteudo_text)
    token_match = re.search(r'name="__RequestVerificationToken".*?value="([^"]+)"', conteudo_text)
    if not (chomikid_match and token_match):
        k.log(f"Could not find chomikid or token on profile page for {user_chomik_name}.", xbmc.LOGWARNING)
        notify(traducao(40202), error=True)
        return

    chomikid = chomikid_match.group(1)
    token = token_match.group(1)
    pagina = 1
    current_url_param = st.params.get('url', profile_url)
    form_d = {'page': str(pagina), 'chomikName': chomikid, '__RequestVerificationToken': token}
    ref_data = {'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded', 'Host': site_to_use.replace('https://', '').replace('/', ''), 'Origin': site_to_use, 'Referer': current_url_param, 'User-Agent': user_agent, 'X-Requested-With': 'XMLHttpRequest'}
    favorites_api_url = site_to_use + 'action/Friends/ShowAllFriends'
    k.log(f"Posting to {favorites_api_url} to get favorites list.", xbmc.LOGDEBUG)
    info_bytes = net.http_POST(favorites_api_url, form_data=form_d, headers=ref_data).content
    if not info_bytes:
        notify(traducao(40203), error=True)
        return

    info_text = info_bytes.decode('utf-8', 'ignore').replace('javascript:;', '/javascript:;')
    users = re.findall(r'<div class="friend avatar">.*?<a href="/([^"]+?)" title="([^"]+?)">.*?<img.*?src="([^"]+?)".*?>', info_text, re.DOTALL | re.IGNORECASE)
    if not users:
         k.log("No favorite users found in the API response.", xbmc.LOGINFO)
         notify(traducao(40204), error=True)
         return

    total_favs = len(users)
    all_favs_data = []
    for urluser, nomeuser, thumbuser in users:
        if not thumbuser.startswith(('http:', 'https:')):
             thumbuser = "https:" + thumbuser if thumbuser.startswith('//') else site_to_use.rstrip('/') + thumbuser
        display_name = f"{html.unescape(nomeuser)}"
        user_profile_url = site_to_use.rstrip('/') + '/' + urluser.lstrip('/')
        all_favs_data.append((display_name, user_profile_url, thumbuser))
    for fav_data in all_favs_data:
        addDir(fav_data[0], fav_data[1], 3, fav_data[2], total_favs, True)
    paginas(info_text)


def atalhos(action=None):
    conn, cursor = _get_db_connection()
    if not conn: return
    try:
        if action == 'addfolder' or action == 'addfile':
            current_url = st.params.get("url", "")
            current_name = st.params.get("name", "")
            if not current_url or not current_name:
                 k.log("URL or Name missing for adding shortcut", xbmc.LOGWARNING)
                 notify(traducao(40181), error=True)
                 return
            cleaned_name = clean_title(current_name)
            shortcut_type = "folder" if action == 'addfolder' else "file"
            try:
                 cursor.execute("INSERT OR IGNORE INTO atalhos (name, url, type) VALUES (?, ?, ?)",
                                (cleaned_name, current_url, shortcut_type))
                 conn.commit()
                 if cursor.rowcount > 0:
                      notify(traducao(10000))
                 else:
                      notify(traducao(40112))
            except sqlite3.Error as e:
                 k.log(f"Database error adding shortcut '{cleaned_name}': {e}", xbmc.LOGERROR)
                 notify(traducao(40129).format(f"{traducao(10000).lower()}: {e}"), error=True)
        elif action == 'remove':
            ref_to_remove_str = st.params.get("name", "")
            if ref_to_remove_str.isdigit():
                ref_to_remove = int(ref_to_remove_str)
                try:
                     cursor.execute("DELETE FROM atalhos WHERE ref = ?", (ref_to_remove,))
                     conn.commit()
                     if cursor.rowcount > 0:
                          notify(traducao(10001))
                          xbmc.executebuiltin("Container.Refresh")
                     else:
                          notify(traducao(40113))
                except sqlite3.Error as e:
                     k.log(f"Database error removing shortcut ref {ref_to_remove}: {e}", xbmc.LOGERROR)
                     notify(traducao(40129).format(f"{traducao(10001).lower()}: {e}"), error=True)
            else:
                 k.log(f"Invalid ref provided for shortcut removal: {ref_to_remove_str}", xbmc.LOGWARNING)
                 notify(traducao(40176), error=True)
        else:
            cursor.execute("SELECT ref, name, url, type FROM atalhos ORDER BY name COLLATE NOCASE")
            shortcuts_data = cursor.fetchall()
            total_items = len(shortcuts_data)
            if not shortcuts_data:
                 notify(traducao(40115))
            for atal in shortcuts_data:
                ref, db_name, db_url, db_type = atal
                try:
                    if db_url.startswith(MainURL):
                        path_part = db_url.split(MainURL, 1)[1]
                        path_elements = path_part.split('/')
                        if len(path_elements) > 1:
                             display_path_raw = '/'.join(path_elements[:-1])
                             display_path = urllib.parse.unquote_plus(display_path_raw).replace('*', '/')
                        else: display_path = "/"
                    else: display_path = "External"
                except Exception:
                    display_path = "ErrorPath"
                display_name_item = f'{db_name} ({display_path})'
                if db_type == 'file':
                    file_icon = GetThumbExt(os.path.splitext(db_url)[1])
                    addCont(display_name_item, db_url, 4, '', file_icon, total_items, False, atalhos_param=str(ref))
                elif db_type == 'folder':
                    folder_icon = os.path.join(wtpath, art[1:], 'folder.png')
                    addDir(display_name_item, db_url, 3, folder_icon, total_items, True, atalhos_param=str(ref))
    except Exception as e:
         k.log(f"Error in atalhos function (action: {action}): {e}", xbmc.LOGERROR)
         traceback.print_exc()
         notify(traducao(40177).format(e), error=True)
    finally:
        if conn: conn.close()


# Importaciones entre módulos de funciones al final: así las referencias circulares son seguras
from resources.lib.listing import paginas
