# -*- coding: utf-8 -*-
"""Metadatos a partir del nombre de archivo (siempre) y de TMDb (opcional, con clave de API)."""
import json
import re
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait

from . import kodiutils as k, store

_SXXEXX = re.compile(r"(?i)(?<![a-z0-9])s(\d{1,2})[ ._-]?e(\d{1,3})(?![a-z0-9])")
_NXNN = re.compile(r"(?i)(?<![a-z0-9])(\d{1,2})x(\d{2,3})(?![a-z0-9])")
_YEAR = re.compile(r"(?<!\d)(19[2-9]\d|20[0-4]\d)(?!\d)")
_NOISE = re.compile(
    r"(?i)(?<![a-z0-9])(2160p|1080[pi]|720p|576p|480p|4k|uhd|hdr10?\+?|dolby|bluray|blu-ray|bdrip|brrip|"
    r"web-?dl|web-?rip|hdtv|dvdrip|dvdscr|hdrip|cam|x26[45]|h\.?26[45]|hevc|xvid|divx|aac|ac3|eac3|dts|"
    r"atmos|remux|proper|repack|extended|unrated|dual|multi|latino|castellano|espa[nñ]ol|spanish|vose|"
    r"lektor|napisy|dubbing|subbed|dubbed|10bit|imax)(?![a-z0-9])"
)
_EXT = re.compile(r"\.[A-Za-z0-9]{2,5}$")
_TMDB = "https://api.themoviedb.org/3"
_IMG = "https://image.tmdb.org/t/p/"
_TTL = 30 * 86400


def enabled():
    return (k.ADDON.getSetting("metadata_parse") or "true") == "true"


def tmdb_key():
    return (k.ADDON.getSetting("tmdb_api_key") or "").strip()


def parse(filename):
    """-> {'title','year','season','episode','kind'}  kind: episode | movie | video"""
    name = _EXT.sub("", (filename or "").replace("+", " ")).strip()
    name = re.sub(r"[\[\(\{][^\]\)\}]*[\]\)\}]", lambda m: m.group(0) if _YEAR.fullmatch(m.group(0).strip("[({})]")) else " ", name)
    name = re.sub(r"[._]+", " ", name)
    season = episode = year = None
    cut = len(name)
    m = _SXXEXX.search(name) or _NXNN.search(name)
    if m:
        season, episode = int(m.group(1)), int(m.group(2))
        cut = m.start()
    ym = None
    for ym in _YEAR.finditer(name):
        pass  # último año: evita confundir "2001 Odisea del espacio (1968)" con el primer número
    if ym and (not m or ym.start() < cut):
        year = int(ym.group(1))
        if not m:
            cut = min(cut, ym.start())
    nm = _NOISE.search(name)
    if nm and nm.start() < cut and nm.start() > 0:
        cut = nm.start()
    title = re.sub(r"\s+", " ", name[:cut]).strip(" -–—_([{)]}")
    if not title:
        title = re.sub(r"\s+", " ", name).strip()
    kind = "episode" if season is not None else ("movie" if year else "video")
    return {"title": title, "year": year, "season": season, "episode": episode, "kind": kind}


def _ckey(info, lang):
    if info["kind"] == "episode":
        return "tv2|%s|%s|s%se%s|%s" % (info["title"].lower(), info["year"] or "", info.get("season"), info.get("episode"), lang)
    return "movie|%s|%s|%s" % (info["title"].lower(), info["year"] or "", lang)


def _lang():
    return (k.ADDON.getSetting("metadata_lang") or "es-ES").strip() or "es-ES"


def cached(info):
    if not tmdb_key() or not info.get("title"):
        return None
    try:
        with store.db() as c:
            row = c.execute("SELECT ts, data FROM meta_cache WHERE key=?", (_ckey(info, _lang()),)).fetchone()
        if row and time.time() - row[0] < _TTL:
            return json.loads(row[1]) or {}  # {} = consultado sin resultado (no reintentar); None = sin consultar
    except Exception:
        pass
    return None


def _http_json(path, params, key):
    headers = {"Accept": "application/json"}
    if key.startswith("eyJ"):  # token v4 (Bearer)
        headers["Authorization"] = "Bearer " + key
    else:
        params["api_key"] = key
    req = urllib.request.Request("%s%s?%s" % (_TMDB, path, urllib.parse.urlencode(params)), headers=headers)
    with urllib.request.urlopen(req, timeout=4) as resp:
        return json.loads(resp.read().decode("utf-8", "ignore"))


