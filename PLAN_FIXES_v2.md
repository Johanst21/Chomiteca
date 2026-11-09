# PLAN_FIXES_v2 — Chomiteca

| Campo | Valor |
|---|---|
| Objetivo | Cerrar bugs del informe original + features pequeñas + limpieza, en releases incrementales |
| Base del código | 1.13.0 publicada (github.com/johanst21/chomiteca) |
| Fecha | 2026-11-08 |
| Autor | Plan generado a partir del informe de revisión original + hallazgos de fixtures |
| Uso | Personal, repo público bajo GPL-3.0 |
| Ejecución | Un bloque = una rama o commit, tests verdes, revisión humana antes del siguiente |

**Comprobación estándar tras cada bloque:** `python3 -m compileall resources/lib` y `pytest -q`. Ambos deben pasar antes del commit.

**Fixtures disponibles** en `tests/fixtures/` (commit `0efa718`):
- `folder_normal.html` (172 KB): vista lista, con `&quot;` sintético y paginación absoluta
- `folder_protected.html` (44 KB): reto real de carpeta protegida (`ProtectedFolderChomikLogin`, `LoginToFolder`, `ChomikId`, `FolderId`)
- `search_results.html` (116 KB): resultados de búsqueda reales con marcadores de sesión

---

## Tabla resumen por versión

### 1.14.0 — Hotfixes y seguridad — COMPLETADA (release: ver GitHub)

| ID | Título | Gravedad | Esfuerzo | Depende de | Estado |
|---|---|---|---|---|---|
| F27 | Paginación con URLs absolutas | alto (bug activo) | S | ninguno | [x] merged (391775c) |
| F27c | Fix pagination regression from F27 | alto (regresión) | `listing.py`, `tests/test_pagination.py` | S | F27 | [x] pending release |
| F22a | Account model + store_password setting | alto (seguridad) | S | ninguno | [x] merged (85398c8) |
| F22b | Cookie import helpers + verify_session | alto (seguridad) | M | F22a | [x] merged (20e0484) |
| F22c | Cookie import UI + README | alto (seguridad) | M | F22b | [x] merged (0e86b53) |
| F12 | `import errno` al bloque de imports | bajo | XS | ninguno | [x] merged (2b3b05b) |
| F13 | `notify` en `search._build_index` | bajo | XS | ninguno | [x] merged (2b3b05b) |

Nota: F22 se dividió en F22a/b/c durante la implementación para reducir riesgo. El tag de release `v1.14.0` se crea en el paso final de publicación.

**Hotfix 2026-11-09:** `ReturnConteudo` required relative URLs, but Chomikuj switched to absolute URLs in file links. Folders showed 0/0 items. Fixed in commit `c4c6d56` before release. The `v1.14.0` tag was recreated to include this hotfix.

### 1.14.1 — Scraping robusto

| ID | Título | Gravedad | Archivos | Esfuerzo | Depende de | Estado |
|---|---|---|---|---|---|---|
| F17 | Endurecer regex login y paginación | medio | `auth.py`, `listing.py`, `resolver.py` | S | fixtures | [ ] |
| F10 | `clean()` no rompe con `&quot;` | bajo (sintético) | `common.py`, `listing.py` | S | fixtures | [ ] |
| F15 | `temp.txt` no contamina paginación | medio | `listing.py`, `search.py` | S | ninguno | [ ] |
| F18 | Bajos sueltos (tools, subtitles, prefetch, state) | bajo | varios | S | ninguno | [ ] |

### 1.15.0 — UX y features pequeñas

| ID | Título | Gravedad | Archivos | Esfuerzo | Depende de | Estado |
|---|---|---|---|---|---|---|
| F20 | Renovar enlace si falla reproducción | mejora | `playstate.py`, `playback.py`, `resolver.py` | S | F03 (hecho) | [ ] |
| F19 | Subtítulos sidecar | mejora | `subtitles.py`, `listing.py` | S-M | ninguno | [ ] |
| F23 | Tráiler vía TMDb | mejora | `metadata.py`, `playback.py`, `settings.xml` | S | ninguno | [ ] |

### 1.16.0 — Limpieza técnica

| ID | Título | Gravedad | Archivos | Esfuerzo | Depende de | Estado |
|---|---|---|---|---|---|---|
| F16 | Limpiar código muerto (playlist, folder-type, modos 1/9) | bajo | `listing.py`, `browse.py`, `playlist.py`, `router.py` | M | ninguno | [ ] |
| F14 | `ReplaceSpecialChar` folding | bajo | `common.py` | S | análisis de uso | [ ] |

### 1.17.0 — Refactor y features grandes (futuro)

| ID | Título | Gravedad | Esfuerzo | Depende de | Estado |
|---|---|---|---|---|---|
| F30 | Cliente HTTP único | refactor | L | F05, F17, tests | [ ] |
| F31 | Eliminar estado global y activar `reuselanguageinvoker` | refactor | M | F30 | [ ] |
| F21 | Reproducir carpeta como cola | feature | M | F20 | [ ] |
| F24 | "Continuar viendo" (migración DB) | feature | M | F20 | [ ] |
| F25 | Búsqueda global rediseñada (sin `temp.txt`) | feature | M | F15 | [ ] |
| F26 | STRM programado desde el servicio | feature | M | F02 (hecho), F04 (hecho) | [ ] |

