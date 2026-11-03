# Chomiteca

<p align="center">
  <img src="icon.png" alt="Chomiteca Logo" width="200"/>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPL v3"></a>
  <a href="https://github.com/johanst21/chomiteca/releases/tag/v1.12.0"><img src="https://img.shields.io/badge/Release-v1.12.0-green.svg" alt="Release v1.12.0"></a>
</p>

A Kodi video/audio add-on for browsing, streaming, and managing content from Chomikuj.pl.

Personal fork of [plugin.video.chomiteca](https://github.com/Leinad4Mind/Leinad4Mind-Kodi-Addons-Repo/tree/master/plugin.video.chomiteca) by Leinad4Mind, focusing on critical bug fixes, robustness improvements, data loss prevention, and modern Kodi 21 (Omega) compatibility. **It is not an official release** and is not affiliated with or endorsed by the original author or Chomikuj.pl.

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

## Cambios respecto al upstream

Ver [CHANGELOG.md](CHANGELOG.md).

### 1.13.0 (esta release)

- **F03:** PlayerMonitor no contamina la siguiente reproducción tras un fallo.
- **F04:** servicio robusto ante excepciones; warm-up no bloquea el cierre de Kodi.
- **F05:** Session reintenta `IncompleteRead`/`EOFError`/`zlib.error`.
- **F06:** búsqueda local pliega `ł`, `đ`, `ø`, `ß`, `æ`, `œ`.
- **F08:** descargas robustas (416, extensión, disco lleno).
- **F09:** título de reproducción limpio (sin BBCode, sin `default_title`, sin pérdida de unicode).
- **F11:** settings.xml sin defaults vacíos (log limpio).

### 1.12.0

- **F02 (crítico):** la poda de STRM y el índice de búsqueda ya no se ejecutan si el escaneo se interrumpe.

### Pendiente para 1.14.0

- F10: `clean()` con comillas (requiere fixtures HTML).
- Limpieza menor documentada en CHANGELOG.

## Estado del proyecto

Fork en desarrollo activo. La 1.13.0 cierra los bugs críticos y altos identificados en la revisión del código original. Pendiente para 1.14.0: F10 (requiere fixtures HTML) y limpieza menor.

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