_SEASONS = {}


def _season(show_id, number, lang, key):
    """Datos de una temporada (póster y lista de capítulos); una sola petición por temporada y ejecución."""
    ck = (show_id, number, lang)
    if ck not in _SEASONS:
        _SEASONS[ck] = _http_json("/tv/%s/season/%d" % (show_id, number), {"language": lang}, key)
    return _SEASONS[ck]


def lookup(info):
    """Consulta TMDb (y cachea, también los fallos para no repetir). Devuelve dict o None."""
    key = tmdb_key()
    if not key or not info.get("title"):
        return None
    lang = _lang()
    ck = _ckey(info, lang)
    result = None
    try:
        is_tv = info["kind"] == "episode"
        params = {"query": info["title"], "language": lang}
        if info.get("year"):
            params["first_air_date_year" if is_tv else "year"] = info["year"]
        data = _http_json("/search/tv" if is_tv else "/search/movie", params, key)
        hits = data.get("results") or []
        if not hits and info.get("year"):  # el año del nombre de archivo a veces no coincide con TMDb
            params.pop("first_air_date_year" if is_tv else "year", None)
            hits = (_http_json("/search/tv" if is_tv else "/search/movie", params, key).get("results") or [])
        if hits:
            h = hits[0]
            date = (h.get("first_air_date") if is_tv else h.get("release_date")) or ""
            result = {
                "title": h.get("name") if is_tv else h.get("title"),
                "year": int(date[:4]) if date[:4].isdigit() else None,
                "plot": h.get("overview") or "",
                "rating": h.get("vote_average") or 0,
                "poster": (_IMG + "w500" + h["poster_path"]) if h.get("poster_path") else "",
                "fanart": (_IMG + "w1280" + h["backdrop_path"]) if h.get("backdrop_path") else "",
            }
            if is_tv and info.get("season") is not None and info.get("episode") is not None:
                try:
                    season = _season(h["id"], info["season"], lang, key)
                    if season.get("poster_path"):
                        result["poster"] = _IMG + "w500" + season["poster_path"]  # póster de la temporada del capítulo
                    ep = next((e for e in season.get("episodes") or [] if e.get("episode_number") == info["episode"]), None)
                    if ep:
                        overview = ep.get("overview") or ""
                        if not overview and lang.lower() != "en-us":  # sin sinopsis en tu idioma: se usa la inglesa
                            ep_en = next((e for e in _season(h["id"], info["season"], "en-US", key).get("episodes") or [] if e.get("episode_number") == info["episode"]), None)
                            overview = (ep_en or {}).get("overview") or ""
                        if overview: result["plot"] = overview  # sinopsis del capítulo (no la de la serie)
                        result["episode_title"] = ep.get("name") or ""
                        if ep.get("still_path"): result["still"] = _IMG + "w500" + ep["still_path"]
                except Exception as exc:
                    k.log("TMDb season lookup failed: %s" % exc, k.xbmc.LOGDEBUG)  # se queda con póster y sinopsis de la serie
    except Exception as exc:
        k.log("TMDb lookup failed: %s" % exc, k.xbmc.LOGDEBUG)
        return None  # error de red: no cachear, se reintentará
    try:
        with store.db() as c:
            c.execute("INSERT OR REPLACE INTO meta_cache(key, ts, data) VALUES (?,?,?)", (ck, time.time(), json.dumps(result)))
    except Exception:
        pass
    return result


def prefetch(filenames, budget=6.0, workers=4):
    """Consulta TMDb en paralelo para los nombres sin caché, con un tope de tiempo total."""
    if not tmdb_key():
        return
    todo, seen = [], set()
    for fn in filenames:
        info = parse(fn)
        key = _ckey(info, _lang())
        if info["title"] and key not in seen and cached(info) is None:
            seen.add(key)
            todo.append(info)
    if not todo:
        return
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        wait([pool.submit(lookup, i) for i in todo[:40]], timeout=budget)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


# ---------------------------------------------------------------------------------------------
# Carpetas (series, temporadas y películas): póster y sinopsis al situarse sobre la carpeta
# ---------------------------------------------------------------------------------------------
_SEASON_DIR = re.compile(r"(?i)^\s*(?:season|temporada|temp|sezon|seria|series|serie|t|s)[ ._-]*0*(\d{1,2})(?!\d)")
parent_name = ""  # nombre de la carpeta que se está listando (lo fija listing.pastas); sirve para las carpetas de temporada


