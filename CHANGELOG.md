# Changelog

All notable changes to this fork are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.14.0] - 2026-11-10

### Fixed
- Fixed a critical bug where folder pagination failed if a search had been performed previously. Removed dependency on the `temp.txt` temporary file; pagination is now strictly based on the current URL and mode.
- Fixed pagination handling for absolute URLs returned by Chomikuj and resolved layout false positives.
- Replaced empty defaults in `settings.xml` to eliminate "error reading the default value" log spam in Kodi 21.
- Moved `import errno` to module-level imports in `downloadqueue`.
- User is now notified when a search index cannot be completed due to a network error.

### Added
- Option to authenticate via imported browser cookies instead of storing the Chomikuj password in plain text in `accounts.json`.
  - New "Store password" setting in Settings → General.
  - Import cookies via text string or Netscape `cookies.txt` file.
  - Existing accounts with stored passwords continue to work unchanged.
- `Session.set_raw_cookie_string()` and `Session.import_mozilla_cookies()` helpers.
- `auth.verify_session()` to validate cookies.
- `Session.request()` now accepts an optional `timeout=` kwarg.
- Security & Authentication section in `README.md`.

### Changed
- Updated documentation to English for public release.

## [1.13.0] - 2026-11-03

### Fixed
- PlayerMonitor no longer applies seek or saves progress from a failed playback to the next one. Discard playback state older than 90 seconds or on non-Chomikuj files.
- Service no longer dies on unexpected exceptions; warm-up runs in a daemon thread so Kodi shuts down cleanly without delay.
- Session converts `IncompleteRead`, `EOFError`, and `zlib.error` into `OSError` retriable with exponential backoff.
- Local search folds special characters (`ł`, `Ł`, `đ`, `Đ`, `ø`, `Ø`, `ß`, `æ`, `œ`) before NFKD normalisation.
- Downloads properly handle HTTP 416 with invalid `.part` files (deletes and restarts), preserve file extensions on long filenames (>150 characters), and treat disk full as a terminal error without retrying.
- Unified playback title cleaning without BBCode, HTML, size suffixes, or `default_title`.
- Eliminated settings defaults log spam.

## [1.12.0] - 2026-11-03

### Fixed
- STRM pruning and search index are no longer executed if the folder scan is interrupted. Prevents data loss during network failures, expired sessions, or manual cancellation.
- Download folder function notifies when a folder was only partially scanned instead of failing silently.

### Added
- Test harness with Kodi stubs (`tests/`, `conftest.py`, `pytest.ini`) to validate fixes without Kodi installed.
