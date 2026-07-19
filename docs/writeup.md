# DarkFiber: a physics-first coherence engine for Distributed Acoustic Sensing, validated by what it refused to confirm

*Draft technical writeup — Bloque B1. Every number below is sourced against
`docs/writeup_data.md`, `validacion_real/scoreboard.md`,
`validacion_real/NOTES.md`, and `CHANGELOG.md`. This is a draft for author
review, not a publication — see the note at the end.*

## 1. Abstract

DarkFiber is a physics-first coherence engine for earthquake detection on
Distributed Acoustic Sensing (DAS) fiber-optic arrays. Instead of treating
each of an array's hundreds to thousands of channels as an independent
per-channel classification problem, it measures the one property that
distinguishes a real seismic wavefront from noise or traffic: a coherent
moveout across the array, quantified by slant-stack semblance and
corroborated by an independent onset-velocity regression. No LLM sits in
the verdict path; the system measures physics and reports what it
measures. We validated the pipeline against 43 real DAS recordings across
four array installations (Stanford, Ridgecrest, Arcata, Monterey Bay) —
16 carrying a cataloged real earthquake to score against, 27 with no
cataloged event as a false-alarm check — plus a qualitative teleseism
case (Pawnee, 22 raw files) validated separately. The
honest result: **0 of 16 real local/regional earthquakes were confirmed as
`SISMO_CONFIRMADO`**, 8 were correctly flagged as weak-but-present
(`HONEST_UNKNOWN`), 2 as regional/emergent arrivals beyond the array's
resolving aperture (`HONEST_REGIONAL`), and 6 fell below the measured
detection floor for their array (`MISS_BELOW_FLOOR`) — with zero false
alarms across all 27 no-event files and zero cases where the engine saw a
real signal and lost it (`MISS_SUPPRESSED = 0`). Two apparent
confirmations from earlier validation passes were subsequently retracted
by two independent internal guards once density re-segmentation exposed
event-fusion artifacts and grid-boundary non-measurements underneath them.
The thesis of this paper is that this outcome — not a headline detection
count — is the actual evidence of a serious measurement system: it
rejected results that would have been convenient to keep, for reasons it
can show its work on.

## 2. The problem

A modern DAS interrogator turns a single fiber-optic cable into an array
of hundreds to thousands of strain-rate sensors, sampled at tens to
hundreds of Hz. That density is the appeal — and the trap. Treated as
independent channels, a monitoring system built around per-channel
anomaly detection or per-channel ML classifiers drowns in false alarms:
traffic, wind, human activity, and instrument artifacts all produce
per-channel excursions that look, in isolation, like signal. A real
seismic wavefront, however, is not a per-channel event: it is a single
physical disturbance crossing the array as a whole, arriving at each
channel with a time delay set by its apparent velocity along the fiber —
the *moveout*. That slope, not any single channel's amplitude, is the
physically meaningful discriminant between "an earthquake crossed this
array" and "something happened near one point on this cable."
`figures/fig1_pendiente_es_fisica.png` illustrates this directly: the same
raw per-channel traces that look like scattered, ambiguous transients
resolve into an unambiguous plane-wave arrival once plotted as
time-vs-channel-position, because the physics *is* the slope.

## 3. Method

The pipeline is three tiers, each auditable independently:

1. **Tier 0 (STA/LTA triage).** A cheap per-channel short-term/long-term
   average ratio flags candidate time-channel windows worth examining
   further, filtering the overwhelming majority of silence before any
   heavier computation runs.
2. **Coherence (slant-stack semblance).** Candidate windows are stacked
   along a swept grid of apparent velocities; the velocity that maximizes
   waveform-shape semblance across channels is the measured apparent
   velocity of the arrival, if the array is coherent enough to resolve
   one. `figures/fig2_semblanza.png` and `figures/fig3_beam_fases_PS.png`
   show this on a synthetic confirmed-earthquake scenario: a clear
   interior semblance peak, and P/S phase picks on the resulting beam.
