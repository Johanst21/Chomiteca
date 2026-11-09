# -*- coding: utf-8 -*-
"""Menús y listado de carpetas de Chomikuj (paginación, precarga)."""
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

from resources.lib.common import DIALOG_MESSAGE, GetThumbExt, MODE_DELETE_COOKIES, MODE_MANAGE_ACCOUNTS, MODE_SETTINGS, MainURL, VIDEO_EXTS_UI, abrir_url_cookie, art, caixadetexto, clean, clean_title, cookies, get_active_account_details, login, nameURL, net, notify, returnExtra, returnValues, selfAddon, traducao, user_agent, wtpath
from resources.lib.ui import addCont, addDir, addLink, end_directory


_PAGINATION_HREF_RE = re.compile(
    r'href=["\'](?:https?://[^/"\']+)?(/[^"\']+?)["\']'
)


def _is_pagination_link(anchor_html, kind):
    """Return True if anchor_html looks like a pagination link of `kind` ('prev' or 'next').

    Matches the pre-F27 regex behavior (class OR rel, case-insensitive, substring match)
    plus absolute URL support via _PAGINATION_HREF_RE.
    """
    href_match = _PAGINATION_HREF_RE.search(anchor_html)
    if not href_match:
        return False

    class_match = re.search(r'(?:class|id)=["\']([^"\']+)["\']', anchor_html, re.IGNORECASE)
    class_val = class_match.group(1).lower() if class_match else ""

    rel_match = re.search(r'rel=["\']([^"\']+)["\']', anchor_html, re.IGNORECASE)
    rel_val = rel_match.group(1).lower() if rel_match else ""

    if kind == "prev":
        if "prev" in class_val or "previous" in class_val or "left" in class_val:
            return True
        if rel_val in ("prev", "previous"):
            return True
        return False
    else:  # next
        if "next" in class_val or "right" in class_val:
            return True
        if rel_val == "next":
            return True
        return False


def menu_principal(_):
    active_account = get_active_account_details()
    display_label_for_menu = "N/A"
    chomik_user_for_url = ""

    if active_account:
        display_label_for_menu = active_account.get('label', active_account.get('username', "N/A"))
        chomik_user_for_url = active_account.get('username', '')
    is_logged_in = bool(active_account and os.path.exists(cookies))

    addDir(traducao(40080),
           "manage_accounts_action",
           MODE_MANAGE_ACCOUNTS,
           os.path.join(wtpath, art[1:], "account.png"),
           0,
           False)

    if is_logged_in and chomik_user_for_url:
        quoted_user_url_part = urllib.parse.quote(chomik_user_for_url)
        my_prefix = traducao(40009)
        my_chomikuj_display_label = f"{my_prefix.strip()} {nameURL}: {display_label_for_menu}"
        addDir(my_chomikuj_display_label, MainURL + quoted_user_url_part, 3, os.path.join(wtpath, art[1:], "my.png"), 0, True)

    addDir(traducao(40054), MainURL, 18, os.path.join(wtpath, art[1:], "attach.png"), 0, True)
    addDir(traducao(40011), "search", 7, os.path.join(wtpath, art[1:], "search.png"), 0, True)
    addDir(strings.t(40300), "downloads", 50, os.path.join(wtpath, art[1:], "attach.png"), 0, True)
    addDir(strings.t(40401), "settings", MODE_SETTINGS, os.path.join(wtpath, art[1:], 'defs.png'), 0, False)
    addDir(strings.t(40301), "diagnostics", 54, os.path.join(wtpath, art[1:], "defs.png"), 0, False)  # Prueba de conexión (penúltimo)

    if os.path.exists(cookies):
        addDir(traducao(40081), "delete_cookies_action", MODE_DELETE_COOKIES, os.path.join(wtpath, art[1:], "delCookies.png"), 0, False)