def _clean_dir(name):
    return re.sub(r"\s+", " ", re.sub(r"\[/?[A-Za-z]+[^\]]*\]", "", name or "")).strip()


_YEAR_PAREN = re.compile(r"\(\s*((?:19|20)\d{2})\s*\)")


def folder_info(name, parent=None):
    """-> {'title','year','season'} solo para carpetas de serie/película, es decir, "Nombre (Año)", y para las
    carpetas de temporada ("Temporada 1") que cuelgan de una de ellas. Carpetas organizadoras (Netflix, HBO Max,
    Uploaded, Privado...) -> None."""
    name = _clean_dir(name)
    if not name or name.startswith(".."):
        return None
    sm = _SEASON_DIR.match(name)
    if sm:
        parent_clean = _clean_dir(parent or parent_name)
        ym = _YEAR_PAREN.search(parent_clean)
        if not ym:
            return None
        show = parse(parent_clean)
        if not show["title"]:
            return None
        return {"title": show["title"], "year": int(ym.group(1)), "season": int(sm.group(1))}
    ym = _YEAR_PAREN.search(name)
    if not ym:
        return None
    title = parse(name)["title"]
    if not title or len(title) < 2:
        return None
    return {"title": title, "year": int(ym.group(1)), "season": None}


def _fkey(info, lang):
    return "dir|%s|%s|%s|%s" % (info["title"].lower(), info["year"] or "", info["season"] or "", lang)


def folder_cached(name, parent=None):
    if not tmdb_key():
        return None
    info = folder_info(name, parent)
    if not info:
        return None
    try:
        with store.db() as c:
            row = c.execute("SELECT ts, data FROM meta_cache WHERE key=?", (_fkey(info, _lang()),)).fetchone()
        if row and time.time() - row[0] < _TTL:
            return json.loads(row[1]) or {}  # {} = consultado sin resultado (no reintentar); None = sin consultar
    except Exception:
        pass
    return None


def _pick(hits, year):
    hits = [h for h in hits if h.get("media_type") in ("tv", "movie")]
    if not hits:
        return None
    if year:
        for h in hits:
            date = h.get("first_air_date") or h.get("release_date") or ""
            if date[:4] == str(year):
                return h
    return hits[0]


def lookup_folder(info):
    key = tmdb_key()
    if not key:
        return None
    lang = _lang()
    ck = _fkey(info, lang)
    result = None
    try:
        params = {"query": info["title"], "language": lang, "include_adult": "false"}
        if info["season"]:  # temporada: se busca la serie y luego el póster de esa temporada
            sp = {"query": info["title"], "language": lang}
            if info["year"]:
                sp["first_air_date_year"] = info["year"]
            hits = _http_json("/search/tv", sp, key).get("results") or []
            if not hits and info["year"]:
                sp.pop("first_air_date_year")
                hits = _http_json("/search/tv", sp, key).get("results") or []
            if hits:
                show = hits[0]
                season = _http_json("/tv/%s/season/%d" % (show["id"], info["season"]), {"language": lang}, key)
                poster = season.get("poster_path") or show.get("poster_path")
                date = show.get("first_air_date") or ""
                result = {
                    "kind": "season", "title": show.get("name"), "season": info["season"],
                    "year": int(date[:4]) if date[:4].isdigit() else None,
                    "plot": season.get("overview") or show.get("overview") or "",
                    "rating": show.get("vote_average") or 0,
                    "poster": (_IMG + "w500" + poster) if poster else "",
                    "fanart": (_IMG + "w1280" + show["backdrop_path"]) if show.get("backdrop_path") else "",
                }
        else:
            if info["year"]:
                params["year"] = info["year"]  # solo afecta a películas en /search/multi; las series se filtran en _pick
            hits = _http_json("/search/multi", params, key).get("results") or []
            if not hits and info["year"]:
                params.pop("year")
                hits = _http_json("/search/multi", params, key).get("results") or []
            h = _pick(hits, info["year"])
            if h:
                is_tv = h["media_type"] == "tv"
                date = (h.get("first_air_date") if is_tv else h.get("release_date")) or ""
                result = {
                    "kind": "tvshow" if is_tv else "movie",
                    "title": h.get("name") if is_tv else h.get("title"),
                    "year": int(date[:4]) if date[:4].isdigit() else None,
                    "plot": h.get("overview") or "",
                    "rating": h.get("vote_average") or 0,
                    "poster": (_IMG + "w500" + h["poster_path"]) if h.get("poster_path") else "",
                    "fanart": (_IMG + "w1280" + h["backdrop_path"]) if h.get("backdrop_path") else "",
                }
    except Exception as exc:
        k.log("TMDb folder lookup failed: %s" % exc, k.xbmc.LOGDEBUG)
        return None
    try:
        with store.db() as c:
            c.execute("INSERT OR REPLACE INTO meta_cache(key, ts, data) VALUES (?,?,?)", (ck, time.time(), json.dumps(result)))
    except Exception:
        pass
    return result


