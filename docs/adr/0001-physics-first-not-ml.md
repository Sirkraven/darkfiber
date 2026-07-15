# 0001 — Physics-first coherence, not a per-channel ML classifier

## Status
Accepted.

## Context
The predecessor system (v4) ran a CNN independently on every channel's
spectrogram. It worked, but had a structural failure mode: a single noisy
channel could produce a confident "earthquake" prediction with no way to
check it against what the rest of the array saw. In practice this showed
up as a ~5% per-channel false-positive rate on real deployments — noise
that *looked* seismic to a model trained on individual spectrograms, but
that a human glancing at the full channel-time plane would dismiss in a
second, because a real earthquake crosses hundreds of channels almost at
once and a transient in one fiber segment doesn't.

## Decision
Treat the whole array as **one instrument**, and classify events by
measuring the physics of how they move across it: slant-stack semblance
for wavefront velocity, coincidence fraction for "did this hit everywhere
at once", trajectory regression for slow-moving sources (vehicles). A CNN
or other ML classifier can still say "this spectrogram looks like an
earthquake" — but that verdict only escalates when the array-wide
coherence measurement agrees that it *propagates* like one. See
`coherence.py`'s module docstring for the three independent, physically
grounded measurements this is built on.

## Consequences
- Every verdict carries `explanations`: physical quantities (velocity,
  semblance, coincidence fraction), not a bare softmax score. A human can
  audit the reasoning without touching the model weights.
- The system can be validated against synthetic scenarios with exact known
  ground truth (`run_validation.py`) *before* any real training data
  exists — the physics doesn't need labeled examples to be correct.
- It also means the system can be *wrong* in a new way: physically
  coherent but unclassifiable events (see ADR 0002) needed a class that
  doesn't exist in a pure ML-classifier design, because "confidence
  score too low" and "confidently propagating like something we don't
  have a category for" are different failure modes.
- Cost: this is slower to adapt to genuinely novel signal types than
  retraining a classifier, since new physics (e.g. a new source
  geometry) needs a new branch in the decision tree, not just new labels.
  The signature catalog (`catalog.py`) exists to soften that — recurring
  unknowns get flagged for a human to name, without retraining anything.
