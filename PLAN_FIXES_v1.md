# PLAN_FIXES_v1 — Chomiteca

| Campo | Valor |
|---|---|
| Objetivo v1 | Corregir los bugs críticos y altos de la revisión sin tocar arquitectura ni scraping |
| Base del código | ZIP de revisión, `addon.xml` 1.11.3 (asumido; ver "Pendiente de decidir") |
| Fecha | 2026-11-01 |
| Autor | Plan generado con Claude a partir del informe de revisión |
| Uso | Personal, sin publicación |
| Ejecución | Un bloque = una rama o un commit, con tests verdes o justificación y revisión humana antes del siguiente |

**Fuera de alcance (resumen):** cliente HTTP único, eliminar `t0mm0` o `chomikdb.db`, cambios de regex HTML sin fixtures, `reuselanguageinvoker`, anti-inactividad, scraping paralelo, `strings.py` y `.po`, funciones nuevas grandes. Detalle en la sección final.

**Comprobación estándar tras cada bloque:** `python -m compileall resources/lib` y `pytest -q`. Ambos deben pasar antes del commit.

---

## Tabla resumen

| ID | Título | Gravedad | Archivos | Esfuerzo | Depende de | Estado |
|---|---|---|---|---|---|---|
| F00 | Arnés de tests con stubs de Kodi | infraestructura | `tests/`, `tests/conftest.py`, `pytest.ini`, `requirements-dev.txt`, `.gitignore` | S | ninguno | [ ] |
| F01 | [diag] Nombres de cookie antes/después de `LoginToFolder` | alto | `session.py`, `listing.py` | S | F00 | cancelado (A1 no reproducible) |
| F02 | Guardia de poda de STRM e índice parcial | crítico | `library.py`, `search.py`, `downloads.py` | M | F00 | [ ] |
| F03 | `PlayerMonitor` con estado por reproducción y `onPlayBackError` | alto | `playstate.py` | S | F00 | [ ] |
| F04 | Servicio endurecido (try/except por tick, `_warm_up` en hilo) | alto | `resources/lib/service.py` | S | F00 (mejor tras F05) | [ ] |
| F05 | Mapeo de excepciones de red en `Session._request_once` | medio | `session.py` | S | F00 | [ ] |
| F06 | `_norm` con plegado de `ł Ł đ Đ ø Ø ß æ œ` | medio | `search.py`, `common.py` (condicional) | S | F00 | [ ] |
| F07 | Persistir cookies de `Session` y enrutar login de carpeta por ella | alto | `session.py`, `listing.py`, `favorites.py`, `search.py`, `common.py` | M | F01, F05 | cancelado (dependía de F01) |
| F08 | Descargas: 416, extensión conservada, disco lleno terminal | medio | `downloadqueue.py` | S | F00 | [ ] |
| F09 | Títulos de reproducción reales y consistentes | medio | `router.py`, `playback.py`, `textutils.py` (nuevo), `common.py` | S | F00 | [ ] |
| F10 | `clean()` sin romper atributos con comillas | medio | `common.py`, `listing.py`, `library.py` | M | F00 + fixtures HTML | [ ] bloqueado por fixtures |

---

## Orden recomendado de ejecución

**Tanda 0 (bloqueante):**
1. F00. Sin arnés de tests no se puede verificar ningún otro bloque.

**Primera tanda (4 bloques, tras F00):**
2. F02. Es el único riesgo de pérdida de datos.
3. F05. Reduce las vías por las que el servicio muere (lo usa F04).
4. F03.
5. F04.

*(Nota: F01 y F07 han sido cancelados y no se ejecutan).*

**Segunda tanda:**
6. F06.
7. F08.
8. F09.

**Tercera tanda (con condiciones):**
9. F10, solo cuando existan los fixtures HTML.

Regla: no empieces el siguiente bloque sin revisar el diff del anterior.

---

## Diagnóstico previo obligatorio

*(No hay diagnósticos previos pendientes. F01 fue cancelado tras descartarse A1).*

---