---

## Orden recomendado

**1.14.0 (tanda única, ~1h):**
1. F27. Bug activo en producción, arreglarlo primero.
2. F22. Seguridad real.
3. F12. XS, 2 minutos.
4. F13. XS, 2 minutos.
5. Empaquetar y publicar 1.14.0.

**1.14.1 (tanda única, ~2h):**
6. F17. Con fixture real de carpeta protegida.
7. F10. Con fixture sintético.
8. F15. Aislado.
9. F18. Varios bajos en un commit.
10. Empaquetar y publicar 1.14.1.

**1.15.0 (tanda única, ~2h):**
11. F20. Encaja con F03.
12. F19. Feature pequeña.
13. F23. Cosmético.
14. Empaquetar y publicar 1.15.0.

**1.16.0 (tanda única, ~2h):**
15. F16. M, con calma.
16. F14. Tras análisis.
17. Empaquetar y publicar 1.16.0.

**1.17.0:** futuro, sin fecha. Se planifica cuando 1.16.0 esté estable.

Regla: no empieces el siguiente bloque sin revisar el diff del anterior. No mergees un bloque a `master` sin `pytest` verde.

---

## 1.14.0 — Hotfixes y seguridad

### F27 — Paginación con URLs absolutas

- **Origen:** hallazgo confirmado por fixture `folder_normal.html`
- **Gravedad:** alto (bug activo en producción)
- **Archivos a tocar:** `resources/lib/listing.py`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c fix/f27-pagination-absolute` / `git commit -m "F27: paginación soporta URLs absolutas de Chomikuj"`
- **Objetivo (1 frase):** Que la detección de página siguiente/anterior funcione con los `href` absolutos (`https://chomikuj.pl/...`) que devuelve Chomikuj, no solo con rutas relativas.
- **Cambios concretos:**
  1. Localizar la regex de paginación en `listing.py:520`: `href=["\']/([^"\']+?)["\']`.
  2. Sustituir por una regex que acepte **ambas** formas (relativa y absoluta). Opciones:
     - Extraer el path con `urllib.parse.urlparse(href).path` y unificar.
     - O regex: `href=["\'](?:https?://[^/]+)?/([^"\']+?)["\']`.
  3. Añadir validación adicional: el `class` del enlace debe contener exactamente una de `left|right|next|prev` como palabra, no como subcadena. Actualmente `class="uploadMinimalize right greenButton"` da falso positivo. Filtrar por atributo `rel="N"` (que los paginadores reales sí tienen: `<a href="..." class="right" rel="2" title="...">`).
  4. Si la regex actual se usa en otros sitios, aplicar el mismo fix allí (buscar con `grep -rn "class=\"[^\"]*left\|right" resources/lib/`).
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_pagination.py` (nuevo)
  - casos:
    - `folder_normal.html`: detecta `https://chomikuj.pl/Sechel/Prueba,2` como página siguiente.
    - Ignora `<a class="uploadMinimalize right greenButton" href="javascript:;">` como falso positivo.
    - URL relativa `/Sechel/Prueba,2` sigue funcionando.
    - Página sin paginador devuelve `None`.
- **Criterios de aceptación:**
  - [ ] `folder_normal.html` produce URL de página siguiente correcta.
  - [ ] No se detectan falsos positivos del layout.
  - [ ] Compatibilidad con URLs relativas (fixtures viejos o tests previos).
  - [ ] Tests nuevos pasan; existentes verdes.
  - [ ] Sin cambios fuera de `listing.py` y el test nuevo.
- **Cómo verificar a mano:** En Kodi, navegar a una carpeta con varias páginas y confirmar que "siguiente" lleva a la página correcta (hoy no lo hace).
- **Riesgos / notas:** Si hay más de un consumidor de la regex, arreglarlos todos en el mismo commit.
- **Estado:** [ ]

### F22 — Importar cookies, no guardar contraseña

- **Origen:** informe, sección 5 (quick win de seguridad)
- **Gravedad:** alto (seguridad)
- **Archivos a tocar:** `resources/lib/accounts_ui.py`, `resources/lib/accounts.py`, `resources/lib/common.py`, `resources/settings.xml`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c fix/f22-cookie-import` / `git commit -m "F22: opción de importar cookies y no guardar contraseña en accounts.json"`
- **Objetivo (1 frase):** Ofrecer al usuario la opción de autenticarse importando cookies de Chomikuj en lugar de guardar la contraseña en texto plano en `accounts.json`.
- **Cambios concretos:**
  1. En `settings.xml`: añadir setting booleano `store_password` con default `true` (compatibilidad) y descripción clara: "Guardar contraseña en accounts.json (inseguro en Windows/Android). Desactiva si prefieres importar cookies."
  2. En `accounts.py`: al guardar una cuenta, si `store_password` es `false`, guardar `password=""` y marcar `auth_method="cookies"`.
  3. En `accounts_ui.py`: añadir diálogo "Importar cookies" que:
     - Pida al usuario pegar las cookies de Chomikuj (formato `PHPSESSID=...; chomikujpl=...`).
     - O pida al usuario un fichero `cookies.txt` exportado con extensión de navegador.
     - Guarde las cookies en `cookies.lwp` vía `Session.save()`.
     - Marque la cuenta como `auth_method="cookies"`.
  4. En `auth.login`: si `auth_method == "cookies"`, cargar `cookies.lwp` y verificar sesión (hacer un GET a la home y comprobar marcador `Wyloguj`); si falla, pedir al usuario reimportar cookies.
  5. En `common.py`: revisar `save_accounts` para no romper compatibilidad con cuentas antiguas que sí tienen password.
  6. Documentar en README (EN): "Your password is stored in plain text in `accounts.json` by default. You can disable this in Settings → Accounts → Store password, and authenticate via imported cookies instead."
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_accounts_auth.py` (nuevo)
  - casos:
    - Cuenta guardada con `store_password=false` no tiene password en el JSON.
    - Login con `auth_method="cookies"` carga de `cookies.lwp` y verifica sesión.
    - Cuenta antigua (con password) sigue funcionando igual.
    - `accounts.json` no se modifica si el usuario no guarda.
