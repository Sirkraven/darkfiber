<p align="right"><a href="README.md">English</a></p>

# darkfiber

[![CI](https://github.com/Sirkraven/darkfiber/actions/workflows/ci.yml/badge.svg)](https://github.com/Sirkraven/darkfiber/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**Un motor de coherencia física para Distributed Acoustic Sensing (DAS).**
En el plano canal-tiempo, la pendiente de un evento ES su física: un sismo
real cruza el arreglo a km/s (moveout casi vertical), un vehículo a ~2-40
m/s (una franja diagonal lenta), y un transitorio de un solo canal no tiene
pendiente. Esto mide esa pendiente en vez de pedirle a un clasificador por
canal que adivine.

<p align="center">
  <img src="docs/figures/fig1_pendiente_es_fisica.png" width="850"
       alt="Tres paneles: moveout casi vertical para un sismo, franja diagonal lenta para un vehículo, y un solo punto sin pendiente para un transitorio local.">
</p>

## Quickstart

```bash
pip install -e ".[figs]"
python -m darkfiber.run_validation --figs   # 5 escenarios sintéticos, 12/12 checks, ~15s
```

## Resultados — datos reales, no solo sintéticos

Cada veredicto sobre datos reales de abajo está cruzado contra una fuente
independiente (tiempo de origen del USGS, o la verdad-terreno embebida en
el dataset [QuakeFlow DAS](https://huggingface.co/datasets/AI4EPS/quakeflow_das))
— no solo contra los propios escenarios sintéticos de este repositorio.

| Evento | Arreglo | Magnitud | Veredicto | Outcome |
|---|---|---|---|---|
| East Foothills, 2017-10-10 | Stanford-1 Campus | M4.1 | `SISMO_CONFIRMADO` | **HIT** — 2.8s antes del origen USGS |
| Pawnee, OK (telesismo), 2016-09-03 | Stanford-1 Campus | M5.8 | `COHERENTE_DESCONOCIDO` | correctamente no sobre-confirmado — la llegada emergente de un telesismo no es un moveout local |
| Ridgecrest, 2020-06-24 | Ridgecrest North | M2.67 | `COHERENTE_DESCONOCIDO` | señal débil, correctamente no sobre-confirmado |
| Ridgecrest, 2020-06-24 | Ridgecrest North | M5.8 | `POSIBLE_REGIONAL_EMERGENTE` | correctamente escalado, no suprimido — [fue un bug real](CHANGELOG.md), corregido en 1.0.0 |

Detalle completo, incluyendo cómo se encontró y verificó cada uno:
[`validacion_real/NOTES.md`](validacion_real/NOTES.md). Scoreboard vivo
(se regenera desde el ledger): [`validacion_real/scoreboard.md`](validacion_real/scoreboard.md).

Validación sintética (verdad-terreno conocida,
`python -m darkfiber.run_validation --figs`): **12/12 checks**, incluyendo
un escenario armado específicamente para reproducir el bug regional-emergente
de arriba (`E_regional_emergente`) para que no pueda regresionar en silencio.

## Caja de honestidad — leé esto antes de confiar en un número de arriba

**Qué está realmente validado:** 4 eventos reales en 2 arreglos
(Stanford-1 Campus, Ridgecrest North), cada uno cruzado contra una fuente
de verdad-terreno independiente. Es una muestra chica. La infraestructura
para hacerla crecer (`run_on_quakeflow.py`, el ledger, el scoreboard) ya
soporta decenas de eventos en los tres arreglos que QuakeFlow DAS pone a
disposición (Arcata, Monterey Bay, Ridgecrest) — el límite hoy es el
tamaño de la muestra, no la herramienta.

**Límite conocido — apertura vs. distancia:** un sismo real y fuerte puede
ser simultáneamente "demasiado lejano/emergente para que este arreglo mida
una velocidad" y "no un falso positivo". [`docs/adr/0002`](docs/adr/0002-regional-emergent-class.md)
y [`characterize_aperture.py`](src/darkfiber/characterize_aperture.py)
documentan esto con dos barridos sintéticos; para una apertura de ~9 km
(Ridgecrest North), la medición de velocidad por semblanza se degrada bien
antes de lo que predeciría el límite geométrico ingenuo de muestreo. No
extrapoles el comportamiento de sismo-confirmado de este sistema a
arreglos mucho más cortos que los validados acá sin volver a correr esa
caracterización.

**Deuda consciente — sesgo de selección:** los 4 eventos reales de arriba
no fueron una muestra aleatoria ciega. Cada uno se encontró buscando en
USGS/QuakeFlow un candidato plausible (magnitud, distancia, disponibilidad
de datos), lo cual sesga hacia eventos con más chance de dar un resultado
limpio. El caso regional-emergente M5.8 es el contraejemplo que mantuvo
esto honesto — NO fue el resultado que la búsqueda buscaba — pero la tasa
base de "qué tan seguido acierta este sistema sobre un evento real sin
seleccionar" todavía no se conoce. Hacer crecer el ledger con un lote sin
filtrar (no elegido a mano por dar buena historia) es el próximo paso
real, no un detalle de pulido.

**El recall hoy es un escalar, debería ser una curva.** `recall_gauge()`
reporta la tasa de detección sobre 5 inyecciones sintéticas. Ver
[`docs/adr/0007`](docs/adr/0007-recall-as-curve-not-scalar.md) sobre por
qué una curva recall-vs-SNR con intervalos de confianza es el objetivo
correcto, y por qué no hay que sobre-interpretar un escalar de 5 muestras.

## Arquitectura

```
arreglo crudo (canales × tiempo)
        │
        ▼
  Nivel 0 — triage.py           STA/LTA vectorizado (cumsum), toda la matriz a la vez
        │  99.98% del silencio nunca llega a lo que sigue
        ▼
  Nivel 1 — batching.py         micro-batching asíncrono para inferencia ML (opcional, ONNX)
        │
        ▼
  Nivel 2 — coherence.py        slant-stack/semblanza, coincidencia, regresión de
        │                       trayectoria → CoherenceAgent.analyze()
        ▼
  EventClass ── SISMO_CONFIRMADO / FUENTE_MOVIL_TRAFICO / POSIBLE_REGIONAL_EMERGENTE
             └─ COHERENTE_DESCONOCIDO / INCOHERENTE_LOCAL_SUPRIMIDO
        │
        ▼
  catalog.py (desconocido → recurrente → nombrado, por array_id)
  run_on_quakeflow.py → ledger → calibrate.py (propone, humano aplica)
```

## Módulos

| Archivo | Qué hace |
|---|---|
| `contracts.py` | Contratos Pydantic v2: configs, `TriggerEvent`, `CoherenceResult` con `explanations` auditables |
| `triage.py` | **Nivel 0**: STA/LTA vectorizado exacto (cumsum, LTA retardado) sobre toda la matriz |
| `coherence.py` | **Nivel 2**: slant-stack/semblanza, coincidencia, rastreo de fuentes móviles, beam apilado, picking P/S |
| `batching.py` | **Nivel 1**: `AsyncMicroBatcher` para inferencia ONNX en lotes (max 64 / 20 ms) |
| `catalog.py` | Catálogo vivo de firmas (SQLite): desconocidos recurrentes → clase nombrada sin reentrenar; también el ledger P2 y los perfiles/propuestas de arreglo P3 |
| `selftest.py` | Inyección sintética sobre buffers reales/vivos + gauge de recall |
| `synth.py` | Constructores de escenarios sintéticos físicamente correctos |
| `run_validation.py` | Reproduce cada número de la tabla de arriba (`--figs` genera las figuras) |
| `run_on_stanford.py` | Adaptador CLI para H5/NPZ reales de Stanford |
| `convert_stanford_sgy.py` | SEG-Y real de Stanford (PubDAS / `FiberOpticEarthquakes`) → NPZ |
| `run_on_quakeflow.py` | Arnés de validación contra QuakeFlow DAS, respaldado por el ledger |
| `characterize_aperture.py` | El límite apertura/distancia, caracterizado con dos barridos sintéticos |
| `calibrate.py` | Propone ajustes de umbral con evidencia; nunca aplica en silencio |
| `interferometry.py` | Interferometría de fuente virtual desde el ruido de tráfico descartado — `--demo` valida contra verdad-terreno conocida |

## Datos

Este repositorio nunca distribuye datos DAS. Para correr contra eventos reales:

```bash
pip install huggingface_hub hf_xet
python -c "from huggingface_hub import hf_hub_download; \
  hf_hub_download('AI4EPS/quakeflow_das', 'ridgecrest_north/data/<event_id>.h5', repo_type='dataset')"
python -m darkfiber.run_on_quakeflow --dir <carpeta> --array-id ridgecrest_north
```

Ver [`validacion_real/NOTES.md`](validacion_real/NOTES.md) para el camino
SEG-Y de Stanford (PubDAS vía Globus) como fuente alternativa, y para los
detalles encontrados al usar ambas (la frecuencia de muestreo NO es
constante a lo largo de la vida de un despliegue — siempre leerla del
header del archivo, nunca asumirla).

## Cómo citar

Ver [`CITATION.cff`](CITATION.cff).

## Contribuir

Ver [`CONTRIBUTING.md`](CONTRIBUTING.md) y [`docs/adr/`](docs/adr/) para
las decisiones detrás del diseño.

## Licencia

MIT — ver [`LICENSE`](LICENSE).
