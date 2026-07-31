# QA E2E — Gate final de calidad pre-paper

*2026-07-30. Corrido después de que la serie de 8 SNR50 quedó CONGELADA
(commit `1090fc4`). Este QA REPORTA — ningún hallazgo se arregla acá sin
aprobación explícita (excepción declarada: un hash stale que yo mismo
introduje en la misma sesión, corregido inline y señalado como tal en
QA-3.1 — no es un hallazgo de código/metodología). Bloque A sigue
congelado: los tests nuevos (`tests/analytical/`) EJERCITAN el código
existente, no lo tocan. No hay segunda pasada — lo que sigue de acá es
la decisión del autor sobre qué CRÍTICO/MAYOR se arregla, y después la
estructura del paper.*

## Resumen ejecutivo

**14 hallazgos: 2 CRÍTICO, 5 MAYOR, 6 MENOR, 1 no encontrado/no aplica.**
Los dos CRÍTICO son números muertos en los documentos que alimentarán
el paper: el "spread 3.7×" (arcata 5.9 vs monterey_bay 1.6, la cita
central de `writeup.md`/`writeup.es.md`/`writeup_data.md`/`pilot_kit.md`)
quedó obsoleto dos veces — ya lo estaba desde N=4 (4.83×) y ahora arcata
mide 8.00, no 5.9 (spread real 5.0×) — y "pytest 20/20 passing" (mismos
dos documentos) no refleja ni de lejos el tamaño real de la suite
(101/102 con los tests nuevos de este QA, 53/53 sin ellos). El código
del path de veredicto (coherence.py 93%, triage.py 89%, ambos con
cobertura real medida) y las 8 fórmulas físicas re-derivadas
independientemente en `tests/analytical/` pasan limpio — el motor de
decisión está mejor verificado que la documentación que lo describe.
Los 5 MAYOR son de reproducibilidad (mypy --strict: 144 errores; schema
de provenance incompleto en las 3 corridas pre-F1.1; CI 3.10-3.12 no
verificable localmente). Los MENOR son calidad sin impacto en los 8
SNR50 publicados.

---

## QA-1 — Física: validación contra soluciones cerradas

`tests/analytical/test_closed_form.py`, 49 tests nuevos: **48 pasan, 1
falla por diseño** (es un detector, no una aserción de calidad — ver
QA-1.8). Corridos junto al resto de la suite sin regresiones
(`tests/` completo: 102 tests, 101 pasan, la misma 1 falla intencional).