- **Criterios de aceptación:**
  - [ ] Un usuario puede configurar "no guardar contraseña" y autenticarse por cookies.
  - [ ] El fichero `accounts.json` no contiene password en ese modo.
  - [ ] Cuentas existentes con password siguen funcionando.
  - [ ] Tests nuevos pasan; existentes verdes.
  - [ ] README actualizado con la nota de seguridad.
- **Cómo verificar a mano:** Configurar "no guardar contraseña", añadir cuenta por cookies, reiniciar Kodi, verificar que la sesión persiste y que `accounts.json` no tiene password.
- **Riesgos / notas:**
  - **Bloqueado por**: ninguna dependencia técnica, pero conviene hacerlo después de F27 (estabilidad de base).
  - Este bloque roza la seguridad del usuario; cualquier error aquí es crítico. Tests exhaustivos obligatorios.
  - No eliminar `accounts.json` ni migrar automáticamente. Solo ofrecer la opción.
- **Estado:** [ ]

### F12 — `import errno` al bloque de imports

- **Origen:** nota de F08
- **Gravedad:** bajo (estilo)
- **Archivos a tocar:** `resources/lib/downloadqueue.py`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c chore/f12-import-errno` / `git commit -m "F12: mover import errno al bloque de imports en downloadqueue"`
- **Objetivo (1 frase):** Mover `import errno` del `except OSError` interno al bloque de imports de módulo, sin cambiar comportamiento.
- **Cambios concretos:**
  1. Localizar `import errno` dentro de `_download_one` (introducido en F08).
  2. Borrarlo de ahí.
  3. Añadir `import errno` al bloque de imports del principio del módulo, junto a `os`, `re`, `random`, etc.
  4. No cambiar nada más.
- **Tests a añadir o actualizar:** ninguno. Los tests existentes de `downloadqueue` deben seguir verdes.
- **Criterios de aceptación:**
  - [ ] `pytest -q` verde.
  - [ ] `git diff master -- downloadqueue.py` es un cambio de 2 líneas (quitar uno, añadir otro).
  - [ ] Sin cambios funcionales.
- **Cómo verificar a mano:** No aplica.
- **Riesgos / notas:** Ninguno.
- **Estado:** [ ]

### F13 — `notify` en `search._build_index` con escaneo incompleto

- **Origen:** nota de F02
- **Gravedad:** bajo
- **Archivos a tocar:** `resources/lib/search.py`, opcionalmente `strings.py` y `.po`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c chore/f13-search-notify` / `git commit -m "F13: notify al usuario cuando el índice de búsqueda no se pudo completar"`
- **Objetivo (1 frase):** Que el usuario sepa que la búsqueda falló por red/sesión, en lugar de ver "0 resultados".
- **Cambios concretos:**
  1. En `search._build_index`, en el `except WalkIncomplete` (introducido en F02), añadir `notify(strings.t(ID))` además del `k.log`.
  2. Elegir el ID de string más adecuado. Si existe uno tipo "Error de red" o "No se pudo completar la operación", usarlo. Si no, añadir uno nuevo a `strings.py` y a ambos `.po`:
     - EN: "Search index could not be completed due to a network error. Try again later."
     - ES: "El índice de búsqueda no se pudo completar por un error de red. Inténtalo más tarde."
  3. Mantener el `return None` después del notify.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_search_index_notify.py` (nuevo)
  - casos:
    - `_build_index` con walker que lanza `WalkIncomplete` llama a `notify` exactamente una vez.
    - Sigue devolviendo `None`.
    - No escribe el JSON.
    - Sin cambios en el caso de walker completo.
- **Criterios de aceptación:**
  - [ ] `notify` se llama en el caso de escaneo incompleto.
  - [ ] `pytest -q` verde.
  - [ ] Cambio mínimo (1-2 líneas en `search.py` + nuevo string si aplica).
- **Cómo verificar a mano:** Desconectar red a mitad de la indexación de búsqueda; debe aparecer notificación, no "0 resultados" silencioso.
- **Riesgos / notas:** Si se decide añadir nuevo string a `strings.py`, hay que tocar `strings.py` **y** los dos `.po`. Si el usuario prefiere no tocar traducciones ahora, usar un ID existente (aunque el mensaje sea menos preciso).
- **Estado:** [ ]

---

## 1.14.1 — Scraping robusto

### F17 — Endurecer regex de login y paginación

- **Origen:** informe, M8 (login) + hallazgo de fixtures (paginación)
- **Gravedad:** medio
- **Archivos a tocar:** `resources/lib/auth.py`, `resources/lib/listing.py`
- **Depende de:** fixtures en `tests/fixtures/` (commit `0efa718`)
- **Rama/commit sugerido:** `git switch -c fix/f17-regex-hardening` / `git commit -m "F17: regex de login y paginación validadas contra HTML real de Chomikuj"`
- **Objetivo (1 frase):** Que el addon detecte correctamente el login y la paginación con el HTML real de Chomikuj 2026, no con marcadores obsoletos.
- **Cambios concretos:**
  1. En `auth.py:14`, sustituir `_OK_MARKERS = ('"LoggedIn":true', '"IsSuccess":true', "ChomikToolbar.IsLogged = true")` por marcadores confirmados en fixtures. Reportar primero al usuario qué marcadores aparecen realmente en `folder_normal.html` y `search_results.html` (por ejemplo, `Wyloguj`, `logout`, acción `LogOut`). Cambiar los marcadores solo tras confirmación.
  2. En `listing.py`, la detección de "no logueado" debe usar marcadores presentes en `folder_protected.html` cuando se pide contraseña: por ejemplo, presencia de `<form.*LoginToFolder` o el campo `ChomikId`. Verificar contra el fixture.
  3. Añadir un helper `is_logged_in(html)` en `auth.py` que devuelva `True`/`False` de forma robusta, con tests.
  4. Mantener compatibilidad con el endpoint AJAX `/action/Login/Login` para el login programático, pero añadir fallback a los marcadores del HTML si el JSON no los tiene.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_auth_regex.py` (nuevo)
  - casos:
    - `folder_normal.html` → `is_logged_in` devuelve `True`.
    - `search_results.html` → `is_logged_in` devuelve `True`.
    - `folder_protected.html` → `is_logged_in` devuelve `True` (el usuario ya está logueado, la carpeta pide password extra, no es un problema de sesión).
    - HTML de login fallido (fixture sintético `tests/fixtures/login_failed.html` con `<form.*Login.*bad credentials>` o similar) → `is_logged_in` devuelve `False`.
