# Chomiteca (fork)

Personal fork of [plugin.video.chomiteca](https://github.com/Leinad4Mind/Leinad4Mind-Kodi-Addons-Repo/tree/master/plugin.video.chomiteca) by Leinad4Mind.

This fork includes bug fixes and robustness improvements. **It is not the official version** and is not endorsed by the original author.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE).

## Installation

1. Download the ZIP from the [latest release](https://github.com/johanst21/chomiteca/releases/latest).
2. In Kodi: **Settings → Add-ons → Install from zip file**.
3. Select the downloaded ZIP.

Compatible with Kodi 21 (Omega). Not tested on earlier versions.

## Changes from upstream

See [CHANGELOG.md](CHANGELOG.md) for the full list.

### 1.13.0 (current release)

- **F03:** PlayerMonitor no longer carries over seek or progress from a failed playback to the next one.
- **F04:** Service is robust against unexpected exceptions in a tick; warm-up runs in a daemon thread (no shutdown delay).
- **F05:** Session retries `IncompleteRead` / `EOFError` / `zlib.error` as `OSError` with backoff.
- **F06:** Local search folds `ł`, `Ł`, `đ`, `Đ`, `ø`, `Ø`, `ß`, `æ`, `œ` before NFKD. "lodz" finds "Łódź", "walesa" finds "Wałęsa".
- **F08:** Downloads handle HTTP 416 (invalid `.part`), preserve extension on long names (>150 chars), and treat disk full as a terminal error without retries.
- **F09:** Playback title without BBCode, HTML, size suffix, or `default_title` on both code paths.
- **F11:** `settings.xml` without empty defaults. No more "error reading the default value" spam in Kodi 21 logs.

### 1.12.0

- **F02 (critical):** STRM pruning and search index are no longer executed if the folder scan is interrupted. Prevents data loss.

### Pending for 1.14.0

- **F10:** `clean()` breaks attributes with `&quot;` before parsing (blocked by real Chomikuj HTML fixtures).
- Minor cleanup documented in [CHANGELOG.md](CHANGELOG.md).

## Project status

Active development fork. 1.13.0 closes all critical and high-severity bugs identified in the original code review. Pending for 1.14.0: F10 (requires HTML fixtures) and minor cleanup.

## Disclaimer

This addon accesses Chomikuj.pl via scraping. There is no official relationship with Chomikuj.pl or with Leinad4Mind. Use at your own risk.
