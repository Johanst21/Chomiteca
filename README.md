# Chomiteca (fork)

A personal fork of [plugin.video.chomiteca](https://github.com/Leinad4Mind/Leinad4Mind-Kodi-Addons-Repo/tree/master/plugin.video.chomiteca) by Leinad4Mind.

This fork focuses on critical bug fixes, robustness improvements, data loss prevention, and modern Kodi 21 (Omega) compatibility. **It is not an official release** and is not affiliated with or endorsed by the original author or Chomikuj.pl.

## Features

- **Chomikuj.pl Browsing & Streaming**: Browse personal accounts, public folders, and play supported video and audio files directly in Kodi.
- **Kodi Library Integration**: Generate `.strm` files and metadata (`.nfo`) to integrate remote files seamlessly into your Kodi library.
- **Background Downloads**: Built-in queue manager for downloading media files with resume capability.
- **Search & Local Indexing**: Search for files and accounts, with optimized caching for responsive lookups.
- **Subtitle Integration**: Automatic and manual subtitle matching.

## Compatibility

- **Kodi**: Tested and supported on **Kodi 21 (Omega)** (Python 3).
- **Platforms**: Cross-platform (Windows, Linux, Android, macOS).

## Installation

1. Download the release ZIP file (`plugin.video.chomiteca-x.x.x.zip`) from the [Releases](https://github.com/johanst21/chomiteca/releases) page.
2. In Kodi, go to **Settings** → **Add-ons** → **Install from zip file**.
3. Select the downloaded ZIP file.
4. Wait for the add-on enabled notification.

## Changes & Releases

For detailed change history, see [CHANGELOG.md](CHANGELOG.md).

### 1.12.0 (Current Release)

- **Critical Fix (F02):** STRM library pruning and search indexing are now guarded against incomplete folder scans (`WalkIncomplete`). This completely prevents data loss (`.strm` and `.nfo` file deletion) and corrupted partial search caches when encountering network dropouts, expired sessions, or manual cancellations.
- **Download Queue Safeguards:** `downloads.download_folder` now notifies when a folder scan was aborted and only enqueues successfully parsed items instead of failing silently.
- **Test Suite:** Comprehensive test harness with Kodi Python stubs (`pytest`) for automated validation without requiring an active Kodi instance.

### Roadmap for 1.13.0

- **F03:** Prevent `PlayerMonitor` from carrying over stale seek / resume points from aborted or failed playbacks.
- **F04:** Protect the background service loop from dying on unhandled exceptions and ensure graceful Kodi shutdown without blocking on warm-up threads.
- **F05:** Retry handling in `Session` for `IncompleteRead`, `EOFError`, and `zlib.error`.
- **F06 - F10:** International character folding in search, 416 range handling in downloads, BBCode sanitization, and parser robustness.

## Development & Testing

Run unit tests locally using `pytest`:

```bash
pytest -q
```

All core library logic is decoupled and testable using the provided test stubs.

## License

This project is licensed under the **GNU General Public License v3.0 or later** (GPL-3.0-or-later). See [LICENSE](LICENSE) for the full license text.

## Disclaimer

This add-on accesses Chomikuj.pl through web scraping and public interfaces. There is no official relationship with Chomikuj.pl or Leinad4Mind. Use at your own discretion and responsibility.