def topcolecionadores():
    active_account = get_active_account_details()
    if not active_account or not active_account.get('username'):
         notify(traducao(40225), error=True)
         return

    current_username_url_part = urllib.parse.quote(active_account['username'])
    label_to_use = active_account.get('label', nameURL)

    if not login(True):
         notify(traducao(40190), error=True)
         return

    page_url = MainURL + current_username_url_part
    k.log(f"Fetching top collectors from: {page_url}", xbmc.LOGINFO)

    conteudo_bytes = abrir_url_cookie(page_url)
    if not conteudo_bytes:
        notify(traducao(40191), error=True)
        return

    conteudo_text = clean(conteudo_bytes.decode('utf-8', 'ignore'))
    collectors_section_match = re.search(r'<ul class="friendsList">(.*?)</ul>', conteudo_text, re.DOTALL | re.IGNORECASE)
    if not collectors_section_match:
         k.log("Could not find collectors list section in HTML.", xbmc.LOGWARNING)
         notify(traducao(40192), error=True)
         return

    collectors_html = collectors_section_match.group(1)
    users = re.findall(r'<li.*?><div class="friend avatar">.*?<a href="/([^"]+?)" title="([^"]+?)">.*?<img.*?src="([^"]+?)".*?>.*?</a>.*?<i>(\d+)</i>.*?</li>', collectors_html, re.DOTALL | re.IGNORECASE)
    if not users:
         k.log("No users found within the collectors list HTML.", xbmc.LOGINFO)
         notify(traducao(40193), error=True)
         return

    total_users = len(users)
    all_users_data = []
    for urluser, nomeuser, thumbuser, nruser in users:
        if not thumbuser.startswith(('http:', 'https:')):
            thumbuser = "https:" + thumbuser if thumbuser.startswith('//') else MainURL.rstrip('/') + thumbuser
        display_name = f'{nruser}º {label_to_use} {html.unescape(nomeuser)}'
        user_profile_url = MainURL.rstrip('/') + '/' + urluser.lstrip('/')
        all_users_data.append((display_name, user_profile_url, thumbuser))
    for user_data in all_users_data:
        addDir(user_data[0], user_data[1], 3, user_data[2], total_users, True)


