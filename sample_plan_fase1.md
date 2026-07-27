# Sample plan pre-registrado — F1.3 (SNR50, extensión a más instalaciones)

**Fecha de registro:** revisión tras verificación del mecanismo de
calibración SNR, criterio de estacionariedad, corrección int16 y cierre
parcial de ComCat para FOSSA. Nada se descarga hasta que este documento
esté completo (Stanford-2 y FORESEE siguen con placeholders) y lo
apruebes.

## 0. Aviso sobre nombres no confiables — traducción de UI de Globus

El listado raíz que usé para una versión anterior de este documento
venía de una captura con la UI de Globus traducida al español — la
evidencia: mostraba "Explosión1" donde el `Camino` (path) real es
`/Data/Blast1/`, y otros nombres de display ("FOSA", "Datos",
"citación.txt", "DAS-Mes") que no coinciden con los nombres técnicos
reales. "FORESEE" → "prever" en esa misma traducción explica **"PREVER"**:
es FORESEE, no un dataset distinto. **Identidad confirmada por
mecanismo**, no por evidencia de archivo todavía.

**Consecuencia práctica**: no re-derivo nada de los nombres de display
del listado raíz anterior. Solo trato como confiables los `Camino`
(paths) literales que me pasaste directamente y los nombres técnicos de
archivo dentro de esos paths. Esto también pone en duda **`Licencia.txt`**
— marcado como pendiente de reconfirmación, no como dato firme.

## 0b. Verificación de mecanismo — RMS local vs. global (bloqueante, resuelto)

**Resultado: LOCAL.** Rastreado con cita de código, no supuesto:

1. `snr_curve.run_trial` → `selftest.inject_and_verify_sized(source["noise"], ...)`
   — recibe el pool COMPLETO de ruido de esa fuente (`source["noise"]`).
2. Dentro de `inject_and_verify_sized` (`selftest.py:126-128`):
   ```python
   rng = np.random.default_rng(seed)
   start = int(rng.integers(0, n_t - min_len_n))
   window = noise[:, start : start + min_len_n]
   ```
   Recorta una ventana LOCAL aleatoria de tamaño `min_len_n` del pool
   completo — todavía no calibra nada acá.
3. Esa `window` (no el pool completo) se pasa como `live_buffer` a
   `inject_and_verify` (`selftest.py:129-131`).
4. Dentro de `inject_and_verify` (`selftest.py:39,44`):
   ```python
   data = live_buffer.copy()   # == window, la ventana LOCAL
   ...
   amp = snr_to_amplitude(snr, data, wav)
   ```
   `snr_to_amplitude` (`synth.py:237,258`) calcula
   `amp = target_snr * noise_rms(noise_window) / wavelet_rms(wavelet)`,
   donde `noise_window` acá es `data` — **la ventana local del trial**,
   no el pool completo ni un RMS pooled/global del archivo.

**Consecuencia (rama LOCAL, como preveías)**: la deriva NO corrompe la
calibración por trial — cada trial es exactamente SNR=X respecto a SU
PROPIA ventana, por construcción, sin importar si el resto del pool está
más fuerte o más débil. El chequeo de estacionariedad de la §2 mide
**homogeneidad de régimen** (si la curva de 140 trials termina siendo una
mezcla de condiciones de ruido bien distintas dentro del mismo pool), no
la validez de ningún trial individual. El claim final se redacta como
**"SNR50 medido contra la ventana de ruido X del sitio"**, exactamente
igual que los 4 arrays ya medidos (ninguno de ellos reclama tampoco
invariancia día/noche o estacional — usan la ventana que tenían
disponible).

## 1. FOSSA — corrección real (error de reconocimiento previo, no del draft de specs)

```
/FOSSA/Data/westSac_<YYMMDDHHMMSS>.tdms
```

- **Formato real**: NI TDMS (no HDF5 — el patrón anterior era una
  contaminación de mi propia estimación especulativa de F1.2b, corregida).
- **Duración real por archivo**: 60 segundos. **Tamaño real**: ~699 MB.
- **Fecha observada**: 2017-09-06 (al menos un archivo; no asumo que sea
  la única fecha disponible).

