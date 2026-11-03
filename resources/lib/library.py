# -*- coding: utf-8 -*-
"""Biblioteca de Kodi y generación de STRM (incremental)."""
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

from resources.lib.common import DIALOG_MESSAGE, MONITOR, MainURL, _get_db_connection, abrir_url_cookie, addon_id, clean, clean_folder, clean_title, get_active_account_details, notify, real_fs_name, real_title, returnValues, savefile, selfAddon, traducao, try_create_folder


class WalkIncomplete(Exception):
    """Lanzada cuando walk_folder_files no puede completar el recorrido de una carpeta o página."""
    pass


def add_to_library_opt(name_param, url_param):
    options = [traducao(40150), traducao(40151), traducao(40152)]
    mapping = {traducao(40150): "movie", traducao(40151): "tvshow", traducao(40152): "musicvideo"}
    dialog_title = traducao(40051)
    choose = DIALOG_MESSAGE.select(dialog_title, options)
    if choose > -1 and choose < len(options):
        selected_option = options[choose]
        content_type = mapping[selected_option]
        add_to_library(name_param, url_param, content_type, batch=False, updatelibrary=True)


def add_to_library_batch(updatelibrary=True):
     options = [traducao(40150), traducao(40151), traducao(40152)]
     mapping = {traducao(40150): "movie", traducao(40151): "tvshow", traducao(40152): "musicvideo"}
     dialog_title = f"{traducao(40051)} ({traducao(40133)})"
     choose = DIALOG_MESSAGE.select(dialog_title, options)
     if choose > -1 and choose < len(options): content_type = mapping[options[choose]]
     else: return

     conn, cursor = _get_db_connection()
     if not conn: return
     items_added = 0; items_failed = 0; total_items = 0
     progress = None
     try:
          cursor.execute("SELECT COUNT(*) FROM playlist"); total_items = cursor.fetchone()[0]
          if total_items == 0:
               notify(traducao(40134)); return
          cursor.execute("SELECT url, title FROM playlist"); playlist_entries = cursor.fetchall()
          progress = xbmcgui.DialogProgress()
          progress.create(traducao(40135), traducao(40136).format(total_items))
          for i, entry in enumerate(playlist_entries):
               url_item, title_item = entry
               if progress.iscanceled(): k.log("Batch add to library cancelled by user.", xbmc.LOGINFO); break
               clean_Title_item = real_title(title_item)
               progress.update(int(((i + 1) / total_items) * 100), f"{traducao(40025).split('...')[0]}: {clean_Title_item}")
               success = add_to_library(clean_Title_item, url_item, content_type, batch=True, updatelibrary=False)
               if success: items_added += 1
               else: items_failed += 1
          progress.close(); progress = None
          if not MONITOR.abortRequested():
              clear_playlist_db(); k.log("Cleared playlist table after batch add.", xbmc.LOGINFO)
          else: k.log("Playlist DB not cleared due to cancellation.", xbmc.LOGINFO)

          if not MONITOR.abortRequested() and updatelibrary:
               notify(traducao(40137), title=traducao(40138))
               xbmc.executebuiltin("UpdateLibrary(video)")

          result_msg = traducao(40139).format(items_added, total_items)
          if items_failed > 0: result_msg += traducao(40153).format(items_failed)
          if MONITOR.abortRequested(): result_msg = traducao(40154).format(result_msg)
          notify(result_msg)
     except sqlite3.Error as e:
          k.log(f"Database error during batch add: {e}", xbmc.LOGERROR)
          notify(traducao(40178).format(f"{traducao(40133)}: {e}"), error=True)
     except Exception as e:
          k.log(f"General error during batch add: {e}", xbmc.LOGERROR); traceback.print_exc()
          notify(traducao(40129).format(f"{traducao(40133)}: {e}"), error=True)
     finally:
          if progress: progress.close()
          if conn: conn.close()


