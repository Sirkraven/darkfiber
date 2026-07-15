# 0007 — Recall should be reported as a curve with confidence intervals, not a scalar

## Status
Accepted as a principle. **Not yet implemented** — documented honestly
below; today's implementation is the scalar in Consequences.

## Context
`selftest.recall_gauge()` reports the fraction of synthetic injections that
were both detected and classified as a confirmed earthquake. In this
project's own validation runs, that number comes from five injections at
five different (velocity, SNR) pairs — e.g. "80% (4/5 inyecciones)". A
single scalar from n=5 trials invites a reader to treat 80% as a precise,
stable measurement of detection capability. It isn't: with five trials,
the binomial confidence interval around 80% is wide enough that the true
recall could plausibly be anywhere from around 40% to nearly 100%. Worse,
a single scalar hides the actual shape of the thing that matters
operationally: recall isn't constant across SNR, it's a curve that's near
100% at high SNR and falls off approaching the detection threshold — and
*where* it falls off, and how sharply, is the number an operator actually
needs to size alerting thresholds.

## Decision
The target metric for detection capability is a **recall-vs-SNR curve with
confidence intervals** (and, where the sample supports it, an SNR50 — the
SNR at which recall crosses 50%), not a single scalar. `run_on_quakeflow.py`
already accumulates real-world outcomes into a ledger that grows with every
run (`ledger` table, `HIT`/`HONEST_UNKNOWN`/etc.) — the same accumulation
principle applies to the synthetic self-test: more injections across a
denser SNR grid, per array (since noise floor differs per array — see
`array_profiles.synth_recall`), converging toward a curve instead of a
point estimate.

## Consequences
- **Honesty check**: today, `recall_gauge()` and the per-array
  `synth_recall` in `array_profiles` are both scalars from small samples
  (5 injections in `run_validation.py`; 4 in
  `run_on_quakeflow.run_array_selftest`). Neither reports a confidence
  interval. This ADR documents the target, not the current state — the
  scalar is what ships in 1.0.0.
- Building the curve is mostly a sample-size problem, not an algorithmic
  one: `selftest.inject_and_verify` already takes arbitrary
  `(v_app_mps, snr)` pairs, so a denser sweep plus a Wilson or Jeffreys
  interval per SNR bucket is additive work, not a redesign.
- Any PR that reports a recall number in a README, a release note, or a
  scoreboard should show the sample size next to it (as this changelog and
  `validacion_real/NOTES.md` do) until the curve exists.
