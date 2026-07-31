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

**⚠️ Superseded 2026-07-31 (QA gate)**: este era el estado real a N=4
(F1.1) — no se edita, es historia. La serie CONGELADA final (N=8) tiene
arcata=8.00 (no 5.9, corregido por heterogeneidad de pool, ver
`docs/observaciones.md` 2026-07-30/31) y stanford1_campus ya NO es el
máximo — arcata lo es. Spread vigente: 5.00× (8.00/1.6). Tabla final:
`docs/array_geometry_table.md`.

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

---

## F1.2b — Verificación de specs (cerrado)

*Solo lectura, previa al pre-registro. Cero descargas de datos DAS reales.
Objetivo: cerrar cada "No confirmado" de la tabla F1.2 con fuente primaria
antes de que cualquier candidato pueda entrar a F1.3.*

### Fe de erratas (no edición silenciosa)

**FORESEE estaba mal ubicado en el census v1.** Decía "Brady Hot Springs,
NV, geotérmico" — **incorrecto**. Fuente primaria (Zhu et al. 2021, *Solid
Earth*, y el propio paper de PubDAS §4.2, Spica et al. 2023): FORESEE está
en **Penn State University, State College, PA** — campus universitario,
fibra oscura enterrada en conducto de concreto a 1-10 m de profundidad
bajo el campus. El error de v1 vino de una búsqueda general que mezcló
FORESEE con FORGE/PoroTomo (ambos sí en Brady Hot Springs, NV, pero son
proyectos geotérmicos distintos) sin verificar contra el paper que
efectivamente lo describe — exactamente el tipo de error que la
verificación de F1.2b existe para atrapar. Fila corregida en la tabla de
abajo, no se borra el error de v1 sin dejar constancia.

### Specs completas — fuente primaria: Table 1, Spica et al. 2023 (PubDAS)

Conseguí el preprint completo (EarthArXiv, `eartharxiv.org/repository/object/3574/download/7140/`,
33 páginas, extraído con PyMuPDF porque el WebFetch normal no pudo
parsear el PDF). La Tabla 1 del paper da specs exactas de los 8 datasets
que PubDAS aloja — esto reemplaza casi todos los "No confirmado" de la
tabla v1 con la fuente primaria real, no una reconstrucción.

| Candidato | Canales | Spacing | Gauge length | fs (archivo alojado) | Formato | T. span alojado | Vol. total alojado | Duración mín. ruido/trial (recalculada) |
|---|---|---|---|---|---|---|---|---|
| FOSSA | **11,648** (confirmado dos veces: texto §4.3 y CL/CS de Tabla 1: 23,300m/2m) | 2 m | 10 m | 500 Hz (nativo, sin downsamplear) | TDMS (Silixa nativo; la Tabla 1 imprime "TDSM", posible error de OCR del PDF — no corregido silenciosamente, señalado acá) | 7 días | 11,680 GB | **56.3 s** (aperture=23,300 m) |
| FORESEE (Penn State, corregido) | 2,137 canales geolocalizados por tap test (Zhu et al. 2021, texto); Tabla 1 da CL=4,900m/CS=2m → ~2,450 canales nominales en el archivo — **discrepancia menor entre las dos fuentes primarias, no resuelta, ambas citadas** | 2 m | 10 m | 125 Hz alojado en PubDAS (downsampleado desde 500 Hz nativo — único preprocesamiento aplicado, según el propio paper) | HDF5 | 365 días (primer año del experimento; el experimento completo corrió 2.5 años, abr-2019 a oct-2022, pero PubDAS solo tiene el primer año) | 29,338 GB (el dataset más grande de PubDAS) | **22.6 s** (aperture=4,900 m, CL de Tabla 1) / 21.4 s si se usa la apertura de los 2,137 canales calibrados — ambas cerca del ~22s esperado |
| Stanford-2 (Sand Hill Road) | **1,250** (confirmado tres veces: FDSN red `9T`, Tabla 1, y texto §4.6) | 8.16 m | 20 m | 250 Hz (nativo) | SEG-Y | 14 días (2 semanas completas, 1-14 marzo 2020) | 2,887 GB | **32.3 s** (aperture=10,200 m) |
| Fairbanks Permafrost | **4,000** (CL=4,000m/CS=1m de Tabla 1, consistente con "4,000 sensores @ 1m" de fuente secundaria) | 1 m | 10 m | 1,000 Hz | TDMS (mismo caveat de OCR que FOSSA) | 59 días nominales — **pero ver caveat abajo** | 10,441 GB | **20.9 s** (aperture=4,000 m) |
| LaFarge-Conco (mina) | **1,120** (CL≈1,120m/CS=1m de Tabla 1 y texto §4.4 — 3 capas de cable en el mismo trazado, no 3× canales) | 1 m | 10 m | 1,000 Hz | SEG-Y | 2 días (con fuentes activas: pesa de 23kg + 2 tronaduras de mina) | 45 GB (el dataset más chico de PubDAS por lejos) | **15.7 s** (aperture=1,120 m) |
| PoroTomo DASH (Brady Hot Springs, NV) | **8,720** (Silixa iDAS, fuente: GDR + literatura secundaria cruzada con dos búsquedas independientes) | 1.021 m | 10 m | 1,000 Hz | SEG-Y + H5 | 15-18 días (8-26 marzo 2016, con una pausa) | 81,000 GB (Tabla 3 de PubDAS, dataset externo — no en PubDAS mismo, ver más abajo) | **Ambiguo — ver caveat geométrico abajo**: 29.7 s si se usa longitud de cable (~8,800m) o 16.4 s si se usa la apertura geométrica real (~1.5km, arreglo en "espina de pescado"/zigzag) |
| Brno (event classification, condicional) | **1,663** (confirmado, PMC full text) | 1 m | No especificado en el paper | **No resuelto — ver sección Brno abajo** | HDF5 | No especificado en el paper (mismo gap que fs) | 46 GB total (Figshare) | **16.7 s** (aperture=1,662 m) — calculable independientemente del gap de fs |

