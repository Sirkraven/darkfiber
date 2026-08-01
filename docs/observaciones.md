# Observaciones — Bloque C y extensión SNR50 (F1)

Bitácora de comportamientos raros, capacidades inesperadas, hallazgos
verificados, correcciones a atribuciones propias, y pendientes
declarados que aparecen mientras se construye C (operable) o se corre la
extensión de SNR50 a más instalaciones (F1, ver
`docs/snr50_extension_fase1.md`). Empezó como insumo crudo de una sola
fase (no todo acá tiene que tener sentido todavía) pero hoy es también
el artefacto principal de traspaso de F1 — el registro donde vive el
razonamiento detrás de los números de `docs/array_geometry_table.md` y
`docs/writeup.md`/`writeup.es.md` §6/§7, no solo el resultado final.
Cada entrada: fecha, de qué fase salió, qué se observó, y (si aplica)
para qué podría servir. No confundir con el backlog de
`PLAN_CIERRE_Y_LANZAMIENTO.md` (ese es trabajo declarado y concreto;
esto es más crudo, todavía sin decidir si es trabajo — aunque algunas
entradas de F1, como las fe de erratas y los pendientes marcados
"declarado", ya cruzan esa línea).

## 2026-08-01 — QA-1.5 reescrito: la versión original nunca ejercitaba `inject_and_verify_sized`

