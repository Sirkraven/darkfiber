# Extensión de SNR50 a más instalaciones — Fase 1

*Objetivo: convertir el hallazgo de 3 arrays (spread 3.7×) en un
resultado con 8-10 instalaciones, midiendo SNR50 con el protocolo
existente (`darkfiber-snr-curve`) sobre ruido de fondo real — no hacen
falta eventos catalogados, solo ruido con metadata confiable. Bloque A
(A5-A10) congelado: este trabajo corre el pipeline existente, no lo
modifica.*

## F1.1 — Reconocimiento + Stanford (cerrado)

### 1. Protocolo: formato, metadata, duración de ruido, selección

`darkfiber-snr-curve` (`snr_curve.py`) toma un `--dir` con archivos ya en
disco — hoy `.h5` (QuakeFlow, attrs embebidos) y `.npz` (sin convención
de attrs propia — `--fs`/`--dx` obligatorios, agregado en este bloque,
ver "Cambio de código" abajo). Para cada escalón de SNR de
`SNR_STEPS=(1,2,3,5,8,12,20)`, inyecta `N_PER_STEP=20` sismos sintéticos
(onda plana, velocidad aleatoria en `[2000,6500]` m/s) sobre ventanas de
ruido real, y mide qué fracción el pipeline completo (Tier0 + Coherencia)
clasifica `SISMO_CONFIRMADO`. Total: 7×20 = **140 inyecciones**.

**Selección de ruido — automática, no curada a mano**: `gather_noise_sources`
toma TODOS los archivos de `--dir`; si el archivo trae `event_time_index`
embebido, corta `[0, origen−5s]` y `[origen+5s, fin]` como ruido; sin eso
(el caso de `.npz`), usa el archivo completo — salvo que se dé
`--exclude-s INICIO FIN` (agregado en este bloque), que excluye esa
ventana manualmente en su lugar. Es el mismo mecanismo generalizado, no
uno nuevo.

**Duración mínima de ruido por trial — derivada de
`selftest.inject_and_verify_sized`**, peor caso a `v_app=2000` m/s (el
extremo lento sorteado):

```
min_len_s ≈ 13.6 + 0.001833 × aperture_m      (aperture_m = (n_channels−1) × spacing_m)
```

Verificado numéricamente: ridgecrest_north (9,192 m) → 30.5s; arcata
(15,411 m) → 41.9s; stanford1_campus (5,100 m) → 22.9s. Para F1.2, pedir
varias veces este piso por candidato (no el mínimo exacto), para que las
140 inyecciones tengan margen real de muestreo sin agotar los reintentos
(`max_attempts = n×25` por escalón).

### 2. Umbral Tier0 de cada SNR50 existente — verificado, no supuesto

| Array | SNR50 | Umbral de medición | Evidencia |
|---|---|---|---|
| monterey_bay | 1.6 | 4.0 (default) | `array_profiles` + nota A8 ("default retenido, sin evidencia de descalibración") |
| ridgecrest_north | 2.5 | 8.0 (calibrado, A7/A8) | `figures/snr_curve_ridgecrest_north.json` — corrida completa (140/140, runtime 173s) con `threshold_source="perfil del arreglo (calibrate.py --apply)"` |
| arcata | 5.9 | 4.0 (default) | ídem monterey_bay, nota A8 propia |
| stanford1_campus | **7.73** | 4.0 (default) | esta corrida — ver §3 |

Los 4 valores están medidos bajo el umbral de producción REAL de su
propio array — comparables entre sí. (Nota de proceso: encontré una
entrada archivada en `array_profile_history` para ridgecrest_north que,
por un bug de secuencia ya documentado y corregido en A7, sugería que
el SNR50 vigente podía estar midiendo bajo un umbral viejo — se
descartó con el JSON de la corrida real, que es autoconsistente y
completo. Ver `docs/observaciones.md`, 2026-07-24, para el detalle
completo de esa verificación.)

### 3. Stanford — corrido

- **Archivo**: `D:\darkfiber\data\stanford\eastfoothills_real.npz` — único
  `.npz` de Stanford en disco. 626 canales, 89,999 muestras @ 100Hz
  (900.0s), dx=8.16m (aperture=5,100m).
