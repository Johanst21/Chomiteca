# -*- coding: utf-8 -*-
"""Cola de descargas persistente. El plugin encola; el servicio (Manager) descarga con reanudación."""
import os
import random
import re
import shutil
import threading
import time
import urllib.error
import urllib.request

import xbmc
import xbmcvfs

from . import accounts, auth, kodiutils as k, resolver, store, strings
from .session import make_session

CHUNK = 256 * 1024
ACTIVE = ("queued", "downloading", "paused")


class DiskFull(Exception):
    """Error terminal: no hay espacio en disco. No reintentar."""
    pass


def safe_name(name, default="file", max_len=150):
    if not name:
        return default
    name = re.sub(r"\[/?(?:COLOR|B|I)[^\]]*\]", "", str(name))
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
    if not name:
        return default
    stem, ext = os.path.splitext(name)
    budget = max_len - len(ext)
    if budget < 1:
        budget = 1
    stem = stem[:budget]
    return (stem + ext) or default


def enqueue(page_url, title, dest_root, rel_dir=""):
    """Añade a la cola (sin duplicar si ya hay una activa con el mismo origen y destino)."""
    parts = [safe_name(p) for p in re.split(r"[\\/]+", rel_dir) if p.strip()]
    dest = os.path.join(dest_root, *parts, safe_name(title))
    with store.db() as c:
        row = c.execute("SELECT id FROM downloads WHERE page_url=? AND dest=? AND status IN ('queued','downloading','paused')",
                        (page_url, dest)).fetchone()
        if row:
            return row[0]
        cur = c.execute("INSERT INTO downloads(page_url, title, dest, status, ts) VALUES (?,?,?,?,?)",
                        (page_url, title, dest, "queued", time.time()))
        return cur.lastrowid


def list_all():
    with store.db() as c:
        return c.execute("SELECT id, title, dest, status, done, total, error FROM downloads ORDER BY id").fetchall()


def _set(download_id, **fields):
    cols = ", ".join("%s=?" % f for f in fields)
    with store.db() as c:
        c.execute("UPDATE downloads SET %s WHERE id=?" % cols, list(fields.values()) + [download_id])


def _status(download_id):
    with store.db() as c:
        row = c.execute("SELECT status FROM downloads WHERE id=?", (download_id,)).fetchone()
    return row[0] if row else None


def _part_path(dest):
    return dest + ".part"


def act(download_id, action):
    """pause | resume | cancel | retry | remove | clear | pause_all | resume_all"""
    with store.db() as c:
        if action == "clear":
            c.execute("DELETE FROM downloads WHERE status IN ('done','canceled','error')")
        elif action == "pause_all":
            c.execute("UPDATE downloads SET status='paused' WHERE status IN ('queued','downloading')")
        elif action == "resume_all":
            c.execute("UPDATE downloads SET status='queued' WHERE status='paused'")
        else:
            row = c.execute("SELECT dest, status FROM downloads WHERE id=?", (download_id,)).fetchone()
            if not row:
                return
            dest, status = row
            if action == "pause" and status in ("queued", "downloading"):
                c.execute("UPDATE downloads SET status='paused' WHERE id=?", (download_id,))
            elif action in ("resume", "retry") and status in ("paused", "error", "canceled"):
                c.execute("UPDATE downloads SET status='queued', error=NULL WHERE id=?", (download_id,))
            elif action == "cancel" and status in ACTIVE:
                c.execute("UPDATE downloads SET status='canceled' WHERE id=?", (download_id,))
                _remove_part(dest)
            elif action == "remove":
                if status in ACTIVE:
                    _remove_part(dest)
                c.execute("DELETE FROM downloads WHERE id=?", (download_id,))


def _remove_part(dest):
    try:
        os.remove(_part_path(dest))
    except OSError:
        pass


class _Sink:
    """Escritura local con reanudación; fuera del sistema de ficheros local (smb://, nfs://...) sin reanudar."""

    def __init__(self, part, resume_from):
        self.local = "://" not in part
        self.offset = 0
        if self.local:
            os.makedirs(os.path.dirname(part), exist_ok=True)
            if resume_from and os.path.exists(part):
                self.offset = os.path.getsize(part)
                self.fh = open(part, "ab")
            else:
                self.fh = open(part, "wb")
        else:
            xbmcvfs.mkdirs(os.path.dirname(part) + "/")
            self.fh = xbmcvfs.File(part, "w")

    def write(self, data):
        self.fh.write(data if self.local else bytearray(data))

    def close(self):
        self.fh.close()


def _finalize(part, dest):
    if "://" in dest:
        xbmcvfs.delete(dest)
        if not xbmcvfs.rename(part, dest):
            raise OSError("rename failed")
    else:
        os.replace(part, dest)


def _resolve(page_url):
    for attempt in (0, 1):
        session = make_session()
        if not session.has_cookies():
            account = accounts.active()
            if not account:
                raise resolver.ResolveError(k.tr(40109, "No active account"))
            auth.login(session, account)
        try:
            return resolver.resolve(session, page_url)
        except resolver.ResolveError as exc:
            if attempt == 0 and exc.relogin:
                session.clear()
                continue
            raise


