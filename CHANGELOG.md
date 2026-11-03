# Changelog

All notable changes to this fork are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.13.0] - 2026-11-03

### Fixed
- **F03:** `PlayerMonitor` no longer applies seek or saves progress from a failed playback to the next one. Added `onPlayBackError` that clears state, and marks older than 90 s or on non-Chomikuj files are discarded.
- **F04:** Service no longer dies on unexpected exceptions in a tick; warm-up runs in a daemon thread (Kodi shuts down without long delays).
- **F05:** `Session` converts `IncompleteRead`, `EOFError`, and `zlib.error` into `OSError` retriable with backoff.
- **F06:** Local search folds `ł`, `Ł`, `đ`, `Đ`, `ø`, `Ø`, `ß`, `æ`, `œ` before NFKD. "lodz" finds "Łódź", "walesa" finds "Wałęsa".
- **F08:** Downloads correctly handle `HTTP 416` with invalid `.part` (deletes and restarts once), preserve extension on long names (>150 chars), and treat disk full as a terminal error without retries.
- **F09:** Playback title without BBCode, HTML, size suffix, or `default_title` on both code paths (lightweight and with subtitles). `real_title` unified in `textutils.py` with behavior identical to the original.
- **F11:** `settings.xml` with non-empty defaults. Eliminates "error reading the default value" spam in Kodi 21 logs.

### Pending for 1.14.0
- **F10:** `clean()` breaks attributes with `&quot;` before parsing (blocked by real Chomikuj HTML fixtures).
- Cleanup: `import errno` in `downloadqueue._download_one` (move to imports block).
- Cleanup: `search._build_index` returns `None` on incomplete scan without explicit `notify`.
- Cleanup: `ReplaceSpecialChar` with the same character folding as `_norm`, if confirmed its output is not used for paths.

## [1.12.0] - 2026-11-03

### Fixed
- **F02 (critical):** STRM pruning and search index are no longer executed if the folder scan is interrupted (`WalkIncomplete`). Prevents a network failure, expired session, or manual cancellation from deleting valid `.strm` and `.nfo` files or saving a partial index as valid for 6 hours.
- `downloads.download_folder` now notifies when the folder was partially scanned and only queues what was read, instead of failing silently.

### Added
- Test harness with Kodi stubs (`tests/`, `conftest.py`, `pytest.ini`) to validate fixes without Kodi installed.