## F00 — Arnés de tests con stubs de Kodi
- **Origen en el informe:** sección "Sin tests" y "Pendiente de decidir" del informe de revisión
- **Gravedad:** infraestructura (bloquea al resto)
- **Archivos a tocar:** `tests/__init__.py` (nuevo), `tests/conftest.py` (nuevo), `pytest.ini` (nuevo), `requirements-dev.txt` (nuevo), `.gitignore`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c chore/f00-test-harness` / `git commit -m "F00: arnés de tests con stubs de Kodi"`
- **Objetivo (1 frase):** Poder ejecutar `pytest -q` sin Kodi instalado, con módulos de Kodi simulados, para que los tests de los bloques siguientes tengan un arnés donde correr.
- **Cambios concretos:**
  1. Crear `tests/__init__.py` vacío.
  2. Crear `tests/conftest.py` que inserte en `sys.modules` stubs de `xbmc`, `xbmcgui`, `xbmcvfs`, `xbmcaddon`, `xbmcplugin`, `xbmcswift2` (si se importa). Cada stub expone los nombres usados en el proyecto (`log`, `LOGINFO`, `LOGWARNING`, `LOGERROR`, `LOGDEBUG`, `translatePath`, `executeJSONRPC`, `Player`, `Monitor`, `ListItem`, `Window`, `getSetting`, `setSetting`, `openSettings`, `Addon`, `getLocalizedString`, `addItem`, `endOfDirectory`, `setResolvedUrl`, etc.).
  3. `xbmcaddon.Addon()` debe devolver un objeto con `getSetting(key)` que devuelva `""` y `setSetting` no-op. `Addon.getLocalizedString(id)` devuelve `str(id)`.
  4. `xbmc.Monitor` con `waitForAbort(timeout)` que devuelva `False` y lleve un contador de llamadas para que los tests puedan limitar ticks.
  5. Crear `pytest.ini` (o añadir a `pyproject.toml`): `[pytest]` con `testpaths = tests` y `python_files = test_*.py`.
  6. Crear `requirements-dev.txt` con `pytest>=8` y `pytest-mock`.
  7. Ampliar `.gitignore` con `__pycache__/`, `*.pyc`, `.pytest_cache/`, `*.zip`, `_review_staging/`.
  8. Añadir `tests/test_smoke.py` con un test trivial que importe `resources.lib.session` y `resources.lib.textutils` si existe, para validar el arnés.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_smoke.py`
  - casos: `import resources.lib.session` no lanza; `xbmcaddon.Addon().getSetting("x") == ""`; `xbmc.Monitor().waitForAbort(0.01) is False`.
- **Criterios de aceptación:**
  - [ ] `pytest -q` ejecuta y el test de smoke pasa sin Kodi instalado.
  - [ ] `python -m compileall resources/lib` pasa.
  - [ ] El `.gitignore` excluye `__pycache__/`, `.pytest_cache/` y `*.zip`.
  - [ ] Sin cambios fuera de los archivos listados (no tocar `resources/lib/*` en este bloque).
- **Cómo verificar a mano (si aplica):** En un venv limpio, `pip install -r requirements-dev.txt` y `pytest -q` en verde.
- **Riesgos / notas:** El alcance de los stubs puede crecer cuando un test concreto importe un símbolo no cubierto. Se amplía en el bloque que lo necesite, no aquí.
- **Estado:** [ ]

---

