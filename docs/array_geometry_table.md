# Tabla consolidada de geometría y SNR50 por arreglo

*Generada por pedido explícito (F1.6): los campos de geometría/ambiente/SNR50
estaban repartidos entre `sample_plan_fase1.md` (SNR50 + ambiente),
`docs/writeup.md`/`writeup.es.md` (geometría de 3 arrays), `docs/writeup_data.md`
(geometría con reconciliación de errores) y `docs/snr50_extension_fase1.md`
(census con specs de candidatos PubDAS). Esa dispersión ya causó al menos un
error de razonamiento documentado (ver `docs/observaciones.md`, hipótesis
MARS/monterey_bay refutada en F1.2b). Esta tabla no reemplaza esos documentos
(cada uno tiene contexto/narrativa que esta tabla no captura) — es la
referencia rápida de un solo lugar. Generada leyendo directo
`array_profiles` de `D:\darkfiber\ledger\quakeflow_ledger.db` + los JSON de
curva en `figures/snr_curve_*.json` (columna IC) el 2026-07-29 — no
recalculada ni re-derivada de memoria.

**Fuente de "Ambiente"**: `sample_plan_fase1.md` §"Spread de 7 arrays"
para los 7 arreglos medidos antes de FOSSA. Para FOSSA (la 8va fila,
agregada en este documento después de que su corrida completa cerró):
`docs/snr50_extension_fase1.md`, tabla de candidatos F1.2, fila #3
("Urbano — fibra oscura de telecom", verbatim). `—` significa no
sourceado todavía (arcata) — no se completa acá con un valor inventado.

**Fuente de "IC" (columna final)**: no existe un IC directo sobre el SNR50
interpolado (es una interpolación lineal entre dos escalones medidos, no un
estimador de proporción por sí mismo). Se reporta el IC Wilson 95% de los
DOS escalones que bracketan el cruce de recall=50% (`interpolate_snr50`),
n=20 cada uno — son los números reales que sostienen la interpolación, no
un IC sintetizado.

| Array | Ambiente | n_ch | spacing (dx) | apertura | fs | SNR50 | IC95% (escalones que bracketan 50%) |
|---|---|---|---|---|---|---|---|
| monterey_bay | Submarino (SeaFOAM) | 2,845 | 5.2 m | 14,788.8 m (14.79 km) | 199.995 Hz | 1.60 | [0.9,23.6]@SNR1 / [58.4,91.9]@SNR2 |
| FORESEE (foresee) | Urbano, campus universitario | 2,137 | 2.0 m | 4,272.0 m (4.27 km) | 125.0 Hz | 1.75 | [0.9,23.6]@SNR1 / [43.3,81.9]@SNR2 |
| Stanford-2 (stanford2_sandhill) | Urbano, vía pública | 352 | 8.16 m | 2,864.16 m (2.86 km) | 250.0 Hz | 1.77 | [0.0,16.1]@SNR1 / [43.3,81.9]@SNR2 |
| Valencia (valencia_submarine) | Submarino | 2,468 | 16.8 m | 41,445.6 m (41.45 km) | 250.0 Hz | 2.33 | [25.8,65.8]@SNR2 / [38.7,78.1]@SNR3 |
| ridgecrest_north | Desierto/rural | 1,150 | 8.0 m | 9,192.0 m (9.19 km) | 100.0 Hz | 2.50 | [5.2,36.0]@SNR2 / [64.0,94.8]@SNR3 |
| FOSSA | Urbano — fibra oscura de telecom | 11,648 | 2.0 m | 23,294.0 m (23.29 km) | 500.0 Hz | 4.50 | [0.9,23.6]@SNR3 / [43.3,81.9]@SNR5 |
| arcata | — (no sourceado) | 3,020 | 5.104762077331543 m | 15,411.28 m (15.41 km) | 100.0 Hz | 5.9 | [18.1,56.7]@SNR5 / [64.0,94.8]@SNR8 |
| stanford1_campus | Urbano, campus universitario | 626 | 8.16 m | 5,100.0 m (5.10 km) | 100.0 Hz | 7.73 | [0.0,16.1]@SNR5 / [34.2,74.2]@SNR8 |

**Nota sobre orden**: filas ordenadas por SNR50 ascendente (menos sensible
arriba de la escala de sensibilidad, es decir monterey_bay necesita el SNR
sintético más chico para alcanzar 50% de recall — ver
`docs/writeup.md`/`writeup.es.md` §4 sobre por qué SNR50 no es comparable
entre arrays en unidades físicas absolutas, solo dentro de la escala propia
de cada instalación).

**FOSSA — corrida completa cerrada 2026-07-29** (curva completa aprobada
con Docker cerrado, ver hilo F1.6; commit `9a07ecc`, `pipeline_hash`
inyectado post-hoc en `figures/snr_curve_fossa.json` — ver nota de
provenance ahí mismo). Runtime real: 27,480.4s (7h38, cerca de la
extrapolación de 7h27). `array_profiles` actualizado por la propia
corrida (`n_ch`/`aperture_m` reales del archivo, no el nominal de
PubDAS — coinciden exacto: apertura = (n_ch−1)×dx = 11,647×2.0m =
23,294.0m, `ArrayGeometry.aperture_m` en `contracts.py` — NO
n_ch×dx, que da 23,296.0m; apertura es la distancia punta-a-punta del
arreglo, no `n_ch` veces el espaciado). **Dato
crudo, no investigado todavía**: la curva de recall de FOSSA NO es
monótona en los escalones altos — 90%@SNR8 → 80%@SNR12 → 60%@SNR20 (IC
Wilson se solapan, pasa el chequeo de monotonía-dentro-de-IC igual que
Valencia) — mismo patrón cualitativo que la anomalía de Valencia
(entrada 2026-07-27 de `docs/observaciones.md`), en el segundo arreglo
de mayor apertura de la serie (23.3km, después de Valencia).
**Corrección (ver `docs/observaciones.md`, fe de erratas 2026-07-29/30):
NO es el mismo mecanismo W/T que Valencia** — verificado con aritmética,
no asumido: para FOSSA, `v* = 0.30·L/W ≈ 1,997 m/s` cae DEBAJO de todo
el rango inyectado (2,000-6,500 m/s), así que el techo geométrico de
`coincidence_fraction` va de 30.05% a 97.7% dentro de ese rango —
insuficiente para explicar un 40% de no-hits en SNR=20 (solo ~15% de los
sorteos caen bajo un techo de 40%). Para Valencia, `v*≈3,553 m/s` SÍ caía
DENTRO del rango, lo que hacía el mecanismo geométrico suficiente por sí
solo. La no-monotonicidad de FOSSA queda sin explicación mecánica
todavía — ver pendiente F1.6 (b) en `docs/observaciones.md`
(hipótesis candidata: autosupresión STA/LTA, no verificada).

**Nota de reconciliación arcata**: `array_profiles.dx` trae
`5.104762077331543` (float con ruido de precisión de punto flotante, no
redondeado a 5.1) — reportado tal cual sale de la base, no limpiado, para
que esta tabla sea trazable byte-a-byte contra la fuente.

**Pendiente (fase de paper, no ahora)**: sourcear el ambiente de arcata
desde la documentación de GorDAS/`quakeflow_das` antes de que esta tabla
alimente cualquier claim tipo "ningún proxy geométrico/de ambiente
predice SNR50" — ese claim exige los 8 ambientes sourceados, no 7 de 8
con uno inferido o inventado. No se completa acá con un valor sin fuente
primaria (mismo criterio que Brno en `docs/snr50_extension_fase1.md`
F1.2b).
