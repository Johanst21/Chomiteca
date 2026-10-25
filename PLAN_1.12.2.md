# PLAN_1.12.2 — Chomiteca (plugin.video.chomiteca)

| Campo | Valor |
|---|---|
| Addon | Chomiteca (`plugin.video.chomiteca`) |
| Versión actual | 1.12.1 |
| Versión objetivo | 1.12.2 |
| Plataforma | Kodi 22+ ("Piers") / Python 3.13, solo stdlib |

## Problemas históricos y su estado real

| Problema | Estado en 1.12.1 |
|---|---|
| UnicodeDecodeError | Resuelto: todos los `decode` usan `ignore`/`replace`; único estricto (`t0mm0.load_data`) cubierto por `ValueError`. |
| Contraseñas especiales | Resuelto en login (`urlencode` + UTF-8); siguen en claro en `accounts.json` (0600). |
| Cookies | Parcial: nada guarda el jar tras el login (C1); seis rutas borran sin coordinarse. |
| Login | Frágil: marcadores sin verificar, sin captcha, `has_cookies()` no valida la sesión (M1). |
| Paginación | Funciona en el caso feliz; regex laxas, `temp.txt` global, posible `??` (M4). |
| Buffering | No verificable estáticamente; el addon entrega `url|headers` con `setContentLookup(False)`; depende de Kodi/servidor. |
| STRM | Camino correcto (`mode=25` -> `router.play_mode`); riesgos: extensiones (M3), poda destructiva (C2). |
| Scraping recursivo | Funciona, pero sin detección de fallo parcial (C2) ni throttling. |
| Sesiones | `make_session()` por petición, tres copias del relogin (A1). |

## Reglas para el agente de código

1. Un commit por tarea. Mensaje: `P0/C1: <descripción corta>` (prefijo = prioridad/ID de la tarea).
2. Cambios mínimos que cumplan el criterio de aceptación. No refactorizar de más ni "aprovechar" para limpiar.
3. No tocar scraping (`patterns.py`, regex de `listing.py`/`library.py`) ni `strings.py`/`.po` salvo que la tarea lo pida expresamente. Cuando una tarea añada cadenas: nuevo ID = máximo ID usado + 1 (`grep -rn "4[0-9]\{4\}" resources/lib/strings.py`), añadirlo en `strings.py` y en AMBOS `.po` (en_gb y es_es).
4. Si algo depende del HTML real de Chomikuj, dejar `# TODO(verify): motivo`. No inventar marcadores ni nombres de cookies como si estuvieran confirmados.
5. Tras cada tarea: `python -m compileall resources/lib` y, si existe `tests/`, `pytest -q`. Ambos deben pasar antes del commit.
6. Cambiar `version="1.12.2"` en `addon.xml` SOLO en la última tarea (Z1).
7. Mantener el estilo existente: f-strings, imports relativos/`resources.lib` como en cada módulo, logging con `k.log(...)`/`xbmc.log`. Nunca registrar contraseñas, valores de cookies ni tokens.
8. Rutas siempre relativas a la raíz del addon (`resources/lib/session.py`).
9. Si una tarea no se puede completar con el código real (p. ej. la estructura difiere de lo descrito), parar, dejar `# TODO(verify)` y anotarlo en el mensaje del commit en vez de improvisar.

---

# P0 — Riesgo de datos o bloqueo

### C1 — Persistir cookies de forma atómica y con lock
- **Prioridad:** P0
- **Archivos afectados:** `resources/lib/session.py`, `resources/lib/common.py` (solo comprobar `_SessionNet._do`)
- **Problema:** `session.save()` solo se llama en `auth.login`. `_SessionNet._do` y `Session.request` crean una sesión por petición y descartan el jar: la cookie de `LoginToFolder` y cualquier cookie renovada se pierden. El guardado no es atómico ni tiene lock (carreras servicio/descargas/STRM).
- **Cambios:**
  1. En `session.py` añadir `import threading`, `import xbmc` y un lock de módulo.
  2. Guardar una instantánea del jar y escribir solo si cambia, con `.tmp` + `os.replace`:
     ```python
     _SAVE_LOCK = threading.Lock()

     class Session:
         def __init__(self, cookie_path, timeout=20):
             ...  # (código existente)
             self._snap = self._snapshot()

         def _snapshot(self):
             return tuple(sorted((c.domain, c.path, c.name, c.value) for c in self.jar))

         def save(self):
             with _SAVE_LOCK:
                 tmp = self.cookie_path + ".tmp"
                 self.jar.save(tmp, ignore_discard=True)
                 try:
                     os.chmod(tmp, 0o600)
                 except OSError:
                     pass
                 os.replace(tmp, self.cookie_path)
             self._snap = self._snapshot()

         def _save_if_changed(self):
             if self._snapshot() != self._snap:
                 try:
                     self.save()
                 except OSError as exc:
                     k.log("No se pudieron guardar las cookies: %s" % exc, xbmc.LOGWARNING)
     ```
  3. En `Session.request`, dentro del bucle de reintentos, tras `body = self._request_once(...)` llamar a `self._save_if_changed()` y devolver `body`.
  4. En `Session.clear()`, tras vaciar el jar y borrar el fichero, `self._snap = ()`.
  5. Log de depuración (solo NOMBRES de cookies añadidas/cambiadas, nunca valores) para poder verificar qué cookie fija `LoginToFolder`.
- **Criterio de aceptación:**
  - [ ] Si una petición añade una cookie al jar, el fichero `cookies.lwp` la contiene tras la petición (test con `_request_once` simulado).
  - [ ] Sin cambios en el jar no se reescribe el fichero (mtime estable).
  - [ ] No queda `cookies.lwp.tmp` tras guardar; permisos 0600 donde el SO lo permita.
  - [ ] `compileall` y `pytest` pasan.
- **Notas / riesgos:** `# TODO(verify): si Chomikuj guarda el acceso a carpeta protegida en cookie o en sesión de servidor; si no hay cookie nueva tras LoginToFolder, el bucle de contraseña tiene otra causa.`

