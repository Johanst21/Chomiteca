# -*- coding: utf-8 -*-
"""Caché de páginas de carpetas (HTML) con TTL, separada por cuenta."""
import random
import time

from . import accounts, kodiutils as k, store

MAX_BODY = 2 * 1024 * 1024


def ttl_seconds():
    try:
        return max(0, int(float(k.ADDON.getSetting("cache_minutes") or 10))) * 60
    except ValueError:
        return 600


def scope():
    acc = accounts.active() or {}
    return acc.get("id", "anon")


def _key(url, scope_id=None):
    return "%s|%s" % (scope_id or scope(), url)


def get(url, ttl=None, scope_id=None):
    ttl = ttl_seconds() if ttl is None else ttl
    if ttl <= 0:
        return None
    try:
        with store.db() as c:
            row = c.execute("SELECT ts, body FROM page_cache WHERE key=?", (_key(url, scope_id),)).fetchone()
        if row and time.time() - row[0] <= ttl:
            return bytes(row[1])
    except Exception as exc:
        k.log("cache.get: %s" % exc, k.xbmc.LOGWARNING)
    return None


def put(url, body, scope_id=None):
    if not body or len(body) > MAX_BODY or ttl_seconds() <= 0:
        return
    try:
        with store.db() as c:
            c.execute("INSERT OR REPLACE INTO page_cache(key, ts, body) VALUES (?,?,?)",
                      (_key(url, scope_id), time.time(), body))
            if random.random() < 0.05:  # limpieza ocasional de entradas de más de un día
                c.execute("DELETE FROM page_cache WHERE ts < ?", (time.time() - 86400,))
    except Exception as exc:
        k.log("cache.put: %s" % exc, k.xbmc.LOGWARNING)


def invalidate(url=None):
    """url=None vacía todo; con url, borra esa página y sus variantes con query (?...)."""
    try:
        with store.db() as c:
            if url is None:
                c.execute("DELETE FROM page_cache")
            else:
                like = _key(url).replace("%", r"\%").replace("_", r"\_") + "%"
                c.execute("DELETE FROM page_cache WHERE key LIKE ? ESCAPE '\\'", (like,))
    except Exception as exc:
        k.log("cache.invalidate: %s" % exc, k.xbmc.LOGWARNING)


def stats():
    try:
        with store.db() as c:
            n, size = c.execute("SELECT COUNT(*), COALESCE(SUM(LENGTH(body)),0) FROM page_cache").fetchone()
        return n, size
    except Exception:
        return 0, 0