def add_to_library(name_param, url_param, content_type, batch=False, updatelibrary=True):
    success = False; strm_path_final = ""
    try:
        title_cleaned = real_title(name_param)
        if not title_cleaned: k.log(f"Skipping library add due to empty cleaned title from '{name_param}'", xbmc.LOGWARNING); return False
        library_paths = {'movie': st.moviesFolder, 'tvshow': st.tvshowFolder, 'musicvideo': st.musicvideoFolder}
        base_folder = library_paths.get(content_type)
        if not base_folder: notify(traducao(40155).format(content_type), error=True); return False

        final_filename_base = title_cleaned; strm_folder = base_folder
        if content_type == "tvshow":
             pass; st.season_requested = False
             resolved_tvshow, resolved_season, resolved_episode = GetTVShowNameResolved(title_cleaned)
             if resolved_tvshow and resolved_season and resolved_episode:
                 tvshow_foldername = real_fs_name(resolved_tvshow)
                 strm_folder_tvshow = os.path.join(base_folder, tvshow_foldername)
                 if not try_create_folder(strm_folder_tvshow): return False

                 use_season_folders = selfAddon.getSetting("tvshowlibrary-enable") == "true"
                 filename_format = selfAddon.getSetting("tvshowfilename-format")

                 if use_season_folders:
                      season_folder_name = f"{traducao(40073)} {resolved_season.lstrip('0')}"
                      strm_folder = os.path.join(strm_folder_tvshow, season_folder_name)
                      if not try_create_folder(strm_folder): return False
                 else: strm_folder = strm_folder_tvshow

                 if filename_format == "showname.sXXeYY": final_filename_base = f"{tvshow_foldername} S{resolved_season}E{resolved_episode}"
                 elif filename_format == "sXXeYY.episodename": final_filename_base = f"S{resolved_season}E{resolved_episode} - {title_cleaned}"
                 else: final_filename_base = f"{tvshow_foldername} S{resolved_season}E{resolved_episode}"
             else:
                  k.log(f"Could not resolve TV Show S/E for: {title_cleaned}. Adding as file in TV base folder.", xbmc.LOGWARNING)
                  strm_folder = base_folder; final_filename_base = title_cleaned
        elif content_type == "movie":
             use_movie_folders = selfAddon.getSetting("movielibrary-enable") == "true"
             if use_movie_folders:
                  movie_foldername = real_fs_name(final_filename_base)
                  year_match = re.search(r'\((\d{4})\)', movie_foldername)
                  if year_match:
                       base_title_folder = re.sub(r'\s*\(\d{4}\)', '', movie_foldername).strip()
                       movie_foldername = f"{base_title_folder} ({year_match.group(1)})"
                  strm_folder = os.path.join(base_folder, movie_foldername)
                  if not try_create_folder(strm_folder): return False
             if selfAddon.getSetting("moviename-enable") == "false":
                  year_match_fn = re.search(r'\((\d{4})\)', final_filename_base)
                  if year_match_fn:
                       base_title_fn = re.sub(r'\s*\(\d{4}\)', '', final_filename_base).strip()
                       final_filename_base = f"{base_title_fn} ({year_match_fn.group(1)})"
        elif content_type == "musicvideo":
            strm_folder = base_folder
            final_filename_base = real_fs_name(final_filename_base)

        strm_content = f"plugin://{addon_id}/?url={urllib.parse.quote_plus(url_param)}&mode=25&name={urllib.parse.quote_plus(final_filename_base)}"
        strm_filename_safe = real_fs_name(final_filename_base)
        strm_filename = f"{strm_filename_safe}.strm"
        strm_path_final = os.path.join(strm_folder, strm_filename)
        k.log(f"Creating library file: {strm_path_final}", xbmc.LOGINFO)
        success = savefile(strm_filename, strm_content, pastafinal=strm_folder)

        if success and not batch and updatelibrary:
             notify(traducao(40137), title=traducao(40138))
             xbmc.executebuiltin("UpdateLibrary(video)")
        if not batch:
             if success: notify(traducao(40174).format(final_filename_base))
             else: notify(traducao(40175).format(final_filename_base), error=True)
    except Exception as e:
         k.log(f"Error adding item '{name_param}' to library: {e}", xbmc.LOGERROR); traceback.print_exc()
         if not batch: notify(traducao(40129).format(f"{traducao(40051)}: {e}"), error=True)
         success = False
    return success


def get_valid_season_input():
     dialog_title = traducao(12000)
     while True:
          season_input = DIALOG_MESSAGE.input(dialog_title, type=xbmcgui.INPUT_NUMERIC)
          if season_input and season_input.isdigit():
               num = int(season_input)
               if 0 < num < 100: return season_input.zfill(2)
               else: notify(traducao(40173), error=True)
          elif season_input is None or season_input == "": return None
          else: notify(traducao(12002), error=True)


