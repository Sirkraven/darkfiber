# Plan Fase 2 — Paper (technical note) · **Rev. 11**

**2026-08-06 (Rev. 11).** Existe el **borrador completo del manuscrito**
(`manuscrito_borrador_v1.md`). Cambia el estado de F2.G, se unifica la
formulación del piso del spread, y se agrega el punto de control de auditoría
para cuando Alex devuelva el texto reescrito.

**Rev. 10:** F2.D cerrado. **CI verde con evidencia**, cuatro
figuras generadas y bit-idénticas, **p-valores corregidos a enumeración exacta**.
Con esto **la parte técnica del paper está terminada**: lo que queda es escritura.
Ver `esqueleto_manuscrito_v1.md` para la guía de redacción.

**Rev. 9:** Cierra F2.B1: `fs` de stanford1_campus resuelto contra
el header, objeción de Valencia **retirada**, smoketest limpio. Con eso **la capa
de medición queda sin rojos**. Lo que sigue es trabajo de construcción, no de
descubrimiento. Rev. 8 había cerrado el sourcing: **8/8 ambientes y 7/8 interrogadores**
con fuente primaria. Trae tres hallazgos que reordenan §4.5 y §6, y una
reclasificación de `ridgecrest_north`. Rev. 7 había llegado a 6/8. Rev. 6 corrigió un diagnóstico equivocado de la Rev. 5 y cerró los dos
pendientes de QA contra el `QA_REPORT.md` vigente.
**Al adoptar esta rev., borrar `docs/plan_fase2_paper (1).md` y commitear una sola
copia canónica.**

**Corrección respecto de Rev. 5:** la Rev. 5 afirmaba que "los 3 arrays pre-F1.1"
nunca se escribió como lista de nombres. **Falso.** `QA_REPORT.md` §3.3 los
nombra: `monterey_bay`, `ridgecrest_north`, `arcata`. El defecto real es otro
(ver §3, D2).

Documento vigente. Pedir al iniciar chat nuevo junto a `docs/observaciones.md`,
`docs/array_geometry_table.md`, `docs/QA_REPORT.md`.

---

## §0 Encuadre y reparto

Technical note sobre un **protocolo de aceptación de sitio para detectabilidad
sísmica en DAS**. NO "motor de coherencia physics-first".
Alex escribe la prosa; Claude arma estructura, tablas, specs y verificación;
Claude Code ejecuta. **Ningún texto de manuscrito sale de Claude.**
**Destino: solo EarthArXiv.** ≤6,000 palabras, ≤5 figuras, ≤3 tablas.
**Resultado primario = SNR50 por sitio.** Correlaciones subordinadas.

---

## §1 Estado de verificación — la tabla que gobierna todo

Cada afirmación del paper con su estado real. **Nada pasa a prosa hasta estar en
verde.**

| Afirmación | Estado | Dónde |
|---|---|---|
| 8 SNR50 congelados | ✅ repo + verificación independiente | `series_robustness.py` |
| Invariante `(n_ch−1)·dx` 8/8 | ✅ repo | test |
| 4 coeficientes ρ | ✅ repo + independiente | módulo |
| 8 envolventes propagadas | ✅ repo + independiente | módulo |
| Cota A: 24/40,320, máx \|ρ\|=0.5952 | ✅ repo + independiente | módulo |
| Cota B (decisión de conjunto pendiente) | ⚠️ ver D2 | F2.A2 |
| Umbral crítico 0.7381 | ⚠️ correcto pero **heredado** | F2.A2 |
| Spread puntual 5.33× | ✅ trivial desde la tabla | — |
| **Cota del spread ≈3.50×** | ❌ **solo calculado en chat** | F2.A2 |
| pytest | ✅ 132/132 última corrida | — |
| Ambiente ×8 con fuente primaria | ✅ **8 de 8** | cerrado |
| Interrogador ×8 | ✅ **7 de 8** + un `—` explícito (ridgecrest) | cerrado |
| Gauge length ×8 | ⚠️ 6 de 8 | menor |
| Subgrupo urbano-telecom (5 arrays, 84.8%) | ✅ verificado | §4.5 |
| QuantX compartido best/worst | ⚠️ **por verificar contra metadatos** | §6 |
| `fs` de stanford1_campus | ✅ **header autoritativo: 100.0 Hz** | cerrado |
| Rango de canales de Valencia | ✅ **cerrado — objeción retirada** | cerrado |
| Consumidores por glob de `snr_curve_*.json` | ✅ ninguno | cerrado |
| `noise_exclusion` de stanford1_campus | ⚠️ **verificar** — pool de ruido de ventanas alrededor del M4.1 | F2.C |
| Metadatos sourceados volcados al repo | ❌ viven solo en el plan | F2.C |
| Auditoría de 6 figuras heredadas | ❌ sin empezar | F2.C |
| CI verde 3.10/3.11/3.12 | ✅ QA-06 cerrado, commit `e234cf9` | — |
| ¿CI cubre commits en `dev`? | ⚠️ verificado vía PR draft cerrado | F2.A2 |
| Párrafo de comparabilidad | ❌ no escrito | §3 |
| Auditoría de 6 figuras heredadas | ❌ sin empezar | F2.C |
| Bibliografía 20+ | ❌ sin empezar | F2.E |

**Verificado 2026-08-02, no repetir:**
- **V1.** Los 8 SNR50 se re-derivan exactos invirtiendo los IC Wilson publicados.
  **La serie es auto-verificable a mano.** Es propiedad del reporte, se declara.
