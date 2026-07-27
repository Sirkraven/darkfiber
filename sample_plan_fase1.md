# Sample plan pre-registrado — F1.3 (SNR50, extensión a más instalaciones)

**Fecha de registro:** instanciación final con capturas reales sin
traducción de los 4 arrays. Nada se descarga hasta que apruebes este
commit y dispares las transferencias en Globus (endpoint
`alejandro-darkfiber`).

## 0. Estado

Los 4 arrays (FOSSA, Valencia, Stanford-2, FORESEE) tienen ahora
estructura real confirmada — nombres de archivo literales (primero de
cada secuencia), formato, tamaño por archivo. **Estos archivos SON el
primer segmento cronológico — no hay cherry-pick, se instancia la regla
ya pre-registrada, no se elige a mano.**

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

### 1c. Esquema de lectura — REVISADO por la evidencia de huecos

**La posible existencia de huecos entre archivos (§1) cambia la
recomendación de la revisión anterior.** Antes proponía leer ventanas
que podían cruzar el borde entre 2 archivos consecutivos, tratándolos
como un stream virtual continuo — eso asume contigüidad estricta, que
la evidencia ahora pone en duda. Cruzar un borde real (con hueco) crearía
un salto discontinuo dentro de la ventana de un trial — un artefacto
que podría confundir al STA/LTA o corromper la coherencia, no por SNR
insuficiente sino por una construcción inválida de la ventana.

**Recomendación revisada, más simple**: **un archivo completo por
trial, elegido al azar entre los K=19, cargado bajo demanda (lazy)**.
Cada trial sortea CUÁL de los 19 archivos usar, carga SOLO ESE archivo
(~0.7GB, se libera después), y saca su ventana local de adentro (mismo
margen de jitter de un solo archivo, ~3.7s, que ya tenía cada archivo
individualmente). La variedad de muestreo entre los 140 trials viene de
CUÁL archivo se sortea (19 opciones, ~7.4 trials/archivo en promedio),
no de cruzar bordes. Esto:
- Evita por completo la complejidad de lectura parcial cruzando bordes
  de `npTDMS` (ya no hace falta verificar su rendimiento para eso).
- Mantiene la RAM acotada a 1 archivo (~0.7GB) por trial, igual que la
  propuesta anterior, pero con una implementación más simple: una
  variante "lazy" de `gather_noise_sources` que guarda RUTAS de archivo
  en la lista de fuentes en vez de arrays ya cargados, y difiere el
  `load_file` real al momento de `inject_and_verify_sized`, descartando
  el array después. La versión actual de `gather_noise_sources` carga
  TODO en RAM de una — con K=19 eso sí sería el problema original
  (13.3GB simultáneos), confirmando que hace falta este cambio, no es
  opcional.
- No depende de ninguna verificación de contigüidad estricta entre
  archivos — directamente no la necesita, cada trial usa un solo
  archivo.

Esto reemplaza la Opción B/B-lite de la revisión anterior — es más
simple que ambas y no tiene el riesgo de rendimiento de `npTDMS` que
tenían. Confirmá si estás de acuerdo con este cambio de diseño.

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

### 3a. Loader — REUSA `convert_stanford_sgy.py`/`read_segy()` tal cual, sin cambios

Verificación aritmética del archivo real: 75.30 MB, descontando
overhead SEG-Y (1250 canales × 240B header + 3,600B de headers de
archivo = 303,600 bytes), 1250 canales × 250Hz × 4 bytes (float32) da
**59.997s ≈ 60.00s exactos** — confirma 1250 canales (el array
completo, no el subrango 400-750, que se aplica después en análisis) y
250Hz, consistente con todo lo ya sabido de Tabla 1/FDSN.

`read_segy()` (`convert_stanford_sgy.py:47-67`) ya es genérico — lee
`sample_interval_us`/`samples_per_trace`/`data_format_code` del header
binario SEG-Y real, no asume nada, falla si el format code no es 5
(IEEE float32). **Mismo archivo, misma convención de nombre
(`cbt_processed_*`) que Stanford-1 (ya usado en F1.1)** — no hace falta
un loader nuevo. Único punto a confirmar en el primer archivo real (no
un test nuevo, una verificación puntual): si la derivada
fase-óptica→strain-rate que aplica `convert_stanford_sgy.py` por
default también hace falta acá (mismo tipo de interrogador ODH-3,
presumible pero no asumido a ciegas).

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

### 4a. Discrepancia de canales (F1.2b) — resuelta por aritmética del archivo real

F1.2b había dejado abierta una discrepancia: 2,137 canales geolocalizados
por tap test (texto de Zhu et al. 2021) vs. ~2,450 nominales (CL/CS de
Tabla 1). Con el tamaño real del archivo (321.15 MB, fs=125Hz alojado,
float32):

| Hipótesis n_ch | Duración implícita |
|---|---|
| 2,137 | **300.56s ≈ 5.009 min** |
| 2,450 | 262.16s ≈ 4.369 min |

2,137 da casi exactamente 5 minutos — coincide con el patrón de carpeta
mensual (`<YYYYMM>`) de forma mucho más limpia que 2,450. **Uso 2,137
como el valor correcto**, resolviendo la discrepancia con evidencia del
archivo real, no dejándola abierta. Piso de ruido recalculado:
aperture=(2,137-1)×2m=4,272m → **21.4s** (vs. 22.6s con la aperture de
Tabla 1/CL=4,900m — diferencia menor, no cambia ninguna decisión de
presupuesto).

### 4a-bis. Loader — comparte el HDF5 genérico nuevo con Valencia (§2a)

Mismo problema (`load_quakeflow_h5` no aplica sin riesgo), misma
solución: loader HDF5 genérico con fs/dx obligatorios. Para FORESEE:
`fs=125` (alojado), `dx=2.0`. Un solo loader nuevo sirve a los dos
arrays (Valencia y FORESEE) — no hace falta uno por array, es el mismo
contrato genérico con distintos valores de override.

### 4b. Test único para el loader HDF5 genérico (Valencia + FORESEE)

Análogo a `test_npz_loader_shape_dtype_fs_dx` + `test_npz_requires_explicit_fs_dx`:
`SystemExit` si fs/dx faltan (nunca asumidos), shape/dtype correctos
contra fixtures sintéticas para ambos casos (parametrizado, un solo
archivo de test, no dos loaders separados). No implementado en este
commit — tarea de F1.4, junto con el loader mismo.

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
