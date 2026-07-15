# Validación sobre datos reales del arreglo DAS de Stanford

Los `.npz` grandes (matrices completas) no se versionan acá — son reproducibles
en minutos desde el SEG-Y crudo con `../convert_stanford_sgy.py`. Esta carpeta
solo guarda los resultados livianos (JSONL + consola) de cada corrida.

## Caso 1 — Pawnee M5.8 (telesismo), 2016-09-03

- **Fuente:** GitHub `eileenrmartin/FiberOpticEarthquakes`, carpeta `data/Pawnee/*.sgy`
  (22 archivos de 60s, 626 canales, 50 Hz).
- **Verdad-terreno:** USGS, M5.8, origen 2016-09-03 12:02:44 UTC, Oklahoma
  (~2500 km de Stanford — telesismo, no sismo local).
- **Resultado:** `resultados_pawnee_subrange.jsonl` / `resultados_pawnee_full.jsonl`.
  24 eventos `COHERENTE_DESCONOCIDO` (coherencia real de 70-100% del arreglo,
  semblanza baja ~0.01, sin velocidad limpia). **Cero `SISMO_CONFIRMADO`.**
- **Por qué es el resultado correcto:** un telesismo llega como onda superficial
  emergente, no como moveout de plano-onda local — el propio docstring de
  `run_on_stanford.py` lo anticipa. El motor está siendo honesto, no fallando.
- **Interferometría real:** se extrajo el tramo de tráfico real detectado
  dentro de esta grabación (`evt_0006`, 263-349s) y se corrió
  `interferometry.py --npz` sobre él (`gather_pawnee_traffic_real.npz`).
  Resultado: v=261 m/s, R²=0.00 — no alucina velocidad con una sola pasada
  de 86s (la demo sintética necesitó 240s para converger). Comportamiento
  honesto, no un fallo.

## Caso 2 — East Foothills M4.1 (sismo local), 2017-10-10 ✅

- **Fuente:** PubDAS (Globus, `Campus Stanford-1/Datos/2017/10/10/`), 3 archivos
  SEG-Y de 5 min cada uno (626 canales, **100 Hz** — la tasa de muestreo varió
  con el tiempo respecto a Pawnee), cubriendo 00:46:37–01:01:37 UTC.
- **Verdad-terreno:** USGS, M4.1, origen 2017-10-10 00:53:18 UTC, ~46 km de
  Stanford (sismo local real).
- **Resultado:** `resultados_eastfoothills.jsonl` →
  ```
  evt_0015_39822  [398.2s–449.0s]  canales 4–612
  → SISMO_CONFIRMADO
     Coincidencia 58.8% (97.3% del arreglo) | semblanza 0.292 | v_app=8000 m/s
     579/626 canales coherentes con el beam
  ```
- **Por qué es una prueba fuerte:** el origen real (USGS) cae en el segundo 401
  de la grabación. El veredicto del motor cubre el segundo 398.2–449.0 — arranca
  2.8s *antes* del origen real y lo contiene entero. Cruce contra una fuente
  independiente (USGS), no contra el propio dataset. Semblanza 0.292 es un
  orden de magnitud más alta que el caso telesísmico (~0.01), consistente con
  la física esperada: sismo local con moveout limpio vs. telesismo emergente.

## Caso 3 — Ridgecrest North (Hugging Face `AI4EPS/quakeflow_das`), dos magnitudes

- **Fuente:** `huggingface.co/datasets/AI4EPS/quakeflow_das`, carpeta `ridgecrest_north/data/`.
  A diferencia de PubDAS/Globus, acá **cada archivo `.h5` es un evento ya curado**
  (nombrado por su ID real de USGS/SCEDC), con metadata embebida
  (`magnitude`, `latitude`, `longitude`, `event_time`, `event_time_index`, `dt_s`,
  `dx_m`) — cero riesgo de huecos de grabación, cero necesidad de cruzar fechas
  a mano contra USGS. Descarga directa en una línea:
  ```python
  from huggingface_hub import hf_hub_download  # requiere también: pip install hf_xet
  hf_hub_download("AI4EPS/quakeflow_das", "ridgecrest_north/data/<event_id>.h5", repo_type="dataset")
  ```
  Formato: HDF5, dataset `data` (canales×tiempo), ya en microstrain/s (no hace
  falta derivar fase→strain-rate como con el SEG-Y de Stanford). 1150 canales,
  fs=100 Hz, dx=8 m.