- **V2.** Los 4 ρ se reproducen desde la geometría: `n_ch` +0.1905, `dx` 0.0000,
  apertura +0.3095, `fs` −0.3805.
- **V3.** `(n_ch−1)·dx` exacto en las 8 filas, incluida FOSSA (23,294.0 m).
- **V4.** Valencia identificada por aritmética: canal 2977 × 16.8 m = 50.0 km
  (primeros 50 km del ISLALINK Valencia–Palma); subrango 510–2977 = 2,468 ch.
- **V6.** **`fs` de stanford1_campus = 100.0 Hz**, leído del header binario real
  de los tres SEG-Y (`sample_interval_us = 10000`) con `read_binary_header` /
  `read_segy` del propio proyecto. Coincide con `array_profiles`. **PubDAS Tabla 1
  declara 50 Hz para "Stanford-1"**; los SEG-Y de Pawnee (2016) sí dan 50 Hz
  exacto, y `writeup.md` ya documentaba que la tasa varía por adquisición —
  50 Hz en la grabación de Pawnee 2016, 100 Hz en la de East Foothills 2017.
  Explicación consistente: son dos instantáneas temporales del mismo arreglo
  físico. **El header es la fuente autoritativa. Ver la nota de cita obligatoria
  en §5.1-nonies.**
- **V7.** **Rango de canales de Valencia: cerrado, objeción retirada.** El 510 no
  era una estimación del proyecto: es el número de canal tal cual figura en la
  fila 1 de `DAS-1-geometry-Valencia-undersea.csv` (2.468 filas, 1-indexado,
  provisto por el operador), y el código ya lo documentaba
  (`snr_curve.py:212`). El CSV trae **profundidad por canal**: canal 510 →
  0.221 m (recién sumergido); canal 547 → 7.20 m. **Ningún canal del subrango
  cae en tierra.** La estimación de 9,189 m / 16.8 m ≈ canal 547 supone traza
  recta y espaciado uniforme; el CSV del operador la domina.
- **V8.** **Ningún consumidor levanta `snr_curve_*.json` por glob.**
  `run_on_quakeflow.py`, `snr_curve.py` y `series_robustness.py` construyen
  siempre el nombre exacto desde un `array_id` explícito. El único glob era el
  `.gitignore`, ya corregido con enumeración.
- **V5.** Umbral crítico 0.7381 verificado por enumeración con aritmética
  racional: Σd²=22 → ρ=0.7381, p=0.04583; Σd²=24 → ρ=0.7143, p=0.05759.

---

## §2 Serie congelada

| Array | SNR50 | Envolvente | Bracket | Interrogador | Ambiente |
|---|---|---|---|---|---|
| monterey_bay | 1.50 | [1.0746, 1.9254] | 1→2 | OptaSense **QuantX** (GL 20.4 m) | Submarino — fibra oscura del cable MARS de MBARI, 52 km. **Profundidad muy variable ⇒ el ruido de fondo cambia a lo largo del cable** |
| FORESEE | 1.75 | [1.4529, 2.0000] | 1→2 | Silixa **iDAS-v2** (GL 10 m) | Fibra oscura bajo campus Penn State; conducto de hormigón enterrado 1–10 m |
| Stanford-2 | 1.769231 | [1.5153, 2.0000] | 1→2 | OptaSense **ODH-3** (GL 20 m) | Telecom, vía pública — Sand Hill Rd, Palo Alto |
| Valencia | 2.333333 | [2.0000, 3.0000] | 2→3 | Febus Optics **A1-R** (GL 30.4 m) | Telecom IslaLink; 9,189 m en tierra, 40,811 m bajo lecho marino |
| ridgecrest_north | 2.666667 | [2.3595, 3.0000] | 2→3 | `—` (no consta en la fuente) | **Telecom — fibra oscura subterránea en la ciudad de Ridgecrest** (reclasificado, ver §5.1-quinquies) |
| FOSSA | 4.50 | [3.9057, 5.0000] | 3→5 | Silixa **iDAS-v2** (GL 10 m) | Telecom ESnet. **Cuatro ambientes**: urbano, cultivo, I-5, corredor ferroviario |
| stanford1_campus | 7.727273 | [6.7508, 8.0000] | 5→8 | OptaSense **ODH-3** (GL 7.14 m) | Telecom, conductos bajo campus de Stanford; PVC con aire, **acoplamiento solo por gravedad y fricción** |
| arcata | 8.00 | [6.2306, 8.0000] | **punto medido** | Luna **QuantX** | Telecom — Vero Communications, Arcata↔Eureka |

**Fuentes:** Spica et al. 2023 (PubDAS) Tabla 1 y §§4.2–4.8 para FORESEE,
Stanford-2, Valencia, FOSSA y stanford1_campus · Romanowicz et al. 2023
(SRL 94(5):2348–2359, DOI 10.1785/0220230047) para monterey_bay/SeaFOAM ·
Li et al. 2021 (AGU Advances 2(2), DOI 10.1029/2021AV000395) y Yang et al. 2022
(GRL, DOI 10.1029/2021GL096503) para ridgecrest_north · McGuire et al. 2025
(SRL 96(4):2489–2503) + fichas USGS para arcata · Biondi et al. arXiv:2203.05932
como corroboración de stanford1_campus.

