# 0004 — `sosfiltfilt` (zero-phase, second-order sections) for the bandpass

## Status
Accepted.

## Context
Every real and synthetic signal in this project goes through a 1-24 Hz
bandpass (`synth.bandpass`) before Tier0 triage and coherence analysis. The
filter's phase response matters here in a way it might not in a generic
signal-processing pipeline: the whole method rests on measuring *time
delays* between channels (slant-stack) and *arrival times* on the stacked
beam (P/S phase picking). A filter that introduces a frequency-dependent
phase shift would distort exactly the quantity being measured.

## Decision
Use `scipy.signal.sosfiltfilt` — forward-backward filtering in
second-order-sections form — for every bandpass in the pipeline. Two
properties matter:

- **Zero-phase**: forward-backward filtering cancels the phase distortion
  a causal filter would introduce, so arrival-time measurements aren't
  biased by the filter itself.
- **Second-order sections**: numerically stable for the filter orders used
  here, avoiding the coefficient blow-up that direct-form (`b, a`)
  representations can hit at this bandwidth.

## Consequences
- `sosfiltfilt` is non-causal (it needs the whole signal, forward and
  backward) — fine for the batch/offline analysis this project does today,
  but real-time streaming deployment would need a causal alternative for
  the online path, at the cost of some phase distortion budget. Not solved
  here; flagged as a real constraint for anyone adapting this to a live
  stream.
- Every module that touches raw or synthetic waveforms imports the same
  `synth.bandpass` rather than reimplementing filtering — one filter
  design, everywhere, so this decision doesn't need to be re-litigated per
  module.