def GetTVShowNameResolved(title):
    pass
    tvshow = ""; season = ""; episode = ""; year = ""
    cleaned_title = title

    patterns = [
        re.compile(r'^(.*?)(?:\s*[._\-\(\[\s]?)?(?:(\d{4})[._\-\)\]\s]*)?[\._\-\s\[]*(?:[Ss]eason\s*)?(\d{1,2})[\._\-\s]*[XxEePp\.]*(?:[Ee]pisode\s*)?(\d{1,3})(?:[\._\- ]*[EePp]?(\d{1,3}))?(?![-\d])', re.IGNORECASE),
        re.compile(r'^(.*?)(?:\s*[._\-\(\[\s]?)?(?:(\d{4})[._\-\)\]\s]*)?[\._\-\s]+(?<!\d)(\d{1})(\d{2})(?![0-9\.])', re.IGNORECASE),
        re.compile(r'^(.*?)(?:\s*[._\-\(\[\s]?)?(?:(\d{4})[._\-\)\]\s]*)?[\._\-\s]+(?<!\d)(\d{2})(\d{2})(?![0-9\.])', re.IGNORECASE),
        re.compile(r'^(.*?)(?:\s*[._\-\(\[\s]?)?(?:(\d{4})[._\-\)\]\s]*)?[\._\-\s]+(?:Part|Episode|Ep)[\._\-\s]*(\d{1,3})(?![-\d])', re.IGNORECASE),
    ]
    match_found = False
    for i, pattern in enumerate(patterns):
        match = pattern.search(cleaned_title)
        if match:
            groups = match.groups()
            temp_show = groups[0].strip()
            temp_show = re.sub(r'[._\-\s]+$', '', temp_show).strip()

            if i == 0:
                temp_year = groups[1] if groups[1] and len(groups[1]) == 4 else None
                temp_season = groups[2]
                temp_episode = groups[3]
                if groups[4]: temp_episode = groups[3]
                if temp_show and temp_season and temp_episode:
                     tvshow = temp_show; year = temp_year
                     season = temp_season.zfill(2); episode = temp_episode.zfill(2)
                     match_found = True; break
            elif i == 1:
                temp_year = groups[1] if groups[1] and len(groups[1]) == 4 else None
                temp_season = groups[2]; temp_episode = groups[3]
                if temp_show and temp_season and temp_episode and int(temp_season) > 0 and int(temp_episode) > 0:
                     tvshow = temp_show; year = temp_year
                     season = temp_season.zfill(2); episode = temp_episode.zfill(2)
                     match_found = True; break
            elif i == 2:
                temp_year = groups[1] if groups[1] and len(groups[1]) == 4 else None
                temp_season = groups[2]; temp_episode = groups[3]
                if temp_show and temp_season and temp_episode and int(temp_season) > 0 and int(temp_episode) > 0:
                     tvshow = temp_show; year = temp_year
                     season = temp_season.zfill(2); episode = temp_episode.zfill(2)
                     match_found = True; break
            elif i == 3:
                 temp_year = groups[1] if groups[1] and len(groups[1]) == 4 else None
                 temp_episode = groups[2]
                 if temp_show and temp_episode:
                      tvshow = temp_show; year = temp_year; episode = temp_episode.zfill(2)
                      if not st.season_requested:
                           season_input_val = get_valid_season_input()
                           if season_input_val:
                                st.season_var = season_input_val
                                season = st.season_var
                                st.season_requested = True
                                match_found = True; break
                           else: return "", "", ""
                      else:
                           season = st.season_var
                           match_found = True; break

    if match_found:
         if year and selfAddon.getSetting("tvshowyear-enable", "true") == "true":
              if not re.search(r'\(\s*' + re.escape(year) + r'\s*\)', tvshow):
                  tvshow = f"{tvshow} ({year})"
         return tvshow, season, episode
    else:
         return "", "", ""


