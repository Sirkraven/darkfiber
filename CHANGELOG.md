# Changelog

All notable changes to this project are documented here. Bugs found and
closed are listed alongside features — they're evidence of rigor, not
something to hide.

## [Unreleased]

### Added

- **`replay.py` + `stream_runner.py` (C1, Bloque C/"operable")**: streaming
  path from files to a live-paced flow, with demonstrated batch/stream
  parity. `replay()` is a real-time-paced (or `--speed N` accelerated)
  async chunk generator over an H5/NPZ; `StreamRunner` consumes it
  incrementally and finalizes `(TriggerEvent, CoherenceResult)` pairs
  that match what `run_on_quakeflow.process_file` (batch) would produce
  on the same complete file. Design note: Tier0 is exactly causal, so a
  growing (never-evicting) buffer gives exact parity on that front for
  free; the bandpass (`sosfiltfilt`, zero-phase, ADR 0004) is the one
  non-causal step, handled by not finalizing an event until the buffer
  has enough trailing margin for the filter to have converged
  (`FINALIZE_SAFETY_MARGIN_S`, empirically measured on real data, not a
  theoretical bound) *and* the raw Tier0 block containing it (before any
  A5 density re-segmentation) has genuinely closed — see
  `stream_runner.raw_block_settled_end_s` for a real bug this caught and
  fixed during verification (see "Fixed" below). Permanent parity test:
  `tests/test_stream_parity.py` (synthetic, CI-safe, matches the
  project's synthetic-only CI policy).
- `scripts/verify_stream_parity_real.py`: manual, read-only (never opens
  the ledger) batch-vs-stream comparison against real local `.h5` files,
  for the parts of C1's acceptance that pytest can't cover with real
  data. Not run in CI.

### Fixed

- **Found verifying C1 against a real Ridgecrest file (M5.8)**: an early
  `StreamRunner` design finalized events as soon as there was quiet
  *after their own boundary*, without checking whether the raw Tier0
  block containing them (before A5's density re-segmentation) had
  actually closed. Since density re-segmentation re-examines a raw
  block's full extent every pass, an early, not-yet-closed raw block
  produced sub-event boundaries that later shifted once real closure
  happened — the earlier, wrong sub-events had already been finalized,
  producing duplicates absent from the batch reference (real symptom:
  `evt_0000_1021_*` in an early pass, `evt_0000_1045_*` once the
  enclosing block actually closed). Fixed in
  `stream_runner.raw_block_settled_end_s`, which requires the raw
  block's own closure within a bandpass-trusted prefix of the buffer,
  not just quiet after the extracted sub-event.
- **Discovered, not "fixed" (a property of the algorithm, not a
  streaming bug)**: for genuinely marginal `INCOHERENTE_LOCAL_SUPRIMIDO`
  (noise-floor, already-suppressed) candidates, even the *batch*
  function's own output is sensitive to how much of the file it's given
  — `bandpass(data[:, :n], fs)` for a real Ridgecrest file produces a
  different set of noise-floor candidates at different `n`, well past
  any reasonable settling margin, confirmed by scanning many `n` values
  directly (no streaming involved). Both interpretations agree these
  aren't real signals; `verify_stream_parity_real.py` requires exact
  parity on every other class and reports this class's differences as
  informational, not a failure.

### Known limits (declared, not silently shipped)

- **C1's "no lag at `--speed 10`" acceptance is only fully met for
  moderate arrays.** `StreamRunner` re-runs bandpass + Tier0 on the
  *entire* growing buffer every analysis pass (required for bandpass
  exactness — see "Added" above), so total cost across a stream grows
  roughly with the square of the number of passes for a fixed interval.
  Verified on two real files from different arrays: ridgecrest_north
  (1150 ch, 120s) processed in 17.5s of wall clock at `--speed 10`
  (expected 12s, ~1.5x over); arcata (3020 ch, 420s, one continuous
  420s-long event — a worst case for this growth pattern) took 244.6s
  (expected 42s, ~5.8x over), down from 1055.9s before raising the
  default `analysis_interval_s` from 2.0s to 10.0s (a real, measured
  4.3x improvement, but not a full fix). Batch/stream *verdict* parity
  held exactly in both cases regardless. A bounded ring buffer with real
  sample eviction (no re-growth of the recomputation window with file
  length) removes this cost pattern entirely — that's C3's job
  (continuous 24h operation), explicitly out of C1's scope (demonstrate
  parity), not a silently-shipped gap.

## [1.1.0] - 2026-07-20 — "Bloque A" (A1-A10)

Follow-up validation pass after 1.0.0/v5.2. Re-examined every
real-data confirmation the pipeline had produced, using two new
independent guards, and found that **none of them survive**: the project's
real-world track record goes from "1 confirmed local earthquake" to
"0 confirmed, all real detections correctly downgraded to honest
uncertainty." That is the intended failure mode of a system built not to
over-claim, and it's the headline result of this block. Full write-up:
`validacion_real/NOTES.md`; final scoreboard: `validacion_real/scoreboard.md`.

### Corrected

- **The 1.0.0 East Foothills M4.1 `SISMO_CONFIRMADO` claim (below, in the
  `[1.0.0]` section) does not hold and is retracted.** Two independent
  problems, found in sequence:
  1. **Fusion artifact (A5).** The originally reported block
     (`[398.2s, 449.0s]`, 50.8 s wide, said to start 2.8 s *before* the
     USGS origin) was a merged block spanning multiple physically distinct
     arrivals — the same failure mode A5's density re-segmentation was
     built to catch on Ridgecrest. Re-segmented under the current
     pipeline, the real dense core (`evt_0016_41033`, `[410.3s, 423.8s]`,
     13.5 s) starts **9.3 s *after*** the origin — consistent with real
     P/S travel time at ~46 km, not "before the earthquake happened."
  2. **Boundary solution, not a measurement (A9/A10).** That real core's
     apparent velocity (`-1,500 m/s`) is exactly `seismic_v_min_mps`, the
     edge of the search grid — semblance rises monotonically into the
     boundary with no interior peak, the same non-measurement pattern
     that had already invalidated the Ridgecrest M5.8 "detection." The
     independent Theil-Sen onset-velocity estimate (163,200 m/s, R²=0.00)
     disagrees with the semblance value by 200%, so the cross-estimator
     concordance gate (A10) rejects the confirmation too — two
     independent guards, same verdict.

  Current verdict for this event: `POSIBLE_REGIONAL_EMERGENTE`
  (`HONEST_REGIONAL`), `dt_detect_s=9.3`, `snr_observado=15.9`. See
  `validacion_real/NOTES.md`, Caso 2, and ADRs 0009-0011.

### Added

- **`characterize_aperture.py` extended; new `snr_curve.py` (A1)**: measures
  detection recall as a function of SNR against each array's *real*
  background noise (not synthetic-generic), replacing the old fixed-4-point
  self-test that had been silently measuring the wrong thing (found on
  Arcata: 0% recall reported at nominal SNR≈4.7-5.9 turned out to be a
  short-window bug in the SNR extraction itself, not insufficient signal).
  See ADR 0007.
- **Density re-segmentation of merged blocks (A5)**: a Tier0 block that
  exceeds `max_merged_block_s` is re-examined for internal high-density
  sub-blocks instead of being scored as one event. Fixes event fusion on
  Ridgecrest (hundreds of real seismic files, some minutes apart, were
  being merged into single mega-blocks) and, retrospectively, on the
  East Foothills M4.1 file above.
- **Causal, asymmetric ledger matching (A6)**: the QuakeFlow validation
  harness's window for matching a Tier0 candidate against a catalogued
  origin is now `[origin, origin + causal_margin_s]`, not a symmetric
  tolerance window — a real detection cannot start before the earthquake
  that caused it. See ADR 0008.
- **`MISS_BELOW_FLOOR` outcome, split from `MISS_SUPPRESSED` (A6)**: a
  real cataloged event with zero Tier0 candidates in the causal window
  (consistent with being below the detection floor) is now distinguished
  from a real event where Tier0 *did* fire and the candidate was lost or
  suppressed (a genuine classification bug). Previously both fell into
  one undifferentiated `MISS_SUPPRESSED` bucket. See ADR 0009.
- **Per-array Tier0 calibration, evidence-gated (A7-A8)**: `calibrate.py`
  gained a second mode (`--dir` + `--param tier0_threshold`) that proposes
  a per-array STA/LTA threshold from real noise-floor evidence, refuses to
  propose anything that would break an existing confirmed HIT, and (A8)
  sweeps a threshold grid against both real files and a synthetic check
  before proposing — Ridgecrest's `array_profiles` threshold (8.0, up
  from the 4.0 global default) is the one calibration that survived this
  bar; Arcata and Monterey Bay's sweeps found no improving candidate and
  kept the default.
