# Changelog

All notable changes to this project are documented here. Bugs found and
closed are listed alongside features — they're evidence of rigor, not
something to hide.

## [Unreleased]

### Added

- **F1.3 pre-registration for the SNR50 extension** (`sample_plan_fase1.md`/
  `.json`), reconciling my paper-sourced draft with the user's own direct
  Globus reconnaissance. Final selection: **FOSSA, Valencia (submarine
  channels only), Stanford-2 (channels 400-750)** — FORESEE pending one
  more check (its "PREVER" folder couldn't be independently confirmed as
  FORESEE or as anything else). Three exclusions, each documented with
  its own specific reason rather than lumped together: Fairbanks
  (active-source-only hosted data), LaFarge-Conco (confirmed by direct
  Globus listing — `Data/` is `{Blast1, Blast2, ESS, HammerTap,
  MiniVibe}`, no separable passive-noise folder, stronger evidence than
  the paper-based assumption in F1.2b), PoroTomo DASH (71 segments of
  ~100m each, no linear run at a scale comparable to the other
  candidates). Resolved a Stanford-2-vs-Stanford-3 question that turned
  out to have the wrong premise: Stanford-3 shares its physical fiber
  loop with Stanford-1 (already measured as `stanford1_campus` in F1.1),
  not with Stanford-2 (a genuinely different site, Sand Hill Road/Palo
  Alto) — sourced directly from the PubDAS paper's own Figure 6 caption.
  Real per-file Globus granularity (FOSSA: 1h/6.16GB; Valencia:
  10min/1.78GB) replaced the earlier rate-based volume estimates, cutting
  the declared download budget from the prior draft's ~29.6GB down to
  **~11.75GB** (FOSSA 6.16 + Valencia 5.34 + Stanford-2 ~0.25 GB
  estimated, still pending its own file-pattern confirmation) — well
  under the user's 40GB ceiling. Exact filenames aren't pre-registered
  as literal values (no Globus access on this side to read the real
  listing) — instead the deterministic *selection rule* (first
  chronological file, ComCat-screened before running) is committed now,
  with a short checklist for the user to apply it directly in Globus.
  Nothing downloaded or run — commit is the pre-registration artifact
  itself, gated behind the user's separate approval before any transfer
  or measurement.

- **F1.2b: spec verification for the F1.2 candidate census, closing every
  "no confirmado" field against a primary source before any candidate can
  reach F1.3.** Read-only, no DAS data downloaded. Recovered the actual
  PubDAS paper's Table 1 (exact specs for all 8 hosted datasets) by
  extracting the EarthArXiv preprint PDF directly with PyMuPDF after
  WebFetch's HTML-to-markdown conversion failed on it — this is the
  primary source behind most of the corrections below, not a
  reconstruction. **Real errata, recorded not silently fixed**: FORESEE
  was misplaced in the v1 census as Brady Hot Springs, NV (geothermal) —
  it's actually at Penn State, State College, PA (urban university
  campus); the error came from an unverified general search conflating it
  with the physically separate PoroTomo/FORGE projects that really are at
  Brady Hot Springs. Completed exact channel count, spacing, gauge
  length, hosted sampling rate, format, and volume for FOSSA, FORESEE,
  Stanford-2, Fairbanks, LaFarge-Conco, and PoroTomo DASH; recomputed each
  one's minimum noise-duration floor from the corrected apertures.
  PoroTomo DASH surfaced a real open question, not resolved here: its
  zigzag "fishbone" layout means cable length (~8.8km) and geometric
  aperture (~1.5km) diverge sharply, and the noise-floor formula assumes
  a roughly linear cable — both values reported, no default picked.
  Fairbanks flagged with an operational caveat: the PubDAS-hosted subset
  is active-source only (nightly vibrator sweeps), so real background-
  noise availability between sweeps needs confirming at first read access,
  not assumed. Brno's stored-file sampling rate could not be resolved
  even from the full paper (PMC12078700) — the paper states only the
  interrogator's 20kHz pulse rate, never the stored HDF5 time-axis rate —
  so Brno stays excluded from F1.3 until resolved by another channel
  (author contact or a first metadata-only read, the latter needing its
  own separate authorization). Verified and refuted, with the primary
  source's own Table 1/Table 3, the hypothesis that PubDAS's "seafloor"
  8th dataset is the MARS/Monterey Bay cable: none of PubDAS's 8 hosted
  datasets is a Monterey Bay dataset at all — PubDAS's real seafloor
  entry is Valencia (Spain, submarine telecom cable, a genuine new
  candidate not yet in the selected list). A much smaller, non-PubDAS-
  hosted "Monterey Bay" entry does exist in the paper's Table 3 (4 days,
  0.565GB) but its size/duration point to the original 2018 4-day MARS
  campaign, not the year-long SeaFOAM deployment the project's existing
  `monterey_bay` array almost certainly comes from (near-exact channel-
  spacing/fs match to Romanowicz et al. 2023) — same physical cable, two
  different experiments, not the same dataset. Globus setup steps
  documented from the paper's own §6 and cross-checked against
  `DAS-RCN/awesome-das` for the actual endpoint link (not taken from a
  single unverified search result): install + first OAuth login are
  necessarily user-side; scripted transfers after that could be automated
  in F1.4/F1.5 if authorized. Declared, not-yet-executed per-array
  download-size plan (~30GB proposed ceiling for the 6 candidates with
  complete specs) added for F1.3 to work from. Full detail:
  `docs/snr50_extension_fase1.md` §F1.2b.
