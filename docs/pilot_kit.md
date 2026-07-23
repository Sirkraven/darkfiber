# DarkFiber pilot kit — for a fiber operator's technical team

*This document is meant to be sent as-is to a technical contact at a fiber
operator or seismic network, without a prior call. It describes what a
2-week shadow-mode evaluation of DarkFiber against your own DAS
installation would require, what you'd get out of it, and exactly what
data would and wouldn't leave your infrastructure. Every number here is
sourced from the project's public validation record — see "Where these
numbers come from" at the end.*

## What this is, in one paragraph

DarkFiber is a physics-first coherence engine for earthquake detection on
Distributed Acoustic Sensing (DAS) arrays: instead of a per-channel
classifier, it measures whether a signal moves across the array at a
physically plausible seismic velocity (slant-stack semblance,
corroborated by an independent onset-velocity regression), and reports a
verdict with a full audit trail — never a bare score. It is not
production-hardened yet (see "What this pilot is *not*" below); this kit
is how a first real installation would be evaluated safely, without ever
putting the operator's own monitoring on the line.

## What you would need to provide

- **Data, as files.** Today DarkFiber ingests DAS recordings as files —
  HDF5 in the QuakeFlow convention (sampling rate and channel spacing
  read from embedded attributes) or NPZ (with `fs`/`dx` supplied
  explicitly). **There is no live socket/API adapter for a specific
  interrogator's streaming protocol yet** — that is explicitly out of
  scope for the current codebase (`src/darkfiber/replay.py`'s own
  docstring calls this "deuda declarada para cuando haya hardware real
  hablando un protocolo de verdad"). In practice, shadow mode today means
  your interrogator (or its existing acquisition software) periodically
  writing out files — e.g., one per hour or per detected trigger — that
  we then feed through the streaming pipeline. If your interrogator can
  do that, no other integration work is needed on your end.
- **Array geometry.** Channel count, channel spacing (or equivalent —
  gauge length/spacing as configured on your interrogator), and sampling
  rate. Three numbers.
- **Compute.** The pipeline is pure NumPy/SciPy — no GPU, no ML
  framework, no network access required to run. Measured throughput for
  the cheap first-pass triage stage (Tier 0, STA/LTA): 10 minutes of a
  full array (75 MB) triaged in ~1.05 s on a 4-core laptop CPU (Intel
  Core i5-11300H, no GPU) — about 570× real time
  (`darkfiber-validate`'s own benchmark, reproducible on request). The
  heavier coherence stage only runs on the small fraction of
  channel-time cells Tier 0 flags (99.98% of quiet time never reaches
  it), so this is representative of steady-state load, not a
  worst-case. This has not been load-tested at continuous 24h operation
  against a live feed yet — see "What this pilot is *not*" below.
- **Something to compare against.** Shadow mode's whole point is
  comparing DarkFiber's verdicts against ground truth you already have —
  your own catalog, a regional network's catalog (USGS/SCEDC-style), or
  simply your operators' own knowledge of what happened on the fiber
  during the window. Without that, a shadow run produces verdicts but no
  evaluation.

## What you would receive

- **The dashboard** (`darkfiber-dashboard`, Streamlit): a live
  channel-time waterfall with events marked, the full verdict feed with
  every verdict's complete explanation (not a score — the reasoning),
  the signature catalog for recurring unidentified sources, and a
  "latido" (heartbeat) view of your array's own last self-test.
- **Every verdict, fully explained.** DarkFiber's decision tree has
  seven possible outcomes, not a binary alert/no-alert — including two
  ways to be honestly uncertain (`HONEST_UNKNOWN`, `HONEST_REGIONAL`)
  and two ways to fail loud when the array can't see far enough
  (`MISS_SUPPRESSED`, `MISS_BELOW_FLOOR`). Nothing is a bare score;
  every verdict carries the measurements that produced it.
- **An SNR50 curve measured against *your* array's own real background
  noise** — not a generic spec. This is the actual performance number
  that matters: at what SNR does this specific installation's own noise
  floor let DarkFiber detect a real event 50% of the time. Across the
  three installations validated so far this varies 3.7× (1.6 to 5.9)
  between arrays of broadly similar channel count — geometry alone does
  not predict it, so we don't report a generic spec, we measure yours
  (`darkfiber-snr-curve`, same method as `docs/writeup.md` §4.2).
- **A scoreboard**, in the same format already public for this
  project's own validation (`validacion_real/scoreboard.md`): your
  array's own outcomes, tallied against whatever ground truth you
  compared against, with Wilson 95% confidence intervals given the
  sample will be small.

## The 2-week shadow-mode plan

1. **Week 0 (setup, off your critical path).** You hand off array
   geometry + a first batch of files (ideally spanning both quiet
   periods and at least one known real event, if you have one on
   record). We run the array self-test and produce the initial SNR50
   curve and detection-floor estimate for your installation
   (`array_profiles` in the local SQLite ledger — see the data agreement
   below for exactly what that stores).
2. **Weeks 1-2 (shadow, no alerting).** DarkFiber runs against files as
   you deliver them (batch, not a persistent connection — see above) and
   produces verdicts into the local ledger. **Nothing pages anyone.**
   This is a shadow run: it exists to be compared, not acted on.
3. **End of week 2: the comparison.** Every DarkFiber verdict during the
   window gets checked against whatever ground truth you have for that
   period (your catalog, a regional network's, or your own operators'
   knowledge). The result is a scoreboard in the same format as this
   project's own public validation, specific to your installation.
4. **Decision point.** You get the scoreboard, the SNR50 curve, and every
   verdict's full explanation. Whether DarkFiber is worth running for
   real on this fiber is your call, made against measured numbers for
   your own array, not a marketing claim about arrays in general.

## What this pilot is *not*

Said plainly, because the project's whole premise is not over-claiming:

- **Not a live, always-on connection to your interrogator.** Today's
  integration is file handoff, as above. A real streaming adapter for a
  specific interrogator's protocol is future work, not built.
- **Not validated for continuous 24h+ operation yet.** The streaming
  path (`stream_runner.py`) currently re-processes its whole growing
  buffer on every analysis pass, which is measurably slow on large
  arrays under fast-forward replay: Arcata (3,020 channels) took ~5.8×
  longer than the file's own duration at `--speed 10` — already down
  from ~25× before the one mitigation applied so far (raising the
  analysis interval from 2.0s to 10.0s, a real but partial fix; see
  `CHANGELOG.md`, "Known limits"). A bounded ring buffer that removes
  this cost pattern for real continuous operation is planned (declared
  as C3 in this project's own closure plan) but not done. A 2-week
  shadow pilot on periodically-delivered files does not depend on this;
  a permanent, always-on deployment would.
- **Not a replacement for your existing monitoring during the pilot.**
  Shadow mode means exactly that — it runs alongside what you already
  trust, not instead of it, for the whole two weeks.
- **Not tuned to produce confirmations.** Across the 16 real
  ground-truth-matched earthquakes validated so far, none reached a
  clean `SISMO_CONFIRMADO` — the system's own guards retracted two
  earlier apparent confirmations when they turned out to rest on
  measurement artifacts (density-merged blocks, a velocity estimate
  pinned to the edge of its search grid rather than a real interior
  peak). If your pilot also produces mostly honest-uncertain verdicts
  rather than clean confirmations, that is consistent with what this
  system has done everywhere else it's been tested, not a sign
  something is broken.

## Data handling, in short

See `docs/pilot_data_agreement_template.md` for the fillable version.
The short version: your raw DAS waveform data never leaves your own
infrastructure — DarkFiber's local SQLite ledger stores file references,
derived numeric metrics (coincidence fraction, semblance, apparent
velocity, SNR), verdicts, and any ground truth you supply for comparison
— never raw channel-time waveform samples (see `catalog.py`'s own table
schema: `ledger`, `array_profiles`, and related tables carry JSON metrics
and file paths, not signal data).

## Where these numbers come from

Every figure above is reproducible from this project's own public
record, not asserted from memory: the Tier 0 throughput benchmark and
the 570× figure come from `darkfiber-validate`'s own benchmark section
(re-run to confirm before this kit is sent to anyone); the 3.7× SNR50
spread and the 16-event validation matrix are in `docs/writeup.md` §4
and `validacion_real/scoreboard.md`; the streaming performance limit is
in `CHANGELOG.md`'s `[Unreleased]` "Known limits" section. Code,
license, and DOI: `https://github.com/Sirkraven/darkfiber`
(AGPL-3.0-or-later).
