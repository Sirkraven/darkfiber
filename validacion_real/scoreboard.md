# Scoreboard — validación contra verdad-terreno (P2)

## Matriz final (todos los arreglos, IC 95% Wilson)

| resultado | n/N | tasa | IC 95% Wilson |
|---|---|---|---|
| HIT | 0/16 | 0.0% | [0.0%, 19.4%] |
| HONEST_UNKNOWN | 8/16 | 50.0% | [28.0%, 72.0%] |
| HONEST_REGIONAL | 2/16 | 12.5% | [3.5%, 36.0%] |
| MISS_SUPPRESSED | 0/16 | 0.0% | [0.0%, 19.4%] |
| MISS_BELOW_FLOOR | 6/16 | 37.5% | [18.5%, 61.4%] |
| CORRECT_REJECTION (archivos sin catálogo) | 27/27 | 100.0% | [87.5%, 100.0%] |
| FALSE_ALARM (archivos sin catálogo) | 0/27 | 0.0% | [0.0%, 12.5%] |

> Muestra chica (N=16 eventos reales); los intervalos son anchos a propósito, no se maquillan. MISS_SUPPRESSED = Tier0 disparó un candidato causal y se perdió/suprimió (modo de falla malo); MISS_BELOW_FLOOR = ningún candidato Tier0 cayó en la ventana causal [origen, origen+margen] (ver A6) — consistente con estar bajo el piso de detección, no un bug de clasificación.

## arcata (15 eventos)

> **Calibración Tier0 (A8)**: A8: barrido threshold [4.0, 4.5, 5.0, 5.5, 6.0, 7.0, 8.0, 9.0, 10.0, 12.0] evaluado contra 15 archivo(s) crudo(s) + chequeo sintético -- ningún candidato mejora un outcome sin romper otro (real o sintético). Default retenido, sin evidencia de descalibración.

| outcome | n |
|---|---|
| CORRECT_REJECTION | 12 |
| HONEST_UNKNOWN | 3 |

| archivo | magnitud | veredicto | outcome | dt_detect_s | snr_observado |
|---|---|---|---|---|---|
| 20221226T024457Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230103T081020Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230111T054015Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230215T142504Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230228T001004Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230313T062204Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230404T231428Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230421T090028Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230915T171719Z.h5 | 1.48 | COHERENTE_DESCONOCIDO | HONEST_UNKNOWN | — | — |
| 20240612T063748Z.h5 | 1.92 | COHERENTE_DESCONOCIDO | HONEST_UNKNOWN | — | — |
| 20240628T132048Z.h5 | 1.85 | COHERENTE_DESCONOCIDO | HONEST_UNKNOWN | — | — |
| 20241205T205720Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20241206T053920Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20241209T083020Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20241221T151620Z.h5 | — | None | CORRECT_REJECTION | — | — |

## monterey_bay (15 eventos)

> **Calibración Tier0 (A8)**: A8: barrido threshold [4.0, 4.5, 5.0, 5.5, 6.0, 7.0] evaluado contra 15 archivo(s) crudo(s) + chequeo sintético -- ningún candidato mejora un outcome sin romper otro (real o sintético). Default retenido, sin evidencia de descalibración.

| outcome | n |
|---|---|
| CORRECT_REJECTION | 15 |

| archivo | magnitud | veredicto | outcome | dt_detect_s | snr_observado |
|---|---|---|---|---|---|
| 20220802T054858Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20220809T005458Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20220828T140758Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230407T074209Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230505T133353Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20230714T024558Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20231028T013810Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20231029T061810Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20231109T130910Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20231110T105410Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20231116T130210Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20231124T104510Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20240123T123210Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20240913T221528Z.h5 | — | None | CORRECT_REJECTION | — | — |
| 20241206T180928Z.h5 | — | None | CORRECT_REJECTION | — | — |

## ridgecrest_north (12 eventos)

> **Calibración Tier0 (A8)**: threshold=8.0 (propuesta aplicada vía `calibrate.py --apply`, default global 4.0; ver tabla `proposals`).

| outcome | n |
|---|---|
| HONEST_REGIONAL | 1 |
| HONEST_UNKNOWN | 5 |
| MISS_BELOW_FLOOR | 6 |

| archivo | magnitud | veredicto | outcome | dt_detect_s | snr_observado |
|---|---|---|---|---|---|
| ci37280444.h5 | 2.67 | None | MISS_BELOW_FLOOR | — | — |
| ci37283964.h5 | 2.09 | None | MISS_BELOW_FLOOR | — | — |
| ci38595194.h5 | 1.55 | None | MISS_BELOW_FLOOR | — | — |
| ci38609250.h5 | 1.73 | COHERENTE_DESCONOCIDO | HONEST_UNKNOWN | 34.1 | 0.98 |
| ci39268999.h5 | 2.18 | None | MISS_BELOW_FLOOR | — | — |
| ci39274823.h5 | 1.53 | None | MISS_BELOW_FLOOR | — | — |
| ci39276375.h5 | 1.86 | COHERENTE_DESCONOCIDO | HONEST_UNKNOWN | 21.1 | 4.75 |
| ci39280383.h5 | 1.78 | COHERENTE_DESCONOCIDO | HONEST_UNKNOWN | 14.1 | 1.09 |
| ci39287087.h5 | 1.63 | COHERENTE_DESCONOCIDO | HONEST_UNKNOWN | 58.3 | 1.04 |
| ci39491040.h5 | 1.67 | None | MISS_BELOW_FLOOR | — | — |
| ci39493944.h5 | 5.80 | POSIBLE_REGIONAL_EMERGENTE | HONEST_REGIONAL | 17.1 | 33.24 |
| ci39495248.h5 | 1.61 | COHERENTE_DESCONOCIDO | HONEST_UNKNOWN | 40.4 | 2.68 |

## stanford1_campus (1 eventos)

| outcome | n |
|---|---|
| HONEST_REGIONAL | 1 |

| archivo | magnitud | veredicto | outcome | dt_detect_s | snr_observado |
|---|---|---|---|---|---|
| eastfoothills_20171010_005137.npz | 4.10 | POSIBLE_REGIONAL_EMERGENTE | HONEST_REGIONAL | 9.3 | 15.93 |
