# Pre-registro — Veta #1: largo de coherencia espacial del ruido de fondo vs. SNR50

*F1.6. Lectura pura de pools de ruido ya en disco (los mismos que produjeron
cada SNR50 medido). Cero descargas, cero corridas del pipeline de decisión,
Bloque A intacto. Fijado ANTES de mirar ningún resultado — ver
`docs/observaciones.md` para el hilo completo de discusión que llevó a cada
cierre de este documento. Aprobado por Alejandro en estructura + 6 cierres
(2026-07-30) antes de ejecutar.*

## 1. Métrica primaria

Largo de coherencia espacial del ruido de fondo, `L_c`, en **metros**
(unidad primaria — el spacing real va de 2m a 16.8m entre arrays, así que
"canales" y "metros" ordenan distinto; el fenómeno físico responde a
distancia, no a densidad de muestreo. Se reporta también en canales como
métrica secundaria, nunca como sustituto).

**Estimador: no-paramétrico**, primer cruce de la coherencia
magnitud-cuadrado (MSC) binneada por separación con el valor 0.368 (1/e),
interpolado linealmente entre los dos bines que lo bracketan (mismo patrón
que `interpolate_snr50` ya usa en el proyecto). El ajuste exponencial
`MSC(Δ)=exp(-Δ/L_c)` se reporta como métrica **secundaria** únicamente —
NO como estimador primario, porque asume intercepto=1 en `Δ=dx` (la MSC
real a la separación mínima suele estar bien por debajo de 1, y cuánto
varía por array no está establecido) y porque introduciría una bondad de
ajuste no declarada de antemano.

*Justificación contra el mecanismo del pipeline*: `coherence.py` mide
semblanza al apilar canales a lo largo de un moveout de prueba — es, en
esencia, coherencia inter-canal condicionada a una velocidad. Si el ruido
de fondo ya es espacialmente coherente a cierta escala, ese apilamiento
gana menos ventaja al stackear señal real por encima de un piso de ruido
que ya coopera consigo mismo espacialmente. Un `L_c` más largo predice,
por este mecanismo, un SNR50 más alto.

## 2. Banda y colapso en frecuencia

**1-24 Hz post-bandpass** — exactamente `synth.bandpass` (Butterworth
orden 4, fase cero vía `sosfiltfilt`, `lo=1.0, hi=24.0`), la misma función
que usa el resto del proyecto (`docs/adr/0004`). No banda ancha, no un
filtro reimplementado con otros parámetros.

La MSC es `γ²(f)` — un valor por frecuencia. Colapso a un número por par
de canales: **promedio plano (no ponderado) de `γ²(f)` sobre 1-24 Hz**.
Elegido sobre ponderar por potencia o tomar el pico: el propio bandpass
del pipeline trata la banda de forma uniforme (sin ponderación interna),
así que promediar plano es la elección más consistente con cómo el
pipeline ya usa esta banda — y evita un grado de libertad de más
(esquema de ponderación) no justificado de antemano. El pico se descarta
explícitamente por sesgar hacia arriba (es sensible a un solo bin ruidoso,
exactamente lo que promediar busca controlar).

## 3. Reducción de sesgo — N_d fijo, igual para los 8 arrays

**Hallazgo que motiva este cierre**: la MSC de canales NO correlacionados
tiene esperanza `1/N_d`, no 0 — con pocos segmentos promediados, el piso
de la MSC queda artificialmente alto, cerca o por encima del umbral 1/e.
Con pools de duración muy dispar entre arrays (Stanford-2: 4×~60s;
Valencia: 3×~601s; FOSSA: 20×60s; stanford1_campus: 840s en 2 tramos), un
`N_d` "lo que el pool dé" haría que `L_c` ordene por duración de pool
disponible, no por física del sitio.

**Verificado (lectura real de los pools pre-registrados de cada
SNR50, 2026-07-30, `gather_noise_sources` para los formatos hdf5/npz/segy,
metadata TDMS para FOSSA — sin cargar el pipeline de decisión)**:

| Array | Pool total (s) | Estructura de fragmentos | Segmentos de 5.0s no-solapados disponibles |
|---|---|---|---|
| Stanford-2 | 240.0 | 4 archivos × ~59.996s | 4 × floor(59.996/5)=11 → **44** |
| monterey_bay | 900.0 | 15 archivos × 60.0s | 15 × 12 → **180** |
| stanford1_campus | 840.0 | 2 tramos: 395.0s + 444.99s | 79 + 88 → **167** |
| FOSSA | 1200.0 | 20 archivos × 60.0s (verificado leyendo metadata TDMS, sin carga completa) | 20 × 12 → **240** |
| ridgecrest_north | 1320.0 | 24 tramos: 12×25.0s + 12×85.0s | 12×5 + 12×17 → **264** |
| FORESEE | 1200.0 | 2 archivos × 600.0s | 2 × 120 → **240** |
| Valencia | 1803.0 | 3 archivos × ~601.0s | 3 × 120 → **360** |
| arcata | 3900.0 | 8×120.0s + 7×420.0s | 8×24 + 7×84 → **780** |

**Fijado**: segmento = **5.0s** por segmento (Δf=0.2Hz de resolución
espectral en banda, más que suficiente para 1-24Hz), **N_d=30 fijo para
los 8 arrays** — el mínimo disponible (Stanford-2, 44) supera 30 con
margen (14 de sobra); ningún array se queda corto, así que no hace falta
reportar ningún array excluido o con N_d reducido. Cuando un array tiene
más de 30 segmentos disponibles, se usan los **primeros 30 en orden
cronológico de archivo** (regla determinística, sin aleatoriedad, sin
grado de libertad de selección) — se descarta el resto, incluso en
arrays con mucho más disponible (ej. arcata, 780 disponibles, usa 30).

Bias esperado de la MSC de fondo bajo ruido no correlacionado con
N_d=30: `1/30 ≈ 0.033`, muy por debajo del umbral 1/e=0.368 — ya no hay
confusión piso-de-sesgo vs. umbral de cruce.

## 4. Pools de ruido y channel_range

Exactamente los mismos pools que produjeron cada SNR50 (mismos archivos,
mismos segmentos de exclusión — automático vía `event_time_index` o
manual vía `--exclude-s`, según cada array), y el mismo `channel_range`
de cada corrida real: **Valencia 510-2977, Stanford-2 399-750**, el resto
completo. Cero re-selección de ventanas o archivos.

## 5. Bines de separación y submuestreo de pares

**Ancho de bin: 20 metros, fijo e idéntico entre los 8 arrays** —
elegido por encima del `dx` más grueso de la serie (Valencia, 16.8m) para
que todo array tenga al menos un par nativo por bin sin necesitar
interpolar por debajo de su propia resolución de canal.

**Submuestreo de pares** (necesario: FOSSA con 11,648 canales tiene
~67.8M pares totales, inviable calcular todos): para cada bin de
separación, si el número de pares elegibles supera **500**, se
subm-uestrea determinísticamente tomando 1 de cada `K` pares en orden de
índice de canal (`K = ceil(n_elegibles / 500)`, sin aleatoriedad, mismo
criterio para los 8 arrays) — nunca aleatorio, siempre reproducible desde
cero sin depender de una semilla.

## 6. Regla de piso (censura por abajo)

`L_c < 2·dx` es no-medible con el spacing de ese array (dx va de 2m a
16.8m — el piso difiere por array). **Fijado**: valores por debajo del
piso se registran como censurados y se les asigna el valor `2·dx` de ese
array para el cómputo de rangos de Spearman (no se excluyen).

**Justificación medida, no solo argumentada** (cierre del punto 6 de
Alejandro): en el caso degenerado donde los 8 arrays cayeran censurados
en el piso, el valor asignado sería `2·dx` en los 8 — y como
`rango(2·dx) = rango(dx)` (transformación monótona, Spearman es
invariante a eso), ese escenario degenerado da EXACTAMENTE la misma ρ que
correlacionar `dx` puro contra SNR50. Ya medido (ver tabla de proxies
abajo): `ρ=+0.0843, p=0.843` — lejísimos de significativo. La regla de
piso, en el peor caso posible, no fabrica una correlación espuria; en el
peor caso reduce a un proxy ya probado y refutado.

## 7. Regla de techo (censura por arriba) — simétrica a la de piso