def pastas(url, name, formcont={}, conteudo=b'', past=False, deFora=False, listagem=False):
    MainPlayList = []
    uniqueList = []
    conteudo_text = ''
    is_search_mode = re.search('/action/SearchFiles', url) or re.search('/action/nada', url)
    is_special_foldertype_search = st.foldertype == 1 and is_search_mode and not deFora
    selectlist = []
    urllist = []
    sitebase, _, color, _ = returnValues(url)
    if not sitebase:
        notify(traducao(40127).format(url), error=True)
        return
    host = sitebase.replace('https://', '').replace('/', '')
    metadata.parent_name = html.unescape(re.sub(r'\[/?[A-Za-z]+[^\]]*\]', '', name or ''))  # carpeta que se lista: da contexto a las carpetas de temporada

    if is_search_mode and not conteudo:
        if not formcont or 'FileName' not in formcont:
            k.log("Search action called without search term (FileName).", xbmc.LOGWARNING)
            notify(traducao(40181), error=True)
            return
        k.log(f"Performing search with terms: {formcont.get('FileName', '')}", xbmc.LOGINFO)
        ref_data_search = {'Host': host, 'Connection': 'keep-alive', 'Referer': f'https://{host}/', 'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8', 'User-Agent': user_agent}
        search_post_url = sitebase + '/action/SearchFiles'
        try:
             response_search_container = net.http_POST(search_post_url, form_data=formcont, headers=ref_data_search)
             conteudo_container_bytes = response_search_container.content
             if not conteudo_container_bytes:
                 raise ValueError("Received empty container page for search.")
             conteudo_container_text = conteudo_container_bytes.decode('utf-8','ignore')
             k.log(f"Search container page status: {response_search_container.code}", xbmc.LOGDEBUG)
             filename_m = re.search(r'name="FileName".*?value="([^"]+)"', conteudo_container_text)
             ftype_m = re.search(r'name="FileType".*?value="([^"]+)"', conteudo_container_text)
             token_m = re.search(r'name="__RequestVerificationToken".*?value="([^"]+)"', conteudo_container_text)
             if not (filename_m and token_m):
                 raise ValueError("Missing FileName or Token for search results AJAX call.")
             filename = filename_m.group(1)
             ftype = ftype_m.group(1) if ftype_m else formcont.get('FileType', 'All')
             token = token_m.group(1)
             pagina = 1
             form_d_ajax = {'IsGallery': 'False', 'FileName': filename, 'FileType': ftype, 'ShowAdultContent': 'True', 'Page': pagina, '__RequestVerificationToken': token}
             if selfAddon.getSetting('activate-size') == 'true':
                 form_d_ajax['SizeFrom'] = selfAddon.getSetting('min-size')
                 form_d_ajax['SizeTo'] = selfAddon.getSetting('max-size')
             st.addon.save_data('temp.txt', form_d_ajax)
             ref_data_ajax = {'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded', 'Host': host, 'Origin': sitebase, 'Referer': url, 'User-Agent': user_agent, 'X-Requested-With': 'XMLHttpRequest'}
             ajax_results_url = sitebase + '/action/SearchFiles'
             k.log(f"Fetching search results page 1 via AJAX.", xbmc.LOGDEBUG)
             response_ajax = net.http_POST(ajax_results_url, form_data=form_d_ajax, headers=ref_data_ajax)
             conteudo = response_ajax.content
             if not conteudo:
                 k.log("Received empty content for first page of search results.", xbmc.LOGWARNING)
                 notify(traducao(40188), error=True)
                 return
             k.log(f"Search results AJAX status: {response_ajax.code}", xbmc.LOGDEBUG)
        except Exception as e:
            k.log(f"Error during search request or parameter extraction: {e}", xbmc.LOGERROR)
            traceback.print_exc()
            notify(traducao(40182).format(e), error=True)
            return
    elif not conteudo:
        extra = returnExtra()
        folder_url = url + extra
        k.log(f"Fetching folder content: {folder_url}", xbmc.LOGINFO)
        conteudo_bytes = abrir_url_cookie(folder_url, cache=True)
        if not conteudo_bytes:
            k.log(f"Failed to open URL: {folder_url}", xbmc.LOGERROR)
            k.log(f"Retrying fetch without extras: {url}", xbmc.LOGINFO)
            conteudo_bytes = abrir_url_cookie(url)
            if not conteudo_bytes:
                 notify(traducao(40183), error=True)
                 return
        conteudo = conteudo_bytes

    if not isinstance(conteudo, bytes):
         k.log("Content provided to pastas() is not bytes, attempting encode.", xbmc.LOGWARNING)
         try:
              conteudo = str(conteudo).encode('utf-8')
         except Exception as enc_e:
              k.log(f"Failed to encode content to bytes: {enc_e}", xbmc.LOGERROR)
              notify(traducao(40184), error=True)
              return
    try:
        conteudo_text = clean(conteudo.decode('utf-8', 'ignore'))
    except Exception as dec_e:
        k.log(f"Failed to decode or clean content: {dec_e}", xbmc.LOGERROR)
        notify(traducao(40185), error=True)
        return

    if 'ProtectedFolderChomikLogin' in conteudo_text:
        k.log("Protected folder detected.", xbmc.LOGINFO)
        chomikid_m = re.search(r'id="ChomikId".*?value="([^"]+)"', conteudo_text)
        folderid_m = re.search(r'id="FolderId".*?value="([^"]+)"', conteudo_text)
        foldername_m = re.search(r'id="FolderName".*?value="([^"]+)"', conteudo_text)
        token_m = re.search(r'name="__RequestVerificationToken".*?value="([^"]+)"', conteudo_text)
        if not (chomikid_m and folderid_m and foldername_m and token_m):
            k.log("Could not find all elements for password protected folder.", xbmc.LOGERROR)
            notify(traducao(40186), error=True)
            return
        chomikid, folderid, foldername, token = chomikid_m.group(1), folderid_m.group(1), foldername_m.group(1), token_m.group(1)
        passwordfolder = caixadetexto('password')
        if passwordfolder is None: return
        form_d_pass = {'ChomikId': chomikid, 'FolderId': folderid, 'FolderName': foldername, 'Password': passwordfolder, 'Remember': 'true', '__RequestVerificationToken': token}
        ref_data_pass = {'Accept': '*/*', 'Content-Type': 'application/x-www-form-urlencoded', 'Host': host, 'Origin': sitebase, 'Referer': url, 'User-Agent': user_agent, 'X-Requested-With': 'XMLHttpRequest'}
        pass_submit_url = sitebase + '/action/Files/LoginToFolder'
        k.log("Submitting password for protected folder.", xbmc.LOGDEBUG)
        try:
            teste_bytes = net.http_POST(pass_submit_url, form_data=form_d_pass, headers=ref_data_pass).content
            if not teste_bytes:
                raise ValueError("Empty response after password submission.")
            teste_text = urllib.parse.unquote(teste_bytes.decode('utf-8', 'ignore'))
            if '"IsSuccess":false' in teste_text or '"IsValid":false' in teste_text:
                error_msg = traducao(40002)
                error_m = re.search(r'"Errors":\["([^"]+)"\]', teste_text)
                if error_m: error_msg = error_m.group(1)
                notify(f"{traducao(40129).split(':')[0]}: {error_msg}", error=True)
                return
            else:
                k.log("Password accepted, reloading folder content.", xbmc.LOGINFO)
                cache_mod.invalidate(url)
                xbmc.executebuiltin("Container.Refresh")
        except Exception as pass_e:
             k.log(f"Error submitting folder password: {pass_e}", xbmc.LOGERROR)
             notify(traducao(40187).format(pass_e), error=True)
        return
    else:
        if not deFora:
            try:
                conta_match = re.search(r'<div class="fileInfoFrame.*?<span class="bold">([^<]+?)</span>\s+<span class="bold">([^<]+?)</span>\s+([^<]+?)</p>', conteudo_text)
                nomeconta_match = re.search(r'id="FriendsTargetChomikName".*?value="([^"]+)"', conteudo_text)
                if conta_match and nomeconta_match:
                    _, conta_val, conta_unit = conta_match.groups()
                    nomeconta = html.unescape(nomeconta_match.group(1))
                    size_display = f"{conta_val.strip()} {conta_unit.strip()}"
                    addLink(f'{traducao(40023)}{nomeconta}: {size_display}', '', os.path.join(wtpath, art[1:], 'user.png'))
            except Exception as e:
                k.log(f"Could not parse account info: {e}", xbmc.LOGINFO)

        if not deFora and not is_search_mode and url != MainURL and url.strip('/') != MainURL.strip('/'):
            try:
                parent_url = '/'.join(url.rstrip('/').split('/')[:-1])
                if parent_url and parent_url != MainURL.rstrip('/'):
                    if parent_url.startswith(MainURL) and len(parent_url) > len(MainURL.rstrip('/')):
                         addDir(f".. [COLOR gray]({traducao(40111)})[/COLOR]", parent_url, 3, "DefaultFolderBack.png", 0, True)
                    elif not parent_url.startswith(MainURL) and parent_url:
                         addDir(f".. [COLOR gray]({traducao(40111)})[/COLOR]", parent_url, 3, "DefaultFolderBack.png", 0, True)
            except Exception as e:
                k.log(f"Error creating parent folder link: {e}", xbmc.LOGINFO)

        try:
            pastas_match = re.search(r'<div id="foldersList">(.*?)</table>', conteudo_text, re.DOTALL | re.IGNORECASE)
            if pastas_match:
                 folder_html = pastas_match.group(1)
                 seleccionados = re.findall(r'<a href="/([^"]+?)".*?title="([^"]+?)">(.*?)</a>', folder_html, re.DOTALL | re.IGNORECASE)
                 total_folders = len(seleccionados)
                 if not listagem and not is_search_mode:
                     metadata.prefetch_folders([html.unescape(re.sub('<[^>]+>', '', n_html)).strip() or html.unescape(n_title) for _u, n_title, n_html in seleccionados], metadata.parent_name)
                 for urlpasta_part, nomepasta_title, nomepasta_html in seleccionados:
                     nomepasta_clean = html.unescape(re.sub('<[^>]+>', '', nomepasta_html)).strip()
                     nomepasta = nomepasta_clean if nomepasta_clean else html.unescape(nomepasta_title)
                     displock = ' [COLOR red](' + traducao(40024) + ')[/COLOR]' if '<span class="pass">' in nomepasta_html else ''
                     translations_map = {
                         'Dokumenty': traducao(40057), 'Documentos': traducao(40057),
                         'Galeria': traducao(40058),
                         'Prywatne': traducao(40059), 'Privada': traducao(40059)
                     }
                     nomepasta_display = translations_map.get(nomepasta, nomepasta)
                     folder_url = sitebase.rstrip('/') + '/' + urlpasta_part.lstrip('/')
                     addDir(f'{nomepasta_display}{displock}', folder_url, 3, os.path.join(wtpath, art[1:], 'folder.png'), total_folders, True)
        except Exception as e:
            k.log(f"Error parsing folders: {e}", xbmc.LOGERROR)
            traceback.print_exc()

        if not is_search_mode:
             k.log("Clearing temporary playlist DB before listing folder contents.", xbmc.LOGINFO)
             clear_playlist_db()
        reslist = []
        if not listagem: metadata_prefetch_from_html(conteudo_text)
        try:
             reslist = ReturnConteudo(conteudo_text, color, url, deFora, return_file_list=listagem)
        except Exception as e:
             k.log(f"Error processing files via ReturnConteudo: {e}", xbmc.LOGERROR)
             traceback.print_exc()

        if listagem:
            return reslist

        if reslist:
            if deFora or is_search_mode:
                 try:
                      reslist = _sort_search_results(reslist)
                 except Exception as sort_e:
                      k.log(f"Sorting results failed: {sort_e}", xbmc.LOGWARNING)
            total_items_res = len(reslist)
            for size_info, item_data in reslist:
                if is_special_foldertype_search:
                    if len(item_data) == 2:
                         label, item_url = item_data
                         unique_key = item_url
                         if unique_key not in uniqueList:
                             uniqueList.append(unique_key)
                             selectlist.append(label)
                             urllist.append(item_url)
                else:
                    if len(item_data) >= 7:
                         color_val, title, ext, size_str, url_part, mode_item, thumb = item_data[:7]
                         unique_key = url_part
                         if unique_key not in uniqueList:
                             uniqueList.append(unique_key)
                             full_item_url = sitebase.rstrip('/') + '/' + url_part.lstrip('/')
                             if ext.lower() in ['.mkv', '.avi', '.mp4', '.mp3', '.flac', '.m4a', '.wmv', '.mov', '.wav', '.ogg']:
                                 clean_title_for_playlist = clean_title(f"{title}{ext}")
                                 MainPlayList.append([clean_title_for_playlist, full_item_url])
                             display_name = f'{title}{ext} [COLOR white]{size_str}[/COLOR]'
                             addCont(display_name, full_item_url, 4, size_str, thumb, total_items_res)

            if is_special_foldertype_search:
                 if selectlist:
                     choose = DIALOG_MESSAGE.select(traducao(40048), selectlist)
                     if choose > -1 and choose < len(urllist):
                          analyzer(urllist[choose])
                          end_directory()
                          return
                     else:
                          end_directory()
                          return
                 else:
                      notify(traducao(40189))
                      end_directory()
                      return
            if MainPlayList:
                 added_count = add_items_to_playlist_db(MainPlayList)
                 k.log(f"Saved {added_count} items to temporary playlist DB.", xbmc.LOGINFO)
        if not deFora and not is_special_foldertype_search:
            paginas(conteudo_text)
            if not is_search_mode: prefetch_next_page(conteudo_text, url)