| # | Qué se verificó | Resultado | Evidencia |
|---|---|---|---|
| 1.1 | `snr_to_amplitude` round-trip exacto (5 SNR objetivo) + invariancia de escala (×1000/÷1000) + sobrevive upcast desde float16/int16 | **PASA** | `test_snr_to_amplitude_round_trip_exact`, `test_snr_to_amplitude_scale_invariant`, `test_snr_to_amplitude_survives_low_precision_origin_upcast`. La propiedad "no colapsa a la grilla del dtype de origen" ya la cubren, mejor calibrados con datos reales, `tests/test_replay_hdf5_generic.py::test_injection_arithmetic_never_rounds_through_float16` y `tests/test_replay_tdms.py::test_low_snr_injection_survives_int16_source_via_tdms` — no se reimplementó peor acá. |
| 1.2 | Onda plana a v conocida (2000/4000/6500 m/s × dx=2m/16.8m) → pico de semblanza en el punto de grilla más cercano; semblanza en [0,1]; señal limpia →>0.9; ruido blanco →~1/n_ch | **PASA**, las 6 combinaciones velocidad×geometría exactas al punto de grilla más cercano (`rel=1e-9`); semblanza de ruido blanco medida en banda `[1/(4·n_ch), 6/n_ch]` sobre 5 semillas | `test_plane_wave_semblance_peak_matches_known_velocity`, `test_semblance_perfect_coherent_signal_near_one`, `test_semblance_white_noise_near_one_over_n_channels` |
| 1.3 | Theil-Sen sobre onsets de pendiente conocida (re-derivación directa de `scipy.stats.theilslopes` + `coherence.fit_onset_velocity` de punta a punta) | **PASA**, error relativo <2% con jitter de pick de 10ms | `test_theilsen_recovers_known_slope_directly`, `test_fit_onset_velocity_end_to_end_recovers_known_slope` |
| 1.4 | `v_app_max_resoluble(L,fs,k) == L·fs/k` exacto (3 combinaciones); velocidad fuera de grilla → `boundary_pinned=True` | **PASA**. Nota importante encontrada leyendo el código: `v_app_max_resoluble` es **puramente informativo** dentro de `coherence.analyze()` — solo aparece en el texto de `explanations` de la rama REGIONAL_EMERGENT, **no participa del árbol de decisión** `is_seismic`. El guard que sí está en el árbol de decisión es `_velocity_peak_is_boundary` (borde de la propia grilla de búsqueda), verificado por separado. No es una discrepancia código/docs — es una distinción que vale la pena que el paper tenga clara si cita la fórmula como parte del *mecanismo de decisión* en vez de una *característica informativa reportada*. | `test_v_app_max_resoluble_matches_closed_form`, `test_velocity_outside_grid_triggers_boundary_pinned`, `coherence.py:653,659` (uso real, solo en `expl.append`) |
| 1.5 | Re-derivar `13.6 + 0.001833·aperture_m` desde las piezas REALES de `selftest.inject_and_verify_sized` (no la fórmula documentada) | **CONFIRMADO CORRECTO** — re-derivación algebraica manual (`warmup_s`=8.8 + 2×`pipeline_margin_s` + `moveout_s`(v=2000) + `len(ricker)/fs` + 2.0 = 13.6 + aperture×(2/1500+1/2000) = 13.6 + 0.0018333…·aperture, coincide exacto) y test numérico en 4 aperturas reales, error relativo <1% | `test_noise_floor_constants_rederived_from_real_code`, `selftest.py:119-128` |
| 1.6 | `W`=`coincidence_window_s`==3.5s contra el default real; techo `W/T` con Valencia (v*=3,552.5) y FOSSA (v*=1,996.6) como casos sintéticos cerrados | **PASA**, `coincidence_fraction` sintético dentro de ±0.02 absoluto del techo `W/T` predicho en ambos casos | `test_coincidence_window_default_is_3_5s`, `test_coincidence_fraction_matches_w_over_t_closed_form` |
| 1.7 | Ventanas STA/LTA en segundos → muestras correctas en los 5 fs reales de la serie (100/125/200/250/500 Hz) | **PASA**, la garantía "ratio==1.0 exacto durante `warmup_s`" se sostiene en los 5 fs | `test_sta_lta_warmup_boundary_exact_at_each_real_fs` |
| 1.8 | Grep de TODO `n_ch*dx` (sin `-1`) en `src/`+`docs/` | **1 ocurrencia encontrada, verificada BENIGNA** — `src/darkfiber/interferometry.py:301`, `x_start_m=n_ch * dx + 150.0`: posiciona una fuente sintética de interferometría 150m PASADO el extremo del arreglo (segundo pase, simétrico al primero en `x_start_m=-150.0`), no calcula la apertura del arreglo — la diferencia de 1 `dx` es despreciable contra el margen explícito de 150m ya sumado. No es el bug de `docs/array_geometry_table.md` (ya corregido, ver `docs/observaciones.md` 2026-07-30). **Clasificación: MENOR (verificado no-bug, listado por transparencia del detector).** | `test_no_naked_n_ch_times_dx_aperture_formula_in_source` (falla por diseño — es el detector reportando su único hallazgo) |
| 1.9 | Wilson CI vs. re-derivación independiente (formula de texto + `scipy.stats.norm`, NO reusa `snr_curve.wilson_ci`) en 5 casos borde; `interpolate_snr50` en cruce exacto, curva que nunca cruza, curva no monótona | **PASA**, los 5 casos de Wilson coinciden a `1e-9`; los 3 bordes de interpolación se comportan como se espera (cruce exacto devuelto exacto, `None` si nunca cruza, primer cruce ascendente encontrado en curva tipo-Valencia/FOSSA) | `test_wilson_ci_matches_independent_rederivation`, `test_interpolate_snr50_exact_crossing_at_a_step`, `test_interpolate_snr50_never_crosses_returns_none`, `test_interpolate_snr50_non_monotonic_still_finds_first_crossing` |
| 1.10 | `stationarity_check` (umbral 3.0×): caso que dispara (recorta al subconjunto contiguo estable) y caso terminal (fallback a pool completo cuando ni un subconjunto de `k_min` califica) | **PASA**, ambas ramas verificadas por separado (con `k_min` default=1 el fallback terminal es casi inalcanzable — cualquier ventana de 1 elemento califica trivialmente — así que se forzó con `k_min=2` sobre una serie donde ningún par adyacente baja de 3× para ejercitar esa rama específicamente) | `test_stationarity_check_trims_outlier_to_stable_contiguous_subset`, `test_stationarity_check_falls_back_to_full_pool_when_no_subset_reaches_k_min` |

