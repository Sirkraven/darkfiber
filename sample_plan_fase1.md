# Sample plan pre-registrado — F1.3/F1.4/F1.5 (SNR50, extensión a más instalaciones)

**Fecha de registro:** F1.5 (corridas) cerrado para FORESEE, Stanford-2
y Valencia — las 3 curvas nuevas están medidas, ver §14. **FOSSA sigue
sin correr** — va al final, con su piloto de un escalón, después de
bajar su Ola 3 (TDMS), por instrucción explícita.

## 0. Estado

**Ola 1 descargada** en `D:\darkfiber\data\` (subcarpetas por array):
FORESEE (10 archivos .hdf5 — 2 son la medición pre-registrada, 8 son
reserva declarada, no entran a la corrida), Stanford-2 (10 archivos
.sgy — 4 medición + 6 reserva), FOSSA (solo metadata: chanmap +
licencia, sin `.tdms` todavía), Valencia (solo metadata: geometrías +
licencia, sin `.hdf5` todavía). **La medición usa exactamente los
archivos de este documento — si el chequeo de estacionariedad rechaza
alguno, se avisa antes de sustituir por uno de reserva (desviación del
pre-registro, requiere aprobación explícita, no se resuelve sola).**

Los 4 arrays tienen estructura real confirmada — nombres de archivo
literales (primero de cada secuencia), formato, tamaño por archivo.
**Estos archivos SON el primer segmento cronológico — no hay
cherry-pick, se instancia la regla ya pre-registrada, no se elige a
mano.**

## 1. FOSSA

- **Estructura real**: `/FOSSA/Data/` — carpeta plana (NO hay subcarpetas
  por fecha como asumí en una revisión anterior; corregido acá).
- **Primer archivo**: `westSac_170906155429.tdms` (699.45 MB,
  2017-09-06 15:54:29 UTC).
- **K=19 consecutivos** cronológicamente desde ese archivo. Nota: el
  rango que diste (155429 → 171329) cubre 79 minutos — más ancho que
  19×60s=19 min si los archivos fueran perfectamente contiguos. Esto es
  evidencia de que **puede haber huecos reales en la secuencia** (no
  asumido, pero tampoco descartado) — ver §1c, cambia el diseño del
  esquema de lectura.
- **Tamaño**: 19 × 699.45 MB = **13.29 GB**.
- **Chanmap**: `DASchanmap_westsac_2017.csv` (268.55 KB) — resuelve
  conteo real de canales/spacing, reemplaza la hipótesis de 11,648 por
  aritmética inversa.
- **Formato**: NI TDMS, int16.
- **Licencia**: `licence.txt` (raíz de FOSSA, 15.72 KB — nombre en
  inglés británico, no "license.txt"; contenido sin leer, se lee tras
  la descarga).
- **ComCat**: ventana limpia, ya verificado en la revisión anterior
  (2017-09-06, día completo, 300km de Sacramento/Woodland, M≥2.0 —
  cero eventos cerca de 15:54-16:14 UTC).

### 1a. Loader TDMS — sin cambios de diseño, F1.4

`npTDMS`, upcast a float32 inmediato (mismo contrato que
`replay.load_file`, `replay.py:39-40`), fs/spacing del chanmap CSV +
header TDMS, nunca asumidos. Tests: dtype/shape (análogo a
`test_npz_loader_shape_dtype_fs_dx`) + supervivencia de inyección a
SNR=1 sin cuantización (§1e del borrador anterior, sin cambios).

### 1b. Presupuesto — sin cambios (K=19, 13.29 GB)

Piso de ruido: 56.3s (aperture=23,300m). Margen ~20× con K=19
(1,140s nominal — o más ancho si hay huecos reales, ver abajo).

### 1c. Esquema de lectura — corregido: el mecanismo NO cambia, solo la carga en RAM

**Corrección de la revisión anterior.** El texto previo ("un archivo
completo por trial") describía mal lo que realmente proponía y sonaba
a un cambio de mecanismo de medición — no lo era, pero la redacción no
lo dejaba claro. **El mecanismo es idéntico al de los 4 arrays ya
medidos, sin excepción**: dos etapas, tal como pediste.

1. **Selección de archivo**: `run_step` ya sortea, para cada trial, UNA
   fuente al azar de la lista (`sources[picker.integers(0, len(sources))]`
   — `snr_curve.py:194`, código existente, sin cambios). Para FOSSA, la
   lista tiene 19 fuentes en vez de las 12-15 de los otros arrays — mismo
   mecanismo, más opciones.
2. **Ventana local dentro de ese archivo**: `inject_and_verify_sized`
   (`selftest.py:126-131`, también sin cambios) recorta una ventana
   ALEATORIA de `min_len_n` muestras DENTRO de la fuente elegida, y
   `snr_to_amplitude` calibra el SNR contra el RMS de ESA ventana local
   — el mismo mecanismo §0b, sin excepción para FOSSA.

**Lo único que cambia para FOSSA es CÓMO llegan los datos a la lista de
`sources`, no qué hace el pipeline con ellos.** `gather_noise_sources`
hoy carga TODOS los archivos de la lista en RAM de una vez — con K=19
de FOSSA (~0.7GB c/u) eso son 13.3GB simultáneos, inviable. La solución
es una variante "lazy" de `gather_noise_sources` que guarda las RUTAS
de los 19 archivos en la lista de fuentes en vez de arrays ya cargados,
y difiere el `load_file` real al momento en que `inject_and_verify_sized`
necesita esa fuente para un trial — cargando SOLO el archivo elegido en
el paso 1, liberándolo después. Nunca cruza el borde entre archivos (la
ventana del paso 2 vive enteramente dentro del archivo del paso 1) — por
eso los huecos de grabación (§1, evidencia de 79 min para 19 archivos)
no importan: no hace falta asumir contigüidad para nada, ni verificarla.

**Verificación del piso contra el archivo de 60s — con la fórmula
exacta de `inject_and_verify_sized`, no la aproximación**: el piso
depende de `v_app` (sorteado por trial en `V_APP_RANGE_MPS=(2000,6500)`
m/s) porque el término de moveout es `aperture_m / v_app`. Con
aperture=23,300m, `seismic_v_min_mps=1500`, `warmup_s=8.8s`
(`lta_s=8.0+gap_s=0.4+sta_s=0.4`), wavelet Ricker `dur_s=0.8s` (default
de `synth.ricker` — el `6.0` del código es la frecuencia central, no la
duración; aclarado para no repetir el error de lectura):

| `v_app` sorteado | piso exacto | margen en archivo de 60s |
|---|---|---|
| 2000 m/s (el más lento, peor caso) | **56.317s** | **3.683s** |
| 3200 m/s | 51.948s | 8.052s |
| 4500 m/s | 49.844s | 10.156s |
| 6500 m/s (el más rápido) | 48.251s | 11.749s |

**Respuesta directa a tu pregunta — NO, no cabe holgado en el peor
caso.** El piso SIEMPRE cabe (60s > 56.317s en el peor caso, ningún
trial se descarta por ventana insuficiente — `n_t > min_len_n` se
cumple con margen positivo en todos los casos), pero el margen de
sorteo dentro de un mismo archivo va de 3.68s (v_app lento) a 11.75s
(v_app rápido), no es generoso en el extremo lento. La variedad real
entre los 140 trials viene predominantemente de CUÁL de los 19 archivos
se sortea (mecanismo existente, sin cambios), no de dónde cae la
ventana dentro de un archivo dado — eso es cierto para FOSSA en mayor
medida que para arrays con pools de archivos más largos (ej. el
`.npz` de Stanford-1 en F1.1 tenía 900s en un solo archivo, margen de
~840s). No lo resuelvo acá — es tu decisión si 3.68s de margen en el
peor caso es aceptable tal cual, o si preferís otra cosa (ej. bajar K
para gastar menos y compensar con algo distinto, o aceptarlo con esta
cifra documentada). Confirmá antes de que esto se implemente en F1.4.

## 2. Valencia

- **Estructura real**: `/Valencia/Data/SR_Valencia_<ts>_UTC/`.
- **Primer archivo**: `SR_Valencia_2020-09-01_13-21-28_UTC` (1.78 GB,
  HDF5, 10 min).
- **3 archivos consecutivos**: **5.34 GB** (sin cambios respecto a la
  revisión anterior).
- **Geometría — CONFIRMA la restricción submarina, ya no es estimada**:
  dos archivos separados en la raíz, `DAS-1-geometry-Valencia-undersea.csv`
  y `DAS-1-geometry-Valencia-onland.csv` — el split tierra/mar viene
  directamente de PubDAS, no hace falta estimarlo por aritmética
  (9,189m/16.8m≈canal 548, como había calculado antes). El canal exacto
  de corte sale de contar filas en `-onland.csv` una vez descargado —
  reemplaza la estimación, no la contradice (mismo orden de magnitud
  esperado).
- **Licencia**: `ODBL_license.txt` — **cierra el gap de licencia que
  había quedado abierto en F1.2b/F1.3** (Open Database License,
  confirmado por nombre de archivo; contenido exacto se lee tras
  descarga, pero el tipo de licencia ya no es una incógnita).
- **ComCat**: verificado ahora — 2020-09-01, día completo, radio 300km
  del área Valencia/Palma de Mallorca (39.2°N, 1.0°E), M≥2.0. **Cero
  eventos en todo el día.** Ventana limpia, sin `--exclude-s`.

### 2a. Loader — HDF5 genérico nuevo, NO reusar `load_quakeflow_h5` tal cual

Revisé `load_quakeflow_h5` (`run_on_quakeflow.py:114-134`): tiene
**defaults silenciosos** si faltan los attrs —
`_attr(attrs, "dt_s", 0.01)` y `_attr(attrs, "dx_m", 8.0)` — es decir,
si un archivo NO trae esos attrs con esos nombres exactos, el loader
**asume fs=100Hz/dx=8m en silencio en vez de fallar**. Esto es
exactamente lo que la regla del proyecto prohíbe para formatos nuevos
(ver el contrato explícito de `.npz`, que sí falla fuerte). Valencia no
es QuakeFlow — no sé si su HDF5 trae esos attrs con esos nombres, y no
lo voy a asumir.

**Se necesita un loader nuevo** (compartido con FORESEE, ver §3a — mismo
formato genérico, mismo problema): lee el primer dataset 2D del HDF5
(mismo fallback defensivo que ya existe), pero **fs/dx son OBLIGATORIOS
como override explícito** (mismo contrato que `.npz` en `replay.py`,
`SystemExit` si faltan) — nunca leídos de attrs no verificados. Valores
a pasar explícitamente (de Tabla 1, PubDAS, ya conocidos):
`fs=250` (alojado, downsampleado), `dx=16.8`.

## 3. Stanford-2

- **Estructura real**: `/Stanford-2-Sandhill-Road/Data/<YYYYMMDD>/`.
- **Primer archivo**: `cbt_processed_20200301_065859.550+0000.sgy`
  (75.30 MB, SEG-Y, dentro de `20200301/`).
- **K=4 consecutivos**: **0.30 GB** (verificación aritmética abajo
  confirma el estimado de "~3-4" que diste — cierro en 4).
- **Geometría**: `Stanford-2-Sandhill-Road-geometry.csv` — a verificar
  contra ella el subrango recto 400-750 (hallazgo del paper primario,
  Spica et al. 2023 §4.6) antes de correr; si la geometría real difiere,
  el subrango se ajusta a lo que diga el CSV, no al número del paper.
- **Licencia**: `ODBL_license.txt` (mismo tipo que Valencia).
- **ComCat**: verificado — 2020-03-01, día completo, radio 300km de
  Stanford/Palo Alto (37.42°N, 122.17°O), M≥2.0. Un solo evento ese
  día (M2.2, Danville CA, 16:09:34 UTC) — **más de 9 horas de distancia**
  de la ventana (06:58:59 UTC). Ventana limpia, sin `--exclude-s`.

### 3a. Loader — F1.4 CERRADO: REUSA `convert_stanford_sgy.py`/`read_segy()` tal cual, verificado contra el archivo real

**Corrido contra el archivo real** (`cbt_processed_20200301_065859.550+0000.sgy`,
Ola 1): `read_binary_header` da `sample_interval_us=4000, samples_per_trace=15000,
format_code=5`; `read_segy()` devuelve `data.shape=(1250, 15000)`,
`fs=250.0`, duración exacta `60.0s` — coincide con la verificación
aritmética previa, ahora confirmado directamente, no solo por cálculo.
**Sin cambios de código** — `read_segy()` (`convert_stanford_sgy.py:47-67`)
ya es genérico (lee todo del header real, nunca asume), mismo archivo,
misma convención de nombre (`cbt_processed_*`) que Stanford-1.

Valores de la muestra real: rango aproximado -205,735 a +205,191,
magnitud consistente con **fase óptica desenrollada, no strain-rate
todavía** — confirma (no solo presume) que la derivada
fase→strain-rate por default de `convert_stanford_sgy.py` también hace
falta acá, mismo comportamiento que Stanford-1.

**Geometría real** (`Stanford-2-Sandhill-Road-geometry.csv`, 352 filas):
cubre exactamente canales **399-750** (no 400-750 — ligero corrimiento
de a uno respecto al número citado del paper), contiguos, confirmado.
Distancia haversine acumulada entre canales consecutivos:
**2,847.07m** de longitud de trayecto real, spacing mediano **7.87m**
(cerca del 8.16m nominal — diferencia esperable entre GPS real y spec).
Razón trayecto-real/distancia-recta = **1.045** — el segmento es
genuinamente casi lineal (4.5% más largo que la línea recta
extremo-a-extremo), **confirmado con evidencia geométrica real, no solo
citado del paper**. Piso de ruido recalculado con la apertura real:
13.6+0.001833×2,847.07=**18.82s** (vs. 18.8s ya estimado — coincide).

**Test nuevo** (`tests/test_convert_stanford_sgy.py`, 4 tests): header
binario real reflejado sin asumir (parámetros de Stanford-2: 1250
canales, sample_interval=4000µs), shape/dtype/fs exactos contra una
fixture sintética con esos mismos parámetros, rechazo fuerte de
`format_code != 5`, y `fs` derivado del header (no hardcodeado,
verificado con un sample_interval distinto). **F1.4 de Stanford-2
cerrado — no hace falta loader nuevo.**

## 4. FORESEE

- **Estructura real**: `/FORESEE/Data/<YYYYMM>/`.
- **Primer archivo**: `FORESEE_UTC_20190404_194804.hdf5` (321.15 MB,
  dentro de `201904/`).
- **K=2 consecutivos**: **0.64 GB**.
- **Chanmap**: `foresee_ch_loc.txt` (raíz, 72.65 KB).
- **Licencia**: `ODBL_license.txt`.
- **ComCat**: verificado — 2019-04-04, día completo, radio 300km de
  State College PA (40.79°N, 77.86°O), M≥2.0. **Cero eventos en todo
  el día.** Ventana limpia, sin `--exclude-s`.

### 4a. F1.4 CERRADO — discrepancia de canales resuelta directo del archivo real, no solo por aritmética

Abierto el archivo real (`FORESEE_UTC_20190404_194804.hdf5`, Ola 1) con
`h5py`: dataset `raw`, shape **`(2137, 75000)`**, dtype **`float16`**
(no float32 como se había asumido en el cálculo de F1.2b/F1.3 —
corregido acá). `foresee_ch_loc.txt` (geometría real): **2,137 líneas
exactas** — coincide con el shape del HDF5, canal por canal. **2,137
confirmado directamente, no solo por aritmética inversa.** El archivo y
el dataset `raw` **no traen NINGÚN attr** (ni `dt_s`/`dx_m` ni ningún
otro nombre) — confirma que el riesgo de default silencioso de
`load_quakeflow_h5` (§2a) era real, no hipotético.

**Corrección de la estimación de duración**: con el dtype real
(float16, 2 bytes) en vez del float32 asumido, la duración real por
archivo es **~600s (10 minutos)**, no ~300s (5 minutos) como daba el
cálculo anterior con el dtype equivocado. Confirmado por dos vías
independientes: (a) `75000 muestras / fs` con `fs` derivado de los
deltas reales del dataset `timestamp` (`np.diff`, mediana =
0.0079999s → fs=125.0016Hz, prácticamente 125Hz exacto) da 599.98s;
(b) `2137×75000×2 bytes + 75000×8 bytes (timestamp float64) ≈
321,150,000 bytes`, coincide con el tamaño real del archivo
(321,152,048 bytes) casi exacto. **Esto hace el margen de sorteo de
FORESEE mucho más cómodo de lo que se había estimado** — con K=2
archivos de ~600s cada uno (1,200s totales) contra un piso de ~21s, el
margen es de cientos de segundos, sin ninguna de las tensiones que sí
tiene FOSSA (§1c).

**Apertura real** (haversine sobre `foresee_ch_loc.txt`, 2,137 puntos
lat/lon): longitud de trayecto acumulada **4,303.4m**, spacing mediano
**2.01m** (coincide con el 2.0m ya usado). Piso de ruido recalculado
con esta apertura real: 13.6+0.001833×4,303.4=**21.49s** (vs. 21.4s con
la aproximación (n-1)×dx, prácticamente igual — no cambia nada).

**Nota nueva, no anticipada**: `float16` es un tercer dtype de origen
distinto a todo lo visto hasta ahora en el proyecto (float32 en la
mayoría, int16 en FOSSA, ahora float16 en FORESEE) — mismo tipo de
cuidado que int16: el loader debe upcastear a float32 INMEDIATAMENTE,
nunca hacer aritmética en float16 (precisión de ~3 dígitos
significativos, mantisa de 10 bits). A diferencia de int16, no hay
riesgo de truncar-a-cero en la inyección (float16 tiene exponente
flotante, no trunca fracciones a 0 como un entero) — pero SÍ hay una
pérdida de precisión ya presente en el dato de origen (decisión de
quien preparó el HDF5 de PubDAS, para ahorrar espacio) que ningún
loader puede recuperar — una propiedad del dato, no un bug de pipeline
a corregir, señalado igual que el headroom de grabación de FOSSA.

### 4b. Loader — `load_hdf5_generic`, implementado y verificado contra el archivo real

Nueva función `replay.load_hdf5_generic(path, fs, dx, key=None)`
(`replay.py`), **a propósito separada de `load_quakeflow_h5`**: `fs`/`dx`
OBLIGATORIOS (`SystemExit` si faltan, mismo contrato que `.npz`), nunca
lee attrs (ni falta que hace — FORESEE no trae ninguno). `key`: si no
se da, prueba `"raw"` primero (la convención real observada en
FORESEE), después el primer dataset 2D que encuentre — **un solo
loader sirve a Valencia y FORESEE**, no hace falta uno por array,
mientras ninguno de los dos use una convención de nombre distinta a lo
ya visto (a confirmar cuando Valencia se descargue en Ola 2).

**Verificado contra el archivo real** (no solo la fixture sintética):
`load_hdf5_generic(path, fs=125.0, dx=2.0)` da `data.shape=(2137, 75000)`,
`data.dtype=float32` (upcast confirmado desde el float16 real),
`attrs={}`. Sin `fs`/`dx`, `SystemExit` confirmado contra el archivo
real también, no solo sintético.

**6 tests nuevos** (`tests/test_replay_hdf5_generic.py`): `SystemExit`
sin fs/dx (las 3 combinaciones: sin ninguno, solo fs, solo dx); attrs
presentes pero ignorados a propósito (el loader nunca los lee, ni con
nombres distintos a la convención QuakeFlow); shape/dtype/upcast vía
la clave `"raw"` por default (fixture float16, igual que el real);
fallback al primer dataset 2D si `"raw"` no existe; `key` explícito
inexistente falla fuerte (no cae en silencio al fallback); y
supervivencia de una inyección a SNR=1 sobre datos float16-de-origen
sin degradarse tras el upcast (mismo tipo de chequeo que el int16 de
FOSSA, ahora para el tercer dtype). **F1.4 de FORESEE cerrado.**

## 5. Presupuesto final

| Array | Archivos | Tamaño |
|---|---|---|
| FOSSA | 19 × 699.45 MB | 13.29 GB |
| Valencia | 3 × 1.78 GB | 5.34 GB |
| Stanford-2 | 4 × 75.30 MB | 0.30 GB |
| FORESEE | 2 × 321.15 MB | 0.64 GB |
| Chanmaps/geometrías/licencias (7 archivos chicos) | — | < 1 MB |
| **Total** | | **~19.57 GB** |

Techo: 40 GB. Margen: ~20.4 GB. Coincide con tu estimación (~19.7GB).
**Este es el número final** — los 4 arrays ya tienen archivo real, no
quedan provisorios por tasa.

## 6. Parámetros comunes — sin cambios

| Parámetro | Valor |
|---|---|
| `SNR_STEPS` | `(1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0)` |
| `N_PER_STEP` | 20 (140 por array) |
| `V_APP_RANGE_MPS` | `(2000.0, 6500.0)`, signo aleatorio |
| Wavelet | Ricker |
| Umbral Tier0 | 4.0 (default, homogéneo) |
| Seed | Hardcoded: `np.random.default_rng(1_000 + step_idx)` |

## 7. Criterio de estacionariedad — sin cambios, uniforme en los 4

Umbral: max/min RMS por archivo > 3.0× → subconjunto contiguo más largo
bajo el umbral (empate: el que empieza más temprano). K_min proporcional
a ~10× el piso propio de cada array. Rama terminal: pool completo +
flag de deriva explícito, nunca en silencio. (Detalle completo y
justificación: commit anterior.)

**Confirmado explícitamente para FOSSA, dado el hallazgo de huecos de
§1**: el chequeo opera sobre la serie de RMS por archivo del pool (19
valores, uno por archivo), **sin asumir contigüidad temporal entre
ellos en ningún punto** — ni para calcular la serie (cada RMS es del
archivo completo, no de un tramo cruzando bordes) ni para el algoritmo
de subconjunto contiguo (que opera sobre el ÍNDICE de los archivos en
la lista ordenada cronológicamente, no sobre su separación real en
tiempo). Los huecos de grabación no rompen nada de este chequeo.

## 8. Loaders necesarios — resumen para F1.4

| Array | Loader | Estado |
|---|---|---|
| FOSSA | TDMS nuevo (`npTDMS`) + lectura lazy de 1 archivo/trial (§1c revisado) | Diseñado, no implementado |
| Valencia | HDF5 genérico nuevo, fs/dx obligatorios | Diseñado, no implementado |
| FORESEE | Mismo HDF5 genérico que Valencia | Diseñado, no implementado |
| Stanford-2 | **Reusa `convert_stanford_sgy.py`/`read_segy()` sin cambios** | Ya existe, verificar derivada en primer archivo real |

## 9. Lista de transferencias — Globus (endpoint `alejandro-darkfiber`)

**Archivos de datos** (regla: primeros N cronológicamente desde el
archivo dado, sin cherry-pick):

1. `/FOSSA/Data/westSac_170906155429.tdms` + 18 siguientes cronológicamente (19 total, ~13.29 GB)
2. `/Valencia/Data/SR_Valencia_2020-09-01_13-21-28_UTC/...` + 2 siguientes cronológicamente (3 total, ~5.34 GB)
3. `/Stanford-2-Sandhill-Road/Data/20200301/cbt_processed_20200301_065859.550+0000.sgy` + 3 siguientes cronológicamente (4 total, ~0.30 GB)
4. `/FORESEE/Data/201904/FORESEE_UTC_20190404_194804.hdf5` + 1 siguiente cronológicamente (2 total, ~0.64 GB)

**Metadata/chanmaps** (5 archivos):

5. `/FOSSA/DASchanmap_westsac_2017.csv` (268.55 KB)
6. `/Valencia/DAS-1-geometry-Valencia-undersea.csv`
7. `/Valencia/DAS-1-geometry-Valencia-onland.csv`
8. `/Stanford-2-Sandhill-Road/Stanford-2-Sandhill-Road-geometry.csv`
9. `/FORESEE/foresee_ch_loc.txt` (72.65 KB)

**Licencias** (4 archivos):

10. `/FOSSA/licence.txt` (15.72 KB)
11. `/Valencia/ODBL_license.txt`
12. `/Stanford-2-Sandhill-Road/ODBL_license.txt`
13. `/FORESEE/ODBL_license.txt`

**Total: 28 archivos** (19+3+4+2 de datos + 5 metadata + 4 licencias) —
más que el ~26 estimado porque conté las 2 geometrías de Valencia por
separado. Ninguna transferencia disparada todavía.

## 10. Screening ComCat — los 4, cerrado

| Array | Ventana | Resultado |
|---|---|---|
| FOSSA | 2017-09-06 ~15:54-16:14 UTC | Limpio (verificado en revisión anterior) |
| Valencia | 2020-09-01 ~13:21 UTC | Limpio — 0 eventos M≥2.0/300km todo el día |
| Stanford-2 | 2020-03-01 ~06:59 UTC | Limpio — 1 evento M2.2 a las 16:09 UTC (>9h de distancia) |
| FORESEE | 2019-04-04 ~19:48 UTC | Limpio — 0 eventos M≥2.0/300km todo el día |

**Ninguno de los 4 necesita `--exclude-s`** — las ventanas completas se
usan como ruido.

## 11. Compromiso — sin cambios

Los segmentos de la §9 se corren tal cual salen. Desviaciones
pre-declaradas: regla de parada por tamaño (~20% de exceso),
protocolo de piloto FOSSA, algoritmo de subsetting por estacionariedad
— todas por costo/homogeneidad, nunca por resultado.

## 12. Protocolo especial FOSSA — sin cambios, aprobado

1. Descargar los 19 archivos + chanmap.
2. Confirmar canal-count/spacing reales contra el chanmap.
3. Chequeo de estacionariedad.
4. Headroom de grabación int16 (fracción de muestras cerca de ±32767).
5. Piloto: 1 escalón (SNR=8, n=20), esquema de lectura lazy revisado (§1c).
6. Decisión post-piloto: completar 140 o decimar espacialmente.

## 13. Archivos de respaldo

- `sample_plan_fase1.json`: versión máquina-legible, mismo estado.

## 14. F1.5 — Resultados

Orden ejecutado: FORESEE → Stanford-2 → Valencia (livianos primero,
loaders ya probados en F1.4). Para cada uno: chequeo de estacionariedad
(§7) primero, curva completa solo si pasó limpio. Ningún archivo de
reserva entró a ninguna corrida — los 3 usaron exactamente el set
pre-registrado, `input_files_explicit_list=true` en los 3 JSON de
salida (lista literal, no glob de carpeta).

**Trabajo de infraestructura hecho para poder correr esto** (no estaba
armado en F1.4, que solo probó los loaders de forma aislada):
`gather_noise_sources` ganó dos parámetros nuevos, `loader` (callable
para inyectar `load_hdf5_generic`/`read_segy` en vez del `load_file`
por-extensión) y `channel_range` (1-indexado inclusive, igual que los
archivos de geometría reales, convertido a slice 0-indexado en un solo
lugar). `snr_curve.py` ganó `--format {auto,hdf5-generic,segy}`,
`--hdf5-key`, `--channel-start/--channel-end`, y `--files` (lista
explícita, para no arrastrar los archivos de reserva del glob de
`--dir`). El criterio de estacionariedad de F1.3 (diseñado, nunca
implementado) ahora es código real: `snr_curve.stationarity_check()`,
5 tests nuevos cubriendo el caso limpio, el subconjunto, el empate, y
la rama terminal. La derivada fase→strain-rate de Stanford
(`convert_stanford_sgy.py`) se extrajo a una función reusable
(`phase_to_strain_rate`) para que `snr_curve.py` la aplique sin
duplicar la lógica.

### FORESEE

**Estacionariedad**: limpio. max/min RMS = **1.06×** (muy por debajo del
umbral 3.0×), ambos archivos pre-registrados usados sin recorte.

**Curva**: threshold=4.0 (default), 140/140 trials válidos, monótona
dentro de IC Wilson 95%, runtime 312.7s.

| SNR | recall | IC95% Wilson | n |
|---|---|---|---|
| 1 | 5.0% | [0.9, 23.6] | 20 |
| 2 | 65.0% | [43.3, 81.9] | 20 |
| 3 | 95.0% | [76.4, 99.1] | 20 |
| 5 | 100.0% | [83.9, 100.0] | 20 |
| 8 | 100.0% | [83.9, 100.0] | 20 |
| 12 | 100.0% | [83.9, 100.0] | 20 |
| 20 | 100.0% | [83.9, 100.0] | 20 |

**SNR50 = 1.75.** JSON: `figures/snr_curve_foresee.json`. Figura:
`figures/fig6_recall_snr_foresee.png`.

### Stanford-2 (Sand Hill Road, canales 399-750)

**Estacionariedad**: limpio. max/min RMS = **1.37×**, los 4 archivos
pre-registrados usados sin recorte.

**Curva**: threshold=4.0 (default), 140/140 trials válidos, monótona
dentro de IC Wilson 95%, runtime 109.3s. Canales restringidos a
399-750 (352 canales, segmento recto confirmado por geometría GPS real
en F1.4) — aplicado ANTES de correr, como se pidió.

| SNR | recall | IC95% Wilson | n |
|---|---|---|---|
| 1 | 0.0% | [0.0, 16.1] | 20 |
| 2 | 65.0% | [43.3, 81.9] | 20 |
| 3 | 95.0% | [76.4, 99.1] | 20 |
| 5 | 100.0% | [83.9, 100.0] | 20 |
| 8 | 100.0% | [83.9, 100.0] | 20 |
| 12 | 100.0% | [83.9, 100.0] | 20 |
| 20 | 100.0% | [83.9, 100.0] | 20 |

**SNR50 = 1.77.** JSON: `figures/snr_curve_stanford2_sandhill.json`.
Figura: `figures/fig6_recall_snr_stanford2_sandhill.png`.

### Valencia (submarino, canales 510-2977)

**Corrección de geometría (F1.5, sobre lo pre-registrado en F1.3)**: al
cargar el archivo real de geometría submarina
(`DAS-1-geometry-Valencia-undersea.csv`), el canal de arranque real es
**510**, no el ~548 estimado en F1.3 por aritmética de
distancia/spacing — el CSV lista directamente el rango 510-2977 (2,468
canales), sin ambigüedad. El KMZ de la parte terrestre
(`DAS-1-geometry-Valencia-onland.kmz`) resultó ser solo una traza
geográfica (LineString, 9,189m — coincide exacto con el valor del
paper) sin canales numerados, así que no aporta el límite por sí solo;
el límite real sale enteramente del CSV submarino.

**Corrección de layout HDF5 (F1.4→F1.5)**: el dataset real NO es 2D
simple como FORESEE — es 3D, `(601 bloques, 250 muestras/bloque, 2977
canales)`, anidado 3 niveles bajo grupos
(`fa1-20050027/Source1/Zone1/SR_Valencia`). `load_hdf5_generic` se
extendió (F1.5) para detectar y reordenar este layout, validando que la
dimensión del medio coincida con `fs` antes de reordenar (nunca a
ciegas). dtype real: **float32** (estándar, confirmado al cargar — no
hizo falta el test de grilla de precisión que si aplicó a FORESEE por
su float16).

**Dato real de calidad de canal, no un error de pipeline**: `sanitize()`
encontró 150,250 muestras no-finitas (NaN/Inf) por archivo — exactamente
un canal completo (150,250 = 601×250, el tamaño de un canal entero) — y
2 canales muertos (varianza ~0): índices 2466-2467 dentro del subrango
submarino, es decir **canales reales 2976-2977, la punta más lejana y
más profunda del cable** (~377-379m de profundidad, según la geometría
real). `sanitize()` ya maneja esto correctamente (zeroea y reporta, no
rompe nada aguas abajo) — queda documentado como propiedad real del
sitio (posible degradación de acople en el extremo del cable), no
como un bug.

**Estacionariedad**: limpio. max/min RMS = **1.04×**, los 3 archivos
pre-registrados usados sin recorte.

**Curva**: threshold=4.0 (default), 140/140 trials válidos, runtime
1894.2s (2,468 canales, la corrida más cara de las 3 — comparable a
monterey_bay/arcata en escala de canales).

| SNR | recall | IC95% Wilson | n |
|---|---|---|---|
| 1 | 15.0% | [5.2, 36.0] | 20 |
| 2 | 45.0% | [25.8, 65.8] | 20 |
| 3 | 60.0% | [38.7, 78.1] | 20 |
| 5 | 60.0% | [38.7, 78.1] | 20 |
| 8 | 90.0% | [69.9, 97.2] | 20 |
| 12 | 85.0% | [64.0, 94.8] | 20 |
| 20 | 70.0% | [48.1, 85.5] | 20 |

**SNR50 = 2.33.** JSON: `figures/snr_curve_valencia_submarine.json`.
Figura: `figures/fig6_recall_snr_valencia_submarine.png`.

**Hallazgo real, no ocultado por pasar el chequeo de monotonía**: el
script confirma "monótona dentro de IC Wilson 95%" (las 3 escalones
altos se solapan en sus intervalos: [69.9,97.2] / [64.0,94.8] /
[48.1,85.5]), pero el PUNTO estimado cae dos veces seguidas en el
extremo alto: 90%→85%→70% (SNR=8→12→20) — y **nunca llega a 100%**, a
diferencia de los otros 6 arrays ya medidos, que sí llegan y se quedan
en 100% desde algún escalón en adelante. Con n=20/escalón esto es
compatible con ruido estadístico puro (las IC se solapan de sobra), pero
es la primera curva de la serie con esta forma — no se descarta que sea
una característica real del sitio (ambiente submarino, o el efecto de
los 2 canales muertos reduciendo la apertura efectiva). **No se diseña
ningún experimento para esto ahora** — mismo criterio que la
observación de ridgecrest_north en F1.1 — queda para F1.6 con más N.

### Spread de 7 arrays (antes de FOSSA)

| Array | SNR50 | Ambiente |
|---|---|---|
| monterey_bay | 1.6 | Submarino (SeaFOAM) |
| FORESEE | 1.75 | Urbano, campus universitario |
| Stanford-2 | 1.77 | Urbano, vía pública |
| Valencia | 2.33 | Submarino |
| ridgecrest_north | 2.5 | Desierto/rural |
| arcata | 5.9 | — |
| stanford1_campus | 7.73 | Urbano, campus universitario |

**Spread = 7.73/1.6 = 4.83× — IDÉNTICO al de 4 arrays.** Los 3 arrays
nuevos cayeron DENTRO del rango ya observado (1.6-7.73), no lo
ampliaron por ninguno de los dos extremos — ni el mínimo (monterey_bay)
ni el máximo (stanford1_campus) cambiaron. Puramente descriptivo, sin
intentar explicación causal acá (eso es trabajo de F1.6) — pero es la
primera confirmación real de que el spread observado con 4 arrays no
era un artefacto de muestra chica que se iba a disolver con más datos.
