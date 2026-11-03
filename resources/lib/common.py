# -*- coding: utf-8 -*-
"""Infraestructura compartida: constantes, red con caché/reintentos, login y cuentas, utilidades de texto."""
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
from resources.lib import accounts as accounts_store


# ---- constantes ----
net = Net()
MONITOR = xbmc.Monitor()
VIDEO_EXTS_UI = ['.mkv', '.mp4', '.avi', '.wmv', '.mov', '.flv', '.ts', '.m2ts', '.iso', '.mpg', '.mpeg', '.webm', '.vob', '.3gp']
AUDIO_EXTS = ['.mp3', '.flac', '.m4a', '.aac', '.ogg', '.wav', '.wma', '.ac3', '.alac', '.ape', '.mid', '.midi', '.aiff']
addon_id = 'plugin.video.chomiteca'
selfAddon = k.ADDON  # proxy: siempre lee los ajustes actuales
nameURL = 'Chomikuj'
MainURL = 'https://chomikuj.pl/'
art = '/resources/art/'
user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
KODI_PLAYER = xbmc.Player()
wtpath = k.ADDON_PATH
iconpequeno = os.path.join(wtpath, art[1:], 'iconpq.png')
DIALOG_MESSAGE = xbmcgui.Dialog()
pastaperfil = xbmcvfs.translatePath(selfAddon.getAddonInfo('profile'))
cookies = os.path.join(pastaperfil, "cookies.lwp")
DATABASE_PATCH = os.path.join(pastaperfil, "chomikdb.db")
ACCOUNTS_FILE = os.path.join(pastaperfil, "accounts.json")
MODE_MANAGE_ACCOUNTS = 40
MODE_DELETE_COOKIES = 33
MODE_SETTINGS = 8
MODE_STRM_GEN_DIALOG = 35


def load_accounts():
    return accounts_store.load()


def save_accounts(accounts_list):
    try:
        accounts_store.save(accounts_list)  # escritura atómica con permisos 0600
        return True
    except OSError as e:
        k.log(f"Error guardando accounts.json: {e}", xbmc.LOGERROR)
        return False


def get_active_account_details():
    active_id = selfAddon.getSetting('active_account_id')
    if not active_id:
        return None
    accounts = load_accounts()
    for acc in accounts:
        if acc.get('id') == active_id:
            return acc
    return None


def update_global_user_refs(account_details):
    pass
    if account_details and account_details.get('username'):
        st.username_setting_global_ref = account_details['username']
        st.usernameURL_global_ref = urllib.parse.quote(st.username_setting_global_ref)
    else:
        st.username_setting_global_ref = ""
        st.usernameURL_global_ref = ""
    k.log(f"Global user refs updated: User='{st.username_setting_global_ref}', URLPart='{st.usernameURL_global_ref}'", xbmc.LOGDEBUG)


def set_active_account_and_relogin(account_id_to_activate, account_details_provided=None):
    old_active_id = selfAddon.getSetting('active_account_id')
    target_account = account_details_provided
    if not target_account:
        accounts = load_accounts()
        for acc in accounts:
            if acc.get('id') == account_id_to_activate:
                target_account = acc
                break
    if not target_account:
        notify(traducao(40097).format(account_id_to_activate), error=True)
        return

    account_display_name = target_account.get('label', target_account.get('username'))
    if old_active_id == account_id_to_activate:
        notify(traducao(40098).format(account_display_name))
    else:
        selfAddon.setSetting('active_account_id', account_id_to_activate)
        notify(traducao(40099).format(account_display_name))

    update_global_user_refs(target_account)
    if os.path.exists(cookies):
        try:
            os.remove(cookies)
            k.log("Cookies eliminadas para cambio/re-login de cuenta.", xbmc.LOGINFO)
        except Exception as e:
            k.log(f"Error eliminando cookies: {e}", xbmc.LOGERROR)

    if login(defora=True):
        notify(traducao(40095))
    else:
        notify(traducao(40096), error=True)
    xbmc.executebuiltin("Container.Refresh")


