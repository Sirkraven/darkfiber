# Observaciones — Bloque C

Bitácora de comportamientos raros, capacidades inesperadas, o ideas tipo
"esto también serviría para..." que aparecen mientras se construye C
(operable). No todo acá tiene que tener sentido todavía — es el insumo
crudo para la fase de exploración posterior, no un documento pulido. Cada
entrada: fecha, de qué fase salió, qué se observó, y (si aplica) para qué
podría servir. No confundir con el backlog de `PLAN_CIERRE_Y_LANZAMIENTO.md`
(ese es trabajo declarado y concreto; esto es más crudo, todavía sin
decidir si es trabajo).

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
