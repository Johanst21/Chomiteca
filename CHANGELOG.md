# Changelog

Todas las modificaciones relevantes de este fork se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado es [SemVer](https://semver.org/lang/es/).

## [1.12.0] - 2026-11-03

### Corregido
- **F02 (crítico):** la poda de STRM y el índice de búsqueda ya no se ejecutan si el escaneo de carpeta se interrumpe a mitad (`WalkIncomplete`). Evita que un fallo de red, sesión caducada o cancelación manual borre `.strm` y `.nfo` válidos o guarde un índice parcial como bueno durante 6 horas.
- `downloads.download_folder` ahora notifica cuando la carpeta se escaneó parcialmente y solo encola lo que se pudo leer, en vez de fallar silenciosamente.

### Añadido
- Arnés de tests con stubs de Kodi (`tests/`, `conftest.py`, `pytest.ini`) para poder validar los fixes sin Kodi instalado.

## [Unreleased] — pendiente para 1.13.0

### Por corregir
- **F03:** `PlayerMonitor` aplica seek y progreso de una reproducción fallida a la siguiente. Pendiente de acotar el estado por reproducción y limpiar en `onPlayBackError`.
- **F04:** el servicio puede morir en silencio si una excepción inesperada escapa del bucle, y `_warm_up` puede bloquear el cierre de Kodi. Pendiente de try/except por tick y warm-up en hilo daemon.
- **F05:** `Session` no mapea `IncompleteRead`, `EOFError` ni `zlib.error` a `OSError`, por lo que no entran en el bucle de reintentos. Pendiente de mapeo.
- **F06:** `_norm` no pliega `ł`, `Ł`, `đ`, `Ø`, `ß`, `æ`, `œ`, por lo que "lodz" no encuentra "Łódź".
- **F08:** descargas: manejo de 416, extensión conservada y disco lleno terminal.
- **F09:** títulos de reproducción con BBCode y `default_title`.
- **F10:** `clean()` rompe atributos con `&quot;` antes de parsear (bloqueado por fixtures HTML).
