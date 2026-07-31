# DarkFiber: un motor de coherencia física para Distributed Acoustic Sensing — con límites de detección medidos por instalación y abstención honesta

*Traducción de cortesía — el documento canónico es la versión en inglés,
[`writeup.md`](writeup.md); ante cualquier discrepancia, la versión
inglesa manda. Borrador técnico — Bloque B1/F4.1. Cada cifra de abajo está
respaldada por `docs/writeup_data.md`, `validacion_real/scoreboard.md`,
`validacion_real/NOTES.md` y `CHANGELOG.md`. Este es un borrador para
revisión del autor, no una publicación — ver la nota al final.*

## 1. Resumen

DarkFiber es un motor de coherencia física para detección de sismos sobre
arreglos de fibra óptica de Distributed Acoustic Sensing (DAS). En vez de
tratar cada uno de los cientos o miles de canales de un arreglo como un
problema de clasificación independiente por canal, mide la única
propiedad que distingue un frente sísmico real de ruido o tráfico: un
moveout coherente a través del arreglo, cuantificado por semblanza de
slant-stack y corroborado por una regresión de velocidad de onset
independiente. Ningún LLM participa en el camino del veredicto: el
sistema mide física y reporta lo que mide.

Validamos el pipeline contra 43 grabaciones DAS reales en cuatro
instalaciones de arreglo (Stanford, Ridgecrest, Arcata, Monterey Bay): 16
llevan un sismo real catalogado, puntuado contra verdad-terreno
USGS/SCEDC, 13 de esos 16 sorteados de una muestra pre-registrada antes
de ver ningún resultado.

La confiabilidad va primero en los resultados. Sobre los 27 archivos sin
evento catalogado, el sistema produjo **cero falsas alarmas**. Sobre cada
evento real, produjo **cero casos de una señal real detectada y después
descartada**.

De los 16 sismos reales, **ninguno alcanzó una confirmación limpia** — 8
se midieron como débiles-pero-presentes, 2 como llegadas
regionales/emergentes más allá de la apertura resoluble del arreglo, y 6
cayeron bajo el propio piso de detección de ese arreglo, cada bolsillo
explicado por una curva directamente medida, no una suposición.

El hallazgo central es que la detectabilidad misma es una propiedad de la
instalación, no de la geometría del arreglo: recall-vs-SNR, medido contra
el ruido de fondo real propio de cada arreglo, da un factor de 5.00× de
dispersión en SNR50 entre instalaciones de tamaño ampliamente comparable
— el número que un operador necesitaría en la práctica para evaluar si un
arreglo dado puede ver un evento dado. Dos confirmaciones aparentes de
pasadas de validación anteriores fueron retractadas después por dos
guardas internas independientes, una vez que la re-segmentación por
densidad expuso artefactos de fusión de eventos y no-mediciones de borde
de grilla debajo de ellas — que el sistema retracte sus propios dos
resultados titulares es la evidencia más clara disponible de que no está
afinado para producir confirmaciones. Los límites de detección se dan en
forma cerrada como función de la apertura del arreglo y la tasa de
muestreo. El código, el ledger completo de validación, y un DOI son
públicos.

## 2. El problema

La mayor parte del cable de fibra óptica enterrado y submarino del mundo
está "oscuro" — tendido para capacidad futura, sin usar hoy. Distributed
Acoustic Sensing (DAS) convierte cualquiera de esos hilos en un arreglo
denso de sensores de tasa de deformación gratis: un interrogador en un
solo extremo de un cable ya existente produce un arreglo sísmico de facto
de kilómetros de largo, sobre infraestructura que ya está en el suelo. El
obstáculo para usar de verdad esa capacidad latente para monitoreo
sísmico nunca fue realmente la detección — es la confianza. Un sistema
sobre el cual un operador de red sísmica pueda actuar tiene que no gritar
lobo, y tiene que mostrar su razonamiento en vez de emitir un puntaje
opaco. Este artículo trata de construir esa capa.

Un interrogador DAS moderno convierte un único cable de fibra óptica en
un arreglo de cientos o miles de sensores de tasa de deformación,
muestreados a decenas o cientos de Hz. Esa densidad es lo que hace real
la oportunidad — y lo que hace del análisis por canal el enfoque
equivocado. Tratado como canales independientes, un sistema de monitoreo
construido alrededor de detección de anomalías por canal o clasificadores
ML por canal se ahoga en falsas alarmas: tráfico, viento, actividad
humana y artefactos de instrumento producen todos excursiones por canal
que, aisladas, parecen señal. Un frente sísmico real, sin embargo, no es
un evento por canal: es una única perturbación física que cruza el
arreglo entero, llegando a cada canal con un retardo de tiempo fijado por
su velocidad aparente a lo largo de la fibra — el *moveout*. Esa
pendiente, no la amplitud de ningún canal individual, es el discriminante
físicamente significativo entre "un sismo cruzó este arreglo" y "algo
pasó cerca de un punto de este cable." La Figura 1 ilustra esto
directamente: las mismas trazas crudas por canal que parecen transitorios
dispersos y ambiguos se resuelven en una llegada de onda plana inequívoca
una vez graficadas como tiempo-vs-posición-de-canal, porque la física *es*
la pendiente.

