# Chomiteca (fork)

Fork personal de [plugin.video.chomiteca](https://github.com/Leinad4Mind/Leinad4Mind-Kodi-Addons-Repo/tree/master/plugin.video.chomiteca) de Leinad4Mind.

Este fork incluye correcciones de bugs y mejoras de robustez. **No es la versión oficial** ni está respaldado por el autor original.

## Licencia

GPL-3.0-or-later. Ver [LICENSE](LICENSE).

## Instalación

1. Descarga el ZIP de la última release desde la sección [Releases](https://github.com/johanst21/chomiteca/releases).
2. En Kodi: Ajustes → Add-ons → Instalar desde archivo ZIP.
3. Selecciona el ZIP descargado.

Compatible con Kodi 21 (Omega). No probado en versiones anteriores.

## Cambios respecto al upstream

Ver [CHANGELOG.md](CHANGELOG.md).

### 1.12.0 (esta release)

- **F02 (crítico):** la poda de STRM y el índice de búsqueda ya no se ejecutan si el escaneo de carpeta se interrumpe a mitad. Evita pérdida de datos en `.strm` y `.nfo` cuando hay fallos de red, sesión caducada o cancelación manual.

### Pendiente para 1.13.0

- F03: `PlayerMonitor` no aplicará seek de una reproducción fallida a la siguiente.
- F04: el servicio no morirá ante excepciones inesperadas y el warm-up no bloqueará el cierre de Kodi.
- F05: `Session` tratará `IncompleteRead`/`EOFError`/`zlib.error` como errores reintentables.
- F06, F08, F09, F10: mejoras pendientes.

## Estado del proyecto

Fork en desarrollo activo. La 1.12.0 arregla el bug crítico de pérdida de datos (F02), pero aún no incluye los fixes de robustez de reproducción y servicio (F03, F04, F05), que llegarán en 1.13.0.

## Disclaimer

Este addon accede a Chomikuj.pl mediante scraping. No hay relación oficial con Chomikuj.pl ni con Leinad4Mind. Úsalo bajo tu responsabilidad.
