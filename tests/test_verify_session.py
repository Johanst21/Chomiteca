# -*- coding: utf-8 -*-
from unittest.mock import MagicMock
from resources.lib import auth
from resources.lib.session import Session


def test_verify_session_valid_marker(tmp_path):
    sess = Session(str(tmp_path / "c.lwp"))
    sess.request = MagicMock(return_value=b'{"LoggedIn":true,"IsSuccess":true}')
    assert auth.verify_session(sess) is True


def test_verify_session_valid_title(tmp_path):
    sess = Session(str(tmp_path / "c.lwp"))
    sess.request = MagicMock(return_value=b"<html><head><title>Pliki u\xc5\xbcytkownika testuser - Chomikuj.pl</title></head></html>")
    assert auth.verify_session(sess, username="testuser") is True


def test_verify_session_wrong_user(tmp_path):
    sess = Session(str(tmp_path / "c.lwp"))
    sess.request = MagicMock(return_value=b'{"LoggedIn":true} <html><title>Pliki u\xc5\xbcytkownika otheruser</title></html>')
    assert auth.verify_session(sess, username="testuser") is False


def test_verify_session_no_markers(tmp_path):
    sess = Session(str(tmp_path / "c.lwp"))
    sess.request = MagicMock(return_value=b"<html><title>Logowanie</title><body>login form</body></html>")
    assert auth.verify_session(sess) is False


def test_verify_session_network_error(tmp_path):
    sess = Session(str(tmp_path / "c.lwp"))
    sess.request = MagicMock(side_effect=OSError("connection refused"))
    assert auth.verify_session(sess) is False


def test_verify_session_empty_response(tmp_path):
    sess = Session(str(tmp_path / "c.lwp"))
    sess.request = MagicMock(return_value=b"")
    assert auth.verify_session(sess) is False

    sess.request = MagicMock(return_value=None)
    assert auth.verify_session(sess) is False


def test_verify_session_passes_timeout(tmp_path):
    sess = Session(str(tmp_path / "c.lwp"))
    sess.request = MagicMock(return_value=b'{"LoggedIn":true}')
    auth.verify_session(sess, timeout=7)
    sess.request.assert_called_once_with("https://chomikuj.pl/", timeout=7)
