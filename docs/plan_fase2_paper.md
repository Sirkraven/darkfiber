# Plan Fase 2 — Paper (technical note) · **Rev. 6**

**2026-08-02.** Rev. 6 corrige un diagnóstico equivocado de la Rev. 5 y cierra los
dos pendientes de QA contra el `QA_REPORT.md` vigente.
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
| Ambiente ×8 con fuente primaria | ❌ 1 de 8 | F2.B |
| Interrogador ×8 | ❌ 2 de 8 | F2.B |
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
- **V5.** Umbral crítico 0.7381 verificado por enumeración con aritmética
  racional: Σd²=22 → ρ=0.7381, p=0.04583; Σd²=24 → ρ=0.7143, p=0.05759.

---

## §2 Serie congelada

| Array | SNR50 | Envolvente | Bracket | Interrogador | Ambiente |
|---|---|---|---|---|---|
| monterey_bay | 1.50 | [1.0746, 1.9254] | 1→2 | `—` | `—` |
| FORESEE | 1.75 | [1.4529, 2.0000] | 1→2 | `—` | `—` |
| Stanford-2 | 1.769231 | [1.5153, 2.0000] | 1→2 | `—` | `—` |
| Valencia | 2.333333 | [2.0000, 3.0000] | 2→3 | FEBUS A1-R | `—` |
| ridgecrest_north | 2.666667 | [2.3595, 3.0000] | 2→3 | `—` | `—` |
| FOSSA | 4.50 | [3.9057, 5.0000] | 3→5 | `—` | `—` |
| stanford1_campus | 7.727273 | [6.7508, 8.0000] | 5→8 | `—` | `—` |
| arcata | 8.00 | [6.2306, 8.0000] | **punto medido** | Luna QuantX | Urbano, fibra telecom |

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
**⚠ Precisión pendiente:** la cota inferior da **3.4974×** con envolventes a 2
decimales y **3.5062×** con las de 4. Decir "al menos 3.50×" sobreafirma en el
primer caso. **El valor autoritativo sale del módulo a precisión completa
(F2.A2); hasta entonces, la formulación segura es "≥3.49×".**

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
PubDAS (Spica et al. 2023). **McGuire et al. 2025**, SRL 96(4):2489–2503.

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

### §6 Discussion · §7 Data & code · §8 References
Complementariedad con SEAFOM. Trabajo futuro como hipótesis con vía de
falsificación. **La veta de adquisición no puede insinuar evidencia fuerte
(§5.3).** Zenodo DOI, repo AGPL, higiene de licencias, historia de
congelamiento. 20+ referencias formales.

---

## §5 Correcciones pendientes

**5.1 Ambiente:** 1 de 8 con fuente primaria real. Ejecutar D3.
**5.2 Interrogador:** 2 de 8 (arcata Luna QuantX; Valencia FEBUS A1-R).
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
| **F2.A2** | Corrección Cota B + spread + umbral + erratas + tracking JSON | ▶ **siguiente** |
| **F2.B** | Sourcing: 7 ambientes + 6 interrogadores | pendiente |
| **F2.C** | Auditoría de 6 figuras heredadas (default: no sobrevive) | pendiente |
| **F2.D** | Figuras nuevas, sidecar con `input_files` y hash | pendiente |
| **F2.E** | Bibliografía 20+ | pendiente |
| **F2.F** | Hoja de 13 caveats | pendiente |
| **F2.G** | Alex escribe la prosa | — |
| **F2.H** | Checklist EarthArXiv | — |

**Cerrados contra `QA_REPORT.md` vigente:** QA-06 cerrado con evidencia
(tres causas apiladas: trigger, extra `tdms`/QA-15, pin de `ruff`/QA-16;
3.10/3.11/3.12 verdes en las 5 etapas, commit `e234cf9`, PR draft #3 cerrado sin
mergear). Conteo real de hallazgos del gate: **16** (14 + QA-15 + QA-16).

**Flanco abierto:** la verificación de CI se hizo abriendo un PR draft que luego
se cerró. Si el trigger de `dev` sigue sin disparar, el commit `77f2ed6` de F2.A
**no pasó por CI** — se verificó en venv local 3.10, que no es equivalente.

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
