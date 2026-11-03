# -*- coding: utf-8 -*-
"""Búsqueda: historial, filtros, orden y ejecución."""
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

from resources.lib.common import DIALOG_MESSAGE, MainURL, GetThumbExt, art, abrir_url, caixadetexto, clean, get_active_account_details, login, net, notify, pastaperfil, selfAddon, traducao, user_agent, wtpath


def _history_limit():
    try: return max(0, min(50, int(float(selfAddon.getSetting('search_history_size') or 15))))
    except ValueError: return 15


def _history_list():
    if _history_limit() <= 0: return []
    try:
        with store.db() as c:
            return c.execute("SELECT term, ftype FROM search_history ORDER BY ts DESC LIMIT ?", (_history_limit(),)).fetchall()
    except Exception as e:
        k.log(f"Search history unavailable: {e}", xbmc.LOGWARNING)
        return []


def _history_add(term, ftype):
    limit = _history_limit()
    if limit <= 0 or not term: return
    try:
        with store.db() as c:
            c.execute("INSERT OR REPLACE INTO search_history(term, ftype, ts) VALUES (?,?,?)", (term, ftype, _time.time()))
            c.execute("DELETE FROM search_history WHERE id NOT IN (SELECT id FROM search_history ORDER BY ts DESC LIMIT ?)", (limit,))
    except Exception as e:
        k.log(f"Could not store search history: {e}", xbmc.LOGWARNING)


def _history_clear():
    try:
        with store.db() as c: c.execute("DELETE FROM search_history")
    except Exception as e:
        k.log(f"Could not clear search history: {e}", xbmc.LOGWARNING)


def _search_sort_mode():
    mode = selfAddon.getSetting('search_sort')
    if mode == '': mode = '1' if selfAddon.getSetting('search-order') == 'true' else '0'  # compatibilidad con el ajuste antiguo
    return mode


def _sort_search_results(reslist):
    mode = _search_sort_mode()
    def size_key(item): return item[0] if isinstance(item[0], (int, float)) else 0
    def name_key(item):
        data = item[1]
        return str(data[1] if len(data) >= 3 else data[0]).lower()
    if mode == '1': return sorted(reslist, key=size_key, reverse=True)
    if mode == '2': return sorted(reslist, key=size_key)
    if mode == '3': return sorted(reslist, key=name_key)
    return reslist


def _search_filters_dialog():
    sort_labels = [strings.t(40325), strings.t(40326), strings.t(40327), strings.t(40328)]
    try: preselect = int(_search_sort_mode())
    except ValueError: preselect = 0
    idx = DIALOG_MESSAGE.select(strings.t(40324), sort_labels, preselect=preselect)
    if idx < 0: return
    selfAddon.setSetting('search_sort', str(idx))
    min_mb = DIALOG_MESSAGE.numeric(0, strings.t(40329), selfAddon.getSetting('min-size') or '0')
    if min_mb == '': return
    max_mb = DIALOG_MESSAGE.numeric(0, strings.t(40330), selfAddon.getSetting('max-size') or '0')
    if max_mb == '': return
    selfAddon.setSetting('min-size', min_mb)
    selfAddon.setSetting('max-size', max_mb)
    selfAddon.setSetting('activate-size', 'true' if (min_mb not in ('', '0') or max_mb not in ('', '0')) else 'false')
    notify(strings.t(40346))


def _search_type_options():
    target_site = MainURL
    options_url = target_site + 'action/Help'
    k.log(f"Fetching search options from: {options_url}", xbmc.LOGINFO)
    conteudo_bytes = abrir_url(options_url)
    options_found = []
    if conteudo_bytes:
        conteudo_text = clean(conteudo_bytes.decode('utf-8', 'ignore'))
        options_found = re.findall(r'<option value="([^"]+?)">([^<]+?)</option>', conteudo_text)
    if not options_found:
         k.log("Could not find search options in HTML; using defaults.", xbmc.LOGWARNING)
         opcoeslabel = ["Video", "Audio", "Image", "Document", "Archive", "All"]
         opcoesvalue = ["video", "audio", "image", "doc", "archive", "all"]
    else:
         opcoesvalue = [opt[0] for opt in options_found]
         opcoeslabel = [html.unescape(opt[1]).strip() for opt in options_found]
    translations = {0: traducao(40067), 1: traducao(40069), 2: traducao(40068), 3: traducao(40070), 4: traducao(40071), 5: traducao(40066), 6: traducao(40072)}
    for i in range(min(len(opcoeslabel), len(translations))):
        opcoeslabel[i] = translations[i]
        if opcoesvalue[i] == "all": opcoeslabel[i] = translations[5]
    return opcoeslabel, opcoesvalue


