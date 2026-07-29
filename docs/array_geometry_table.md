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

**Fuente de "Ambiente"**: `sample_plan_fase1.md` §"Spread de 7 arrays". `—`
significa no sourceado todavía (arcata) — no se completa acá con un valor
inventado.

**Fuente de "IC" (columna final)**: no existe un IC directo sobre el SNR50
interpolado (es una interpolación lineal entre dos escalones medidos, no un
estimador de proporción por sí mismo). Se reporta el IC Wilson 95% de los
DOS escalones que bracketan el cruce de recall=50% (`interpolate_snr50`),
n=20 cada uno — son los números reales que sostienen la interpolación, no
un IC sintetizado.

| Array | Ambiente | n_ch | spacing (dx) | apertura | fs | SNR50 | IC95% (escalones que bracketan 50%) |
|---|---|---|---|---|---|---|---|
| monterey_bay | Submarino (SeaFOAM) | 2,845 | 5.2 m | 14,788.8 m (14.79 km) | 199.995 Hz | 1.60 | [0.9,23.6]@SNR1 / [58.4,91.9]@SNR2 |
| Stanford-2 (stanford2_sandhill) | Urbano, vía pública | 352 | 8.16 m | 2,864.16 m (2.86 km) | 250.0 Hz | 1.77 | [0.0,16.1]@SNR1 / [43.3,81.9]@SNR2 |
| FORESEE (foresee) | Urbano, campus universitario | 2,137 | 2.0 m | 4,272.0 m (4.27 km) | 125.0 Hz | 1.75 | [0.9,23.6]@SNR1 / [43.3,81.9]@SNR2 |
| Valencia (valencia_submarine) | Submarino | 2,468 | 16.8 m | 41,445.6 m (41.45 km) | 250.0 Hz | 2.33 | [25.8,65.8]@SNR2 / [38.7,78.1]@SNR3 |
| ridgecrest_north | Desierto/rural | 1,150 | 8.0 m | 9,192.0 m (9.19 km) | 100.0 Hz | 2.50 | [5.2,36.0]@SNR2 / [64.0,94.8]@SNR3 |
| arcata | — (no sourceado) | 3,020 | 5.104762077331543 m | 15,411.28 m (15.41 km) | 100.0 Hz | 5.9 | [18.1,56.7]@SNR5 / [64.0,94.8]@SNR8 |
| stanford1_campus | Urbano, campus universitario | 626 | 8.16 m | 5,100.0 m (5.10 km) | 100.0 Hz | 7.73 | [0.0,16.1]@SNR5 / [34.2,74.2]@SNR8 |
| FOSSA | Urbano — fibra oscura de telecom | 11,648 (nominal, PubDAS) | 2.0 m | 23,300 m (23.3 km) | 500.0 Hz | **pendiente** | curva completa aún no corrida — ver `docs/observaciones.md` 2026-07-28/29 (I/O 12×, extrapolación 7h27); solo `figures/snr_curve_fossa_smoketest.json` existe hoy, no en `array_profiles` |

**Nota sobre orden**: filas 1-7 ordenadas por SNR50 ascendente (menos sensible
arriba de la escala de sensibilidad, es decir monterey_bay necesita el SNR
sintético más chico para alcanzar 50% de recall — ver
`docs/writeup.md`/`writeup.es.md` §4 sobre por qué SNR50 no es comparable
entre arrays en unidades físicas absolutas, solo dentro de la escala propia
de cada instalación). FOSSA al final porque no tiene SNR50 medido todavía,
no por su geometría.

**Nota de reconciliación arcata**: `array_profiles.dx` trae
`5.104762077331543` (float con ruido de precisión de punto flotante, no
redondeado a 5.1) — reportado tal cual sale de la base, no limpiado, para
que esta tabla sea trazable byte-a-byte contra la fuente.