![Figura 1: tres paneles canal-tiempo — moveout casi vertical para un sismo, franja diagonal lenta para un vehículo, y un solo punto sin pendiente para un transitorio local.](../figures/fig1_pendiente_es_fisica.png)

## 3. Método

El pipeline tiene tres niveles, cada uno auditable de forma
independiente:

1. **Nivel 0 (triage STA/LTA).** Una razón corta-plazo/largo-plazo barata
   por canal marca ventanas candidatas de tiempo-canal que valen la pena
   examinar más, filtrando la abrumadora mayoría del silencio antes de
   que corra cualquier cómputo más pesado.
2. **Coherencia (semblanza de slant-stack).** Las ventanas candidatas se
   apilan a lo largo de una grilla barrida de velocidades aparentes; la
   velocidad que maximiza la semblanza de forma de onda entre canales es
   la velocidad aparente medida de la llegada, si el arreglo es lo
   suficientemente coherente como para resolver una. Las Figuras 2 y 3
   muestran esto sobre un escenario sintético de sismo-confirmado: un
   pico de semblanza interior claro, y picks de fase P/S sobre el beam
   resultante.

   ![Figura 2: semblanza de slant-stack vs. velocidad aparente, un pico interior claro.](../figures/fig2_semblanza.png)

   ![Figura 3: el beam apilado con los picks de fase P/S marcados.](../figures/fig3_beam_fases_PS.png)
3. **Supervisor / taxonomía.** La velocidad medida, su fracción de
   coincidencia (parte del arreglo disparada casi-simultáneamente) y su
   fracción de extensión (extensión espacial del disparo) se clasifican
   en uno de cinco veredictos: `SISMO_CONFIRMADO` (sismo local
   confirmado), `FUENTE_MOVIL_TRAFICO` (fuente móvil, p. ej. tráfico
   vehicular — rastreado por regresión de trayectoria, no por moveout),
   `INCOHERENTE_LOCAL_SUPRIMIDO` (falso positivo local suprimido,
   huella espacial chica), `COHERENTE_DESCONOCIDO` (coherente pero sin
   clasificar — alimenta el catálogo de firmas), y
   `POSIBLE_REGIONAL_EMERGENTE` (llegada masiva, casi-simultánea,
   espacialmente decorrelacionada, cuyo moveout la apertura del arreglo
   no puede resolver — eventos regionales o distantes; ver §7).

Dos compromisos de diseño hacen que `SISMO_CONFIRMADO` sea
específicamente difícil de ganar, ambos agregados después de fallas
sobre datos reales (§6):

- **Un máximo de semblanza en el borde de la grilla no es una medición.**
  Si el argmax de semblanza cae en el borde de la grilla de velocidades
  barrida en vez de en un pico interior genuino, el resultado se marca
  `boundary_pinned=True` y no puede por sí solo sostener una
  confirmación — una curva que sube monótonamente hasta pegarse al borde
  de la grilla significa que el óptimo real está fuera del rango
  barrido, no que el valor del borde sea correcto.
- **La confirmación exige que dos estimadores independientes concuerden.**
  Junto a la semblanza de slant-stack, una segunda medición,
  estructuralmente distinta — regresión Theil-Sen (mediana repetida)
  sobre el primer cruce de umbral STA/LTA de cada canal versus su
  posición — debe recuperar una velocidad aparente compatible (dentro de
  40% de diferencia relativa) antes de que `SISMO_CONFIRMADO` sea
  alcanzable. La robustez de Theil-Sen ante picks ruidosos por canal
  (punto de quiebre hasta ~29% de los puntos) la vuelve un chequeo
  genuinamente independiente sobre la medición de semblanza, no uno
  correlacionado.

Un catálogo de firmas (respaldado en SQLite, aislado por `array_id`)
además aprende señales recurrentes sin clasificar — un evento
coherente-pero-desconocido visto repetidamente puede ser nombrado por un
operador humano sin reentrenar ningún modelo, y esa etiqueta se reconoce
después en ocurrencias futuras por similitud con el vector guardado, no
por un límite de clasificador.

**Ningún LLM participa en este camino.** Cada campo de un veredicto —
velocidad aparente, semblanza, fracción de coincidencia, concordancia del
ajuste de onset — es una medición física directa, y cada veredicto lleva
una lista `explanations` legible por humanos que muestra exactamente qué
mediciones lo produjeron. Nada acá es un resumen o juicio de un modelo de
lenguaje.

## 4. Datos

La validación sobre datos reales usó dos fuentes:

