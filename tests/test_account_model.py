# -*- coding: utf-8 -*-
import json
from resources.lib import accounts, kodiutils as k


def test_add_password_account(tmp_path, monkeypatch):
    test_file = str(tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", test_file)

    acc = accounts.add("user1", "pass1", label="User One")
    assert acc["auth_method"] == "password"
    assert acc["password"] == "pass1"
    assert acc["username"] == "user1"
    assert acc["label"] == "User One"

    loaded = accounts.load()
    assert len(loaded) == 1
    assert loaded[0]["auth_method"] == "password"
    assert loaded[0]["password"] == "pass1"


def test_add_cookie_account(tmp_path, monkeypatch):
    test_file = str(tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", test_file)

    acc = accounts.add("user2", "", label="User Two", auth_method="cookies")
    assert acc["auth_method"] == "cookies"
    assert acc["password"] == ""
    assert acc["username"] == "user2"

    loaded = accounts.load()
    assert len(loaded) == 1
    assert loaded[0]["auth_method"] == "cookies"
    assert loaded[0]["password"] == ""


def test_load_legacy_account_no_auth_method(tmp_path, monkeypatch):
    test_file = str(tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", test_file)

    legacy_data = [{"id": "x", "username": "u", "password": "p", "label": "l"}]
    with open(test_file, "w", encoding="utf-8") as fh:
        json.dump(legacy_data, fh)

    loaded = accounts.load()
    assert len(loaded) == 1
    assert loaded[0]["auth_method"] == "password"
    assert loaded[0]["username"] == "u"
    assert loaded[0]["password"] == "p"


def test_load_does_not_rewrite_file(tmp_path, monkeypatch):
    test_file = str(tmp_path / "accounts.json")
    monkeypatch.setattr(accounts, "ACCOUNTS_FILE", test_file)

    original_content = '[{"id": "x", "username": "u", "password": "p", "label": "l"}]'
    with open(test_file, "w", encoding="utf-8") as fh:
        fh.write(original_content)

    loaded = accounts.load()
    assert loaded[0]["auth_method"] == "password"

    with open(test_file, "r", encoding="utf-8") as fh:
        raw_after = fh.read()

    assert raw_after == original_content
    assert "auth_method" not in raw_after