**Verificación aritmética**: 11,648 canales (Tabla 1, PubDAS) × 500 Hz ×
2 bytes (int16) × 60s = 698,880,000 bytes = **698.88 MB** — coincide con
"~699MB" casi exacto. Confirma canal-count, fs, y **dtype real: int16**
— primer candidato de este lote sin float32 nativo.

**Importante — el conteo de 11,648 sigue siendo una hipótesis por
aritmética inversa, no un dato leído de un manifiesto de canales real**
(ver §1c, chanmap).

### 1a. Loader TDMS — tarea de F1.4, no de este pre-registro

Loader nuevo (`npTDMS`) en la capa de IO, paralelo al de `.npz` (F1.1).
`fs`/`spacing` se leen del header TDMS y de
**`DASchanmap_westsac_2017.csv`** — nunca asumidos. Test unitario
análogo a `tests/test_snr_curve.py`. No implementado en este commit.

### 1b. Presupuesto FOSSA — archivos de 60s

Piso de ruido: **56.3s** (aperture=23,300m, Tabla 1 — supersede el
"57.6s" de un mensaje más viejo, que usaba un conteo de canales
redondeado ~12,000).

| K (archivos) | Duración total | Margen sobre el piso | Tamaño |
|---|---|---|---|
| 10 | 600s | 10.7× | 6.99 GB |
| 15 | 900s | 16.0× | 10.48 GB |
| **19 (confirmado)** | **1,140s** | **20.2×** | **13.28 GB** |

### 1c. Chanmap — entra a la lista de transferencia, resuelve el conteo real de canales

**`DASchanmap_westsac_2017.csv`** (raíz de FOSSA, 268KB) — agregado a la
lista de transferencias (§8). El conteo real de canales y el spacing
real salen de ahí, no de mi aritmética inversa. **Mi "11,648" queda como
hipótesis a confirmar** — si el chanmap da un número distinto (por
ejemplo, canales "buenos" vs. totales, como pasó con SCEDC/Ridgecrest:
1,250 totales / 1,150 buenos), el piso de 56.3s se recalcula con el
número real del chanmap, no con la hipótesis. Costo de transferencia:
despreciable (268KB).

### 1d. Esquema de lectura de ruido — decisión de diseño, mi recomendación

**El problema real**: con archivos de 60s y un piso de 56.3s, un solo
archivo deja ~3.7s de margen para el offset aleatorio de cada trial.
Concatenar K=19 archivos en RAM (13.3GB) no es viable ni escala.

- **Opción A — concatenar todo en RAM**: simple, pero 7-14GB simultáneos
  para K=10-19 — inviable, como ya señalaste.
- **Opción B (recomendada) — lectura on-demand por trial, RAM acotada**:
  por cada uno de los 140 trials, sortear offset sobre la línea de
  tiempo virtual completa (K×60s), leer solo esa ventana vía la API de
  lectura parcial de `npTDMS` (puede cruzar el borde entre 2 archivos
  consecutivos — a verificar que los timestamps son estrictamente
  contiguos antes de tratarlos como stream único). RAM por trial acotada
  a ~0.66GB, variedad de muestreo sobre TODA la ventana descargada.
  Riesgo: depende de que la lectura parcial de `npTDMS` sea eficiente en
  la práctica — no verificado todavía, tarea de F1.4.
- **B-lite (contingencia)**: concatenar en RAM solo 3-4 archivos por vez
  (~2.1-2.8GB), rotar en chunks — salvavidas si B no rinde bien.

Recomendación: B, con B-lite como respaldo. Decisión final: tuya.

### 1e. int16 — dos verificaciones distintas, no una

**(a) Path de inyección/medición — nunca debe castear a int16 post-inyección.**

Contrato ya establecido y documentado en el código (no algo que haya que
inventar): `replay.load_file` declara explícitamente en su docstring
(`replay.py:39-40`) — *"Devuelve (data[canales, muestras] **float32**,
fs, dx, attrs)"* — y lo cumple hoy mismo para `.npz`
(`replay.py:63`: `data = np.asarray(z[key], dtype=np.float32)`),
sin importar el dtype de origen. **El loader TDMS de F1.4 tiene que
seguir el mismo contrato: upcast a float32 INMEDIATAMENTE al cargar,
antes de que `gather_noise_sources`/`inject_and_verify_sized` toquen el
array.**