- **Arreglo DAS de Stanford (vía SEG-Y de PubDAS/Globus, y vía el
  repositorio de GitHub `FiberOpticEarthquakes` para Pawnee)**: 626
  canales, 8.16 m de espaciado, 100 Hz (la tasa de muestreo varía según
  la adquisición — 50 Hz para la grabación de Pawnee de 2016, 100 Hz para
  la grabación de East Foothills de 2017; leída del header SEG-Y, nunca
  asumida). East Foothills M4.1 (2017-10-10) está registrado en el ledger
  de validación QuakeFlow (1 evento); Pawnee M5.8 (2016-09-03, un
  telesismo a ~2.500 km del arreglo, 22 archivos SEG-Y crudos) se validó
  cualitativamente y **no** está en el ledger — la llegada emergente de
  onda superficial de un telesismo no es el caso de moveout de sismo
  local que el scoring de verdad-terreno del ledger está construido para
  puntuar.
- **QuakeFlow DAS (Hugging Face `AI4EPS/quakeflow_das`)**, tres
  instalaciones, cada una con archivos `.h5` por evento ya curados con
  verdad-terreno USGS/SCEDC embebida (magnitud, tiempo de origen, índice
  de muestra del evento):

  | Arreglo | Archivos (ledger) | Canales | fs (Hz) | Espaciado de canal (m) | Apertura (m) |
  |---|---|---|---|---|---|
  | ridgecrest_north | 12 | 1.150 | 100.0 | 8.0 | 9.192 |
  | arcata | 15 | 3.020 | 100.0 | 5.10 | 15.411 |
  | monterey_bay | 15 | 2.845 | ~200.0 | 5.2 | 14.789 |

**Una nota sobre monterey_bay:** su RMS de ruido de fondo medido
(`array_profiles.noise_stats_json.rms_mean ≈ 60.106`) está
aproximadamente 5-6 órdenes de magnitud por encima de los otros tres
arreglos (0.02-0.16), y su tasa de muestreo es `fs≈199.995 Hz` en vez de
un 200.0 Hz limpio — ambos tomados textuales del ledger. La explicación
probable es que este archivo fuente particular de QuakeFlow está en
unidades físicas distintas a los otros tres arreglos (p. ej. cuentas
crudas del digitalizador en vez de tasa de microstrain). Esto **no**
socava los resultados de SNR50/recall de arriba: `snr_to_amplitude()`,
la única definición operativa de SNR del proyecto, escala un wavelet
inyectado por el RMS de ruido *local*
(`amp = target_snr · RMS(ruido) / RMS(wavelet)`), así que es invariante
de escala por construcción — un SNR50 de 1.6 significa lo mismo en la
escala de monterey_bay que el 8.00 de arcata significa en la escala de
arcata. Lo que sí significa: no debería sacarse de este dataset ninguna
comparación de amplitud *absoluta*, offset de semblanza, o umbrales en
unidades crudas entre arreglos, y confirmar las unidades físicas reales
del archivo fuente de monterey_bay es trabajo abierto y declarado
(backlog), no resuelto acá.

Un segundo número relacionado: `array_profiles.synth_recall = 0.0` para
monterey_bay — una métrica de auto-test legada, de bajo poder estadístico
(`run_array_selftest`, 3 escalones de SNR × 3 intentos = 9 inyecciones en
total) calculada por separado de la curva de recall bien powered de
arriba (7 escalones × 20 intentos = 140 inyecciones, la misma definición
`snr_to_amplitude`). Cero éxitos en 9 intentos es difícil de reconciliar
con la propia medición de la curva de recall en los mismos valores de SNR
(SNR=3: 18/20 aciertos; SNR=8: 18/20 aciertos) — si el recall real ahí es
realmente ~90%, 0/9 tiene una probabilidad de aproximadamente 1 en mil
millones por azar, lo cual argumenta en contra del ruido de muestreo
ordinario. La anomalía de unidades de arriba no es la explicación:
`run_array_selftest` inyecta vía la misma `snr_to_amplitude()` invariante
de escala, así que un desajuste de unidades crudas no debería, por el
mecanismo visible acá, anular su recall mientras deja intacto el recall
de la curva. Esto se reporta como una discrepancia abierta y bien
evidenciada entre dos caminos de código de auto-test sobre el mismo
arreglo, mecanismo sin resolver, en vez de conectada con la anomalía de
unidades por especulación. Ambas son ítems de backlog
(`docs/writeup_data.md`); investigar más implicaría correr código nuevo
contra el Bloque A, que se mantiene congelado para este release.

El ledger de validación QuakeFlow totaliza **43 eventos entre estas
cuatro entradas de arreglo/instalación** (arcata 15, monterey_bay 15,
ridgecrest_north 12, Stanford/East Foothills 1), todos con archivos
fuente distintos — verificado por `SELECT COUNT(*), COUNT(DISTINCT
event_file) FROM ledger` devolviendo `(43, 43)`. 8 archivos adicionales de
ridgecrest_north ya descargados quedan como reserva explícita sin correr,
pendiente de un nuevo pre-registro, no incorporados a esta muestra.

