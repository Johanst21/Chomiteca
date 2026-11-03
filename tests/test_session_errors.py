# -*- coding: utf-8 -*-
import http.client
import pytest
import zlib
from unittest.mock import MagicMock

from resources.lib.session import Session


class FakeResponse:
    def __init__(self, raw=b"ok", headers=None):
        self._raw = raw
        self.headers = headers or {}

    def read(self):
        if isinstance(self._raw, Exception):
            raise self._raw
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


def test_request_once_incomplete_read_raises_oserror(tmp_path):
    cookie_path = str(tmp_path / "cookies.lwp")
    sess = Session(cookie_path)
    mock_opener = MagicMock()
    mock_opener.open.return_value = FakeResponse(raw=http.client.IncompleteRead(b""))
    sess._opener = mock_opener

    with pytest.raises(OSError) as exc_info:
        sess._request_once("https://example.com/test")

    assert "IncompleteRead" in str(exc_info.value)


def test_session_request_retries_on_incomplete_read(tmp_path):
    cookie_path = str(tmp_path / "cookies.lwp")
    sess = Session(cookie_path)
    mock_opener = MagicMock()
    # 1st call raises IncompleteRead, 2nd call returns valid response
    resp1 = FakeResponse(raw=http.client.IncompleteRead(b""))
    resp2 = FakeResponse(raw=b"success")
    mock_opener.open.side_effect = [resp1, resp2]
    sess._opener = mock_opener

    result = sess.request("https://example.com/test", retries=2)
    assert result == b"success"
    assert mock_opener.open.call_count == 2


def test_request_once_zlib_error_raises_oserror(tmp_path):
    cookie_path = str(tmp_path / "cookies.lwp")
    sess = Session(cookie_path)
    mock_opener = MagicMock()
    # Invalid compressed data with deflate header to trigger zlib.error on decompression
    mock_opener.open.return_value = FakeResponse(raw=b"not-deflate-data", headers={"Content-Encoding": "deflate"})
    sess._opener = mock_opener

    with pytest.raises(OSError) as exc_info:
        sess._request_once("https://example.com/test")

    assert "Fallo de lectura/descompresión de red" in str(exc_info.value)
    assert "error" in str(exc_info.value).lower()


def test_request_once_eof_error_raises_oserror(tmp_path):
    cookie_path = str(tmp_path / "cookies.lwp")
    sess = Session(cookie_path)
    mock_opener = MagicMock()
    mock_opener.open.return_value = FakeResponse(raw=EOFError("unexpected EOF"))
    sess._opener = mock_opener

    with pytest.raises(OSError) as exc_info:
        sess._request_once("https://example.com/test")

    assert "EOFError" in str(exc_info.value)


def test_request_once_success_unchanged(tmp_path):
    cookie_path = str(tmp_path / "cookies.lwp")
    sess = Session(cookie_path)
    mock_opener = MagicMock()
    mock_opener.open.return_value = FakeResponse(raw=b"hello world")
    sess._opener = mock_opener

    result = sess._request_once("https://example.com/test")
    assert result == b"hello world"