### M1 — Detectar sesión caducada y acotar el patrón de contraseña
- **Prioridad:** P0
- **Archivos afectados:** `resources/lib/auth.py`, `resources/lib/resolver.py`, `resources/lib/session.py`
- **Problema:** `has_cookies()` solo mira que haya cookies (el jar se carga con `ignore_expires=True`); el relogin solo ocurre con 401/403 o si faltan FileId/Token. El patrón `has[łl]o|password` de `resolver._ERRORS` coincide con cualquier HTML con un campo password y puede mostrar «contraseña de archivo» en vez de reloguear.
- **Cambios:**
  1. `auth.py`: añadir
     ```python
     LOGGED_OUT = re.compile(r'action/Login/Login|ChomikToolbar\.IsLogged\s*=\s*false', re.I)  # TODO(verify)

     def looks_logged_out(html_text):
         return bool(LOGGED_OUT.search(html_text or ""))
     ```
  2. `resolver.resolve()`: tras obtener `page`, `if auth.looks_logged_out(page): raise ResolveError(k.tr(40342, "Sesión caducada"), relogin=True)`.
  3. `resolver._ERRORS`: sustituir el patrón `has[łl]o|password` por uno acotado a un mensaje de error JSON, p. ej. `re.compile(r'"(?:Message|Error|Errors)"[^}]*?has[łl]o', re.I)  # TODO(verify)`.
  4. `session.py`: en `Session.__init__` cargar con `self.jar.load(ignore_discard=True, ignore_expires=False)` para descartar cookies caducadas.
  5. No tocar los bucles de relogin existentes (router, playback, downloadqueue): ya reintentan una vez con `exc.relogin`.
- **Criterio de aceptación:**
  - [ ] Test: página con marcador de login -> `ResolveError(relogin=True)`.
  - [ ] Un `<input type="password">` en la respuesta ya no produce el error de contraseña de archivo.
  - [ ] Cookies caducadas en el fichero no cuentan para `has_cookies()`.
  - [ ] `compileall` y `pytest` pasan.
- **Notas / riesgos:** `# TODO(verify): marcadores de deslogueado y forma del JSON de error con HTML/respuesta real de Chomikuj.` Depende de C1.

### C2 — Poda de STRM solo con escaneo completo
- **Prioridad:** P0
- **Archivos afectados:** `resources/lib/library.py`, `resources/lib/strm_auto.py` (solo verificar)
- **Problema:** si una página falla (`if not body: break`), la carpeta está protegida, la sesión caducó o la estructura es desconocida, `walk_folder_files` devuelve 0 archivos sin error; `aborted` solo se activa al cerrar Kodi, y la poda borra `.strm`/`.nfo` válidos.
- **Cambios:**
  1. En `library.py`:
     ```python
     class WalkResult:
         complete = True
     ```
  2. `walk_folder_files(initial_url, progress_cb=None, include_folders=False, result=None)`: poner `result.complete = False` (si `result`) cuando `not body`, cuando `not patterns.check_structure(text_page, page)`, cuando `'ProtectedFolderChomikLogin' in text_page`, o ante excepción al descargar la página; en esos casos seguir con `break` como hasta ahora.
  3. `create_strm_files_recursive_chomiteca`: crear `walk = WalkResult()`, pasarlo al walker y podar solo si:
     ```python
     if prune and not aborted and walk.complete and len(seen_paths) >= 0.5 * len(indexed):
     ```
  4. Si se omite la poda, `k.log("STRM: poda omitida (escaneo incompleto o recuento sospechoso)", xbmc.LOGWARNING)`.
- **Criterio de aceptación:**
  - [ ] Con una página que falla a mitad, no se elimina ningún `.strm` aunque `strm_prune` esté activo.
  - [ ] Con escaneo completo y archivos realmente desaparecidos, la poda sigue funcionando.
  - [ ] Si el recuento cae por debajo del 50 % del índice previo, no se poda.
  - [ ] `compileall` y `pytest` pasan.
- **Notas / riesgos:** `check_structure` también devuelve `False` en una carpeta realmente vacía: en ese caso no se poda (comportamiento conservador, aceptado). Lanza un aviso de usuario una vez por ejecución; no cambiar ese comportamiento aquí.

---

# P1 — Corrección funcional

### M2 — Respetar nombres reales (dejar de usar `clean_title` para mostrar/guardar)
- **Prioridad:** P1
- **Archivos afectados:** `resources/lib/listing.py` (línea ~311), `resources/lib/favorites.py` (~88), `resources/lib/playback.py` (~84)
- **Problema:** `clean_title`/`ReplaceSpecialChar` convierte espacios, puntos y guiones en `-` y pasa a ASCII (`Władca Pierścieni (2001).mkv` -> `Wadca-Pierscieni-2001-mkv`). Afecta a nombres de accesos directos, playlist/lote «añadir a biblioteca» y título de reproducción.
- **Cambios:**
  1. `listing.py`: `clean_title_for_playlist = real_title(f"{title}{ext}")` (importar `real_title` desde `resources.lib.common`).
  2. `favorites.py` (`atalhos`, `addfolder/addfile`): `cleaned_name = real_title(current_name)`.
  3. `playback.handle_resolved`: `clean_display_name = real_title(display_name)`.
  4. Dejar `clean_title`/`ReplaceSpecialChar` definidos (los usa `trailer`).
- **Criterio de aceptación:**
  - [ ] `real_title("Władca Pierścieni (2001).mkv")` se conserva tal cual en atajo, playlist y título de reproducción.
  - [ ] Un `.strm` generado por el lote ya no termina en `-mkv`.
  - [ ] `grep -n "clean_title" resources/lib` solo queda en `common.py` y `playback.trailer`.
- **Notas / riesgos:** los atajos ya guardados con guiones no son recuperables (el nombre original se perdió); no migrar. A4 más tarde elimina la playlist en BD.

### M3 — Tabla única de extensiones
- **Prioridad:** P1
- **Archivos afectados:** `resources/lib/player.py`, `resources/lib/common.py`, `resources/lib/listing.py`, `resources/lib/ui.py`
- **Problema:** tres tablas distintas (`player.VIDEO_EXT`, `common.VIDEO_EXTS_UI`, lista literal en `listing.py`). `.m4v` tiene icono pero `player` no lo reconoce («extensión no soportada»); `.iso` se lista como vídeo pero se rechaza al reproducir; faltan `.opus`, `.mka`, `.dts`.
- **Cambios:**
  1. `player.py`: añadir a `VIDEO_EXT` `.m4v .divx .rmvb .rm .mts .m2v`; a `AUDIO_EXT` `.opus .mka .dts`. No añadir `.iso`.
  2. `common.py`: `VIDEO_EXTS_UI = sorted(player.VIDEO_EXT)` y `AUDIO_EXTS = sorted(player.AUDIO_EXT)` (importar `player`; no hay ciclo: `player` no importa `common`).
  3. `listing.py` (~310): sustituir la lista literal por `player.kind_of(ext) in ("video", "audio")`.
  4. `ui.addCont` usa `player.kind_of(ext)` en vez de comparar con las listas de `common`.
