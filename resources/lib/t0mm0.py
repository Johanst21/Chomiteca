# -*- coding: utf-8 -*-
import traceback
import xbmc, xbmcaddon, xbmcgui, xbmcplugin, xbmcvfs
import re, os, unicodedata, socket, gzip, json
from io import BytesIO
import urllib.parse
from urllib.parse import urlencode, parse_qs, quote_plus
from urllib.request import Request, urlopen, build_opener, HTTPHandler, HTTPCookieProcessor, ProxyHandler, HTTPBasicAuthHandler
from urllib.error import URLError, HTTPError
from http.cookiejar import LWPCookieJar
import html
import xbmcvfs


class HeadRequest(Request):
    def get_method(self):
        return "HEAD"

class Net:
    _cj = LWPCookieJar()
    _proxy = None
    _user_agent = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0")
    _http_debug = False

    def __init__(self, cookie_file="", proxy="", user_agent="", http_debug=False):
        if cookie_file:
            self.load_cookies(cookie_file)
        if proxy:
            self.set_proxy(proxy)
        if user_agent:
            self.set_user_agent(user_agent)
        self._http_debug = http_debug
        self._opener = None
        self._update_opener()

    def load_cookies(self, cookie_file):
        try:
            self._cj.load(cookie_file, ignore_discard=True, ignore_expires=True)
            self._update_opener()
            xbmc.log(f"[Net] Loaded cookies from: {cookie_file}", xbmc.LOGDEBUG)
            return True
        except Exception as e:
            xbmc.log(f"[Net] Failed to load cookie file {cookie_file}: {e}", xbmc.LOGERROR)
            return False

    def get_cookies(self):
        return self._cj._cookies

    def save_cookies(self, cookie_file):
        try:
            self._cj.save(cookie_file, ignore_discard=True)
            xbmc.log(f"[Net] Saved cookies to: {cookie_file}", xbmc.LOGDEBUG)
        except Exception as e:
            xbmc.log(f"[Net] Failed to save cookie file {cookie_file}: {e}", xbmc.LOGERROR)

    def set_proxy(self, proxy):
        self._proxy = proxy
        self._update_opener()

    def get_proxy(self):
        return self._proxy

    def set_user_agent(self, user_agent):
        self._user_agent = user_agent

    def get_user_agent(self):
        return self._user_agent

    def _update_opener(self):
        handlers = []
        if self._http_debug:
             http_handler = HTTPHandler()
             xbmc.log("[Net] HTTP Debugging might not be fully enabled depending on Python version.", xbmc.LOGWARNING)
        else:
             http_handler = HTTPHandler()

        handlers.append(HTTPCookieProcessor(self._cj))
        handlers.append(HTTPBasicAuthHandler())
        handlers.append(http_handler)

        if self._proxy:
            try:
                 handlers.append(ProxyHandler({"http": self._proxy, "https": self._proxy}))
                 xbmc.log(f"[Net] Using proxy: {self._proxy}", xbmc.LOGDEBUG)
            except Exception as e:
                 xbmc.log(f"[Net] Invalid proxy format '{self._proxy}': {e}", xbmc.LOGERROR)

        self._opener = build_opener(*handlers)

    def _create_request(self, url, form_data=None, headers={}, method=None, compression=True):
         req_headers = {}
         req_headers["User-Agent"] = self._user_agent
         if compression:
             req_headers["Accept-Encoding"] = "gzip, deflate"
         req_headers.update(headers)

         encoded_data = None
         if form_data:
             try:
                 safe_form_data = {}
                 for k, v in form_data.items():
                      safe_form_data[k] = str(v) if not isinstance(v, (str, bytes)) else v
                 encoded_data = urlencode(safe_form_data).encode('utf-8')
             except Exception as enc_e:
                  xbmc.log(f"[Net] Failed to encode form data: {enc_e}", xbmc.LOGERROR)
                  raise ValueError("Invalid form data") from enc_e

         return Request(url, data=encoded_data, headers=req_headers, method=method)

    def http_GET(self, url, headers={}, compression=True, timeout=30):
        return self._fetch(url, headers=headers, compression=compression, timeout=timeout)

    def http_POST(self, url, form_data, headers={}, compression=True, timeout=30):
        return self._fetch(url, form_data=form_data, headers=headers, compression=compression, timeout=timeout)

    def http_HEAD(self, url, headers={}, timeout=15):
        req_headers = {'User-Agent': self._user_agent}
        req_headers.update(headers)
        req = HeadRequest(url, headers=req_headers)

        try:
            if not self._opener: self._update_opener()
            with self._opener.open(req, timeout=timeout) as response:
                 return HttpResponse(response)
        except Exception as e:
            xbmc.log(f"[Net] HEAD request failed for {url}: {e}", xbmc.LOGERROR)
            return None

    def _fetch(self, url, form_data=None, headers={}, compression=True, timeout=30):
        xbmc.log(f"[Net] Fetching URL: {url}{' (POST)' if form_data else ''}", xbmc.LOGDEBUG)
        try:
            request = self._create_request(url, form_data, headers, compression=compression)
        except ValueError as e:
             xbmc.log(f"[Net] Fetch failed due to request creation error: {e}", xbmc.LOGERROR)
             return None

        content_bytes = b""
        response = None
        try:
            if not self._opener: self._update_opener()
            with self._opener.open(request, timeout=timeout) as response:
                 content_bytes = response.read()
                 if response.info().get("content-encoding", "").lower() == "gzip":
                     xbmc.log("[Net] Decompressing gzip content.", xbmc.LOGDEBUG)
                     try:
                         content_bytes = gzip.GzipFile(fileobj=BytesIO(content_bytes)).read()
                     except Exception as gzip_e:
                         xbmc.log(f"[Net] Gzip decompression failed: {gzip_e}", xbmc.LOGERROR)
                         return HttpResponse(response, error=f"Gzip decompression failed: {gzip_e}")

                 elif response.info().get("content-encoding", "").lower() == "deflate":
                      xbmc.log("[Net] Decompressing deflate content (requires zlib).", xbmc.LOGDEBUG)
                      try:
                           import zlib
                           content_bytes = zlib.decompress(content_bytes)
                      except ImportError:
                           xbmc.log("[Net] zlib module not available for deflate decompression.", xbmc.LOGERROR)
                           return HttpResponse(response, error="zlib required for deflate")
                      except Exception as deflate_e:
                           xbmc.log(f"[Net] Deflate decompression failed: {deflate_e}", xbmc.LOGERROR)
                           return HttpResponse(response, error=f"Deflate decompression failed: {deflate_e}")


                 return HttpResponse(response, content_bytes=content_bytes)

        except HTTPError as e:
             xbmc.log(f"[Net] HTTP Error {e.code}: {e.reason} for URL: {url}", xbmc.LOGERROR)
             try: error_body = e.read()
             except: error_body = b''
             return HttpResponse(e, content_bytes=error_body, error=f"HTTP Error {e.code}: {e.reason}")
        except URLError as e:
             xbmc.log(f"[Net] URL Error: {e.reason} for URL: {url}", xbmc.LOGERROR)
             return HttpResponse(None, error=f"URL Error: {e.reason}")
        except Exception as e:
             xbmc.log(f"[Net] General Error fetching URL {url}: {e}", xbmc.LOGERROR)
             traceback.print_exc()
             return HttpResponse(None, error=f"General Error: {e}")