3. **Supervisor / taxonomy.** The measured velocity, its coincidence
   fraction (share of the array triggered near-simultaneously) and span
   fraction (spatial extent of the trigger) are classified into one of
   five verdicts: `SISMO_CONFIRMADO` (confirmed local earthquake),
   `FUENTE_MOVIL_TRAFICO` (moving source, e.g. vehicle traffic — tracked
   by trajectory regression, not moveout), `INCOHERENTE_LOCAL_SUPRIMIDO`
   (suppressed local false positive, small spatial footprint),
   `COHERENTE_DESCONOCIDO` (coherent but unclassified — feeds the
   signature catalog), and `POSIBLE_REGIONAL_EMERGENTE` (massive,
   quasi-simultaneous, spatially-decorrelated arrival whose moveout the
   array's aperture cannot resolve — regional or distant events; see §7).

Two design commitments make `SISMO_CONFIRMADO` specifically hard to earn,
both added after real-data failures (§6):

- **A grid-boundary semblance maximum is not a measurement.** If the
  semblance argmax sits on the edge of the swept velocity grid rather
  than at a genuine interior peak, the result is flagged
  `boundary_pinned=True` and cannot by itself support confirmation — a
  monotonically-rising curve pinned to a grid edge means the true optimum
  lies outside the swept range, not that the edge value is correct.
- **Confirmation requires two independent estimators to agree.** Alongside
  slant-stack semblance, a second, structurally different measurement —
  Theil-Sen (repeated-median) regression on each channel's first STA/LTA
  threshold crossing versus its position — must recover a compatible
  apparent velocity (within 40% relative difference) before
  `SISMO_CONFIRMADO` is reachable. Theil-Sen's robustness to noisy
  per-channel picks (breakdown point up to ~29% of points) makes it a
  genuinely independent check on the semblance measurement, not a
  correlated one.

A signature catalog (SQLite-backed, `array_id`-scoped) additionally learns
recurring unclassified signals — a coherent-but-unknown event seen
repeatedly can be named by a human operator without retraining any model,
and that label is then recognized on future occurrences by similarity to
the stored vector, not by a classifier boundary.

**No LLM participates in this path.** Every field in a verdict —
apparent velocity, semblance, coincidence fraction, onset-fit agreement —
is a direct physical measurement, and every verdict carries a
human-readable `explanations` list showing exactly which measurements
produced it. Nothing here is a language model's summary or judgment call.

## 4. Data

Real-data validation drew on two sources:

- **Stanford DAS array (via PubDAS/Globus SEG-Y, and via the
  `FiberOpticEarthquakes` GitHub repository for Pawnee)**: 626 channels,
  8.16 m spacing, 100 Hz (sampling rate varies by acquisition — 50 Hz for
  the 2016 Pawnee recording, 100 Hz for the 2017 East Foothills recording;
  read from the SEG-Y header, never assumed). East Foothills M4.1
  (2017-10-10) is registered in the QuakeFlow validation ledger (1 event);
  Pawnee M5.8 (2016-09-03, a teleseism ~2,500 km from the array, 22 raw
  SEG-Y files) was validated qualitatively and is **not** in the ledger —
  a teleseism's emergent surface-wave arrival is not the local-earthquake
  moveout case the ledger's ground-truth scoring is built to score.
- **QuakeFlow DAS (Hugging Face `AI4EPS/quakeflow_das`)**, three
  installations, each pre-curated per-event `.h5` with embedded USGS/SCEDC
  ground truth (magnitude, origin time, event sample index):

  | Array | Files (ledger) | Channels | fs (Hz) | Channel spacing (m) | Aperture (m) |
  |---|---|---|---|---|---|
  | ridgecrest_north | 12 | 1,150 | 100.0 | 8.0 | 9,192 |
  | arcata | 15 | 3,020 | 100.0 | 5.10 | 15,411 |
  | monterey_bay | 15 | 2,845 | ~200.0 | 5.2 | 14,789 |

**A caveat on monterey_bay, stated rather than silently normalized away:**
its measured background noise RMS (`array_profiles.noise_stats_json.rms_mean
≈ 60,106`) is roughly 5-6 orders of magnitude above the other three arrays
(0.02-0.16), and its sampling rate is `fs≈199.995 Hz` rather than a clean
200.0 Hz — both taken verbatim from the ledger, not transcription errors.
The likely explanation is that this particular QuakeFlow source file is in
different physical units than the other three arrays (e.g. raw
digitizer counts rather than microstrain-rate), not a measurement error on
our side. This does **not** undermine the SNR50/recall results above:
`snr_to_amplitude()`, the project's one operative SNR definition, scales
an injected wavelet by the *local* noise RMS
(`amp = target_snr · RMS(noise) / RMS(wavelet)`), so it is scale-invariant
by construction — a SNR50 of 1.6 means the same thing on monterey_bay's
scale as arcata's 5.9 means on arcata's. What it does mean: no comparison
of *absolute* amplitude, semblance offset, or raw-unit thresholds across
arrays should be drawn from this dataset, and confirming the actual
physical units of the monterey_bay source file is open, declared work
(backlog), not resolved here.

A second, related number needs the same care rather than a tidy story:
`array_profiles.synth_recall = 0.0` for monterey_bay — a legacy,
low-power self-test metric (`run_array_selftest`, 3 SNR steps × 3 trials
= 9 injections total) computed separately from the properly-powered
recall curve above (7 steps × 20 trials = 140 injections, the same
`snr_to_amplitude` definition). Zero successes in 9 trials is hard to
reconcile with the recall curve's own measurement at the same SNR values
(SNR=3: 18/20 hits; SNR=8: 18/20 hits) — if the true recall there is
really ~90%, 0/9 has roughly a 1-in-a-billion probability by chance,
which argues against reading it as ordinary sampling noise. It is
tempting to blame the same unit anomaly above, but that story does not
actually hold up: `run_array_selftest` injects via the same
scale-invariant `snr_to_amplitude()`, so a raw-unit mismatch should not,
by the mechanism we can see, zero out its recall while leaving the
curve's recall intact. We are not asserting a cause here — flagging a
real, well-evidenced discrepancy between two self-test code paths on the
same array, with the actual mechanism unresolved, rather than connecting
it to the unit anomaly without evidence that the connection is real. Both
are backlog items (`docs/writeup_data.md`), not investigated further in
this documentation pass since doing so would mean running new code
against Bloque A, which stays frozen.

The QuakeFlow validation ledger totals **43 events across these four
array/installation entries** (arcata 15, monterey_bay 15,
ridgecrest_north 12, Stanford/East Foothills 1), all with distinct source
files — verified by `SELECT COUNT(*), COUNT(DISTINCT event_file) FROM
ledger` returning `(43, 43)`. Every ridgecrest_north file used is part of
a pre-registered sample (`sample_plan.md`, drawn 2026-07-15 before any
result was seen, seed fixed and logged); 8 additional downloaded
ridgecrest_north files remain an explicit, unrun reserve pending a fresh
pre-registration, not folded into this sample.

Of the 43, 16 carry a cataloged real earthquake (magnitude, origin time)
against which the engine's verdict is scored; the remaining 27 have no
cataloged event and serve as a false-alarm check.

## 5. Results

### 5.1 Final matrix (N=16 ground-truth-matched real events)

| Outcome | n/N | Rate | Wilson 95% CI |
|---|---|---|---|
| HIT | 0/16 | 0.0% | [0.0%, 19.4%] |
| HONEST_UNKNOWN | 8/16 | 50.0% | [28.0%, 72.0%] |
| HONEST_REGIONAL | 2/16 | 12.5% | [3.5%, 36.0%] |
| MISS_SUPPRESSED | 0/16 | 0.0% | [0.0%, 19.4%] |
| MISS_BELOW_FLOOR | 6/16 | 37.5% | [18.5%, 61.4%] |

Plus, on the 27 files with no cataloged event: **27/27 CORRECT_REJECTION,
0/27 FALSE_ALARM.**

`HIT` means a real local/regional earthquake reached `SISMO_CONFIRMADO`.
`HONEST_UNKNOWN` means the engine saw a real but weak signal and correctly
declined to over-confirm it. `HONEST_REGIONAL` means a real, large,
spatially-massive arrival was correctly recognized as beyond this array's
resolving aperture rather than forced into a confirmed-or-suppressed
binary. `MISS_SUPPRESSED` (zero occurrences) would mean the engine
detected something and discarded it wrongly — the bad failure mode.
`MISS_BELOW_FLOOR` means no Tier0 candidate ever appeared in the causal
matching window for that event at all, consistent with the event being
below this array's measured detection floor rather than a classification
bug (§5.2 measures that floor directly). The sample is small (N=16) and
the Wilson intervals are correspondingly wide — reported as measured, not
smoothed. `figures/fig6_detectabilidad.png` plots every ground-truth-matched
event as magnitude vs. distance (or aperture, where distance isn't
available), colored by outcome — the empirical detectability envelope
this matrix traces out, rather than an assumed one.

### 5.2 Detectability as a property of installation, not geometry

Detection recall was measured directly by injecting synthetic events at
known SNR into each array's own real background noise (not a generic
noise model) and recording the SNR at which recall crosses 50% (SNR50),
with Wilson 95% confidence intervals at each step (n=20 trials/step):