- **Criterios de aceptación:**
  - [ ] Los cuatro tests pasan.
  - [ ] Los marcadores nuevos están documentados en un comentario en `auth.py`.
  - [ ] No hay regresión en el login actual (probar con `Sechel` en Kodi tras el cambio).
- **Cómo verificar a mano:** Login con `Sechel`, cerrar y reabrir Kodi, verificar que no pide credenciales de nuevo. Y que al hacer `Container.Refresh` la sesión sigue activa.
- **Riesgos / notas:**
  - **Bloqueado por**: primero hay que verificar qué marcadores reales aparecen en los fixtures. PÁRATE en el Paso 1 y reporta antes de cambiar `auth.py`.
  - Si Chomikuj cambia de nuevo el HTML, los fixtures quedarán obsoletos. Conviene actualizarlos periódicamente.
- **Estado:** [ ]

### F10 — `clean()` no rompe con `&quot;`

- **Origen:** informe, M2
- **Gravedad:** bajo (sintético, no reproducible en producción)
- **Archivos a tocar:** `resources/lib/common.py`, `resources/lib/listing.py`
- **Depende de:** fixture sintético en `folder_normal.html` (marcado con comentario HTML `SYNTHETIC`)
- **Rama/commit sugerido:** `git switch -c fix/f10-clean-quotes` / `git commit -m "F10: clean() no convierte &quot; antes de parsear atributos"`
- **Objetivo (1 frase):** Que un título con `&quot;` (imposible en Chomikuj hoy, pero defensivo) no se trunque al parsear `title="..."`.
- **Cambios concretos:**
  1. En `common.py`, revisar la función `clean()` y `dictionary.py`. `&quot;` se sustituye por `"` antes de aplicar la regex `title="([^"]+)"`. Eso hace que la regex se corte en la primera comilla interior.
  2. Opción A: no aplicar `&quot;`→`"` en `clean()` cuando el texto va a ser parseado con regex de atributos; dejar que `html.unescape` lo resuelva después de extraer el atributo.
  3. Opción B: parsear primero (regex sobre `&quot;` literal) y aplicar `clean()` sobre el valor extraído.
  4. Elegir la opción con el fixture real (`folder_normal.html` sintético). Si la opción A rompe otros usos de `clean()`, usar B.
  5. Aplicar el cambio en `listing.py` (2 sitios) y `library.py:350` si se decide tocar el consumidor en lugar de `clean()`.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_clean_quotes.py` (nuevo)
  - casos:
    - `folder_normal.html` (sintético): un título con `&quot;` se captura entero.
    - `folder_normal.html` (sin la parte sintética): resultados idénticos a hoy.
    - `search_results.html`: resultados idénticos a hoy (no regresión).
- **Criterios de aceptación:**
  - [ ] El título con `&quot;` sintético se captura completo.
  - [ ] Los otros títulos de los fixtures se capturan igual que antes.
  - [ ] No hay regresión en `search_results.html`.
  - [ ] `pytest -q` verde.
- **Cómo verificar a mano:** No aplica (el caso no se produce en producción). Verificar con el fixture sintético en tests.
- **Riesgos / notas:** Como Chomikuj rechaza `"` en nombres de archivo, este fix es **defensivo**. Si en el futuro Chomikuj lo permite, ya estará cubierto. Si en algún momento se decide no tocar `clean()` (alto riesgo de regresión), F10 puede archivarse y solo mantener el test sintético que documente el comportamiento actual.
- **Estado:** [ ]

