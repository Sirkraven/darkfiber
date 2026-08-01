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
0.65, no cruza 0.7381).

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

**2.5 — Provenance**: 3/8 corridas (monterey_bay, ridgecrest_north,
stanford1_campus) con schema incompleto por ser anteriores a que
existiera; ninguna de las 8 tiene `seeds`/`checksum` nativos. **Ligado
explícitamente**, en `PLAN_CIERRE_Y_LANZAMIENTO.md`, al backlog ya
declarado de auto-sello de versión (`git rev-parse HEAD` al arrancar la
corrida) — es el mismo problema visto desde el lado de datos y desde el
lado de diseño, una sola entrada de backlog. No se re-corren
monterey_bay/stanford1_campus (Bloque A, y para monterey_bay/
ridgecrest_north además porque 3.0/3.1 confirmaron que la brecha es de
lista de archivos, no de código — ver QA-3 abajo).

**2.6 — CI multi-versión — HALLAZGO NUEVO, sin resolver**: se hizo
`git push origin dev` (commit `3a6a097`) para disparar la verificación
pedida. **Descubrimiento: `.github/workflows/ci.yml` dispara SOLO en
`push: branches: [main]` y en `pull_request`** — un push a `dev` no
ejecuta CI en absoluto (confirmado vía API pública de GitHub: el último
run visible es de un PR anterior, 2026-07-22, nada posterior al push de
hoy). **No se abrió un PR dev→main unilateralmente** — eso cruza la
Fase F3 de `PLAN_CIERRE_Y_LANZAMIENTO.md` ("Claude Code prepara la
rama y el texto del PR; ALEJANDRO aprueba el merge"), y abrir uno ahora
adelantaría ese hito fuera de secuencia. Queda pendiente de decisión:
¿abrir un PR (borrador, sin mergear) solo para correr CI, o dejar la
verificación de 3.10/3.11/3.12 para cuando llegue F3 naturalmente?

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
alcanzable por cualquiera de los 4 proxies es **0.6545 (fs)** — no
cruza 0.7381 ni en el peor caso posible. Registrado en
`docs/observaciones.md` 2026-07-31.

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
  ridgecrest_north 2.50 → sigue vigente (no se re-mide) pero anotado
  con el mismo caveat de no-reproducibilidad con las herramientas
  actuales. Ambos en `docs/observaciones.md`/`docs/array_geometry_table.md`
  2026-07-31.

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
| QA-05 | MAYOR | Provenance incompleta 3/8 + sin seeds/checksum nativos | Documentado para limitaciones del paper; ligado al backlog de auto-sello |
| QA-06 | MAYOR | CI no verificable | **Hallazgo nuevo**: push a `dev` no dispara CI (trigger config). Pendiente de decisión (¿PR borrador?) |
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