def ReturnConteudo(conteudo_text_param, color_param, url2_param, deFora_param, return_file_list=False):
    reslist_local = []
    file_blocks_local = []
    list_view_pattern = r'<div id="listView".*?>(.*?)<div class="smallBL" id="selectedFilesActionButtons">'
    list_view_match = re.search(list_view_pattern, conteudo_text_param, re.DOTALL | re.IGNORECASE)

    if list_view_match:
        list_html = list_view_match.group(1)
        file_block_pattern = r'(<div class="filerow(?: alt)? fileItemContainer">.*?<div class="clear">\s*</div>)'
        try:
            file_blocks_local = re.findall(file_block_pattern, list_html, re.DOTALL | re.IGNORECASE)
        except Exception as findall_error:
            file_blocks_local = []
            k.log(f"ERROR during re.findall for file_blocks: {findall_error}", xbmc.LOGERROR)
    else:
        file_blocks_local = []

    for part_item in file_blocks_local:
        link_title_pattern = r'<a[^>]*?class="expanderHeader[^"]*?"[^>]*?href="(?:https?://[^/"]+)?/([^"]+)"[^>]*?title="([^"]+)"'
        match_item = re.search(link_title_pattern, part_item, re.DOTALL | re.IGNORECASE)

        if match_item:
            url_part_match_item = match_item.group(1).strip()
            title_html_item = match_item.group(2).strip()
            try:
                title_from_html_item = html.unescape(title_html_item)
                site_base_url_item, _, _, _ = returnValues(url2_param)
                if not site_base_url_item: site_base_url_item = MainURL
                full_item_url_item = site_base_url_item.rstrip('/') + '/' + url_part_match_item.lstrip('/')
                is_folder_icon_item = 'folderIconClass' in part_item
                is_likely_folder_link_item = not re.search(r'\.\w{2,5}\s*\(', url_part_match_item) and not re.search(r'\.\w{2,5}$', url_part_match_item.split('/')[-1])
                is_folder_item = is_folder_icon_item or (is_likely_folder_link_item and not re.search(r'fileId=\d+', url_part_match_item))


                if is_folder_item:
                    if not return_file_list:
                        folder_name_match_item = re.search(r'<span class="fileinfoFilenameText[^"]*">(.*?)</span>', part_item, re.DOTALL)
                        if not folder_name_match_item:
                           folder_name_match_item = re.search(r'<a[^>]+title="([^"]+)"[^>]*>', part_item)

                        folder_name_display_item = title_from_html_item
                        if folder_name_match_item:
                            raw_name = folder_name_match_item.group(1).strip()
                            folder_name_display_item = html.unescape(re.sub(r'<[^>]+>', '', raw_name))

                        lock_match_item = re.search(r'<span class="pass">', part_item)
                        displock_item = ' [COLOR red](' + traducao(40024) + ')[/COLOR]' if lock_match_item else ''
                        display_folder_name_item = f'{folder_name_display_item}{displock_item}'
                        folder_icon_item = os.path.join(wtpath, art[1:], 'folder.png')
                        addDir(display_folder_name_item, full_item_url_item, 3, folder_icon_item, 0, True)
                else:
                    size_match_li_item = re.search(r'<li><span>([\d,.]+\s*[KMGT]?B)</span></li>', part_item)
                    size_str_raw_item = size_match_li_item.group(1).strip() if size_match_li_item else "0 B"
                    size_display_ui_item = f"({size_str_raw_item})"

                    name_from_title_attr = title_from_html_item
                    name_no_ext_item, file_ext_only_item = os.path.splitext(name_from_title_attr)

                    if not file_ext_only_item or len(file_ext_only_item) > 6 or ' ' in file_ext_only_item:
                        path_part_for_ext_item = url_part_match_item.split('?')[0].split('/')[-1]
                        path_part_for_ext_item_cleaned = re.sub(r'\s*\([\d,.]+\s*[KMGT]?B\)$', '', path_part_for_ext_item).strip()
                        name_from_url, ext_from_url = os.path.splitext(path_part_for_ext_item_cleaned)
                        if ext_from_url and len(ext_from_url) <= 6 and '.' in ext_from_url:
                            file_ext_only_item = ext_from_url
                            # el nombre real es el título del enlace (la URL lo trae codificado y sin '+' ni corchetes fiables)
                            title_stripped = re.sub(re.escape(ext_from_url) + r'$', '', name_from_title_attr, flags=re.IGNORECASE).strip()
                            name_no_ext_item = title_stripped or name_from_url
                        else:
                            file_ext_only_item = ""
                            name_no_ext_item = name_from_title_attr


                    thumb_icon_item = GetThumbExt(file_ext_only_item)
                    item_mode_val = 4
                    file_id_val_item = None
                    file_id_rel_match_item = re.search(r'class="[^"]*fileIdContainer[^"]*".*?rel="(\d+)"', part_item, re.IGNORECASE | re.DOTALL)
                    if file_id_rel_match_item:
                        file_id_val_item = file_id_rel_match_item.group(1)
                    else:
                        file_id_checkbox_match_item = re.search(r'<input[^>]+name="selectFileItem"[^>]+value="(\d+)"', part_item, re.IGNORECASE)
                        if file_id_checkbox_match_item:
                            file_id_val_item = file_id_checkbox_match_item.group(1)

                    if return_file_list:
                        sort_key_temp_item = 0
                        item_data_for_strm_item = [
                            color_param,
                            name_no_ext_item,
                            file_ext_only_item,
                            size_display_ui_item,
                            url_part_match_item,
                            item_mode_val,
                            thumb_icon_item,
                            file_id_val_item
                        ]
                        reslist_local.append([sort_key_temp_item, item_data_for_strm_item])
                    else:
                        display_name_for_ui_item = f'{name_no_ext_item}{file_ext_only_item} [COLOR white]{size_display_ui_item}[/COLOR]'
                        addCont(display_name_for_ui_item, full_item_url_item, item_mode_val, size_display_ui_item, thumb_icon_item, 0)
            except Exception as processing_error_item:
                 k.log(f"ERROR processing item: Title='{title_html_item}', URLPart='{url_part_match_item}', Error: {processing_error_item}", xbmc.LOGERROR)
                 traceback.print_exc()
    return reslist_local