def generate_strm_files_dialog(chomikuj_folder_url, folder_name_display):
    last_used_path = selfAddon.getSetting('strm_default_browse_path')
    default_start_path = ""

    if last_used_path and xbmcvfs.exists(last_used_path):
        try:
            stat_info = xbmcvfs.Stat(last_used_path)
            if stat.S_ISDIR(stat_info.st_mode()):
                default_start_path = last_used_path
            else:
                st.addon.log_warning(f"STRM Gen: Last used path '{last_used_path}' is not a directory. Ignoring.")
        except Exception as e:
            st.addon.log_warning(f"STRM Gen: Error stating last used path '{last_used_path}': {e}. Ignoring.")

    dialog_title = traducao(40161)
    k.log(f"STRM Gen: Opening folder selection dialog. Default attempt: '{default_start_path}'", xbmc.LOGINFO)

    selected_item_path = DIALOG_MESSAGE.browse(
        type=0,
        heading=dialog_title,
        shares="files",
        defaultt=default_start_path
    )
    k.log(f"STRM Gen: Path selected by user: '{selected_item_path}'", xbmc.LOGINFO)

    if selected_item_path:
        actual_output_folder = str(selected_item_path)

        if actual_output_folder.startswith(('smb://', 'nfs://', 'upnp://', 'ftp://')) and not actual_output_folder.endswith('/'):
            actual_output_folder += '/'
            k.log(f"STRM Gen: Added trailing slash to network path: {actual_output_folder}", xbmc.LOGINFO)

        if not xbmcvfs.exists(actual_output_folder):
            st.addon.log_info(f"STRM Gen: Base output folder '{actual_output_folder}' does not exist. Attempting to create with xbmcvfs.mkdirs().")
            if not xbmcvfs.mkdirs(actual_output_folder):
                notify(traducao(40163).format(actual_output_folder), error=True)
                st.addon.log_error(f"STRM Gen: xbmcvfs.mkdirs() failed to create base output folder '{actual_output_folder}'. Aborting.")
                return
            else:
                 st.addon.log_info(f"STRM Gen: Successfully created base output folder: {actual_output_folder}")
        else:
            try:
                stat_info = xbmcvfs.Stat(actual_output_folder)
                if not stat.S_ISDIR(stat_info.st_mode()):
                    notify(traducao(40158).format(actual_output_folder), error=True)
                    st.addon.log_error(f"STRM Gen: Base output path '{actual_output_folder}' exists but is not a directory. Aborting.")
                    return
                else:
                    st.addon.log_info(f"STRM Gen: Base output folder '{actual_output_folder}' exists and is a directory.")
            except Exception as stat_e:
                st.addon.log_error(f"STRM Gen: Error stating existing base path {actual_output_folder}: {stat_e}. Aborting.")
                notify(traducao(40159).format(stat_e), error=True); return

        selfAddon.setSetting('strm_default_browse_path', actual_output_folder)

        active_acc = get_active_account_details()
        if not active_acc or not active_acc.get('username'):
            notify(traducao(40225), error=True)
            return

        dialog_prog = None
        try:
            dialog_prog = xbmcgui.DialogProgressBG()
            dialog_prog.create(traducao(40164).format(folder_name_display), traducao(40165))
            create_strm_files_recursive_chomiteca(chomikuj_folder_url, actual_output_folder, dialog_prog)
        except Exception as e:
            k.log(f"STRM Gen: Error: {e}", xbmc.LOGERROR); traceback.print_exc(); notify(traducao(40129).format(f"STRM: {e}"), error=True)
        finally:
            if dialog_prog:
                try: dialog_prog.close()
                except: pass
    else:
        notify(traducao(40166))


def get_next_page_url_for_strm_gen(conteudo_text_param, current_page_url_param):
    sitebase_val, _, _, _ = returnValues(current_page_url_param)
    if not sitebase_val:
        try:
            parsed_uri = urlparse(current_page_url_param)
            sitebase_val = f"{parsed_uri.scheme}://{parsed_uri.netloc}"
            if not sitebase_val or sitebase_val == "://": return None
        except Exception: return None

    next_page_url_val = None
    try:
        next_page_match = re.search(r'<a[^>]+href=["\']/([^"\']+?)["\'][^>]*?(?:rel=["\']next["\']|(?:class|id)=["\'][^"\']*(?:next|right)[^"\']*["\'])[^>]*?>', conteudo_text_param, re.IGNORECASE)
        if next_page_match:
            urlpag_part_next_val = html.unescape(next_page_match.group(1))
            if not urlpag_part_next_val.startswith(('javascript:', '#')):
                next_page_url_val = sitebase_val.rstrip('/') + '/' + urlpag_part_next_val.lstrip('/')
    except Exception as e: k.log(f"STRM_GEN_PAGINATION: Error parsing next page link: {e}", xbmc.LOGERROR); traceback.print_exc()
    return next_page_url_val