### F15 — `temp.txt` no contamina paginación

- **Origen:** informe, M1
- **Gravedad:** medio
- **Archivos a tocar:** `resources/lib/listing.py`, `resources/lib/search.py`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c fix/f15-temp-pagination` / `git commit -m "F15: paginación no usa temp.txt tras búsqueda global"`
- **Objetivo (1 frase):** Que el "siguiente" de una carpeta navegada después de una búsqueda global no muestre resultados de la búsqueda vieja.
- **Cambios concretos:**
  1. Localizar `listing.py:514`: `or st.addon.load_data('temp.txt')`.
  2. Localizar dónde se escribe `temp.txt`: `listing.py:149` y `search.py:282`.
  3. Eliminar la lectura de `temp.txt` como fallback de paginación. La paginación debe basarse en la URL actual (`mode=23`/`24` + `term` + `page`), no en estado de fichero.
  4. Si el paginador necesita `term`, extraerlo del parámetro `url` actual (`?term=...`), no de `temp.txt`.
  5. Dejar de escribir `temp.txt` (borrar los dos sitios que lo escriben).
  6. Si algún flujo depende de `temp.txt` (por ejemplo, "última búsqueda" en UI), leer del parámetro URL en lugar de fichero.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_pagination_state.py` (nuevo)
  - casos:
    - Navegar de una búsqueda a una carpeta y pulsar "siguiente": usa la URL de la carpeta, no `temp.txt`.
    - Múltiples búsquedas consecutivas: cada una mantiene su `term` en la URL, no se contaminan.
    - `temp.txt` no se lee en ningún flujo de paginación.
- **Criterios de aceptación:**
  - [ ] Paginación de carpeta después de búsqueda funciona correctamente.
  - [ ] `temp.txt` no se escribe ni se lee.
  - [ ] Búsqueda global sigue funcionando (modo 23/24).
  - [ ] `pytest -q` verde.
- **Cómo verificar a mano:** Buscar algo (modo 23/24), volver atrás, entrar en una carpeta, pulsar "siguiente". Debe mostrar la página siguiente de la carpeta, no de la búsqueda.
- **Riesgos / notas:** Si hay flujos que dependen de `temp.txt` que no detectamos, se romperán. Buscar exhaustivamente con `grep -rn "temp.txt" resources/`.
- **Estado:** [ ]

### F18 — Bajos sueltos (tools, subtitles, prefetch, state)

- **Origen:** informe, sección "Bajo"
- **Gravedad:** bajo
- **Archivos a tocar:** `resources/lib/tools.py`, `resources/lib/subtitles.py`, `resources/lib/listing.py`, `resources/lib/state.py`, `resources/lib/browse.py`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c chore/f18-low-priority` / `git commit -m "F18: varios arreglos menores (logs, prefetch, state)"`
- **Objetivo (1 frase):** Cerrar 4 bugs bajos del informe en un solo commit de limpieza.
- **Cambios concretos:**
  1. **`tools.py:29`**: `text.replace(user, '<usuario>')` sin límites. Cambiar a `text.replace(user, '<usuario>')` con `if len(user) >= 3` para evitar que un usuario corto (como "a") destroce el log.
  2. **`subtitles.py`**: cambiar `xbmc.log(...)` por `k.log(...)` con `kodiutils.redact` para evitar volcar tokens en el log. Y bajar el nivel del volcado de respuesta de login de `DEBUG` a `INFO` o eliminarlo.
  3. **`listing.py:557`**: hilo de prefetch sin `daemon=True`. Añadir `daemon=True` al `threading.Thread(...)`.
  4. **`browse.main` / `state.init()` doble**: revisar si `state.init()` se llama dos veces en algunos flujos (browse.main + play_entry). Si es así, mover a un punto único o hacerlo idempotente.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_low_priority.py` (nuevo)
  - casos:
    - `tools.replace_user_in_log("usuario", "corto")` con `user="a"` no reemplaza "a" en cada palabra.
    - `state.init()` llamado dos veces no crashea y no reinicia estado.
    - El hilo de prefetch es daemon (verificar `thread.daemon == True` si es inspeccionable).
- **Criterios de aceptación:**
  - [ ] Los 4 cambios aplicados.
  - [ ] `pytest -q` verde.
  - [ ] No hay regresión en logs (verificar que los logs de subtitles siguen saliendo pero sin tokens).
- **Cómo verificar a mano:** Revisar `kodi.log` tras un ciclo de búsqueda + subtítulos, confirmar que no hay tokens en el log.
- **Riesgos / notas:** Cuatro cambios en un commit. Si alguno causa regresión, difícil de aislar. Alternativa: cuatro commits pequeños en la misma rama.
- **Estado:** [ ]

