# 0008 — Causal, asymmetric ground-truth matching window

## Status
Accepted. Found and fixed on real data (A6).

## Context
The QuakeFlow validation harness (`run_on_quakeflow.py`) scores a Tier0
candidate against a catalogued origin by checking whether the candidate
falls inside a tolerance window around `event_time_index`. The original
window was symmetric: `[origin - tol, origin + tol]`. That's wrong on
physical grounds — a real detection cannot begin before the earthquake
that caused it, there is no causality running backwards. A symmetric
window can match a Tier0 candidate that starts near the catalogued origin
by coincidence, with no causal relationship to it, and count it as a HIT
or a MISS for the wrong reason.

## Decision
Matching now uses `[origin, origin + causal_margin_s]` — a one-sided
window (`causal_margin_s`, `run_on_quakeflow.py`). The margin comes from
expected travel time of the slowest reasonable regional/surface phase
(`MIN_REGIONAL_VELOCITY_MPS = 2000 m/s`) over the epicentral distance when
known; QuakeFlow DAS files don't currently populate `distance_km`, so a
documented fixed ceiling (`DEFAULT_MAX_TRAVEL_MARGIN_S = 60.0`, chosen
generously against the real M5.8 Ridgecrest observation of 16.8 s
origin-to-burst) applies instead. Among multiple candidates inside the
causal window, the one with the most triggered channels is selected —
picking by smallest time gap (the pre-A6 rule) could grab a one-channel
spurious pick over the real, array-wide event.

## Consequences
- Every real detection's `dt_detect_s` in the ledger is now non-negative
  by construction (time since origin, not signed offset) — a negative
  `dt_detect_s` would mean a detection before its cause, which the
  matching logic can no longer produce.
- This directly falsified the original East Foothills M4.1 "2.8 s before
  the origin" claim from the 1.0.0 release: under causal matching, that
  claim is impossible by construction. Re-running showed the "before"
  read was a block-fusion artifact (ADR-adjacent, see CHANGELOG
  `[Unreleased]` — A5 re-segmentation), not a real causality violation.
- Enables the `MISS_BELOW_FLOOR` vs `MISS_SUPPRESSED` split (ADR 0009):
  without a well-defined causal window, "no candidate in the window" and
  "candidate outside the window discarded" aren't distinguishable.