---

## QA-2 — Código: estándares

**2.1 — Cobertura** (`pytest --cov=darkfiber`, TOTAL 40%, 3623 stmts/2177 sin cubrir):

| Módulo | Cobertura | Rol | Veredicto |
|---|---|---|---|
| `coherence.py` | 93% | path de veredicto | OK (≥90%) |
| `triage.py` | 89% | path de veredicto | **MAYOR — <90% por 1 punto** |
| `contracts.py` | 95% | contratos | OK |
| `synth.py` | 92% | inyección sintética | OK |
| `stream_runner.py` | 95% | streaming (no path crítico listado, informativo) | OK |
| `selftest.py` | 85% | harness de medición | informativo, no listado en el path crítico pedido |
| `snr_curve.py` | 25% | **path crítico listado** (produce los 8 SNR50 publicados) | **<70%, hallazgo (ver nota abajo)** |
| `replay.py` | 65% | **path crítico listado** (loaders) | <70%, MENOR |
| `convert_stanford_sgy.py` | 51% | loader (Stanford-2) | <70%, MENOR |
| `catalog.py` | 57% | **path crítico listado** | <70%, MENOR |
| `calibrate.py`,`run_on_quakeflow.py`,`run_on_stanford.py`,`run_validation.py`,`dashboard.py`,`pipeline_daemon.py`,`installation_config.py`,`batching.py`,`characterize_aperture.py` | 0-23% | fuera del path crítico listado explícitamente | MENOR, cubiertos en la práctica por `darkfiber-validate` (29/29, ver QA-2.6) más que por pytest unitario |

Nota sobre `snr_curve.py` (25%): el núcleo NUMÉRICO ya tiene tests
dedicados (`wilson_ci`, `interpolate_snr50`, `stationarity_check`,
ahora con QA-1.9/1.10 además de los pre-existentes) — lo no cubierto es
mayormente el CLI/argparse y las ramas `--format` de orquestación de
archivos (`main()`, líneas 684-1068). Clasificado MENOR por la regla
literal del gate (no es "path de veredicto"), pero señalado porque es,
en los hechos, el módulo que produce cada número que va al paper — vale
la pena más cobertura de la que la regla estricta exige.

**2.2 — Defaults silenciosos de parámetros físicos**:

| Ubicación | Default | ¿Alcanzable en un path real? | Clasificación |
|---|---|---|---|
| `run_on_quakeflow.py:132-133` (`load_quakeflow_h5`) | `dt_s`→0.01 (fs=100Hz), `dx_m`→8.0 si faltan attrs | **SÍ** — ya conocido/declarado antes de este QA | MAYOR (ya conocido) |
| `contracts.py:23-24` (`ArrayGeometry.channel_spacing_m`/`fs_hz`) | 8.0m / 50.0Hz (Pydantic `Field`) | **NO** — verificado: los 9 sitios de construcción real (`calibrate.py`, `characterize_aperture.py`, `dashboard.py`, `run_on_quakeflow.py`×2, `run_on_stanford.py`, `snr_curve.py`×2, más el `GEOM` sintético de `run_validation.py`) pasan `channel_spacing_m`/`fs_hz` explícitos siempre | MENOR (default muerto, nunca ejercitado) |

Propuesta (no aplicada): para `load_quakeflow_h5`, `raise SystemExit`
si `dt_s`/`dx_m` faltan, mismo contrato que `load_hdf5_generic` ya
usa — compatibilidad verificada: los archivos reales de los 8 arrays
SIEMPRE traen esos attrs (confirmado directamente sobre los archivos de
arcata/monterey_bay/ridgecrest_north durante la auditoría de F1.6), así
que endurecer esto no rompería ninguna corrida ya publicada. Para
`ArrayGeometry`, quitar el default (`Field(..., gt=0)`) — mismo
argumento: no hay ningún call site real que dependa de él hoy.

**2.3 — Determinismo**: mapa completo de fuentes de aleatoriedad en
`src/darkfiber/` (14 sitios, todos con seed explícito, ninguno
`default_rng()` sin argumento):