- **`snr_curve.py` gains `.npz` support and manual noise-exclusion windows
  (F1.1, SNR50 extension to more installations)**: `gather_noise_sources`
  now loads through `replay.load_file` (same loader `stream_runner.py`/
  `pipeline_daemon.py` already use) instead of a QuakeFlow-only `.h5`
  path, so formats without embedded ground truth (`.npz`) work too — new
  `--fs`/`--dx` CLI flags, `SystemExit` if missing (never assumed, per
  project convention). New `--exclude-s START END` generalizes the
  existing event-time-index noise split to files without embedded
  ground truth: same before/after-window logic, applied manually. Output
  JSON gained a `noise_exclusion` block recording, per noise source, its
  `exclusion_kind` (`"event_time_index"` / `"manual (--exclude-s)"` /
  `"none"`) and exact `segment_s` — traceable after the fact, not just
  visible in the console at run time. 4 new tests
  (`tests/test_snr_curve.py`): `.npz` loader shape/dtype/explicit fs-dx,
  and two independent checks that an excluded window never leaks into
  the returned noise pool. No changes to Tier0/coherence/supervisor
  (Bloque A, frozen).
- **Stanford (`stanford1_campus`) SNR50 measured: 7.73**, closing F1.1 of
  the SNR50-extension plan. Run against the existing
  `eastfoothills_real.npz` (626 ch, fs=100Hz, dx=8.16m) with
  `--exclude-s 395 455` (covers the USGS origin at t=401s, the A10 dense
  core `[410.3,423.8]`s, and the tail of the originally-fused block),
  threshold left at the global default (4.0 — this array never had an
  A7/A8 calibration applied). 140/140 valid trials, monotone non-decreasing
  recall within Wilson 95% CI. Updates the cross-array spread from 3.7×
  (3 arrays) to 4.83× (4 arrays):
  `monterey_bay (1.6) < ridgecrest_north (2.5) < arcata (5.9) < stanford1_campus (7.73)`.
  Full technical note, protocol details, and per-array threshold
  provenance: `docs/snr50_extension_fase1.md`.
- **F1.2 read-only census of public DAS datasets** (no downloads — metadata
  and documentation only): 7 new candidate installations found across
  PubDAS, Figshare, and OEDI, ranked by access method and installation-
  environment diversity for a future F1.3 pre-registration (not started —
  gated behind explicit approval). Two datasets initially suspected of
  being new leads were verified, with direct evidence, to be arrays
  already in the project under a different name (GorDAS = `arcata`;
  SCEDC AWS Open Data DAS-Ridgecrest = `ridgecrest_north`, exact channel-
  count match). Full table: `docs/snr50_extension_fase1.md`.
