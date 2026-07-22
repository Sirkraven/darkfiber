# Observaciones — Bloque C

Bitácora de comportamientos raros, capacidades inesperadas, o ideas tipo
"esto también serviría para..." que aparecen mientras se construye C
(operable). No todo acá tiene que tener sentido todavía — es el insumo
crudo para la fase de exploración posterior, no un documento pulido. Cada
entrada: fecha, de qué fase salió, qué se observó, y (si aplica) para qué
podría servir. No confundir con el backlog de `PLAN_CIERRE_Y_LANZAMIENTO.md`
(ese es trabajo declarado y concreto; esto es más crudo, todavía sin
decidir si es trabajo).

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
