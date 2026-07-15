# Changelog

All notable changes to this project are documented here. Bugs found and
closed are listed alongside features — they're evidence of rigor, not
something to hide.

## [1.0.0] - 2026-07-14

Public release. Internally this was "v5.2": the taxonomy fix, the
aperture/distance characterization, the QuakeFlow validation harness, and
the calibration engine, packaged for publication.

### Added

- **New verdict class `POSIBLE_REGIONAL_EMERGENTE`** (`EventClass`). Massive,
  quasi-simultaneous, spatially-decorrelated arrivals (regional/distant
  events whose moveout the array's aperture can't resolve) now get their
  own honest label instead of being forced into "confirmed" or
  "suppressed". See `docs/adr/0002-regional-emergent-class.md`.
- Robust onset-velocity fallback (Theil-Sen regression on first STA/LTA
  crossings per channel) for emergent arrivals where waveform-shape
  semblance collapses. See `docs/adr/0005-theil-sen-onsets.md`.
- `characterize_aperture.py`: closed-form geometric resolution limit
  (`v_app_max_resoluble`) plus two synthetic sweeps (geometry, coherence)
  that turn "why didn't this array resolve that event's velocity" from a
  case-by-case mystery into a documented, reproducible curve.
- `run_on_quakeflow.py`: validation harness against
  [AI4EPS/quakeflow_das](https://huggingface.co/datasets/AI4EPS/quakeflow_das)
  (real, pre-curated DAS earthquake events with embedded ground truth). Each
  run is scored against the embedded origin (`OutcomeLabel`: HIT,
  HONEST_UNKNOWN, HONEST_REGIONAL, MISS_SUPPRESSED, FALSE_ALARM,
  CORRECT_REJECTION) and persisted to a SQLite ledger, UPSERT'd by file so
  repeated runs don't duplicate.
- `calibrate.py`: reads the ledger, PROPOSES threshold adjustments with
  evidence (which events would flip, from what to what), and refuses to
  silently apply anything — `--apply` is required, and it will not propose
  a change that breaks an existing confirmed HIT.
- Per-array profiles (`array_profiles` table): real noise floor (RMS
  percentiles) and a `synth_recall` measured by injecting synthetic events
  into that array's *actual* background noise, not a generic one.
  `CoherenceConfig.from_array_profile()` loads calibrated thresholds when
  available.
- Signature catalog gained `array_id` scoping: what's learned on one array
  no longer leaks into another array's unknown-signature clustering.
- Full package restructuring for publication: `src/darkfiber/`, `pyproject.toml`
  with console scripts, ruff + mypy clean, pytest suite, ADRs, bilingual
  README.

### Fixed

- **Critical**: the local-transient suppression branch could fire on events
  with high `coincidence_fraction`/`span_fraction` — i.e. it could suppress
  a real, large earthquake as a "single-point false positive" if its
  waveform-shape semblance happened to be low (true for real regional
  arrivals). Found on a real M5.8 event (Ridgecrest array, 93% of the array
  energized) that was being classified `INCOHERENTE_LOCAL_SUPRIMIDO` before
  this fix. Suppression is now unreachable whenever either fraction exceeds
  0.5 (see `docs/adr/0002`).
- Event-selection bug in the QuakeFlow harness: when multiple `TriggerEvent`
  candidates overlapped the real origin's tolerance window, picking the one
  with the smallest time gap could select a one-channel spurious pick over
  the real, array-wide event. Now selects by channel count among the
  overlapping candidates.
- **Found in the pre-publish clean-room test** (fresh clone, fresh venv, no
  prior knowledge of the project): the exact `Quickstart` command crashed on
  a clean Windows machine with `UnicodeEncodeError`, because the default
  console codepage (cp1252) can't encode the arrows every CLI prints. Every
  CLI entry point now calls `ensure_utf8_stdio()` first (`_cli_utf8.py`) —
  the demo commands work out of the box, no `PYTHONIOENCODING` workaround
  required.
- Also found in the same test: `run_validation.py` and
  `characterize_aperture.py` wrote their JSON summary into `figures/`
  *before* that directory was guaranteed to exist (it was only created
  inside the `--figs` figure-generation code path, and even then, after
  the JSON write). A completely fresh checkout without a pre-existing
  `figures/` directory crashed with `FileNotFoundError` — every previous
  test run in this project's history happened to reuse a directory created
  by an earlier run, which is exactly why a clean-room test with a fresh
  clone matters.

### Validated (real data, not synthetic)

- Pawnee M5.8 teleseism (2016, Stanford array, via `FiberOpticEarthquakes`
  SEG-Y) → `COHERENTE_DESCONOCIDO` — correct: a teleseism's emergent
  surface-wave arrival isn't a local-earthquake moveout, and the pipeline
  doesn't force it into one.
- East Foothills M4.1 (2017, Stanford array) → `SISMO_CONFIRMADO`, 2.8 s
  before the USGS-published origin time, on the correct beam.
- Ridgecrest M2.67 (2020, via QuakeFlow DAS) → `COHERENTE_DESCONOCIDO`
  (weak signal, correctly not over-confirmed).
- Ridgecrest M5.8 (2020, via QuakeFlow DAS) → `POSIBLE_REGIONAL_EMERGENTE`
  post-fix (was `INCOHERENTE_LOCAL_SUPRIMIDO` pre-fix — the bug above).

Full write-up: `validacion_real/NOTES.md`.

## [0.2.0] - 2026-07-13 ("v5.1", internal)

Real-data validation, no code changes to the decision tree. First contact
between the synthetic-only v5.0 pipeline and actual field data.

### Added

- `run_on_stanford.py`: adapter for real Stanford H5/NPZ (`--orientation`,
  NaN/dead-channel sanitization).
- `convert_stanford_sgy.py`: real SEG-Y (Stanford-1 Campus array, both the
  50 Hz 2016 acquisition and the 100 Hz 2017 acquisition — sampling rate is
  read from the header, never assumed) to NPZ.
- Real-data smoke tests against Pawnee (teleseism) and East Foothills
  (local M4.1) recordings.

### Discovered (not yet fixed here — see 1.0.0)

- The East Foothills M4.1 confirmed correctly. The Pawnee teleseism
  correctly stayed `COHERENTE_DESCONOCIDO`. Neither of those exposed the
  regional-emergent taxonomy gap — that took a genuinely regional-scale
  real event (Ridgecrest M5.8, added in 1.0.0) to surface.

## [0.1.0] - v5.0 (internal, predates this repository's history)

Initial physics-first coherence engine. Synthetic validation only, 9/9
checks green (`run_validation.py`).

### Fixed (pre-release audit, 8 issues closed before first internal use)

Carried over from the project's own "monolito sin grietas" audit, kept here
because they're part of the real history:

- (A) float32 overflow in STA/LTA → normalized by absolute maximum.
- (B) simultaneous events in disjoint array zones were merged into one →
  separated by channel-gap splitting (`split_gap_channels`).
- (C) semblance over envelopes had a ~0.6 DC floor that made the threshold
  decorative → mean removed over the central region before computing
  semblance.
- (D) semblance clamping against floating-point rounding past 1.0.
- (E) the signature catalog crashed under `asyncio.to_thread`
  (`check_same_thread`) → multi-threaded connection + WAL + lock.
- (F) the micro-batcher could hang futures forever under corrupted
  batches → fail-safe loop, verified against corrupted batches.
- (G) out-of-buffer writes in the synthetic generator → edge guards.
- (H) the channels×time vs time×channels heuristic failed on short clips
  → explicit `--orientation` + real-data hygiene (NaN→0, dead-channel
  report).

[1.0.0]: https://github.com/Sirkraven/darkfiber/releases/tag/v1.0.0
