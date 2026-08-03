# QA E2E — Gate final de calidad pre-paper

*2026-07-30/31. Corrido después de que la serie de 8 SNR50 quedó
CONGELADA (commit `1090fc4`). El QA reporta; los fixes de esta pasada
(off-by-one de `interferometry.py`, detector de QA-08, 11 documentos
con números muertos, CHANGELOG) están explícitamente autorizados y
aplicados — ver Bloque 2 de la conversación que cerró este gate. Bloque
A intacto: los tests nuevos (`tests/analytical/`) EJERCITAN el código,
nunca lo modifican; la única corrección de código real
(`interferometry.py:301`) es un demo standalone fuera del path de
medición de SNR50. Cerrado — sin segunda pasada de QA.*

## Resumen ejecutivo

**14 hallazgos, decisión tomada en los 14: 2 CRÍTICO corregidos, 1 MAYOR
resuelto en la propia pasada, 1 MAYOR cerrado por evidencia (no era
real), 3 MAYOR a backlog documentado, 6 MENOR a backlog (uno con fix
aplicado), 1 no aplica.** Los dos CRÍTICO (números muertos "spread
3.7×"/"pytest 20/20" en los documentos que alimentan el paper) están
corregidos en los 11 archivos donde aparecían, con un erratum en
CHANGELOG para el release v1.1.0 ya publicado (no editado
retroactivamente). El motor de decisión pasa 102/102 tests (incluidas
las 8 fórmulas físicas re-derivadas independientemente en
`tests/analytical/`) — mejor verificado que la documentación que lo
describe, que ya está corregida también. Cierre de la investigación
B5/arcata: determinismo total confirmado (cero aleatoriedad sin
sembrar) y cero cambios funcionales de código desde antes de la primera
medición de arcata — la discrepancia de reproducibilidad (arcata Y
ridgecrest_north) es de lista de archivos de la era pre-F1.1, no de
código, y el claim central de la serie es robusto incluso si esos 3
arrays estuvieran mal medidos (máximo ρ alcanzable en el peor caso:
~~0.65~~ **0.6506** — corregido 2026-08-02, no cruza 0.7381; ver 3.3
para el detalle y la fe de erratas completa).

**Addendum 2026-08-01 (Bloque 4, ver 2.6/2.8/2.9)**: cerrar QA-06 (CI
verificable) resultó ser tres hallazgos independientes apilados, no
uno — el trigger de `ci.yml`, el extra `tdms` faltante (**QA-15**,
MAYOR, con fix) y `ruff` sin pin exacto (**QA-16**, MAYOR, con fix,
mismo patrón de reproducibilidad ya documentado para numpy/mypy). Con
las tres capas resueltas, las 3 versiones soportadas (3.10/3.11/3.12)
corren la suite completa en verde por primera vez desde que existe esa
suite ampliada — PR draft #3 cerrado sin mergear tras confirmarlo.
Total de hallazgos del gate: **16** (14 originales + 2 de este
addendum).

---

## QA-1 — Física: validación contra soluciones cerradas

`tests/analytical/test_closed_form.py`: **102/102 tests verdes en toda
la suite** (era 101/102 al momento del primer reporte — la única falla
era el detector de QA-1.8/QA-08, resuelta más abajo).

| # | Qué se verificó | Resultado | Evidencia |
|---|---|---|---|
| 1.1 | `snr_to_amplitude` round-trip exacto (5 SNR objetivo) + invariancia de escala (×1000/÷1000) + sobrevive upcast desde float16/int16 | **PASA** | `test_snr_to_amplitude_round_trip_exact`, `test_snr_to_amplitude_scale_invariant`, `test_snr_to_amplitude_survives_low_precision_origin_upcast`; la propiedad de no-redondeo la cubren, mejor calibrados, `tests/test_replay_hdf5_generic.py::test_injection_arithmetic_never_rounds_through_float16` y `tests/test_replay_tdms.py::test_low_snr_injection_survives_int16_source_via_tdms` |
| 1.2 | Onda plana a v conocida (2000/4000/6500 m/s × dx=2m/16.8m) → pico de semblanza en el punto de grilla más cercano; semblanza en [0,1]; señal limpia →>0.9; ruido blanco →~1/n_ch | **PASA**, las 6 combinaciones exactas (`rel=1e-9`) | `test_plane_wave_semblance_peak_matches_known_velocity` + 2 tests más |
| 1.3 | Theil-Sen sobre onsets de pendiente conocida, de punta a punta | **PASA**, error relativo <2% | `test_theilsen_recovers_known_slope_directly`, `test_fit_onset_velocity_end_to_end_recovers_known_slope` |
| 1.4 | `v_app_max_resoluble(L,fs,k)==L·fs/k` exacto; velocidad fuera de grilla → `boundary_pinned=True` | **PASA**. Nota: `v_app_max_resoluble` es puramente informativo dentro de `coherence.analyze()` (solo en `explanations` de REGIONAL_EMERGENT) — el guard real en el árbol de decisión es `_velocity_peak_is_boundary`, verificado por separado | `coherence.py:653,659` |
| 1.5 | Re-derivar `13.6+0.001833·aperture_m` desde las piezas reales de `inject_and_verify_sized` | **CONFIRMADO CORRECTO**, no un hallazgo. **Reescrito 2026-08-01** (ver `docs/observaciones.md`): la versión original nunca llamaba a `inject_and_verify_sized` — reconstruía su aritmética a mano en el test con piezas reales (`Tier0Config().warmup_s`, `pipeline_margin_s()`, `ricker()`) pero sin ejercitar la función real, así que un bug en cómo `inject_and_verify_sized` ensambla esas piezas no se habría detectado. La versión nueva llama la función real con ruido justo por debajo/encima del piso documentado y verifica que acepte/rechace (`None`/no-`None`) exactamente donde la fórmula predice — la formula queda verificada contra comportamiento real, no contra una relectura de su código. Mismo resultado (formula sigue confirmada), método más fuerte. | `test_noise_floor_constants_rederived_from_real_code` |
| 1.6 | `W=3.5s` contra el default real; techo `W/T` con Valencia/FOSSA como casos cerrados | **PASA**, ±0.02 absoluto | `test_coincidence_fraction_matches_w_over_t_closed_form` |
| 1.7 | STA/LTA en los 5 fs reales (100/125/200/250/500Hz) | **PASA** | `test_sta_lta_warmup_boundary_exact_at_each_real_fs` |
| 1.8 | Grep de apertura mal calculada, ampliado (E2, 2026-07-31) a variantes semánticas (`n_channels*dx`, `n_ch*spacing`, `channel_spacing(_m)`, `len(...)*dx`), excluyendo `QA_REPORT.md`/`observaciones.md` (registros históricos que citan el patrón en prosa) | **CERRADO — ver QA-08 abajo, código corregido, 0 matches** | `test_no_naked_n_ch_times_dx_aperture_formula_in_source` |
| 1.9 | Wilson CI vs. re-derivación independiente (5 casos borde); `interpolate_snr50` (3 casos borde) | **PASA**, `1e-9` | 4 tests |
| 1.10 | `stationarity_check`, sus dos ramas (recorte y fallback terminal) | **PASA** | 2 tests |

---

## QA-2 — Código: estándares

**2.1 — Cobertura**: sin cambios respecto del primer reporte (los fixes
de esta pasada no tocaron el path de veredicto). `coherence.py` 93%,
`triage.py` 89% — **ver QA-03 abajo para la clasificación por
contenido, ya cerrada**. `snr_curve.py` 25% (núcleo numérico cubierto,
CLI/orquestación no) — backlog, no MAYOR. Resto de módulos fuera del
path crítico (0-57%) — backlog, cubiertos en la práctica por
`darkfiber-validate` (29/29).

**2.2 — Defaults silenciosos**: `load_quakeflow_h5` (conocido,
`run_on_quakeflow.py:132-133`) y `ArrayGeometry` (`contracts.py:23-24`,
nunca ejercitado) — ambos a **backlog en
`PLAN_CIERRE_Y_LANZAMIENTO.md`** con la verificación de D1.3 adjunta
("existe, no se usó" para `load_quakeflow_h5` — los 3 pools QuakeFlow
tenían sus attrs completos).

**2.3 — Determinismo — CERRADO, auditoría exhaustiva repetida (D1.2)**:
14 sitios `default_rng(...)`, TODOS con entero explícito; **cero**
`default_rng()`/`default_rng(None)` sin argumento; **cero**
`np.random.rand`/`random.random`/`random.shuffle`/`random.choice`
sueltos en `src/darkfiber/`. Orden de archivos también determinístico
(`sorted(glob(...))` en las 4 rutas de construcción de `snr_curve.py` +
`calibrate.py`/`run_on_quakeflow.py`/`pipeline_daemon.py`).
**Conclusión, con las palabras exactas pedidas**: la aleatoriedad sin
sembrar queda DESCARTADA como causa de la discrepancia de B5 en TODA la
serie, no solo en las corridas pre-F1.1. Registrado en
`docs/observaciones.md` 2026-07-31.

**2.4 — mypy**: el mypy CONFIGURADO del proyecto pasa limpio. `--strict`
(diagnóstico puntual del gate): 144 errores/18 archivos, cero en
`coherence.py`/`triage.py` más allá de 5/1 respectivamente. **A backlog
en `PLAN_CIERRE_Y_LANZAMIENTO.md`** con desglose completo por módulo —
el diagnóstico ya respondió lo que importaba.

**2.5 — Provenance — CERRADO 2026-08-01, pasa de 3/8 a 0/8**: al
momento de este hallazgo, 3/8 corridas (monterey_bay, ridgecrest_north,
stanford1_campus) tenían schema incompleto por ser anteriores a que
`--files` explícito existiera como práctica estándar. Las 3 quedaron
re-medidas con provenance completa: monterey_bay y ridgecrest_north el
2026-07-31 (2 de 3 dieron valores distintos a los archivados — ver
QA-3/investigación B5), stanford1_campus el 2026-08-01 (sin cambio de
valor, ver `docs/observaciones.md`). **Las 8 corridas activas tienen
hoy `input_files`/`noise_exclusion` completos** — verificación cruzada
en las 3 fuentes (ledger, `array_geometry_table.md`, JSON) en
`docs/observaciones.md` 2026-08-01, cero discrepancias.

**Sigue abierto, sin cambios**: ninguna de las 8 tiene `seeds`/
`checksum` nativos. **Ligado explícitamente**, en
`PLAN_CIERRE_Y_LANZAMIENTO.md`, al backlog ya declarado de auto-sello de
versión (`git rev-parse HEAD` al arrancar la corrida) — es el mismo
problema visto desde el lado de datos y desde el lado de diseño, una
sola entrada de backlog.

**2.6 — CI multi-versión — CERRADO 2026-08-01 (Bloque 4)**: el claim "CI
verde en 3.10/3.11/3.12" estaba sin verificar, y no por una sola razón —
al perseguirlo aparecieron **tres capas independientes de falsa
confianza**, cada una ocultando a la siguiente hasta que se resolvía la
anterior:

- **(a) Trigger de CI mal configurado**: `git push origin dev` (commit
  `3a6a097`, gate original) no disparó nada — `.github/workflows/ci.yml`
  dispara SOLO en `push: branches: [main]` y en `pull_request`, así que
  un push a `dev` no ejecuta CI en absoluto (confirmado vía API pública
  de GitHub: el último run visible era de un PR anterior, 2026-07-22,
  nada posterior al push de ese día). Sin esto resuelto, nunca se
  llegaba a ejecutar nada — la capa (b) era invisible.
- **(b) Extra `tdms` faltante en el install de `ci.yml`**: una vez
  disparado (PR draft #3, dev→main, abierto exclusivamente para poder
  correr CI, sin cruzar la Fase F3 de `PLAN_CIERRE_Y_LANZAMIENTO.md`),
  `pytest` no llegaba a colectar la suite completa —
  `tests/test_replay_tdms.py` importa `nptdms` sin guarda y ese extra
  nunca estuvo en el install de `ci.yml`. Ver **QA-15** para el
  diagnóstico y fix completos — es MAYOR por derecho propio (afecta a
  terceros, no solo a CI).
- **(c) `ruff` sin pin exacto (`ruff>=0.6`)**: incluso con (a) y (b)
  resueltos, el "Format check" seguía fallando en rondas sucesivas
  porque el criterio de formateo de `ruff` cambió entre la versión
  vieja instalada en el entorno de trabajo (0.12.0) y la que CI instala
  en cada corrida fresca (la última disponible, 0.16.1) — verde local,
  rojo en CI, con **cero cambios de código de por medio**. Ver **QA-16**
  para el diagnóstico y fix completos.

Cada capa enmascaraba a la siguiente: hasta no resolver (a) no se veía
(b), y hasta no resolver (b) no se veía (c) (2026-07-31/08-01, el PR
falló primero en formato con la versión vieja de ruff en un commit
donde (b) todavía no se había tocado, así que ni siquiera hay una
corrida histórica que aísle una sola capa a la vez). El claim de "CI
verde" nunca fue una sola verificación pendiente — eran tres,
independientes, y las tres tenían que cerrarse antes de que "verde"
significara algo.

**Resolución final**: las tres capas corregidas (a: se abrió el PR
draft para disparar CI manualmente, sin abrir uno permanente hacia
`main` — F3 sigue gateada; b: ver QA-15; c: ver QA-16). PR draft #3
con **3.10/3.11/3.12 verdes en las 5 etapas** (lint, format, mypy,
tests, validación E2E) — commit `e234cf9`. PR **cerrado sin mergear**
por Alejandro, rama `dev` intacta. Es la primera vez que la suite
ampliada corre de punta a punta en el entorno real de CI desde que
existe.

**2.7 (QA-08, antes clasificado MENOR→MAYOR→MENOR, CERRADO CON FIX)**:
`interferometry.py:301` tenía el mismo off-by-one de apertura
(`n_ch*dx` en vez de `(n_ch-1)*dx`) en la posición de la fuente
sintética del segundo pase del demo de interferometría. Verificado
antes de clasificar (no asumido): **SÍ alimenta un artefacto publicado**
(Figura 11 de `writeup.md`/`.es.md`, y el claim "4/4" de
`tests/test_interferometry.py`) — pero de los 4 checks del demo, los 2
que miden precisión de velocidad usan el pase único (nunca tocan la
línea del bug); el único check que depende del pase asimétrico es una
desigualdad direccional (ganancia de SNR por stacking) que un desfasaje
de 8m sobre 158m no podía voltear. **Corregido** (`(n_ch-1)*dx`),
re-verificado 4/4 sin inestabilidad. Fe de erratas en
`docs/observaciones.md` 2026-07-31.

**2.8 (QA-15, MAYOR, hallazgo nuevo, 2026-08-01) — la suite nunca había
corrido de punta a punta en el entorno real de CI, y el gap es
reproducible por cualquier tercero, no solo un problema de CI**: con
(a) y (c) de 2.6 resueltos, `pytest` seguía sin colectar ni un test:
`tests/test_replay_tdms.py:12` importa `nptdms` a nivel de módulo, sin
guarda, y `ci.yml` **nunca incluyó el extra `tdms`** en su install
(`pip install -e ".[dev,h5,figs]"`) — gap presente desde que el archivo
se agregó en F1.5 (commit `649a345`, 2026-07-28); `ci.yml` no se había
tocado desde el release inicial (2026-07-14). Nadie lo había visto
porque CI jamás había llegado tan lejos: los intentos de 2026-07-31 en
adelante fallaban antes (formato/mypy — ver QA-16 y el punto siguiente),
y los últimos runs verdes (2026-07-22) son anteriores a que el archivo
existiera.

Diagnóstico previo al fix, para descartar que fuera solo config de CI:
un venv limpio con Python 3.10 + `pip install -e ".[dev,h5,figs]"` (el
comando exacto de `ci.yml`, ya con las dependencias realmente pineadas
del proyecto en vez de las sueltas que tenía el entorno de trabajo)
**reprodujo el mismo `ModuleNotFoundError` fuera de CI** — de paso,
mypy limpio en ese mismo venv encontró 2 errores reales que la
verificación anterior (con `mypy`/`numpy` sueltos, no pineados) nunca
había visto: un `# type: ignore[import-untyped]` obsoleto en
`installation_config.py:82` (removido) y un conflicto de tipo de shape
entre dos ramas de asignación en `replay.py:145` (`data: np.ndarray`
declarado antes del `if/elif`, fix mínimo) — mencionados acá porque es
la misma evidencia que confirmó que el venv era fiel a CI antes de usarlo
para diagnosticar `tdms`.

**Confirmado reproducible localmente, no solo en CI**: cualquier
tercero que clone el repo e instale solo los extras que cree necesitar
(siguiendo el patrón documentado por-feature de `pyproject.toml`) se
lleva el mismo `ModuleNotFoundError`. Esto es MAYOR, no config de CI:
afecta reproducibilidad por terceros, el estándar que este proyecto
sostiene explícitamente.

**Corregido con dos fixes complementarios** (uno no sustituye al otro):
`ci.yml` ahora instala `tdms` (CI debe ejercitar la suite completa,
incluido el loader de FOSSA, no saltearlo); y `test_replay_tdms.py`
ahora usa `pytest.importorskip("nptdms")` antes del import real, para
que un clon sin el extra degrade limpio en vez de romper la colección —
alineado con el patrón **ya existente** `test_dashboard.py:19`
(`pytest.importorskip("streamlit")`), que el diagnóstico inicial no
había visto (se corrigió la afirmación de "no hay precedente" en cuanto
apareció evidencia de lo contrario). Nota relacionada, fuera de alcance
de este fix: `test_replay_hdf5_generic.py` importa `h5py` a nivel de
módulo con el mismo patrón sin guarda — hoy no rompe nada porque `h5`
siempre está en el install de CI, pero es la misma clase de fragilidad
si algún día ese extra se saca de la lista por defecto. Backlog, no
bloqueante.

**Verificación final, PR draft #3, commit `e234cf9`**: 3.10/3.11/3.12
verdes en las 5 etapas (lint, format, mypy, tests, validación E2E).
Conteo de tests confirmado localmente en el venv 3.10 fiel a CI:
**101 passed + 1 skipped** (streamlit/dashboard, extra no instalado a
propósito, correctamente guardado) — igual a los 102 de siempre.
Límite de verificación declarado: la API pública de GitHub no expone
el log de texto de los jobs sin permisos de admin (confirmado, 403),
así que el conteo exacto en 3.11/3.12 no se leyó literalmente del
log — se infiere de que las 3 corridas comparten instalación idéntica
de dependencias pineadas y de que no existe ningún
`sys.version_info`/`skipif` condicional por versión en todo el
repo (`tests/`, `src/darkfiber/`, grep sin matches).

**2.9 (QA-16, hallazgo de reproducibilidad, MAYOR, con fix) — tooling de
CI con versión flotante, mismo patrón ya documentado para numpy/mypy,
sin haberse corregido para `ruff`**: `pyproject.toml` tenía
`ruff>=0.6`, sin pin exacto. El entorno de trabajo tenía instalado
`ruff==0.12.0`; CI, al hacer `pip install` en cada corrida fresca,
resuelve siempre la última versión disponible (`0.16.1` al momento de
este hallazgo). El criterio de `ruff format` cambió entre esas dos
versiones — dos archivos que ya estaban en el repo
(`src/darkfiber/snr_curve.py`, `tests/analytical/test_closed_form.py`,
y luego `validacion_real/NOTES.md` en una segunda ronda, un bloque de
código Python embebido en un fence de Markdown) pasaban `ruff format
--check` en 0.12.0 y fallaban en 0.16.1, **con cero cambios de código de
por medio** — verde local, rojo en CI, exactamente la misma familia de
bug que el comentario ya existente en `pyproject.toml` describe para
`numpy`/`mypy` ("local-green/CI-red drift"). La diferencia es que ese
comentario nunca se generalizó a `ruff`, pese a que el mecanismo es
idéntico: una dependencia de tooling (no del código en sí) sin pin
exacto, en un proyecto cuyo argumento central es la reproducibilidad,
es una contradicción directa con ese argumento — no hace falta que
cambie el código para que "pasa/no pasa" cambie de respuesta.

**Corregido**: `ruff==0.16.1` pineado en `pyproject.toml`, con un
comentario explicando el mecanismo (mismo estilo que el de
numpy/mypy, referenciándolo). Reformateados los 3 archivos afectados
contra el pin (`ruff format .`). Re-verificado con `ruff==0.16.1`
instalado localmente (misma versión que resuelve CI): `ruff check`,
`ruff format --check`, ambos limpios. No queda ninguna dependencia de
`[project.optional-dependencies].dev` sin pin exacto salvo `pytest` y
`pre-commit`, que no participan de ningún chequeo determinístico
byte-a-byte (pytest solo colecciona/ejecuta; una salida distinta entre
versiones de pytest sería un test fallando, no un "verde/rojo" mudo
como el de un formateador) — no se pinearon acá por no ser la causa de
este hallazgo, decisión explícita, no descuido.

---

## QA-3 — Consistencia datos ↔ documentos

**3.1 — Cross-check triple**: cero discrepancias en los 8 (sin
cambios respecto del primer reporte).

**3.2 — Recalculo de los 4 ρ de proxies** con la tabla congelada final:
n_ch +0.1905, dx 0.0000, apertura +0.3095, fs −0.3805 (sin cambio).
Conclusión no cambia. Fe de erratas ya en `docs/observaciones.md`
2026-07-30.

**3.3 — Robustez, verificado por enumeración exhaustiva (no analítica,
no tomado de la palabra de nadie)**: dejando que monterey_bay,
ridgecrest_north Y arcata (los 3 arrays de provenance pre-F1.1) tomen
CUALQUIER SNR50 en `[0.5,15.0]` simultáneamente, el máximo `|ρ|`
alcanzable por cualquiera de los 4 proxies es ~~**0.6545 (fs)**~~ — no
cruza 0.7381 ni en el peor caso posible. Registrado en
`docs/observaciones.md` 2026-07-31.

**⚠️ Superseded 2026-08-02**: el 0.6545 de arriba **no reproduce**.
Implementado en código commiteado y testeado
(`src/darkfiber/series_robustness.py`, `cota_b`, ver
`docs/plan_fase2_paper.md` §2.5 / Comanda F2.A2), verificado por
enumeración exhaustiva de extensiones lineales (336 ordenamientos
factibles para esta lista exacta) Y por una búsqueda aleatoria
independiente de 200,000 puntos — ambos métodos coinciden en
**0.6506 (fs)**, no 0.6545. Re-verificado además bajo las cuatro
convenciones de ranking posibles (Pearson sobre rangos promedio ==
`scipy.stats.spearmanr`, fórmula Σd² con rangos promedio, fórmula Σd²
con rangos ordinales, Pearson sobre rangos ordinales): **ninguna de
las cuatro da 0.6545** (0.6506 / 0.6012 / 0.6667 / 0.6667
respectivamente). Es un error numérico genuino de cuando este cálculo
se hizo fuera de código — no cambia la conclusión (0.6506 tampoco
cruza 0.7381), pero el número exacto estaba mal. Valor correcto:
**0.6506 (fs)**.

**Nota de contradicción, sin resolver acá (decisión de Alex, ver
`docs/plan_fase2_paper.md` F2.0/D3)**: este párrafo llama a
`{monterey_bay, ridgecrest_north, arcata}` "los 3 arrays de provenance
pre-F1.1" — pero **2.5/QA-05 identifican como provenance
REALMENTE incompleta pre-F1.1** a `{monterey_bay, ridgecrest_north,
stanford1_campus}` (arcata entró por heterogeneidad de geometría, no
por provenance). Son dos definiciones distintas del mismo apodo. El
módulo de código ahora calcula AMBAS explícitamente
(`SET_QA33`/`SET_PRE_F11`, esta última con `stanford1_campus` en vez
de o además de arcata) y no elige cuál va al paper — hallazgo
sustantivo: bajo la definición de QA-05 (`SET_PRE_F11`, 4 arrays
libres), el máximo `|ρ|` **SÍ cruza 0.7381** en 3 de los 4 proxies
(n_ch 0.8810, apertura 0.9524, fs 0.9698 — solo `dx` 0.4940 se
mantiene debajo). El claim de robustez del negativo depende de cuál
definición se adopte.

**3.4 — Investigación B5 (arcata 5.90 vs. reconstrucción 7.33) —
CERRADA**:
- **3.0, git log discriminante**: 6 commits tocaron el path de medición
  desde antes de la primera medición de arcata (2026-07-24); diff
  exacto de `run_step`/`inject_and_verify` contra ese punto: **BYTE-
  IDÉNTICO** en las líneas que consumen el generador aleatorio — solo
  parámetros opt-in con default preservado y campos aditivos. **Cero
  cambios funcionales.**
- **3.1, reconstrucción de ridgecrest_north** (pool homogéneo, sin
  ambigüedad de geometría): tampoco reproduce el 2.50 archivado (da
  2.67), incluso tras corregir DOS errores propios encontrados en el
  camino (orden de archivo no alfabetizado; threshold=4.0 en vez del
  8.0 calibrado real de A7/A8 — este último confirmó, de forma
  independiente, un hallazgo YA documentado el 2026-07-24: el SNR50 de
  ridgecrest_north es idéntico bajo threshold 4.0 y 8.0, gobernado
  aguas abajo por coherencia, no por Tier0).
- **Aplicando la regla de decisión pre-declarada, literal**: no
  reproduce + 3.0 confirma cero cambios de código → **es lista de
  archivos, en arcata Y en ridgecrest_north** → se documenta así, **no
  dispara re-medición** (la re-medición estaba condicionada a cambios
  de código, que no hubo). No se identificó el subconjunto/orden exacto
  que reproduciría los valores archivados — límite de reproducibilidad
  de la era pre-F1.1, declarado, no resuelto.
- **3.2**: arcata 5.90 → **"superseded Y NO REPRODUCIBLE"**.
  ridgecrest_north 2.50 → ~~sigue vigente (no se re-mide)~~ pero anotado
  con el mismo caveat de no-reproducibilidad con las herramientas
  actuales. Ambos en `docs/observaciones.md`/`docs/array_geometry_table.md`
  2026-07-31.
  **⚠️ Superseded 2026-08-02**: "sigue vigente (no se re-mide)" quedó
  obsoleto el mismo 2026-07-31, más tarde el mismo día — el gate de QA
  SÍ re-midió ridgecrest_north (junto con monterey_bay) y adoptó
  **2.67**, exactamente como ya documenta `docs/array_geometry_table.md`
  con su propia fe de erratas del 2026-08-01. Este `QA_REPORT.md` nunca
  recibió esa corrección; queda hecha acá. El valor vigente de
  ridgecrest_north es **2.67**, no 2.50.

**3.5 — Verificación final de hashes**: recalculados los 8 sha256
contra lo documentado — **los 7 no tocados coinciden exacto**; arcata
coincide con el valor ya corregido (`bfaa1254fdb0…6e878e25409`, ver
2.7/QA-07 del primer reporte). Sin drift.

**3.6 (antes 3.3 del primer reporte) — Inventario de caveats**: sin
cambios — censura de bin (veta #1) y nulo pre-registrado correctamente
no reflejados (resultado no concluyente); mecanismo W/T de Valencia
sincronizado; no-monotonicidad de FOSSA y heterogeneidad de pools
**marcados como OBLIGATORIOS en el checklist de la fase de escritura**
(no backlog opcional).

**3.7 (antes 3.4) — Barrido de números muertos, AMPLIADO (2.0)**:
corregidos en 11 archivos (`writeup.md`, `writeup.es.md`,
`writeup_data.md`, `pilot_kit.md`, `snr50_extension_fase1.md` — nota de
superseded, no editado en el lugar — y los 3 borradores de
`announcement_v1.1/`): "3.7×"→"5.00×", "arcata 5.9"→"8.00", "pytest
20/20"→"102/102". `CHANGELOG.md [Unreleased]` gana la entrada de
erratum para `[1.1.0]` (release/DOI/PDF no tocados). "12,000ch"/
"~2,450 canales" (censo PubDAS) y "decimator2" — verificados
benignos/no encontrados, sin acción.

**3.8 (antes 3.5) — writeup.es.md**: confirmado en backlog de fase de
paper (`PLAN_CIERRE_Y_LANZAMIENTO.md` Fase F1 ítem 6) — sin
sincronizar ahora, solo entraron las correcciones numéricas de 2.0-2.2.

**3.9 — Interferometry.py, flag para fase de paper**: no importado por
ningún módulo de `src/darkfiber` — demo standalone que alimenta
Figura 11 y el claim "4/4" del writeup, nada más. Anotado en el
checklist de escritura (junto a 3.6): decisión explícita pendiente
sobre si la Figura 11 entra en el alcance del paper reencuadrado como
technical note, o se corta con el resto de "motor de coherencia
physics-first".

---

## Hallazgos — tabla consolidada final

| ID | Severidad | Hallazgo | Estado final |
|---|---|---|---|
| QA-01 | CRÍTICO | "Spread 3.7×" obsoleto | **CORREGIDO** — 11 archivos, commit `3a6a097` |
| QA-02 | CRÍTICO | "pytest 20/20" obsoleto | **CORREGIDO** — 102/102 real |
| QA-03 | MAYOR | `triage.py` 89%<90% | **CERRADO por contenido** — de las 13 líneas sin cubrir: 4 defensivas (estados imposibles), 1 función de reporting sin relación al árbol de decisión, 1 rama de fallback rara pero no-taxonómica, y 5 líneas (`sta_lta_ratio` bloqueado por canal) que SÍ son producción real pero ya verificadas por `darkfiber-validate` (29/29, "Bloqueo por canal: mismo raster") — invisibles a `pytest --cov` pero no es un gap real. Cero líneas de clasificación/umbral/taxonomía sin cubrir. |
| QA-04 | MAYOR | `mypy --strict`, 144 errores | Backlog documentado (`PLAN_CIERRE_Y_LANZAMIENTO.md`), no se arregla ahora |
| QA-05 | MAYOR (parcialmente resuelto) | Provenance incompleta 3/8 + sin seeds/checksum nativos | **3/8→0/8 CERRADO 2026-08-01** (las 3 re-medidas con `--files` explícito). Sub-punto "sin seeds/checksum nativos" sigue abierto, ligado al backlog de auto-sello |
| QA-06 | MAYOR (resuelto) | "CI verde en 3.10/3.11/3.12" sin verificar por **tres causas independientes**: (a) trigger de `ci.yml` no dispara en push a `dev`, (b) extra `tdms` faltante → pytest no colecciona (QA-15), (c) `ruff` sin pin exacto → verde local/rojo CI (QA-16) | **CERRADO 2026-08-01**: PR draft #3 abierto solo para disparar CI; (a)(b)(c) resueltas una por una (cada una ocultaba a la siguiente); 3.10/3.11/3.12 verdes en las 5 etapas, commit `e234cf9`. PR cerrado sin mergear por Alejandro, rama `dev` intacta, F3 sigue gateada |
| QA-15 | MAYOR (con fix) | `ci.yml` sin el extra `tdms` — colección de pytest rota, reproducible por terceros sin ese extra | **CORREGIDO** — `ci.yml` instala `tdms`; `test_replay_tdms.py` usa `pytest.importorskip` (alineado con precedente `test_dashboard.py`). Ver 2.8. Nota relacionada sin resolver: `test_replay_hdf5_generic.py` tiene la misma fragilidad teórica con el extra `h5`, backlog |
| QA-16 | MAYOR (con fix) | `ruff>=0.6` sin pin exacto — mismo patrón "local-green/CI-red" ya documentado para numpy/mypy, nunca generalizado a las herramientas de lint/format | **CORREGIDO** — `ruff==0.16.1` pineado en `pyproject.toml` con el mismo estilo de comentario que numpy/mypy; 3 archivos reformateados contra el pin. Ver 2.9 |
| QA-07 | MAYOR (resuelto) | sha256 de arcata stale | Corregido inline, re-verificado en 3.5 |
| QA-08 | MENOR (con fix) | off-by-one `interferometry.py:301` | **CORREGIDO**, 4/4 re-verificado, fe de erratas registrada |
| QA-09 | MENOR | `ArrayGeometry` default silencioso | Backlog (`PLAN_CIERRE_Y_LANZAMIENTO.md`) |
| QA-10 | MENOR (cerrado) | `load_quakeflow_h5` default | Verificado: existe, nunca se usó. Backlog para endurecer |
| QA-11 | MENOR | `snr_curve.py` 25% cobertura | Backlog, señalado con precisión (núcleo numérico cubierto) |
| QA-12 | MENOR | Módulos 0-57% fuera de path crítico | Backlog |
| QA-13 | MENOR→OBLIGATORIO | Caveats FOSSA/heterogeneidad sin reflejo | **Checklist obligatorio de la fase de escritura**, no backlog opcional |
| QA-14 | no aplica | "decimator2" no encontrado | Cerrado — error de conversación, nunca entró al repo |

---

## Cierre

Bloques 1-3 completos. Hashes verificados (3.5). `QA_REPORT.md`
actualizado con la decisión de cada uno de los 14 hallazgos. Único
punto abierto: QA-06 (¿PR borrador para verificar CI, o esperar a F3?)
— el resto no requiere más acción de QA. Sin segunda pasada: lo que
aparezca durante la escritura del paper se trata como errata puntual,
no como reapertura de este gate.