- **Criterio de aceptación:**
  - [ ] `player.kind_of(".m4v") == "video"`, `kind_of(".iso") == "other"`, `kind_of(".opus") == "audio"`.
  - [ ] `grep -rn "'.mkv'\|\".mkv\"" resources/lib` solo muestra la definición en `player.py` (y el mapa de iconos).
  - [ ] Un `.m4v` se reproduce desde la carpeta y desde STRM.

### M4 — Paginación robusta y sin estado global
- **Prioridad:** P1
- **Archivos afectados:** `resources/lib/patterns.py`, `resources/lib/listing.py`, `resources/lib/library.py` (autorizado a tocar scraping en esta tarea)
- **Problema:** `NEXT_PAGE/PREV_PAGE` aceptan cualquier `<a class="…right…">` y exigen `href` antes de `class`; `paginas()` decide el modo 24 por la existencia de `temp.txt` (nunca se borra); `url + returnExtra()` da `??` si la URL ya lleva query.
- **Cambios:**
  1. `patterns.py`: reemplazar las dos regex por `find_page_link(page_html, direction, current_url)` que recorre las etiquetas `<a ...>` (orden de atributos indiferente), acepta `rel="next|prev"` o una clase cuyo token sea exactamente `next`/`prev`/`previous` (sin subcadenas `right`/`left`), descarta `javascript:` y `#`, y exige que la ruta comparta el prefijo de la carpeta actual. `# TODO(verify)` contra HTML real.
  2. Actualizar los tres usos: `listing.paginas`, `library.get_next_page_url_for_strm_gen`, y por extensión `listing.prefetch_next_page`.
  3. `listing.paginas`: `idmode_next = 24 if '/action/SearchFiles' in current_url_param else 3` (quitar la condición `st.addon.load_data('temp.txt')`).
  4. Helper en `common.py` y úsalo en `pastas` y `prefetch_next_page` (misma cadena = misma clave de caché):
     ```python
     def add_query(url, extra):
         sep = "&" if "?" in url else "?"
         return url + sep + extra.lstrip("?")
     ```
- **Criterio de aceptación:**
  - [ ] Test sintético: `<a href="/action/Help" class="topLinks right">` no se confunde con «siguiente».
  - [ ] Test: el enlace se encuentra aunque `class` vaya antes de `href`.
  - [ ] `add_query("/u/f,2?a=1", "?b=2") == "/u/f,2?a=1&b=2"`.
  - [ ] El «siguiente» de una carpeta normal apunta al modo 3 aunque exista `temp.txt`.
- **Notas / riesgos:** `# TODO(verify): estructura real de la paginación de Chomikuj (rel/class/href).` El `temp.txt` de la búsqueda global lo elimina A3.

### M5 — Descargas: conservar extensión, tratar 416, no reintentar disco lleno
- **Prioridad:** P1
- **Archivos afectados:** `resources/lib/downloadqueue.py`, `resources/lib/common.py` (`real_fs_name`)
- **Problema:** `safe_name` corta a 150 caracteres y pierde la extensión; el HTTP 416 se reintenta 3 veces dejando el `.part` huérfano; el error de espacio libre se reintenta re-resolviendo el enlace.
- **Cambios:**
  1. `downloadqueue.safe_name`:
     ```python
     def safe_name(name, default="file", limit=150):
         name = re.sub(r"\[/?(?:COLOR|B|I)[^\]]*\]", "", str(name))
         name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .")
         if len(name) > limit:
             stem, ext = os.path.splitext(name)
             name = stem[:limit - len(ext)].rstrip(" .") + ext
         return name or default
     ```
  2. Mismo criterio de truncado en `common.real_fs_name` (conservar extensión si la hay).
  3. `_download_one`: inicializar `have = 0` antes del `for`; en `except urllib.error.HTTPError`, `if exc.code == 416 and have: _remove_part(dest); last_error = "HTTP 416"; continue`.
  4. Definir `class DiskFull(OSError)`; lanzarla en lugar de `OSError(strings.t(40343))`; capturarla antes de `except (OSError, URLError)` marcando `status="error"` sin reintentar.
- **Criterio de aceptación:**
  - [ ] `safe_name("x"*200 + ".mkv")` termina en `.mkv` y mide <= 150.
  - [ ] Un 416 con `.part` existente borra el `.part` y reinicia desde cero en el siguiente intento.
  - [ ] Disco lleno: un solo intento, estado `error` con el mensaje 40343.

### M6 — No cachear páginas inválidas
- **Prioridad:** P1
- **Archivos afectados:** `resources/lib/common.py` (`abrir_url_cookie`, `create_login_single`), `resources/lib/cache.py`
- **Problema:** `abrir_url_cookie(cache=True)` guarda cualquier 200 durante `cache_minutes`, incluso la página de «no logueado» o el aviso de carpeta protegida; tras relogin se sigue viendo la página vacía.
- **Cambios:**
  1. En `common.py`:
     ```python
     def _cacheable(body):
         text_ = body.decode("utf-8", "ignore")
         if "ProtectedFolderChomikLogin" in text_ or auth.looks_logged_out(text_):
             return False
         return bool(patterns.FOLDERS_BLOCK.search(text_) or patterns.LIST_VIEW.search(text_))
     ```
     y `if use_cache and body and _cacheable(body): cache_mod.put(url_param, body)`.
  2. En `create_login_single`, tras login correcto, `cache_mod.invalidate()`.
- **Criterio de aceptación:**
  - [ ] Respuesta con marcador de login o de carpeta protegida no se guarda en `page_cache`.
  - [ ] Tras un relogin se vacía la caché de páginas.
- **Notas / riesgos:** una carpeta realmente vacía tampoco se cachea (aceptado). Depende de M1 (`looks_logged_out`). `# TODO(verify)`.

---

# P2 — Menores, arquitectura y rendimiento

