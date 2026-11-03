# -*- coding: utf-8 -*-
import io
import os
import shutil
import sqlite3
import tempfile
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
import xbmc

from resources.lib import downloadqueue, resolver, store
from resources.lib.downloadqueue import DiskFull, safe_name


def test_safe_name_preserva_extension():
    name = safe_name("a" * 300 + ".mkv")
    assert name.endswith(".mkv")
    assert len(name) <= 150


def test_safe_name_preserva_mp4():
    name = safe_name("b" * 200 + ".mp4")
    assert name.endswith(".mp4")
    assert len(name) <= 150


def test_safe_name_sin_extension():
    name = safe_name("a" * 300)
    assert len(name) <= 150
    assert not name.endswith(".")


def test_diskfull_no_hereda_oserror():
    assert not issubclass(DiskFull, OSError)


class _DummyResponse(io.BytesIO):
    def __init__(self, data=b"", status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.headers = headers or {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def temp_env(monkeypatch):
    tmpdir = tempfile.mkdtemp()
    db_file = os.path.join(tmpdir, "test.db")
    monkeypatch.setattr(store, "DB_PATH", db_file)
    store._READY.clear()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_416_borra_part_y_reintenta_una_vez(temp_env):
    dest = os.path.join(temp_env, "movie.mkv")
    part = dest + ".part"
    with open(part, "wb") as f:
        f.write(b"corrupt or complete part data")

    with store.db() as c:
        cur = c.execute(
            "INSERT INTO downloads(page_url, title, dest, status, ts) VALUES (?, ?, ?, ?, ?)",
            ("http://example.com/item", "movie.mkv", dest, "downloading", 123.0)
        )
        dl_id = cur.lastrowid

    monitor = xbmc.Monitor()

    dummy_link = MagicMock()
    dummy_link.url = "http://cdn.example.com/file.mkv"
    dummy_link.headers = {}

    err_416 = urllib.error.HTTPError(
        url=dummy_link.url,
        code=416,
        msg="Requested Range Not Satisfiable",
        hdrs=None,
        fp=io.BytesIO(b"")
    )
    ok_resp = _DummyResponse(b"full movie content", status=200)

    call_count = 0
    def fake_urlopen(req, timeout=30):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            assert "Range" in req.headers
            raise err_416
        else:
            assert "Range" not in req.headers
            return ok_resp

    with patch("resources.lib.downloadqueue._resolve", return_value=dummy_link), \
         patch("urllib.request.urlopen", side_effect=fake_urlopen):
        downloadqueue._download_one(dl_id, monitor)

    assert call_count == 2
    assert not os.path.exists(part)
    assert os.path.exists(dest)
    with open(dest, "rb") as f:
        assert f.read() == b"full movie content"

    assert downloadqueue._status(dl_id) == "done"


def test_diskfull_termina_sin_reintentar(temp_env):
    dest = os.path.join(temp_env, "movie.mkv")

    with store.db() as c:
        cur = c.execute(
            "INSERT INTO downloads(page_url, title, dest, status, ts) VALUES (?, ?, ?, ?, ?)",
            ("http://example.com/item", "movie.mkv", dest, "downloading", 123.0)
        )
        dl_id = cur.lastrowid

    monitor = xbmc.Monitor()

    dummy_link = MagicMock()
    dummy_link.url = "http://cdn.example.com/file.mkv"
    dummy_link.headers = {}

    # Total length 10MB
    data = b"x" * 1024
    ok_resp = _DummyResponse(data, status=200, headers={"Content-Length": "10485760"})

    mock_resolve = MagicMock(return_value=dummy_link)
    mock_urlopen = MagicMock(return_value=ok_resp)

    # Free space = 0 bytes
    dummy_usage = MagicMock(free=0, total=100000000, used=100000000)

    with patch("resources.lib.downloadqueue._resolve", mock_resolve), \
         patch("urllib.request.urlopen", mock_urlopen), \
         patch("shutil.disk_usage", return_value=dummy_usage):
        downloadqueue._download_one(dl_id, monitor)

    # Verificaciones:
    # 1. status == 'error'
    assert downloadqueue._status(dl_id) == "error"
    # 2. _resolve y urlopen fueron llamados exactamente 1 vez (sin reintentos en el loop de 3 intentos)
    assert mock_resolve.call_count == 1
    assert mock_urlopen.call_count == 1
    # 3. No se finalizó el fichero destino
    assert not os.path.exists(dest)