**Erratum puntual post-gate** (el gate QA E2E cerró en `1090fc4`/
`78fa16d` sin segunda pasada; esto entra como la excepción ya declarada
en el cierre: "lo que aparezca durante la escritura del paper se trata
como errata puntual, no como reapertura del gate").

`test_noise_floor_constants_rederived_from_real_code`
(`tests/analytical/test_closed_form.py`, QA-1.5) decía re-derivar
`13.6+0.001833·aperture_m` "desde las piezas reales de
`inject_and_verify_sized`", pero en realidad nunca llamaba a esa
función: reconstruía su aritmética a mano dentro del propio test
(`Tier0Config().warmup_s + pipeline_margin_s(...) + ... `) usando piezas
reales, y comparaba ese cálculo de mano contra la fórmula documentada.
Un bug real en cómo `inject_and_verify_sized` ENSAMBLA esas piezas
(orden de operaciones, un término de más/menos) no se habría detectado
— el test se habría estado verificando contra sí mismo.

Reescrito para llamar la función real dos veces por combinación
`(n_ch, dx, fs_hz)`: ruido de `predicted_min_len - 1s` (debe devolver
`None`, rechazado) y `predicted_min_len + 1s` (debe devolver no-`None`,
aceptado), con `v_app_mps=2000.0` (peor caso, el más lento de
`V_APP_RANGE_MPS`) y las 4 geometrías reales del proyecto (ridgecrest_north,
arcata, valencia, stanford-2). **Mismo resultado que antes — la fórmula
documentada sigue confirmada correcta** — pero ahora contra el
comportamiento real de la función, no contra una relectura de su
código. 49/49 en `tests/analytical/test_closed_form.py`, suite completa
sin cambios de conteo. Ningún número publicado cambia; solo el método de
verificación. `docs/QA_REPORT.md` fila 1.5 actualizada con la misma
nota.

## 2026-07-31 — Los 3 arrays pre-F1.1 quedan re-medidos con herramienta actual — monterey_bay cambia (1.60→1.50), ridgecrest_north adoptado (2.67), spread pasa a 5.33×

**QA E2E, cierre de items 1/2 del gate.**

**Item 1 — ridgecrest_north**: antes de adoptar 2.67 como valor
publicado, verifiqué (no asumí) que no cambia nada aguas abajo: el
orden de rango de los 8 SNR50 es idéntico con 2.50 o con 2.67
(`ridgecrest_north` sigue entre Valencia y FOSSA en ambos casos), así
que los 4 ρ de Spearman quedan EXACTOS (n_ch +0.1905, dx 0.0000,
apertura +0.3095, fs −0.3805) y el spread (definido por max/min, que no
involucra a ridgecrest_north) tampoco se mueve por este cambio en
particular. Corrida oficial vía `darkfiber-snr-curve` (no el script de
diagnóstico usado para B5) con `--files` explícito (los 12 archivos,
alfabetizados) y provenance completa: **SNR50=2.67**, threshold=8.0
auto-resuelto desde `array_profiles` (A7/A8), 140/140 trials, curva
monótona dentro de IC. `array_profiles` actualizado; el 2.50 anterior
archivado en `array_profile_history` como **superseded Y NO
REPRODUCIBLE** (mismo hallazgo de B5 ya documentado arriba).

**Item 2 — monterey_bay**: threshold verificado ANTES de correr (no
asumido) — `array_profiles.thresholds_json` = `{"threshold": 4.0,
"tier0_threshold_calibration_note": "A8: barrido... default retenido,
sin evidencia de descalibración"}` — 4.0 es el valor real, confirmado,
no una suposición (a diferencia del error cometido con
ridgecrest_north). Corrida oficial con `--files` explícito (los 15
archivos pre-registrados), threshold=4.0 auto-resuelto: **SNR50=1.50**
(CAMBIÓ de 1.60 — a diferencia de ridgecrest_north/threshold, que dio
el mismo número con o sin el bug, acá el valor en sí es distinto).
140/140 trials, curva monótona. `array_profiles` actualizado; el 1.60
anterior archivado en `array_profile_history` como **superseded**
(mismo patrón que arcata/ridgecrest_north — lista de archivos de la era
pre-F1.1 no registrada, no investigado más allá de eso, no se intentó
diagnosticar la causa exacta como se hizo con B5/arcata).

**Verificado antes de adoptar** (no asumido): con monterey_bay=1.50, el
orden de rango de los 8 sigue idéntico (monterey_bay sigue siendo el
mínimo — 1.50 sigue por debajo de FORESEE 1.75) — los 4 ρ de Spearman
quedan, de nuevo, EXACTOS. **El spread SÍ cambia**: `8.00/1.50 = 5.33×`
— no `5.00×` (que ya había reemplazado el `4.83×`/`3.7×` originales
hace apenas un commit). Pendiente: cascadear esta corrección a los
documentos narrativos (`writeup.md`/`.es.md`/`writeup_data.md`/
`pilot_kit.md`/`announcement_v1.1/*`, CHANGELOG.md) donde `5.00×` ya se
había escrito — no aplicado todavía, a la espera de confirmación (fuera
del alcance explícito pedido para este cierre, que solo pedía
actualizar esta tabla y observaciones).

**Con esto, los 3 arrays de provenance pre-F1.1 quedan los 3 re-medidos
con la herramienta actual, `--files` explícito y provenance completa —
2 de 3 (arcata, monterey_bay) dieron un valor DISTINTO al archivado; el
tercero (ridgecrest_north) dio un valor distinto pero ya fue adoptado
sin volver a investigar la causa exacta (a diferencia de arcata, donde
la heterogeneidad de geometría SÍ se identificó). En los 3 casos, el
código quedó verificado estable (sin cambios funcionales, QA-3.0) — la
explicación atribuida es lista de archivos no registrada, en los 3.
Esto es la justificación empírica, no solo de diseño, de dos piezas de
trabajo que este proyecto ya tiene en marcha: el campo `input_files`
que F1.1 agregó al schema (antes de eso, no había forma de saber qué
archivos habían producido un SNR50 — exactamente el agujero que hizo
irresoluble esta investigación para los 3 valores pre-F1.1), y el
auto-sello de versión que está en el backlog de
`PLAN_CIERRE_Y_LANZAMIENTO.md` (sin la lista de archivos exacta
registrada, ni el hash de commit, un valor pre-F1.1 es, en los hechos,
imposible de auditar retroactivamente — el problema visto desde su
consecuencia, no desde su diseño original).

## 2026-07-31 — QA-3.0/3.1/3.2 CERRADO: sin cambios de código desde antes de F1.1; ridgecrest_north TAMPOCO reproduce con el código actual — "lista de archivos" en ambos, por regla de decisión pre-declarada

**QA E2E, cierre de B5.**

**3.0 — git log discriminante.** `git log --oneline --since=2026-07-19`
sobre los 5 módulos del path de medición
(`snr_curve.py`/`selftest.py`/`synth.py`/`coherence.py`/`triage.py`) da
6 commits (`11c76a5`, `11ba713`, `649a345`, `c948875`, `9a07ecc`,
`d9d32de`). Diff exacto de cada uno contra las líneas que consumen el
generador aleatorio (`run_step`, `run_trial`, `inject_and_verify`,
`inject_and_verify_sized`): **`run_step` es BYTE-IDÉNTICO** entre el
commit que documentó arcata=5.9 por primera vez (`da4e4d5e`,
2026-07-24) y HEAD — las únicas adiciones son un parámetro
`diagnostics=None` opcional (no-op si no se pide) y campos puramente
aditivos en `CoherenceResult`/`SelfTestResult` (`onset_agrees`, etc.).
`triage.py` (`d9d32de`, ANTERIOR a la primera medición de arcata) ganó
`seg_numbers`/`sample_offset` para streaming, pero con default `None`
preserva "el comportamiento exacto anterior... para todo llamador
existente, batch incluido" (verbatim del propio mensaje de commit).
**Conclusión: sin cambios funcionales en el path de medición** desde
antes de que arcata se midiera por primera vez.

**3.1 — reconstrucción de ridgecrest_north (pool homogéneo, sin
ambigüedad de geometría).** Primer intento: 12 archivos en el orden
`ridgecrest_already_used + ridgecrest_new_random` (el orden que vengo
usando toda la sesión), threshold=4.0 → **SNR50=2.90, NO reproduce
2.50**. Encontré y corregí un bug propio antes de sacar conclusiones:
ese orden NO es el alfabético (`sorted(glob(...))`, lo que el código
real usa cuando no se pasa `--files`) — reordené alfabéticamente:
**SNR50=2.67, sigue sin reproducir**. Encontré un segundo error propio:
usé threshold=4.0 (default), pero ridgecrest_north tiene calibración
A7/A8 real, threshold=8.0 (`array_profiles.thresholds_json`) — corregido
y re-corrido: **SNR50=2.67 otra vez, IDÉNTICO bajo threshold=4.0 y
8.0**. Esto último no es un bug — coincide EXACTO con el hallazgo ya
documentado el 2026-07-24 ("SNR50 de ridgecrest_north: idéntico bajo
threshold 4.0 y 8.0", más abajo en este archivo): para este array, el
cruce de 50% recall está gobernado aguas abajo (coherencia/semblanza),
no por el umbral Tier0 — confirmado de nuevo, de forma independiente,
en esta reconstrucción.

**Con los dos bugs propios corregidos (orden de archivo, threshold), la
reconstrucción SIGUE sin reproducir 2.50 (da 2.67).**

**Aplicando la regla de decisión pre-declarada, literal**: no
reproduce → ambiguo entre código y lista de archivos → 3.0 desempata →
3.0 confirma CERO cambios funcionales → **conclusión: es lista de
archivos, en arcata Y en ridgecrest_north, y se documenta así, sin
disparar re-medición** (la re-medición estaba condicionada a que 3.0
mostrara cambios funcionales, y no los mostró). No pude identificar el
subconjunto/orden exacto de archivos que reproduciría 2.50 — la lista
de 12 archivos en `sample_plan_draw.json` es la única registrada, y ni
en su orden original ni alfabetizada reproduce el valor archivado. Esto
queda como límite de reproducibilidad de la era pre-F1.1, no como
código inestable.

**3.2 — corrección del registro**: el 5.90 de arcata pasa de
"superseded" a **"superseded Y NO REPRODUCIBLE"** (la reconstrucción
con seeds/código idénticos dio 7.33, no 5.90). El 2.50 de
ridgecrest_north **sigue vigente** (no se re-mide, por la regla de
arriba) pero queda anotado con el mismo caveat: **no reproducible con
las herramientas y el archivo de pool actuales** — mismo patrón que
arcata, un nivel de severidad por debajo (acá no hay evidencia de
heterogeneidad de geometría de por medio; el pool es homogéneo,
verificado). monterey_bay no se testeó de la misma forma (no pedido por
la regla) — queda con el mismo caveat implícito de "provenance
pre-F1.1, no re-verificado", ya cubierto por QA-05.

## 2026-07-31 — QA-3.3: robustez del claim central verificada — inmune a que los 3 arrays pre-F1.1 estén equivocados

**QA E2E, verificado antes de registrar (no tomado de la palabra del
usuario).** Los 4 ρ de proxies contra la tabla congelada (arcata=8.00):
n_ch +0.1905, dx 0.0000, apertura +0.3095, fs −0.3805 — coinciden con lo
ya registrado en la entrada "FE DE ERRATAS (QA-3.2)" de 2026-07-30.

**Sensibilidad extrema, verificada por enumeración exhaustiva (no
analítica)**: dejando que monterey_bay, ridgecrest_north Y arcata (los
3 arrays con provenance pre-F1.1, ver QA-05) tomen **cualquier** SNR50
en `[0.5, 15.0]` simultáneamente (barrido de todas las combinaciones de
"slot" relevantes entre los 5 valores fijos de FORESEE/Stanford-2/
Valencia/FOSSA/stanford1_campus — Spearman solo depende del orden, así
que alcanza con probar una posición por cada hueco entre valores fijos,
no un continuo), el **máximo ρ alcanzable en valor absoluto por
cualquiera de los 4 proxies es 0.6545 (fs)** — confirmado por cómputo
exhaustivo, no estimado. **Ninguno cruza 0.7381** en el peor caso
posible. El claim central ("ningún proxy geométrico/de muestreo predice
SNR50") es robusto a que los 3 arrays con provenance más débil de toda
la serie estén completamente equivocados.

## 2026-07-31 — QA-2.3 CERRADO: determinismo total confirmado, descarta aleatoriedad sin sembrar como causa de B5 en TODA la serie

**QA E2E, auditoría exhaustiva (D1.2/D1.3).** La aleatoriedad sin
sembrar queda **DESCARTADA como causa** en toda la serie — no solo en
las corridas pre-F1.1: 14 sitios `default_rng(...)` en
`src/darkfiber/`, TODOS con entero explícito (`1_000+step_idx` en
`snr_curve.py`, `seed` encadenado en `selftest.py`/`synth.py`, seeds
fijos en el harness sintético de Bloque A); **cero** `default_rng()`/
`default_rng(None)` sin argumento; **cero** `np.random.rand`/
`random.random()`/`random.shuffle`/`random.choice` sueltos en todo el
árbol. Orden de archivos también determinístico: las 4 rutas de
construcción de `files` en `snr_curve.py` (auto/segy/tdms/`--files`
explícito) están las 4 envueltas en `sorted(...)`, mismo patrón en
`calibrate.py`/`run_on_quakeflow.py`/`pipeline_daemon.py`. Con esto, la
discrepancia de B5 (arcata: 5.90 archivado vs. 7.33 reconstruido con
seeds idénticos) se explica por **lista de archivos o cambio de código
entre versiones** — nunca por aleatoriedad, en ningún array de la
serie.

**De paso, cierra QA-10**: la propia auditoría de homogeneidad de pools
(entrada 2026-07-30, "Auditoría de homogeneidad de pool") leyó los
attrs (`dt_s`/`dx_m`) de TODOS los archivos de los 3 pools QuakeFlow
(monterey_bay 15, ridgecrest_north 12, arcata 15) con éxito, sin
recurrir nunca al default silencioso de `load_quakeflow_h5`
(`run_on_quakeflow.py:132-133`, `dt_s`→0.01/`dx_m`→8.0 si faltan).
Declarado explícito: **el default existe en el código, pero nunca se
ejerció en ninguna corrida publicada de la serie de 8.**

## 2026-07-31 — FE DE ERRATAS: off-by-one en `interferometry.py:301` corregido (QA-08/E1)

**QA E2E, seguimiento.** El demo sintético de interferometría
(`run_demo`, `interferometry.py`) intenta posicionar la fuente del
segundo pase 150m simétricamente respecto del primero (`x_start_m=-150.0`
antes del arreglo, `x_start_m=<fin del arreglo>+150.0` después) — pero
el "fin del arreglo" estaba mal calculado como `n_ch*dx` en vez de
`(n_ch-1)*dx` (mismo patrón exacto que el bug ya corregido de
`docs/array_geometry_table.md`, ver entrada 2026-07-30). El standoff
real del segundo pase era 158m, no los 150m intencionales (con
`dx=8.0m` del demo, 1 canal de diferencia sobre 150m ≈ 5.3%).

**Impacto, verificado antes de decidir la severidad (no asumido)**:
`interferometry.py` no lo importa ningún otro módulo de
`src/darkfiber` — no toca el path de medición de SNR50 ni ningún
`array_profiles`. Sí alimenta `docs/writeup.md`/`writeup.es.md`
(Figura 11, `fig4_interferometria.png`) y el claim "4/4" de
`tests/test_interferometry.py::test_interferometry_demo_passes_all_four_checks`.
De los 4 checks del demo, los 2 que miden precisión de velocidad
(`err1<=10%`, `r2_1>=0.90`) usan el pase ÚNICO (`two_passes=False`) —
nunca tocan la línea del bug. El único check que sí depende del pase
asimétrico es la ganancia de SNR por stacking (`snr2>=snr1`), una
desigualdad direccional que un desfasaje de 8m sobre 158m no podía
voltear. La Figura 11 se construye solo con los datos del pase único.
**Clasificación final: MENOR** (impacto acotado, verificado con
evidencia — no asumido de entrada).

**Corregido**: `x_start_m=n_ch * dx + 150.0` → `x_start_m=(n_ch - 1) * dx + 150.0`.
Re-verificado tras el fix: `run_demo()` sigue dando **4/4**, ningún
check se volvió inestable (de hecho `v2` pasó a medir exacto 400 m/s,
igual al real, aunque `v2` nunca estuvo assertado). `tests/test_interferometry.py`
verde.

## 2026-07-30 — FE DE ERRATAS (QA-3.2): los 4 rho de proxies cambian con arcata=8.00, conclusión no cambia

**QA E2E, gate pre-paper.** Recalculados los 4 Spearman ρ (n_ch, dx,
apertura, fs vs SNR50) sobre la tabla CONGELADA final (arcata=8.00, no
5.9 — la geometría de arcata no cambió, solo su SNR50). Valores viejos
(registrados 2026-07-30, entrada "Cuantificación Spearman", más abajo)
vs. nuevos:

| Proxy | ρ viejo (arcata=5.9) | ρ nuevo (arcata=8.00) | p nuevo |
|---|---|---|---|
| n_ch | +0.0714 | **+0.1905** | 0.6514 |
| dx | +0.0843 | **0.0000** | 1.0000 |
| apertura | +0.2381 | **+0.3095** | 0.4556 |
| fs | −0.3805 | −0.3805 (sin cambio) | 0.3524 |

Los 4 siguen muy por debajo de `|ρ|=0.7381` — **la conclusión no
cambia** (ningún proxy geométrico/de muestreo predice SNR50), pero los
números sí, y quedan corregidos acá para que nadie cite los viejos
después de este commit. Ver `docs/QA_REPORT.md` QA-3.2 para el detalle
de la verificación.

## 2026-07-30 — CIERRE: serie de 8 SNR50 CONGELADA — arcata re-medido (8.00, antes 5.9), spread corregido a 5.0×

**Cierre de la auditoría de la entrada de abajo, por la regla de decisión
pre-declarada (heterogéneo → re-medición restringida a la geometría
mayoritaria + provenance completa; homogéneo → documentar y cerrar).**
monterey_bay y ridgecrest_north: homogéneos, sin cambios. arcata:
heterogéneo, re-medido.

**Re-medición de arcata** — `python -m darkfiber.snr_curve --dir
D:/darkfiber/data/quakeflow/arcata --array-id arcata --files
20230215T142504Z.h5 ... 20241221T151620Z.h5` (los 12 archivos de
3,020ch/100Hz, explícitos, EXCLUYENDO los 3 de 7,550ch/125Hz),
threshold=4.0 (default, sin cambios). 140/140 trials válidos, curva
monótona dentro de IC Wilson 95%. **SNR50 = 8.00** (antes 5.9, medido
sin saberlo sobre un pool que mezclaba dos geometrías). El valor
anterior queda archivado con procedencia en `array_profile_history`
(upsert automático, no sobrescritura silenciosa — confirmado en el log
de la corrida: "Curva/SNR50 previos de 'arcata' archivados... antes de
sobrescribir"). Provenance completa en el JSON nuevo
(`input_files`/`noise_exclusion`, schema actual). No es una corrida de
datos nuevos ni un evento real re-evaluado — Bloque A intacto: misma
metodología de ruido sintético sobre el mismo pool de ruido real,
restringida a la geometría que la fila de `array_profiles` describe.

**Spread de la serie, corregido**: con arcata en 8.00, el máximo de la
serie deja de ser stanford1_campus (7.73) — **spread = 8.00/1.60 =
5.0×**, no el 4.83× reportado en la entrada "Cierre de la serie N=8"
(2026-07-30, abajo) ni el 4.83× de F1.1-F1.5. Esa entrada anterior
queda como estaba (no se edita en silencio) — esta es la corrección
vigente.

**Tabla final de 8 SNR50, con sha256 completo de cada `snr_curve_<id>.json`**
(ver también `docs/array_geometry_table.md`, hashes truncados ahí por
legibilidad):

| Array | SNR50 | sha256 |
|---|---|---|
| monterey_bay | 1.60 | `f35789e6b3e91c7b65e3868b7e889b500af05319bde57fcc0cd650218b837230` |
| FORESEE | 1.75 | `ef8890b37bc8247c8fa738234011149397ee7e47e4957e283d5089934b9580f5` |
| Stanford-2 | 1.7692307692307692 | `c5756e8c796b8ce6761607c9f39d8067c6be3a24646287c841fe3c5072f0a625` |
| Valencia | 2.3333333333333335 | `b1dff168b3972236675c55e0575337bfb573a6c2d1884794eb9c0cf1d21c8330` |
| ridgecrest_north | 2.50 | `75cdc830f9b88ed477b31507c9c32b0a7fbd0e2e74e6823b7a95ba530e6c762b` |
| FOSSA | 4.50 | `1f566023c027233091a269f668add82f393e001e0c208c97d1445a4e78532ed3` |
| stanford1_campus | 7.727272727272727 | `326beaefd0b689af126c8f10fd26e2a57b011711495dc62a2598eefebfa9e7a9` |
| arcata | **8.00** | `bfaa1254fdb00954a4d0693ccf2ea3a294d82dbd6dc5215188d9d6e878e25409` (recalculado tras inyectar `pipeline_hash`; el valor previo `37f9a215d180…9cec29ff630` quedó stale — ver QA-3.1, `docs/QA_REPORT.md`) |

Commit que cierra esta serie: ver el próximo commit de este mismo día
en `git log` (mensaje "F1.6: cierre de serie"). El JSON de arcata lleva
además `pipeline_hash`/`pipeline_hash_source` inyectados post-hoc con
ese commit, mismo criterio que FOSSA (2026-07-29).

**Línea de llegada declarada por el usuario**: sin más comandos de
medición/auditoría sobre esta serie a partir de acá. Lo siguiente es
la estructura del paper.

## 2026-07-30 — Auditoría de homogeneidad de pool: monterey_bay y ridgecrest_north OK, arcata heterogéneo (confirmado, con la apertura de su geometría minoritaria)

**Cierre del hallazgo de arcata (entradas de arriba/abajo, 2026-07-30):
¿es arcata un caso aislado o el resto de los pools multi-archivo
pre-F1.1 (misma era) tienen el mismo problema?** stanford1_campus queda
exento por construcción — confirmado con `ls` del directorio
(`D:\darkfiber\data\stanford`): un solo `eastfoothills_real.npz`, medido
en F1.1 con `--fs`/`--dx` explícitos, no hay pool multi-archivo que
pueda ser heterogéneo.

**A1 — tabla por archivo** (`n_ch`/`fs`/`dx` de los attrs embebidos,
leídos directo, no de memoria):

`monterey_bay` (15 archivos) — TODOS `n_ch=2,845`, `dx=5.2m`. `fs` toma
dos valores: `200.004959` (4 archivos) y `199.995422` (11 archivos) —
jitter de reloj de ~0.0047%, ya documentado como benigno en
`docs/writeup_data.md` ("fs no es un 200Hz limpio"), NO una clase
estructural distinta como arcata.

`ridgecrest_north` (12 archivos) — TODOS `n_ch=1,150`, `fs=100.0`,
`dx=8.0m`, sin ninguna variación, ni siquiera jitter.

**A2 — veredicto por pool**: **monterey_bay HOMOGÉNEO**, **ridgecrest_north
HOMOGÉNEO**. Por la regla de decisión pre-declarada: documentar y
cerrar, sin re-medición.

**A3 — arcata, apertura de la geometría minoritaria (pendiente cerrado)**:
los 3 archivos de 7,550 canales @ 125Hz tienen `dx=2.0419046878814697m`
→ apertura implícita `(7550-1)×2.0419046878814697 = 15,414.34m`. Contra
la apertura de la geometría mayoritaria (3,020ch, la de
`array_profiles`): `(3020-1)×5.104762077331543 = 15,411.28m`. Las dos
aperturas son casi idénticas (~3m de diferencia, 0.02%) — consistente
con el mismo cable físico bajo dos configuraciones de adquisición
distintas (canal/gauge), no dos instalaciones distintas.

**Aplicando la regla de decisión pre-declarada**: arcata es
**heterogéneo** → re-medición restringida a la geometría mayoritaria
(3,020ch/100Hz, la de `array_profiles`), con provenance completa del
schema actual (`--files` explícito, 12 archivos). Corriendo — ver
entrada de cierre de esta misma fecha, más abajo, con el resultado y
los hashes finales de la serie.

## 2026-07-30 — CORRECCIÓN de lectura de la entrada de abajo: no es "L_c no predice SNR50", es "el binneado pre-registrado no resolvió L_c en la mayoría de los arrays"

**El resultado (ρ=−0.2515) NO se toca — se corrige cómo se lee, con
aritmética verificada, no reinterpretación libre.** Seis puntos, no
cinco:

**(C1) El límite vinculante real fue el BIN de 20m en 7/8 arrays, no el
piso `2·dx` como decía mi framing original.** Comparando `2·dx` contra
el ancho de bin fijo (20m) por array: monterey_bay 10.4<20,
FORESEE 4.0<20, Stanford-2 16.32<20, ridgecrest_north 16.0<20,
FOSSA 4.0<20, arcata 10.21<20, stanford1_campus 16.32<20 — **7 de 8 con
piso por DEBAJO del bin**. Solo Valencia (`2·dx`=33.6m) tiene piso por
ENCIMA del bin (20m). De esos 7, 6 quedaron efectivamente censurados
(FORESEE fue el único de los 7 que sí cruzó dentro de su propio primer
bin resoluble antes del piso).

**(C2) Inconsistencia real en mi implementación, declarada, no oculta**:
la detección de censura ocurría a la resolución del BIN (20m — si el
primer bin ya estaba bajo 0.368, se marcaba censurado), pero el VALOR
asignado era `2·dx` (4.0-16.3m según el array) — una escala más fina
que la que el método realmente sondeó. No invalida el resultado (las
reglas de censura estaban fijadas de antemano, antes de correr nada) —
pero explica por qué 6 de los 8 puntos terminan siendo, en los hechos,
marcadores de posición ordenados por `dx` (`2·dx` es monótono en `dx`),
no mediciones independientes de coherencia real.

**(C3) Límite ESTRUCTURAL de esta serie de 8 arrays, no un defecto del
análisis en sí**: `2·dx` recorre de 4.0m (dx=2m, FOSSA/FORESEE) a 33.6m
(dx=16.8m, Valencia) — factor **8.4×**. Ningún ancho de bin único en
metros puede servir simultáneamente a los dos extremos de esa escala.
Cualquier métrica de cruce en metros hereda este problema con esta
mezcla particular de instalaciones — si el fenómeno físico vive por
debajo de ~34m, estos 8 arrays, con estos spacings, no pueden testearlo
con una métrica de cruce sin rediseñar el bin por array (lo que a su vez
rompe la comparabilidad entre arrays que el diseño buscaba).

**(C4) Lectura correcta a partir de acá**: *"el binneado pre-registrado
no resolvió `L_c` en la mayoría de los arrays"* — NO *"`L_c` no predice
SNR50"*. Reportar un nulo limpio sería sobre-afirmar un resultado
negativo, exactamente el mismo tipo de error que sobre-afirmar un
hallazgo positivo, en la dirección contraria. El `ρ=−0.2515` sigue
siendo el número real bajo las reglas fijadas — pero no debe leerse
como evidencia de ausencia de mecanismo, porque el instrumento no llegó
a medir la cantidad de interés en 6 de 8 casos.

**(C5) Dato diagnóstico que faltaba — los únicos 2 valores realmente
medidos** (no censurados, cruce genuino dentro del rango observado):
**FORESEE, `L_c`=16.38m** (dx=2.0m, muy por encima de su propio piso de
4.0m) y **ridgecrest_north, `L_c`=20.52m** (dx=8.0m, por encima incluso
del ancho de bin — un cruce interpolado más allá del primer bin). El
`ρ=−0.2515` observado sobre 8 puntos está dominado, en la práctica, por
dónde caen estos DOS valores reales relativo a los 6 marcadores de
`2·dx` — con n_efectivo real de 2 mediciones independientes, no 8, el
dato no sostiene ninguna lectura direccional confiable en ningún
sentido.

**(C6) Responsabilidad del diseño, no de la ejecución**: el ancho de bin
de 20m estaba fijado en el pre-registro tal como fue aprobado — un
chequeo contra `2·dx` de los 8 arrays (aritmética simple, disponible
antes de correr nada) habría mostrado esto de antemano. Se registra así
para que quede como responsabilidad compartida del diseño aprobado, no
como un error introducido en la ejecución.

## 2026-07-30 — Veta #1 EJECUTADA: rho=-0.2515 medido — el binneado de 20m no resolvió L_c en 6/8 arrays (ver corrección de lectura arriba)

**F1.6, resultado del pre-registro `docs/prereg_veta1_coherencia_ruido.md`
(commit `9f4c550`), corrido tal cual quedó fijado — cero ajustes al
protocolo después de ver el número final.** Lectura pura de los pools
pre-registrados, Bloque A intacto.

### Resultado

| Array | L_c (m) | Estado | SNR50 |
|---|---|---|---|
| FOSSA | 4.00 | censurado (piso) | 4.50 |
| arcata | 10.21 | censurado (piso) | 5.9 |
| monterey_bay | 10.40 | censurado (piso) | 1.60 |
| Stanford-2 | 16.32 | censurado (piso) | 1.7692 |
| stanford1_campus | 16.32 | censurado (piso) | 7.7273 |
| FORESEE | 16.38 | **medido** | 1.75 |
| ridgecrest_north | 20.52 | **medido** | 2.50 |
| Valencia | 33.60 | censurado (piso) | 2.3333 |

**Spearman ρ(L_c, SNR50) = −0.2515** (p≈0.548, aproximado) — el número
en sí no se toca, no cruza ningún umbral pre-registrado en ninguna
dirección. **Pero ver la corrección de lectura de la entrada de arriba
(2026-07-30) antes de citar esto como "nulo"**: 6 de los 8 valores de
`L_c` son marcadores de posición (`2·dx`, censurados), no mediciones —
la lectura correcta es que el binneado de 20m no resolvió la métrica en
la mayoría de los arrays, no que se haya confirmado la ausencia de
relación entre coherencia del ruido y SNR50.

### Dos problemas encontrados y corregidos DURANTE la ejecución (no ajustes al protocolo)

**(1) Bug de encoding, igual que el de FOSSA (2026-07-30, entrada de
abajo).** La primera corrida murió en Valencia: `sanitize()`
(`run_on_stanford.py`) imprime "→" en su reporte de canales muertos, y
la consola de Windows en cp1252 no lo puede codificar — `UnicodeEncodeError`,
no un bug del análisis. Arreglado forzando `PYTHONIOENCODING=utf-8` en
la corrida, no tocando el código del pipeline.

**(2) Hallazgo real, no un bug de mi script: arcata tiene DOS geometrías
distintas entre sus 15 archivos pre-registrados.** Los primeros 3
archivos cronológicos (2022-12-26 a 2023-01-11) son **7,550 canales @
125Hz, dx=2.0419m**; los otros 12 (2023-02-15 en adelante) son **3,020
canales @ 100Hz, dx=5.104762077331543m** — esto último coincide EXACTO
con lo que `array_profiles.arcata` tiene registrado. Mi primera corrida
tomó los 2 primeros archivos de la lista (la geometría minoritaria,
7,550ch) sin saberlo, dando un `L_c` calculado sobre canales/spacing que
NO son los de la instalación que `array_profiles` describe. Corregido
tomando archivos de la geometría de 100Hz/3020ch (coincidencia
casualmente: el `rho` final no cambió, aunque el `L_c` de arcata sí,
10.21m en vez de 4.08m — quedó en el mismo lugar del ranking, 2do más
bajo, en ambos casos).

**Esto último es, en sí, un hallazgo que excede la veta #1**: arcata
cambió de configuración de adquisición (fs/dx/n_ch) a mitad de su propia
serie de 15 archivos pre-registrados, algo que ni el census F1.2 ni la
medición original de SNR50 (F1.0, anterior a este documento) señalan
explícitamente. No se investiga más acá ni se re-abre Bloque A (el
SNR50=5.9 de arcata queda como está, congelado) — pero `array_profiles`
y `docs/array_geometry_table.md` describen arcata con UNA sola fila de
geometría cuando en los archivos reales hay dos. Vale la pena que quede
anotado para quien revise el dataset de arcata más de cerca (fase de
paper o auditoría externa) — no se resuelve acá.

## 2026-07-30 — Cuantificación Spearman: ningún proxy geométrico/de muestreo predice SNR50 sobre los 8 arrays medidos (n_ch, apertura, fs)

**F1.6, dato nuevo y verificado — recalculado de forma independiente
desde `docs/array_geometry_table.md` antes de registrar los números
propuestos, no tomado de memoria.** Convierte a cuantitativo el claim
cualitativo ya existente ("la detectabilidad es por instalación, no una
constante geométrica", `docs/writeup.md`/`writeup.es.md` §6/§7) —
material directo para §5.2 cuando se escriba esa sección.

Los 8 puntos (n_ch, apertura_m, fs_hz, SNR50) salen tal cual de
`array_geometry_table.md` (a su vez de `array_profiles` +
`figures/snr_curve_*.json`). Spearman ρ de cada proxy contra SNR50
(recalculado con `scipy.stats.spearmanr`, que maneja empates —
`fs` tiene dos empates reales: 250.0 Hz en Stanford-2/Valencia, 100.0 Hz
en ridgecrest_north/arcata/stanford1_campus):

| Proxy | ρ (Spearman) | p (aprox., t de Student n=8) |
|---|---|---|
| n_ch | +0.0714 | 0.8665 |
| apertura | +0.2381 | 0.5702 |
| fs | −0.3805 | 0.3524 |

**Umbral confirmatorio, por enumeración EXACTA (no aproximación
asintótica) de las 8! = 40,320 permutaciones posibles de rangos para
n=8** (verificado corriendo la enumeración completa, no citado de una
tabla): dos colas `|ρ| ≥ 0.7381` (P exacto = 0.0458); una cola
`ρ ≥ 0.6429` (P exacto = 0.0481). Los tres proxies quedan muy por debajo
de cualquiera de los dos umbrales — ninguno se acerca a significativo.

**Por qué importa la apertura en particular**: de los tres, es el
candidato geométrico más obvio para cualquier revisor externo (más
apertura → más canales potencialmente coherentes con el beam → mejor
stacking, es el razonamiento intuitivo) y NUNCA se había testeado como
proxy antes de esta entrada — solo se había usado para explicar
mecanismos puntuales (el techo `v_app_max_resoluble`, el gate W/T de
Valencia). Puesta a prueba directamente contra los 8 SNR50 medidos,
queda refutada como predictor (ρ=+0.24, muy lejos de 0.7381). Esto no
contradice los hallazgos W/T de Valencia/FOSSA (esos son afirmaciones
sobre el MECANISMO de un array puntual con datos por-trial, no sobre si
la apertura predice el SNR50 AGREGADO entre arrays — son preguntas
distintas, ambas pueden ser ciertas a la vez).

## 2026-07-30 — Bug propio: `python -c` con acento inline corrompió un string antes de llegar a Python (mojibake silencioso, no detectado sin releer)

**Operacional, no de física.** Al parchear `figures/snr_curve_fossa.json`
con el campo `pipeline_hash_source: "inyección manual post-corrida"`
vía `python -c "..."` en la terminal de Windows, el acento de
"inyección" se corrompió a nivel de la propia línea de comando (la
consola no está en codepage UTF-8) ANTES de que el string llegara al
intérprete de Python — `json.dump` escribió fielmente un `�` de
reemplazo al archivo, sin error ni warning de ningún lado. Se detectó
releyendo el campo con `repr()` inmediatamente después de escribir (no
se asumió que el patch había salido bien por no haber excepción).
Arreglado escribiendo el patch como archivo `.py` en UTF-8 (vía la
herramienta de escritura de archivos, no la terminal) y verificado con
`assert` sobre el valor releído. **Para qué sirve**: cualquier patch
futuro de un JSON con texto no-ASCII vía `python -c` inline en esta
terminal corre el mismo riesgo silencioso — preferir un archivo `.py`
explícito en UTF-8 cuando el string tiene tildes/ñ, y releer+verificar
el campo después de escribir en vez de confiar en la ausencia de
excepción.

## 2026-07-30 — Cierre de la serie N=8 (FOSSA corrida completa): spread 4.83× estable desde N=4

**F1.6, cierre.** Con FOSSA cerrada (SNR50=4.50, 140/140 trials válidos,
`array_profiles` actualizado, commit `9a07ecc` + `pipeline_hash`
post-hoc en `figures/snr_curve_fossa.json`), la serie completa de 8
arreglos queda: monterey_bay 1.60, FORESEE 1.75, Stanford-2 1.77,
Valencia 2.33, ridgecrest_north 2.50, FOSSA 4.50, arcata 5.9,
stanford1_campus 7.73. **Spread = 7.73/1.60 = 4.83× — idéntico al ya
observado con N=4 y N=7** (ver entradas previas de
`sample_plan_fase1.md`/`docs/observaciones.md`). FOSSA cayó DENTRO del
rango ya observado, no lo amplió por ningún extremo — cuarta
confirmación consecutiva de que el spread no es un artefacto de muestra
chica. Tabla consolidada final: `docs/array_geometry_table.md`.

**Superseded 2026-07-30**: arcata se re-midió (heterogeneidad de pool
detectada en veta #1) y pasó de 5.9 a **8.00** — el spread vigente es
**5.0×** (8.00/1.60), no 4.83×. Ver entrada de cierre "CIERRE: serie de
8 SNR50 CONGELADA", más arriba en este archivo. Esta entrada queda como
registro histórico de lo que se sabía en ese momento, no se edita.

## 2026-07-30 — FE DE ERRATAS: mi atribución del dip de FOSSA al mecanismo W/T de Valencia era incorrecta

**Corrección a mi propia atribución, no un hallazgo de otra persona —
mismo criterio que la fe de erratas de FORESEE (`docs/snr50_extension_fase1.md`,
F1.2b): el error se documenta, no se edita en silencio.** Al reportar el
cierre de FOSSA, escribí en `docs/array_geometry_table.md` que la
no-monotonicidad de su curva (90%@SNR8 → 80%@SNR12 → 60%@SNR20) era
"consistente con la hipótesis W/T ya cerrada para Valencia" — sin
verificar la aritmética primero. **Verificado después (aritmética
simple, `L=23,294m`, `W=coincidence_window_s=3.5s`, ambos reales):
NO lo es.**

Despejando `v` de `W/T = seismic_min_coincidence` (0.30) se obtiene la
velocidad `v*` bajo la cual el techo geométrico de `coincidence_fraction`
cae por debajo del piso de 30%:

- **FOSSA**: `v* = 0.30 × 23,294 / 3.5 ≈ 1,997 m/s` — cae DEBAJO de todo
  el rango de `v_app` inyectado (2,000-6,500 m/s, uniforme). Dentro de
  ese rango, el techo W/T va de 30.05% (a 2,000 m/s, el extremo lento
  sorteable) a 97.7% (a 6,500 m/s) — prácticamente todo el rango queda
  por ENCIMA del piso de coincidencia. Solo ~15% de los sorteos caen
  bajo un techo de 40% (`v < 2,663 m/s`). Esto es estructuralmente
  insuficiente para explicar un 40% de no-hits en SNR=20 (8/20 trials):
  el mecanismo geométrico puro de Valencia, aplicado a la geometría de
  FOSSA, predice que la enorme mayoría de los sorteos deberían pasar el
  gate de coincidencia sin problema.
- **Valencia, en contraste**: `v* ≈ 3,553 m/s` (recalculado con el mismo
  método, `L=41,446m`) cae DENTRO del rango inyectado — una fracción
  sustancial de los sorteos aleatorios de `v_app` caen por construcción
  bajo el piso de coincidencia, sin importar el SNR. Ahí el mecanismo
  geométrico SÍ es suficiente por sí solo (ver entrada del 2026-07-29
  de abajo, verificada contra los 11 trials no-hit reales).

**Son dos fenómenos distintos, no el mismo mecanismo escalado a otra
apertura.** La no-monotonicidad de FOSSA queda sin explicación mecánica
— abierta como pendiente F1.6 (b), abajo. Corregido en
`docs/array_geometry_table.md` (nota de FOSSA), no editado en silencio.

## PENDIENTE F1.6 (declarado, NO ejecutado todavía) — dos lecturas read-only sobre diagnósticos ya en disco

**(a) Veta #1 — largo de coherencia espacial del ruido vs. SNR50, n=8.**
Con los 8 SNR50 ya medidos y cerrados, explorar si el largo de
coherencia espacial del ruido de fondo (no el ambiente categórico, una
métrica continua) correlaciona con SNR50 entre arreglos.
**Pre-registrar métrica, umbral y criterio ANTES de correr** — mismo
estándar que el resto del proyecto (pre-registro antes de ver el
resultado), no ajustar la métrica después de ver si correlaciona.

**(b) No-monotonicidad de FOSSA — ¿concentrada o repartida?** Con
`trial_diagnostics` de FOSSA ya en disco (`--dump-trial-diagnostics`
estuvo activo en la corrida completa): ¿los no-hits de SNR=12/20 se
concentran en el extremo lento de `v_app` con `coincidence_fraction`
cerca de 0.30 (i.e., el mecanismo SÍ actúa pero con más margen del que
la aritmética de arriba sugiere — a re-verificar con los datos reales,
no solo la aritmética teórica), o están repartidos por todo el rango de
velocidades? Si están repartidos (no concentrados en el extremo lento):
**hipótesis a verificar EN CÓDIGO, no asumir** — autosupresión de
STA/LTA: una señal fuerte (SNR alto) infla el LTA (long-term average)
de los canales/ventanas posteriores, elevando el piso de disparo y
suprimiendo el trigger en parte del arreglo — lo que explicaría recall
DECRECIENTE con SNR creciente (patrón inverso al esperado, visto tanto
en FOSSA como en Valencia). Leer la definición exacta de la ventana LTA
(`triage.py` o donde esté implementado el STA/LTA) antes de sostener
esta hipótesis — no asumir el mecanismo de la ventana sin confirmarlo
en el código primero.

**Anotación adicional (2026-07-30), solo registro — NO ejecutar, NO es
conclusión**: los dos únicos arreglos de los 8 con cola no-monótona
(Valencia y FOSSA) son, también, las dos aperturas mayores de la serie
— puestos 1 y 2 (41.4km y 23.3km); el tercero por apertura (arcata,
15.4km) sube monótono a 100%, y los otros cinco también. **Etiquetado
explícitamente como post-hoc**: la probabilidad de que los 2 arreglos
marcados a mano (por tener cola no-monótona) coincidan exactos con el
top-2 por apertura, si no hubiera ninguna relación real, es
`1/C(8,2) = 1/28 ≈ 3.6%` — mismo orden de magnitud que la hipótesis de
`fs` que en su momento pareció prometedora (~2.9%) y resultó falsa. No
se sostiene como hallazgo, es un patrón a tener en cuenta. Sí afina la
pregunta (b) de arriba: el mecanismo geométrico W/T simple ya quedó
descartado para FOSSA (fe de erratas de arriba), pero si existe un
mecanismo real que escala con apertura y no es ese, la autosupresión
STA/LTA sigue siendo candidata coherente con esta observación — el
tránsito del frente de onda a través del arreglo es proporcional a `L`
(mismo `T=L/v_app` del hallazgo W/T), así que el tiempo durante el cual
el LTA de un canal tardío queda contaminado por la energía de canales
tempranos también escalaría con la apertura. Verificar en código antes
de sostenerla, como ya está anotado arriba — esto no adelanta esa
verificación, solo la motiva un poco más.

## 2026-07-27 — Valencia: curva SNR50 no llega a 100% de recall (única de 7 arrays con esta forma)

**Observación, no experimento — F1.5.** Las 7 curvas SNR50 medidas
hasta ahora (monterey_bay, ridgecrest_north, arcata, stanford1_campus,
FORESEE, Stanford-2, Valencia) tienen todas la misma forma esperada
—recall sube monótono hasta 100% y se queda ahí— EXCEPTO Valencia: sube
hasta 90% en SNR=8, y despue baja a 85% (SNR=12) y 70% (SNR=20), sin
llegar nunca a 100% dentro del rango barrido (1-20).

El chequeo de monotonía-dentro-de-IC pasa igual (los IC Wilson 95% de
esos 3 escalones se solapan: [69.9,97.2] / [64.0,94.8] / [48.1,85.5] —
compatible con ruido estadístico puro a n=20/escalón), así que esto NO
bloqueó la medición ni se trató como error. Pero es la primera curva de
la serie con esta forma, y vale la pena tenerlo registrado en vez de
solo reportar el SNR50 interpolado (2.33) sin más contexto.

Dos candidatas a explicación, NINGUNA investigada todavía (no se diseña
experimento ahora): (1) es simple ruido de muestreo, se va a disolver
con más N en F1.6; (2) hay algo real del sitio — Valencia es el único
array submarino de los 7 con geometría de cable NO perfectamente lineal
en toda su extensión (mezcla tierra+mar, aunque acá se midió solo el
tramo submarino) y tiene 2 canales muertos confirmados en la punta más
profunda del cable (ver entrada de abajo) que reducen la apertura
efectiva sin que el pipeline lo sepa (el `n_ch`/`dx` que ve
`ArrayGeometry` sigue siendo el nominal, no el efectivo con 2 canales
muertos descontados).

## PENDIENTE F1.6 (declarado, NO ejecutado todavía) — Valencia: ¿la partición hit/no-hit en SNR=8/12/20 separa limpiamente en v*≈3,553 m/s?

**Trabajo declarado para la próxima sesión de F1.6, no crudo — instrucción
explícita: no ejecutar ahora.** Con los diagnósticos por-trial completos
de Valencia ya disponibles (`figures/snr_curve_valencia_submarine.json`,
`trial_diagnostics`, commit `9a07ecc`), falta verificar si la partición
hit/no-hit en los escalones SNR=8/12/20 separa limpiamente en
`v_app ≈ 3,553 m/s` (umbral hipotético, no derivado todavía en código —
a verificar, no asumir). Si separa: el techo de recall es puramente
geométrico (consecuencia directa del hallazgo W/T de la entrada de
abajo — a v_app por debajo de ese umbral, T=L/v_app crece lo suficiente
para que W/T caiga bajo `seismic_min_coincidence=0.30` con certeza; por
arriba, no) y el "dip" 90%→85%→70% de SNR=8→12→20 (entrada del
2026-07-27) es ruido de muestreo del mix de velocidades sorteadas al
azar en cada escalón (n=20/escalón, `v_app` uniforme en [2000,6500] —
un escalón puede sortear por azar más trials lentos que otro) — cierre
total de la anomalía, no solo del mecanismo. Si NO separa limpiamente,
reportar qué sí explica el resto de la dispersión.

## 2026-07-29 — Valencia: cierre de la pregunta abierta de la entrada anterior — W/T explica el 19.7%-30.0%, no era disparo STA/LTA disperso

**Seguimiento same-day de la entrada de abajo.** La entrada anterior dejó
abierto "¿por qué el disparo STA/LTA por-canal es tan disperso/parcial en
Valencia?", con heterogeneidad de ruido submarino y umbral mal calibrado
como candidatas sin investigar. Resultado, con aritmética verificada
contra los 11 trials no-hit reales (no supuesta): **no hace falta ninguna
de las dos candidatas.** `coincidence_fraction` mide la fracción máxima
de canales disparados dentro de la ventana `coincidence_window_s=3.5s`
(valor real leído del código, no asumido); el moveout real a través de la
apertura completa (L=41.45km) tarda `T=L/v_app` segundos — a los
`v_app` reales de estos 10 trials (2,200-3,400 m/s, `boundary_pinned=False`,
`onset_agrees=True`), T=12.6-18.8s, y `W/T` predice 18.6%-27.7% contra
19.7%-30.0% observado — cierra dentro de 2.5 puntos en los 10 casos. Es
decir: aunque CADA canal dispare perfectamente bien (no hay evidencia de
disparo "ruidoso" o parcial), el propio hecho de que el frente tarde
12-19s en cruzar el arreglo entero, contra una ventana fija de 3.5s,
acota matemáticamente el techo de coincidencia alcanzable muy por debajo
del piso `seismic_min_coincidence=0.30` — sin necesidad de invocar
heterogeneidad de acople submarino ni mala calibración. Documentado como
límite conocido en `docs/writeup.es.md` §7 / `docs/writeup.md` §6, sin
tocar umbral ni código (Bloque A congelado). El único de los 11 trials
que NO ajusta bien (30.0% observado vs. 12.7% predicho) es justo el que
tiene `boundary_pinned=True` — su `v_app` no es confiable (pineado en el
piso de la grilla), consistente con que la fórmula depende de tener una
`v_app` real para calcular `T`.

## 2026-07-29 — Valencia: instrumentado el porqué de los no-hits — no es el techo de apertura, es el gate de coincidencia STA/LTA

**Seguimiento de la entrada anterior (2026-07-27), ahora con dato en vez
de dos candidatas sin investigar.** Se agregó propagación de diagnóstico
por-trial (`CoherenceResult.boundary_pinned/onset_agrees/v_app_onset_mps/
explanations` → `SelfTestResult`, capa IO pura, Bloque A intacto) y se
re-corrió SOLO Valencia con `--dump-trial-diagnostics` (mismos 3
archivos/threshold/seeds del F1.5 original — determinismo bit-exacto
confirmado: SNR50=2.33 y los 7 pares hits/n idénticos, runtime
1894.2s→2039.0s dentro de variación normal).

La hipótesis de techo de apertura/resolución (`v_app_max ∝ L`,
propuesta antes de tener este dato) predecía que los no-hits a SNR alto
serían mayormente `boundary_pinned=True` (velocidad fuera del rango
resoluble por esta apertura). **Resultado: NO.** De los 11 trials no-hit
en SNR=8/12/20:
- 0/11 sin candidato Tier0 en absoluto.
- 1/11 con `boundary_pinned=True`/`onset_agrees=False` (un pico pineado
  en el piso de la grilla, 1500 m/s) — la única instancia real del
  mecanismo hipotetizado.
- **10/11 con velocidad correctamente resuelta y corroborada**
  (`boundary_pinned=False`, `onset_agrees=True`, semblanza-vs-onset
  dentro de 0-4% de diferencia, velocidad bien adentro de
  [1500,8000] m/s) pero clasificados `COHERENTE_DESCONOCIDO`. La causa,
  leída directo de `coincidence_fraction`: los 10 caen en 19.7%-30.0%,
  contra el piso `seismic_min_coincidence=0.30` — el STA/LTA dispara en
  muy pocos canales casi-simultáneamente, aunque el `span_fraction` sea
  100% (los canales que sí disparan están dispersos por todo el cable,
  no agrupados) y la semblanza post-hoc confirme que la señal está
  presente en ~92-100% de los canales una vez que se conoce la
  velocidad correcta.

**Para qué sirve**: refuta con dato la hipótesis original (útil
negativo, no solo "no confirmado") y abre una pregunta nueva y más
concreta para F1.6: ¿por qué el disparo STA/LTA por-canal es tan
disperso/parcial en Valencia específicamente? Candidatas sin investigar
todavía: heterogeneidad real de ruido a lo largo del cable submarino
(condición de acople variable, ver los 2 canales muertos de la entrada
de abajo como posible síntoma relacionado de lo mismo), o un umbral
STA/LTA calibrado para arrays terrestres que no transfiere bien a un
ambiente submarino. La infraestructura (`--dump-trial-diagnostics`)
queda disponible para instrumentar el mismo diagnóstico en cualquier
otro array de la serie sin tener que re-derivar esto desde cero.

## 2026-07-28 — FOSSA: piloto muestra un factor 12× de degradación de I/O entre dos pasadas idénticas, misma sesión

**Observación operacional, no de física — F1.5.** Durante el piloto de
FOSSA (previo a decidir si correr la curva completa de 140 trials), se
midieron tres pasadas read-only/piloto sobre los mismos 19 archivos
`.tdms` (~699MB c/u), todas con el mismo trabajo por archivo (cargar
completo vía `replay.load_tdms`, eager read):

1. Serie de RMS para estacionariedad (`compute_rms_series_lazy`, 19
   cargas): **628.5s** (~33.1s/archivo).
2. Chequeo de headroom int16 (19 cargas, mismo método de carga, sin
   ningún cómputo extra relevante): **7,597.8s** (~400s/archivo) — un
   factor **12×** sobre el trabajo #1, siendo exactamente el mismo
   trabajo.
3. Piloto SNR=8 (`run_step_lazy_single_file`, 20 cargas + 20 trials):
   **4,204.4s** (~210s/trial) — 6-10× más lento que el benchmark de
   carga de un solo archivo ya establecido en F1.4/F1.5 (14.6-22.4s).

Ninguna de las tres corridas cambió el código del loader entre medio —
es la misma función, los mismos archivos, en la misma sesión de esta
máquina. La hipótesis más simple es contención externa (antivirus
re-escaneando archivos binarios grandes leídos repetidamente,
throttling térmico tras I/O sostenido, u otro proceso de fondo), no una
propiedad real de `load_tdms` ni del diseño de lectura lazy de 1
archivo/trial. **No investigado más ahora** — se decidió no tomar la
extrapolación ×7 del piloto (≈8h10min) como estimador confiable del
costo real de la curva completa de FOSSA sin re-medir en condiciones
más limpias, y se dejó la decisión curva-completa/decimación/re-medición
pendiente del usuario en vez de decidir unilateralmente con un número
sospechoso. Si esto vuelve a aparecer en otra corrida pesada (Valencia
ya fue la más cara de las 3 curvas medidas, 1894.2s, sin este patrón),
vale la pena perfilar qué proceso específico está compitiendo por
disco/CPU en vez de asumir que es ruido de una sola vez.

**Seguimiento 2026-07-29 — perfilado, causa parcialmente identificada,
NO totalmente resuelta.** `docker ps -a` mostró `repo-dashboard-1`
(Streamlit) corriendo hacía 2 días con un bind-mount RW en vivo a
`D:\darkfiber\repo\data` (mismo disco físico que
`D:\darkfiber\data\Fossa\`), file-watcher poll-based (confirmado en su
propio log), y un healthcheck roto (puerto 8080 en vez de 8501) con
**2,438 fallos consecutivos** acumulados en 2 días. Se detuvo
(`docker stop`, reversible) y una carga aislada de un solo archivo dio
18.0s (limpio). PERO: el re-piloto completo (mismos seeds, 20 trials)
solo mejoró 9% (4,204.4s→3,829.0s) — la lentitud sostenida NO se
explica (solo) por el contenedor. Se verificó que ambos discos son
NVMe SSD (descarta disco mecánico lento) y que Defender está activo
pero sus exclusiones no son inspeccionables/editables sin admin desde
esta sesión (bloqueado, no descartado). RAM del sistema: 15.8GB
totales, solo 3.7GB libres al momento de medir — presión de memoria
real durante cargas sostenidas de arrays de ~1.4GB queda como la
explicación más plausible sin descartar, y no es arreglable por código.
**Extrapolación limpia (×7 sobre 3,829.0s) = 7h27min, todavía por
encima del techo de 6h pre-autorizado** — la curva completa de FOSSA
sigue sin correrse, pendiente de decisión explícita.

## 2026-07-27 — Valencia: 2 canales muertos confirmados en la punta más profunda del cable submarino

**Hallazgo de calidad de dato real, F1.5, no un bug de pipeline.**
`run_on_stanford.sanitize()` (ya existente, sin cambios) detectó, en
los 3 archivos reales de Valencia: 150,250 muestras no-finitas por
archivo (exactamente 601×250, un canal completo — sugiere que es UN
canal específico con el archivo entero en NaN/Inf, no ruido disperso) y
2 canales con varianza ~0 (índices 2466-2467 dentro del subrango
submarino restringido a 510-2977, es decir **canales reales 2976 y
2977** — los últimos dos de todo el arreglo). Según la geometría real
(`DAS-1-geometry-Valencia-undersea.csv`), esos dos canales están a
~377-379m de profundidad, la punta más lejana y más profunda de todo el
tendido — consistente con una hipótesis razonable (acople degradado en
el extremo del cable) aunque no confirmada, no investigada más acá.

`sanitize()` ya maneja esto correctamente (zeroea las muestras no
finitas, reporta los canales muertos, no dispara falsos triggers) — no
hizo falta ningún cambio de código para que la medición fuera segura.
Queda anotado porque es la primera vez en el proyecto que se ve un dato
real con canales muertos EN LA PUNTA del arreglo específicamente (no
dispersos), y porque la apertura nominal que usa `ArrayGeometry`
(`(n_ch-1)*dx`) no descuenta estos 2 canales — la apertura EFECTIVA es
ligeramente menor a la nominal, sin que nada en el pipeline actual lo
sepa o lo corrija. No cambia ninguna decisión tomada en F1.5 (2 de 2468
canales es despreciable), pero si esto se repite en otros arrays con
más canales muertos, valdría la pena que `ArrayGeometry` o
`gather_noise_sources` lo reporten explícitamente en el JSON de salida,
no solo en el log de consola.

## 2026-07-27 — Heterogeneidad de dtype de origen entre arrays: int16, float16, float32 — comparabilidad de SNR50 verificada, no asumida

**Hallazgo, surge de F1.4 (loaders de FORESEE/Stanford-2).** La serie de
SNR50 ahora cruza tres dtypes de origen distintos: `int16` (FOSSA,
truncamiento por cuantización si se opera en el tipo original — riesgo
de la señal completa redondeándose a cero a SNR bajo), `float16`
(FORESEE, redondeo por precisión chica — ~3 dígitos significativos,
rango dinámico chico — riesgo distinto: no trunca a cero, pero pierde
precisión de forma silenciosa), y `float32` (todos los demás:
ridgecrest_north, arcata, monterey_bay, stanford1_campus, Valencia,
Stanford-2 — estos dos últimos porque `read_segy()` decodifica IEEE
float32 directo del header SEG-Y).

**Por qué esto no rompe la comparabilidad de la serie — verificado, no
supuesto**: `synth.snr_to_amplitude` es invariante a escala (calibra
`amp = target_snr × RMS(ruido)/RMS(wavelet)`, ambos RMS en float64 —
`noise_rms`/`wavelet_rms` hacen `.astype(np.float64)` explícito,
confirmado leyendo el código). Pero esa invariancia matemática solo es
real si la aritmética de inyección (`add_plane_wave`) y la medición
downstream (STA/LTA en `triage.py`, semblanza en `coherence.py`) de
verdad ocurren en float32/float64 — nunca acumulando en el dtype de
origen. Confirmado por dos vías independientes para cada dtype de
riesgo (int16 en FOSSA, float16 en FORESEE — ambos loaders (`replay.py`)
upcastean a float32 INMEDIATAMENTE al cargar, antes de que cualquier
otra función toque el array):

1. **Grep del código**: cero usos de `int16`/`float16` en `coherence.py`
   y `triage.py` — semblanza en `dtype=np.float64`, STA/LTA cumsum en
   `dtype=np.float64`, todo lo demás float32.
2. **Test de precisión, no solo de detección** (`tests/test_replay_hdf5_generic.py::test_injection_arithmetic_never_rounds_through_float16`):
   inyecta a SNR=1 (el escalón más frágil) sobre datos cargados de
   float16, y verifica que los valores inyectados NO caen en la grilla
   discreta de float16 (round-trip float16→float32 sin cambio) — con
   datos reales, solo ~1% de las 384 muestras inyectadas coincidieron
   por azar con su propia versión redondeada a float16; si la aritmética
   hubiera pasado por float16 en algún punto, el 100% coincidiría por
   definición. Mismo tipo de chequeo (supervivencia a SNR=1) ya existía
   para el truncamiento de int16 de FOSSA (`test_low_snr_injection_survives_int16_source`,
   commit anterior).

**Conclusión**: la comparabilidad de SNR50 entre arrays con dtype de
origen distinto está verificada con evidencia (grep + test de
precisión), no asumida por la invariancia matemática de la fórmula
sola. Pendiente: confirmar el dtype real de Valencia al cargarla en
Ola 2 — si es otro float "raro" (float16 u otro), aplicar el mismo test
de supervivencia antes de correr su curva.

## 2026-07-27 — Deriva de RMS entre archivos, 4 arrays ya medidos: CV 65-198%, spread hasta 60×

**Hallazgo, no experimento diseñado — surge de construir el criterio de
estacionariedad para F1.3** (ver `sample_plan_fase1.md` §2). Caracterización
de solo lectura (`gather_noise_sources` + `synth.noise_rms` sobre los
mismos archivos reales ya usados en cada medición — cero re-corridas,
cero cambios de código, Bloque A intacto): la serie temporal de RMS
por archivo/fuente del pool de ruido de cada array ya medido varía
muchísimo más de lo que hubiera asumido a priori.

| Array | n fuentes | CV (std/mean) | max/min RMS |
|---|---|---|---|
| ridgecrest_north | 40 | 1.913 | 39.9× |
| arcata | 15 | 0.654 | 10.1× |
| monterey_bay | 15 | 1.982 | 60.5× |

**Por qué importa para leer SNR50 correctamente**: el mecanismo de
calibración de SNR es LOCAL por trial, no global/pooled — verificado con
cita de código en `sample_plan_fase1.md` §0b (`selftest.py:126-131`,
`synth.py:237,258`): cada trial calcula `noise_rms()` sobre SU PROPIA
ventana sorteada, nunca sobre el pool completo. Esto significa que
SNR50 es, por construcción, un **piso de estructura de ruido invariante
a la escala absoluta del pool** — cada inyección es exactamente SNR=X
relativo a su propio entorno inmediato, sin importar si ese entorno
viene de un archivo "fuerte" o "débil" del pool. La consecuencia
práctica: la serie de 4 SNR50 (1.6/2.5/5.9/7.73) sigue siendo
comparable entre arrays PESE a que sus pools individuales tengan una
heterogeneidad interna enorme (65%-198% de CV) — la heterogeneidad no
contamina la medición, solo amplía el rango de condiciones que la curva
termina promediando. Sin este mecanismo verificado, la magnitud de esta
deriva sería motivo de alarma real; con él, es un dato esperable de
"ruido real de sitio a lo largo de sesiones muy separadas en el
tiempo", no un indicio de medición rota.

**Nota adicional, no buscada pero relevante**: el chequeo de
estacionariedad propuesto para los arrays nuevos de F1.3 (serie de RMS
archivo-a-archivo, umbral 3.0×) cubre implícitamente contaminación
telesísmica no detectada de la ventana de ruido — un arribo telesísmico
real dentro de un archivo se manifestaría como un salto anómalo de RMS
en la serie, exactamente lo que el chequeo ya está mirando. No es un
chequeo separado a diseñar, es un efecto secundario gratuito del mismo
mecanismo.

No se diseña ningún experimento para esto ahora — queda registrado como
contexto de interpretación para F1.6, donde la serie completa (7-8
arrays) permitiría ver si el CV intra-pool correlaciona con algo (ej.
con la dispersión del propio SNR50 entre arrays, o con el ambiente de
instalación).

## 2026-07-24 — SNR50 de ridgecrest_north: idéntico bajo threshold 4.0 y 8.0

**Observación, no experimento — a revisitar en F1.6 con N mayor.**
Verificando la procedencia de los 3 SNR50 existentes para la extensión
de Fase 1 (ver `docs/snr50_extension_fase1.md`), encontré que
ridgecrest_north tiene DOS mediciones completas de SNR50, una bajo
threshold=4.0 (default, archivada en `array_profile_history` tras la
corrección A7 — "curva/SNR50 medidos bajo threshold=4.0... SNR50=2.50")
y otra bajo threshold=8.0 (calibrado, A7/A8 — la vigente,
`figures/snr_curve_ridgecrest_north.json`, corrida completa 140/140,
`threshold_source="perfil del arreglo (calibrate.py --apply)"`) — **el
valor interpolado es el MISMO: SNR50=2.50 en ambas.** Dos JSON como
evidencia, ambos con curvas completas (no truncadas ni degeneradas):
el snapshot archivado (4.0) y `figures/snr_curve_ridgecrest_north.json`
(8.0).

Posible indicio de que, para este array, el crossing de 50% recall está
gobernado por la COHERENCIA (semblanza + concordancia de estimadores,
aguas abajo) y no por Tier0/STA-LTA (aguas arriba) — un cambio de
umbral de disparo de 4.0 a 8.0 (2×) no movió el punto donde el pipeline
completo cruza 50% de detección. Si esto se sostiene con N mayor (más
arrays, más pasos de umbral), tendría una implicación práctica directa
para F1.5/F1.6: el umbral Tier0 de un array nuevo importaría menos de
lo esperado para su SNR50 medido, siempre que no esté tan mal calibrado
que empiece a suprimir triggers reales antes de que lleguen a
coherencia. No se diseña ningún experimento para esto ahora — queda
registrado para cuando F1.6 tenga más arrays y pueda mirarlo con
evidencia, no una anécdota de N=1.

## 2026-07-24 — Shutdown ordenado del pipeline (SIGTERM/SQLite)

**`add_signal_handler` es Unix-only, y `kill -SIGINT` desde git-bash en
Windows no llega de forma confiable a un proceso de consola real** —
confirmado a mano en esta misma máquina: `NotImplementedError` al
registrar el handler (esperado, documentado en la propia librería
estándar), y un `SIGINT` mandado vía `kill` desde git-bash NO disparó
siquiera el `except KeyboardInterrupt` de respaldo que ya existía en
`main()` — el proceso siguió corriendo hasta un `taskkill //F` directo.
Esto significa que el path de shutdown ordenado (el motivo entero de
este trabajo) no se puede verificar de punta a punta en esta máquina de
desarrollo — solo por revisión de código + el patrón estándar de
`asyncio`. Vale la pena, si esto vuelve a tocarse, probarlo de verdad en
un contenedor Linux (`docker compose stop pipeline` con
`stop_grace_period`) antes de confiar en que funciona como está escrito.

**El intento de reproducir un shutdown ordenado en Windows terminó
siendo, sin querer, una prueba real de la OTRA mitad del fix.** Como el
`SIGINT` no disparó nada, tuve que matar el proceso con `taskkill //F`
-- un kill duro genuino, sin ningún cleanup. El `-wal` quedó en 140 KiB
(bien por debajo del nuevo umbral de `wal_autocheckpoint=100`, ~400 KiB)
y `PRAGMA integrity_check` dio "ok" con las 10 filas ya escritas
intactas y legibles. Ni siquiera hizo falta que el handler de señal
funcionara para que el ajuste de `wal_autocheckpoint` ya redujera la
exposición real ante un kill duro -- las dos partes del fix son
independientes y cada una aporta algo por separado, no solo en conjunto.

**`data/count.py`, un script de una sola línea de consulta al ledger,
apareció sin trackear en el working directory durante la verificación
final** (`ruff check .` lo encontró, `ruff check src/ tests/` no, que es
lo que CI realmente corre sobre un checkout limpio). No lo toqué --
parece ser la propia herramienta de inspección que originó el reporte
del bug de shutdown (cuenta filas por tabla, coincide con el "150 filas"
mencionado). Queda como está, fuera de git, no es parte de este trabajo.

## 2026-07-23 — Test de regresión para el bug de finalización prematura de C1

**Reconocimiento del caso real de C1.** Antes de escribir el test, se
buscó en `CHANGELOG.md`, este mismo archivo, `docs/adr/0006-batch-stream-parity.md`
y el historial de git (commit `1794fc1`, único commit de C1 — atómico,
sin WIP previo) el caso real que expuso el bug. Resultado: el MECANISMO
está documentado completo y consistente en tres fuentes independientes
(el mensaje del commit, `CHANGELOG.md`, y el docstring actual de
`raw_block_settled_end_s`) — el diseño original finalizaba un sub-evento
en cuanto había silencio DESPUÉS de su propio borde, sin chequear si el
bloque crudo que lo contenía (antes de la re-segmentación por densidad,
A5) seguía abierto. Pero los VALORES concretos del caso real NO están —
solo dos índices de muestra sin `fs` asociada (`evt_0000_1021_*` →
`evt_0000_1045_*`), ni ventana temporal, ni límites de bloque, ni el
archivo confirmado (se infiere circunstancialmente que era
`ci39493944.h5`, el único M5.8 de Ridgecrest usado en todo el proyecto,
pero el commit nunca lo nombra). Tampoco hay una revisión de git con el
diseño bugueado aislado para reproducir contra ella — C1 llegó al
repo ya arreglado. Se decidió, en vez de inventar esos valores, construir
el test enteramente sobre el mecanismo documentado, con datos sintéticos
propios — más honesto que fabricar una reconstrucción con apariencia de
precisión que el registro no sostiene.

**El test (`tests/test_closure_criterion.py`) construye un `raster`
sintético directamente** (sin pasar por `StreamRunner`/física de onda):
un evento A con un valle de silencio interno más corto que
`merge_gap_s` (no debería partir el bloque — el mismo tipo de hueco que
la estrategia bugueada confunde con un final) seguido de un gap real
mayor a `merge_gap_s` y un evento B. El criterio de cierre correcto
(ahora inyectable, `StreamRunner(closure_criterion=...)`, ver
`stream_runner.ClosureCriterion`) pasa los tres asserts necesarios
(ninguno alcanza solo): no fragmenta A en el valle, cierra A antes de
que B empiece (no degenera en "nunca cerrar", que es exactamente el
estado medido en Arcata — ver CHANGELOG C3), y lo hace con latencia
acotada. Un doble de test que reproduce el diseño pre-C1
(`_buggy_pre_c1_closure_criterion`, nunca en producción) SÍ fragmenta A
en el valle, confirmado corriendo la MISMA aserción que usa la
estrategia correcta y capturando el `AssertionError` real:
`settled_end_s=8.0` reportado repetidamente (75 veces, entre t=8.02s y
más) mientras el bloque crudo verdadero era `(5.0, 11.0)` — la firma
exacta del bug real (mismo tipo de corrimiento que
`evt_0000_1021_*` → `evt_0000_1045_*`, solo que con valores propios,
trazables, no inventados con apariencia del caso real).

**Por qué esto importa más allá de este test puntual**: es el
instrumento que hace auditable la heurística de cierre por densidad que
C3 dejó como backlog (necesaria porque el criterio actual casi nunca
cierra en arreglos grandes como Arcata) — cualquier implementación nueva
de `ClosureCriterion` se valida con este mismo test antes de reemplazar
la actual, sin volver a razonar el mecanismo desde cero cada vez.

## 2026-07-23 — C3 (ring buffer + operación continua)

**El hallazgo más importante de C3 no fue de implementación: fue que la
compuerta de cierre de bloque crudo (`raw_block_settled_end_s`, ya
existente desde C1) prácticamente nunca se abre en un arreglo real y
grande.** Escaneando el archivo real de Arcata usado para medir C3
(3.020 canales, 420s): el 92.3% de la línea de tiempo tiene AL MENOS UN
canal por encima del umbral Tier0 en algún instante — con tantos
canales, es casi estadísticamente garantizado. El bloque crudo
("¿algún canal disparado?") termina siendo UNO SOLO que cubre casi el
archivo entero, sin importar que la re-segmentación por densidad (A5) sí
logre extraer eventos individuales limpios adentro — A5 actúa DESPUÉS
del cierre, no ayuda a que el bloque exterior cierre. Resultado medido:
el buffer retenido llega al 100% del archivo (cero eviction real) tanto
en el caso patológico (un solo bloque sin resegmentar, 5 de 6 archivos
de Arcata muestreados) como en el caso "normal" (con 113 eventos
significativos bien extraídos) — la propia extracción de eventos
funciona perfecto, pero la eviction nunca tiene oportunidad de actuar.
Los dos números duros de C3 (margen ≥2× a `--speed 1`, sin lag
acumulativo a `--speed 10`) NO se cumplen para Arcata con el diseño
actual: 0.92× y 0.21× respectivamente, medidos, no estimados. Vale la
pena, para cualquier trabajo futuro sobre esto, no tratarlo como "hay que
optimizar la eviction" — la eviction que se construyó funciona
correctamente donde tiene oportunidad de actuar (confirmado con un
archivo real de Ridgecrest y con un test sintético largo). El problema
real está un nivel más arriba: la propia noción de "bloque cerrado" para
un arreglo de miles de canales necesitaría un criterio de densidad, no
de "¿absolutamente ningún canal activo?" — y tocar eso significa tocar
la misma lógica que ya evitó un bug real de finalización prematura en
C1, así que cualquier cambio ahí necesita el mismo nivel de rigor
empírico que esa vez, no un parche rápido.

**Bug real, encontrado en el camino a lo anterior: numerar eventos por
posición LOCAL en la ventana de cada pasada no sobrevive ni siquiera sin
eviction, en datos reales con mucha actividad.** La primera versión de
la numeración persistente (`StreamRunner._seg_global_n`) asignaba un
número global la PRIMERA vez que veía la posición absoluta de inicio de
un segmento — pero un segmento perteneciente a un bloque crudo TODAVÍA
ABIERTO puede cambiar de forma entre pasadas a medida que llega más
contexto (la re-segmentación por densidad re-examina el bloque abierto
completo cada vez, por diseño desde A5) — numerar esa forma provisoria
como si fuera definitiva infla el conteo total muy por encima del que
produce el batch. Se encontró recién al verificar contra un archivo real
de Arcata con eventos normales (el escenario sintético de este mismo
Bloque, más limpio, no lo disparaba) — otro recordatorio de que la
verificación sintética de este proyecto (política de CI) no sustituye la
verificación manual contra datos reales que exige
`PLAN_CIERRE_Y_LANZAMIENTO`, ni siquiera para un cambio que "solo" toca
bookkeeping de numeración, no física.

**El asentamiento del bandpass no-causal en el borde IZQUIERDO de una
ventana recortada (eviction) es, medido sobre un archivo real de
Ridgecrest cerca del M5.8, más rápido que el borde derecho ya
documentado en C1** (converge a diferencia relativa exactamente 0.0 a
partir de ~10s de margen, contra los ~20s medidos para el borde derecho
en C1) — no se usó ese número más chico como margen real (se reusa
`finalize_margin_s`, ya más grande, por simplicidad y para no introducir
una segunda constante empírica), pero vale la pena tenerlo registrado
como dato en sí: sugiere que la asimetría entre bordes de un filtro
`sosfiltfilt` (forward-backward) no es necesariamente simétrica, y que
si algún día hace falta apretar el margen para ganar rendimiento, el
lado izquierdo tiene más margen de sobra que el derecho.

**La estabilidad de memoria del daemon a través de MUCHOS ciclos de
archivo (23 loops de un archivo real de 120s en 240s de reloj real,
+0.3% de RSS) es una propiedad DISTINTA de si la eviction logra achicar
el buffer DENTRO de un archivo/stream único** — vale la pena no
confundirlas en reportes futuros. La primera está sólidamente
confirmada (cada `StreamRunner` se recolecta por completo entre
archivos); la segunda depende enteramente del hallazgo de arriba sobre
el cierre de bloques crudos.

## 2026-07-23 — C4 (pilot kit)

**Escribir el pilot kit obligó a nombrar en voz alta un hueco que ya
existía pero nunca se había hecho explícito como límite del producto: hoy
no existe ningún adaptador de ingesta en vivo (socket/API) contra el
protocolo real de un interrogador.** `replay.py` ya lo decía en su propio
docstring ("deuda declarada para cuando haya hardware real hablando un
protocolo de verdad"), pero era una nota de implementación, no algo
dirigido a un lector externo. Al escribir "qué necesita el dueño de la
fibra" para el pilot kit, quedó claro que shadow-mode HOY solo puede
ofrecerse como entrega periódica de archivos, no como conexión persistente
— y que prometer lo segundo sin tenerlo sería exactamente el tipo de
sobreventa que el proyecto existe para no hacer. Vale la pena que cuando
C3 (ring buffer + Docker) avance, alguien revise si ese trabajo también
habilita o no un adaptador de ingesta real — hoy son dos huecos distintos
(rendimiento del buffer vs. protocolo de hardware) que un lector externo
fácilmente confundiría como uno solo.

**El esquema de `catalog.py` (ledger, array_profiles, etc.) nunca guardó
la forma de onda cruda en ninguna tabla — eso ya era cierto por
construcción, sin que nadie lo hubiera declarado como propiedad del
diseño.** Al escribir la sección de manejo de datos del pilot kit
(qué se guarda, qué no), revisar el `CREATE TABLE` real confirmó que cada
tabla solo guarda referencias de archivo, métricas numéricas derivadas y
metadatos — nunca las muestras canal-tiempo. Esto se convirtió en el
argumento central (y verificable, no una promesa) de "los datos crudos
del operador nunca salen de su infraestructura" en el acuerdo de datos.
Vale la pena mantenerlo así deliberadamente de acá en más (no es difícil
que una futura función de debugging agregue una columna BLOB con una
ventana cruda "solo para diagnóstico" y rompa esta propiedad sin que
nadie lo note) — candidato a un test de regresión de esquema si el
proyecto llega a tener un pilot real corriendo.

## 2026-07-22 — C2 (dashboard)

**`streamlit run archivo.py` ejecuta el archivo como script standalone
(`__main__`, sin paquete padre) — imports relativos revientan.**
`dashboard.py` usaba `from .catalog import ...` (mismo estilo que todo el
resto del proyecto) y funcionaba perfecto corrido como
`python -m darkfiber.dashboard`, pero streamlit lo ejecuta con `exec()`
directo sobre el archivo, no como módulo del paquete — `ImportError:
attempted relative import with no known parent package`. Lo atrapó el
propio smoke test (`AppTest`, que corre el script tal como streamlit lo
haría) antes de probarlo a mano. Arreglado con imports absolutos
(`from darkfiber.catalog import ...`) en ese archivo puntual. Vale la
pena recordarlo si en algún momento se agrega OTRO entry point pensado
para correr vía `streamlit run` (o cualquier otro runner que haga lo
mismo) — no es intuitivo que el mismo import que funciona en todo el
resto del proyecto rompa acá.

**`st.table()` con una columna de tipo mixto (float + string) falla la
conversión a Arrow, pero streamlit lo "arregla" solo, en silencio.** La
columna "magnitud" del scoreboard mezclaba números reales (verdad-terreno
QuakeFlow) con el placeholder de texto `"—"` (sin verdad-terreno) — pyarrow
tira `ArrowTypeError`, streamlit lo atrapa y hace un fallback automático
("Applying automatic fixes for column types"), así que la UI no se rompe,
pero el log queda con un traceback que parece un error real. Se arregló
forzando la columna entera a texto en vez de confiar en el fallback. Vale
la pena revisar el resto de las tablas del proyecto (si en algún momento
se muestran en una UI, no solo en markdown) por el mismo patrón: cualquier
columna que mezcle `None`/placeholder de texto con un número real es
candidata a este mismo problema silencioso.

**El waterfall en vivo del M5.8 real de Ridgecrest, corrido a través de
`replay.py`->`StreamRunner`, muestra el frente de llegada iluminando casi
todo el arreglo (~1150 canales) a partir de ~47s de forma inequívoca a
simple vista** — la misma física que cuenta §6 del writeup, pero como
imagen en vez de números. Podría ser un buen candidato para una figura
del writeup o del paquete de difusión más adelante (hoy no hay ninguna
figura que muestre el M5.8 "crudo", solo sus métricas) — no se persiguió
acá, es una idea para cuando se arme el material de difusión.

**El catálogo de firmas real está genuinamente vacío** (confirmado de
nuevo acá, ya lo decía el WIP de C2 de la sesión anterior) — ninguna
corrida real de `run_on_quakeflow.py` llama a `cat.match()`. La vista de
catálogo del dashboard es, hoy, principalmente una demo de la
*capacidad*, no una vista de datos reales. Sigue siendo la pieza de
trabajo más clara si en algún momento se decide conectar
`COHERENTE_DESCONOCIDO` real al catálogo (extraer un vector de firma de
un evento real es, en sí, una decisión de diseño física que no está
tomada todavía — qué representa "la identidad" de una señal recurrente,
más allá de sus métricas de coherencia).

## 2026-07-22 — C1 (streaming)

**La inestabilidad de supresión bajo truncamiento de archivo no es un bug
de streaming, es una propiedad del propio batch.** Escaneando
`bandpass(data[:, :n], fs)` para un archivo real de Ridgecrest a muchos
valores de `n` (sin ningún streaming de por medio), el conjunto exacto de
candidatos `INCOHERENTE_LOCAL_SUPRIMIDO` cambia de forma no monótona —
aparecen, desaparecen, cambian de borde — incluso en `n` bien lejos de
cualquier margen de asentamiento razonable del filtro. El batch
"correcto" (archivo completo) no es un punto de convergencia estable al
que otros `n` se acerquen: es más bien un valor entre varios que
fluctúan. Ver backlog: "estabilidad de la supresión frente a bordes de
ventana". Para qué podría servir además de arreglarlo: si esta
inestabilidad es medible y acotada, podría convertirse en una señal de
"confianza" per-evento (un candidato cuya clasificación cambia mucho
entre re-cómputos con distinto contexto es, por construcción, menos
confiable que uno estable) — no implementado, solo la idea.

**El buffer creciente da "veredictos provisorios" gratis.** Como
`StreamRunner` recomputa sobre el buffer completo en cada pasada, un
evento que todavía no se finalizó (le falta margen) YA tiene un
veredicto tentativo disponible en cada pasada intermedia — hoy se
descarta (solo se emite el finalizado). Podría exponerse como un canal
de "borrador, puede cambiar" separado del canal de veredictos finales,
para un dashboard operativo que quiera mostrar "algo está pasando" antes
de que el sistema esté seguro. Tensión directa con la honestidad del
proyecto (un veredicto provisorio que después cambia es exactamente el
tipo de cosa que el sistema existe para NO hacer) — si se persigue,
tendría que estar marcado como borrador de forma imposible de confundir
con un veredicto real, en la UI y en el dato mismo.

**El asentamiento del bandpass no-causal es medible y tiene una escala de
tiempo concreta**, no solo "hay que esperar un rato": en el archivo real
de Ridgecrest probado, la diferencia relativa cae de ~82% (0s de margen
extra) a ~3e-6 (5s) a exactamente 0.0 (20s), para una transición cerca de
un evento fuerte. Esa curva de convergencia en sí (no solo el margen
elegido) podría ser un dato reusable: caracterizar el "settling time"
típico del filtro 1-24Hz sobre ruido real de cada instalación (parecido
en espíritu a `snr_curve.py` / SNR50 por arreglo) en vez de un margen
fijo global — dato de calibración por arreglo, no una constante.

**El costo O(n_pasadas²) del buffer creciente escala con canales, no solo
con duración.** Arcata (3020 canales) es ~2.6× más lento por-muestra que
Ridgecrest (1150 canales) en el mismo cómputo, antes incluso de contar
que también tuvo más pasadas por ser un archivo más largo con un evento
único de 420s (peor caso: un solo bloque que nunca cierra hasta el
final). Vale la pena, cuando se diseñe el ring buffer de C3, no asumir
que el costo por pasada es plano entre arreglos — perfilarlo por
instalación real, no solo por duración de archivo.