def _download_one(download_id, monitor):
    with store.db() as c:
        row = c.execute("SELECT page_url, dest FROM downloads WHERE id=?", (download_id,)).fetchone()
    if not row:
        return
    page_url, dest = row
    part = _part_path(dest)
    last_error = None
    for attempt in range(3):
        if monitor.abortRequested() or _status(download_id) != "downloading":
            return
        try:
            link = _resolve(page_url)  # el enlace es temporal: se resuelve al empezar y al reintentar
            have = os.path.getsize(part) if "://" not in part and os.path.exists(part) else 0
            headers = dict(link.headers)
            if have:
                headers["Range"] = "bytes=%d-" % have
            try:
                resp_cm = urllib.request.urlopen(urllib.request.Request(link.url, headers=headers), timeout=30)
            except urllib.error.HTTPError as exc:
                if exc.code == 416 and have > 0:
                    try:
                        os.remove(part)
                    except FileNotFoundError:
                        pass
                    k.log("Download: 416 con .part existente; se reinicia desde cero: %s" % link.url, xbmc.LOGWARNING)
                    have = 0
                    headers.pop("Range", None)
                    resp_cm = urllib.request.urlopen(urllib.request.Request(link.url, headers=headers), timeout=30)
                else:
                    raise
            with resp_cm as resp:
                status = getattr(resp, "status", 200)
                length = int(resp.headers.get("Content-Length") or 0)
                if have and status == 206:
                    total = have + length
                else:
                    have, total = 0, length  # el servidor no admite Range: empezar de cero
                if total:
                    probe = os.path.dirname(dest) if os.path.isdir(os.path.dirname(dest)) else os.path.expanduser("~")
                    try:
                        if "://" not in dest and shutil.disk_usage(probe).free < (total - have) + 50 * 1024 * 1024:
                            raise DiskFull(strings.t(40343))
                    except FileNotFoundError:
                        pass
                sink = _Sink(part, resume_from=have > 0)
                done, tick = have, time.time()
                try:
                    while True:
                        if monitor.abortRequested():
                            _set(download_id, status="queued", done=done)  # se reanuda al volver a abrir Kodi
                            return
                        chunk = resp.read(CHUNK)
                        if not chunk:
                            break
                        sink.write(chunk)
                        done += len(chunk)
                        if time.time() - tick >= 1:
                            tick = time.time()
                            if _status(download_id) != "downloading":  # pausa/cancelación desde la interfaz
                                _set(download_id, done=done, total=total)
                                return
                            _set(download_id, done=done, total=total)
                finally:
                    sink.close()
            if total and done < total:
                raise OSError("incomplete: %d/%d" % (done, total))
            _finalize(part, dest)
            _set(download_id, status="done", done=done, total=max(total, done), error=None)
            k.log("Download finished: %s" % os.path.basename(dest))
            return
        except DiskFull as exc:
            k.log("Download: disco lleno, abortando sin reintentar: %s" % exc, xbmc.LOGERROR)
            _set(download_id, status="error", error=str(exc)[:200])
            return
        except resolver.ResolveError as exc:
            _set(download_id, status="error", error=str(exc)[:200])  # no se arregla reintentando
            return
        except urllib.error.HTTPError as exc:
            last_error = strings.t(40349) if exc.code in (402, 429) else "HTTP %s" % exc.code
            if exc.code in (401, 403, 404, 410, 402, 416):
                break
        except OSError as exc:
            import errno
            if exc.errno == errno.ENOSPC:
                k.log("Download: disco lleno, abortando sin reintentar: %s" % exc, xbmc.LOGERROR)
                _set(download_id, status="error", error=str(exc)[:200])
                return
            last_error = str(exc)
        except urllib.error.URLError as exc:
            last_error = str(exc)
        if attempt < 2 and monitor.waitForAbort(2 * (2 ** attempt) * (0.5 + random.random())):
            return
    if _status(download_id) == "downloading":
        _set(download_id, status="error", error=(last_error or "error")[:200])
        k.log("Download failed: %s" % last_error, xbmc.LOGWARNING)


class Manager:
    """Se ejecuta en el servicio: arranca hasta N descargas simultáneas y respeta pausa/cancelación."""

    def __init__(self, monitor):
        self.monitor = monitor
        self.threads = {}
        try:
            with store.db() as c:  # tras un cierre brusco, lo que estaba descargando vuelve a la cola
                c.execute("UPDATE downloads SET status='queued' WHERE status='downloading'")
        except Exception as exc:
            k.log("Manager init: %s" % exc, xbmc.LOGWARNING)

    def _max(self):
        try:
            return max(1, min(5, int(float(k.ADDON.getSetting("max_downloads") or 2))))
        except ValueError:
            return 2

    def tick(self):
        self.threads = {i: t for i, t in self.threads.items() if t.is_alive()}
        free = self._max() - len(self.threads)
        if free <= 0:
            return
        try:
            with store.db() as c:
                rows = c.execute("SELECT id FROM downloads WHERE status='queued' ORDER BY id LIMIT ?", (free,)).fetchall()
                for (download_id,) in rows:
                    c.execute("UPDATE downloads SET status='downloading' WHERE id=?", (download_id,))
        except Exception as exc:
            k.log("Manager.tick: %s" % exc, xbmc.LOGWARNING)
            return
        for (download_id,) in rows:
            thread = threading.Thread(target=self._run, args=(download_id,), daemon=True)
            self.threads[download_id] = thread
            thread.start()

    def _run(self, download_id):
        try:
            _download_one(download_id, self.monitor)
        except Exception as exc:  # una descarga rota nunca debe tumbar el servicio
            k.log("Download thread crashed: %r" % exc, xbmc.LOGERROR)
            try:
                _set(download_id, status="error", error=str(exc)[:200])
            except Exception:
                pass