def notify(msg, title="Chomiteca", error=False):
    icon = xbmcgui.NOTIFICATION_ERROR if error else xbmcgui.NOTIFICATION_INFO
    k.log(f"{title}: {msg}", level=xbmc.LOGERROR if error else xbmc.LOGINFO)
    # Dialog().notification: sin construir cadenas de executebuiltin (las comillas en msg las rompían)
    xbmcgui.Dialog().notification(title, str(msg), icon, 5000)


def delete_cookies(delCookiesPath):
    confirm = DIALOG_MESSAGE.yesno(traducao(40087), f"{traducao(10105).split('?')[0]} {traducao(40081).lower()}?")
    if confirm:
        if os.path.exists(delCookiesPath):
            try:
                os.remove(delCookiesPath)
                notify(traducao(40106))
                xbmc.executebuiltin("Container.Refresh")
            except OSError as e:
                k.log(f"Error deleting cookies file {delCookiesPath}: {e}", xbmc.LOGERROR)
                notify(traducao(40129).format(f"{traducao(40081)}: {e}"), error=True)
        else:
            notify(traducao(40107))
    else:
        notify(traducao(40108))


def login(defora=False):
    active_account = get_active_account_details()
    if not active_account or not active_account.get('username') or not active_account.get('password'):
        k.log("Login attempt failed: No active account or incomplete credentials.", xbmc.LOGWARNING)
        if not defora:
            notify(traducao(40109), error=True)
        return False
    current_username = active_account['username']
    current_password = active_account['password']
    current_site = MainURL
    current_label = active_account.get('label', nameURL)
    cookies_ok = False
    if os.path.exists(cookies):
        try:
            cookies_ok = net.load_cookies(cookies)
            if cookies_ok:
                k.log(f"Cookies cargadas del archivo para cuenta: {current_label}", xbmc.LOGINFO)
            else:
                k.log(f"net.load_cookies devolvió False para {current_label}. Intentando login completo.", xbmc.LOGWARNING)
        except Exception as e:
            k.log(f"Error cargando cookies de {cookies} para {current_label}: {e}", xbmc.LOGERROR)
            cookies_ok = False
    if not cookies_ok:
        k.log(f"Cookies inválidas/ausentes o fallo al cargar para {current_label}. Intentando login completo.", xbmc.LOGINFO)
        return create_login_single(current_username, current_password, current_site, current_label, defora)
    else:
        k.log(f"Usando cookies existentes para {current_label}.", xbmc.LOGINFO)
        return True


def create_login_single(user, pwd, site, label, defora_flag=False):
    """Login completo delegando en resources/lib/auth.py; sincroniza el cookie jar heredado (net)."""
    try:
        k.log(f"Attempting login for account: {label}", xbmc.LOGINFO)
        auth.login(make_session(), {"username": user, "password": pwd, "label": label})
        net.load_cookies(cookies)
        return True
    except auth.LoginError as e:
        if not defora_flag:
            notify(f"{label}: {e}", error=True)
        else:
            k.log(f"Login failed for {label}: {e}", xbmc.LOGWARNING)
        return False
    except Exception as e:
        k.log(f"Login exception for {label}: {e}", xbmc.LOGERROR)
        if not defora_flag:
            notify(traducao(40129).format(f"{label}: {e}"), error=True)
        return False


