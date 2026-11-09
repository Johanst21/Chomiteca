# -*- coding: utf-8 -*-
from unittest.mock import MagicMock
import pytest

from resources.lib import accounts_ui, auth


def test_import_flow_paste_success(monkeypatch):
    mock_dialog = MagicMock()
    mock_dialog.select.return_value = 0  # Paste option
    monkeypatch.setattr(accounts_ui.xbmcgui, "Dialog", lambda: mock_dialog)

    mock_kb = MagicMock()
    mock_kb.isConfirmed.return_value = True
    mock_kb.getText.return_value = "PHPSESSID=abc12345"
    monkeypatch.setattr(accounts_ui.xbmc, "Keyboard", lambda default="", heading="", hidden=False: mock_kb, raising=False)

    mock_session = MagicMock()
    mock_session.set_raw_cookie_string.return_value = (1, [])
    monkeypatch.setattr(auth, "verify_session", lambda s, u: True)

    ok, reason = accounts_ui.import_cookies_flow("user1", session=mock_session)
    assert ok is True
    assert reason == "ok"
    mock_session.set_raw_cookie_string.assert_called_once_with("PHPSESSID=abc12345")


def test_import_flow_paste_cancelled(monkeypatch):
    mock_dialog = MagicMock()
    mock_dialog.select.return_value = 0
    monkeypatch.setattr(accounts_ui.xbmcgui, "Dialog", lambda: mock_dialog)

    mock_kb = MagicMock()
    mock_kb.isConfirmed.return_value = False
    mock_kb.getText.return_value = ""
    monkeypatch.setattr(accounts_ui.xbmc, "Keyboard", lambda default="", heading="", hidden=False: mock_kb, raising=False)

    mock_session = MagicMock()
    ok, reason = accounts_ui.import_cookies_flow("user1", session=mock_session)
    assert ok is False
    assert reason == "cancelled"


def test_import_flow_file_success(monkeypatch):
    mock_dialog = MagicMock()
    mock_dialog.select.return_value = 1  # File browse option
    monkeypatch.setattr(accounts_ui.xbmcgui, "Dialog", lambda: mock_dialog)

    monkeypatch.setattr(accounts_ui.DIALOG_MESSAGE, "browse", lambda typ, heading, shares, mask: "/path/to/cookies.txt", raising=False)

    mock_session = MagicMock()
    mock_session.import_mozilla_cookies.return_value = (2, 0)
    monkeypatch.setattr(auth, "verify_session", lambda s, u: True)

    ok, reason = accounts_ui.import_cookies_flow("user1", session=mock_session)
    assert ok is True
    assert reason == "ok"
    mock_session.import_mozilla_cookies.assert_called_once_with("/path/to/cookies.txt")


def test_import_flow_no_cookies_imported(monkeypatch):
    mock_dialog = MagicMock()
    mock_dialog.select.return_value = 0
    monkeypatch.setattr(accounts_ui.xbmcgui, "Dialog", lambda: mock_dialog)

    mock_kb = MagicMock()
    mock_kb.isConfirmed.return_value = True
    mock_kb.getText.return_value = "invalid; format"
    monkeypatch.setattr(accounts_ui.xbmc, "Keyboard", lambda default="", heading="", hidden=False: mock_kb, raising=False)

    mock_session = MagicMock()
    mock_session.set_raw_cookie_string.return_value = (0, ["error"])

    ok, reason = accounts_ui.import_cookies_flow("user1", session=mock_session)
    assert ok is False
    assert reason == "no_cookies_imported"


def test_import_flow_verify_fail_retry_yes(monkeypatch):
    call_count = {"select": 0, "verify": 0}

    def fake_select(heading, options):
        call_count["select"] += 1
        return 0

    mock_dialog = MagicMock()
    mock_dialog.select.side_effect = fake_select
    monkeypatch.setattr(accounts_ui.xbmcgui, "Dialog", lambda: mock_dialog)

    mock_kb = MagicMock()
    mock_kb.isConfirmed.return_value = True
    mock_kb.getText.return_value = "PHPSESSID=session"
    monkeypatch.setattr(accounts_ui.xbmc, "Keyboard", lambda default="", heading="", hidden=False: mock_kb, raising=False)

    def fake_yesno(heading, msg):
        return True

    monkeypatch.setattr(accounts_ui.DIALOG_MESSAGE, "yesno", fake_yesno, raising=False)

    mock_session = MagicMock()
    mock_session.set_raw_cookie_string.return_value = (1, [])

    def fake_verify(s, u):
        call_count["verify"] += 1
        return call_count["verify"] > 1

    monkeypatch.setattr(auth, "verify_session", fake_verify)

    ok, reason = accounts_ui.import_cookies_flow("user1", session=mock_session)
    assert ok is True
    assert reason == "ok"
    assert call_count["select"] == 2
    assert call_count["verify"] == 2


def test_import_flow_verify_fail_retry_no(monkeypatch):
    mock_dialog = MagicMock()
    mock_dialog.select.return_value = 0
    monkeypatch.setattr(accounts_ui.xbmcgui, "Dialog", lambda: mock_dialog)

    mock_kb = MagicMock()
    mock_kb.isConfirmed.return_value = True
    mock_kb.getText.return_value = "PHPSESSID=session"
    monkeypatch.setattr(accounts_ui.xbmc, "Keyboard", lambda default="", heading="", hidden=False: mock_kb, raising=False)

    monkeypatch.setattr(accounts_ui.DIALOG_MESSAGE, "yesno", lambda heading, msg: False, raising=False)

    mock_session = MagicMock()
    mock_session.set_raw_cookie_string.return_value = (1, [])
    monkeypatch.setattr(auth, "verify_session", lambda s, u: False)

    ok, reason = accounts_ui.import_cookies_flow("user1", session=mock_session)
    assert ok is False
    assert reason == "verify_failed"


def test_import_flow_real_session_empty_cookie_triggers_no_imported(tmp_path, monkeypatch):
    from resources.lib.session import Session

    cookie_file = str(tmp_path / "cookies.lwp")
    real_session = Session(cookie_file)

    mock_dialog = MagicMock()
    mock_dialog.select.return_value = 0
    monkeypatch.setattr(accounts_ui.xbmcgui, "Dialog", lambda: mock_dialog)

    mock_kb = MagicMock()
    mock_kb.isConfirmed.return_value = True
    # An input without valid key=value format parses into 0 cookies
    mock_kb.getText.return_value = "invalid_cookie_format_without_equals"
    monkeypatch.setattr(accounts_ui.xbmc, "Keyboard", lambda default="", heading="", hidden=False: mock_kb, raising=False)

    ok, reason = accounts_ui.import_cookies_flow("user1", session=real_session)
    assert ok is False
    assert reason == "no_cookies_imported"