**El `—` de ridgecrest_north es deliberado.** Li et al. 2021 documenta el arreglo
(10 km de fibra, 1.250 canales, 8 m de espaciado, ciudad de Ridgecrest) pero no
declara el modelo de interrogador en el texto accesible. **Prohibido rellenarlo
por inferencia.** Nota de desambiguación: existen dos arreglos DAS de Ridgecrest
en la literatura; el de esta serie es el de respuesta rápida de 2019
(1.250 canales, 8 m), no el posterior de 80 km y 10 m.

**Verificaciones que salieron del mismo pase, sin costo:** los 2,137 canales de
FORESEE son exactamente los localizados por tap test; los 11,648 de FOSSA son
exactamente las posiciones de calidad utilizable; los 626 de stanford1 coinciden;
los 352 de Stanford-2 son los canales 399–750, la sección de mayor SNR entre el
Stanford Hospital y SLAC. **Ninguno de los cuatro conteos era arbitrario.**

`—` = pendiente de fuente primaria. **Prohibido rellenar desde documentación
propia del proyecto.**

Congelada 2026-07-30, reabierta 07-31→08-01 (QA-05), re-congelada 08-01.

---

## §3 Decisiones — con razón registrada

**D1 — El abstract lidera con el resultado medido y lo acota en la misma frase.**
Orden de hechos: (1) rango 1.50–8.00; (2) cociente entre extremos 5.33×;
(3) cota inferior bajo propagación conservadora.
*Razón:* el cociente entre extremos usa 2 de 8 puntos, y son los peor
restringidos (brackets de 3 pasos; stanford1 desde 0/20 exacto).
**✅ RESUELTO en F2.A2.** El módulo dio el valor exacto a precisión completa:
**3.5061978766918225**, máximo alcanzable 7.444480411580644.
**FORMULACIÓN ÚNICA Y VIGENTE: "al menos 3.51×".** Nada de "≥3.49×" ni "≥3.50×"
— las dos son formulaciones de transición ya superadas. Redondear a 3.50 es
correcto pero desperdicia precisión sin ganar seguridad. **Si aparece cualquiera
de las dos versiones viejas en documentación, es un número muerto**: mismo patrón
que costó el 5.00× frente al 5.33×.

**D2 — SUPERSEDED 3× — el diagnóstico de Rev. 5 era incorrecto.**

*Historia, no se borra.* v1 "las dos cotas en §4.3". v2 "eliminar la Cota B".
v3 "la especificación era ambigua". **Las tres mal, por razones distintas.**

**Lo que realmente pasa, verificado contra `QA_REPORT.md` vigente:**

1. **La especificación SÍ existe como lista.** §3.3 nombra `monterey_bay`,
   `ridgecrest_north`, `arcata`. Claude Code corrió exactamente eso.
2. **`QA_REPORT.md` se contradice a sí mismo.** §3.3 etiqueta a esos tres como
   "los 3 arrays de provenance pre-F1.1", pero §2.5 y QA-05 identifican a los de
   provenance incompleta como `monterey_bay`, `ridgecrest_north`,
   **`stanford1_campus`**. arcata entró por heterogeneidad de geometría, no por
   provenance. **La lista tiene un miembro distinto del que su etiqueta declara.**
3. **La etiqueta es lo que se propagó.** Al citarse en §10 de las instrucciones
   quedó como "los 3 arrays pre-F1.1", sin nombres. *La lista existía; se perdió
   al resumirse.* Ese es el modo de falla, y la regla correcta es: **cuando una
   especificación se cita en otro documento, se cita la lista, no la descripción.**
4. **El 0.6545 no reproduce igual.** Bajo la lista explícita de §3.3, dos
   implementaciones independientes dan **0.6506**. Probadas las cuatro
   convenciones de rango: Pearson/rangos promedio 0.6506 · fórmula Σd² con
   promedios 0.6012 · Σd² ordinal 0.6667 · Pearson ordinal 0.6667. **Ninguna da
   0.6545.** Es un error numérico genuino, no de especificación.

**Cota A → §4.3, robustez del resultado negativo. Sin cambios.**
24 de 40,320 ordenamientos, **máx |ρ| = 0.5952** (apertura), los 8 arrays libres
en su envolvente. No cruza. **Es la cota del abstract; el abstract no cambia.**

**Cota B → decisión abierta, ver §3-bis.** Dos opciones defendibles, con
consecuencias distintas. Ninguna se ejecuta sin decisión de Alex.

**Fe de erratas del 0.6545 — TRES lugares, no uno:**
- `QA_REPORT.md` §3.3 (el enunciado completo).
- `QA_REPORT.md` **resumen ejecutivo**, que repite "máximo ρ alcanzable en el
  peor caso: 0.65".
- `docs/observaciones.md` 2026-07-31, donde §3.3 dice que quedó registrado.

**Fe de erratas adicional, no relacionada al 0.6545:** `QA_REPORT.md` §3.2 sigue
diciendo que `ridgecrest_north` 2.50 "sigue vigente (no se re-mide)". Esa decisión
está **superseded** — se re-midió y 2.67 fue adoptado, como documenta
`array_geometry_table.md` con su propia fe de erratas del 2026-08-01. El
`QA_REPORT` nunca recibió esa corrección.

**Declarar que ambas cotas son enumeraciones exhaustivas, no muestreo.**

---

## §3-bis Decisión abierta — qué conjunto libera la Cota B