# --- Búsqueda local: recorre las carpetas y subcarpetas de la cuenta activa -------------------------------
_INDEX_TTL = 6 * 3600  # el índice de la cuenta se reutiliza 6 horas (o hasta "Actualizar índice")


def _norm(text):
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def _index_path(username):
    safe = re.sub(r'[^A-Za-z0-9_.-]+', '_', username)
    return os.path.join(pastaperfil, f'search_index_{safe}.json')


def _load_index(username):
    try:
        with open(_index_path(username), 'r', encoding='utf-8') as fh:
            data = json.load(fh)
        if time.time() - data.get('ts', 0) < _INDEX_TTL and data.get('items'):
            return data['items']
    except (OSError, ValueError):
        pass
    return None


def _build_index(username):
    """Recorre toda la cuenta (carpetas, subcarpetas y páginas). Devuelve None si el usuario cancela o el escaneo es incompleto."""
    from resources.lib.library import walk_folder_files, WalkIncomplete
    root = MainURL + urllib.parse.quote(username)
    progress = xbmcgui.DialogProgress()
    progress.create(traducao(40011), strings.t(40395))
    items, state = [], {'files': 0, 'dirs': 0, 'cancel': False}

    def on_page(rel, page):
        if progress.iscanceled(): state['cancel'] = True; return
        shown = rel or '/'
        if len(shown) > 60: shown = '...' + shown[-57:]
        try: progress.update(0, f"{strings.t(40395)}\n{shown}\n{strings.t(40396).format(state['files'], state['dirs'])}")
        except Exception: pass

    try:
        try:
            for entry in walk_folder_files(root, on_page, include_folders=True):
                if state['cancel'] or progress.iscanceled(): state['cancel'] = True; break
                if entry.get('is_dir'):
                    state['dirs'] += 1
                    items.append(['d', entry['title'], '', entry['url'], '', entry['rel_dir']])
                else:
                    state['files'] += 1
                    items.append(['f', entry['title'], entry['ext'], entry['url'], entry['size'], entry['rel_dir']])
        except WalkIncomplete:
            k.log("Search: indexación incompleta; no se persiste el índice", xbmc.LOGWARNING)
            return None
    finally:
        progress.close()
    if state['cancel']: return None
    try:
        os.makedirs(pastaperfil, exist_ok=True)
        with open(_index_path(username), 'w', encoding='utf-8') as fh:
            json.dump({'ts': time.time(), 'items': items}, fh)
    except OSError as e:
        k.log(f"Could not save search index: {e}", xbmc.LOGWARNING)
    return items


def _get_index(username, force=False):
    if not force:
        items = _load_index(username)
        if items is not None: return items
    return _build_index(username)


def run_search(term, force_index=False):
    """Busca `term` (todas las palabras, sin importar mayúsculas ni acentos) en los nombres de carpetas y archivos de la cuenta."""
    account = get_active_account_details()
    if not account or not account.get('username'):
        notify(traducao(40225), error=True); return
    if not login(True):
        notify(traducao(40195), error=True); return
    items = _get_index(account['username'], force=force_index)
    if items is None:
        notify(strings.t(40397)); return
    words = _norm(term).split()
    if not words:
        return
    _history_add(term, '')
    hits = []
    for kind, title, ext, url, size, rel in items:
        hay = _norm(f"{title}{ext}")
        if all(w in hay for w in words): hits.append((kind, title, ext, url, size, rel))
    if not hits:
        notify(strings.t(40398).format(term)); return
    sort_mode = _search_sort_mode()
    if sort_mode == '3': hits.sort(key=lambda h: (h[0] != 'd', _norm(h[1])))
    else: hits.sort(key=lambda h: (h[0] != 'd', _norm(h[5] + '/' + h[1])))  # carpetas primero, luego por ruta
    total = len(hits)
    from resources.lib.ui import addCont, addDir
    folder_icon = os.path.join(wtpath, art[1:], 'folder.png')
    for kind, title, ext, url, size, rel in hits:
        where = urllib.parse.unquote_plus(rel).replace('\\', '/') if rel else '/'
        if kind == 'd':
            addDir(f"{title} [COLOR gray]({where})[/COLOR]", url, 3, folder_icon, total, True)
        else:
            addCont(f"{title}{ext} [COLOR gray]({where})[/COLOR] [COLOR white]{size}[/COLOR]", url, 4, size, GetThumbExt(ext), total)