def walk_folder_files(initial_url, progress_cb=None, include_folders=False):
    """Recorre una carpeta de Chomikuj (subcarpetas y páginas) y cede cada archivo:
    {'rel_dir','title','ext','url','file_id','size'}. Con include_folders=True cede también cada subcarpeta
    ({'is_dir': True,'rel_dir','title','url'}). Respeta el cierre de Kodi."""
    queue = [(initial_url, "")]
    seen_pages = set()
    while queue:
        if MONITOR.abortRequested(): return
        base_url, rel = queue.pop(0)
        page, first_page = base_url, True
        while page:
            if MONITOR.abortRequested() or page in seen_pages: break
            seen_pages.add(page)
            if progress_cb: progress_cb(rel, page)
            body = abrir_url_cookie(page, erro=False)  # sin caché: se quiere el estado real
            if not body: raise WalkIncomplete(page)
            text_page = clean(body.decode('utf-8', 'ignore'))
            sitebase, _, color, _ = returnValues(page)
            sitebase = sitebase or MainURL
            if first_page:
                folders_m = re.search(r'<div id="foldersList">(.*?)</table>', text_page, re.DOTALL | re.IGNORECASE)
                if folders_m:
                    for part, title_attr, name_html in re.findall(r'<a href="/([^"]+?)".*?title="([^"]+?)">(.*?)</a>', folders_m.group(1), re.DOTALL | re.IGNORECASE):
                        folder_name = html.unescape(re.sub('<[^>]+>', '', name_html)).strip() or html.unescape(title_attr).strip()
                        fs_name = real_fs_name(folder_name)  # nombre real de Chomikuj (con espacios, paréntesis, etc.)
                        if fs_name:
                            sub_url = sitebase.rstrip('/') + '/' + part.lstrip('/')
                            queue.append((sub_url, os.path.join(rel, fs_name)))
                            if include_folders:
                                yield {'is_dir': True, 'rel_dir': rel, 'title': real_title(folder_name), 'url': sub_url}
                first_page = False
            for _, item in ReturnConteudo(text_page, color, page, False, return_file_list=True) or []:
                if len(item) < 8: continue
                yield {'rel_dir': rel, 'title': item[1], 'ext': item[2], 'size': item[3], 'file_id': item[7],
                       'url': sitebase.rstrip('/') + '/' + item[4].lstrip('/')}
            nxt = get_next_page_url_for_strm_gen(text_page, page)
            page = nxt if nxt and nxt != page else None


def _ensure_dir(path):
    if xbmcvfs.exists(path): return True
    return bool(xbmcvfs.mkdirs(path))


def _write_text(path, text):
    fh = xbmcvfs.File(path, 'w')
    try: return bool(fh.write(text))
    finally: fh.close()


def _strm_basename(entry, normalize, used):
    """Nombre del .strm sin extensión. normalize: 'Título (Año)' / 'Serie - S01E02' (lo que reconocen los scrapers de Kodi)."""
    raw = f"{entry['title']}{entry['ext']}"
    base = real_fs_name(entry['title'])  # nombre real de Chomikuj sin extensión (.strm la añade)
    if normalize:
        info = metadata.parse(raw)
        if info['kind'] == 'episode' and info['title']:
            base = dq.safe_name(f"{info['title']} - S{info['season']:02d}E{info['episode']:02d}")  # sin clean_folder: conserva espacios
        elif info['kind'] == 'movie' and info['title']:
            base = dq.safe_name(f"{info['title']} ({info['year']})")
    candidate, n = base, 1
    while candidate.lower() in used:  # dos ficheros con el mismo SxxExx o título: no pisarse
        n += 1; candidate = f"{base} ({n})"
    used.add(candidate.lower())
    return candidate


def _nfo_for(entry):
    info = metadata.parse(f"{entry['title']}{entry['ext']}")
    if info['kind'] == 'episode':
        return ("episodedetails", f"<title>{_xml_escape(info['title'])}</title><showtitle>{_xml_escape(info['title'])}</showtitle>"
                                  f"<season>{info['season']}</season><episode>{info['episode']}</episode>")
    if info['kind'] == 'movie':
        return ("movie", f"<title>{_xml_escape(info['title'])}</title><year>{info['year']}</year>")
    return None