def SearchResults(size_str, color, title, ext, size_display, url_part, mode, thumb, file_id, reslist):
    sort_key_bytes = 0
    try:
        num_part_match = re.match(r"([\d,.]+)", size_str.replace(',','.'))
        num_part = float(num_part_match.group(0)) if num_part_match else 0
        if 'GB' in size_str.upper(): sort_key_bytes = int(num_part * 1024 * 1024 * 1024)
        elif 'MB' in size_str.upper(): sort_key_bytes = int(num_part * 1024 * 1024)
        elif 'KB' in size_str.upper(): sort_key_bytes = int(num_part * 1024)
        elif 'B' in size_str.upper(): sort_key_bytes = int(num_part)
        else: sort_key_bytes = int(num_part)
    except (ValueError, AttributeError) as e:
        k.log(f"Error converting size '{size_str}' to bytes: {e}", xbmc.LOGWARNING)
        sort_key_bytes = 0
    item_data = [color, title, ext, size_display, url_part, mode, thumb, file_id]
    reslist.append([sort_key_bytes, item_data])
    return reslist


def SearchResultsFora(size_str, label, url, reslist):
    sort_key_bytes = 0
    try:
        num_part_match = re.match(r"([\d,.]+)", size_str.replace(',','.'))
        num_part = float(num_part_match.group(0)) if num_part_match else 0
        if 'GB' in size_str.upper(): sort_key_bytes = int(num_part * 1024 * 1024 * 1024)
        elif 'MB' in size_str.upper(): sort_key_bytes = int(num_part * 1024 * 1024)
        elif 'KB' in size_str.upper(): sort_key_bytes = int(num_part * 1024)
        elif 'B' in size_str.upper(): sort_key_bytes = int(num_part)
        else: sort_key_bytes = int(num_part)
    except (ValueError, AttributeError) as e:
        k.log(f"Error converting size (Fora) '{size_str}' to bytes: {e}", xbmc.LOGWARNING)
        sort_key_bytes = 0
    item_data = [label, url]
    reslist.append([sort_key_bytes, item_data])
    return reslist