## F01 — [diag] Nombres de cookie antes/después de `LoginToFolder`
- **Origen en el informe:** A1
- **Gravedad:** alto (diagnóstico)
- **Archivos a tocar:** `resources/lib/session.py`, `resources/lib/listing.py`. (Opcional: `resources/lib/common.py` en `abrir_url_cookie`, solo si el usuario decide que quiere la traza completa.)
- **Depende de:** F00
- **Rama/commit sugerido:** `git switch -c diag/f01-cookie-names` / `git commit -m "F01 [diag]: log de nombres de cookie en LoginToFolder"`
- **Objetivo (1 frase):** Saber con evidencia si el acceso a carpeta protegida se guarda en una cookie que se pierde al no persistir el jar.
- **Cambios concretos:**
  1. En `session.py` añadir `cookie_names(jar)`, que devuelve la lista ordenada de `dominio:nombre` (**nunca valores**).
  2. El POST a `LoginToFolder` se hace con `net.http_POST` en `listing.py:209`, no con `Session`. Por eso la instrumentación va en `listing.py` alrededor de ese POST: loguear `cookie_names(net._cj)` antes y después.
  3. Prefijo de log fijo `[diag-cookies]` y nivel `LOGINFO` con `k.log`, para poder filtrar `kodi.log`.
  4. **Opcional, no obligatorio en este bloque:** log en `common.abrir_url_cookie` tras `net.load_cookies(cookies)`. Solo si quieres ver además qué sobrevive al `Container.Refresh`. Si lo añades, va en el mismo commit y lo mencionas en la descripción.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_session_diag.py`
  - casos: `cookie_names` devuelve solo `dominio:nombre`; con un jar de prueba que contiene un valor secreto, el valor no aparece en el resultado; jar vacío devuelve `[]`.
- **Criterios de aceptación:**
  - [ ] Al abrir una carpeta protegida y meter la contraseña, `kodi.log` muestra 2 líneas `[diag-cookies]`: antes del POST y después del POST. (3 si activaste el log opcional en `common.abrir_url_cookie`.)
  - [ ] Ningún valor de cookie aparece en el log.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados (y, si aplica, el log opcional en `common.py`).
- **Cómo verificar a mano (si aplica):** Entra en una carpeta con contraseña, introdúcela y copia las líneas `[diag-cookies]`.
  - Si tras el POST aparece un nombre nuevo y (con el log opcional) tras la recarga del fichero no está: **A1 confirmado, se ejecuta F07**.
  - Si no aparece ningún nombre nuevo: **A1 descartado como causa del bucle, F07 se cancela** y se abre otra investigación.
- **Riesgos / notas:** Retirar la instrumentación (o bajarla a `LOGDEBUG`) al cerrar F07 o al cancelarlo.
- **Estado:** cancelado (A1 no reproducible)

**Resultado del diagnóstico (2026-11-03):** Cancelado. El usuario confirma que en su uso real las carpetas protegidas (incluida una con folder password propia) no generan bucle de contraseña. A1 no reproducible. La instrumentación `[diag-cookies]` no se llegó a validar en Kodi por desincronización entre el repo (Linux) y el addon instalado (Windows). Se descarta la línea de trabajo.

---

## F02 — Guardia de poda de STRM e índice parcial
- **Origen en el informe:** C1
- **Gravedad:** crítico
- **Archivos a tocar:** `resources/lib/library.py`, `resources/lib/search.py`, `resources/lib/downloads.py`
- **Depende de:** F00
- **Rama/commit sugerido:** `git switch -c fix/f02-strm-prune-guard` / `git commit -m "F02: no podar STRM ni guardar índice con escaneo incompleto"`
- **Objetivo (1 frase):** Que un fallo parcial del recorrido nunca borre `.strm` y `.nfo` válidos ni deje un índice incompleto dado por bueno.
- **Cambios concretos:**
  1. En `library.py` definir `class WalkIncomplete(Exception)`.
  2. En `walk_folder_files` (`library.py:349`) sustituir `if not body: break` por `raise WalkIncomplete(page)`.
  3. En `create_strm_files_recursive_chomiteca`: capturar `WalkIncomplete`, poner `complete = False` y loguear `STRM: escaneo incompleto (<página>); se omite la poda` en `LOGWARNING`.
  4. Condición de poda (`library.py:464`): `if prune and complete and not aborted and len(seen_paths) >= 0.5 * len(indexed):`. Si no se cumple y `prune` estaba activo, loguear que se omitió y por qué.
  5. En `search._build_index`: capturar `WalkIncomplete`, no escribir `search_index_<user>.json`, avisar al usuario con `notify` y devolver `None`.
  6. En `downloads.download_folder`: capturar `WalkIncomplete`, conservar lo ya encolado y avisar de que la carpeta quedó parcial.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_walker_guard.py`
  - casos: (a) `abrir_url_cookie` simulado devuelve `b""` en la 2.ª página: se lanza `WalkIncomplete` y no se borra ningún `.strm`; (b) escaneo completo con archivos desaparecidos: sí se poda; (c) recuento visto < 50 % del índice: no se poda; (d) `_build_index` con walker incompleto no escribe el JSON.