def _get_db_connection():
    try:
        conn = sqlite3.connect(DATABASE_PATCH, timeout=10)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS atalhos (
                ref INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                type TEXT NOT NULL CHECK(type IN ('folder', 'file'))
            )
        """)
        conn.commit()
        return conn, cursor
    except sqlite3.Error as e:
        k.log(f"Database connection error: {e}", xbmc.LOGERROR)
        notify(traducao(40226).format(e), error=True)
        return None, None


def returnExtra():
    sort_type = "Name"
    ascending = "True"
    files_sort = selfAddon.getSetting('filesorder')
    files_asc = selfAddon.getSetting('fileasc')

    if files_sort == "1": sort_type = "Extension"
    elif files_sort == "2": sort_type = "DateModified"
    elif files_sort == "3": sort_type = "Size"
    else: sort_type = "Name"

    if files_asc == "1": ascending = "False"
    else: ascending = "True"

    return f'?IsGallery=False&requestedFolderMode=filesList&fileListSortType={sort_type}&fileListAscending={ascending}'


def GetThumbExt(extensao):
    extensao = extensao.strip().lower()
    base_art_path = os.path.join(wtpath, art[1:])
    extensao_to_path = {
        ".7z": "rar/7z.png", ".ace": "rar/ace.png", ".rar": "rar/rar.png", ".tar": "rar/tar.png", ".zip": "rar/zip.png", ".jar": "rar/jar.png", ".gz": "rar/rar.png", ".tgz": "rar/rar.png",
        ".aac": "music/aac.png", ".aiff": "music/aiff.png", ".flac": "music/flac.png", ".m4a": "music/m4a.png", ".mp3": "music/mp3.png", ".ogg": "music/ogg.png", ".wav": "music/wav.png", ".wma": "music/wma.png", ".ac3": "music/ac3.png", ".m3u": "music/m3u.png", ".mid": "music/midi.png", ".midi": "music/midi.png",
        ".bmp": "foto/bmp.png", ".gif": "foto/gif.png", ".ico": "foto/ico.png", ".jpeg": "foto/jpeg.png", ".jpg": "foto/jpg.png", ".png": "foto/png.png", ".tif": "foto/tif.png", ".tiff": "foto/tiff.png", ".webp": "foto/webp.png", ".svg": "foto/png.png",
        ".bin": "img/bin.png", ".cue": "img/cue.png", ".img": "img/img.png", ".iso": "img/iso.png", ".mdf": "img/mdf.png", ".mds": "img/mds.png", ".nrg": "img/iso.png",
        ".avi": "video/avi.png", ".mkv": "video/mkv.png", ".mov": "video/mov.png", ".mp4": "video/mp4.png", ".mpeg": "video/mpeg.png", ".mpg": "video/mpg.png", ".ogm": "video/ogm.png", ".m4v": "video/m4v.png", ".wmv": "video/wmv.png", ".flv": "video/flv.png", ".webm": "video/webm.png", ".ts": "video/ts.png", ".m2ts": "video/m2ts.png", ".vob": "video/vob.png", ".ifo": "video/ifo.png", ".rm": "video/rm.png", ".rmvb": "video/rm.png", ".3gp": "video/3gp.png",
        ".doc": "files/doc.png", ".docx": "files/doc.png", ".xls": "files/xls.png", ".xlsx": "files/xls.png", ".ppt": "files/ppt.png", ".pptx": "files/ppt.png", ".pdf": "files/pdf.png", ".txt": "files/txt.png", ".rtf": "files/rtf.png", ".csv": "files/txt.png",
        ".exe": "files/exe.png", ".msi": "files/exe.png", ".apk": "files/apk.png",
        ".epub": "files/epub.png", ".mobi": "files/epub.png",
        ".torrent": "files/torrent.png",
        ".srt": "files/srt.png", ".sub": "files/sub.png", ".ass": "files/ass.png",
        ".py": "files/py.png", ".xml": "files/xml.png", ".html": "files/html.png", ".js": "files/js.png",
    }
    default_icon_relative = "file.png"
    icon_relative_path = extensao_to_path.get(extensao, default_icon_relative)
    full_path = os.path.join(base_art_path, icon_relative_path)
    default_full_path = os.path.join(base_art_path, default_icon_relative)
    if not xbmcvfs.exists(full_path):
         return default_full_path
    return full_path


def getKey(item):
    if isinstance(item, (list, tuple)) and len(item) > 0 and isinstance(item[0], (int, float)):
        return int(item[0])
    return 0


def ReturnStatus(site_label_param):
    if site_label_param == nameURL:
        active_account = get_active_account_details()
        if active_account and os.path.exists(cookies):
             return True
    return False


def returnValues(link):
    if not link: return None, None, None, None
    if "chomikuj.pl" in link:
        return MainURL, nameURL, "white", 24
    else:
        try:
            parsed_link = urlparse(link)
            base_url_fallback = f"{parsed_link.scheme}://{parsed_link.netloc}/"
            return base_url_fallback, parsed_link.netloc, "grey", 3
        except Exception:
            k.log(f"Could not determine site for link: {link}", xbmc.LOGWARNING)
            return None, None, None, None


def ReplaceSpecialChar(text):
    if not isinstance(text, str):
        try: text = str(text, 'utf-8')
        except TypeError: text = str(text)
        except UnicodeDecodeError: text = str(text)
    try:
        normalized_text = unicodedata.normalize('NFKD', text)
        ascii_text = normalized_text.encode('ascii', 'ignore').decode('ascii')
    except Exception as norm_e:
        st.addon.log_warning(f"Unicode normalization/ASCII conversion failed for '{text[:50]}': {norm_e}")
        ascii_text = text
    cleaned_text = re.sub(r'[^\w\s\.\-_]', '_', ascii_text)
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    cleaned_text = cleaned_text.strip(' .-_')
    cleaned_text = re.sub(r'[\s\._-]+', '-', cleaned_text)
    cleaned_text = cleaned_text.strip('-')
    return cleaned_text


def clean_folder(folder):
    try:
        if not isinstance(folder, str): folder = str(folder)
        decoded_folder = urllib.parse.unquote_plus(folder)
        no_format = re.sub(r'\[/?(?:B|COLOR|I|UPPERCASE|LOWERCASE|CR|CAPITALIZE|LIGHT)](.*?)(\[/(?:B|COLOR|I|UPPERCASE|LOWERCASE|CR|CAPITALIZE|LIGHT)])?|\[/?(?:B|COLOR|I|UPPERCASE|LOWERCASE|CR|CAPITALIZE|LIGHT)]', r'\1', decoded_folder, flags=re.IGNORECASE)
        no_format = re.sub(r'\[COLOR [^\]]+\](.*?)\[/COLOR\]', r'\1', no_format, flags=re.IGNORECASE)
        no_tags = re.sub('<[^>]+>', '', no_format)
        cleaned = ReplaceSpecialChar(html.unescape(no_tags))
        max_len = 100
        if len(cleaned) > max_len:
            name_part, ext_part = os.path.splitext(cleaned)
            if len(name_part) > max_len - len(ext_part) -1:
                 name_part = name_part[:max_len - len(ext_part) -1]
            cleaned = name_part + ext_part
        return cleaned.strip() if cleaned else "default_folder_name"
    except Exception as e:
         st.addon.log_warning(f"Error cleaning folder name '{folder}': {e}")
         return "error_cleaned_folder"


def clean_title(title):
    try:
        if not isinstance(title, str): title = str(title)
        decoded_title = urllib.parse.unquote_plus(title)
        no_format = re.sub(r'\[/?(?:B|COLOR|I|UPPERCASE|LOWERCASE|CR|CAPITALIZE|LIGHT)](.*?)(\[/(?:B|COLOR|I|UPPERCASE|LOWERCASE|CR|CAPITALIZE|LIGHT)])?|\[/?(?:B|COLOR|I|UPPERCASE|LOWERCASE|CR|CAPITALIZE|LIGHT)]', r'\1', decoded_title, flags=re.IGNORECASE)
        no_format = re.sub(r'\[COLOR [^\]]+\](.*?)\[/COLOR\]', r'\1', no_format, flags=re.IGNORECASE)
        no_tags = re.sub('<[^>]+>', '', no_format)
        cleaned = ReplaceSpecialChar(html.unescape(no_tags))
        return cleaned.strip() if cleaned else "default_title"
    except Exception as e:
        st.addon.log_warning(f"Error cleaning title '{title}': {e}")
        return title


_BBCODE = re.compile(r'\[/?(?:B|I|CR|UPPERCASE|LOWERCASE|CAPITALIZE|LIGHT)\]|\[/?COLOR[^\]]*\]', re.IGNORECASE)


from .textutils import real_title  # noqa: F401 (reexport)


def real_fs_name(text, max_len=180):
    """Como real_title pero válido como nombre de archivo/carpeta (solo cambia lo que el sistema de archivos prohíbe)."""
    name = real_title(text)
    name = name.replace(':', ' -').replace('"', "'")
    name = re.sub(r'[<>/\\|*\x00-\x1f]', '_', name).replace('?', '')
    name = re.sub(r'\s+', ' ', name).strip(' .')
    if len(name) > max_len:
        name = name[:max_len].rstrip(' .')
    return name or "sin_nombre"


def try_create_folder(folder_path):
     if not folder_path: return False
     if any(folder_path.startswith(proto) for proto in ['smb://', 'nfs://', 'ftp://', 'http://', 'https://', 'upnp://']): return True

     if not xbmcvfs.exists(folder_path):
          st.addon.log_info(f"Directory does not exist, attempting to create: {folder_path}")
          try:
               if xbmcvfs.mkdirs(folder_path):
                    st.addon.log_info(f"Successfully created directory: {folder_path}"); return True
               else:
                    st.addon.log_error(f"xbmcvfs.mkdirs failed to create directory (returned False): {folder_path}")
                    notify(traducao(40156).format(os.path.basename(folder_path)), error=True); return False
          except Exception as e:
               st.addon.log_error(f"Exception creating directory {folder_path}: {e}")
               notify(traducao(40157).format(e), error=True); return False
     else:
          try:
              stat_info = xbmcvfs.Stat(folder_path)
              if stat.S_ISDIR(stat_info.st_mode()):
                  return True
              else:
                  st.addon.log_error(f"Path exists but is not a directory: {folder_path}")
                  notify(traducao(40158).format(os.path.basename(folder_path)), error=True); return False
          except Exception as stat_e:
              st.addon.log_error(f"Error stating existing path {folder_path}: {stat_e}")
              notify(traducao(40159).format(stat_e), error=True); return False


def caixadetexto(context, ftype=""):
    title = "Input"; default_text = ""; hidden = False
    if context == "pastas": title = f"{traducao(40010)}{nameURL}"
    elif context == "password": title = traducao(40061); hidden = True; default_text = ""
    elif context == "pesquisa":
        title = traducao(40031)
        try: default_text = selfAddon.getSetting("ultima-pesquisa")
        except: pass
    else: title = context

    keyboard = xbmc.Keyboard(default_text, title, hidden)
    keyboard.doModal()
    if keyboard.isConfirmed():
        search_text = keyboard.getText()
        if context == "pesquisa":
             try: selfAddon.setSetting("ultima-pesquisa", search_text)
             except: pass
        return search_text
    else: return None


def abrir_url(url_param, headers=None, data=None, method=None):
    if headers is None: headers = {'User-Agent': user_agent}
    encoded_data = None
    if data:
        try: encoded_data = urllib.parse.urlencode(data).encode('utf-8')
        except Exception as enc_e: k.log(f"Failed to encode POST data for {url_param}: {enc_e}", xbmc.LOGERROR); return None

    if method: method = method.upper()
    if encoded_data and not method: method = 'POST'
    elif not method: method = 'GET'

    req = urllib.request.Request(url_param, data=encoded_data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
             if 200 <= response.getcode() < 300:
                 return response.read()
             else:
                 k.log(f"HTTP Error {response.getcode()} fetching {url_param}. Response: {response.read()[:500]}", xbmc.LOGERROR)
                 return None
    except urllib.error.HTTPError as e:
        k.log(f"HTTP Error {e.code}: {e.reason} for URL: {url_param}. Response: {e.read()[:500]}", xbmc.LOGERROR)
        return None
    except urllib.error.URLError as e:
        k.log(f"URL Error: {e.reason} for URL: {url_param}", xbmc.LOGERROR)
        return None
    except Exception as e:
        k.log(f"General Error fetching URL {url_param}: {e}", xbmc.LOGERROR); traceback.print_exc()
        return None


def savefile(filename, contents, pastafinal=pastaperfil):
    destination = os.path.join(pastafinal, filename) if pastafinal else filename
    fh = None
    try:
        if pastafinal and not any(pastafinal.startswith(proto) for proto in ['smb://', 'nfs://', 'ftp://', 'http://', 'https://', 'upnp://']):
            if not xbmcvfs.exists(pastafinal):
                xbmcvfs.mkdirs(pastafinal)

        mode_write = 'w'
        if isinstance(contents, bytes):
            mode_write = 'wb'
        elif not isinstance(contents, str):
            contents = str(contents)

        fh = xbmcvfs.File(destination, mode_write)
        fh.write(contents)
        return True
    except Exception as e:
        k.log(f"Failed to save file: {destination} - Error: {e}", xbmc.LOGERROR); traceback.print_exc()
        return False
    finally:
        if fh: fh.close()


def openfile(filename, pastafinal=pastaperfil):
    destination = os.path.join(pastafinal, filename)
    fh = None
    try:
        if not xbmcvfs.exists(destination): return None
        fh = xbmcvfs.File(destination, 'rb')
        contents = fh.readBytes()
        return contents
    except Exception as e:
        k.log(f"Failed to open file: {destination} - Error: {e}", xbmc.LOGERROR); traceback.print_exc()
        return None
    finally:
        if fh: fh.close()


def abrir_url_cookie(url_param, erro=True, data=None, method=None, cache=False):
    """GET/POST con las cookies de sesión. cache=True usa la caché de carpetas (solo GET).
    Reintenta con backoff ante 429/5xx/timeouts y reloguea una vez si la sesión caducó (401/403)."""
    if data and method is None: method = 'POST'
    use_cache = bool(cache) and method != 'POST' and not data
    if use_cache:
        hit = cache_mod.get(url_param)
        if hit is not None:
            k.log("Cache hit for folder page", xbmc.LOGDEBUG)
            return hit
    if not os.path.exists(cookies):
         k.log("Cookie file not found for request.", xbmc.LOGWARNING)
         if not login(True):
              if erro: notify(traducao(40217), error=True)
              return None
    try:
        if not net.load_cookies(cookies):
             k.log("Failed to set cookies in net object from file.", xbmc.LOGWARNING)
             if not login(True):
                  if erro: notify(traducao(40218), error=True)
                  return None
             if not net.load_cookies(cookies):
                  if erro: notify(traducao(40219), error=True)
                  return None
    except Exception as cookie_e:
        k.log(f"Error setting/loading cookies: {cookie_e}", xbmc.LOGERROR)
        if erro: notify(traducao(40220).format(cookie_e), error=True)
        return None

    sitebase, _, _, _ = returnValues(url_param)
    host_val = urlparse(sitebase if sitebase else url_param).netloc
    referer_val = sitebase if sitebase else url_param
    ref_data = {
        'Host': host_val,
        'Connection': 'keep-alive',
        'Referer': referer_val,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'User-Agent': user_agent
    }
    relogged = False
    last_msg = None
    for attempt in range(3):
        try:
            if method == 'POST':
                response = net.http_POST(url_param, form_data=data, headers=ref_data)
            else:
                response = net.http_GET(url_param, headers=ref_data)
            code = getattr(response, 'code', 200)
            if code in (401, 403) and not relogged:
                relogged = True
                if erro: notify(strings.t(40342))
                delete_cookies_silent()
                if login(True) and net.load_cookies(cookies):
                    continue
                last_msg = describe_error(code); break
            if code in (429, 500, 502, 503, 504) and attempt < 2:
                last_msg = describe_error(code)
                k.log(f"HTTP {code} (attempt {attempt + 1}/3), retrying.", xbmc.LOGWARNING)
                if MONITOR.waitForAbort(backoff(attempt)): return None
                continue
            if code >= 400:
                k.log(f"HTTP Error {code} fetching (with cookies). Response: {response.content[:200]}", xbmc.LOGERROR)
                last_msg = describe_error(code); break
            body = response.content
            if use_cache and body: cache_mod.put(url_param, body)
            return body
        except Exception as e:
            last_msg = describe_error(e)
            k.log(f"Error fetching URL with cookies (attempt {attempt + 1}/3): {e}", xbmc.LOGERROR)
            if attempt < 2:
                if MONITOR.waitForAbort(backoff(attempt)): return None
                continue
    if erro and last_msg:
        notify(f"{traducao(40032)}: {last_msg}", error=True)
    return None


def delete_cookies_silent():
    try:
        if os.path.exists(cookies): os.remove(cookies)
    except OSError as e:
        k.log(f"Could not remove cookie file: {e}", xbmc.LOGWARNING)


def redirect(url_param):
     k.log(f"Checking redirect for: {url_param}", xbmc.LOGDEBUG)
     try:
          req = urllib.request.Request(url_param, headers={'User-Agent': user_agent}, method='HEAD')
          with urllib.request.urlopen(req, timeout=10) as response:
               final_url = response.geturl()
               return final_url
     except Exception as e:
          k.log(f"Failed to get redirected URL for {url_param}: {e}", xbmc.LOGWARNING)
          return url_param


def get_params():
    param = {}
    if len(sys.argv) > 2 and sys.argv[2]:
        paramstring = sys.argv[2]
        if paramstring.startswith('?'): paramstring = paramstring[1:]
        if paramstring:
            pairs = paramstring.split('&')
            for pair in pairs:
                if '=' in pair:
                    splitparams = pair.split('=', 1); key = splitparams[0]
                    try: value = urllib.parse.unquote_plus(splitparams[1])
                    except Exception as dec_e:
                         k.log(f"Error decoding param value '{splitparams[1]}' for key '{key}': {dec_e}", xbmc.LOGWARNING)
                         value = splitparams[1]
                    param[key] = value
                elif pair: param[pair] = ""
    return param


def clean(text):
    if not isinstance(text, str):
         try: text = text.decode('utf-8', 'ignore')
         except AttributeError: text = str(text)
         except UnicodeDecodeError: text = str(text)
    try:
        if 'dictionary' in globals() and isinstance(dictionary, dict) and dictionary:
            pattern = re.compile("|".join(map(re.escape, dictionary.keys())))
            return pattern.sub(lambda match: dictionary[match.group(0)], text)
        else:
            return text
    except NameError:
        return text
    except Exception as e:
        k.log(f"Error during text cleaning with dictionary: {e}", xbmc.LOGERROR)
        return text


def traducao(text_id):
    try:
        return selfAddon.getLocalizedString(int(text_id)) or str(text_id)
    except ValueError:
        k.log(f"Invalid ID (not an int) passed to traducao: {text_id}", xbmc.LOGERROR)
        return f"InvalidID: {text_id}"
    except Exception as e:
        k.log(f"Error getting localized string for ID {text_id}: {e}", xbmc.LOGERROR)
        return f"UntranslatedID: {text_id}"


def init_user_refs():
    """Antes warm_up_connection(): hacía login + una petición en CADA invocación (también al reproducir).
    El calentamiento de sesión ahora lo hace service.py una sola vez al iniciar Kodi."""
    update_global_user_refs(get_active_account_details())