class HttpResponse:
    content = b""
    _text = None
    _response = None
    error = None

    def __init__(self, response, content_bytes=b"", error=None):
        self._response = response
        self.content = content_bytes
        self.error = error

    def _decode_content(self):
        if self.error:
             xbmc.log(f"[HttpResponse] Cannot decode content due to fetch error: {self.error}", xbmc.LOGWARNING)
             return f"<Error fetching content: {self.error}>"

        encoding = 'utf-8'
        try:
            if self._response and hasattr(self._response, 'headers'):
                 content_type = self._response.headers.get("content-type", "").lower()
                 if "charset=" in content_type:
                     encoding = content_type.split("charset=")[-1].strip()
                     xbmc.log(f"[HttpResponse] Encoding from header: {encoding}", xbmc.LOGDEBUG)

            try:
                 meta_match = re.search(b'<meta.*?charset=([^"\']+)["\']', self.content, re.IGNORECASE)
                 if meta_match:
                     meta_encoding = meta_match.group(1).decode('ascii', 'ignore').strip()
                     if meta_encoding and (encoding == 'utf-8' or not encoding):
                         encoding = meta_encoding
                         xbmc.log(f"[HttpResponse] Encoding from meta tag: {encoding}", xbmc.LOGDEBUG)
            except Exception as re_e:
                 xbmc.log(f"[HttpResponse] Regex error checking meta tag: {re_e}", xbmc.LOGWARNING)

            xbmc.log(f"[HttpResponse] Decoding content with '{encoding}'", xbmc.LOGDEBUG)

            try:
                 self._text = self.content.decode(encoding, errors='replace')
            except LookupError:
                 xbmc.log(f"[HttpResponse] Invalid encoding name '{encoding}', falling back to utf-8.", xbmc.LOGWARNING)
                 self._text = self.content.decode('utf-8', errors='replace')

        except Exception as decode_e:
             xbmc.log(f"[HttpResponse] Error during content decoding: {decode_e}", xbmc.LOGERROR)
             self._text = f"<Error decoding content: {decode_e}>"
             self.error = f"Decoding Error: {decode_e}"

        return self._text

    @property
    def text(self):
        if self._text is None:
            self._decode_content()
        return self._text

    def get_headers(self):
        if self._response and hasattr(self._response, 'headers'):
             return self._response.headers
        elif self._response and hasattr(self._response, 'info'):
             return self._response.info()
        return {}

    def get_url(self):
        if self._response and hasattr(self._response, 'geturl'):
             return self._response.geturl()
        return ""

    @property
    def code(self):
         if self._response and hasattr(self._response, 'code'):
              return self._response.code
         elif self._response and hasattr(self._response, 'status'):
              return self._response.status
         return 0