| Array | SNR50 |
|---|---|
| ridgecrest_north | 2.5 |
| monterey_bay | 1.6 |
| arcata | 5.9 |

(`figures/fig6_recall_snr_ridgecrest_north.png`,
`figures/fig6_recall_snr_monterey_bay.png`,
`figures/fig6_recall_snr_arcata.png`.) Arcata's 5.9 vs. monterey_bay's
1.6 is a 3.7× spread (5.9 / 1.6 = 3.6875) across installations with
broadly comparable channel counts and spacing — detectability is not a
fixed property of "how many channels" or "how long is the array," it is
a property of the specific installation's real noise floor, and has to
be measured per-installation rather than assumed.
Per-array threshold calibration (`calibrate.py`, evidence-gated: a
threshold sweep must not break an existing confirmed HIT to be proposed)
found one improving change — ridgecrest_north's Tier0 threshold (4.0 →
8.0) — and found no improving change for arcata or monterey_bay, which
kept their defaults.

`figures/fig7_validacion_cruzada_arcata.png` and
`figures/fig7_validacion_cruzada_ridgecrest_north.png` show the
cross-validation of these calibrated thresholds against the real,
ground-truth-matched events per array.

## 6. The two artifacts, as a case study

This is the section that carries the paper's actual argument. Two events
each passed through an apparent confirmation and were subsequently
rejected — independently, for physically distinct reasons — by guards
built specifically because these two events exposed the gaps they close.