- **Criterios de aceptación:**
  - [ ] Con una página que falla a mitad, no se elimina ningún `.strm` aunque `strm_prune` esté activo.
  - [ ] Con escaneo completo y archivos realmente desaparecidos, la poda sigue funcionando.
  - [ ] Un recorrido interrumpido no deja `search_index_<user>.json` escrito.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
  - [ ] Log claro (`LOGWARNING`) cuando se omite la poda.
- **Cómo verificar a mano (si aplica):** Activa `strm_prune`, genera STRM de una carpeta, desactiva la red a mitad de una segunda generación y confirma que los `.strm` siguen en disco y que el log explica que se omitió la poda.
- **Riesgos / notas:** Una carpeta realmente vacía en origen dará recuento 0 y tampoco podará (comportamiento conservador aceptado). Los tres consumidores del walker deben tratarse en el mismo commit.
- **Estado:** [ ]

---

## F03 — `PlayerMonitor` con estado por reproducción y `onPlayBackError`
- **Origen en el informe:** A3
- **Gravedad:** alto
- **Archivos a tocar:** `resources/lib/playstate.py`
- **Depende de:** F00
- **Rama/commit sugerido:** `git switch -c fix/f03-playermonitor-stale-key` / `git commit -m "F03: PlayerMonitor ignora marcas caducadas y limpia en error"`
- **Objetivo (1 frase):** Que una reproducción fallida no contamine la siguiente reproducción (seek y progreso ajenos).
- **Cambios concretos:**
  1. En `mark_playing` (`playstate.py:71`) guardar en la propiedad `clave|timestamp` en lugar de solo la clave. El offset sigue en su propiedad.
  2. Extraer una función pura `_parse_mark(raw, now, max_age=90)` que devuelva la clave o `None` si la marca está vacía, mal formada o caducada.
  3. En `onAVStarted` (`playstate.py:104`) usar `_parse_mark`. Además exigir que `getPlayingFile()` contenga `chomikuj`. Si no se cumple: `self.key = None`, limpiar propiedades y salir.
  4. Añadir `onPlayBackError(self)`: `self.key = None` y limpiar ambas propiedades de `Window(10000)`.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_playstate_mark.py`
  - casos: `_parse_mark` con marca fresca devuelve la clave; con marca de más de 90 s devuelve `None`; con cadena vacía devuelve `None`; con formato antiguo (solo clave, sin `|`) **devuelve `None`** (no hay timestamp que validar, se descarta).
- **Criterios de aceptación:**
  - [ ] Tras una reproducción fallida, reproducir un fichero local no aplica seek ni guarda progreso bajo la clave anterior.
  - [ ] La reproducción normal sigue guardando posición y marcando visto.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
  - [ ] Log claro cuando se descarta una marca caducada (`LOGDEBUG`).
- **Cómo verificar a mano (si aplica):** Lanza un archivo con enlace que falle (cancela o corta red), espera más de 90 s, reproduce un vídeo local y comprueba en `kodi.log` que se descartó la marca.
- **Riesgos / notas:** Si Kodi no dispara `onPlayBackError` en algún caso, la caducidad por tiempo es la red de seguridad.
- **Estado:** [ ]

---

## F04 — Servicio endurecido
- **Origen en el informe:** A4
- **Gravedad:** alto
- **Archivos a tocar:** `resources/lib/service.py`
- **Depende de:** F00 (recomendado tras F05)
- **Rama/commit sugerido:** `git switch -c fix/f04-service-hardening` / `git commit -m "F04: servicio con try/except por tick y warm-up en hilo"`
- **Objetivo (1 frase):** Que ninguna excepción mate el servicio y que el login inicial no bloquee ni retrase el cierre de Kodi.
- **Cambios concretos:**
  1. Envolver el cuerpo del bucle de `run()` en `try/except Exception`, con `k.log("service tick: %r" % exc, xbmc.LOGERROR)`. El bucle continúa.
  2. Ejecutar `_warm_up()` en un `threading.Thread(target=..., daemon=True)` al llegar a `ticks == 15`, una sola vez.
  3. Dentro del hilo, capturar `Exception` genérica además de `auth.LoginError`.
  4. `downloadqueue.Manager` y `player.tick()` siguen en el hilo principal.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_service_loop.py`
  - casos: con `Monitor` simulado (3 ticks) y `player.tick` que lanza en el segundo, el bucle completa los 3 ticks; `_warm_up` se lanza una sola vez; una excepción dentro de `_warm_up` no afecta al bucle.