De los 43, 16 llevan un sismo real catalogado (magnitud, tiempo de
origen) contra el cual se puntúa el veredicto del motor; los 27 restantes
no tienen evento catalogado y sirven como chequeo de falsa alarma. De
esos 16, **13 vienen de una muestra pre-registrada antes de ver ningún
resultado** (`sample_plan.md`, sorteada el 2026-07-15, semilla fija y
registrada): los 3 eventos con verdad-terreno de arcata y 10 de los 12 de
ridgecrest_north. Los 3 restantes — East Foothills M4.1, y los 2 eventos
elegidos a mano de ridgecrest_north (M2.67 y M5.8) — son anteriores a esa
disciplina y se eligieron como candidatos plausibles, no sorteados a
ciegas. Dos de esos tres (M4.1 y M5.8) son los casos
retractados/re-examinados en §6; el tercero (M2.67) no lo es — su origen
elegido a mano se anota acá por completitud, no porque su propio outcome
(`MISS_BELOW_FLOOR`) haya necesitado re-examinación.

## 5. Resultados

### 5.1 La confiabilidad primero

La taxonomía de abajo tiene más de dos outcomes porque el sistema está
construido para reportar lo que realmente midió, no para colapsar cada
evento en un binario confirmar/rechazar — cada bolsillo es una salida
distinta e intencional, no una disculpa por la ausencia de un acierto
confirmado. Los dos números que más importan para un sistema operativo
van primero: sobre los 27 archivos sin evento catalogado, el sistema
produjo **27/27 rechazos correctos y 0 falsas alarmas**; sobre cada
evento real con verdad-terreno, produjo **0 casos de `MISS_SUPPRESSED`**
— ninguna instancia de una señal real detectada y después descartada mal,
el modo de falla que un sistema de monitoreo existe para evitar.

**Matriz final (N=16 eventos reales con verdad-terreno):**

| Outcome | n/N | Tasa | IC 95% Wilson |
|---|---|---|---|
| HIT | 0/16 | 0.0% | [0.0%, 19.4%] |
| HONEST_UNKNOWN | 8/16 | 50.0% | [28.0%, 72.0%] |
| HONEST_REGIONAL | 2/16 | 12.5% | [3.5%, 36.0%] |
| MISS_SUPPRESSED | 0/16 | 0.0% | [0.0%, 19.4%] |
| MISS_BELOW_FLOOR | 6/16 | 37.5% | [18.5%, 61.4%] |

Además, sobre los 27 archivos sin evento catalogado: **27/27
CORRECT_REJECTION, 0/27 FALSE_ALARM.**

`HIT` significa que un sismo local/regional real alcanzó
`SISMO_CONFIRMADO`. `HONEST_UNKNOWN` significa que el motor midió una
señal real pero débil y la reportó como tal en vez de sobre-confirmarla.
`HONEST_REGIONAL` significa que una llegada real, grande, espacialmente
masiva, fue reconocida como más allá de la apertura resoluble de este
arreglo en vez de forzada a un binario confirmado-o-suprimido.
`MISS_SUPPRESSED` es el outcome que significaría que el motor detectó
algo y lo descartó mal; ocurrió cero veces. `MISS_BELOW_FLOOR` significa
que ningún candidato de Nivel 0 apareció en la ventana de emparejamiento
causal para ese evento, consistente con que el evento esté bajo el piso
de detección medido de ese arreglo en vez de un bug de clasificación
(§5.2 mide ese piso directamente). La muestra es chica (N=16), así que
los intervalos de Wilson son correspondientemente anchos — reportados
como se midieron. La Figura 4 grafica cada evento con verdad-terreno como
magnitud vs. distancia (o apertura, donde no hay distancia disponible),
coloreado por outcome — la envolvente de detectabilidad empírica que
traza esta matriz.

![Figura 4: dispersión magnitud vs. distancia/apertura, coloreada por outcome.](../figures/fig6_detectabilidad.png)

### 5.2 La detectabilidad como propiedad de la instalación, no de la geometría

El recall de detección se midió directamente inyectando eventos
sintéticos a SNR conocido en el ruido de fondo real propio de cada
arreglo (no un modelo de ruido genérico) y registrando el SNR al cual el
recall cruza 50% (SNR50), con intervalos de confianza de Wilson 95% en
cada escalón (n=20 intentos/escalón):

| Arreglo | SNR50 |
|---|---|
| ridgecrest_north | 2.5 |
| monterey_bay | 1.6 |
| arcata | 8.00 |

El 8.00 de arcata contra el 1.6 de monterey_bay es un factor de 5.00×
(8.00 / 1.6 = 5.00) entre instalaciones con conteos de canal y
espaciados ampliamente comparables: la detectabilidad es una propiedad
del piso de ruido real de esa instalación específica, no de "cuántos
canales" o "qué tan largo es el arreglo". La implicancia práctica es lo
que hace que valga la pena medirla en vez de asumirla — SNR50 es lenguaje
de especificación. Un operador puede tomar la curva propia
recall-vs-SNR de una instalación propuesta y evaluar directamente si va a
ver la clase de evento que le importa, de la misma forma en que el
ruido equivalente de entrada de un sensor se usa para evaluar si puede
ver una señal dada, en vez de inferir la detectabilidad solo desde la
apertura y el conteo de canales.