| Opción | Conjunto | Ordenamientos | máx \|ρ\| | ¿cruza? |
|---|---|---|---|---|
| **1** | los 3 de §3.3 (monterey, ridgecrest, arcata) | 336 | **0.6506** (fs) | no |
| **2** | los 4 pre-F1.1 (+ stanford1_campus) | 1,680 | **0.9698** (fs) | **sí** |

**Opción 1 — corregir el número y nada más.** Errata mínima: 0.6545 → 0.6506.
Preserva la especificación publicada y la cota sigue sin cruzar. Historia simple.
*Contra:* la lista de §3.3 excluye a `stanford1_campus`, que **sí** era uno de los
tres marcados por QA-05, e incluye a arcata, que no lo era. Es un conjunto
arbitrario heredado de un error de etiqueta, y eso queda en el registro.

**Opción 2 — liberar los cuatro valores pre-F1.1.** Es el conjunto honesto: los
cuatro estaban sin verificar antes de F1.1. Cruza el umbral, y **ese es el punto**
— describe un contrafáctico eliminado midiendo, y le pone número a la exigencia de
`input_files`: sin listas de archivos registradas, el resultado negativo central
no se habría podido sostener. Va a §4.6 (reproducibilidad), no a §4.3.
*Contra:* requiere prosa impecable, o un lector apurado lee "0.97, cruza" y
concluye fragilidad.

**D3 — Los ambientes se anclan a fuente primaria.** `—` explícito donde no
exista. **Prohibido rellenar desde `sample_plan_fase1.md` o
`snr50_extension_fase1.md`.** El caso arcata (McGuire et al. 2025) fija el
estándar.

---

## §4 Estructura del manuscrito

### §1 Introduction
Gap: la detectabilidad es propiedad del **sistema desplegado**, no derivable de
una hoja de specs. Contribución: (1) SNR50 con protocolo pre-registrado;
(2) taxonomía de abstención; (3) hallazgo negativo con cota exhaustiva.
**Párrafo obligatorio de no-reclamo:** slant-stack y semblanza son literatura
establecida. Su ausencia causó el rechazo previo.

### §2 Related work & positioning
Neidell & Taner 1971; Taner et al. 1979. **Lior et al. 2021**, JGR 126(3)
e2020JB020925. **Ugalde et al. 2021**, SRL 93(1):351–363.
**Rodriguez, Seguí, Ugalde et al. 2025**, IEEE JSTARS 18:19869–19883 (CQI).
Muñoz & Soto 2022. Williams et al. 2019. **SEAFOM MSP-02 / `pySEAFOM`**.
PubDAS (**Spica et al. 2023**, SRL 94(2A):983–998). **McGuire et al. 2025**,
SRL 96(4):2489–2503. **Romanowicz et al. 2023**, SRL 94(5):2348–2359 (SeaFOAM).
**Li et al. 2021**, AGU Advances 2(2) e2021AV000395 (Ridgecrest).
**Yang et al. 2022**, GRL, DOI 10.1029/2021GL096503 (variabilidad de sitio
sub-kilométrica sobre el arreglo de Ridgecrest).
**Biondi et al.** arXiv:2203.05932 (Stanford DAS array).

**Tabla de posicionamiento (va al manuscrito).** Cada celda verificable abriendo
el paper citado:

| | Lior 2021 | Ugalde 2021 | CQI 2025 | SEAFOM | **SNR50** |
|---|---|---|---|---|---|
| Unidad medida | cable | cable | **canal** | interrogador | **instalación** |
| ¿Requiere sismos reales? | sí | sí | sí + etiquetado | no | **no** |
| Verdad-terreno | modelo de fuente | — | inspección visual | banco | **por construcción** |
| Modelo-dependiente | sí | no | sí | no | **no** |
| Incluye el detector | no | no | no | no | **sí** |
| Unidades | magnitud/dist. | dB | score 0–1 | specs | **adimensional** |
| Instalaciones | 3 | 1 región | 4 | banco | **8, 4 ambientes** |
| Pre-registro | no | no | no | n/a | **sí** |

**Redactar en positivo, nunca como crítica.**

### §3 Method
- Pasos de SNR lineal adimensional (1,2,3,5,8,12,20), 20 trials/paso.
- **Estimación:** interpolación lineal entre escalones bracketantes
  (`interpolate_snr50`, QA-1.9). No hay IC sobre el interpolado; se reportan los
  IC Wilson de los escalones + envolvente. **Declarar la grilla no uniforme.**
- **[BLOQUEANTE] Párrafo de comparabilidad.** `noise_rms()` es por trial sobre su
  propia ventana (`selftest.py:126-131`, `synth.py:237,258`) ⇒ invariante a la
  escala del pool, por eso la serie es comparable pese a CV intra-pool 65–198% y
  spread de RMS hasta 60×. **Y por eso mismo no es convertible a sensibilidad
  física absoluta.** Riesgo si falta: "5.33×" se lee como "5.33× más sensibles".
- **Umbral Tier0 no uniforme** (monterey 4.0; ridgecrest 8.0). Refuerza que se
  mide el sistema desplegado *incluyendo su detector calibrado*.
- Invariantes: SNR lineal nunca dB; float ≥32; `(n_ch−1)·dx`; `fs`/`dx`
  explícitos; `min_len_s ≈ 13.6 + 0.001833·aperture_m`.