def create_strm_files_recursive_chomiteca(initial_chomikuj_url, base_output_dir, dialog_prog):
    """Genera STRM de forma incremental: no reescribe lo que no cambió, normaliza nombres y escribe .nfo (opcional)
    y puede eliminar los STRM cuyo origen desapareció."""
    normalize = selfAddon.getSetting('strm_normalize') == 'true'
    write_nfo = selfAddon.getSetting('strm_nfo') == 'true'
    prune = selfAddon.getSetting('strm_prune') == 'true'
    root_key = f"{initial_chomikuj_url}|{base_output_dir}"
    stats = {'new': 0, 'updated': 0, 'same': 0, 'removed': 0}
    seen_paths, used_names = set(), {}
    state = {'files': 0}

    def progress(rel, page):
        if not dialog_prog: return
        try:
            shown = rel or "/"
            if len(shown) > 40: shown = "..." + shown[-37:]
            dialog_prog.update(50, f"{traducao(30035)}: {shown}", f"STRM: {state['files']}")
        except Exception: pass

    try:
        with store.db() as c:
            indexed = dict(c.execute("SELECT path, url FROM strm_index WHERE root=?", (root_key,)).fetchall())
    except Exception as e:
        k.log(f"STRM index unavailable: {e}", xbmc.LOGWARNING); indexed = {}

    aborted = False
    complete = True
    try:
        for entry in walk_folder_files(initial_chomikuj_url, progress):
            if MONITOR.abortRequested(): aborted = True; break
            folder = os.path.join(base_output_dir, entry['rel_dir'])
            if not _ensure_dir(folder):
                k.log(f"STRM Gen: cannot create directory {folder}", xbmc.LOGWARNING); continue
            base = _strm_basename(entry, normalize, used_names.setdefault(folder, set()))
            if not base: continue
            path = os.path.join(folder, f"{base}.strm")
            content = f"plugin://{addon_id}/?url={urllib.parse.quote_plus(entry['url'])}&mode=25&name={urllib.parse.quote_plus(real_title(entry['title'] + entry['ext']))}"
            seen_paths.add(path)
            state['files'] += 1
            if indexed.get(path) == content and xbmcvfs.exists(path):
                stats['same'] += 1
            elif _write_text(path, content):
                stats['updated' if path in indexed else 'new'] += 1
                try:
                    with store.db() as c:
                        c.execute("INSERT OR REPLACE INTO strm_index(path, url, root, ts) VALUES (?,?,?,?)", (path, content, root_key, _time.time()))
                except Exception as e: k.log(f"STRM index write failed: {e}", xbmc.LOGWARNING)
            else:
                k.log(f"STRM Gen: failed to save {path}", xbmc.LOGWARNING); continue
            if write_nfo:
                nfo = _nfo_for(entry)
                nfo_path = os.path.join(folder, f"{base}.nfo")
                if nfo and not xbmcvfs.exists(nfo_path):
                    _write_text(nfo_path, f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n<{nfo[0]}>{nfo[1]}</{nfo[0]}>\n')
    except WalkIncomplete as exc:
        complete = False
        k.log("STRM: escaneo incompleto en página %s; se omite la poda" % exc, xbmc.LOGWARNING)

    if prune and complete and not aborted and not MONITOR.abortRequested() and len(seen_paths) >= 0.5 * len(indexed):
        for stale in [p for p in indexed if p not in seen_paths]:
            xbmcvfs.delete(stale)
            nfo_stale = os.path.splitext(stale)[0] + ".nfo"
            if xbmcvfs.exists(nfo_stale): xbmcvfs.delete(nfo_stale)
            stats['removed'] += 1
            try:
                with store.db() as c: c.execute("DELETE FROM strm_index WHERE path=?", (stale,))
            except Exception: pass
    elif prune:
        k.log("STRM: poda omitida (complete=%s, seen=%d, indexed=%d)" % (complete, len(seen_paths), len(indexed)), xbmc.LOGWARNING)

    summary = strings.t(40371).format(stats['new'], stats['updated'], stats['same'], stats['removed'])
    if dialog_prog:
        try:
            dialog_prog.update(100, traducao(40170) if aborted else traducao(40169), summary)
            xbmc.sleep(1200)
        except Exception: pass
    notify(summary)
    if selfAddon.getSetting('strm_update_library') == 'true' and (stats['new'] or stats['updated'] or stats['removed']):
        xbmc.executebuiltin('UpdateLibrary(video)')


# Importaciones entre módulos de funciones al final: así las referencias circulares son seguras
from resources.lib.listing import ReturnConteudo
from resources.lib.playlist import clear_playlist_db
