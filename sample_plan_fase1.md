# Sample plan pre-registrado — F1.3 (SNR50, extensión a más instalaciones)

**Fecha de registro:** revisión tras corrección real de FOSSA + cierre de
identidad FORESEE/PREVER. Nada se descarga hasta que este documento esté
completo (Stanford-2 y FORESEE siguen con placeholders) y lo apruebes.

## 0. Aviso sobre nombres no confiables — traducción de UI de Globus

El listado raíz que usé para la versión anterior de este documento venía
de una captura con la UI de Globus traducida al español — la evidencia:
mostraba "Explosión1" donde el `Camino` (path) real es `/Data/Blast1/`,
y otros nombres de display ("FOSA", "Datos", "citación.txt", "DAS-Mes")
que no coinciden con los nombres técnicos reales. "FORESEE" → "prever"
en esa misma traducción explica **"PREVER"**: es FORESEE, no un dataset
distinto. **Identidad confirmada por mecanismo**, no por evidencia de
archivo todavía — las capturas sin traducción están en camino.

**Consecuencia práctica**: no re-derivo nada de los nombres de display
del listado raíz anterior. Solo trato como confiables los `Camino`
(paths) literales que me pasaste directamente (`/FOSSA/Data/...`,
`/Valencia/Data/...`, `/Stanford-3-ODH4/Data/...`) y los nombres técnicos
de archivo dentro de esos paths — no los nombres de carpeta de nivel
raíz que vi traducidos. Esto también pone en duda **`Licencia.txt`**,
que había citado en la revisión anterior como si fuera un nombre
literal — puede ser, igual que "citación.txt", un nombre traducido para
display. Marcado como pendiente de reconfirmación, no como dato firme.

## 1. FOSSA — corrección real (error de reconocimiento previo, no del draft de specs)

La estructura real es:

```
/FOSSA/Data/westSac_<YYMMDDHHMMSS>.tdms
```