- **Exclusión manual**: `--exclude-s 395 455` — cubre el origen USGS real
  (segundo 401 exacto, `validacion_real/NOTES.md`), el núcleo denso A10
  (`[410.3s, 423.8s]`) y la cola del bloque fusionado original hasta
  449s. Deja 840s de ruido real (395s antes + 445s después), muy por
  encima del piso de 22.9s por trial.
- **Umbral**: 4.0 (default global — `stanford1_campus` nunca tuvo una
  calibración A7/A8 aplicada; confirmado antes de correr, no asumido).
- **Comando exacto**:
  ```
  python -m darkfiber.snr_curve --dir D:/darkfiber/data/stanford \
    --array-id stanford1_campus --db D:/darkfiber/ledger/quakeflow_ledger.db \
    --fs 100 --dx 8.16 --exclude-s 395 455 --figs
  ```
- **Resultado**: **SNR50 = 7.73** (interpolado). Curva monótona no
  decreciente dentro de IC Wilson 95% en las 7 escalones (140/140 trials
  válidos). Recall 0% hasta SNR=5, salta a 55% en SNR=8, 85% en
  SNR=12-20. Runtime: 76.2s.

  | SNR | recall | IC95% Wilson | n |
  |---|---|---|---|
  | 1 | 0% | [0.0, 16.1] | 20 |
  | 2 | 0% | [0.0, 16.1] | 20 |
  | 3 | 0% | [0.0, 16.1] | 20 |
  | 5 | 0% | [0.0, 16.1] | 20 |
  | 8 | 55% | [34.2, 74.2] | 20 |
  | 12 | 85% | [64.0, 94.8] | 20 |
  | 20 | 85% | [64.0, 94.8] | 20 |

  Figura: `figures/fig6_recall_snr_stanford1_campus.png`. JSON completo
  con provenance de exclusión: `figures/snr_curve_stanford1_campus.json`.
  Ledger actualizado: `array_profiles` row `stanford1_campus`
  (`D:\darkfiber\ledger\quakeflow_ledger.db`).

### 4. Cambio de código

`snr_curve.py` ganó soporte `.npz` (reusa `replay.load_file`, mismo
loader que `stream_runner.py`/`pipeline_daemon.py` — no uno nuevo) y
`--exclude-s INICIO FIN` para excluir manualmente una ventana de evento
conocido en archivos sin `event_time_index` embebido. Cada fuente de
ruido en el JSON de salida ahora trae `exclusion_kind`
(`"event_time_index"` / `"manual (--exclude-s)"` / `"none"`) y su
`segment_s`, bajo un bloque `noise_exclusion` nuevo — trazable después
del hecho, no solo visible en la consola al momento de correr. Test
unitario (`tests/test_snr_curve.py`, 4 tests): fs/dx nunca se asumen
para `.npz` (`SystemExit` si faltan), shape/dtype/fs/dx del loader
verificados contra el comportamiento real (no supuesto), y la ventana
excluida provablemente no aparece en el pool de ruido devuelto (dos
chequeos independientes: rangos sin solape + un valor marca que no
aparece en ningún array devuelto). No toca Tier0/coherencia/supervisor.
`pytest` 24/24, `darkfiber-validate` 29/29, ruff/mypy limpios.

### Spread actualizado (4 arrays)

```
monterey_bay (1.6) < ridgecrest_north (2.5) < arcata (5.9) < stanford1_campus (7.73)
```

Spread 4.83× (7.73/1.6), arriba del 3.7× de 3 arrays. Stanford es,
hasta ahora, la instalación MENOS sensible medida — necesita casi el
doble de SNR que arcata (la segunda menos sensible) para alcanzar 50%
de recall. No se intenta ninguna explicación causal acá (N=4, todavía
descriptivo) — eso es trabajo de F1.6.

---

## F1.2 — Census de candidatos (cerrado)

*Solo lectura — cero descargas de datos DAS reales. Se consultó metadata,
papers y documentación pública. Ninguna corrida real empieza acá; eso es
F1.5, todavía no gateado.*

### Fuentes consultadas

