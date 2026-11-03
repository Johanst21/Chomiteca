from resources.lib.playstate import _parse_mark


def test_parse_mark_fresh():
    assert _parse_mark("chomikuj:abc123|100", now=150, max_age=90) == "chomikuj:abc123"


def test_parse_mark_expired():
    assert _parse_mark("chomikuj:abc123|100", now=200, max_age=90) is None


def test_parse_mark_empty():
    assert _parse_mark("", now=150) is None


def test_parse_mark_none():
    assert _parse_mark(None, now=150) is None


def test_parse_mark_old_format():
    assert _parse_mark("chomikuj:abc123", now=150) is None


def test_parse_mark_invalid_ts():
    assert _parse_mark("chomikuj:abc123|notanumber", now=150) is None


def test_parse_mark_negative_age():
    assert _parse_mark("chomikuj:abc123|200", now=150) == "chomikuj:abc123"
