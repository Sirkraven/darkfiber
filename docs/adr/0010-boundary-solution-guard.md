# 0010 — A grid-boundary semblance maximum is a non-measurement

## Status
Accepted. Found on real data (A9), invalidated a previously-published HIT.

## Context
Apparent velocity is measured by slant-stack semblance over a swept grid
(`np.geomspace(seismic_v_min_mps, seismic_v_max_mps, n_velocity_steps)`,
default 1500-8000 m/s). The real Ridgecrest M5.8 event's reported
`apparent_velocity_mps` was `-8000.0` — not a value near 8000, but
*exactly* `seismic_v_max_mps`, the upper edge of the swept range. Plotting
the full semblance-vs-velocity curve (not just the argmax) showed why:
semblance rose monotonically across the entire grid with no interior peak,
meaning the true optimum lies outside the swept range entirely. The number
`8000` wasn't a measurement of the event's velocity; it was where the
sweep stopped. The same exact pattern (`-1500.0 = seismic_v_min_mps`)
later turned up on the East Foothills M4.1 file once A5's re-segmentation
isolated its real dense core — the 1.0.0 release's one confirmed HIT had
the identical pathology.

## Decision
`coherence._velocity_peak_is_boundary()` checks whether the semblance
argmax sits on the edge of its branch of the grid (or isn't a strict
interior peak) and sets `CoherenceResult.boundary_pinned = True` when it
does. A boundary-pinned result can no longer, by itself, produce
`SISMO_CONFIRMADO` — `apparent_velocity_mps` in that state is not a
resolved measurement, regardless of how high the semblance value is.

## Consequences
- This is a necessary but not sufficient guard: `run_validation.py`
  scenario I (a synthetic "distant/fast" event) constructs a case where
  the argmax lands one step *inside* the boundary
  (`boundary_pinned=False`) while still being physically wrong — the
  boundary check alone doesn't catch that. See ADR 0011 for the second,
  independent layer that does.
- Boundary-pinned results are not discarded, just downgraded — they still
  carry their `explanations` and get surfaced as `POSIBLE_REGIONAL_EMERGENTE`
  when the coincidence/span criteria for that class are met (ADR 0002),
  rather than silently vanishing.
- Retroactive audit gap, handled explicitly rather than hidden: ledger
  rows scored `HIT` before A9 have `metrics_json` predating the
  `boundary_pinned` field, so they cannot be mechanically re-checked
  against this guard without re-reading the raw data. `run_on_quakeflow.py`
  now flags any such un-reverified `HIT` row explicitly in scoreboard
  output instead of presenting it as validated.
- `seismic_v_min_mps`/`seismic_v_max_mps` remain configurable, but this
  guard means widening the grid is now the correct response to a
  boundary-pinned real event, not raising confidence in the pinned value.