def pastas_ref(url):
    k.log(f"pastas_ref called for {url}. Use Container.Refresh instead.", xbmc.LOGWARNING)
    xbmc.executebuiltin("Container.Refresh")


def paginas(conteudo_text):
    current_url_param = st.params.get("url", "")
    if not current_url_param:
        k.log("Could not get current URL in paginas function.", xbmc.LOGWARNING)
        global_url = globals().get('url')
        if global_url:
            current_url_param = global_url
        else:
            k.log("No URL context for pagination, cannot add next/prev links.", xbmc.LOGWARNING)
            return


    sitebase, _, color, _ = returnValues(current_url_param)
    if not sitebase or not color:
         k.log("Could not determine sitebase/color for pagination.", xbmc.LOGWARNING)
         return

    previous_page_url = None
    next_page_url = None
    label_prev = f"[B][COLOR gold]{traducao(40064)}[/COLOR][/B][COLOR {color}]{traducao(40062).strip()}[/COLOR]"
    label_next = f"[B][COLOR gold]{traducao(40063)}[/COLOR][/B][COLOR {color}]{traducao(40062).strip()}[/COLOR]"
    icon_prev = os.path.join(wtpath, art[1:], 'back.png')
    icon_next = os.path.join(wtpath, art[1:], 'next.png')
    idmode = 3

    if '/action/SearchFiles' in current_url_param or st.addon.load_data('temp.txt'):
        idmode_next = 24
    else:
        idmode_next = 3

    try:
        for anchor in re.findall(r'<a[^>]+>', conteudo_text):
            if _is_pagination_link(anchor, "prev"):
                match = _PAGINATION_HREF_RE.search(anchor)
                if match:
                    urlpag_part_prev = html.unescape(match.group(1))
                    if not urlpag_part_prev.startswith(('javascript:', '#')):
                        previous_page_url = sitebase.rstrip('/') + '/' + urlpag_part_prev.lstrip('/')
                        k.log(f"Found previous page link: {previous_page_url} (mode 3)", xbmc.LOGDEBUG)
                        break
        if not previous_page_url:
            k.log("Previous page link not found.", xbmc.LOGDEBUG)

        for anchor in re.findall(r'<a[^>]+>', conteudo_text):
            if _is_pagination_link(anchor, "next"):
                match = _PAGINATION_HREF_RE.search(anchor)
                if match:
                    urlpag_part_next = html.unescape(match.group(1))
                    if not urlpag_part_next.startswith(('javascript:', '#')):
                        next_page_url = sitebase.rstrip('/') + '/' + urlpag_part_next.lstrip('/')
                        k.log(f"Found next page link: {next_page_url} (mode {idmode_next})", xbmc.LOGDEBUG)
                        break
        if not next_page_url:
            k.log("Standard next page link not found.", xbmc.LOGDEBUG)

        if previous_page_url: addDir(label_prev, previous_page_url, 3, icon_prev, 0, True)
        if next_page_url: addDir(label_next, next_page_url, idmode_next, icon_next, 0, True)
    except Exception as e:
        k.log(f"Error parsing pagination: {e}", xbmc.LOGERROR)
        traceback.print_exc()