`L_c` no es medible más allá de la apertura del propio array (no hay
separación observable más grande que eso). **Fijado**: si la MSC
binneada no cruza 0.368 en ningún bin dentro de `[0, apertura]`, se
registra como censurado por arriba y se asigna el valor de la
**apertura** de ese array para el cómputo de rangos (mismo criterio
conservador que el piso: subestima cuánto podrían diferir dos arrays
ambos censurados por arriba, no extrapola más allá de lo observado).
Ejemplo señalado por Alejandro: Stanford-2 tiene apertura 2,864.16m y en
1-24Hz las longitudes de onda (a velocidades aparentes plausibles) van de
~12m a ~3km — un `L_c` del orden de km quedaría censurado por techo ahí.

## 8. Dirección predicha y umbrales confirmatorios (n=8, exacto)

**Dirección predicha, declarada explícita**: correlación **POSITIVA** —
más coherencia espacial del ruido → el stacking ayuda menos → SNR50 más
alto.

Umbrales exactos por enumeración completa de las 8!=40,320 permutaciones
posibles para n=8 (verificado corriendo la enumeración, no tomado de
tabla): dos colas `|ρ|≥0.7381` (P=0.0458); una cola `ρ≥0.6429` (P=0.0481).

- **Confirmatorio**: `ρ ≥ +0.7381` (cruza el umbral de dos colas **Y**
  el signo es el predicho). Un `ρ` negativo fuerte que cruce ese mismo
  umbral en magnitud **NO confirma** la hipótesis — es un hallazgo sin
  explicación por este mecanismo, se reporta como tal, no como soporte.
  Esto es una **condición de validez**, no un ajuste post-hoc.
- **Sugestivo, no confirmatorio**: `0.5 ≤ |ρ| < 0.7381`, cualquier signo.
- El umbral de una cola (0.6429) se reporta solo como referencia — **nunca
  se usa como confirmatorio**, ni con el signo predicho.
- Por debajo de `|ρ|=0.5`: nulo, sin indicio.

## 9. Regla anti-p-hacking

UNA métrica primaria: `L_c` en metros, definición no-paramétrica (primer
cruce de MSC=0.368, bines de 20m, promedio plano 1-24Hz, N_d=30 fijo),
fijada antes de correr. Cualquier variante (el ajuste exponencial de §1,
la versión en canales, otro umbral de coherencia, otra banda) se reporta
como exploratoria — nunca sustituye a la primaria después de ver el
resultado.

## 10. Limitación declarada del mecanismo (no se resuelve acá)

El mecanismo teorizado (§1) requiere ruido coherente CON estructura de
velocidad DENTRO de la grilla de slant-stack barrida (1,500-8,000 m/s).
Ruido coherente a lag cero (lentitud 0, llega a todos los canales a la
vez) queda FUERA de esa grilla y no se apila con ella —
`L_c`, tal como está definido acá (coherencia MSC genérica entre pares,
sin condicionar a un moveout específico), no distingue entre coherencia
por lag-cero (irrelevante para el mecanismo) y coherencia con estructura
de velocidad dentro de la grilla (relevante). `L_c` es una aproximación
de primer orden de la cantidad físicamente relevante, no la cantidad
misma. Necesario tenerlo presente para interpretar tanto un confirmatorio
(¿es realmente el mecanismo de slant-stack, o solo correlaciona con algo
que también correlaciona con lag-cero?) como un nulo (¿ausencia real de
mecanismo, o `L_c` dominado por coherencia lag-cero que diluye la señal
relevante?) sin sobre-leer ninguno de los dos resultados.

## 11. Proxies ya refutados (contexto, no parte de este pre-registro)

Del hilo previo de `docs/observaciones.md` (2026-07-30), los cuatro
proxies de "hoja de specs" ya probados contra los 8 SNR50, ninguno
significativo:

| Proxy | ρ (Spearman) | p (aprox.) |
|---|---|---|
| n_ch | +0.0714 | 0.8665 |
| dx / spacing | +0.0843 | 0.8426 |
| apertura | +0.2381 | 0.5702 |
| fs | −0.3805 | 0.3524 |

Ninguno cruza `|ρ|=0.7381`. `L_c` es la primera métrica CONTINUA de
propiedad del ruido real (no de la hoja de specs del hardware) que se
prueba en esta serie.