### East Foothills, M4.1, 2017-10-10 (Stanford array)

An early validation pass (P0) reported `SISMO_CONFIRMADO` on a block
spanning [398.2s, 449.0s] (50.8 s wide), 58.8% coincidence (97.3% of the
array), semblance 0.292, apparent velocity 8,000 m/s, 579/626 coherent
channels — and, because the USGS-published origin fell at second 401 of
the recording, this read as arriving 2.8 s *before* the cataloged origin.

Two problems surfaced on re-examination:

1. **A grid-boundary non-measurement.** `apparent_velocity_mps=-8000.0`
   was exactly `seismic_v_max_mps`, the edge of the swept velocity grid,
   not an interior optimum — the same exact pattern later found on the
   Ridgecrest M5.8 (below) at the opposite edge.
2. **Event fusion.** The 50.8 s block was a merged block spanning
   physically distinct arrivals — density re-segmentation, built to fix
   this exact failure mode on Ridgecrest, isolated the real dense core
   (`evt_0016_41033`, [410.3s, 423.8s], 13.5 s) once applied
   retrospectively to this file. That core starts **9.3 s *after*** the
   cataloged origin — consistent with real P/S travel time at ~46 km
   distance — not before it. The original "2.8 s before" reading was an
   artifact of the merged block including ~12 s of unrelated activity
   preceding the real arrival.

Re-run under the current pipeline (`run_on_stanford.py --dump-curve` on
the three original SEG-Y files, re-verified byte-identical to the
originally converted `.npz`), the isolated real core still pins to the
opposite grid boundary (`v_app=-1,500 m/s = seismic_v_min_mps`, semblance
0.217, `boundary_pinned=True`), and its independent onset-velocity
estimate (Theil-Sen: 163,200 m/s, R²=0.00) disagrees with the semblance
value by 200% — rejected by both the boundary guard and the
cross-estimator concordance gate, independently. Zero
`SISMO_CONFIRMADO` verdicts occur anywhere across the file's full 900
seconds. Current verdict: `POSIBLE_REGIONAL_EMERGENTE`
(`HONEST_REGIONAL`), detected 9.3 s after origin, SNR 15.9.

### Ridgecrest, M5.8, 2020-06-24 (QuakeFlow DAS, `ci39493944.h5`)