### m1 — `IncompleteRead` y `HTTPException` como error de red
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/session.py`
- **Problema:** `http.client.IncompleteRead` no hereda de `OSError`: no se reintenta y acaba en «Error inesperado».
- **Cambios:**
  1. `import http.client` y, en `_request_once`, envolver `open`/`read`:
     ```python
     except http.client.HTTPException as exc:
         raise OSError(str(exc)) from exc
     ```
- **Criterio de aceptación:**
  - [ ] Test: `_request_once` simulado que lanza `IncompleteRead` se reintenta con `retries>0` y acaba como `OSError`.

### m2 — Título de reproducción sin BBCode ni tamaño
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/ui.py` (`addCont`), `resources/lib/router.py`
- **Problema:** el `name` de la URL lleva `[COLOR white](1.2 GB)[/COLOR]` y acaba en el título, en `progress.title` y en scrobblers.
- **Cambios:**
  1. `ui.addCont`: calcular `plain = real_title(re.sub(r'\s*\[COLOR[^\]]*\].*?\[/COLOR\]\s*$', '', name_param))` y usarlo en `name=` de la URL y de los menús contextuales; la etiqueta visible conserva el tamaño.
  2. `router.play_mode`: `label = re.sub(r"\s*\([\d,.]+\s*[KMGT]?B\)\s*$", "", real_title(title))` (importar `real_title` desde `resources.lib.common`, con import local para no cargar el módulo pesado antes de tiempo).
- **Criterio de aceptación:**
  - [ ] `progress.title` ya no contiene `[COLOR` ni el tamaño.
  - [ ] «Continuar viendo» muestra el título limpio.

### m3 — `clean()` no debe romper atributos HTML
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/dictionary.py`, `resources/lib/common.py` (`clean`)
- **Problema:** `clean()` sustituye `&quot; &lt; &gt;` por `" < >` en todo el HTML antes de regex con `[^"]`/`[^>]`; un nombre con comillas trunca el `title="…"`. Además aplica ~170 alternativas sobre hasta 2 MB por página.
- **Cambios:**
  1. Reducir `dictionary` a: `\r`, `\n`, `\t` -> `""`, `&nbsp;` -> `" "`, `&amp;` -> `&`. Eliminar la tabla de entidades numéricas y `&quot; &lt; &gt; &apos;` (los campos ya pasan por `html.unescape`).
  2. `common.clean()`: compilar el patrón una sola vez a nivel de módulo.
- **Criterio de aceptación:**
  - [ ] `clean('title="a &quot;b&quot;"')` conserva `&quot;` y `patterns.FILE_LINK` captura el título completo.
  - [ ] Los listados siguen funcionando (las regex que asumen `<li><span>` sin saltos de línea siguen coincidiendo).
- **Notas / riesgos:** `&amp;` se mantiene porque las `href` de carpeta/archivo no se desescapan en todos los puntos. No tocar más reemplazos sin HTML real.

### m4 — Búsqueda local insensible a `ł`
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/search.py` (`_norm`)
- **Problema:** NFKD no descompone `ł`: `Władca` -> `w adca`; «wladca» no lo encuentra.
- **Cambios:**
  1. `_FOLD = str.maketrans("łŁđĐøØ", "lLdDoO")` y `text = (text or "").translate(_FOLD)` antes de `unicodedata.normalize`.
- **Criterio de aceptación:**
  - [ ] `_norm("Władca Pierścieni") == _norm("wladca pierscieni")`.
  - [ ] El índice existente sigue siendo válido (no guarda texto normalizado).

### m5 — `.nfo` solo con identificador TMDb
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/library.py` (`_nfo_for`), `resources/lib/metadata.py` (solo si falta el id)
- **Problema:** un `.nfo` mínimo (título/año) puede hacer que Kodi lo trate como fuente completa y no use el scraper.
- **Cambios:**
  1. Inspeccionar `metadata.lookup`/`cached`: si el dict no incluye el id de TMDb, añadirlo (`"id"`) sin cambiar el resto.
  2. `_nfo_for`: para películas con id en caché devolver solo `<uniqueid type="tmdb" default="true">ID</uniqueid>`; para episodios y para entradas sin id devolver `None` (no escribir `.nfo`).
- **Criterio de aceptación:**
  - [ ] Con `strm_nfo` activo no se escriben `.nfo` con solo título/año.
  - [ ] Los `.nfo` de película llevan `uniqueid` TMDb.
- **Notas / riesgos:** `# TODO(verify): comportamiento del scraper de Kodi 22 con un .nfo que solo contiene uniqueid.` Opción desactivada por defecto.

### m6 — Diagnóstico sin efectos secundarios en las cookies reales
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/tools.py`
- **Problema:** `diagnostics()` hace un login real que limpia y sobrescribe `cookies.lwp`.
- **Cambios:**
  1. Usar una sesión temporal: `session = Session(os.path.join(k.PROFILE, "cookies_diag.lwp"))` (importar `Session` de `.session`) y borrar el fichero en `finally`.
- **Criterio de aceptación:**
  - [ ] Tras abrir el diagnóstico, `cookies.lwp` conserva el mismo contenido y mtime.
  - [ ] El diagnóstico sigue mostrando el marcador de login reconocido.

### m7 — Redacción de usuario sin falsos positivos
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/tools.py` (`_redact_all`)
- **Problema:** `text.replace(user, '<usuario>')` corrompe el log si el usuario es corto.
- **Cambios:**
  1. Omitir usuarios de menos de 3 caracteres y usar `re.sub(r'(?<!\w)' + re.escape(user) + r'(?!\w)', '<usuario>', text)`.
- **Criterio de aceptación:**
  - [ ] Un usuario `a` no altera el log exportado; un usuario largo se sustituye solo como palabra completa.

### A5 — Tests con fixtures (arnés)
- **Prioridad:** P2
- **Archivos afectados:** `tests/conftest.py`, `tests/test_*.py`, `tests/fixtures/*.html` (nuevos, en la raíz del addon)
- **Problema:** no hay tests; `patterns`, `quality`, `metadata.parse`, `resolver.normalize_url`, etc. son puros y detectarían cambios de la web.
- **Cambios:**
  1. `tests/conftest.py` con stubs de Kodi antes de importar el addon:
     ```python
     import sys, types, tempfile
     from unittest.mock import MagicMock
     TMP = tempfile.mkdtemp()
     sys.path.insert(0, ".")

     class _Addon:
         def getAddonInfo(self, key):
             return {"id": "plugin.video.chomiteca", "name": "Chomiteca", "path": TMP,
                     "profile": TMP, "version": "0"}.get(key, "")
         def getSetting(self, _): return ""
         def getSettingBool(self, _): return False
         def getLocalizedString(self, _): return ""

     xbmc = types.ModuleType("xbmc")
     xbmc.LOGDEBUG, xbmc.LOGINFO, xbmc.LOGWARNING, xbmc.LOGERROR = 0, 1, 2, 3
     xbmc.log = lambda *a, **kw: None
     xbmc.Player = type("Player", (), {})
     xbmc.Monitor = type("Monitor", (), {"waitForAbort": lambda s, t=0: False,
                                         "abortRequested": lambda s: False})
     xbmcvfs = types.ModuleType("xbmcvfs"); xbmcvfs.translatePath = lambda p: p
     xbmcaddon = types.ModuleType("xbmcaddon"); xbmcaddon.Addon = _Addon
     sys.modules.update({"xbmc": xbmc, "xbmcvfs": xbmcvfs, "xbmcaddon": xbmcaddon,
                         "xbmcgui": MagicMock(), "xbmcplugin": MagicMock()})
     ```
  2. Tests iniciales: `quality.parse/passes`, `metadata.parse`, `resolver.normalize_url/ext_of`, `patterns` con fixtures HTML sintéticas, `real_title`, `safe_name`, `search._norm`.
  3. `tests/fixtures/README.txt`: indicar que los HTML son sintéticos y deben sustituirse por capturas reales (sin datos personales).