- `snr_curve.py:334,446` (`run_step`/`run_step_lazy_single_file`): `1_000 + step_idx` — determinístico por escalón SNR.
- `selftest.py:130` (`inject_and_verify_sized`): `seed` recibido del llamador (encadenado desde el `picker` de arriba).
- `synth.py:27,56,91,136,184,272`: cada generador sintético (`make_noise`, `add_plane_wave`, `add_moving_source`, `add_moving_radiator`, `add_emergent_regional`, `add_local_spike`) toma `seed` como parámetro con default fijo propio (0-5).
- `run_validation.py:153,561,713`: seeds fijos (99, 7, 0) para el harness sintético de Bloque A.
- `run_on_quakeflow.py:470`: `picker = np.random.default_rng(200)`.
- `dashboard.py:286`: `seed=0` (solo UI).

**Verificado: cero fuentes de aleatoriedad sin seed** en todo `src/darkfiber/` (grep de `np.random.rand`, `random.random()`, `default_rng()`/`default_rng(None)` sin argumento — cero resultados).

**2.4 — Contratos / mypy**: el mypy CONFIGURADO del proyecto
(`pyproject.toml`, `disallow_untyped_defs=false`) pasa limpio — "Success:
no issues found in 22 source files", consistente con lo que los docs ya
afirman. Corrido además en modo **`--strict`** (no el configurado, a
pedido explícito del gate): **144 errores en 18 archivos**, mayormente
`no-untyped-def` (funciones sin anotar) y `type-arg` (`dict`/`list` sin
parámetros de tipo). Por módulo: `snr_curve.py` 32, `catalog.py` 16,
`run_on_quakeflow.py` 14, `interferometry.py` 13, `calibrate.py` 9,
`run_validation.py`/`dashboard.py`/`characterize_aperture.py` 8 c/u,
`pipeline_daemon.py`/`batching.py` 7 c/u, `synth.py`/`coherence.py` 5
c/u, `stream_runner.py`/`replay.py` 3 c/u, `convert_stanford_sgy.py`/
`contracts.py` 2 c/u, `triage.py`/`run_on_stanford.py` 1 c/u. **MAYOR**
— no arreglado (no aplica bajo el mypy configurado del proyecto hoy,
que SÍ pasa; esto es una medición adicional pedida por el gate, no una
regresión).

**2.5 — Provenance del schema actual** (`input_files`, `exclusion_kind`
dentro de `noise_exclusion.sources`, `threshold`/`threshold_source`,
`seeds`, checksums) — verificado leyendo las 8 JSON reales:

| Array | threshold | input_files | noise_exclusion | seeds (top-level) | Era |
|---|---|---|---|---|---|
| monterey_bay | ✗ | ✗ | ✗ | ✗ | pre-F1.1 (schema mínimo: solo `array_id`/`curve`/`snr50`/`snr_steps`/`n_per_step`/`runtime_s`) |
| ridgecrest_north | ✓ | ✗ | ✗ | ✗ | pre-F1.1, parcial |
| stanford1_campus | ✓ | ✗ | ✓ | ✗ | F1.1 temprano (antes de que `input_files`/`format` existieran) |
| FORESEE, Stanford-2, Valencia, FOSSA, arcata (re-medido) | ✓ | ✓ | ✓ | solo dentro de `trial_diagnostics` (Valencia y FOSSA únicamente) | F1.4+ / F1.6 |

**Ninguna de las 8** tiene un campo `seeds` a nivel top-level ni un
campo `checksum`/`hash` embebido nativo (los `pipeline_hash` de
FOSSA/arcata son inyección manual post-corrida, declarada como tal, no
generados por el harness — ver backlog ya declarado en
`PLAN_CIERRE_Y_LANZAMIENTO.md`, "auto-sellar version"). **MAYOR** — para
la sección de limitaciones del paper: 3 de 8 corridas (monterey_bay,
ridgecrest_north, stanford1_campus) tienen provenance incompleta o
ausente por ser anteriores a que el schema existiera; no se re-corren
(igual criterio que Bloque A congelado — arcata SÍ se re-midió porque
tenía un problema de DATOS, no de provenance, ver F1.6).

**2.6 — CI multi-versión**: `.github/workflows/ci.yml` define matrix
`python-version: ["3.10", "3.11", "3.12"]` (verificado leyendo el
archivo). **No verificable localmente**: sin `gh` CLI disponible en esta
sesión y con solo Python 3.13.9 instalado localmente (fuera de la
matriz pinneada), no se pudo confirmar el estado verde/rojo del run más
reciente. **MAYOR** — gap de verificación, no evidencia de fallo.

