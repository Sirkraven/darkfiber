# 0011 — Confirmation requires two independent velocity estimators to agree

## Status
Accepted (A10).

## Context
The boundary guard (ADR 0010) catches solutions pinned to the edge of the
search grid, but not every wrong solution is pinned. `run_validation.py`
scenario I constructs a synthetic "distant/fast" event whose semblance
argmax lands one grid step *inside* the boundary (`boundary_pinned=False`)
— a plausible-looking interior peak — while the independent Theil-Sen
onset-velocity fit (ADR 0005) recovers a wildly different value (194%
discrepancy, R²≈0 on the onset fit, "flat moveout" territory). The real
Ridgecrest M5.8 event showed the same divergence for real
(`v_app_onset=-10,282 m/s` vs. `v_semblance=-1,500 m/s`) — in that case the
boundary guard already caught it independently, but the discrepancy itself
was flagged first and is a signal on its own.

The general point: semblance and onset-regression are different
measurements of the same physical quantity, derived from different parts
of the signal (fine waveform shape vs. coarse first-arrival timing). If
they don't agree, at least one is wrong, and neither guard alone (the
boundary check, or a semblance/R² threshold) reliably knows which.

## Decision
`SISMO_CONFIRMADO` now requires `|v_semblance|` and `|v_onset|` to agree
within `onset_agreement_tol_frac` (40% relative difference) whenever an
onset fit is available. This is a *second, independent* layer alongside
the boundary guard, not a replacement for it — defense in depth, not
redundancy: a solution could in principle be an interior peak (passes
ADR 0010) and still disagree with the onset estimate.

The 40% tolerance is deliberately loose, not tight: `run_validation.py`
validates each estimator against ground truth *separately*, with its own
tolerance (slant-stack ≤8%, onset ≤15% on the clean synthetic scenario A).
Two independently-correct-within-tolerance estimates can still differ from
each other by up to ~23% in the worst case by simple error addition, and
real noisy data is messier than the clean synthetic. 40% leaves headroom
for that without diluting past the point of catching a real discrepancy
like the M5.8's (>200%).

No R² floor gates the onset side of this check — tried and discarded
during A10. An early attempt (`onset_agreement_min_r2=0.15`) rejected
healthy confirmations on real Ridgecrest noise where injected events had
`v_onset` within 1% of ground truth but `R²=0.03`. Theil-Sen is a robust
estimator specifically because it tolerates noisy per-channel picks
without the *slope* breaking; a low R² measures scatter around the fitted
line, not whether the slope itself is trustworthy. The corroboration
criterion is velocity agreement, not fit quality.

## Consequences
- `CoherenceResult.v_app_onset_mps`/`onset_fit_r2` are now load-bearing
  for confirmation, not just diagnostic fields — an event with too few
  channels for the onset fit (`onset_fit_min_channels`, default 30) cannot
  reach `SISMO_CONFIRMADO` via this path even if semblance alone looks
  clean.
- `run_validation.py` scenario I is a permanent regression guard
  specifically for "boundary guard passes, concordance gate must still
  catch it" — deleting or weakening this gate would silently reopen that
  failure mode without any other check noticing.
- Combined with ADR 0010, this is why the project's real-event scoreboard
  currently stands at 0/16 `HIT`: both real events that ever reached
  `SISMO_CONFIRMADO` (Ridgecrest M5.8, East Foothills M4.1) had a
  boundary-pinned and/or concordance-failing velocity, and both guards
  independently reject them.