![Figura 5: recall vs. SNR, ridgecrest_north, con IC 95% Wilson y SNR50 marcado.](../figures/fig6_recall_snr_ridgecrest_north.png)

![Figura 6: recall vs. SNR, monterey_bay.](../figures/fig6_recall_snr_monterey_bay.png)

![Figura 7: recall vs. SNR, arcata.](../figures/fig6_recall_snr_arcata.png)

### 5.3 Calibración condicionada a evidencia y validación cruzada

La calibración de umbral por arreglo (`calibrate.py`, condicionada a
evidencia: un barrido de umbral no puede romper un HIT confirmado
existente para ser propuesto) encontró un cambio que mejora — el umbral
de Nivel 0 de ridgecrest_north (4.0 → 8.0) — y no encontró ningún cambio
que mejore para arcata o monterey_bay, que conservaron sus defaults. Las
Figuras 8 y 9 muestran la validación cruzada de estos umbrales calibrados
contra los eventos reales con verdad-terreno, por arreglo: la curva
sintética recall-vs-SNR de §5.2, con cada evento real superpuesto en su
propio SNR observado.

![Figura 8: validación cruzada, arcata — curva sintética de recall con los eventos reales superpuestos.](../figures/fig7_validacion_cruzada_arcata.png)

![Figura 9: validación cruzada, ridgecrest_north.](../figures/fig7_validacion_cruzada_ridgecrest_north.png)

## 6. Los dos artefactos, como estudio de caso

Esta es la sección que lleva el argumento real del artículo. Dos eventos
pasaron cada uno por una confirmación aparente y fueron después
rechazados — de forma independiente, por razones físicamente distintas —
por guardas construidas específicamente porque estos dos eventos
expusieron los huecos que cierran.

### East Foothills, M4.1, 2017-10-10 (arreglo de Stanford)

Una pasada de validación temprana (P0) reportó `SISMO_CONFIRMADO` sobre
un bloque que abarcaba [398.2s, 449.0s] (50.8 s de ancho), 58.8% de
coincidencia (97.3% del arreglo), semblanza 0.292, velocidad aparente
8.000 m/s, 579/626 canales coherentes — y, porque el origen publicado por
el USGS caía en el segundo 401 de la grabación, esto se leyó como una
llegada 2.8 s *antes* del origen catalogado.

Dos problemas surgieron al re-examinar:

1. **Una no-medición de borde de grilla.** `apparent_velocity_mps=-8000.0`
   era exactamente `seismic_v_max_mps`, el borde de la grilla de
   velocidad barrida, no un óptimo interior — el mismo patrón exacto
   encontrado después en el M5.8 de Ridgecrest (abajo) en el borde
   opuesto.
2. **Fusión de eventos.** El bloque de 50.8 s era un bloque fusionado que
   abarcaba llegadas físicamente distintas — la re-segmentación por
   densidad, construida para arreglar este mismo modo de falla en
   Ridgecrest, aisló el núcleo denso real (`evt_0016_41033`,
   [410.3s, 423.8s], 13.5 s) al aplicarse retrospectivamente a este
   archivo. Ese núcleo arranca **9.3 s *después*** del origen catalogado
   — consistente con el tiempo de viaje P/S real a ~46 km de distancia —
   no antes. La lectura original de "2.8 s antes" era un artefacto del
   bloque fusionado que incluía ~12 s de actividad no relacionada previa
   a la llegada real.

Re-corrido bajo el pipeline actual (`run_on_stanford.py --dump-curve`
sobre los tres archivos SEG-Y originales, re-verificados idénticos byte a
byte al `.npz` convertido originalmente), el núcleo real aislado sigue
pegado al borde opuesto de la grilla (`v_app=-1.500 m/s =
seismic_v_min_mps`, semblanza 0.217, `boundary_pinned=True`), y su
estimación de velocidad de onset independiente (Theil-Sen: 163.200 m/s,
R²=0.00) discrepa de la semblanza en 200% — rechazada tanto por la
guarda de borde como por el guardián de concordancia entre estimadores,
de forma independiente. Cero veredictos `SISMO_CONFIRMADO` ocurren en
ningún lugar de los 900 segundos completos del archivo. Veredicto actual:
`POSIBLE_REGIONAL_EMERGENTE` (`HONEST_REGIONAL`), detectado 9.3 s después
del origen, SNR 15.9.

### Ridgecrest, M5.8, 2020-06-24 (QuakeFlow DAS, `ci39493944.h5`)

