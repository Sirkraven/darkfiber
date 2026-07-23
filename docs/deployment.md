# Deployment (C3): on-prem / edge

*Cloud IaC is explicitly out of scope for this pass — per
`PLAN_CIERRE_Y_LANZAMIENTO.md`'s own C3 delta, that only gets built if
the author confirms cloud scope. This document covers the default:
running on the operator's own hardware, which is the only mode actually
needed for a pilot (see `docs/pilot_kit.md`).*

## Requirements

- Docker + Docker Compose (v2, the `docker compose` subcommand).
- The pipeline's own measured footprint: pure NumPy/SciPy, no GPU. Tier 0
  throughput was benchmarked at ~570× real time on a 4-core laptop CPU
  (see `docs/pilot_kit.md` for the exact number and how to reproduce it).
  This has **not** been load-tested for true 24/7 operation against a
  busy real array yet — see "Known limits" below before sizing hardware
  for a specific installation.
- Enough disk for the SQLite ledger + rotated logs + backups (all small
  relative to the DAS recordings themselves — none of the raw waveform
  data is duplicated into the ledger, see
  `docs/pilot_data_agreement_template.md`).

## Quickstart

```bash
mkdir -p data
cp installation.example.yaml data/installation.yaml
# edit data/installation.yaml: array_id, geometry, data_source.path
# put the source .h5/.npz file(s) where data_source.path points, under ./data/
docker compose up
```

- Pipeline healthcheck: `http://localhost:8080/healthz` (200 while
  actively processing, 503 if stale) and `http://localhost:8080/status`
  (JSON: uptime, files/chunks/verdicts processed, last error if any).
- Dashboard: `http://localhost:8501`.
- Restart policy is `unless-stopped`: killing either container brings it
  back automatically. The ledger is SQLite in WAL mode (see
  `catalog.py`), which is the standard safe-under-crash configuration —
  restarting the pipeline mid-write does not corrupt it.

## Config

Everything installation-specific lives in `installation.yaml` — see
`installation.example.yaml` for every field with comments, and
`src/darkfiber/installation_config.py` for the authoritative schema
(Pydantic model, validates on load). No constant is hardcoded in
`pipeline_daemon.py` itself.

## Known limits (declared, not silently shipped)

- **No live hardware ingestion adapter.** `data_source.mode` only
  supports `replay_loop` today — periodic file handoff, not a
  persistent connection to a real interrogator's protocol. See
  `docs/pilot_kit.md`, "what this pilot is *not*."
- **Eviction does not bound memory/CPU for every real array.** The
  streaming buffer's real eviction (bounded retention, not a
  never-shrinking buffer — see `stream_runner.py`) only fires once a
  raw Tier 0 block genuinely closes (a multi-second gap with *zero*
  channels active anywhere in the array). Measured on a real 3,020-channel
  Arcata file: with continuous, sparse background activity across that
  many channels, the array-wide "any channel active" signal essentially
  never goes fully silent (92% of the file's timeline had at least one
  channel above threshold), so the raw block never closes and eviction
  never triggers — the buffer grows for the whole file regardless of
  this pass's changes. Measured wall-clock margin on that file:
  `--speed 1` at 0.92× (needs ≥2×), `--speed 10` at 0.21× (needs no
  cumulative lag) — **the C3 acceptance numbers are not met for this
  array as currently built.** The eviction mechanism itself is
  correct and *does* bound memory for arrays/files where raw blocks
  do close (verified against a real Ridgecrest file and a long synthetic
  stream test). Closing this gap for busy, many-channel arrays needs a
  different closure heuristic — a density-aware criterion for the raw
  block itself, not just for splitting an already-closed one (today's
  A5 density resegmentation only runs *after* closure) — flagged as
  follow-up work, not attempted in this pass given the risk of
  reintroducing the premature-finalization bug that the current
  strict closure check exists to prevent.
- **24h continuous-operation soak test: not run as a literal 24-wall-clock-hour
  test in this pass** (impractical within this session) — instead, a scaled
  proxy was run and measured: the daemon's core loop (fresh `StreamRunner`
  per file, matching `pipeline_daemon.py`'s actual per-file lifecycle) against
  a real Ridgecrest file (120s, 1,150 channels), looped at max replay speed
  for 240s of real wall clock (23 full loops, ~46 minutes of stream-equivalent
  time, 230 verdicts written to the ledger). Resident memory measured via
  `psutil` at each loop boundary: 171.6 MB → 173.0 MB, +0.3% over the run,
  flat — no cross-loop leak. This demonstrates the daemon-level property that
  matters for long-running operation (each file's `StreamRunner` and its
  buffer are garbage-collected once that file finishes, so repeated looping
  doesn't accumulate) — it does **not** by itself demonstrate that eviction
  bounds memory *within* one very-long-running stream for every array; that
  was checked separately (a 900s synthetic stream test with real eviction
  firing, and the real-Arcata finding above where it doesn't). A genuine
  unattended 24h run against a real array is recommended before treating this
  gate as closed with full confidence.
