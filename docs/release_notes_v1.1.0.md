# darkfiber v1.1.0

A follow-up validation pass that found its own published claim was wrong,
built the guards that caught it, and now reports 0 confirmed earthquakes
out of 16 real events instead of 1 — which is the actual evidence this
system works as designed.

## The headline: we retracted our own v1.0.0 result

v1.0.0 reported one confirmed local earthquake (East Foothills M4.1,
"2.8s before the USGS origin"). It was wrong, and we found out why
ourselves, on our own initiative, before anyone outside the project
raised it. Two independent problems, found in sequence:

1. **A fusion artifact.** The reported block merged the real arrival with
   ~12s of unrelated prior activity — density re-segmentation isolates
   the real 13.5s core, which actually starts 9.3s *after* the origin,
   consistent with real P/S travel time. "Before the earthquake" was
   never physically possible; it was a block-merging bug.
2. **A grid-boundary non-measurement.** The reported apparent velocity
   (8,000 m/s) was exactly the edge of the search grid, not an interior
   optimum — the same pattern that had already invalidated a separate
   apparent confirmation (the Ridgecrest M5.8). A monotonically-rising
   semblance curve pinned to a grid edge means the true velocity is
   outside the swept range, not that the edge value is correct.

Both events are now `POSIBLE_REGIONAL_EMERGENTE` — honestly
unresolved, not falsely confirmed. Full account:
[`docs/writeup.md`](writeup.md) §6, or [`CHANGELOG.md`](../CHANGELOG.md).

## New: two independent guards that make confirmation harder to earn

- **Boundary-solution guard**: a semblance argmax sitting on the edge of
  the swept velocity grid is flagged (`boundary_pinned=True`) and cannot
  by itself support `SISMO_CONFIRMADO`.
- **Cross-estimator concordance gate**: confirmation now also requires an
  independent onset-velocity estimate (Theil-Sen regression on per-channel
  STA/LTA crossings) to agree with the semblance-based velocity within
  40% — catching interior-but-wrong peaks the boundary guard alone
  cannot.

See [`docs/adr/0010`](adr/0010-boundary-solution-guard.md) and
[`docs/adr/0011`](adr/0011-cross-estimator-concordance.md).

## Also new

- **Causal, asymmetric ground-truth matching** (a detection cannot start
  before the earthquake that caused it) and a **`MISS_BELOW_FLOOR` vs
  `MISS_SUPPRESSED` split** in the validation harness, so "this array
  never saw a candidate" (consistent with being below the detection
  floor) is distinguished from "the engine saw something and lost it"
  (a real classification bug). See [`docs/adr/0008`](adr/0008-causal-asymmetric-matching.md)
  and [`docs/adr/0009`](adr/0009-miss-suppressed-vs-below-floor.md).
- **Density re-segmentation** of merged Tier0 blocks, fixing event fusion
  found on real Ridgecrest data (and, retroactively, the East Foothills
  file above).
- **Per-array Tier0 calibration**, evidence-gated: `calibrate.py` now
  proposes a per-array STA/LTA threshold from real noise-floor evidence
  and refuses to propose anything that would break an existing confirmed
  HIT. Ridgecrest North's threshold (4.0 → 8.0) is the one calibration
  that survived this bar.
- **`snr_curve.py`**: recall-vs-SNR measured against each array's own
  real background noise, with Wilson 95% confidence intervals and an
  SNR50 summary — replaces an earlier fixed-4-point self-test that had
  been silently measuring the wrong thing.
- **The validation sample nearly tripled and mostly stopped being
  hand-picked**: from 4 hand-picked real events across 2 arrays in
  v1.0.0, to 43 real files across 4 arrays (16 ground-truth-matched, 27
  as a false-alarm check), 13 of the 16 drawn from a sample pre-registered
  *before* any result was seen (`sample_plan.md`) — the selection-bias
  debt v1.0.0 declared is now mostly, not fully, paid down.
- **Full technical writeup**: [`docs/writeup.md`](writeup.md) (English,
  canonical) / [`docs/writeup.es.md`](writeup.es.md) (Spanish, courtesy
  translation) — the complete methodology, results matrix, and the two
  retracted cases as a case study, every number traced to its source in
  [`docs/writeup_data.md`](writeup_data.md).

## Validated on real data — the honest result

**0 of 16** real, ground-truth-matched events reached `SISMO_CONFIRMADO`.
8 correctly flagged as weak-but-present (`HONEST_UNKNOWN`), 2 as
regional/emergent arrivals beyond the array's resolving aperture
(`HONEST_REGIONAL`), 6 below the array's measured detection floor
(`MISS_BELOW_FLOOR`) — and zero cases where the engine saw a real signal
and discarded it wrongly (`MISS_SUPPRESSED = 0`). Plus 27/27 correct
rejections on files with no cataloged event, 0 false alarms. Full matrix:
[`validacion_real/scoreboard.md`](../validacion_real/scoreboard.md).

This is a small sample (N=16) — the Wilson 95% confidence intervals are
correspondingly wide, reported as measured, not smoothed. See the
"Honesty box" in the README, and [`docs/writeup.md`](writeup.md) §7 for
known limits, including an open question the data doesn't resolve: why
both real near-miss events pinned to a grid boundary instead of showing
a noisy-but-interior peak, unlike the clean synthetic sweeps.

## Upgrading

No breaking API changes from v1.0.0. `EventClass` and `OutcomeLabel`
values are unchanged; `CoherenceResult` gained `v_app_onset_mps`,
`onset_fit_r2`, and `boundary_pinned` fields (additive). If you were
relying on the v1.0.0 East Foothills M4.1 result as a confirmed
detection, stop — see the retraction above.

## Full changelog

See [`CHANGELOG.md`](../CHANGELOG.md), `[1.1.0]`.