- **Criterio de aceptación:**
  - [ ] `pytest -q` pasa sin Kodi instalado.
  - [ ] `python -m compileall resources/lib` sigue pasando.
- **Notas / riesgos:** `# TODO(verify): sustituir fixtures sintéticas por HTML real.` Al empaquetar el zip excluir `tests/` (`zip -r ... -x "*/tests/*"`). Va primero en el orden de commits aunque sea P2.

### A7 — Metadatos de `addon.xml`
- **Prioridad:** P2
- **Archivos afectados:** `addon.xml`
- **Problema:** faltan `<source>` y `<website>` en `xbmc.addon.metadata`.
- **Cambios:**
  1. Añadir `<source>` y `<website>` con la URL real del repositorio del proyecto.
- **Criterio de aceptación:**
  - [ ] El XML sigue siendo válido (`python -c "import xml.dom.minidom as m; m.parse('addon.xml')"`).
- **Notas / riesgos:** si no se conoce la URL, NO añadir las etiquetas con valores inventados; dejar `<!-- TODO(verify): URL del repositorio -->` y anotarlo en el commit.

### R1 — `playstate` en lote y WAL una sola vez
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/playstate.py`, `resources/lib/store.py`, `resources/lib/listing.py`, `resources/lib/browse.py`
- **Problema:** `ui.addCont` llama a `playstate.get()` por archivo; cada llamada abre una conexión SQLite y ejecuta `PRAGMA journal_mode=WAL`.
- **Cambios:**
  1. `store._connect`: mover el `PRAGMA journal_mode=WAL` dentro del bloque `if DB_PATH not in _READY`.
  2. `playstate.py`: caché por invocación `_BULK = {}`, `prefetch(keys)` con una consulta `WHERE key IN (...)` por tandas de 500, y `get()` consulta `_BULK` primero.
  3. `listing.ReturnConteudo`: antes del bucle, calcular las claves (`key_for`) de los vídeos/audios y llamar a `playstate.prefetch`.
  4. `browse.main`: `playstate._BULK.clear()` al inicio.
- **Criterio de aceptación:**
  - [ ] Listar 200 archivos hace como máximo 1 consulta a `progress` (comprobar con un contador en test).
  - [ ] El estado visto/posición se sigue mostrando igual.

### A3 — Búsqueda global sin estado (`temp.txt`)
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/search.py`, `resources/lib/listing.py`
- **Problema:** la paginación de la búsqueda global depende de `temp.txt` (estado global en disco).
- **Cambios:**
  1. Extraer de `listing.pastas` el bloque de búsqueda a `search.fetch_results_page(term, ftype, page)` (POST contenedor -> token -> POST AJAX), sin cambiar campos ni cabeceras.
  2. `paginas()` (caso búsqueda): el enlace «siguiente» lleva `mode=24&q=<term>&ft=<tipo>&page=<N+1>`.
  3. `proxpesquisa_ck_page` lee esos parámetros de `st.params` y llama a `fetch_results_page`.
  4. Eliminar todo uso de `save_data/load_data('temp.txt')`.
- **Criterio de aceptación:**
  - [ ] `grep -rn "temp.txt" resources` no devuelve resultados.
  - [ ] La página 2 de una búsqueda funciona sin haber hecho la página 1 antes (sin estado previo).
- **Notas / riesgos:** `# TODO(verify): campos del formulario y del AJAX con respuesta real.` Depende de M4. Reusar el código existente; no reescribir el parseo.

### A1 — Cliente único `ChomikClient`
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/client.py` (nuevo), `resources/lib/common.py`, `resources/lib/router.py`, `resources/lib/playback.py`, `resources/lib/downloadqueue.py`, `resources/lib/service.py`
- **Problema:** dos pilas HTTP, `make_session()` por petición (recarga el jar cada vez) y tres copias de la lógica `_get_link`/relogin.
- **Cambios:**
  1. `client.py`: clase `ChomikClient` con `get(url, cache=False, referer=None, retries=2)`, `post(url, data, headers=None)`, `ensure_login()`, `is_logged_in()` y `resolve_link(page_url)` (relogin una sola vez ante `ResolveError.relogin`). `get_client()` devuelve un singleton por proceso con lock; recarga el jar solo si cambia el `mtime` de `cookies.lwp`.
  2. Sustituir `_get_link` en `router.py`, `playback.py` y `downloadqueue._resolve` por `client.get_client().resolve_link(...)`.
  3. `common._SessionNet._do` y `abrir_url_cookie` pasan a ser adaptadores finos sobre el cliente (misma firma y misma respuesta `_NetResponse`, para no tocar a los llamadores).
  4. `service._warm_up` usa `ensure_login()`.
- **Criterio de aceptación:**
  - [ ] `grep -rn "def _get_link\|def _resolve" resources/lib` no encuentra duplicados.
  - [ ] Test con sesión simulada: sesión caducada -> exactamente un relogin y éxito.
  - [ ] Reproducir, listar, descargar y generar STRM siguen funcionando.
- **Notas / riesgos:** tarea grande; mantener los adaptadores para minimizar el diff. Depende de C1, M1 y M6.

### A4 — SQLite único
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/store.py`, `resources/lib/common.py`, `resources/lib/favorites.py`, `resources/lib/playlist.py`, `resources/lib/library.py`, `resources/lib/listing.py`, `resources/lib/browse.py`
- **Problema:** `atalhos` y `playlist` viven en `chomikdb.db`; el resto en `chomiteca.db`. El listado hace `DELETE FROM playlist` + `INSERT` en cada carpeta para modos inalcanzables (15 y 30).
- **Cambios:**
  1. Añadir la tabla `atalhos` al esquema de `store.py`.
  2. Migración única: si existe `chomikdb.db`, copiar `atalhos` con `INSERT OR IGNORE` y renombrar el fichero a `chomikdb.db.migrated`.
  3. `favorites.atalhos` usa `store.db()`.
  4. Eliminar `playlist.py`, los modos 15 y 30 de `browse.main`, `add_to_library_batch`, y las llamadas `clear_playlist_db`/`add_items_to_playlist_db` de `listing.pastas`.
  5. Eliminar `common._get_db_connection` y `DATABASE_PATCH`.