- **Criterios de aceptación:**
  - [ ] Una excepción en un tick se registra y el servicio sigue vivo.
  - [ ] El login inicial no bloquea `waitForAbort`.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
  - [ ] Log claro con el tipo de excepción.
- **Cómo verificar a mano (si aplica):** Arranca Kodi sin red y comprueba que el servicio sigue procesando la cola de descargas cuando vuelve la red y que Kodi cierra sin esperas largas.
- **Riesgos / notas:** El hilo de warm-up usa `make_session()` y escribe `cookies.lwp`; hasta F07 no hay lock de guardado. Riesgo bajo: es una sola escritura al inicio.
- **Estado:** [ ]

---

## F05 — Mapeo de excepciones de red en `Session._request_once`
- **Origen en el informe:** M3
- **Gravedad:** medio
- **Archivos a tocar:** `resources/lib/session.py`
- **Depende de:** F00
- **Rama/commit sugerido:** `git switch -c fix/f05-session-exceptions` / `git commit -m "F05: Session convierte IncompleteRead/EOFError/zlib.error en OSError"`
- **Objetivo (1 frase):** Que las lecturas truncadas o cuerpos corruptos entren en el bucle de reintentos y no escapen como excepciones genéricas.
- **Cambios concretos:**
  1. En `_request_once` (`session.py:113-118`) capturar `(http.client.HTTPException, EOFError, zlib.error)` alrededor de `resp.read()` y de la descompresión, y relanzar como `OSError(...) from exc`.
  2. `Session.request` ya reintenta `OSError`: confirmar que `IncompleteRead` convertido se reintenta con backoff.
  3. No cambiar el comportamiento de `HttpError` ni de los códigos de reintento.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_session_errors.py`
  - casos: opener simulado que lanza `IncompleteRead` produce `OSError` y se reintenta `retries` veces; `gzip` truncado produce `OSError`; respuesta correcta no cambia.
- **Criterios de aceptación:**
  - [ ] `IncompleteRead`, `EOFError` y `zlib.error` ya no escapan de `Session.request`.
  - [ ] Los reintentos se aplican a esos casos cuando `retries > 0`.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
  - [ ] Log claro si falla tras agotar reintentos.
- **Cómo verificar a mano (si aplica):** No reproducible a mano de forma fiable; basta con los tests.
- **Riesgos / notas:** Ninguno relevante.
- **Estado:** [ ]

---

## F06 — `_norm` con plegado de caracteres sin descomposición
- **Origen en el informe:** M6
- **Gravedad:** medio
- **Archivos a tocar:** `resources/lib/search.py`; `resources/lib/common.py` solo si la condición de abajo se cumple
- **Depende de:** F00
- **Rama/commit sugerido:** `git switch -c fix/f06-norm-fold` / `git commit -m "F06: _norm pliega ł đ ø ß æ œ para la búsqueda local"`
- **Objetivo (1 frase):** Que buscar "lodz" o "walesa" encuentre "Łódź" y "Wałęsa".
- **Cambios concretos:**
  1. En `search.py` definir una tabla `str.maketrans` con `ł→l, Ł→L, đ→d, Đ→D, ø→o, Ø→O, ß→ss, æ→ae, œ→oe` y aplicarla antes de `unicodedata.normalize("NFKD", ...)` en `_norm` (`search.py:120`).
  2. Para `common.ReplaceSpecialChar` (`common.py:283`): aplicar el mismo plegado **solo si** un `grep` confirma que su salida no se usa para rutas o claves ya persistidas (STRM usa `real_fs_name`). Si hay duda, dejarlo y anotarlo en el commit.
  3. No hace falta reindexar: la normalización se aplica al buscar.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_search_norm.py`
  - casos: `_norm("Łódź") == "lodz"`, `_norm("Wałęsa") == "walesa"`, `_norm("Żółć") == "zolc"`, `_norm("Dzień dobry") == "dzien dobry"`; `_norm("lodz") in _norm("Łódź")`.
