# -*- coding: utf-8 -*-
from unittest.mock import MagicMock
import pytest

from resources.lib import auth, common


def test_login_password_account_uses_password(monkeypatch):
    monkeypatch.setattr(
        common,
        "get_active_account_details",
        lambda: {"id": "1", "username": "alice", "password": "secret", "label": "Alice", "auth_method": "password"},
    )
    called = []

    def fake_create_login_single(user, pwd, site, label, defora_flag=False):
        called.append((user, pwd, site, label))
        return True

    monkeypatch.setattr(common, "create_login_single", fake_create_login_single)
    # Ensure cookies file doesn't exist so it calls create_login_single
    monkeypatch.setattr(common.os.path, "exists", lambda p: False)

    res = common.login()
    assert res is True
    assert len(called) == 1
    assert called[0][0] == "alice"
    assert called[0][1] == "secret"


def test_login_cookie_account_no_cookies_returns_false(monkeypatch):
    monkeypatch.setattr(
        common,
        "get_active_account_details",
        lambda: {"id": "2", "username": "bob", "password": "", "label": "Bob", "auth_method": "cookies"},
    )
    mock_session = MagicMock()
    mock_session.has_cookies.return_value = False
    monkeypatch.setattr(common, "make_session", lambda: mock_session)

    res = common.login()
    assert res is False


def test_login_cookie_account_with_valid_cookies(monkeypatch):
    monkeypatch.setattr(
        common,
        "get_active_account_details",
        lambda: {"id": "3", "username": "carol", "password": "", "label": "Carol", "auth_method": "cookies"},
    )
    mock_session = MagicMock()
    mock_session.has_cookies.return_value = True
    monkeypatch.setattr(common, "make_session", lambda: mock_session)
    monkeypatch.setattr(auth, "verify_session", lambda s, u: True)

    res = common.login()
    assert res is True


def test_login_cookie_account_with_expired_cookies(monkeypatch):
    monkeypatch.setattr(
        common,
        "get_active_account_details",
        lambda: {"id": "4", "username": "dave", "password": "", "label": "Dave", "auth_method": "cookies"},
    )
    mock_session = MagicMock()
    mock_session.has_cookies.return_value = True
    monkeypatch.setattr(common, "make_session", lambda: mock_session)
    monkeypatch.setattr(auth, "verify_session", lambda s, u: False)

    res = common.login()
    assert res is False