---

## 1.15.0 — UX y features pequeñas

### F20 — Renovar enlace si falla reproducción

- **Origen:** informe, sección 5 (quick win)
- **Gravedad:** mejora de UX
- **Archivos a tocar:** `resources/lib/playstate.py`, `resources/lib/playback.py`, `resources/lib/resolver.py`
- **Depende de:** F03 (hecho en 1.13.0)
- **Rama/commit sugerido:** `git switch -c feat/f20-retry-on-error` / `git commit -m "F20: reintentar reproducción renovando el enlace si falla"`
- **Objetivo (1 frase):** Que si un enlace caduca a mitad de reproducción (`onPlayBackError`), el addon re-resuelva una vez y vuelva a intentar, sin molestar al usuario.
- **Cambios concretos:**
  1. En `playstate.PlayerMonitor`, `onPlayBackError` (introducido en F03) ahora limpia estado. Extender: guardar la URL original (`page_url`) y el `key` en un atributo `self._last_failed` con timestamp.
  2. En `playback.py`, donde se llama a `player.play(...)`, envolver en un bucle de 2 intentos. Si el primer intento falla con `onPlayBackError`, renovar el enlace (`resolver.get_link(page_url)`) y reintentar una vez.
  3. Límite: máximo 1 reintento por reproducción. Si falla dos veces, mostrar `notify("No se pudo reproducir el archivo. Inténtalo de nuevo más tarde.")`.
  4. No reintentar si el usuario canceló manualmente (distinguir "cancel" de "error").
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_retry_playback.py` (nuevo)
  - casos:
    - `onPlayBackError` marca la reproducción como fallida y permite reintento.
    - Un reintento exitoso no propaga error.
    - Dos fallos seguidos muestran notify y no reintentan más.
    - Cancelación manual no dispara reintento.
- **Criterios de aceptación:**
  - [ ] Un enlace caducado se reintenta una vez y funciona.
  - [ ] Dos fallos seguidos muestran mensaje al usuario.
  - [ ] Cancelación manual no dispara reintento.
  - [ ] `pytest -q` verde.
- **Cómo verificar a mano:** Reproducir un archivo, cortar la red 3 s, restaurar. Debe recuperarse con un reintento.
- **Riesgos / notas:** No reintentar en bucle infinito. Límite duro de 1 reintento.
- **Estado:** [ ]

### F19 — Subtítulos sidecar

- **Origen:** informe, sección 5
- **Gravedad:** mejora de UX
- **Archivos a tocar:** `resources/lib/subtitles.py`, `resources/lib/listing.py`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c feat/f19-sidecar-subs` / `git commit -m "F19: subtítulos sidecar (.srt) desde la misma carpeta de Chomikuj"`
- **Objetivo (1 frase):** Antes de llamar a OpenSubtitles.org (API a punto de cerrar), buscar un `.srt` con el mismo nombre base que el vídeo en la misma carpeta de Chomikuj.
- **Cambios concretos:**
  1. En `subtitles.getsubtitles(name, lang1, lang2)`:
     - Primero, buscar en el listado de la carpeta actual un archivo `.srt` cuyo `stem` coincida con el `stem` del vídeo (case-insensitive, tolerar sufijos como `.en.srt`, `.es.srt`, `.forced.srt`).
     - Si se encuentra, descargar el `.srt` a temp y pasarlo a Kodi (`item.setSubtitles([path])`).
     - Si no hay sidecar, fallback a OpenSubtitles (comportamiento actual).
  2. El listado de la carpeta actual ya está en `st` (state) tras navegar. Reutilizarlo en lugar de hacer otra petición.
  3. Si no hay `.srt`, log informativo y fallback.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_sidecar_subs.py` (nuevo)
  - casos:
    - Sidecar exacto (`nombre.mkv` + `nombre.srt`) se detecta.
    - Sidecar con sufijo de idioma (`nombre.en.srt`) se detecta como inglés.
    - Sidecar con nombre distinto no se detecta.
    - Sin sidecar, fallback a OpenSubtitles.
- **Criterios de aceptación:**
  - [ ] Con sidecar en la carpeta, Kodi lo usa automáticamente.
  - [ ] Sin sidecar, comportamiento igual que hoy.
  - [ ] `pytest -q` verde.
- **Cómo verificar a mano:** Subir un `.mkv` y un `.srt` con mismo nombre base a Chomikuj, reproducir, verificar subtítulos cargados.
- **Riesgos / notas:** La API de OpenSubtitles.org cierra en 2026. F19 es preparación para el fin. Si no se implementa, los subtítulos dejarán de funcionar.
- **Estado:** [ ]

### F23 — Tráiler vía TMDb

- **Origen:** informe, sección 5
- **Gravedad:** mejora cosmética
- **Archivos a tocar:** `resources/lib/metadata.py`, `resources/lib/playback.py`, `resources/settings.xml`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c feat/f23-tmdb-trailer` / `git commit -m "F23: tráiler vía TMDb, elimina dependencia de YouTube API key"`
- **Objetivo (1 frase):** Reproducir el tráiler usando el ID de YouTube que TMDb ya devuelve, sin pedir al usuario que configure su propia YouTube API key.
- **Cambios concretos:**
  1. En `metadata.py`, `get_movie_info` / `get_tv_info` ya devuelve `youtube_trailer_id` (o similar). Confirmar.
  2. En `playback.trailer(...)`: en lugar de llamar a YouTube Data API (que requiere clave del usuario), construir la URL `plugin://plugin.video.youtube/play/?video_id=<id>` (si el usuario tiene YouTube addon) o `https://www.youtube.com/watch?v=<id>` (resolver vía `resolver`).
  3. En `settings.xml`: eliminar o marcar como obsoleto el setting `youtube_api_key`. Migrar a opcional.
  4. En README (EN): "Trailers use TMDb's YouTube ID. The YouTube API key setting is no longer required."
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_trailer_tmdb.py` (nuevo)
  - casos:
    - `trailer("Inception")` devuelve URL con ID de YouTube correcto (mock TMDb).
    - Sin ID de TMDb, no falla y muestra notify.
- **Criterios de aceptación:**
  - [ ] Tráiler se reproduce sin YouTube API key configurada.
  - [ ] Si no hay ID de TMDb, mensaje claro al usuario.
  - [ ] `pytest -q` verde.
- **Cómo verificar a mano:** Sin YouTube key, buscar una peli, pulsar "tráiler", verificar reproducción.
- **Riesgos / notas:** Si el usuario tiene instalado el addon YouTube para Kodi, mejor usar `plugin://`; si no, resolver URL directa. Preguntar al usuario qué prefiere.
- **Estado:** [ ]