def prefetch_next_page(conteudo_text, current_url):
    """Descarga la página siguiente en segundo plano y la deja en la caché (la navegación pasa a ser instantánea)."""
    if selfAddon.getSetting('prefetch_next') == 'false' or cache_mod.ttl_seconds() <= 0: return
    next_url = get_next_page_url_for_strm_gen(conteudo_text, current_url)
    if not next_url or next_url == current_url: return
    full_url = next_url + returnExtra()  # misma URL que usará pastas() al entrar -> misma clave de caché
    scope_id = cache_mod.scope()
    if cache_mod.get(full_url, scope_id=scope_id) is not None: return
    def worker():
        try:
            body = make_session().request(full_url, headers={'Referer': MainURL, 'Accept': 'text/html,*/*;q=0.8'}, retries=1)
            cache_mod.put(full_url, body, scope_id=scope_id)
        except Exception as e:
            k.log(f"Prefetch skipped: {e}", xbmc.LOGDEBUG)
    threading.Thread(target=worker, name="chomiteca-prefetch").start()


def refresh_folder_cache(url_param):
    cache_mod.invalidate(url_param)
    notify(strings.t(40320))
    xbmc.executebuiltin("Container.Refresh")


def metadata_prefetch_from_html(conteudo_text):
    if not (metadata.enabled() and metadata.tmdb_key()): return
    names = []
    for url_part, title in re.findall(r'<a[^>]*?class="expanderHeader[^"]*?"[^>]*?href="/([^"]+)"[^>]*?title="([^"]+)"', conteudo_text, re.IGNORECASE | re.DOTALL):
        title = html.unescape(title)
        ext_title = os.path.splitext(title)[1].lower()
        ext_url = os.path.splitext(re.sub(r'\s*\([\d,.]+\s*[KMGT]?B\)$', '', url_part.split('?')[0].split('/')[-1]).strip())[1].lower()
        if ext_title in VIDEO_EXTS_UI or ext_url in VIDEO_EXTS_UI or re.search(r'\.(?:mkv|mp4|avi|wmv|mov|m2ts|ts|mpg|mpeg|webm)(?![a-z0-9])', url_part, re.IGNORECASE): names.append(title)  # el título puede no llevar extensión ("...5.1][HDO]")
    if names: metadata.prefetch(names)


# Importaciones entre módulos de funciones al final: así las referencias circulares son seguras
from resources.lib.library import get_next_page_url_for_strm_gen
from resources.lib.playback import analyzer
from resources.lib.playlist import add_items_to_playlist_db, clear_playlist_db
from resources.lib.search import _sort_search_results