Por qué importa concretamente: `add_plane_wave` (`synth.py:71`) hace
`data[i, s:s+w] += a * wavelet` in-place. Si `data` siguiera siendo
int16 en ese punto (loader roto, sin el upcast), NumPy trunca el
resultado de vuelta a entero — a SNR=1 (el escalón más frágil, amplitud
inyectada más chica), el riesgo real es que la señal completa se
redondee a cero, silenciosamente. **Corrupción de pipeline, no del
dato** — evitable por diseño si el loader nuevo respeta el contrato ya
establecido, pero necesita testearse explícitamente porque es la primera
vez que el proyecto toca una fuente int16.

**Test a escribir en F1.4** (diseño, no implementado en este commit):
1. `test_tdms_loader_upcasts_to_float32` — análogo a
   `test_npz_loader_shape_dtype_fs_dx`: dtype devuelto es float32 pese a
   que la fuente es int16.
2. `test_low_snr_injection_survives_int16_source_quantization` —
   fixture sintética int16 (`_write_tdms`, análoga a `_write_npz`) con
   RMS controlado, inyección a SNR=1 (peor caso), verifica que
   `data_después - data_antes` es no-nulo y reproduce el wavelet
   escalado por el `amp` esperado dentro de una tolerancia numérica
   chica — no cero, no truncado a pasos enteros. Puede escribirse y
   correrse HOY con datos sintéticos (sin esperar la descarga real),
   igual que ya se hace con `.npz` — queda anotado para F1.4, no
   implementado en este commit porque el loader mismo tampoco lo está.

**(b) Headroom de GRABACIÓN — propiedad del dato, no del pipeline.**

Distinto del punto (a): una vez descargados los K=19 archivos reales,
medir la fracción de muestras con `abs(valor) > 0.95 * 32767` (cerca de
saturar el rango de int16). Si el interrogador original ya clipeaba
transientes fuertes (tráfico pesado muy cerca del cable, por ejemplo),
eso es una propiedad del SITIO/instrumento, se documenta como tal en la
nota técnica de FOSSA — no se puede medir sin los archivos reales,
queda como paso post-descarga (parte de la secuencia de la §7, no
antes).

## 2. Criterio de estacionariedad — pre-registrado, uniforme para los 4 arrays nuevos

**Métrica**: serie temporal de `noise_rms()` (ya en banda de análisis —
`gather_noise_sources` aplica `bandpass` antes, `snr_curve.py:118-119`)
por archivo/fuente en el pool, más spread por cuartiles de canal como
descriptivo (no gatilla acción, solo diagnóstico).

### Caracterización empírica de los 4 arrays ya medidos (hecha acá, solo lectura, sin re-correr nada)

Corrida sobre los mismos archivos reales ya usados en cada medición
(`gather_noise_sources` + `synth.noise_rms`, cero cambios de código,
Bloque A intacto):

| Array | n fuentes | CV (std/mean) | max/min RMS |
|---|---|---|---|
| ridgecrest_north | 40 | 1.913 | 39.9× |
| arcata | 15 | 0.654 | 10.1× |
| monterey_bay | 15 | 1.982 | 60.5× |

**Caveat honesto sobre esta comparación**: estos 3 valores miden
variabilidad ENTRE SESIONES muy separadas en el tiempo (arcata: 15
archivos entre 2022-12-26 y 2024-12-21, casi 2 años de separación) — no
variabilidad DENTRO de una sesión continua de minutos, que es el caso de
FOSSA (19 archivos consecutivos de 1 minuto, ~20 minutos totales). No es
una comparación directamente equivalente. Lo que SÍ aporta: confirma que
el proyecto ya acepta, y produce curvas SNR50 consideradas válidas
(1.6/2.5/5.9, publicadas), sobre pools con variabilidad ENORME (65%-198%
de CV) — evidencia de que "alta variabilidad" por sí sola no es
descalificante bajo el mecanismo LOCAL verificado en §0b. Esto es
contexto de respaldo, no un ancla numérica directa para el umbral de
FOSSA (que es sobre una escala de tiempo muy distinta).

### Umbral de acción — propuesto, con justificación

**Propongo: max/min de RMS por archivo > 3.0× dentro del pool de
FOSSA.** Razonamiento (atado al mecanismo, no heredado de tu 20%):