93.4% del arreglo (1.150 canales, 9.19 km de apertura) se disparó
simultáneamente durante una ventana de 78.9 s — inequívocamente real,
inequívocamente grande — con semblanza ≈0, porque a la apertura de este
arreglo relativa a la distancia del evento, la llegada es un tren de
ondas ancho y decorrelacionado en vez de un frente de onda plana
coherente. Antes del arreglo de taxonomía, el propio historial de bugs
de este proyecto llama a esto el peor modo de falla posible para un
sistema de monitoreo: el motor clasificó este evento
`INCOHERENTE_LOCAL_SUPRIMIDO` — suprimido, como si fuera un falso
positivo de un solo canal — porque la rama de supresión solo chequeaba
coherencia-canal-con-beam (que colapsa a ~0 para una llegada genuinamente
decorrelacionada), nunca la *extensión* del disparo. El arreglo
(`POSIBLE_REGIONAL_EMERGENTE`, supresión inalcanzable siempre que la
fracción de coincidencia o de extensión supere 0.5) corrigió la
clasificación.

Aplicando las guardas posteriores retroactivamente a este mismo evento:
su velocidad aparente (`-8.000 m/s = seismic_v_max_mps`) está pegada al
borde, y su estimación de velocidad de onset (`-10.282 m/s`) discrepa de
la semblanza (`-1.500 m/s`) en más de 200% — el guardián de concordancia
rechaza la confirmación de este evento de forma independiente de la
guarda de borde. Se descartó saturación de instrumento directamente
(solo 2/1.150 canales cerca del máximo de amplitud). Veredicto final:
`POSIBLE_REGIONAL_EMERGENTE` (`HONEST_REGIONAL`), detectado 17.1 s
después del origen, SNR 33.24.

### Por qué esto es el argumento, no un apéndice

Ambos eventos son sismos reales, grandes, inequívocos, para los cuales el
arreglo genuinamente no pudo resolver un moveout de onda plana limpio — y
en ambos casos, los propios chequeos internos del sistema lo atraparon,
usando dos mediciones estructuralmente distintas (un chequeo geométrico
de borde sobre un estimador; un chequeo de acuerdo entre dos estimadores
independientes) que coincidieron. Un sistema que retracta sus propios dos
"aciertos" titulares cuando sus propias guardas dicen que la velocidad no
es real no es un sistema afinado para producir confirmaciones — la
taxonomía existe precisamente para que "no puedo resolver esto" sea una
salida distinta, honesta, e igual de accionable que "confirmado" o
"ruido."

## 7. Límites conocidos

**La apertura acota la velocidad resoluble, en forma cerrada.** Un
slant-stack sobre un arreglo de apertura `L` (metros) muestreado a `fs`
Hz solo puede resolver una velocidad aparente si el retardo total a lo
largo del arreglo abarca al menos `k` muestras (default k=3) — por
debajo de eso, el corrimiento de canal-0-a-canal-N es sub-muestra e
indistinguible de infinito (moveout plano). Forma cerrada:
`v_app_max_resoluble = L · fs / k` (`coherence.v_app_max_resoluble`). La
Figura 10 barre esto directamente: sobre eventos sintéticos limpios con
velocidad real conocida, el error de medición se mantiene cerca de un
piso de ~2.4% (exacto: 2.36500596068128%, `figures/limite_apertura.json`)
a lo largo de un rango amplio de aperturas y velocidades, hasta que la
velocidad se acerca al techo geométrico de esa apertura, donde el error
crece fuertemente.

![Figura 10: error de medición de velocidad vs. velocidad real, barrido en distintas aperturas — el límite geométrico de resolución.](../figures/fig5_limite_apertura.png)

**La detectabilidad es por instalación, no una constante geométrica.**
El factor de 5.00× de §5.2 en SNR50 (arcata 8.00 vs. monterey_bay 1.6)
entre tres arreglos con conteos de canal ampliamente similares implica
que "¿este arreglo va a ver un evento dado?" no puede responderse solo
desde la geometría; hace falta medir contra el ruido real de esa
instalación.

**El gate de coincidencia masiva penaliza por construcción a los
arreglos de apertura muy grande.** `coincidence_fraction` mide la
fracción máxima de canales que disparan dentro de una ventana corta `W`
(`coincidence_window_s`, default 3.5s) — pero el moveout real de un
sismo cruzando la apertura completa `L` a velocidad aparente `v_app`
tarda `T = L / v_app` segundos, así que la fracción máxima físicamente
alcanzable está acotada por `~W/T` (canales disparando cada uno una vez,
repartidos a lo largo de todo el tiempo de cruce). Para Valencia
(L=41.45 km — el arreglo de mayor apertura con curva SNR50 completa
medida hasta ahora; el siguiente es arcata, 15.4 km), verificado con los
11 trials no-hit de SNR≥8 de la corrida real con
`--dump-trial-diagnostics`: en los 10/11 con velocidad correctamente
resuelta (`boundary_pinned=False`, `v_app` entre 2,200 y 3,400 m/s), W/T
predice 18.6%-27.7% contra 19.7%-30.0% observado en
`coincidence_fraction` — la aritmética cierra (diferencia ≤2.5 puntos
en los 10 casos). Los 10 caen bajo el piso `seismic_min_coincidence=0.30`,
exactamente donde el gate los descarta. No es una miscalibración del
umbral para cable submarino ni ruido de disparo disperso por canal: es
una propiedad geométrica de la métrica misma — a mayor apertura, mayor
`T` para una `v_app` dada, menor techo de coincidencia alcanzable con
una ventana `W` fija. Hallazgo declarado, Bloque A congelado: no se
cambia el umbral ni el código a partir de esto.

