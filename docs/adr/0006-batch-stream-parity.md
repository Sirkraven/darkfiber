# 0006 — Batch/stream parity as a design commitment

## Status
Accepted as a principle. **Not yet a running test** — documented honestly
below.

## Context
The Tier0 triage (`triage.sta_lta_ratio`) is implemented as an exact
vectorized computation (cumsum-based STA, delayed LTA) over a full
channel×time matrix. The micro-batching layer (`batching.py`) exists
specifically because the intended deployment shape is different: a live
DAS interrogator producing a continuous stream, analyzed in windows, with
ML inference batched for throughput (`AsyncMicroBatcher`). Those are two
different code paths in a live system, and the risk that motivates this
ADR is concrete: it is easy for an offline batch computation and its
windowed-streaming equivalent to *quietly* diverge — a boundary effect at
window edges, an LTA warm-up period handled differently, an off-by-one in
where a window starts — and for that divergence to show up only as a
slightly-wrong verdict on real traffic, with no test ever catching it.

## Decision
Batch analysis (`run_validation.py`, `run_on_stanford.py`,
`run_on_quakeflow.py` today) and any future streaming ingestion path must
produce **identical** `CoherenceResult` verdicts, within numerical
tolerance, for the same underlying data — whether that data is handed to
the pipeline as one array or as a sequence of overlapping streamed
windows. This is a correctness property to test explicitly once a
streaming path exists, not something to assume "should just work" because
the STA/LTA math is vectorized.

## Consequences
- **Honesty check**: as of this release, there is no streaming ingestion
  module in this repository — everything runs in batch/offline mode. The
  `latency_note` field on `SelfTestResult` ("offline batch; en streaming la
  latencia la fija la ventana de análisis") is the only place that
  acknowledges the gap today. This ADR exists so that gap has a name and a
  test obligation attached to it *before* a streaming path is built, not
  discovered after it ships with a silent divergence.
- When a streaming path is added, the acceptance bar is: same input data,
  batch and streamed, same verdicts. That test belongs next to
  `test_scenarios.py`, not bolted on afterward.
