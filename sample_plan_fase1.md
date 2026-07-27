# Sample plan pre-registrado — F1.3 (SNR50, extensión a más instalaciones)

**Fecha de registro:** consolidación final tras reconocimiento cruzado
(mi draft de specs + tu reconocimiento real de la estructura de Globus).
Este documento se commitea ANTES de disparar cualquier transferencia real
o correr `snr_curve.py` sobre ninguno de los arrays de abajo. Nada corre
hasta tu aprobación explícita del commit.

## 1. Criterios de inclusión/exclusión — las 3 exclusiones, cada una con su razón

De los 6 candidatos originalmente seleccionados, **3 quedan excluidos**,
cada uno por una razón distinta y específica — no es el mismo tipo de
problema en los tres casos:

| Candidato | Razón de exclusión | Tipo |
|---|---|---|
| **Fairbanks** | El subconjunto alojado en PubDAS es exclusivamente activo (barridos de un Surface Orbital Vibrator, varias veces por noche) — no ruido ambiente pasivo confirmado en volumen suficiente. Exclusión **metodológica**: el dato existe y es accesible, pero no sirve para lo que este protocolo necesita (ruido de fondo real para inyectar sismos sintéticos encima). | Metodológica |
| **LaFarge-Conco** | Confirmado en el reconocimiento real de Globus: `Data/` = `{Blast1, Blast2, ESS, HammerTap, MiniVibe}` — las 5 subcarpetas son fuente activa, sin una carpeta de ruido ambiente pasivo. Esto es más fuerte que la duda que tenía en el census v1/F1.2b (que asumía, por el texto del paper, que había "ruido de camiones y cintas transportadoras" utilizable) — la estructura real de archivos no ofrece ese ruido como producto separable y descargable. Exclusión **metodológica**, confirmada con evidencia directa de la fuente real, no solo del paper. | Metodológica |
| **PoroTomo DASH** | Geometría: 71 segmentos contiguos de ~100m cada uno (tres líneas paralelas en zigzag), sin ningún tramo recto comparable a los otros candidatos (1.1-50km vs. ~100m). Cualquier subsegmento utilizable mediría a una escala física 10-50× menor — la escala del arreglo pasaría a ser una variable de confusión mezclada con el ambiente, no una medición comparable de "SNR50 de una instalación". No hay un subsegmento razonable que resuelva esto. Exclusión **de diseño/comparabilidad**, no de acceso. | Diseño/comparabilidad |

**Selección final: 3 confirmados (FOSSA, Valencia, Stanford-2) + FORESEE
pendiente de una verificación más (ver §2).**

## 2. FORESEE — pendiente, no bloqueante para el resto

No apareció en el listado raíz de PubDAS que viste (`DAS-Mes-02.2023`,
`Fairbanks`, `PREVER`, `FOSA`, `LaFargeConco`, `Stanford-1/2/3`,
`Valencia`). Verifiqué "PREVER" contra todas las fuentes que tengo
(el paper primario de PubDAS, `DAS-RCN/awesome-das`, búsqueda general) —
**no encontré ningún dataset llamado "PREVER" en ningún lado**, ni
tampoco evidencia de que FORESEE haya sido renombrado así. Dos
posibilidades que no puedo distinguir sin acceso directo a Globus:

1. `PREVER` es en realidad `FORESEE` con un nombre de carpeta distinto al
   que aparece en el paper (2023) — los datasets se pudieron reorganizar
   desde entonces.