- **Ordered shutdown for the pipeline daemon and container survivability
  (C3 operational hardening)**, prompted by both pipeline and dashboard
  containers dying simultaneously with exit code 137 (external SIGKILL —
  root cause outside this repo, already investigated and closed: not
  OOM, not SQLite corruption, not a broken bind mount, not the
  healthcheck). `docker-compose.yml`: `stop_grace_period: 30s` on both
  services (`restart: unless-stopped` was already present on both, not
  newly added) and a bounded `json-file` logging driver (`max-size: 20m`,
  `max-file: 5`) so container logs can't grow unbounded. `catalog.py`:
  new `SignatureCatalog.close()` (`PRAGMA wal_checkpoint(TRUNCATE)` then
  connection close, under the same lock as every other write) and
  `wal_autocheckpoint` tightened from SQLite's default 1000 pages
  (~4 MiB) to 100 (~400 KiB) at connection open, bounding how much a hard
  kill can lose to a handful of writes instead of up to the old
  threshold. `pipeline_daemon.py`: `loop.add_signal_handler` (not
  `signal.signal` — its callbacks run inside the event loop itself, safe
  to touch asyncio primitives) registers SIGTERM/SIGINT handlers that set
  a `shutdown` Event; the existing (but never actually triggered by
  `docker stop`, since nothing installed a SIGTERM handler before this)
  `finally: stop.set(); backup_task.cancel()` in `run_forever()` is
  extended, not replaced, to also await the backup task's real
  cancellation and call the new `cat.close()`. `_run_file` checks
  `shutdown` once per chunk and stops consuming new ones early, but
  always still calls `runner.finish()` before returning — drains
  whatever's already buffered instead of dropping it, doesn't wait out
  an entire real-time-paced file just to respond to a stop request.
  `add_signal_handler` is Unix-only (confirmed directly: `NotImplementedError`
  on this Windows dev machine); guarded per-signal with a warning instead
  of crashing, and the pre-existing `KeyboardInterrupt` catch in `main()`
  remains as a fallback — Docker, the actual deployment target, is always
  Linux. The graceful-shutdown *path* itself could only be verified by
  code review here (git-bash's `kill -SIGINT` doesn't reliably reach a
  Windows console process the way a real SIGINT would), but the
  `wal_autocheckpoint` tightening WAS verified under a real forced kill
  on this machine: WAL stayed bounded at 140 KiB and
  `PRAGMA integrity_check` reported "ok" with all rows intact. Also
  verified directly: `_run_file` given a `shutdown` already set ~50ms
  into a real Ridgecrest replay still produced and persisted its one
  buffered verdict via `finish()`.
  `wal_autocheckpoint=100` and the shutdown handling were applied per
  explicit author confirmation; a proposed `UNIQUE` constraint for
  `live_verdicts` idempotency was explicitly declined — see
  `PLAN_CIERRE_Y_LANZAMIENTO.md`'s backlog for why (the table is already
  an intentional append-only occurrence log, not deduplicated; the real
  gap is specific to a future "growing incoming directory" pilot mode,
  not this fix).

- **`tests/test_closure_criterion.py`: permanent regression test for the
  premature-finalization bug C1 closed**, and the instrument that will
  make the backlogged density-aware closure heuristic (see C3's "Known
  limits" above) auditable before it replaces the current one.
  `stream_runner.raw_block_settled_end_s` is now injectable
  (`StreamRunner(closure_criterion=...)`, `ClosureCriterion` type alias —
  same functional-DI pattern as `infer_fn` in `batching.py`, default
  unchanged, no behavior change for any existing caller). A reconnaissance
  pass first confirmed the real C1 case's mechanism is fully documented
  (three independent, consistent sources: the commit message, this
  CHANGELOG, and `raw_block_settled_end_s`'s own docstring — finalizing a
  sub-event as soon as there's quiet *after its own boundary*, without
  checking whether the enclosing raw block had actually closed) but its
  concrete values are not (two sample indices with no `fs` attached,
  `evt_0000_1021_*` → `evt_0000_1045_*`; no file confirmed — only
  circumstantial evidence it was `ci39493944.h5`; no window, no block
  bounds; C1 landed as a single atomic commit, so there's no buggy
  revision in git to check out either) — rather than reconstruct those
  missing values, the test reproduces the documented *mechanism* on its
  own synthetic `raster` (a block with a partial-silence valley shorter
  than `merge_gap_s`, which shouldn't split it, followed by a real gap
  longer than `merge_gap_s` and a second block). Three checks apply to
  the production criterion, all required together (any subset admits a
  degenerate pass): no fragmentation (doesn't split the valleyed block —
  the actual C1 bug), no fusion (does close the first block before the
  second one starts — without this, "never closes," the real measured
  Arcata state above, would trivially pass "no fragmentation"), and a
  bounded closure latency. A test double reproducing the pre-C1 design
  (`_buggy_pre_c1_closure_criterion`, test-only, never imported outside
  this file) is run through the exact same fragmentation assertion used
  for the production criterion, and does fail it — captured directly:
  `settled_end_s=8.0` reported repeatedly while the true block was
  `(5.0, 11.0)`, the same shape of error as the real
  `evt_0000_1021_*`/`evt_0000_1045_*` symptom, on traceable synthetic
  values instead of a reconstruction dressed up as the real case. The
  mechanism behind the real C1 bug now has an executable, CI-permanent
  representation, not just the prose in commit `1794fc1`.

- **Real ring-buffer eviction in `stream_runner.py` (C3, Bloque
  C/"operable")**: the buffer no longer grows for the life of the
  stream — once a raw Tier0 block genuinely closes, everything before it
  (minus `finalize_margin_s` of retained margin) is physically dropped,
  turning the per-pass cost from O(buffer size, growing without bound)
  into O(a bounded margin), independent of total stream duration. Two
  mechanisms make this exact, not approximate: `_safe_evict_point` never
  cuts through a segment (retreats to a segment's own start, with an
  extra `pullback_n` cushion — see "Fixed" below for why the cushion is
  load-bearing, not decorative); and `StreamRunner._seg_global_n`
  assigns each real segment's `event_id` number ONCE, persistently, by
  its absolute start position, rather than re-deriving it from local
  position in each pass's shrinking window (`extract_events` gained a
  `seg_numbers` parameter for this, default `None` preserves the exact
  old behavior for every other caller, batch included). New
  CI-safe permanent test: `test_stream_eviction_stays_bounded_and_parity_holds_over_long_stream`
  (900s synthetic stream, 5 well-separated events) — asserts both exact
  batch/stream parity AND that the retained buffer stays under 30% of
  the stream's total size, so a regression to unbounded growth fails
  loudly, not silently.