---

## 1.16.0 — Limpieza técnica

### F16 — Limpiar código muerto

- **Origen:** informe, M7
- **Gravedad:** bajo (mantenibilidad)
- **Archivos a tocar:** `resources/lib/listing.py`, `resources/lib/browse.py`, `resources/lib/playlist.py`, `resources/lib/router.py`
- **Depende de:** ninguno
- **Rama/commit sugerido:** `git switch -c chore/f16-dead-code` / `git commit -m "F16: eliminar código muerto (playlist, folder-type, modos 1/9)"`
- **Objetivo (1 frase):** Quitar el bloque de playlist que nunca se ejecuta, la config `folder-type` inerte, y los modos 1 y 9 que ningún menú enlaza.
- **Cambios concretos:**
  1. **Playlist muerta en `listing.py`:** `ReturnConteudo(..., return_file_list=listagem)` devuelve `[]` salvo con `listagem=True`. El bloque `if reslist:` en `listing.py:284` nunca se ejecuta en listado normal. Eliminar el bloque o simplificarlo. Confirmar antes con `grep -rn "add_items_to_playlist_db\|clear_playlist_db" resources/lib/`.
  2. **`clear_playlist_db()` en `listing.py:280`:** se llama en cada listado, aunque el bloque posterior no se ejecute. Eliminar la llamada si no hay consumidor real.
  3. **`folder-type` setting:** es inerte salvo que con valor 1 suprime paginación en resultados de búsqueda. Revisar y eliminar, o documentar el efecto.
  4. **Modos 1 y 9:** `topcolecionadores` y `favoritos` existen en el dispatch de `router.py`/`browse.py` pero ningún menú los enlaza. Eliminar del dispatch o dejar comentados con nota.
  5. **Funciones sin llamadas:** `_search_filters_dialog`, `_search_type_options`, `SearchResults`, `SearchResultsFora`, `getKey`, `ReturnStatus`, `openfile`, `accounts.set_active`, `player.show_image`. Verificar con `grep -rn "nombre" resources/lib/` y eliminar las que no tengan consumidor.
- **Tests a añadir o actualizar:** ninguno funcional. Añadir `tests/test_no_dead_imports.py` que verifique que los módulos importan sin errores tras la limpieza.
- **Criterios de aceptación:**
  - [ ] Código eliminado no se usa en ningún sitio (`grep` confirma).
  - [ ] `pytest -q` verde.
  - [ ] `compileall` sin errores.
  - [ ] Reducción de líneas totales en `resources/lib/`.
- **Cómo verificar a mano:** Navegar, buscar, reproducir. Todo debe seguir funcionando igual.
- **Riesgos / notas:** Es M y requiere cuidado. Si algo estaba "muerto pero conectado" (por ejemplo, un setting que activa un flujo), se rompe. Verificar cada eliminación con `grep` antes de tocar.
- **Estado:** [ ]

### F14 — `ReplaceSpecialChar` folding

- **Origen:** informe, M6 (complemento)
- **Gravedad:** bajo
- **Archivos a tocar:** `resources/lib/common.py`
- **Depende de:** análisis previo de uso en rutas
- **Rama/commit sugerido:** `git switch -c chore/f14-fold-replace` / `git commit -m "F14: ReplaceSpecialChar usa el mismo plegado que _norm (si es seguro)"`
- **Objetivo (1 frase):** Aplicar a `ReplaceSpecialChar` el mismo plegado de `ł`, `đ`, `ø`, `ß`, `æ`, `œ` que ya tiene `_norm` en `search.py`, **solo si** su salida no se usa para rutas ni claves persistidas.
- **Análisis previo (obligatorio):**
  1. `grep -rn "ReplaceSpecialChar" resources/lib/`
  2. Para cada call site, identificar si la salida va a rutas o nombres de fichero (`real_fs_name`, `clean_folder`, STRM, descargas).
  3. Si **algún** call site usa la salida para rutas persistidas, **NO tocar** `ReplaceSpecialChar`. En su lugar, crear `ReplaceSpecialCharDisplay` (nueva función) que solo se use en contextos de UI/búsqueda.