1. El mecanismo LOCAL (§0b) hace que la acción de este chequeo sea de
   bajo riesgo — en el peor caso, recortar a un subconjunto contiguo más
   chico (nunca por debajo de K_min=10, ver terminal) o etiquetar el
   pool completo. No hay downside de "medir sobre datos corruptos".
   Eso justifica un umbral relativamente sensible (no hace falta ser
   conservador para evitar un daño que no existe).
2. Al mismo tiempo, 3.0× es sustancialmente MÁS CHICO que el piso más
   bajo observado entre-sesiones en los 3 arrays ya aceptados (10.1× en
   arcata) — un salto de régimen DENTRO de una sola sesión continua de
   ~20 minutos que igualara siquiera el caso entre-sesiones MÁS SUAVE ya
   tolerado sería, razonablemente, sorprendente y digno de nota — no
   estoy inventando un número arbitrario, estoy poniendo la barra
   deliberadamente por debajo de lo que ya sabemos que el proyecto
   tolera sin problema, precisamente porque la escala temporal es
   distinta y no debería necesitar tanta tolerancia.
3. No tengo una derivación estadística de primeros principios más fina
   que esta (necesitaría caracterizar el tiempo de correlación del
   ruido ambiental real de FOSSA, que no tengo sin los datos) — lo digo
   explícito en vez de aparentar más precisión de la que tengo.

**Algoritmo si dispara** (max/min > 3.0×): tomar el subconjunto contiguo
más largo cuyo propio max/min interno sea ≤3.0×, escaneando todos los
subconjuntos contiguos posibles del pool de 19; en caso de empate en
longitud, el que empieza más temprano cronológicamente (mismo criterio
anti-cherry-picking del resto del documento — nunca el de menor CV entre
empates, eso sería elegir por resultado).

**Piso**: K_min=10 archivos (600s) para FOSSA — coincide con la
alternativa económica ya presentada en §1b.

**Rama terminal**: si ni el subconjunto contiguo más largo llega a
K_min=10, se mide sobre el pool COMPLETO (los 19) y el SNR50 de FOSSA
entra a la serie cross-array con un **flag de deriva explícito** en el
JSON de salida y en la nota técnica — nunca en silencio, nunca se
declara "inmedible".

**Esto queda pre-registrado como criterio uniforme para los 4 arrays
nuevos** (FOSSA, Valencia, Stanford-2, FORESEE) — mismo umbral (3.0×),
mismo algoritmo, mismo K_min proporcional (~10× el piso de ruido propio
de cada array, redondeado a archivos enteros — para Valencia ya da
K_min≤3, no afecta el K=3 ya planeado).

## 3. Presupuesto total

| Array | Base | Tamaño declarado |
|---|---|---|
| FOSSA (K=19) | 19 archivos reales de 60s/699MB | **13.28 GB** |
| Valencia | 3 archivos reales de 10min/1.78GB | **5.34 GB** |
| Stanford-2 | Estimado por tasa — pendiente de captura real | ~0.25 GB (provisorio) |
| FORESEE | Estimado por tasa — pendiente de captura real | ~0.42 GB (provisorio) |
| Chanmap FOSSA | `DASchanmap_westsac_2017.csv` | 268 KB, despreciable |
| Archivos de licencia/citación | Nombres a reconfirmar (§0) | < 1 MB, despreciable |
| **Total (K=19)** | | **~19.3 GB** |
| **Total (K=10, alternativa económica)** | | **~13.0 GB** |

Sigue abierto hasta las capturas reales de Stanford-2/FORESEE.

## 4. Selección final — estado actual

| Array | Estado |
|---|---|
| FOSSA | ✅ Specs, presupuesto, mecanismo de calibración, umbral de estacionariedad, y verificación int16 resueltos. Loader TDMS pendiente (F1.4). ComCat de la ventana propuesta: limpio (§6). |
| Valencia | ✅ Sin cambios — specs y presupuesto reales. |
| Stanford-2 | ⏳ Specs físicas conocidas, archivo real pendiente de captura sin traducción. |
| FORESEE | ⏳ Identidad confirmada, specs de archivo pendientes de captura sin traducción. |
| Fairbanks, LaFarge-Conco, PoroTomo DASH | ❌ Excluidos (sin cambios). |
| Stanford-3 | ❌ No entra (sin cambios). |