- **Criterio de aceptación:**
  - [ ] Los atajos existentes aparecen tras migrar; la migración es idempotente.
  - [ ] Listar una carpeta no escribe en ninguna tabla de playlist.
  - [ ] `grep -rn "_get_db_connection\|playlist" resources/lib` sin referencias a la antigua BD.
- **Notas / riesgos:** el modo 30 era inalcanzable desde la UI, por lo que no hay regresión funcional; M2 queda como corrección previa independiente.

### A2 — Eliminar `t0mm0.py` y adelgazar `state.py`
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/t0mm0.py` (borrar), `resources/lib/state.py`, módulos que usan `st.addon.*`
- **Problema:** `t0mm0.py` (371 líneas) es un envoltorio heredado: solo se usa `st.addon.log_*` y `save_data/load_data`.
- **Cambios:**
  1. Reemplazar `st.addon.log_info/log_warning/log_error/log_debug(msg)` por `k.log(msg, xbmc.LOGINFO/LOGWARNING/LOGERROR/LOGDEBUG)`.
  2. Quitar de `state.py` el atributo `addon` y los campos sin uso (`addon_handle`, `username_setting_global_ref`, `usernameURL_global_ref`, etc., tras `grep`). `state.py` NO se elimina del todo en 1.12.2.
  3. Borrar `t0mm0.py` y su import en `state.init()`.
- **Criterio de aceptación:**
  - [ ] `grep -rn "st\.addon\|t0mm0" resources` devuelve 0 resultados.
  - [ ] `compileall` y `pytest` pasan; el menú y la reproducción siguen funcionando.
- **Notas / riesgos:** depende de A3 (que elimina `save_data/load_data`). La supresión total de `state.py` está fuera de alcance.

### R2 — Prefetch de TMDb sin bloquear el listado
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/metadata.py`, `resources/lib/listing.py`
- **Problema:** `prefetch`/`prefetch_folders` bloquean hasta 6 s cada vez (12 s si hay carpetas y archivos).
- **Cambios:**
  1. Reducir el presupuesto síncrono a ~1 s y dejar que el resto de la tarea continúe en un hilo daemon.
  2. Al terminar, si se guardó algún dato nuevo y el contenedor actual sigue siendo el mismo (`xbmc.getInfoLabel("Container.FolderPath")` coincide con el plugin URL del listado), lanzar `Container.Refresh` como máximo una vez por carpeta cada 60 s (propiedad de ventana como guarda).
- **Criterio de aceptación:**
  - [ ] Abrir una carpeta con TMDb activo y sin caché tarda ~1 s, no 6-12 s.
  - [ ] No hay bucles de refresco; si el usuario navegó a otra carpeta, no se refresca.
- **Notas / riesgos:** `# TODO(verify): comportamiento de Container.Refresh en Kodi 22 durante la navegación.`

### R3 — Caché de entradas ya parseadas
- **Prioridad:** P2
- **Archivos afectados:** `resources/lib/cache.py`, `resources/lib/store.py`, `resources/lib/listing.py`
- **Problema:** se cachea HTML bruto (hasta 2 MB) y se reparsea cada vez.
- **Cambios:**
  1. Tabla `parsed_cache(key, ts, json)` y funciones `cache.get_parsed/put_parsed`.
  2. En `listing.pastas`, guardar como JSON las tripletas de carpetas y los `item_data` que devuelve `ReturnConteudo(return_file_list=True)`, y reutilizarlas si hay acierto. No cambiar ninguna regex.
  3. Mantener la caché de HTML como respaldo.
- **Criterio de aceptación:**
  - [ ] Segundo acceso a una carpeta no ejecuta las regex de parseo (log/contador en test).
  - [ ] Invalidar la carpeta (`refresh_folder_cache`) limpia también `parsed_cache`.
- **Notas / riesgos:** tarea opcional; hacerla solo si A1 y A5 están completas. Respeta la regla de no tocar scraping: solo se cachea su salida.

### A6 — `reuselanguageinvoker`
- **Prioridad:** P2
- **Archivos afectados:** `addon.xml`
- **Problema:** cada invocación del plugin arranca un intérprete nuevo e importa ~25 módulos.
- **Cambios:**
  1. Añadir `<reuselanguageinvoker>true</reuselanguageinvoker>` en `<extension point="xbmc.python.pluginsource">`.
  2. Auditar que no quedan globales con estado obsoleto: `store._READY` (por ruta, OK), `patterns._warned` (aviso una vez por sesión de Kodi, aceptado), `metadata.parent_name` (se fija en cada listado), `playstate._BULK` (se limpia en `browse.main`).
- **Criterio de aceptación:**
  - [ ] Cambiar de cuenta, ajustes y menú siguen reflejando valores actuales.
  - [ ] Reproducción, descargas y STRM sin regresiones (prueba manual).
- **Notas / riesgos:** si hay cualquier regresión, revertir solo esta línea. Hacer después de A2 y R1. `# TODO(verify)` mide el tiempo de arranque antes/después.

---

# P3 — Funcionalidades

### F1 — Subtítulos sidecar
- **Prioridad:** P3
- **Archivos afectados:** `resources/lib/subtitles.py`, `resources/lib/player.py`, `resources/lib/router.py`, `resources/settings.xml`, `resources/lib/strings.py`, `.po`
- **Problema:** los `.srt/.ass` del mismo nombre en la carpeta no se cargan; `player.play` ya acepta `subtitle_path` sin usarlo.
- **Cambios:**
  1. `subtitles.find_sidecars(client, page_url)`: lista la carpeta del vídeo (`ReturnConteudo(return_file_list=True)`) y devuelve hasta 3 archivos `.srt/.ass` cuyo nombre empiece por el del vídeo (normalizado, admitiendo sufijo de idioma).
  2. Resolverlos con `client.resolve_link`, descargarlos (<= 2 MB, timeout 15 s) a `PROFILE/subs/<hash>.<ext>`.
  3. `player.play`: pasar a `subtitle_paths` (lista) y `item.setSubtitles(lista)`.
  4. `router.play_mode`: resolver primero los subtítulos y el vídeo al final (el enlace de vídeo caduca).
  5. Ajuste booleano `sidecar_subs` (por defecto `true`) con sus cadenas.