| Fuente | Resultado |
|---|---|
| HF `AI4EPS/quakeflow_das` | 3 subsets, los 3 ya en uso por el proyecto (ridgecrest_north, monterey_bay, arcata). Sin candidatos nuevos. |
| PubDAS (Univ. Michigan, `pubdas.github.io`) | 8 datasets, ~90TB, acceso primario vía Globus. Se identificaron 6 de los 8 con specs suficientes (ver tabla). El artículo SRL/EarthArXiv fuente (Spica et al. 2023) está paywalled/sin Tabla 1 accesible por los canales probados — el octavo dataset (mencionado como "seafloor" en el abstract) no se pudo identificar por nombre con las fuentes disponibles. Nota de proceso, no un dato inventado: se deja documentado como brecha, no se completa con una suposición. |
| SCEDC AWS Open Data (DAS-Ridgecrest) | **Descartado como candidato nuevo** — verificado: 1,250 canales totales / 1,150 "good channels" tras filtrado (`das_info.csv`), coincide exacto con `array_profiles.n_ch=1150` del `ridgecrest_north` ya medido. Mismo array físico. |
| EarthScope DAS-RCN | Sin portal/catálogo indexado propio (confirmado vía `iris.edu/hq/initiatives/das_rcn`) — apunta al mismo PubDAS y a un Google Doc comunitario ("Public DAS Datasets") que devolvió HTTP 410 (dado de baja) al intentar accederlo directamente. Sin candidatos nuevos más allá de los ya cubiertos por PubDAS. |
| DAS-RCN data portal | Mismo hallazgo que la fila anterior — no es un portal separado, es el mismo conjunto de punteros (PubDAS + el Google Doc, ahora inaccesible). |
| IRIS/EarthScope | GAGE/SAGE en transición a acceso autenticado (IdM) para casi todo — no se investigó más profundo porque no aportó datasets nuevos verificables sin cuenta; queda como candidato de acceso restringido a revisar en F1.3 si hace falta más N. |
| Búsqueda general (fuera de la lista original) | Encontró 1 candidato sólido no cubierto por las fuentes de arriba: "Comprehensive Dataset for Event Classification" (Brno, Figshare). También encontró GorDAS, **descartado** — verificado vía WebSearch que su conteo de archivos de evento (2,470) coincide exacto con el subset "Arcata" de HF `quakeflow_das`, ya en uso. |

### Campo obligatorio: ambiente de instalación

Para cada candidato de la tabla se marca **"(inferido)"** cuando el
ambiente no viene declarado como tal en la metadata/landing page del
dataset y se dedujo del paper asociado — nunca se presenta una inferencia
como si fuera un campo fuente. En los 7 candidatos de abajo, todos menos
uno (LaFarge-Conco, ambiente confirmado por el nombre del sitio pero sin
mayor detalle textual) tienen el ambiente declarado explícitamente en el
texto consultado — no fue necesario inferir de una lectura indirecta del
paper en ningún caso.

### Tabla de candidatos (7)

Orden: (1) accesible sin Globus/cuenta primero, (2) diversidad de
ambiente. `duración mínima de ruido/trial` = fórmula F1.1
(`13.6 + 0.001833 × aperture_m`), aplicada donde la apertura es
calculable a partir de canales × spacing confirmados.

