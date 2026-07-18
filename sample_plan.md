# Sample plan pre-registrado — A2/A3 (PLAN v5.2)

**Fecha de registro:** 2026-07-15, ANTES de correr `run_on_quakeflow.py` sobre
ningún archivo de arcata o monterey_bay. Este documento fija qué eventos se
van a validar y cómo se eligieron, comprometido por escrito antes de ver un
solo resultado — así el scoreboard de A2/A3 no puede quedar sesgado por
"buscar hasta encontrar un caso lindo" (ver "Deuda consciente — sesgo de
selección" en el README: los 4 eventos reales de A0/P2 SÍ fueron elegidos a
mano buscando candidatos plausibles; A2/A3 corrige eso).

## Regla de juego

1. El universo de candidatos por arreglo es la lista COMPLETA de archivos
   `.h5` bajo `<arreglo>/data/` en `huggingface.co/datasets/AI4EPS/quakeflow_das`,
   tal como la devolvió `huggingface_hub.list_repo_files` el 2026-07-15
   (snapshot completo en `sample_plan_universe.json`, 751/2470/33 archivos
   para ridgecrest_north/arcata/monterey_bay respectivamente).
2. La muestra es un sorteo uniforme sin reemplazo (`numpy.random.default_rng`,
   `seed=20260715`), sin mirar magnitud, fecha, ni ningún atributo del
   archivo antes de elegirlo. El sorteo completo, reproducible, está en
   `sample_plan_draw.json`.
3. Los 2 archivos de ridgecrest_north ya usados en A0/P2
   (`ci37280444.h5` M2.67, `ci39493944.h5` M5.8, documentados en
   `validacion_real/NOTES.md`) fueron elegidos A MANO — se excluyen del
   universo de sorteo para no contaminar la muestra nueva con una elección
   ya hecha con otro criterio.
4. Compromiso: los eventos de este documento se corren TAL CUAL salgan por
   `run_on_quakeflow.py`, se registran en el ledger y en el scoreboard sin
   excepción — incluso si el resultado es un MISS, un archivo sin verdad-
   terreno embebida, o un archivo corrupto/vacío. No se re-sortea, no se
   sustituye, no se descarta nada por el resultado. Un archivo que falle
   por razones técnicas (I/O, esquema inesperado) se documenta como tal,
   no se reemplaza silenciosamente por otro sorteo.
5. Arcata en particular: `validacion_real/NOTES.md` ya advierte que
   "algunos archivos (sobre todo en Arcata) carecen de attrs completos".
   Si un archivo sorteado no trae `magnitude`/`event_time`, igual se corre
   — `build_ground_truth()` devuelve `None` y `process_file()` ya maneja
   ese caso (outcome `FALSE_ALARM`/`CORRECT_REJECTION` según corresponda,
   sin verdad-terreno). Se cuenta y reporta cuántos de los 15 sorteados
   caen en ese caso, como dato honesto sobre la cobertura real del dataset,
   no como motivo para volver a sortear.

## Ridgecrest North — ampliación de ruido para A1 (ya descargados y corridos)

Los mismos 10 archivos sorteados abajo se usaron para ampliar el pool de
ruido real de `snr_curve.py` (de 2 a 12 archivos, de 220s a 1,320s de ruido
utilizable) — no es un sorteo aparte, es el mismo sorteo reusado para dos
propósitos (ruido de fondo en A1, candidatos a verdad-terreno en A3), sin
elegir a mano cuáles "sirven mejor" para cada uso.

| # | Archivo | Estado |
|---|---|---|
| 1 | `ci37280444.h5` | ya usado (A0/P2, elegido a mano — M2.67) |
| 2 | `ci39493944.h5` | ya usado (A0/P2, elegido a mano — M5.8) |
| 3 | `ci37283964.h5` | sorteado, descargado |
| 4 | `ci38595194.h5` | sorteado, descargado |
| 5 | `ci38609250.h5` | sorteado, descargado |
| 6 | `ci39268999.h5` | sorteado, descargado |
| 7 | `ci39274823.h5` | sorteado, descargado |
| 8 | `ci39276375.h5` | sorteado, descargado |
| 9 | `ci39280383.h5` | sorteado, descargado |
| 10 | `ci39287087.h5` | sorteado, descargado |
| 11 | `ci39491040.h5` | sorteado, descargado |
| 12 | `ci39495248.h5` | sorteado, descargado |

## Arcata — pre-registrado para A2, NO descargado todavía

Universo: 2,470 archivos (`arcata/data/*.h5`, timestamps, no IDs de evento
USGS/SCEDC — a diferencia de ridgecrest, la cobertura de verdad-terreno
embebida es una incógnita hasta correr `--inspect` sobre estos 15).

| # | Archivo |
|---|---|
| 1 | `20221226T024457Z.h5` |
| 2 | `20230103T081020Z.h5` |
| 3 | `20230111T054015Z.h5` |
| 4 | `20230215T142504Z.h5` |
| 5 | `20230228T001004Z.h5` |
| 6 | `20230313T062204Z.h5` |
| 7 | `20230404T231428Z.h5` |
| 8 | `20230421T090028Z.h5` |
| 9 | `20230915T171719Z.h5` |
| 10 | `20240612T063748Z.h5` |
| 11 | `20240628T132048Z.h5` |
| 12 | `20241205T205720Z.h5` |
| 13 | `20241206T053920Z.h5` |
| 14 | `20241209T083020Z.h5` |
| 15 | `20241221T151620Z.h5` |

## Monterey Bay — pre-registrado para A2, NO descargado todavía

Universo: 33 archivos totales (`monterey_bay/data/*.h5`) — la muestra de 15
cubre el 45% del universo completo, la fracción más alta de los tres
arreglos por lo chico que es el catálogo disponible.

| # | Archivo |
|---|---|
| 1 | `20220802T054858Z.h5` |
| 2 | `20220809T005458Z.h5` |
| 3 | `20220828T140758Z.h5` |
| 4 | `20230407T074209Z.h5` |
| 5 | `20230505T133353Z.h5` |
| 6 | `20230714T024558Z.h5` |
| 7 | `20231028T013810Z.h5` |
| 8 | `20231029T061810Z.h5` |
| 9 | `20231109T130910Z.h5` |
| 10 | `20231110T105410Z.h5` |
| 11 | `20231116T130210Z.h5` |
| 12 | `20231124T104510Z.h5` |
| 13 | `20240123T123210Z.h5` |
| 14 | `20240913T221528Z.h5` |
| 15 | `20241206T180928Z.h5` |

## Archivos de respaldo (auditoría/reproducibilidad)

- `sample_plan_universe.json`: snapshot completo del universo de candidatos
  por arreglo (751/2470/33 archivos), tal como lo devolvió la API el
  2026-07-15.
- `sample_plan_draw.json`: el sorteo mismo (seed, listas), en formato
  máquina-legible — esta tabla es su versión para lectura humana.

## Próximo paso (A2, no arrancado todavía)

Descargar los 15+15 archivos de arcata/monterey_bay de las tablas de
arriba y correr `run_on_quakeflow.py --dir <carpeta> --array-id <arreglo>`
sobre cada uno, exactamente como salgan.