# --- Plataformas (Netflix, HBO Max, Disney+...): el logo de TMDb hace de carátula ---------------------------
_PLATFORM_ALIASES = {"max": "hbomax", "hbo": "hbomax", "prime": "amazonprimevideo", "primevideo": "amazonprimevideo",
                     "amazon": "amazonprimevideo", "amazonprime": "amazonprimevideo", "appletv": "appletvplus",
                     "apple": "appletvplus", "paramount": "paramountplus", "disney": "disneyplus"}


def _pname(text):
    text = _clean_dir(text).lower().replace("+", " plus ")
    return re.sub(r"[^a-z0-9]+", "", text)


def _region():
    parts = _lang().replace("_", "-").split("-")
    return parts[1].upper() if len(parts) > 1 and len(parts[1]) == 2 else "US"


def _providers_key():
    return "providers|%s" % _region()


def _providers_cached():
    try:
        with store.db() as c:
            row = c.execute("SELECT ts, data FROM meta_cache WHERE key=?", (_providers_key(),)).fetchone()
        if row and time.time() - row[0] < _TTL:
            return json.loads(row[1]) or {}
    except Exception:
        pass
    return None


def _fetch_providers():
    """Lista de plataformas de TMDb (series y películas) de tu región -> {nombre normalizado: url del logo}."""
    key = tmdb_key()
    if not key:
        return None
    logos = {}
    try:
        for kind in ("tv", "movie"):
            data = _http_json("/watch/providers/%s" % kind, {"watch_region": _region(), "language": _lang()}, key)
            for p in data.get("results") or []:
                if p.get("logo_path") and p.get("provider_name"):
                    logos.setdefault(_pname(p["provider_name"]), _IMG + "w500" + p["logo_path"])
    except Exception as exc:
        k.log("TMDb providers failed: %s" % exc, k.xbmc.LOGDEBUG)
        return None
    try:
        with store.db() as c:
            c.execute("INSERT OR REPLACE INTO meta_cache(key, ts, data) VALUES (?,?,?)", (_providers_key(), time.time(), json.dumps(logos)))
    except Exception:
        pass
    return logos


def platform_logo(name):
    """Logo de la plataforma si el nombre de la carpeta es una (Netflix, HBO Max, Disney +...); solo lee la caché."""
    if not tmdb_key():
        return None
    logos = _providers_cached()
    wanted = _pname(name)
    if not logos or len(wanted) < 3:
        return None
    wanted = _PLATFORM_ALIASES.get(wanted, wanted)
    if wanted in logos:
        return logos[wanted]
    if len(wanted) >= 5:
        for pname, url in logos.items():
            if pname.startswith(wanted) or wanted.startswith(pname):
                return url
    return None


def prefetch_folders(names, parent=None, budget=6.0, workers=4):
    """Consulta TMDb en paralelo para las carpetas sin caché (y carga la lista de plataformas si hace falta)."""
    if not tmdb_key():
        return
    todo, seen, other = [], set(), False
    for nm in names:
        info = folder_info(nm, parent)
        if not info:
            other = True  # carpeta que no es serie/película: puede ser una plataforma
            continue
        key = _fkey(info, _lang())
        if key not in seen and folder_cached(nm, parent) is None:
            seen.add(key)
            todo.append(info)
    if other and _providers_cached() is None:
        _fetch_providers()
    if not todo:
        return
    pool = ThreadPoolExecutor(max_workers=workers)
    try:
        wait([pool.submit(lookup_folder, i) for i in todo[:40]], timeout=budget)
    finally:
        pool.shutdown(wait=False, cancel_futures=True)