### §4 Results — orden fijo
1. Serie SNR50 (Tabla 1 + Fig 1), con D1.
2. Forma continua 1.50–8.00, no bimodal.
3. **Por qué la medición no es sustituible por specs** (Tabla 2 + Fig 2):
   4 ρ, umbral 0.7381, **Cota A**.
   *Nota obligatoria:* las re-mediciones de F1.1 no alteraron ningún rango; por
   eso los ρ son idénticos antes y después.
4. Hipótesis refutadas con predicción registrada de antemano.
5. **Ambiente — descriptivo, sin test.** Categórica, n=8: ningún test tiene poder.
6. **Reproducibilidad y provenance** (Tabla 3) + **Cota B** reencuadrada
   (solo si se adopta la Opción 2 de §3-bis).

### §5 Limitations — trece
1. No-monotonicidad en **Valencia y FOSSA**, mecanismos distintos verificados con
   aritmética (`v*≈3,553` dentro del rango vs `v*≈1,997` debajo).
2. Heterogeneidad de pools pre-F1.1.
3. Censura de coherencia (6/8 al piso, n efectivo 2); `2·dx` de 4.0 a 33.6 m.
4. Dtypes mixtos y cómo se verificó la comparabilidad.
5. Respuesta espectral no normalizada entre interrogadores.
6. Provenance: las 8 tienen `input_files`; **ninguna tiene `seeds`/`checksum`
   nativos**; `pipeline_hash` de FOSSA **inyectado post-hoc**.
7. n=8 solo detecta |ρ| ≥ 0.7381.
8. Mide el **sistema desplegado**, no el sitio aislado.
9. Resolución: 20 trials/paso; 7.73 y 8.00 no separables.
10. Grilla no uniforme; stanford1 interpola desde 0/20 cruzando 3 pasos.
11. Apertura nominal vs efectiva (Valencia, canales 2976–2977).
12. arcata: el 8.00 se midió sobre los 12 archivos de la geometría mayoritaria.
13. **[EL MÁS EXPUESTO] Inyección sintética, no campos de onda reales.** Los
    eventos reales fuertes saturan al borde del grid; los sintéticos dan picos
    interiores. **SNR50 no es un proxy validado de detectabilidad real.** Vía de
    falsificación: contrastar contra magnitud de completitud donde haya catálogo.

### §6 Discussion — la cadena de eliminación

**Estructura del argumento (esto ordena la sección):** el resultado negativo no es
una observación suelta, es una eliminación en cadena.

1. **No lo explican las variables de catálogo** — medido. `n_ch`, `dx`, apertura y
   `fs`, ninguno alcanza |ρ| ≥ 0.7381 con n=8, y la Cota A muestra que sigue sin
   alcanzarlo aun liberando los 8 dentro de su precisión de medición.
2. **No lo explica la categoría de ambiente** — medido, y **sin necesitar
   estadístico**: cinco de las ocho instalaciones son fibra de telecom y cubren
   el 84.8% del spread total.
3. **Posiblemente tampoco el interrogador** — el mejor y el peor de la serie
   comparten modelo. **Pendiente de verificación (§5.1-octies).**
4. **Lo que queda es el despliegue mismo.** El acoplamiento es el candidato con
   nombre.

**Límite honesto que va escrito:** con n=8 una eliminación nunca es exhaustiva, y
el paso 4 no está testeado.

**[ADVERTENCIA DE REDACCIÓN — no colapsar dos cosas distintas.]** "Ambiente" en
la Tabla 1 es una categoría gruesa (submarino / urbano / telecom). "Acoplamiento"
es cómo está físicamente sujeto ese cable, y **no coincide con la categoría**:
stanford1_campus y Stanford-2 son ambos telecom urbanos y tienen acoplamientos
completamente distintos — uno flota en un conducto de PVC con aire, el otro va
bajo una vía pública. Esa distinción es lo que permite que "el ambiente no
predice" y "el acoplamiento podría explicar" convivan sin contradecirse. Si en la
prosa quedan pegadas, un revisor va a decir que el paper se contradice.

**Evidencia externa que apoya la escala del efecto:** Yang et al. 2022 (GRL)
documentaron que **sobre el propio arreglo de Ridgecrest, en solo 8 km**, la
amplificación de sitio varía sustancialmente y correlaciona con la estructura
somera. Es literatura ajena mostrando que la variabilidad relevante ocurre a
escala sub-kilométrica dentro de una misma instalación.

**[POST-HOC, NO TESTEADA — etiquetar como tal.]** Con los ambientes sourceados
aparece un patrón: los dos peores SNR50 de la serie son `stanford1_campus` (7.73)
y `arcata` (8.00). Stanford-1 es el único de la serie cuyo acoplamiento está
documentado como **exclusivamente por gravedad y fricción** dentro de un conducto
de PVC lleno de aire. El mejor de la serie, `monterey_bay` (1.50), es submarino;
Valencia, también submarino, es cuarto.

Si el acoplamiento con el medio fuera el factor dominante, **explicaría el
hallazgo negativo**: ninguna variable de catálogo predice SNR50 porque la variable
que manda no figura en ningún catálogo. Converge con lo que dos interlocutores de
la industria señalaron por separado (§8).

**No está testeado y n=8 no alcanza para testearlo.** Va como hipótesis con vía de
falsificación declarada: clasificar las instalaciones por tipo de acoplamiento
documentado y repetir la prueba de rango con más instalaciones.