---

## QA-3 — Consistencia datos ↔ documentos

**3.1 — Cross-check triple** (`array_geometry_table.md` ↔
`array_profiles` ↔ JSON de cada curva), verificado programáticamente
sobre los 8: **CERO discrepancias en SNR50 ni en geometría** (fs/dx/n_ch/
aperture_m idénticos en las tres fuentes, comparación exacta, no
aproximada). Encontrado DURANTE esta verificación (no antes): el
`sha256` de `snr_curve_arcata.json` documentado en `observaciones.md` y
`array_geometry_table.md` había quedado **stale** — se computó ANTES de
inyectar `pipeline_hash` en el JSON (mismo patrón de la corrida de
FOSSA), así que el archivo cambió después de documentar su hash.
**Corregido inline en esta misma pasada** (no es un hallazgo de código
o metodología, es un error mío de secuencia dentro de la sesión — señalado
por transparencia, no escondido): hash viejo `37f9a215d180…`, nuevo y
verificado `bfaa1254fdb0…6e878e25409`. Clasificado **MAYOR** (afectaba
la reproducibilidad del propio artefacto de auditoría) pero YA
resuelto, no pendiente de decisión.

**3.2 — Recalculo de los 4 rho de proxies** contra la tabla congelada
final (arcata=8.00): ver fe de erratas ya registrada en
`docs/observaciones.md` (2026-07-30, "FE DE ERRATAS (QA-3.2)"). n_ch
+0.0714→+0.1905, dx +0.0843→0.0000, apertura +0.2381→+0.3095, fs sin
cambio (−0.3805). **La conclusión no cambia** (ninguno cruza 0.7381).

**3.3 — Inventario de caveats** — ¿cada uno tiene entrada en
`observaciones.md` Y reflejo en el documento que el paper citará?

| Caveat | En observaciones.md | Reflejo en writeup.md/es.md | Estado |
|---|---|---|---|
| Censura de bin en veta #1 (piso vs. bin, C1-C6) | ✓ (2026-07-30) | ✗ | No reflejado — veta #1 es un resultado no concluyente, no publicado, correctamente no citado en el writeup todavía |
| Nulo pre-registrado de veta #1 (ρ=−0.2515) | ✓ | ✗ | Ídem — consistente con no sobre-afirmar un nulo no interpretable |
| Mecanismo W/T de Valencia | ✓ (2026-07-29) | ✓ (§7 es./§6 en, agregado en este mismo hilo F1.6) | Sincronizado |
| No-monotonicidad de FOSSA sin mecanismo (W/T descartado) | ✓ | ✗ (solo en `array_geometry_table.md`) | **Gap real** — el writeup describe el mecanismo de Valencia pero no menciona que FOSSA NO comparte ese mecanismo pese al mismo síntoma |
| Heterogeneidad de pools (arcata, monterey_bay/ridgecrest_north auditados) | ✓ | ✗ | **Gap real** — el writeup todavía describe el spread de 3 arrays original, ni siquiera llegó a mencionar 8 arrays, mucho menos esta auditoría |
| Dtypes mixtos (int16/float16/float32) entre arrays | ✓ (2026-07-27) | ✗ | No mencionado en el writeup |

**3.4 — Barrido de números muertos** (ver hallazgos CRÍTICOS #1/#2 arriba
para el detalle completo de 3.7×/pytest 20-20). Verificados y
descartados como NO problemáticos: "12,000ch" (FOSSA) y "~2,450
canales" (FORESEE) en `docs/snr50_extension_fase1.md` — son estimados
de censo PRE-registro explícitamente marcados como preliminares/con
discrepancia declarada en el propio documento, no presentados como
valor actual (el valor real, 11,648/2,137, es el que usan
`array_profiles`/`array_geometry_table.md` en todos lados). "decimator2"
— buscado en `src/`+`docs/` completos, **cero ocurrencias, no aplica**
(no encontrado en este estado del repo).