**La muestra es chica.** N=16 eventos reales con verdad-terreno da
intervalos de Wilson anchos — p. ej. la tasa real de HONEST_UNKNOWN
podría plausiblemente estar en cualquier lado entre 28% y 72%. Reportado
como se midió, al tamaño de muestra realmente disponible.

**Una pregunta abierta.** Ambos eventos reales "casi-fallidos" de §6 se
pegaron al *borde* de la grilla de velocidad barrida en vez de mostrar un
pico interior con error elevado, mientras que el barrido sintético de
arriba muestra picos interiores limpios con error bajo y acotado a lo
largo de un rango comparablemente amplio de velocidades y aperturas
reales. Por qué sismos reales fuertes en estos dos arreglos produjeron
curvas de semblanza que saturan en el borde en vez de picos
ruidosos-pero-interiores no está resuelto por nada en este dataset — la
pregunta abierta más interesante que esta validación sacó a la luz, no un
resultado zanjado.

## 8. Trabajo futuro

**Interferometría de fuente virtual desde el tráfico descartado —
monitoreo pasivo del subsuelo, no sismicidad inducida.** Para ser
explícitos sobre qué NO es esto: nada acá propone generar o disparar
sismos para calibrar nada. El tráfico vehicular ya está cruzando el
arreglo y hoy se descarta como ruido (`FUENTE_MOVIL_TRAFICO`) una vez que
se mide su trayectoria; la idea es puramente pasiva — usar una fuente que
ya existe para recuperar la función de Green empírica entre pares de
canales vía interferometría de función de correlación de ruido (NCF), la
técnica estándar de sismología pasiva para monitorear cómo cambia el
subsuelo mismo con el tiempo (estructura de velocidad, daño, saturación)
sin ninguna fuente activa en absoluto (`interferometry.py`, console
script `darkfiber-interferometry`). La validación sintética de este
camino pasa completa (`tests/test_interferometry.py`,
`test_interferometry_demo_passes_all_four_checks`, 4/4); la Figura 11
muestra el gather de fuente virtual resultante — la función de Green
empírica recuperada entre canales puramente por correlación cruzada de
tráfico que pasa, el patrón de moveout en forma de "V" característico de
una fuente virtual genuina.

![Figura 11: gather de fuente virtual desde ruido de tráfico, la función de Green empírica.](../figures/fig4_interferometria.png)

Sobre datos reales (Pawnee), un segmento de tráfico genuino recuperado
de dentro de la grabación (`evt_0006`, 263–349 s) produjo v=261 m/s,
R²=0.00 en una sola pasada de 86 s — inconcluyente a la cantidad de datos
reales disponible hasta ahora (la demo sintética necesitó 240 s para
converger), reportado como tal en vez de como una velocidad fabricada.
Extender esto a ventanas de tráfico real más largas es trabajo abierto.

**Una capa cognitiva de solo lectura, estrictamente separada del camino
del veredicto.** Una extensión separada, de alcance explícito
(`darkfiber_cortex`, instalación opcional, pre-registrada como su propio
plan) está diseñada alrededor de un principio no negociable: *la física
decide; la capa cognitiva interpreta, investiga y propone — nunca al
revés.* El pipeline determinista de veredictos (Nivel 0 → coherencia →
supervisor → catálogo) sigue siendo el arco reflejo: auditable,
determinista, sin verse afectado por si la capa cognitiva está siquiera
instalada. Cualquier capa de narración, generación de hipótesis o
propuesta de mejora se conectaría vía una conexión estrictamente de solo
lectura al ledger y al catálogo, escribiría solo en su propio almacén
separado, y nunca emitiría, modificaría ni bloquearía un veredicto — con
cada afirmación factual que haga obligada a citar un ID de fila real del
ledger, verificado por un validador determinista. Esto hereda por
construcción el propio principio de honestidad del motor central: cuando
una respuesta no está en el registro, la salida correcta es "no está en
el registro", no una adivinanza que suena plausible.

## 9. Reproducibilidad

- **Código y licencia**: `https://github.com/Sirkraven/darkfiber`
  (AGPL-3.0-or-later). **DOI concept** (siempre apunta a la última
  versión): `10.5281/zenodo.21383275`. **DOI de esta versión**:
  `10.5281/zenodo.21455992` (`CITATION.cff`).
- **Console scripts** (`pyproject.toml`, instalados vía
  `pip install -e .`): `darkfiber-validate` (suite sintética,
  `run_validation.py`), `darkfiber-stanford` / `darkfiber-quakeflow`
  (arneses de datos reales), `darkfiber-calibrate` (calibración de umbral
  condicionada a evidencia), `darkfiber-aperture` (barrido de
  apertura/geometría, §7), `darkfiber-interferometry` (§8),
  `darkfiber-convert-sgy` (SEG-Y de Stanford → NPZ), `darkfiber-snr-curve`
  (curvas de recall de §5.2), `darkfiber-replay` (replay paced en tiempo
  real para el camino de streaming, `CHANGELOG.md [Unreleased]`).