- **Criterio de aceptación:**
  - [ ] Vídeo con `.srt` hermano: la pista aparece sin buscar subtítulos online.
  - [ ] Sin hermanos o con ajuste desactivado: comportamiento actual.
  - [ ] Fallo al descargar un subtítulo no impide reproducir el vídeo.
- **Notas / riesgos:** `# TODO(verify): convención de nombres de subtítulos en carpetas reales y si pueden estar en otra página de la paginación.` Depende de A1.

### F2 — Reproducir carpeta como cola
- **Prioridad:** P3
- **Archivos afectados:** `resources/lib/browse.py`, `resources/lib/ui.py`, `resources/lib/library.py`, `resources/lib/strings.py`, `.po`
- **Problema:** no hay forma de reproducir una carpeta entera (tras A4 el modo 15 ya no existe).
- **Cambios:**
  1. `library.walk_folder_files(..., recursive=True)`: con `recursive=False` no añade subcarpetas a la cola.
  2. Modo nuevo 62 en `browse.main` -> `play_folder(url, name)`: lista los archivos de la carpeta (sin recursión), ordena por nombre natural, filtra con `player.kind_of in ("video","audio")` y construye un `xbmc.PlayList` con entradas `plugin://...?mode=4&url=...&name=...` resueltas de forma perezosa (patrón de `playlist.play_playlist_from_db`).
  3. Entrada de menú contextual «Reproducir carpeta» en `ui.addDir` para carpetas (modo 3).
- **Criterio de aceptación:**
  - [ ] Desde una carpeta de episodios se reproducen en orden y el siguiente se resuelve al llegar su turno.
  - [ ] Una carpeta sin vídeo/audio muestra aviso y no hace nada.
- **Notas / riesgos:** limitado a la primera página de la carpeta si hay paginación (`# TODO(verify)`).

### F3 — Búsqueda global de Chomikuj
- **Prioridad:** P3
- **Archivos afectados:** `resources/lib/browse.py`, `resources/lib/listing.py` (`menu_principal`), `resources/lib/search.py`, `resources/lib/strings.py`, `.po`
- **Problema:** la búsqueda actual solo recorre las carpetas de la cuenta; el backend global sigue en el código pero no tiene entrada en el menú.
- **Cambios:**
  1. Modo nuevo 63: pide el término (`caixadetexto('pesquisa')`), lo guarda con `_history_add(term, 'global')` y llama a `pastas_de_fora('search', term)`.
  2. Entrada «Buscar en Chomikuj (global)» en `menu_principal`.
  3. La paginación usa el modo 24 sin estado (A3).
- **Criterio de aceptación:**
  - [ ] Una búsqueda global lista resultados y la página 2 funciona.
  - [ ] La búsqueda local sigue intacta.
- **Notas / riesgos:** `# TODO(verify)` con respuesta real. Depende de A3 y C1.

### F4 — Renovar enlace si falla la reproducción
- **Prioridad:** P3
- **Archivos afectados:** `resources/lib/playstate.py` (`PlayerMonitor`), `resources/lib/player.py`, `resources/settings.xml`, `resources/lib/strings.py`, `.po`
- **Problema:** el enlace temporal puede caducar o cortarse a mitad de reproducción y no hay reintento.
- **Cambios:**
  1. Extraer de `player.play` una función `build_item(link, title, kind, offset)` reutilizable.
  2. `PlayerMonitor.onPlayBackError`: si hay `self.key` y `self.url`, y no se superó `MAX_RETRIES = 2` en 60 s para esa clave, guardar posición (`self.last`), resolver un enlace nuevo en un hilo con `client.resolve_link(self.url)`, llamar a `playstate.mark_playing(key, offset, url, title)` y reproducir con `StartOffset = last`.
  3. Ajuste booleano `renew_on_error` (por defecto `true`).
- **Criterio de aceptación:**
  - [ ] Un error simulado produce un único reintento con `StartOffset` igual a la última posición.
  - [ ] Tras 2 reintentos no se reintenta más (sin bucles).
  - [ ] Con el ajuste desactivado no hace nada.
- **Notas / riesgos:** `# TODO(verify): qué callbacks emite Kodi 22 al cortarse un stream HTTP (onPlayBackError/onPlayBackStopped).` Depende de A1 y M1.

### F5 — Importar cookies
- **Prioridad:** P3
- **Archivos afectados:** `resources/lib/browse.py`, `resources/lib/tools.py`, `resources/settings.xml`, `resources/lib/strings.py`, `.po`
- **Problema:** con captcha o bloqueo de login no hay forma de entrar; reCAPTCHA no se resuelve en Kodi.
- **Cambios:**
  1. Modo nuevo 64 («Importar cookies»): `Dialog().browse(1, ..., 'files', '.txt|.json')`.
  2. Parsear Netscape (`http.cookiejar.MozillaCookieJar`) o JSON (lista con `name`, `value`, `domain`, `path`, `expires`); quedarse solo con dominios `chomikuj.pl`.
  3. Hacer copia del `cookies.lwp` actual, cargar las nuevas cookies en la sesión y guardarlas con `session.save()`; comprobar con una petición a `MAIN_URL + usuario` y `not auth.looks_logged_out(...)`; si falla, restaurar la copia.
  4. Botón en Ajustes -> Cuentas y sesiones.
- **Criterio de aceptación:**
  - [ ] Importar cookies válidas deja la sesión activa sin pedir login.
  - [ ] Un fichero inválido no destruye la sesión previa.
  - [ ] Ningún valor de cookie aparece en el log.
- **Notas / riesgos:** `# TODO(verify): nombres de las cookies de autenticación de Chomikuj.` Depende de C1 y A1.

### F6 — Anti-inactividad (opcional, desactivado por defecto)
- **Prioridad:** P3
- **Archivos afectados:** `resources/lib/keepalive.py` (nuevo), `resources/lib/service.py`, `resources/lib/ui.py`, `resources/settings.xml`, `resources/lib/strings.py`, `.po`
- **Problema:** las cuentas inactivas pueden perder archivos; se pide una actividad mínima periódica.
- **Cambios:**
  1. Ajustes: `keepalive_days` (entero, 0 = desactivado), `keepalive_url` (cadena), `keepalive_last` (oculto). Texto de ayuda que indique que es actividad automatizada con su cuenta y que revise los términos de Chomikuj.
  2. Menú contextual en archivos: «Usar como archivo anti-inactividad» (guarda `keepalive_url`).
  3. `keepalive.py`: `due()` (con jitter de ±10 %) y `run()` en un hilo: `client.ensure_login()`, `client.resolve_link(url)`, petición con `Range: bytes=0-65535`, leer como máximo 64 KB y cerrar; guardar `keepalive_last`; en fallo registrar aviso y reintentar al día siguiente.
  4. `service.run`: comprobar `keepalive.due()` cada 60 s, sin competir con una reproducción en curso.