class Addon:
    def __init__(self, addon_id=None, argv=None):
        if addon_id:
             self.addon = xbmcaddon.Addon(id=addon_id)
        elif argv and len(argv) > 0:
             try:
                  plugin_url_parts = urllib.parse.urlparse(argv[0])
                  self.addon = xbmcaddon.Addon(id=plugin_url_parts.netloc)
             except Exception as e:
                  xbmc.log(f"[Addon] Could not determine addon ID from argv[0]='{argv[0]}': {e}. Use explicit addon_id.", xbmc.LOGERROR)
                  raise ValueError("Could not initialize Addon: ID unknown.") from e
        else:
             raise ValueError("Addon ID or argv required to initialize Addon class.")

        self.addon_id = self.get_id()
        self.handle = -1
        self.url = ""
        self.queries = {}

        if argv and len(argv) >= 3:
            self.url = argv[0]
            try:
                self.handle = int(argv[1])
            except ValueError:
                xbmc.log(f"[Addon:{self.addon_id}] Invalid handle provided: {argv[1]}", xbmc.LOGERROR)
                self.handle = -1
            if argv[2] and argv[2].startswith('?'):
                self.queries = self.parse_query(argv[2][1:])
            elif argv[2]:
                self.queries = self.parse_query(argv[2])


    def get_author(self): return self.addon.getAddonInfo("author")
    def get_changelog(self): return self.addon.getAddonInfo("changelog")
    def get_description(self): return self.addon.getAddonInfo("description")
    def get_disclaimer(self): return self.addon.getAddonInfo("disclaimer")
    def get_fanart(self): return self.addon.getAddonInfo("fanart")
    def get_icon(self): return self.addon.getAddonInfo("icon")
    def get_id(self): return self.addon.getAddonInfo("id")
    def get_name(self): return self.addon.getAddonInfo("name")
    def get_path(self): return xbmcvfs.translatePath(self.addon.getAddonInfo("path"))
    def get_profile(self): return xbmcvfs.translatePath(self.addon.getAddonInfo("profile"))
    def get_summary(self): return self.addon.getAddonInfo("summary")
    def get_version(self): return self.addon.getAddonInfo("version")
    def get_setting(self, setting_id): return self.addon.getSetting(setting_id)
    def get_string(self, string_id): return self.addon.getLocalizedString(int(string_id))

    def parse_query(self, query, defaults={}):
        parsed = parse_qs(query)
        q = defaults.copy()
        for key, value in parsed.items():
            if len(value) == 1:
                q[key] = value[0]
            else:
                q[key] = value
        return q

    def build_plugin_url(self, queries):
        base_url = f"plugin://{self.addon_id}/"
        safe_queries = {}
        for k, v in queries.items():
             if isinstance(v, bytes):
                  safe_queries[k] = v.decode('utf-8', 'ignore')
             elif not isinstance(v, str):
                  safe_queries[k] = str(v)
             else:
                  safe_queries[k] = v
        return base_url + "?" + urlencode(safe_queries)


    def log(self, msg, level=xbmc.LOGINFO):
        from resources.lib.kodiutils import redact
        log_msg = f"[{self.get_name()}] {redact(msg)}"
        xbmc.log(log_msg, level=level)

    def log_error(self, msg): self.log(msg, xbmc.LOGERROR)
    def log_warning(self, msg): self.log(msg, xbmc.LOGWARNING)
    def log_info(self, msg): self.log(msg, xbmc.LOGINFO)
    def log_debug(self, msg): self.log(msg, xbmc.LOGDEBUG)


    def show_ok_dialog(self, lines, title=None, is_error=False):
        if not title: title = self.get_name()
        if isinstance(lines, (str, bytes)): lines = [lines]
        processed_lines = []
        for line in lines:
            if isinstance(line, bytes):
                 processed_lines.append(line.decode('utf-8', 'replace'))
            else:
                 processed_lines.append(str(line))

        line1 = processed_lines[0] if len(processed_lines) > 0 else ""
        line2 = processed_lines[1] if len(processed_lines) > 1 else ""
        line3 = processed_lines[2] if len(processed_lines) > 2 else ""
        if len(processed_lines) > 3:
            line3 += " (...) " + " ".join(processed_lines[3:])

        log_msg = f"{title}: {line1} {line2} {line3}".strip()
        if is_error: self.log_error(log_msg)
        else: self.log_info(log_msg)

        xbmcgui.Dialog().ok(title, "\n".join(x for x in (line1, line2, line3) if x))

    def show_error_dialog(self, lines):
        self.show_ok_dialog(lines, title=f"Error - {self.get_name()}", is_error=True)

    def show_small_popup(self, title="", msg="", delay=5000, image=""):
        title_str = str(title)
        msg_str = str(msg)
        icon_path = self.get_icon()
        if image and isinstance(image, str) and os.path.exists(image):
            icon_path = image
        elif not os.path.exists(icon_path):
             icon_path = ""

        delay_ms = int(delay)

        xbmcgui.Dialog().notification(title_str, msg_str, icon_path or xbmcgui.NOTIFICATION_INFO, int(delay_ms))

    def show_countdown(self, time_to_wait, title="", text=""):
        dialog = xbmcgui.DialogProgress()
        try:
            title_str = str(title) if title else self.get_name()
            text_str = str(text)

            dialog.create(title_str)
            self.log_info(f"Countdown started: waiting {time_to_wait} seconds")

            secs = 0
            increment = 100.0 / time_to_wait if time_to_wait > 0 else 100.0

            cancelled = False
            while secs <= time_to_wait:
                if dialog.iscanceled():
                    cancelled = True
                    break

                secs_left = time_to_wait - secs
                percent = int(min(increment * secs, 100))

                remaining_display = f"Waiting: {secs_left} seconds remaining..."
                dialog.update(percent, f"{text_str}\n{remaining_display}")

                if secs_left <= 0: break

                xbmc.sleep(1000)
                secs += 1

            if cancelled:
                self.log_info("Countdown cancelled by user.")
                return False
            else:
                self.log_info("Countdown finished.")
                return True
        except Exception as e:
             self.log_error(f"Error during countdown: {e}")
             return False
        finally:
             if dialog: dialog.close()


    def show_settings(self): self.addon.openSettings()

    def resolve_url(self, stream_url):
        if self.handle < 0:
             self.log_error("Cannot resolve URL: Invalid plugin handle.")
             return False

        if stream_url:
            self.log_info(f"Resolved URL: {stream_url}")
            listitem = xbmcgui.ListItem(path=stream_url)
            xbmcplugin.setResolvedUrl(self.handle, True, listitem)
            return True
        else:
            self.log_error("Failed to resolve URL (URL was empty or None).")
            self.show_error_dialog(["Sorry, failed to resolve URL."])
            xbmcplugin.setResolvedUrl(self.handle, False, xbmcgui.ListItem())
            return False


    def get_playlist(self, pl_type, new=False):
        if pl_type not in [xbmc.PLAYLIST_MUSIC, xbmc.PLAYLIST_VIDEO]:
             self.log_error(f"Invalid playlist type requested: {pl_type}")
             return None
        playlist = xbmc.PlayList(pl_type)
        if new:
            playlist.clear()
        return playlist

    def get_music_playlist(self, new=False): return self.get_playlist(xbmc.PLAYLIST_MUSIC, new)
    def get_video_playlist(self, new=False): return self.get_playlist(xbmc.PLAYLIST_VIDEO, new)


    def add_item(self, queries={}, infolabels={}, contextmenu_items=[], context_replace=False, img="", fanart="", resolved_url=None, total_items=0, playlist=None, item_type="video", is_folder=False):
        if self.handle < 0 and playlist is None:
             self.log_error("Cannot add item: Invalid plugin handle and no playlist provided.")
             return

        title = str(infolabels.get("title", "Untitled Item"))

        if resolved_url:
            play_url = resolved_url
        else:
             play_url = self.build_plugin_url(queries)


        listitem = xbmcgui.ListItem(label=title)

        safe_infolabels = {k: str(v) for k, v in infolabels.items() if v is not None}
        if "mediatype" not in safe_infolabels:
            if is_folder: safe_infolabels["mediatype"] = "folder"
            elif item_type == "video": safe_infolabels["mediatype"] = "video"
            elif item_type == "music": safe_infolabels["mediatype"] = "song"
        try:
            tag = listitem.getMusicInfoTag() if item_type == "music" else listitem.getVideoInfoTag()
            tag.setTitle(title)
        except Exception as tag_e:
            xbmc.log(f"[Net] InfoTag no disponible: {tag_e}", xbmc.LOGWARNING)

        art_dict = {}
        if img:
             art_dict['icon'] = img
             art_dict['thumb'] = img
        fanart_path = fanart if fanart else self.get_fanart()
        if fanart_path and not os.path.isabs(fanart_path):
             addon_path_root = self.get_path()
             potential_fanart_path = os.path.join(addon_path_root, fanart_path)
             if os.path.exists(potential_fanart_path):
                  fanart_path = potential_fanart_path
             else:
                  full_info_fanart = self.addon.getAddonInfo("fanart")
                  if os.path.exists(full_info_fanart): fanart_path = full_info_fanart
                  else: fanart_path = ""

        if fanart_path: art_dict['fanart'] = fanart_path
        listitem.setArt(art_dict)

        if not is_folder:
             listitem.setProperty('IsPlayable', 'true')

        if contextmenu_items:
             listitem.addContextMenuItems(contextmenu_items, replaceItems=context_replace)

        if playlist is not None:
             self.log_debug(f"Adding item to playlist: '{title}' - URL: {play_url}")
             playlist.add(play_url, listitem)
        elif self.handle >= 0:
             self.log_debug(f"Adding directory item: '{title}' - URL: {play_url} Folder: {is_folder}")
             xbmcplugin.addDirectoryItem(self.handle, play_url, listitem, isFolder=is_folder)


    def add_video_item(self, queries={}, infolabels={}, contextmenu_items=[], context_replace=False, img="", fanart="", resolved_url=None, total_items=0, playlist=None):
        self.add_item(queries,infolabels,contextmenu_items,context_replace,img,fanart,resolved_url,total_items,playlist,item_type="video", is_folder=False)

    def add_music_item(self, queries={}, infolabels={}, contextmenu_items=[], context_replace=False, img="", fanart="", resolved_url=None, total_items=0, playlist=None):
        self.add_item(queries, infolabels, contextmenu_items, context_replace, img, fanart, resolved_url, total_items, playlist, item_type="music", is_folder=False)

    def add_directory(self, queries={}, infolabels={}, contextmenu_items=[], context_replace=False, img="", fanart="", total_items=0, is_folder=True):
        plugin_url = self.build_plugin_url(queries)
        self.add_item(queries, infolabels, contextmenu_items, context_replace, img, fanart, resolved_url=plugin_url, total_items=total_items, item_type="video", is_folder=is_folder)


    def end_of_directory(self, succeeded=True, update_listing=False, cache_to_disc=True):
        if self.handle >= 0:
             xbmcplugin.endOfDirectory(self.handle, succeeded=succeeded, updateListing=update_listing, cacheToDisc=cache_to_disc)
             self.log_debug(f"Ended directory listing (handle {self.handle}).")
        else:
             self.log_warning("Tried to end directory listing but handle is invalid.")


    def _decode_html_entities_callback(self, matches):
        entity_code = matches.group(1)
        try:
            if entity_code.startswith('x'):
                 return chr(int(entity_code[1:], 16))
            else:
                 return chr(int(entity_code))
        except ValueError:
            return matches.group(0)


    def decode_html_entities(self, data):
        if not isinstance(data, str): return data
        try:
            return re.sub(r"&#(x?[0-9a-fA-F]+);?", self._decode_html_entities_callback, data)
        except Exception as e:
            self.log_warning(f"Error decoding HTML entities: {e}")
            return data

    def unescape(self, text):
        if not isinstance(text, str): return text
        try:
            text = html.unescape(text)
        except Exception as e:
            self.log_warning(f"Error during HTML unescape: {e}")
            pass
        return text


    def unescape_dict(self, d):
        out = {}
        for key, value in d.items():
            if isinstance(value, str):
                out[key] = self.unescape(value)
            elif isinstance(value, list):
                 out[key] = [self.unescape(item) if isinstance(item, str) else item for item in value]
            elif isinstance(value, dict):
                 out[key] = self.unescape_dict(value)
            else:
                out[key] = value
        return out


    def save_data(self, filename, data):
        profile_path = self.get_profile()
        if not profile_path:
            self.log_error("Cannot save data: Addon profile path not found.")
            return False
        try:
             if not os.path.isdir(profile_path):
                  os.makedirs(profile_path)
                  self.log_info(f"Created addon profile directory: {profile_path}")
        except OSError as e:
             self.log_error(f"Failed to create profile directory {profile_path}: {e}")
             return False

        save_path = os.path.join(profile_path, filename)
        try:
            with open(save_path, "wb") as f:
                f.write(json.dumps(data).encode("utf-8"))
            self.log_debug(f"Saved data to: {save_path}")
            return True
        except Exception as e:
            self.log_error(f"Failed to save data to {save_path}: {e}")
            traceback.print_exc()
            return False


    def load_data(self, filename, default=None):
        profile_path = self.get_profile()
        if not profile_path:
             self.log_error("Cannot load data: Addon profile path not found.")
             return default

        load_path = os.path.join(profile_path, filename)
        if not os.path.isfile(load_path):
            self.log_debug(f"Data file not found: {load_path}")
            return default

        try:
            with open(load_path, "rb") as f:
                data = json.loads(f.read().decode("utf-8"))
            self.log_debug(f"Loaded data from: {load_path}")
            return data
        except (ValueError, EOFError) as e:
            self.log_error(f"Invalid data file {load_path}: {e}. Ignoring.")
        except Exception as e:
            self.log_error(f"Failed to load data from {load_path}: {e}")
            traceback.print_exc()

        return default
