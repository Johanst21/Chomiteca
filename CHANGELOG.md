# Changelog

All notable changes to this fork are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.14.0] - 2026-11-09

### Fixed
- **F27:** Pagination now handles the absolute URLs (`https://chomikuj.pl/...`) that Chomikuj actually returns, and ignores layout false positives (e.g. `uploadMinimalize right greenButton`). Next/Previous page buttons were non-functional before this fix.
- **F22:** Option to authenticate via imported browser cookies instead of storing the Chomikuj password in plain text in `accounts.json`. New setting "Store password" (Settings → General) toggles the behavior. Cookie import supports both paste-string and Netscape `cookies.txt` file. Existing accounts with stored passwords continue to work unchanged.
- **F12:** `import errno` moved to module imports in `downloadqueue` (cosmetic).
- **F13:** User is now notified when the search index cannot be completed due to a network error, instead of silently showing "0 results".

### Added
- New string IDs 40403–40415 for the cookie import UI.
- `Session.set_raw_cookie_string()` and `Session.import_mozilla_cookies()` helpers.
- `auth.verify_session()` to validate cookies without raising on network errors.
- `Session.request()` now accepts an optional `timeout=` kwarg.
- Security & Authentication section in `README.md`.

### Pending for 1.14.1
- **F17:** Harden login/pagination regex against real Chomikuj HTML.
- **F10:** `clean()` with `&quot;` (synthetic fixture; real Chomikuj rejects `"` in filenames).
- **F15:** `temp.txt` contaminating pagination after global search.
- **F18:** Low-priority cleanups (tools, subtitles, prefetch, state).
- Known issue: "reimport cookies for non-active account" shows a generic login-failure warning before the import flow (noted for polish).

## [1.13.0] - 2026-11-03

### Fixed
- `PlayerMonitor` no longer applies seek or saves progress from a failed playback to the next one. Added `onPlayBackError` that clears state, and marks older than 90 s or on non-Chomikuj files are discarded.
- Service no longer dies on unexpected exceptions in a tick; warm-up runs in a daemon thread (Kodi shuts down without long delays).
- `Session` converts `IncompleteRead`, `EOFError`, and `zlib.error` into `OSError` retriable with backoff.
- Local search folds `ł`, `Ł`, `đ`, `Đ`, `ø`, `Ø`, `ß`, `æ`, `œ` before NFKD. "lodz" finds "Łódź", "walesa" finds "Wałęsa".
- Downloads correctly handle `HTTP 416` with invalid `.part` (deletes and restarts once), preserve extension on long names (>150 chars), and treat disk full as a terminal error without retries.
- Playback title without BBCode, HTML, size suffix, or `default_title` on both code paths (lightweight and with subtitles). `real_title` unified in `textutils.py` with behavior identical to the original.
- `settings.xml` with non-empty defaults. Eliminates "error reading the default value" spam in Kodi 21 logs.

### Pending for 1.14.0
- HTML entity cleaning edge case with quotes before parsing (blocked by real Chomikuj HTML fixtures).
- Move `import errno` to top-level imports in `downloadqueue._download_one`.
- Add explicit notification when search scan is interrupted.
- Character folding parity in `ReplaceSpecialChar`.

## [1.12.0] - 2026-11-03

### Fixed
- Critical fix: STRM pruning and search index are no longer executed if the folder scan is interrupted (`WalkIncomplete`). Prevents a network failure, expired session, or manual cancellation from deleting valid `.strm` and `.nfo` files or saving a partial index as valid for 6 hours.
- `downloads.download_folder` now notifies when the folder was partially scanned and only queues what was read, instead of failing silently.

### Added
- Test harness with Kodi stubs (`tests/`, `conftest.py`, `pytest.ini`) to validate fixes without Kodi installed.