- **Boundary-solution guard (A9)**: if a semblance-vs-velocity curve's
  argmax sits on the edge of the search grid rather than at an interior
  peak, that's flagged as `boundary_pinned=True` and can no longer, by
  itself, produce `SISMO_CONFIRMADO` — a monotonically-rising curve
  pinned to a grid edge means the true optimum is outside the swept
  range, not that 8000 m/s (or whatever the edge is) is the answer. Found
  on the real Ridgecrest M5.8 and, retroactively, the East Foothills M4.1.
  See ADR 0010.
- **Cross-estimator concordance gate (A10)**: `SISMO_CONFIRMADO` now also
  requires the independent Theil-Sen onset-velocity estimate to agree with
  the semblance-based velocity within tolerance. Catches the case the
  boundary guard alone cannot: an *interior* semblance peak that is still
  wrong (verified in `run_validation.py` scenario I, a synthetic
  "distant/fast" event whose semblance peak sits one step inside the grid
  boundary — `boundary_pinned=False` — but whose onset velocity disagrees
  by 194%). See ADR 0011.

### Fixed

- The pre-A9 QuakeFlow scoreboard classified `HIT` rows purely on
  `SISMO_CONFIRMADO` without re-running them through the boundary guard
  (their stored `metrics_json` predates the `boundary_pinned` field). The
  harness now flags any such row explicitly instead of silently reporting
  a HIT that was never checked against the new guard.

