# -*- coding: utf-8 -*-

import json, xbmc, xbmcaddon, xbmcvfs, os, re, zlib, base64, traceback
import xmlrpc.client

try:
    addon_id = "plugin.video.chomiteca"
    selfAddon = xbmcaddon.Addon(id=addon_id)
    log_prefix = f"[{selfAddon.getAddonInfo('name')} Subtitles]"
except Exception as e:
    log_prefix = "[Chomiteca Subtitles]"
    xbmc.log(f"{log_prefix} Could not get addon instance: {e}", xbmc.LOGWARNING)


def log(message, level=xbmc.LOGINFO):
    xbmc.log(f"{log_prefix} {message}", level=level)


def getsubtitles(name, lang1=None, lang2=None):
    cleaned_name = ""
    subtitle_path = None

    try:
        match = re.match(r'\[B\](?:\[COLOR.*?\])?(.*?)(?:\[/COLOR\])?\[/B\](?:.*)', name, re.IGNORECASE)
        if match:
            cleaned_name = match.group(1).strip()
        else:
            cleaned_name = name.strip()

        if not cleaned_name:
            log(f"Could not clean name from input: {name}", xbmc.LOGWARNING)
            cleaned_name = name

        log(f"Cleaned name for subtitle search: {cleaned_name}", xbmc.LOGDEBUG)
    except Exception as clean_e:
         log(f"Error cleaning name '{name}': {clean_e}", xbmc.LOGERROR)
         cleaned_name = name

    langDict = {'afrikaans': 'afr', 'albanian': 'alb', 'arabic': 'ara', 'armenian': 'arm', 'basque': 'baq',
                'bengali': 'ben', 'bosnian': 'bos', 'breton': 'bre', 'bulgarian': 'bul', 'burmese': 'bur',
                'catalan': 'cat', 'chinese': 'chi', 'croatian': 'hrv', 'czech': 'cze', 'danish': 'dan',
                'dutch': 'dut', 'english': 'eng', 'esperanto': 'epo', 'estonian': 'est', 'finnish': 'fin',
                'french': 'fre', 'galician': 'glg', 'georgian': 'geo', 'german': 'ger', 'greek': 'ell',
                'hebrew': 'heb', 'hindi': 'hin', 'hungarian': 'hun', 'icelandic': 'ice', 'indonesian': 'ind',
                'italian': 'ita', 'japanese': 'jpn', 'kazakh': 'kaz', 'khmer': 'khm', 'korean': 'kor',
                'latvian': 'lav', 'lithuanian': 'lit', 'luxembourgish': 'ltz', 'macedonian': 'mac', 'malay': 'may',
                'malayalam': 'mal', 'manipuri': 'mni', 'mongolian': 'mon', 'montenegrin': 'mne', 'norwegian': 'nor',
                'occitan': 'oci', 'persian': 'per', 'polish': 'pol', 'portuguese': 'por',
                'portuguese-br': 'pob',
                'romanian': 'rum', 'russian': 'rus', 'serbian': 'srp',
                'sinhalese': 'sin', 'slovak': 'slo', 'slovenian': 'slv', 'spanish': 'spa', 'swahili': 'swa',
                'swedish': 'swe', 'syriac': 'syr', 'tagalog': 'tgl', 'tamil': 'tam', 'telugu': 'tel',
                'thai': 'tha', 'turkish': 'tur', 'ukrainian': 'ukr', 'urdu': 'urd', 'vietnamese': 'vie'}

    langs_codes = []
    if lang1 and lang1.lower() in langDict: langs_codes.append(langDict[lang1.lower()])
    if lang2 and lang2.lower() in langDict: langs_codes.append(langDict[lang2.lower()])

    langs_codes = list(dict.fromkeys(langs_codes))
    langs_search_str = ','.join(langs_codes)

    if not langs_search_str:
        log("No valid languages selected for subtitle search.", xbmc.LOGWARNING)
        return None

    log(f"Searching subtitles for languages: {langs_search_str}", xbmc.LOGINFO)

    server = None
    token = None
    search_results = None
    counterloop = 0
    max_loops = 2  # antes 5 (hasta 20 s de espera antes de reproducir si la API no responde)

    endpoint = 'https://api.opensubtitles.org/xml-rpc'  # OpenSubtitles.org anunció el cierre de esta API en 2026: la función puede no responder

    while not search_results and counterloop < max_loops:
        try:
            if counterloop > 0:
                log(f"Retrying API connection (Attempt {counterloop + 1}) after delay...", xbmc.LOGINFO)
                xbmc.sleep(2000 * counterloop)

            log(f"Connecting to OpenSubtitles API: {endpoint}", xbmc.LOGDEBUG)
            server = xmlrpc.client.ServerProxy(endpoint, verbose=0)

            user_agent_api = f"Kodi Addon {addon_id}"
            log(f"Logging in with UserAgent: {user_agent_api}", xbmc.LOGDEBUG)
            login_response = server.LogIn('', '', 'en', user_agent_api)
            log(f"Login response: {login_response}", xbmc.LOGDEBUG)

            if login_response.get('status') != '200 OK':
                raise ConnectionError(f"OpenSubtitles Login failed: {login_response.get('status')}")

            token = login_response.get('token')
            if not token:
                 raise ConnectionError("OpenSubtitles Login failed: No token received.")
            log(f"Login successful, Token obtained.", xbmc.LOGDEBUG)

            search_query = [{'query': cleaned_name, 'sublanguageid': langs_search_str}]
            log(f"Searching subtitles with query: {search_query}", xbmc.LOGDEBUG)
            search_response = server.SearchSubtitles(token, search_query)

            try: log(f"Search Response (raw): {json.dumps(search_response, indent=2)}", xbmc.LOGDEBUG)
            except: log(f"Search Response (repr): {repr(search_response)}", xbmc.LOGDEBUG)


            if search_response.get('status') != '200 OK':
                 log(f"SearchSubtitles failed with status: {search_response.get('status')}", xbmc.LOGWARNING)
                 search_results = []
            elif not search_response.get('data'):
                 log("No subtitle results found (data field empty/missing).", xbmc.LOGINFO)
                 search_results = []
            else:
                 search_results = search_response['data']
                 log(f"Found {len(search_results)} potential subtitle results.", xbmc.LOGINFO)
                 break

        except xmlrpc.client.Fault as xml_e:
            log(f"XML-RPC Fault (Loop {counterloop+1}/{max_loops}): {xml_e}", xbmc.LOGERROR)
            traceback.print_exc()
        except ConnectionRefusedError as conn_e:
            log(f"Connection Refused (Loop {counterloop+1}/{max_loops}): {conn_e} - Check endpoint/network.", xbmc.LOGERROR)
        except Exception as e:
            log(f"Error during OpenSubtitles communication (Loop {counterloop+1}/{max_loops}): {e}", xbmc.LOGERROR)
            traceback.print_exc()

        counterloop += 1

    if not token or server is None:
        log("Could not establish connection or login to OpenSubtitles.", xbmc.LOGERROR)
        return None

    if not search_results:
        log(f"No subtitles found for '{cleaned_name}' in languages '{langs_search_str}'.", xbmc.LOGINFO)
        return None

    log("Filtering and ranking subtitle results...", xbmc.LOGDEBUG)
    matched_subtitle = None
    results_cd1 = [sub for sub in search_results if sub.get('SubSumCD') == '1']
    log(f"Found {len(results_cd1)} results matching 1 CD.", xbmc.LOGDEBUG)

    quality = ['bluray', 'blueray', 'hdrip', 'brrip', 'bdrip', 'dvdrip', 'webdl', 'webrip', 'hdtv', 'x264', 'x265']
    movie_quality_tags = [q for q in quality if q in name.lower()]
    log(f"Detected quality tags in original name: {movie_quality_tags}", xbmc.LOGDEBUG)

    for lang_code in langs_codes:
        subs_for_lang = [sub for sub in results_cd1 if sub.get('SubLanguageID') == lang_code]
        if not subs_for_lang: continue

        log(f"Found {len(subs_for_lang)} results for language '{lang_code}'. Ranking...", xbmc.LOGDEBUG)

        exact_match = [sub for sub in subs_for_lang if cleaned_name.lower() in sub.get('MovieReleaseName', '').lower()]
        if exact_match:
             exact_match.sort(key=lambda s: float(s.get('SubRating', '0.0')), reverse=True)
             matched_subtitle = exact_match[0]
             log(f"Rank 1: Found exact release name match: {matched_subtitle.get('SubFileName')}", xbmc.LOGINFO)
             break

        if movie_quality_tags:
            quality_match = [sub for sub in subs_for_lang if any(q in sub.get('MovieReleaseName', '').lower() for q in movie_quality_tags)]
            if quality_match:
                 quality_match.sort(key=lambda s: float(s.get('SubRating', '0.0')), reverse=True)
                 matched_subtitle = quality_match[0]
                 log(f"Rank 2: Found quality tag match: {matched_subtitle.get('SubFileName')}", xbmc.LOGINFO)
                 break

        subs_for_lang.sort(key=lambda s: float(s.get('SubRating', '0.0') or '0.0'), reverse=True)
        matched_subtitle = subs_for_lang[0]
        log(f"Rank 3: Using highest rated subtitle as fallback: {matched_subtitle.get('SubFileName')}", xbmc.LOGINFO)
        break

    if not matched_subtitle:
        log("No suitable subtitle found after filtering and ranking.", xbmc.LOGINFO)
        return None

    log(f"Selected subtitle: ID {matched_subtitle.get('IDSubtitleFile')}, File: {matched_subtitle.get('SubFileName')}, Lang: {matched_subtitle.get('SubLanguageID')}, Rating: {matched_subtitle.get('SubRating')}", xbmc.LOGINFO)
    subtitle_id_to_download = matched_subtitle.get("IDSubtitleFile")
    if not subtitle_id_to_download:
         log("Selected subtitle is missing IDSubtitleFile.", xbmc.LOGERROR)
         return None

    kodi_lang_code = matched_subtitle.get('SubLanguageID', 'unk')
    try:
        temp_lang = xbmc.convertLanguage(kodi_lang_code, xbmc.ISO_639_1)
        if temp_lang: kodi_lang_code = temp_lang
        log(f"Using language code for filename: {kodi_lang_code}", xbmc.LOGDEBUG)
    except Exception as lang_e:
        log(f"Could not convert language code {kodi_lang_code} using xbmc.convertLanguage: {lang_e}", xbmc.LOGWARNING)


    try:
        log(f"Downloading subtitle ID: {subtitle_id_to_download}", xbmc.LOGDEBUG)
        download_response = server.DownloadSubtitles(token, [subtitle_id_to_download])

        if download_response.get('status') != '200 OK' or not download_response.get('data'):
            raise ValueError(f"DownloadSubtitles failed: {download_response.get('status', 'Unknown error')}")

        base64_data = download_response['data'][0]['data']

        log("Decoding base64 data...", xbmc.LOGDEBUG)
        if isinstance(base64_data, str):
             subtitle_compressed_bytes = base64.b64decode(base64_data.encode('ascii'))
        elif isinstance(base64_data, bytes):
             subtitle_compressed_bytes = base64.b64decode(base64_data)
        else:
             try: subtitle_compressed_bytes = base64.b64decode(base64_data.data)
             except: raise TypeError("Unsupported type for base64 data from API")


        log("Decompressing subtitle data...", xbmc.LOGDEBUG)
        decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
        subtitle_content_bytes = decompressor.decompress(subtitle_compressed_bytes)
        subtitle_content_bytes += decompressor.flush()


        temp_dir = xbmcvfs.translatePath('special://temp/')
        if not xbmcvfs.exists(temp_dir): xbmcvfs.mkdirs(temp_dir)

        subtitle_filename = f'DownloadedSubtitles.{kodi_lang_code}.srt'
        subtitle_path = os.path.join(temp_dir, subtitle_filename)

        log(f"Saving subtitle to temporary file: {subtitle_path}", xbmc.LOGINFO)
        try:
            with xbmcvfs.File(subtitle_path, 'wb') as file:
                 bytes_written = file.write(subtitle_content_bytes)
                 if bytes_written != len(subtitle_content_bytes):
                     log(f"Warning: Bytes written ({bytes_written}) differs from expected ({len(subtitle_content_bytes)}). File may be incomplete.", xbmc.LOGWARNING)
            log("Subtitle file saved successfully.", xbmc.LOGINFO)
            return subtitle_path

        except Exception as write_e:
            log(f"Failed to write subtitle file {subtitle_path}: {write_e}", xbmc.LOGERROR)
            traceback.print_exc()
            return None

    except Exception as e:
        log(f"Error during subtitle download/processing: {e}", xbmc.LOGERROR)
        traceback.print_exc()
        return None