- **Formato real**: NI TDMS (no HDF5 — el "`decimator2_*.h5`, 6.16GB/1h"
  de la revisión anterior era una contaminación de mi estimación F1.2b
  (que había especulado "TDMS, tabla imprime TDSM" pero después, sin
  evidencia real de Globus, terminé escribiendo un patrón HDF5 inventado
  por analogía con Valencia — error mío en esa instancia, no en el
  reconocimiento que me pasaste ahora).
- **Duración real por archivo**: **60 segundos** (no 1 hora).
- **Tamaño real por archivo**: ~699 MB.
- **Fecha observada**: 2017-09-06 (al menos un archivo con esa fecha;
  no asumo que sea la única fecha disponible).

**Verificación aritmética** (no solo aceptado de tu mensaje, calculado
acá): 11,648 canales (Tabla 1, PubDAS) × 500 Hz × 2 bytes (int16) × 60s
= 698,880,000 bytes = **698.88 MB** — coincide con tu "~699MB" casi
exacto. Esto confirma tres cosas al mismo tiempo: el conteo de canales
(11,648, ya sabido de Tabla 1), la tasa de muestreo (500Hz, ya sabida) y
**el dtype real: int16, no float32** — un dato nuevo que no teníamos.
Todos los demás arrays medidos hasta ahora (Stanford, arcata, etc.)
venían en float32 vía `.npz`/`.h5` — FOSSA es el primer candidato con
dtype entero, otra cosa a manejar en el loader nuevo.

### 1a. Loader TDMS — tarea de F1.4, no de este pre-registro

Se necesita un loader nuevo (librería `npTDMS`) en la capa de IO,
paralelo al que ya existe para `.npz` (F1.1) — mismo principio: `fs`/
`spacing` se leen del header TDMS y del archivo de mapeo de canales
(**`DASchanmap_westsac_2017.csv`**, confirmado que existe junto a los
datos), **nunca asumidos**. Test unitario análogo a
`tests/test_snr_curve.py`: shape/dtype/fs/spacing verificados contra el
comportamiento real del loader, no supuestos. No implementado en este
commit — queda anotado como bloqueante de F1.4 antes de poder correr
FOSSA de verdad.

### 1b. Presupuesto FOSSA — recalculado con archivos de 60s

Piso de ruido: **56.3s** (aperture=23,300m, Tabla 1 — este es el valor
correcto, vigente desde F1.2b; el "57.6s" que puede aparecer en mensajes
más viejos míos era una estimación previa con un conteo de canales menos
preciso (~12,000 redondeado) — superseded, no vigente).

| K (archivos) | Duración total | Margen sobre el piso | Tamaño |
|---|---|---|---|
| 10 | 600s | 10.7× | **6.99 GB** |
| 15 | 900s | 16.0× | 10.48 GB |
| **19 (recomendado)** | **1,140s** | **20.2×** | **13.28 GB** |

**Recomendación: K=19** (~13.3 GB) — mismo criterio de margen (~20×) que
ya usé para Valencia, por consistencia entre arrays del mismo
pre-registro. Si el presupuesto total ajusta apretado, K=10 (~7.0 GB,
10.7×) es la alternativa más barata — igual cubre el piso con margen
razonable, solo con menos variedad de muestreo temporal. Decisión tuya.

### 1c. Esquema de lectura de ruido — decisión de diseño, mi recomendación

**El problema real**: con archivos de 60s y un piso de 56.3s, un solo
archivo deja ~3.7s de margen para el offset aleatorio de cada trial —
muy poca variedad si cada uno de los 140 trials sortea dentro del MISMO
archivo de 60s repetidamente. Concatenar los K=19 archivos en RAM (13.3
GB) para tener un margen de sorteo real a lo largo de los 1,140s
completos **no es viable** — de acuerdo con vos, y además no escala si
más adelante se decide un K más grande.

**Dos opciones, recomiendo la B:**

- **Opción A — concatenar todo en RAM**: simple de implementar (mismo
  patrón que ya existe para múltiples `.h5`/`.npz` en
  `gather_noise_sources`), pero cuesta K×0.7GB simultáneos en RAM
  (7-14GB para K=10-19) — inviable como vos ya señalaste, y no escala.
- **Opción B (recomendada) — lectura on-demand por trial, RAM acotada**:
  para cada uno de los 140 trials, sortear un offset sobre la línea de
  tiempo VIRTUAL completa (K×60s = hasta 1,140s), identificar en qué
  archivo(s) cae esa ventana (puede cruzar el borde entre dos archivos
  consecutivos de 60s), y leer SOLO esos bytes vía la API de lectura
  parcial de `npTDMS` (`channel.read_data(offset, length)` o
  equivalente — a verificar en la implementación real de F1.4, no
  asumido que funcione performante sin probarlo). RAM por trial acotada
  al tamaño de la ventana leída (~57s ≈ 0.66GB en el peor caso, bien
  dentro del límite de 2-3GB que pediste), con variedad de muestreo real
  a lo largo de TODA la ventana descargada, no solo dentro de un archivo
  de 60s.
  - **Qué gana**: máxima variedad de muestreo (offset uniforme sobre
    1,140s reales, no sobre 60s), RAM acotada y predecible por trial,
    no penaliza por elegir un K más grande.
  - **Qué pierde/riesgo**: más complejidad de implementación (manejo de
    borde entre archivos, verificar que los archivos consecutivos son
    real y estrictamente contiguos en tiempo — a confirmar con los
    timestamps del nombre de archivo antes de tratarlos como un stream
    único, no asumido) y depende de que la lectura parcial de `npTDMS`
    realmente sea eficiente — si no lo es en la práctica, esto se
    degrada a tener que leer el archivo completo de todos modos (mismo
    costo que la opción A pero un archivo a la vez, no K).
- **Alternativa B-lite (contingencia si la lectura parcial de npTDMS no
  rinde bien)**: concatenar en RAM solo un subconjunto chico y contiguo
  por vez (ej. 3-4 archivos ≈ 180-240s ≈ 2.1-2.8GB), rotar por varios de
  esos "chunks" a lo largo de los 140 trials, descartando cada chunk de
  RAM antes de cargar el siguiente. Menos variedad que B pura (offsets
  acotados a chunks discretos, no a todo el rango) pero sin depender de
  que la lectura parcial de npTDMS funcione bien — sirve como plan B si
  B falla en la implementación real.

Mi recomendación es B, con B-lite como salvavidas si en F1.4 la lectura
parcial de npTDMS no se comporta como se espera. Decisión final: tuya.

## 2. Presupuesto total — recalculado

| Array | Base | Tamaño declarado |
|---|---|---|
| FOSSA (K=19, recomendado) | 19 archivos reales de 60s/699MB | **13.28 GB** |
| Valencia | 3 archivos reales de 10min/1.78GB (sin cambios) | **5.34 GB** |
| Stanford-2 | Estimado por tasa — **pendiente de captura real** | ~0.25 GB (provisorio) |
| FORESEE | Estimado por tasa (Tabla 1, Vol/T.span) — **pendiente de captura real, identidad confirmada pero specs de archivo no** | ~0.42 GB (provisorio) |
| Archivos de licencia/citación | Nombres a reconfirmar (ver §0) | < 1 MB, despreciable |
| **Total (con K=19 para FOSSA)** | | **~19.3 GB** |
| **Total (con K=10, alternativa económica)** | | **~13.0 GB** |

Ambos escenarios caen dentro de tu estimación ("15-22GB") y muy por
debajo del techo de 40GB. **No declaro un número final único todavía**
— faltan las capturas reales de Stanford-2 y FORESEE (los dos
provisorios de la tabla sí son estimaciones por tasa, no por archivo
real, a diferencia de FOSSA/Valencia que ya son exactos). Cuando
lleguen, este total se cierra con precisión.

## 3. Selección final — estado actual

| Array | Estado |
|---|---|
| FOSSA | ✅ Specs y presupuesto reales, corregidos. Loader TDMS pendiente (F1.4). |
| Valencia | ✅ Sin cambios respecto a la revisión anterior — specs y presupuesto reales. |
| Stanford-2 | ⏳ Specs físicas conocidas (canales 400-750, apertura 2,856m), archivo real **pendiente de captura sin traducción**. |
| FORESEE | ⏳ Identidad confirmada (PREVER = FORESEE, por mecanismo de traducción). Specs de archivo real **pendientes de captura sin traducción**. |
| Fairbanks, LaFarge-Conco, PoroTomo DASH | ❌ Excluidos — sin cambios, ver commit anterior para las 3 razones específicas. |
| Stanford-3 | ❌ No entra — mismo sitio físico que `stanford1_campus`, ya medido (sin cambios). |

## 4. Parámetros comunes — sin cambios

| Parámetro | Valor | Fuente |
|---|---|---|
| `SNR_STEPS` | `(1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0)` | `snr_curve.py:55` |
| `N_PER_STEP` | 20 (140 inyecciones totales por array) | `snr_curve.py:56` |
| `V_APP_RANGE_MPS` | `(2000.0, 6500.0)`, signo aleatorio | `snr_curve.py:57` |
| Wavelet | Ricker (`synth.ricker`) | `snr_curve.py:52` |
| Umbral Tier0 | 4.0 (default, homogéneo) | ninguno tuvo calibración A7/A8 |
| Seed | Hardcoded: `np.random.default_rng(1_000 + step_idx)` | `snr_curve.py:187` |

## 5. Regla de selección — sin cambios de fondo, instanciada solo con capturas confiables

La regla (primer segmento cronológico disponible, sin mirar contenido,
screening contra USGS ComCat antes de correr) se mantiene igual. Se
instancia con nombres literales **solo** a partir de capturas sin
traducción — los placeholders de abajo quedan explícitos hasta entonces:

- **FOSSA**: primeros 19 archivos `westSac_<YYMMDDHHMMSS>.tdms`
  cronológicamente consecutivos bajo `/FOSSA/Data/` — verificar antes de
  tratarlos como stream continuo que los timestamps consecutivos
  difieren en exactamente 60s (sin huecos). Si 2017-09-06 es el único
  día disponible, la elección es automática (todo ese día); si hay más
  fechas, se aplica la regla (la primera cronológicamente).
- **Valencia**: primeros 3 archivos `SR_Valencia_*_10mins.h5`
  consecutivos bajo `/Valencia/Data/` — sin cambios.
- **Stanford-2**: `<PENDIENTE DE CAPTURA SIN TRADUCCIÓN>` — patrón de
  archivo, granularidad y tamaño real desconocidos todavía.
- **FORESEE**: `<PENDIENTE DE CAPTURA SIN TRADUCCIÓN>` — mismo estado
  que Stanford-2. Identidad confirmada, specs de archivo no.
- **Screening ComCat**: sin cambios — antes de correr, verificar la
  fecha/hora exacta del segmento elegido contra USGS ComCat (M≥3, radio
  razonable de cada ubicación); si hay evento, `--exclude-s` con margen
  5.0s; si no, ventana completa como ruido.

## 6. Protocolo especial FOSSA — sin cambios de fondo, aprobado

1. Descargar los K=19 archivos declarados (~13.3 GB) una sola vez.
2. Correr UN escalón (SNR=8, n=20 trials) usando el esquema de lectura
   de la §1c (Opción B).
3. Medir `runtime_s` real.
4. Extrapolar ×7 para estimar el total de 140.
5. Sanity check ya hecho contra los 4 arrays medidos: rango plausible
   2-5.7h para el total.
6. Decisión post-piloto (no tomada acá): completar los 140 o decimar
   espacialmente (documentado si se aplica).

## 7. Lista de transferencias — actualizada

1. `/FOSSA/Data/westSac_<PRIMEROS 19 TIMESTAMPS CONSECUTIVOS>.tdms` (~13.28 GB) — patrón y formato confirmados, timestamps exactos a completar por vos en Globus
2. `/Valencia/Data/<PRIMER SR_Valencia_*_UTC DISPONIBLE>/..._10mins.h5` × 3 archivos consecutivos (~5.34 GB) — sin cambios
3. `/Stanford-2/...` — **pendiente de captura sin traducción** antes de poder armar la ruta
4. `/FORESEE/...` (identidad confirmada, ruta real bajo ese nombre técnico a confirmar con captura sin traducción)
5. Archivo(s) de licencia/citación — nombres a reconfirmar (ver §0), no asumidos "Licencia.txt"/"ODBL_license.txt" hasta la próxima captura

**No se dispara ninguna transferencia todavía** — este documento sigue
incompleto (2 de 4 arrays con specs de archivo reales) hasta las
próximas capturas.

## 8. Compromiso — sin cambios

Los segmentos que resulten de la regla de la §5 se corren tal cual
salen. Las únicas desviaciones pre-declaradas son la regla de parada por
tamaño (~20% de exceso sobre lo declarado) y el protocolo de piloto de
FOSSA (§6), ambas por costo, nunca por resultado.

## 9. Archivos de respaldo

- `sample_plan_fase1.json`: versión máquina-legible, mismo estado
  (FOSSA/Valencia cerrados, Stanford-2/FORESEE con placeholders).
