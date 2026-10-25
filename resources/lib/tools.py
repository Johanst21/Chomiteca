# -*- coding: utf-8 -*-
"""Diagnóstico y exportación de registro redactado."""
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

from resources.lib.common import DIALOG_MESSAGE, MainURL, cookies, get_active_account_details, load_accounts, net, notify, pastaperfil, selfAddon, user_agent


def _redact_all(text):
    text = k.redact(text)
    for acc in load_accounts() or []:
        user = acc.get('username')
        if user: text = text.replace(user, '<usuario>')
    for secret_id in ('tmdb_api_key', 'youtube_api_key'):
        val = selfAddon.getSetting(secret_id)
        if val: text = text.replace(val, '***')
    return text


def _versions_block():
    return [f"{strings.t(40389)}:",
            f"  addon: {selfAddon.getAddonInfo('version')}",
            f"  Kodi: {xbmc.getInfoLabel('System.BuildVersion')}",
            f"  Python: {sys.version.split()[0]}"]


def diagnostics():
    ok, bad = strings.t(40386), strings.t(40387)
    lines = [f"[B]{strings.t(40335)}[/B]", ""]
    t0 = _time.time()
    try:
        req = urllib.request.Request(MainURL, headers={'User-Agent': user_agent})
        with urllib.request.urlopen(req, timeout=10) as resp:
            lines.append(f"{strings.t(40380)}: {ok} (HTTP {resp.status}, {int((_time.time() - t0) * 1000)} ms)")
    except Exception as e:
        lines.append(f"{strings.t(40380)}: {bad} - {describe_error(e)}")
    account = get_active_account_details()
    lines.append(f"{strings.t(40381)}: {account.get('label') or account.get('username') if account else strings.t(40388)}")
    if account:
        session = make_session()
        try:
            auth.login(session, {'username': account['username'], 'password': account['password'], 'label': account.get('label', '')})
            lines.append(f"{strings.t(40382)}: {ok}")
            net.load_cookies(cookies)
            try:
                page = session.request(MainURL + urllib.parse.quote(account['username']), retries=1)
                lines.append(f"{strings.t(40383)}: {ok} ({len(page) // 1024} KB)")
            except Exception as e:
                lines.append(f"{strings.t(40383)}: {bad} - {describe_error(e)}")
        except auth.LoginError as e:
            lines.append(f"{strings.t(40382)}: {bad} - {e}")
    rows = dq.list_all()
    lines.append(f"{strings.t(40384)}: {len(rows)} ({sum(1 for r in rows if r[3] == 'downloading')} {strings.t(40309).lower()})")
    n, size = cache_mod.stats()
    lines.append(f"{strings.t(40385)}: {n} ({size // 1024} KB, TTL {cache_mod.ttl_seconds() // 60} min)")
    lines.append("")
    lines += _versions_block()
    DIALOG_MESSAGE.textviewer(strings.t(40301), _redact_all("\n".join(lines)))


def export_log():
    """Guarda las últimas líneas de kodi.log con cookies, tokens, usuarios y claves redactados."""
    src = xbmcvfs.translatePath('special://logpath/kodi.log')
    try:
        with open(src, 'r', encoding='utf-8', errors='ignore') as fh:
            tail = fh.readlines()[-4000:]
    except OSError as e:
        notify(str(e), error=True); return
    out = os.path.join(pastaperfil, 'chomiteca_log_redactado.txt')
    body = "\n".join(_versions_block()) + "\n\n" + "".join(_redact_all(line) for line in tail)
    try:
        os.makedirs(pastaperfil, exist_ok=True)
        with open(out, 'w', encoding='utf-8') as fh: fh.write(body)
    except OSError as e:
        notify(str(e), error=True); return
    DIALOG_MESSAGE.ok(strings.t(40337), strings.t(40336).format(out))


def set_tmdb_key():
    """Pide la clave de TMDb con el teclado y la guarda (se lanza desde Ajustes > Metadatos)."""
    current = (k.ADDON.getSetting('tmdb_api_key') or '').strip()
    value = xbmcgui.Dialog().input(strings.t(40390), defaultt=current, type=xbmcgui.INPUT_ALPHANUM)
    if value is None or value.strip() == current:
        return
    k.ADDON.setSetting('tmdb_api_key', value.strip())
    k.notify(strings.t(40391) if value.strip() else strings.t(40392))