**Caveat Fairbanks** (no estaba en v1, aparece al leer el texto completo
del paper): el dataset alojado en PubDAS **no es ruido continuo** — es
"el experimento activo, que graba disparos secuenciales de un único
Surface Orbital Vibrator (SOV), barrido varias veces cada noche" (texto
§4.1). Los 59 días nominales de T.span probablemente contienen huecos
grandes entre sesiones de barrido nocturno — la tasa promedio del dataset
(10,441 GB / 59 días ≈ 2.05 MB/s) es baja para 4,000 canales @ 1kHz
(¬16 MB/s en crudo), lo que es consistente con grabación no continua, no
con compresión. **No confirmado si hay suficiente ruido de fondo real
entre barridos para 140 inyecciones — a verificar en el primer acceso de
solo lectura (F1.4), no asumido acá.**

**Caveat LaFarge-Conco**: aunque el dataset trae fuentes activas
(marcado ⋆ en Tabla 1), el texto confirma que SÍ hay ruido de fondo real
utilizable: "ruido de fondo de tráfico de camiones de mina y cintas
transportadoras se observa durante el experimento DAS, excepto cuando la
mina se despejó para las tronaduras" (§4.4) — no es un dataset
puramente activo, a diferencia de la duda abierta en Fairbanks.

**Caveat PoroTomo DASH — ambigüedad geométrica real, no resuelta**: el
arreglo tiene forma de "espina de pescado" (zigzag) con apertura
geométrica máxima de ~1.5 km en dirección NE-SW, pero la longitud total
de cable es ~8.8-8.9 km (el cable se dobla sobre sí mismo repetidamente).
La fórmula de duración mínima de ruido (`min_len_s`) se derivó asumiendo
un cable aproximadamente lineal (válido para los otros 6 arrays de esta
tabla) — para un arreglo zigzag, la apertura físicamente relevante para
el moveout de plano-onda es la geométrica (~1.5 km), no la longitud de
cable. Usar la apertura geométrica da un piso más bajo (16.4s) que usar
la longitud de cable (29.7s). **No decido acá cuál usar — queda como
pregunta abierta explícita para F1.3**, con ambos valores calculados y
citados.

### Brno — resolución del paper completo

Conseguí el full-text vía PMC (`pmc.ncbi.nlm.nih.gov/articles/PMC12078700/`,
Nature *Scientific Data* 2025, Brno University of Technology). Resultado:

- **Ambiente**: confirmado directo del texto, no inferido — "instalada 1
  metro bajo tierra, junto a la vereda" en un campus universitario en
  Brno, Rep. Checa. Fibra ITU-T G.652.D estándar, originalmente para
  comunicación inter-campus.
- **Licencia**: confirmado — **CC BY-NC-ND 4.0**. Tag aplicado: **excluido
  de cualquier uso comercial y de redistribución modificada.**