- **`pipeline_daemon.py` (`darkfiber-pipeline`) + `installation_config.py`
  (C3)**: continuous-operation entry point. Reads one `installation.yaml`
  per instrument (`installation.example.yaml` is the annotated template)
  covering array geometry, calibrated thresholds, data source, ledger
  path, logging, healthcheck, and backup — zero hardcoded constants in
  the daemon itself, per `PLAN_v5.2`'s §C3 spec. Runs `replay.py` ->
  `StreamRunner` against the configured file(s) in a loop (today's only
  mode — see "Known limits"), writes each finalized verdict to a new
  `live_verdicts` table (`catalog.py`) kept deliberately separate from
  the ground-truth `ledger`, exposes `/healthz` + `/status` over a
  stdlib `http.server` (no new web-framework dependency), and backs up
  the SQLite ledger periodically via `sqlite3.Connection.backup()` (the
  crash-safe native API, not a raw file copy). New optional extra:
  `pip install darkfiber[ops]` (`pyyaml`).
- **`Dockerfile` + `docker-compose.yml` + `.dockerignore` +
  `docs/deployment.md` (C3)**: one image, two services (`pipeline`,
  `dashboard`) sharing a data volume; `unless-stopped` restart policy;
  Docker `HEALTHCHECK` wired to the daemon's own `/healthz`. **Not
  tested end-to-end** — Docker isn't installed in the environment this
  was built in; only YAML/syntax-checked. The underlying daemon logic
  itself *was* verified directly (see below), just not the container
  build/run cycle — flagged, not silently assumed working.

### Fixed