- **Criterios de aceptación:**
  - [ ] Los casos de test pasan, incluidos los que antes devolvían `odz` y `wa esa`.
  - [ ] La búsqueda de "walesa" encuentra "Wałęsa" en un índice existente.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
- **Cómo verificar a mano (si aplica):** Busca "lodz" en tu cuenta, con un archivo cuyo nombre contenga "Łódź".
- **Riesgos / notas:** Cambiar `ReplaceSpecialChar` altera `clean_title`/`clean_folder`; por eso es condicional.
- **Estado:** [ ]

---

## F07 — Persistir cookies de `Session` y enrutar el login de carpeta por ella
- **Origen en el informe:** A1
- **Gravedad:** alto
- **Archivos a tocar:** `resources/lib/session.py`, `resources/lib/listing.py`, `resources/lib/favorites.py`, `resources/lib/search.py`, `resources/lib/common.py`
- **Depende de:** F01 (resultado que confirme A1), F05
- **Rama/commit sugerido:** `git switch -c fix/f07-persist-cookies` / `git commit -m "F07: guardado atómico del jar y login de carpeta por Session"`
- **Objetivo (1 frase):** Que una cookie nueva (p. ej. la de `LoginToFolder`) sobreviva a `Container.Refresh`.
- **Cambios concretos:**
  1. En `session.py`: `_SAVE_LOCK = threading.Lock()`, instantánea del jar `(dominio, ruta, nombre, valor)`, `save()` con `.tmp` + `os.replace` y `chmod 0o600`, y `_save_if_changed()` llamado tras cada petición correcta en `Session.request`.
  2. Sustituir en `listing.py:209` el `net.http_POST` de `LoginToFolder` por una llamada a `Session` (con `try/except HttpError/OSError`), de modo que el guardado ocurra.
  3. Hacer lo mismo en las llamadas `net.http_POST(...).content` de `favorites.py:62` y `search.py:272`, adaptando el manejo de errores (`Session` lanza `HttpError`, no devuelve respuesta con `code`).
  4. Mantener `net` y `abrir_url_cookie` sin eliminar nada: esto no es el cliente único.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_session_save.py`
  - casos: una petición que añade una cookie deja el fichero actualizado; sin cambios en el jar no se reescribe (mtime estable); no queda `cookies.lwp.tmp`; permisos `0600` donde el SO lo permita; **el fichero `cookies.lwp` contiene la cookie `LoginToFolder` tras una petición simulada** (verificable leyendo el jar con `http.cookiejar.LWPCookieJar` desde el propio test, sin depender de logs).
- **Criterios de aceptación:**
  - [ ] Tras introducir la contraseña de una carpeta protegida, la carpeta se abre sin volver a pedirla en la misma sesión.
  - [ ] **Inspeccionando `cookies.lwp` con un script de test (no con logs), la cookie de `LoginToFolder` está presente tras el flujo.** Esto sustituye al criterio anterior basado en `[diag-cookies]`, que dependía de instrumentación retirable.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
  - [ ] Log claro si falla el guardado (`LOGWARNING`).
- **Cómo verificar a mano (si aplica):** Repite el caso de F01 y comprueba que no hay bucle.
- **Riesgos / notas:**
  - **Bloqueado por diagnóstico:** no empezar sin el resultado de F01. Si F01 descarta A1, cancelar este bloque.
  - Es el bloque con más riesgo de la v1 porque toca 5 archivos. Si el diff supera ~150 líneas, hacer commits separados por módulo dentro de la misma rama.
  - Esto roza el límite de "cliente único" (fuera de alcance): no eliminar `net` ni unificar relogins.
- **Estado:** cancelado (dependía de F01)

**Resultado:** Cancelado. Dependía de F01, que se ha descartado. No se implementa el guardado atómico del jar ni el enrutado de `LoginToFolder` por `Session`. Si en el futuro se reproduce el bucle, reabrir como bloque nuevo.

---

## F08 — Descargas: 416, extensión conservada, disco lleno terminal
- **Origen en el informe:** M4
- **Gravedad:** medio
- **Archivos a tocar:** `resources/lib/downloadqueue.py`
- **Depende de:** F00
- **Rama/commit sugerido:** `git switch -c fix/f08-downloads` / `git commit -m "F08: descargas gestionan 416, conservan extensión y no reintentan disco lleno"`
- **Objetivo (1 frase):** Que las descargas no fallen por `.part` inválido, no pierdan la extensión y no gasten reintentos en un disco lleno.
- **Cambios concretos:**
  1. Ante `HTTPError` 416 (`downloadqueue.py:163`, cabecera `Range`) con `have > 0`: borrar el `.part`, reiniciar desde cero y reintentar **una sola vez**.
  2. `safe_name` (`downloadqueue.py:22`): recortar el nombre sin la extensión (`stem[:150 - len(ext)] + ext`), de modo que la extensión sobreviva.
  3. Disco lleno (`downloadqueue.py:175`): definir `class DiskFull(Exception)` (hereda de `Exception`, **no de `OSError`**, para que no entre en el `except OSError` de reintento), lanzarla y marcar `status='error'` con mensaje; el hilo termina.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_downloadqueue.py`
  - casos: `safe_name` con un nombre de 300 caracteres conserva `.mkv`; 416 con `urlopen` simulado borra el `.part` y reintenta una vez; con `disk_usage` simulado a casi 0 la descarga queda en `error` sin reintentos; `issubclass(DiskFull, OSError) is False`.