- **La bandera de fs — no se pudo resolver, y no es un gap mío**: el
  paper especifica una "tasa de repetición de pulso de 20 kHz" pero
  **nunca declara explícitamente la tasa temporal del archivo HDF5
  almacenado** (que puede ser menor que la tasa de pulso del
  interrogador — son cosas distintas, como ya se sospechaba en el census
  v1). La sección de Data Records describe la forma del array
  (`RawData`, Tiempo × 1,663 canales) pero no da el Hz del eje temporal.
  **Esto es una omisión real del paper, confirmada al leer el texto
  completo — no una búsqueda insuficiente de mi parte.** Sin ese dato,
  Brno **no cumple "specs completas" y no entra a F1.3** en este estado.
  Dos caminos posibles, ninguno tomado acá: (a) contactar a los autores
  (Brno Univ. of Technology, Dept. de Telecomunicaciones), o (b) leer el
  header del propio archivo HDF5 tras un primer acceso de solo lectura —
  lo segundo ya cruza la línea hacia "tocar el dataset", así que
  necesitaría autorización explícita separada antes de F1.3, no implícita
  acá.

### Hipótesis MARS/Monterey Bay — refutada como estaba planteada, con matiz

Encontré la Tabla 1 (los 8 datasets que PubDAS aloja DIRECTAMENTE) y la
Tabla 3 (lista no-exhaustiva de OTROS datasets DAS en OTRAS plataformas,
solo referenciados por el paper) en el mismo PDF. Resultado:

- **Los 8 datasets que PubDAS aloja son**: Fairbanks, FORESEE, FOSSA,
  LaFarge-Conco, Stanford-1, Stanford-2, Stanford-3, **Valencia**. **No
  hay ningún dataset de Monterey Bay/MARS entre los 8 alojados por
  PubDAS.** El ejemplo real de "seafloor" que menciona el abstract del
  paper es **Valencia** (cable submarino de telecomunicaciones
  Valencia-Palma de Mallorca, operado por IslaLink — 2,977 canales,
  16.8m spacing, 1000Hz nativo/250Hz alojado, HDF5, 40,811 de sus 50,000m
  están bajo el lecho marino del Mediterráneo, confirmado por presencia
  de oleaje/microsismo secundario en los registros) — **no Monterey Bay**.
  La hipótesis, tal como estaba planteada ("el octavo dataset seafloor =
  MARS = monterey_bay"), **queda refutada**: PubDAS no tiene un dataset
  de Monterey Bay entre sus 8 propios.
- **Matiz — sí existe un "Monterey Bay" en la Tabla 3** (dataset externo,
  NO alojado por PubDAS, solo catalogado): "Monterey Bay, Moss Landing
  CA, 4 días, 0.565 GB, tinyurl.com/ynab86bc". Por duración (4 días) y
  tamaño (0.565 GB, minúsculo), esto coincide con la campaña original de
  2018 de Lindsey et al. (4 días de mantenimiento del nodo MARS,
  ~10,000 canales, cable repropuesto como arreglo DAS) — **NO con
  SeaFOAM** (Romanowicz et al. 2023, despliegue de un año completo,
  10,245 canales/5.1m/200Hz — specs que coinciden casi exactas con el
  `monterey_bay` ya medido en el proyecto: 2,845 canales/5.2m/199.995Hz,
  probablemente un subconjunto de canales de SeaFOAM). Es decir: **hay
  evidencia razonable de que el `monterey_bay` del proyecto viene de
  SeaFOAM, no de la campaña de 4 días de 2018** — son dos experimentos
  físicamente en el mismo cable pero temporalmente distintos y con
  specs distintas (10,000 canales/4 días/2018 vs. 10,245 canales/1
  año/2022-2023). La entrada de Tabla 3 sería, en principio, un
  candidato nuevo genuino (chico, descargable sin Globus vía el link
  corto) — pero no estaba en la lista de 7 seleccionados y no lo agrego
  acá sin tu aprobación, solo lo dejo documentado como hallazgo.
- **Recomendación no pedida pero relevante**: Valencia llena mejor el
  hueco de diversidad "seafloor/submarino" que la hipótesis original
  buscaba — es un candidato PubDAS real, con specs completas de fuente
  primaria, no en la lista de 7. Lo señalo para tu consideración, no lo
  agrego a la selección.

### Setup de Globus — pasos exactos

Fuente primaria: §6 del paper de PubDAS ("How to access PubDAS") +
verificación cruzada del link real contra `github.com/DAS-RCN/awesome-das`
(no tomado de una sola búsqueda sin verificar).

**Lo que hacés vos** (instalación + autenticación, según tu propia
instrucción — no automatizable sin tus credenciales):
1. Instalar **Globus Connect Personal** (Windows/Mac/Linux, gratis) desde
   `globus.org` — agente liviano de un solo usuario.
2. Autenticarte en `app.globus.org` (login institucional o cuenta
   Globus/Google/ORCID — OAuth, requiere tu navegador).
3. Registrar tu máquina como un "endpoint" personal de Globus (parte del
   instalador — le da nombre/ownership, queda asociado a tu cuenta).
4. Primer acceso a la colección PubDAS vía navegador para aceptar
   términos, si los pide: `https://app.globus.org/file-manager?origin_id=706e304c-5def-11ec-9b5c-f9dfb1abb183&origin_path=/`
   (endpoint ID verificado contra `DAS-RCN/awesome-das`, no inventado).

**Lo automatizable después** (una vez que tu endpoint esté activo y
autenticado — yo podría scriptear esto si lo autorizás en F1.4/F1.5, no
ahora):
- Transferencias específicas vía `globus-cli transfer` o el SDK de Python
  de Globus, apuntando de la colección PubDAS a tu endpoint personal —
  no requiere reautenticar cada vez mientras el token siga vigente.
- Selección de archivos/rangos de fecha específicos dentro de cada
  dataset (Globus permite filtrar por carpeta/patrón antes de transferir).
- Verificación de integridad post-transferencia (Globus ya hace checksum
  automático, no hace falta un paso separado).

**No automatizable en ningún punto**: la instalación del software y el
primer login OAuth — ambos requieren tu navegador/credenciales, por
diseño de Globus, no por una limitación mía.

### Plan de descarga por array — tamaños declarados ANTES de bajar

Propuesta de techo, **no ejecutado, a tu aprobación**: descargar ~10× el
piso de `min_len_s` por candidato (margen conservador, consistente con
la recomendación ya escrita en F1.1 de "pedir varias veces el piso, no
el mínimo exacto"), calculado con la tasa Vol/T.span de cada dataset
(Tabla 1). **No es el tamaño total del dataset — es una ventana acotada
de ruido real, elegida por vos antes de bajar nada.**

| Candidato | Ventana propuesta (10×piso) | Tasa (Vol/T.span) | Tamaño estimado |
|---|---|---|---|
| LaFarge-Conco | 157 s | 0.26 MB/s | **~0.04 GB** |
| FORESEE | 226 s | 0.93 MB/s | **~0.21 GB** |
| Fairbanks | 209 s | 2.05 MB/s (promedio — ver caveat de huecos arriba) | **~0.43 GB** |
| Stanford-2 | 323 s | 2.39 MB/s | **~0.77 GB** |
| FOSSA | 563 s | 19.31 MB/s | **~10.6 GB** |
| PoroTomo DASH | 164-297 s (según qué apertura se use) | 62.5 MB/s | **~10.0-18.1 GB** |
| Brno | No calculable — falta fs y duración total del archivo fuente | — | — |
| **Total (6 con specs completas)** | — | — | **~22-30 GB** |

FOSSA y PoroTomo dominan el costo (tasa alta: muchos canales × fs alta).
Un techo total de **~30 GB** para el primer batch cubriría los 6 con
specs completas, dejando margen. **No se baja nada con esto — es la cifra
a la que pedís que se ajuste el plan de F1.3/F1.4, vos decidís el techo
real.**

### Veredicto por candidato — ¿entra a F1.3 con specs completas?

| Candidato | Specs completas? | Notas |
|---|---|---|
| FOSSA | Sí | Único caveat menor: formato TDMS con posible error de OCR en la fuente |
| FORESEE (corregido) | Sí | Ubicación corregida; discrepancia menor de canales (2,137 vs ~2,450) documentada, no bloqueante |
| Stanford-2 | Sí | Triple-confirmado, sin caveats |
| Fairbanks | Sí, con caveat operacional | Specs completas, pero falta confirmar cuánto ruido real de fondo hay entre barridos SOV antes de comprometer F1.3 |
| LaFarge-Conco | Sí | Ruido de fondo real confirmado presente pese a ser dataset "activo" |
| PoroTomo DASH | Sí, con ambigüedad abierta | Specs completas; falta decidir qué apertura usar (geométrica vs. longitud de cable) |
| Brno | **No** | fs y duración total del archivo no están en el paper — gap real de la fuente, no mío. Queda condicional hasta resolverse por otra vía |

---
