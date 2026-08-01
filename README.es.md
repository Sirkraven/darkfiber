<p align="right"><a href="README.md">English</a></p>

# darkfiber

[![CI](https://github.com/Sirkraven/darkfiber/actions/workflows/ci.yml/badge.svg)](https://github.com/Sirkraven/darkfiber/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21383275.svg)](https://doi.org/10.5281/zenodo.21383275)
[![License: AGPL v3+](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)
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
git clone https://github.com/Sirkraven/darkfiber.git
cd darkfiber
pip install -e ".[figs]"
python -m darkfiber.run_validation --figs   # 9 escenarios sintéticos, 29/29 checks, ~11s
```

Cada módulo se puede correr como `python -m darkfiber.<módulo>` o con su
console script instalado (`darkfiber-<nombre>` — ver la tabla de
[Módulos](#módulos)). Por ejemplo, la otra demo sintética, con su propio
chequeo contra verdad-terreno:

```bash
python -m darkfiber.interferometry --demo --figs
```

**Para correr los tests** (no se instalan con el comando de arriba — hace
falta el extra `dev`):

```bash
pip install -e ".[dev,h5,figs]"
pytest
```

## Caja de honestidad — leé esto antes de confiar en un número de abajo

**Resultado principal: 0 sismos confirmados sobre 16 eventos reales con
verdad-terreno — y esa es la evidencia real de que el sistema funciona.**
Dos confirmaciones aparentes de pasadas de validación anteriores (un M4.1
y un M5.8, ambos reales, ambos grandes) fueron retractadas después por dos
guardas internas independientes — un chequeo de que un pico
semblanza-vs-velocidad no está simplemente pegado al borde de la grilla de
búsqueda (una no-medición), y la exigencia de que un segundo estimador de
velocidad, estructuralmente distinto, concuerde con el primero. Relato
completo, incluyendo exactamente cómo se atrapó cada uno: [el writeup
técnico](docs/writeup.md) §6 (borrador, en revisión del autor), o la
versión corta en [`CHANGELOG.md`](CHANGELOG.md) `[1.1.0]`.

**Qué está realmente validado:** 43 grabaciones DAS reales en 4
instalaciones (Stanford, Ridgecrest North, Arcata, Monterey Bay) — 16 con
un sismo real catalogado contra el cual medir (verdad-terreno
USGS/SCEDC), 27 sin evento catalogado como chequeo de falsa alarma (27/27
correctamente rechazados, 0 falsas alarmas) — más un caso telesísmico
cualitativo (Pawnee) validado por separado. Matriz completa en
"Resultados" más abajo; [`validacion_real/scoreboard.md`](validacion_real/scoreboard.md)
es la versión viva y regenerable, y [`validacion_real/NOTES.md`](validacion_real/NOTES.md)
es el relato completo.

**Sesgo de selección — mayormente pagado, no eliminado.** De los 16
eventos reales con verdad-terreno, 13 (los 3 de Arcata, y 10 de los 12 de
Ridgecrest North) son una muestra ciega pre-registrada, sorteada antes de
ver ningún resultado y comprometida a correrse tal cual salga
([`sample_plan.md`](sample_plan.md)). Los 3 restantes (East Foothills
M4.1, y los 2 eventos elegidos a mano de Ridgecrest North — M2.67 y el
M5.8 discutido arriba) son anteriores a esa disciplina y se eligieron a
mano como candidatos plausibles — señalado como tal, no mezclado en
silencio. Pawnee (el caso telesísmico cualitativo) también se eligió a
mano y queda fuera de los 16 por completo, como ya se aclaró arriba.

**Límite conocido — apertura vs. distancia:** un sismo real y fuerte puede
ser simultáneamente "demasiado lejano/emergente para que este arreglo mida
una velocidad" y "no un falso positivo". [`docs/adr/0002`](docs/adr/0002-regional-emergent-class.md)
y [`characterize_aperture.py`](src/darkfiber/characterize_aperture.py)
documentan esto con dos barridos sintéticos. La detectabilidad misma
(SNR50) se mide por instalación, no se asume desde la geometría: arcata
8.00 vs. monterey_bay 1.50, un factor de 5.33× — ver
[el writeup](docs/writeup.md) §5.2 y
[`docs/adr/0007`](docs/adr/0007-recall-as-curve-not-scalar.md).

**La muestra es chica.** N=16 eventos reales con verdad-terreno da
intervalos de Wilson 95% anchos en cada tasa de abajo — reportados como se
midieron, sin suavizar.

## Resultados — datos reales, no solo sintéticos

Cada veredicto sobre datos reales está cruzado contra una fuente
independiente (tiempo de origen del USGS/SCEDC, o la verdad-terreno
embebida en el dataset [QuakeFlow DAS](https://huggingface.co/datasets/AI4EPS/quakeflow_das))
— no solo contra los propios escenarios sintéticos de este repositorio.

**Matriz final (N=16 eventos reales con verdad-terreno, IC 95% Wilson):**

| Outcome | n/N | Tasa | IC 95% |
|---|---|---|---|
| `SISMO_CONFIRMADO` (HIT) | 0/16 | 0.0% | [0.0%, 19.4%] |
| `COHERENTE_DESCONOCIDO` (HONEST_UNKNOWN) | 8/16 | 50.0% | [28.0%, 72.0%] |
| `POSIBLE_REGIONAL_EMERGENTE` (HONEST_REGIONAL) | 2/16 | 12.5% | [3.5%, 36.0%] |
| MISS_SUPPRESSED (el motor lo vio y lo descartó mal) | 0/16 | 0.0% | [0.0%, 19.4%] |
| MISS_BELOW_FLOOR (bajo el piso de detección medido de ese arreglo) | 6/16 | 37.5% | [18.5%, 61.4%] |

Además, sobre los 27 archivos sin evento catalogado: **27/27
correctamente rechazados, 0 falsas alarmas.**

Detalle completo, incluyendo cómo se encontró y verificó cada evento
real — y, para dos de ellos, cómo se retractaron al fallar una guarda
independiente: [el writeup técnico](docs/writeup.md) (borrador) o
[`validacion_real/NOTES.md`](validacion_real/NOTES.md) (notas de trabajo
completas). Scoreboard vivo (se regenera desde el ledger, desglose por
arreglo): [`validacion_real/scoreboard.md`](validacion_real/scoreboard.md).

Validación sintética (verdad-terreno conocida,
`python -m darkfiber.run_validation --figs`): **29/29 checks** en 9
escenarios, incluyendo algunos armados específicamente para reproducir el
bug regional-emergente, la no-medición de borde de grilla, y la
discrepancia entre estimadores de arriba, para que ninguno pueda
regresionar en silencio.

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

| Archivo | Console script | Qué hace |
|---|---|---|
| `contracts.py` | — | Contratos Pydantic v2: configs, `TriggerEvent`, `CoherenceResult` con `explanations` auditables |
| `triage.py` | — | **Nivel 0**: STA/LTA vectorizado exacto (cumsum, LTA retardado) sobre toda la matriz |
| `coherence.py` | — | **Nivel 2**: slant-stack/semblanza, coincidencia, rastreo de fuentes móviles, beam apilado, picking P/S |
| `batching.py` | — | **Nivel 1**: `AsyncMicroBatcher` para inferencia ONNX en lotes (max 64 / 20 ms) |
| `catalog.py` | — | Catálogo vivo de firmas (SQLite): desconocidos recurrentes → clase nombrada sin reentrenar; también el ledger P2 y los perfiles/propuestas de arreglo P3 |
| `selftest.py` | — | Inyección sintética sobre buffers reales/vivos + gauge de recall |
| `synth.py` | — | Constructores de escenarios sintéticos físicamente correctos |
| `run_validation.py` | `darkfiber-validate` | Reproduce cada número de la tabla de arriba (`--figs` genera las figuras) |
| `run_on_stanford.py` | `darkfiber-stanford` | Adaptador CLI para H5/NPZ reales de Stanford |
| `convert_stanford_sgy.py` | `darkfiber-convert-sgy` | SEG-Y real de Stanford (PubDAS / `FiberOpticEarthquakes`) → NPZ |
| `run_on_quakeflow.py` | `darkfiber-quakeflow` | Arnés de validación contra QuakeFlow DAS, respaldado por el ledger |
| `characterize_aperture.py` | `darkfiber-aperture` | El límite apertura/distancia, caracterizado con dos barridos sintéticos |
| `calibrate.py` | `darkfiber-calibrate` | Propone ajustes de umbral con evidencia; nunca aplica en silencio |
| `interferometry.py` | `darkfiber-interferometry` | Interferometría de fuente virtual desde el ruido de tráfico descartado — `--demo` valida contra verdad-terreno conocida |
| `snr_curve.py` | `darkfiber-snr-curve` | Curva recall-vs-SNR contra el ruido de fondo real propio de cada arreglo, con IC de Wilson y SNR50 |

`contracts.py`/`triage.py`/`coherence.py`/`batching.py`/`catalog.py`/`selftest.py`/`synth.py`
son módulos de biblioteca, no CLIs independientes — se importan, no se corren.

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

AGPL-3.0-or-later — ver [`LICENSE`](LICENSE). Es una licencia copyleft de
uso en red: si corrés una versión modificada de este software como
servicio de red, tenés que poner el código fuente modificado a
disposición de los usuarios de ese servicio (AGPL §13). Ver el texto
completo de la licencia para los términos exactos.