### §7 Data & code · §8 References
Complementariedad con SEAFOM. Trabajo futuro como hipótesis con vía de
falsificación. **La veta de adquisición no puede insinuar evidencia fuerte
(§5.3).** Zenodo DOI, repo AGPL, higiene de licencias, historia de
congelamiento. 20+ referencias formales.

---

## §5 Correcciones pendientes

**5.1 Ambiente e interrogador: 6 de 8 cerrados.** Faltan `monterey_bay` (no está
en PubDAS; candidato de fuente: Lindsey, Dawe & Ajo-Franklin 2019, *Science*,
cable MARS de Monterey Bay) y `ridgecrest_north` (tampoco en PubDAS; proviene de
`AI4EPS/quakeflow_das`).

**5.1-bis FOSSA no tiene un ambiente, tiene cuatro.** La etiqueta "Urbano" de la
tabla es incorrecta: PubDAS §4.3 documenta que la fibra atraviesa zona urbana,
tierras de cultivo junto al río Sacramento, la Interestatal 5 y por tramos un
corredor ferroviario muy usado. **Corregir en Tabla 1**, y usarlo para reforzar
el caveat 8: SNR50 mide el sistema desplegado, no un sitio homogéneo.

**5.1-ter Discrepancia de `fs` en stanford1_campus.** PubDAS Tabla 1 da **50 Hz**;
la tabla del proyecto dice **100.0 Hz**. Impacto medido: ρ(fs, SNR50) pasa de
−0.3805 a −0.3856; **ninguno cruza 0.7381 y la conclusión no se mueve**. Pero
`fs` es un proxy publicado y la invariante de §3 dice que sale del header o de
argumento explícito, nunca se asume. **Resolver leyendo el header** (F2.B1).

**5.1-quater Rango de canales de Valencia.** PubDAS §4.8: los primeros 9,189 m
están en tierra, o sea que el submarino empieza en el canal ~548
(9,189 / 16.8 = 547.0). El subrango de la tabla es 510–2977. Si el indexado
coincide, **38 canales (510–547) quedarían en tierra** dentro de un subrango
declarado submarino. Verificar la convención de indexado antes de concluir nada.

**5.1-quinquies `ridgecrest_north` estaba mal clasificado — corrección de Tabla 1.**
La tabla decía "Desierto/rural". Las fuentes primarias dicen que se accedió a
10 km de **fibra oscura subterránea de telecomunicaciones dentro de la ciudad de
Ridgecrest** y se convirtió en un arreglo de 1.250 canales a 8 m (Li et al. 2021;
Yang et al. 2022). La ciudad está en el desierto de Mojave, pero el cable es
telecom urbano enterrado. **Corregir.**

**5.1-sexies El subgrupo urbano-telecom pasa de 4 a 5 arrays — refuerza §4.5.**
Con la reclasificación de ridgecrest, **cinco de las ocho instalaciones** son
fibra de telecomunicaciones: Stanford-2 (1.77), ridgecrest_north (2.67),
FOSSA (4.50), stanford1_campus (7.73), arcata (8.00). Extremos 1.77 y 8.00 →
**4.52×, el 84.8% del spread total de 5.33×**. El cociente no cambia respecto del
subgrupo de 4 (ridgecrest cae en el medio); lo que cambia es que ahora son cinco
de ocho. **Es la forma directa del claim central y no necesita ningún
estadístico.**

**5.1-septies monterey_bay tampoco es un ambiente homogéneo.** Romanowicz et al.
2023: la profundidad del agua varía significativamente a lo largo del cable de
52 km, así que las características del ruido de fondo cambian con ella, con
niveles mucho más altos en aguas someras. **Segundo array, después de FOSSA,
donde una etiqueta única de ambiente es una simplificación.** Refuerza el caveat 8.

**5.1-octies [POR VERIFICAR] El mejor y el peor comparten modelo de
interrogador.** `monterey_bay` (1.50, el más sensible) usa un **QuantX de
OptaSense**; `arcata` (8.00, el menos sensible) usa un **QuantX de Luna**. Mismo
nombre de modelo, distinto prefijo corporativo. Si se sostiene, es evidencia
directa de que el interrogador no determina la detectabilidad del sistema
desplegado. **Hoy se apoya solo en el nombre del modelo en dos fuentes distintas
— verificar contra los metadatos de ambos datasets antes de escribirlo.** Es un
claim fuerte y no puede descansar en una coincidencia de nombre comercial.

**5.1-nonies [NOTA DE CITA OBLIGATORIA] `fs` de stanford1_campus.** En Tabla 1
del manuscrito, el valor **100.0 Hz** se cita explícitamente como **valor del
header del archivo utilizado**, no como valor del repositorio. PubDAS Tabla 1
declara 50 Hz para ese arreglo. Sin la nota, cualquiera que compare el paper
contra PubDAS ve 50 vs 100 y asume un error de transcripción. *El ambiente y el
interrogador sourceados siguen válidos: describen el arreglo físico, no la época
de adquisición.*

**5.1-decies [REGLA GENERAL, ganada en V7] La metadata del operador domina a la
aritmética sobre un resumen de paper.** Donde exista archivo de geometría o
metadata del instrumento, esa es la fuente autoritativa; una cifra derivada
dividiendo longitud por espaciado supone traza recta y espaciado uniforme y no
compite. Aplicar a las siete filas restantes antes de publicar cualquier
geometría.

