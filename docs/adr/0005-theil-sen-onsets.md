# 0005 — Theil-Sen (repeated-median) regression for the onset-velocity fallback

## Status
Accepted.

## Context
Slant-stack semblance measures velocity by finding the shift that makes
channels' waveforms *look alike* once aligned. That collapses for emergent,
decorrelated arrivals (ADR 0002) — the fine waveform structure differs
channel to channel even though the coarse envelope arrives together. The
onset-fallback (`coherence.fit_onset_velocity`) instead fits a line through
each channel's first STA/LTA threshold crossing vs. its position — a
coarser signal, but one that survives waveform decorrelation. Per-channel
onset picks on real, noisy data are themselves noisy: a channel can trip
early on unrelated local noise or late on a weak arrival, and those aren't
symmetric, well-behaved errors — they're outliers.

## Decision
Fit the onset-time-vs-position relationship with Theil-Sen (the median of
all pairwise slopes between picked points), not ordinary least squares. A
single wild outlier pick can only pull an OLS fit proportionally to its
leverage; Theil-Sen's breakdown point is much higher (up to ~29% of points
can be arbitrary before the estimate breaks), which matches what
per-channel onset picking on real fiber actually produces — a plausible
line with a handful of clearly wrong picks, not the other way around.

## Consequences
- Cost: computing all pairwise slopes is O(n²) in the number of picked
  channels; `onset_fit_min_channels` (default 30) bounds this to something
  cheap in practice, and the fallback only runs on the coincident-but-low-
  semblance path, not on every event.
- `run_validation.py`'s scenario A checks the onset fallback's recovered
  velocity against the same ground truth used for the semblance-based
  measurement (15% tolerance) — a regression guard that this fallback
  doesn't quietly break the confirmed-earthquake path it was never meant
  to touch.
- A flat fit (slope ≈ 0) is reported explicitly as "moveout plano:
  incidencia casi vertical u origen fuera de la resolución de esta
  apertura" rather than as a spuriously large or infinite velocity — the
  honesty principle applies to the fallback measurement too.