- **Criterios de aceptación:**
  - [ ] Un `.part` inválido ya no agota los 3 reintentos con el mismo `Range`.
  - [ ] Los nombres largos conservan su extensión.
  - [ ] El disco lleno falla a la primera, sin re-resolver el enlace.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
  - [ ] Log claro con la causa.
- **Cómo verificar a mano (si aplica):** Encola un archivo con nombre de más de 150 caracteres y comprueba que el destino conserva la extensión.
- **Riesgos / notas:** La cancelación que borra el `.part` mientras el hilo escribe (informe, M4) queda fuera de este bloque.
- **Estado:** [ ]

---

## F09 — Títulos de reproducción reales y consistentes
- **Origen en el informe:** M5
- **Gravedad:** medio
- **Archivos a tocar:** `resources/lib/router.py`, `resources/lib/playback.py`, `resources/lib/textutils.py` (nuevo), `resources/lib/common.py`
- **Depende de:** F00
- **Rama/commit sugerido:** `git switch -c fix/f09-real-titles` / `git commit -m "F09: título de reproducción sin BBCode ni tamaño"`
- **Objetivo (1 frase):** Que el título mostrado y guardado sea el nombre real de Chomikuj en los dos caminos de reproducción.
- **Cambios concretos:**
  1. Crear `textutils.py` ligero (sin importar `common`) con `real_title(text)` y `strip_size_label(text)`, que quita el sufijo `[COLOR…](tamaño)[/COLOR]`. Reutilizar la regex de `ui.decorate_file_item`.
  2. `common.real_title` pasa a reexportar la de `textutils` para no romper llamadas existentes.
  3. `router.py:45`: `label = real_title(strip_size_label(title)) or <nombre de la URL>`.
  4. `playback.py:114`: usar la misma función para el título mostrado. **No** cambiar el término de búsqueda de subtítulos (`getsubtitles`), que queda como está.
  5. Con esto `"default_title"` deja de mostrarse como título.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_textutils.py`
  - casos: `Nombre.mkv [COLOR white](1.2 GB)[/COLOR]` produce `Nombre.mkv`; un nombre en cirílico se conserva; `Wałęsa` se conserva; cadena vacía devuelve vacío.
- **Criterios de aceptación:**
  - [ ] El OSD no muestra BBCode ni el tamaño.
  - [ ] Con subtítulos activados el título coincide con el del camino ligero.
  - [ ] Un nombre sin caracteres latinos ya no se muestra como `default_title`.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
- **Cómo verificar a mano (si aplica):** Reproduce un archivo con tilde y otro con nombre en cirílico, con subtítulos activados y desactivados.
- **Riesgos / notas:** `playstate.save` guardará el título limpio; las filas antiguas conservan el sucio, sin impacto funcional.
- **Estado:** [ ]

---

## F10 — `clean()` sin romper atributos con comillas
- **Origen en el informe:** M2
- **Gravedad:** medio
- **Archivos a tocar:** `resources/lib/common.py`, `resources/lib/listing.py`, `resources/lib/library.py`
- **Depende de:** F00 + fixtures HTML reales (ver "Fixtures pendientes")
- **Rama/commit sugerido:** `git switch -c fix/f10-clean-quotes` / `git commit -m "F10: clean() no convierte &quot; antes de parsear atributos"`
- **Objetivo (1 frase):** Que un nombre con comillas no se trunque al parsear `title="..."`.
- **Cambios concretos:**
  1. Elegir con el fixture real la opción más pequeña: (a) no aplicar `&quot;`→`"` en `clean()` y dejar que `html.unescape` lo resuelva al extraer el atributo, o (b) parsear antes de `clean()`.
  2. Aplicarla en los tres puntos donde se llama a `clean()` sobre páginas: `listing.py` (2 sitios) y `library.py:350`.
  3. No modificar ninguna regex de `ReturnConteudo` ni de `paginas`.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_listing_quotes.py`
  - casos: con el fixture que contiene un nombre con comillas, el título capturado es completo; los fixtures sin comillas producen el mismo resultado que antes.
- **Criterios de aceptación:**
  - [ ] Con el fixture real, un nombre con comillas se captura entero.
  - [ ] Los otros fixtures producen resultados idénticos a antes del cambio.
  - [ ] Tests nuevos pasan; tests existentes siguen pasando.
  - [ ] Sin cambios fuera de los archivos listados.
- **Cómo verificar a mano (si aplica):** Lista una carpeta con un archivo cuyo nombre lleve comillas.
- **Riesgos / notas:** **Bloqueado por fixtures HTML.** Sin ellos solo se puede probar con HTML sintético, que no basta para tocar parsing. Tampoco se sabe si el HTML real escapa las comillas como `&quot;`.
- **Estado:** [ ] (bloqueado)

---

## Pendiente de decidir

- [ ] **Kodi objetivo y distribución.** ¿Kodi 22 con Python 3.13, solo en tu red? Asumido: sí.
- [ ] **Uso de los modos 23/24 (búsqueda global, p. ej. desde Emby).** No bloquea ningún bloque de esta v1; decide la prioridad del bug de `temp.txt`, que queda fuera de este plan.
- [ ] **Versión base: 1.11.3 o 1.12.1.** Asumido 1.11.3. Si la base real es 1.12.1, revisar los números de línea de F02 a F05 antes de empezar.

Los bloques F00 a F06, F08 y F09 no dependen de las tres decisiones con su valor por defecto. F07 y F10 están bloqueados por sus propias condiciones.

---

## Fixtures pendientes

Guardar 3 HTML reales en `tests/fixtures/`, sin tokens, cookies ni datos personales:

- [ ] `folder_normal.html`: carpeta normal con varios archivos, subcarpetas y paginación. **Debe** incluir al menos un archivo con `"` en el nombre. Sin ese caso, F10 no puede desbloquearse.
- [ ] `folder_protected.html`: carpeta protegida (página con `ProtectedFolderChomikLogin`).
- [ ] `search_results.html`: respuesta de resultados de búsqueda.

**Sin estos ficheros, cualquier bloque que toque parsing queda bloqueado.** En esta v1 afecta solo a F10.

---

## Fuera de alcance v1

| Excluido | Por qué |
|---|---|
| Cliente HTTP único, eliminar `t0mm0`, eliminar `chomikdb.db` | Toca todas las rutas de red; antes hacen falta F05, F07 y tests |
| Cambios en regex de HTML (`ReturnConteudo`, `paginas`, `resolver._FILE_ID`, `_URL_PATTERNS`) | No se pueden verificar sin fixtures reales |
| `reuselanguageinvoker` | El estado global y el jar de clase lo hacen inseguro por ahora |
| Anti-inactividad, scraping paralelo | Riesgo de bloqueo por parte de Chomikuj |
| Renombrar `strings.py` o tocar `.po` | Tres fuentes de verdad sin la herramienta de volcado |
| "Continuar viendo", STRM programado, búsqueda global rediseñada | Funciones nuevas grandes; primero estabilizar |