**5.1-undecies [VERIFICAR] `noise_exclusion` de stanford1_campus.** Sus archivos
son `eastfoothills_segy` — extractos alrededor del **M4.1 de East Foothills**, el
evento cuya confirmación fue retractada. El pool de ruido proviene por tanto de
ventanas alrededor de un terremoto real, que es coherente entre canales, que es
exactamente lo que el detector busca. Si quedara energía del evento dentro de la
ventana de ruido, podría producir hits contabilizados como detección de la
inyección. `noise_exclusion` existe para esto y está en la provenance de las 8,
así que probablemente esté cubierto. **Se verifica igual porque
`stanford1_campus` es uno de los dos extremos que sostienen el 5.33×.**

**5.1-duodecies [MODO DE FALLA NUEVO, ocurrido en F2.D] Una verificación que
pasa cuando no hay nada que verificar.** `os.path.relpath()` falla en Windows
cuando la carpeta de salida está en otra unidad que el repo. El script de
comparación de bit-identidad devolvió **"OK" sobre archivos que no existían**:
dos cadenas vacías son iguales. Es la peor clase de bug —invisible y generador de
confianza falsa— y es la versión de "aceptar un test que importa sin ejercitar"
aplicada a una verificación. Detectado y corregido con fallback a ruta absoluta,
y la verificación se rehizo de forma que **falla ruidosamente si algo falta**.
**Regla que deja: toda verificación de igualdad debe fallar cuando el objeto
comparado no existe.** Entrada obligatoria en `observaciones.md`.