- **M2.67** (`ci37280444`, 15km SSE de Lone Pine, CA, 2020-06-24 17:56:58 UTC):
  `resultados_ridgecrest_M2.7.jsonl` → `COHERENTE_DESCONOCIDO`, semblanza 0.007.
  Se verificó a mano que la energía SÍ sube ~30-40% justo en la muestra del
  origen real (índice 3000) vs. el ruido de fondo — el evento está presente,
  pero es débil (M2.67) y el motor correctamente no lo sobre-confirma.

- **M5.8** (`ci39493944`, 18km SSE de Lone Pine, CA, 2020-06-24 12:00:49 UTC):
  `resultados_ridgecrest_M58.jsonl` → 93.4% del arreglo disparado
  simultáneamente (78.9s de duración) pero semblanza ≈0 y
  **`INCOHERENTE_LOCAL_SUPRIMIDO`**, no `SISMO_CONFIRMADO`. Se descartó
  saturación del instrumento (solo 2/1150 canales cerca del máximo de
  amplitud). Explicación más probable: la apertura de este sub-arreglo es
  corta (~9.2 km) frente a la distancia real al epicentro, y un M5.8 real
  a esa distancia llega como tren de ondas S/superficiales ancho y
  emergente — parecido al caso Pawnee — no como un frente plano con
  moveout limpio. Es un buen ejemplo honesto de la limitación conocida:
  aperturas cortas relative a la distancia no bastan para "ver" la pendiente,
  incluso ante un sismo real fuerte.

## P0 — fix de taxonomía (POSIBLE_REGIONAL_EMERGENTE), verificado en campo

Implementado según `PLAN_v5.1_para_claude_code.md` (P0). Antes de este fix, el
M5.8 de Ridgecrest caía en `INCOHERENTE_LOCAL_SUPRIMIDO` pese a tener 93% del
arreglo energizado — autocontradictorio y el peor modo de falla posible para
un sistema de monitoreo. Causa raíz: la rama de supresión solo miraba
`n_coh` (canales coherentes CON EL BEAM), no la extensión real del disparo;
un tren emergente real tiene semblanza ~0 → `n_coh` ~0 → caía en supresión
aunque el arreglo entero estuviera energizado.

Fix: nueva clase `POSIBLE_REGIONAL_EMERGENTE`, con supresión ahora prohibida
por construcción cuando `coincidence_fraction` o `span_fraction` superan 0.5
(ver `coherence.py`). Se agregó también un fallback de moveout por onsets
(Theil-Sen sobre primeros cruces STA/LTA por canal) para intentar medir
velocidad incluso cuando la semblanza de forma de onda muere.

Validación sintética: escenario E (`E_regional_emergente` en
`run_validation.py`, onda de banda angosta 1-6Hz con envolvente compartida
+ fading independiente por canal) → 12/12 checks. Regresión de campo
(re-corridos con el fix, resultados en esta carpeta):

- `resultados_M58_P0.jsonl`: M5.8 Ridgecrest → **`POSIBLE_REGIONAL_EMERGENTE`**
  (antes: `INCOHERENTE_LOCAL_SUPRIMIDO`). Explicación cita apertura L=9.19 km.
- `resultados_M267_P0.jsonl`: M2.67 Ridgecrest → sigue `COHERENTE_DESCONOCIDO`
  (sin regresión, f_c=25% < 50% no activa la rama regional).