- **Two real numbering bugs, both found verifying against real Arcata
  data (the synthetic test suite didn't catch either — its scenario is
  cleaner than a real, busy array)**:
  1. A segment already finalized but not yet evicted can become
     undetectable in fresh re-computation once the buffer's own edge
     gets within Tier0's warmup zone of it (`ratio` forced to 1.0 for
     the first `lta_s+sta_s+gap_s`, see `sta_lta_ratio`) — corrupting
     the numbering of whatever comes after it in that pass. Fixed by
     giving `_safe_evict_point` a protected zone `[a - pullback_n, b]`
     around every not-yet-evicted segment (not just `[a, b]`), so the
     buffer's edge never gets close enough to matter.
  2. A segment belonging to a still-open raw block can change shape
     between passes as more context arrives (density re-segmentation,
     A5, re-examines the whole open block every time by design) —
     assigning it a permanent global number before it's confirmed
     closed let each revision consume a new number, inflating the
     total count far past what batch produces. Fixed by only
     persisting a segment's number once it's confirmed closed (or at
     `finish()`, when everything is finalized regardless of margin,
     matching how batch treats the file's true end); still-open
     segments get a throwaway, never-reused number that's consistent
     with them never actually being finalized that pass.

### Known limits (declared, not silently shipped)

- **The two C3 hard numeric requirements (Arcata margin ≥2× at
  `--speed 1`, no cumulative lag at `--speed 10`) are NOT met**, measured
  on a real 3,020-channel, 420s Arcata file: 0.92× and 0.21× respectively
  — both below target. Root cause, confirmed by direct measurement, is
  architectural, not a bug in this pass's eviction code: the raw-block
  closure gate (`raw_block_settled_end_s`, unchanged since C1) requires
  a multi-second window with *zero* channels active anywhere in the
  array. On this file, 92.3% of the timeline has at least one of 3,020
  channels above the Tier0 threshold somewhere — with that many
  channels, near-statistically guaranteed — so the raw block essentially
  never closes and eviction never gets a chance to run, even though the
  eviction mechanism itself is correct (verified against a real
  Ridgecrest file and the synthetic long-stream test above, both of
  which have genuine quiet gaps). Closing this gap needs a
  density-aware closure heuristic for the raw block itself (today's A5
  density resegmentation only runs *after* closure) — flagged as
  follow-up, not attempted here given the risk of reintroducing the
  premature-finalization bug the current strict check exists to
  prevent. See `docs/deployment.md` and `docs/observaciones.md`
  (2026-07-23) for the full measurement.
- **24h continuous-operation soak test not run literally.** A scaled
  proxy was: the daemon's actual per-file loop against a real 120s
  Ridgecrest file, looped for 240s of wall clock (23 full loops, ~46 min
  of stream-equivalent time) — resident memory flat (171.6 → 173.0 MB,
  +0.3%), no cross-loop leak. This confirms daemon-level stability
  across many files, a different property from whether eviction bounds
  memory *within* one very long stream (see above) — see
  `docs/deployment.md` for the distinction. A genuine unattended 24h run
  is recommended before treating this gate as closed with full
  confidence.

- **`docs/pilot_kit.md` + `docs/pilot_data_agreement_template.md` (C4,
  Bloque C/"operable")**: the pilot kit for a fiber operator's technical
  team — sendable as-is, no prior call needed, per the acceptance
  criterion in the project's own closure plan. Covers what an operator
  would need to provide (files in the formats `replay.py` already
  ingests; array geometry; something to compare against), what they'd
  receive (dashboard, fully-explained verdicts, an SNR50 curve measured
  against *their* array's own real noise, a scoreboard in the same
  format as `validacion_real/scoreboard.md`), a 2-week shadow-mode plan,
  and an explicit "what this pilot is *not*" section: no live
  socket/API adapter to a real interrogator protocol exists yet (shadow
  mode today means periodic file handoff, not a persistent connection);
  continuous 24h+ operation is not validated (Arcata's `--speed 10`
  streaming lag, already documented below, is the concrete reason); and
  the system is not tuned to produce confirmations, so mostly
  honest-uncertain pilot verdicts would be consistent with every other
  array validated so far, not a sign of malfunction. The data agreement
  template documents, verified against `catalog.py`'s actual table
  schema (not asserted from memory), that raw DAS waveform data is never
  stored in the local ledger — only file references, derived scalar
  metrics, verdicts, and supplied ground truth.

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

- **`dashboard.py` (C2, Bloque C/"operable")**: Streamlit operator
  dashboard, four tabs against the same `SignatureCatalog` the rest of
  the project reads/writes. *Vivo*: runs a `replay.py`/`StreamRunner`
  demo against a local file (blocking, run-to-completion rather than
  incrementally live — a deliberate simplification that avoids the
  race-condition risk of updating Streamlit state from a background
  thread) and renders the resulting channel-time waterfall with finalized
  events marked, plus the full verdict feed (`explanations` included).
  *Catálogo*: signature catalog browser (prototypes, unknown clusters,
  naming/"bautizo" flow). *Latido*: per-array last self-test, SNR50, and
  synthetic recall curve. *Scoreboard*: live outcome matrix with Wilson
  95% CIs. Console script: `darkfiber-dashboard`
  (`streamlit>=1.30`, optional `[dashboard]` extra). CI-safe smoke test:
  `tests/test_dashboard.py`, using `streamlit.testing.v1.AppTest` (which
  actually executes the script, not just imports it) against an empty
  temp ledger.

### Fixed

- **Relative imports break under `streamlit run`**: `dashboard.py`
  originally used the project's usual `from .catalog import ...` style,
  which works fine under `python -m darkfiber.dashboard` but fails under
  `streamlit run`, which executes the file directly with no parent
  package (`ImportError: attempted relative import with no known parent
  package`). Caught by `tests/test_dashboard.py`'s `AppTest` run, not by
  a plain import check. Fixed by switching to absolute imports
  (`from darkfiber.catalog import ...`) in that file. See
  `docs/observaciones.md`, 2026-07-22, for the general note in case a
  future entry point needs the same treatment.
- **`ArrowTypeError` on a mixed-type table column**: the scoreboard's
  per-array table had a "magnitud" column mixing real floats (QuakeFlow
  ground truth) with the placeholder string `"—"` (no ground truth);
  Streamlit silently auto-recovers from this (logs a warning, applies its
  own type coercion) but the underlying cause was fixed properly instead
  of relying on that fallback, by formatting the column to a string
  unconditionally.

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
