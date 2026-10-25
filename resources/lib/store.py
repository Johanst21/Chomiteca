# -*- coding: utf-8 -*-
"""SQLite compartido entre el plugin y el servicio (caché, historial, metadatos, progreso, descargas, índice STRM)."""
import os
import sqlite3
from contextlib import contextmanager

from . import kodiutils as k

DB_PATH = os.path.join(k.PROFILE, "chomiteca.db")

_READY = set()
_SCHEMA = """
CREATE TABLE IF NOT EXISTS page_cache (key TEXT PRIMARY KEY, ts REAL NOT NULL, body BLOB);
CREATE TABLE IF NOT EXISTS search_history (id INTEGER PRIMARY KEY AUTOINCREMENT, term TEXT NOT NULL,
    ftype TEXT NOT NULL DEFAULT '', ts REAL NOT NULL, UNIQUE(term, ftype));
CREATE TABLE IF NOT EXISTS meta_cache (key TEXT PRIMARY KEY, ts REAL NOT NULL, data TEXT);
CREATE TABLE IF NOT EXISTS progress (key TEXT PRIMARY KEY, position REAL NOT NULL DEFAULT 0,
    total REAL NOT NULL DEFAULT 0, watched INTEGER NOT NULL DEFAULT 0, ts REAL NOT NULL, title TEXT);
CREATE TABLE IF NOT EXISTS downloads (id INTEGER PRIMARY KEY AUTOINCREMENT, page_url TEXT NOT NULL,
    title TEXT NOT NULL, dest TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'queued',
    done INTEGER NOT NULL DEFAULT 0, total INTEGER NOT NULL DEFAULT 0, error TEXT, ts REAL NOT NULL);
CREATE TABLE IF NOT EXISTS strm_index (path TEXT PRIMARY KEY, url TEXT NOT NULL, root TEXT NOT NULL, ts REAL NOT NULL);
"""


def _connect():
    os.makedirs(k.PROFILE, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    try:
        conn.execute("PRAGMA journal_mode=WAL")  # plugin y servicio escriben a la vez
    except sqlite3.DatabaseError:
        pass
    if DB_PATH not in _READY:
        conn.executescript(_SCHEMA)
        _READY.add(DB_PATH)
    return conn


@contextmanager
def db():
    """with store.db() as c: ...  (commit al salir; rollback si hay excepción; siempre cierra)."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