- `resultados_M41_P0.jsonl`: East Foothills M4.1 → sigue `SISMO_CONFIRMADO`
  en el mismo evento exacto (398.2-449.0s, sin regresión). Bonus: dos eventos
  que antes quedaban en `COHERENTE_DESCONOCIDO` ahora se reclasifican como
  `POSIBLE_REGIONAL_EMERGENTE` (etiqueta más honesta y accionable).

## P2 — arnés QuakeFlow + ledger de verdad-terreno

`run_on_quakeflow.py` corre el pipeline sobre `.h5` de QuakeFlow DAS
(Hugging Face) y persiste cada resultado en un ledger SQLite
(`quakeflow_ledger.db`, tabla `ledger`, UPSERT por `event_file` — no duplica
entre corridas, verificado). `../scoreboard.md` y
`../figures/fig6_detectabilidad.png` se generan solos a partir del ledger.

Los 3 casos reales de esta sesión, ya en el ledger:

| archivo | arreglo | magnitud | veredicto | outcome |
|---|---|---|---|---|
| eastfoothills_...npz | stanford1_campus | 4.1 | SISMO_CONFIRMADO | **HIT** |
| ci37280444.h5 | ridgecrest_north | 2.67 | COHERENTE_DESCONOCIDO | **HONEST_UNKNOWN** |
| ci39493944.h5 | ridgecrest_north | 5.8 | POSIBLE_REGIONAL_EMERGENTE | **HONEST_REGIONAL** |

Bug encontrado y corregido durante esta fase: cuando varios `TriggerEvent`
solapan la tolerancia horaria del origen real, elegir el de MENOR distancia
temporal agarraba un pico espurio de 1 canal en vez del blob real de todo
el arreglo (le "ganaba" al M5.8 real por estar más cerca en el tiempo). Fix:
elegir por MÁS canales disparados entre los candidatos que solapan.

El caso M4.1 viene de SEG-Y de Stanford (no del formato QuakeFlow), se
registró en el mismo ledger reusando el resultado ya calculado en P0
(`resultados_M41_P0.jsonl`) — ver `register` inline, no quedó como script
permanente porque es un caso puntual de fuente distinta.

## Cómo reproducir

```bash
# Vía PubDAS/Globus (SEG-Y, requiere cuenta Globus + navegar huecos de grabación):
python convert_stanford_sgy.py <carpeta_con_sgy> --out evento.npz
python run_on_stanford.py --npz evento.npz --key data --fs <fs_real> --dx 8.16 \
    --out resultados.jsonl

# Vía Hugging Face quakeflow_das (HDF5 ya curado por evento, sin huecos, sin cuenta):
pip install huggingface_hub hf_xet
python -c "from huggingface_hub import hf_hub_download; \
  hf_hub_download('AI4EPS/quakeflow_das', 'ridgecrest_north/data/<id>.h5', repo_type='dataset')"
python run_on_stanford.py --h5 <archivo>.h5 --dataset data --fs 100 --dx 8 \
    --out resultados.jsonl
```

## Lecciones para la próxima búsqueda

- El nombre de archivo trae el timestamp UTC (`cbt_processed_YYYYMMDD_HHMMSS.mmm+0000.sgy`)
  pero el filtro de Globus hace *prefix match* desde el inicio del string completo,
  no substring libre — hay que filtrar por `YYYYMMDD_HH` completo, no fragmentos sueltos.
- La tasa de muestreo (fs) **no es constante** en todo el archivo Stanford-1 (50 Hz
  en 2016, 100 Hz al menos en oct-2017) — siempre leer el header SEG-Y real, nunca
  asumir el valor del README.
- Hay huecos de grabación reales de horas/días completos en algunas fechas
  (2018-09-03 hora 02, 2018-06-11 hora 18, 2017-07-12 no se encontró) — no son
  errores de navegación, son huecos genuinos del archivo. Conviene verificar
  primero qué hay en un día (sin filtrar por hora) antes de perseguir un sismo
  puntual.