def pesquisa():
    """Historial -> nueva búsqueda -> resultados de las carpetas y subcarpetas de la cuenta activa."""
    while True:
        history = _history_list()
        entries = [strings.t(40321)]
        for term_h, _ftype_h in history:
            entries.append(term_h)
        entries.append(strings.t(40399))  # Actualizar índice
        if history: entries.append(strings.t(40322))
        choice = DIALOG_MESSAGE.select(traducao(40022), entries)
        if choice < 0: return
        if choice == 0:
            term = caixadetexto('pesquisa')
            if term: return run_search(term)
            continue
        if choice <= len(history):
            return run_search(history[choice - 1][0])
        if choice == len(history) + 1:
            account = get_active_account_details()
            if account and account.get('username') and login(True):
                items = _get_index(account['username'], force=True)
                if items is not None: notify(strings.t(40400).format(len(items)))
            continue
        _history_clear(); notify(strings.t(40331))


def proxpesquisa_ck_page():
    form_d = {}
    try:
        loaded_data = st.addon.load_data('temp.txt')
        if isinstance(loaded_data, dict) and 'Page' in loaded_data:
             form_d = loaded_data
             form_d["Page"] = int(form_d.get("Page", 0)) + 1
        else:
             k.log("Invalid or missing temp data for next search page.", xbmc.LOGERROR)
             notify(traducao(40205), error=True)
             return
    except Exception as e:
         k.log(f"Error loading temp search data: {e}", xbmc.LOGERROR)
         notify(traducao(40206).format(e), error=True)
         return

    site_url = MainURL
    host = site_url.replace('https://', '').replace('/', '')
    referer_url = st.params.get('url', site_url)
    ref_data = {'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded', 'Host': host, 'Origin': site_url, 'Referer': referer_url, 'User-Agent': user_agent, 'X-Requested-With': 'XMLHttpRequest'}
    if not login(True):
        notify(traducao(40207), error=True)
        return

    search_api_url = site_url + 'action/SearchFiles'
    k.log(f"Fetching next search page ({form_d.get('Page', '?')}) from {search_api_url}", xbmc.LOGINFO)
    try:
        conteudo_bytes = net.http_POST(search_api_url, form_data=form_d, headers=ref_data).content
        if not conteudo_bytes:
            k.log("No content received for next search page.", xbmc.LOGWARNING)
            notify(traducao(40208), error=True)
            return
    except Exception as e:
         k.log(f"Error fetching next search page: {e}", xbmc.LOGERROR)
         notify(traducao(40209).format(e), error=True)
         return

    try: st.addon.save_data("temp.txt", form_d)
    except Exception as e: k.log(f"Error saving updated temp search data: {e}", xbmc.LOGWARNING)
    page_name = f"{traducao(40031)} {traducao(40062)} {form_d.get('Page', '?')}"
    placeholder_url = site_url + f'/action/SearchFiles/page{form_d.get("Page", "?")}'
    pastas(placeholder_url, page_name, conteudo=conteudo_bytes)


def pastas_de_fora(url, name, formcont=None, conteudo=b''):
    k.log(f"External search request: Name='{name}', URL='{url}'", xbmc.LOGINFO)
    if not login(True):
        notify(traducao(40195), error=True)
        return

    file_type_setting = selfAddon.getSetting('search-file-type') or 'video'
    search_term = name
    form_data = {
        'submitSearchFiles': 'Procurar', 'IsGallery': 'False',
        'FileName': search_term, 'FileType': file_type_setting,
        'ShowAdultContent': 'True'
    }
    activate_size_setting = selfAddon.getSetting('activate-size')
    if activate_size_setting != 'false':
        form_data['SizeFrom'] = selfAddon.getSetting('min-size')
        form_data['SizeTo'] = selfAddon.getSetting('max-size')
    placeholder_url = MainURL + '/action/SearchFiles/external_search_initiated'
    pastas(placeholder_url, f"{traducao(40031)}: {search_term}", formcont=form_data, conteudo=b'', past=False, deFora=True)


def test(pesquisa):
    k.log(f"--- Running Test Search for: {pesquisa} ---", xbmc.LOGINFO)
    if not login(True): k.log("Test search failed: Login required.", xbmc.LOGERROR); return None
    form_d = {'FileName': pesquisa, 'submitSearchFiles': 'Buscar', 'FileType': 'video', 'IsGallery': 'False', 'ShowAdultContent': 'True'}
    search_url = MainURL + '/action/SearchFiles/test_search_mode'
    results = pastas(search_url, f"{traducao(40031)}: {pesquisa}", formcont=form_d, past=True, deFora=True, listagem=True)
    k.log(f"--- Test Search Results ({len(results) if results else 0} items): {results} ---", xbmc.LOGINFO)
    return results


# Importaciones entre módulos de funciones al final: así las referencias circulares son seguras
from resources.lib.listing import pastas