93.4% of the array (1,150 channels, 9.19 km aperture) triggered
simultaneously over a 78.9 s window — unambiguously real, unambiguously
large — with semblance ≈0, because at this array's aperture relative to
the event's distance, the arrival is a broad, decorrelated wave train
rather than a coherent plane-wave front. Before the taxonomy fix this
project's own bug tracker calls the worst possible failure mode for a
monitoring system: the engine classified this event
`INCOHERENTE_LOCAL_SUPRIMIDO` — suppressed, as if it were a one-channel
false positive — because the suppression branch checked only
channel-coherence-with-beam (which collapses to ~0 for a genuinely
decorrelated arrival), never the *extent* of the trigger. The fix
(`POSIBLE_REGIONAL_EMERGENTE`, unreachable-suppression whenever
coincidence or span fraction exceeds 0.5) corrected the classification.

Applying the later guards retroactively to this same event: its apparent
velocity (`-8,000 m/s = seismic_v_max_mps`) is boundary-pinned, and its
onset-velocity estimate (`-10,282 m/s`) disagrees with the semblance
value (`-1,500 m/s`) by over 200% — the concordance gate rejects
confirmation for this event independently of the boundary guard.
Instrument saturation was ruled out directly (only 2/1,150 channels near
amplitude max). Final verdict: `POSIBLE_REGIONAL_EMERGENTE`
(`HONEST_REGIONAL`), detected 17.1 s after origin, SNR 33.24.

### Why this is the argument, not an appendix

Both events are real, large, unambiguous earthquakes that the array
genuinely could not resolve a clean plane-wave moveout for — and in both
cases, the system's own internal checks caught it, using two structurally
different measurements (a geometric boundary check on one estimator; an
agreement check between two independent estimators) that happened to
agree. A system that will retract its own two headline "hits" when its
own guards say the velocity isn't real is not a system tuned to produce
confirmations — the taxonomy exists precisely so "I can't resolve this"
is a distinct, honest, and equally actionable output from "confirmed" or
"noise."

## 7. Known limits

**Aperture bounds resolvable velocity, in closed form.** A slant-stack
over an array of aperture `L` (meters) sampled at `fs` Hz can only
resolve an apparent velocity if the total delay across the array spans at
least `k` samples (default k=3) — below that, the channel-0-to-channel-N
shift is sub-sample and indistinguishable from infinite (flat moveout).
Closed form: `v_app_max_resoluble = L · fs / k`
(`coherence.v_app_max_resoluble`). `figures/fig5_limite_apertura.png`
sweeps this directly: on clean synthetic events with a known true
velocity, measurement error stays near a floor of ~2.4% (exact:
2.36500596068128%, `figures/limite_apertura.json`) across a wide range of
apertures and velocities, up until the velocity approaches the
geometric ceiling for that aperture, where error grows sharply.

**Detectability is per-installation, not a geometric constant** — §5.2's
3.7× spread in SNR50 (arcata 5.9 vs. monterey_bay 1.6) across three
arrays with broadly similar channel counts means "will this array see a
given event" cannot be answered from geometry alone; it requires
measuring against that installation's real noise.

**The sample is small.** N=16 ground-truth-matched real events yields
wide Wilson intervals (e.g. HONEST_UNKNOWN's true rate could plausibly be
anywhere from 28% to 72%) — reported honestly rather than dressed up with
a false precision the sample doesn't support.

**An open question, not papered over:** both real "near-miss" events in
§6 pinned to the *edge* of the swept velocity grid rather than showing an
interior peak with elevated error, while the synthetic sweep (§7, above)
shows clean interior peaks with low, bounded error across a comparably
wide range of true velocities and apertures. Why real strong earthquakes
at these two arrays produced boundary-saturating semblance curves instead
of noisy-but-interior peaks is not resolved by anything in this dataset —
recorded here as the most interesting open question this validation
surfaced, not as a settled result.

## 8. Future work

