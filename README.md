<p align="right"><a href="README.es.md">Español</a></p>

# darkfiber

[![CI](https://github.com/Sirkraven/darkfiber/actions/workflows/ci.yml/badge.svg)](https://github.com/Sirkraven/darkfiber/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.21383276.svg)](https://doi.org/10.5281/zenodo.21383276)
[![License: AGPL v3+](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](pyproject.toml)

**A physics-first coherence engine for Distributed Acoustic Sensing (DAS).**
In the channel-time plane, an event's *slope* is its physics: a real
earthquake crosses the array at km/s (near-vertical moveout), a vehicle at
~2-40 m/s (a slow diagonal streak), and a single-channel transient has no
slope at all. This measures that slope instead of asking a per-channel
classifier to guess.

<p align="center">
  <img src="docs/figures/fig1_pendiente_es_fisica.png" width="850"
       alt="Three panels: a steep near-vertical moveout for an earthquake, a slow diagonal streak for a vehicle, and a single point with no slope for a local transient.">
</p>

## Quickstart

```bash
git clone https://github.com/Sirkraven/darkfiber.git
cd darkfiber
pip install -e ".[figs]"
python -m darkfiber.run_validation --figs   # 9 synthetic scenarios, 29/29 checks, ~11s
```

Every module is runnable either as `python -m darkfiber.<module>` or via
its installed console script (`darkfiber-<name>` — see the
[Modules](#modules) table). For example, the other synthetic demo with a
known-ground-truth check of its own:

```bash
python -m darkfiber.interferometry --demo --figs
```

**Running the test suite** (not installed by the command above — needs the
`dev` extra):

```bash
pip install -e ".[dev,h5,figs]"
pytest
```

## Honesty box — read this before trusting a number below

**Headline result: 0 confirmed earthquakes out of 16 real, ground-truth-matched
events — and that is the actual evidence this system works.** Two apparent
confirmations from earlier validation passes (a M4.1 and a M5.8, both real,
both large) were subsequently retracted by two independent internal
guards — a check that a semblance-vs-velocity peak isn't just sitting on
the edge of the search grid (a non-measurement), and a requirement that a
second, structurally different velocity estimator agree with the first.
Full account, including exactly how each was caught: [the technical
writeup](docs/writeup.md) §6 (draft, under author review), or the short
version in [`CHANGELOG.md`](CHANGELOG.md) `[Unreleased]`.

**What's actually validated:** 43 real DAS recordings across 4 array
installations (Stanford, Ridgecrest North, Arcata, Monterey Bay) — 16
carrying a cataloged real earthquake scored against USGS/SCEDC ground
truth, 27 with no cataloged event as a false-alarm check (27/27 correctly
rejected, 0 false alarms) — plus a qualitative teleseism case (Pawnee)
validated separately. Full matrix in "Results" below;
[`validacion_real/scoreboard.md`](validacion_real/scoreboard.md) is the
live, regenerable version and [`validacion_real/NOTES.md`](validacion_real/NOTES.md)
is the full narrative.

**Selection bias — mostly paid down, not eliminated.** Of the 16
ground-truth-matched real events, 13 (Arcata's 3, and 10 of Ridgecrest
North's 12) are a pre-registered blind sample, drawn before any result
was seen and committed to run as-is regardless of outcome
([`sample_plan.md`](sample_plan.md)). The remaining 3 (East Foothills
M4.1, and the 2 hand-picked Ridgecrest North events — M2.67 and the M5.8
discussed above) predate that discipline and were hand-picked as
plausible candidates — flagged as such, not blended in silently. Pawnee
(the qualitative teleseism case) was also hand-picked and is outside the
16 entirely, as noted above.

**Known limit — aperture vs. distance:** a real, strong earthquake can be
simultaneously "too far/emergent for this array to measure a velocity" and
"not a false positive". [`docs/adr/0002`](docs/adr/0002-regional-emergent-class.md)
and [`characterize_aperture.py`](src/darkfiber/characterize_aperture.py)
document this with two synthetic sweeps. Detectability itself (SNR50) is
measured per installation, not assumed from geometry: arcata 5.9 vs.
monterey_bay 1.6, a 3.7× spread — see
[the writeup](docs/writeup.md) §5.2 and
[`docs/adr/0007`](docs/adr/0007-recall-as-curve-not-scalar.md).

**The sample is small.** N=16 ground-truth-matched real events gives wide
Wilson 95% confidence intervals on every rate below — reported as
measured, not smoothed over.

## Results — real data, not just synthetic

Every real-data verdict is cross-checked against an independent source
(USGS/SCEDC origin time, or the ground truth embedded in the
[QuakeFlow DAS](https://huggingface.co/datasets/AI4EPS/quakeflow_das)
dataset) — not just against this repository's own synthetic scenarios.

**Final matrix (N=16 ground-truth-matched real events, Wilson 95% CI):**

| Outcome | n/N | Rate | 95% CI |
|---|---|---|---|
| `SISMO_CONFIRMADO` (HIT) | 0/16 | 0.0% | [0.0%, 19.4%] |
| `COHERENTE_DESCONOCIDO` (HONEST_UNKNOWN) | 8/16 | 50.0% | [28.0%, 72.0%] |
| `POSIBLE_REGIONAL_EMERGENTE` (HONEST_REGIONAL) | 2/16 | 12.5% | [3.5%, 36.0%] |
| MISS_SUPPRESSED (engine saw it, discarded it wrongly) | 0/16 | 0.0% | [0.0%, 19.4%] |
| MISS_BELOW_FLOOR (below this array's measured detection floor) | 6/16 | 37.5% | [18.5%, 61.4%] |

Plus, on the 27 files with no cataloged event: **27/27 correctly rejected,
0 false alarms.**

Full write-up, including how each real event was found, cross-checked,
and — for two of them — retracted once it failed an independent guard:
[the technical writeup](docs/writeup.md) (draft) or
[`validacion_real/NOTES.md`](validacion_real/NOTES.md) (full working
notes). Live scoreboard (regenerates from the ledger, per-array
breakdown): [`validacion_real/scoreboard.md`](validacion_real/scoreboard.md).

Synthetic validation (known ground truth, `python -m darkfiber.run_validation --figs`):
**29/29 checks** across 9 scenarios, including ones built specifically to
reproduce the regional-emergent bug, the grid-boundary non-measurement,
and the cross-estimator disagreement above, so none of them can regress
silently.

## Architecture

```
raw array (channels × time)
        │
        ▼
  Tier 0 — triage.py            STA/LTA, vectorized (cumsum), whole matrix at once
        │  99.98% of silence never reaches anything downstream
        ▼
  Tier 1 — batching.py          async micro-batching for ML inference (optional, ONNX)
        │
        ▼
  Tier 2 — coherence.py         slant-stack semblance, coincidence, trajectory
        │                       regression → CoherenceAgent.analyze()
        ▼
  EventClass ── SISMO_CONFIRMADO / FUENTE_MOVIL_TRAFICO / POSIBLE_REGIONAL_EMERGENTE
             └─ COHERENTE_DESCONOCIDO / INCOHERENTE_LOCAL_SUPRIMIDO
        │
        ▼
  catalog.py (unknown → recurring → named, per array_id)
  run_on_quakeflow.py → ledger → calibrate.py (propose, human applies)
```

## Modules

| File | Console script | What it does |
|---|---|---|
| `contracts.py` | — | Pydantic v2 contracts: configs, `TriggerEvent`, `CoherenceResult` with auditable `explanations` |
| `triage.py` | — | **Tier 0**: exact vectorized STA/LTA (cumsum, delayed LTA) over the whole matrix |
| `coherence.py` | — | **Tier 2**: slant-stack/semblance, coincidence, moving-source tracking, stacked beam, P/S picking |
| `batching.py` | — | **Tier 1**: `AsyncMicroBatcher` for batched ONNX inference (max 64 / 20 ms) |
| `catalog.py` | — | Live signature catalog (SQLite): recurring unknowns → promoted to a named class without retraining; also the P2 ledger and P3 array profiles/proposals |
| `selftest.py` | — | Synthetic injection over live/real buffers + recall gauge |
| `synth.py` | — | Physically-correct synthetic scenario builders |
| `run_validation.py` | `darkfiber-validate` | Reproduces every number in the table above (`--figs` for figures) |
| `run_on_stanford.py` | `darkfiber-stanford` | CLI adapter for real Stanford H5/NPZ |
| `convert_stanford_sgy.py` | `darkfiber-convert-sgy` | Real Stanford SEG-Y (PubDAS / `FiberOpticEarthquakes`) → NPZ |
| `run_on_quakeflow.py` | `darkfiber-quakeflow` | Validation harness against QuakeFlow DAS, ledger-backed |
| `characterize_aperture.py` | `darkfiber-aperture` | The aperture/distance limit, characterized with two synthetic sweeps |
| `calibrate.py` | `darkfiber-calibrate` | Proposes threshold adjustments with evidence; never applies silently |
| `interferometry.py` | `darkfiber-interferometry` | Virtual-source interferometry from discarded traffic noise — `--demo` validates against known ground truth |
| `snr_curve.py` | `darkfiber-snr-curve` | Recall-vs-SNR curve against an array's own real background noise, with Wilson CIs and SNR50 |

`contracts.py`/`triage.py`/`coherence.py`/`batching.py`/`catalog.py`/`selftest.py`/`synth.py`
are library modules, not standalone CLIs — import them, don't run them.

## Data

This repository never ships DAS data. To run against real events:

```bash
pip install huggingface_hub hf_xet
python -c "from huggingface_hub import hf_hub_download; \
  hf_hub_download('AI4EPS/quakeflow_das', 'ridgecrest_north/data/<event_id>.h5', repo_type='dataset')"
python -m darkfiber.run_on_quakeflow --dir <folder> --array-id ridgecrest_north
```

See [`validacion_real/NOTES.md`](validacion_real/NOTES.md) for the
Stanford SEG-Y path (PubDAS via Globus) as an alternative source, and for
the gotchas found while using both (sampling rate is not constant across a
deployment's lifetime — always read it from the file header, never assume
it).

## How to cite

See [`CITATION.cff`](CITATION.cff).

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`docs/adr/`](docs/adr/) for
the decisions behind the design.

## License

AGPL-3.0-or-later — see [`LICENSE`](LICENSE). Note this is a network-use
copyleft license: if you run a modified version of this software as a
network service, you must make the modified source available to the
service's users (AGPL §13). See the license text for the exact terms.
