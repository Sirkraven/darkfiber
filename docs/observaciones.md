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

## 2026-07-30 — Veta #1 EJECUTADA: resultado NULO — L_c no predice SNR50 (rho=-0.2515, signo contrario al predicho, no llega a sugestivo)

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

**Spearman ρ(L_c, SNR50) = −0.2515** (p≈0.548, aproximado). **Resultado:
NULO** — ni siquiera entra en la zona sugestiva pre-registrada
(`0.5≤|ρ|<0.7381`), y el signo es NEGATIVO, contrario a la dirección
predicha (positiva). Bajo las reglas fijadas de antemano (§8 del
pre-registro), esto es inequívocamente un no-hallazgo: no hace falta
invocar la condición de validez del signo porque ni la magnitud alcanza
el umbral sugestivo.

**Caveat honesto sobre el poder del test, declarado ahora que se ve**:
6 de los 8 arrays (todos menos FORESEE y ridgecrest_north) quedaron
**censurados en el piso** — el ancho de bin fijado (20m) resultó más
grueso que `2·dx` para la mayoría de los arrays de spacing chico (2-8m),
así que el método no pudo resolver nada más fino que su propio bin más
cercano al origen para esos 6. Esto reduce la varianza real explotable
por Spearman (6 de 8 valores son, en los hechos, una función monótona
de `dx` solamente, no de una medición independiente de coherencia) — el
resultado nulo es genuino bajo las reglas fijadas, pero el test tuvo
menos poder real del que el pre-registro asumía implícitamente. Queda
como limitación del EXPERIMENTO ejecutado (no del pre-registro en sí,
que fijó la regla de censura correctamente y de antemano) para cualquier
lectura futura de este número.

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
