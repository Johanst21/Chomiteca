# -*- coding: utf-8 -*-
from resources.lib.session import Session


def test_set_raw_cookie_string_basic(tmp_path):
    sess = Session(str(tmp_path / "cookies.lwp"))
    imported, skipped = sess.set_raw_cookie_string("PHPSESSID=abc; chomikujpl=def")
    assert imported == 2
    assert skipped == []
    assert sess.has_cookies()
    cookie_names = {c.name for c in sess.jar}
    assert cookie_names == {"PHPSESSID", "chomikujpl"}


def test_set_raw_cookie_string_invalid(tmp_path):
    sess = Session(str(tmp_path / "cookies.lwp"))
    imported, skipped = sess.set_raw_cookie_string("garbage_no_equals; PHPSESSID=abc")
    assert imported == 1
    assert "garbage_no_equals" in skipped
    assert {c.name for c in sess.jar} == {"PHPSESSID"}


def test_set_raw_cookie_string_empty(tmp_path):
    sess = Session(str(tmp_path / "cookies.lwp"))
    imported, skipped = sess.set_raw_cookie_string("")
    assert imported == 0
    assert skipped == []
    assert not sess.has_cookies()

    imported2, skipped2 = sess.set_raw_cookie_string("   ")
    assert imported2 == 0
    assert skipped2 == []


def test_set_raw_cookie_string_saves_to_disk(tmp_path):
    cookie_file = tmp_path / "cookies.lwp"
    sess = Session(str(cookie_file))
    imported, skipped = sess.set_raw_cookie_string("PHPSESSID=mysecrettoken")
    assert imported == 1
    assert cookie_file.exists()
    content = cookie_file.read_text(encoding="utf-8")
    assert "PHPSESSID" in content
    assert "mysecrettoken" in content


def test_import_mozilla_cookies_basic(tmp_path):
    cookies_txt = tmp_path / "cookies.txt"
    # Netscape HTTP Cookie File format:
    # domain, flag (include subdomains), path, secure, expiration, name, value (separated by tabs)
    lines = [
        "# Netscape HTTP Cookie File",
        ".chomikuj.pl\tTRUE\t/\tTRUE\t9999999999\tPHPSESSID\tabc",
        ".chomikuj.pl\tTRUE\t/\tTRUE\t9999999999\tchomikujpl\tdef",
        ".example.com\tTRUE\t/\tFALSE\t9999999999\tfoo\tbar",
    ]
    cookies_txt.write_text("\n".join(lines) + "\n", encoding="utf-8")

    sess = Session(str(tmp_path / "cookies.lwp"))
    imported, skipped = sess.import_mozilla_cookies(str(cookies_txt))
    assert imported == 2
    assert skipped == 1
    names = {c.name for c in sess.jar}
    assert names == {"PHPSESSID", "chomikujpl"}


def test_import_mozilla_cookies_missing_file(tmp_path):
    sess = Session(str(tmp_path / "cookies.lwp"))
    imported, skipped = sess.import_mozilla_cookies(str(tmp_path / "nonexistent.txt"))
    assert imported == 0
    assert skipped == 0