**3.5 — writeup.es.md desincronizado**: confirmado que sincronizar
`writeup.es.md` contra la versión final es un ítem YA declarado en
`PLAN_CIERRE_Y_LANZAMIENTO.md` (Fase F1, ítem 6: "Generar
docs/writeup.es.md: TRADUCCIÓN COMPLETA Y FIEL... la canónica es la
inglesa") — **no se sincroniza ahora**, correcto conforme al plan
existente. El inventario de 3.3 y los números muertos de 3.4 aplican
por igual a AMBAS versiones (inglesa y española) — no es un problema
exclusivo de la traducción, la versión canónica (inglesa) también está
desactualizada.

---

## Hallazgos — tabla consolidada

| # | Severidad | Hallazgo | Evidencia |
|---|---|---|---|
| 1 | **CRÍTICO** | "Spread 3.7×" (arcata 5.9/monterey_bay 1.6) citado como hallazgo central en `writeup.md:245,377`, `writeup.es.md:41,313,457`, `writeup_data.md:274,323`, `pilot_kit.md:75,157`, `announcement_v1.1/earth_arxiv_metadata.md:56` — obsoleto desde N=4 (4.83×) y ahora arcata=8.00 (spread real 5.0×) | QA-3.4, `docs/observaciones.md` 2026-07-30 |
| 2 | **CRÍTICO** | "pytest 20/20 passing" en `writeup.md:481`, `writeup.es.md:565` — real: 101/102 (con QA) / 53/53 (sin QA) | QA-3.4, corrida real de esta sesión |
| 3 | MAYOR | `triage.py` 89% de cobertura, path de veredicto, <90% | QA-2.1 |
| 4 | MAYOR | `mypy --strict`: 144 errores en 18 archivos (el mypy configurado del proyecto SÍ pasa limpio) | QA-2.4 |
| 5 | MAYOR | Provenance incompleta en 3/8 corridas pre-F1.1 (monterey_bay sin threshold/input_files/noise_exclusion; ridgecrest_north sin input_files/noise_exclusion; stanford1_campus sin input_files/format); ninguna de las 8 tiene `seeds`/`checksum` embebidos nativos | QA-2.5 |
| 6 | MAYOR | CI 3.10/3.11/3.12 configurado pero no verificable localmente (sin `gh`, sin esos intérpretes instalados) | QA-2.6 |
| 7 | MAYOR (ya resuelto en esta pasada) | `sha256` de `snr_curve_arcata.json` quedó stale en `observaciones.md`/`array_geometry_table.md` tras inyectar `pipeline_hash` — corregido inline | QA-3.1 |
| 8 | MENOR | `interferometry.py:301`, único `n_ch*dx` sin `-1` del repo — verificado benigno (posición de fuente sintética, no cálculo de apertura) | QA-1.8 |
| 9 | MENOR | `ArrayGeometry.channel_spacing_m`/`fs_hz` (`contracts.py:23-24`) tienen default silencioso pero nunca se ejercita en ningún call site real | QA-2.2 |
| 10 | MENOR | `load_quakeflow_h5` default silencioso conocido (fs=100/dx=8 si faltan attrs) — propuesta de fallo fuerte no aplicada | QA-2.2 |
| 11 | MENOR | `snr_curve.py` 25% de cobertura — produce los 8 SNR50 publicados; núcleo numérico sí cubierto, CLI/orquestación no | QA-2.1 |
| 12 | MENOR | Módulos fuera del path crítico con 0-57% cobertura (calibrate/run_on_quakeflow/run_on_stanford/run_validation/dashboard/pipeline_daemon/installation_config/batching/characterize_aperture/catalog/replay/convert_stanford_sgy) | QA-2.1 |
| 13 | MENOR | Caveats de FOSSA-no-monotonicidad y heterogeneidad de pools sin reflejo en writeup.md/es.md | QA-3.3 |
| — | no aplica | "decimator2": no encontrado en el repo | QA-3.4 |

---

## Cierre

QA-1: 48/49 verificaciones de física pasan; la única falla es un
detector funcionando como debía. QA-2: el código del path de veredicto
está bien cubierto y tipado bajo el estándar configurado del proyecto;
bajo un estándar más estricto (pedido explícito de este gate) aparecen
144 gaps de tipado, ninguno en la lógica central de decisión. QA-3: los
datos publicados (los 8 SNR50, su geometría, sus 4 proxies) están
limpios y cruzan-verificados — el problema real está en los DOCUMENTOS
narrativos (`writeup.md`/`.es.md`), que quedaron dos ciclos de hallazgo
atrás de la serie congelada.

Decisión pendiente del autor: qué CRÍTICO/MAYOR se arregla y cuándo
(cada uno con su propio gate). Los MENOR quedan para backlog. Sin
segunda pasada de QA — lo que aparezca durante la escritura del paper
se trata como errata puntual.