**Virtual-source interferometry from discarded traffic — passive
subsurface monitoring, not induced seismicity.** To be explicit about
what this is not: nothing here proposes generating or triggering
earthquakes to calibrate anything. Vehicle traffic is already crossing
the array and is currently discarded as noise (`FUENTE_MOVIL_TRAFICO`)
once its trajectory is measured; the idea is purely passive — using a
source that already exists to recover the empirical Green's function
between channel pairs via noise-correlation-function (NCF)
interferometry, the standard passive-seismology technique for monitoring
how the subsurface itself changes over time (velocity structure,
damage, saturation) without any active source at all
(`interferometry.py`, `darkfiber-interferometry` console script). The
synthetic validation of
this path passes fully (`tests/test_interferometry.py`,
`test_interferometry_demo_passes_all_four_checks`, 4/4);
`figures/fig4_interferometria.png` shows the resulting virtual-source
gather — the empirical Green's function recovered between channels
purely from cross-correlating passing traffic, the "V"-shaped moveout
pattern characteristic of a genuine virtual source. On real data
(Pawnee), a genuine traffic segment recovered from within the recording
(`evt_0006`, 263–349 s) produced v=261 m/s, R²=0.00 on a single 86 s pass
— honestly inconclusive with the amount of real data available (the
synthetic demo needed 240 s to converge), rather than a fabricated
velocity. Extending this to longer real traffic windows is open work.

**A read-only cognitive layer, strictly separated from the verdict path.**
A separate, explicitly-scoped extension (`darkfiber_cortex`, optional
install, pre-registered as its own plan) is designed around one
non-negotiable principle: *physics decides; the cognitive layer
interprets, investigates, and proposes — never the reverse.* The
deterministic verdict pipeline (Tier0 → coherence → supervisor →
catalog) stays the reflex arc: auditable, deterministic, unaffected by
whether the cognitive layer is even installed. Any narration,
hypothesis-generation, or improvement-proposal layer would connect via a
strictly read-only connection to the ledger and catalog, write only to
its own separate store, and never emit, modify, or block a verdict — with
every factual claim it makes required to cite a real ledger row ID,
checked by a deterministic validator. This inherits the core engine's own
honesty principle by construction: when an answer isn't in the record,
the correct output is "not in the record," not a plausible-sounding guess.

## 9. Reproducibility

- **Code and license**: `https://github.com/Sirkraven/darkfiber`
  (AGPL-3.0-or-later). **DOI**: `10.5281/zenodo.21383276` (`CITATION.cff`).
- **Console scripts** (`pyproject.toml`, installed via `pip install -e .`):
  `darkfiber-validate` (synthetic suite, `run_validation.py`),
  `darkfiber-stanford` / `darkfiber-quakeflow` (real-data harnesses),
  `darkfiber-calibrate` (evidence-gated threshold calibration),
  `darkfiber-aperture` (aperture/geometry sweep, §7),
  `darkfiber-interferometry` (§8), `darkfiber-convert-sgy` (Stanford
  SEG-Y → NPZ), `darkfiber-snr-curve` (§5.2 recall curves).
- **Tests**: `pytest` (11/11 passing) and `darkfiber-validate` (29/29
  synthetic checks) are both required green before any change to the
  decision tree is considered validated; re-confirmed in this same
  documentation pass (`CHANGELOG.md [Unreleased]`).
- **Data**: none of the real DAS recordings ship in the repository. Stanford
  data is fetched from PubDAS/Globus or the `FiberOpticEarthquakes` GitHub
  mirror and converted locally (`convert_stanford_sgy.py`); QuakeFlow DAS
  data is fetched on demand from
  `huggingface.co/datasets/AI4EPS/quakeflow_das`. Every real-data verdict
  in `validacion_real/scoreboard.md` is reproducible from these public
  sources plus the pinned pre-registered sample (`sample_plan.md`,
  `sample_plan_draw.json`, `sample_plan_universe.json`) that selected
  which files to run, fixed before any result was seen.
- **Every figure in this document is regenerable** from the scripts above;
  none are checked into version control (`figures/` is gitignored by
  design) and none were hand-edited.

---

## Author review note

This draft was written by Claude Code from the project's own committed
record (`CHANGELOG.md`, `validacion_real/NOTES.md`,
`validacion_real/scoreboard.md`, the QuakeFlow ledger, and the `figures/`
outputs) per `docs/writeup_data.md`'s traceability scaffold. Two open
items surfaced while extracting that scaffold and were resolved by data
recovery, not by re-running Bloque A or adjusting any claim to fit — see
`docs/writeup_data.md`, "Open gates — resolution log," for the full
account (in short: monterey_bay's SNR50 existed in an archived pre-A5
ledger snapshot and was restored to the active ledger with its original
provenance intact, rather than re-measured). Nothing here is submitted
anywhere. Alejandro reviews as the paper's actual author before anything
goes to EarthArXiv or any external venue.