- **Criterio de aceptación:**
  - [ ] Con `keepalive_days = 0` no se hace ninguna petición.
  - [ ] Con el ajuste activo se hace como máximo una lectura de <= 64 KB por intervalo.
  - [ ] No se registran URLs con query ni cookies.
- **Notas / riesgos:** `# TODO(verify): política real de inactividad de Chomikuj y si una lectura parcial cuenta como actividad.` Depende de C1 y A1.

---

# Release

### Z1 — Versión 1.12.2
- **Prioridad:** P3
- **Archivos afectados:** `addon.xml`, `changelog.txt`
- **Problema:** publicar la versión con todas las tareas completadas.
- **Cambios:**
  1. `addon.xml`: `version="1.12.2"` y actualizar `<news>` con un resumen de una línea.
  2. `changelog.txt`: nueva entrada al principio con el formato existente (`[B]v1.12.2:[/B]` y viñetas ARREGLO/CAMBIO/NUEVO), una viñeta por tarea completada.
  3. Empaquetar el zip excluyendo `tests/`.
- **Criterio de aceptación:**
  - [ ] `compileall` y `pytest` pasan.
  - [ ] Prueba manual: login, listar, paginar, reproducir (vídeo y `.m4v`), reanudar, STRM desde biblioteca, descarga con reanudación, carpeta protegida.
  - [ ] El zip no contiene `tests/` ni `.tmp`.

---

# Dependencias entre tareas

| Tarea | Depende de | Motivo |
|---|---|---|
| A5 | — | Arnés de tests; se hace primero |
| C1 | A5 | Test del guardado de cookies |
| M1 | C1 | Asume cookies persistidas y `ignore_expires=False` coherente |
| C2 | — | Independiente (usa `patterns.check_structure`) |
| M6 | M1 | Usa `auth.looks_logged_out` |
| M2, M3, M5 | — | Independientes |
| M4 | A5 | Tests de paginación |
| m1–m7 | — | Independientes (m2 y m3 mejor tras A5) |
| A7 | — | Independiente |
| R1 | — | Independiente; antes de A6 |
| A3 | M4 | Reutiliza la paginación estable |
| A1 | C1, M1, M6 | El cliente unifica login/caché/relogin |
| A4 | M2 | M2 corrige antes los usos de la playlist |
| A2 | A3 | A3 elimina `save_data/load_data` |
| R2 | — | Independiente |
| R3 | A1, A5 | Necesita cliente único y tests |
| F1 | A1 | Usa `client.resolve_link` |
| F2 | A4 | La playlist en BD ya no existe |
| F3 | A3, C1 | Paginación sin estado y sesión fiable |
| F4 | A1, M1 | Resolver enlace nuevo con relogin fiable |
| F5 | C1, A1 | Guardado atómico y cliente único |
| F6 | C1, A1 | Sesión persistente y resolución |
| A6 | A2, R1 | Estado global limpio antes de reutilizar el intérprete |
| Z1 | todas | Última tarea |

# Orden de commits sugerido

1. P2/A5: arnés de tests (conftest con stubs de Kodi)
2. P0/C1: persistir cookies de forma atómica
3. P0/M1: detectar sesión caducada y acotar patrón de contraseña
4. P0/C2: poda de STRM solo con escaneo completo
5. P1/M6: no cachear páginas inválidas
6. P1/M2: nombres reales en atajos, lote y título
7. P1/M3: tabla única de extensiones
8. P1/M4: paginación robusta
9. P1/M5: descargas (extensión, 416, disco lleno)
10. P2/m1: IncompleteRead como error de red
11. P2/m2: título sin BBCode ni tamaño
12. P2/m3: `clean()` sin romper atributos
13. P2/m4: `_norm` con `ł`
14. P2/m7: redacción de usuario
15. P2/m6: diagnóstico sin tocar cookies reales
16. P2/m5: `.nfo` solo con id TMDb
17. P2/A7: `<source>` y `<website>`
18. P2/R1: `playstate` en lote y WAL una vez
19. P2/A3: búsqueda global sin estado
20. P2/A1: cliente único `ChomikClient`
21. P2/A4: SQLite único
22. P2/A2: eliminar `t0mm0.py` y adelgazar `state.py`
23. P2/R2: prefetch de TMDb sin bloqueo
24. P2/R3: caché de entradas parseadas (opcional)
25. P3/F1: subtítulos sidecar
26. P3/F2: reproducir carpeta como cola
27. P3/F3: búsqueda global en el menú
28. P3/F4: renovar enlace en `onPlayBackError`
29. P3/F5: importar cookies
30. P3/F6: anti-inactividad (opcional)
31. P2/A6: `reuselanguageinvoker`
32. P3/Z1: versión 1.12.2, changelog y empaquetado

# Fuera de alcance (no se hace en 1.12.2)

- **Reescritura completa del scraper** (regex -> parser DOM): sin HTML real versionado como fixtures el riesgo de regresión es alto; R3 solo cachea su salida.
- **Migrar a otro cliente HTTP** (requests/httpx): añadiría una dependencia externa; la stdlib basta con A1.
- **Rediseño de UI/menús**: fuera del objetivo de estabilización; solo se añaden entradas puntuales (F2, F3, F5, F6).
- **Eliminar `state.py` por completo** (pasar contexto explícito a todas las funciones): alto volumen de cambios; A2 lo adelgaza sin eliminarlo.
- **Cifrar `accounts.json`**: Kodi no ofrece almacén seguro; se mantiene el fichero con permisos 0600 y la redacción de logs.
- **Resolver captcha/reCAPTCHA automáticamente**: requeriría servicios externos y choca con los términos del sitio; F5 ofrece importar la sesión como alternativa.
- **Perfil de buffering / `advancedsettings.xml`**: depende de ajustes de Kodi 22 no verificados; F4 mitiga los cortes sin tocar la configuración de Kodi.
- **Sincronización bidireccional STRM con papelera**: C2 solo hace segura la poda existente.
- **Cambios de endpoints o flujo de login de Chomikuj**: no verificables sin el sitio real.