- **Cambios concretos:**
  - Si es seguro: aplicar `_FOLD` de `search.py` antes del NFKD en `ReplaceSpecialChar`.
  - Si no es seguro: crear `ReplaceSpecialCharDisplay` nueva, usarla solo en `search.py` y `clean_title`.
- **Tests a añadir o actualizar:**
  - archivo: `tests/test_replace_special.py` (nuevo)
  - casos:
    - `ReplaceSpecialChar("Łódź")` → `"lodz"` (o nuevo comportamiento).
    - Si se creó `ReplaceSpecialCharDisplay`, test específico.
    - Rutas existentes (STRM, descargas) no cambian.
- **Criterios de aceptación:**
  - [ ] Análisis confirmado: la salida no se usa para rutas persistidas.
  - [ ] Si es seguro, `ReplaceSpecialChar` pliega los caracteres.
  - [ ] Si no es seguro, se crea `ReplaceSpecialCharDisplay` y se usa solo en UI.
  - [ ] `pytest -q` verde.
- **Riesgos / notas:** Si hay duda, **no tocar**. F14 puede archivarse sin consecuencias (el problema real de búsqueda ya está resuelto en F06).
- **Estado:** [ ]

---

## 1.17.0 — Refactor y features grandes (futuro)

Sin fechas. Se planificará cuando 1.16.0 esté estable.

### F30 — Cliente HTTP único

- **Objetivo:** Unificar `Session` (moderno) y `t0mm0.Net` (legacy) en un solo cliente con reintentos, cookies y excepciones consistentes.
- **Alcance:** `session.py`, `t0mm0.py` (eliminar), todos los módulos que usen `net.http_*`. Eliminar `chomikdb.db` (segunda SQLite). Unificar `_get_link` duplicado en `router.py`, `playback.py`, `downloadqueue.py`.
- **Riesgo:** Alto. Toca toda la red.
- **Estado:** [ ]

### F31 — Eliminar estado global y activar `reuselanguageinvoker`

- **Objetivo:** Quitar `state.py` como variables de módulo, `metadata.parent_name` global, `Net._cj` de clase. Activar `reuselanguageinvoker` en `addon.xml` para acelerar invocaciones en Kodi 21+.
- **Depende de:** F30.
- **Riesgo:** Alto. Sin tests de integración robustos, no tocar.
- **Estado:** [ ]

### F21 — Reproducir carpeta como cola

- **Objetivo:** Desde una carpeta, botón "Reproducir todo" que encola todos los archivos y arranca el primero. Útil para series.
- **Depende de:** F20.
- **Estado:** [ ]

### F24 — "Continuar viendo"

- **Objetivo:** Entrada en el menú raíz con historial de progreso. Requiere migración de `progress.key` (hash) a `progress.url` para poder navegar al archivo.
- **Depende de:** F20.
- **Estado:** [ ]

### F25 — Búsqueda global rediseñada

- **Objetivo:** Paginación por URL (`mode=24&term=...&page=N`), sin `temp.txt`. Ya preparado por F15.
- **Depende de:** F15.
- **Estado:** [ ]

### F26 — STRM programado desde el servicio

- **Objetivo:** Regenerar STRM de una carpeta periódicamente desde el servicio (cron interno). Reutiliza `create_strm_files_recursive_chomiteca` con la guardia de F02.
- **Depende de:** F02 (hecho), F04 (hecho).
- **Estado:** [ ]

---

## Fuera de alcance

| Excluido | Por qué |
|---|---|
| Cambios en regex HTML sin fixtures | Necesita fixtures reales; ya los tenemos para los casos clave |
| Anti-inactividad, scraping paralelo | Riesgo de bloqueo por Chomikuj |
| Renombrar `strings.py` o `.po` masivamente | Tres fuentes de verdad; solo tocar strings específicos cuando F13 lo requiera |
| Rediseño de UI | No es objetivo de este fork |
| Nuevas fuentes de contenido | Fuera de alcance |

---

## Notas de mantenimiento

- **Fixtures:** si Chomikuj cambia el HTML, regenerar los fixtures con el mismo procedimiento documentado en el hilo de 1.14.0. Marcar la fecha de captura en un comentario dentro del HTML.
- **Tests:** cada bloque debe añadir al menos un test. Los bloques XS pueden reutilizar tests existentes si no hay lógica nueva.
- **Commits:** mensaje siempre `F{ID}: descripción corta`. Sin emojis, sin mayúsculas al principio del cuerpo.
- **Ramas:** `fix/f{ID}-slug` para fixes, `feat/f{ID}-slug` para features, `chore/f{ID}-slug` para limpieza.
- **Merge a master:** `git merge --no-ff` con mensaje `merge F{ID}: descripción`. Tag `v{X.Y.Z}` tras el merge. Push y release al final de cada versión.