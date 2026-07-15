# 0002 — A fifth verdict class: `POSIBLE_REGIONAL_EMERGENTE`

## Status
Accepted. Fixed a real bug found on real data.

## Context
A real M5.8 earthquake (Ridgecrest array, QuakeFlow DAS dataset) energized
93% of the array almost simultaneously — clearly not noise, clearly not a
single-channel artifact — but its waveform-shape semblance was ≈0.001,
because at that distance and with that array's ~9 km aperture, the arrival
is a broad, decorrelated wave train, not a coherent plane-wave front. The
pipeline classified it `INCOHERENTE_LOCAL_SUPRIMIDO` — "suppressed local
false positive". A monitoring system that suppresses a real, large
earthquake has its worst possible failure mode, and it did so for a
physically explicable, entirely predictable reason: the suppression branch
only checked `n_coh` (channels correlated with the beam, which collapses
to ~0 for a genuinely decorrelated arrival), never the *extent* of the
trigger. See `characterize_aperture.py` for the sweep that shows this
low-semblance-despite-real-signal regime is not an edge case — it's what
happens whenever an array's aperture is short relative to the distance to
a real source.

## Decision
The suppression branch is now unreachable whenever `coincidence_fraction`
or `span_fraction` exceeds 0.5 — energy that wide is never a single-point
transient, full stop, regardless of what semblance says. Events that reach
that bar without confirming as a local earthquake (semblance too low,
apparent velocity out of the confirmable band) get a new verdict,
`POSIBLE_REGIONAL_EMERGENTE`, with an explicit "escalate for external
verification" explanation and — where possible — a fallback velocity
estimate via robust onset regression (ADR 0005).

## Consequences
- The verdict space grew from 4 to 5 classes; every consumer of
  `EventClass` needs to handle the new one (checked via `OutcomeLabel`
  mapping in the QuakeFlow harness: `HONEST_REGIONAL`).
- This is deliberately *not* folded into `COHERENTE_DESCONOCIDO`: an
  unclassified-but-coherent signal in a small footprint (candidate for the
  signature catalog) and a massive regional/distant arrival that a human
  needs to check against a seismic network are different operational
  situations and deserve different alerting.
- `characterize_aperture.py` exists so this class's rationale — "this
  array's aperture cannot resolve this event's moveout" — is a documented,
  reproducible curve per array, not a fact rediscovered every time a new
  real event surprises the on-call engineer.