**5.2 Gauge length obtenido de regalo** en el mismo pase: FORESEE 10 m,
FOSSA 10 m, Stanford-2 20 m, stanford1 7.14 m, Valencia 30.4 m. No estaba en la
tabla y es relevante para el caveat 5 (respuesta espectral): el GL genera muescas
de strain nulo a múltiplos de la longitud de calibre.
**5.3 Veta de adquisición sobre número no reproducible:** el "pool mixto dio
5.90" está superseded Y NO REPRODUCIBLE; la reconstrucción dio **7.33**.
Comparación defendible **7.33 vs 8.00** — magnitud de 2.10 a **0.67**, dentro de
la resolución. Fe de erratas a §7-B de las instrucciones.
**5.4 Tabla 3, reproducibilidad — subsección propia.** 2 de 3 re-mediciones
cambiaron; reconstrucciones con mismos seeds no reprodujeron (arcata 5.90→7.33,
ridgecrest 2.50→2.67) con `git log` confirmando código idéntico. Un pipeline
determinista no reprodujo sus propias mediciones porque la lista de archivos no
estaba registrada.
**5.5 Fe de erratas sobre la regla de decisión** (solo contemplaba "cambió el
código"). Ejemplo de auto-corrección sobre el *método de decidir*.

---

## §6 Correcciones al documento de instrucciones

- **§10: "los 3 arrays pre-F1.1" es una descripción que reemplazó a una lista.**
  La lista existe en `QA_REPORT.md` §3.3. Debe citarse la lista, no la etiqueta —
  y la etiqueta de §3.3 además no coincide con su propio contenido.
- **§10: el 0.6545 se corrige según la opción elegida en §3-bis del plan.**
- **§7-B:** cita 5.90; debe decir 7.33.
- **§10:** "16 hallazgos" es **correcto** (14 + QA-15 + QA-16 del addendum
  2026-08-01) — retirar la objeción de la Rev. 5. "pytest 102/102" → **132/132**.
  "provenance completa 8/8" es correcto para `input_files`/`noise_exclusion`
  (QA-05 pasó de 3/8 a 0/8), pero `seeds`/`checksum` nativos siguen abiertos.
- **§10: CI verde se publica** — QA-06 cerrado, commit `e234cf9`.
- **§11:** el ambiente de arcata ya está sourceado; sigue figurando pendiente.

---

## §7 Bloques de trabajo

| Bloque | Contenido | Estado |
|---|---|---|
| **F2.A** | Envolventes + cotas al repo | ✅ commit `77f2ed6` |
| **F2.A2** | Corrección Cota B + spread + umbral + erratas | ✅ commit `d0fd074` |
| **F2.A3** | Tracking de JSON congelados + push + consolidación de planes | ✅ commit `46e28d7` |
| **F2.B** | Sourcing de ambientes e interrogadores | ✅ 8/8 y 7/8, en este plan |
| **F2.B1** | Diagnóstico `fs` / Valencia / glob | ✅ V6, V7, V8 |
| **F2.C** | Metadatos al repo + `noise_exclusion` + auditoría de 6 figuras | ✅ commit `5d2fc99` |
| **F2.D** | CI en `dev` + las 4 figuras | ✅ commits `cd6d63b`, `52a41e4` |
| **F2.E** | Bibliografía 20+ (13 verificadas, faltan 4 nombradas) | pendiente |
| **F2.F** | Hoja de 13 caveats | pendiente |
| **F2.G** | **Alex reescribe en su voz sobre `manuscrito_borrador_v1.md`** | ▶ **en curso** |
| **F2.G2** | Auditoría del manuscrito devuelto — ver §7-bis | pendiente |
| **F2.D** | Figuras nuevas, sidecar con `input_files` y hash | pendiente |
| **F2.E** | Bibliografía 20+ | pendiente |
| **F2.F** | Hoja de 13 caveats | pendiente |
| **F2.G** | Alex escribe la prosa | — |
| **F2.H** | Checklist EarthArXiv | — |

**Cerrados contra `QA_REPORT.md` vigente:** QA-06 cerrado con evidencia
(tres causas apiladas: trigger, extra `tdms`/QA-15, pin de `ruff`/QA-16;
3.10/3.11/3.12 verdes en las 5 etapas, commit `e234cf9`, PR draft #3 cerrado sin
mergear). Conteo real de hallazgos del gate: **16** (14 + QA-15 + QA-16).

**⚠ PENDIENTE OPERATIVO: el commit `52a41e4` (figuras) no está pusheado.**
Después de F2.A3 no se deja trabajo viviendo en un solo disco.

**Flanco cerrado 2026-08-06:** `ci.yml` ya dispara en `dev` (commit `cd6d63b`) y
la corrida es real. Lo que sigue es histórico: la verificación de CI de QA-06 se
había hecho abriendo un PR draft que luego se cerró. Si el trigger de `dev` sigue sin disparar, el commit `77f2ed6` de F2.A
**no pasó por CI** — se verificó en venv local 3.10, que no es equivalente.

---

## §7-bis Auditoría del manuscrito reescrito — qué se verifica al recibirlo

Alex reescribe a mano sobre el borrador y lo devuelve. **La transcripción manual
es donde más fallan los números.** El control es este, y se corre entero:

**Integridad numérica — lo que más falla.** Contrastar dígito a dígito contra
`series_robustness.json` y la Tabla 3 del borrador: los 8 SNR50, las 8
envolventes, los conteos por escalón, los 4 ρ, los 4 p exactos, el umbral 0.7381,
las dos cotas (0.5952 y 0.9698 con sus conteos de ordenamientos 24 y 1,680), el
spread 5.33× y su piso **3.51×**, el subgrupo telecom 4.52× / 84.8%, y el piso de
contaminación 4.57×. **Un dígito movido invalida la celda.**

**Presencia obligatoria — ausencia = no se envía.**
- Las **trece limitaciones**, ninguna omitida ni fusionada.
- El **párrafo de no-reclamo** de §1 (slant-stack y semblanza se citan, no se
  reclaman). Su ausencia fue causal del rechazo anterior.
- El **párrafo de comparabilidad** de §3.2, **con sus dos mitades**: comparable
  como cociente adimensional Y no convertible a sensibilidad absoluta.
- La **tabla de posicionamiento** de §2.
- Las **cuatro notas al pie de la Tabla 2** (`fs` del header, los dos `—`
  deliberados, la desambiguación de los dos arreglos de Ridgecrest, y que FOSSA y
  monterey_bay no admiten etiqueta única).
- La declaración de que **la serie es verificable a mano**.

**Riesgos de redacción — leer específicamente estos tres párrafos.**
1. **§4.6, la Cota B.** Verificar que el 0.9698 aparezca **después** de explicar
   qué se hizo, y que la frase de cierre diga que el contrafáctico fue
   **eliminado midiendo**. Si queda ambiguo, un lector apurado concluye
   fragilidad. Es el párrafo más delicado del manuscrito.
2. **§6.2, ambiente vs acoplamiento.** Verificar que la distinción quede
   explícita. Si las dos afirmaciones quedan pegadas, un revisor dice que el
   paper se contradice.
3. **§6.4, la veta de adquisición.** Verificar que **no insinúe evidencia
   fuerte**: la comparación defendible es 7.33 vs 8.00, diferencia de 0.67,
   dentro de la resolución de la serie.

**Ausencia obligatoria.** Ninguna afirmación de novedad sobre slant-stack,
semblanza, Theil-Sen o STA/LTA. Ninguna formulación que lea SNR50 como
sensibilidad absoluta.

**Corchetes a completar por Alex:** afiliación · URL del repositorio · DOI de
Zenodo · bibliografía hasta 20+ (faltan SEAFOM MSP-02, `pySEAFOM`, Wilson 1927 y
Spearman 1904).

---

## §8 Hilo Aragón Photonics — separado, fuera del camino crítico

Único entregable comprometido: documento de 2 páginas.
**Regla dura:** solo material **ya anclado al DOI público**. Si crece más allá de
dos páginas, es deriva.
Contenido: qué es SNR50 y qué no es; protocolo y pre-registro; serie con
envolventes; **las 13 limitaciones al frente**; tabla de posicionamiento; y la
declaración de que el preprint v1.1.0 lleva encuadre retirado.
**Diferido a septiembre:** vía científica vs. aplicada. **Conflicto registrado:**
asesoría continua remunerada con un fabricante es incompatible con emitir
certificaciones neutrales.
**Verificado:** HDAS no está en la serie; su banda de ventaja (sub-Hz a mHz) está
por debajo de la banda de análisis (1–24 Hz).

---

## §9 Reglas activas
Toda afirmación: medida con protocolo pre-registrado, citada, o hipótesis con vía
de falsificación. Estimación ≠ observación. Fe de erratas, no edición silenciosa.
Alcance congelado; vetas A y B después del envío. Bloque A no se toca.
**Toda especificación de un cálculo se escribe como lista explícita de nombres.
Y cuando se cita en otro documento, se cita la lista, no la descripción** — el
0.6545 se volvió irrastreable porque la lista de `QA_REPORT.md` §3.3 se resumió
como "los 3 arrays pre-F1.1" al propagarse a las instrucciones.

## §10 Backlog
Auto-sello de versión. `seeds`/`checksum` nativos. CLA. `ArrayGeometry` con
canales muertos y apertura efectiva. SRL y JOSS.