- **Tests**: `pytest` (102/102 pasando) y `darkfiber-validate` (29/29
  chequeos sintéticos) son ambos requeridos en verde antes de que
  cualquier cambio al árbol de decisión se considere validado;
  re-confirmado en esta misma pasada de documentación (`CHANGELOG.md`).
- **Datos**: ninguna de las grabaciones DAS reales viene en el
  repositorio. Los datos de Stanford se obtienen de PubDAS/Globus o del
  espejo de GitHub `FiberOpticEarthquakes` y se convierten localmente
  (`convert_stanford_sgy.py`); los datos de QuakeFlow DAS se obtienen a
  demanda desde `huggingface.co/datasets/AI4EPS/quakeflow_das`. Cada
  veredicto sobre datos reales en `validacion_real/scoreboard.md` es
  reproducible desde estas fuentes públicas más la muestra
  pre-registrada y fijada (`sample_plan.md`, `sample_plan_draw.json`,
  `sample_plan_universe.json`) que eligió qué archivos correr, fijada
  antes de ver ningún resultado.
- **Cada figura de este documento es regenerable** desde los scripts de
  arriba; ninguna está en control de versiones (`figures/` está excluida
  vía gitignore por diseño) y ninguna fue editada a mano.
- **Una nota bilingüe**: la prosa de este documento es inglesa; los
  títulos internos/etiquetas de eje de las figuras son en español,
  siguiendo la convención de idioma de trabajo propia del proyecto
  (código y API en inglés, las propias `explanations` del sistema y su
  código de generación de figuras en español, en `run_validation.py`,
  `run_on_quakeflow.py`, `characterize_aperture.py`, `snr_curve.py`, e
  `interferometry.py`). Producir variantes con etiquetas en inglés
  implicaría agregar un segundo camino de idioma al código de graficado
  en los cinco módulos sin alterar el default en español que usa el
  propio flujo de desarrollo del proyecto — evaluado como esfuerzo real,
  multi-archivo, no un re-etiquetado rápido, así que se declara acá en
  vez de intentarse en esta pasada. Cada leyenda de figura en el texto de
  arriba dice en inglés qué muestra la figura.

---

## Nota de revisión del autor

Este borrador fue escrito por Claude Code a partir del registro
propio comprometido del proyecto (`CHANGELOG.md`,
`validacion_real/NOTES.md`, `validacion_real/scoreboard.md`, el ledger de
QuakeFlow, y las salidas de `figures/`) según el andamio de trazabilidad
de `docs/writeup_data.md`. Dos ítems abiertos surgieron al extraer ese
andamio y se resolvieron por recuperación de datos, no volviendo a correr
el Bloque A ni ajustando ninguna afirmación para que cierre — ver
`docs/writeup_data.md`, "Open gates — resolution log," para el relato
completo (en corto: el SNR50 de monterey_bay existía en un snapshot de
ledger pre-A5 archivado y se restauró al ledger activo con su procedencia
original intacta, en vez de re-medirse). Nada de esto está enviado a
ningún lado. Alejandro revisa como el autor real antes de que nada vaya
a EarthArXiv o a cualquier otro medio externo.

**FASE F4.1 (pasada editorial, aprobada por el autor antes de empezar):**
el título, el resumen, la apertura de §2, y la estructura de §5 se
reordenaron y re-enmarcaron — el lector conoce la capacidad del sistema
antes que su resultado nulo, y el resultado nulo se enmarca como evidencia
del método, no como disculpa. Las referencias a figuras se renumeraron
secuencialmente (1-11, resolviendo una colisión de numeración previa) y
se barrió el lenguaje en busca de cobertura defensiva gratuita. Ningún
hecho, cifra, o la retractación de §6 cambió o se suavizó; cada cifra de
esta pasada está verificada contra `docs/writeup_data.md`, sección "FASE
F4.1 — editorial pass".

**FASE F4.2 (ajustes finales, aprobado por el autor para publicación):**
la autoría en la portada y en los metadatos ahora dice solo "Alejandro
Yucare Ríos, independent researcher" — el handle de GitHub vive
únicamente en la URL del repositorio en §9, no pegado al nombre
(`CITATION.cff` y el borrador de metadatos de EarthArXiv se actualizaron
igual). El resumen se partió en párrafos más cortos con sus tres cifras
titulares (cero falsas alarmas en los 27 archivos sin evento; cero casos
de una señal real detectada y descartada; cero confirmaciones limpias,
cada una explicada por una curva medida) destacadas para que se lean en
unos quince segundos. No se agregó ni quitó información. La construcción
del PDF pasó de comandos sueltos a `scripts/build_preprint_pdf.sh` +
`docs/preprint_cover.html` (versionados en git; el `.html`/`.pdf`
generado sigue excluido, igual que `figures/`), por reproducibilidad, ya
que esta era la segunda regeneración.