### Recovered

- **monterey_bay's SNR50 (1.6) and full recall-vs-SNR curve, lost from the
  active `array_profiles` row by a later, unrelated upsert.** Traced to an
  archived pre-A5 ledger snapshot (`updated`=2026-07-15T23:54:33 UTC, same
  measurement) where the value still existed with clean provenance;
  restored to the active ledger via `SignatureCatalog.upsert_array_profile()`
  (the real COALESCE code path, not a raw SQL write), leaving every other
  field of the row untouched, after taking a full backup of the active
  ledger first. Not a re-measurement — Bloque A stayed frozen throughout.
  `array_profile_history` had zero rows for `monterey_bay`, which rules
  out an intentional archive-then-clear via `archive_array_profile()` (A7)
  as the explanation; whatever wrote the later row most likely predates
  the current COALESCE-safe `upsert_array_profile`. Full account:
  `docs/writeup_data.md`, "Open gates — resolution log."
- **Debt registered, not yet fixed**: nothing currently tests that an
  `array_profiles` upsert cannot silently drop `recall_curve_json`/`snr50`
  without going through `archive_array_profile()` first — the loss above
  went undetected until the writeup's traceability pass caught it by hand.
  A regression test for "an upsert never nullifies a previously-measured
  field without an `array_profile_history` row explaining why" belongs in
  the v1.2 backlog.

### Validated (real data, not synthetic) — supersedes the `[1.0.0]` section below

- Pawnee M5.8 teleseism → `COHERENTE_DESCONOCIDO`, unchanged (Bloque A
  didn't touch this file; the emergent-surface-wave read was already
  correct).
- East Foothills M4.1 → `POSIBLE_REGIONAL_EMERGENTE` (was `SISMO_CONFIRMADO`
  in 1.0.0 — see "Corrected" above).
- Ridgecrest M2.67 → `COHERENTE_DESCONOCIDO`, unchanged.
- Ridgecrest M5.8 → `POSIBLE_REGIONAL_EMERGENTE`, unchanged verdict, but
  now additionally passes through the A9/A10 guards (it was the real
  event that motivated building them) instead of relying on the
  taxonomy fix alone.
- **Net result across all real, ground-truth-matched events validated to
  date (N=16, `validacion_real/scoreboard.md`): 0/16 `HIT`.** 8/16
  `HONEST_UNKNOWN`, 2/16 `HONEST_REGIONAL`, 6/16 `MISS_BELOW_FLOOR`, 0/16
  `MISS_SUPPRESSED`. Plus 27/27 `CORRECT_REJECTION` on files without a
  catalogued event, 0/27 `FALSE_ALARM`. Sample size is small and the
  Wilson 95% CIs are correspondingly wide — reported as-is, not dressed up.

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
  **⚠️ Retracted — see `[1.1.0]` above.** This was a fusion artifact
  (the "2.8 s before" block was merged with unrelated prior activity) and
  a boundary-solution non-measurement; re-examined in Bloque A (A5/A9/A10),
  current verdict is `POSIBLE_REGIONAL_EMERGENTE`.
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

[1.1.0]: https://github.com/Sirkraven/darkfiber/releases/tag/v1.1.0
[1.0.0]: https://github.com/Sirkraven/darkfiber/releases/tag/v1.0.0