## 5. Parámetros comunes — sin cambios

| Parámetro | Valor | Fuente |
|---|---|---|
| `SNR_STEPS` | `(1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0)` | `snr_curve.py:55` |
| `N_PER_STEP` | 20 (140 por array) | `snr_curve.py:56` |
| `V_APP_RANGE_MPS` | `(2000.0, 6500.0)`, signo aleatorio | `snr_curve.py:57` |
| Wavelet | Ricker | `snr_curve.py:52` |
| Umbral Tier0 | 4.0 (default, homogéneo) | — |
| Seed | Hardcoded: `np.random.default_rng(1_000 + step_idx)` | `snr_curve.py:187` |

## 6. Regla de selección + ComCat — FOSSA instanciado, resto pendiente

**FOSSA — ventana concreta**: 2017-09-06, ~15:54–16:14 UTC (~19-20
archivos consecutivos `westSac_*.tdms`).

**Screening ComCat, hecho ahora, no diferido**: consulté directamente la
API de USGS ComCat (`earthquake.usgs.gov/fdsnws/event`) para el día
completo 2017-09-06, radio de 300km alrededor de Sacramento/Woodland CA,
M≥2.0 (más conservador que el M≥3 pre-registrado). **Resultado: limpio.**
5 eventos ese día en todo el radio (M2.07-M2.6), el más cercano en
tiempo a las 15:54-16:14 UTC está a más de 3 horas de distancia (11:48
UTC y 18:27 UTC). **Ningún evento cae dentro de la ventana ni cerca —
la ventana completa se usa como ruido, sin `--exclude-s`.**

- **Valencia**: primeros 3 archivos `SR_Valencia_*_10mins.h5`
  consecutivos — screening ComCat pendiente hasta fijar el timestamp
  exacto.
- **Stanford-2 / FORESEE**: `<PENDIENTE DE CAPTURA SIN TRADUCCIÓN>`.

## 7. Secuencia pre-registrada de FOSSA

En este orden, no intercambiable:

1. Descargar K=19 archivos (`westSac_*.tdms`, ~13.28 GB) +
   `DASchanmap_westsac_2017.csv` (268 KB).
2. Confirmar canal-count/spacing reales contra el chanmap (§1c) —
   recalcular el piso de ruido si difiere de la hipótesis de 11,648.
3. Chequeo de estacionariedad (§2): serie de `noise_rms()` por archivo,
   max/min vs. umbral 3.0×, aplicar algoritmo de subconjunto si dispara.
4. Headroom de grabación int16 (§1e-b): fracción de muestras cerca de
   ±32767, documentar como propiedad del sitio.
5. Piloto: UN escalón (SNR=8, n=20 trials), esquema de lectura §1d
   (Opción B), medir `runtime_s` real.
6. Decisión post-piloto (no tomada acá): completar los 140 o decimar
   espacialmente, documentado si se aplica.

## 8. Lista de transferencias — actualizada

1. `/FOSSA/Data/westSac_<PRIMEROS 19 TIMESTAMPS, 2017-09-06 ~15:54-16:14 UTC>.tdms` (~13.28 GB)
2. `/FOSSA/DASchanmap_westsac_2017.csv` (268 KB) — **nuevo en esta revisión**
3. `/Valencia/Data/<PRIMER SR_Valencia_*_UTC DISPONIBLE>/..._10mins.h5` × 3 (~5.34 GB)
4. `/Stanford-2/...` — pendiente de captura sin traducción
5. `/FORESEE/...` — pendiente de captura sin traducción
6. Archivo(s) de licencia/citación — nombres a reconfirmar (§0)

**No se dispara ninguna transferencia todavía.**

## 9. Compromiso — sin cambios

Los segmentos que resulten de la regla de la §6 se corren tal cual
salen. Desviaciones pre-declaradas: regla de parada por tamaño (~20%),
protocolo de piloto FOSSA (§7), y el algoritmo de subsetting por
estacionariedad (§2) — todas por costo/homogeneidad de régimen, nunca
por resultado del pipeline.

## 10. Archivos de respaldo

- `sample_plan_fase1.json`: versión máquina-legible, mismo estado.
