# Changelog

Todas las modificaciones relevantes de este fork se documentan aquí.

El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) y el versionado es [SemVer](https://semver.org/lang/es/).

## [1.13.0] - 2026-11-03

### Corregido
- **F03:** `PlayerMonitor` ya no aplica seek ni guarda progreso de una reproducción fallida a la siguiente. Añadido `onPlayBackError` que limpia el estado, y las marcas caducadas (>90 s) o con fichero no-Chomikuj se descartan.
- **F04:** el servicio ya no muere ante excepciones inesperadas en un tick, y el warm-up se ejecuta en un hilo daemon (Kodi cierra sin esperas largas).
- **F05:** `Session` convierte `IncompleteRead`, `EOFError` y `zlib.error` en `OSError` reintentable con backoff.
- **F06:** la búsqueda local pliega `ł`, `Ł`, `đ`, `Đ`, `ø`, `Ø`, `ß`, `æ`, `œ` antes del NFKD. "lodz" encuentra "Łódź", "walesa" encuentra "Wałęsa".
- **F08:** descargas gestionan correctamente el `HTTP 416` con `.part` inválido (borra y reinicia una vez), conservan la extensión en nombres largos (>150 caracteres) y tratan el disco lleno como error terminal sin reintentos.
- **F09:** título de reproducción sin BBCode, sin HTML, sin sufijo de tamaño y sin `default_title` en ambos caminos (ligero y con subtítulos). `real_title` unificado en `textutils.py` con comportamiento idéntico al original.
- **F11:** `settings.xml` con defaults no vacíos. Desaparece el spam de `error reading the default value` en el log de Kodi 21.

### Pendiente para 1.14.0
- **F10:** `clean()` rompe atributos con `&quot;` antes de parsear (bloqueado por fixtures HTML reales de Chomikuj).
- Limpieza: `import errno` en `downloadqueue._download_one` (subir al bloque de imports).
- Limpieza: `search._build_index` devuelve `None` en escaneo incompleto sin `notify` explícito.
- Limpieza: `ReplaceSpecialChar` con el mismo plegado de caracteres que `_norm`, si se confirma que su salida no se usa para rutas.

## [1.12.0] - 2026-11-03