| # | Nombre | Ubicación | Ambiente de instalación | Canales | Spacing | fs | Formato | Duración mín. ruido/trial | Acceso | Licencia y cita |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | PoroTomo DASH/DASV | Brady Hot Springs, NV | Geotérmico — DASH: trinchera superficial en zigzag; DASV: pozo vertical (363m) | No confirmado con precisión (no hallado en fuentes consultadas) | No confirmado | No confirmado | SEG-Y, HDF5, H5 estandarizado | No calculable (falta apertura confirmada) | HTTPS directo, **sin cuenta** (OEDI data viewer) | CC BY 4.0. Feigl et al. 2018 (DOE/OEDI submission 980) |
| 2 | Comprehensive Dataset for Event Classification | Brno, Rep. Checa | Campus universitario — fibra enterrada, telecom (declarado, no inferido: "buried single-mode fiber optic cable" alrededor de un campus) | 1,663 | 1 m | No confirmado con precisión (fuente cita "20 kHz" pero probablemente es la tasa de pulso del interrogador OptaSense ODH-F, no la tasa de archivo almacenado — **bandera, no asumido como dato limpio**) | HDF5, ~46 GB | 16.6 s | HTTPS directo (Figshare), **sin cuenta** | **CC BY-NC-ND 4.0** — no comercial, sin derivados. Bandera real: incompatible con cualquier uso que no sea investigación no comercial sin redistribución modificada. Brno Univ. of Technology, Nature Sci. Data (2025), DOI 10.6084/m9.figshare.27004732 |
| 3 | FOSSA (Fiber-Optic Sacramento Seismic Array) | West Sacramento → Woodland, CA | Urbano — fibra oscura de telecom | 12,000 | 2 m | 500 Hz | No confirmado (PubDAS, probablemente HDF5 estandarizado — no verificado directamente) | 57.6 s | Globus (PubDAS) | Licencia no unificada en PubDAS — a verificar por dataset al momento de acceso (PubDAS es índice, no dueño de la licencia). Lindsey et al. |
| 4 | Fairbanks Permafrost Experiment | Fairbanks, AK | Permafrost — cable enterrado, experimento de deshielo controlado | 4,000 | 1 m | No confirmado con precisión | No confirmado | 20.9 s | Globus (PubDAS) | Ídem PubDAS — no unificada, a verificar |
| 5 | LaFarge-Conco Mine DAS Experiment | North Aurora, IL | Mina subterránea — room-and-pillar, cable en trinchera de 250m (3 capas) | No confirmado con precisión (no hallado) | No confirmado | 1000 Hz | No confirmado | No calculable (falta apertura confirmada) | Globus (PubDAS); red FDSN `5S` (2017) | Ídem PubDAS — no unificada, a verificar |
| 6 | FORESEE (Brady Hot Springs) | Brady Hot Springs, NV | Geotérmico — trinchera superficial (8,700m) + pozo (400m), mismo sitio físico que PoroTomo (proyecto distinto, 2016 vs. este) | ~8,700 (superficial) | ~1 m (gauge length 10m) | No confirmado con precisión | No confirmado | 30.3 s (usando apertura superficial ≈9,100m) | Globus (PubDAS) | Ídem PubDAS — no unificada, a verificar |
| 7 | Stanford 2 / Sand Hill Road Array | Sand Hill Rd, Stanford, CA | Urbano — fibra oscura de telecom bajo una vía pública (hospital → SLAC) | 1,250 | 8.16 m | 250 Hz | No confirmado (PubDAS) | 32.3 s | Globus (PubDAS); red FDSN `9T` (2019-2023) | Ídem PubDAS — no unificada, a verificar |

**Nota de honestidad de datos**: varios campos quedaron "No confirmado"
en vez de completarse con un valor plausible — es una consecuencia directa
de la regla del proyecto de no inventar/reconstruir valores no
sourceados. Antes de que cualquiera de estos candidatos entre a F1.3, esos
campos necesitan una fuente primaria directa (el paper completo, no solo
abstract/PMC, o la metadata del propio dataset tras un primer acceso de
solo-lectura).

**Nota sobre diversidad real**: de los 7, dos (FORESEE y PoroTomo) son el
mismo sitio físico (Brady Hot Springs) con dos despliegues DAS distintos
en años distintos — cuentan como una sola fuente de diversidad de
ambiente, no dos, a la hora de armar el subconjunto final en F1.3. No se
diseña esa selección acá.

### No-candidatos descartados (mismo array ya en el proyecto, con evidencia)

| Nombre encontrado | Array del proyecto | Evidencia |
|---|---|---|
| GorDAS | `arcata` | Conteo de archivos de evento idéntico (2,470) al subset "Arcata" de HF `quakeflow_das` |
| SCEDC AWS Open Data DAS-Ridgecrest | `ridgecrest_north` | 1,150 "good channels" tras filtrado — coincide exacto con `array_profiles.n_ch` |
| PubDAS "Stanford 1 (Stanford campus array)" | `stanford1_campus` | Coincidencia de nombre/convención con el array ya corrido en F1.1 — **inferencia por nombre, no verificación directa por conteo de canales** (a diferencia de las dos filas de arriba). Marcado explícitamente como menos verificado que los otros dos descartes. |