2. `PREVER` es un dataset genuinamente distinto, no documentado en el
   paper de 2023 (el propio paper dice "hay planes de agregar nuevos
   datasets").

Dato a favor de seguir buscando: el paper primario dice explícitamente
que FORESEE es **el dataset más grande de todo PubDAS** (29,338 GB) — si
sigue alojado ahí, sería raro que pasara inadvertido al scrollear la
raíz. La carta de datos original de Zhu et al. 2021 menciona un canal de
distribución separado, "Penn State Data Commons", como alternativa a
PubDAS — es posible que haya migrado ahí y ya no esté en el Globus de
PubDAS.

**Pedido concreto, cuando puedas**: abrí `PREVER` y fijate si los
nombres de archivo tienen fechas entre abril-2019 y marzo-2020 (el rango
alojado según el paper) o si el formato es HDF5 — eso lo confirma o
descarta en segundos. Si no es eso, o si FORESEE no aparece en ningún
lado de la colección, la selección queda en 3 y se documenta así, sin
bloquear el resto de este pre-registro.

## 3. Stanford-2 vs. Stanford-3 — no son intercambiables, la pregunta tenía un supuesto incorrecto

Releí el texto primario (Spica et al. 2023, pie de Fig. 6, la fuente más
directa que tengo — no pude leer el README/CSV real de Globus yo mismo,
sin acceso): **"Stanford 1 and 3 recorded the same fiber loop on main
campus but with different IUs. Stanford 2 was recorded around Palo
Alto."**

Esto resuelve la pregunta con un giro: el duplicado NO es
Stanford-2-vs-Stanford-3 — es **Stanford-3-vs-Stanford-1**, y
Stanford-1 (`stanford1_campus`) **ya está medido** (F1.1, SNR50=7.73).
Stanford-3 es un experimento de 6-9 días con un segundo interrogador
(ODH-4) sobre el MISMO loop de fibra que Stanford-1 — agregarlo sería
remedir el mismo sitio físico, no una instalación nueva.

Stanford-2 (Sand Hill Road/Palo Alto) es un sitio físicamente distinto
— confirmado, no inferido por nombre. **Recomendación: Stanford-2 entra,
Stanford-3 NO entra** (ni como candidato nuevo — es el mismo sitio que
`stanford1_campus`, ya cubierto).

## 4. Parámetros comunes — sin cambios, ya verificados contra el código

| Parámetro | Valor | Fuente |
|---|---|---|
| `SNR_STEPS` | `(1.0, 2.0, 3.0, 5.0, 8.0, 12.0, 20.0)` | `snr_curve.py:55` |
| `N_PER_STEP` | 20 (140 inyecciones totales por array) | `snr_curve.py:56` |
| `V_APP_RANGE_MPS` | `(2000.0, 6500.0)`, signo aleatorio | `snr_curve.py:57` |
| Wavelet | Ricker (`synth.ricker`) | `snr_curve.py:52` |
| Umbral Tier0 | **4.0** (default, homogéneo en los 3) | ninguno tuvo calibración A7/A8 |
| Seed | Hardcoded, no configurable: `np.random.default_rng(1_000 + step_idx)`, idéntico en cualquier array/corrida | `snr_curve.py:187` |

## 5. Selección final — estructura real de Globus + regla de selección instanciada

**Restricción real, no resuelta del todo**: no tengo acceso a Globus yo
mismo (requiere tu cuenta). Lo que sigue combina la estructura real que
vos relevaste (rutas, patrones de nombre, tamaños/granularidad exactos)
con la regla de selección ya pre-registrada (primer segmento
cronológico, sin mirar contenido, screening contra USGS ComCat antes de
correr). Donde la regla apunta a "el primer archivo disponible" pero no
tengo el valor literal de esa fecha/timestamp (porque no vi el listado
completo), lo marco explícito — no lo invento.

### FOSSA

- **Patrón real**: `/FOSSA/Data/<YYYYMMDD>/decimator2_<fecha>_<hora>.00.00_UTC.h5`
- **Granularidad real**: 1 archivo = 1 hora = **6.16 GB**
- **Piso de ruido**: 56.3s (aperture=23,300m, sin cambios de F1.2b/borrador anterior)
- **Archivos necesarios**: 1 hora (3,600s) cubre ~64× el piso — de sobra,
  mejor que el margen de 20× que había propuesto. **1 solo archivo.**
- **Selección**: la PRIMERA carpeta `<YYYYMMDD>` cronológicamente
  disponible bajo `/FOSSA/Data/`, el primer `.h5` dentro de ella —
  `<PRIMER YYYYMMDD DISPONIBLE>/decimator2_<PRIMER YYYYMMDD>_<PRIMERA HORA>.00.00_UTC.h5`.
  **No tengo el valor literal** (no vi el listado completo de carpetas) —
  se completa con el primer valor real al triggerear la transferencia,
  aplicando la regla tal cual (orden cronológico ascendente, sin elegir a mano).
- **Screening**: antes de correr, verificar la fecha/hora exacta de esa
  hora contra USGS ComCat (radio razonable de Sacramento/Woodland, CA,
  M≥3) — si hay evento, `--exclude-s` con margen 5.0s; si no, archivo
  completo como ruido.
- **Tamaño declarado: 6.16 GB**

### Valencia (canales submarinos, aprobado)

- **Patrón real**: `/Valencia/Data/SR_Valencia_<ts>_UTC/SR_Valencia_..._10mins.h5`
- **Granularidad real**: 1 archivo = 10 min = **1.78 GB** (array completo,
  2,977 canales — el recorte a canales submarinos [~548-2977] se aplica
  después, en el análisis, no en la descarga; Globus transfiere archivos
  enteros)
- **Piso de ruido (submarino, ~548-2977, aperture=40,811m)**: 88.4s
- **Archivos necesarios**: ceil(1,768s / 600s) = **3 archivos
  consecutivos** = 1,800s (20.4× el piso)
- **Selección**: los PRIMEROS 3 archivos `SR_Valencia_*_10mins.h5`
  cronológicamente consecutivos bajo `/Valencia/Data/`. **No tengo el
  valor literal del primer timestamp** — mismo criterio que FOSSA, se
  completa al triggerear.
- **Screening**: USGS ComCat, radio del cable Valencia-Palma de
  Mallorca, M≥3, antes de correr.
- **Nota de implementación (F1.4, no bloqueante acá)**: restringir el
  análisis a canales submarinos requiere slicing por rango de canal
  después de cargar el archivo — `gather_noise_sources`/`replay.load_file`
  no tienen hoy un parámetro de rango de canales. No es un cambio hecho
  en este pre-registro, queda anotado para cuando se implemente la
  corrida real.
- **Tamaño declarado: 3 × 1.78 GB = 5.34 GB**

### Stanford-2 (canales 400-750, aprobado)

- **Patrón real**: **no confirmado** — no me diste el patrón de carpeta/archivo
  de `/Stanford-2/` como sí hiciste con FOSSA/Valencia/Stanford-3. Uso el
  mismo interrogador (ODH-3) que Stanford-1, cuyo archivo ya usado en
  F1.1 confirma convención de 5 minutos por SEG-Y (`validacion_real/NOTES.md`:
  "3 archivos SEG-Y de 5 min cada uno") — **extrapolación razonable, no
  confirmada independientemente para Stanford-2**.
- **Piso de ruido (canales 400-750, aperture=2,856m)**: 18.8s
- **Estimación por tasa** (Vol/T.span de Tabla 1, no por archivo real):
  ventana de 376s (20×) × ~0.67 MB/s (350/1250 canales de la tasa total)
  ≈ **0.25 GB** — placeholder hasta confirmar la granularidad real.
- **Pedido concreto**: cuando puedas, mismo relevamiento que hiciste para
  los otros 3 (patrón de carpeta, tamaño/duración por archivo) — no
  bloqueante, es el array más barato del lote incluso si mi estimación
  está errada por 2-3×.
- **Tamaño declarado (estimado, a confirmar): ~0.25 GB**

### Archivos de licencia (a transferir junto con los datos)

- `/Licencia.txt` (raíz de PubDAS, 373B) — probablemente aplica en
  general; cierra (o no) el gap de licencia de Valencia. Se verifica
  leyéndolo después de la transferencia, no se asume el contenido.
- `/Stanford-2/ODBL_license.txt` — licencia específica de Stanford-2
  (ODBL — Open Database License, a confirmar leyendo el archivo real,
  nombre sugiere ODBL pero no asumo el contenido exacto sin leerlo).
- Si al entrar a `/Valencia/` aparece un archivo de licencia propio
  (no solo el de la raíz), agregalo también — no lo teníamos en el
  relevamiento que me pasaste.

## 6. Presupuesto total — recalculado sobre archivos reales

| Array | Base | Tamaño declarado |
|---|---|---|
| FOSSA | 1 archivo real (6.16 GB, 1h) | **6.16 GB** |
| Valencia | 3 archivos reales (1.78 GB × 3, 30 min) | **5.34 GB** |
| Stanford-2 | Estimado por tasa, granularidad real no confirmada | **~0.25 GB** |
| Archivos de licencia | 2-3 archivos, texto plano | **< 1 MB, despreciable** |
| **Total** | | **~11.75 GB** (techo: 40 GB — margen de ~28 GB) |

Coincide con tu propia estimación ("10-15GB"). Los dos archivos reales
(FOSSA, Valencia) ya no son estimaciones por tasa — son tamaños de
archivo Globus reales, mucho más precisos que la aproximación Vol/T.span
del borrador anterior (que había dado 21.2GB para FOSSA y 7.67GB para
Valencia — ambas eran sobreestimaciones porque no tenían en cuenta la
granularidad real de archivo).

**Regla de parada sin cambios**: si el tamaño real excede lo declarado
acá por más de ~20%, parar y avisar antes de seguir.

## 7. Protocolo especial FOSSA — sin cambios, aprobado

1. Descargar el único archivo declarado arriba (6.16 GB) una sola vez —
   sirve tanto para el piloto como (si se aprueba) para la corrida
   completa de 140.
2. Correr UN escalón (SNR=8, n=20 trials) — elegido por ejercitar el
   camino completo del pipeline, no el rechazo temprano de escalones
   bajos.
3. Medir `runtime_s` real.
4. Extrapolar ×7 para estimar el total de 140.
5. Sanity check contra los 4 arrays ya medidos: rango plausible 2-5.7h
   para el total (ver borrador anterior para el detalle del cálculo).
6. Decisión post-piloto (no tomada acá): completar los 140 o decimar
   espacialmente (documentado explícitamente si se aplica).

## 8. Lista de transferencias — para disparar en Globus

Acción concreta con la info que tengo; los 2 archivos marcados
`<PRIMER ... DISPONIBLE>` necesitan que apliques la regla vos mismo
(orden cronológico ascendente, primero de la lista) porque no vi el
listado completo:

1. `/FOSSA/Data/<PRIMER YYYYMMDD DISPONIBLE>/decimator2_<esa fecha>_<esa hora>.00.00_UTC.h5` (~6.16 GB)
2. `/Valencia/Data/<PRIMER SR_Valencia_*_UTC DISPONIBLE>/..._10mins.h5` **× 3 archivos consecutivos** (~5.34 GB total)
3. `/Stanford-2/...` — patrón a confirmar antes de armar la ruta exacta (~0.25 GB estimado)
4. `/Licencia.txt` (373 B)
5. `/Stanford-2/ODBL_license.txt`

Una vez que dispares 1-2 (y 3, cuando confirmes el patrón), pasame los
nombres literales resultantes para completar este documento con la
provenance exacta (URL, checksum si Globus lo da, fecha de descarga) —
eso cierra el pre-registro del todo. Nada de esto se corrió ni se bajó
todavía de mi lado.

## 9. Compromiso — sin cambios

Los segmentos que resulten de la regla de la §5 se corren tal cual salen
— no se re-elige el archivo si el resultado no gusta, no se descarta un
array por un mal resultado. Las únicas desviaciones pre-declaradas son
la regla de parada por tamaño (§6) y el protocolo de piloto de FOSSA
(§7), ambas por costo, nunca por resultado.

## 10. Archivos de respaldo

- `sample_plan_fase1.json`: versión máquina-legible.
